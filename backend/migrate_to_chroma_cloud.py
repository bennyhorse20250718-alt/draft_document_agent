"""
Migrate local ChromaDB knowledge base to Chroma Cloud.

Copies all vectors, documents, and metadata directly — no re-embedding needed.
This is much faster than re-running ingest_documents.py for large collections.

Usage (run from the backend/ directory):
    python migrate_to_chroma_cloud.py

Required env vars (in backend/.env):
    CHROMA_DB_PATH           path to your local chroma_db directory
    CHROMA_CLOUD_API_KEY     chr_xxxxxxxxxxxxxxxxxxxxxxxx
    CHROMA_CLOUD_TENANT      your-tenant-id
    CHROMA_CLOUD_DATABASE    default_database  (or your custom database name)

The script is idempotent — re-running it skips IDs that already exist in the cloud.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.config import Settings as ChromaSettings

COLLECTION_NAME = "documents"
BATCH_SIZE = 200   # items per upsert call (keep ≤ 500 for Chroma Cloud limits)


def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"[ERROR] Environment variable {key} is not set. Check backend/.env")
        sys.exit(1)
    return val


def main() -> None:
    # ── Source: local PersistentClient ───────────────────────────────────────
    local_path = os.environ.get("CHROMA_DB_PATH", "./data/chroma_db")
    if not Path(local_path).exists():
        print(f"[ERROR] Local ChromaDB not found at: {local_path}")
        print("        Run ingest_documents.py first, or check CHROMA_DB_PATH in .env")
        sys.exit(1)

    print(f"[INFO] Connecting to local ChromaDB at: {local_path}")
    local_client = chromadb.PersistentClient(
        path=local_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    try:
        local_col = local_client.get_collection(COLLECTION_NAME)
    except Exception:
        print(f"[ERROR] Collection '{COLLECTION_NAME}' not found in local ChromaDB.")
        print("        Run ingest_documents.py first.")
        sys.exit(1)

    total = local_col.count()
    print(f"[INFO] Local collection has {total:,} chunks.")
    if total == 0:
        print("[WARN] Nothing to migrate.")
        return

    # ── Destination: Chroma Cloud ─────────────────────────────────────────────
    api_key  = _require_env("CHROMA_CLOUD_API_KEY")
    tenant   = _require_env("CHROMA_CLOUD_TENANT")
    database = os.environ.get("CHROMA_CLOUD_DATABASE", "default_database")

    print(f"[INFO] Connecting to Chroma Cloud (tenant={tenant}, database={database}) ...")
    cloud_client = chromadb.CloudClient(
        tenant=tenant,
        database=database,
        api_key=api_key,
    )

    cloud_col = cloud_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    existing_cloud = cloud_col.count()
    print(f"[INFO] Cloud collection currently has {existing_cloud:,} chunks.")

    # ── Migrate in batches ────────────────────────────────────────────────────
    offset = 0
    migrated = 0
    skipped = 0

    print(f"[INFO] Starting migration in batches of {BATCH_SIZE} ...")

    while offset < total:
        # Fetch a batch from local (with embeddings)
        batch = local_col.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )

        ids        = batch["ids"]
        documents  = batch["documents"]
        metadatas  = batch["metadatas"]
        embeddings = batch["embeddings"]

        if not ids:
            break

        # Check which IDs already exist in cloud to stay idempotent
        existing = cloud_col.get(ids=ids, include=[])
        existing_ids = set(existing["ids"])
        new_mask = [i for i, id_ in enumerate(ids) if id_ not in existing_ids]

        if new_mask:
            cloud_col.add(
                ids        = [ids[i]        for i in new_mask],
                documents  = [documents[i]  for i in new_mask],
                metadatas  = [metadatas[i]  for i in new_mask],
                embeddings = [embeddings[i] for i in new_mask],
            )
            migrated += len(new_mask)

        skipped += len(ids) - len(new_mask)
        offset  += len(ids)

        pct = min(offset, total) / total * 100
        print(f"  [{pct:5.1f}%]  {offset:,}/{total:,}  — migrated {migrated:,}, skipped {skipped:,} (already in cloud)")

    # ── Verify ────────────────────────────────────────────────────────────────
    final_cloud = cloud_col.count()
    print(f"\n[DONE] Migration complete.")
    print(f"       Local chunks  : {total:,}")
    print(f"       Cloud chunks  : {final_cloud:,}")
    if final_cloud >= total:
        print("       ✓ All chunks are present in Chroma Cloud.")
    else:
        print(f"       ⚠ Cloud has fewer chunks ({final_cloud}) than local ({total}). Re-run to retry.")


if __name__ == "__main__":
    main()
