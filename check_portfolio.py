import asyncio
from src.brokers.co_invest import CoInvestClient

async def main():
    async with CoInvestClient() as c:
        print("== PORTFOLIO ==")
        print(await c.get_portfolio())
        print()
        print("== OPEN ORDERS ==")
        print(await c.view_open_orders())

asyncio.run(main())
