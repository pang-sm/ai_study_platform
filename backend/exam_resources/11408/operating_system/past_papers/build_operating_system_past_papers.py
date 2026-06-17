"""Build OS past papers from OCR text into ExamQuestionBank."""
import json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

OCR_TXT = BASE / "exam_resources/11408/operating_system/past_papers/raw/11408_2022_2026_operating_system_OCR.txt"
CHKD = BASE / "exam_resources/11408/operating_system/past_papers/checked"
RPT = BASE / "exam_resources/11408/operating_system/past_papers/import_reports"
PATCHES_FILE = BASE / "exam_resources/11408/operating_system/past_papers/manual_review_patches.json"

SUBJECT_KEY = "operating_system"
SUBJECT_NAME = "操作系统"
CHOICE_RANGE = range(23, 33)  # Q23-Q32
BIG_NUMBERS = [45, 46]

def parse_ocr(fp):
    """Parse OCR text into structured questions."""
    text = Path(fp).read_text(encoding="utf-8")
    lines = text.split('\n')

    questions = []
    current_year = None
    current_q = None  # {year, qnum, stem_lines, opts, answer, answer_status}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Year header
        ym = re.match(r'(\d{4})\s*年', line)
        if ym:
            # Flush previous question
            if current_q:
                finalize_question(current_q, questions)
            current_year = int(ym.group(1))
            current_q = None
            i += 1; continue

        # Question marker
        qm = re.match(r'第\s*(\d+)\s*题', line)
        if qm and current_year:
            # Flush previous
            if current_q:
                finalize_question(current_q, questions)
            qnum = int(qm.group(1))
            current_q = {
                'year': current_year,
                'qnum': qnum,
                'stem_lines': [],
                'opts': {},
                'answer': '',
                'answer_status': 'confirmed',
            }
            i += 1; continue

        # Answer line
        am = re.match(r'答案[：:]\s*(.+)', line)
        if am and current_q:
            ans = am.group(1).strip()
            if '待补充' in ans:
                current_q['answer_status'] = 'pending'
            current_q['answer'] = ans
            # Flush immediately after answer
            finalize_question(current_q, questions)
            current_q = None
            i += 1; continue

        # Collect stem + options lines
        if current_q and line and not line.startswith('【截图OCR') and not line.startswith('11408'):
            # Check if line is an option
            opt_m = re.match(r'^\s*([A-D])[.．、)\s]\s*(.+)', line)
            if opt_m:
                current_q['opts'][opt_m.group(1)] = opt_m.group(2).strip()
            else:
                current_q['stem_lines'].append(line)

        i += 1

    # Flush last question
    if current_q:
        finalize_question(current_q, questions)

    return questions

def clean_ocr_stem(stem, qnum, year):
    """Remove obvious OCR artifacts from question stem."""
    # Remove trailing orphan characters like "mo", "m4", etc.
    stem = re.sub(r'\s+mo\s*$', '', stem)
    stem = re.sub(r'\s+m\d+\s*$', '', stem)
    # Remove garbled table remnants (only replace consecutive garbled tokens)
    garbled_table_pattern = re.compile(r'(?:\b(?:EE|CE|ER|el|pel|fe|Act|B2|ame)\b\s*){2,}')
    stem = garbled_table_pattern.sub('【表格数据见原题】', stem)
    # Clean up duplicate markers
    stem = re.sub(r'(【表格数据见原题】[\s|]*)+', '【表格数据见原题】', stem)
    # Fix stray parentheses
    stem = re.sub(r'《\)', '）', stem)
    stem = re.sub(r'\(》', '（', stem)
    # Collapse multiple spaces
    stem = re.sub(r'\s{2,}', ' ', stem)
    return stem.strip()

def clean_ocr_options(opts):
    """Clean option text from OCR merging issues."""
    cleaned = {}
    for k, v in opts.items():
        if k not in 'ABCD':
            continue
        # Remove artifacts
        v = re.sub(r'\s+', ' ', v).strip()
        cleaned[k] = v
    return cleaned

