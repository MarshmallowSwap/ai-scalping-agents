import asyncio
from src.brokers.co_invest import CoInvestClient

async def main():
    async with CoInvestClient() as c:
        for args in [
            {"symbol": "BTC", "interval": "5m"},
            {"symbol": "BTC", "interval": "5m", "limit": 100},
        ]:
            try:
                r = await c.call("show_chart", args)
                print(f"=== show_chart {args} ===")
                print(str(r)[:800])
                print()
            except Exception as e:
                print(f"ERRORE {args}: {e}")

asyncio.run(main())
