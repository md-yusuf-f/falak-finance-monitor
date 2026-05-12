try:
    import pandas as pd
    import ta
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def compute_indicators(candles: list[dict]) -> dict:
    if not PANDAS_AVAILABLE:
        raise RuntimeError("pandas and ta are required for indicators")

    if len(candles) < 50:
        raise ValueError("Insufficient candle data (need >= 50)")

    df = pd.DataFrame(candles)
    close = pd.to_numeric(df["close"])
    high = pd.to_numeric(df["high"])
    low = pd.to_numeric(df["low"])

    rsi_val = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    ema9_val = ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1]
    ema21_val = ta.trend.EMAIndicator(close, window=21).ema_indicator().iloc[-1]
    ema50_val = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]
    atr_val = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]

    def clean(val):
        if pd.isna(val):
            return None
        return round(float(val), 2)

    return {
        "rsi": clean(rsi_val),
        "ema9": clean(ema9_val),
        "ema21": clean(ema21_val),
        "ema50": clean(ema50_val),
        "atr": clean(atr_val),
    }
