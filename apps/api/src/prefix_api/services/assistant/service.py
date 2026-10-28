"""The AI Prep Assistant pipeline (safety rules a-d).

1. Deterministic red-flag rules. A match never reaches the LLM.
2. LLM triage: red flag (second layer) and whether the question is about prep at all.
3. Retrieval over only this patient's applicable steps (the appointment's timeline).
4. Grounded answer from those steps, with cited step references.
5. Checks: citations must be steps that were provided; numbers must come from them.

Anything other than a checked answer gets a fixed, human-written reply and goes to a
person (escalation plus task). That path never needs the LLM, so it works when the LLM is
down, refuses, or is not configured.
"""

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.db.models import (
    Appointment,
    AssistantExchange,
    Patient,
    PatientTimelineEvent,
    PrepStep,
    ProcedureType,
)
from prefix_api.domain.deidentify import deidentify
from prefix_api.domain.enums import (
    AppointmentStatus,
    AssistantOutcome,
    AuditAction,
    EscalationSeverity,
    EscalationSource,
    TaskType,
    TimelineEventStatus,
)
from prefix_api.domain.errors import AuthenticationError, ConflictError, NotFoundError
from prefix_api.domain.grounding import describe_offset, describe_time_to, ungrounded_numbers
from prefix_api.domain.principal import PatientPrincipal
from prefix_api.domain.red_flags import detect_red_flags
from prefix_api.services.assistant.llm import (
    PROMPT_VERSION,
    AssistantLLM,
    AssistantLLMError,
    StepContext,
)
from prefix_api.services.audit import record_audit
from prefix_api.services.check_ins import create_escalation, create_task
from prefix_api.services.embeddings import EmbeddingProvider
from prefix_api.services.step_translations import base_language, cached_translations

PURPOSE = "patient_assistant"
MAX_CONTEXT_STEPS = 12
URGENT_CALL_WITHIN = dt.timedelta(minutes=15)
_CLOSED = frozenset({AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED})

# Fixed replies, written by people. The LLM never writes what a patient sees when a
# question is escalated.
EMERGENCY_REPLY = {
    "en": (
        "What you describe may need urgent care. Please call 112 or go to the nearest "
        "emergency department now. We have also told your care team."
    ),
    "hi": (
        "आप जो बता रहे हैं, उसके लिए तुरंत इलाज की ज़रूरत हो सकती है। कृपया अभी 112 पर फ़ोन "
        "करें या नज़दीकी इमरजेंसी विभाग में जाएँ। हमने आपकी देखभाल टीम को भी बता दिया है।"
    ),
}
NURSE_REPLY = {
    "en": (
        "I can only answer questions about the steps in your prep plan, so I have sent your "
        "question to your care team. A nurse will contact you. If you feel unwell, call 112."
    ),
    "hi": (
        "मैं केवल आपकी तैयारी की योजना के चरणों के बारे में जवाब दे सकता हूँ, इसलिए मैंने आपका "
        "सवाल आपकी देखभाल टीम को भेज दिया है। एक नर्स आपसे संपर्क करेगी। तबीयत ठीक न लगे तो "
        "112 पर फ़ोन करें।"
    ),
}
_NURSE_REASON = {
    AssistantOutcome.OUT_OF_PROTOCOL: "Question is not about the prep plan",
    AssistantOutcome.NOT_COVERED: "The approved steps do not answer the question",
    AssistantOutcome.CHECK_FAILED: "The draft answer failed the safety checks",
    AssistantOutcome.UNAVAILABLE: "The assistant was unavailable",
}


@dataclass(frozen=True, slots=True)
class Citation:
    event_id: uuid.UUID
    title: str


@dataclass(frozen=True, slots=True)
class AssistantReply:
    exchange: AssistantExchange
    citations: list[Citation]

    @property
    def escalated(self) -> bool:
        return self.exchange.outcome is not AssistantOutcome.ANSWERED


@dataclass(frozen=True, slots=True)
class _Step:
    ref: str
    event: PatientTimelineEvent
    step: PrepStep

    def context(self) -> StepContext:
        return StepContext(
            ref=self.ref,
            title=self.step.title,
            instruction=self.step.instruction_text,
            timing=describe_offset(self.step.offset_minutes),
        )


@dataclass(frozen=True, slots=True)
class _Decision:
    outcome: AssistantOutcome
    reply: str
    reason: str | None = None
    cited: tuple[_Step, ...] = ()


def _reply_language(language: str) -> str:
    return "hi" if base_language(language) == "hi" else "en"


