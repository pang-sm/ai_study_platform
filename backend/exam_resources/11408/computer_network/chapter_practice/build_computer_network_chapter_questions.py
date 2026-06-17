"""Build computer_network chapter questions from annotated TXT."""
import json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

TXT = BASE / "exam_resources/11408/computer_network/chapter_practice/raw/2027计算机网络_原创配套习题_全章总汇_带知识点标注.txt"
CHKD = BASE / "exam_resources/11408/computer_network/chapter_practice/checked"
RPT = BASE / "exam_resources/11408/computer_network/chapter_practice/import_reports"

# CN chapter and section mapping
SEC_TITLES = {
    "1.1":"计算机网络概述", "1.2":"计算机网络体系结构与参考模型",
    "2.1":"物理层基础", "2.2":"传输介质", "2.3":"物理层设备",
    "3.1":"数据链路层功能", "3.2":"组帧", "3.3":"差错控制", "3.4":"流量控制与可靠传输",
    "3.5":"介质访问控制", "3.6":"局域网", "3.7":"广域网", "3.8":"数据链路层设备",
    "4.1":"网络层功能", "4.2":"路由算法", "4.3":"IPv4", "4.4":"IPv6",
    "4.5":"路由协议", "4.6":"IP组播", "4.7":"移动IP", "4.8":"网络层设备",
    "5.1":"传输层概述", "5.2":"UDP", "5.3":"TCP",
    "6.1":"网络应用模型", "6.2":"DNS", "6.3":"FTP", "6.4":"电子邮件",
    "6.5":"万维网WWW", "6.6":"其他应用",
}

CH_TITLES = {
    1:"计算机网络体系结构", 2:"物理层", 3:"数据链路层",
    4:"网络层", 5:"传输层", 6:"应用层",
}

SUBJECT_KEY = "computer_network"
SUBJECT_NAME = "计算机网络"
COURSE_ID = "computer_network_11408"

def norm(raw_kp):
    """Normalize knowledge point to chapter+section."""
    # Handle formats like "1.1.1 计算机网络的概念" or "1.1.4 报文交换"
    m = re.match(r'(\d+)\.(\d+)', raw_kp)
    if not m:
        return (0, "", raw_kp, "", raw_kp)
    ch = int(m.group(1))
    sec = f"{ch}.{m.group(2)}"
    sn = SEC_TITLES.get(sec, raw_kp)
    cn = CH_TITLES.get(ch, f"第{ch}章")
    return (ch, sec, sn, cn, raw_kp)

def parse(fp):
    qs = []
    lines = Path(fp).read_text(encoding="utf-8").split('\n')
    i = 0; n = len(lines)
    current_kp = ""
    current_section = ""  # e.g., "1.1.1"
    current_chapter = 0
    type_big = False  # Track current question type context

    # Skip header lines
    while i < n:
        l = lines[i].strip()
        if '第1章' in l or '第1批' in l:
            i += 1
            break
        i += 1

    while i < n:
        l = lines[i].strip()

        # Chapter header: "第X章 计算机网络体系结构"
        chm = re.match(r'第(\d+)章\s+(.+)', l)
        if chm and '批' not in l:
            current_chapter = int(chm.group(1))
            i += 1; continue

        # Section header: "1.1.1 计算机网络的概念" or "1.1.4 分组交换"
        secm = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s+(.+)', l)
        if secm and '一、' not in l and '二、' not in l and '三、' not in l:
            current_section = secm.group(1)
            type_big = False  # Reset type context on section change
            i += 1; continue

        # Type header: "一、单项选择题" / "二、综合应用题"
        # Only set type_big=True for PURE big/综合 sections (NOT mixed sections)
        if ('一、' in l or '二、' in l or '三、' in l) and ('选择' in l or '综合' in l or '应用' in l):
            is_mixed = '选择' in l and ('综合' in l or '应用' in l)
            type_big = (('综合' in l or '大题' in l or '应用' in l) and not is_mixed)
            i += 1; continue

        # Knowledge point marker: 【知识点：1.1.1 计算机网络的概念】
        km = re.match(r'【知识点：(.+?)】', l)
        if km:
            current_kp = km.group(1).strip()
            i += 1; continue

        # Question number: "01. 题干..." or "01．题干..."
        qm = re.match(r'^(\d+)[.．、]\s*(.+)', l)
        if qm and len(l) > 5:
            qnum = int(qm.group(1))
            stem = qm.group(2).strip()

            # Determine type: check "综合应用题" prefix in stem
            is_big_stem = re.search(r'综合应用|综合题|大题|简答|计算', stem[:15]) if stem else False

            # Determine type based on context AND stem content
            if type_big or is_big_stem:
                qtype = "big"
            else:
                qtype = "choice"

            opts = {}; ans = ""; explanation = ""
            j = i + 1

            # Read options/answer from subsequent lines
            while j < n and j < i + 12:
                nl = lines[j].rstrip()
                nls = nl.strip()

                # Next question or chapter marker - stop
                if re.match(r'^(第\d+章|\d+\.\d+|【知识点：|一、|二、|三、)', nls):
                    break
                if re.match(r'^\d+[.．、]\s*', nls) and len(nls) > 5 and j > i + 1:
                    break

                # Option: "A. xxx"
                om = re.match(r'^\s*([A-D])[.．、]\s*(.+)', nl)
                if om and not re.match(r'^\d+[.．、]', nls):
                    opts[om.group(1)] = om.group(2).strip()

                # Answer: "答案：X" or "答案: X"
                elif re.search(r'^答案[：:]', nls):
                    am = re.search(r'答案[：:]\s*(.+)', nls)
                    if am:
                        ans = am.group(1).strip()

                # Explanation
                elif re.search(r'^解析[：:]', nls):
                    exm = re.search(r'解析[：:]\s*(.+)', nls)
                    if exm:
                        explanation = exm.group(1).strip()

                j += 1

            # Determine chapter from section
            ch, sec, sn, cn, raw_kp = norm(current_kp or current_section)
            if ch == 0 and current_chapter:
                ch = current_chapter
                cn = CH_TITLES.get(ch, f"第{ch}章")

            # Quality check
            review_notes = []
            if qtype == "choice" and len(opts) < 4:
                missing = [x for x in 'ABCD' if x not in opts]
                review_notes.append(f'选项缺失: {",".join(missing)}')
            if not ans:
                review_notes.append('答案缺失')
            if not stem:
                review_notes.append('题干缺失')
            # Check option merging (only flag if other label followed by option-style delimiter: . ． ) ］)
            for k, v in opts.items():
                for other in 'ABCD':
                    if other != k and v and re.search(rf'{other}[.．)）]', v):
                        if not v.startswith(other + '.') and not v.startswith(other + '．') and not v.startswith(other + ')'):
                            review_notes.append(f'选项{k}包含{other}内容')

            quality = 'need_review' if review_notes else 'ready'

            qs.append({
                'exam_type': '11408',
                'subject': SUBJECT_KEY,
                'course_id': COURSE_ID,
                'subject_name': SUBJECT_NAME,
                'chapter_no': ch,
                'chapter_title': cn,
                'section_code': sec,
                'section_title': sn,
                'knowledge_point_code': current_kp or current_section,
                'knowledge_point_title': current_kp or current_section,
                'question_number': qnum if current_chapter else 0,
                'question_type': qtype,
                'question_text': stem,
                'options': opts,
                'answer': ans,
                'explanation': explanation,
                'text_quality': quality,
                'review_notes': '; '.join(review_notes),
                'is_active': True,
            })

            i = j - 1  # jump to last processed line
        else:
            # May be continuation of big question stem
            pass

        i += 1

    # Assign unique question numbers
    for idx, q in enumerate(qs):
        q['global_index'] = idx + 1

    return qs

