"""Apply manual fixes to OCR JSON files from a fix template.
Usage: python scripts/apply_exam_ocr_manual_fixes.py --subject data_structure --fix-file <path>
"""
import argparse, json, os, shutil, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exam_paper_parser import EXAM_SUBJECTS, CACHE_DIR


def backup_file(path):
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = backup_dir / f"{path.name}.{ts}.bak"
    shutil.copy2(str(path), str(bak))
    return bak


def apply_fixes(subject_key, fix_file):
    if not fix_file.exists():
        print(f"ERROR: Fix file not found: {fix_file}")
        return

    template = json.loads(fix_file.read_text(encoding="utf-8"))
    items = template.get("items", [])
    if not items:
        print("No items to fix.")
        return

    print(f"Applying {len(items)} manual fixes for {EXAM_SUBJECTS[subject_key]}...\n")

    fixed_count = 0
    by_year = {}
    for item in items:
        year = item["year"]
        by_year.setdefault(year, []).append(item)

    for year, year_items in sorted(by_year.items()):
        cache_file = CACHE_DIR / subject_key / f"{year}.ocr.json"
        if not cache_file.exists():
            print(f"  SKIP {year}: OCR cache not found")
            continue

        # Backup
        bak = backup_file(cache_file)
        print(f"  Backup: {bak.name}")

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        questions = data.get("questions", [])
        year_fixed = 0

        for item in year_items:
            num = item["number"]
            fix = item.get("fix_fields", {})
            notes = item.get("notes", "")

            q = next((q for q in questions if q["number"] == num), None)
            if not q:
                print(f"    Q{num}: NOT FOUND in cache")
                continue

            changed = []
            # Stem
            if fix.get("stem", "").strip():
                q["stem"] = fix["stem"].strip()
                changed.append("stem")
            # Options
            opts_fix = fix.get("options", {})
            if opts_fix:
                for lbl in ["A", "B", "C", "D"]:
                    if opts_fix.get(lbl, "").strip():
                        if "options" not in q:
                            q["options"] = {}
                        q["options"][lbl] = opts_fix[lbl].strip()
                        changed.append(f"options.{lbl}")
            # Answer
            if fix.get("answer", "").strip():
                q["answer"] = fix["answer"].strip()
                changed.append("answer")

            if changed:
                q["manual_fixed"] = True
                q["need_manual_check"] = False
                q["ocr_quality"] = "manual"
                if notes:
                    q["fix_notes"] = notes
                year_fixed += 1
                print(f"    Q{num} ({item['type']}): fixed {', '.join(changed)}")
            else:
                print(f"    Q{num} ({item['type']}): no non-empty fix fields, SKIPPED")

        if year_fixed > 0:
            cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            fixed_count += year_fixed

    print(f"\nTotal fixed: {fixed_count} questions")

    # Re-run check
    print("\n--- Post-fix Check ---")
    from scripts.check_exam_ocr import check_year
    problems_remaining = []
    for year in sorted(by_year.keys()):
        yd = check_year(subject_key, year)
        probs = [q for q in yd["questions"] if q["status"] != "ok"]
        problems_remaining.extend({"year": year, **p} for p in probs)
        print(f"  {year}: {yd['total']} total, {yd['problem_count']} problems remaining")
        for qr in probs:
            print(f"    Q{qr['number']}: {', '.join(qr['issues'])}")

    stem_missing = [p for p in problems_remaining if "stem为空" in p.get("issues", [])]
    opt_missing = [p for p in problems_remaining if any("选项缺失" in i for i in p.get("issues", []))]
    ans_missing = [p for p in problems_remaining if any("答案缺失" in i for i in p.get("issues", []))]

    print(f"\nRemaining after fix:")
    print(f"  Still missing stem: {len(stem_missing)}")
    print(f"  Still missing options: {len(opt_missing)}")
    print(f"  Still missing answer: {len(ans_missing)}")
    print(f"  Total remaining problems: {len(problems_remaining)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="data_structure", choices=list(EXAM_SUBJECTS.keys()))
    parser.add_argument("--fix-file", required=True)
    args = parser.parse_args()
    apply_fixes(args.subject, Path(args.fix_file) if not isinstance(args.fix_file, Path) else args.fix_file)


if __name__ == "__main__":
    from pathlib import Path
    main()
