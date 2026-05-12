import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import ccxt.async_support as ccxt

async def test():
    ex = ccxt.binance({
        "apiKey": os.getenv("BINANCE_API_KEY"),
        "secret": os.getenv("BINANCE_SECRET_KEY"),
        "enableRateLimit": True,
        "options": {"defaultType": "spot", "recvWindow": 60000, "fetchCurrencies": False},
    })
    try:
        bal = await ex.fetch_balance()
        free = {k: v for k, v in bal["free"].items() if v and v > 0}
        print("Balances:", free)
    except Exception as e:
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", e)
        if hasattr(e, 'http_status'):
            print("HTTP STATUS:", e.http_status)
        if hasattr(e, 'json_response'):
            print("RESPONSE:", e.json_response)
    finally:
        await ex.close()

asyncio.run(test())
