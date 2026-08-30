"""Deduplicate 11408 chapter questions in exam_question_bank.

Natural key = full-content hash (subject_key + knowledge_point_id + question_type
+ normalized stem + options + standard_answer). Chapter questions have no
year/question_number, so content is the stable identity.

Unlike past-paper (0 user references), chapter questions ARE referenced by:
  - exam_question_done_records.question_bank_id
  - exam_wrong_questions.question_bank_id
  - exam_practice_attempts.{question_ids_json, answers_json, result_json}

So this script migrates references from duplicate (inactive) -> canonical (active)
before deleting, and merges uniqueness collisions.

SAFETY: dry-run by default; --execute writes (with backup + single transaction).

Usage:
    python scripts/maintenance/dedupe_chapter_questions.py [--db PATH] [--subject S] [--execute] [--backup PATH]
"""
import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys


def norm(s):
    return "".join((s or "").split())


def content_hash(subject_key, kp, qtype, stem, options, answer):
    h = hashlib.sha1()
    for part in [subject_key, kp or "", qtype, norm(stem), (options or "").strip(), (answer or "").strip()]:
        h.update(part.encode("utf-8"))
    return h.hexdigest()


def backup_db(src_path, backup_path):
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(backup_path)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return backup_path


def build_mapping(cur, subject):
    """Return (active_by_hash, inactive_rows) where inactive_rows = [(id, hash, canonical_id|None)]."""
    active_by_hash = {}
    for rid, kp, qt, stem, opts, ans in cur.execute(
        "SELECT id, knowledge_point_id, question_type, stem, options_json, standard_answer "
        "FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=1",
        (subject,),
    ):
        active_by_hash[content_hash(subject, kp, qt, stem, opts, ans)] = rid

    inactive_rows = []
    for rid, kp, qt, stem, opts, ans in cur.execute(
        "SELECT id, knowledge_point_id, question_type, stem, options_json, standard_answer "
        "FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=0",
        (subject,),
    ):
        h = content_hash(subject, kp, qt, stem, opts, ans)
        inactive_rows.append((rid, h, active_by_hash.get(h)))
    return active_by_hash, inactive_rows


def migrate_done_records(cur, mapping):
    """Move done-records from duplicate -> canonical, merging done_count collisions."""
    for dup_id, canonical in mapping.items():
        rows = cur.execute(
            "SELECT id, username FROM exam_question_done_records WHERE question_bank_id=?", (dup_id,)
        ).fetchall()
        for rowid, username in rows:
            # If this user already has a record for the canonical id, merge.
            existing = cur.execute(
                "SELECT id, done_count, first_done_at, last_done_at FROM exam_question_done_records "
                "WHERE username=? AND question_bank_id=?",
                (username, canonical),
            ).fetchone()
            this = cur.execute(
                "SELECT done_count, first_done_at, last_done_at FROM exam_question_done_records WHERE id=?",
                (rowid,),
            ).fetchone()
            if existing:
                eid, ecnt, ef, el = existing
                tcnt, tf, tl = this
                merged_first = min(ef or tf or "", tf or ef or "")
                merged_last = max(el or tl or "", tl or el or "")
                cur.execute(
                    "UPDATE exam_question_done_records SET done_count=done_count+?, first_done_at=?, last_done_at=? WHERE id=?",
                    (tcnt, merged_first, merged_last, eid),
                )
                cur.execute("DELETE FROM exam_question_done_records WHERE id=?", (rowid,))
            else:
                cur.execute(
                    "UPDATE exam_question_done_records SET question_bank_id=? WHERE id=?",
                    (canonical, rowid),
                )


def migrate_wrong_questions(cur, mapping):
    """Move wrong-questions from duplicate -> canonical, merging (keep unresolved, sum review_count)."""
    for dup_id, canonical in mapping.items():
        rows = cur.execute(
            "SELECT id, username FROM exam_wrong_questions WHERE question_bank_id=?", (dup_id,)
        ).fetchall()
        for rowid, username in rows:
            existing = cur.execute(
                "SELECT id FROM exam_wrong_questions WHERE username=? AND question_bank_id=?",
                (username, canonical),
            ).fetchone()
            this = cur.execute(
                "SELECT mastered, review_count, updated_at FROM exam_wrong_questions WHERE id=?", (rowid,)
            ).fetchone()
            t_mastered, t_review, t_upd = this
            if existing:
                eid = existing[0]
                # keep unresolved (mastered=0) as the surviving row's state
                cur.execute(
                    "UPDATE exam_wrong_questions SET mastered=mastered AND ?, review_count=review_count+? WHERE id=?",
                    (1 if t_mastered else 0, t_review, eid),
                )
                cur.execute("DELETE FROM exam_wrong_questions WHERE id=?", (rowid,))
            else:
                cur.execute(
                    "UPDATE exam_wrong_questions SET question_bank_id=? WHERE id=?",
                    (canonical, rowid),
                )


