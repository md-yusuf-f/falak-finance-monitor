import asyncio
import logging
from datetime import datetime, timezone

try:
    from ..models import AnalysisResult, PortfolioSnapshot
    from . import groq_analysis, falak_analysis, gemini_analysis
except ImportError:
    from models import AnalysisResult, PortfolioSnapshot
    from analysis import groq_analysis, falak_analysis, gemini_analysis

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

    groq_task = _safe(groq_analysis.analyse(data), "Groq")
    falak_task = _safe(falak_analysis.analyse(data), "Falak AI")
    gemini_task = _safe(gemini_analysis.analyse(data), "Gemini")

    groq_result, falak_result, gemini_result = await asyncio.gather(
        groq_task, falak_task, gemini_task
    )

    return AnalysisResult(
        groq_verdict=groq_result,
        falak_breakdown=falak_result,
        gemini_risks=gemini_result,
        timestamp=datetime.now(timezone.utc),
        disclaimer=DISCLAIMER,
    )
