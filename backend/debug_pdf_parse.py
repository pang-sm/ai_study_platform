"""
Diagnostic script for investigating PDF parse failures.
Uses raw SQL to avoid model-column mismatches with local SQLite.
Usage:
  python backend/debug_pdf_parse.py --subject "C语言"
  python backend/debug_pdf_parse.py --material-id 123
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Constants from main.py
MAX_PDF_CHARS = 12000
MIN_PDF_AVG_PAGE_CHARS = 120


def is_pdf_text_usable(extracted_text: str, total_pages: int) -> bool:
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return False
    checked_pages = max(1, min(total_pages or 1, 15))
    return len(cleaned) / checked_pages >= MIN_PDF_AVG_PAGE_CHARS


def get_db_path():
    script_dir = Path(__file__).resolve().parent
    db_path = script_dir / "app.db"
    if db_path.exists():
        return str(db_path)
    # Try relative from cwd
    cwd_db = Path.cwd() / "backend" / "app.db"
    if cwd_db.exists():
        return str(cwd_db)
    return None


COLS = [
    "id", "username", "subject", "file_type", "original_filename",
    "file_size", "file_hash", "file_path", "extracted_text", "summary",
    "parse_status", "parse_error", "extract_method", "qwen_used",
    "total_pages", "parsed_pages", "chunk_count", "ocr_required",
    "parse_progress", "parse_completed_at", "created_at", "is_deleted",
]


def diagnose_db(db_path, subject=None, material_id=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Check available columns
        info = conn.execute("PRAGMA table_info(study_materials)").fetchall()
        available_cols = {row[1] for row in info}
        cols_to_select = [c for c in COLS if c in available_cols]

        where = ["is_deleted = 0"]
        params = []
        if subject:
            where.append("subject = ?")
            params.append(subject)
        if material_id:
            where.append("id = ?")
            params.append(material_id)

        sql = f"SELECT {', '.join(cols_to_select)} FROM study_materials WHERE {' AND '.join(where)} ORDER BY id"
        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print("NO MATERIALS FOUND")
            # Show all distinct subjects
            subjects = conn.execute("SELECT DISTINCT subject FROM study_materials WHERE is_deleted = 0").fetchall()
            print(f"Available subjects: {[s[0] for s in subjects]}")
            return

        success_list = []
        failed_list = []
        other_list = []

        for row in rows:
            r = dict(row)
            status = r.get("parse_status") or "unknown"
            text = r.get("extracted_text") or ""
            pages = r.get("total_pages") or 0
            data = {
                "id": r["id"],
                "filename": r.get("original_filename", "?"),
                "file_type": r.get("file_type", "?"),
                "file_size": r.get("file_size") or 0,
                "total_pages": pages,
                "extracted_text_len": len(text),
                "extracted_text_preview": text[:200] if text else "",
                "chunk_count": r.get("chunk_count") or 0,
                "parse_status": status,
                "parse_error": r.get("parse_error") or "",
                "file_path": r.get("file_path") or "",
                "extract_method": r.get("extract_method") or "",
                "qwen_used": r.get("qwen_used") or 0,
                "ocr_required": r.get("ocr_required") or 0,
                "parse_progress": r.get("parse_progress") or 0,
                "avg_chars_per_page": len(text) / max(1, pages),
                "is_text_usable": is_pdf_text_usable(text, pages) if r.get("file_type") == "pdf" else "N/A",
            }
            if status in ("success", "indexed"):
                success_list.append(data)
            elif status == "failed":
                failed_list.append(data)
            else:
                other_list.append(data)

        print(f"\n{'='*80}")
        print(f"TOTAL: {len(rows)} | SUCCESS: {len(success_list)} | FAILED: {len(failed_list)} | OTHER: {len(other_list)}")
        print(f"{'='*80}")

        if success_list:
            print("\n--- SUCCESSFUL PDFs ---")
            for d in success_list:
                print(f"  [{d['id']}] {d['filename']}")
                print(f"      size={d['file_size']}B pages={d['total_pages']} text_len={d['extracted_text_len']} chunks={d['chunk_count']} avg_chars/page={d['avg_chars_per_page']:.1f} usable={d['is_text_usable']}")
                print(f"      method={d['extract_method']} qwen={d['qwen_used']} ocr={d['ocr_required']}")
                print(f"      path={d['file_path']}")
                if d['extracted_text_preview']:
                    print(f"      text: {d['extracted_text_preview'][:120]}...")

        if failed_list:
            print("\n--- FAILED PDFs ---")
            for d in failed_list:
                print(f"  [{d['id']}] {d['filename']}")
                print(f"      size={d['file_size']}B pages={d['total_pages']} text_len={d['extracted_text_len']} chunks={d['chunk_count']} avg_chars/page={d['avg_chars_per_page']:.1f} usable={d['is_text_usable']}")
                print(f"      method={d['extract_method']} qwen={d['qwen_used']} ocr={d['ocr_required']}")
                print(f"      error: {d['parse_error']}")
                print(f"      path={d['file_path']}")
                if d['extracted_text_preview']:
                    print(f"      text: {d['extracted_text_preview'][:120]}...")

                # Warnings
                if d['chunk_count'] > 0:
                    print(f"      ** WARNING: has {d['chunk_count']} chunks but status=failed **")
                if d['extracted_text_len'] > 0:
                    print(f"      ** WARNING: has {d['extracted_text_len']} chars text but status=failed **")

        if other_list:
            print("\n--- OTHER STATUS ---")
            for d in other_list:
                print(f"  [{d['id']}] {d['filename']} status={d['parse_status']} chunks={d['chunk_count']} text_len={d['extracted_text_len']} error={d['parse_error'][:100] if d['parse_error'] else ''}")

        # Analysis
        if failed_list and success_list:
            print("\n--- COMPARISON ---")
            ss = [d['file_size'] for d in success_list]
            fs = [d['file_size'] for d in failed_list]
            print(f"  Size (B):  success [{min(ss)}-{max(ss)}] vs failed [{min(fs)}-{max(fs)}]")

            sp = [d['total_pages'] for d in success_list]
            fp = [d['total_pages'] for d in failed_list]
            print(f"  Pages:     success [{min(sp)}-{max(sp)}] vs failed [{min(fp)}-{max(fp)}]")

            st = [d['extracted_text_len'] for d in success_list]
            ft = [d['extracted_text_len'] for d in failed_list]
            print(f"  Text len:  success [{min(st)}-{max(st)}] vs failed [{min(ft)}-{max(ft)}]")

            sa = [d['avg_chars_per_page'] for d in success_list]
            fa = [d['avg_chars_per_page'] for d in failed_list]
            print(f"  Avg chars/page: success [{min(sa):.1f}-{max(sa):.1f}] vs failed [{min(fa):.1f}-{max(fa):.1f}]")

            # Error distribution
            err_counts = {}
            for d in failed_list:
                e = d['parse_error'][:100] if d['parse_error'] else "(empty)"
                err_counts[e] = err_counts.get(e, 0) + 1
            print(f"\n  Errors:")
            for err, cnt in sorted(err_counts.items(), key=lambda x: -x[1]):
                print(f"    [{cnt}x] {err}")

            text_but_failed = [d for d in failed_list if d['extracted_text_len'] > 0]
            chunks_but_failed = [d for d in failed_list if d['chunk_count'] > 0]
            if text_but_failed:
                print(f"\n  ** {len(text_but_failed)} failed PDFs have extracted text (status bug?) **")
            if chunks_but_failed:
                print(f"\n  ** {len(chunks_but_failed)} failed PDFs have chunks (status bug?) **")

        # Check file existence
        print("\n--- DISK CHECK ---")
        base_dir = Path(db_path).parent
        for d in failed_list + success_list:
            fp = d['file_path']
            if fp:
                full = base_dir / fp
                exists = full.exists()
                if not exists and d['parse_status'] == 'failed':
                    print(f"  [{d['id']}] MISSING: {fp}")

    finally:
        conn.close()


def diagnose_file(file_path_str):
    """Diagnose a single PDF file on disk."""
    from io import BytesIO

    file_path = Path(file_path_str)
    print(f"File: {file_path}")
    print(f"Exists: {file_path.exists()}")
    if not file_path.exists():
        return

    file_bytes = file_path.read_bytes()
    print(f"Size: {len(file_bytes)} bytes ({len(file_bytes)/1024:.1f} KB)")

    # PyMuPDF
    import fitz
    print("\n--- PyMuPDF (fitz) ---")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total = len(doc)
        print(f"Pages: {total}")
        text_parts = []
        total_chars = 0
        for i in range(total):
            try:
                t = (doc.load_page(i).get_text("text") or "").strip()
            except Exception as exc:
                t = ""
                print(f"  Page {i+1}: ERROR - {exc}")
            l = len(t)
            total_chars += l
            text_parts.append(t)
            if i < 5:  # Show first 5 pages
                print(f"  Page {i+1}: {l} chars")
                if t:
                    print(f"    {t[:120]}...")
            elif i == 5:
                print(f"  ... (showing first 5 pages of {total})")
        doc.close()
        combined = "\n".join(text_parts)
        avg = total_chars / max(1, total)
        usable = is_pdf_text_usable(combined, total)
        print(f"Total chars: {total_chars}, avg/page: {avg:.1f}")
        print(f"is_pdf_text_usable: {usable} (threshold: {MIN_PDF_AVG_PAGE_CHARS} chars/page)")
        if not usable:
            print(f"  -> Would trigger OCR fallback!")
    except Exception as e:
        print(f"PyMuPDF ERROR: {e}")
        import traceback
        traceback.print_exc()

    # pypdf
    from pypdf import PdfReader
    print("\n--- pypdf ---")
    try:
        reader = PdfReader(BytesIO(file_bytes))
        total = len(reader.pages)
        print(f"Pages: {total}")
        text_parts = []
        total_chars = 0
        for i in range(total):
            try:
                t = (reader.pages[i].extract_text() or "").strip()
            except Exception as exc:
                t = ""
                print(f"  Page {i+1}: ERROR - {exc}")
            l = len(t)
            total_chars += l
            text_parts.append(t)
            if i < 5:
                print(f"  Page {i+1}: {l} chars")
                if t:
                    print(f"    {t[:120]}...")
            elif i == 5:
                print(f"  ... (showing first 5 pages of {total})")
        combined = "\n".join(text_parts)
        avg = total_chars / max(1, total)
        usable = is_pdf_text_usable(combined, total)
        print(f"Total chars: {total_chars}, avg/page: {avg:.1f}")
        print(f"is_pdf_text_usable: {usable} (threshold: {MIN_PDF_AVG_PAGE_CHARS} chars/page)")
    except Exception as e:
        print(f"pypdf ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", type=str, default=None)
    parser.add_argument("--material-id", type=int, default=None)
    parser.add_argument("--file", type=str, default=None)
    args = parser.parse_args()

    if args.file:
        diagnose_file(args.file)
    else:
        db_path = get_db_path()
        if not db_path:
            print("ERROR: Cannot find app.db")
            sys.exit(1)
        print(f"Database: {db_path}")
        diagnose_db(db_path, subject=args.subject, material_id=args.material_id)
