import json
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "falak.db")

_CREATE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    data TEXT NOT NULL
)
"""

_CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    condition TEXT NOT NULL,
    threshold REAL NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
)
"""

_CREATE_CANDLES = """
CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    UNIQUE(symbol, interval, timestamp)
)
"""

_CREATE_PAPER_POSITIONS = """
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    opened_at TEXT NOT NULL
)
"""

_CREATE_PAPER_TRADES = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL
)
"""

_CREATE_STRATEGY_SIGNALS = """
CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    signal TEXT NOT NULL,
    rule TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    vetoed INTEGER NOT NULL DEFAULT 0,
    veto_reason TEXT
)
"""


async def init_db() -> None:
    db_parent = Path(DB_PATH).expanduser().parent
    if str(db_parent) not in ("", "."):
        db_parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_SNAPSHOTS)
        await db.execute(_CREATE_ALERTS)
        await db.execute(_CREATE_CANDLES)
        await db.execute(_CREATE_PAPER_POSITIONS)
        await db.execute(_CREATE_PAPER_TRADES)
        await db.execute(_CREATE_STRATEGY_SIGNALS)
        await db.commit()


async def save_snapshot(snapshot: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO snapshots (timestamp, data) VALUES (?, ?)",
            (snapshot["timestamp"], json.dumps(snapshot)),
        )
        await db.commit()


async def get_latest_snapshot() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data FROM snapshots ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
    return json.loads(row["data"]) if row else None


async def get_history(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [json.loads(r["data"]) for r in rows]


async def save_alert(symbol: str, condition: str, threshold: float) -> int:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO alerts (symbol, condition, threshold, created_at) VALUES (?, ?, ?, ?)",
            (symbol.upper(), condition, threshold, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_alerts() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, symbol, condition, threshold, enabled FROM alerts ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_alert(alert_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        await db.commit()


async def save_candles(rows: list[dict]) -> None:
    if not rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT OR IGNORE INTO candles (symbol, interval, timestamp, open, high, low, close, volume)
            VALUES (:symbol, :interval, :timestamp, :open, :high, :low, :close, :volume)
            """,
            rows,
        )
        await db.commit()


async def get_candles(symbol: str, interval: str, limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT symbol, interval, timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND interval = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (symbol, interval, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    # Return oldest-first
    return [dict(r) for r in reversed(rows)]


async def save_paper_position(row: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO paper_positions (symbol, side, qty, entry_price, stop_loss, take_profit, opened_at)
            VALUES (:symbol, :side, :qty, :entry_price, :stop_loss, :take_profit, :opened_at)
            """,
            row,
        )
        await db.commit()


async def get_open_positions(symbol: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM paper_positions"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def close_paper_position(position_id: int, exit_price: float, pnl: float, closed_at: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)) as cursor:
            pos = await cursor.fetchone()
            if not pos:
                return

        await db.execute(
            """
            INSERT INTO paper_trades (symbol, side, qty, entry_price, exit_price, pnl, opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pos["symbol"], pos["side"], pos["qty"], pos["entry_price"], exit_price, pnl, pos["opened_at"], closed_at),
        )
        await db.execute("DELETE FROM paper_positions WHERE id = ?", (position_id,))
        await db.commit()


async def get_paper_trades_today() -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM paper_trades WHERE closed_at LIKE ?", (f"{today}%",)
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def save_strategy_signal(row: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO strategy_signals (symbol, signal, rule, timestamp, vetoed, veto_reason)
            VALUES (:symbol, :signal, :rule, :timestamp, :vetoed, :veto_reason)
            """,
            row,
        )
        await db.commit()
