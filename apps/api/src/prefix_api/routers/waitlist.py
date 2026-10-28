"""Waitlist backfill: the waitlist, released slots, and at most one open offer per slot."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.db.models import Patient
from prefix_api.domain.enums import WaitlistStatus
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.appointments import AppointmentOut
from prefix_api.schemas.waitlist import (
    OfferOut,
    ReleasedSlotOut,
    WaitlistEntryCreate,
    WaitlistEntryOut,
)
from prefix_api.services.waitlist import OfferView, ReleasedSlot, WaitlistRow, WaitlistService

router = APIRouter(
    prefix="/waitlist", tags=["waitlist"], dependencies=[Depends(patient_data_route)]
)

Reader = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_READ))]
Writer = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_WRITE))]


def _patient_name(patient: Patient) -> str:
    return f"{patient.first_name} {patient.last_name}"


def _entry_out(row: WaitlistRow) -> WaitlistEntryOut:
    return WaitlistEntryOut(
        id=row.entry.id,
        patient_id=row.patient.id,
        patient_name=_patient_name(row.patient),
        procedure_name=row.procedure_name,
        earliest_date=row.entry.earliest_date,
        latest_date=row.entry.latest_date,
        priority=row.entry.priority,
        status=row.entry.status,
    )


def _offer_out(view: OfferView) -> OfferOut:
    return OfferOut(
        id=view.offer.id,
        status=view.offer.status,
        waitlist_entry_id=view.offer.waitlist_entry_id,
        patient_id=view.patient.id,
        patient_name=_patient_name(view.patient),
        reasons=view.offer.reasons,
    )


def _slot_out(slot: ReleasedSlot) -> ReleasedSlotOut:
    return ReleasedSlotOut(
        appointment_id=slot.appointment.id,
        procedure_name=slot.procedure_name,
        facility_name=slot.facility_name,
        scheduled_at=slot.appointment.scheduled_at,
        open_offer=_offer_out(slot.offer) if slot.offer is not None else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def add_entry(data: WaitlistEntryCreate, principal: Writer, session: DbSession) -> WaitlistEntryOut:
    return _entry_out(WaitlistService(session).add(principal, data))


@router.get("")
def list_entries(
    principal: Reader,
    session: DbSession,
    entry_status: Annotated[WaitlistStatus, Query(alias="status")] = WaitlistStatus.ACTIVE,
) -> list[WaitlistEntryOut]:
    rows = WaitlistService(session).entries(principal, status=entry_status)
    return [_entry_out(row) for row in rows]


@router.post("/{entry_id}/remove")
def remove_entry(entry_id: uuid.UUID, principal: Writer, session: DbSession) -> WaitlistEntryOut:
    return _entry_out(WaitlistService(session).remove(principal, entry_id))


@router.get("/slots")
def released_slots(principal: Reader, session: DbSession, now: Now) -> list[ReleasedSlotOut]:
    slots = WaitlistService(session).released_slots(principal, now=now)
    return [_slot_out(slot) for slot in slots]


@router.post("/slots/{slot_id}/find-backfill")
def find_backfill(slot_id: uuid.UUID, principal: Writer, session: DbSession, now: Now) -> OfferOut:
    return _offer_out(WaitlistService(session).find_backfill(principal, slot_id, now=now))


@router.post("/offers/{offer_id}/accept")
def accept_offer(
    offer_id: uuid.UUID, principal: Writer, session: DbSession, now: Now
) -> AppointmentOut:
    booked = WaitlistService(session).accept(principal, offer_id, now=now)
    return AppointmentOut.model_validate(booked)


@router.post("/offers/{offer_id}/decline")
def decline_offer(offer_id: uuid.UUID, principal: Writer, session: DbSession) -> OfferOut:
    return _offer_out(WaitlistService(session).decline(principal, offer_id))
