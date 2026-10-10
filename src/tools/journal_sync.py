"""Sincronizza il journal con get_position_history di Co-Invest.

Estrae le posizioni chiuse e le registra come eventi 'closed' nel journal,
con PnL reale (gross - fees), così le metriche di performance sono veritiere.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.brokers.co_invest import CoInvestClient

JOURNAL_PATH = Path("data/trades_journal.jsonl")

# Esempio riga:
# - BTC long — closed; complete observed origin; activity 2026-...; opened ...;
#   closed ...; entry 0.0006 @ 83002; exit 0.0006 @ 83001;
#   gross realized PnL -0.0006 (excludes fees and funding); fees: 0.09462171 USDC
POS_PATTERN = re.compile(
    r"-\s+(?P<symbol>\w+)\s+(?P<side>long|short)\s+—\s+(?P<status>\w+);"
    r".*?opened\s+(?P<opened>[\dT:\-.Z]+);\s+"
    r"closed\s+(?P<closed>[\dT:\-.Z]+);\s+"
    r"entry\s+(?P<entry_size>[\d.]+)\s+@\s+(?P<entry_price>[\d.]+);\s+"
    r"exit\s+(?P<exit_size>[\d.]+)\s+@\s+(?P<exit_price>[\d.]+);\s+"
    r"gross realized PnL\s+(?P<gross_pnl>[-\d.]+).*?;\s+"
    r"fees:\s+(?P<fees>[\d.]+)\s+USDC",
    re.IGNORECASE | re.DOTALL,
)


def parse_closed_positions(text: str) -> list[dict]:
    """Estrae le posizioni chiuse dal testo di get_position_history."""
    out = []
    for m in POS_PATTERN.finditer(text):
        gross = float(m.group("gross_pnl"))
        fees = float(m.group("fees"))
        net = gross - fees
        out.append({
            "symbol": m.group("symbol").upper(),
            "side": m.group("side").lower(),
            "status": m.group("status").lower(),
            "opened_at": m.group("opened"),
            "closed_at": m.group("closed"),
            "entry_size": float(m.group("entry_size")),
            "entry_price": float(m.group("entry_price")),
            "exit_size": float(m.group("exit_size")),
            "exit_price": float(m.group("exit_price")),
            "gross_pnl_usd": round(gross, 6),
            "fees_usd": round(fees, 6),
            "net_pnl_usd": round(net, 6),
        })
    return [p for p in out if p["status"] == "closed"]


def _existing_closed_keys() -> set[str]:
    """Chiavi univoche delle posizioni chiuse già registrate."""
    if not JOURNAL_PATH.exists():
        return set()
    keys: set[str] = set()
    with JOURNAL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") == "closed" and "key" in e:
                keys.add(e["key"])
    return keys


def _append_journal(entry: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def sync_with_client(client: CoInvestClient) -> dict:
    """Sincronizza usando un client MCP già avviato."""
    raw = await client.get_position_history()
    text = str(raw)
    closed = parse_closed_positions(text)
    existing = _existing_closed_keys()
    added = 0
    for c in closed:
        key = f"{c['symbol']}|{c['opened_at']}|{c['closed_at']}"
        if key in existing:
            continue
        _append_journal({"event": "closed", "key": key, **c})
        added += 1
    return {"parsed": len(closed), "added": added}


async def sync_standalone() -> dict:
    """Entry point standalone: apre e chiude il client."""
    async with CoInvestClient() as client:
        return await sync_with_client(client)


def main() -> None:
    result = asyncio.run(sync_standalone())
    print(f"Posizioni chiuse parsate: {result['parsed']}")
    print(f"Nuovi eventi aggiunti:    {result['added']}")


if __name__ == "__main__":
    main()