def finalize_question(q, questions):
    """Clean and add question to list."""
    stem = ' '.join(q['stem_lines']).strip()
    # Clean common OCR artifacts
    stem = clean_ocr_stem(stem, q['qnum'], q['year'])
    stem = re.sub(r'\s+', ' ', stem)
    stem = stem.strip()

    qtype = 'big' if q['qnum'] in BIG_NUMBERS else 'choice'
    opts = clean_ocr_options(q['opts']) if qtype == 'choice' else {}

    # Validate choice options
    if qtype == 'choice':
        # Keep only A-D keys
        opts = {k: v for k, v in opts.items() if k in 'ABCD'}
        # Check for merged options (B/D text merged into A/C values)
        for key in list(opts.keys()):
            val = opts[key]
            # Check if another option label is embedded: e.g., "A.xxx B.yyy" in key A
            for other in 'ABCD':
                if other != key:
                    pattern = rf'\b{other}[.．、)\s]'
                    if re.search(pattern, val):
                        # Try to split
                        parts = re.split(rf'\s*\b{other}[.．、)\s]\s*', val, maxsplit=1)
                        if len(parts) == 2:
                            opts[key] = parts[0].strip()
                            if other not in opts:
                                opts[other] = parts[1].strip()

    # Determine review notes
    review_notes = []
    if qtype == 'choice' and len(opts) < 4:
        missing = [x for x in 'ABCD' if x not in opts]
        review_notes.append(f'选项缺失: {",".join(missing)}')
    if q.get('answer_status') == 'pending':
        review_notes.append('答案待补充（PDF未检测到参考答案）')
    if not stem:
        review_notes.append('题干缺失')
    # Check for table/chart dependency
    if re.search(r'下表|下表所|如下表|右图|下图|如图|表中|图示', stem):
        review_notes.append('【图示/表格缺失，待补充原题截图】')

    questions.append({
        'exam_type': '11408',
        'subject': SUBJECT_KEY,
        'course_id': f'{SUBJECT_KEY}_11408',
        'subject_name': SUBJECT_NAME,
        'year': q['year'],
        'paper_name': f"{q['year']}年操作系统真题",
        'question_number': q['qnum'],
        'question_type': qtype,
        'question_text': stem,
        'options': opts,
        'answer': q['answer'],
        'answer_status': q['answer_status'],
        'explanation': '',
        'source_ref': f"{q['year']}-Q{q['qnum']:02d}",
        'text_quality': 'ready' if (
            stem and q['answer'] and q.get('answer_status') == 'confirmed' and
            (qtype != 'choice' or len(opts) >= 4) and
            not review_notes
        ) else 'need_review',
        'review_notes': '; '.join(review_notes) if review_notes else '',
        'is_active': True,
    })

def apply_patches(questions):
    """Apply manual review patches to fix answers, options, and review_notes."""
    if not PATCHES_FILE.exists():
        print(f"  No patches file: {PATCHES_FILE}")
        return
    patches_data = json.loads(PATCHES_FILE.read_text(encoding="utf-8"))
    patches = patches_data.get("patches", [])
    if not patches:
        return

    print(f"  Applying {len(patches)} manual patches...")
    patched = 0
    for p in patches:
        yr = p.get("year")
        num = p.get("number")
        # Find matching question
        for q in questions:
            if q["year"] == yr and q["question_number"] == num:
                fix_type = p.get("fix", "")

                changed = False

                # Fix stem
                if p.get("stem_cleanup"):
                    q["question_text"] = p["stem_cleanup"]
                    changed = True

                # Fix options
                new_opts = p.get("options", {})
                if new_opts and len(new_opts) == 4:
                    q["options"] = new_opts
                    changed = True

                # Fix answer
                new_answer = p.get("answer", "")
                if new_answer and ("待补充" in q.get("answer", "") or
                                   q.get("answer_status") == "pending" or
                                   p.get("quality") == "ready"):
                    q["answer"] = new_answer
                    q["answer_status"] = "confirmed"
                    changed = True

                # Fix review_notes
                if p.get("review_notes"):
                    q["review_notes"] = p["review_notes"]
                    changed = True
                elif p.get("quality") == "ready":
                    q["review_notes"] = ""

                # Apply quality
                if p.get("quality"):
                    q["text_quality"] = p["quality"]

                if changed:
                    patched += 1
                    print(f"    Patched: {yr}-{num:02d} ({p.get('fix','')}) -> quality={q['text_quality']}")

                break
    print(f"  Patched {patched} items.")


