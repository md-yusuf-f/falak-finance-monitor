You are implementing Wave 9 of the falak-finance-monitor project.
This is a FastAPI backend (Python 3.12) running on Windows, deployed via Docker + Tailscale on OCI ARM64.

## Current project state (after Wave 8)

backend/
  main.py              # FastAPI app, lifespan, all endpoints, rate limiting
  models.py            # Holding, PortfolioSnapshot, AnalysisResult, Alert
  db.py                # aiosqlite layer — snapshots + alerts + candles tables
  scheduler.py         # APScheduler: daily_report, kite_token_check, candle_collect, candle_gap_check
  requirements.txt
  requirements-dev.txt
  collectors/
    __init__.py        # exports fetch_zerodha_holdings, fetch_binance_holdings, fetch_kite_trades, fetch_candles
    zerodha.py
    binance.py
    market.py          # fetch_candles() via CCXT, enableRateLimit=True
  analysis/
    __init__.py
    router.py          # run_analysis() — Groq + Falak AI + Gemini in parallel
    groq_analysis.py   # portfolio HOLD/REVIEW/TRIM verdict (llama-3.3-70b-versatile)
    falak_analysis.py
    gemini_analysis.py
    indicators.py      # compute_indicators() — RSI 14, EMA 9/21/50, ATR 14 via ta library
  notifications/
    __init__.py
    telegram.py        # TelegramNotifier with bot commands + alert push
  tests/
    conftest.py
    test_api.py        # 9 tests
    test_collectors.py # 6 tests
    test_analysis.py   # 4 tests
    test_notifications.py # 7 tests
    test_market.py     # 9 tests  (35 total, all passing)
.env.example

## Wave 9 deliverables — implement ALL of these

### 1. backend/db.py — add three tables

Add to `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    opened_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    signal TEXT NOT NULL,
    rule TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    vetoed INTEGER NOT NULL DEFAULT 0,
    veto_reason TEXT
)
```

Add these async functions:
- `save_paper_position(row: dict)` — INSERT into paper_positions; row has keys: symbol, side, qty, entry_price, stop_loss, take_profit, opened_at
- `get_open_positions(symbol: str | None = None) -> list[dict]` — fetch all rows from paper_positions; filter by symbol if provided
- `close_paper_position(position_id: int, exit_price: float, pnl: float, closed_at: str)` — DELETE from paper_positions where id=?, INSERT into paper_trades
- `get_paper_trades_today() -> list[dict]` — fetch paper_trades where closed_at starts with today's date (UTC)
- `save_strategy_signal(row: dict)` — INSERT into strategy_signals; row has keys: symbol, signal, rule, timestamp, vetoed, veto_reason

### 2. backend/strategy/ (new directory)

Create `backend/strategy/__init__.py`:
```python
from .engine import StrategyEngine, SignalEvent
from .rules import check_rules
from .paper_executor import PaperExecutor
from .risk import RiskManager
from .backtester import Backtester

__all__ = [
    "StrategyEngine", "SignalEvent",
    "check_rules",
    "PaperExecutor",
    "RiskManager",
    "Backtester",
]
```

### 3. backend/strategy/rules.py (new)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class RuleResult:
    signal: str          # "BUY" or "SELL"
    rule: str            # human-readable rule name
    stop_loss: float
    take_profit: float

def check_rules(indicators: dict, last_close: float) -> Optional[RuleResult]:
```

- Evaluate rules in priority order; return first match or None
- Rule 1 `rsi_oversold`: if `indicators["rsi"]` < 30 → BUY signal; stop = last_close - indicators["atr"] * 1.5; take_profit = last_close + indicators["atr"] * 2.0
- Rule 2 `rsi_overbought`: if `indicators["rsi"]` > 70 → SELL signal; stop = last_close + indicators["atr"] * 1.5; take_profit = last_close - indicators["atr"] * 2.0
- Rule 3 `ema_crossover_bullish`: if `indicators["ema9"]` > `indicators["ema21"]` and `indicators["ema9"] - indicators["ema21"]` < indicators["atr"] * 0.5 → BUY; same stop/take_profit formula as rsi_oversold
- Returns None if no rule fires
- Raises `ValueError` if any required key in indicators is None

### 4. backend/strategy/engine.py (new)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SignalEvent:
    symbol: str
    signal: str         # "BUY" or "SELL"
    rule: str
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: str      # ISO 8601 UTC

class StrategyEngine:
    async def evaluate(
        self,
        symbol: str,
        indicators: dict,
        candles: list[dict],
        risk: "RiskManager",
        executor: "PaperExecutor",
        notifier,            # TelegramNotifier | None
    ) -> Optional[SignalEvent]:
```

