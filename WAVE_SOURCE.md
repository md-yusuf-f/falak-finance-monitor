# Falak Finance Monitor Progress

## Current Status

- Local Windows deployment is working at `http://127.0.0.1:8765`.
- Backend starts with Uvicorn and serves both API routes and `frontend/index.html`.
- Kite Personal API authorization flow is implemented and tested.
- Kite access token is saved locally to `data/kite_access_token.txt`.
- Zerodha equity and Coin mutual fund holdings fetch successfully through `/api/holdings`.
- Binance failures no longer block Zerodha/Coin holdings (returns empty list).
- Dashboard groups holdings into separate panels: Zerodha, Coin, Binance, INDmoney.
- `.env` is ignored via `.codexignore`; `.env.example` remains safe to keep.
- Full backend built from spec: models, db, collectors, analysis modules, main.py, requirements.txt.
- KiteConnect sync calls wrapped in `asyncio.to_thread()` — no event loop blocking.
- Frontend holdings layout changed to 2×2 grid (Row 1: Zerodha | Coin, Row 2: Binance | INDmoney).
- Each source panel table is scrollable (max-height 280px) — no more long unbounded panels.
- Allocation chart panel moved to Row 3 (below holdings), fixed height 460px.
- AI analysis router uses `asyncio.gather()` with 30s timeout and graceful fallback per provider.

## Important Local Files

- `frontend/index.html` - single-file dashboard.
- `backend/main.py` - FastAPI app, frontend serving, Kite auth routes, holdings API.
- `backend/models.py` - Pydantic models; supports `source="indmoney"`.
- `backend/db.py` - aiosqlite layer; auto-creates `data/` directory if missing.
- `backend/collectors/zerodha.py` - Kite/Coin holdings fetcher, token-file fallback, async-safe.
- `backend/collectors/binance.py` - Binance holdings fetcher; returns empty list if keys absent or error.
- `backend/analysis/router.py` - runs Claude, OpenAI, Gemini in parallel with 30s timeout.
- `backend/analysis/claude_analysis.py` - HOLD/REVIEW/TRIM verdicts per asset.
- `backend/analysis/openai_analysis.py` - allocation breakdown vs ideal.
- `backend/analysis/gemini_analysis.py` - risk flags with rule-based pre-seeding.
- `backend/requirements.txt` - all Python dependencies.
- `data/falak.db` - local SQLite database.
- `data/kite_access_token.txt` - local Kite daily access token.
- `.env` - local secrets and runtime paths; do not commit.

## Local Run Commands

From `D:\Dev\Project\falak-finance-monitor`:

```powershell
$env:DB_PATH='data/falak.db'
$env:KITE_ACCESS_TOKEN_FILE='data/kite_access_token.txt'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Kite login/token refresh:

```text
http://127.0.0.1:8765/auth/kite/login
```

## Validation Completed

- `python -m py_compile` passed for all backend files.
- `/health` returns HTTP 200.
- `/` serves the dashboard.
- `/api/holdings` returns Zerodha + Coin holdings after Kite authorization.
- `/api/analyse` route accepts a sample portfolio and returns expected top-level shape.
- Code review: all external calls in try/except, no hardcoded secrets, async throughout.

## Wave 2 — Security & Code Quality (2026-05-12)

### Security Hardening
- Added `slowapi>=0.1.9` rate limiter: `/api/holdings` 10/min, `/api/analyse` 2/min, Kite OAuth 5/min
- Nonce-based CSRF protection on Kite OAuth: cookie set on `/auth/kite/login`, validated+consumed on `/auth/kite/callback`
- Holdings count cap: `/api/analyse` rejects payloads with >500 holdings (HTTP 422)
- Atomic token write in `kite_callback`: writes to `.tmp` then renames to prevent partial-read race

### AI Model Fixes
- `openai_analysis.py`: default model `gpt-5.2` → `gpt-4o` (invalid model was crashing on call)
- `gemini_analysis.py`: default model `gemini-3-pro-preview` → `gemini-1.5-pro` (preview endpoint unstable)

### Logging
- `main.py`: `logging.basicConfig` configured at startup; logs startup, token save, holdings errors, analysis trigger
- `zerodha.py`: logs equity + MF fetch failures before raising
- `binance.py`: logs USD/INR rate fallback with actual exception
- `router.py`: logs per-provider timeout and failure with provider name

### Frontend
- Removed dead first `renderHoldings` definition (flat-table version from old design was silently overriding the source-panel version — only the correct per-source-panel version remains)

### Config
- Added `.env.example` at project root documenting all env vars
- `backend/requirements.txt`: added `slowapi>=0.1.9`

---

## Known Warnings

- `google-generativeai` emits an upstream deprecation warning. Still runs.
- Docker Compose warns that `version: "3.8"` is obsolete (explicitly requested earlier).
- Docker on this Windows machine may warn about access to `C:\Users\moham\.docker\config.json`.
- AI model names in `openai_analysis.py` and `gemini_analysis.py` are set via env vars (`OPENAI_MODEL`, `GEMINI_MODEL`, `ANTHROPIC_MODEL`) with user-chosen defaults — update `.env` if model names change.

## To-Do

1. Add visible frontend status for partial collector errors (e.g. Binance unavailable while Zerodha succeeds).
2. Add INDmoney data path.
   - Decide whether this is CSV import, email statement parsing, or consent-based source.
   - Store imported INDmoney holdings with `source="indmoney"`.
3. Improve AI analysis UX.
   - Show clear UI message when API keys are missing.
   - Make AI providers optional (not all-or-nothing failure).
4. Add manual "Refresh Kite Token" button or clear link in dashboard.
5. Add favicon route to avoid `/favicon.ico` 404 noise.
6. Add tests for:
   - Kite callback token save.
   - `/api/holdings` partial success (Binance down, Zerodha up).
   - Dashboard source grouping.
7. Prepare Falak server deployment.
   - Create production `.env`.
   - Set `TAILSCALE_IP`.
   - Set `DB_PATH=/app/data/falak.db`.
   - Set `KITE_ACCESS_TOKEN_FILE=/app/data/kite_access_token.txt`.
   - Re-test Docker Compose on server.

## Deployment Notes For Falak

- Use Tailscale IP binding in `.env`.
- Do not expose port 8765 publicly through OCI security lists.
- The Kite redirect URL for server deployment must match the deployed host URL.
- Current local redirect URL is:

```text
http://127.0.0.1:8765/auth/kite/callback
```

- Falak deployment redirect URL should become:

```text
http://<falak-tailscale-ip>:8765/auth/kite/callback
```
