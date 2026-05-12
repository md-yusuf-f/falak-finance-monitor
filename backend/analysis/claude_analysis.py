import json
import os
from anthropic import AsyncAnthropic

DISCLAIMER = "Not financial advice. For informational purposes only."
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


async def analyse(snapshot: dict) -> dict:
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    holdings_text = json.dumps(snapshot.get("holdings", []), indent=2)

    prompt = (
        "You are a portfolio analyst. Given these holdings, provide a per-asset "
        "HOLD/REVIEW/TRIM verdict and an overall health string.\n\n"
        f"Holdings:\n{holdings_text}\n\n"
        "Respond ONLY with valid JSON matching this schema:\n"
        '{"overall_health": "<string>", "verdicts": [{"symbol": "<str>", '
        '"verdict": "HOLD|REVIEW|TRIM", "reason": "<str>"}], "disclaimer": "<str>"}'
    )

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        result = json.loads(raw)
        result["disclaimer"] = DISCLAIMER
        return result
    except Exception as exc:
        return {"error": f"Claude analysis failed: {exc}", "disclaimer": DISCLAIMER}
