"""
Search / retrieval routes.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

from app.schemas import SearchRequest, SearchResult
from app.services.retrieval import get_retrieval_service, RetrievalService

# Root of the Document/ folder (backend/app/routes/ → up 4 levels → local_version/)
_DOCUMENTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Document"

# Map from date metadata string back to the year sub-folder name under Document/pdf/
_DATE_TO_YEAR_FOLDER: dict[str, str] = {
    "2023-2024": "hhb-e_2324",
    "2024-2025": "hhb-e_2425",
    "2025-2026": "hhb-e_2526",
    "2026-2027": "hhb-e_2627",
    "2027-2028": "hhb-e_2728",
}

router = APIRouter(prefix="/search", tags=["Search"])


def _svc() -> RetrievalService:
    return get_retrieval_service()


@router.post("", response_model=list[SearchResult], summary="Semantic + keyword search")
def search(request: SearchRequest, svc: RetrievalService = Depends(_svc)):
    if svc.collection_count() == 0:
        raise HTTPException(
            status_code=400,
            detail="Knowledge base is empty. Please upload documents first.",
        )

    filters = {}
    if request.doc_type:
        filters["doc_type"] = request.doc_type
    if request.language:
        filters["language"] = request.language
    if request.tone:
        filters["tone"] = request.tone

    raw = svc.search(request.query, top_k=request.top_k, filters=filters or None)

    results = []
    for item in raw:
        meta = item["metadata"]
        results.append(
            SearchResult(
                doc_id=meta.get("doc_id", ""),
                source=meta.get("source", ""),
                score=round(item["score"], 4),
                excerpt=item["text"][:300],
                metadata=meta,
            )
        )
    return results


@router.get("/preview/{doc_id}", summary="Get full text preview of a document")
def preview_document(doc_id: str, svc: RetrievalService = Depends(_svc)):
    chunks = svc.get_chunks_for_doc(doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    full_text = "\n\n".join(c["text"] for c in chunks)
    meta = chunks[0]["metadata"] if chunks else {}
    return {"doc_id": doc_id, "text": full_text, "metadata": meta}


@router.get("/pdf/{doc_id}", summary="Serve the original PDF for a document")
def get_pdf(doc_id: str, svc: RetrievalService = Depends(_svc)):
    """Locate and stream the PDF file that corresponds to the given document ID."""
    chunks = svc.get_chunks_for_doc(doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found in knowledge base")

    meta = chunks[0]["metadata"]
    source: str = meta.get("source", "")
    # Source is stored as e.g. '10_HHB009.pdf.txt' or '10_HHB009.pdf'
    pdf_name = source.removesuffix(".txt")  # strip .txt if present

    pdf_root = _DOCUMENTS_DIR / "pdf"
    txt_root = _DOCUMENTS_DIR / "txt"

    def _serve(path: Path) -> FileResponse:
        logger.info("Serving PDF: %s (doc_id=%s, year=%s)", path.name, doc_id, path.parent.name)
        return FileResponse(
            str(path),
            media_type="application/pdf",
            filename=pdf_name,
            headers={
                "Content-Disposition": f'inline; filename="{pdf_name}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    if pdf_root.exists():
        # Strategy 1: Locate the source .txt file in Document/txt to identify the correct year
        # folder, then look for the PDF in the matching Document/pdf/<year>/ folder.
        # This is the most reliable method as it is independent of stored metadata.
        if txt_root.exists() and source:
            for txt_match in txt_root.rglob(source):
                year_folder = txt_match.parent.name  # e.g. 'hhb-e_2526'
                pdf_candidate = pdf_root / year_folder / pdf_name
                if pdf_candidate.is_file():
                    return _serve(pdf_candidate)

        # Strategy 2: Use the date metadata to reverse-map to the year folder
        date_str: str = meta.get("date", "")
        year_folder = _DATE_TO_YEAR_FOLDER.get(date_str)
        if year_folder:
            specific = pdf_root / year_folder / pdf_name
            if specific.is_file():
                return _serve(specific)

        # Strategy 3: Recursive search as a last resort (may return wrong year on name collision)
        for candidate in pdf_root.rglob(pdf_name):
            if candidate.is_file():
                return _serve(candidate)

    raise HTTPException(
        status_code=404,
        detail=f"PDF file '{pdf_name}' not found on disk. Only text preview is available.",
    )
