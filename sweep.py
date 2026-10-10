"""Sweep di configurazioni per trovare i parametri migliori.

Modalita':
  python sweep.py DB SYMBOL          # con fee reali
  python sweep.py DB SYMBOL --no-fee # TEST: fee=0, slippage=0
"""

from __future__ import annotations

import itertools
import sys

from src.backtest.engine import BacktestEngine
from src.backtest.loader import load_candles
from src.backtest.metrics import compute_metrics
from src.backtest.strategies import add_indicators


def run_config(db, symbol, strategies, sl_atr, tp_atr, max_bars, size=50.0, lev=3, no_fee=False):
    df = load_candles(db, symbol)
    if len(df) < 250:
        return None
    df = add_indicators(df)
    fee_rate = 0.0 if no_fee else 0.0005
    slippage = 0.0 if no_fee else 5.0
    engine = BacktestEngine(
        fee_rate=fee_rate, slippage_bps=slippage,
        sl_atr_mult=sl_atr, tp_atr_mult=tp_atr,
        max_bars_held=max_bars, strategies=strategies,
        size_usd=size, leverage=lev,
    )
    r = engine.run(symbol, df)
    return compute_metrics(r)


def main():
    args = sys.argv[1:]
    no_fee = "--no-fee" in args
    args = [a for a in args if a != "--no-fee"]

    db = args[0]
    symbol = args[1] if len(args) > 1 else "BTC_USDT_PERP"

    strategies_sets = [
        ["tf_long", "tf_short"],
        ["mr_long", "mr_short"],
        ["tf_long"],
        ["tf_short"],
        ["mr_long"],
        ["mr_short"],
    ]
    sl_options = [1.5, 2.0, 3.0]
    tp_options = [4.0, 6.0, 8.0, 12.0]
    max_bars_options = [30, 60, 120]

    fee_label = "FEE=0, SLIP=0 (TEST)" if no_fee else "FEE=0.05%, SLIP=0.05%"
    print(f"Sweep su {symbol} [{fee_label}]...")
    print(f"{'STRATEGIES':<25} {'SL':>4} {'TP':>4} {'BARS':>5} {'N':>5} {'WIN%':>6} "
          f"{'PNL$':>9} {'PF':>6} {'RET%':>7}")
    print("-" * 85)

    results = []
    for strat, sl, tp, mb in itertools.product(
        strategies_sets, sl_options, tp_options, max_bars_options
    ):
        m = run_config(db, symbol, strat, sl, tp, mb, no_fee=no_fee)
        if m is None or m["trades"] < 10:
            continue
        results.append((strat, sl, tp, mb, m))
        strat_name = "+".join(strat)
        print(f"{strat_name:<25} {sl:>4} {tp:>4} {mb:>5} {m['trades']:>5} "
              f"{m['win_rate']:>6} {m['total_pnl_usd']:>9} "
              f"{str(m['profit_factor']):>6} {m['return_pct']:>7}")

    results.sort(key=lambda x: x[4]["return_pct"], reverse=True)
    print("\n=== TOP 5 per return % ===")
    for strat, sl, tp, mb, m in results[:5]:
        strat_name = "+".join(strat)
        print(f"  {strat_name} | SL={sl}xATR TP={tp}xATR bars={mb} | "
              f"N={m['trades']} WR={m['win_rate']}% PnL=${m['total_pnl_usd']} "
              f"PF={m['profit_factor']} ret={m['return_pct']}% DD={m['max_drawdown_pct']}%")


if __name__ == "__main__":
    main()
