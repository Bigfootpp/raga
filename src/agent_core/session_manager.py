from pathlib import Path
from typing import Optional

from agent_core.database import SessionRepository
from agent_core.session import Session

class SessionNotFound(Exception):
    pass

class SessionManager:
    def __init__(self, repo: SessionRepository):
        self._repo = repo

    @classmethod
    async def create(cls, path: Path | str) -> "SessionManager":
        return cls(await SessionRepository.create(path=path))

    async def new_session(self, title: str = "Untitled Session") -> Session:
        session_id = await self._repo.create_session(title)
        return Session(session_id=session_id)

    async def load_session(self, session_id: str) -> Session:
        session_data = await self._repo.get_session(session_id)
        if not session_data:
            raise SessionNotFound("Session doesn't exist")
        messages = await self._repo.load_messages(session_id)
        session = Session(session_id=session_id)
        session.load_history(messages)
        return session

    async def get_session_ids(self) -> list[str]:
        return await self._repo.get_session_ids()

    async def get_sessions(self) -> list[Session]:
        session_ids = await self.get_session_ids()
        sessions = [await self.load_session(id) for id in session_ids]
        return sessions

    async def persist_turn(self, session: Session) -> None:
        if not session.session_id:
            raise ValueError("Session without ID (not persisted)")
        new_messages = session.get_new_messages()
        if new_messages:
            await self._repo.append_messages_batch(session.session_id, new_messages)
            await self._repo.update_session_timestamp(session.session_id)
        session.record()

    async def rewind(self, session_id: str, n: int = 1) -> Optional[Session]:
        await self._repo.rewind_user_messages(session_id, n)
        return await self.load_session(session_id)