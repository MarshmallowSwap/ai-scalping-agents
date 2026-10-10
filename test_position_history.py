import asyncio
from src.brokers.co_invest import CoInvestClient

async def main():
    async with CoInvestClient() as c:
        # Prova vari argomenti
        for args in [{}, {"limit": 20}, {"symbol": "BTC"}, {"symbol": "BTC", "limit": 20}]:
            try:
                r = await c.call("get_position_history", args)
                print(f"=== get_position_history {args} ===")
                print(str(r)[:2000])
                print()
            except Exception as e:
                print(f"ERRORE {args}: {e}")

asyncio.run(main())
