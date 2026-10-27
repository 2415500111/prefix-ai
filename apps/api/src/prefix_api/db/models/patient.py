import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey
from prefix_api.db.types import EncryptedDate, EncryptedString, str_enum
from prefix_api.domain.enums import MessageChannel


class Patient(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    """A patient. Identifying fields are encrypted; `*_bidx` columns allow exact lookup."""

    __tablename__ = "patient"
    __table_args__ = (
        UniqueConstraint("organization_id", "mrn_bidx"),
        Index("ix_patient_org_phone_bidx", "organization_id", "phone_bidx"),
        Index("ix_patient_org_email_bidx", "organization_id", "email_bidx"),
    )

    # Encrypted PII
    first_name: Mapped[str] = mapped_column(EncryptedString("patient.first_name"))
    last_name: Mapped[str] = mapped_column(EncryptedString("patient.last_name"))
    date_of_birth: Mapped[dt.date] = mapped_column(EncryptedDate("patient.date_of_birth"))
    phone: Mapped[str | None] = mapped_column(EncryptedString("patient.phone"))
    email: Mapped[str | None] = mapped_column(EncryptedString("patient.email"))
    mrn: Mapped[str | None] = mapped_column(EncryptedString("patient.mrn"))

    # Keyed hashes of normalized values, for exact-match search without decrypting.
    phone_bidx: Mapped[str | None] = mapped_column(String(64))
    email_bidx: Mapped[str | None] = mapped_column(String(64))
    mrn_bidx: Mapped[str | None] = mapped_column(String(64))

    # Communication preferences and consent
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    preferred_channel: Mapped[MessageChannel] = mapped_column(
        str_enum(MessageChannel, "message_channel"), default=MessageChannel.SMS
    )
    consent_to_message: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_timestamp: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # Condition flags used by protocol step conditions
    on_anticoagulant: Mapped[bool] = mapped_column(Boolean, default=False)
    diabetic_on_insulin: Mapped[bool] = mapped_column(Boolean, default=False)
    on_glp1_agonist: Mapped[bool] = mapped_column(Boolean, default=False)
    has_contrast_allergy: Mapped[bool] = mapped_column(Boolean, default=False)
    egfr_value: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    has_metal_implant: Mapped[bool] = mapped_column(Boolean, default=False)


class PatientMagicLink(UUIDPrimaryKey, TenantScoped, Base):
    """A single-use login link for a patient. Only the token's SHA-256 hash is stored."""

    __tablename__ = "patient_magic_link"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patient.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