- Checks `EXECUTION_MODE` env var; if not `"paper"`, raises `RuntimeError("EXECUTION_MODE must be paper")`
- Calls `check_rules(indicators, last_close=candles[-1]["close"])`; if None → return None
- Calls `risk.check_cooldown(symbol)`; if False → return None (cooldown active)
- Calls `risk.check_circuit_breaker()`; if False → log WARNING + send Telegram alert "⚠️ Circuit breaker active — paper trading halted for today"; return None
- AI veto: import and call `groq_analysis.get_verdict(symbol)` (see note below); if verdict is `"TRIM"` → log veto, call `save_strategy_signal` with vetoed=1, veto_reason="Groq TRIM", return None
- If all checks pass: build `SignalEvent`, call `executor.execute(signal_event)`, call `risk.record_signal(symbol)`, call `save_strategy_signal` with vetoed=0, send Telegram notification: `f"📊 Signal: {symbol} {signal_event.signal} @ {signal_event.entry_price} | Rule: {signal_event.rule} | Stop: {signal_event.stop_loss} | TP: {signal_event.take_profit}"`
- Returns `SignalEvent`

**Note on AI veto**: `groq_analysis.py` currently has `run_groq_analysis(holdings: list) -> str` which accepts portfolio holdings. For Wave 9, add a new function `get_verdict(symbol: str) -> str` to `backend/analysis/groq_analysis.py` that sends a single-symbol check: prompt `"Is {symbol} a HOLD, REVIEW, or TRIM right now? Reply with one word only."` using the same Groq client setup. Returns `"HOLD"` on any exception (fail-safe default — do not block signals on Groq errors).

### 5. backend/strategy/paper_executor.py (new)

```python
class PaperExecutor:
    async def execute(self, signal: "SignalEvent") -> None:
    async def check_stops(self, current_prices: dict[str, float]) -> list[dict]:
```

- `execute()`: calls `save_paper_position()` with signal data; qty = computed from `RISK_PER_TRADE_PCT` (default 0.02) * 10000 (fixed paper capital) / entry_price (rounded to 6 dp)
- `check_stops(current_prices)`: loads all open positions via `get_open_positions()`; for each position, checks if current price crossed stop_loss or take_profit; closes via `close_paper_position()` with calculated PnL; returns list of closed position dicts

### 6. backend/strategy/risk.py (new)

```python
class RiskManager:
    COOLDOWN_HOURS: int = 4

    async def check_cooldown(self, symbol: str) -> bool:
    async def check_circuit_breaker(self) -> bool:
    async def record_signal(self, symbol: str) -> None:
```

- `check_cooldown(symbol)`: queries `strategy_signals` for the most recent signal for `symbol` where `vetoed=0`; returns True if no signal found OR last signal timestamp is > 4h ago; returns False (cooldown active) otherwise
- `check_circuit_breaker()`: calls `get_paper_trades_today()`; sums all `pnl` values; if total < `DAILY_DRAWDOWN_LIMIT` * 10000 (paper capital) → returns False; otherwise True; default `DAILY_DRAWDOWN_LIMIT` = float(os.getenv("DAILY_DRAWDOWN_LIMIT", "-0.05"))
- `record_signal(symbol)`: inserts a row into `strategy_signals` to mark cooldown start (this is also done in engine.py via `save_strategy_signal`, so `record_signal` can be a no-op if signal already recorded — do not double-insert)

### 7. backend/strategy/backtester.py (new)

```python
class Backtester:
    async def run(self, symbol: str, interval: str = "15m") -> dict:
```

- Calls `get_candles(symbol, interval, limit=5000)` (fetches up to 5000 candles from DB)
- Raises `ValueError` if fewer than 672 candles available (672 = 7 days × 24h × 4 per hour for 15m)
- Replays candles in order using a sliding window of 100 candles to compute `compute_indicators()`
- At each step, calls `check_rules(indicators, last_close=candle["close"])`
- Tracks: paper_capital=10000, paper_positions (open trades), paper_trades_history (closed trades)
- Position sizing: same as `PaperExecutor` (RISK_PER_TRADE_PCT * capital / entry_price)
- Closes positions when stop_loss or take_profit hit in subsequent candles
- Returns dict:
  ```python
  {
      "symbol": symbol,
      "interval": interval,
      "candles_used": int,
      "total_trades": int,
      "win_rate": float,        # wins / total_trades, or 0.0 if no trades
      "avg_return_pct": float,  # avg pnl per trade as % of entry
      "max_drawdown_pct": float # max drawdown from peak capital as %
  }
  ```

### 8. backend/scheduler.py — add one job

Add Job 5 to `Scheduler.start()`:

