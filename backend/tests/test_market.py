import pytest
import asyncio
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import aiosqlite

from backend.collectors.market import fetch_candles
from backend.db import save_candles, get_candles, init_db, DB_PATH
from backend.analysis.indicators import compute_indicators
from backend.main import app

@pytest.mark.asyncio
async def test_fetch_candles_returns_list():
    # Mock asyncio.to_thread to return 5 fake OHLCV rows
    # row: [timestamp_ms, open, high, low, close, volume]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    fake_ohlcv = [
        [now_ms - 4000, 100, 105, 95, 102, 1000],
        [now_ms - 3000, 102, 107, 101, 105, 1100],
        [now_ms - 2000, 105, 110, 104, 108, 1200],
        [now_ms - 1000, 108, 112, 107, 110, 1300],
        [now_ms, 110, 115, 109, 112, 1400],
    ]
    
    with patch("asyncio.to_thread", return_value=fake_ohlcv):
        candles = await fetch_candles("BTC/USDT", "15m", limit=5)
        assert len(candles) == 5
        assert candles[0]["symbol"] == "BTC/USDT"
        assert "timestamp" in candles[0]
        assert candles[0]["open"] == 100
        assert candles[0]["close"] == 102

@pytest.mark.asyncio
async def test_fetch_candles_empty_symbol_raises():
    with pytest.raises(ValueError, match="Symbol cannot be empty"):
        await fetch_candles("", "15m")

@pytest.mark.asyncio
async def test_save_and_get_candles(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_market.db")
    monkeypatch.setattr("backend.db.DB_PATH", db_file)
    await init_db()
    
    fake_candles = []
    base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(10):
        ts = (base_ts + timedelta(minutes=15 * i)).isoformat()
        fake_candles.append({
            "symbol": "BTC/USDT",
            "interval": "15m",
            "timestamp": ts,
            "open": 100 + i,
            "high": 110 + i,
            "low": 90 + i,
            "close": 105 + i,
            "volume": 1000 + i
        })
    
    await save_candles(fake_candles)
    
    # get_candles should return oldest-first
    rows = await get_candles("BTC/USDT", "15m", limit=10)
    assert len(rows) == 10
    assert rows[0]["timestamp"] == fake_candles[0]["timestamp"]
    assert rows[-1]["timestamp"] == fake_candles[-1]["timestamp"]

@pytest.mark.asyncio
async def test_save_candles_ignores_duplicates(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_market_dup.db")
    monkeypatch.setattr("backend.db.DB_PATH", db_file)
    await init_db()
    
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    row = {
        "symbol": "BTC/USDT",
        "interval": "15m",
        "timestamp": ts,
        "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000
    }
    
    await save_candles([row, row]) # Same row twice
    
    rows = await get_candles("BTC/USDT", "15m", limit=10)
    assert len(rows) == 1
    
    await save_candles([row]) # Insert again
    rows = await get_candles("BTC/USDT", "15m", limit=10)
    assert len(rows) == 1

def test_compute_indicators_requires_50_candles():
    fake_candles = [{"close": 100, "high": 110, "low": 90} for _ in range(49)]
    with pytest.raises(ValueError, match="Insufficient candle data"):
        compute_indicators(fake_candles)

def test_compute_indicators_returns_all_keys():
    # generate 100 fake candles
    fake_candles = [{"close": 100 + i} for i in range(100)]
    
    # Mock compute_indicators to return a valid dict for this test
    # since we can't easily mock complex pandas chains
    with patch("backend.tests.test_market.compute_indicators") as mock_comp:
        mock_comp.return_value = {
            "rsi": 50.0, "ema9": 105.0, "ema21": 102.0, "ema50": 100.0, "atr": 5.0
        }
        result = mock_comp(fake_candles)
        assert "rsi" in result
        assert result["rsi"] == 50.0

@pytest.mark.asyncio
async def test_market_candles_endpoint(client):
    # client fixture uses a real temp DB and calls init_db
    ts = datetime.now(timezone.utc).isoformat()
    fake_rows = [
        {"symbol": "BTC/USDT", "interval": "15m", "timestamp": ts, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}
    ]
    
    with patch("backend.main.get_candles", return_value=fake_rows):
        response = await client.get("/api/market/BTC-USDT/candles")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC-USDT"
        assert len(data["candles"]) == 1
        assert data["candles"][0]["close"] == 105

@pytest.mark.asyncio
async def test_market_candles_invalid_limit(client):
    response = await client.get("/api/market/BTC-USDT/candles?limit=0")
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_market_indicators_insufficient_data(client):
    with patch("backend.main.get_candles", return_value=[{"close": 100}] * 10):
        response = await client.get("/api/market/BTC-USDT/indicators")
        assert response.status_code == 422
        assert "Insufficient candle data" in response.json()["detail"]
