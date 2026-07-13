from pathlib import Path
from typing import Any

import aiosqlite
from aiosqlite import Connection
from uuid import uuid4

from shared.messages import Message, message_adapter


async def _get_db(path: Path) -> Connection:
    path.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA foreign_keys = ON;")
    return db


async def init_db(db: Connection) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            data TEXT NOT NULL,  -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages(session_id);
    """)

class DatabaseError(Exception):
    pass

class SessionRepository:
    def __init__(self, path: Path):
        self._path = path

    @classmethod
    async def create(cls, path: Path) -> "SessionRepository":
        db = await _get_db(path)
        await init_db(db)
        return cls(path)
    
    async def get_db(self):
        return await _get_db(self._path)

    async def create_session(self, title: str = "New Session") -> str:
        session_id = str(uuid4())
        async with await self.get_db() as db:
            await db.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title),
            )
            await db.commit()
            return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        async with await self.get_db() as db:
            cur = await db.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_session_timestamp(self, session_id: str) -> None:
        async with await self.get_db() as db:
            await db.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            await db.commit()

    async def delete_session(self, session_id: str) -> None:
        async with await self.get_db() as db:
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()


    async def load_messages(self, session_id: str) -> list[Message]:
        async with await self.get_db() as db:
            cur = await db.execute(
                "SELECT data FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
            rows = await cur.fetchall()
            return [message_adapter.validate_json(row["data"]) for row in rows]

    async def append_message(self, session_id: str, message: Message) -> int:
        data_json = message.model_dump_json(exclude_none=True)

        async with await self.get_db() as db:
            cur = await db.execute(
                "INSERT INTO messages (session_id, data) VALUES (?, ?)",
                (session_id, data_json),
            )
            await db.commit()
            if cur.lastrowid:
                return cur.lastrowid
            raise DatabaseError("Failed to insert message into the database")

    async def append_messages_batch(self, session_id: str, messages: list[Message]) -> list[int]:
        if not messages:
            return []
            
        ids = []
        async with await self.get_db() as db:
            await db.execute("BEGIN TRANSACTION;")
            
            try:
                for m in messages:
                    data_json = m.model_dump_json(exclude_none=True)
                    cur = await db.execute(
                        "INSERT INTO messages (session_id, data) VALUES (?, ?)",
                        (session_id, data_json),
                    )
                    if cur.lastrowid is None:
                        raise DatabaseError("Failed to insert message into the database")
                    ids.append(cur.lastrowid)
                    
                await db.commit()
                
            except Exception:
                await db.rollback()
                raise
                
            return ids
        
    async def rewind_user_messages(self, session_id: str, n: int = 1) -> int:
        async with await self.get_db() as db:
            cur = await db.execute(
                """
                SELECT id FROM messages
                WHERE session_id = ? AND json_extract(data, '$.role') = 'user'
                ORDER BY id DESC
                LIMIT 1 OFFSET ?
                """,
                (session_id, n - 1),
            )
            row = await cur.fetchone()
            if not row:
                return 0 

            cutoff_id = row["id"]

            cur = await db.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ? AND id >= ?",
                (session_id, cutoff_id),
            )
            count_row = await cur.fetchone()
            deleted = count_row["cnt"] if count_row else 0

            await db.execute(
                "DELETE FROM messages WHERE session_id = ? AND id >= ?",
                (session_id, cutoff_id),
            )
            await db.commit()
            return deleted