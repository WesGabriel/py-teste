import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.client import LLMClient, LLMError, LLMResponse
from app.prompts.system import build_system_prompt


def test_build_system_prompt_contains_all_sections() -> None:
    prompt = build_system_prompt(["Seção A: conteúdo A", "Seção B: conteúdo B"])
    assert "Seção A: conteúdo A" in prompt
    assert "Seção B: conteúdo B" in prompt


def test_build_system_prompt_separator() -> None:
    prompt = build_system_prompt(["A", "B"])
    assert "---" in prompt


def test_build_system_prompt_single_section() -> None:
    prompt = build_system_prompt(["Única seção"])
    assert "Única seção" in prompt
    assert prompt.count("---") == 0


def test_build_system_prompt_instruction_present() -> None:
    prompt = build_system_prompt(["qualquer coisa"])
    assert "APENAS" in prompt or "apenas" in prompt.lower()


def _make_mock_response(content: str, model: str = "gpt-4o-mini") -> MagicMock:
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.model = model
    response.usage = None
    return response


@pytest.mark.anyio
async def test_llm_client_returns_response() -> None:
    client = LLMClient(api_key="fake", base_url="http://fake", model="gpt-4o-mini")
    mock_response = _make_mock_response("Resposta do modelo")

    with patch.object(
        client._client.chat.completions,
        "create",
        new=AsyncMock(return_value=mock_response),
    ):
        result = await client.complete(
            system="instrução",
            messages=[{"role": "user", "content": "pergunta"}],
        )

    assert isinstance(result, LLMResponse)
    assert result.content == "Resposta do modelo"
    assert result.model == "gpt-4o-mini"


@pytest.mark.anyio
async def test_llm_client_includes_system_in_messages() -> None:
    client = LLMClient(api_key="fake", base_url="http://fake", model="gpt-4o-mini")
    mock_response = _make_mock_response("ok")
    captured: list[list] = []

    async def fake_create(**kwargs):  
        captured.append(kwargs["messages"])
        return mock_response

    with patch.object(client._client.chat.completions, "create", side_effect=fake_create):
        await client.complete(system="system-msg", messages=[{"role": "user", "content": "x"}])

    sent_messages = captured[0]
    assert sent_messages[0] == {"role": "system", "content": "system-msg"}
    assert sent_messages[1] == {"role": "user", "content": "x"}


@pytest.mark.anyio
async def test_llm_error_wraps_generic_exception() -> None:
    client = LLMClient(api_key="fake", base_url="http://fake", model="gpt-4o-mini")

    with patch.object(
        client._client.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("timeout")),
    ):
        with pytest.raises(LLMError, match="Falha na chamada ao LLM"):
            await client.complete(system="s", messages=[{"role": "user", "content": "q"}])


@pytest.mark.anyio
async def test_llm_error_on_empty_content() -> None:
    client = LLMClient(api_key="fake", base_url="http://fake", model="gpt-4o-mini")
    mock_response = _make_mock_response("")

    with patch.object(
        client._client.chat.completions,
        "create",
        new=AsyncMock(return_value=mock_response),
    ):
        with pytest.raises(LLMError, match="vazia"):
            await client.complete(system="s", messages=[{"role": "user", "content": "q"}])


@pytest.mark.anyio
async def test_llm_error_on_none_content() -> None:
    client = LLMClient(api_key="fake", base_url="http://fake", model="gpt-4o-mini")
    mock_response = _make_mock_response(None)  

    with patch.object(
        client._client.chat.completions,
        "create",
        new=AsyncMock(return_value=mock_response),
    ):
        with pytest.raises(LLMError):
            await client.complete(system="s", messages=[{"role": "user", "content": "q"}])


@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY não definida — pulando teste de integração live",
)
@pytest.mark.anyio
async def test_llm_client_live() -> None:
    api_key = os.environ["LLM_API_KEY"]
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    client = LLMClient(api_key=api_key, base_url=base_url, model=model)
    result = await client.complete(
        system="Responda em uma palavra.",
        messages=[{"role": "user", "content": "Diga apenas: ok"}],
    )
    assert isinstance(result.content, str)
    assert len(result.content) > 0
