import asyncio
from src.brokers.co_invest import CoInvestClient

async def main():
    async with CoInvestClient() as c:
        print("Attivo paper trading...")
        print(await c.enable_paper_trading())
        print()
        print("Stato attuale:")
        print(await c.paper_trading_status())

asyncio.run(main())
