from unittest.mock import AsyncMock, patch

import pytest

from app.tools.kb_tool import KBTool
from app.tools.markdown_parser import KBSection, normalize, parse_sections, score_section

SAMPLE_KB = """\
# Python Agent Knowledge Base

## Composição
Composição é a técnica de combinar objetos como dependências.
Use quando quiser flexibilidade e testabilidade.

## Herança
Herança é útil para hierarquias estáveis e bem definidas.
Evite herança profunda.

## Orquestração
O agente orquestra chamadas de ferramentas e do LLM.
Decide qual caminho seguir com base no contexto.

## Pontos de atenção
Esta seção é uma armadilha conceitual e não deve aparecer nos resultados.

## Validação
Validação garante contratos entre camadas do sistema.
"""

TRAP_ONLY_KB = """\
# KB

## Pontos de atenção
Conteúdo de armadilha.

## PONTOS DE ATENÇÃO
Outra variação da armadilha.
"""

REAL_STRUCTURE_KB = """\
# KB Real

## Composição

### Definição
Composição é combinar objetos.

### Ponto de atenção
"Composição é sempre melhor que herança em qualquer cenário."

## Herança

### Definição
Herança compartilha comportamento.

### Ponto de atenção
"Herança é sempre a pior escolha."
"""


def test_parse_sections_basic() -> None:
    sections = parse_sections(SAMPLE_KB)
    titles = [s.title for s in sections]
    assert "Composição" in titles
    assert "Herança" in titles
    assert "Orquestração" in titles


def test_parse_sections_count_excludes_trap() -> None:
    sections = parse_sections(SAMPLE_KB)
    assert len(sections) == 4


def test_parse_filters_trap() -> None:
    sections = parse_sections(SAMPLE_KB)
    titles = [s.title for s in sections]
    assert "Pontos de atenção" not in titles


def test_parse_trap_case_insensitive() -> None:
    sections = parse_sections(TRAP_ONLY_KB)
    assert sections == []


def test_parse_body_content() -> None:
    sections = parse_sections(SAMPLE_KB)
    composicao = next(s for s in sections if s.title == "Composição")
    assert "combinar objetos" in composicao.body


def test_parse_strips_trap_subsections_from_body() -> None:
    sections = parse_sections(REAL_STRUCTURE_KB)
    composicao = next(s for s in sections if s.title == "Composição")
    assert "sempre melhor que herança" not in composicao.body


def test_parse_keeps_definition_after_trap_removal() -> None:
    sections = parse_sections(REAL_STRUCTURE_KB)
    composicao = next(s for s in sections if s.title == "Composição")
    assert "combinar objetos" in composicao.body


def test_parse_strips_trap_from_all_sections() -> None:
    sections = parse_sections(REAL_STRUCTURE_KB)
    heranca = next(s for s in sections if s.title == "Herança")
    assert "sempre a pior escolha" not in heranca.body


def test_normalize_strips_accents() -> None:
    assert normalize("atenção") == "atencao"


def test_normalize_lowercase() -> None:
    assert normalize("COMPOSIÇÃO") == "composicao"


def test_normalize_removes_punctuation() -> None:
    result = normalize("olá, mundo!")
    assert "," not in result
    assert "!" not in result


def test_score_exact_overlap() -> None:
    section = KBSection(title="Composição", body="objetos dependencias flexibilidade")
    score = score_section(section, "composicao objetos")
    assert score == 1.0


def test_score_zero_overlap() -> None:
    section = KBSection(title="Herança", body="hierarquia estavel")
    score = score_section(section, "pizza macarrão")
    assert score == 0.0


def test_score_partial_overlap() -> None:
    section = KBSection(title="Herança", body="hierarquia estavel")
    score = score_section(section, "heranca pizza macarrao")
    assert abs(score - 1 / 3) < 1e-9


def test_score_empty_query() -> None:
    section = KBSection(title="X", body="anything")
    assert score_section(section, "") == 0.0


@pytest.mark.anyio
async def test_search_below_threshold_returns_empty() -> None:
    tool = KBTool(kb_url="http://fake", threshold=0.15)

    with patch.object(tool, "_fetch_raw", new=AsyncMock(return_value=SAMPLE_KB)):
        sections, above = await tool.search("pizza macarrão", client=None)  

    assert sections == []
    assert above is False


@pytest.mark.anyio
async def test_search_returns_relevant_section() -> None:
    tool = KBTool(kb_url="http://fake", threshold=0.10)

    with patch.object(tool, "_fetch_raw", new=AsyncMock(return_value=SAMPLE_KB)):
        sections, above = await tool.search("o que é composição", client=None)  

    assert above is True
    titles = [s.title for s in sections]
    assert "Composição" in titles


@pytest.mark.anyio
async def test_search_respects_top_n() -> None:
    tool = KBTool(kb_url="http://fake", threshold=0.05, top_n=1)

    with patch.object(tool, "_fetch_raw", new=AsyncMock(return_value=SAMPLE_KB)):
        sections, above = await tool.search("composição herança orquestração", client=None)  

    assert len(sections) <= 1


@pytest.mark.anyio
async def test_cache_not_refetched_within_ttl() -> None:
    tool = KBTool(kb_url="http://fake", ttl=300, threshold=0.0, top_n=5)
    mock_fetch = AsyncMock(return_value=SAMPLE_KB)

    with patch.object(tool, "_fetch_raw", new=mock_fetch):
        await tool.search("composição", client=None)  
        await tool.search("herança", client=None)  

    assert mock_fetch.call_count == 2
