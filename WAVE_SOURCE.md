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

## Wave 7 — Telegram Bot + Kite Token Monitoring (Next)

**Goal**: Notifications and interactive commands via Telegram; automated detection of expired Kite tokens before they silently block execution.

> **Why token monitoring here**: Kite Personal API tokens expire daily and require a full OAuth re-login. Once Wave 9 introduces strategy signals, a stale token will silently block all order-related calls with no alert. Adding detection in Wave 7 — when the scheduler is being set up — costs almost nothing and eliminates a critical silent failure mode.

### Deliverables
- `backend/notifications/telegram.py` — bot using `python-telegram-bot`
- `backend/scheduler.py` — APScheduler in same process (no separate worker yet)
- Commands: `/portfolio` (summary), `/health` (system status), `/analyse` (trigger AI analysis), `/kite_status` (check if token is valid or expired)
- Alert breach → push Telegram message automatically
- Daily report at configured time (portfolio snapshot summary)
- **Kite token expiry check**: scheduler job at `KITE_TOKEN_ALERT_CRON` (default `0 8 * * *`) — reads token file, calls Kite `/user/profile`, sends Telegram alert if token is missing or API returns 403
- Bot sends "Unknown command. Use /help to see available commands." for unrecognised inputs
- New env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `KITE_TOKEN_ALERT_CRON`

### Files to Create/Modify
- `backend/notifications/telegram.py` (new)
- `backend/scheduler.py` (new)
- `backend/main.py` — wire scheduler startup/shutdown lifespan
- `backend/requirements.txt` — add `python-telegram-bot>=21`, `apscheduler>=3.10`
- `.env.example` — document new vars
- `backend/tests/test_notifications.py` (new)

### Verification
1. Bot responds to `/portfolio` with current holdings summary
2. Price alert breach triggers Telegram push within 30s
3. Daily report fires at scheduled time (manually trigger cron job in test)
4. `/kite_status` returns "Token valid" when token file exists and Kite responds 200; returns "Token EXPIRED — re-login at /auth/kite/login" otherwise
5. Scheduler fires token check at 8 AM: simulate missing token file, confirm Telegram message received
6. Bot replies "Unknown command" for arbitrary text input
7. Existing 19 tests still pass

---

## Wave 8 — Binance OHLCV + Technical Indicators

**Goal**: Market data foundation enabling the strategy engine.

### Deliverables
- `backend/collectors/market.py` — CCXT candle fetching (BTCUSDT, ETHUSDT) with `enableRateLimit=True`, max 10 req/min
- `backend/analysis/indicators.py` — RSI 14, EMA (9/21/50), ATR 14 calculations using `pandas-ta`
- New DB table: `candles(symbol, interval, timestamp, open, high, low, close, volume)` with unique constraint on `(symbol, interval, timestamp)`
- Background job (via Wave 7 scheduler): collect 15m candles every 15 minutes
- **Candle gap detection**: if no new candle arrives within 2× the collection interval (30m for 15m feed), scheduler logs a WARNING and sends Telegram alert
- New endpoint: `GET /api/market/{symbol}/candles?interval=15m&limit=100`
- New endpoint: `GET /api/market/{symbol}/indicators` — returns current RSI, EMA stack, ATR

### Dependencies
- `ccxt>=4.2`, `pandas>=2.0`, `pandas-ta>=0.3` for indicators
- Note: `pandas-ta` is minimally maintained; `ta-lib` is the migration path if ARM64 build issues arise (see Wave 12)

### Verification
1. Fetch 100 candles BTCUSDT 15m — all 100 rows stored in `candles` table
2. Compute RSI 14 on stored candles — value matches TradingView within ±0.5
3. Simulate gap: pause CCXT mock for 35 minutes, confirm Telegram gap alert fires
4. `/api/market/BTCUSDT/indicators` returns `rsi`, `ema9`, `ema21`, `ema50`, `atr` fields

---

## Wave 9 — Strategy Engine + Paper Trading

**Goal**: Deterministic trading rules with simulated execution and historical validation before live paper positions.

