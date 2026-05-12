import json
import os
from openai import AsyncOpenAI

DISCLAIMER = "Not financial advice. For informational purposes only."
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
BASE_URL = "https://api.groq.com/openai/v1"


async def analyse(snapshot: dict) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"error": "Groq analysis failed: GROQ_API_KEY not set", "disclaimer": DISCLAIMER}
    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
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
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        result = json.loads(raw)
        result["disclaimer"] = DISCLAIMER
        return result
    except Exception as exc:
        return {"error": f"Groq analysis failed: {exc}", "disclaimer": DISCLAIMER}
