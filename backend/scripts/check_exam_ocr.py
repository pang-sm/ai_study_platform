"""Check 11408 exam OCR results and generate self-check reports.
Usage: python scripts/check_exam_ocr.py --subject data_structure
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exam_paper_parser import EXAM_SUBJECTS, CACHE_DIR


def check_question(q, year):
    issues = []
    qtype = q.get("type", "")
    stem = q.get("stem") or q.get("content") or ""
    opts = q.get("options") or {}
    answer = (q.get("answer") or "").strip()
    images = q.get("image_urls") or []
    ocr_quality = q.get("ocr_quality", "none")
    need_check = q.get("need_manual_check", False)

    is_choice = "选择" in qtype
    is_big = "大题" in qtype or "大" in qtype

    status = "ok"

    # Stem check
    if not stem.strip() or stem.strip() == f"第 {q.get('number',0)} 题":
        issues.append("stem为空")
        status = "error"
    elif len(stem) < 10:
        issues.append(f"stem过短({len(stem)}字符)")
        status = "warning"

    # Options check (only for choice questions)
    options_complete = False
    if is_choice:
        missing = []
        for label in ["A", "B", "C", "D"]:
            if not (opts.get(label) or "").strip():
                missing.append(label)
        if missing:
            issues.append(f"选项缺失: {','.join(missing)}")
            status = "warning" if not issues else status
        else:
            options_complete = True
    else:
        options_complete = True  # N/A for big questions

    # Answer check
    if not answer:
        issues.append("答案缺失")
        status = "warning" if not issues else status

    # Image check
    has_images = len(images) > 0

    # OCR quality
    if ocr_quality == "failed":
        issues.append("OCR失败")
        status = "error"
    elif ocr_quality == "none":
        issues.append("未OCR")
        status = "warning" if not issues else status

    if need_check:
        issues.append("需人工检查")

    # Determine overall status
    if not issues:
        status = "ok"
    elif not status:
        status = "warning"

    return {
        "number": q.get("number", 0),
        "type": qtype,
        "stem_length": len(stem),
        "options_complete": options_complete,
        "answer": answer,
        "has_images": has_images,
        "ocr_quality": ocr_quality,
        "need_manual_check": need_check,
        "status": status,
        "issues": issues,
    }


def check_year(subject_key, year):
    cache_file = CACHE_DIR / subject_key / f"{year}.ocr.json"
    if not cache_file.exists():
        return {"total": 0, "choice_count": 0, "big_count": 0, "complete": 0, "problems": 0, "questions": []}
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    results = []
    choice_count = 0
    big_count = 0
    problem_count = 0
    for q in questions:
        r = check_question(q, year)
        results.append(r)
        if "选择" in (q.get("type") or ""):
            choice_count += 1
        else:
            big_count += 1
        if r["status"] != "ok":
            problem_count += 1
    return {
        "total": len(results),
        "choice_count": choice_count,
        "big_count": big_count,
        "complete_count": len(results) - problem_count,
        "problem_count": problem_count,
        "questions": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="data_structure", choices=list(EXAM_SUBJECTS.keys()))
    args = parser.parse_args()
    sk = args.subject
    sn = EXAM_SUBJECTS[sk]
    years = [2022, 2023, 2024, 2025, 2026]

    all_data = {}
    problems = []
    # Prevent emoji encoding issues on Windows console
    import io, locale
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except: pass
    print(f"\n11408 {sn} 真题 OCR 自检")

    # Overview table
    print("## 总览\n")
    print("| 年份 | 总题数 | 选择题 | 大题 | 完整题 | 异常题 | 状态 |")
    print("|---|---:|---:|---:|---:|---:|---|")
    for year in years:
        yd = check_year(sk, year)
        all_data[str(year)] = yd
        status = "[OK]" if yd["problem_count"] == 0 else "[!!]"
        print(f"| {year} | {yd['total']} | {yd['choice_count']} | {yd['big_count']} | {yd['complete_count']} | {yd['problem_count']} | {status} |")
        for qr in yd["questions"]:
            if qr["status"] != "ok":
                problems.append({"year": year, **qr})

    # Per-year detail
    for year in years:
        yd = all_data[str(year)]
        print(f"\n## {year} 年\n")
        print("| 题号 | 类型 | stem字符 | 选项完整 | 答案 | 图片 | OCR质量 | 人工检查 | 状态 |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for qr in yd["questions"]:
            s = qr["status"]
            emoji = {"ok": "[OK]", "warning": "[!!]", "error": "❌"}.get(s, "❓")
            print(f"| {qr['number']} | {qr['type']} | {qr['stem_length']} | {'✅' if qr['options_complete'] else '❌'} | {qr['answer']} | {'✅' if qr['has_images'] else '❌'} | {qr['ocr_quality']} | {'是' if qr['need_manual_check'] else '否'} | {emoji} |")

    # Problems
    if problems:
        print(f"\n## 异常题列表 ({len(problems)} 题)\n")
        for p in problems:
            issues_str = "; ".join(p["issues"])
            print(f"- **{p['year']} 第 {p['number']} 题** ({p['type']}): {issues_str} (stem={p['stem_length']}chars)")

    # Samples
    print("\n## 样例题预览\n")
    for year in years:
        yd = all_data[str(year)]
        data = json.loads((CACHE_DIR / sk / f"{year}.ocr.json").read_text(encoding="utf-8"))
        qs = data.get("questions", [])
        choice_q = next((q for q in qs if "选择" in (q.get("type") or "")), None)
        big_q = next((q for q in qs if "大" in (q.get("type") or "")), None)
        print(f"### {year} 年")
        if choice_q:
            print(f"**选择题 #{choice_q['number']}**")
            print(f"> {choice_q.get('stem','')[:200]}")
            opts = choice_q.get("options", {})
            for lbl in ["A","B","C","D"]:
                if opts.get(lbl):
                    print(f"- {lbl}: {opts[lbl][:100]}")
        if big_q:
            print(f"\n**大题 #{big_q['number']}**")
            print(f"> {big_q.get('stem','')[:200]}")
        print()

    # Save reports
    cache_dir = CACHE_DIR / sk
    md_path = cache_dir / "ocr_check_report.md"
    # Regenerate MD output directly
    lines = []
    lines.append(f"# 11408 {sn} 真题 OCR 自检报告\n")
    lines.append("## 总览\n")
    lines.append("| 年份 | 总题数 | 选择题 | 大题 | 完整题 | 异常题 | 状态 |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for year in years:
        yd = all_data[str(year)]
        status_icon = "[OK]" if yd["problem_count"] == 0 else "[!!]"
        lines.append(f"| {year} | {yd['total']} | {yd['choice_count']} | {yd['big_count']} | {yd['complete_count']} | {yd['problem_count']} | {status_icon} |")
    for year in years:
        yd = all_data[str(year)]
        lines.append(f"\n## {year} 年\n")
        lines.append("| 题号 | 类型 | stem字符 | 选项完整 | 答案 | 图片 | OCR质量 | 人工检查 | 状态 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for qr in yd["questions"]:
            s = qr["status"]
            emoji = {"ok": "[OK]", "warning": "[!!]", "error": "❌"}.get(s, "❓")
            lines.append(f"| {qr['number']} | {qr['type']} | {qr['stem_length']} | {'✅' if qr['options_complete'] else '❌'} | {qr['answer']} | {'✅' if qr['has_images'] else '❌'} | {qr['ocr_quality']} | {'是' if qr['need_manual_check'] else '否'} | {emoji} |")
    if problems:
        lines.append(f"\n## 异常题列表 ({len(problems)} 题)\n")
        for p in problems:
            lines.append(f"- **{p['year']} 第 {p['number']} 题** ({p['type']}): {'; '.join(p['issues'])} (stem={p['stem_length']}chars)")
    for year in years:
        yd = all_data[str(year)]
        data = json.loads((CACHE_DIR / sk / f"{year}.ocr.json").read_text(encoding="utf-8"))
        qs = data.get("questions", [])
        choice_q = next((q for q in qs if "选" in (q.get("type") or "")), None)
        big_q = next((q for q in qs if "大" in (q.get("type") or "")), None)
        lines.append(f"\n### {year} 年")
        if choice_q:
            lines.append(f"**选择题 #{choice_q['number']}**")
            lines.append(f"> {choice_q.get('stem','')[:200]}")
            for lbl in ["A","B","C","D"]:
                v = (choice_q.get("options") or {}).get(lbl, "")
                if v: lines.append(f"- {lbl}: {v[:100]}")
        if big_q:
            lines.append(f"\n**大题 #{big_q['number']}**")
            lines.append(f"> {big_q.get('stem','')[:200]}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # JSON report
    for year in years:
        yd = all_data[str(year)]
        # Load real questions for sample stems
        data = json.loads((CACHE_DIR / sk / f"{year}.ocr.json").read_text(encoding="utf-8"))
        qs = data.get("questions", [])
        for qr in yd["questions"]:
            real_q = next((q for q in qs if q.get("number") == qr["number"]), None)
            if real_q:
                qr["stem_preview"] = real_q.get("stem", "")[:200]
                qr["options_preview"] = {k: v[:80] for k, v in real_q.get("options", {}).items()}

    json_report = {
        "subject_key": sk,
        "subject_name": sn,
        "years": {str(y): all_data[str(y)] for y in years},
        "problems": problems,
    }
    json_path = cache_dir / "ocr_check_report.json"
    json_path.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n报告已保存:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")
    print(f"  异常题:   {len(problems)} 题")


if __name__ == "__main__":
    main()
