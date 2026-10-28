"""CSV imports: check a file first (dry run), then commit it if every row is valid."""

from typing import Annotated

from fastapi import APIRouter, Depends

from prefix_api.api.deps import DbSession, Now, patient_data_route, require
from prefix_api.domain.permissions import Permission
from prefix_api.domain.principal import StaffPrincipal
from prefix_api.schemas.imports import ImportReportOut, ImportRequest, RowErrorOut
from prefix_api.services.imports import ImportReport, ImportService

router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(patient_data_route)])

StaffPatientWriter = Annotated[StaffPrincipal, Depends(require(Permission.PATIENT_WRITE))]
StaffAppointmentWriter = Annotated[StaffPrincipal, Depends(require(Permission.APPOINTMENT_WRITE))]


def _report_out(report: ImportReport) -> ImportReportOut:
    return ImportReportOut(
        kind=report.kind,
        rows=report.rows,
        valid_rows=report.valid_rows,
        imported=report.imported,
        committed=report.committed,
        ignored_columns=report.ignored_columns,
        errors=[
            RowErrorOut(line=error.line, column=error.column, message=error.message)
            for error in report.errors
        ],
    )


@router.post("/patients")
def import_patients(
    data: ImportRequest,
    principal: StaffPatientWriter,
    session: DbSession,
    now: Now,
) -> ImportReportOut:
    return _report_out(ImportService(session).patients(principal, data, now=now))


@router.post("/appointments")
def import_appointments(
    data: ImportRequest,
    principal: StaffAppointmentWriter,
    session: DbSession,
    now: Now,
) -> ImportReportOut:
    return _report_out(ImportService(session).appointments(principal, data, now=now))
