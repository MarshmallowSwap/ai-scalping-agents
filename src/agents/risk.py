"""Risk Agent: valida le proposte di trade contro limiti di rischio hard-coded."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.agents.decision import DecisionAgent, TradeProposal
from src.agents.analyst import AnalystAgent
from src.brokers.co_invest import CoInvestClient


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str]
    final_size_usd: float
    final_leverage: int


class RiskAgent:
    """Regole di rischio:
    - max_notional_per_trade: importo massimo in USD per singolo trade
    - max_leverage: leva massima consentita
    - max_open_positions: numero massimo di posizioni contemporanee
    - max_confidence_required: sotto questa soglia non si trada
    - min_distance_sl_atr: lo stop loss deve essere almeno X * ATR
    """

    def __init__(
        self,
        max_notional_per_trade: float = 300.0,
        max_leverage: int = 5,
        max_open_positions: int = 3,
        min_confidence: float = 0.3,
        min_sl_atr_multiple: float = 1.0,
    ):
        self.max_notional_per_trade = max_notional_per_trade
        self.max_leverage = max_leverage
        self.max_open_positions = max_open_positions
        self.min_confidence = min_confidence
        self.min_sl_atr_multiple = min_sl_atr_multiple

    def validate(
        self,
        proposal: TradeProposal,
        open_positions_count: int = 0,
        available_balance_usd: float = 0.0,
    ) -> RiskDecision:
        reasons: list[str] = []

        # 1) Nessun trade -> rifiutato
        if proposal.side == "none":
            return RiskDecision(False, ["Nessun setup di trading"], 0.0, proposal.leverage)

        # 2) Confidenza minima
        if proposal.confidence < self.min_confidence:
            reasons.append(
                f"Confidenza {proposal.confidence:.2f} < {self.min_confidence}"
            )

        # 3) Limite posizioni aperte
        if open_positions_count >= self.max_open_positions:
            reasons.append(
                f"Posizioni aperte {open_positions_count} >= {self.max_open_positions}"
            )

        # 4) Size: cap al massimo consentito
        final_size = min(proposal.size_usd, self.max_notional_per_trade)
        if final_size < proposal.size_usd:
            reasons.append(
                f"Size ridotta da ${proposal.size_usd} a ${final_size} "
                f"(max ${self.max_notional_per_trade})"
            )

        # 5) Leva: cap al massimo consentito
        final_lev = min(proposal.leverage, self.max_leverage)
        if final_lev < proposal.leverage:
            reasons.append(
                f"Leva ridotta da {proposal.leverage}x a {final_lev}x "
                f"(max {self.max_leverage}x)"
            )

        # 6) Margine disponibile
        required_margin = final_size / final_lev if final_lev > 0 else float("inf")
        if available_balance_usd > 0 and required_margin > available_balance_usd:
            reasons.append(
                f"Margine richiesto ${required_margin:.2f} > disponibile "
                f"${available_balance_usd:.2f}"
            )
            return RiskDecision(False, reasons, final_size, final_lev)

        # 7) Distanza SL minima in ATR
        if proposal.analyst and proposal.stop_loss is not None:
            atr = proposal.analyst.atr14
            sl_dist = abs(proposal.analyst.price - proposal.stop_loss)
            min_dist = self.min_sl_atr_multiple * atr
            if sl_dist < min_dist:
                reasons.append(
                    f"SL troppo vicino ({sl_dist:.2f} < {min_dist:.2f} = "
                    f"{self.min_sl_atr_multiple}*ATR)"
                )

        approved = not any(">=" in r or ">" in r or "troppo" in r for r in reasons)
        return RiskDecision(approved, reasons or ["OK"], final_size, final_lev)


async def _demo() -> None:
    async with CoInvestClient() as c:
        analyst = AnalystAgent(c)
        decision = DecisionAgent(base_notional_usd=200.0, default_leverage=3)
        risk = RiskAgent()

        portfolio = await c.get_portfolio()
        print("Portfolio attuale:")
        print(portfolio)
        print()

        for symbol in ["BTC", "ETH", "SOL"]:
            report = await analyst.analyze(symbol, interval="1m")
            prop = decision.decide(report)
            rd = risk.validate(prop, open_positions_count=0, available_balance_usd=10000.0)
            print(f"\n=== {symbol} ===")
            print(f"Side: {prop.side}  Conf: {prop.confidence}  "
                  f"Size proposta: ${prop.size_usd}  Lev: {prop.leverage}x")
            print(f"Approvato: {rd.approved}")
            print(f"Size finale: ${rd.final_size_usd}  Lev finale: {rd.final_leverage}x")
            print(f"Motivazioni: {'; '.join(rd.reasons)}")


if __name__ == "__main__":
    asyncio.run(_demo())
