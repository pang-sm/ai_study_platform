"""Read-only audit of 11408 chapter question over-seeding in exam_question_bank.

Root cause (same as v16.6 past-paper): the chapter builders run on every deploy
and use UPDATE is_active=False + INSERT (non-idempotent). Chapter questions have
no year/question_number, so the stable identity is a full-content hash.

This script is STRICTLY READ-ONLY. It reports per subject: total/active/inactive,
distinct-content counts, inactive->active mapping coverage (mapped vs orphaned),
and how many user-data references point at inactive rows.

Usage:
    python scripts/maintenance/audit_chapter_question_duplicates.py [--db PATH]
"""
import argparse
import hashlib
import sqlite3
import sys


def norm(s: str) -> str:
    return "".join((s or "").split())


def content_hash(subject_key, kp, qtype, stem, options, answer) -> str:
    h = hashlib.sha1()
    for part in [subject_key, kp or "", qtype, norm(stem), (options or "").strip(), (answer or "").strip()]:
        h.update(part.encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="backend/app.db")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    cur = conn.cursor()

    subjects = ["data_structure", "computer_organization", "operating_system", "computer_network"]

    print("=== chapter: subject x total/active/inactive + content uniqueness ===")
    for subj in subjects:
        total, active = cur.execute(
            "SELECT COUNT(*), SUM(is_active) FROM exam_question_bank WHERE subject_key=? AND source_type='chapter'",
            (subj,),
        ).fetchone()
        inactive = total - (active or 0)
        d_act = cur.execute(
            "SELECT COUNT(DISTINCT stem) FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=1",
            (subj,),
        ).fetchone()[0]
        d_inact = cur.execute(
            "SELECT COUNT(DISTINCT stem) FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=0",
            (subj,),
        ).fetchone()[0]
        print(f"  {subj}: total={total} active={active} inactive={inactive} | distinct_stem active={d_act} inactive={d_inact}")

    print("\n=== active content-hash uniqueness (duplicate active rows?) ===")
    for subj in subjects:
        rows = cur.execute(
            "SELECT knowledge_point_id, question_type, stem, options_json, standard_answer "
            "FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=1",
            (subj,),
        ).fetchall()
        hashes = set()
        dup = 0
        for kp, qt, stem, opts, ans in rows:
            h = content_hash(subj, kp, qt, stem, opts, ans)
            if h in hashes:
                dup += 1
            hashes.add(h)
        print(f"  {subj}: active={len(rows)} distinct_fullcontent={len(hashes)} duplicate_active_rows={dup}")

    print("\n=== inactive -> active mapping coverage ===")
    for subj in subjects:
        act_hashes = set()
        for kp, qt, stem, opts, ans in cur.execute(
            "SELECT knowledge_point_id, question_type, stem, options_json, standard_answer "
            "FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=1",
            (subj,),
        ):
            act_hashes.add(content_hash(subj, kp, qt, stem, opts, ans))
        inact_hashes = set()
        for kp, qt, stem, opts, ans in cur.execute(
            "SELECT knowledge_point_id, question_type, stem, options_json, standard_answer "
            "FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=0",
            (subj,),
        ):
            inact_hashes.add(content_hash(subj, kp, qt, stem, opts, ans))
        mapped = len(inact_hashes & act_hashes)
        orphaned = len(inact_hashes - act_hashes)
        print(f"  {subj}: inactive distinct={len(inact_hashes)} mapped_to_active={mapped} orphaned={orphaned}")

    print("\n=== user-data references to inactive chapter rows ===")
    for subj in subjects:
        parts = []
        for tbl, col in [("exam_question_done_records", "question_bank_id"), ("exam_wrong_questions", "question_bank_id")]:
            n = cur.execute(
                f"SELECT COUNT(*) FROM {tbl} r JOIN exam_question_bank q ON r.{col}=q.id "
                f"WHERE q.subject_key=? AND q.source_type='chapter' AND q.is_active=0",
                (subj,),
            ).fetchone()[0]
            parts.append(f"{tbl}={n}")
        print(f"  {subj}: " + " ".join(parts))

    print("\n=== exam_practice_attempts JSON chapter refs (active/inactive) ===")
    import json
    chap_ids = set(r[0] for r in cur.execute("SELECT id FROM exam_question_bank WHERE source_type='chapter'"))
    active_ids = set(r[0] for r in cur.execute("SELECT id FROM exam_question_bank WHERE source_type='chapter' AND is_active=1"))
    ref_active = ref_inactive = 0
    for (ij,) in cur.execute("SELECT question_ids_json FROM exam_practice_attempts WHERE question_ids_json IS NOT NULL"):
        try:
            for x in json.loads(ij):
                xi = int(x) if str(x).isdigit() else None
                if xi in chap_ids:
                    if xi in active_ids:
                        ref_active += 1
                    else:
                        ref_inactive += 1
        except Exception:
            pass
    print(f"  active={ref_active} inactive={ref_inactive}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
