import asyncio
import logging
import os
from pathlib import Path
from kiteconnect import KiteConnect

try:
    from ..models import Holding
except ImportError:
    from models import Holding

log = logging.getLogger(__name__)


def _get_kite() -> KiteConnect:
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN") or _read_access_token_file()
    if not access_token:
        raise ValueError("Kite token expired. Update KITE_ACCESS_TOKEN in .env")
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _read_access_token_file() -> str:
    token_path = Path(os.getenv("KITE_ACCESS_TOKEN_FILE", "data/kite_access_token.txt"))
    if not token_path.exists():
        return ""
    return token_path.read_text(encoding="utf-8").strip()


async def fetch_zerodha_holdings() -> list[Holding]:
    try:
        kite = _get_kite()
    except ValueError:
        raise

    holdings: list[Holding] = []

    try:
        equity = await asyncio.to_thread(kite.holdings)
        for h in equity:
            ltp = h.get("last_price") or h.get("average_price", 0)
            qty = h.get("quantity", 0)
            avg = h.get("average_price", 0)
            value = qty * ltp
            cost = qty * avg
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0.0
            holdings.append(
                Holding(
                    symbol=h["tradingsymbol"],
                    source="zerodha",
                    type="equity",
                    quantity=qty,
                    avg_cost=avg,
                    current_price=ltp,
                    current_value_inr=value,
                    unrealised_pnl=pnl,
                    unrealised_pnl_pct=pnl_pct,
                    currency="INR",
                )
            )
    except Exception as exc:
        log.error("Zerodha equity fetch failed: %s", exc)
        raise RuntimeError(f"Zerodha equity fetch failed: {exc}") from exc

    try:
        mf = await asyncio.to_thread(kite.mf_holdings)
        for h in mf:
            qty = h.get("quantity", 0)
            avg = h.get("average_price", 0)
            nav = h.get("last_price") or avg
            value = qty * nav
            cost = qty * avg
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0.0
            holdings.append(
                Holding(
                    symbol=h["tradingsymbol"],
                    source="coin",
                    type="mutual_fund",
                    quantity=qty,
                    avg_cost=avg,
                    current_price=nav,
                    current_value_inr=value,
                    unrealised_pnl=pnl,
                    unrealised_pnl_pct=pnl_pct,
                    currency="INR",
                )
            )
    except Exception as exc:
        log.error("Zerodha MF fetch failed: %s", exc)
        raise RuntimeError(f"Zerodha MF fetch failed: {exc}") from exc

    return holdings


async def fetch_kite_trades() -> list[dict]:
    try:
        kite = _get_kite()
    except ValueError:
        raise
    try:
        trades = await asyncio.to_thread(kite.trades)
        return trades or []
    except Exception as exc:
        log.error("Kite trades fetch failed: %s", exc)
        raise RuntimeError(f"Kite trades fetch failed: {exc}") from exc
