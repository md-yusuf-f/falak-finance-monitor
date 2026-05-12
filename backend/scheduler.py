import logging
import os
from pathlib import Path

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .notifications.telegram import TelegramNotifier
from .collectors import fetch_zerodha_holdings, fetch_binance_holdings, fetch_candles
from .db import save_candles, get_candles

log = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        daily_report_cron = os.getenv("DAILY_REPORT_CRON", "0 9 * * *")
        kite_token_cron = os.getenv("KITE_TOKEN_ALERT_CRON", "0 8 * * *")

        self.scheduler.add_job(
            self.daily_report,
            CronTrigger.from_crontab(daily_report_cron),
            name="daily_report"
        )
        self.scheduler.add_job(
            self.kite_token_check,
            CronTrigger.from_crontab(kite_token_cron),
            name="kite_token_check"
        )
        
        # Job 3: candle_collect - every 15 minutes
        self.scheduler.add_job(
            self.candle_collect,
            IntervalTrigger(minutes=15),
            name="candle_collect"
        )

        # Job 4: candle_gap_check - every 15 minutes, offset by 1 minute
        from datetime import datetime, timedelta
        start_date = datetime.now() + timedelta(minutes=1)
        self.scheduler.add_job(
            self.candle_gap_check,
            IntervalTrigger(minutes=15, start_date=start_date),
            name="candle_gap_check"
        )

        self.scheduler.start()
        log.info("Scheduler started with jobs: daily_report (%s), kite_token_check (%s), candle_collect, candle_gap_check", 
                 daily_report_cron, kite_token_cron)

    async def stop(self):
        self.scheduler.shutdown()
        log.info("Scheduler stopped")

    async def daily_report(self):
        log.info("Running daily_report job")
        try:
            zerodha_holdings = await fetch_zerodha_holdings()
            binance_holdings = await fetch_binance_holdings()

            z_total = sum(h.current_value_inr for h in zerodha_holdings)
            b_total = sum(h.current_value_inr for h in binance_holdings)
            grand_total = z_total + b_total

            msg = (
                f"📅 *Daily Portfolio Report*\n\n"
                f"Zerodha: ₹{z_total:,.2f} ({len(zerodha_holdings)} holdings)\n"
                f"Binance: ₹{b_total:,.2f} ({len(binance_holdings)} holdings)\n"
                f"--- \n"
                f"*Grand Total: ₹{grand_total:,.2f}*"
            )
            await self.notifier.send(msg)
        except Exception as exc:
            log.error("Error in daily_report job: %s", exc)

    async def kite_token_check(self):
        log.info("Running kite_token_check job")
        try:
            token_file = Path(os.getenv("KITE_ACCESS_TOKEN_FILE", "data/kite_access_token.txt"))
            is_valid = False
            
            if token_file.exists() and token_file.stat().st_size > 0:
                token = token_file.read_text(encoding="utf-8").strip()
                api_key = os.getenv("KITE_API_KEY")
                
                async with httpx.AsyncClient() as client:
                    headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{token}"}
                    response = await client.get("https://api.kite.trade/user/profile", headers=headers)
                    if response.status_code == 200:
                        is_valid = True
                        log.info("Kite token is valid")
            
            if not is_valid:
                await self.notifier.send("⚠️ Kite token EXPIRED — re-login at /auth/kite/login")
        except Exception as exc:
            log.error("Error in kite_token_check job: %s", exc)

    async def candle_collect(self):
        log.info("Running candle_collect job")
        symbols_env = os.getenv("MARKET_SYMBOLS", "BTC/USDT,ETH/USDT")
        symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]
        for symbol in symbols:
            try:
                candles = await fetch_candles(symbol, interval="15m", limit=100)
                await save_candles(candles)
                log.info("Saved %d candles for %s", len(candles), symbol)
            except Exception as exc:
                log.error("Error collecting candles for %s: %s", symbol, exc)

    async def candle_gap_check(self):
        log.info("Running candle_gap_check job")
        symbols_env = os.getenv("MARKET_SYMBOLS", "BTC/USDT,ETH/USDT")
        symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]
        for symbol in symbols:
            try:
                rows = await get_candles(symbol, "15m", limit=1)
                if not rows:
                    continue
                
                latest = rows[0]
                from datetime import datetime, timezone
                last_ts = datetime.fromisoformat(latest["timestamp"])
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                diff_mins = int((now - last_ts).total_seconds() / 60)
                
                if diff_mins > 30:
                    msg = f"⚠️ Candle gap detected: {symbol} 15m — last candle {diff_mins}m ago"
                    log.warning(msg)
                    await self.notifier.send(msg)
            except Exception as exc:
                log.error("Error in candle_gap_check for %s: %s", symbol, exc)
