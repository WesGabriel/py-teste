import logging
from dataclasses import dataclass, field

import httpx

from app.core.constants import FALLBACK_ANSWER
from app.llm.client import LLMClient, LLMError
from app.prompts.system import build_system_prompt
from app.tools.kb_tool import KBTool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    sources: list[dict[str, str]] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        kb_tool: KBTool,
        llm_client: LLMClient,
        session_store: object | None = None,
    ) -> None:
        self._kb = kb_tool
        self._llm = llm_client
        self._session_store = session_store

    async def run(
        self,
        message: str,
        http_client: httpx.AsyncClient,
        session_id: str | None = None,
    ) -> AgentResponse:
        logger.info("Agent.run session_id=%s message=%r", session_id, message[:80])

        sections, above_threshold = await self._kb.search(message, http_client)

        if not above_threshold:
            logger.info("Fallback: nenhuma seção atingiu o threshold")
            return AgentResponse(answer=FALLBACK_ANSWER, sources=[])

        system_prompt = build_system_prompt([s.body for s in sections])
        messages = self._build_messages(message, session_id)

        try:
            llm_response = await self._llm.complete(system=system_prompt, messages=messages)
        except LLMError as exc:
            logger.warning("LLMError capturado, retornando fallback: %s", exc)
            return AgentResponse(answer=FALLBACK_ANSWER, sources=[])

        self._save_to_session(session_id, message, llm_response.content)

        sources = [{"section": s.title} for s in sections]
        return AgentResponse(answer=llm_response.content, sources=sources)

    def _build_messages(
        self, message: str, session_id: str | None
    ) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []

        if session_id and self._session_store is not None:
            raw_history = self._session_store.get_history(session_id)  
            history = [{"role": m.role, "content": m.content} for m in raw_history]

        history.append({"role": "user", "content": message})
        return history

    def _save_to_session(
        self, session_id: str | None, user_message: str, assistant_reply: str
    ) -> None:
        if session_id and self._session_store is not None:
            self._session_store.add_message(session_id, "user", user_message)  
            self._session_store.add_message(session_id, "assistant", assistant_reply)
