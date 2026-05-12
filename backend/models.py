from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel


class Holding(BaseModel):
    symbol: str
    source: Literal["zerodha", "coin", "binance", "indmoney"]
    type: Literal["equity", "mutual_fund", "crypto"]
    quantity: float
    avg_cost: float
    current_price: float
    current_value_inr: float
    unrealised_pnl: float
    unrealised_pnl_pct: float
    currency: str = "INR"


class PortfolioSnapshot(BaseModel):
    timestamp: datetime
    holdings: list[Holding]
    total_value_inr: float
    total_pnl_inr: float
    total_pnl_pct: float


class AnalysisResult(BaseModel):
    claude_verdict: Any
    openai_breakdown: Any
    gemini_risks: Any
    timestamp: datetime
    disclaimer: str = "Not financial advice. For informational purposes only."
