from __future__ import annotations

import logging
import uuid
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.documents import chunk_text, extract_text, extract_text_from_bytes

logger = logging.getLogger(__name__)

_client: chromadb.PersistentClient | None = None
_collection = None
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info("Carregando modelo de embeddings: %s", settings.embedding_model)
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_db_path)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        _collection = _client.get_or_create_collection(
            name="documents",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def ingest_file(file_path: str | Path, source_name: str | None = None) -> int:
    path = Path(file_path)
    name = source_name or path.name
    logger.info("Indexando arquivo: %s", name)

    text = extract_text(path)
    return _add_chunks(text, source=name)


def ingest_bytes(data: bytes, mime_type: str, source_name: str) -> int:
    logger.info("Indexando documento recebido: %s (%s)", source_name, mime_type)
    text = extract_text_from_bytes(data, mime_type)
    return _add_chunks(text, source=source_name)


def _add_chunks(text: str, source: str) -> int:
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        logger.warning("Nenhum texto extraído de: %s", source)
        return 0

    collection = _get_collection()

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": source, "chunk": i} for i, _ in enumerate(chunks)]
    collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    logger.info("Indexados %d chunks de '%s'", len(chunks), source)
    return len(chunks)


def retrieve(query: str, k: int | None = None) -> list[dict]:
    collection = _get_collection()
    k = k or settings.retrieval_k

    results = collection.query(
        query_texts=[query],
        n_results=min(k, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["documents"]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({"text": doc, "source": meta.get("source", ""), "score": 1 - dist})

    return chunks


def collection_count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


def load_documents_folder() -> int:
    folder = Path(settings.documents_path)
    if not folder.exists():
        return 0

    supported = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"}
    total = 0
    for file in folder.iterdir():
        if file.suffix.lower() in supported:
            try:
                total += ingest_file(file)
            except Exception as e:
                logger.error("Erro ao indexar %s: %s", file.name, e)
    return total
