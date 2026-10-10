"""Orchestrator: ciclo Analyst -> Decision -> Risk -> Suggest -> (Execute)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.agents.analyst import AnalystAgent
from src.agents.decision import DecisionAgent, TradeProposal
from src.agents.risk import RiskAgent
from src.brokers.co_invest import CoInvestClient

SYMBOLS = ["BTC", "ETH", "SOL"]
INTERVAL = "1m"
JOURNAL_PATH = Path("data/trades_journal.jsonl")


def get_available_balance_from_text(text: str) -> float:
    m = re.search(r"\$([\d,]+\.?\d*)\s+available", text)
    return float(m.group(1).replace(",", "")) if m else 0.0


def force_test_proposal(symbol: str, price: float) -> TradeProposal:
    return TradeProposal(
        symbol=symbol,
        side="long",
        confidence=0.9,
        size_usd=50.0,
        leverage=3,
        order_type="market",
        limit_price=None,
        take_profit=round(price * 1.005, 2),
        stop_loss=round(price * 0.995, 2),
        reasoning="FORCE TEST: proposta costruita a mano per validare la pipeline",
        analyst=None,
    )


def log_journal(entry: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ask_confirmation(symbol: str, side: str, size: float, lev: int) -> bool:
    prompt = f"Confermi ESEGUIRE {side.upper()} {symbol} size=${size} lev={lev}x? [SI/no]: "
    ans = input(prompt).strip().lower()
    return ans in ("si", "s", "y", "yes")


async def run_cycle(force_test: bool = False, execute: bool = False) -> None:
    async with CoInvestClient() as client:
        analyst = AnalystAgent(client)
        decision = DecisionAgent(base_notional_usd=150.0, default_leverage=3)
        risk = RiskAgent(max_notional_per_trade=200.0, max_leverage=3)

        portfolio = await client.get_portfolio()
        available = get_available_balance_from_text(str(portfolio))
        print(f"Paper balance disponibile: ${available:.2f}\n")

        for symbol in SYMBOLS:
            print(f"===== {symbol} ({INTERVAL}) =====")

            report = await analyst.analyze(symbol, interval=INTERVAL)
            if force_test:
                prop = force_test_proposal(symbol, report.price)
                prop.analyst = report
                print(f"[FORCE TEST] price={report.price}")
            else:
                prop = decision.decide(report)
                print(f"Analyst: price={report.price}  RSI={report.rsi14:.2f}  "
                      f"MACD hist={report.macd_hist:.3f}")
                print(f"Decision: side={prop.side}  conf={prop.confidence}  "
                      f"size=${prop.size_usd}  lev={prop.leverage}x")

            rd = risk.validate(prop, open_positions_count=0, available_balance_usd=available)
            print(f"Risk: approved={rd.approved}  size=${rd.final_size_usd}  "
                  f"lev={rd.final_leverage}x")
            if rd.reasons:
                print(f"Risk reasons: {'; '.join(rd.reasons)}")

            if not rd.approved:
                print("-> Nessun trade proposto.\n")
                continue

            final_prop = TradeProposal(
                symbol=prop.symbol, side=prop.side, confidence=prop.confidence,
                size_usd=rd.final_size_usd, leverage=rd.final_leverage,
                order_type=prop.order_type, limit_price=prop.limit_price,
                take_profit=prop.take_profit, stop_loss=prop.stop_loss,
                reasoning=prop.reasoning, analyst=prop.analyst,
            )

            suggest_args = {
                "asset": final_prop.symbol,
                "side": final_prop.side,
                "leverage": final_prop.leverage,
                "orderType": final_prop.order_type,
                "size": final_prop.size_usd,
                "reasoning": final_prop.reasoning,
            }
            if final_prop.take_profit is not None:
                suggest_args["takeProfit"] = final_prop.take_profit
            if final_prop.stop_loss is not None:
                suggest_args["stopLoss"] = final_prop.stop_loss

            print(f"-> Chiamo suggest_trade per {final_prop.symbol} {final_prop.side}...")
            try:
                result = await client.suggest_trade(**suggest_args)
            except Exception as e:
                print(f"ERRORE suggest_trade: {e}\n")
                continue

            # suggest_trade restituisce spesso due blocchi: testo + JSON
            suggestion_json = None
            if isinstance(result, dict) and "order" in result:
                suggestion_json = result
            elif isinstance(result, str):
                # Prova a estrarre l'ultima riga JSON
                for line in reversed(result.splitlines()):
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            suggestion_json = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue

            if suggestion_json is None:
                print("Impossibile estrarre la proposta. Output grezzo:")
                print(str(result)[:500])
                print()
                continue

            order = suggestion_json.get("order", {})
            print(f"Suggestion: {order.get('side','?').upper()} {order.get('asset','?')} "
                  f"size=${order.get('size','?')} lev={order.get('leverage','?')}x "
                  f"| status={suggestion_json.get('status')} "
                  f"| mode={suggestion_json.get('executionMode')}")

            if not execute:
                print("-> Modalita' suggest-only. Aggiungi --execute per eseguire.\n")
                log_journal({"event": "suggested", "symbol": symbol, "suggestion": suggestion_json})
                continue

            if not ask_confirmation(
                order.get("asset", "?"),
                order.get("side", "?"),
                order.get("size", 0),
                order.get("leverage", 1),
            ):
                print("-> Annullato dall'utente.\n")
                log_journal({"event": "user_cancelled", "symbol": symbol, "suggestion": suggestion_json})
                continue

            idem_key = f"{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
            print(f"-> Eseguo (idempotencyKey={idem_key})...")
            try:
                exec_result = await client.execute_suggestion(suggestion_json, idempotency_key=idem_key)
                print("Execute result:")
                print(exec_result)
                log_journal({
                    "event": "executed",
                    "symbol": symbol,
                    "idempotency_key": idem_key,
                    "suggestion": suggestion_json,
                    "result": exec_result if isinstance(exec_result, (dict, list, str)) else str(exec_result),
                })
            except Exception as e:
                print(f"ERRORE execute_order: {e}")
                log_journal({"event": "execute_error", "symbol": symbol, "error": str(e)})

            print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-test", action="store_true",
                        help="Forza una proposta LONG per testare la pipeline")
    parser.add_argument("--execute", action="store_true",
                        help="Esegue le proposte approvate (richiede conferma interattiva)")
    args = parser.parse_args()
    asyncio.run(run_cycle(force_test=args.force_test, execute=args.execute))


if __name__ == "__main__":
    main()
