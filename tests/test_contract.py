from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.constants import FALLBACK_ANSWER
from app.main import app
from app.orchestration.agent import AgentResponse


def make_mock_agent(answer: str, sources: list[dict]) -> MagicMock:
    agent = MagicMock()
    agent.run = AsyncMock(return_value=AgentResponse(answer=answer, sources=sources))
    return agent


def inject_agent(agent: MagicMock) -> None:
    app.state.agent = agent
    app.state.http_client = MagicMock()


@pytest.mark.anyio
async def test_health_returns_200() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_post_messages_returns_200_with_answer() -> None:
    inject_agent(make_mock_agent(answer="Composição é combinar objetos.", sources=[]))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={"message": "o que é composição?"})

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body


@pytest.mark.anyio
async def test_post_messages_fallback_shape() -> None:
    inject_agent(make_mock_agent(answer=FALLBACK_ANSWER, sources=[]))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={"message": "qual é o clima hoje?"})

    body = response.json()
    assert body["answer"] == FALLBACK_ANSWER
    assert body["sources"] == []


@pytest.mark.anyio
async def test_post_messages_sources_structure() -> None:
    inject_agent(
        make_mock_agent(
            answer="Resposta com fontes.",
            sources=[{"section": "Composição"}, {"section": "Herança"}],
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={"message": "composição e herança"})

    sources = response.json()["sources"]
    assert len(sources) == 2
    assert sources[0] == {"section": "Composição"}
    assert sources[1] == {"section": "Herança"}


@pytest.mark.anyio
async def test_post_messages_with_session_id() -> None:
    agent = make_mock_agent(answer="ok", sources=[])
    inject_agent(agent)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/messages",
            json={"message": "composição?", "session_id": "abc-123"},
        )

    assert response.status_code == 200
    call_kwargs = agent.run.call_args.kwargs
    assert call_kwargs.get("session_id") == "abc-123"


@pytest.mark.anyio
async def test_post_messages_empty_string_returns_422() -> None:
    inject_agent(make_mock_agent(answer="irrelevante", sources=[]))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={"message": ""})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_messages_missing_message_returns_422() -> None:
    inject_agent(make_mock_agent(answer="irrelevante", sources=[]))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_messages_message_too_long_returns_422() -> None:
    inject_agent(make_mock_agent(answer="irrelevante", sources=[]))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/messages", json={"message": "x" * 2001})

    assert response.status_code == 422
