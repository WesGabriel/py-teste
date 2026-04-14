import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.llm.client import LLMClient
from app.memory.session_store import InMemorySessionStore
from app.orchestration.agent import Agent
from app.tools.kb_tool import KBTool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("Iniciando aplicação model=%s", settings.llm_model)

    http_client = httpx.AsyncClient()

    kb_tool = KBTool(
        kb_url=settings.kb_url,
        ttl=settings.kb_cache_ttl,
        top_n=settings.top_n_sections,
        threshold=settings.relevance_threshold,
    )

    llm_client = LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )

    session_store = InMemorySessionStore()

    agent = Agent(kb_tool=kb_tool, llm_client=llm_client, session_store=session_store)

    app.state.http_client = http_client
    app.state.agent = agent

    logger.info("Aplicação pronta")
    yield

    await http_client.aclose()
    logger.info("Aplicação encerrada")


app = FastAPI(title="AI Agent Backend", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