class AssistantService:
    def __init__(
        self, session: Session, llm: AssistantLLM | None, embedder: EmbeddingProvider
    ) -> None:
        self._session = session
        self._llm = llm
        self._embedder = embedder

    def ask(
        self,
        principal: PatientPrincipal,
        appointment_id: uuid.UUID,
        question: str,
        *,
        language: str,
        now: dt.datetime,
    ) -> AssistantReply:
        appointment = self._appointment(principal, appointment_id, for_update=True)
        patient = self._patient(principal)
        names = [patient.first_name, patient.last_name]
        lang = _reply_language(language)

        red_flags = detect_red_flags(question)
        decision = (
            _Decision(
                AssistantOutcome.RED_FLAG,
                EMERGENCY_REPLY[lang],
                reason="Red-flag words: " + ", ".join(sorted(red_flags)),
            )
            if red_flags
            else self._ask_llm(appointment, question, names, language, now)
        )

        escalation_id = None
        if decision.outcome is not AssistantOutcome.ANSWERED:
            escalation_id = self._escalate(patient, appointment, question, decision, now)
        exchange = AssistantExchange(
            organization_id=principal.organization_id,
            patient_id=patient.id,
            appointment_id=appointment.id,
            question=question,
            reply=decision.reply,
            # Fixed replies exist in English and Hindi; answers come in the asked language.
            language=base_language(language)
            if decision.outcome is AssistantOutcome.ANSWERED
            else lang,
            outcome=decision.outcome,
            red_flags=sorted(red_flags),
            reason=decision.reason,
            cited_event_ids=[str(step.event.id) for step in decision.cited],
            redactions=deidentify(question, names=names).counts,
            escalation_id=escalation_id,
            model=self._llm.model if self._llm and not red_flags else None,
            prompt_version=PROMPT_VERSION,
        )
        self._session.add(exchange)
        self._session.flush()
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.CREATE,
            entity_type="assistant_exchange",
            entity_id=exchange.id,
            patient_id=patient.id,
            purpose=PURPOSE,
            details={"status": decision.outcome.value},
        )
        return AssistantReply(exchange, self._citations(decision.cited, language))

    def history(
        self, principal: PatientPrincipal, appointment_id: uuid.UUID, *, language: str
    ) -> list[AssistantReply]:
        appointment = self._appointment(principal, appointment_id, allow_closed=True)
        exchanges = list(
            self._session.scalars(
                select(AssistantExchange)
                .where(
                    AssistantExchange.appointment_id == appointment.id,
                    AssistantExchange.patient_id == principal.patient_id,
                )
                .order_by(AssistantExchange.created_at)
            )
        )
        replies = []
        for exchange in exchanges:
            record_audit(
                self._session,
                principal=principal,
                action=AuditAction.READ,
                entity_type="assistant_exchange",
                entity_id=exchange.id,
                patient_id=principal.patient_id,
                purpose=PURPOSE,
            )
            cited = self._cited_steps(exchange.cited_event_ids)
            replies.append(AssistantReply(exchange, self._citations(cited, language)))
        return replies

    # -- pipeline ------------------------------------------------------------------------

    def _ask_llm(
        self,
        appointment: Appointment,
        question: str,
        names: list[str],
        language: str,
        now: dt.datetime,
    ) -> _Decision:
        lang = _reply_language(language)
        nurse = NURSE_REPLY[lang]
        if self._llm is None:
            return _Decision(AssistantOutcome.UNAVAILABLE, nurse, "No LLM is configured")
        try:
            triage = self._llm.triage(question, names=names)
        except AssistantLLMError as exc:
            return _Decision(AssistantOutcome.UNAVAILABLE, nurse, str(exc))
        if triage.red_flag:
            return _Decision(
                AssistantOutcome.RED_FLAG, EMERGENCY_REPLY[lang], f"Triage: {triage.reason}"
            )
        if not triage.about_prep:
            return _Decision(AssistantOutcome.OUT_OF_PROTOCOL, nurse, f"Triage: {triage.reason}")

        steps = self._retrieve(appointment, question)
        if not steps:
            return _Decision(AssistantOutcome.NOT_COVERED, nurse, "No applicable steps")
        procedure = self._session.get_one(ProcedureType, appointment.procedure_type_id)
        time_to = describe_time_to(appointment.scheduled_at, now)
        try:
            answer = self._llm.answer(
                question,
                names=names,
                steps=[s.context() for s in steps],
                procedure=procedure.name,
                time_to_procedure=time_to,
                language=language,
            )
        except AssistantLLMError as exc:
            return _Decision(AssistantOutcome.UNAVAILABLE, nurse, str(exc))
        if not answer.covered or not answer.text:
            return _Decision(
                AssistantOutcome.NOT_COVERED, nurse, _NURSE_REASON[AssistantOutcome.NOT_COVERED]
            )

        by_ref = {s.ref: s for s in steps}
        unknown = [ref for ref in answer.cited_refs if ref not in by_ref]
        if not answer.cited_refs or unknown:
            return _Decision(AssistantOutcome.CHECK_FAILED, nurse, "Answer cited no provided step")
        cited = tuple(dict.fromkeys(by_ref[ref] for ref in answer.cited_refs))
        sources = [time_to] + [
            f"{s.context().timing} {s.step.title} {s.step.instruction_text}" for s in cited
        ]
        stray = ungrounded_numbers(answer.text, sources)
        if stray:
            return _Decision(
                AssistantOutcome.CHECK_FAILED,
                nurse,
                "Answer used numbers not in the cited steps: " + ", ".join(sorted(stray)),
            )
        return _Decision(AssistantOutcome.ANSWERED, answer.text, cited=cited)

    def _retrieve(self, appointment: Appointment, question: str) -> list[_Step]:
        """The appointment's own active steps, most relevant first, then in time order.

        Protocols are short, so usually every step fits; ranking matters only for long
        ones. The question is embedded locally and never leaves the server.
        """
        [vector] = self._embedder.embed([question])
        rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .where(
                PatientTimelineEvent.appointment_id == appointment.id,
                PatientTimelineEvent.status != TimelineEventStatus.CANCELLED,
            )
            .order_by(PrepStep.embedding.cosine_distance(vector).nulls_last())
            .limit(MAX_CONTEXT_STEPS)
        ).all()
        chronological = sorted(rows, key=lambda row: (row[0].due_at, row[1].sort_order))
        return [
            _Step(ref=f"S{index}", event=event, step=step)
            for index, (event, step) in enumerate(chronological, start=1)
        ]

    def _escalate(
        self,
        patient: Patient,
        appointment: Appointment,
        question: str,
        decision: _Decision,
        now: dt.datetime,
    ) -> uuid.UUID:
        principal = PatientPrincipal(patient_id=patient.id, organization_id=patient.organization_id)
        red_flag = decision.outcome is AssistantOutcome.RED_FLAG
        reason = decision.reason or _NURSE_REASON.get(decision.outcome, "")
        escalation = create_escalation(
            self._session,
            principal=principal,
            patient=patient,
            appointment=appointment,
            severity=EscalationSeverity.URGENT if red_flag else EscalationSeverity.NORMAL,
            source=EscalationSource.RED_FLAG if red_flag else EscalationSource.OUT_OF_PROTOCOL,
            # Encrypted column: the patient's own words go here, for the nurse.
            summary=f"{reason}\nPatient asked: {question}",
            purpose=PURPOSE,
        )
        create_task(
            self._session,
            patient=patient,
            appointment_id=appointment.id,
            task_type=TaskType.CALL_PATIENT if red_flag else TaskType.NURSE_REVIEW,
            title="Urgent: possible red flag in assistant question"
            if red_flag
            else "Answer a patient's question from the assistant",
            now=now,
            escalation_id=escalation.id,
            due_in=URGENT_CALL_WITHIN if red_flag else dt.timedelta(hours=2),
        )
        if red_flag and appointment.status is not AppointmentStatus.CANCELLED:
            appointment.status = AppointmentStatus.AT_RISK
        return escalation.id

    # -- helpers -------------------------------------------------------------------------

    def _citations(self, cited: tuple[_Step, ...] | list[_Step], language: str) -> list[Citation]:
        translations = cached_translations(self._session, (s.step.id for s in cited), language)
        return [
            Citation(
                event_id=s.event.id,
                title=translations[s.step.id].title if s.step.id in translations else s.step.title,
            )
            for s in cited
        ]

    def _cited_steps(self, event_ids: list[str]) -> list[_Step]:
        if not event_ids:
            return []
        rows = self._session.execute(
            select(PatientTimelineEvent, PrepStep)
            .join(PrepStep, PrepStep.id == PatientTimelineEvent.step_id)
            .where(PatientTimelineEvent.id.in_([uuid.UUID(e) for e in event_ids]))
        ).all()
        found = {event.id: (event, step) for event, step in rows}
        return [
            _Step(ref="", event=found[uuid.UUID(e)][0], step=found[uuid.UUID(e)][1])
            for e in event_ids
            if uuid.UUID(e) in found
        ]

    def _patient(self, principal: PatientPrincipal) -> Patient:
        patient = self._session.get(Patient, principal.patient_id)
        if patient is None or patient.organization_id != principal.organization_id:
            raise AuthenticationError("Patient session is no longer valid")
        # The patient's names are read only to remove them from the question.
        record_audit(
            self._session,
            principal=principal,
            action=AuditAction.READ,
            entity_type="patient",
            entity_id=patient.id,
            patient_id=patient.id,
            purpose="assistant_deidentification",
        )
        return patient

    def _appointment(
        self,
        principal: PatientPrincipal,
        appointment_id: uuid.UUID,
        *,
        for_update: bool = False,
        allow_closed: bool = False,
    ) -> Appointment:
        query = select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.organization_id == principal.organization_id,
            Appointment.patient_id == principal.patient_id,
        )
        if for_update:
            query = query.with_for_update()
        appointment = self._session.scalar(query)
        if appointment is None:
            raise NotFoundError("Appointment not found")
        if appointment.status in _CLOSED and not allow_closed:
            raise ConflictError(f"This appointment is {appointment.status.value.lower()}")
        return appointment
