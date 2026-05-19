"""
Document management routes: upload, list, delete, preview.
"""
import os
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends

from app.config import get_settings, Settings
from app.schemas import DocumentMetadataIn, DocumentSummary
from app.services.ingestion import get_ingestion_service, IngestionService

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _svc() -> IngestionService:
    return get_ingestion_service()


@router.post("/upload", summary="Upload and ingest a document")
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF, DOCX, or TXT file")],
    doc_type: Annotated[str, Form()] = "Unknown",
    topic: Annotated[str, Form()] = "",
    date: Annotated[str, Form()] = "",
    tone: Annotated[str, Form()] = "Formal",
    department: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "English",
    settings: Settings = Depends(get_settings),
    svc: IngestionService = Depends(_svc),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Save to disk
    dest = Path(settings.documents_path) / (file.filename or "upload")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    metadata = {
        "doc_type": doc_type, "topic": topic, "date": date,
        "tone": tone, "department": department, "language": language,
    }
    result = svc.ingest_file(str(dest), metadata=metadata)
    return result


@router.get("", response_model=list[DocumentSummary], summary="List all ingested documents")
def list_documents(svc: IngestionService = Depends(_svc)):
    return svc.list_documents()


@router.delete("/{doc_id}", summary="Delete a document from the knowledge base")
def delete_document(doc_id: str, svc: IngestionService = Depends(_svc)):
    deleted = svc.delete_document(doc_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted_chunks": deleted}
