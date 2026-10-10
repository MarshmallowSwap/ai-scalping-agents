"""Strategie di trading applicabili su un DataFrame OHLCV.

Versione v1: stessi segnali del Decision Agent live, ma su dati storici.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge tutti gli indicatori usati dalle strategie."""
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]

    out["rsi14"] = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_hist"] = macd.macd_diff()

    out["ema20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    out["ema50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    out["ema200"] = ta.trend.EMAIndicator(close, window=200).ema_indicator()

    out["atr14"] = ta.volatility.AverageTrueRange(
        high=high, low=low, close=close, window=14
    ).average_true_range()

    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    out["bb_upper"] = bb.bollinger_hband()
    out["bb_middle"] = bb.bollinger_mavg()
    out["bb_lower"] = bb.bollinger_lband()

    stoch = ta.momentum.StochasticOscillator(
        high=high, low=low, close=close, window=14, smooth_window=3
    )
    out["stoch_k"] = stoch.stoch()
    out["stoch_d"] = stoch.stoch_signal()

    return out


def signal_mr_long(row: pd.Series) -> bool:
    """Mean reversion long: RSI molto basso."""
    return row["rsi14"] < 35


def signal_mr_short(row: pd.Series) -> bool:
    """Mean reversion short: RSI molto alto."""
    return row["rsi14"] > 70


def signal_tf_long(row: pd.Series) -> bool:
    """Trend following long."""
    return (
        row["ema20"] > row["ema50"]
        and row["macd_hist"] > 0
        and row["close"] > row["ema20"]
    )


def signal_tf_short(row: pd.Series) -> bool:
    """Trend following short."""
    return (
        row["ema20"] < row["ema50"]
        and row["macd_hist"] < 0
        and row["close"] < row["ema20"]
    )


STRATEGIES = {
    "mr_long": signal_mr_long,
    "mr_short": signal_mr_short,
    "tf_long": signal_tf_long,
    "tf_short": signal_tf_short,
}


def get_signal(row: pd.Series, active: list[str]) -> str | None:
    """Ritorna 'long', 'short' o None in base alle strategie attive."""
    longs = [s for s in active if s.endswith("_long")]
    shorts = [s for s in active if s.endswith("_short")]

    for name in longs:
        if STRATEGIES[name](row):
            return "long"
    for name in shorts:
        if STRATEGIES[name](row):
            return "short"
    return None
