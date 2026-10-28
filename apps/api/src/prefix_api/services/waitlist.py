"""Waitlist backfill (lite): fill a released slot from the waitlist, one offer at a time.

- A released slot is a cancelled procedure that is still ahead and not yet filled.
- "Find backfill" ranks the waitlisted patients who fit: same procedure, the slot's local date
  inside their window, and enough notice for the prep. The slot is offered to the best candidate
  only. Patients who declined this slot, or who already have this procedure booked, are skipped.
- Accepting books the candidate into the slot. The slot row is locked first and the database
  allows one accepted offer per slot, so two staff members cannot book the same slot.
- Declining puts the candidate back on the list. The next "Find backfill" offers the next one.
- Locks are always taken in the order slot, offer, waitlist entry, so requests cannot deadlock.
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    BackfillOffer,
    Facility,
    Patient,
    PrepStep,
    ProcedureType,
    WaitlistEntry,
)
from prefix_api.domain.enums import (
    AppointmentStatus,
    AuditAction,
    OfferStatus,
    WaitlistStatus,
)
from prefix_api.domain.errors import ConflictError, NotFoundError, ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import organizations as org_repo
from prefix_api.repositories import patients as patients_repo
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.schemas.waitlist import WaitlistEntryCreate
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.audit import record_audit

PURPOSE = "waitlist_backfill"
SLOT_HORIZON = dt.timedelta(days=7)
MAX_CANDIDATES = 20


@dataclass(frozen=True, slots=True)
class WaitlistRow:
    entry: WaitlistEntry
    patient: Patient
    procedure_name: str


@dataclass(frozen=True, slots=True)
class Candidate:
    entry: WaitlistEntry
    patient: Patient
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class OfferView:
    offer: BackfillOffer
    patient: Patient


@dataclass(frozen=True, slots=True)
class ReleasedSlot:
    appointment: Appointment
    procedure_name: str
    facility_name: str
    offer: OfferView | None


def _hours(delta: dt.timedelta) -> int:
    return int(delta.total_seconds() // 3600)


def prep_lead(session: Session, protocol_id: uuid.UUID | None) -> dt.timedelta | None:
    """How long before the procedure the prep starts: the largest offset of the protocol.

    Step conditions are ignored on purpose, so the answer is never too optimistic.
    """
    if protocol_id is None:
        return None
    offset = session.scalar(
        select(PrepStep.offset_minutes)
        .where(PrepStep.protocol_id == protocol_id)
        .order_by(PrepStep.offset_minutes.desc())
        .limit(1)
    )
    return dt.timedelta(minutes=offset or 0)


class WaitlistService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- the list ------------------------------------------------------------------------

    def add(self, principal: StaffPrincipal, data: WaitlistEntryCreate) -> WaitlistRow:
        principal.require(Permission.APPOINTMENT_WRITE)
        org_id = principal.organization_id
        patient = patients_repo.get_patient(self._session, org_id, data.patient_id)
        if patient is None:
            raise ValidationFailedError("Unknown patient")
        procedure = org_repo.get_procedure_type(self._session, org_id, data.procedure_type_id)
        if procedure is None:
            raise ValidationFailedError("Unknown procedure type")
        entry = WaitlistEntry(
            organization_id=org_id,
            patient_id=patient.id,
            procedure_type_id=procedure.id,
            earliest_date=data.earliest_date,
            latest_date=data.latest_date,
            priority=data.priority,
            status=WaitlistStatus.ACTIVE,
        )
        self._session.add(entry)
        self._session.flush()
        self._audit(principal, AuditAction.CREATE, "waitlist_entry", entry.id, patient.id)
        return WaitlistRow(entry=entry, patient=patient, procedure_name=procedure.name)

    def entries(self, principal: StaffPrincipal, *, status: WaitlistStatus) -> list[WaitlistRow]:
        principal.require(Permission.PATIENT_READ)
        rows = self._session.execute(
            select(WaitlistEntry, Patient, ProcedureType)
            .join(Patient, Patient.id == WaitlistEntry.patient_id)
            .join(ProcedureType, ProcedureType.id == WaitlistEntry.procedure_type_id)
            .where(
                WaitlistEntry.organization_id == principal.organization_id,
                WaitlistEntry.status == status,
            )
            .order_by(WaitlistEntry.priority.desc(), WaitlistEntry.created_at)
        ).all()
        for entry, patient, _ in rows:
            self._audit(principal, AuditAction.LIST, "waitlist_entry", entry.id, patient.id)
        return [
            WaitlistRow(entry=entry, patient=patient, procedure_name=procedure.name)
            for entry, patient, procedure in rows
        ]

    def remove(self, principal: StaffPrincipal, entry_id: uuid.UUID) -> WaitlistRow:
        principal.require(Permission.APPOINTMENT_WRITE)
        entry = self._load_entry(principal, entry_id)
        if entry.status is not WaitlistStatus.ACTIVE:
            raise ConflictError(f"This entry is {entry.status.value.lower()} and cannot be removed")
        entry.status = WaitlistStatus.REMOVED
        self._session.flush()
        self._audit(
            principal,
            AuditAction.UPDATE,
            "waitlist_entry",
            entry.id,
            entry.patient_id,
            details={"status": WaitlistStatus.REMOVED.value},
        )
        return self._row(entry)

    # -- released slots and offers -------------------------------------------------------

    def released_slots(self, principal: StaffPrincipal, *, now: dt.datetime) -> list[ReleasedSlot]:
        principal.require(Permission.APPOINTMENT_READ)
        principal.require(Permission.PATIENT_READ)
        rows = self._session.execute(
            select(Appointment, ProcedureType.name, Facility.name)
            .join(ProcedureType, ProcedureType.id == Appointment.procedure_type_id)
            .join(Facility, Facility.id == Appointment.facility_id)
            .where(
                Appointment.organization_id == principal.organization_id,
                Appointment.status == AppointmentStatus.CANCELLED,
                Appointment.scheduled_at > now,
                Appointment.scheduled_at < now + SLOT_HORIZON,
                # A slot with an accepted offer has been filled, so it leaves the list.
                ~select(BackfillOffer.id)
                .where(
                    BackfillOffer.slot_appointment_id == Appointment.id,
                    BackfillOffer.status == OfferStatus.ACCEPTED,
                )
                .exists(),
            )
            .order_by(Appointment.scheduled_at)
        ).all()
        offers = self._open_offers([appointment.id for appointment, _, _ in rows])
        released: list[ReleasedSlot] = []
        for appointment, procedure_name, facility_name in rows:
            self._audit(
                principal, AuditAction.LIST, "appointment", appointment.id, appointment.patient_id
            )
            offer = offers.get(appointment.id)
            if offer is not None:
                self._audit(
                    principal, AuditAction.READ, "backfill_offer", offer.offer.id, offer.patient.id
                )
            released.append(
                ReleasedSlot(
                    appointment=appointment,
                    procedure_name=procedure_name,
                    facility_name=facility_name,
                    offer=offer,
                )
            )
        return released

    def find_backfill(
        self, principal: StaffPrincipal, slot_id: uuid.UUID, *, now: dt.datetime
    ) -> OfferView:
        principal.require(Permission.APPOINTMENT_WRITE)
        principal.require(Permission.PATIENT_READ)
        slot = self._lock_slot(principal, slot_id)
        self._require_released(slot, now)
        if self._is_filled(slot.id):
            raise ConflictError("This slot has already been filled")

        existing = self._open_offer(slot.id)
        if existing is not None:
            view = self._view(existing)
            self._audit(principal, AuditAction.READ, "backfill_offer", existing.id, view.patient.id)
            return view

        candidate = self._best_candidate(principal, slot, now=now)
        if candidate is None:
            raise NotFoundError("No waitlisted patient fits this slot")
        # Re-read the entry under a lock: it may have been removed since it was ranked.
        entry = self._lock_entry(candidate.entry.id)
        if entry.status is not WaitlistStatus.ACTIVE:
            raise ConflictError("The waitlist changed while offering this slot. Try again.")
        entry.status = WaitlistStatus.OFFERED
        offer = BackfillOffer(
            organization_id=principal.organization_id,
            slot_appointment_id=slot.id,
            waitlist_entry_id=entry.id,
            status=OfferStatus.OPEN,
            reasons=candidate.reasons,
        )
        self._session.add(offer)
        self._session.flush()
        self._audit(principal, AuditAction.CREATE, "backfill_offer", offer.id, entry.patient_id)
        return OfferView(offer=offer, patient=candidate.patient)

    def accept(
        self, principal: StaffPrincipal, offer_id: uuid.UUID, *, now: dt.datetime
    ) -> Appointment:
        """Book the candidate into the slot. The slot and the offer are locked for the decision."""
        principal.require(Permission.APPOINTMENT_WRITE)
        pending = self._load_offer(principal, offer_id)
        slot = self._lock_slot(principal, pending.slot_appointment_id)
        offer = self._load_offer(principal, offer_id, lock=True)
        if offer.status is not OfferStatus.OPEN:
            raise ConflictError(f"This offer is already {offer.status.value.lower()}")
        if slot.status is not AppointmentStatus.CANCELLED or slot.scheduled_at <= now:
            raise ConflictError("This slot is no longer open for backfill")
        entry = self._lock_entry(offer.waitlist_entry_id)

        booked = AppointmentService(self._session).create(
            principal,
            AppointmentCreate(
                patient_id=entry.patient_id,
                facility_id=slot.facility_id,
                procedure_type_id=slot.procedure_type_id,
                protocol_id=slot.protocol_id,
                clinician_id=slot.clinician_id,
                arrival_at=slot.arrival_at,
                scheduled_at=slot.scheduled_at,
                duration_minutes=slot.duration_minutes,
            ),
            now=now,
        )
        offer.status = OfferStatus.ACCEPTED
        offer.booked_appointment_id = booked.id
        entry.status = WaitlistStatus.BOOKED
        self._session.flush()
        self._audit(
            principal,
            AuditAction.UPDATE,
            "backfill_offer",
            offer.id,
            entry.patient_id,
            details={"status": OfferStatus.ACCEPTED.value},
        )
        return booked

    def decline(self, principal: StaffPrincipal, offer_id: uuid.UUID) -> OfferView:
        principal.require(Permission.APPOINTMENT_WRITE)
        offer = self._load_offer(principal, offer_id, lock=True)
        if offer.status is not OfferStatus.OPEN:
            raise ConflictError(f"This offer is already {offer.status.value.lower()}")
        offer.status = OfferStatus.DECLINED
        entry = self._lock_entry(offer.waitlist_entry_id)
        if entry.status is WaitlistStatus.OFFERED:
            entry.status = WaitlistStatus.ACTIVE
        self._session.flush()
        self._audit(
            principal,
            AuditAction.UPDATE,
            "backfill_offer",
            offer.id,
            entry.patient_id,
            details={"status": OfferStatus.DECLINED.value},
        )
        return self._view(offer)

    # -- helpers -------------------------------------------------------------------------

    def _best_candidate(
        self, principal: StaffPrincipal, slot: Appointment, *, now: dt.datetime
    ) -> Candidate | None:
        candidates = self._candidates(principal, slot, now=now)
        return candidates[0] if candidates else None

    def _candidates(
        self, principal: StaffPrincipal, slot: Appointment, *, now: dt.datetime
    ) -> list[Candidate]:
        """Waitlisted patients who fit the slot, best first, each with the reasons."""
        lead = prep_lead(self._session, slot.protocol_id)
        notice = slot.scheduled_at - now
        if lead is None or notice < lead:
            return []  # the prep could not start in time for anyone
        facility = self._session.get(Facility, slot.facility_id)
        if facility is None:  # pragma: no cover - the foreign key prevents this
            return []
        local_day = slot.scheduled_at.astimezone(ZoneInfo(facility.timezone)).date()

        declined = select(BackfillOffer.waitlist_entry_id).where(
            BackfillOffer.slot_appointment_id == slot.id,
            BackfillOffer.status == OfferStatus.DECLINED,
        )
        already_booked = (
            select(Appointment.id)
            .where(
                Appointment.patient_id == WaitlistEntry.patient_id,
                Appointment.procedure_type_id == slot.procedure_type_id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.scheduled_at > now,
            )
            .exists()
        )
        rows = self._session.execute(
            select(WaitlistEntry, Patient)
            .join(Patient, Patient.id == WaitlistEntry.patient_id)
            .where(
                WaitlistEntry.organization_id == principal.organization_id,
                WaitlistEntry.status == WaitlistStatus.ACTIVE,
                WaitlistEntry.procedure_type_id == slot.procedure_type_id,
                WaitlistEntry.earliest_date <= local_day,
                WaitlistEntry.latest_date >= local_day,
                WaitlistEntry.id.not_in(declined),
                ~already_booked,
            )
            .order_by(WaitlistEntry.priority.desc(), WaitlistEntry.created_at)
            .limit(MAX_CANDIDATES)
        ).all()

        candidates: list[Candidate] = []
        for entry, patient in rows:
            reasons = [
                f"Slot date is inside their window ({entry.earliest_date} to {entry.latest_date})",
                f"{_hours(notice)} hours of notice; prep starts {_hours(lead)} hours before",
            ]
            if entry.priority:
                reasons.insert(0, f"Priority {entry.priority}")
            self._audit(principal, AuditAction.LIST, "waitlist_entry", entry.id, patient.id)
            candidates.append(Candidate(entry=entry, patient=patient, reasons=reasons))
        return candidates

    def _open_offers(self, slot_ids: list[uuid.UUID]) -> dict[uuid.UUID, OfferView]:
        if not slot_ids:
            return {}
        rows = self._session.execute(
            select(BackfillOffer, Patient)
            .join(WaitlistEntry, WaitlistEntry.id == BackfillOffer.waitlist_entry_id)
            .join(Patient, Patient.id == WaitlistEntry.patient_id)
            .where(
                BackfillOffer.slot_appointment_id.in_(slot_ids),
                BackfillOffer.status == OfferStatus.OPEN,
            )
        ).all()
        return {offer.slot_appointment_id: OfferView(offer, patient) for offer, patient in rows}

    def _open_offer(self, slot_id: uuid.UUID) -> BackfillOffer | None:
        return self._session.scalar(
            select(BackfillOffer).where(
                BackfillOffer.slot_appointment_id == slot_id,
                BackfillOffer.status == OfferStatus.OPEN,
            )
        )

    def _is_filled(self, slot_id: uuid.UUID) -> bool:
        accepted = self._session.scalar(
            select(BackfillOffer.id).where(
                BackfillOffer.slot_appointment_id == slot_id,
                BackfillOffer.status == OfferStatus.ACCEPTED,
            )
        )
        return accepted is not None

    @staticmethod
    def _require_released(slot: Appointment, now: dt.datetime) -> None:
        if slot.status is not AppointmentStatus.CANCELLED or slot.scheduled_at <= now:
            raise ConflictError("Only a released slot that is still ahead can be backfilled")

    def _view(self, offer: BackfillOffer) -> OfferView:
        patient = self._session.scalar(
            select(Patient)
            .join(WaitlistEntry, WaitlistEntry.patient_id == Patient.id)
            .where(WaitlistEntry.id == offer.waitlist_entry_id)
        )
        if patient is None:  # pragma: no cover - the foreign key prevents this
            raise NotFoundError("Patient not found")
        return OfferView(offer=offer, patient=patient)

    def _row(self, entry: WaitlistEntry) -> WaitlistRow:
        patient = self._session.get(Patient, entry.patient_id)
        procedure = self._session.get(ProcedureType, entry.procedure_type_id)
        if patient is None or procedure is None:  # pragma: no cover - foreign keys prevent this
            raise NotFoundError("Waitlist entry not found")
        return WaitlistRow(entry=entry, patient=patient, procedure_name=procedure.name)

    def _lock_slot(self, principal: StaffPrincipal, slot_id: uuid.UUID) -> Appointment:
        slot = self._session.scalar(
            select(Appointment)
            .where(
                Appointment.id == slot_id,
                Appointment.organization_id == principal.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if slot is None:
            raise NotFoundError("Slot not found")
        return slot

    def _lock_entry(self, entry_id: uuid.UUID) -> WaitlistEntry:
        entry = self._session.scalar(
            select(WaitlistEntry)
            .where(WaitlistEntry.id == entry_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if entry is None:  # pragma: no cover - the foreign key prevents this
            raise NotFoundError("Waitlist entry not found")
        return entry

    def _load_entry(self, principal: StaffPrincipal, entry_id: uuid.UUID) -> WaitlistEntry:
        entry = self._session.scalar(
            select(WaitlistEntry).where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.organization_id == principal.organization_id,
            )
        )
        if entry is None:
            raise NotFoundError("Waitlist entry not found")
        return entry

    def _load_offer(
        self, principal: StaffPrincipal, offer_id: uuid.UUID, *, lock: bool = False
    ) -> BackfillOffer:
        query = select(BackfillOffer).where(
            BackfillOffer.id == offer_id,
            BackfillOffer.organization_id == principal.organization_id,
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        offer = self._session.scalar(query)
        if offer is None:
            raise NotFoundError("Offer not found")
        return offer

    def _audit(
        self,
        principal: StaffPrincipal,
        action: AuditAction,
        entity_type: str,
        entity_id: uuid.UUID,
        patient_id: uuid.UUID,
        *,
        details: dict[str, str] | None = None,
    ) -> None:
        record_audit(
            self._session,
            principal=principal,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=patient_id,
            purpose=PURPOSE,
            details=details,
        )
