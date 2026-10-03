"""FastAPI application entry point.

Wires the routers together, warms the embedding model and vector store on
startup, and turns domain exceptions into clean JSON errors.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, documents
from app.config import settings
from app.models.schemas import ConfigResponse, HealthResponse
from app.rag import embeddings, vectorstore
from app.rag.exceptions import RAGError
from app.rag.loader import SUPPORTED_EXTENSIONS
from app.services import document_service

__version__ = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rag")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the heavy components so the first user request is not the slow one."""
    settings.ensure_directories()
    logger.info("Starting RAG From Scratch v%s", __version__)

    try:
        embeddings.get_embeddings()
        logger.info("Embedding model ready: %s", settings.embedding_model)
    except RAGError as exc:
        logger.error("Embedding model unavailable: %s", exc.message)

    try:
        chunks = vectorstore.count_chunks()
        document_service.reconcile_with_vectorstore()
        logger.info("Vector store ready: %d chunks indexed", chunks)
    except RAGError as exc:
        logger.error("Vector store unavailable: %s", exc.message)

    if not settings.has_groq_key:
        logger.warning(
            "GROQ_API_KEY is not set — retrieval works, answer generation will fail."
        )
    else:
        logger.info("Groq model: %s", settings.groq_model)

    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="RAG From Scratch",
    description=(
        "Intelligent document question answering. Upload documents, then ask "
        "questions answered strictly from their retrieved contents."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Measure request latency, append custom header, and log endpoint timings."""
    import time

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    if request.url.path != "/health":
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.exception_handler(RAGError)
async def rag_exception_handler(_: Request, exc: RAGError) -> JSONResponse:
    """Render any domain error as ``{detail, code}`` with its own status."""
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.message, "code": exc.code}
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Report component readiness. Never raises — this is the liveness probe."""
    embedding_ready = embeddings.is_ready()
    store_ready = vectorstore.is_ready()
    documents_count = len(document_service.list_documents())
    chunks = document_service.total_chunks()

    problems: list[str] = []
    if not settings.has_groq_key:
        problems.append("GROQ_API_KEY is not configured; generation is unavailable.")
    if not embedding_ready:
        problems.append("Embedding model failed to load.")
    if not store_ready:
        problems.append("Vector store is unreachable.")

    return HealthResponse(
        status="ok" if not problems else "degraded",
        version=__version__,
        llm_configured=settings.has_groq_key,
        llm_model=settings.groq_model,
        embedding_model=settings.embedding_model,
        embedding_ready=embedding_ready,
        vectorstore_ready=store_ready,
        indexed_documents=documents_count,
        indexed_chunks=chunks,
        detail=" ".join(problems) or None,
    )


@app.get("/config", response_model=ConfigResponse, tags=["system"])
def config() -> ConfigResponse:
    """Non-secret settings the frontend needs. Never returns the API key."""
    return ConfigResponse(
        llm_model=settings.groq_model,
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        top_k=settings.top_k,
        max_upload_mb=settings.max_upload_mb,
        supported_types=sorted({ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS}),
    )


app.include_router(documents.router)
app.include_router(chat.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.api_host, port=settings.api_port, reload=False
    )
