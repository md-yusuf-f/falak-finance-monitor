from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.collectors.binance as binance_mod
from backend.collectors.binance import fetch_binance_holdings
from backend.collectors.zerodha import fetch_zerodha_holdings


async def test_zerodha_no_token_raises(monkeypatch):
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("KITE_ACCESS_TOKEN_FILE", "/nonexistent/path/token.txt")

    with pytest.raises(ValueError, match="token expired"):
        await fetch_zerodha_holdings()


async def test_zerodha_equity_holdings(monkeypatch):
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "test_token")

    mock_kite = MagicMock()
    mock_kite.holdings.return_value = [
        {"tradingsymbol": "INFY", "quantity": 10, "average_price": 1000.0, "last_price": 1200.0}
    ]
    mock_kite.mf_holdings.return_value = []

    with patch("backend.collectors.zerodha.KiteConnect", return_value=mock_kite):
        result = await fetch_zerodha_holdings()

    assert len(result) == 1
    assert result[0].symbol == "INFY"
    assert result[0].source == "zerodha"
    assert result[0].quantity == 10
    assert pytest.approx(result[0].unrealised_pnl_pct) == 20.0


async def test_zerodha_mf_holdings(monkeypatch):
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "test_token")

    mock_kite = MagicMock()
    mock_kite.holdings.return_value = []
    mock_kite.mf_holdings.return_value = [
        {"tradingsymbol": "NIPPON-G", "quantity": 100.0, "average_price": 50.0, "last_price": 55.0}
    ]

    with patch("backend.collectors.zerodha.KiteConnect", return_value=mock_kite):
        result = await fetch_zerodha_holdings()

    assert len(result) == 1
    assert result[0].source == "coin"
    assert result[0].type == "mutual_fund"


async def test_zerodha_equity_api_error_raises(monkeypatch):
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "test_token")

    mock_kite = MagicMock()
    mock_kite.holdings.side_effect = Exception("Network error")

    with patch("backend.collectors.zerodha.KiteConnect", return_value=mock_kite):
        with pytest.raises(RuntimeError, match="equity fetch failed"):
            await fetch_zerodha_holdings()


async def test_binance_no_keys_returns_empty(monkeypatch):
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)

    result = await fetch_binance_holdings()
    assert result == []


async def test_binance_exchange_error_raises(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "test_key")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "test_secret")

    mock_ex = MagicMock()
    mock_ex.fetch_balance = AsyncMock(side_effect=Exception("Connection refused"))
    mock_ex.fetch_tickers = AsyncMock()
    mock_ex.close = AsyncMock()

    with (
        patch.object(binance_mod.ccxt, "binance", return_value=mock_ex),
        patch("backend.collectors.binance._live_usd_inr", new_callable=AsyncMock, return_value=84.0),
    ):
        with pytest.raises(RuntimeError, match="Binance fetch failed"):
            await fetch_binance_holdings()
