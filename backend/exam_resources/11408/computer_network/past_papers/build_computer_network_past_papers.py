"""Build computer_network past papers from structured TXT into ExamQuestionBank."""
import json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

TXT = BASE / "exam_resources/11408/computer_network/past_papers/raw/11408_2022_2026_计算机网络_题目答案.txt"
CHKD = BASE / "exam_resources/11408/computer_network/past_papers/checked"
RPT = BASE / "exam_resources/11408/computer_network/past_papers/import_reports"

SUBJECT_KEY = "computer_network"
SUBJECT_NAME = "计算机网络"
COURSE_ID = "computer_network_11408"
CHOICE_RANGE = range(33, 41)  # Q33-Q40
BIG_NUMBERS = [47]

# CN chapter titles
CH_TITLES = {
    1:"计算机网络体系结构", 2:"物理层", 3:"数据链路层",
    4:"网络层", 5:"传输层", 6:"应用层",
}

def guess_chapter(stem, answer_text=""):
    """Guess which CN chapter a question belongs to based on keywords."""
    text = (stem + " " + (answer_text or "")).lower()
    scores = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0}

    # Ch1: Architecture & Reference Model
    if any(kw in text for kw in ['osi','iso','参考模型','体系结构','分层','tcp/ip','协议栈','服务','接口']):
        scores[1] += 1

    # Ch2: Physical layer
    if any(kw in text for kw in ['带宽','信道','无噪声','调制','ask','qam','奈奎斯特','香农','码元','baud',
                                   '物理层','中继器','集线器','传输介质','信号','双绞线','光纤']):
        scores[2] += 1

    # Ch3: Data link layer
    if any(kw in text for kw in ['帧','mac','差错','crc','停-等','gbn','sr','选择重传','后退n',
                                   'csma','以太网','交换机','桥接','vlan','ppp','hdlc',
                                   '数据链路','流量控制','滑动窗口','广播域','冲突域','网桥']):
        scores[3] += 1

    # Ch4: Network layer
    if any(kw in text for kw in ['ip地址','子网','子网掩码','网络地址','路由','rip','ospf','bgp',
                                   '网络层','分组','ttl','icmp','arp','dhcp','nat','cidr',
                                   'sdn','流表','路由器','下一跳','转发','最长前缀',
                                   '默认网关','网关','ipv4','ipv6','192.168','183.80']):
        scores[4] += 1

    # Ch5: Transport layer
    if any(kw in text for kw in ['tcp','udp','传输层','拥塞','窗口','mss','rtt','msl',
                                   '三次握手','四次挥手','fin','syn','ack','流量','超时',
                                   '端口','套接字','可靠传输','序号','确认']):
        scores[5] += 1

    # Ch6: Application layer
    if any(kw in text for kw in ['http','dns','ftp','smtp','pop3','应用层','web','url',
                                   'cookie','缓存','邮件','万维网','p2p','dhcp服务器']):
        scores[6] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 4  # Default to network layer


def parse(fp):
    text = Path(fp).read_text(encoding="utf-8")
    lines = text.split('\n')

    questions = []
    current_year = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Year header: "2022 年"
        ym = re.match(r'(\d{4})\s*年', line)
        if ym:
            current_year = int(ym.group(1))
            i += 1; continue

        # Question: "第 33 题" or "第 47 题"
        qm = re.match(r'第\s*(\d+)\s*题', line)
        if qm and current_year:
            qnum = int(qm.group(1))
            stem_lines = []
            opts = {}
            ans = ""
            diagram_info = ""
            j = i + 1

            # Collect question content
            while j < len(lines):
                nl = lines[j].rstrip()
                nls = nl.strip()

                # Stop at next question, year, or separator
                if re.match(r'^(第\s*\d+\s*题|\d{4}\s*年|=+)', nls):
                    break

                # Diagram info line
                if nls.startswith('图示信息：') or nls.startswith('图示信息:'):
                    diagram_info = nls.replace('图示信息：', '').replace('图示信息:', '').strip()
                    j += 1; continue

                # Answer line
                am = re.match(r'^答案[：:]\s*(.*)', nls)
                if am:
                    ans = am.group(1).strip()
                    # If answer is multi-line (for comprehensive questions)
                    if not ans:
                        ans_lines = []
                        j += 1
                        while j < len(lines):
                            anl = lines[j].rstrip().strip()
                            if re.match(r'^(第\s*\d+\s*题|\d{4}\s*年|=+)', anl):
                                break
                            if anl:
                                ans_lines.append(anl)
                            j += 1
                        ans = '\n'.join(ans_lines)
                        j -= 1  # back up
                    break

                # Option: "A. xxx"
                om = re.match(r'^([A-D])[.．、]\s*(.+)', nl)
                if om:
                    opts[om.group(1)] = om.group(2).strip()
                    j += 1; continue

                # Question text: "题目：..."
                if nls.startswith('题目：') or nls.startswith('题目:'):
                    stem_lines.append(nls.replace('题目：', '').replace('题目:', '').strip())
                elif nls:
                    stem_lines.append(nls)

                j += 1

            stem = ' '.join(stem_lines).strip()
            # Add diagram info to stem
            if diagram_info:
                stem = stem + '\n\n【图示信息】\n' + diagram_info

            qtype = 'big' if qnum in BIG_NUMBERS else 'choice'

            # Quality check
            review_notes = []
            if qtype == 'choice' and len(opts) < 4:
                missing = [x for x in 'ABCD' if x not in opts]
                review_notes.append(f'选项缺失: {",".join(missing)}')
            if not ans:
                review_notes.append('答案缺失')
            # Check option merging
            for k, v in opts.items():
                for other in 'ABCD':
                    if other != k and v and re.search(rf'{other}[.．)）]', v):
                        if not v.startswith(other + '.') and not v.startswith(other + '．'):
                            review_notes.append(f'选项{k}包含{other}内容')

            quality = 'need_review' if review_notes else 'ready'

            # Guess chapter
            ch_no = guess_chapter(stem, ans)
            ch_title = CH_TITLES.get(ch_no, f"第{ch_no}章")

            questions.append({
                'exam_type': '11408',
                'subject': SUBJECT_KEY,
                'course_id': COURSE_ID,
                'subject_name': SUBJECT_NAME,
                'year': current_year,
                'paper_name': f"{current_year}年计算机网络真题",
                'question_number': qnum,
                'question_type': qtype,
                'question_text': stem,
                'options': opts,
                'answer': ans,
                'explanation': '',
                'source_ref': f"{current_year}-Q{qnum:02d}",
                'chapter_no': ch_no,
                'chapter_title': ch_title,
                'text_quality': quality,
                'review_notes': '; '.join(review_notes),
                'image_required': bool(diagram_info),
                'is_active': True,
            })

            i = j - 1

        i += 1

    return questions

