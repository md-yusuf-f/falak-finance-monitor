import logging
import os
import httpx
from pathlib import Path

try:
    from ..models import Holding
except ImportError:
    from models import Holding

log = logging.getLogger(__name__)

_BASE_URL = "https://api.indstocks.com"
_TOKEN_FILE = Path(os.getenv("INDSTOCKS_ACCESS_TOKEN_FILE", "data/indstocks_access_token.txt"))


def _read_token_file() -> str:
    path = Path(os.getenv("INDSTOCKS_ACCESS_TOKEN_FILE", "data/indstocks_access_token.txt"))
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _get_headers() -> dict[str, str]:
    token = os.getenv("INDSTOCKS_ACCESS_TOKEN") or _read_token_file()
    if not token:
        raise ValueError("INDSTOCKS_ACCESS_TOKEN not set — add to .env or token file")
    return {"Authorization": token, "Content-Type": "application/json"}


async def fetch_indstocks_holdings() -> list[Holding]:
    headers = _get_headers()
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=15.0) as client:
        try:
            resp = await client.get("/portfolio/holdings")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise ValueError("INDstocks token expired or invalid. Update INDSTOCKS_ACCESS_TOKEN in .env")
            raise RuntimeError(f"INDstocks holdings fetch failed: HTTP {status}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"INDstocks holdings fetch failed: {exc}") from exc

        payload = resp.json()
        # API may return {"data": [...]} or a direct list
        rows = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            rows = []

        holdings: list[Holding] = []
        for h in rows:
            symbol = h.get("tradingsymbol") or h.get("symbol") or ""
            if not symbol:
                continue
            qty = float(h.get("quantity") or h.get("qty") or 0)
            avg = float(h.get("average_price") or h.get("avg_price") or 0)
            ltp = float(h.get("last_price") or h.get("ltp") or avg)
            value = qty * ltp
            cost = qty * avg
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0.0
            holdings.append(
                Holding(
                    symbol=symbol,
                    source="indmoney",
                    type="equity",
                    quantity=qty,
                    avg_cost=avg,
                    current_price=ltp,
                    current_value_inr=value,
                    unrealised_pnl=pnl,
                    unrealised_pnl_pct=pnl_pct,
                    currency="INR",
                )
            )

        log.info("INDstocks: fetched %d holdings", len(holdings))
        return holdings
