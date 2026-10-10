"""Decision Agent: trasforma un report di analisi in una proposta di trade.

v0: regole deterministiche (nessun LLM). Facile da testare e debuggare.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from src.agents.analyst import AnalystAgent, AnalystReport
from src.brokers.co_invest import CoInvestClient

Side = Literal["long", "short", "none"]


@dataclass
class TradeProposal:
    symbol: str
    side: Side
    confidence: float          # 0.0 - 1.0
    size_usd: float            # notional in USD
    leverage: int
    order_type: str            # "market" o "limit"
    limit_price: float | None
    take_profit: float | None
    stop_loss: float | None
    reasoning: str
    analyst: AnalystReport | None = None


class DecisionAgent:
    """Regole semplici:
    - LONG se: RSI < 40 AND EMA20 > EMA50 AND MACD hist > 0
    - SHORT se: RSI > 65 AND EMA20 < EMA50 AND MACD hist < 0
    - Altrimenti: nessun trade (side='none')
    Size e SL/TP calcolati via ATR.
    """

    def __init__(self, base_notional_usd: float = 200.0, default_leverage: int = 3):
        self.base_notional_usd = base_notional_usd
        self.default_leverage = default_leverage

    def decide(self, report: AnalystReport) -> TradeProposal:
        rsi = report.rsi14
        ema20 = report.ema20
        ema50 = report.ema50
        macd_hist = report.macd_hist
        atr = report.atr14
        price = report.price

        side: Side = "none"
        confidence = 0.0
        reasons: list[str] = []

        if rsi < 40 and ema20 > ema50 and macd_hist > 0:
            side = "long"
            confidence = min(1.0, (40 - rsi) / 20 + 0.4)
            reasons.append(f"RSI {rsi:.1f} < 40 (ipervenduto)")
            reasons.append(f"EMA20 > EMA50 ({ema20:.0f} > {ema50:.0f})")
            reasons.append(f"MACD hist positivo ({macd_hist:.3f})")
        elif rsi > 65 and ema20 < ema50 and macd_hist < 0:
            side = "short"
            confidence = min(1.0, (rsi - 65) / 20 + 0.4)
            reasons.append(f"RSI {rsi:.1f} > 65 (ipercomprato)")
            reasons.append(f"EMA20 < EMA50 ({ema20:.0f} < {ema50:.0f})")
            reasons.append(f"MACD hist negativo ({macd_hist:.3f})")
        else:
            reasons.append(
                f"Nessun setup valido: RSI {rsi:.1f}, EMA20 {ema20:.0f}, "
                f"EMA50 {ema50:.0f}, MACD hist {macd_hist:.3f}"
            )

        # SL/TP basati su ATR (solo se c'e' un trade)
        if side == "none":
            sl = None
            tp = None
            size_usd = 0.0
        else:
            sl_dist = 1.5 * atr
            tp_dist = 3.0 * atr
            if side == "long":
                sl = round(price - sl_dist, 2)
                tp = round(price + tp_dist, 2)
            else:
                sl = round(price + sl_dist, 2)
                tp = round(price - tp_dist, 2)
            size_usd = self.base_notional_usd * (0.5 + confidence / 2)

        return TradeProposal(
            symbol=report.symbol,
            side=side,
            confidence=round(confidence, 2),
            size_usd=round(size_usd, 2),
            leverage=self.default_leverage,
            order_type="market",
            limit_price=None,
            take_profit=tp,
            stop_loss=sl,
            reasoning=" | ".join(reasons),
            analyst=report,
        )


async def _demo() -> None:
    async with CoInvestClient() as c:
        analyst = AnalystAgent(c)
        decision = DecisionAgent(base_notional_usd=200.0, default_leverage=3)

        for symbol in ["BTC", "ETH", "SOL"]:
            report = await analyst.analyze(symbol, interval="5m")
            prop = decision.decide(report)
            print(f"\n=== {symbol} ===")
            print(f"Price: {report.price}  RSI: {report.rsi14:.2f}  "
                  f"EMA20: {report.ema20:.0f}  EMA50: {report.ema50:.0f}  "
                  f"MACD hist: {report.macd_hist:.3f}")
            print(f"Side: {prop.side}  Confidence: {prop.confidence}  "
                  f"Size: ${prop.size_usd}  Lev: {prop.leverage}x")
            print(f"SL: {prop.stop_loss}  TP: {prop.take_profit}")
            print(f"Reasoning: {prop.reasoning}")


if __name__ == "__main__":
    asyncio.run(_demo())
