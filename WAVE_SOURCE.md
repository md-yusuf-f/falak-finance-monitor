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
- `openai_analysis.py`: default model `gpt-5.2` → `gpt-4o`
- `gemini_analysis.py`: default model `gemini-3-pro-preview` → `gemini-1.5-pro`

### Logging
- `main.py`, `zerodha.py`, `binance.py`, `router.py`: structured logging throughout

### Frontend
- Removed dead duplicate `renderHoldings` definition

### Config
- `backend/requirements.txt`: added `slowapi>=0.1.9`

---

## Wave 3 — Test Suite (2026-05-12)

- Added `backend/tests/conftest.py`: async fixtures, per-test isolated SQLite via `monkeypatch`
- Added `backend/tests/test_api.py`: 9 tests — health, holdings (full/partial/both-down), analyse (valid/422), snapshot 404, history empty, OAuth 403
- Added `backend/tests/test_collectors.py`: 6 tests — Zerodha no-token, equity/MF success, equity error, Binance no-keys/error
- Added `backend/tests/test_analysis.py`: 4 tests — all fail, timeout, all succeed, result shape
- Added `pytest.ini` (UTF-8 no-BOM), `backend/requirements-dev.txt`
- 19 tests total, all passing

---

## Wave 4 — Features (2026-05-12)

### New API Endpoints
- `GET /api/trades` — today's Kite trades (5/min rate limit)
- `GET /api/alerts` — list price alerts
- `POST /api/alerts` — create price alert (symbol, above/below, threshold)
- `DELETE /api/alerts/{id}` — remove alert

### New Frontend Features
1. **Partial error banner** — amber warning when one source (e.g. Binance) fails but others succeed
2. **Kite Login button** — in topbar, opens `/auth/kite/login` in new tab
3. **Dark/Light mode toggle** — persisted in `localStorage`; all futuristic effects disabled in light mode
4. **Chart tabs** — "By Type" (equity/MF/crypto) and "By Source" (Zerodha/Coin/Binance) doughnut views
5. **Snapshot diff row** — shows value/P&L change vs previous snapshot using `/api/history`
6. **Today's Trades** — on-demand table from `/api/trades`
7. **Price Alerts** — form to add alerts, list with delete, breach toasts on refresh

### Backend
- `backend/db.py`: added `alerts` table, `save_alert`, `get_alerts`, `delete_alert`
- `backend/models.py`: added `Alert` model, `alert_breaches` field on `PortfolioSnapshot`
- `backend/collectors/zerodha.py`: added `fetch_kite_trades()`
- `backend/main.py`: alert breach check on every `/api/holdings` call

---

## Wave 5 — UI Polish (2026-05-12)

### Futuristic Dark Theme Layer
- Dot-grid radial background on body
- Brand terminal cursor blink animation (`FALAK FINANCE MONITOR_`)
- Topbar cyan gradient bottom line
- Card inner glow + 1px accent border
- Total value and P&L text-shadow glows (cyan/green/red)
- Section title short cyan gradient underline
- Source panel colored left borders by data source (Zerodha purple, Coin cyan, Binance gold, INDmoney green)
- Table header dark gradient, spaced letters
- Row hover left cyan flash
- Button hover `box-shadow` glow
- Thin cyan custom scrollbars
- Toast slide-in + loader pulse animations
- Chart box radial depth gradient
- Analysis card top cyan border
- Badge neon box-shadows
- All effects stripped in light mode

### Live P&L Auto-Refresh
- "Live" toggle button in topbar
- Pulsing green dot + countdown timer (30s interval)
- Background refresh — no loading overlay, data updates in-place
- Respects 10/min rate limit

### Portfolio Value History Chart
- Line chart (Chart.js) below Allocation doughnut
- Shows `total_value_inr` over last 30 snapshots (oldest-first)
- Single `/api/history` fetch serves both diff row and history chart
- Re-renders with correct axis colors on dark/light theme switch
- Updates automatically on Live mode refresh

---

## Wave 6 — AI Provider Swap (2026-05-12)

