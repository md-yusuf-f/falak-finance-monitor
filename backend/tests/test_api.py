from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.models import AnalysisResult, Holding, PortfolioSnapshot
from backend.tests.conftest import make_holding, make_snapshot


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_holdings_returns_both_sources(client):
    z = make_holding("INFY", "zerodha", "equity")
    b = make_holding("BTC", "binance", "crypto")
    with (
        patch("backend.main.fetch_zerodha_holdings", new_callable=AsyncMock, return_value=[z]),
        patch("backend.main.fetch_binance_holdings", new_callable=AsyncMock, return_value=[b]),
        patch("backend.main.fetch_indstocks_holdings", new_callable=AsyncMock, return_value=[]),
    ):
        resp = await client.get("/api/holdings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["holdings"]) == 2
    assert pytest.approx(data["total_value_inr"]) == 24000.0


async def test_holdings_binance_down_zerodha_up(client):
    z = make_holding("RELIANCE", "zerodha", "equity")
    with (
        patch("backend.main.fetch_zerodha_holdings", new_callable=AsyncMock, return_value=[z]),
        patch("backend.main.fetch_binance_holdings", new_callable=AsyncMock, side_effect=RuntimeError("Binance down")),
        patch("backend.main.fetch_indstocks_holdings", new_callable=AsyncMock, return_value=[]),
    ):
        resp = await client.get("/api/holdings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["symbol"] == "RELIANCE"


async def test_holdings_both_down_returns_502(client):
    with (
        patch("backend.main.fetch_zerodha_holdings", new_callable=AsyncMock, side_effect=RuntimeError("Z down")),
        patch("backend.main.fetch_binance_holdings", new_callable=AsyncMock, side_effect=RuntimeError("B down")),
        patch("backend.main.fetch_indstocks_holdings", new_callable=AsyncMock, side_effect=RuntimeError("IND down")),
    ):
        resp = await client.get("/api/holdings")
    assert resp.status_code == 502


async def test_analyse_valid_snapshot(client):
    snapshot = make_snapshot()
    mock_result = AnalysisResult(
        claude_verdict={"verdict": "HOLD"},
        openai_breakdown={"allocation": {}},
        gemini_risks={"risks": []},
        timestamp=datetime.now(timezone.utc),
    )
    with patch("backend.main.run_analysis", new_callable=AsyncMock, return_value=mock_result):
        resp = await client.post("/api/analyse", json=snapshot.model_dump(mode="json"))
    assert resp.status_code == 200
    data = resp.json()
    assert "claude_verdict" in data
    assert "disclaimer" in data


async def test_analyse_too_many_holdings_returns_422(client):
    holdings = [
        Holding(
            symbol=f"STOCK{i}",
            source="zerodha",
            type="equity",
            quantity=1,
            avg_cost=100.0,
            current_price=110.0,
            current_value_inr=110.0,
            unrealised_pnl=10.0,
            unrealised_pnl_pct=10.0,
        )
        for i in range(501)
    ]
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=holdings,
        total_value_inr=55110.0,
        total_pnl_inr=5010.0,
        total_pnl_pct=10.0,
    )
    resp = await client.post("/api/analyse", json=snapshot.model_dump(mode="json"))
    assert resp.status_code == 422


async def test_latest_snapshot_no_data_returns_404(client):
    resp = await client.get("/api/snapshot/latest")
    assert resp.status_code == 404


async def test_history_empty_returns_list(client):
    resp = await client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_kite_callback_no_nonce_returns_403(client):
    resp = await client.get("/auth/kite/callback?request_token=abc123")
    assert resp.status_code == 403
