"""
Batch reparse all failed materials for a given course subject.

Usage (dry-run first):
  python backend/reparse_failed_materials.py --subject "C语言" --dry-run

Then execute:
  python backend/reparse_failed_materials.py --subject "C语言"

This script reuses the same internal parsing functions as the
POST /materials/{id}/reparse endpoint — no duplicate logic.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import SessionLocal, init_user_profile_schema
import models
from subjects import normalize_subject


def _ensure_schema():
    """Ensure the local DB has all required columns (idempotent)."""
    init_user_profile_schema()


def utc_now():
    return datetime.now(timezone.utc)


def serialize_datetime(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# These helpers mirror the ones in main.py — imported at runtime to avoid
# circular imports, since main.py does FastAPI app setup at import time.
def _resolve_stored_file_path(stored_file_path: str) -> Path:
    from main import resolve_stored_file_path
    return resolve_stored_file_path(stored_file_path)


def _reparse_one(db, material):
    """Reparse a single material, mirroring the POST /materials/{id}/reparse logic."""
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
    )

    material_id = material.id
    result = {
        "id": material_id,
        "filename": material.original_filename,
        "old_status": material.parse_status,
        "old_error": material.parse_error or "",
        "new_status": None,
        "new_error": None,
        "chunk_count": 0,
    }

    file_path = _resolve_stored_file_path(material.file_path)
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

    material.parse_status = "parsing"
    material.parse_error = None
    material.parse_progress = 1
    material.parse_started_at = serialize_datetime(utc_now())
    db.commit()
    db.refresh(material)

    file_type = (material.file_type or "").lower()
    original_filename = material.original_filename or ""

    try:
        if file_type == "pdf":
            total_pages, page_texts = extract_pdf_pages(file_bytes)
            extracted_text = build_pdf_text_from_pages(page_texts)
            is_text = is_pdf_text_usable(extracted_text, total_pages)

            update_material_parse_state(
                db, material_id,
                total_pages=total_pages,
                parse_progress=20,
                parsed_pages=0,
                ocr_required=0 if is_text else 1,
            )

            if is_text:
                material, chunk_count = complete_material_with_local_pdf_text(
                    db, material, extracted_text, total_pages,
                )
                result["new_status"] = "success"
                result["chunk_count"] = chunk_count
            else:
                parse_scanned_pdf_in_background(db, material, file_bytes, extracted_text)
                db.refresh(material)
                result["new_status"] = material.parse_status or "unknown"
                result["new_error"] = material.parse_error or ""
                result["chunk_count"] = material.chunk_count or 0

        elif file_type == "image":
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
                from main import get_material_for_parsing
                update_material_parse_state(db, material_id, parse_status="parsing", parse_progress=10)
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
                        parse_error=qwen_result.get("error") or "图片 OCR 解析失败，未能提取文字。",
                        parse_progress=0,
                        parse_completed_at=serialize_datetime(utc_now()),
                    )
                    result["new_status"] = "failed"
                    result["new_error"] = qwen_result.get("error") or "图片 OCR 解析失败"

        elif file_type in ("docx", "pptx", "text", "code"):
            from document_parser import extract_supported_file_text
            doc_result = extract_supported_file_text(file_bytes, original_filename)
            extracted_text = doc_result["text"]
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
                parse_error=f"暂不支持 {file_type} 类型的批量重新解析。",
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
            result["new_status"] = "failed"
            result["new_error"] = f"暂不支持 {file_type} 类型"

    except Exception as exc:
        import traceback
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
        result["traceback"] = traceback.format_exc()[-500:]

    db.refresh(material)
    return result


def run(subject: str, dry_run: bool = True):
    _ensure_schema()
    canonical = normalize_subject(subject)
    db = SessionLocal()

    # Query failed materials for this subject
    materials = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.subject == canonical,
            models.StudyMaterial.parse_status == "failed",
            models.StudyMaterial.is_deleted.is_(False),
        )
        .order_by(models.StudyMaterial.id)
        .all()
    )

    if not materials:
        # Also try partial / parsing that may be stuck
        materials = (
            db.query(models.StudyMaterial)
            .filter(
                models.StudyMaterial.subject == canonical,
                models.StudyMaterial.parse_status.in_(["failed", "parsing", "pending"]),
                models.StudyMaterial.is_deleted.is_(False),
            )
            .order_by(models.StudyMaterial.id)
            .all()
        )

    if not materials:
        print(f"未找到 {canonical} 课程下需要重新解析的资料。")
        # Show all materials for debugging
        all_mats = (
            db.query(models.StudyMaterial)
            .filter(
                models.StudyMaterial.subject == canonical,
                models.StudyMaterial.is_deleted.is_(False),
            )
            .all()
        )
        if all_mats:
            print(f"\n该课程下共有 {len(all_mats)} 份资料：")
            for m in all_mats:
                print(f"  [{m.id}] {m.original_filename}  status={m.parse_status}  chunks={m.chunk_count}")
        else:
            print(f"\n该课程下没有任何资料。可用的课程：")
            subjects = (
                db.query(models.StudyMaterial.subject)
                .filter(models.StudyMaterial.is_deleted.is_(False))
                .distinct()
                .all()
            )
            for s in subjects:
                count = (
                    db.query(models.StudyMaterial)
                    .filter(
                        models.StudyMaterial.subject == s[0],
                        models.StudyMaterial.is_deleted.is_(False),
                    )
                    .count()
                )
                print(f"  {s[0]} ({count} 份)")
        db.close()
        return

    print(f"{'[DRY RUN] ' if dry_run else ''}课程: {canonical}")
    print(f"找到 {len(materials)} 份需要重新解析的资料：\n")
    for m in materials:
        print(f"  [{m.id}] {m.original_filename}")
        print(f"      类型: {m.file_type}  大小: {m.file_size}B  状态: {m.parse_status}")
        if m.parse_error:
            print(f"      错误: {m.parse_error[:120]}")

    if dry_run:
        print(f"\n--- 以上为 dry-run，共 {len(materials)} 份文件待处理 ---")
        print("确认无误后执行: python backend/reparse_failed_materials.py --subject \"C语言\"")
        db.close()
        return

    print(f"\n开始重新解析 {len(materials)} 份资料...\n")

    results = []
    for i, material in enumerate(materials, 1):
        print(f"[{i}/{len(materials)}] 正在重新解析: [{material.id}] {material.original_filename} ...")
        try:
            result = _reparse_one(db, material)
            results.append(result)
            status_icon = "OK" if result["new_status"] == "success" else "FAIL"
            print(f"  {status_icon} -> {result['new_status']}  chunks={result['chunk_count']}")
            if result["new_error"]:
                print(f"        error: {result['new_error'][:150]}")
            if result.get("traceback"):
                print(f"        traceback: {result['traceback'][:300]}")
        except Exception as exc:
            import traceback
            print(f"  FAIL (unhandled) -> {exc}")
            traceback.print_exc()
            results.append({
                "id": material.id,
                "filename": material.original_filename,
                "old_status": material.parse_status,
                "new_status": "failed",
                "new_error": f"未捕获异常：{str(exc)[:200]}",
                "chunk_count": 0,
            })
        print()

    # Summary
    success_count = sum(1 for r in results if r["new_status"] == "success")
    partial_count = sum(1 for r in results if r["new_status"] == "partial")
    failed_count = sum(1 for r in results if r["new_status"] == "failed")
    total_chunks = sum(r["chunk_count"] for r in results)

    print("=" * 60)
    print(f"重新解析完成: 成功 {success_count} | 部分成功 {partial_count} | 失败 {failed_count}")
    print(f"共生成 {total_chunks} 个知识片段")
    print("=" * 60)

    if success_count > 0:
        print("\n成功解析：")
        for r in results:
            if r["new_status"] == "success":
                print(f"  [{r['id']}] {r['filename']}  chunks={r['chunk_count']}")

    if partial_count > 0:
        print("\n部分成功：")
        for r in results:
            if r["new_status"] == "partial":
                print(f"  [{r['id']}] {r['filename']}  chunks={r['chunk_count']}  error={r['new_error'][:120]}")

    if failed_count > 0:
        print("\n仍失败：")
        for r in results:
            if r["new_status"] == "failed":
                print(f"  [{r['id']}] {r['filename']}  error={r['new_error'][:150]}")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量重新解析课程失败资料")
    parser.add_argument("--subject", type=str, required=True, help="课程名称，如 'C语言'")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="仅列出待处理文件，不实际执行（默认开启）")
    parser.add_argument("--execute", dest="dry_run", action="store_false",
                        help="实际执行重新解析")
    args = parser.parse_args()

    print(f"Database: {Path(__file__).resolve().parent / 'app.db'}")
    run(subject=args.subject, dry_run=args.dry_run)
