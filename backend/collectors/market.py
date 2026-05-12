import asyncio
import ccxt
from datetime import datetime, timezone


async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 100) -> list[dict]:
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    if limit < 1:
        raise ValueError("Limit must be at least 1")

    exchange = ccxt.binance({"enableRateLimit": True})
    try:
        ohlcv = await asyncio.to_thread(
            exchange.fetch_ohlcv, symbol, timeframe=interval, limit=limit
        )
        candles = []
        for row in ohlcv:
            ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).isoformat()
            candles.append({
                "symbol": symbol,
                "interval": interval,
                "timestamp": ts,
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            })
        return candles
    except Exception as exc:
        raise RuntimeError(f"CCXT fetch failed: {exc}")
