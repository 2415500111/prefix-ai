"""Core data model: tenants, users, patients, scheduling, protocols, engagement, audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27 22:15:51.959747
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column(
            "actor_type",
            sa.Enum(
                "USER",
                "PATIENT",
                "SYSTEM",
                "ANONYMOUS",
                name="actor_type",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "READ",
                "LIST",
                "CREATE",
                "UPDATE",
                "DELETE",
                "EXPORT",
                "LOGIN",
                "LOGIN_FAILED",
                "LOGOUT",
                "TOKEN_REFRESH",
                "TOKEN_REUSE_DETECTED",
                "MAGIC_LINK_ISSUED",
                "MAGIC_LINK_REDEEMED",
                "MAGIC_LINK_REJECTED",
                name="audit_action",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_log_occurred_at"), "audit_log", ["occurred_at"], unique=False)
    op.create_index(
        op.f("ix_audit_log_organization_id"), "audit_log", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_audit_log_patient_id"), "audit_log", ["patient_id"], unique=False)
    op.create_table(
        "organization",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("default_timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
        sa.UniqueConstraint("slug", name=op.f("uq_organization_slug")),
    )
    op.create_table(
        "app_user",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "ADMIN",
                "COORDINATOR",
                "NURSE",
                "CLINICIAN",
                "VIEWER",
                name="role",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_app_user_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_index(
        op.f("ix_app_user_organization_id"), "app_user", ["organization_id"], unique=False
    )
    op.create_table(
        "facility",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("maps_url", sa.String(length=1000), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_facility_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facility")),
        sa.UniqueConstraint(
            "organization_id", "name", name=op.f("uq_facility_organization_id_name")
        ),
    )
    op.create_index(
        op.f("ix_facility_organization_id"), "facility", ["organization_id"], unique=False
    )
    op.create_table(
        "patient",
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("date_of_birth", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("mrn", sa.Text(), nullable=True),
        sa.Column("phone_bidx", sa.String(length=64), nullable=True),
        sa.Column("email_bidx", sa.String(length=64), nullable=True),
        sa.Column("mrn_bidx", sa.String(length=64), nullable=True),
        sa.Column("preferred_language", sa.String(length=8), nullable=False),
        sa.Column(
            "preferred_channel",
            sa.Enum(
                "SMS",
                "WHATSAPP",
                "EMAIL",
                "PORTAL",
                name="message_channel",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("consent_to_message", sa.Boolean(), nullable=False),
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("on_anticoagulant", sa.Boolean(), nullable=False),
        sa.Column("diabetic_on_insulin", sa.Boolean(), nullable=False),
        sa.Column("on_glp1_agonist", sa.Boolean(), nullable=False),
        sa.Column("has_contrast_allergy", sa.Boolean(), nullable=False),
        sa.Column("egfr_value", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("has_metal_implant", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_patient_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient")),
        sa.UniqueConstraint(
            "organization_id", "mrn_bidx", name=op.f("uq_patient_organization_id_mrn_bidx")
        ),
    )
    op.create_index(
        "ix_patient_org_email_bidx", "patient", ["organization_id", "email_bidx"], unique=False
    )
    op.create_index(
        "ix_patient_org_phone_bidx", "patient", ["organization_id", "phone_bidx"], unique=False
    )
    op.create_index(
        op.f("ix_patient_organization_id"), "patient", ["organization_id"], unique=False
    )
    op.create_table(
        "procedure_type",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("or_cost_per_minute", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("requires_sedation", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_procedure_type_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procedure_type")),
        sa.UniqueConstraint(
            "organization_id", "code", name=op.f("uq_procedure_type_organization_id_code")
        ),
    )
    op.create_index(
        op.f("ix_procedure_type_organization_id"),
        "procedure_type",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "patient_magic_link",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_patient_magic_link_created_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_patient_magic_link_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_patient_magic_link_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_magic_link")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_patient_magic_link_token_hash")),
    )
    op.create_index(
        op.f("ix_patient_magic_link_organization_id"),
        "patient_magic_link",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_magic_link_patient_id"), "patient_magic_link", ["patient_id"], unique=False
    )
    op.create_table(
        "prep_protocol",
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("procedure_type_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "APPROVED",
                "RETIRED",
                name="protocol_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status != 'APPROVED' OR (approved_by_id IS NOT NULL AND approved_at IS NOT NULL)",
            name=op.f("ck_prep_protocol_approved_has_approver"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"],
            ["app_user.id"],
            name=op.f("fk_prep_protocol_approved_by_id_app_user"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["app_user.id"],
            name=op.f("fk_prep_protocol_created_by_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_prep_protocol_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_type_id"],
            ["procedure_type.id"],
            name=op.f("fk_prep_protocol_procedure_type_id_procedure_type"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_protocol")),
        sa.UniqueConstraint(
            "family_id", "version", name=op.f("uq_prep_protocol_family_id_version")
        ),
    )
    op.create_index(
        op.f("ix_prep_protocol_family_id"), "prep_protocol", ["family_id"], unique=False
    )
    op.create_index(
        op.f("ix_prep_protocol_organization_id"), "prep_protocol", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_prep_protocol_procedure_type_id"),
        "prep_protocol",
        ["procedure_type_id"],
        unique=False,
    )
    op.create_table(
        "refresh_token",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_refresh_token_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_token_token_hash")),
    )
    op.create_index(
        op.f("ix_refresh_token_family_id"), "refresh_token", ["family_id"], unique=False
    )
    op.create_index(op.f("ix_refresh_token_user_id"), "refresh_token", ["user_id"], unique=False)
    op.create_table(
        "waitlist_entry",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("procedure_type_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=True),
        sa.Column("earliest_date", sa.Date(), nullable=False),
        sa.Column("latest_date", sa.Date(), nullable=False),
        sa.Column("prep_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "OFFERED",
                "BOOKED",
                "REMOVED",
                name="waitlist_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "latest_date >= earliest_date", name=op.f("ck_waitlist_entry_date_window_valid")
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facility.id"],
            name=op.f("fk_waitlist_entry_facility_id_facility"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_waitlist_entry_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_waitlist_entry_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_type_id"],
            ["procedure_type.id"],
            name=op.f("fk_waitlist_entry_procedure_type_id_procedure_type"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waitlist_entry")),
    )
    op.create_index(
        op.f("ix_waitlist_entry_organization_id"),
        "waitlist_entry",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_waitlist_entry_patient_id"), "waitlist_entry", ["patient_id"], unique=False
    )
    op.create_index(
        op.f("ix_waitlist_entry_procedure_type_id"),
        "waitlist_entry",
        ["procedure_type_id"],
        unique=False,
    )
    op.create_index(op.f("ix_waitlist_entry_status"), "waitlist_entry", ["status"], unique=False)
    op.create_table(
        "appointment",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("procedure_type_id", sa.Uuid(), nullable=False),
        sa.Column("clinician_id", sa.Uuid(), nullable=True),
        sa.Column("protocol_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SCHEDULED",
                "READY",
                "AT_RISK",
                "CANCELLED",
                "COMPLETED",
                name="appointment_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "cancellation_reason",
            sa.Enum(
                "INADEQUATE_BOWEL_PREP",
                "ATE_OR_DRANK",
                "MEDICATION_NOT_STOPPED",
                "NO_ESCORT",
                "MISSING_LABS",
                "MISSING_PAPERWORK",
                "PATIENT_NO_SHOW",
                "PATIENT_REQUESTED",
                "CLINICAL_REASON",
                "FACILITY_OR_STAFF",
                "OTHER",
                name="cancellation_reason",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=True,
        ),
        sa.Column("cancellation_note", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinician_id"],
            ["app_user.id"],
            name=op.f("fk_appointment_clinician_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facility.id"],
            name=op.f("fk_appointment_facility_id_facility"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_appointment_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_appointment_patient_id_patient"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_type_id"],
            ["procedure_type.id"],
            name=op.f("fk_appointment_procedure_type_id_procedure_type"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_id"],
            ["prep_protocol.id"],
            name=op.f("fk_appointment_protocol_id_prep_protocol"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment")),
    )
    op.create_index(
        op.f("ix_appointment_clinician_id"), "appointment", ["clinician_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointment_facility_id"), "appointment", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointment_organization_id"), "appointment", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_appointment_patient_id"), "appointment", ["patient_id"], unique=False)
    op.create_index(
        op.f("ix_appointment_procedure_type_id"), "appointment", ["procedure_type_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointment_scheduled_at"), "appointment", ["scheduled_at"], unique=False
    )
    op.create_index(op.f("ix_appointment_status"), "appointment", ["status"], unique=False)
    op.create_table(
        "prep_step",
        sa.Column("protocol_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "DIET",
                "FASTING",
                "MEDICATION",
                "BOWEL_PREP",
                "LAB",
                "LOGISTICS",
                "PAPERWORK",
                name="step_category",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("offset_minutes >= 0", name=op.f("ck_prep_step_offset_not_negative")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_prep_step_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_id"],
            ["prep_protocol.id"],
            name=op.f("fk_prep_step_protocol_id_prep_protocol"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_step")),
    )
    op.create_index(
        op.f("ix_prep_step_organization_id"), "prep_step", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_prep_step_protocol_id"), "prep_step", ["protocol_id"], unique=False)
    op.create_table(
        "escalation",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "RED_FLAG",
                "OUT_OF_PROTOCOL",
                "PATIENT_REPORTED_PROBLEM",
                "HIGH_RISK",
                "STAFF",
                name="escalation_source",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "URGENT",
                "HIGH",
                "NORMAL",
                name="escalation_severity",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "ACKNOWLEDGED",
                "RESOLVED",
                name="escalation_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_escalation_appointment_id_appointment"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"],
            ["app_user.id"],
            name=op.f("fk_escalation_assigned_to_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_escalation_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_escalation_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_escalation")),
    )
    op.create_index(
        op.f("ix_escalation_appointment_id"), "escalation", ["appointment_id"], unique=False
    )
    op.create_index(
        op.f("ix_escalation_organization_id"), "escalation", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_escalation_patient_id"), "escalation", ["patient_id"], unique=False)
    op.create_index(op.f("ix_escalation_status"), "escalation", ["status"], unique=False)
    op.create_table(
        "patient_timeline_event",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SENT",
                "CONFIRMED",
                "MISSED",
                "SKIPPED",
                "CANCELLED",
                "FAILED",
                name="timeline_event_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_patient_timeline_event_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_patient_timeline_event_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_patient_timeline_event_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["prep_step.id"],
            name=op.f("fk_patient_timeline_event_step_id_prep_step"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_timeline_event")),
        sa.UniqueConstraint(
            "appointment_id",
            "step_id",
            name=op.f("uq_patient_timeline_event_appointment_id_step_id"),
        ),
    )
    op.create_index(
        op.f("ix_patient_timeline_event_appointment_id"),
        "patient_timeline_event",
        ["appointment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_timeline_event_due_at"), "patient_timeline_event", ["due_at"], unique=False
    )
    op.create_index(
        op.f("ix_patient_timeline_event_organization_id"),
        "patient_timeline_event",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_timeline_event_patient_id"),
        "patient_timeline_event",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_timeline_event_send_at"),
        "patient_timeline_event",
        ["send_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_timeline_event_status"), "patient_timeline_event", ["status"], unique=False
    )
    op.create_table(
        "risk_score",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                name="risk_level",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name=op.f("ck_risk_score_score_range")),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_risk_score_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_risk_score_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_score")),
    )
    op.create_index(
        op.f("ix_risk_score_appointment_id"), "risk_score", ["appointment_id"], unique=False
    )
    op.create_index(op.f("ix_risk_score_computed_at"), "risk_score", ["computed_at"], unique=False)
    op.create_index(
        op.f("ix_risk_score_organization_id"), "risk_score", ["organization_id"], unique=False
    )
    op.create_table(
        "check_in",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("timeline_event_id", sa.Uuid(), nullable=True),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "ANSWERED",
                "EXPIRED",
                name="check_in_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "response",
            sa.Enum(
                "YES",
                "NO",
                "HELP",
                "OTHER",
                name="check_in_response",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=True,
        ),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_check_in_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_check_in_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_check_in_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["timeline_event_id"],
            ["patient_timeline_event.id"],
            name=op.f("fk_check_in_timeline_event_id_patient_timeline_event"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_in")),
    )
    op.create_index(
        op.f("ix_check_in_appointment_id"), "check_in", ["appointment_id"], unique=False
    )
    op.create_index(
        op.f("ix_check_in_organization_id"), "check_in", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_check_in_patient_id"), "check_in", ["patient_id"], unique=False)
    op.create_index(op.f("ix_check_in_status"), "check_in", ["status"], unique=False)
    op.create_table(
        "message",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("timeline_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum(
                "SMS",
                "WHATSAPP",
                "EMAIL",
                "PORTAL",
                name="message_channel",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "direction",
            sa.Enum(
                "OUTBOUND",
                "INBOUND",
                name="message_direction",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "SENT",
                "DELIVERED",
                "FAILED",
                "RECEIVED",
                name="message_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("original_body", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_message_appointment_id_appointment"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_message_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_message_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["timeline_event_id"],
            ["patient_timeline_event.id"],
            name=op.f("fk_message_timeline_event_id_patient_timeline_event"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
    )
    op.create_index(op.f("ix_message_appointment_id"), "message", ["appointment_id"], unique=False)
    op.create_index(
        op.f("ix_message_organization_id"), "message", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_message_patient_id"), "message", ["patient_id"], unique=False)
    op.create_index(
        op.f("ix_message_provider_message_id"), "message", ["provider_message_id"], unique=False
    )
    op.create_table(
        "task",
        sa.Column(
            "type",
            sa.Enum(
                "CALL_PATIENT",
                "CONFIRM_ESCORT",
                "REVIEW_RISK",
                "RESCHEDULE",
                "BACKFILL_SLOT",
                "NURSE_REVIEW",
                "OTHER",
                name="task_type",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "DONE",
                "CANCELLED",
                name="task_status",
                native_enum=False,
                create_constraint=True,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=True),
        sa.Column("escalation_id", sa.Uuid(), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_task_appointment_id_appointment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["app_user.id"],
            name=op.f("fk_task_assignee_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["escalation_id"],
            ["escalation.id"],
            name=op.f("fk_task_escalation_id_escalation"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_task_organization_id_organization"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_task_patient_id_patient"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
    )
    op.create_index(op.f("ix_task_appointment_id"), "task", ["appointment_id"], unique=False)
    op.create_index(op.f("ix_task_assignee_id"), "task", ["assignee_id"], unique=False)
    op.create_index(op.f("ix_task_due_at"), "task", ["due_at"], unique=False)
    op.create_index(op.f("ix_task_organization_id"), "task", ["organization_id"], unique=False)
    op.create_index(op.f("ix_task_patient_id"), "task", ["patient_id"], unique=False)
    op.create_index(op.f("ix_task_status"), "task", ["status"], unique=False)
    # Audit history is append-only: reject UPDATE, DELETE and TRUNCATE at the database level.
    op.execute(
        """
        CREATE FUNCTION audit_log_reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (% rejected)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_reject_change()"
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_reject_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_reject_change()")
    op.drop_index(op.f("ix_task_status"), table_name="task")
    op.drop_index(op.f("ix_task_patient_id"), table_name="task")
    op.drop_index(op.f("ix_task_organization_id"), table_name="task")
    op.drop_index(op.f("ix_task_due_at"), table_name="task")
    op.drop_index(op.f("ix_task_assignee_id"), table_name="task")
    op.drop_index(op.f("ix_task_appointment_id"), table_name="task")
    op.drop_table("task")
    op.drop_index(op.f("ix_message_provider_message_id"), table_name="message")
    op.drop_index(op.f("ix_message_patient_id"), table_name="message")
    op.drop_index(op.f("ix_message_organization_id"), table_name="message")
    op.drop_index(op.f("ix_message_appointment_id"), table_name="message")
    op.drop_table("message")
    op.drop_index(op.f("ix_check_in_status"), table_name="check_in")
    op.drop_index(op.f("ix_check_in_patient_id"), table_name="check_in")
    op.drop_index(op.f("ix_check_in_organization_id"), table_name="check_in")
    op.drop_index(op.f("ix_check_in_appointment_id"), table_name="check_in")
    op.drop_table("check_in")
    op.drop_index(op.f("ix_risk_score_organization_id"), table_name="risk_score")
    op.drop_index(op.f("ix_risk_score_computed_at"), table_name="risk_score")
    op.drop_index(op.f("ix_risk_score_appointment_id"), table_name="risk_score")
    op.drop_table("risk_score")
    op.drop_index(op.f("ix_patient_timeline_event_status"), table_name="patient_timeline_event")
    op.drop_index(op.f("ix_patient_timeline_event_send_at"), table_name="patient_timeline_event")
    op.drop_index(op.f("ix_patient_timeline_event_patient_id"), table_name="patient_timeline_event")
    op.drop_index(
        op.f("ix_patient_timeline_event_organization_id"), table_name="patient_timeline_event"
    )
    op.drop_index(op.f("ix_patient_timeline_event_due_at"), table_name="patient_timeline_event")
    op.drop_index(
        op.f("ix_patient_timeline_event_appointment_id"), table_name="patient_timeline_event"
    )
    op.drop_table("patient_timeline_event")
    op.drop_index(op.f("ix_escalation_status"), table_name="escalation")
    op.drop_index(op.f("ix_escalation_patient_id"), table_name="escalation")
    op.drop_index(op.f("ix_escalation_organization_id"), table_name="escalation")
    op.drop_index(op.f("ix_escalation_appointment_id"), table_name="escalation")
    op.drop_table("escalation")
    op.drop_index(op.f("ix_prep_step_protocol_id"), table_name="prep_step")
    op.drop_index(op.f("ix_prep_step_organization_id"), table_name="prep_step")
    op.drop_table("prep_step")
    op.drop_index(op.f("ix_appointment_status"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_scheduled_at"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_procedure_type_id"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_patient_id"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_organization_id"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_facility_id"), table_name="appointment")
    op.drop_index(op.f("ix_appointment_clinician_id"), table_name="appointment")
    op.drop_table("appointment")
    op.drop_index(op.f("ix_waitlist_entry_status"), table_name="waitlist_entry")
    op.drop_index(op.f("ix_waitlist_entry_procedure_type_id"), table_name="waitlist_entry")
    op.drop_index(op.f("ix_waitlist_entry_patient_id"), table_name="waitlist_entry")
    op.drop_index(op.f("ix_waitlist_entry_organization_id"), table_name="waitlist_entry")
    op.drop_table("waitlist_entry")
    op.drop_index(op.f("ix_refresh_token_user_id"), table_name="refresh_token")
    op.drop_index(op.f("ix_refresh_token_family_id"), table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_index(op.f("ix_prep_protocol_procedure_type_id"), table_name="prep_protocol")
    op.drop_index(op.f("ix_prep_protocol_organization_id"), table_name="prep_protocol")
    op.drop_index(op.f("ix_prep_protocol_family_id"), table_name="prep_protocol")
    op.drop_table("prep_protocol")
    op.drop_index(op.f("ix_patient_magic_link_patient_id"), table_name="patient_magic_link")
    op.drop_index(op.f("ix_patient_magic_link_organization_id"), table_name="patient_magic_link")
    op.drop_table("patient_magic_link")
    op.drop_index(op.f("ix_procedure_type_organization_id"), table_name="procedure_type")
    op.drop_table("procedure_type")
    op.drop_index(op.f("ix_patient_organization_id"), table_name="patient")
    op.drop_index("ix_patient_org_phone_bidx", table_name="patient")
    op.drop_index("ix_patient_org_email_bidx", table_name="patient")
    op.drop_table("patient")
    op.drop_index(op.f("ix_facility_organization_id"), table_name="facility")
    op.drop_table("facility")
    op.drop_index(op.f("ix_app_user_organization_id"), table_name="app_user")
    op.drop_table("app_user")
    op.drop_table("organization")
    op.drop_index(op.f("ix_audit_log_patient_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_organization_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_occurred_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
