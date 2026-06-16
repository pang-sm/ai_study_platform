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

def finalize_question(q, questions):
    """Clean and add question to list."""
    stem = ' '.join(q['stem_lines']).strip()
    # Clean common OCR artifacts
    stem = re.sub(r'\s+', ' ', stem)
    stem = stem.strip()

    qtype = 'big' if q['qnum'] in BIG_NUMBERS else 'choice'
    opts = q['opts'] if qtype == 'choice' else {}

    # Validate choice options
    if qtype == 'choice':
        # Keep only A-D keys
        opts = {k: v for k, v in opts.items() if k in 'ABCD'}
        if len(opts) < 4:
            # Try to fill missing options from stem
            pass

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
            (qtype != 'choice' or len(opts) >= 4)
        ) else 'need_review',
        'is_active': True,
    })

def main():
    dry_run = '--dry-run' in sys.argv
    questions = parse_ocr(OCR_TXT)

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
        is_ready = (quality == 'ready')
        item = models.ExamQuestionBank(
            subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
            source_type="past_paper", visibility="public",
            knowledge_point_id="", knowledge_point_name="", knowledge_point_path="",
            year=q['year'], question_number=q['question_number'],
            question_type=q['question_type'],
            stem=q['question_text'],
            options_json=json.dumps(q.get('options', {}), ensure_ascii=False),
            standard_answer=q.get('answer', ''),
            analysis="",
            difficulty="基础",
            source_ref=f"past_paper:{q['source_ref']}",
            quality_status=quality,
            is_active=is_ready,
        )
        db.add(item); ins += 1
        if is_ready:
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
