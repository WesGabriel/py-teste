from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import FALLBACK_ANSWER
from app.llm.client import LLMError, LLMResponse
from app.orchestration.agent import Agent, AgentResponse
from app.tools.markdown_parser import KBSection


def make_kb_tool(sections: list[KBSection], above_threshold: bool) -> MagicMock:
    tool = MagicMock()
    tool.search = AsyncMock(return_value=(sections, above_threshold))
    return tool


def make_llm_client(content: str = "Resposta gerada", model: str = "gpt-4o-mini") -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=LLMResponse(content=content, model=model))
    return client


def make_llm_client_raising(error: Exception) -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(side_effect=error)
    return client


SECTION_A = KBSection(title="Composição", body="Composição é combinar objetos.")
SECTION_B = KBSection(title="Herança", body="Herança é extensão de classes.")


@pytest.mark.anyio
async def test_agent_fallback_when_below_threshold() -> None:
    kb = make_kb_tool(sections=[], above_threshold=False)
    llm = make_llm_client()
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="o que é pizza?", http_client=None)  

    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.anyio
async def test_agent_no_llm_call_when_below_threshold() -> None:
    kb = make_kb_tool(sections=[], above_threshold=False)
    llm = make_llm_client()
    agent = Agent(kb_tool=kb, llm_client=llm)

    await agent.run(message="o que é pizza?", http_client=None)  

    llm.complete.assert_not_called()


@pytest.mark.anyio
async def test_agent_calls_llm_above_threshold() -> None:
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client(content="Composição é a técnica de combinar objetos.")
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="o que é composição?", http_client=None)  

    llm.complete.assert_called_once()
    assert result.answer == "Composição é a técnica de combinar objetos."


@pytest.mark.anyio
async def test_agent_sources_match_sections_returned_by_kb() -> None:
    kb = make_kb_tool(sections=[SECTION_A, SECTION_B], above_threshold=True)
    llm = make_llm_client()
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="composição e herança", http_client=None)  

    assert result.sources == [
        {"section": "Composição"},
        {"section": "Herança"},
    ]


@pytest.mark.anyio
async def test_agent_answer_comes_from_llm() -> None:
    expected = "A composição permite flexibilidade por injeção de dependências."
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client(content=expected)
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="composição?", http_client=None)  

    assert result.answer == expected


@pytest.mark.anyio
async def test_agent_fallback_on_llm_error() -> None:
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client_raising(LLMError("timeout"))
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="composição?", http_client=None)  

    assert result.answer == FALLBACK_ANSWER
    assert result.sources == []


@pytest.mark.anyio
async def test_agent_fallback_on_llm_error_does_not_raise() -> None:
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client_raising(LLMError("rate limit"))
    agent = Agent(kb_tool=kb, llm_client=llm)

    result = await agent.run(message="qualquer coisa", http_client=None)  
    assert isinstance(result, AgentResponse)


@pytest.mark.anyio
async def test_agent_stateless_without_session_id() -> None:
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client()
    session_store = MagicMock()
    agent = Agent(kb_tool=kb, llm_client=llm, session_store=session_store)

    await agent.run(message="composição?", http_client=None, session_id=None)  

    session_store.get_history.assert_not_called()
    session_store.add_message.assert_not_called()


@pytest.mark.anyio
async def test_agent_uses_session_store_when_session_id_provided() -> None:
    kb = make_kb_tool(sections=[SECTION_A], above_threshold=True)
    llm = make_llm_client()

    session_store = MagicMock()
    session_store.get_history.return_value = []

    agent = Agent(kb_tool=kb, llm_client=llm, session_store=session_store)
    await agent.run(message="composição?", http_client=None, session_id="sess-1")  

    session_store.get_history.assert_called_once_with("sess-1")
    assert session_store.add_message.call_count == 2
