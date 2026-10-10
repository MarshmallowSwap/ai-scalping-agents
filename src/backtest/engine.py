"""Motore di backtest event-driven con fee, slippage, funding, liquidazione.

Miglioramenti v2:
  - Liquidazione forzata se il margine si esaurisce (maintenance margin ~0.5%)
  - Funding rate applicato ogni 8h alle posizioni aperte
  - PnL calcolato sull'equity reale (no leva moltiplicata sul PnL)
  - Exit reason esplicite: 'tp', 'sl', 'signal', 'timeout', 'liq', 'end'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from src.backtest.strategies import get_signal

Side = Literal["long", "short"]

MAINTENANCE_MARGIN = 0.005  # 0.5%
FUNDING_INTERVAL_BARS_5M = 96  # 8h / 5m = 96 barre


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    side: Side
    entry_price: float
    exit_price: float
    size_usd: float
    leverage: int
    pnl_usd: float
    pnl_pct: float
    exit_reason: str
    bars_held: int
    funding_paid_usd: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    initial_balance: float = 10_000.0
    final_balance: float = 10_000.0
    total_fees_paid: float = 0.0
    total_funding_paid: float = 0.0
    liquidation_count: int = 0


class BacktestEngine:
    """Motore event-driven realistico.

    Parametri:
        fee_rate: commissione per lato (default 0.05%)
        slippage_bps: slippage in bps per lato (default 5)
        sl_atr_mult: distanza SL in ATR (default 1.5)
        tp_atr_mult: distanza TP in ATR (default 3.0)
        max_bars_held: timeout in barre (0 = nessuno)
        strategies: lista di strategie attive
        size_usd: notional per trade (default $50)
        leverage: leva (default 3x)
        funding_rate_per_8h: tasso funding medio per 8h (default 0.0001 = 0.01%)
    """

    def __init__(
        self,
        fee_rate: float = 0.0005,
        slippage_bps: float = 5.0,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
        max_bars_held: int = 60,
        strategies: list[str] | None = None,
        initial_balance: float = 10_000.0,
        size_usd: float = 50.0,
        leverage: int = 3,
        funding_rate_per_8h: float = 0.0001,
    ):
        self.fee_rate = fee_rate
        self.slippage = slippage_bps / 10_000.0
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.max_bars_held = max_bars_held
        self.strategies = strategies or ["tf_long", "tf_short"]
        self.initial_balance = initial_balance
        self.size_usd = size_usd
        self.leverage = leverage
        self.funding_rate_per_8h = funding_rate_per_8h

    def run(self, symbol: str, df: pd.DataFrame) -> BacktestResult:
        result = BacktestResult(symbol=symbol, initial_balance=self.initial_balance)
        balance = self.initial_balance

        position: dict | None = None
        bars_held = 0
        funding_bars_since = 0

        for i in range(200, len(df)):
            row = df.iloc[i]
            ts = df.index[i]

            # -------- GESTIONE POSIZIONE APERTA --------
            if position is not None:
                bars_held += 1
                exit_price = None
                reason = None
                funding_this_trade = 0.0

                # 1) Liquidazione (check prio alta)
                if position["side"] == "long":
                    liq_price = position["entry"] * (1 - 1.0 / self.leverage + MAINTENANCE_MARGIN)
                    if row["low"] <= liq_price:
                        exit_price = liq_price
                        reason = "liq"
                else:
                    liq_price = position["entry"] * (1 + 1.0 / self.leverage - MAINTENANCE_MARGIN)
                    if row["high"] >= liq_price:
                        exit_price = liq_price
                        reason = "liq"

                # 2) SL / TP
                if exit_price is None:
                    if position["side"] == "long":
                        if row["low"] <= position["sl"]:
                            exit_price = position["sl"]
                            reason = "sl"
                        elif row["high"] >= position["tp"]:
                            exit_price = position["tp"]
                            reason = "tp"
                    else:
                        if row["high"] >= position["sl"]:
                            exit_price = position["sl"]
                            reason = "sl"
                        elif row["low"] <= position["tp"]:
                            exit_price = position["tp"]
                            reason = "tp"

                # 3) Segnale opposto
                if exit_price is None:
                    sig = get_signal(row, self.strategies)
                    if sig is not None and sig != position["side"]:
                        exit_price = row["close"]
                        reason = "signal"

                # 4) Timeout
                if exit_price is None and self.max_bars_held > 0 and bars_held >= self.max_bars_held:
                    exit_price = row["close"]
                    reason = "timeout"

                # --- Funding (applicato ogni FUNDING_INTERVAL_BARS) ---
                funding_bars_since += 1
                if funding_bars_since >= FUNDING_INTERVAL_BARS_5M:
                    funding_bars_since = 0
                    # Per LONG su funding positivo: paghi. Per SHORT: incassi.
                    notional = self.size_usd
                    if position["side"] == "long":
                        cost = notional * self.funding_rate_per_8h
                    else:
                        cost = -notional * self.funding_rate_per_8h
                    balance -= cost
                    result.total_funding_paid += cost
                    funding_this_trade += cost

                # --- Chiusura ---
                if exit_price is not None:
                    if position["side"] == "long":
                        fill = exit_price * (1 - self.slippage)
                        pnl_gross = (fill - position["entry"]) / position["entry"]
                    else:
                        fill = exit_price * (1 + self.slippage)
                        pnl_gross = (position["entry"] - fill) / position["entry"]

                    notional = self.size_usd
                    pnl_usd = notional * pnl_gross
                    fees = notional * self.fee_rate * 2
                    pnl_usd -= fees
                    balance += pnl_usd
                    result.total_fees_paid += fees

                    result.trades.append(Trade(
                        entry_time=position["entry_time"],
                        exit_time=ts,
                        symbol=symbol,
                        side=position["side"],
                        entry_price=position["entry"],
                        exit_price=fill,
                        size_usd=notional,
                        leverage=self.leverage,
                        pnl_usd=round(pnl_usd, 6),
                        pnl_pct=round(pnl_gross * 100, 4),
                        exit_reason=reason or "unknown",
                        bars_held=bars_held,
                        funding_paid_usd=round(funding_this_trade, 6),
                    ))
                    if reason == "liq":
                        result.liquidation_count += 1
                    position = None
                    bars_held = 0
                    funding_bars_since = 0

            # -------- NUOVO INGRESSO --------
            if position is None and not pd.isna(row["atr14"]) and row["atr14"] > 0:
                sig = get_signal(row, self.strategies)
                if sig is not None:
                    entry = row["close"]
                    if sig == "long":
                        entry_fill = entry * (1 + self.slippage)
                        sl = entry_fill - self.sl_atr_mult * row["atr14"]
                        tp = entry_fill + self.tp_atr_mult * row["atr14"]
                    else:
                        entry_fill = entry * (1 - self.slippage)
                        sl = entry_fill + self.sl_atr_mult * row["atr14"]
                        tp = entry_fill - self.tp_atr_mult * row["atr14"]

                    position = {
                        "side": sig,
                        "entry": entry_fill,
                        "sl": sl,
                        "tp": tp,
                        "entry_time": ts,
                    }
                    bars_held = 0
                    funding_bars_since = 0

            # -------- EQUITY CURVE --------
            unrealized = 0.0
            if position is not None:
                if position["side"] == "long":
                    pnl_gross = (row["close"] - position["entry"]) / position["entry"]
                else:
                    pnl_gross = (position["entry"] - row["close"]) / position["entry"]
                unrealized = self.size_usd * pnl_gross
            result.equity_curve.append((ts, balance + unrealized))

        result.final_balance = balance
        return result
