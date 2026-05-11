"""
Async SQLite persistence layer for memos and reminders.

This module keeps the current bot flow intact while adding two durable stores:
- memo_table: notes and accounting entries
- reminder_table: pending reminders for proactive delivery
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite manager for memo and reminder data."""

    def __init__(self, db_path: Optional[str] = None):
        env_db_path = os.getenv("DB_PATH")
        default_path = Path(__file__).resolve().parents[1] / "data" / "assistant.db"
        self.db_path = Path(db_path or env_db_path or default_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Open the database and create tables if needed."""
        if self._connection is not None:
            return

        async with self._init_lock:
            if self._connection is not None:
                return

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = await aiosqlite.connect(str(self.db_path))
            connection.row_factory = aiosqlite.Row

            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.execute("PRAGMA busy_timeout = 5000")
            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memo_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    "type" TEXT NOT NULL,
                    content TEXT NOT NULL,
                    amount REAL,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memo_user_timestamp
                ON memo_table(user_id, timestamp);

                CREATE INDEX IF NOT EXISTS idx_memo_user_type
                ON memo_table(user_id, "type");

                CREATE TABLE IF NOT EXISTS reminder_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reminder_content TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_reminder_pending
                ON reminder_table(completed, trigger_time);

                CREATE INDEX IF NOT EXISTS idx_reminder_user
                ON reminder_table(user_id);
                """
            )
            await connection.commit()
            self._connection = connection
            logger.debug("数据库已初始化: %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is None:
            return

        await self._connection.close()
        self._connection = None
        logger.debug("数据库连接已关闭")

    async def _get_connection(self) -> aiosqlite.Connection:
        await self.initialize()
        if self._connection is None:
            raise RuntimeError("Database is not initialized")
        return self._connection

    @staticmethod
    def _normalize_datetime(value: Optional[datetime | str]) -> str:
        """Convert datetimes into a stable UTC ISO string."""
        if value is None:
            current_time = datetime.now(timezone.utc)
        elif isinstance(value, datetime):
            current_time = value
        else:
            current_time = datetime.fromisoformat(value)

        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        return current_time.astimezone(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        return dict(row)

    async def add_memo(
        self,
        user_id: int,
        memo_type: str,
        content: str,
        amount: Optional[float] = None,
        timestamp: Optional[datetime | str] = None,
    ) -> int:
        """Store a memo or accounting record."""
        connection = await self._get_connection()
        timestamp_text = self._normalize_datetime(timestamp)

        cursor = await connection.execute(
            'INSERT INTO memo_table (user_id, "type", content, amount, timestamp) '
            'VALUES (?, ?, ?, ?, ?)',
            (user_id, memo_type, content, amount, timestamp_text),
        )
        await connection.commit()
        return int(cursor.lastrowid)

    async def get_memos(
        self,
        user_id: Optional[int] = None,
        memo_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch stored memos with optional filters."""
        connection = await self._get_connection()
        query = 'SELECT id, user_id, "type", content, amount, timestamp FROM memo_table WHERE 1=1'
        params: list[Any] = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        if memo_type is not None:
            query += ' AND "type" = ?'
            params.append(memo_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _date_prefix(value: Optional[datetime | date | str]) -> str:
        """Convert a date-like value into YYYY-MM-DD for SQLite text matching."""
        if value is None:
            return datetime.now(timezone.utc).date().isoformat()

        if isinstance(value, date) and not isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, datetime):
            normalized = value
        else:
            normalized = datetime.fromisoformat(value)

        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=timezone.utc)

        return normalized.astimezone(timezone.utc).date().isoformat()

    async def sum_memos(
        self,
        user_id: int,
        memo_type: Optional[str] = None,
        keyword: Optional[str] = None,
        on_date: Optional[datetime | date | str] = None,
    ) -> float:
        """Sum memo amounts for the given user and optional filters."""
        connection = await self._get_connection()
        query = 'SELECT COALESCE(SUM(amount), 0) AS total_amount FROM memo_table WHERE user_id = ? AND amount IS NOT NULL'
        params: list[Any] = [user_id]

        if memo_type is not None:
            query += ' AND "type" = ?'
            params.append(memo_type)

        if keyword:
            query += " AND content LIKE ?"
            params.append(f"%{keyword}%")

        if on_date is not None:
            query += " AND substr(timestamp, 1, 10) = ?"
            params.append(self._date_prefix(on_date))

        async with connection.execute(query, params) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return 0.0

        return float(row["total_amount"] or 0)

    async def get_memos_by_keyword(
        self,
        user_id: int,
        keyword: str,
        memo_type: Optional[str] = None,
        on_date: Optional[datetime | date | str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch memo entries matching a keyword, optionally constrained to a date."""
        connection = await self._get_connection()
        query = 'SELECT id, user_id, "type", content, amount, timestamp FROM memo_table WHERE user_id = ? AND content LIKE ?'
        params: list[Any] = [user_id, f"%{keyword}%"]

        if memo_type is not None:
            query += ' AND "type" = ?'
            params.append(memo_type)

        if on_date is not None:
            query += " AND substr(timestamp, 1, 10) = ?"
            params.append(self._date_prefix(on_date))

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    async def add_reminder(
        self,
        user_id: int,
        reminder_content: str,
        trigger_time: datetime | str,
        completed: bool = False,
    ) -> int:
        """Store a reminder that can be triggered later."""
        connection = await self._get_connection()
        trigger_time_text = self._normalize_datetime(trigger_time)

        cursor = await connection.execute(
            "INSERT INTO reminder_table (user_id, reminder_content, trigger_time, completed) VALUES (?, ?, ?, ?)",
            (user_id, reminder_content, trigger_time_text, int(completed)),
        )
        await connection.commit()
        return int(cursor.lastrowid)

    async def get_pending_reminders(self, user_id: Optional[int] = None) -> list[dict[str, Any]]:
        """Fetch reminders that have not been completed yet."""
        connection = await self._get_connection()
        query = (
            "SELECT id, user_id, reminder_content, trigger_time, completed "
            "FROM reminder_table WHERE completed = 0"
        )
        params: list[Any] = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY trigger_time ASC"

        async with connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def get_due_reminders(
        self,
        current_time: Optional[datetime | str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch reminders whose trigger time has arrived."""
        connection = await self._get_connection()
        current_time_text = self._normalize_datetime(current_time)

        async with connection.execute(
            "SELECT id, user_id, reminder_content, trigger_time, completed "
            "FROM reminder_table WHERE completed = 0 AND trigger_time <= ? "
            "ORDER BY trigger_time ASC",
            (current_time_text,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    async def complete_reminder(self, reminder_id: int) -> None:
        """Mark a reminder as completed after it has been sent."""
        connection = await self._get_connection()
        await connection.execute(
            "UPDATE reminder_table SET completed = 1 WHERE id = ?",
            (reminder_id,),
        )
        await connection.commit()

    async def delete_reminder(self, reminder_id: int) -> None:
        """Remove a reminder from the table."""
        connection = await self._get_connection()
        await connection.execute("DELETE FROM reminder_table WHERE id = ?", (reminder_id,))
        await connection.commit()
