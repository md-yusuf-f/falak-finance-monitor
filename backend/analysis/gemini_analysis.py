import json
import os
import google.generativeai as genai

DISCLAIMER = "Not financial advice. For informational purposes only."
MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _compute_risk_flags(holdings: list[dict], total_value: float) -> list[dict]:
    """Pre-compute rule-based flags to seed the prompt."""
    flags = []
    crypto_value = sum(
        h["current_value_inr"] for h in holdings if h.get("type") == "crypto"
    )
    if total_value > 0:
        crypto_pct = crypto_value / total_value * 100
        if crypto_pct > 15:
            flags.append(
                {
                    "severity": "MEDIUM",
                    "flag": "High crypto allocation",
                    "detail": f"Crypto is {crypto_pct:.1f}% of portfolio (>15%)",
                }
            )

    for h in holdings:
        if total_value > 0:
            pct = h["current_value_inr"] / total_value * 100
            if pct > 20:
                flags.append(
                    {
                        "severity": "HIGH",
                        "flag": f"Concentration in {h['symbol']}",
                        "detail": f"{h['symbol']} is {pct:.1f}% of portfolio (>20%)",
                    }
                )
        if h.get("unrealised_pnl_pct", 0) < -20:
            flags.append(
                {
                    "severity": "MEDIUM",
                    "flag": f"Large unrealised loss in {h['symbol']}",
                    "detail": f"Down {h['unrealised_pnl_pct']:.1f}% (<-20%)",
                }
            )

    return flags


async def analyse(snapshot: dict) -> dict:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(MODEL)

    holdings = snapshot.get("holdings", [])
    total_value = snapshot.get("total_value_inr", 0)
    seeded_flags = _compute_risk_flags(holdings, total_value)
    holdings_text = json.dumps(holdings, indent=2)

    prompt = (
        "You are a risk analyst. Given these holdings and pre-computed risk flags, "
        "identify all risk flags (include the pre-computed ones plus any you find), "
        "score overall risk 1-10, and write a risk summary.\n\n"
        f"Holdings:\n{holdings_text}\n\n"
        f"Pre-computed flags:\n{json.dumps(seeded_flags, indent=2)}\n\n"
        "Respond ONLY with valid JSON matching this schema:\n"
        '{"flags": [{"severity": "HIGH|MEDIUM|LOW", "flag": "<str>", "detail": "<str>"}], '
        '"risk_score": <1-10>, "risk_summary": "<string>"}'
    )

    try:
        response = await model.generate_content_async(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        result["disclaimer"] = DISCLAIMER
        return result
    except Exception as exc:
        return {"error": f"Gemini analysis failed: {exc}", "disclaimer": DISCLAIMER}
