import asyncio
import logging
from datetime import datetime, timezone

try:
    from ..models import AnalysisResult, PortfolioSnapshot
    from . import claude_analysis, openai_analysis, gemini_analysis
except ImportError:
    from models import AnalysisResult, PortfolioSnapshot
    from analysis import claude_analysis, openai_analysis, gemini_analysis

TIMEOUT = 30.0
DISCLAIMER = "Not financial advice. For informational purposes only."
log = logging.getLogger(__name__)


async def _safe(coro, fallback_key: str) -> dict:
    try:
        return await asyncio.wait_for(coro, timeout=TIMEOUT)
    except asyncio.TimeoutError:
        log.warning("%s analysis timed out after %.0fs", fallback_key, TIMEOUT)
        return {"error": f"{fallback_key} timed out after {TIMEOUT}s", "disclaimer": DISCLAIMER}
    except Exception as exc:
        log.error("%s analysis failed: %s", fallback_key, exc)
        return {"error": f"{fallback_key} failed: {exc}", "disclaimer": DISCLAIMER}


async def run_analysis(snapshot: PortfolioSnapshot) -> AnalysisResult:
    data = snapshot.model_dump(mode="json")
    ts = data.get("timestamp")
    if hasattr(ts, "isoformat"):
        data["timestamp"] = ts.isoformat()
    elif not isinstance(ts, str):
        data["timestamp"] = str(ts)

    claude_task = _safe(claude_analysis.analyse(data), "Claude")
    openai_task = _safe(openai_analysis.analyse(data), "OpenAI")
    gemini_task = _safe(gemini_analysis.analyse(data), "Gemini")

    claude_result, openai_result, gemini_result = await asyncio.gather(
        claude_task, openai_task, gemini_task
    )

    return AnalysisResult(
        claude_verdict=claude_result,
        openai_breakdown=openai_result,
        gemini_risks=gemini_result,
        timestamp=datetime.now(timezone.utc),
        disclaimer=DISCLAIMER,
    )
