"""
Batch ingestion script — processes all documents under the Document/ folder.

Folder structure expected:
    Document/
      txt/
        hhb-e_2324/   ← pre-extracted .pdf.txt files (preferred)
        hhb-e_2425/
        hhb-e_2526/
      pdf/
        hhb-e_2324/   ← original PDFs (used when no txt equivalent)
        hhb-e_2425/
        hhb-e_2526/

Run from the backend/ directory:
    python ingest_documents.py [--force]

Options:
    --force    Re-ingest documents that are already in the knowledge base.
"""
import sys
import os
import re
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.ingestion import IngestionService

DOCUMENTS_DIR = Path(__file__).parent.parent / "Document"
BATCH_SIZE = 50  # Print a checkpoint every N documents

# Map 4-digit year codes in folder names to human-readable strings
YEAR_CODE_MAP: dict[str, str] = {
    "2324": "2023-2024",
    "2425": "2024-2025",
    "2526": "2025-2026",
    "2627": "2026-2027",
    "2728": "2027-2028",
}


def parse_year(folder_name: str) -> str:
    """Extract a readable year string from a folder name like 'hhb-e_2324'."""
    m = re.search(r"_(\d{4})$", folder_name)
    if m:
        return YEAR_CODE_MAP.get(m.group(1), m.group(1))
    return ""


def build_metadata(folder_name: str) -> dict:
    return {
        "doc_type": "Official Reply",
        "topic": "Legislative Council Written Reply",
        "date": parse_year(folder_name),
        "tone": "Formal",
        "department": "Government",
        "language": "English",
    }


def collect_files() -> list[tuple[Path, dict]]:
    """
    Walk Document/txt/ and return all pre-extracted text files.
    Returns a list of (file_path, metadata) tuples.
    """
    entries: list[tuple[Path, dict]] = []

    # ── Pre-extracted text files ─────────────────────────────────────────────
    txt_root = DOCUMENTS_DIR / "txt"
    if txt_root.exists():
        for year_dir in sorted(txt_root.iterdir()):
            if not year_dir.is_dir():
                continue
            meta = build_metadata(year_dir.name)
            for txt_file in sorted(year_dir.glob("*.txt")):
                entries.append((txt_file, meta))

    return entries


def main(force: bool = False) -> None:
    svc = IngestionService()

    # Build a set of sources already in the KB (by filename) so we can skip them
    existing_sources: set[str] = set()
    if not force:
        for doc in svc.list_documents():
            existing_sources.add(doc["source"])

    all_files = collect_files()
    if not all_files:
        print(f"No documents found under {DOCUMENTS_DIR}")
        return

    total = len(all_files)
    to_skip = [f for f, _ in all_files if f.name in existing_sources]
    to_ingest = [(f, m) for f, m in all_files if f.name not in existing_sources]

    print(f"Documents found   : {total}")
    print(f"Already ingested  : {len(to_skip)}  (use --force to re-ingest)")
    print(f"To ingest now     : {len(to_ingest)}\n")

    if not to_ingest:
        print("Knowledge base is already up to date.")
        print(f"Total KB documents: {len(svc.list_documents())}")
        return

    success = failed = 0
    for i, (file_path, metadata) in enumerate(to_ingest, 1):
        label = f"[{file_path.parent.name}] {file_path.name}"
        print(f"  [{i:4d}/{len(to_ingest)}] {label} ... ", end="", flush=True)
        try:
            result = svc.ingest_file(str(file_path), metadata=metadata)
            print(f"OK ({result['chunks']} chunks)")
            success += 1
        except Exception as exc:
            print(f"FAILED — {exc}")
            failed += 1

        if i % BATCH_SIZE == 0:
            print(f"\n  ── checkpoint {i}/{len(to_ingest)}: {success} OK, {failed} failed ──\n")

    print(f"\nIngestion complete: {success} succeeded, {failed} failed.")
    print(f"Total KB documents: {len(svc.list_documents())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB.")
    parser.add_argument("--force", action="store_true", help="Re-ingest already-ingested documents.")
    args = parser.parse_args()
    main(force=args.force)