Job 5: `strategy_run` — interval every 15 minutes, offset by 5 minutes (start 5 min after scheduler start, so it runs after `candle_collect` + processing time)
- For each symbol in `["BTC/USDT", "ETH/USDT"]`:
  - Calls `get_candles(symbol, "15m", limit=200)` — needs at least 50 for indicators
  - If < 50 candles: logs INFO "Not enough candles for {symbol}, skipping" and continues
  - Calls `compute_indicators(candles)`
  - Calls `engine.evaluate(symbol, indicators, candles, risk, executor, notifier)`
  - Calls `executor.check_stops({symbol: candles[-1]["close"]})`
- Catches all exceptions internally; logs ERROR on failure
- Uses shared `StrategyEngine`, `RiskManager`, `PaperExecutor` instances (instantiate once in `Scheduler.__init__`)

### 9. backend/analysis/groq_analysis.py — add one function

Add to existing file (do NOT modify existing `run_groq_analysis` function):

```python
async def get_verdict(symbol: str) -> str:
```

- Uses same `AsyncGroq` client setup as existing function
- Sends prompt: `f"For the asset {symbol}, reply with exactly one word — HOLD, REVIEW, or TRIM — based on current market conditions."`
- Returns the stripped uppercase first word of the response
- On any exception: logs WARNING and returns `"HOLD"` (fail-safe — never block signals due to Groq errors)

### 10. .env.example additions

Add:
```
EXECUTION_MODE=paper            # paper or live (live not available until Wave 15)
RISK_PER_TRADE_PCT=0.02         # 2% of paper capital per trade
DAILY_DRAWDOWN_LIMIT=-0.05      # halt paper trading if daily P&L < -5%
```

### 11. backend/tests/test_strategy.py (new)

Write pytest-asyncio tests:

1. `test_rsi_oversold_generates_buy_signal` — call `check_rules({"rsi": 28.5, "ema9": 100, "ema21": 102, "ema50": 105, "atr": 500}, 42000)`, assert result.signal == "BUY" and result.rule == "rsi_oversold"
2. `test_rsi_overbought_generates_sell_signal` — call `check_rules({"rsi": 72.1, "ema9": 102, "ema21": 100, "ema50": 99, "atr": 500}, 42000)`, assert result.signal == "SELL" and result.rule == "rsi_overbought"
3. `test_no_signal_when_rsi_neutral` — RSI=55, ema9 < ema21 → `check_rules()` returns None
4. `test_groq_trim_vetoes_signal` — mock `groq_analysis.get_verdict` to return "TRIM"; mock `check_rules` to return a BUY RuleResult; mock risk (cooldown OK, circuit breaker OK); call `engine.evaluate()`; assert result is None; assert `save_strategy_signal` called with vetoed=1
5. `test_circuit_breaker_halts_signals` — mock `get_paper_trades_today` returning trades with total pnl = -520 (capital 10000, drawdown -5.2%); call `risk.check_circuit_breaker()`; assert returns False
6. `test_paper_executor_saves_position` — call `executor.execute(signal_event)` with mocked `save_paper_position`; assert called once with correct symbol/side/entry_price keys
7. `test_backtester_requires_7_days` — mock `get_candles` returning 100 candles (< 672); assert `ValueError` raised

## Rules

- NEVER mock the database in tests — use real aiosqlite with temp file via existing conftest.py fixtures for DB tests; use `unittest.mock.patch` only for external calls (Groq, Telegram)
- Keep all new files under 500 lines; `backtester.py` is the most at-risk — keep logic tight
- `EXECUTION_MODE=paper` guard must be the FIRST check in `engine.evaluate()` — before any DB reads
- All DB calls are async — no sync aiosqlite usage
- `get_verdict()` in groq_analysis.py must NEVER raise — return "HOLD" on any error
- Run `python -m py_compile backend/strategy/engine.py backend/strategy/rules.py backend/strategy/paper_executor.py backend/strategy/risk.py backend/strategy/backtester.py backend/db.py backend/scheduler.py backend/analysis/groq_analysis.py` after writing — fix any syntax errors
- Run existing tests: `python -m pytest backend/tests/ -v` — all 35 must still pass after your changes
- Do not modify any existing test files

## What NOT to do

- Do not implement `EXECUTION_MODE=live` — that is Wave 15
- Do not add new API endpoints — strategy runs via scheduler only in Wave 9
- Do not install packages — strategy module uses only stdlib + existing deps (aiosqlite, ta, pandas)
- Do not create Docker files or CI configs
- Do not add features beyond the spec above
- Do not create documentation files

## Finish criteria

- All 11 items above implemented
- `py_compile` passes on all new/modified Python files
- All 35 existing tests pass
- At least 5 new tests in `test_strategy.py` pass
- Backtester runs to completion (may show 0 trades if candle history < 7 days — that is acceptable; it must not crash)
- Report which files were created/modified and final test count
