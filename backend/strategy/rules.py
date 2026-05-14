from dataclasses import dataclass
from typing import Optional

@dataclass
class RuleResult:
    signal: str          # "BUY" or "SELL"
    rule: str            # human-readable rule name
    stop_loss: float
    take_profit: float

def check_rules(indicators: dict, last_close: float) -> Optional[RuleResult]:
    required_keys = ["rsi", "ema9", "ema21", "atr"]
    for key in required_keys:
        if indicators.get(key) is None:
            raise ValueError(f"Indicator {key} is None")

    rsi = indicators["rsi"]
    ema9 = indicators["ema9"]
    ema21 = indicators["ema21"]
    atr = indicators["atr"]

    # Rule 1: rsi_oversold
    if rsi < 30:
        return RuleResult(
            signal="BUY",
            rule="rsi_oversold",
            stop_loss=last_close - atr * 1.5,
            take_profit=last_close + atr * 2.0
        )

    # Rule 2: rsi_overbought
    if rsi > 70:
        return RuleResult(
            signal="SELL",
            rule="rsi_overbought",
            stop_loss=last_close + atr * 1.5,
            take_profit=last_close - atr * 2.0
        )

    # Rule 3: ema_crossover_bullish
    if ema9 > ema21 and (ema9 - ema21) < atr * 0.5:
        return RuleResult(
            signal="BUY",
            rule="ema_crossover_bullish",
            stop_loss=last_close - atr * 1.5,
            take_profit=last_close + atr * 2.0
        )

    return None
