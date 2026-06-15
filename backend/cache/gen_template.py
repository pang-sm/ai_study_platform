import json, os, sys
sys.path.insert(0, r"C:\Users\26477\Desktop\ai_study_platform\backend")
os.chdir(r"C:\Users\26477\Desktop\ai_study_platform\backend")
from exam_paper_parser import CACHE_DIR

sk = "data_structure"
# Collect all problematic questions with image_urls
problems = [
    (2022, 1), (2022, 4), (2022, 8), (2022, 9), (2022, 41),
    (2023, 5), (2023, 41),
    (2024, 5), (2024, 6), (2024, 10), (2024, 41),
    (2025, 1), (2025, 4), (2025, 8), (2025, 41),
    (2026, 2), (2026, 5), (2026, 8), (2026, 41),
]

items = []
for year, num in problems:
    cache_file = CACHE_DIR / sk / f"{year}.ocr.json"
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    q = next((q for q in data["questions"] if q["number"] == num), None)
    if q:
        item = {
            "year": year, "number": num,
            "type": q.get("type",""),
            "image_urls": q.get("image_urls", []),
            "current_stem": q.get("stem", ""),
            "current_options": q.get("options", {}),
            "answer": q.get("answer", ""),
            "fix_fields": {
                "stem": "",
                "options": {"A": "", "B": "", "C": "", "D": ""},
            },
            "notes": ""
        }
        items.append(item)
        print(f"  {year} Q{num}: imgs={len(q.get('image_urls',[]))} stem_len={len(q.get('stem',''))} opts={list(q.get('options',{}).keys())}")

template = {
    "subject_key": sk,
    "subject_name": "数据结构",
    "items": items
}
out = CACHE_DIR / sk / "manual_fix_template.json"
out.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nTemplate saved: {out}")
print(f"Total items: {len(items)}")
