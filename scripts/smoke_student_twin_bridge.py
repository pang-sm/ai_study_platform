"""End-to-end smoke test: product LearningEvent -> scientific StudentTwin snapshot.

Runs the REAL ``zhixue_runtime`` student_twin adapter (rule-based, deterministic, no
neural checkpoint).  Requires the runtime Python (which has numpy) — e.g.

    D:\\ZhixueAI\\envs\\runtime\\Scripts\\python.exe scripts/smoke_student_twin_bridge.py

It validates that the product bridge (``data_plane.student_twin_runtime``) maps a
LearningEvent correctly and replays a deterministic state, WITHOUT copying any scientific
formula into the product backend.  The scientific engine is the single source of truth.
"""
import json
import os
import sys
from types import SimpleNamespace

ZHIXUE_HOME = os.getenv("ZHIXUE_HOME") or r"D:\ZhixueAI"
os.environ["ZHIXUE_HOME"] = ZHIXUE_HOME

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
RUNTIME_SRC = os.path.join(ZHIXUE_HOME, "runtime_package", "v1", "src")
for p in (BACKEND, RUNTIME_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from data_plane import student_twin_runtime as bridge  # noqa: E402


def le(event_id, user_id, ts, correct, question_id="q1"):
    return SimpleNamespace(
        event_id=event_id, user_id=user_id, source_user_ref=f"user-{user_id}",
        occurred_at=ts, source_type="course_practice", course_id=None,
        subject_key="math", question_id=question_id, answer="B", correct=correct,
        response_time_ms=None, attempt_no=None,
        knowledge_point_ref_json=json.dumps({"type": "FREE_TEXT", "value": "kp1"}),
    )


def main():
    events = [
        le("e1", 1, 1000.0, False),
        le("e2", 1, 1060.0, False),
        le("e3", 1, 1120.0, True),
    ]

    # ── mapping: product LearningEvent -> scientific StudentTwin event ──
    m = bridge.map_event(events[0])
    assert m["activity_type"] == "PRACTICE"
    assert m["concept_id"] == "kp1"          # FREE_TEXT knowledge_point_ref value
    assert m["correctness"] is False
    # optional fields are NOT fabricated
    assert m["response_time_ms"] is None
    assert m["attempts"] is None
    assert m["hints"] is None

    # ── deterministic replay: two fresh replayers -> identical final state ──
    def replay():
        r = bridge.StudentTwinReplayer()
        try:
            for e in events:
                r.ingest(e)
            return r.state("1")
        finally:
            r.close()

    s1 = replay()
    s2 = replay()
    assert s1 == s2, "student_twin replay is not deterministic"
    assert s1["user_id"] == "1"
    assert "global_ability" in s1 and "concepts" in s1
    assert 0.0 <= s1["global_ability"] <= 1.0

    concept = s1["concepts"]["kp1"]
    assert concept["exposure_count"] == 3          # ordered multi-event replay accumulated
    assert concept["mastery_probability"] is not None

    print("student_twin bridge smoke PASS")
    print("  global_ability:", s1["global_ability"])
    print("  concept exposure_count:", concept["exposure_count"])
    print("  concept mastery_probability:", concept["mastery_probability"])


if __name__ == "__main__":
    main()
