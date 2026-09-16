"""Prove the runtime service pulls in no heavy deps (torch/transformers/faiss/pandas).

Runs in a FRESH subprocess so the assertion is not polluted by this pytest process.
"""
import json
import os
import subprocess
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZHIXUE = os.environ.get("ZHIXUE_HOME") or r"D:\ZhixueAI"

CHECK = r'''
import json, os, sys
os.environ["ZHIXUE_HOME"] = r"%ZHIXUE%"
os.environ["ZHIXUE_RUNTIME_SRC"] = r"%ZHIXUE%\runtime_package\v1\src"
sys.path.insert(0, r"%ROOT%")
from app.runtime_bridge import replay_state
from app.contracts import StudentTwinEvent
events = [
    StudentTwinEvent(event_id="e1", occurred_at=1000.0, activity_type="PRACTICE", correct=False, source="course_practice", concept_ref="c1"),
    StudentTwinEvent(event_id="e2", occurred_at=1060.0, activity_type="PRACTICE", correct=True, source="course_practice", concept_ref="c1"),
]
state = replay_state("u1", events)
assert state["user_id"] == "u1"
heavy = {m: (m in sys.modules) for m in ("torch", "transformers", "faiss", "pandas", "numpy")}
print(json.dumps(heavy))
'''


def test_no_heavy_imports():
    code = CHECK.replace("%ZHIXUE%", ZHIXUE).replace("%ROOT%", _ROOT)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    heavy = json.loads(r.stdout.strip().splitlines()[-1])
    assert heavy["torch"] is False
    assert heavy["transformers"] is False
    assert heavy["faiss"] is False
    assert heavy["pandas"] is False
    assert heavy["numpy"] is True
