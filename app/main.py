import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse

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
    "image/webp",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Carregando documentos da pasta /app/documents")
    count = rag.load_documents_folder()
    total = rag.collection_count()
    logger.info("Pré-carregados: %d novos chunks | %d total", count, total)
    yield


app = FastAPI(title="WhatsApp Document Q&A", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "chunks_indexed": rag.collection_count()}


@app.post("/webhook")
async def webhook(
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    phone = From  # e.g. whatsapp:+5511999999999

    # --- Document received ---
    if NumMedia > 0 and MediaUrl0 and _is_document(MediaContentType0):
        await _handle_document(phone, MediaUrl0, MediaContentType0)
        return PlainTextResponse("")

    # --- Text question ---
    text = Body.strip()
    if text:
        await _handle_question(phone, text)

    return PlainTextResponse("")


def _is_document(mime: str) -> bool:
    return mime in DOCUMENT_MIMES or any(
        t in mime for t in ("pdf", "word", "officedocument", "text/plain", "image")
    )


async def _handle_document(phone: str, media_url: str, mime: str):
    file_name = media_url.split("/")[-1] or "documento"
    whatsapp.send_text(phone, f"Recebi o documento. Processando, aguarde...")
    try:
        data = whatsapp.download_media(media_url)
        chunks_added = rag.ingest_bytes(data, mime, file_name)
        total = rag.collection_count()
        whatsapp.send_text(
            phone,
            f"Documento indexado!\n"
            f"Trechos extraídos: {chunks_added}\n"
            f"Total no banco: {total}\n\n"
            "Agora pode fazer perguntas sobre ele.",
        )
    except Exception as e:
        logger.error("Erro ao processar documento: %s", e)
        whatsapp.send_text(phone, "Erro ao processar o documento. Tente novamente.")


async def _handle_question(phone: str, question: str):
    logger.info("Pergunta de %s: %s", phone, question[:80])
    chunks = rag.retrieve(question)
    answer = answer_with_context(question, chunks)
    whatsapp.send_text(phone, answer)
