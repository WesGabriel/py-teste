from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.client import LLMResponse
from app.memory.session_store import InMemorySessionStore
from app.orchestration.agent import Agent
from app.tools.markdown_parser import KBSection


def make_agent_with_store(store: InMemorySessionStore) -> Agent:
    kb = MagicMock()
    section = KBSection(title="Composição", body="Composição é combinar objetos.")
    kb.search = AsyncMock(return_value=([section], True))

    llm = MagicMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(content="Resposta do assistente.", model="gpt-4o-mini")
    )

    return Agent(kb_tool=kb, llm_client=llm, session_store=store)


def test_store_starts_empty() -> None:
    store = InMemorySessionStore()
    assert store.get_history("qualquer-id") == []


def test_store_add_and_retrieve_messages() -> None:
    store = InMemorySessionStore()
    store.add_message("s1", "user", "Olá")
    store.add_message("s1", "assistant", "Oi, tudo bem?")

    history = store.get_history("s1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Olá"
    assert history[1].role == "assistant"
    assert history[1].content == "Oi, tudo bem?"


def test_store_returns_copy_of_history() -> None:
    store = InMemorySessionStore()
    store.add_message("s1", "user", "mensagem")

    history = store.get_history("s1")
    history.clear()

    assert len(store.get_history("s1")) == 1


def test_store_session_isolation() -> None:
    store = InMemorySessionStore()
    store.add_message("sess-A", "user", "Pergunta A")
    store.add_message("sess-B", "user", "Pergunta B")

    history_a = store.get_history("sess-A")
    history_b = store.get_history("sess-B")

    assert len(history_a) == 1
    assert history_a[0].content == "Pergunta A"
    assert len(history_b) == 1
    assert history_b[0].content == "Pergunta B"


def test_store_unknown_session_returns_empty() -> None:
    store = InMemorySessionStore()
    assert store.get_history("inexistente") == []


def test_store_truncates_to_max_messages() -> None:
    store = InMemorySessionStore(max_messages=3)
    for i in range(5):
        store.add_message("s1", "user", f"msg {i}")

    history = store.get_history("s1")
    assert len(history) == 3
    assert history[0].content == "msg 2"
    assert history[2].content == "msg 4"


def test_store_exactly_max_messages_not_truncated() -> None:
    store = InMemorySessionStore(max_messages=3)
    for i in range(3):
        store.add_message("s1", "user", f"msg {i}")

    assert len(store.get_history("s1")) == 3


def test_store_evicts_expired_session() -> None:
    store = InMemorySessionStore(ttl=60)
    store.add_message("s1", "user", "mensagem antiga")

    store._store["s1"][0].timestamp = 0.0

    result = store.get_history("s1")
    assert result == []
    assert "s1" not in store._store


def test_store_active_session_not_evicted() -> None:
    store = InMemorySessionStore(ttl=3600)
    store.add_message("s1", "user", "mensagem recente")

    result = store.get_history("s1")
    assert len(result) == 1


def test_store_only_expired_sessions_evicted() -> None:
    store = InMemorySessionStore(ttl=60)
    store.add_message("ativa", "user", "recente")
    store.add_message("expirada", "user", "antiga")

    store._store["expirada"][0].timestamp = 0.0

    assert len(store.get_history("ativa")) == 1
    assert store.get_history("expirada") == []


@pytest.mark.anyio
async def test_agent_saves_exchange_to_session() -> None:
    store = InMemorySessionStore()
    agent = make_agent_with_store(store)

    await agent.run(message="o que é composição?", http_client=None, session_id="s1")  

    history = store.get_history("s1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "o que é composição?"
    assert history[1].role == "assistant"
    assert history[1].content == "Resposta do assistente."


@pytest.mark.anyio
async def test_agent_history_passed_to_llm_on_second_turn() -> None:
    store = InMemorySessionStore()
    agent = make_agent_with_store(store)

    await agent.run(message="primeira mensagem", http_client=None, session_id="s1")  
    await agent.run(message="segunda mensagem", http_client=None, session_id="s1")  

    call_args = agent._llm.complete.call_args
    messages_sent = call_args.kwargs["messages"]

    roles = [m["role"] for m in messages_sent]
    assert roles == ["user", "assistant", "user"]
    assert messages_sent[-1]["content"] == "segunda mensagem"


@pytest.mark.anyio
async def test_agent_two_sessions_do_not_share_context() -> None:
    store = InMemorySessionStore()
    agent = make_agent_with_store(store)

    await agent.run(message="mensagem sessão A", http_client=None, session_id="A")  
    await agent.run(message="mensagem sessão B", http_client=None, session_id="B")  

    hist_a = store.get_history("A")
    hist_b = store.get_history("B")

    contents_a = [m.content for m in hist_a]
    contents_b = [m.content for m in hist_b]

    assert "mensagem sessão B" not in contents_a
    assert "mensagem sessão A" not in contents_b


@pytest.mark.anyio
async def test_agent_stateless_when_no_session_id() -> None:
    store = InMemorySessionStore()
    agent = make_agent_with_store(store)

    await agent.run(message="mensagem sem sessão", http_client=None, session_id=None)  

    assert store._store == {}