> **AI veto note**: Wave 9 uses the Groq verdict (HOLD/REVIEW/TRIM) from Wave 6 as its AI filter — not a numeric confidence score. If Groq returns `TRIM` for the traded symbol, the signal is blocked. Numeric confidence scoring (0–1) is introduced in Wave 12 and replaces this simpler gate at that point.

### Deliverables
- `backend/strategy/` directory:
  - `engine.py` — rule evaluator; runs rules against latest indicators, emits `SignalEvent`
  - `rules.py` — RSI oversold (<30) / overbought (>70), EMA 9/21 crossover, ATR-scaled stop distance
  - `paper_executor.py` — simulated order placement, position tracking, fill at last close price
  - `risk.py` — per-trade stop-loss, take-profit, 4h same-symbol cooldown, daily drawdown circuit breaker
  - `backtester.py` — replay stored candles (Wave 8 DB) against strategy rules; outputs win rate, avg return, max drawdown
- New DB tables: `paper_positions`, `paper_trades`, `strategy_signals`
- Signal → Telegram notification (symbol, rule triggered, paper entry price)
- **AI veto**: `engine.py` calls `groq_analysis` on signal symbol; blocks execution if verdict is `TRIM`
- Backtester must be run against ≥ 7 days of stored candles and show positive expectancy before paper trading is enabled

### Safety Constraints
- `EXECUTION_MODE=paper` env guard (default); engine refuses to call any live order API
- Max 2% capital per trade (configurable via `RISK_PER_TRADE_PCT`)
- 4h cooldown per symbol after any signal
- Daily drawdown circuit breaker: halt all paper signals + Telegram alert if paper P&L < -5% on the day

### Verification
1. Run backtester on 7 days of BTCUSDT 15m candles — output shows win rate ≥ 1 trade, max drawdown printed
2. Simulate RSI < 30 → paper BUY executed → row in `paper_positions` → Telegram notification sent
3. Stop-loss test: position open, price drops past stop → paper SELL executed, position closed
4. AI veto test: mock Groq to return `TRIM` → signal generated by rule but NOT executed, veto logged
5. Circuit breaker test: inject -5.1% paper P&L → scheduler halts signal loop + Telegram fires
6. All existing 19 tests still pass; add ≥ 5 new tests for strategy module

---

## Wave 10 — PostgreSQL + Redis Migration

**Goal**: Production-grade persistence and caching; SQLite is not appropriate for concurrent write load from Wave 9's scheduler jobs.

### Deliverables
- PostgreSQL replaces SQLite (`asyncpg` driver)
- Alembic migrations: `alembic/` directory, initial migration covers full current schema including `candles`, `paper_positions`, `paper_trades`, `strategy_signals`
- Redis cache: holdings (60s TTL), candles (30s TTL), analysis results (5min TTL)
- `backend/cache.py` — Redis wrapper (`aioredis`)
- `docker-compose.yml`: add `postgres` + `redis` services
- All existing tests updated to use test PostgreSQL container (via `pytest-docker` or `testcontainers-python`)
- Data migration script: `scripts/migrate_sqlite_to_pg.py` with row-count parity assertion (fails loudly if counts differ)

### Migration Safety
- SQLite path kept in `DB_PATH` env var; PostgreSQL activated by setting `POSTGRES_URL`
- Migration script asserts: row count in SQLite == row count in PostgreSQL for each table before exiting
- SQLite file backed up to `data/falak_pre_migration.db` before migration runs

### Verification
1. Run `scripts/migrate_sqlite_to_pg.py` against populated SQLite — script prints per-table counts and confirms parity
2. Start app with `POSTGRES_URL` set — `/api/holdings` returns same data as before migration
3. Redis cache hit: call `/api/holdings` twice in < 60s, second call served from cache (confirm via log)
4. All tests pass against PostgreSQL container

---

## Wave 11 — Observability

**Goal**: Production monitoring, structured logging, and alerting so regressions surface before users notice.

