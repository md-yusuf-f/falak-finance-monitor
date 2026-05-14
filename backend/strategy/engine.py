import os
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from .rules import check_rules
from ..analysis import groq_analysis
from ..db import save_strategy_signal

logger = logging.getLogger(__name__)

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
        execution_mode = os.getenv("EXECUTION_MODE")
        if execution_mode != "paper":
            raise RuntimeError("EXECUTION_MODE must be paper")

        last_close = candles[-1]["close"]
        rule_result = check_rules(indicators, last_close)
        if not rule_result:
            return None

        # Cooldown check
        if not await risk.check_cooldown(symbol):
            return None

        # Circuit breaker check
        if not await risk.check_circuit_breaker():
            msg = "⚠️ Circuit breaker active — paper trading halted for today"
            logger.warning(msg)
            if notifier:
                await notifier.send_message(msg)
            return None

        # AI Veto
        verdict = await groq_analysis.get_verdict(symbol)
        if verdict == "TRIM":
            logger.info(f"Signal for {symbol} vetoed by Groq: {verdict}")
            await save_strategy_signal({
                "symbol": symbol,
                "signal": rule_result.signal,
                "rule": rule_result.rule,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "vetoed": 1,
                "veto_reason": f"Groq {verdict}"
            })
            return None

        # Valid signal
        timestamp = datetime.now(timezone.utc).isoformat()
        signal_event = SignalEvent(
            symbol=symbol,
            signal=rule_result.signal,
            rule=rule_result.rule,
            entry_price=last_close,
            stop_loss=rule_result.stop_loss,
            take_profit=rule_result.take_profit,
            timestamp=timestamp
        )

        await executor.execute(signal_event)
        await risk.record_signal(symbol)
        await save_strategy_signal({
            "symbol": symbol,
            "signal": signal_event.signal,
            "rule": signal_event.rule,
            "timestamp": timestamp,
            "vetoed": 0,
            "veto_reason": None
        })

        if notifier:
            msg = (
                f"📊 Signal: {symbol} {signal_event.signal} @ {signal_event.entry_price} | "
                f"Rule: {signal_event.rule} | Stop: {signal_event.stop_loss} | TP: {signal_event.take_profit}"
            )
            await notifier.send_message(msg)

        return signal_event

from .risk import RiskManager
from .paper_executor import PaperExecutor
