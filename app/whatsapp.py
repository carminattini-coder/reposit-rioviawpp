import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

HEADERS = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}
BASE_URL = settings.evolution_api_url.rstrip("/")
INSTANCE = settings.evolution_instance


async def send_text(phone: str, text: str) -> None:
    url = f"{BASE_URL}/message/sendText/{INSTANCE}"
    payload = {"number": phone, "text": text}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        if resp.status_code >= 400:
            logger.error("Erro ao enviar mensagem: %s %s", resp.status_code, resp.text)


async def download_media(media_url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(media_url, headers=HEADERS)
        resp.raise_for_status()
        return resp.content


async def get_media_base64(message_id: str) -> dict:
    url = f"{BASE_URL}/chat/getBase64FromMediaMessage/{INSTANCE}"
    payload = {"message": {"key": {"id": message_id}}, "convertToMp4": False}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
