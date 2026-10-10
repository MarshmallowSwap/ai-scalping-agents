"""Scheduler: esegue il ciclo Analyst -> Decision -> Risk -> Suggest ogni N secondi.

Modalita':
  - dry-run (default): produce proposte, le salva nel journal, NON esegue
  - execute          : esegue le proposte approvate (senza prompt interattivo)

Uso:
  python -m src.tools.scheduler                              # 300s, dry-run
  python -m src.tools.scheduler --interval 60                # 60s
  python -m src.tools.scheduler --symbols BTC,ETH            # solo BTC e ETH
  python -m src.tools.scheduler --max-cycles 10              # si ferma dopo 10 cicli
  python -m src.tools.scheduler --execute --max-notional 50  # esegue (con policy)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import signal
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.agents.analyst import AnalystAgent
from src.agents.decision import DecisionAgent, TradeProposal
from src.agents.risk import RiskAgent
from src.brokers.co_invest import CoInvestClient

JOURNAL_PATH = Path("data/trades_journal.jsonl")
LOG_PATH = Path("data/scheduler.log")

logger = logging.getLogger("scheduler")


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def log_journal(entry: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_available_balance_from_text(text: str) -> float:
    m = re.search(r"\$([\d,]+\.?\d*)\s+available", text)
    return float(m.group(1).replace(",", "")) if m else 0.0


def extract_suggestion_json(result) -> dict | None:
    if isinstance(result, dict) and "order" in result:
        return result
    if isinstance(result, str):
        for line in reversed(result.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return None


async def single_cycle(
    client: CoInvestClient,
    symbols: list[str],
    timeframe: str,
    execute: bool,
    max_notional: float,
) -> None:
    analyst = AnalystAgent(client)
    decision = DecisionAgent(base_notional_usd=150.0, default_leverage=3)
    risk = RiskAgent(max_notional_per_trade=max_notional, max_leverage=3)

    portfolio = await client.get_portfolio()
    available = get_available_balance_from_text(str(portfolio))
    logger.info("Paper balance: $%.2f", available)

    for symbol in symbols:
        try:
            report = await analyst.analyze(symbol, interval=timeframe)
            prop = decision.decide(report)
            logger.info(
                "%s price=%.2f RSI=%.2f EMA20=%.0f EMA50=%.0f MACD=%.3f -> [%s] %s (conf %.2f)",
                symbol, report.price, report.rsi14, report.ema20, report.ema50,
                report.macd_hist, prop.setup, prop.side, prop.confidence,
            )

            if prop.side == "none":
                log_journal({
                    "event": "no_setup",
                    "symbol": symbol,
                    "report": {
                        "price": report.price, "rsi14": report.rsi14,
                        "ema20": report.ema20, "ema50": report.ema50,
                        "macd_hist": report.macd_hist, "atr14": report.atr14,
                    },
                })
                continue

            rd = risk.validate(prop, open_positions_count=0, available_balance_usd=available)
            if not rd.approved:
                logger.info("%s RIFIUTATO dal Risk Agent: %s", symbol, "; ".join(rd.reasons))
                log_journal({
                    "event": "risk_rejected",
                    "symbol": symbol,
                    "reasons": rd.reasons,
                    "proposal": {"side": prop.side, "size": prop.size_usd, "leverage": prop.leverage},
                })
                continue

            final_size = rd.final_size_usd
            final_lev = rd.final_leverage

            suggest_args = {
                "asset": symbol,
                "side": prop.side,
                "leverage": final_lev,
                "orderType": prop.order_type,
                "size": final_size,
                "reasoning": prop.reasoning,
            }
            if prop.take_profit is not None:
                suggest_args["takeProfit"] = prop.take_profit
            if prop.stop_loss is not None:
                suggest_args["stopLoss"] = prop.stop_loss

            result = await client.suggest_trade(**suggest_args)
            suggestion = extract_suggestion_json(result)

            if suggestion is None:
                logger.warning("%s: impossibile parsare la proposta", symbol)
                log_journal({"event": "suggest_parse_error", "symbol": symbol, "raw": str(result)[:500]})
                continue

            order = suggestion.get("order", {})
            logger.info(
                "%s PROPOSTA: %s size=$%.2f lev=%dx TP=%s SL=%s",
                symbol, order.get("side", "?").upper(),
                float(order.get("size", 0)), int(order.get("leverage", 1)),
                order.get("takeProfit"), order.get("stopLoss"),
            )

            if not execute:
                log_journal({
                    "event": "suggested_dry_run",
                    "symbol": symbol,
                    "suggestion": suggestion,
                })
                continue

            # Esecuzione (solo con --execute)
            idem = f"{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
            logger.info("%s ESECUZIONE (key=%s)", symbol, idem)
            try:
                exec_result = await client.execute_suggestion(suggestion, idempotency_key=idem)
                logger.info("%s ESITO: %s", symbol, str(exec_result)[:200])
                log_journal({
                    "event": "executed",
                    "symbol": symbol,
                    "idempotency_key": idem,
                    "suggestion": suggestion,
                    "result": exec_result if isinstance(exec_result, (dict, list, str)) else str(exec_result),
                })
            except Exception as e:
                logger.error("%s errore execute: %s", symbol, e)
                log_journal({"event": "execute_error", "symbol": symbol, "error": str(e)})

        except Exception as e:
            logger.exception("Errore durante il ciclo su %s: %s", symbol, e)


async def run_scheduler(
    symbols: list[str],
    interval_seconds: int,
    timeframe: str,
    execute: bool,
    max_notional: float,
    max_cycles: int,
) -> None:
    stop = asyncio.Event()

    def _handle_sigint():
        logger.info("Ricevuto Ctrl+C, chiudo al termine del ciclo corrente...")
        stop.set()

    # Gestione Ctrl+C
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_sigint)
            except NotImplementedError:
                # Windows non supporta add_signal_handler per SIGTERM
                pass
    except Exception:
        pass

    logger.info(
        "Scheduler avviato | symbols=%s | interval=%ss | timeframe=%s | execute=%s | max_notional=$%.2f",
        ",".join(symbols), interval_seconds, timeframe, execute, max_notional,
    )

    cycle_num = 0
    async with CoInvestClient() as client:
        while not stop.is_set():
            cycle_num += 1
            logger.info("---- Ciclo #%d ----", cycle_num)
            try:
                await single_cycle(client, symbols, timeframe, execute, max_notional)
            except Exception as e:
                logger.exception("Ciclo fallito: %s", e)

            if max_cycles > 0 and cycle_num >= max_cycles:
                logger.info("Raggiunto max-cycles=%d, esco.", max_cycles)
                break

            logger.info("Prossimo ciclo tra %d secondi...", interval_seconds)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass

    logger.info("Scheduler terminato dopo %d cicli.", cycle_num)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="BTC,ETH,SOL",
                        help="Lista di simboli separati da virgola")
    parser.add_argument("--interval", type=int, default=60,
                        help="Secondi tra un ciclo e il successivo (default 60)")
    parser.add_argument("--timeframe", default="1m",
                        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                        help="Timeframe per l'analisi tecnica (default 5m)")
    parser.add_argument("--execute", action="store_true",
                        help="Esegue le proposte approvate (default: dry-run)")
    parser.add_argument("--max-notional", type=float, default=50.0,
                        help="Notional massimo per trade in USD (default 50)")
    parser.add_argument("--max-cycles", type=int, default=0,
                        help="Numero massimo di cicli (0 = infinito)")
    args = parser.parse_args()

    setup_logging()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    try:
        asyncio.run(run_scheduler(
            symbols=symbols,
            interval_seconds=args.interval,
            timeframe=args.timeframe,
            execute=args.execute,
            max_notional=args.max_notional,
            max_cycles=args.max_cycles,
        ))
    except KeyboardInterrupt:
        logger.info("Interrotto manualmente.")


if __name__ == "__main__":
    main()
