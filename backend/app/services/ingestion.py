"""
Document ingestion service.
Parses PDF/DOCX files, chunks text, and stores embeddings in ChromaDB.
"""
import os
import hashlib
from pathlib import Path
from typing import Optional
import logging

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.chroma_client import get_chroma_client

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1500       # characters per chunk
CHUNK_OVERLAP = 300     # overlap between chunks
COLLECTION_NAME = "documents"


class IngestionService:
    def __init__(self):
        settings = get_settings()
        os.makedirs(settings.documents_path, exist_ok=True)

        self._chroma = get_chroma_client(settings)
        self._collection = self._chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = SentenceTransformer(settings.embedding_model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_file(
        self,
        file_path: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Parse a file, chunk it, embed and store in ChromaDB.
        Returns a summary dict with chunk count and doc_id.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        text = self._extract_text(path)
        if not text.strip():
            raise ValueError(f"No text could be extracted from {path.name}")

        chunks = self._chunk_text(text)
        doc_id = self._file_hash(path)

        base_meta = {
            "source": path.name,
            "doc_id": doc_id,
            "doc_type": metadata.get("doc_type", "Unknown") if metadata else "Unknown",
            "topic": metadata.get("topic", "") if metadata else "",
            "date": metadata.get("date", "") if metadata else "",
            "tone": metadata.get("tone", "Formal") if metadata else "Formal",
            "department": metadata.get("department", "") if metadata else "",
            "language": metadata.get("language", "English") if metadata else "English",
        }

        # Remove existing chunks for this doc so re-ingestion is idempotent
        existing = self._collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])

        ids, embeddings, docs, metas = [], [], [], []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            embedding = self._embedder.encode(chunk).tolist()
            ids.append(chunk_id)
            embeddings.append(embedding)
            docs.append(chunk)
            metas.append({**base_meta, "chunk_index": i, "total_chunks": len(chunks)})

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metas,
        )

        logger.info("Ingested %s: %d chunks stored", path.name, len(chunks))
        return {"doc_id": doc_id, "source": path.name, "chunks": len(chunks)}

    def list_documents(self) -> list[dict]:
        """Return one summary record per unique source document."""
        results = self._collection.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in results["metadatas"]:
            doc_id = meta.get("doc_id", "")
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "source": meta.get("source", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "topic": meta.get("topic", ""),
                    "date": meta.get("date", ""),
                    "tone": meta.get("tone", ""),
                    "department": meta.get("department", ""),
                    "language": meta.get("language", ""),
                    "total_chunks": meta.get("total_chunks", 0),
                }
        return list(seen.values())

    def delete_document(self, doc_id: str) -> int:
        existing = self._collection.get(where={"doc_id": doc_id})
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path)
        if suffix in (".docx", ".doc"):
            return self._extract_docx(path)
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        raise ValueError(f"Unsupported file type: {suffix}")

    def _extract_pdf(self, path: Path) -> str:
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)

    def _extract_docx(self, path: Path) -> str:
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    def _chunk_text(self, text: str) -> list[str]:
        """Sliding-window character chunking with overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    @staticmethod
    def _file_hash(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()[:16]


# Module-level singleton
_service: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    global _service
    if _service is None:
        _service = IngestionService()
    return _service
