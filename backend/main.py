import logging
import os
import asyncio
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

if __package__:
    from .db import init_db, save_snapshot, get_latest_snapshot, get_history
    from .models import PortfolioSnapshot, AnalysisResult
    from .collectors import fetch_zerodha_holdings, fetch_binance_holdings
    from .analysis import run_analysis
else:
    from db import init_db, save_snapshot, get_latest_snapshot, get_history
    from models import PortfolioSnapshot, AnalysisResult
    from collectors import fetch_zerodha_holdings, fetch_binance_holdings
    from analysis import run_analysis

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Falak Finance Monitor")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
KITE_TOKEN_FILE = Path(
    os.getenv("KITE_ACCESS_TOKEN_FILE", "data/kite_access_token.txt")
).resolve()

_MAX_HOLDINGS = 500
_NONCE_TTL = 300
_kite_login_nonces: dict[str, float] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|https?://100\.\d+\.\d+\.\d+(:\d+)?)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    log.info("Falak Finance Monitor started")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/", include_in_schema=False)
async def index():
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
    return FileResponse(FRONTEND_INDEX)


def _kite_client() -> KiteConnect:
    api_key = os.getenv("KITE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="KITE_API_KEY is not configured")
    return KiteConnect(api_key=api_key)


@app.get("/auth/kite/login", include_in_schema=False)
@limiter.limit("5/minute")
async def kite_login(request: Request):
    nonce = secrets.token_urlsafe(16)
    now = time.time()
    _kite_login_nonces[nonce] = now
    expired = [k for k, v in list(_kite_login_nonces.items()) if now - v > _NONCE_TTL]
    for k in expired:
        _kite_login_nonces.pop(k, None)
    response = RedirectResponse(_kite_client().login_url())
    response.set_cookie("kite_nonce", nonce, max_age=_NONCE_TTL, httponly=True, samesite="lax")
    return response


@app.get("/auth/kite/callback", include_in_schema=False)
@limiter.limit("5/minute")
async def kite_callback(request: Request, request_token: str | None = None):
    nonce = request.cookies.get("kite_nonce")
    if not nonce or nonce not in _kite_login_nonces:
        raise HTTPException(status_code=403, detail="Invalid or missing login session")
    initiated_at = _kite_login_nonces.pop(nonce)
    if time.time() - initiated_at > _NONCE_TTL:
        raise HTTPException(status_code=403, detail="Login session expired")

    api_secret = os.getenv("KITE_API_SECRET")
    if not api_secret:
        raise HTTPException(status_code=500, detail="KITE_API_SECRET is not configured")
    if not request_token:
        raise HTTPException(status_code=400, detail="Missing request_token from Kite")

    kite = _kite_client()
    try:
        session = await asyncio.to_thread(
            kite.generate_session, request_token, api_secret=api_secret
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite token exchange failed: {exc}") from exc

    access_token = session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Kite response did not include access_token")

    KITE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = KITE_TOKEN_FILE.with_suffix(".tmp")
    tmp.write_text(access_token, encoding="utf-8")
    tmp.replace(KITE_TOKEN_FILE)
    log.info("Kite access token saved to %s", KITE_TOKEN_FILE)
    return PlainTextResponse(
        "Kite access token saved. You can close this tab and return to Falak Finance Monitor."
    )


@app.get("/api/holdings", response_model=PortfolioSnapshot)
@limiter.limit("10/minute")
async def get_holdings(request: Request):
    errors = []
    zerodha = []
    binance = []

    try:
        zerodha = await fetch_zerodha_holdings()
    except Exception as exc:
        errors.append(f"Zerodha: {exc}")

    try:
        binance = await fetch_binance_holdings()
    except Exception as exc:
        errors.append(f"Binance: {exc}")

    if errors:
        log.warning("Holdings fetch errors: %s", "; ".join(errors))
    if errors and not zerodha and not binance:
        raise HTTPException(status_code=502, detail="; ".join(errors))

    all_holdings = zerodha + binance
    total_value = sum(h.current_value_inr for h in all_holdings)
    total_cost = sum(h.avg_cost * h.quantity for h in all_holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        holdings=all_holdings,
        total_value_inr=total_value,
        total_pnl_inr=total_pnl,
        total_pnl_pct=total_pnl_pct,
    )

    data = snapshot.model_dump(mode="json")
    data["timestamp"] = snapshot.timestamp.isoformat()
    await save_snapshot(data)

    return snapshot


@app.get("/api/snapshot/latest", response_model=PortfolioSnapshot | None)
async def latest_snapshot():
    row = await get_latest_snapshot()
    if not row:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return PortfolioSnapshot(**row)


@app.post("/api/analyse", response_model=AnalysisResult)
@limiter.limit("2/minute")
async def analyse(request: Request, snapshot: PortfolioSnapshot):
    log.info("Running analysis on %d holdings", len(snapshot.holdings))
    if len(snapshot.holdings) > _MAX_HOLDINGS:
        raise HTTPException(
            status_code=422, detail=f"Holdings count exceeds maximum ({_MAX_HOLDINGS})"
        )
    try:
        return await run_analysis(snapshot)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/history")
async def history():
    rows = await get_history(limit=30)
    return rows


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
