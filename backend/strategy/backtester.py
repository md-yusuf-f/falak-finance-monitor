import os
import pandas as pd
from datetime import datetime, timezone
from ..db import get_candles
from ..analysis.indicators import compute_indicators
from .rules import check_rules

class Backtester:
    async def run(self, symbol: str, interval: str = "15m") -> dict:
        candles = await get_candles(symbol, interval, limit=5000)
        if len(candles) < 672:
            raise ValueError(f"Fewer than 672 candles available for {symbol} ({len(candles)})")

        capital = 10000.0
        initial_capital = capital
        risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT", "0.02"))
        
        open_positions = []
        trades_history = []
        peak_capital = initial_capital
        max_drawdown = 0.0

        # Sliding window starts at index 100 to have enough history for indicators
        for i in range(100, len(candles)):
            current_candle = candles[i]
            window = candles[i-100:i]
            
            # 1. Check existing positions
            still_open = []
            for pos in open_positions:
                hit = False
                exit_price = current_candle["close"]
                
                if pos["side"] == "BUY":
                    if current_candle["low"] <= pos["stop_loss"]:
                        hit = True
                        exit_price = pos["stop_loss"]
                    elif current_candle["high"] >= pos["take_profit"]:
                        hit = True
                        exit_price = pos["take_profit"]
                else: # SELL
                    if current_candle["high"] >= pos["stop_loss"]:
                        hit = True
                        exit_price = pos["stop_loss"]
                    elif current_candle["low"] <= pos["take_profit"]:
                        hit = True
                        exit_price = pos["take_profit"]
                
                if hit:
                    if pos["side"] == "BUY":
                        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
                    else:
                        pnl = (pos["entry_price"] - exit_price) * pos["qty"]
                    
                    capital += pnl
                    trades_history.append({
                        "pnl_pct": pnl / (pos["entry_price"] * pos["qty"]) if pos["qty"] > 0 else 0
                    })
                    
                    if capital > peak_capital:
                        peak_capital = capital
                    dd = (peak_capital - capital) / peak_capital
                    if dd > max_drawdown:
                        max_drawdown = dd
                else:
                    still_open.append(pos)
            open_positions = still_open

            # 2. Evaluate new signals
            indicators = compute_indicators(window)
            last_close = window[-1]["close"]
            rule_result = check_rules(indicators, last_close)
            
            if rule_result and not open_positions: # Simple rule: one trade at a time for backtest
                entry_price = current_candle["open"] # Enter at open of current candle
                qty = round((risk_per_trade_pct * capital) / entry_price, 6)
                open_positions.append({
                    "side": rule_result.signal,
                    "qty": qty,
                    "entry_price": entry_price,
                    "stop_loss": rule_result.stop_loss,
                    "take_profit": rule_result.take_profit
                })

        total_trades = len(trades_history)
        wins = len([t for t in trades_history if t["pnl_pct"] > 0])
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        avg_return = sum(t["pnl_pct"] for t in trades_history) / total_trades if total_trades > 0 else 0.0

        return {
            "symbol": symbol,
            "interval": interval,
            "candles_used": len(candles),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "avg_return_pct": round(avg_return * 100, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2)
        }