def main():
    dry_run = '--dry-run' in sys.argv
    questions = parse(TXT)

    t = len(questions)
    c = sum(1 for q in questions if q['question_type'] == 'choice')
    b = t - c
    nrv = sum(1 for q in questions if q['text_quality'] == 'need_review')
    ready = t - nrv

    print(f"Parsed: {t} (choice={c}, big={b}, ready={ready}, need_review={nrv})")

    # Per-chapter breakdown
    ch_counts = defaultdict(lambda: {'choice': 0, 'big': 0, 'nrv': 0})
    for q in questions:
        ch = q.get('chapter_no', 0)
        ch_counts[ch][q['question_type']] += 1
        if q['text_quality'] == 'need_review':
            ch_counts[ch]['nrv'] += 1

    for ch in sorted(ch_counts):
        if ch == 0: continue
        cc = ch_counts[ch]
        cn = CH_TITLES.get(ch, f"Ch{ch}")
        print(f"  Ch{ch} {cn}: {cc['choice']+cc['big']} (c={cc['choice']}, b={cc['big']}, nrv={cc['nrv']})")

    # Save parsed
    CHKD.mkdir(parents=True, exist_ok=True)
    RPT.mkdir(parents=True, exist_ok=True)
    json.dump(questions, (CHKD / "parsed_chapter_practice.json").open("w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\nSaved parsed JSON: {CHKD / 'parsed_chapter_practice.json'}")

    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return

    # Import to DB
    db = SessionLocal()
    deleted = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "chapter",
    ).delete()
    db.commit()
    print(f"Deleted {deleted} old CN chapter practice questions")

    ins = 0
    for q in questions:
        item = models.ExamQuestionBank(
            subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
            source_type="chapter", visibility="public",
            knowledge_point_id=q.get('knowledge_point_code', '') or '',
            knowledge_point_name=q.get('knowledge_point_title', '') or '',
            knowledge_point_path="",
            year=None, question_number=q.get('global_index', 0),
            question_type=q['question_type'],
            stem=q['question_text'],
            options_json=json.dumps(q.get('options', {}), ensure_ascii=False),
            standard_answer=q.get('answer', ''),
            analysis=q.get('explanation', ''),
            difficulty="基础",
            source_ref=f"chapter:{q.get('chapter_no', '')}:{q.get('section_code', '')}",
            quality_status=q['text_quality'],
            is_active=True,
        )
        db.add(item); ins += 1
    db.commit()

    act = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.is_active == True,
    ).count()
    nrv_db = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.quality_status == "need_review",
    ).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active (need_review={nrv_db})")

    # Option merge check
    merge_count = 0
    for q in questions:
        if q['question_type'] == 'choice':
            for k, v in q.get('options', {}).items():
                for other in 'ABCD':
                    if other != k and v and re.search(rf'{other}[.．、)]', v):
                        if not v.startswith(other):
                            merge_count += 1
                            break
    print(f"Option merge issues: {merge_count}")

if __name__ == "__main__":
    main()
