"""Protocol Engine: versioning, approval rules, and use only of approved protocols."""

import uuid
from typing import Any

import pytest
from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prefix_api.core.config import Settings
from prefix_api.db.models import AuditLog, Organization, PrepProtocol, ProcedureType
from prefix_api.domain.enums import AuditAction, ProtocolStatus, Role
from prefix_api.services.protocols import UnapprovedProtocolError, applicable_steps

STEPS: list[dict[str, Any]] = [
    {
        "offset_minutes": 7 * 24 * 60,
        "title": "Blood thinner",
        "instruction_text": "Ask your care team whether to pause your blood thinner.",
        "category": "MEDICATION",
        "requires_confirmation": True,
        "is_critical": True,
        "conditions": {"flag": "on_anticoagulant"},
    },
    {
        "offset_minutes": 24 * 60,
        "title": "Clear liquids",
        "instruction_text": "Clear liquids only from the morning before your procedure.",
        "category": "DIET",
    },
]


class World:
    def __init__(self, build: Builder, settings: Settings) -> None:
        self.org: Organization = build.organization()
        self.procedure_type: ProcedureType = build.procedure_type(self.org)
        self.clinician = staff_headers(settings, build.user(self.org, Role.CLINICIAN))
        self.admin = staff_headers(settings, build.user(self.org, Role.ADMIN))
        self.coordinator = staff_headers(settings, build.user(self.org, Role.COORDINATOR))
        self.nurse = staff_headers(settings, build.user(self.org, Role.NURSE))

    def body(self, **overrides: Any) -> dict[str, Any]:
        return {
            "procedure_type_id": str(self.procedure_type.id),
            "name": "Colonoscopy prep",
            "steps": STEPS,
            **overrides,
        }


@pytest.fixture
def world(build: Builder, settings: Settings) -> World:
    return World(build, settings)


def _create(client: TestClient, world: World, **overrides: Any) -> dict[str, Any]:
    response = client.post("/protocols", json=world.body(**overrides), headers=world.clinician)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def _approve(client: TestClient, world: World, protocol_id: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"/protocols/{protocol_id}/approve", json=body, headers=world.clinician)
    assert response.status_code == 200, response.text
    approved: dict[str, Any] = response.json()
    return approved


def test_clinician_creates_a_draft(client: TestClient, world: World) -> None:
    created = _create(client, world)

    assert created["status"] == "DRAFT"
    assert created["version"] == 1
    assert [s["title"] for s in created["steps"]] == ["Blood thinner", "Clear liquids"]
    assert [s["sort_order"] for s in created["steps"]] == [0, 1]


@pytest.mark.parametrize("role", ["coordinator", "nurse"])
def test_only_editors_can_create(client: TestClient, world: World, role: str) -> None:
    response = client.post("/protocols", json=world.body(), headers=getattr(world, role))

    assert response.status_code == 403


def test_invalid_condition_is_rejected_on_save(client: TestClient, world: World) -> None:
    bad_step = {**STEPS[1], "conditions": {"flag": "is_vip"}}

    response = client.post("/protocols", json=world.body(steps=[bad_step]), headers=world.clinician)

    assert response.status_code == 422


def test_procedure_type_must_belong_to_the_org(
    client: TestClient, world: World, build: Builder
) -> None:
    foreign = build.procedure_type(build.organization())

    response = client.post(
        "/protocols",
        json=world.body(procedure_type_id=str(foreign.id)),
        headers=world.clinician,
    )

    assert response.status_code == 422


def test_approval_records_approver_and_embeds_steps(
    client: TestClient, world: World, db_session: Session
) -> None:
    approved = _approve(client, world, _create(client, world)["id"])

    assert approved["status"] == "APPROVED"
    assert approved["approved_by_id"] is not None
    assert approved["approved_at"] is not None
    protocol = db_session.get(PrepProtocol, uuid.UUID(approved["id"]))
    assert protocol is not None
    for step in protocol.steps:
        assert step.embedding is not None
        assert len(step.embedding) == 384
        assert step.embedding_model == "local-hashing-v1"


@pytest.mark.parametrize("role", ["coordinator", "nurse"])
def test_only_clinicians_and_admins_can_approve(
    client: TestClient, world: World, role: str
) -> None:
    protocol_id = _create(client, world)["id"]

    response = client.post(
        f"/protocols/{protocol_id}/approve", json={}, headers=getattr(world, role)
    )

    assert response.status_code == 403


def test_admin_can_approve(client: TestClient, world: World) -> None:
    protocol_id = _create(client, world)["id"]

    response = client.post(f"/protocols/{protocol_id}/approve", json={}, headers=world.admin)

    assert response.status_code == 200


def test_protocol_without_steps_cannot_be_approved(client: TestClient, world: World) -> None:
    protocol_id = _create(client, world, steps=[])["id"]

    response = client.post(f"/protocols/{protocol_id}/approve", json={}, headers=world.clinician)

    assert response.status_code == 422


