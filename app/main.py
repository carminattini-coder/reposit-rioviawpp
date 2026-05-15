import base64
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from app import rag, whatsapp
from app.llm import answer_with_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando — carregando documentos da pasta /app/documents")
    count = rag.load_documents_folder()
    total = rag.collection_count()
    logger.info("Documentos pré-carregados: %d chunks novos | %d total no banco", count, total)
    yield


app = FastAPI(title="WhatsApp Document Q&A", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "chunks_indexed": rag.collection_count()}


@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    event = body.get("event", "")
    if event != "messages.upsert":
        return {"ok": True}

    data = body.get("data", {})
    key = data.get("key", {})

    # Ignore own messages
    if key.get("fromMe"):
        return {"ok": True}

    phone = key.get("remoteJid", "")
    msg = data.get("message", {})

    # --- Document received ---
    doc_info = _extract_document_info(msg)
    if doc_info:
        await _handle_document(phone, doc_info, data)
        return {"ok": True}

    # --- Text question ---
    text = _extract_text(msg)
    if text:
        await _handle_question(phone, text)

    return {"ok": True}


def _extract_text(msg: dict) -> str:
    return (
        msg.get("conversation")
        or msg.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()


def _extract_document_info(msg: dict) -> dict | None:
    for key in ("documentMessage", "imageMessage", "documentWithCaptionMessage"):
        if key in msg:
            inner = msg[key]
            if key == "documentWithCaptionMessage":
                inner = inner.get("message", {}).get("documentMessage", {})
            mime = inner.get("mimetype", "")
            if mime in DOCUMENT_MIMES or _is_document_mime(mime):
                return {
                    "mime": mime,
                    "file_name": inner.get("fileName", "documento"),
                    "caption": inner.get("caption", ""),
                }
    return None


def _is_document_mime(mime: str) -> bool:
    return any(t in mime for t in ("pdf", "word", "officedocument", "text/plain"))


async def _handle_document(phone: str, doc_info: dict, data: dict):
    file_name = doc_info["file_name"]
    mime = doc_info["mime"]

    await whatsapp.send_text(phone, f"Recebi o documento *{file_name}*. Processando, aguarde...")

    try:
        message_id = data.get("key", {}).get("id", "")
        media_data = await whatsapp.get_media_base64(message_id)
        raw = base64.b64decode(media_data.get("base64", ""))
        chunks_added = rag.ingest_bytes(raw, mime, file_name)
        total = rag.collection_count()
        await whatsapp.send_text(
            phone,
            f"Documento *{file_name}* indexado com sucesso!\n"
            f"Trechos extraídos: {chunks_added}\n"
            f"Total no banco: {total} trechos\n\n"
            "Agora pode fazer perguntas sobre este documento.",
        )
    except Exception as e:
        logger.error("Erro ao processar documento: %s", e)
        await whatsapp.send_text(
            phone,
            f"Erro ao processar o documento *{file_name}*. "
            "Verifique se o arquivo não está corrompido e tente novamente.",
        )


async def _handle_question(phone: str, question: str):
    logger.info("Pergunta de %s: %s", phone, question[:80])

    chunks = rag.retrieve(question)
    answer = answer_with_context(question, chunks)

    # WhatsApp has a 4096 char limit per message
    if len(answer) > 4000:
        parts = _split_message(answer, 4000)
        for part in parts:
            await whatsapp.send_text(phone, part)
    else:
        await whatsapp.send_text(phone, answer)


def _split_message(text: str, limit: int) -> list[str]:
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts
