import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.analysis.router import run_analysis
from backend.models import AnalysisResult, Holding, PortfolioSnapshot


def _snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=[
            Holding(
                symbol="INFY",
                source="zerodha",
                type="equity",
                quantity=10,
                avg_cost=1000.0,
                current_price=1200.0,
                current_value_inr=12000.0,
                unrealised_pnl=2000.0,
                unrealised_pnl_pct=20.0,
            )
        ],
        total_value_inr=12000.0,
        total_pnl_inr=2000.0,
        total_pnl_pct=20.0,
    )


async def test_all_providers_fail_returns_error_fields():
    with (
        patch("backend.analysis.router.claude_analysis.analyse", new_callable=AsyncMock, side_effect=Exception("Claude down")),
        patch("backend.analysis.router.openai_analysis.analyse", new_callable=AsyncMock, side_effect=Exception("OpenAI down")),
        patch("backend.analysis.router.gemini_analysis.analyse", new_callable=AsyncMock, side_effect=Exception("Gemini down")),
    ):
        result = await run_analysis(_snapshot())

    assert isinstance(result, AnalysisResult)
    assert "error" in result.claude_verdict
    assert "error" in result.openai_breakdown
    assert "error" in result.gemini_risks


async def test_one_provider_timeout_others_succeed():
    openai_result = {"allocation": {"equity": 100}}
    gemini_result = {"risks": []}

    with (
        patch("backend.analysis.router.claude_analysis.analyse", new_callable=AsyncMock, side_effect=asyncio.TimeoutError),
        patch("backend.analysis.router.openai_analysis.analyse", new_callable=AsyncMock, return_value=openai_result),
        patch("backend.analysis.router.gemini_analysis.analyse", new_callable=AsyncMock, return_value=gemini_result),
    ):
        result = await run_analysis(_snapshot())

    assert "error" in result.claude_verdict
    assert result.openai_breakdown == openai_result
    assert result.gemini_risks == gemini_result


async def test_all_providers_succeed():
    claude_result = {"verdicts": [{"symbol": "INFY", "verdict": "HOLD"}]}
    openai_result = {"allocation": {"equity": 100}}
    gemini_result = {"risks": []}

    with (
        patch("backend.analysis.router.claude_analysis.analyse", new_callable=AsyncMock, return_value=claude_result),
        patch("backend.analysis.router.openai_analysis.analyse", new_callable=AsyncMock, return_value=openai_result),
        patch("backend.analysis.router.gemini_analysis.analyse", new_callable=AsyncMock, return_value=gemini_result),
    ):
        result = await run_analysis(_snapshot())

    assert result.claude_verdict == claude_result
    assert result.openai_breakdown == openai_result
    assert result.gemini_risks == gemini_result
    assert result.disclaimer == "Not financial advice. For informational purposes only."


async def test_result_has_timestamp_and_disclaimer():
    with (
        patch("backend.analysis.router.claude_analysis.analyse", new_callable=AsyncMock, return_value={}),
        patch("backend.analysis.router.openai_analysis.analyse", new_callable=AsyncMock, return_value={}),
        patch("backend.analysis.router.gemini_analysis.analyse", new_callable=AsyncMock, return_value={}),
    ):
        result = await run_analysis(_snapshot())

    assert isinstance(result.timestamp, datetime)
    assert result.disclaimer != ""
