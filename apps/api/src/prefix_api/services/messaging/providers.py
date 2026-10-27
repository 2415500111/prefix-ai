"""Concrete messaging providers and the factory that picks them from settings."""

import base64
import hashlib
import hmac
import smtplib
import uuid
from email.message import EmailMessage

import httpx2

from prefix_api.core.config import Settings
from prefix_api.core.logging import get_logger
from prefix_api.domain.enums import MessageChannel
from prefix_api.services.messaging.base import (
    MessagingError,
    MessagingProvider,
    OutboundMessage,
    SendResult,
    mask_recipient,
)

logger = get_logger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01"


class ConsoleProvider:
    """Development default: logs that a message would be sent. The body is not logged."""

    name = "console"

    def send(self, message: OutboundMessage) -> SendResult:
        logger.info(
            "message.console_send",
            channel=message.channel.value,
            to=mask_recipient(message.to),
            characters=len(message.body),
        )
        return SendResult(provider=self.name, provider_message_id=f"console-{uuid.uuid4().hex}")


class TwilioProvider:
    """SMS and WhatsApp through Twilio's REST API."""

    name = "twilio"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        sms_from: str | None,
        whatsapp_from: str | None,
        client: httpx2.Client | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._sms_from = sms_from
        self._whatsapp_from = whatsapp_from
        self._client = client or httpx2.Client(timeout=15.0)

    def send(self, message: OutboundMessage) -> SendResult:
        if message.channel is MessageChannel.WHATSAPP:
            if not self._whatsapp_from:
                raise MessagingError("TWILIO_WHATSAPP_FROM is not configured")
            sender, recipient = f"whatsapp:{self._whatsapp_from}", f"whatsapp:{message.to}"
        else:
            if not self._sms_from:
                raise MessagingError("TWILIO_SMS_FROM is not configured")
            sender, recipient = self._sms_from, message.to
        try:
            response = self._client.post(
                f"{TWILIO_API}/Accounts/{self._account_sid}/Messages.json",
                data={"From": sender, "To": recipient, "Body": message.body},
                auth=(self._account_sid, self._auth_token),
            )
        except httpx2.HTTPError as exc:
            raise MessagingError(f"Twilio request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise MessagingError(f"Twilio rejected the message (HTTP {response.status_code})")
        sid = response.json().get("sid")
        return SendResult(provider=self.name, provider_message_id=str(sid) if sid else None)


class SmtpProvider:
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None,
        password: str | None,
        starttls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls

    def send(self, message: OutboundMessage) -> SendResult:
        email = EmailMessage()
        email["From"] = self._sender
        email["To"] = message.to
        email["Subject"] = message.subject
        message_id = f"<{uuid.uuid4().hex}@prefix-ai>"
        email["Message-ID"] = message_id
        email.set_content(message.body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
                if self._starttls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(email)
        except (smtplib.SMTPException, OSError) as exc:
            raise MessagingError(f"SMTP send failed: {type(exc).__name__}") from exc
        return SendResult(provider=self.name, provider_message_id=message_id)


class UnavailableProvider:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def send(self, message: OutboundMessage) -> SendResult:
        raise MessagingError(self._reason)


class ChannelRouter:
    """Sends each message through the provider configured for its channel."""

    def __init__(self, providers: dict[MessageChannel, MessagingProvider]) -> None:
        self._providers = providers

    def send(self, message: OutboundMessage) -> SendResult:
        provider = self._providers.get(message.channel)
        if provider is None:
            raise MessagingError(f"No provider for channel {message.channel.value}")
        return provider.send(message)


def build_messaging_provider(settings: Settings) -> MessagingProvider:
    if settings.messaging_provider == "console":
        return ConsoleProvider()

    twilio: MessagingProvider = TwilioProvider(
        account_sid=settings.twilio_account_sid or "",
        auth_token=settings.twilio_auth_token.get_secret_value()
        if settings.twilio_auth_token
        else "",
        sms_from=settings.twilio_sms_from,
        whatsapp_from=settings.twilio_whatsapp_from,
    )
    email: MessagingProvider
    if settings.smtp_host and settings.smtp_from:
        email = SmtpProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.smtp_from,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            starttls=settings.smtp_starttls,
        )
    else:
        email = UnavailableProvider("SMTP is not configured")
    return ChannelRouter(
        {
            MessageChannel.SMS: twilio,
            MessageChannel.WHATSAPP: twilio,
            MessageChannel.EMAIL: email,
        }
    )


def twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Twilio's X-Twilio-Signature: base64(HMAC-SHA1(token, url + sorted key/value pairs))."""
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def verify_twilio_signature(
    auth_token: str, url: str, params: dict[str, str], signature: str
) -> bool:
    return hmac.compare_digest(twilio_signature(auth_token, url, params), signature)
