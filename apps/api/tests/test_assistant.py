"""The AI Prep Assistant pipeline: grounded answers, or a person (safety rules a, b, d)."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from api_testkit import Builder, patient_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient
from messaging_testkit import Booked, book
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import AssistantExchange, AuditLog, Escalation, Task
from prefix_api.domain.enums import (
    ActorType,
    AppointmentStatus,
    AssistantOutcome,
    AuditAction,
    EscalationSeverity,
    EscalationSource,
    TaskType,
)
from prefix_api.services.assistant.llm import Answer, AssistantLLMError, StepContext, Triage
from prefix_api.services.assistant.service import EMERGENCY_REPLY, NURSE_REPLY

ABOUT_PREP = Triage(red_flag=False, about_prep=True, reason="diet question")
GOOD_ANSWER = Answer(
    covered=True, text="Eat low-fibre food from 3 days before your procedure.", cited_refs=("S1",)
)


@dataclass
class FakeLLM:
    triage_result: Triage | Exception = ABOUT_PREP
    answer_result: Answer | Exception = GOOD_ANSWER
    model: str = "fake-model"
    triaged: list[str] = field(default_factory=list)
    answered: list[dict[str, Any]] = field(default_factory=list)

    def triage(self, question: str, *, names: Sequence[str]) -> Triage:
        self.triaged.append(question)
        if isinstance(self.triage_result, Exception):
            raise self.triage_result
        return self.triage_result

    def answer(
        self,
        question: str,
        *,
        names: Sequence[str],
        steps: Sequence[StepContext],
        procedure: str,
        time_to_procedure: str,
        language: str,
    ) -> Answer:
        self.answered.append(
            {"steps": list(steps), "procedure": procedure, "time": time_to_procedure}
        )
        if isinstance(self.answer_result, Exception):
            raise self.answer_result
        return self.answer_result


@pytest.fixture
def llm(app: FastAPI) -> FakeLLM:
    fake = FakeLLM()
    app.state.assistant_llm = fake
    return fake


@pytest.fixture
def booked(build: Builder, db_session: Session) -> Booked:
    return book(build, db_session)


def ask(
    client: TestClient,
    settings: Settings,
    booked: Booked,
    question: str,
    language: str = "en",
) -> dict[str, Any]:
    response = client.post(
        "/patient/assistant/questions",
        headers=patient_headers(settings, booked.patient),
        json={
            "appointment_id": str(booked.appointment.id),
            "question": question,
            "language": language,
        },
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def escalation_for(db_session: Session, booked: Booked) -> Escalation:
    escalation = db_session.scalar(
        select(Escalation).where(Escalation.patient_id == booked.patient.id)
    )
    assert escalation is not None
    return escalation


def test_a_covered_question_gets_a_grounded_answer_with_citations(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM, db_session: Session
) -> None:
    result = ask(client, settings, booked, "When do I start the low-fibre diet?")

    assert result["outcome"] == "ANSWERED"
    assert result["escalated"] is False
    assert result["reply"] == GOOD_ANSWER.text
    assert result["citations"] == [
        {"event_id": str(booked.events["Low-fibre diet"].id), "title": "Low-fibre diet"}
    ]
    [call] = llm.answered
    assert [(s.ref, s.title, s.timing) for s in call["steps"]] == [
        ("S1", "Low-fibre diet", "3 days before the procedure"),
        ("S2", "Arrange escort", "2 days before the procedure"),
        ("S3", "Clear liquids", "1 day before the procedure"),
    ]
    assert call["procedure"] == "Colonoscopy"
    assert call["time"] == "in 10 days"
    assert db_session.scalar(select(Escalation.id)) is None
    exchange = db_session.scalar(select(AssistantExchange))
    assert exchange is not None
    assert exchange.question == "When do I start the low-fibre diet?"
    assert exchange.model == "fake-model"
    assert exchange.prompt_version == "assistant-v1"


def test_red_flag_rules_escalate_without_calling_the_llm(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM, db_session: Session
) -> None:
    result = ask(client, settings, booked, "I have chest pain after the prep drink")

    assert result["outcome"] == "RED_FLAG"
    assert result["escalated"] is True
    assert result["reply"] == EMERGENCY_REPLY["en"]
    assert llm.triaged == []
    escalation = escalation_for(db_session, booked)
    assert escalation.severity is EscalationSeverity.URGENT
    assert escalation.source is EscalationSource.RED_FLAG
    assert "chest pain after the prep drink" in escalation.summary
    task = db_session.scalar(select(Task).where(Task.escalation_id == escalation.id))
    assert task is not None
    assert task.type is TaskType.CALL_PATIENT
    assert task.due_at is not None
    assert task.due_at - task.created_at <= dt.timedelta(minutes=16)
    db_session.refresh(booked.appointment)
    assert booked.appointment.status is AppointmentStatus.AT_RISK
    exchange = db_session.scalar(select(AssistantExchange))
    assert exchange is not None
    assert exchange.red_flags == ["CHEST_PAIN"]
    assert exchange.model is None


def test_hindi_red_flags_get_the_hindi_emergency_message(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM
) -> None:
    result = ask(client, settings, booked, "मुझे सीने में दर्द हो रहा है", language="hi")

    assert result["reply"] == EMERGENCY_REPLY["hi"]


def test_the_llm_triage_is_a_second_red_flag_layer(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM, db_session: Session
) -> None:
    llm.triage_result = Triage(red_flag=True, about_prep=False, reason="feels very unwell")

    result = ask(client, settings, booked, "I feel very weak and shaky since yesterday")

    assert result["outcome"] == "RED_FLAG"
    assert llm.answered == []
    assert escalation_for(db_session, booked).severity is EscalationSeverity.URGENT


@pytest.mark.parametrize(
    ("triage", "answer", "outcome"),
    [
        pytest.param(
            Triage(red_flag=False, about_prep=False, reason="asks about results"),
            GOOD_ANSWER,
            AssistantOutcome.OUT_OF_PROTOCOL,
            id="out of protocol",
        ),
        pytest.param(
            ABOUT_PREP, Answer(False, "", ()), AssistantOutcome.NOT_COVERED, id="not covered"
        ),
        pytest.param(
            ABOUT_PREP,
            Answer(True, "Follow step nine.", ("S9",)),
            AssistantOutcome.CHECK_FAILED,
            id="unknown citation",
        ),
        pytest.param(
            ABOUT_PREP,
            Answer(True, "Have clear liquids only.", ()),
            AssistantOutcome.CHECK_FAILED,
            id="no citation",
        ),
        pytest.param(
            ABOUT_PREP,
            Answer(True, "Take 2 tablets of your usual medicine.", ("S1",)),
            AssistantOutcome.CHECK_FAILED,
            id="number not in the steps",
        ),
        pytest.param(
            AssistantLLMError("LLM unavailable (APIConnectionError)"),
            GOOD_ANSWER,
            AssistantOutcome.UNAVAILABLE,
            id="triage fails",
        ),
        pytest.param(
            ABOUT_PREP,
            AssistantLLMError("LLM stopped early (refusal)"),
            AssistantOutcome.UNAVAILABLE,
            id="answer fails",
        ),
    ],
)
def test_anything_but_a_checked_answer_goes_to_a_nurse(
    client: TestClient,
    settings: Settings,
    booked: Booked,
    llm: FakeLLM,
    db_session: Session,
    triage: Triage | Exception,
    answer: Answer | Exception,
    outcome: AssistantOutcome,
) -> None:
    llm.triage_result = triage
    llm.answer_result = answer

    result = ask(client, settings, booked, "Can I keep taking my vitamins?")

    assert result["outcome"] == outcome.value
    assert result["reply"] == NURSE_REPLY["en"]
    assert result["citations"] == []
    escalation = escalation_for(db_session, booked)
    assert escalation.severity is EscalationSeverity.NORMAL
    assert escalation.source is EscalationSource.OUT_OF_PROTOCOL
    assert "Can I keep taking my vitamins?" in escalation.summary
    assert (
        db_session.scalar(select(Task.type).where(Task.escalation_id == escalation.id))
        is TaskType.NURSE_REVIEW
    )
    db_session.refresh(booked.appointment)
    assert booked.appointment.status is AppointmentStatus.SCHEDULED


def test_without_an_llm_every_question_goes_to_a_nurse(
    app: FastAPI, client: TestClient, settings: Settings, booked: Booked, db_session: Session
) -> None:
    app.state.assistant_llm = None

    result = ask(client, settings, booked, "Can I drink tea?", language="hi")

    assert result["outcome"] == "UNAVAILABLE"
    assert result["reply"] == NURSE_REPLY["hi"]
    assert escalation_for(db_session, booked).source is EscalationSource.OUT_OF_PROTOCOL


def test_patients_cannot_ask_about_another_patients_appointment(
    client: TestClient,
    settings: Settings,
    build: Builder,
    db_session: Session,
    booked: Booked,
    llm: FakeLLM,
) -> None:
    other = book(build, db_session)

    response = client.post(
        "/patient/assistant/questions",
        headers=patient_headers(settings, other.patient),
        json={"appointment_id": str(booked.appointment.id), "question": "Can I eat rice?"},
    )

    assert response.status_code == 404
    assert llm.triaged == []


def test_questions_are_limited_in_length(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM
) -> None:
    response = client.post(
        "/patient/assistant/questions",
        headers=patient_headers(settings, booked.patient),
        json={"appointment_id": str(booked.appointment.id), "question": "x" * 1001},
    )

    assert response.status_code == 422


def test_history_returns_the_patients_exchanges_and_is_audited(
    client: TestClient, settings: Settings, booked: Booked, llm: FakeLLM, db_session: Session
) -> None:
    ask(client, settings, booked, "When do I start the low-fibre diet?")
    ask(client, settings, booked, "I fainted this morning")

    response = client.get(
        "/patient/assistant/questions",
        headers=patient_headers(settings, booked.patient),
        params={"appointment_id": str(booked.appointment.id)},
    )

    assert response.status_code == 200
    history = response.json()
    assert [h["outcome"] for h in history] == ["ANSWERED", "RED_FLAG"]
    assert history[0]["citations"][0]["title"] == "Low-fibre diet"
    actions = db_session.scalars(
        select(AuditLog.action).where(
            AuditLog.entity_type == "assistant_exchange",
            AuditLog.actor_type == ActorType.PATIENT,
        )
    ).all()
    assert sorted(actions) == sorted([AuditAction.CREATE] * 2 + [AuditAction.READ] * 2)
