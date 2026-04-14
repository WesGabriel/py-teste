# Python Agent

Backend FastAPI que responde perguntas sobre arquitetura e boas práticas Python consultando uma KB Markdown via HTTP. Se nenhuma seção da KB for relevante para a pergunta, o fallback é retornado antes de chamar o LLM — sem tokens desperdiçados, sem alucinação.

---

## Como funciona

```
POST /messages
    │
    ▼
Agent.run(message, session_id)
    │
    ├─▶ KBTool.search(query)
    │       ├─▶ _fetch_raw()  ── cache TTL ──▶ HTTP GET KB_URL
    │       ├─▶ parse_sections()  (descarta "Pontos de atenção")
    │       └─▶ score_section()   (Jaccard sobre palavras normalizadas)
    │
    ├─ score < threshold? ──▶ FALLBACK  (LLM não é chamado)
    │
    ├─▶ InMemorySessionStore.get_history(session_id)
    │
    ├─▶ LLMClient.complete(system_prompt, messages)
    │       └─ LLMError? ──▶ FALLBACK
    │
    ├─▶ InMemorySessionStore.add_message(...)
    │
    └─▶ { answer, sources[] }
```

---

## Estrutura

```
app/
  main.py                  # lifespan monta o grafo de dependências
  api/
    routes.py              # POST /messages
    schemas.py             # MessageRequest, MessageResponse, SourceItem
  core/
    config.py              # Settings(BaseSettings) — falha rápido se var faltando
    constants.py           # FALLBACK_ANSWER, TRAP_SECTION_MARKER
  orchestration/
    agent.py               # coordena KB + LLM + memória
  tools/
    kb_tool.py             # fetch HTTP, cache TTL, search com scoring
    markdown_parser.py     # parse_sections, normalize, score_section
  llm/
    client.py              # LLMClient, LLMError, LLMResponse
  memory/
    session_store.py       # InMemorySessionStore (TTL + max_messages)
  prompts/
    system.py              # build_system_prompt()
tests/
  test_contract.py         # contrato HTTP (8 testes)
  test_kb_tool.py          # parser e scorer (16 testes)
  test_agent.py            # orquestração, todos mockados (9 testes)
  test_llm_client.py       # LLMClient e prompt (10 testes)
  test_session_store.py    # memória de sessão (14 testes)
```

---

## Setup

```bash
uv venv .venv
make install
cp .env.example .env   # preencha LLM_API_KEY
make dev
```

Swagger em `http://localhost:8000/docs`.

## Docker

```bash
cp .env.example .env
make up
curl http://localhost:8000/health
make down
```

---

## Usando a API

```bash
# pergunta dentro do escopo
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "o que é composição?"}' | jq
# { "answer": "...", "sources": [{"section": "Composição"}] }

# pergunta fora do escopo
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "qual é a previsão do tempo?"}' | jq
# { "answer": "Não encontrei informação suficiente...", "sources": [] }

# com memória de sessão
curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "o que é SRP?", "session_id": "s1"}' | jq

curl -s -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "como isso se relaciona com composição?", "session_id": "s1"}' | jq
```

---

## Testes

```bash
make test
# 59 passed, 1 skipped
```

Todos unitários — sem LLM real, sem KB real. O único teste live é pulado quando `LLM_API_KEY` não está definida.

---

## Variáveis de ambiente

| Variável       | Obrigatória | Padrão                      | Descrição                                             |
|----------------|:-----------:|-----------------------------|-------------------------------------------------------|
| `KB_URL`       | Sim         | —                           | URL da KB Markdown                                    |
| `LLM_API_KEY`  | Sim         | —                           | Chave do provedor LLM                                 |
| `LLM_MODEL`    | Não         | `gpt-4o-mini`               | Modelo                                                |
| `LLM_BASE_URL` | Não         | `https://api.openai.com/v1` | Suporta OpenRouter, LM Studio, etc.                   |
| `LLM_PROVIDER` | Não         | `openai`                    | Identificador do provedor (informativo)               |
| `MEMORY_STORE` | Não         | `memory`                    | Tipo de store (`memory` implementado)                 |
| `HOST`         | Não         | `0.0.0.0`                   | Interface do servidor                                 |
| `PORT`         | Não         | `8000`                      | Porta                                                 |

---

## Notas de design

**Threshold antes do LLM.** `Agent.run` busca na KB primeiro. Se nenhuma seção atingir `relevance_threshold`, retorna o fallback na hora — sem chamar o LLM. Isso evita alucinação em perguntas fora do escopo e economiza tokens.

**Filtro de armadilhas no parsing.** Seções com título contendo `"Pontos de atenção"` (e subsections `### Ponto de atenção`) são descartadas em `parse_sections`, antes de qualquer scoring. O filtro é aplicado uma vez, na borda do sistema.

**Jaccard por palavras normalizadas.** Relevância calculada como `|q_words ∩ s_words| / |q_words|` após NFKD + lowercase + remoção de pontuação. Determinístico, testável sem mock, sem dependência externa.

**Composição pura.** `Agent` recebe `KBTool`, `LLMClient` e `InMemorySessionStore` via construtor. `httpx.AsyncClient` é injetado em `KBTool.search()` por chamada, não armazenado na instância — mantém o pool gerenciado pelo `lifespan`. Em testes, qualquer camada pode ser substituída por um mock sem patches globais.

**Limitações.** Store in-memory (histórico perdido ao reiniciar); sem retry na KB (falhas de rede propagam 5xx intencionalmente); scoring por palavras-chave pode não funcionar quando a pergunta usa vocabulário diferente da KB.
