"""Endpoints used by patients themselves (authenticated with a magic-link session)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from prefix_api.api.deps import (
    AssistantLLMDep,
    CurrentPatient,
    DbSession,
    Now,
    SettingsDep,
    patient_data_route,
)
from prefix_api.core.rate_limit import RateLimiter
from prefix_api.schemas.assistant import AssistantQuestionIn, AssistantReplyOut
from prefix_api.schemas.notifications import (
    NotificationFeedOut,
    NotificationReadIn,
    NotificationReadOut,
)
from prefix_api.schemas.patients import (
    LanguageCode,
    MagicLinkRedeem,
    PatientSelfOut,
    PatientSessionOut,
)
from prefix_api.schemas.portal import PortalAppointment, ProblemReport, RescheduleRequest
from prefix_api.services.assistant.service import AssistantService
from prefix_api.services.embeddings import get_embedding_provider
from prefix_api.services.notifications import NotificationService
from prefix_api.services.patient_access import PatientAccessService
from prefix_api.services.portal import PortalService

router = APIRouter(prefix="/patient", tags=["patient portal"])
patient_data = [Depends(patient_data_route)]


@router.post("/session")
def redeem_magic_link(
    body: MagicLinkRedeem, session: DbSession, settings: SettingsDep, now: Now
) -> PatientSessionOut:
    """Exchange a single-use magic-link token (sent in the body, never the URL)."""
    result = PatientAccessService(session, settings).redeem_magic_link(body.token, now=now)
    return PatientSessionOut(access_token=result.access_token, expires_at=result.expires_at)


@router.get("/me", dependencies=patient_data)
def me(principal: CurrentPatient, session: DbSession, settings: SettingsDep) -> PatientSelfOut:
    view = PatientAccessService(session, settings).get_self(principal)
    return PatientSelfOut.model_validate(view)


@router.get("/notifications", dependencies=patient_data)
def my_notifications(
    principal: CurrentPatient, session: DbSession, now: Now, lang: LanguageCode = "en"
) -> NotificationFeedOut:
    """The patient's updates, newest first, with how many are unread."""
    return NotificationService(session).feed(principal, now=now, language=lang)


@router.post("/notifications/read", dependencies=patient_data)
def mark_notifications_read(
    body: NotificationReadIn, principal: CurrentPatient, session: DbSession, now: Now
) -> NotificationReadOut:
    unread = NotificationService(session).mark_read(principal, body.keys, now=now)
    return NotificationReadOut(unread_count=unread)


@router.post("/notifications/read-all", dependencies=patient_data)
def mark_all_notifications_read(
    principal: CurrentPatient, session: DbSession, now: Now
) -> NotificationReadOut:
    unread = NotificationService(session).mark_all_read(principal, now=now)
    return NotificationReadOut(unread_count=unread)


@router.get("/appointments", dependencies=patient_data)
def my_appointments(
    principal: CurrentPatient, session: DbSession, now: Now, lang: LanguageCode = "en"
) -> list[PortalAppointment]:
    return PortalService(session).list_appointments(principal, now=now, language=lang)


@router.post(
    "/steps/{event_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def confirm_step(
    event_id: uuid.UUID, principal: CurrentPatient, session: DbSession, now: Now
) -> None:
    PortalService(session).confirm_step(principal, event_id, now=now)


@router.post(
    "/steps/{event_id}/problem",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def report_problem(
    event_id: uuid.UUID,
    body: ProblemReport,
    principal: CurrentPatient,
    session: DbSession,
    now: Now,
) -> None:
    PortalService(session).report_problem(principal, event_id, note=body.note, now=now)


@router.post(
    "/appointments/{appointment_id}/reschedule-request",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=patient_data,
)
def request_reschedule(
    appointment_id: uuid.UUID,
    body: RescheduleRequest,
    principal: CurrentPatient,
    session: DbSession,
    now: Now,
) -> None:
    PortalService(session).request_reschedule(principal, appointment_id, note=body.note, now=now)


@router.get(
    "/appointments/{appointment_id}/calendar.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
    dependencies=patient_data,
)
def calendar(
    appointment_id: uuid.UUID,
    principal: CurrentPatient,
    session: DbSession,
    settings: SettingsDep,
    now: Now,
) -> Response:
    portal_url = f"{str(settings.web_base_url).rstrip('/')}/p/home"
    ics = PortalService(session).calendar(principal, appointment_id, portal_url=portal_url, now=now)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="procedure.ics"',
            "Cache-Control": "no-store",
        },
    )


def _assistant(session: DbSession, settings: SettingsDep, llm: AssistantLLMDep) -> AssistantService:
    return AssistantService(session, llm, get_embedding_provider(settings.embedding_provider))


AssistantDep = Annotated[AssistantService, Depends(_assistant)]


@router.post("/assistant/questions", dependencies=patient_data)
def ask_assistant(
    body: AssistantQuestionIn,
    principal: CurrentPatient,
    assistant: AssistantDep,
    now: Now,
    request: Request,
) -> AssistantReplyOut:
    """Answer from the patient's own approved steps, or hand the question to a person."""
    limiter: RateLimiter = request.app.state.rate_limiter
    # Each question can call the LLM, so cap how often one patient may ask.
    limiter.check(f"assistant:{principal.patient_id}", limit=20, window_seconds=3600)
    reply = assistant.ask(
        principal, body.appointment_id, body.question, language=body.language, now=now
    )
    return AssistantReplyOut.build(reply)


@router.get("/assistant/questions", dependencies=patient_data)
def assistant_history(
    appointment_id: uuid.UUID,
    principal: CurrentPatient,
    assistant: AssistantDep,
    lang: LanguageCode = "en",
) -> list[AssistantReplyOut]:
    return [
        AssistantReplyOut.build(reply)
        for reply in assistant.history(principal, appointment_id, language=lang)
    ]
