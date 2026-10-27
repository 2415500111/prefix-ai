from dataclasses import dataclass
from typing import Protocol

from prefix_api.domain.enums import MessageChannel


class MessagingError(Exception):
    """A message could not be sent. The text is safe to store (no message body or PHI)."""


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    channel: MessageChannel
    to: str
    """E.164 phone number for SMS/WhatsApp, or an email address."""
    body: str
    subject: str = "Your procedure preparation"


@dataclass(frozen=True, slots=True)
class SendResult:
    provider: str
    provider_message_id: str | None


class MessagingProvider(Protocol):
    def send(self, message: OutboundMessage) -> SendResult: ...


def mask_recipient(to: str) -> str:
    """Enough to tell recipients apart in logs, never the full address."""
    if "@" in to:
        name, _, domain = to.partition("@")
        return f"{name[:1]}***@{domain}"
    return f"***{to[-3:]}" if len(to) > 3 else "***"
