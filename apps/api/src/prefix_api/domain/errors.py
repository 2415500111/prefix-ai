"""Errors raised by services. Routers never raise HTTP errors themselves; one exception
handler maps these to responses."""


class DomainError(Exception):
    code = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """Also used for records in another tenant, so their existence is not revealed."""

    code = "not_found"


class AuthenticationError(DomainError):
    code = "not_authenticated"


class PermissionDeniedError(DomainError):
    code = "permission_denied"


class ConflictError(DomainError):
    code = "conflict"


class ValidationFailedError(DomainError):
    code = "validation_failed"


class RateLimitedError(DomainError):
    code = "rate_limited"
