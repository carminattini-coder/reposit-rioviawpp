from __future__ import annotations

from twilio.rest import Client
from app.config import settings

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def send_text(to: str, text: str) -> None:
    # Split messages longer than 1600 chars (Twilio limit)
    chunks = [text[i:i+1600] for i in range(0, len(text), 1600)]
    client = _get_client()
    for chunk in chunks:
        client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=to,
            body=chunk,
        )


def download_media(media_url: str) -> bytes:
    import httpx
    client = _get_client()
    # Twilio media requires auth
    with httpx.Client(auth=(settings.twilio_account_sid, settings.twilio_auth_token)) as http:
        resp = http.get(media_url)
        resp.raise_for_status()
        return resp.content
