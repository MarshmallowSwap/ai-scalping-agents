"""Runtime: gestisce il loop asyncio e la connessione MCP persistente."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Coroutine

from src.brokers.co_invest import CoInvestClient


class Runtime:
    _instance: "Runtime | None" = None

    def __new__(cls) -> "Runtime":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="runtime-loop")
        self.thread.start()
        self.client: CoInvestClient | None = None
        self.scheduler_task: asyncio.Task | None = None
        self.scheduler_running = False
        self.scheduler_config: dict[str, Any] = {}
        self.log: deque[tuple[str, str]] = deque(maxlen=500)
        self.last_cycle_at: str | None = None
        self.cycle_count = 0

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_sync(self, coro: Coroutine, timeout: float = 60.0) -> Any:
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout=timeout)

    def ensure_client(self) -> CoInvestClient:
        if self.client is None:
            self.client = CoInvestClient()
            self.run_sync(self.client.start(), timeout=30.0)
        return self.client

    def log_line(self, level: str, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.log.appendleft((ts, f"[{level}] {msg}"))

    def start_scheduler(self, config: dict[str, Any]) -> None:
        if self.scheduler_running:
            return
        self.scheduler_config = dict(config)
        self.scheduler_running = True
        self.scheduler_task = asyncio.run_coroutine_threadsafe(
            self._scheduler_loop(), self.loop
        )
        self.log_line("INFO", "Scheduler avviato")

    def stop_scheduler(self) -> None:
        if not self.scheduler_running:
            return
        self.scheduler_running = False
        if self.scheduler_task is not None:
            self.loop.call_soon_threadsafe(self.scheduler_task.cancel)
            self.scheduler_task = None
        self.log_line("INFO", "Scheduler fermato")

    async def _scheduler_loop(self) -> None:
        from src.agents.analyst import AnalystAgent
        from src.agents.decision import DecisionAgent
        from src.agents.risk import RiskAgent

        try:
            client = self.ensure_client()
            while self.scheduler_running:
                cfg = self.scheduler_config
                symbols = cfg.get("symbols", ["BTC_USDT_PERP"])
                timeframe = cfg.get("timeframe", "5m")
                interval = cfg.get("interval", 300)
                execute = cfg.get("execute", False)
                max_notional = cfg.get("max_notional", 50.0)

                self.cycle_count += 1
                self.log_line("INFO", f"Ciclo #{self.cycle_count} avviato ({len(symbols)} simboli)")

                analyst = AnalystAgent(client)
                decision = DecisionAgent(base_notional_usd=150.0, default_leverage=3)
                risk = RiskAgent(max_notional_per_trade=max_notional, max_leverage=3)

                try:
                    portfolio = await client.get_portfolio()
                    import re
                    m = re.search(r"\$([\d,]+\.?\d*)\s+available", str(portfolio))
                    available = float(m.group(1).replace(",", "")) if m else 0.0
                except Exception as e:
                    self.log_line("ERR", f"Portfolio error: {e}")
                    available = 0.0

                for symbol in symbols:
                    try:
                        report = await analyst.analyze(symbol, interval=timeframe)
                        prop = decision.decide(report)

                        if prop.side == "none":
                            self.log_line("DEBUG", f"{symbol}: nessun setup")
                            continue

                        rd = risk.validate(prop, open_positions_count=0, available_balance_usd=available)
                        if not rd.approved:
                            self.log_line("WARN", f"{symbol}: rifiutato ({'; '.join(rd.reasons)})")
                            continue

                        self.log_line(
                            "SIGNAL",
                            f"{symbol} {prop.side.upper()} setup={prop.setup} conf={prop.confidence} "
                            f"size=${rd.final_size_usd} lev={rd.final_leverage}x",
                        )

                        if execute:
                            suggest_args = {
                                "asset": symbol, "side": prop.side,
                                "leverage": rd.final_leverage,
                                "orderType": prop.order_type,
                                "size": rd.final_size_usd,
                                "reasoning": prop.reasoning,
                            }
                            if prop.take_profit is not None:
                                suggest_args["takeProfit"] = prop.take_profit
                            if prop.stop_loss is not None:
                                suggest_args["stopLoss"] = prop.stop_loss
                            result = await client.suggest_trade(**suggest_args)
                            import json as _json
                            suggestion = None
                            if isinstance(result, dict) and "order" in result:
                                suggestion = result
                            elif isinstance(result, str):
                                for line in reversed(result.splitlines()):
                                    line = line.strip()
                                    if line.startswith("{") and line.endswith("}"):
                                        try:
                                            suggestion = _json.loads(line)
                                            break
                                        except Exception:
                                            continue
                            if suggestion:
                                import uuid
                                key = f"{symbol}-{uuid.uuid4().hex[:8]}"
                                await client.execute_suggestion(suggestion, idempotency_key=key)
                                self.log_line("EXEC", f"{symbol} ordine eseguito")
                    except Exception as e:
                        self.log_line("ERR", f"{symbol}: {e}")

                self.last_cycle_at = datetime.now(timezone.utc).strftime("%H:%M:%S")

                # Attesa interrompibile
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_line("ERR", f"Scheduler crash: {e}")
        finally:
            self.scheduler_running = False
            self.log_line("INFO", "Scheduler terminato")


runtime = Runtime()

# ===== Market data via ccxt (dati pubblici, no API key) =====

_ccxt_exchange = None

def _get_exchange():
    global _ccxt_exchange
    if _ccxt_exchange is None:
        import ccxt
        _ccxt_exchange = ccxt.binance({"enableRateLimit": True})
    return _ccxt_exchange


def fetch_candles(symbol: str, timeframe: str = "5m", limit: int = 200):
    """Scarica candele OHLCV da Binance (pubblico). Ritorna DataFrame."""
    import pandas as pd
    ex = _get_exchange()
    pair = f"{symbol}/USDT"
    try:
        raw = ex.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
    except Exception as e:
        raise RuntimeError(f"ccxt fetch_ohlcv error: {e}")
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("timestamp").drop(columns=["ts"])
    return df