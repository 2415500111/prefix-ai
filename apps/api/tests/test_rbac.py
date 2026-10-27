"""Role-based access: each role gets exactly the access in ROLE_PERMISSIONS."""

import uuid
from typing import Any

import pytest
from api_testkit import Builder, staff_headers
from fastapi.testclient import TestClient

from prefix_api.core.config import Settings
from prefix_api.domain.enums import Role
from prefix_api.domain.permissions import ROLE_PERMISSIONS, Permission

ALLOWED = {200, 201}
PATIENT_BODY = {"first_name": "Ravi", "last_name": "Kumar", "date_of_birth": "1980-02-03"}


def _call(client: TestClient, action: str, headers: dict[str, str], patient_id: uuid.UUID) -> int:
    requests: dict[str, tuple[str, str, Any]] = {
        "read_patient": ("GET", f"/patients/{patient_id}", None),
        "list_patients": ("GET", "/patients", None),
        "create_patient": ("POST", "/patients", PATIENT_BODY),
        "update_patient": ("PATCH", f"/patients/{patient_id}", {"on_anticoagulant": True}),
        "magic_link": ("POST", f"/patients/{patient_id}/magic-links", None),
        "list_users": ("GET", "/users", None),
        "create_facility": (
            "POST",
            "/facilities",
            {"name": f"F {uuid.uuid4().hex[:6]}", "timezone": "Asia/Kolkata"},
        ),
    }
    method, url, body = requests[action]
    return client.request(method, url, json=body, headers=headers).status_code


REQUIRED_PERMISSION = {
    "read_patient": Permission.PATIENT_READ,
    "list_patients": Permission.PATIENT_READ,
    "create_patient": Permission.PATIENT_WRITE,
    "update_patient": Permission.PATIENT_WRITE,
    "magic_link": Permission.PATIENT_MAGIC_LINK,
    "list_users": Permission.USER_MANAGE,
    "create_facility": Permission.FACILITY_MANAGE,
}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("action", list(REQUIRED_PERMISSION))
def test_role_access_matches_permission_table(
    client: TestClient, build: Builder, settings: Settings, role: Role, action: str
) -> None:
    org = build.organization()
    patient = build.patient(org)
    headers = staff_headers(settings, build.user(org, role))

    status = _call(client, action, headers, patient.id)

    if REQUIRED_PERMISSION[action] in ROLE_PERMISSIONS[role]:
        assert status in ALLOWED, f"{role} should be allowed to {action}"
    else:
        assert status == 403, f"{role} must not be allowed to {action}"


def test_viewer_cannot_see_any_patient_data() -> None:
    patient_permissions = {
        Permission.PATIENT_READ,
        Permission.PATIENT_WRITE,
        Permission.PATIENT_MAGIC_LINK,
    }
    assert not patient_permissions & ROLE_PERMISSIONS[Role.VIEWER]


def test_only_clinicians_and_admins_can_approve_protocols() -> None:
    approvers = {r for r, perms in ROLE_PERMISSIONS.items() if Permission.PROTOCOL_APPROVE in perms}
    assert approvers == {Role.CLINICIAN, Role.ADMIN}


def test_forbidden_response_does_not_leak_internal_detail(
    client: TestClient, build: Builder, settings: Settings
) -> None:
    org = build.organization()
    response = client.get("/users", headers=staff_headers(settings, build.user(org, Role.NURSE)))

    assert response.status_code == 403
    assert response.json() == {
        "detail": "You do not have permission to do this",
        "code": "permission_denied",
    }
