from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import rag
from app.config import settings
from app.llm import answer_with_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Carregando documentos da pasta /app/documents")
    count = rag.load_documents_folder()
    logger.info("Pré-carregados: %d chunks | total: %d", count, rag.collection_count())
    yield


app = FastAPI(title="Document Q&A", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Public routes ──────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask")
async def ask(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia")
    chunks = rag.retrieve(body.question)
    answer = answer_with_context(body.question, chunks)
    return {"answer": answer}


# ── Admin routes ───────────────────────────────────────────────────────────────

def _check_auth(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autorizado")
    token = authorization.removeprefix("Bearer ")
    if not secrets.compare_digest(token, settings.admin_password):
        raise HTTPException(status_code=401, detail="Senha incorreta")


@app.post("/api/admin/login")
async def login(body: dict):
    password = body.get("password", "")
    if not secrets.compare_digest(password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Senha incorreta")
    return {"token": settings.admin_password}


@app.post("/api/admin/upload")
async def upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    _check_auth(authorization)

    data = await file.read()
    mime = file.content_type or "application/octet-stream"
    filename = file.filename or "documento"

    try:
        chunks = rag.ingest_bytes(data, mime, filename)
        return {"message": f"'{filename}' indexado com {chunks} trechos.", "total": rag.collection_count()}
    except Exception as e:
        logger.error("Erro ao indexar %s: %s", filename, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/documents")
async def list_documents(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    count = rag.collection_count()
    return {"total_chunks": count}


@app.get("/health")
async def health():
    return {"status": "ok", "chunks_indexed": rag.collection_count()}
