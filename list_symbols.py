import sqlite3
import sys

db = sys.argv[1]
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("""
    SELECT symbol, COUNT(*) as n,
           MIN(ts) as first_ts, MAX(ts) as last_ts
    FROM candles
    GROUP BY symbol
    ORDER BY symbol
""")
rows = cur.fetchall()
print(f"{'SYMBOL':<20} {'CANDLES':>10} {'FIRST (UTC)':<22} {'LAST (UTC)':<22}")
print("-" * 78)
import datetime
for s, n, mn, mx in rows:
    f = datetime.datetime.utcfromtimestamp(mn/1000).strftime("%Y-%m-%d %H:%M")
    l = datetime.datetime.utcfromtimestamp(mx/1000).strftime("%Y-%m-%d %H:%M")
    print(f"{s:<20} {n:>10} {f:<22} {l:<22}")
conn.close()
