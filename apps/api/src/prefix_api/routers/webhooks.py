"""Inbound messaging webhooks. Authenticated by provider signature, not by user tokens."""

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from prefix_api.api.deps import DbSession, Now, SettingsDep
from prefix_api.domain.enums import MessageChannel
from prefix_api.domain.errors import AuthenticationError
from prefix_api.services.inbound import handle_inbound_message
from prefix_api.services.messaging.providers import verify_twilio_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("/twilio", include_in_schema=False)
async def twilio_inbound(
    request: Request, session: DbSession, settings: SettingsDep, now: Now
) -> Response:
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}

    if settings.messaging_provider == "live":
        token = settings.twilio_auth_token.get_secret_value() if settings.twilio_auth_token else ""
        url = f"{str(settings.public_api_base_url).rstrip('/')}/webhooks/twilio"
        signature = request.headers.get("X-Twilio-Signature", "")
        if not verify_twilio_signature(token, url, params, signature):
            raise AuthenticationError("Invalid webhook signature")
    elif settings.is_production:
        raise AuthenticationError("Webhooks are disabled without a live messaging provider")

    sender = params.get("From", "")
    channel = MessageChannel.WHATSAPP if sender.startswith("whatsapp:") else MessageChannel.SMS
    phone = sender.removeprefix("whatsapp:")
    if phone:
        # Database work is synchronous; keep it off the event loop.
        await run_in_threadpool(
            handle_inbound_message,
            session,
            from_phone=phone,
            body=params.get("Body", ""),
            channel=channel,
            provider="twilio",
            provider_message_id=params.get("MessageSid"),
            now=now,
        )
    return Response(content=_EMPTY_TWIML, media_type="application/xml")
