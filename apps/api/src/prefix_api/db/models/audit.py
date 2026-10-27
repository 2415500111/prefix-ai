import datetime as dt
import uuid
from typing import Any

from sqlalchemy import BigInteger, DateTime, Identity, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base
from prefix_api.db.types import str_enum
from prefix_api.domain.enums import ActorType, AuditAction


class AuditLog(Base):
    """Append-only record of who did what to which record, when, why and from where.

    A database trigger rejects UPDATE and DELETE. ``details`` must never contain PHI.
    No foreign keys: audit rows must outlive the records they describe.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    actor_type: Mapped[ActorType] = mapped_column(str_enum(ActorType, "actor_type"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[AuditAction] = mapped_column(str_enum(AuditAction, "audit_action"))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    purpose: Mapped[str] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    request_id: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
