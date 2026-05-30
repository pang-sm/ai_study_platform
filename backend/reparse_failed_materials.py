"""
Batch reparse failed materials.

Usage:
  # List ALL failed materials (any subject)
  python backend/reparse_failed_materials.py --all-failed

  # Dry-run for a specific subject (exact match)
  python backend/reparse_failed_materials.py --subject "C语言"

  # Contains match (for "C 语言", "C语言程序设计" etc.)
  python backend/reparse_failed_materials.py --subject-contains "C语言"

  # Single material by ID (dry-run first, then execute)
  python backend/reparse_failed_materials.py --material-id 42
  python backend/reparse_failed_materials.py --material-id 42 --execute

  # Batch execute
  python backend/reparse_failed_materials.py --subject "C语言" --execute
"""

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import SessionLocal, init_user_profile_schema
import models
from subjects import normalize_subject


def _ensure_schema():
    init_user_profile_schema()


def utc_now():
    return datetime.now(timezone.utc)


def serialize_datetime(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _resolve_stored_file_path(stored_file_path: str) -> Path:
    from main import resolve_stored_file_path
    return resolve_stored_file_path(stored_file_path)


def _get_available_columns(db):
    """Return the set of column names actually present in study_materials."""
    result = db.execute(db.query(models.StudyMaterial).limit(0))
    return set(result.keys()) if result.returns_rows else set()


def _diagnose_pdf(file_bytes, label=""):
    """Run both PyMuPDF and pypdf on a PDF and return diagnostic info."""
    info = {"fitz_chars": 0, "pypdf_chars": 0, "fitz_pages": 0, "pypdf_pages": 0, "fitz_error": None, "pypdf_error": None}

    import fitz
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        info["fitz_pages"] = len(doc)
        chars = 0
        for i in range(len(doc)):
            try:
                t = (doc.load_page(i).get_text("text") or "").strip()
            except Exception:
                t = ""
            chars += len(t)
        doc.close()
        info["fitz_chars"] = chars
    except Exception as e:
        info["fitz_error"] = str(e)[:120]

    from pypdf import PdfReader
    from io import BytesIO
    try:
        reader = PdfReader(BytesIO(file_bytes))
        info["pypdf_pages"] = len(reader.pages)
        chars = 0
        for page in reader.pages:
            try:
                t = (page.extract_text() or "").strip()
            except Exception:
                t = ""
            chars += len(t)
        info["pypdf_chars"] = chars
    except Exception as e:
        info["pypdf_error"] = str(e)[:120]

    return info


def _reparse_one(db, material, verbose=False):
    """Reparse a single material, mirroring POST /materials/{id}/reparse."""
    from main import (
        extract_pdf_pages,
        build_pdf_text_from_pages,
        is_pdf_text_usable,
        complete_material_with_local_pdf_text,
        parse_scanned_pdf_in_background,
        update_material_parse_state,
        replace_material_chunks,
        extract_image_text,
        parse_image_with_qwen,
        SCANNED_PDF_PAGE_PROMPT,
        is_qwen_enabled,
    )

    material_id = material.id
    result = {
        "id": material_id,
        "filename": material.original_filename,
        "subject": material.subject,
        "file_type": material.file_type,
        "old_status": material.parse_status,
        "old_error": material.parse_error or "",
        "new_status": None,
        "new_error": None,
        "chunk_count": 0,
        "total_pages": 0,
        "extracted_text_len": 0,
        "is_text_usable": None,
        "used_ocr": False,
        "fitz_chars": 0,
        "pypdf_chars": 0,
    }

    file_path = _resolve_stored_file_path(material.file_path)
    if verbose:
        print(f"    file_path: {file_path}")
        print(f"    file_exists: {file_path.exists()}")

    if not file_path.exists() or not file_path.is_file():
        material.parse_status = "failed"
        material.parse_error = "上传文件不存在，无法重新解析。"
        db.commit()
        result["new_status"] = "failed"
        result["new_error"] = material.parse_error
        return result

    try:
        file_bytes = file_path.read_bytes()
    except Exception as exc:
        material.parse_status = "failed"
        material.parse_error = f"读取原文件失败：{str(exc)[:100]}"
        db.commit()
        result["new_status"] = "failed"
        result["new_error"] = material.parse_error
        return result

    if verbose:
        print(f"    file_size: {len(file_bytes)} bytes ({len(file_bytes)/1024:.1f} KB)")

    file_type = (material.file_type or "").lower()
    original_filename = material.original_filename or ""

    # PDF diagnostic
    if file_type == "pdf" and verbose:
        diag = _diagnose_pdf(file_bytes)
        result["fitz_chars"] = diag["fitz_chars"]
        result["pypdf_chars"] = diag["pypdf_chars"]
        print(f"    PyMuPDF: {diag['fitz_pages']} pages, {diag['fitz_chars']} chars" + (f" ERROR: {diag['fitz_error']}" if diag['fitz_error'] else ""))
        print(f"    pypdf:    {diag['pypdf_pages']} pages, {diag['pypdf_chars']} chars" + (f" ERROR: {diag['pypdf_error']}" if diag['pypdf_error'] else ""))

    material.parse_status = "parsing"
    material.parse_error = None
    material.parse_progress = 1
    material.parse_started_at = serialize_datetime(utc_now())
    db.commit()
    db.refresh(material)

    try:
        if file_type == "pdf":
            total_pages, page_texts = extract_pdf_pages(file_bytes)
            extracted_text = build_pdf_text_from_pages(page_texts)
            is_text = is_pdf_text_usable(extracted_text, total_pages)

            result["total_pages"] = total_pages
            result["extracted_text_len"] = len(extracted_text)
            result["is_text_usable"] = is_text

            if verbose:
                avg = len(extracted_text) / max(1, total_pages) if total_pages > 0 else 0
                print(f"    extract_pdf_pages: {total_pages} total pages, {len(page_texts)} pages with text")
                print(f"    extracted_text: {len(extracted_text)} chars, avg {avg:.1f} chars/page")
                print(f"    is_text_usable: {is_text} (MIN_PDF_MIN_TEXT_CHARS=100, MIN_PDF_AVG_PAGE_CHARS=30)")
                print(f"    QWEN_ENABLED: {is_qwen_enabled()}")

            update_material_parse_state(
                db, material_id,
                total_pages=total_pages,
                parse_progress=20,
                parsed_pages=0,
                ocr_required=0 if is_text else 1,
            )

            if is_text:
                if verbose:
                    print(f"    -> local text path (complete_material_with_local_pdf_text)")
                material, chunk_count = complete_material_with_local_pdf_text(
                    db, material, extracted_text, total_pages,
                )
                result["new_status"] = "success"
                result["chunk_count"] = chunk_count
            else:
                if verbose:
                    print(f"    -> OCR path (parse_scanned_pdf_in_background)")
                result["used_ocr"] = True
                parse_scanned_pdf_in_background(db, material, file_bytes, extracted_text)
                db.refresh(material)
                result["new_status"] = material.parse_status or "unknown"
                result["new_error"] = material.parse_error or ""
                result["chunk_count"] = material.chunk_count or 0

        elif file_type == "image":
            if verbose:
                print(f"    -> image path")
            extracted_text = extract_image_text(file_bytes)
            if (extracted_text or "").strip():
                update_material_parse_state(
                    db, material_id,
                    extracted_text=extracted_text,
                    extract_method="local",
                    parse_progress=40,
                )
                chunk_count = replace_material_chunks(db, material)
                update_material_parse_state(
                    db, material_id,
                    parse_status="success",
                    parse_progress=100,
                    parse_completed_at=serialize_datetime(utc_now()),
                    chunk_count=chunk_count,
                )
                result["new_status"] = "success"
                result["chunk_count"] = chunk_count
            else:
                update_material_parse_state(db, material_id, parse_status="parsing", parse_progress=10)
                from main import get_material_for_parsing
                material = get_material_for_parsing(db, material_id)
                qwen_result = parse_image_with_qwen(str(file_path), prompt=SCANNED_PDF_PAGE_PROMPT)
                qwen_text = (qwen_result.get("extracted_text") or "").strip()
                if qwen_result.get("success") and qwen_text:
                    update_material_parse_state(
                        db, material_id,
                        extracted_text=qwen_text,
                        extract_method="qwen",
                        qwen_used=True,
                        parse_progress=50,
                    )
                    chunk_count = replace_material_chunks(db, material)
                    update_material_parse_state(
                        db, material_id,
                        parse_status="success",
                        parse_progress=100,
                        parse_completed_at=serialize_datetime(utc_now()),
                        chunk_count=chunk_count,
                    )
                    result["new_status"] = "success"
                    result["chunk_count"] = chunk_count
                else:
                    update_material_parse_state(
                        db, material_id,
                        parse_status="failed",
                        parse_error=qwen_result.get("error") or "图片 OCR 解析失败",
                        parse_progress=0,
                        parse_completed_at=serialize_datetime(utc_now()),
                    )
                    result["new_status"] = "failed"
                    result["new_error"] = qwen_result.get("error") or "图片 OCR 解析失败"

        elif file_type in ("docx", "pptx", "text", "code"):
            from document_parser import extract_supported_file_text
            doc_result = extract_supported_file_text(file_bytes, original_filename)
            extracted_text = doc_result["text"]
            if verbose:
                print(f"    -> document path, text_len={len(extracted_text)}")
            if (extracted_text or "").strip():
                update_material_parse_state(
                    db, material_id,
                    extracted_text=extracted_text,
                    extract_method="local",
                    parse_progress=40,
                )
                chunk_count = replace_material_chunks(db, material)
                update_material_parse_state(
                    db, material_id,
                    parse_status="success",
                    parse_progress=100,
                    parse_completed_at=serialize_datetime(utc_now()),
                    chunk_count=chunk_count,
                )
                result["new_status"] = "success"
                result["chunk_count"] = chunk_count
            else:
                update_material_parse_state(
                    db, material_id,
                    parse_status="failed",
                    parse_error="文件内容为空，无法解析。",
                    parse_progress=0,
                    parse_completed_at=serialize_datetime(utc_now()),
                )
                result["new_status"] = "failed"
                result["new_error"] = "文件内容为空，无法解析。"

        else:
            update_material_parse_state(
                db, material_id,
                parse_status="failed",
                parse_error=f"暂不支持 {file_type} 类型的重新解析。",
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
            result["new_status"] = "failed"
            result["new_error"] = f"暂不支持 {file_type} 类型"

    except Exception as exc:
        err_msg = f"重新解析异常：{str(exc)[:200]}"
        try:
            update_material_parse_state(
                db, material_id,
                parse_status="failed",
                parse_error=err_msg,
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
        except Exception:
            pass
        result["new_status"] = "failed"
        result["new_error"] = err_msg
        result["_traceback"] = traceback.format_exc()

    db.refresh(material)
    result["new_status"] = material.parse_status or "unknown"
    result["new_error"] = material.parse_error or ""
    result["chunk_count"] = material.chunk_count or 0
    return result


# ── Query helpers ──

def _query_materials(db, subject=None, subject_contains=None, material_id=None, statuses=None):
    """Flexible query for materials."""
    q = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.is_deleted.is_(False),
    )

    if material_id:
        q = q.filter(models.StudyMaterial.id == material_id)
    elif subject:
        canonical = normalize_subject(subject)
        q = q.filter(models.StudyMaterial.subject == canonical)
    elif subject_contains:
        q = q.filter(models.StudyMaterial.subject.contains(subject_contains))

    if statuses:
        q = q.filter(models.StudyMaterial.parse_status.in_(statuses))
    else:
        q = q.filter(models.StudyMaterial.parse_status == "failed")

    return q.order_by(models.StudyMaterial.id).all()


def _show_all_subjects(db):
    """Show all distinct subjects in the database."""
    rows = (
        db.query(models.StudyMaterial.subject)
        .filter(models.StudyMaterial.is_deleted.is_(False))
        .distinct()
        .all()
    )
    print("数据库中所有课程 subject：")
    for (s,) in rows:
        total = (
            db.query(models.StudyMaterial)
            .filter(models.StudyMaterial.subject == s, models.StudyMaterial.is_deleted.is_(False))
            .count()
        )
        failed = (
            db.query(models.StudyMaterial)
            .filter(models.StudyMaterial.subject == s, models.StudyMaterial.parse_status == "failed", models.StudyMaterial.is_deleted.is_(False))
            .count()
        )
        print(f"  subject='{s}'  共 {total} 份  failed={failed}")


def _print_material_detail(m, idx=None):
    """Print a single material with all diagnostic fields."""
    prefix = f"  [{m.id}]" if idx is None else f"  [{idx}][{m.id}]"
    print(f"{prefix} {m.original_filename}")
    print(f"      subject:      {m.subject}")
    print(f"      file_type:    {m.file_type}")
    print(f"      file_size:    {m.file_size} bytes ({m.file_size/1024:.1f} KB)" if m.file_size else f"      file_size:    {m.file_size}")
    print(f"      parse_status: {m.parse_status}")
    print(f"      parse_error:  {(m.parse_error or '')[:150]}")
    print(f"      chunk_count:  {m.chunk_count or 0}")
    print(f"      file_path:    {m.file_path}")
    print(f"      total_pages:  {m.total_pages or 0}")
    print(f"      extract_method: {m.extract_method or ''}")
    print(f"      qwen_used:    {m.qwen_used}")
    print(f"      ocr_required: {m.ocr_required}")
    print(f"      updated_at:   {m.updated_at}")

    # Check if file exists on disk
    if m.file_path:
        p = _resolve_stored_file_path(m.file_path)
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        print(f"      file_on_disk: {'EXISTS' if exists else 'MISSING'} ({size} bytes)")

    # Check extracted_text
    text = m.extracted_text or ""
    print(f"      extracted_text: {len(text)} chars" + (f"  preview: {text[:100]}..." if text else ""))


def run(args):
    _ensure_schema()
    db = SessionLocal()

    try:
        # ── Mode: show all subjects ──
        if args.list_subjects:
            _show_all_subjects(db)
            return

        # ── Mode: all-failed ──
        if args.all_failed:
            materials = _query_materials(db, statuses=["failed"])
            if not materials:
                materials = _query_materials(db, statuses=["failed", "parsing", "pending"])
            print(f"所有课程 failed/pending 资料: {len(materials)} 份\n")
            for m in materials:
                _print_material_detail(m)
            if not materials:
                _show_all_subjects(db)
            return

        # ── Mode: single material-id ──
        if args.material_id:
            materials = _query_materials(db, material_id=args.material_id)
            if not materials:
                print(f"未找到 material_id={args.material_id} 的资料。")
                _show_all_subjects(db)
                return

            m = materials[0]
            print(f"资料详情：")
            _print_material_detail(m)

            if args.dry_run:
                print(f"\n--- dry-run，未执行 ---")
                print(f"执行: python backend/reparse_failed_materials.py --material-id {args.material_id} --execute")
                return

            print(f"\n开始重新解析...")
            result = _reparse_one(db, m, verbose=True)
            print(f"\n结果：")
            print(f"  状态: {result['old_status']} -> {result['new_status']}")
            print(f"  chunks: {result['chunk_count']}")
            print(f"  total_pages: {result['total_pages']}")
            print(f"  extracted_text: {result['extracted_text_len']} chars")
            print(f"  is_text_usable: {result['is_text_usable']}")
            print(f"  used_ocr: {result['used_ocr']}")
            if result.get("fitz_chars") or result.get("pypdf_chars"):
                print(f"  fitz_chars: {result['fitz_chars']}, pypdf_chars: {result['pypdf_chars']}")
            if result["new_error"]:
                print(f"  error: {result['new_error']}")
            if result.get("_traceback"):
                print(f"\n完整 traceback:\n{result['_traceback']}")
            return

        # ── Mode: subject or subject-contains ──
        materials = []
        search_desc = ""

        if args.subject:
            canonical = normalize_subject(args.subject)
            search_desc = f"subject='{canonical}'"
            materials = _query_materials(db, subject=args.subject, statuses=["failed"])
            if not materials:
                materials = _query_materials(db, subject=args.subject, statuses=["failed", "parsing", "pending"])

        elif args.subject_contains:
            search_desc = f"subject 包含 '{args.subject_contains}'"
            materials = _query_materials(db, subject_contains=args.subject_contains, statuses=["failed"])
            if not materials:
                materials = _query_materials(db, subject_contains=args.subject_contains, statuses=["failed", "parsing", "pending"])

        if not materials:
            print(f"未找到匹配 {search_desc} 的需要重新解析的资料。\n")
            _show_all_subjects(db)
            return

        canonical_subject = materials[0].subject
        print(f"课程: {canonical_subject}")
        print(f"找到 {len(materials)} 份需要重新解析的资料：\n")
        for i, m in enumerate(materials, 1):
            _print_material_detail(m, idx=i)

        if args.dry_run:
            print(f"\n--- dry-run，共 {len(materials)} 份，未执行 ---")
            print(f"执行: python backend/reparse_failed_materials.py --subject '{canonical_subject}' --execute")
            return

        # ── Execute ──
        print(f"\n开始重新解析 {len(materials)} 份资料...\n")

        results = []
        for i, material in enumerate(materials, 1):
            filename = material.original_filename
            print(f"[{i}/{len(materials)}] [{material.id}] {filename}")
            try:
                result = _reparse_one(db, material, verbose=args.verbose)
                results.append(result)
                icon = "OK" if result["new_status"] == "success" else ("~" if result["new_status"] == "partial" else "FAIL")
                print(f"  {icon} {result['old_status']} -> {result['new_status']}  chunks={result['chunk_count']}  pages={result['total_pages']}  text={result['extracted_text_len']}chars  usable={result['is_text_usable']}")
                if result["new_error"]:
                    print(f"  error: {result['new_error'][:200]}")
                if result.get("_traceback"):
                    print(f"  traceback: {result['_traceback'][:400]}")
            except Exception as exc:
                print(f"  UNHANDLED: {exc}")
                traceback.print_exc()
                results.append({
                    "id": material.id, "filename": filename,
                    "old_status": material.parse_status,
                    "new_status": "failed",
                    "new_error": f"未捕获异常：{str(exc)[:200]}",
                    "chunk_count": 0,
                })
            print()

        # ── Summary ──
        success_count = sum(1 for r in results if r["new_status"] == "success")
        partial_count = sum(1 for r in results if r["new_status"] == "partial")
        failed_count = sum(1 for r in results if r["new_status"] == "failed")
        total_chunks = sum(r["chunk_count"] for r in results)

        print("=" * 60)
        print(f"完成: 成功={success_count}  部分={partial_count}  失败={failed_count}  总chunks={total_chunks}")
        print("=" * 60)

        for r in results:
            if r["new_status"] == "success":
                print(f"  OK  [{r['id']}] {r['filename']}  chunks={r['chunk_count']}")
        for r in results:
            if r["new_status"] == "partial":
                print(f"  ~   [{r['id']}] {r['filename']}  chunks={r['chunk_count']}  {r.get('new_error', '')[:100]}")
        for r in results:
            if r["new_status"] == "failed":
                print(f"  FAIL [{r['id']}] {r['filename']}  error={r.get('new_error', '')[:150]}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量重新解析课程失败资料")
    parser.add_argument("--subject", type=str, default=None, help="精确匹配课程 subject (通过 normalize_subject)")
    parser.add_argument("--subject-contains", type=str, default=None, help="模糊匹配课程 subject (LIKE %%text%%)")
    parser.add_argument("--material-id", type=int, default=None, help="重新解析单个资料")
    parser.add_argument("--all-failed", action="store_true", help="列出所有课程的 failed 资料")
    parser.add_argument("--list-subjects", action="store_true", help="列出数据库中所有课程 subject")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细解析过程")
    parser.add_argument("--dry-run", action="store_true", default=True, help="仅预览不执行（默认）")
    parser.add_argument("--execute", dest="dry_run", action="store_false", help="实际执行")
    args = parser.parse_args()

    # If no mode specified, show help
    if not any([args.subject, args.subject_contains, args.material_id, args.all_failed, args.list_subjects]):
        parser.print_help()
        print("\n请至少指定 --subject, --all-failed, --material-id 或 --list-subjects")
        sys.exit(1)

    db_path = Path(__file__).resolve().parent / "app.db"
    print(f"Database: {db_path}  (exists={db_path.exists()})")
    run(args)
