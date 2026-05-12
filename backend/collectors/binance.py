import asyncio
import logging
import os

import aiohttp
import ccxt.async_support as ccxt

try:
    from ..models import Holding
except ImportError:
    from models import Holding

log = logging.getLogger(__name__)
DUST_THRESHOLD_USD = 1.0
_FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=INR"


async def _live_usd_inr() -> float:
    fallback = float(os.getenv("FALLBACK_USD_INR", "84.0"))
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_FRANKFURTER_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                return float(data["rates"]["INR"])
    except Exception as exc:
        log.warning("USD/INR rate fetch failed (%s), using fallback %.2f", exc, fallback)
        return fallback


async def _avg_cost_usd(exchange: ccxt.binance, asset: str) -> float | None:
    if asset == "USDT":
        return 1.0
    try:
        trades = await exchange.fetch_my_trades(f"{asset}/USDT")
    except Exception:
        return None

    total_qty = 0.0
    total_cost = 0.0
    for t in trades:
        if t.get("side") == "buy":
            q = float(t.get("amount") or 0)
            p = float(t.get("price") or 0)
            total_qty += q
            total_cost += q * p

    return (total_cost / total_qty) if total_qty > 0 else None


async def fetch_binance_holdings() -> list[Holding]:
    api_key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_SECRET_KEY")
    if not api_key or not secret:
        return []

    exchange = ccxt.binance(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot", "recvWindow": 60000, "adjustForTimeDifference": True},
        }
    )

    try:
        usd_inr, balance, tickers = await asyncio.gather(
            _live_usd_inr(),
            exchange.fetch_balance(),
            exchange.fetch_tickers(),
        )

        free = balance.get("free", {})

        candidates: list[tuple[str, float, float]] = []
        for asset, qty in free.items():
            if not qty or qty <= 0:
                continue
            if asset == "USDT":
                usd_price = 1.0
            else:
                ticker = tickers.get(f"{asset}/USDT")
                usd_price = ticker.get("last") if ticker else None
            if usd_price is None:
                continue
            if qty * usd_price < DUST_THRESHOLD_USD:
                continue
            candidates.append((asset, qty, usd_price))

        avg_costs = await asyncio.gather(
            *[_avg_cost_usd(exchange, asset) for asset, _, _ in candidates]
        )

        holdings: list[Holding] = []
        for (asset, qty, usd_price), avg_usd in zip(candidates, avg_costs):
            current_inr = usd_price * usd_inr
            value_inr = qty * current_inr

            if avg_usd is not None:
                avg_cost_inr = avg_usd * usd_inr
                cost_inr = qty * avg_cost_inr
                pnl = value_inr - cost_inr
                pnl_pct = (pnl / cost_inr * 100) if cost_inr else 0.0
            else:
                avg_cost_inr = current_inr
                pnl = 0.0
                pnl_pct = 0.0

            holdings.append(
                Holding(
                    symbol=asset,
                    source="binance",
                    type="crypto",
                    quantity=qty,
                    avg_cost=avg_cost_inr,
                    current_price=current_inr,
                    current_value_inr=value_inr,
                    unrealised_pnl=pnl,
                    unrealised_pnl_pct=pnl_pct,
                    currency="INR",
                )
            )

        return holdings

    except Exception as exc:
        raise RuntimeError(f"Binance fetch failed: {exc}") from exc
    finally:
        await exchange.close()
