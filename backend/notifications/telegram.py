import logging
import os
import asyncio
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..collectors import fetch_zerodha_holdings, fetch_binance_holdings
from ..analysis.router import run_analysis
from ..models import PortfolioSnapshot
from ..db import DB_PATH
import aiosqlite

log = logging.getLogger(__name__)

START_TIME = time.time()

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.application = None
        if token and chat_id:
            self.application = Application.builder().token(token).build()
            self._register_handlers()
        else:
            log.warning("Telegram token or chat_id missing. Bot will not be initialized.")

    def _register_handlers(self):
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("health", self.health_command))
        self.application.add_handler(CommandHandler("analyse", self.analyse_command))
        self.application.add_handler(CommandHandler("kite_status", self.kite_status_command))
        self.application.add_handler(CommandHandler("indstocks_token", self.indstocks_token_command))
        self.application.add_handler(CommandHandler("update", self.update_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("start", self.help_command))
        # Handle unknown commands
        from telegram.ext import MessageHandler, filters
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))

    async def send(self, message: str):
        if not self.application or not self.chat_id:
            return
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as exc:
            log.error("Failed to send Telegram message: %s", exc)

    async def start_polling(self):
        if self.application:
            log.info("Starting Telegram bot polling")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

    async def stop(self):
        if self.application:
            log.info("Stopping Telegram bot")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            zerodha_holdings = await fetch_zerodha_holdings()
            binance_holdings = await fetch_binance_holdings()

            z_total = sum(h.current_value_inr for h in zerodha_holdings)
            b_total = sum(h.current_value_inr for h in binance_holdings)
            grand_total = z_total + b_total

            msg = (
                f"📊 *Portfolio Summary*\n\n"
                f"Zerodha: ₹{z_total:,.2f} ({len(zerodha_holdings)} holdings)\n"
                f"Binance: ₹{b_total:,.2f} ({len(binance_holdings)} holdings)\n"
                f"--- \n"
                f"*Grand Total: ₹{grand_total:,.2f}*"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as exc:
            log.error("Error in /portfolio command: %s", exc)
            await update.message.reply_text(f"❌ Error fetching portfolio: {exc}")

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # DB Ping
            db_ok = False
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("SELECT 1")
                    db_ok = True
            except Exception:
                db_ok = False

            # Kite token check
            token_file = Path(os.getenv("KITE_ACCESS_TOKEN_FILE", "data/kite_access_token.txt"))
            kite_ok = token_file.exists() and token_file.stat().st_size > 0

            ind_token_file = Path(os.getenv("INDSTOCKS_ACCESS_TOKEN_FILE", "data/indstocks_access_token.txt"))
            ind_ok = bool(os.getenv("INDSTOCKS_ACCESS_TOKEN")) or (ind_token_file.exists() and ind_token_file.stat().st_size > 0)

            uptime = time.time() - START_TIME
            hours, rem = divmod(int(uptime), 3600)
            minutes, seconds = divmod(rem, 60)

            msg = (
                f"🏥 *System Status*\n\n"
                f"DB Connected: {'✅' if db_ok else '❌'}\n"
                f"Kite Token: {'✅' if kite_ok else '❌'}\n"
                f"INDstocks Token: {'✅' if ind_ok else '❌'}\n"
                f"Uptime: {hours}h {minutes}m {seconds}s"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as exc:
            log.error("Error in /health command: %s", exc)
            await update.message.reply_text(f"❌ Error checking health: {exc}")

    async def analyse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⏳ Running analysis, please wait...")
        try:
            zerodha = await fetch_zerodha_holdings()
            binance = await fetch_binance_holdings()
            all_holdings = zerodha + binance

            if not all_holdings:
                await update.message.reply_text("❌ No holdings found to analyse.")
                return

            total_value = sum(h.current_value_inr for h in all_holdings)
            total_cost = sum(h.avg_cost * h.quantity for h in all_holdings)
            
            snapshot = PortfolioSnapshot(
                timestamp=datetime.now(timezone.utc),
                holdings=all_holdings,
                total_value_inr=total_value,
                total_pnl_inr=total_value - total_cost,
                total_pnl_pct=((total_value - total_cost) / total_cost * 100) if total_cost else 0.0,
                errors=[]
            )

            result = await run_analysis(snapshot)
            
            # Extract groq_verdict and gemini_risk_score
            # Based on analysis/router.py, AnalysisResult has these fields
            groq_verdict = result.groq_verdict.get("verdict", "N/A") if isinstance(result.groq_verdict, dict) else "N/A"
            gemini_score = result.gemini_risks.get("risk_score", "N/A") if isinstance(result.gemini_risks, dict) else "N/A"

            msg = (
                f"🧠 *AI Analysis*\n\n"
                f"*Groq Verdict:* {groq_verdict}\n"
                f"*Gemini Risk Score:* {gemini_score}/10"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as exc:
            log.error("Error in /analyse command: %s", exc)
            await update.message.reply_text(f"❌ Analysis failed: {exc}")

    async def indstocks_token_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /indstocks_token <token>")
            return
        token = context.args[0].strip()
        token_path = Path(os.getenv("INDSTOCKS_ACCESS_TOKEN_FILE", "data/indstocks_access_token.txt"))
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = token_path.with_suffix(".tmp")
            tmp.write_text(token, encoding="utf-8")
            tmp.replace(token_path)
            await update.message.reply_text("INDstocks token updated ✅")
        except Exception as exc:
            log.error("Failed to save INDstocks token: %s", exc)
            await update.message.reply_text(f"❌ Failed to save token: {exc}")

    async def kite_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            token_file = Path(os.getenv("KITE_ACCESS_TOKEN_FILE", "data/kite_access_token.txt"))
            if not token_file.exists() or token_file.stat().st_size == 0:
                await update.message.reply_text("Token EXPIRED — re-login at /auth/kite/login")
                return

            token = token_file.read_text(encoding="utf-8").strip()
            api_key = os.getenv("KITE_API_KEY")
            
            async with httpx.AsyncClient() as client:
                headers = {"X-Kite-Version": "3", "Authorization": f"token {api_key}:{token}"}
                response = await client.get("https://api.kite.trade/user/profile", headers=headers)
                
                if response.status_code == 200:
                    await update.message.reply_text("Token valid ✓")
                elif response.status_code in (401, 403):
                    await update.message.reply_text("Token EXPIRED — re-login at /auth/kite/login")
                else:
                    await update.message.reply_text(f"Kite API error: {response.status_code}")
        except Exception as exc:
            log.error("Error in /kite_status command: %s", exc)
            await update.message.reply_text(f"❌ Error checking Kite status: {exc}")

    async def update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.message.chat_id) != str(self.chat_id):
            await update.message.reply_text("Unauthorized.")
            return

        result = subprocess.run(
            ["git", "-C", "/app", "pull", "origin", "main"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            await update.message.reply_text(f"Git pull failed:\n{result.stderr[:500]}")
            return

        git_output = result.stdout.strip() or "Already up to date."
        await update.message.reply_text(f"Updated. Restarting in 3s...\n\n{git_output}")

        container_name = os.getenv("CONTAINER_NAME", "falak-finance-monitor")

        def _restart():
            time.sleep(3)
            try:
                import docker
                docker.from_env().containers.get(container_name).restart(timeout=10)
            except Exception as exc:
                log.error("Container restart failed: %s", exc)

        threading.Thread(target=_restart, daemon=True).start()

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "Falak Finance Bot\n\n"
            "/portfolio - Holdings summary and total value\n"
            "/health - System status and uptime\n"
            "/analyse - Trigger AI analysis of current portfolio\n"
            "/kite_status - Check if Zerodha/Kite token is valid\n"
            "/indstocks_token <token> - Update INDstocks access token\n"
            "/update - Pull latest code and restart\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_text)

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Unknown command. Use /help to see available commands.")
