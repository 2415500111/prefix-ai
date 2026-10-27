from typing import Any, ClassVar
from urllib.parse import parse_qs

import httpx2
import pytest
from api_testkit import make_test_settings

from prefix_api.domain.enums import MessageChannel
from prefix_api.services.messaging.base import MessagingError, OutboundMessage, mask_recipient
from prefix_api.services.messaging.providers import (
    ChannelRouter,
    ConsoleProvider,
    SmtpProvider,
    TwilioProvider,
    UnavailableProvider,
    build_messaging_provider,
    twilio_signature,
    verify_twilio_signature,
)

SMS = OutboundMessage(channel=MessageChannel.SMS, to="+919800000001", body="Clear liquids only")


def _twilio(handler: Any, **overrides: Any) -> tuple[TwilioProvider, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        result: httpx2.Response = handler(request)
        return result

    options: dict[str, Any] = {
        "account_sid": "AC123",
        "auth_token": "secret",
        "sms_from": "+15550001111",
        "whatsapp_from": "+15550002222",
        **overrides,
    }
    client = httpx2.Client(transport=httpx2.MockTransport(record))
    return TwilioProvider(client=client, **options), seen


def test_console_provider_never_logs_the_body(caplog: pytest.LogCaptureFixture) -> None:
    result = ConsoleProvider().send(SMS)

    assert result.provider == "console"
    assert result.provider_message_id
    assert "Clear liquids" not in caplog.text


def test_twilio_sms_request() -> None:
    provider, seen = _twilio(lambda _: httpx2.Response(201, json={"sid": "SM1"}))

    result = provider.send(SMS)

    assert result.provider_message_id == "SM1"
    [request] = seen
    assert str(request.url) == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    form = parse_qs(request.content.decode())
    assert form == {
        "From": ["+15550001111"],
        "To": ["+919800000001"],
        "Body": ["Clear liquids only"],
    }
    assert request.headers["Authorization"].startswith("Basic ")


def test_twilio_whatsapp_uses_prefixed_numbers() -> None:
    provider, seen = _twilio(lambda _: httpx2.Response(201, json={"sid": "SM2"}))

    provider.send(OutboundMessage(channel=MessageChannel.WHATSAPP, to="+919800000001", body="x"))

    form = parse_qs(seen[0].content.decode())
    assert form["From"] == ["whatsapp:+15550002222"]
    assert form["To"] == ["whatsapp:+919800000001"]


def test_twilio_errors_become_messaging_errors_without_the_body() -> None:
    provider, _ = _twilio(lambda _: httpx2.Response(400, json={"message": "bad"}))

    with pytest.raises(MessagingError) as raised:
        provider.send(SMS)

    assert "HTTP 400" in str(raised.value)
    assert "Clear liquids" not in str(raised.value)


def test_twilio_network_errors_become_messaging_errors() -> None:
    def boom(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down")

    provider, _ = _twilio(boom)

    with pytest.raises(MessagingError, match="ConnectError"):
        provider.send(SMS)


def test_twilio_without_sender_number_fails_clearly() -> None:
    provider, _ = _twilio(lambda _: httpx2.Response(201, json={}), whatsapp_from=None)

    with pytest.raises(MessagingError, match="WHATSAPP_FROM"):
        provider.send(OutboundMessage(channel=MessageChannel.WHATSAPP, to="+91", body="x"))


class FakeSMTP:
    sent: ClassVar[list[Any]] = []
    calls: ClassVar[list[str]] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.calls.append(f"connect {host}:{port}")

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login {user}")

    def send_message(self, message: Any) -> None:
        self.sent.append(message)


def test_smtp_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.sent, FakeSMTP.calls = [], []
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    provider = SmtpProvider(
        host="smtp.example.com",
        port=587,
        sender="prep@example.com",
        username="u",
        password="p",
        starttls=True,
    )

    result = provider.send(
        OutboundMessage(channel=MessageChannel.EMAIL, to="a@example.com", body="Hello")
    )

    assert FakeSMTP.calls == ["connect smtp.example.com:587", "starttls", "login u"]
    [email] = FakeSMTP.sent
    assert email["To"] == "a@example.com"
    assert email.get_content().strip() == "Hello"
    assert result.provider_message_id == email["Message-ID"]


def test_router_picks_the_provider_by_channel() -> None:
    router = ChannelRouter(
        {
            MessageChannel.SMS: ConsoleProvider(),
            MessageChannel.EMAIL: UnavailableProvider("no smtp"),
        }
    )

    assert router.send(SMS).provider == "console"
    with pytest.raises(MessagingError, match="no smtp"):
        router.send(OutboundMessage(channel=MessageChannel.EMAIL, to="a@b.c", body="x"))
    with pytest.raises(MessagingError, match="No provider"):
        router.send(OutboundMessage(channel=MessageChannel.WHATSAPP, to="+1", body="x"))


def test_factory_selects_console_or_live() -> None:
    assert isinstance(build_messaging_provider(make_test_settings()), ConsoleProvider)
    live = build_messaging_provider(
        make_test_settings(
            messaging_provider="live",
            twilio_account_sid="AC1",
            twilio_auth_token="tok",
            twilio_sms_from="+15550001111",
        )
    )
    assert isinstance(live, ChannelRouter)


def test_live_messaging_requires_twilio_credentials() -> None:
    with pytest.raises(ValueError, match="TWILIO_ACCOUNT_SID"):
        make_test_settings(messaging_provider="live")


def test_empty_optional_settings_count_as_unset() -> None:
    settings = make_test_settings(smtp_host="", twilio_auth_token="", anthropic_api_key="")

    assert settings.smtp_host is None
    assert settings.twilio_auth_token is None
    assert settings.anthropic_api_key is None


def test_twilio_signature_round_trip_and_tamper() -> None:
    params = {"From": "+919800000001", "Body": "YES", "MessageSid": "SM1"}
    url = "https://api.example.com/webhooks/twilio"
    signature = twilio_signature("tok", url, params)

    assert verify_twilio_signature("tok", url, params, signature)
    assert not verify_twilio_signature("tok", url, {**params, "Body": "NO"}, signature)
    assert not verify_twilio_signature("other", url, params, signature)


@pytest.mark.parametrize(
    ("to", "masked"),
    [("+919800000123", "***123"), ("asha@example.com", "a***@example.com"), ("12", "***")],
)
def test_recipients_are_masked(to: str, masked: str) -> None:
    assert mask_recipient(to) == masked
