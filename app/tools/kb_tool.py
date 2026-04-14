import logging
import time

import httpx

from app.tools.markdown_parser import KBSection, parse_sections, score_section

logger = logging.getLogger(__name__)


class KBTool:
    def __init__(
        self,
        kb_url: str,
        ttl: int = 300,
        top_n: int = 3,
        threshold: float = 0.15,
    ) -> None:
        self._kb_url = kb_url
        self._ttl = ttl
        self._top_n = top_n
        self._threshold = threshold
        self._cache: str | None = None
        self._fetched_at: float = 0.0

    async def _fetch_raw(self, client: httpx.AsyncClient) -> str:
        now = time.monotonic()
        if self._cache is not None and (now - self._fetched_at) < self._ttl:
            logger.debug("KB cache hit")
            return self._cache

        logger.info("Fetching KB from %s", self._kb_url)
        response = await client.get(self._kb_url, timeout=10.0)
        response.raise_for_status()
        self._cache = response.text
        self._fetched_at = now
        return self._cache

    async def search(
        self,
        query: str,
        client: httpx.AsyncClient,
    ) -> tuple[list[KBSection], bool]:
        raw = await self._fetch_raw(client)
        sections = parse_sections(raw)

        scored = sorted(
            [(score_section(s, query), s) for s in sections],
            key=lambda pair: pair[0],
            reverse=True,
        )

        top = [s for score, s in scored[: self._top_n] if score >= self._threshold]

        if not top:
            logger.info(
                "No section met threshold=%.2f for query=%r", self._threshold, query
            )
            return [], False

        logger.info(
            "Returning %d section(s) above threshold=%.2f", len(top), self._threshold
        )
        return top, True
