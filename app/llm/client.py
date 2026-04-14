import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, system: str, messages: list[dict[str, str]]) -> LLMResponse:
        try:
            logger.info("Chamando LLM model=%s mensagens=%d", self._model, len(messages))
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=0.2,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise LLMError("LLM retornou resposta vazia")

            logger.info("LLM respondeu model=%s tokens=%s", response.model, response.usage)
            return LLMResponse(content=content, model=response.model)

        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Falha na chamada ao LLM: {exc}") from exc
