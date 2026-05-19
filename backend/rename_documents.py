"""
Rename documents by appending the year code to the filename stem.

Examples (year folder hhb-e_2324 → year code 2324):
    Document/txt/hhb-e_2324/2_HHB001.pdf.txt  ->  2_HHB001_2324.pdf.txt
    Document/pdf/hhb-e_2324/2_HHB001.pdf      ->  2_HHB001_2324.pdf

Run from the backend/ directory:
    python rename_documents.py            # dry run — prints what would change
    python rename_documents.py --apply    # actually rename the files

After running with --apply, update the knowledge base:
    python ingest_documents.py            # re-ingests only the renamed files (no --force needed)
"""
import re
import argparse
from pathlib import Path

DOCUMENTS_DIR = Path(__file__).parent.parent / "Document"


def _year_code(folder_name: str) -> str:
    """Extract 4-digit year code from a folder name like 'hhb-e_2324' -> '2324'."""
    m = re.search(r"_(\d{4})$", folder_name)
    return m.group(1) if m else ""


def _rename_txt_folder(folder: Path, year_code: str, apply: bool) -> int:
    """
    Rename *.pdf.txt files in folder.
    '2_HHB001.pdf.txt' -> '2_HHB001_2324.pdf.txt'
    Returns count of files renamed (or that would be renamed).
    """
    count = 0
    for f in sorted(folder.glob("*.pdf.txt")):
        # stem_base is everything before the double extension .pdf.txt
        stem_base = f.name[: -len(".pdf.txt")]
        if stem_base.endswith(f"_{year_code}"):
            continue  # already renamed
        new_name = f"{stem_base}_{year_code}.pdf.txt"
        new_path = f.parent / new_name
        action = "RENAME" if apply else "WOULD RENAME"
        print(f"  {action}: {f.name}  ->  {new_name}")
        if apply:
            f.rename(new_path)
        count += 1
    return count


def _rename_pdf_folder(folder: Path, year_code: str, apply: bool) -> int:
    """
    Rename *.pdf files in folder.
    '2_HHB001.pdf' -> '2_HHB001_2324.pdf'
    Returns count of files renamed (or that would be renamed).
    """
    count = 0
    for f in sorted(folder.glob("*.pdf")):
        stem_base = f.stem  # e.g. '2_HHB001'
        if stem_base.endswith(f"_{year_code}"):
            continue  # already renamed
        new_name = f"{stem_base}_{year_code}.pdf"
        new_path = f.parent / new_name
        action = "RENAME" if apply else "WOULD RENAME"
        print(f"  {action}: {f.name}  ->  {new_name}")
        if apply:
            f.rename(new_path)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append year codes to document filenames."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename the files. Without this flag the script is a dry run.",
    )
    args = parser.parse_args()

    if not args.apply:
        print("=== DRY RUN — pass --apply to rename files ===\n")

    total = 0

    # ── TXT files ─────────────────────────────────────────────────────────────
    txt_root = DOCUMENTS_DIR / "txt"
    if txt_root.exists():
        for year_dir in sorted(txt_root.iterdir()):
            if not year_dir.is_dir():
                continue
            yc = _year_code(year_dir.name)
            if not yc:
                print(f"\n[txt/{year_dir.name}]  SKIP — could not parse year code")
                continue
            print(f"\n[txt/{year_dir.name}]  (year code: {yc})")
            total += _rename_txt_folder(year_dir, yc, args.apply)
    else:
        print(f"WARNING: txt folder not found at {txt_root}")

    # ── PDF files ─────────────────────────────────────────────────────────────
    pdf_root = DOCUMENTS_DIR / "pdf"
    if pdf_root.exists():
        for year_dir in sorted(pdf_root.iterdir()):
            if not year_dir.is_dir():
                continue
            yc = _year_code(year_dir.name)
            if not yc:
                print(f"\n[pdf/{year_dir.name}]  SKIP — could not parse year code")
                continue
            print(f"\n[pdf/{year_dir.name}]  (year code: {yc})")
            total += _rename_pdf_folder(year_dir, yc, args.apply)
    else:
        print(f"WARNING: pdf folder not found at {pdf_root}")

    verb = "Renamed" if args.apply else "Would rename"
    print(f"\n{verb}: {total} file(s)")

    if not args.apply and total > 0:
        print("\nTo apply, run:")
        print("  python rename_documents.py --apply")
        print("\nThen update the knowledge base:")
        print("  python ingest_documents.py")


if __name__ == "__main__":
    main()