### Deliverables
- `prometheus-fastapi-instrumentator` — auto HTTP metrics (latency histograms, status code counters)
- `backend/metrics.py` — custom Prometheus metrics: `falak_signals_total`, `falak_paper_trades_total`, `falak_ai_latency_seconds`, `falak_candle_lag_seconds`, `falak_portfolio_value_inr`
- `python-json-logger` — all logs as structured JSON; log fields: `timestamp`, `level`, `module`, `message`, `duration_ms` where applicable
- `grafana/dashboards/falak_overview.json` — dashboard with panels: portfolio value over time, API p95 latency, signals/hour, candle lag, AI provider latency
- `docker-compose.yml`: add `prometheus` + `grafana` services (Prometheus scrape interval 15s)
- **Prometheus alert rules** (`prometheus/alerts.yml`):
  - `CandleLag`: fire if `falak_candle_lag_seconds > 120` for 5m
  - `AILatencyHigh`: fire if `falak_ai_latency_seconds p95 > 10` for 10m
- `/health` expansion: returns JSON with DB, Redis, Binance, Ollama connectivity checks + latency in ms each; HTTP 200 if all pass, 503 if any fail

### Verification
1. Start stack; open Grafana at `http://localhost:3000` — `falak_overview` dashboard loads, `falak_portfolio_value_inr` panel shows data
2. Trigger a paper trade — `falak_paper_trades_total` counter increments in Prometheus
3. Simulate candle lag > 2 min — `CandleLag` alert fires in Prometheus alert manager
4. Call `/health` with Ollama stopped — returns HTTP 503 with `ollama: {ok: false, latency_ms: null}`

---

## Wave 12 — AI Intelligence Upgrade

**Goal**: Upgrade local AI model for trading-specific analysis; add confidence scoring that gates strategy signals from Wave 9 onward.

> **Model selection**: Run ARM64 inference benchmark before committing to a model. Target: < 3s per analysis call on OCI Ampere A1. Candidates: `qwen2.5:7b` (recommended), `phi-3-mini` (smaller, faster). The current `qwen3:8b` is the fallback if newer models underperform.

### Deliverables
- ARM64 benchmark script: `scripts/benchmark_ollama.sh` — times 10 inference calls per model candidate, outputs p50/p95
- Switch Falak AI model based on benchmark result (`FALAK_AI_MODEL` env var); update `.env.example`
- `backend/analysis/trading_ai.py` — trend classification (BULLISH/BEARISH/NEUTRAL) + confidence score (0.0–1.0) per symbol
- Sentiment scoring: fetch last 5 headlines from CoinDesk RSS for symbol, pass to local model, extract sentiment tag
- **Confidence gate replaces Wave 9 Groq-verdict veto**: `engine.py` updated to call `trading_ai.classify(symbol)`, block signal if `confidence < SIGNAL_CONFIDENCE_THRESHOLD` (default 0.6, configurable)
- **Model fallback chain**: `qwen2.5:7b` → `qwen3:8b` (fallback if primary fails) → Groq cloud (final fallback)
- AI summary on demand via Telegram `/analyse` command

### Verification
1. `scripts/benchmark_ollama.sh` runs and prints per-model latency; selected model achieves < 3s p50 on ARM64
2. `trading_ai.classify("BTCUSDT")` returns `{trend: "BULLISH", confidence: 0.72}` shape
3. Confidence gate: inject mock returning `confidence=0.45` → signal blocked; inject `confidence=0.75` → signal passes
4. Model fallback: stop primary Ollama model → fallback to `qwen3:8b` within 5s; stop both → Groq cloud used
5. Sentiment fetch: mock CoinDesk RSS with bearish headlines → `trend` leans BEARISH

---

## Wave 13 — Microservice Split

**Goal**: Proper service boundaries enabling independent deployment and scaling.

> **Extraction order** (do not split all at once — extract one service per PR, verify monolith still works after each):
> 1. `notification_service` (stateless, easiest)
> 2. `ai_service` (all LLM calls; pure function, no DB writes)
> 3. `market_service` (OHLCV + indicators; writes only to `candles`)
> 4. `strategy_service` (signals + paper trading; reads `candles`, writes `paper_*`)
> 5. `dashboard_service` (web UI + Kite OAuth; read-heavy)

### Service Layout

```
services/
├── market_service/       FastAPI, OHLCV, indicators, candle storage
├── strategy_service/     Signals, paper trading, position management
├── ai_service/           All LLM calls (Groq, Falak AI, Gemini)
├── notification_service/ Telegram bot, alerts, daily reports
└── dashboard_service/    Web UI, portfolio reads, Kite OAuth
```

