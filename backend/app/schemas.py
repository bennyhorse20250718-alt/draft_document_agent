"""
Pydantic schemas shared across routes.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Document / Ingestion ──────────────────────────────────────────────────────

class DocumentMetadataIn(BaseModel):
    doc_type: str = Field(default="Unknown", examples=["Official Reply", "Press Release"])
    topic: str = Field(default="")
    date: str = Field(default="", description="ISO date string, e.g. 2024-03-15")
    tone: str = Field(default="Formal", examples=["Formal", "Neutral", "Urgent"])
    department: str = Field(default="")
    language: str = Field(default="English", examples=["English", "Chinese", "Bilingual"])


class DocumentSummary(BaseModel):
    doc_id: str
    source: str
    doc_type: str
    topic: str
    date: str
    tone: str
    department: str
    language: str
    total_chunks: int


# ── Retrieval ─────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=20, ge=1, le=50)
    doc_type: Optional[str] = None
    language: Optional[str] = None
    tone: Optional[str] = None


class SearchResult(BaseModel):
    doc_id: str
    source: str
    score: float
    excerpt: str          # first 300 chars of the best chunk
    metadata: dict


# ── Generation ────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    topic: str = Field(min_length=1)
    doc_type: str = Field(default="Official Reply")
    tone: str = Field(default="Formal")
    language: str = Field(default="English")
    extra_instructions: str = Field(default="")
    selected_doc_ids: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    ref_num: int
    source: str
    doc_id: str
    excerpt: str
    highlighted_text: str = ""


class DraftResponse(BaseModel):
    draft: str
    citations: list[Citation] = Field(default_factory=list)


class RefineRequest(BaseModel):
    current_draft: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class RefineSectionRequest(BaseModel):
    section_text: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    context: str = Field(default="")


class RegenerateSelectionRequest(BaseModel):
    selected_text: str = Field(min_length=1)
    instruction: str = Field(default="")
    full_draft: str = Field(default="")
    topic: str = Field(default="")
    doc_type: str = Field(default="Official Reply")
    tone: str = Field(default="Formal")
    language: str = Field(default="English")
    citations: list[Citation] = Field(default_factory=list)


# ── Export ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    draft_text: str = Field(min_length=1)
    filename: str = Field(default="draft")
    format: str = Field(default="docx", examples=["docx"])