def migrate_practice_attempts(cur, mapping):
    """Rewrite question_ids_json / answers_json / result_json question ids."""
    idmap = {str(k): str(v) for k, v in mapping.items()}
    for aid, qij, aj, rj in cur.execute(
        "SELECT id, question_ids_json, answers_json, result_json FROM exam_practice_attempts"
    ).fetchall():
        changed = False
        nqij = None
        try:
            qlist = json.loads(qij) if qij else None
            if isinstance(qlist, list):
                seen = set()
                newlist = []
                for x in qlist:
                    k = str(x)
                    if k in idmap:
                        changed = True
                        k = idmap[k]
                    if k not in seen:
                        seen.add(k)
                        newlist.append(k)
                nqij = json.dumps(newlist)
        except Exception:
            nqij = None

        naj = None
        try:
            ad = json.loads(aj) if aj else None
            if isinstance(ad, dict):
                newd = {}
                for k, v in ad.items():
                    nk = idmap.get(str(k), str(k))
                    if str(k) != nk:
                        changed = True
                    newd[nk] = v
                naj = json.dumps(newd)
        except Exception:
            naj = None

        nrj = None
        try:
            rd = json.loads(rj) if rj else None
            if isinstance(rd, dict) and isinstance(rd.get("results"), list):
                for item in rd["results"]:
                    if isinstance(item, dict) and "question_id" in item:
                        k = str(item["question_id"])
                        if k in idmap:
                            item["question_id"] = int(idmap[k])
                            changed = True
                nrj = json.dumps(rd, ensure_ascii=False)
        except Exception:
            nrj = None

        if changed:
            sets = []
            params = []
            if nqij is not None:
                sets.append("question_ids_json=?")
                params.append(nqij)
            if naj is not None:
                sets.append("answers_json=?")
                params.append(naj)
            if nrj is not None:
                sets.append("result_json=?")
                params.append(nrj)
            if sets:
                cur.execute("UPDATE exam_practice_attempts SET " + ", ".join(sets) + " WHERE id=?", params + [aid])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="backend/app.db")
    ap.add_argument("--subject", default=None)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=False)
    ap.add_argument("--execute", dest="execute", action="store_true", default=False)
    ap.add_argument("--backup", default=None)
    args = ap.parse_args()
    if args.execute and args.dry_run:
        print("ERROR: --execute and --dry-run are mutually exclusive.")
        return 2
    if not args.execute:
        args.dry_run = True

    subjects = [args.subject] if args.subject else ["data_structure", "computer_organization", "operating_system", "computer_network"]

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    for subject in subjects:
        active_by_hash, inactive_rows = build_mapping(cur, subject)
        mapped = {rid: cid for rid, h, cid in inactive_rows if cid is not None}
        orphaned = [rid for rid, h, cid in inactive_rows if cid is None]
        total = len(inactive_rows)

        # referenced orphaned rows (must be 0 before execute)
        ref_orphaned = 0
        for tbl, col in [("exam_question_done_records", "question_bank_id"), ("exam_wrong_questions", "question_bank_id")]:
            if orphaned:
                ph = ",".join("?" * len(orphaned))
                n = cur.execute(
                    f"SELECT COUNT(*) FROM {tbl} WHERE {col} IN ({ph})", orphaned
                ).fetchone()[0]
                ref_orphaned += n

        print(f"\n=== {subject} ===")
        print(f"  inactive rows: {total} (mapped={len(mapped)}, orphaned={len(orphaned)})")
        print(f"  canonical active rows: {len(active_by_hash)}")
        print(f"  referenced orphaned rows: {ref_orphaned}")
        print(f"  projected after: total = active + 0 inactive = {len(active_by_hash)}")

        if args.dry_run:
            continue

        if ref_orphaned > 0:
            print(f"  ABORT: {ref_orphaned} references point to orphaned rows; cannot delete safely.")
            conn.close()
            return 1

        # backup (once, before first subject write)
        if not args.backup:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            args.backup = f"{args.db}.chapter-dedupe-backup-{ts}.db"
        if not os.path.exists(args.backup):
            backup_db(args.db, args.backup)
            print(f"\nBackup created: {args.backup} ({os.path.getsize(args.backup)} bytes)")

        try:
            cur.execute("BEGIN IMMEDIATE")
            migrate_done_records(cur, mapped)
            migrate_wrong_questions(cur, mapped)
            migrate_practice_attempts(cur, mapped)
            # delete inactive chapter rows for this subject
            cur.execute(
                "DELETE FROM exam_question_bank WHERE subject_key=? AND source_type='chapter' AND is_active=0",
                (subject,),
            )
            cur.execute("COMMIT")
        except Exception as e:
            conn.rollback()
            print(f"  ERROR during execute, ROLLED BACK: {e}")
            conn.close()
            return 1

        after = cur.execute(
            "SELECT COUNT(*) FROM exam_question_bank WHERE subject_key=? AND source_type='chapter'",
            (subject,),
        ).fetchone()[0]
        print(f"  DONE: after total={after}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
