"""Loader per i DB SQLite di Pionex (candele OHLCV)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def list_symbols(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def load_candles(db_path, symbol, start=None, end=None):
    conn = sqlite3.connect(str(db_path))
    try:
        query = "SELECT ts, o, h, l, c, v FROM candles WHERE symbol = ?"
        params = [symbol]
        if start is not None:
            query += " AND ts >= ?"
            params.append(int(start.timestamp() * 1000))
        if end is not None:
            query += " AND ts <= ?"
            params.append(int(end.timestamp() * 1000))
        query += " ORDER BY ts ASC"
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("timestamp").drop(columns=["ts"])
    df.columns = ["open", "high", "low", "close", "volume"]
    return df


def get_date_range(db_path, symbol):
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT MIN(ts), MAX(ts) FROM candles WHERE symbol = ?", (symbol,)
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return (
            datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            datetime.fromtimestamp(row[1] / 1000, tz=timezone.utc),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    db = sys.argv[1]
    symbols = list_symbols(db)
    print(f"Simboli trovati: {len(symbols)}")
    for s in symbols[:5]:
        rng = get_date_range(db, s)
        df = load_candles(db, s)
        print(f"  {s}: {len(df)} candele | {rng[0]} -> {rng[1]}")
