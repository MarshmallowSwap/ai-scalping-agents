"""CLI per eseguire un backtest su un file SQLite di Pionex."""

from __future__ import annotations

import argparse

import pandas as pd

from src.backtest.engine import BacktestEngine
from src.backtest.loader import list_symbols, load_candles
from src.backtest.metrics import compute_metrics
from src.backtest.strategies import add_indicators


def run_one(db, symbol, strategies, sl_atr_mult, tp_atr_mult, max_bars_held,
            size_usd, leverage, fee_rate):
    df = load_candles(db, symbol)
    if len(df) < 250:
        return {"symbol": symbol, "trades": 0, "error": "dati insufficienti"}

    df = add_indicators(df)
    engine = BacktestEngine(
        fee_rate=fee_rate, slippage_bps=5.0,
        sl_atr_mult=sl_atr_mult, tp_atr_mult=tp_atr_mult,
        max_bars_held=max_bars_held, strategies=strategies,
        size_usd=size_usd, leverage=leverage,
    )
    result = engine.run(symbol, df)
    return compute_metrics(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--symbol")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strategies", default="tf_long,tf_short")
    parser.add_argument("--sl-atr", type=float, default=1.5)
    parser.add_argument("--tp-atr", type=float, default=3.0)
    parser.add_argument("--max-bars", type=int, default=60)
    parser.add_argument("--size", type=float, default=50.0)
    parser.add_argument("--leverage", type=int, default=3)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--min-trades", type=int, default=5)
    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    if args.all:
        symbols = list_symbols(args.db)
    elif args.symbol:
        symbols = [args.symbol]
    else:
        print("Specifica --symbol o --all")
        return

    print(f"Backtest su {len(symbols)} simboli | strategies={strategies}\n")

    rows = []
    for s in symbols:
        m = run_one(
            db=args.db, symbol=s, strategies=strategies,
            sl_atr_mult=args.sl_atr, tp_atr_mult=args.tp_atr,
            max_bars_held=args.max_bars, size_usd=args.size,
            leverage=args.leverage, fee_rate=args.fee_rate,
        )
        rows.append(m)
        print(f"  {s:<22} N={m.get('trades', 0):>4} "
              f"WR={m.get('win_rate', 0):>5}% "
              f"PnL=${m.get('total_pnl_usd', 0):>8} "
              f"PF={m.get('profit_factor', 0)} "
              f"ret={m.get('return_pct', 0):>6}% "
              f"liq={m.get('liquidations', 0)}")

    df = pd.DataFrame(rows)
    if "trades" in df.columns:
        df = df[df["trades"] >= args.min_trades]

    print("\n== TOP 10 per return % ==")
    if "return_pct" in df.columns and len(df) > 0:
        cols = ["symbol", "trades", "win_rate", "total_pnl_usd",
                "profit_factor", "sharpe_daily", "max_drawdown_pct",
                "return_pct", "liquidations"]
        cols = [c for c in cols if c in df.columns]
        top = df.sort_values("return_pct", ascending=False).head(10)
        print(top[cols].to_string(index=False))

        print("\n== MEDIA AGGREGATA ==")
        print(f"  Simboli analizzati: {len(df)}")
        print(f"  Trade totali: {int(df['trades'].sum())}")
        print(f"  Win rate medio: {df['win_rate'].mean():.2f}%")
        print(f"  PnL totale: ${df['total_pnl_usd'].sum():.2f}")
        print(f"  Return medio: {df['return_pct'].mean():.3f}%")
        print(f"  Liquidazioni totali: {int(df['liquidations'].sum())}")


if __name__ == "__main__":
    main()
