"""Monitor: mostra lo stato attuale di portfolio e ordini aperti."""

from __future__ import annotations

import asyncio
import re

from src.brokers.co_invest import CoInvestClient


def extract_balance(text: str) -> dict:
    out = {"equity": None, "available": None, "margin": None, "mode": None}
    m = re.search(r"Account mode:\s*([^\n]+)", text)
    if m:
        out["mode"] = m.group(1).strip()
    m = re.search(r"\$([\d,]+\.?\d*)\s+equity", text)
    if m:
        out["equity"] = float(m.group(1).replace(",", ""))
    m = re.search(r"\$([\d,]+\.?\d*)\s+available", text)
    if m:
        out["available"] = float(m.group(1).replace(",", ""))
    m = re.search(r"\$([\d,]+\.?\d*)\s+margin used", text)
    if m:
        out["margin"] = float(m.group(1).replace(",", ""))
    return out


def parse_positions(text: str) -> list[dict]:
    positions = []
    # Esempio reale:
    # - BTC LONG 3x | Size: $49.81 | Margin: $16.60 | Entry: $83,002 | PnL: +$0.01 (+0%) | TP/SL: $83,416 / $82,586
    pattern = re.compile(
        r"-\s+(?P<symbol>\w+)\s+(?P<side>LONG|SHORT)\s+(?P<lev>\d+)x\s+\|"
        r"\s+Size:\s+\$(?P<size>[\d.]+)\s+\|"
        r"\s+Margin:\s+\$(?P<margin>[\d.]+)\s+\|"
        r"\s+Entry:\s+\$(?P<entry>[\d,]+)\s+\|"
        r"\s+PnL:\s+(?P<sign>[+-]?)\$(?P<pnl>[\d.]+)\s+\((?P<pct_sign>[+-]?)(?P<pct>[\d.]+)%\)"
        r"(?:\s+\|\s+TP/SL:\s+\$(?P<tp>[\d,]+)\s*/\s*\$(?P<sl>[\d,]+))?"
    )
    for line in text.splitlines():
        m = pattern.search(line)
        if m:
            pnl = float(m.group("pnl"))
            if m.group("sign") == "-":
                pnl = -pnl
            pct = float(m.group("pct"))
            if m.group("pct_sign") == "-":
                pct = -pct
            positions.append({
                "symbol": m.group("symbol"),
                "side": m.group("side"),
                "leverage": int(m.group("lev")),
                "size": float(m.group("size")),
                "margin": float(m.group("margin")),
                "entry": float(m.group("entry").replace(",", "")),
                "pnl_usd": pnl,
                "pnl_pct": pct,
                "tp": float(m.group("tp").replace(",", "")) if m.group("tp") else None,
                "sl": float(m.group("sl").replace(",", "")) if m.group("sl") else None,
            })
    return positions


async def monitor() -> None:
    async with CoInvestClient() as client:
        portfolio_raw = await client.get_portfolio()
        portfolio_text = str(portfolio_raw)

        balance = extract_balance(portfolio_text)
        positions = parse_positions(portfolio_text)

        print("=" * 60)
        print(f"Modalita': {balance['mode']}")
        print(f"Equity:    ${balance['equity']}")
        print(f"Available: ${balance['available']}")
        print(f"Margin:    ${balance['margin']}")
        print("=" * 60)

        if not positions:
            print("\nNessuna posizione aperta.")
        else:
            print(f"\nPosizioni aperte ({len(positions)}):\n")
            for p in positions:
                print(f"  {p['symbol']} {p['side']} {p['leverage']}x")
                print(f"    Size:  ${p['size']}  |  Margin: ${p['margin']}")
                print(f"    Entry: ${p['entry']}  |  PnL: ${p['pnl_usd']} ({p['pnl_pct']}%)")
                if p["tp"] and p["sl"]:
                    print(f"    TP:    ${p['tp']}  |  SL: ${p['sl']}")
                print()

        print("Ordini aperti:")
        orders = await client.view_open_orders()
        print(orders)


if __name__ == "__main__":
    asyncio.run(monitor())
