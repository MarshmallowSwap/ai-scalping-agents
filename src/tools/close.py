"""Chiude una posizione esistente in paper (o live, se abilitato).

Uso:
  python -m src.tools.close BTC           # chiusura totale (chiede conferma)
  python -m src.tools.close BTC --yes     # chiusura totale senza prompt
"""

from __future__ import annotations

import argparse
import asyncio

from src.brokers.co_invest import CoInvestClient


async def close(symbol: str, auto_confirm: bool) -> None:
    async with CoInvestClient() as c:
        # 1) Preview
        print(f"Preview chiusura {symbol}...")
        preview = await c.call("close_position", {"symbol": symbol, "confirmed": False})
        print(preview)
        print()

        if not auto_confirm:
            ans = input(f"Confermi chiusura {symbol}? [SI/no]: ").strip().lower()
            if ans not in ("si", "s", "y", "yes"):
                print("Annullato.")
                return

        # 2) Esegui chiusura
        print(f"Chiudo {symbol}...")
        result = await c.call("close_position", {"symbol": symbol, "confirmed": True})
        print(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="Es: BTC, ETH, SOL")
    parser.add_argument("--yes", action="store_true", help="Salta la conferma interattiva")
    args = parser.parse_args()
    asyncio.run(close(args.symbol, args.yes))


if __name__ == "__main__":
    main()
