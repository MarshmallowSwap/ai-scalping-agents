"""Motore di backtest event-driven con fee, slippage, TP/SL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from src.backtest.strategies import get_signal

Side = Literal["long", "short"]


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
    exit_reason: str  # "tp", "sl", "signal", "end"
    bars_held: int


@dataclass
class BacktestResult:
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    initial_balance: float = 10_000.0
    final_balance: float = 10_000.0
    total_fees_paid: float = 0.0


class BacktestEngine:
    """Motore event-driven.

    Parametri:
        fee_rate: commissione per lato (es. 0.0005 = 0.05%)
        slippage_bps: slippage in punti base per lato (es. 5 = 0.05%)
        sl_atr_mult: distanza SL in multipli di ATR
        tp_atr_mult: distanza TP in multipli di ATR
        max_bars_held: chiude forzatamente dopo N barre (0 = nessun limite)
        strategies: lista di strategie attive (es. ["tf_long", "tf_short"])
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

    def run(self, symbol: str, df: pd.DataFrame) -> BacktestResult:
        """Esegue il backtest su un DataFrame con indicatori già calcolati."""
        result = BacktestResult(symbol=symbol, initial_balance=self.initial_balance)
        balance = self.initial_balance

        position: dict | None = None
        bars_held = 0

        for i in range(200, len(df)):  # skip warmup indicatori
            row = df.iloc[i]
            ts = df.index[i]

            # ----- Gestione posizione aperta -----
            if position is not None:
                bars_held += 1
                exit_price = None
                reason = None

                if position["side"] == "long":
                    if row["low"] <= position["sl"]:
                        exit_price = position["sl"]
                        reason = "sl"
                    elif row["high"] >= position["tp"]:
                        exit_price = position["tp"]
                        reason = "tp"
                else:  # short
                    if row["high"] >= position["sl"]:
                        exit_price = position["sl"]
                        reason = "sl"
                    elif row["low"] <= position["tp"]:
                        exit_price = position["tp"]
                        reason = "tp"

                # Segnale di uscita opposto
                if exit_price is None:
                    sig = get_signal(row, self.strategies)
                    if sig is not None and sig != position["side"]:
                        exit_price = row["close"]
                        reason = "signal"

                # Timeout
                if exit_price is None and self.max_bars_held > 0 and bars_held >= self.max_bars_held:
                    exit_price = row["close"]
                    reason = "end"

                if exit_price is not None:
                    # Applica slippage in uscita
                    if position["side"] == "long":
                        fill = exit_price * (1 - self.slippage)
                        pnl_gross = (fill - position["entry"]) / position["entry"]
                    else:
                        fill = exit_price * (1 + self.slippage)
                        pnl_gross = (position["entry"] - fill) / position["entry"]

                    notional = self.size_usd
                    pnl_usd = notional * pnl_gross
                    fees = notional * self.fee_rate * 2  # entry + exit
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
                        pnl_usd=round(pnl_usd, 4),
                        pnl_pct=round(pnl_gross * 100, 4),
                        exit_reason=reason or "unknown",
                        bars_held=bars_held,
                    ))
                    position = None
                    bars_held = 0

            # ----- Nuovo ingresso -----
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

            # Equity curve
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
