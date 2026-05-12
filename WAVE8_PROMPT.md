You are implementing Wave 8 of the falak-finance-monitor project.
This is a FastAPI backend (Python 3.12) running on Windows, deployed via Docker + Tailscale on OCI ARM64.

## Current project state (after Wave 7)

backend/
  main.py              # FastAPI app, lifespan, all endpoints, rate limiting
  models.py            # Holding, PortfolioSnapshot, AnalysisResult, Alert
  db.py                # aiosqlite layer — snapshots + alerts tables
  scheduler.py         # APScheduler with daily_report + kite_token_check jobs
  requirements.txt
  requirements-dev.txt
  collectors/
    __init__.py        # exports fetch_zerodha_holdings, fetch_binance_holdings, fetch_kite_trades
    zerodha.py
    binance.py
  analysis/
    __init__.py
    router.py          # run_analysis() — Groq + Falak AI + Gemini in parallel
    groq_analysis.py
    falak_analysis.py
    gemini_analysis.py
  notifications/
    __init__.py
    telegram.py        # TelegramNotifier with bot commands + alert push
  tests/
    conftest.py
    test_api.py        # 9 tests
    test_collectors.py # 6 tests
    test_analysis.py   # 4 tests
    test_notifications.py # 7 tests  (26 total, all passing)
.env.example

## Wave 8 deliverables — implement ALL of these

### 1. backend/db.py — add candles table

Add to `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    UNIQUE(symbol, interval, timestamp)
)
```

Add these async functions:
- `save_candles(rows: list[dict])` — bulk upsert using `INSERT OR IGNORE`; each dict has keys: symbol, interval, timestamp (ISO string), open, high, low, close, volume
- `get_candles(symbol: str, interval: str, limit: int = 100) -> list[dict]` — fetch most recent `limit` rows ordered by timestamp DESC, return oldest-first

### 2. backend/collectors/market.py (new)

```python
async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 100) -> list[dict]:
```
- Uses `ccxt.binance({"enableRateLimit": True})`
- Calls `exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)` via `asyncio.to_thread()`
- Maps CCXT output `[timestamp_ms, open, high, low, close, volume]` to dicts with keys: symbol, interval, timestamp (ISO 8601 UTC string from ms), open, high, low, close, volume
- Raises `ValueError` if symbol is empty or limit < 1
- Wraps network call in try/except; re-raises as `RuntimeError("CCXT fetch failed: {exc}")`

Export from `collectors/__init__.py`: add `fetch_candles`.

### 3. backend/analysis/indicators.py (new)

```python
def compute_indicators(candles: list[dict]) -> dict:
```
- Input: list of candle dicts (oldest first), must have `close`, `high`, `low` keys
- Raises `ValueError` if fewer than 50 candles (not enough data for EMA-50)
- Uses `pandas_ta` to compute on a `pandas.DataFrame`:
  - RSI 14 → key `rsi` (last value, rounded to 2 dp)
  - EMA 9 → key `ema9`
  - EMA 21 → key `ema21`
  - EMA 50 → key `ema50`
  - ATR 14 → key `atr`
- Returns dict with those 5 keys; any NaN value → `None`

### 4. backend/scheduler.py — add two jobs

Add to `Scheduler.start()`:

Job 3: `candle_collect` — interval every 15 minutes (use `IntervalTrigger(minutes=15)`)
- Fetches 100 candles for each of `["BTC/USDT", "ETH/USDT"]` using `fetch_candles()`
- Saves to DB via `save_candles()`
- Logs count of new rows inserted
- Catches all exceptions internally

Job 4: `candle_gap_check` — interval every 15 minutes (offset by 1 minute; use `IntervalTrigger(minutes=15, start_date=...)` — start 1 min after scheduler start)
- For each symbol `["BTC/USDT", "ETH/USDT"]`: calls `get_candles(symbol, "15m", limit=1)` to get latest stored candle
- Parses timestamp; if latest candle is older than 30 minutes → sends Telegram alert: `"⚠️ Candle gap detected: {symbol} 15m — last candle {age_minutes}m ago"` and logs WARNING
- If no candles exist yet for symbol, skips silently (not an error during startup)

### 5. backend/main.py — add two endpoints

```python
@app.get("/api/market/{symbol}/candles")
async def get_market_candles(symbol: str, interval: str = "15m", limit: int = 100):
```
- Validates: `limit` must be 1–500 (raise HTTP 422 if not); `symbol` must be non-empty
- Fetches from DB via `get_candles(symbol.upper(), interval, limit)`
- Returns `{"symbol": symbol.upper(), "interval": interval, "candles": rows}`

```python
@app.get("/api/market/{symbol}/indicators")
async def get_market_indicators(symbol: str, interval: str = "15m"):
```
- Fetches last 200 candles from DB for the symbol
- If fewer than 50 candles: returns HTTP 422 with detail `"Insufficient candle data (need ≥ 50)"`
- Calls `compute_indicators(candles)` and returns result dict directly
- Wraps in try/except; HTTP 500 on unexpected error

### 6. backend/requirements.txt additions

Add:
  ccxt>=4.2
  pandas>=2.0
  pandas-ta>=0.3

### 7. .env.example additions

Add:
  MARKET_SYMBOLS=BTC/USDT,ETH/USDT   # comma-separated symbols for candle collection

### 8. backend/tests/test_market.py (new)

Write pytest-asyncio tests:
1. `test_fetch_candles_returns_list` — mock `asyncio.to_thread` to return 5 fake OHLCV rows; assert returns 5 dicts with correct keys
2. `test_fetch_candles_empty_symbol_raises` — assert `ValueError` raised
3. `test_save_and_get_candles` — insert 10 candle rows via `save_candles()`, call `get_candles()`, assert 10 rows returned oldest-first (use real aiosqlite temp DB via conftest fixtures)
4. `test_save_candles_ignores_duplicates` — insert same row twice, assert only 1 row in DB
5. `test_compute_indicators_requires_50_candles` — assert `ValueError` raised with 49 candles
6. `test_compute_indicators_returns_all_keys` — generate 100 fake candles (incrementing close price), assert result has `rsi`, `ema9`, `ema21`, `ema50`, `atr` keys
7. `test_market_candles_endpoint` — via TestClient, mock `get_candles` to return 5 rows, assert 200 + correct shape
8. `test_market_candles_invalid_limit` — `limit=0` → HTTP 422
9. `test_market_indicators_insufficient_data` — mock `get_candles` returns 10 rows → HTTP 422

## Rules
- NEVER mock the database in tests — use real aiosqlite with temp file (follow existing conftest.py pattern)
- Keep all new files under 500 lines
- No hardcoded secrets or symbol names — read from env where appropriate
- Async throughout — use `asyncio.to_thread()` for any sync CCXT calls
- All external calls (CCXT network) wrapped in try/except
- Run `python -m py_compile backend/collectors/market.py backend/analysis/indicators.py backend/main.py backend/db.py backend/scheduler.py` after writing — fix any syntax errors
- Run existing tests: `python -m pytest backend/tests/ -v` — all 26 must still pass after your changes
- Do not modify any existing test files

## What NOT to do
- Do not install packages — just update requirements.txt
- Do not create Docker files or CI configs
- Do not add features beyond the spec above
- Do not create documentation files
- Do not use `ta-lib` — use `pandas-ta` only

## Finish criteria
- All 9 items above implemented
- `py_compile` passes on all new/modified Python files
- All 26 existing tests pass
- At least 7 new tests in test_market.py pass
- Report which files were created/modified and final test count
