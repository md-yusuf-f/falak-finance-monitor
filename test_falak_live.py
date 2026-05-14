"""
Live integration test for Falak AI API.
Run from project root:

    $env:FALAK_AI_API_KEY="your-key"
    $env:FALAK_AI_BASE_URL="http://<tailscale-ip>:8080"
    python test_falak_live.py
"""
import asyncio
import sys
import os

sys.path.insert(0, "backend")
from analysis.falak_analysis import get_verdict, analyse

SAMPLE_SNAPSHOT = {
    "holdings": [
        {
            "symbol": "BTC/USDT",
            "source": "binance",
            "type": "crypto",
            "quantity": 0.01,
            "avg_cost": 45000,
            "current_price": 62000,
            "current_value_inr": 51788,
            "unrealised_pnl": 170,
            "unrealised_pnl_pct": 37.7,
            "currency": "USD",
        },
        {
            "symbol": "RELIANCE",
            "source": "zerodha",
            "type": "equity",
            "quantity": 5,
            "avg_cost": 2400,
            "current_price": 2650,
            "current_value_inr": 13250,
            "unrealised_pnl": 1250,
            "unrealised_pnl_pct": 10.4,
            "currency": "INR",
        },
    ]
}


async def main():
    key = os.getenv("FALAK_AI_API_KEY", "")
    url = os.getenv("FALAK_AI_BASE_URL", "http://localhost:8080")

    if not key:
        print("ERROR: FALAK_AI_API_KEY not set")
        sys.exit(1)

    print(f"Target: {url}")
    print("-" * 40)

    print("TEST 1: get_verdict('BTC/USDT')")
    verdict = await get_verdict("BTC/USDT")
    print(f"  Result: {verdict}")
    assert verdict in ["HOLD", "REVIEW", "TRIM"], f"Unexpected verdict: {verdict}"
    print("  PASS")

    print("\nTEST 2: analyse(snapshot)")
    result = await analyse(SAMPLE_SNAPSHOT)
    print(f"  Result: {result}")
    if "error" in result:
        print(f"  FAIL — {result['error']}")
        sys.exit(1)
    assert "allocation" in result, "Missing 'allocation' key"
    assert "disclaimer" in result, "Missing 'disclaimer' key"
    print("  PASS")

    print("\nAll tests passed.")


asyncio.run(main())
