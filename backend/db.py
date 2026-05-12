import json
import os
from pathlib import Path

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "falak.db")

CREATE_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    data TEXT NOT NULL
)
"""


async def init_db() -> None:
    db_parent = Path(DB_PATH).expanduser().parent
    if str(db_parent) not in ("", "."):
        db_parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SNAPSHOTS_SQL)
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
