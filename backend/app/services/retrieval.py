"""
Retrieval service — hybrid semantic + keyword search over ChromaDB.
"""
import os
from pathlib import Path
from typing import Optional
import logging

from fastembed import TextEmbedding

from app.config import get_settings
from app.chroma_client import get_chroma_client

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"
DEFAULT_TOP_K = 8

# Absolute path to Document/txt/ — used to serve full file text to the LLM
_DOCUMENTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Document"


class RetrievalService:
    def __init__(self):
        settings = get_settings()
        self._chroma = get_chroma_client(settings)
        self._collection = self._chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # Normalise short name → full HuggingFace path that fastembed expects
        model_name = settings.embedding_model
        if "/" not in model_name:
            model_name = f"sentence-transformers/{model_name}"
        self._embedder = TextEmbedding(model_name=model_name)

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        Hybrid search: semantic vector search + keyword re-ranking.
        Returns deduplicated results grouped by source document.
        """
        query_embedding = list(self._embedder.embed([query]))[0].tolist()

        where_clause = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if value:
                    conditions.append({key: {"$eq": value}})
            if len(conditions) == 1:
                where_clause = conditions[0]
            elif len(conditions) > 1:
                where_clause = {"$and": conditions}

        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 3, max(1, self._collection.count())),
            include=["documents", "metadatas", "distances"],
        )
        if where_clause:
            kwargs["where"] = where_clause

        results = self._collection.query(**kwargs)

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # Keyword boost: add small score bonus for query word presence
            query_words = set(query.lower().split())
            doc_words = set(doc.lower().split())
            keyword_hits = len(query_words & doc_words)
            keyword_boost = keyword_hits * 0.02

            chunks.append({
                "text": doc,
                "metadata": meta,
                "score": (1 - dist) + keyword_boost,  # cosine similarity + boost
            })

        # Deduplicate: keep best-scoring chunk per source document
        best_per_doc: dict[str, dict] = {}
        for chunk in chunks:
            doc_id = chunk["metadata"].get("doc_id", chunk["metadata"].get("source", ""))
            if doc_id not in best_per_doc or chunk["score"] > best_per_doc[doc_id]["score"]:
                best_per_doc[doc_id] = chunk

        ranked = sorted(best_per_doc.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    def get_chunks_for_doc(self, doc_id: str) -> list[dict]:
        """Retrieve all chunks for a specific document (for preview)."""
        results = self._collection.get(
            where={"doc_id": {"$eq": doc_id}},
            include=["documents", "metadatas"],
        )
        chunks = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            chunks.append({"text": doc, "metadata": meta, "chunk_index": meta.get("chunk_index", 0)})
        chunks.sort(key=lambda x: x["chunk_index"])
        return chunks

    def get_full_text_for_doc(self, doc_id: str) -> tuple[str, dict]:
        """
        Return (full_text, metadata) for a document.
        Reads the original .txt file from disk for a clean, non-overlapping full text.
        Falls back to concatenating all ChromaDB chunks if the file cannot be found.
        """
        all_chunks = self.get_chunks_for_doc(doc_id)
        if not all_chunks:
            return "", {}
        meta = all_chunks[0]["metadata"]
        source: str = meta.get("source", "")
        # Strategy 1: locate the .txt file on disk via rglob (year-folder agnostic)
        txt_root = _DOCUMENTS_DIR / "txt"
        if txt_root.exists() and source:
            for txt_match in txt_root.rglob(source):
                try:
                    return txt_match.read_text(encoding="utf-8", errors="replace"), meta
                except OSError:
                    pass
        # Fallback: reconstruct from stored chunks sorted by chunk_index
        full_text = "\n".join(c["text"] for c in all_chunks)
        return full_text, meta

    def collection_count(self) -> int:
        return self._collection.count()


_service: "RetrievalService | None" = None


def get_retrieval_service() -> RetrievalService:
    global _service
    if _service is None:
        _service = RetrievalService()
    return _service
