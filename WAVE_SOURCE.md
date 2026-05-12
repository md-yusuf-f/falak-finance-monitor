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

---

## FALAK-FINANCE — Platform Vision (2026-05-12)

This project is evolving from a personal portfolio monitor into **FALAK-FINANCE**: a production-grade AI-assisted financial automation platform.

### Vision

Production platform combining:
- Deterministic trading strategies
- AI-assisted analysis (local Ollama LLM — Qwen2.5/Phi-3)
- Real-time Binance market data (BTCUSDT, ETHUSDT)
- Portfolio monitoring (Zerodha equity/MF + Binance crypto — both kept)
- Telegram-based interaction and alerts
- Grafana/Prometheus observability
- Docker microservices on OCI ARM

### Core Philosophy
- Risk management first
- AI as assistant (veto/filter), not autonomous trader
- Paper trading before any live execution
- Modular, scalable, production-grade

### What Waves 1–6 Built (Foundation — Complete)
- FastAPI backend, rate limiting, CSRF, Kite OAuth
- Zerodha equity + MF + Binance crypto holdings aggregation
- Multi-provider AI analysis: Groq + Falak AI (Ollama) + Gemini
- Price alerts, snapshot history, portfolio charts
- Dark-mode SPA, live 30s auto-refresh
- 19 async tests, Docker + Tailscale OCI deployment

---

## Wave 7 — Telegram Bot (Next)

**Goal**: Notifications and interactive commands via Telegram.

### Deliverables
- `backend/notifications/telegram.py` — bot using `python-telegram-bot`
- `backend/scheduler.py` — APScheduler in same process (no separate worker yet)
- Commands: `/portfolio` (summary), `/health` (system status), `/analyse` (trigger AI analysis)
- Alert breach → push Telegram message automatically
- Daily report at configured time (portfolio snapshot summary)
- New env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### Files to Create/Modify
- `backend/notifications/telegram.py` (new)
- `backend/scheduler.py` (new)
- `backend/main.py` — wire scheduler startup/shutdown lifepan
- `backend/requirements.txt` — add `python-telegram-bot>=21`, `apscheduler>=3.10`
- `.env.example` — document new vars
- `backend/tests/test_notifications.py` (new)

### Verification
1. Bot responds to `/portfolio` with current holdings summary
2. Price alert breach triggers Telegram push within 30s
3. Daily report fires at scheduled time
4. Existing 19 tests still pass

---

## Wave 8 — Binance OHLCV + Technical Indicators

**Goal**: Market data foundation enabling strategy engine.

### Deliverables
- `backend/collectors/market.py` — CCXT candle fetching (BTCUSDT, ETHUSDT)
- `backend/analysis/indicators.py` — RSI, EMA (9/21/50), ATR calculations
- New DB table: `candles(symbol, interval, timestamp, open, high, low, close, volume)`
- Background job: collect 15m candles every 15 minutes
- New endpoint: `GET /api/market/{symbol}/candles?interval=15m&limit=100`
- New endpoint: `GET /api/market/{symbol}/indicators` — current RSI, EMA, ATR

### Dependencies
- `pandas>=2.0`, `pandas-ta>=0.3` for indicators

### Verification
- Fetch 100 candles BTCUSDT, compute RSI 14 — value must match TradingView within ±0.5

---

## Wave 9 — Strategy Engine + Paper Trading

**Goal**: Deterministic trading rules with simulated execution.

### Deliverables
- `backend/strategy/` directory:
  - `engine.py` — rule evaluator
  - `rules.py` — RSI overbought/sold, EMA crossover, ATR-based stop rules
  - `paper_executor.py` — simulated order placement, position tracking
  - `risk.py` — stop-loss, take-profit, cooldown, max drawdown controls
- New DB tables: `paper_positions`, `paper_trades`, `strategy_signals`
- Signal → Telegram notification
- AI veto: strategy signal blocked if Falak AI confidence < threshold

### Safety Constraints
- Max 2% capital per trade (configurable)
- Cooldown: no signal within 4h of last signal on same symbol
- Daily drawdown limit: halt if -5% on day
- Paper mode only — `LIVE_TRADING=false` env guard

### Verification
- Simulated RSI oversold signal → paper buy executed → position tracked → stop-loss fires at configured %
- AI veto test: inject bearish AI sentiment → signal blocked