### Removed
- `anthropic` dependency and `claude_analysis.py` usage
- `openai_analysis.py` (OpenAI) usage
- `claude_verdict` / `openai_breakdown` fields from `AnalysisResult`

### Added
- `backend/analysis/groq_analysis.py` — portfolio HOLD/REVIEW/TRIM verdicts via Groq (`llama-3.3-70b-versatile`, free tier)
- `backend/analysis/falak_analysis.py` — allocation breakdown via local Falak AI server (OpenAI-compatible, default `qwen3:8b` @ `localhost:11434/v1`)
- `AnalysisResult` fields renamed: `groq_verdict`, `falak_breakdown`
- `.env.example` updated with `GROQ_API_KEY`, `FALAK_AI_BASE_URL`, `FALAK_AI_MODEL`, `FALAK_AI_API_KEY`
- Frontend cards renamed: Claude → Groq, GPT-4o → Falak AI

### Bug Fixes
- Double error prefix in analysis cards fixed (frontend was prepending "X analysis failed:" on top of backend message)
- Gemini default model changed `gemini-1.5-pro` → `gemini-1.5-flash` (1.5-pro unavailable on v1beta API)

---

## Important Local Files (updated)

- `frontend/index.html` — single-file dashboard (~1900 lines)
- `backend/main.py` — FastAPI app with all endpoints, rate limiting, OAuth
- `backend/models.py` — Pydantic models: `Holding`, `PortfolioSnapshot`, `AnalysisResult`, `Alert`
- `backend/db.py` — aiosqlite layer: snapshots + alerts tables
- `backend/collectors/zerodha.py` — Kite equity + MF + trades
- `backend/collectors/binance.py` — Binance holdings (silent fail if keys absent)
- `backend/analysis/router.py` — runs Groq + Falak AI + Gemini in parallel, 30s timeout
- `backend/analysis/groq_analysis.py` — Groq portfolio verdict
- `backend/analysis/falak_analysis.py` — Falak AI allocation breakdown
- `backend/analysis/gemini_analysis.py` — Gemini risk flags
- `backend/tests/` — 19 pytest-asyncio tests
- `.env.example` — all required env vars documented

---

## Known Warnings

- `google-generativeai` emits upstream deprecation warning. Still runs.
- Docker Compose warns `version: "3.8"` obsolete.
- Falak AI errors if Ollama not running or model not pulled (`ollama pull qwen3:8b`).

---

## To-Do

### High Priority
1. **INDmoney integration** — waiting on API from user. Panel placeholder exists. Store with `source="indmoney"`.
2. **Falak server deployment**
   - Create production `.env` with Tailscale IP binding
   - Set `DB_PATH=/app/data/falak.db`, `KITE_ACCESS_TOKEN_FILE=/app/data/kite_access_token.txt`
   - Update Kite redirect URL to `http://<falak-tailscale-ip>:8765/auth/kite/callback`
   - Re-test Docker Compose on server

### Medium Priority
3. **CI/CD pipeline** — GitHub Actions: `pytest` + `ruff` lint + Docker build on push
4. **CSV export** — `GET /api/export/csv` for holdings + snapshots (1 endpoint, easy win)
5. **Favicon** — add `/favicon.ico` route to stop 404 noise in logs
6. **Kite token refresh UI** — clear "Refresh Token" button/link visible on dashboard

### Low Priority
7. **React migration** — deferred; revisit when JS exceeds ~4k lines or team grows. Full plan saved.
8. **Remove `anthropic` and `openai` (old)** packages from env if installed — `pip uninstall anthropic` safe now
9. **Docker Compose** — remove obsolete `version: "3.8"` line

---

## Deployment Notes For Falak

- Use Tailscale IP binding in production `.env`.
- Do not expose port 8765 publicly through OCI security lists.
- Kite redirect URL must match deployed host:

```text
http://<falak-tailscale-ip>:8765/auth/kite/callback
```

- Falak AI requires Ollama running on the same host or accessible via `FALAK_AI_BASE_URL`.
- Groq runs in cloud — only `GROQ_API_KEY` needed, no local infra.
