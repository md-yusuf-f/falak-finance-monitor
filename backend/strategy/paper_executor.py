import os
from datetime import datetime, timezone
from ..db import save_paper_position, get_open_positions, close_paper_position

class PaperExecutor:
    async def execute(self, signal: "SignalEvent") -> None:
        risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT", "0.02"))
        capital = 10000.0
        
        # qty = (RISK_PER_TRADE_PCT * capital) / entry_price
        qty = round((risk_per_trade_pct * capital) / signal.entry_price, 6)
        
        row = {
            "symbol": signal.symbol,
            "side": signal.signal,
            "qty": qty,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "opened_at": signal.timestamp
        }
        await save_paper_position(row)

    async def check_stops(self, current_prices: dict[str, float]) -> list[dict]:
        open_positions = await get_open_positions()
        closed_trades = []
        now = datetime.now(timezone.utc).isoformat()
        
        for pos in open_positions:
            symbol = pos["symbol"]
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            side = pos["side"]
            hit = False
            exit_price = price
            
            if side == "BUY":
                if price <= pos["stop_loss"]:
                    hit = True
                    exit_price = pos["stop_loss"]
                elif price >= pos["take_profit"]:
                    hit = True
                    exit_price = pos["take_profit"]
            elif side == "SELL":
                if price >= pos["stop_loss"]:
                    hit = True
                    exit_price = pos["stop_loss"]
                elif price <= pos["take_profit"]:
                    hit = True
                    exit_price = pos["take_profit"]
            
            if hit:
                # Calculate PnL
                if side == "BUY":
                    pnl = (exit_price - pos["entry_price"]) * pos["qty"]
                else: # SELL
                    pnl = (pos["entry_price"] - exit_price) * pos["qty"]
                
                await close_paper_position(pos["id"], exit_price, pnl, now)
                closed_trades.append({**pos, "exit_price": exit_price, "pnl": pnl, "closed_at": now})
                
        return closed_trades

from .engine import SignalEvent # Deferred import to avoid circular dependency if any