---

## Wave 10 — PostgreSQL + Redis Migration

**Goal**: Production-grade persistence and caching.

### Deliverables
- PostgreSQL replaces SQLite (`asyncpg` driver)
- Alembic migrations: `alembic/` directory, initial migration from current schema
- Redis cache: holdings (60s TTL), candles (30s TTL), analysis results (5min TTL)
- `backend/cache.py` — Redis wrapper
- `docker-compose.yml`: add `postgres` + `redis` services
- All existing tests updated to use test PostgreSQL container

### Migration Safety
- SQLite kept as fallback until full parity verified on PostgreSQL
- Data migration script: `scripts/migrate_sqlite_to_pg.py`

---

## Wave 11 — Observability

**Goal**: Production monitoring and structured logging.

### Deliverables
- `prometheus-fastapi-instrumentator` — auto HTTP metrics
- `backend/metrics.py` — custom metrics: signals generated, paper trades, AI latency, candle lag
- `python-json-logger` — all logs as structured JSON
- `grafana/dashboards/` — dashboard JSON (portfolio value, API latency, signal rate)
- `docker-compose.yml`: add `prometheus` + `grafana` services
- `/health` expansion: check DB, Redis, Binance, Ollama connectivity with latencies

---

## Wave 12 — AI Intelligence Upgrade

**Goal**: Upgrade Ollama model for trading-specific analysis.

### Deliverables
- Switch Falak AI model: `qwen3:8b` → `qwen2.5:7b` or `phi-3-mini` (ARM-optimized)
- `backend/analysis/trading_ai.py` — trend classification (BULLISH/BEARISH/NEUTRAL)
- Sentiment scoring from crypto news RSS (CoinDesk, CoinTelegraph)
- Confidence score (0–1) per signal
- AI as FILTER: strategy signals require AI confidence ≥ 0.6 to execute
- AI summary pushed to Telegram on demand

---

## Wave 13 — Microservice Split

**Goal**: Proper service boundaries, independent deployment.

### Services
```
services/
├── market-service/      FastAPI, OHLCV, indicators, candle storage
├── strategy-service/    Signals, paper trading, position management
├── ai-service/          All LLM calls (Groq, Falak, Gemini)
├── notification-service/ Telegram bot, alerts, daily reports
└── dashboard-service/   Web UI, portfolio reads, Kite OAuth
```

- Internal communication: shared PostgreSQL + Redis (no inter-service HTTP for now)
- `docker-compose.yml`: 5 services + postgres + redis + prometheus + grafana
- API gateway: Nginx routing by path prefix

---

## Wave 14 — Production Hardening

**Goal**: CI/CD, ARM deployment, secrets management.

### Deliverables
- GitHub Actions: `test → lint → build → push OCI registry → deploy`
- OCI Ampere A1 (ARM64) — verify all Docker images build for `linux/arm64`
- Secrets: OCI Vault integration or `.env` with `chmod 600` + restricted Docker mount
- `pg_dump` cron → OCI Object Storage
- Load test: 100 concurrent `/api/holdings` must complete < 2s p99

---

## To-Do (Active)

### Wave 7 (Start Here)
1. `backend/notifications/telegram.py` — bot setup, commands, alert push
2. `backend/scheduler.py` — APScheduler, daily report job
3. Wire into `backend/main.py` lifespan events
4. Add `python-telegram-bot`, `apscheduler` to requirements
5. Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` to `.env.example`

### Backlog (Pre-Vision)
- **INDmoney integration** — waiting on API. Placeholder panel exists.
- **Favicon** — `/favicon.ico` route to kill 404 log noise
- **Docker Compose** — remove obsolete `version: "3.8"` line
- **Kite token refresh UI** — visible button on dashboard

---

## Deployment Notes

- Tailscale IP binding in production `.env` — never expose 8765 publicly
- Kite redirect URL must match deployed host: `http://<tailscale-ip>:8765/auth/kite/callback`
- Falak AI requires Ollama on same host: `ollama pull qwen2.5:7b`
- Groq cloud: only `GROQ_API_KEY` needed
- PostgreSQL (Wave 10+): `POSTGRES_URL=postgresql+asyncpg://...`
- Redis (Wave 10+): `REDIS_URL=redis://localhost:6379`
