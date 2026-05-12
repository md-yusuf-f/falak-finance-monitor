import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest
from telegram import Update
from telegram.error import TelegramError

from backend.notifications.telegram import TelegramNotifier
from backend.scheduler import Scheduler

@pytest.mark.asyncio
async def test_send_message_success():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    notifier.application = MagicMock()
    notifier.application.bot.send_message = AsyncMock()
    
    await notifier.send("test message")
    
    notifier.application.bot.send_message.assert_called_once_with(
        chat_id="fake_chat_id", text="test message"
    )

@pytest.mark.asyncio
async def test_send_message_silently_ignores_error():
    notifier = TelegramNotifier("fake_token", "fake_chat_id")
    notifier.application = MagicMock()
    notifier.application.bot.send_message = AsyncMock(side_effect=TelegramError("Bot blocked"))
    
    # Should not raise exception
    await notifier.send("test message")
    
    notifier.application.bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_kite_status_valid(tmp_path):
    token_file = tmp_path / "kite_token.txt"
    token_file.write_text("fake_token")
    
    with patch.dict(os.environ, {"KITE_ACCESS_TOKEN_FILE": str(token_file), "KITE_API_KEY": "fake_key"}):
        notifier = TelegramNotifier("fake_token", "fake_chat_id")
        
        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await notifier.kite_status_command(update, context)
            
        args, kwargs = update.message.reply_text.call_args
        assert "valid" in args[0].lower()

@pytest.mark.asyncio
async def test_kite_status_expired(tmp_path):
    token_file = tmp_path / "kite_token.txt"
    token_file.write_text("fake_token")
    
    with patch.dict(os.environ, {"KITE_ACCESS_TOKEN_FILE": str(token_file), "KITE_API_KEY": "fake_key"}):
        notifier = TelegramNotifier("fake_token", "fake_chat_id")
        
        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 403
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await notifier.kite_status_command(update, context)
            
        args, kwargs = update.message.reply_text.call_args
        assert "expired" in args[0].lower()

@pytest.mark.asyncio
async def test_kite_status_missing_file(tmp_path):
    token_file = tmp_path / "non_existent.txt"
    
    with patch.dict(os.environ, {"KITE_ACCESS_TOKEN_FILE": str(token_file)}):
        notifier = TelegramNotifier("fake_token", "fake_chat_id")
        
        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        
        await notifier.kite_status_command(update, context)
            
        args, kwargs = update.message.reply_text.call_args
        assert "expired" in args[0].lower()

@pytest.mark.asyncio
async def test_scheduler_token_check_sends_alert_when_expired(tmp_path):
    token_file = tmp_path / "kite_token.txt"
    token_file.write_text("fake_token")
    
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send = AsyncMock()
    
    scheduler = Scheduler(notifier)
    
    with patch.dict(os.environ, {"KITE_ACCESS_TOKEN_FILE": str(token_file), "KITE_API_KEY": "fake_key"}):
        mock_response = MagicMock()
        mock_response.status_code = 403
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await scheduler.kite_token_check()
            
        notifier.send.assert_called_once()
        args, kwargs = notifier.send.call_args
        assert "EXPIRED" in args[0]

@pytest.mark.asyncio
async def test_scheduler_token_check_no_alert_when_valid(tmp_path):
    token_file = tmp_path / "kite_token.txt"
    token_file.write_text("fake_token")
    
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send = AsyncMock()
    
    scheduler = Scheduler(notifier)
    
    with patch.dict(os.environ, {"KITE_ACCESS_TOKEN_FILE": str(token_file), "KITE_API_KEY": "fake_key"}):
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await scheduler.kite_token_check()
            
        notifier.send.assert_not_called()