def test_sample_protocol_needs_explicit_acknowledgement(
    client: TestClient, world: World, db_session: Session
) -> None:
    protocol_id = _create(client, world)["id"]
    protocol = db_session.get(PrepProtocol, uuid.UUID(protocol_id))
    assert protocol is not None
    protocol.is_sample = True
    db_session.flush()

    refused = client.post(f"/protocols/{protocol_id}/approve", json={}, headers=world.clinician)
    accepted = client.post(
        f"/protocols/{protocol_id}/approve",
        json={"acknowledge_sample": True},
        headers=world.clinician,
    )

    assert refused.status_code == 422
    assert "SAMPLE" in refused.json()["detail"]
    assert accepted.status_code == 200


def test_editing_an_approved_protocol_creates_a_new_draft(client: TestClient, world: World) -> None:
    v1 = _approve(client, world, _create(client, world)["id"])

    edited = client.put(
        f"/protocols/{v1['id']}",
        json=world.body(name="Colonoscopy prep v2"),
        headers=world.clinician,
    ).json()
    original = client.get(f"/protocols/{v1['id']}", headers=world.clinician).json()

    assert edited["id"] != v1["id"]
    assert edited["family_id"] == v1["family_id"]
    assert edited["version"] == 2
    assert edited["status"] == "DRAFT"
    assert original["status"] == "APPROVED"
    assert original["name"] == "Colonoscopy prep"


def test_a_family_has_at_most_one_draft(client: TestClient, world: World) -> None:
    v1 = _approve(client, world, _create(client, world)["id"])
    client.put(f"/protocols/{v1['id']}", json=world.body(), headers=world.clinician)

    second = client.put(f"/protocols/{v1['id']}", json=world.body(), headers=world.clinician)

    assert second.status_code == 409


def test_editing_a_draft_changes_it_in_place(client: TestClient, world: World) -> None:
    draft = _create(client, world)

    edited = client.put(
        f"/protocols/{draft['id']}",
        json=world.body(name="Renamed", steps=STEPS[1:]),
        headers=world.clinician,
    ).json()

    assert edited["id"] == draft["id"]
    assert edited["version"] == 1
    assert edited["name"] == "Renamed"
    assert [s["title"] for s in edited["steps"]] == ["Clear liquids"]


def test_approving_a_new_version_retires_the_old_one(client: TestClient, world: World) -> None:
    v1 = _approve(client, world, _create(client, world)["id"])
    v2 = client.put(f"/protocols/{v1['id']}", json=world.body(), headers=world.clinician).json()

    _approve(client, world, v2["id"])
    versions = client.get(f"/protocols/{v1['id']}/versions", headers=world.clinician).json()

    assert [(v["version"], v["status"]) for v in versions] == [(1, "RETIRED"), (2, "APPROVED")]


def test_approved_protocol_cannot_be_approved_again(client: TestClient, world: World) -> None:
    approved = _approve(client, world, _create(client, world)["id"])

    response = client.post(f"/protocols/{approved['id']}/approve", json={}, headers=world.clinician)

    assert response.status_code == 409


def test_list_shows_latest_version_per_family(client: TestClient, world: World) -> None:
    v1 = _approve(client, world, _create(client, world)["id"])
    client.put(f"/protocols/{v1['id']}", json=world.body(), headers=world.clinician)
    _create(client, world, name="CT prep")

    listed = client.get("/protocols", headers=world.nurse).json()

    assert sorted((p["name"], p["version"]) for p in listed) == [
        ("CT prep", 1),
        ("Colonoscopy prep", 2),
    ]


def test_protocols_are_tenant_scoped(
    client: TestClient, world: World, build: Builder, settings: Settings
) -> None:
    protocol_id = _create(client, world)["id"]
    outsider = staff_headers(settings, build.user(build.organization(), Role.ADMIN))

    assert client.get(f"/protocols/{protocol_id}", headers=outsider).status_code == 404
    assert client.get("/protocols", headers=outsider).json() == []
    approve = client.post(f"/protocols/{protocol_id}/approve", json={}, headers=outsider)
    assert approve.status_code == 404


def test_protocol_changes_are_audited(
    client: TestClient, world: World, db_session: Session
) -> None:
    protocol_id = _approve(client, world, _create(client, world)["id"])["id"]

    actions = db_session.scalars(
        select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(protocol_id))
    ).all()

    assert actions == [AuditAction.CREATE, AuditAction.UPDATE]


def test_applicable_steps_follow_patient_conditions(
    client: TestClient, world: World, db_session: Session
) -> None:
    protocol = db_session.get(
        PrepProtocol, uuid.UUID(_approve(client, world, _create(client, world)["id"])["id"])
    )
    assert protocol is not None

    on_thinner = applicable_steps(protocol, {"on_anticoagulant": True})
    not_on_thinner = applicable_steps(protocol, {"on_anticoagulant": False})

    assert [s.title for s in on_thinner] == ["Blood thinner", "Clear liquids"]
    assert [s.title for s in not_on_thinner] == ["Clear liquids"]


def test_unapproved_protocols_can_never_produce_patient_steps(
    client: TestClient, world: World, db_session: Session
) -> None:
    draft = db_session.get(PrepProtocol, uuid.UUID(_create(client, world)["id"]))
    assert draft is not None
    assert draft.status is ProtocolStatus.DRAFT

    with pytest.raises(UnapprovedProtocolError):
        applicable_steps(draft, {})
