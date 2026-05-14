import json
import os
import logging
import httpx

logger = logging.getLogger(__name__)

DISCLAIMER = "Not financial advice. For informational purposes only."


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def analyse(snapshot: dict) -> dict:
    api_key = os.getenv("FALAK_AI_API_KEY", "")
    if not api_key:
        return {"error": "Falak AI analysis failed: FALAK_AI_API_KEY not set", "disclaimer": DISCLAIMER}

    base_url = os.getenv("FALAK_AI_BASE_URL", "http://localhost:8080")
    holdings_json = json.dumps(snapshot.get("holdings", []), indent=2)
    prompt = (
        "You are a portfolio analyst. Given these holdings, provide allocation by category, "
        "compare vs an ideal allocation, and give a top observation.\n\n"
        f"Holdings:\n{holdings_json}\n\n"
        "Respond ONLY with valid JSON — no markdown, no explanation. Schema:\n"
        '{"allocation": [{"category": "<str>", "value_inr": <number>, "percentage": <number>}], '
        '"vs_ideal": "<string>", "top_observation": "<string>"}'
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/chat",
                headers={"X-API-KEY": api_key},
                json={"prompt": prompt, "session_id": "falak-finance", "force_backend": "local"}
            )
            resp.raise_for_status()
            raw = _strip_markdown(resp.json().get("output", ""))
            result = json.loads(raw)
            result["disclaimer"] = DISCLAIMER
            return result
    except Exception as exc:
        logger.error("Falak AI analysis error: %s", exc)
        return {"error": f"Falak AI analysis failed: {exc}", "disclaimer": DISCLAIMER}


async def get_verdict(symbol: str) -> str:
    api_key = os.getenv("FALAK_AI_API_KEY", "")
    if not api_key:
        return "HOLD"

    base_url = os.getenv("FALAK_AI_BASE_URL", "http://localhost:8080")
    prompt = f"For the asset {symbol}, reply with exactly one word — HOLD, REVIEW, or TRIM — based on current market conditions."

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/chat",
                headers={"X-API-KEY": api_key},
                json={"prompt": prompt, "session_id": "falak-finance", "force_backend": "local"}
            )
            resp.raise_for_status()
            output = resp.json().get("output", "").strip().upper()
            verdict = output.split()[0] if output else "HOLD"
            return verdict if verdict in ["HOLD", "REVIEW", "TRIM"] else "HOLD"
    except Exception as exc:
        logger.error("Falak AI verdict error for %s: %s", symbol, exc)
        return "HOLD"
