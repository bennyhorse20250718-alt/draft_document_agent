"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import documents, search, draft, export
from app.services.retrieval import get_retrieval_service

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly initialise the retrieval service (loads embedding model +
    # connects to Chroma) so the first real request is not slow.
    # A failure here (e.g. Chroma Cloud unreachable) is logged but does NOT
    # crash uvicorn — the service still starts and returns a proper error on
    # requests until Chroma becomes reachable.
    logger.info("Pre-loading retrieval service...")
    try:
        get_retrieval_service()
        logger.info("Retrieval service ready.")
    except Exception as exc:
        logger.error("Retrieval service failed to initialise: %s", exc)
    yield

app = FastAPI(
    title="Draft Document AI Agent",
    description="RAG-powered official document drafting assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(search.router)
app.include_router(draft.router)
app.include_router(export.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
