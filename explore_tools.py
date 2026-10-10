import asyncio
import json
from src.brokers.co_invest import CoInvestClient

async def try_call(client, name, args):
    print(f"\n=== {name} {args} ===")
    try:
        result = await client.call(name, args)
        text = json.dumps(result, indent=2, ensure_ascii=False) if not isinstance(result, str) else result
        print(text[:1500])
    except Exception as e:
        print(f"ERRORE: {e}")

async def main():
    async with CoInvestClient() as c:
        # Portfolio e account
        await try_call(c, "get_portfolio", {})
        await try_call(c, "view_open_orders", {})

        # Technical indicators - proviamo diverse forme di argomento
        await try_call(c, "get_technical_indicators", {"symbol": "BTC"})
        await try_call(c, "get_technical_indicators", {"symbol": "BTC", "timeframe": "1m", "interval": "1m"})

        # Chart
        await try_call(c, "show_chart", {"symbol": "BTC"})

        # News
        await try_call(c, "get_news", {})

        # Policy di automazione
        await try_call(c, "automated_trading_status", {})

asyncio.run(main())
