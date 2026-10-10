"""Test focalizzato su tf_long con fee reali su piu' timeframe."""

from __future__ import annotations

import itertools
import sys

from src.backtest.engine import BacktestEngine
from src.backtest.loader import load_candles
from src.backtest.metrics import compute_metrics
from src.backtest.strategies import add_indicators


def run_one(db, symbol, sl, tp, bars, size=50.0):
    df = load_candles(db, symbol)
    if len(df) < 250:
        return None
    df = add_indicators(df)
    engine = BacktestEngine(
        fee_rate=0.0005, slippage_bps=5.0,
        sl_atr_mult=sl, tp_atr_mult=tp,
        max_bars_held=bars, strategies=["tf_long"],
        size_usd=size, leverage=3,
    )
    r = engine.run(symbol, df)
    return compute_metrics(r)


def main():
    db = sys.argv[1]
    symbol = sys.argv[2] if len(sys.argv) > 2 else "BTC_USDT_PERP"

    print(f"Test tf_long su {symbol}")
    print(f"{'SL':>4} {'TP':>4} {'BARS':>5} {'N':>5} {'WIN%':>6} "
          f"{'PNL$':>9} {'PF':>6} {'RET%':>7} {'DD%':>6}")
    print("-" * 70)

    results = []
    for sl, tp, bars in itertools.product([2.0, 3.0, 4.0], [6.0, 8.0, 12.0, 16.0], [60, 120, 240]):
        m = run_one(db, symbol, sl, tp, bars)
        if m is None or m["trades"] < 20:
            continue
        results.append((sl, tp, bars, m))
        print(f"{sl:>4} {tp:>4} {bars:>5} {m['trades']:>5} {m['win_rate']:>6} "
              f"{m['total_pnl_usd']:>9} {str(m['profit_factor']):>6} "
              f"{m['return_pct']:>7} {m['max_drawdown_pct']:>6}")

    results.sort(key=lambda x: x[3]["return_pct"], reverse=True)
    print("\n=== TOP 5 ===")
    for sl, tp, bars, m in results[:5]:
        print(f"  SL={sl}xATR TP={tp}xATR bars={bars} | N={m['trades']} "
              f"WR={m['win_rate']}% PnL=${m['total_pnl_usd']} PF={m['profit_factor']} "
              f"ret={m['return_pct']}% DD={m['max_drawdown_pct']}%")


if __name__ == "__main__":
    main()
