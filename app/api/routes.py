import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.schemas import MessageRequest, MessageResponse, SourceItem

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/messages", response_model=MessageResponse)
async def post_message(body: MessageRequest, request: Request) -> MessageResponse:
    agent = request.app.state.agent
    http_client = request.app.state.http_client

    try:
        result = await agent.run(
            message=body.message,
            http_client=http_client,
            session_id=body.session_id,
        )
    except Exception as exc:
        logger.error("Erro inesperado em post_message: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno no servidor."},
        )

    return MessageResponse(
        answer=result.answer,
        sources=[SourceItem(section=s["section"]) for s in result.sources],
    )
