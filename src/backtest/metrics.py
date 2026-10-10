"""Metriche di performance per un backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult


def compute_metrics(r: BacktestResult) -> dict:
    trades = r.trades
    n = len(trades)
    if n == 0:
        return {
            "symbol": r.symbol,
            "trades": 0,
            "win_rate": 0.0,
            "avg_pnl_usd": 0.0,
            "total_pnl_usd": 0.0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
            "max_drawdown_pct": 0.0,
            "final_balance": r.final_balance,
            "return_pct": (r.final_balance / r.initial_balance - 1) * 100,
            "total_fees": r.total_fees_paid,
        }

    pnls = np.array([t.pnl_usd for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    win_rate = len(wins) / n if n else 0.0
    total_pnl = float(pnls.sum())
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe (semplice, su PnL per trade)
    if len(pnls) > 1 and pnls.std() > 0:
        sharpe = float(pnls.mean() / pnls.std() * np.sqrt(252 * 288))  # 288 barre 5m/giorno
    else:
        sharpe = 0.0

    # Max drawdown sull'equity curve
    if r.equity_curve:
        eq = pd.Series([v for _, v in r.equity_curve])
        running_max = eq.cummax()
        dd = (eq - running_max) / running_max
        max_dd_pct = float(dd.min() * 100)
    else:
        max_dd_pct = 0.0

    return {
        "symbol": r.symbol,
        "trades": n,
        "win_rate": round(win_rate * 100, 2),
        "avg_pnl_usd": round(float(pnls.mean()), 4),
        "total_pnl_usd": round(total_pnl, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else "inf",
        "sharpe": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "final_balance": round(r.final_balance, 2),
        "return_pct": round((r.final_balance / r.initial_balance - 1) * 100, 3),
        "total_fees": round(r.total_fees_paid, 2),
    }
