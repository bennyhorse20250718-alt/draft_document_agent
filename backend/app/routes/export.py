"""
Export routes — download generated draft as DOCX.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.schemas import ExportRequest
from app.services.export_service import get_export_service, ExportService

router = APIRouter(prefix="/export", tags=["Export"])


def _svc() -> ExportService:
    return get_export_service()


@router.post("/docx", summary="Export draft as DOCX and return download URL")
def export_docx(request: ExportRequest, svc: ExportService = Depends(_svc)):
    if request.format.lower() != "docx":
        raise HTTPException(status_code=400, detail="Only 'docx' format is currently supported.")
    try:
        file_path = svc.export_docx(request.draft_text, filename=request.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"file_path": file_path, "filename": Path(file_path).name}


@router.get("/download/{filename}", summary="Download an exported file")
def download_file(filename: str, svc: ExportService = Depends(_svc)):
    # Prevent path traversal
    safe_name = Path(filename).name
    file_path = Path(svc._export_path) / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_name,
    )
