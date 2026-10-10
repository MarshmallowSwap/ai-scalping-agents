import asyncio
from src.brokers.co_invest import CoInvestClient

async def main():
    async with CoInvestClient() as c:
        raw = await c.get_portfolio()
        print("=== RAW ===")
        print(raw)
        print("=== FINE RAW ===")

asyncio.run(main())
