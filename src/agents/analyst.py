"""Analyst Agent: raccoglie dati di mercato e produce un report strutturato."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.brokers.co_invest import CoInvestClient


@dataclass
class AnalystReport:
    symbol: str
    price: float
    interval: str
    rsi14: float
    macd_hist: float
    ema20: float
    ema50: float
    ema200: float
    atr14: float
    bb_upper: float
    bb_lower: float
    bb_middle: float
    stoch_k: float
    stoch_d: float
    sma20: float
    sma50: float
    vwap: float
    market_summary: str
    raw_indicators: dict[str, Any] = field(default_factory=dict)


class AnalystAgent:
    def __init__(self, client: CoInvestClient):
        self.client = client

    async def analyze(self, symbol: str, interval: str = "5m") -> AnalystReport:
        indicators_raw = await self.client.get_technical_indicators(
            symbol=symbol, interval=interval
        )
        market_raw = await self.client.analyze_market(symbol)

        ind = indicators_raw["indicators"]
        report = AnalystReport(
            symbol=symbol,
            price=float(indicators_raw["currentPrice"]),
            interval=interval,
            rsi14=float(ind["rsi14"]),
            macd_hist=float(ind["macd"]["histogram"]),
            ema20=float(ind["ema"]["ema20"]),
            ema50=float(ind["ema"]["ema50"]),
            ema200=float(ind["ema"]["ema200"]),
            atr14=float(ind["atr14"]),
            bb_upper=float(ind["bollinger"]["upper"]),
            bb_lower=float(ind["bollinger"]["lower"]),
            bb_middle=float(ind["bollinger"]["middle"]),
            stoch_k=float(ind["stochastic"]["k"]),
            stoch_d=float(ind["stochastic"]["d"]),
            sma20=float(ind["sma"]["sma20"]),
            sma50=float(ind["sma"]["sma50"]),
            vwap=float(ind["vwap"]["value"]),
            market_summary=str(market_raw),
            raw_indicators=indicators_raw,
        )
        return report


async def _demo() -> None:
    async with CoInvestClient() as c:
        agent = AnalystAgent(c)
        report = await agent.analyze("BTC", interval="5m")
        print(f"Symbol: {report.symbol} @ {report.price}")
        print(f"RSI14: {report.rsi14:.2f}  MACD hist: {report.macd_hist:.4f}")
        print(f"EMA20/50/200: {report.ema20:.0f}/{report.ema50:.0f}/{report.ema200:.0f}")
        print(f"ATR14: {report.atr14:.2f}  VWAP: {report.vwap:.0f}")
        print(f"Stoch K/D: {report.stoch_k:.2f}/{report.stoch_d:.2f}")
        print(f"BB lower/mid/upper: {report.bb_lower:.0f}/{report.bb_middle:.0f}/{report.bb_upper:.0f}")


if __name__ == "__main__":
    asyncio.run(_demo())
