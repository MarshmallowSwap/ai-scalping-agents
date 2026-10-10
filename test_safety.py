import asyncio
from src.brokers.co_invest import CoInvestClient
from src.tools.safety import SafetyError

async def main():
    async with CoInvestClient() as c:
        # Proposta live finta (NON verra' eseguita: deve fallire prima)
        fake = {
            "executionMode": "live",
            "status": "pending_confirmation",
            "order": {
                "asset": "BTC", "side": "long", "size": 10,
                "leverage": 1, "orderType": "market",
                "reasoning": "safety test",
            },
        }
        try:
            await c.execute_suggestion(fake, idempotency_key="SAFETY-TEST")
            print("ERRORE GRAVE: il sistema ha accettato una proposta LIVE non armata!")
        except SafetyError as e:
            print("OK: live bloccato correttamente.")
            print(f"   Messaggio: {e}")
        except Exception as e:
            print(f"Altro errore (accettabile): {type(e).__name__}: {e}")

asyncio.run(main())
