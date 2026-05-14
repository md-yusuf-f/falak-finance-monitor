import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from backend.strategy.rules import check_rules
from backend.strategy.engine import StrategyEngine, SignalEvent
from backend.strategy.risk import RiskManager
from backend.strategy.paper_executor import PaperExecutor
from backend.db import init_db, save_paper_position, get_open_positions

@pytest.mark.asyncio
async def test_rsi_oversold_generates_buy_signal():
    indicators = {"rsi": 28.5, "ema9": 100, "ema21": 102, "ema50": 105, "atr": 500}
    last_close = 42000
    result = check_rules(indicators, last_close)
    assert result.signal == "BUY"
    assert result.rule == "rsi_oversold"
    assert result.stop_loss == last_close - 500 * 1.5
    assert result.take_profit == last_close + 500 * 2.0

@pytest.mark.asyncio
async def test_rsi_overbought_generates_sell_signal():
    indicators = {"rsi": 72.1, "ema9": 102, "ema21": 100, "ema50": 99, "atr": 500}
    last_close = 42000
    result = check_rules(indicators, last_close)
    assert result.signal == "SELL"
    assert result.rule == "rsi_overbought"
    assert result.stop_loss == last_close + 500 * 1.5
    assert result.take_profit == last_close - 500 * 2.0

@pytest.mark.asyncio
async def test_no_signal_when_rsi_neutral():
    indicators = {"rsi": 55, "ema9": 90, "ema21": 100, "ema50": 110, "atr": 500}
    last_close = 42000
    result = check_rules(indicators, last_close)
    assert result is None

@pytest.mark.asyncio
async def test_groq_trim_vetoes_signal(monkeypatch, tmp_path):
    # Set DB_PATH and initialize DB
    monkeypatch.setattr("backend.db.DB_PATH", str(tmp_path / "test_veto.db"))
    from backend.db import init_db
    await init_db()

    monkeypatch.setenv("EXECUTION_MODE", "paper")
    engine = StrategyEngine()
    risk = AsyncMock(spec=RiskManager)
    risk.check_cooldown.return_value = True
    risk.check_circuit_breaker.return_value = True
    executor = AsyncMock(spec=PaperExecutor)
    notifier = AsyncMock()

    indicators = {"rsi": 28.5, "ema9": 100, "ema21": 102, "ema50": 105, "atr": 500}
    candles = [{"close": 42000}]

    with patch("backend.analysis.groq_analysis.get_verdict", new_callable=AsyncMock) as mock_verdict:
        mock_verdict.return_value = "TRIM"
        # We don't need to patch save_strategy_signal if we have a real DB, 
        # but the test asks to assert it was called.
        # Actually, let's just assert it exists in DB.
        result = await engine.evaluate("BTC/USDT", indicators, candles, risk, executor, notifier)
        assert result is None
        
        from backend.db import DB_PATH
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM strategy_signals") as cursor:
                rows = await cursor.fetchall()
                assert len(rows) == 1
                assert rows[0]["vetoed"] == 1
                assert "Groq TRIM" in rows[0]["veto_reason"]

@pytest.mark.asyncio
async def test_circuit_breaker_halts_signals(monkeypatch):
    monkeypatch.setenv("DAILY_DRAWDOWN_LIMIT", "-0.05")
    risk = RiskManager()
    
    # Mocking get_paper_trades_today to return trades with total pnl = -520 (capital 10000, drawdown -5.2%)
    with patch("backend.strategy.risk.get_paper_trades_today", new_callable=AsyncMock) as mock_trades:
        mock_trades.return_value = [{"pnl": -520}]
        result = await risk.check_circuit_breaker()
        assert result is False

@pytest.mark.asyncio
async def test_paper_executor_saves_position(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.db.DB_PATH", str(tmp_path / "test_executor.db"))
    from backend.db import init_db
    await init_db()
    
    executor = PaperExecutor()
    signal = SignalEvent(
        symbol="BTC/USDT",
        signal="BUY",
        rule="rsi_oversold",
        entry_price=40000.0,
        stop_loss=39000.0,
        take_profit=42000.0,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    # Patch where it is USED
    with patch("backend.strategy.paper_executor.save_paper_position", new_callable=AsyncMock) as mock_save:
        await executor.execute(signal)
        mock_save.assert_called_once()
        args = mock_save.call_args[0][0]
        assert args["symbol"] == "BTC/USDT"
        assert args["side"] == "BUY"
        assert args["entry_price"] == 40000.0

@pytest.mark.asyncio
async def test_backtester_requires_7_days():
    from backend.strategy.backtester import Backtester
    bt = Backtester()
    with patch("backend.strategy.backtester.get_candles", new_callable=AsyncMock) as mock_candles:
        mock_candles.return_value = [{"close": 100}] * 100 # < 672
        with pytest.raises(ValueError, match="Fewer than 672 candles available"):
            await bt.run("BTC/USDT")
