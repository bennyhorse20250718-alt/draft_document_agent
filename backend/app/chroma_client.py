"""
Factory for building a ChromaDB client from application settings.

Supports three modes (set via CHROMA_MODE env var):
  local  — PersistentClient using a local directory (default)
  cloud  — Chroma Cloud (https://cloud.trychroma.com)
  http   — Self-hosted ChromaDB server via HTTP
"""
import os
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings


def get_chroma_client(settings: Settings) -> chromadb.ClientAPI:
    mode = settings.chroma_mode.lower()

    if mode == "cloud":
        return chromadb.CloudClient(
            tenant=settings.chroma_cloud_tenant,
            database=settings.chroma_cloud_database,
            api_key=settings.chroma_cloud_api_key,
        )

    if mode == "http":
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )

    # Default: local persistent storage
    os.makedirs(settings.chroma_db_path, exist_ok=True)
    return chromadb.PersistentClient(
        path=settings.chroma_db_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