> **Naming**: `snake_case` directory names, consistent with existing `backend/collectors/`, `backend/analysis/` conventions.

### DB Table Ownership

| Service | Owns (writes) | Reads |
|---------|--------------|-------|
| `market_service` | `candles` | — |
| `strategy_service` | `paper_positions`, `paper_trades`, `strategy_signals` | `candles` |
| `ai_service` | — | `candles`, `paper_trades` (for context) |
| `notification_service` | — | `alerts`, `paper_trades`, `strategy_signals` |
| `dashboard_service` | `portfolio_snapshots`, `alerts` | all |

- Internal communication: shared PostgreSQL + Redis (no inter-service HTTP for Wave 13)
- `docker-compose.yml`: 5 services + postgres + redis + prometheus + grafana + nginx
- API gateway: Nginx routes by path prefix (`/api/market/` → `market_service`, `/api/strategy/` → `strategy_service`, `/` → `dashboard_service`)

### Verification
1. After each service extraction: `docker compose up` → all services report healthy in `/health`
2. After full split: `GET /api/holdings` returns data (end-to-end through Nginx → `dashboard_service` → PostgreSQL)
3. Paper trade signal flows: `market_service` writes candle → `strategy_service` evaluates → `notification_service` sends Telegram
4. `ai_service` unavailable (kill container) → strategy falls back to Groq cloud (Wave 12 fallback chain)

---

## Wave 14 — Production Hardening

**Goal**: CI/CD pipeline, ARM64 deployment, secrets management, kill switch, and backup.

### Deliverables
- **GitHub Actions** pipeline: `test → lint (ruff) → build multiarch (linux/arm64, linux/amd64) → push OCI registry → deploy`
- **OCI Ampere A1 (ARM64)**: all Docker images verified to build for `linux/arm64` via `docker buildx`
- **Secrets**: OCI Vault integration or `.env` with `chmod 600` + restricted Docker mount (no secrets in image layers)
- **Kill switch**: `TRADING_ENABLED=false` env var — when false, `strategy_service` accepts no new signals and `paper_executor` / `live_executor` (Wave 15) refuse all order calls; API returns 503 on `/api/strategy/signal`
- **API key rotation SOP** (documented in `docs/runbook.md`): quarterly rotation checklist for Groq, Gemini, Binance, Telegram; steps to rotate without downtime
- **Database backup**: `pg_dump` cron (daily 2 AM) → OCI Object Storage; 90-day retention, 7 daily + 4 weekly snapshots kept
- **Log retention**: structured JSON logs rotated daily, 90-day retention via `logrotate` config
- **Load test**: 100 concurrent requests to `/api/holdings` must complete with p99 < 2s (use `locust` or `k6`)

### Verification
1. GitHub Actions pipeline runs on PR: test + lint pass, multi-arch image builds successfully
2. Deploy to OCI ARM64: `uname -m` in container shows `aarch64`
3. Set `TRADING_ENABLED=false` → `POST /api/strategy/signal` returns 503; strategy scheduler logs "trading disabled"
4. Restore from `pg_dump` backup to a fresh PostgreSQL container — row counts match source
5. Load test: `k6 run --vus 100 --duration 30s load_test.js` → p99 latency < 2s

---

## Wave 15 — Live Trading (Zerodha)

**Goal**: Graduate from paper simulation to real Kite order execution, with hard limits and circuit breakers that enforce the "AI as filter, not autonomous trader" principle.

> **Non-negotiable prerequisite**: Wave 9 paper trading must show positive expectancy over ≥ 30 calendar days before `EXECUTION_MODE=live` is ever set. This is enforced by `live_executor.py` at runtime: it reads `paper_trades` history and refuses to place live orders if the paper window is < 30 days or win rate < 50%.

