"""Translations of approved prep steps, cached in the database (safety rule a).

Only clinician-approved step text is ever translated, and a translation that does not keep
the title/instruction shape is discarded so the approved original is used instead. Reads
for the portal come from the cache only; the LLM is called by background work.
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from prefix_api.core.logging import get_logger
from prefix_api.db.models import (
    Appointment,
    Patient,
    PatientTimelineEvent,
    PrepStep,
    PrepStepTranslation,
)
from prefix_api.domain.enums import AppointmentStatus, TimelineEventStatus
from prefix_api.services.translation import LANGUAGE_NAMES, SOURCE_LANGUAGE, Translator

logger = get_logger(__name__)

WARM_HORIZON = dt.timedelta(days=14)


@dataclass(frozen=True, slots=True)
class StepText:
    title: str
    instruction: str


def base_language(language: str) -> str:
    return language.split("-")[0].lower()


def needs_translation(language: str) -> bool:
    code = base_language(language)
    return code != SOURCE_LANGUAGE and code in LANGUAGE_NAMES


def _source(step: PrepStep) -> str:
    return f"{step.title}\n{step.instruction_text}"


def _split(translated: str) -> StepText | None:
    title, _, instruction = translated.partition("\n")
    title, instruction = title.strip(), instruction.strip()
    if not title or not instruction or len(title) > 300:
        return None
    return StepText(title=title, instruction=instruction)


def cached_translations(
    session: Session, step_ids: Iterable[uuid.UUID], language: str
) -> dict[uuid.UUID, StepText]:
    """Translations already in the cache. Never calls the LLM."""
    ids = list(step_ids)
    if not ids or not needs_translation(language):
        return {}
    rows = session.execute(
        select(
            PrepStepTranslation.step_id,
            PrepStepTranslation.title,
            PrepStepTranslation.instruction_text,
        ).where(
            PrepStepTranslation.step_id.in_(ids),
            PrepStepTranslation.language == base_language(language),
        )
    ).all()
    return {step_id: StepText(title, instruction) for step_id, title, instruction in rows}


def translate_step(
    session: Session, translator: Translator, step: PrepStep, language: str
) -> StepText | None:
    """The step in ``language``: from the cache, or translated now and cached.

    Returns None when the approved original must be used (English, unsupported language,
    or any translation problem).
    """
    if not needs_translation(language):
        return None
    code = base_language(language)
    cached = cached_translations(session, [step.id], code).get(step.id)
    if cached is not None:
        return cached
    result = translator.translate(_source(step), code)
    text = _split(result.text) if result.translated else None
    if text is None:
        return None
    session.execute(
        insert(PrepStepTranslation)
        .values(
            id=uuid.uuid7(),
            organization_id=step.organization_id,
            step_id=step.id,
            language=code,
            title=text.title,
            instruction_text=text.instruction,
            translated_by=translator.name,
        )
        .on_conflict_do_nothing(index_elements=["step_id", "language"])
    )
    return text


def missing_translations(
    session: Session, *, now: dt.datetime, limit: int
) -> list[tuple[uuid.UUID, str]]:
    """(step, language) pairs that upcoming patients need and the cache lacks.

    Returns only step ids and language codes, never patient identifiers.
    """
    language = func.lower(func.split_part(Patient.preferred_language, "-", 1))
    supported = [code for code in LANGUAGE_NAMES if code != SOURCE_LANGUAGE]
    rows = session.execute(
        select(PatientTimelineEvent.step_id, language)
        .join(Appointment, Appointment.id == PatientTimelineEvent.appointment_id)
        .join(Patient, Patient.id == PatientTimelineEvent.patient_id)
        .outerjoin(
            PrepStepTranslation,
            and_(
                PrepStepTranslation.step_id == PatientTimelineEvent.step_id,
                PrepStepTranslation.language == language,
            ),
        )
        .where(
            PrepStepTranslation.id.is_(None),
            language.in_(supported),
            PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]),
            Appointment.scheduled_at.between(now, now + WARM_HORIZON),
        )
        .distinct()
        .limit(limit)
    ).all()
    return [(step_id, code) for step_id, code in rows]


def warm_step_translations(
    session_factory: sessionmaker[Session],
    translator: Translator,
    *,
    now: dt.datetime,
    limit: int = 50,
) -> dict[str, int]:
    """Pre-translate steps for the next two weeks' non-English patients."""
    with session_factory() as session:
        pending = missing_translations(session, now=now, limit=limit)
    done = 0
    for step_id, language in pending:
        with session_factory() as session:
            step = session.get(PrepStep, step_id)
            if step is not None and translate_step(session, translator, step, language):
                done += 1
            session.commit()
    outcome = {"missing": len(pending), "translated": done}
    if pending:
        logger.info("translations.warmed", **outcome)
    return outcome
