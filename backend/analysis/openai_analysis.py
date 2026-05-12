import json
import os
from openai import AsyncOpenAI

DISCLAIMER = "Not financial advice. For informational purposes only."
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


async def analyse(snapshot: dict) -> dict:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    holdings_text = json.dumps(snapshot.get("holdings", []), indent=2)

    prompt = (
        "You are a portfolio analyst. Given these holdings, provide allocation by "
        "category, compare vs an ideal allocation, and give a top observation.\n\n"
        f"Holdings:\n{holdings_text}\n\n"
        "Respond ONLY with valid JSON matching this schema:\n"
        '{"allocation": [{"category": "<str>", "value_inr": <number>, '
        '"percentage": <number>}], "vs_ideal": "<string>", "top_observation": "<string>"}'
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
        return {"error": f"OpenAI analysis failed: {exc}", "disclaimer": DISCLAIMER}