def _recalc_quality(q):
    """Recalculate text_quality based on current state."""
    stem = q.get("question_text", "")
    answer = q.get("answer", "")
    qtype = q.get("question_type", "choice")
    opts = q.get("options", {})
    review_notes = q.get("review_notes", "")

    ok = bool(stem) and bool(answer) and q.get("answer_status") == "confirmed"
    if qtype == "choice":
        ok = ok and len(opts) >= 4
    if review_notes:
        ok = False
    return "ready" if ok else "need_review"


def main():
    dry_run = '--dry-run' in sys.argv
    questions = parse_ocr(OCR_TXT)

    # Apply manual review patches
    apply_patches(questions)

    t = len(questions)
    c = sum(1 for q in questions if q['question_type'] == 'choice')
    b = t - c
    pending = sum(1 for q in questions if q['answer_status'] == 'pending')
    need_review = sum(1 for q in questions if q['text_quality'] == 'need_review')

    print(f"Parsed: {t} (choice={c}, big={b}, pending_answers={pending}, need_review={need_review})")

    yrs = defaultdict(lambda: {'choice': 0, 'big': 0})
    for q in questions:
        yrs[q['year']][q['question_type']] += 1
    for yr in sorted(yrs):
        y = yrs[yr]
        print(f"  {yr}: {y['choice']+y['big']} (c={y['choice']}, b={y['big']})")

    # Check completeness
    for yr in sorted(set(q['year'] for q in questions)):
        yr_qs = {q['question_number'] for q in questions if q['year'] == yr}
        mc = [n for n in CHOICE_RANGE if n not in yr_qs]
        mb = [n for n in BIG_NUMBERS if n not in yr_qs]
        if mc: print(f"  {yr}: MISSING choice Q{mc}")
        if mb: print(f"  {yr}: MISSING big Q{mb}")

    # Save
    CHKD.mkdir(parents=True, exist_ok=True); RPT.mkdir(parents=True, exist_ok=True)
    json.dump(questions, (CHKD / "parsed_ready_past_papers.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return

    # Import to DB — delete old records first to avoid duplicates
    db = SessionLocal()
    deleted = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
    ).delete()
    db.commit()
    print(f"Deleted {deleted} old OS past papers")

    ins = 0
    ready_count = 0
    review_count = 0
    for q in questions:
        quality = q.get('text_quality', 'unchecked')
        item = models.ExamQuestionBank(
            subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
            source_type="past_paper", visibility="public",
            knowledge_point_id="", knowledge_point_name="", knowledge_point_path="",
            year=q['year'], question_number=q['question_number'],
            question_type=q['question_type'],
            stem=q['question_text'],
            options_json=json.dumps(q.get('options', {}), ensure_ascii=False),
            standard_answer=q.get('answer', ''),
            analysis=q.get('review_notes', ''),
            difficulty="基础",
            source_ref=f"past_paper:{q['source_ref']}",
            quality_status=quality,
            is_active=True,  # ALL questions visible; quality_status drives UX
        )
        db.add(item); ins += 1
        if quality == 'ready':
            ready_count += 1
        else:
            review_count += 1
    db.commit()

    act = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.is_active == True,
    ).count()
    nrv = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.quality_status == "need_review",
    ).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active (ready={ready_count}, need_review={review_count}, DB need_review={nrv})")

if __name__ == "__main__":
    main()
