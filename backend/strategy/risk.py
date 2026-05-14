import os
from datetime import datetime, timezone, timedelta
from ..db import get_paper_trades_today, save_strategy_signal, DB_PATH
import aiosqlite

class RiskManager:
    COOLDOWN_HOURS: int = 4

    async def check_cooldown(self, symbol: str) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT timestamp FROM strategy_signals WHERE symbol = ? AND vetoed = 0 ORDER BY id DESC LIMIT 1",
                (symbol,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return True
                
                last_signal_time = datetime.fromisoformat(row["timestamp"])
                if datetime.now(timezone.utc) - last_signal_time > timedelta(hours=self.COOLDOWN_HOURS):
                    return True
                return False

    async def check_circuit_breaker(self) -> bool:
        trades = await get_paper_trades_today()
        total_pnl = sum(t["pnl"] for t in trades)
        
        capital = 10000.0
        drawdown_limit = float(os.getenv("DAILY_DRAWDOWN_LIMIT", "-0.05"))
        
        if total_pnl < drawdown_limit * capital:
            return False
        return True

    async def record_signal(self, symbol: str) -> None:
        # record_signal is called by engine.py, but engine already calls save_strategy_signal.
        # Per spec: "can be a no-op if signal already recorded — do not double-insert"
        pass
