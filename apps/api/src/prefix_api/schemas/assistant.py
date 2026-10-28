import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from prefix_api.domain.enums import AssistantOutcome
from prefix_api.schemas.patients import LanguageCode
from prefix_api.services.assistant.llm import MAX_QUESTION_CHARS
from prefix_api.services.assistant.service import AssistantReply

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=MAX_QUESTION_CHARS)
]


class AssistantQuestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appointment_id: uuid.UUID
    question: Question
    language: LanguageCode = "en"


class CitationOut(BaseModel):
    event_id: uuid.UUID
    title: str


class AssistantReplyOut(BaseModel):
    id: uuid.UUID
    question: str
    reply: str
    outcome: AssistantOutcome
    # True when the question went to a person instead of being answered.
    escalated: bool
    citations: list[CitationOut]
    created_at: dt.datetime

    @classmethod
    def build(cls, result: AssistantReply) -> AssistantReplyOut:
        exchange = result.exchange
        return cls(
            id=exchange.id,
            question=exchange.question,
            reply=exchange.reply,
            outcome=exchange.outcome,
            escalated=result.escalated,
            citations=[CitationOut(event_id=c.event_id, title=c.title) for c in result.citations],
            created_at=exchange.created_at,
        )