def main():
    dry_run = '--dry-run' in sys.argv
    questions = parse(TXT)

    t = len(questions)
    c = sum(1 for q in questions if q['question_type'] == 'choice')
    b = t - c
    nrv = sum(1 for q in questions if q['text_quality'] == 'need_review')
    ready = t - nrv

    print(f"Parsed: {t} (choice={c}, big={b}, ready={ready}, need_review={nrv})")

    yrs = defaultdict(lambda: {'choice': 0, 'big': 0, 'nrv': 0})
    for q in questions:
        yrs[q['year']]['choice'] += 1 if q['question_type'] == 'choice' else 0
        yrs[q['year']]['big'] += 1 if q['question_type'] == 'big' else 0
        if q['text_quality'] == 'need_review':
            yrs[q['year']]['nrv'] += 1

    for yr in sorted(yrs):
        y = yrs[yr]
        print(f"  {yr}: {y['choice']+y['big']} (c={y['choice']}, b={y['big']}, nrv={y['nrv']})")

    # Check completeness
    for yr in sorted(set(q['year'] for q in questions)):
        yr_qs = {q['question_number'] for q in questions if q['year'] == yr}
        mc = [n for n in CHOICE_RANGE if n not in yr_qs]
        mb = [n for n in BIG_NUMBERS if n not in yr_qs]
        if mc: print(f"  {yr}: MISSING choice Q{mc}")
        if mb: print(f"  {yr}: MISSING big Q{mb}")

    # Option stats
    opt_missing = sum(1 for q in questions if q['question_type'] == 'choice' and len(q.get('options', {})) < 4)
    opt_merge = 0
    for q in questions:
        if q['question_type'] == 'choice':
            for k, v in q.get('options', {}).items():
                for other in 'ABCD':
                    if other != k and v and re.search(rf'{other}[.．)）]', v):
                        if not v.startswith(other):
                            opt_merge += 1
                            break
    print(f"\nOption stats: missing={opt_missing}, merge={opt_merge}")

    # Save
    CHKD.mkdir(parents=True, exist_ok=True)
    RPT.mkdir(parents=True, exist_ok=True)
    json.dump(questions, (CHKD / "parsed_ready_past_papers.json").open("w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"Saved parsed JSON")

    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return

    # Import to DB
    db = SessionLocal()
    deleted = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
    ).delete()
    db.commit()
    print(f"Deleted {deleted} old CN past papers")

    ins = 0
    for q in questions:
        item = models.ExamQuestionBank(
            subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
            source_type="past_paper", visibility="public",
            knowledge_point_id="", knowledge_point_name="",
            knowledge_point_path="",
            year=q['year'], question_number=q['question_number'],
            question_type=q['question_type'],
            stem=q['question_text'],
            options_json=json.dumps(q.get('options', {}), ensure_ascii=False),
            standard_answer=q.get('answer', ''),
            analysis="",
            difficulty="基础",
            source_ref=f"past_paper:{q['source_ref']}",
            quality_status=q['text_quality'],
            is_active=True,
        )
        db.add(item); ins += 1
    db.commit()

    act = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.is_active == True,
    ).count()
    nrv_db = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.quality_status == "need_review",
    ).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active (need_review={nrv_db})")

    # Verify other data intact
    db2 = SessionLocal()
    os_ch = db2.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == "operating_system",
        models.ExamQuestionBank.source_type == "chapter",
    ).count()
    cn_ch = db2.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == "computer_network",
        models.ExamQuestionBank.source_type == "chapter",
    ).count()
    os_pp = db2.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == "operating_system",
        models.ExamQuestionBank.source_type == "past_paper",
    ).count()
    db2.close()
    print(f"Verify: CN_chapter={cn_ch}, OS_chapter={os_ch}, OS_past_paper={os_pp}")

if __name__ == "__main__":
    main()
