import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.monotonic)


class InMemorySessionStore:
    def __init__(self, ttl: int = 1800, max_messages: int = 20) -> None:
        self._store: dict[str, list[SessionMessage]] = {}
        self._ttl = ttl
        self._max_messages = max_messages

    def get_history(self, session_id: str) -> list[SessionMessage]:
        self._evict_expired()
        return list(self._store.get(session_id, []))

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._evict_expired()

        msgs = self._store.setdefault(session_id, [])
        msgs.append(SessionMessage(role=role, content=content))

        if len(msgs) > self._max_messages:
            self._store[session_id] = msgs[-self._max_messages :]
            logger.debug(
                "Sessão %s truncada para %d mensagens", session_id, self._max_messages
            )

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            sid
            for sid, msgs in self._store.items()
            if msgs and (now - msgs[-1].timestamp) > self._ttl
        ]
        for sid in expired:
            del self._store[sid]
            logger.debug("Sessão %s expirada e removida", sid)
