"""CSV imports of patients and appointments.

Each row goes through the same services as a typed entry, so consent, audit, protocol and
timeline rules all apply. Every row runs in its own savepoint: a bad row is reported and
undone without stopping the others. A dry run runs the whole import and then rolls it back,
so its report is exactly what a real import would do. A real import writes only when every
row is valid, so a file is never half imported.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prefix_api.core.crypto import get_blind_indexer, normalize_identifier, normalize_phone
from prefix_api.db.models import Patient
from prefix_api.domain.csv_import import CsvFormatError, CsvRow, parse_flag, read_table
from prefix_api.domain.enums import AuditAction
from prefix_api.domain.errors import DomainError, ValidationFailedError
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.repositories import organizations as org_repo
from prefix_api.repositories import patients as patients_repo
from prefix_api.schemas.appointments import AppointmentCreate
from prefix_api.schemas.imports import ImportRequest
from prefix_api.schemas.patients import ConditionFlags, PatientCreate
from prefix_api.services.appointments import AppointmentService
from prefix_api.services.audit import record_audit
from prefix_api.services.patients import PatientService

PURPOSE = "bulk_import"

PATIENT_FIELDS = frozenset(PatientCreate.model_fields)
PATIENT_REQUIRED = frozenset({"first_name", "last_name", "date_of_birth"})
FLAG_FIELDS = frozenset({"consent_to_message", *ConditionFlags.model_fields})

APPOINTMENT_FIELDS = frozenset(
    {
        "patient_mrn",
        "patient_phone",
        "facility",
        "procedure_code",
        "scheduled_at",
        "arrival_at",
        "duration_minutes",
    }
)
APPOINTMENT_REQUIRED = frozenset({"facility", "procedure_code", "scheduled_at"})


@dataclass(frozen=True, slots=True)
class RowError:
    line: int
    message: str
    column: str | None = None


@dataclass(frozen=True, slots=True)
class ImportReport:
    kind: str
    rows: int
    valid_rows: int
    imported: int
    committed: bool
    ignored_columns: list[str]
    errors: list[RowError]


class RowRejectedError(Exception):
    """One row cannot be imported. Carries every reason, so the coordinator fixes them at once."""

    def __init__(self, errors: list[RowError]) -> None:
        super().__init__("row rejected")
        self.errors = errors


class _RollbackError(Exception):
    """Rolls back the whole import savepoint without reporting an error."""


def _describe(error: ErrorDetails) -> str:
    return "is required" if error["type"] == "missing" else "is not valid"


def _validated[Model: BaseModel](model: type[Model], values: dict[str, Any], line: int) -> Model:
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        raise RowRejectedError(
            [
                RowError(
                    line=line,
                    column=str(error["loc"][0]) if error["loc"] else None,
                    message=_describe(error),
                )
                for error in exc.errors()
            ]
        ) from exc


def _flag(text: str, line: int, column: str) -> bool:
    value = parse_flag(text)
    if value is None:
        raise RowRejectedError([RowError(line=line, column=column, message="is not yes or no")])
    return value


class ImportService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def patients(
        self, principal: StaffPrincipal, data: ImportRequest, *, now: dt.datetime
    ) -> ImportReport:
        principal.require(Permission.PATIENT_WRITE)
        return self._run(
            principal,
            kind="patients",
            fields=PATIENT_FIELDS,
            required=PATIENT_REQUIRED,
            data=data,
            create=lambda row: self._create_patient(principal, row, now=now),
        )

    def appointments(
        self, principal: StaffPrincipal, data: ImportRequest, *, now: dt.datetime
    ) -> ImportReport:
        principal.require(Permission.APPOINTMENT_WRITE)
        return self._run(
            principal,
            kind="appointments",
            fields=APPOINTMENT_FIELDS,
            required=APPOINTMENT_REQUIRED,
            data=data,
            create=lambda row: self._create_appointment(principal, row, now=now),
        )

    # -- the loop --------------------------------------------------------------------------

    def _run(
        self,
        principal: StaffPrincipal,
        *,
        kind: str,
        fields: frozenset[str],
        required: frozenset[str],
        data: ImportRequest,
        create: Callable[[CsvRow], None],
    ) -> ImportReport:
        try:
            table = read_table(data.csv, fields=fields, required=required, mapping=data.mapping)
        except CsvFormatError as exc:
            raise ValidationFailedError(str(exc)) from exc

        errors: list[RowError] = []
        created = 0
        try:
            with self._session.begin_nested():
                for row in table.rows:
                    try:
                        with self._session.begin_nested():
                            create(row)
                    except RowRejectedError as problem:
                        errors.extend(problem.errors)
                    except DomainError as exc:
                        errors.append(RowError(line=row.line, message=exc.message))
                    except IntegrityError:
                        errors.append(
                            RowError(line=row.line, message="conflicts with existing data")
                        )
                    else:
                        created += 1
                if data.dry_run or errors:
                    raise _RollbackError
                record_audit(
                    self._session,
                    principal=principal,
                    action=AuditAction.CREATE,
                    entity_type="import",
                    purpose=PURPOSE,
                    details={"count": created},
                )
        except _RollbackError:
            pass

        committed = not data.dry_run and not errors
        return ImportReport(
            kind=kind,
            rows=len(table.rows),
            valid_rows=created,
            imported=created if committed else 0,
            committed=committed,
            ignored_columns=table.ignored_columns,
            errors=sorted(errors, key=lambda error: error.line),
        )

    # -- patients --------------------------------------------------------------------------

    def _create_patient(self, principal: StaffPrincipal, row: CsvRow, *, now: dt.datetime) -> None:
        values: dict[str, Any] = dict(row.values)
        for column in FLAG_FIELDS & values.keys():
            values[column] = _flag(values[column], row.line, column)
        if "preferred_channel" in values:
            values["preferred_channel"] = values["preferred_channel"].upper()
        data = _validated(PatientCreate, values, row.line)
        PatientService(self._session).create(principal, data, now=now)

    # -- appointments ----------------------------------------------------------------------

    def _create_appointment(
        self, principal: StaffPrincipal, row: CsvRow, *, now: dt.datetime
    ) -> None:
        values = row.values
        if "patient_mrn" not in values and "patient_phone" not in values:
            raise RowRejectedError(
                [RowError(line=row.line, message="needs patient_mrn or patient_phone")]
            )
        missing = sorted(APPOINTMENT_REQUIRED - values.keys())
        if missing:
            raise RowRejectedError(
                [
                    RowError(line=row.line, column=column, message="is required")
                    for column in missing
                ]
            )

        patient = self._find_patient(principal, values)
        facility = org_repo.get_facility_by_name(
            self._session, principal.organization_id, values["facility"]
        )
        if facility is None:
            raise DomainError("No facility has this name")
        procedure = org_repo.get_procedure_type_by_code(
            self._session, principal.organization_id, values["procedure_code"].upper()
        )
        if procedure is None:
            raise DomainError("No procedure has this code")

        data = _validated(
            AppointmentCreate,
            {
                "patient_id": patient.id,
                "facility_id": facility.id,
                "procedure_type_id": procedure.id,
                "scheduled_at": values["scheduled_at"],
                "arrival_at": values.get("arrival_at"),
                "duration_minutes": values.get("duration_minutes"),
            },
            row.line,
        )
        AppointmentService(self._session).create(principal, data, now=now)

    def _find_patient(self, principal: StaffPrincipal, values: dict[str, str]) -> Patient:
        """Exactly one patient must match. Reading them to match is audited like any read."""
        indexer = get_blind_indexer()
        if "patient_mrn" in values:
            matches = patients_repo.search_patients(
                self._session,
                principal.organization_id,
                mrn_bidx=indexer.index(normalize_identifier(values["patient_mrn"]), "mrn"),
                limit=2,
            )
        else:
            matches = patients_repo.search_patients(
                self._session,
                principal.organization_id,
                phone_bidx=indexer.index(normalize_phone(values["patient_phone"]), "phone"),
                limit=2,
            )
        if not matches:
            raise DomainError("No patient matches this MRN or phone")
        if len(matches) > 1:
            raise DomainError("More than one patient matches this MRN or phone")
        patient = matches[0]
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="patient",
            entity_id=patient.id,
            patient_id=patient.id,
            purpose=PURPOSE,
        )
        return patient
