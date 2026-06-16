"""Build operating_system chapter questions from annotated TXT."""
import json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

TXT = BASE / "exam_resources/11408/operating_system/chapter_practice/raw/2027操作系统_原创配套习题_全章总汇_带知识点标注.txt"
CHKD = BASE / "exam_resources/11408/operating_system/chapter_practice/checked"
RPT = BASE / "exam_resources/11408/operating_system/chapter_practice/import_reports"

SEC_TITLES = {
    "1.1":"操作系统的基本概念","1.2":"操作系统发展历程","1.3":"操作系统运行环境","1.4":"操作系统结构","1.5":"操作系统引导","1.6":"虚拟机",
    "2.1":"进程与线程简介","2.2":"CPU调度","2.3":"同步与互斥","2.4":"死锁",
    "3.1":"内存管理概述","3.2":"虚拟内存管理",
    "4.1":"文件系统基础","4.2":"目录与文件","4.3":"文件系统",
    "5.1":"I/O管理概述","5.2":"设备管理与调度","5.3":"磁盘和固态硬盘",
}
CH_TITLES = {
    1:"计算机系统概述",2:"进程与线程",3:"内存管理",4:"文件管理",5:"输入/输出管理",
}
SUBJECT_KEY = "operating_system"
SUBJECT_NAME = "操作系统"

def norm(raw_kp):
    """Normalize knowledge point to chapter+section."""
    m = re.match(r'(\d+)\.(\d+)', raw_kp)
    if not m: return (0, "", raw_kp, "")
    ch = int(m.group(1))
    sec = f"{ch}.{m.group(2)}"
    sn = SEC_TITLES.get(sec, raw_kp)
    cn = CH_TITLES.get(ch, f"第{ch}章")
    return (ch, sec, sn, cn)

def parse(fp):
    qs = []; rejected = []
    lines = Path(fp).read_text(encoding="utf-8").split('\n')
    i = 0; n = len(lines); kp = ""

    while i < n:
        l = lines[i].strip()

        # Knowledge point banner
        km = re.match(r'【知识点：(.+?)】', l)
        if km:
            kp = km.group(1).strip()
            i += 1; continue

        # Question: "N. 【题型】stem" (chapter 1 format) or "NNN. stem" (chapters 2-5 format)
        qm_typed = re.match(r'^(\d+)\.\s*【(.+?)】\s*(.+)', l)
        qm_plain = re.match(r'^(\d+)\.\s+(.+)', l) if not qm_typed else None

        if qm_typed or qm_plain:
            if qm_typed:
                qnum = int(qm_typed.group(1))
                qtype_label = qm_typed.group(2)
                stem = qm_typed.group(3).strip()
                qtype = "big" if "综合" in qtype_label or "大题" in qtype_label else "choice"
            else:
                qnum = int(qm_plain.group(1))
                stem = qm_plain.group(2).strip()
                qtype = None  # Will determine from options

            opts = {}; ans = ""; j = i + 1

            # Read options/answer from subsequent lines
            while j < n and j < i + 10:
                nl = lines[j]
                # Option line: "   A. ..."
                om = re.match(r'^\s*([A-D])[.．、]\s*(.+)', nl)
                if om and not re.match(r'^\d+\.', nl.strip()):
                    opts[om.group(1)] = om.group(2).strip()
                # Answer line: "   答案：..."
                elif re.search(r'^答案[：:]', nl.strip()):
                    am = re.search(r'答案[：:]\s*(.+)', nl)
                    if am:
                        ans = am.group(1).strip()
                        ans = re.sub(r'^答案要点[：:]\s*', '', ans)
                    j += 1; break
                # Next question or KP banner
                elif re.match(r'^\d+\.\s*【', nl.strip()) or re.match(r'【知识点：', nl.strip()) or re.match(r'^\d+\.\s+\S', nl.strip()):
                    break
                j += 1

            ch, sec, sn, cn = norm(kp)
            has_all_abcd = all(k in opts for k in ['A', 'B', 'C', 'D'])

            # If qtype not explicitly tagged, determine from options
            if qtype is None:
                qtype = "choice" if has_all_abcd else "big"

            if has_all_abcd and qtype == "choice":
                pass  # valid choice
            elif qtype == "big" and len(opts) == 0 and ans:
                pass  # valid big with answer
            elif qtype == "big" and len(opts) == 0 and not ans:
                # Big question without answer — still accept but warn
                pass
            elif len(opts) > 0 and not has_all_abcd:
                rejected.append({"ch": ch, "kp": sec, "kp_name": sn, "ch_title": cn, "raw_kp": kp,
                    "type": "choice_partial", "stem": stem, "opts": opts, "ans": ans,
                    "reason": f"partial options: {sorted(opts.keys())}"})
                i = j; continue
            elif qtype == "choice" and not has_all_abcd:
                # Choice question without A/B/C/D — treat as big if answer exists
                if ans:
                    qtype = "big"
                    opts = {}
                else:
                    rejected.append({"ch": ch, "kp": sec, "kp_name": sn, "ch_title": cn, "raw_kp": kp,
                        "type": "choice_no_opts", "stem": stem, "opts": {}, "ans": ans,
                        "reason": "choice without options and no answer"})
                    i = j; continue

            qs.append({
                "ch": ch, "kp": sec, "kp_name": sn, "ch_title": cn, "raw_kp": kp,
                "type": qtype, "stem": stem, "opts": opts, "ans": ans
            })
            i = j; continue

        i += 1
    return qs, rejected