### Deliverables
- `backend/strategy/live_executor.py` — Kite live order placement via `kiteconnect.place_order()`; reads `EXECUTION_MODE` env var, no-ops silently when `paper`
- `EXECUTION_MODE=paper|live` env var (default: `paper`); separate from `TRADING_ENABLED`
- New DB table: `live_trades(id, symbol, side, qty, price, kite_order_id, status, created_at)`
- **Hard limits (day-1 defaults, all configurable)**:
  - Max 5 live trades per calendar day (`MAX_LIVE_TRADES_PER_DAY=5`)
  - Max 1% NAV per trade (`MAX_TRADE_PCT_NAV=0.01`)
  - Min AI confidence ≥ 0.65 (stricter than paper's 0.6)
- **Circuit breaker**: if live P&L for the day < -2% of NAV → halt all live execution + Telegram alert + set internal flag requiring manual reset
- **Dual audit**: every live order logged to `live_trades` table immediately on placement; Telegram push with order details within 5s
- **Live/paper reconciliation**: daily reconciliation job compares `live_trades` DB against Kite order history; flags any discrepancy via Telegram
- `backend/tests/test_live_executor.py` — all tests use mock Kite client; no real orders in CI

### Safety Constraints
- `live_executor.py` checks paper win rate ≥ 50% over last 30 days; aborts with error if not met
- `TRADING_ENABLED=false` (Wave 14 kill switch) takes priority over `EXECUTION_MODE=live` — checked first
- `KITE_LIVE_ORDER_PRODUCT=MIS` (intraday) by default; `CNC` requires explicit override

### Verification
1. Prerequisite gate: mock paper history < 30 days → `live_executor.place_order()` raises `InsufficientPaperHistoryError`
2. Place mock live order via Kite sandbox (if available) or mock client → row inserted in `live_trades`, Telegram notification received within 5s
3. Circuit breaker: inject live P&L = -2.1% → execution halted, Telegram alert sent, subsequent `place_order()` call raises `CircuitBreakerOpenError`
4. Kill switch: set `TRADING_ENABLED=false` → `place_order()` no-ops regardless of `EXECUTION_MODE`
5. Daily limit: place 5 trades → 6th call raises `DailyLimitExceededError`
6. Reconciliation job: inject a discrepancy between DB and mock Kite history → Telegram alert fires

---

## To-Do (Active)

### Wave 7 (Start Here)
1. `backend/notifications/telegram.py` — bot setup, commands, alert push, unknown-command handler
2. `backend/scheduler.py` — APScheduler, daily report job, Kite token validity check job
3. Wire into `backend/main.py` lifespan events
4. Add `python-telegram-bot>=21`, `apscheduler>=3.10` to requirements
5. Add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `KITE_TOKEN_ALERT_CRON` to `.env.example`

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
- Live trading (Wave 15): `EXECUTION_MODE=live` must be set explicitly; default is `paper`
- Kill switch (Wave 14+): `TRADING_ENABLED=false` halts all signal execution immediately

---

## Wave Review Notes (2026-05-12)

Tracked changes from original Waves 7–14 to this revision:

| Wave | Change |
|------|--------|
| 7 | Added `/kite_status` command; added daily Kite token expiry check job; added `KITE_TOKEN_ALERT_CRON` env var; added 3 new verification steps |
| 8 | Added `enableRateLimit=True` on CCXT; added candle gap detection (2× interval threshold) + Telegram alert; noted `pandas-ta` maintenance status and `ta-lib` migration path; added 2 new verification steps |
| 9 | Fixed forward dependency: AI veto now uses Groq verdict (TRIM = block), not confidence score (Wave 12 feature); added `backtester.py` deliverable; added backtester and end-to-end signal flow verification steps |
| 10 | Added row-count parity assertion to migration script; added SQLite backup step; added Redis cache-hit verification step |
| 11 | Added Prometheus alert rules (`CandleLag`, `AILatencyHigh`); added Grafana smoke-test verification step; added `/health` 503 behaviour on dependency failure |
| 12 | Added ARM64 benchmark script as first deliverable; added model fallback chain (qwen2.5 → qwen3 → Groq cloud); added confidence gate replaces Wave 9 Groq-verdict veto (upgrade path documented) |
| 13 | Fixed service directory naming to `snake_case` (was `kebab-case`); added sequential extraction order; added DB table ownership table; added integration smoke-test verification |
| 14 | Added `TRADING_ENABLED` kill switch; added API key rotation SOP reference; added log retention policy; added `k6` load test verification |
| 15 | **New wave**: Zerodha live trading with prerequisite gate, hard limits, circuit breaker, dual audit, daily reconciliation |