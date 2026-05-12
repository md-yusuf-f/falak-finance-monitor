import os
import pytest
import pytest_asyncio
import sys
from unittest.mock import MagicMock

# pandas and ta are real deps — no mocking needed here

# Set required env vars before importing app modules
os.environ.setdefault("KITE_API_KEY", "test_key")
os.environ.setdefault("KITE_API_SECRET", "test_secret")

from datetime import datetime, timezone  # noqa: E402

import backend.db as _db_module  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Holding, PortfolioSnapshot  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402


def make_holding(symbol="INFY", source="zerodha", asset_type="equity") -> Holding:
    return Holding(
        symbol=symbol,
        source=source,
        type=asset_type,
        quantity=10,
        avg_cost=1000.0,
        current_price=1200.0,
        current_value_inr=12000.0,
        unrealised_pnl=2000.0,
        unrealised_pnl_pct=20.0,
        currency="INR",
    )


def make_snapshot(holdings=None) -> PortfolioSnapshot:
    h = holdings or [make_holding()]
    return PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=h,
        total_value_inr=sum(x.current_value_inr for x in h),
        total_pnl_inr=sum(x.unrealised_pnl for x in h),
        total_pnl_pct=20.0,
    )


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(_db_module, "DB_PATH", str(tmp_path / "test.db"))
    from backend.db import init_db
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
