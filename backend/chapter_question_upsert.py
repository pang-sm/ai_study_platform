"""Idempotent chapter-question upsert for the 11408 chapter builders.

Chapter questions have no year/question_number, so the stable identity is the
full content: (subject_key, knowledge_point_id, question_type, normalized stem,
options, standard_answer).

The previous builders did ``UPDATE is_active=False`` + INSERT on every deploy,
which accumulated one duplicate batch per deploy (the chapter over-seeding root
cause). This helper upserts by content hash so re-running the importer does not
create new rows and existing question IDs are preserved (keeping user
done-records / wrong-questions / attempts pointing at valid rows).
"""
import hashlib
import json


def _norm(s):
    return "".join((s or "").split())


def _options_canonical(options):
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            return (options or "").strip()
    if isinstance(options, dict):
        return json.dumps(options, sort_keys=True, ensure_ascii=False)
    return str(options or "")


def chapter_content_hash(subject_key, kp, qtype, stem, options, answer):
    h = hashlib.sha1()
    for part in [subject_key, kp or "", qtype, _norm(stem), _options_canonical(options), _norm(answer)]:
        h.update(part.encode("utf-8"))
    return h.hexdigest()


def upsert_chapter_questions(db, models, subject_key, subject_name, questions):
    """Upsert chapter questions. `questions` is a list of dicts with keys:
    kp, kp_name, ch_title, type ('choice'|'big'), stem, opts (dict), ans, raw_kp.
    Returns (inserted, updated, deactivated).
    """
    qtype = lambda q: "choice" if q.get("type") == "choice" else "big"  # noqa: E731

    existing = {}
    for row in db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == "chapter",
    ).all():
        key = chapter_content_hash(
            subject_key, row.knowledge_point_id, row.question_type,
            row.stem, row.options_json, row.standard_answer,
        )
        cur = existing.get(key)
        if cur is None or (row.is_active and not cur.is_active) or (row.is_active and cur.is_active and row.id > cur.id):
            existing[key] = row

    seen = set()
    inserted = updated = 0
    for q in questions:
        qt = qtype(q)
        key = chapter_content_hash(
            subject_key, q.get("kp", ""), qt, q.get("stem", ""),
            q.get("opts", {}), q.get("ans", ""),
        )
        seen.add(key)
        row = existing.get(key)
        if row is not None:
            row.knowledge_point_id = q.get("kp", "")
            row.knowledge_point_name = q.get("kp_name", "")
            row.knowledge_point_path = f"{q.get('ch_title', '')} / {q.get('kp_name', '')}"
            row.question_type = qt
            row.stem = q.get("stem", "")
            row.options_json = json.dumps(q.get("opts", {}), ensure_ascii=False)
            row.standard_answer = q.get("ans", "")
            row.source_ref = f"annotated:{q.get('raw_kp', '')}"
            row.is_active = True
            updated += 1
        else:
            db.add(models.ExamQuestionBank(
                subject_key=subject_key, subject_name=subject_name,
                source_type="chapter", visibility="public",
                knowledge_point_id=q.get("kp", ""),
                knowledge_point_name=q.get("kp_name", ""),
                knowledge_point_path=f"{q.get('ch_title', '')} / {q.get('kp_name', '')}",
                question_type=qt, stem=q.get("stem", ""),
                options_json=json.dumps(q.get("opts", {}), ensure_ascii=False),
                standard_answer=q.get("ans", ""), analysis="", difficulty="基础",
                source_ref=f"annotated:{q.get('raw_kp', '')}", is_active=True,
            ))
            inserted += 1

    deactivated = 0
    for key, row in existing.items():
        if key not in seen and row.is_active:
            row.is_active = False
            deactivated += 1

    return inserted, updated, deactivated
