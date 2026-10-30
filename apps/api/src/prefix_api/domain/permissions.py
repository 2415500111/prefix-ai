from enum import StrEnum

from prefix_api.domain.enums import Role


class Permission(StrEnum):
    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    PATIENT_MAGIC_LINK = "patient:magic_link"
    APPOINTMENT_READ = "appointment:read"
    APPOINTMENT_WRITE = "appointment:write"
    PROTOCOL_READ = "protocol:read"
    PROTOCOL_EDIT = "protocol:edit"
    PROTOCOL_APPROVE = "protocol:approve"
    ESCALATION_HANDLE = "escalation:handle"
    TASK_MANAGE = "task:manage"
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"
    FACILITY_MANAGE = "facility:manage"
    STEP_CONFIRM = "step:confirm"
    TASK_COMPLETE = "task:complete"
    DEMO_RESET = "demo:reset"
    MESSAGE_SEND = "message:send"


_P = Permission

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    # Guests can look at everything in the demo hospital and tick things off, nothing more.
    Role.DEMO_VIEWER: frozenset(
        {
            _P.PATIENT_READ,
            _P.PATIENT_MAGIC_LINK,
            _P.APPOINTMENT_READ,
            _P.PROTOCOL_READ,
            _P.ESCALATION_HANDLE,
            _P.TASK_MANAGE,
            _P.TASK_COMPLETE,
            _P.STEP_CONFIRM,
            _P.ANALYTICS_READ,
        }
    ),
    Role.COORDINATOR: frozenset(
        {
            _P.PATIENT_READ,
            _P.PATIENT_WRITE,
            _P.PATIENT_MAGIC_LINK,
            _P.APPOINTMENT_READ,
            _P.APPOINTMENT_WRITE,
            _P.PROTOCOL_READ,
            _P.ESCALATION_HANDLE,
            _P.TASK_MANAGE,
            _P.TASK_COMPLETE,
            _P.STEP_CONFIRM,
            _P.ANALYTICS_READ,
            _P.ANALYTICS_EXPORT,
            _P.MESSAGE_SEND,
        }
    ),
    Role.NURSE: frozenset(
        {
            _P.PATIENT_READ,
            _P.PATIENT_MAGIC_LINK,
            _P.APPOINTMENT_READ,
            _P.PROTOCOL_READ,
            _P.ESCALATION_HANDLE,
            _P.TASK_MANAGE,
            _P.TASK_COMPLETE,
            _P.STEP_CONFIRM,
            _P.MESSAGE_SEND,
        }
    ),
    Role.CLINICIAN: frozenset(
        {
            _P.PATIENT_READ,
            _P.APPOINTMENT_READ,
            _P.PROTOCOL_READ,
            _P.PROTOCOL_EDIT,
            _P.PROTOCOL_APPROVE,
            _P.ESCALATION_HANDLE,
        }
    ),
    # Viewers see aggregate analytics only, never patient-level data.
    Role.VIEWER: frozenset({_P.ANALYTICS_READ}),
}


def role_has(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
