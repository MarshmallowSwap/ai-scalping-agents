import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("== TABELLE ==")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]
for t in tables:
    print(f"  - {t}")

for t in tables:
    print(f"\n== SCHEMA: {t} ==")
    cur.execute(f"PRAGMA table_info('{t}')")
    for col in cur.fetchall():
        print(f"  {col[1]:<25} {col[2]:<12} pk={col[5]}")

    cur.execute(f"SELECT COUNT(*) FROM '{t}'")
    n = cur.fetchone()[0]
    print(f"  Righe: {n}")

    if n > 0:
        print(f"  Prima riga:")
        cur.execute(f"SELECT * FROM '{t}' LIMIT 1")
        print(f"    {cur.fetchone()}")
        print(f"  Ultima riga:")
        cur.execute(f"SELECT * FROM '{t}' ORDER BY rowid DESC LIMIT 1")
        print(f"    {cur.fetchone()}")

conn.close()
