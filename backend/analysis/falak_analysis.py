import json
import os
from openai import AsyncOpenAI

DISCLAIMER = "Not financial advice. For informational purposes only."
MODEL = os.getenv("FALAK_AI_MODEL", "qwen3:8b")
BASE_URL = os.getenv("FALAK_AI_BASE_URL", "http://localhost:11434/v1")


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def analyse(snapshot: dict) -> dict:
    api_key = os.getenv("FALAK_AI_API_KEY", "ollama")
    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    holdings_text = json.dumps(snapshot.get("holdings", []), indent=2)

    prompt = (
        "You are a portfolio analyst. Given these holdings, provide allocation by "
        "category, compare vs an ideal allocation, and give a top observation.\n\n"
        f"Holdings:\n{holdings_text}\n\n"
        "Respond ONLY with valid JSON — no markdown, no explanation. Schema:\n"
        '{"allocation": [{"category": "<str>", "value_inr": <number>, '
        '"percentage": <number>}], "vs_ideal": "<string>", "top_observation": "<string>"}'
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        raw = _strip_markdown(response.choices[0].message.content)
        result = json.loads(raw)
        result["disclaimer"] = DISCLAIMER
        return result
    except Exception as exc:
        return {"error": f"Falak AI analysis failed: {exc}", "disclaimer": DISCLAIMER}
