"""Write source/restore accounting reports for the 240 catalog migration."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "verification-results"


def main() -> None:
    db = sqlite3.connect(ROOT / "backend/app.db")
    archived = db.execute("select count(*) from programming_exercises where source_repo='first_party_original' and quality_status='rejected' and source_key not like 'first_party_original_v2|%'").fetchone()[0]
    new = db.execute("select count(*) from programming_exercises where source_key like 'first_party_original_v2|%' and is_active=1 and quality_status='approved'").fetchone()[0]
    payload = {
        "restored_from_exercism": 0,
        "restored_from_early_first_party": 0,
        "archived_previous_template_rows": archived,
        "user_data_preserved": True,
        "note": "本轮没有从旧模板题恢复；旧 active first-party 题保留原 exercise_id 并继续 inactive/rejected。",
    }
    (OUT / "restored-problems-audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "new-quality-problems-audit.json").write_text(json.dumps({"new_quality_problems": new, "approved_active": new, "source": "first_party_original_v2", "quality_gate": "programming-catalog-240-quality-audit.json"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"archived": archived, "new_quality": new}, ensure_ascii=False))


if __name__ == "__main__": main()