def main():
    dry_run = "--dry-run" in sys.argv
    qs, rejected = parse(TXT)
    t = len(qs); c = sum(1 for q in qs if q["type"] == "choice"); b = t - c; r = len(rejected)
    print(f"Parsed: {t} (choice={c}, big={b}, rejected={r})")

    # Validation
    choice_no_opts = [q for q in qs if q["type"] == "choice" and len(q.get("opts", {})) == 0]
    choice_missing = [q for q in qs if q["type"] == "choice" and not all(k in q.get("opts", {}) for k in ['A', 'B', 'C', 'D'])]
    no_kp = [q for q in qs if not q.get("kp")]
    no_ans = [q for q in qs if not q.get("ans")]
    if choice_no_opts: print(f"WARNING: {len(choice_no_opts)} choice with empty opts!")
    if choice_missing: print(f"WARNING: {len(choice_missing)} choice missing A/B/C/D!")
    if no_kp: print(f"WARNING: {len(no_kp)} no knowledge point!")
    if no_ans: print(f"WARNING: {len(no_ans)} no answer!")

    chc = defaultdict(int); sec = defaultdict(int)
    for q in qs: chc[q["ch"]] += 1; sec[q["kp"]] += 1
    for ch in sorted(chc): print(f"  Ch{ch}: {chc[ch]}")
    for k in sorted(sec): print(f"  {k}: {sec[k]}")

    CHKD.mkdir(parents=True, exist_ok=True); RPT.mkdir(parents=True, exist_ok=True)
    json.dump(qs, (CHKD / "parsed_ready.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(rejected, (CHKD / "parsed_rejected.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    rp = {
        "total": t, "choice": c, "big": b, "rejected": r,
        "choice_no_opts": len(choice_no_opts), "choice_missing_abcd": len(choice_missing),
        "no_kp": len(no_kp), "no_answer": len(no_ans),
        "per_chapter": {str(k): v for k, v in sorted(chc.items())},
        "per_section": {k: v for k, v in sorted(sec.items())},
    }
    json.dump(rp, (RPT / "operating_system_chapter_questions_report.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
    (RPT / "operating_system_chapter_questions_report.md").write_text(
        f"# OS Chapter Questions Report\n- total: {t} (choice={c}, big={b}, rejected={r})\n" +
        "\n".join(f"- Ch{ch}: {chc[ch]}" for ch in sorted(chc)), encoding="utf-8")
    print("Reports saved")

    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return

    # Import
    db = SessionLocal()
    db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "chapter"
    ).update({"is_active": False})
    db.commit()

    ins = 0
    for q in qs:
        it = models.ExamQuestionBank(
            subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
            source_type="chapter", visibility="public",
            knowledge_point_id=q["kp"], knowledge_point_name=q["kp_name"],
            knowledge_point_path=f"{q['ch_title']} / {q['kp_name']}",
            question_type="choice" if q["type"] == "choice" else "big",
            stem=q["stem"], options_json=json.dumps(q.get("opts", {}), ensure_ascii=False),
            standard_answer=q.get("ans", ""), analysis="", difficulty="基础",
            source_ref=f"annotated:{q['raw_kp']}", is_active=True,
        )
        db.add(it); ins += 1
    db.commit()
    act = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SUBJECT_KEY,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.is_active == True,
    ).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active")

if __name__ == "__main__":
    main()
