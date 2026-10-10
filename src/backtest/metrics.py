"""Metriche di performance per un backtest (v2 - corretta)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult


def compute_metrics(r: BacktestResult) -> dict:
    trades = r.trades
    n = len(trades)

    base = {
        "symbol": r.symbol,
        "trades": n,
        "win_rate": 0.0,
        "avg_pnl_usd": 0.0,
        "total_pnl_usd": 0.0,
        "profit_factor": 0.0,
        "sharpe": 0.0,
        "sharpe_daily": 0.0,
        "max_drawdown_pct": 0.0,
        "final_balance": r.final_balance,
        "return_pct": (r.final_balance / r.initial_balance - 1) * 100,
        "total_fees": r.total_fees_paid,
        "liquidations": 0,
    }

    if n == 0:
        return base

    pnls = np.array([t.pnl_usd for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    base["win_rate"] = round(len(wins) / n * 100, 2)
    base["avg_pnl_usd"] = round(float(pnls.mean()), 4)
    base["total_pnl_usd"] = round(float(pnls.sum()), 2)
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    base["profit_factor"] = round(pf, 3) if pf != float("inf") else "inf"

    # Conta liquidazioni
    base["liquidations"] = sum(1 for t in trades if t.exit_reason == "liq")

    # === SHARPE PER-TRADE (mantenuto per confronto storico, ma etichettato) ===
    if n > 1 and pnls.std() > 0:
        base["sharpe"] = round(float(pnls.mean() / pnls.std() * np.sqrt(n)), 3)

    # === SHARPE GIORNALIERO (metodo corretto) ===
    if r.equity_curve and len(r.equity_curve) > 1:
        eq = pd.Series(
            [v for _, v in r.equity_curve],
            index=pd.DatetimeIndex([t for t, _ in r.equity_curve]),
        )
        # Resample a fine giornata (ultimo valore di ogni giorno)
        daily = eq.resample("1D").last().dropna()
        if len(daily) > 2:
            daily_returns = daily.pct_change().dropna()
            if daily_returns.std() > 0:
                base["sharpe_daily"] = round(
                    float(daily_returns.mean() / daily_returns.std() * np.sqrt(365)),
                    3,
                )

    # === MAX DRAWDOWN ===
    if r.equity_curve:
        eq = pd.Series([v for _, v in r.equity_curve])
        running_max = eq.cummax()
        dd = (eq - running_max) / running_max
        base["max_drawdown_pct"] = round(float(dd.min() * 100), 2)

    base["final_balance"] = round(r.final_balance, 2)
    base["return_pct"] = round((r.final_balance / r.initial_balance - 1) * 100, 3)
    base["total_fees"] = round(r.total_fees_paid, 2)

    return base
