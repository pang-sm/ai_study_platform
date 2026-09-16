"""STEP 7C: representative endpoint migrated through the orchestrator (no live API)."""
from unittest.mock import patch

from ai.providers import FakeProvider
from conftest import register_and_login


def test_question_analysis_uses_orchestrator(client):
    register_and_login(client, "mig_1")
    with patch("ai.orchestrator.default_provider_factory",
               return_value=FakeProvider(provider="deepseek", model="deepseek-chat")):
        r = client.post(
            "/exam/11408/operating_system/question-analysis",
            json={"stem": "什么是进程？", "question_type": "选择题",
                  "standard_answer": "A", "user_answer": "B",
                  "options": {"A": "进程", "B": "线程"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["analysis"] == "fake response"
    assert body.get("request_id")
    assert body.get("model") == "deepseek-flash"


def test_question_analysis_requires_stem(client):
    register_and_login(client, "mig_2")
    r = client.post("/exam/11408/operating_system/question-analysis", json={"stem": ""})
    assert r.status_code == 400
