from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class StoredMessage:
    chat_id: int
    message_id: int
    thread_key: int
    author: str
    text: str
    date: int  # UTC timestamp
    raw: dict


@dataclass
class ChatInfo:
    chat_id: int
    title: str
    chat_type: str
    username: Optional[str]
    last_message_ts: int


class MessageStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        if self.db_path.is_dir():
            raise ValueError("DATABASE_PATH должен указывать на файл SQLite, а не папку")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    thread_key INTEGER NOT NULL,
                    author TEXT,
                    text TEXT NOT NULL,
                    date INTEGER NOT NULL,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (chat_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def save_messages(self, records: Iterable[StoredMessage]) -> int:
        rows = [
            (
                record.chat_id,
                record.message_id,
                record.thread_key,
                record.author,
                record.text,
                record.date,
                json.dumps(record.raw, ensure_ascii=False),
            )
            for record in records
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO messages
                (chat_id, message_id, thread_key, author, text, date, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return conn.total_changes

    def load_messages(
        self,
        *,
        chat_id: int,
        since_ts: Optional[int],
        limit: int,
    ) -> List[StoredMessage]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT chat_id, message_id, thread_key, author, text, date, raw_json
                FROM messages
                WHERE chat_id = ? AND date >= ?
                ORDER BY date ASC
                LIMIT ?
                """,
                (chat_id, since_ts if since_ts is not None else 0, limit),
            )
            rows = cursor.fetchall()
        return [
            StoredMessage(
                chat_id=row["chat_id"],
                message_id=row["message_id"],
                thread_key=row["thread_key"],
                author=row["author"] or "Неизвестный участник",
                text=row["text"],
                date=row["date"],
                raw=json.loads(row["raw_json"]),
            )
            for row in rows
        ]

    def list_chats(self) -> List[ChatInfo]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT m.chat_id,
                       m.raw_json,
                       stats.last_date
                FROM messages AS m
                JOIN (
                    SELECT chat_id, MAX(date) AS last_date
                    FROM messages
                    GROUP BY chat_id
                ) AS stats
                ON m.chat_id = stats.chat_id AND m.date = stats.last_date
                ORDER BY stats.last_date DESC
                """
            )
            rows = cursor.fetchall()
        chats: List[ChatInfo] = []
        for row in rows:
            raw = json.loads(row["raw_json"])
            chat_payload = raw.get("chat", {})
            chats.append(
                ChatInfo(
                    chat_id=row["chat_id"],
                    title=chat_payload.get("title")
                    or chat_payload.get("username")
                    or f"Chat {row['chat_id']}",
                    chat_type=chat_payload.get("type", "unknown"),
                    username=chat_payload.get("username"),
                    last_message_ts=row["last_date"],
                )
            )
        return chats

    def get_last_update_id(self) -> Optional[int]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT value FROM metadata WHERE key = 'last_update_id'"
            )
            row = cursor.fetchone()
        if not row:
            return None
        return int(row["value"])

    def set_last_update_id(self, update_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO metadata(key, value)
                VALUES ('last_update_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(update_id),),
            )

    def clear_messages(
        self, *, chat_id: Optional[int] = None, reset_metadata: bool = False
    ) -> int:
        with self._connect() as conn:
            if chat_id is None:
                conn.execute("DELETE FROM messages")
            else:
                conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            removed = conn.total_changes
            if reset_metadata:
                conn.execute("DELETE FROM metadata")
            return removed

