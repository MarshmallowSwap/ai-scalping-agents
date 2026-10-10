"""Decision Agent v1: 4 setup alternativi (2 mean-reversion + 2 trend-following).

Facile da testare e debuggare. Le regole LLM-based arriveranno in v2.
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
    confidence: float
    size_usd: float
    leverage: int
    order_type: str
    limit_price: float | None
    take_profit: float | None
    stop_loss: float | None
    reasoning: str
    setup: str = "none"
    analyst: AnalystReport | None = None


class DecisionAgent:
    """Regole v1: 4 setup alternativi.

    Mean reversion:
      - MR_LONG  : RSI < 35
      - MR_SHORT : RSI > 70
    Trend following:
      - TF_LONG  : EMA20 > EMA50 AND MACD hist > 0 AND price > EMA20
      - TF_SHORT : EMA20 < EMA50 AND MACD hist < 0 AND price < EMA20

    Size e SL/TP basati su ATR.
    """

    def __init__(self, base_notional_usd: float = 200.0, default_leverage: int = 3):
        self.base_notional_usd = base_notional_usd
        self.default_leverage = default_leverage

    def _evaluate(self, report: AnalystReport) -> tuple[Side, str, float, list[str]]:
        rsi = report.rsi14
        ema20 = report.ema20
        ema50 = report.ema50
        macd = report.macd_hist
        price = report.price

        # --- Mean reversion ---
        if rsi < 35:
            conf = min(1.0, (35 - rsi) / 20 + 0.4)
            return "long", "MR_LONG", conf, [
                f"RSI {rsi:.1f} < 35 (ipervenduto)",
                f"MACD hist {macd:.3f}",
            ]
        if rsi > 70:
            conf = min(1.0, (rsi - 70) / 20 + 0.4)
            return "short", "MR_SHORT", conf, [
                f"RSI {rsi:.1f} > 70 (ipercomprato)",
                f"MACD hist {macd:.3f}",
            ]

        # --- Trend following ---
        if ema20 > ema50 and macd > 0 and price > ema20:
            spread_pct = (ema20 - ema50) / ema50 * 100
            conf = min(1.0, spread_pct * 20 + 0.3)
            return "long", "TF_LONG", conf, [
                f"EMA20 > EMA50 ({ema20:.0f} > {ema50:.0f}, +{spread_pct:.3f}%)",
                f"MACD hist positivo ({macd:.3f})",
                f"Prezzo sopra EMA20 ({price:.0f} > {ema20:.0f})",
            ]
        if ema20 < ema50 and macd < 0 and price < ema20:
            spread_pct = (ema50 - ema20) / ema50 * 100
            conf = min(1.0, spread_pct * 20 + 0.3)
            return "short", "TF_SHORT", conf, [
                f"EMA20 < EMA50 ({ema20:.0f} < {ema50:.0f}, -{spread_pct:.3f}%)",
                f"MACD hist negativo ({macd:.3f})",
                f"Prezzo sotto EMA20 ({price:.0f} < {ema20:.0f})",
            ]

        return "none", "NONE", 0.0, [
            f"Nessun setup: RSI={rsi:.1f}, EMA20={ema20:.0f}, EMA50={ema50:.0f}, MACD={macd:.3f}"
        ]

    def decide(self, report: AnalystReport) -> TradeProposal:
        side, setup, confidence, reasons = self._evaluate(report)
        price = report.price
        atr = report.atr14

        if side == "none":
            return TradeProposal(
                symbol=report.symbol, side="none", confidence=0.0, size_usd=0.0,
                leverage=self.default_leverage, order_type="market", limit_price=None,
                take_profit=None, stop_loss=None, reasoning=" | ".join(reasons),
                setup=setup, analyst=report,
            )

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
            symbol=report.symbol, side=side, confidence=round(confidence, 2),
            size_usd=round(size_usd, 2), leverage=self.default_leverage,
            order_type="market", limit_price=None, take_profit=tp, stop_loss=sl,
            reasoning=" | ".join(reasons), setup=setup, analyst=report,
        )


async def _demo() -> None:
    async with CoInvestClient() as c:
        analyst = AnalystAgent(c)
        decision = DecisionAgent(base_notional_usd=150.0, default_leverage=3)

        for symbol in ["BTC", "ETH", "SOL"]:
            report = await analyst.analyze(symbol, interval="1m")
            prop = decision.decide(report)
            print(f"\n=== {symbol} ===")
            print(f"Price: {report.price}  RSI: {report.rsi14:.2f}  "
                  f"EMA20: {report.ema20:.0f}  EMA50: {report.ema50:.0f}  "
                  f"MACD: {report.macd_hist:.3f}")
            print(f"Setup: {prop.setup}  Side: {prop.side}  Conf: {prop.confidence}")
            print(f"Size: ${prop.size_usd}  SL: {prop.stop_loss}  TP: {prop.take_profit}")
            print(f"Reasoning: {prop.reasoning}")


if __name__ == "__main__":
    asyncio.run(_demo())
