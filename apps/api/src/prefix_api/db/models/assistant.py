"""AI Prep Assistant exchanges: one row per patient question."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import EncryptedString, str_enum
from prefix_api.domain.enums import AssistantOutcome


class AssistantExchange(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    """A question, what the patient was shown, and why (for audit and evaluation)."""

    __tablename__ = "assistant_exchange"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointment.id", ondelete="CASCADE"), index=True
    )
    # The patient's own words and the reply may both describe health details: encrypted.
    question: Mapped[str] = mapped_column(EncryptedString("assistant_exchange.question"))
    reply: Mapped[str] = mapped_column(EncryptedString("assistant_exchange.reply"))
    language: Mapped[str] = mapped_column(String(8))
    outcome: Mapped[AssistantOutcome] = mapped_column(
        str_enum(AssistantOutcome, "assistant_outcome"), index=True
    )
    # Red-flag categories found by the deterministic rules (e.g. ["CHEST_PAIN"]).
    red_flags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Short explanation from the LLM triage or the failed check, for the nurse.
    reason: Mapped[str | None] = mapped_column(EncryptedString("assistant_exchange.reason"))
    cited_event_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # How many identifiers of each kind were removed before the LLM saw the question.
    redactions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("escalation.id", ondelete="SET NULL")
    )
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
