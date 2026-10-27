import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import str_enum
from prefix_api.domain.enums import ProtocolStatus, StepCategory


class PrepProtocol(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    """One immutable version of a prep protocol.

    All versions of the same protocol share a ``family_id``. Only APPROVED versions may
    ever be used to generate patient timelines (safety rule a).
    """

    __tablename__ = "prep_protocol"
    __table_args__ = (
        UniqueConstraint("family_id", "version"),
        CheckConstraint(
            "status != 'APPROVED' OR (approved_by_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="approved_has_approver",
        ),
    )

    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    procedure_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("procedure_type.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProtocolStatus] = mapped_column(
        str_enum(ProtocolStatus, "protocol_status"), default=ProtocolStatus.DRAFT
    )
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[PrepStep]] = relationship(
        back_populates="protocol",
        order_by="PrepStep.sort_order",
        cascade="all, delete-orphan",
    )


class PrepStep(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "prep_step"
    __table_args__ = (CheckConstraint("offset_minutes >= 0", name="offset_not_negative"),)

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("prep_protocol.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Minutes before the procedure start at which this step applies.
    offset_minutes: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    instruction_text: Mapped[str] = mapped_column(Text)
    category: Mapped[StepCategory] = mapped_column(str_enum(StepCategory, "step_category"))
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    # Applicability rule evaluated against patient condition flags; null = always applies.
    conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    protocol: Mapped[PrepProtocol] = relationship(back_populates="steps")
