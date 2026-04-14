from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class SourceItem(BaseModel):
    section: str


class MessageResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
