"""
Auth V2 real acceptance: create a fresh user through the formal register flow,
grant exam_11408 study-plan access through the formal membership order flow,
and verify the preserved 11408 operating-system study plan is served.

Runs against the REAL backend/app.db (no temp DB). Email code is captured in
test env because there is no SMTP inbox (documented test-env email capture);
the study-plan request itself is executed by the real app against real data.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ["DATABASE_URL"] = f"sqlite:///{(BACKEND / 'app.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


USERNAME = "acceptance_v2_user"
EMAIL = "acceptance_v2@example.test"
PASSWORD = "secret123"


def walk(nodes, path=""):
    for i, node in enumerate(nodes or [], start=1):
        p = f"{path}.{i}" if path else str(i)
        yield p, node
        yield from walk(node.get("children") or [], p)


def main_run() -> int:
    captured: list[str] = []

    def capture_email(_recipient, code):
        captured.append(code)
        return True

    results = {}
    with TestClient(main.app) as client:
        # 1. Register through the formal email-verification flow.
        with patch.object(main, "_send_email_code", side_effect=capture_email):
            sent = client.post("/auth/register/send-code", json={"email": EMAIL})
        results["register_send_code"] = sent.status_code
        if sent.status_code != 200:
            print("register/send-code FAILED:", sent.status_code, sent.text)
            return 1

        verified = client.post("/auth/register/verify-code", json={"email": EMAIL, "code": captured[-1]})
        results["register_verify_code"] = verified.status_code
        register = client.post("/register", json={"username": USERNAME, "password": PASSWORD, "email": EMAIL})
        results["register_create"] = register.status_code
        if register.status_code != 200:
            print("register FAILED:", register.status_code, register.text)
            return 1

        me = client.post("/me", json={})
        results["me_status"] = me.status_code
        profile = me.json()["user"]
        results["email_verified"] = profile.get("email_verified")
        results["session_cookie"] = "ai_session" in client.cookies

        # 2. Grant exam_11408 study-plan access via the formal order flow.
        order = client.post("/membership/orders", json={"service_key": "exam_11408", "target_plan": "monthly_sprint"})
        results["order_status"] = order.status_code
        if order.status_code != 200:
            print("order FAILED:", order.status_code, order.text)
            return 1
        order_id = order.json()["order"]["id"]
        pay = client.post(f"/membership/orders/{order_id}/pay")
        results["pay_status"] = pay.status_code
        results["paid_plan"] = pay.json().get("order", {}).get("target_plan") if pay.status_code == 200 else None

        # 3. Study plan must be served (200).
        plan = client.get("/exam/11408/subjects/operating_system/study-plan", params={"username": USERNAME})
        results["study_plan_status"] = plan.status_code
        if plan.status_code != 200:
            print("study-plan FAILED:", plan.status_code, plan.text)
            return 1

        body = plan.json()
        results["course_id"] = body.get("course_id")
        results["subject_name"] = body.get("subject_name")
        results["total_knowledge_points"] = body.get("stats", {}).get("total_knowledge_points")

        # 4. Extract the acceptance node(s) and their structural neighbors.
        print("\n=== 地址变换机构 / 页框分配 nodes ===")
        for path, node in walk(body.get("chapters")):
            title = node.get("title") or ""
            code = node.get("code") or ""
            if any(k in title for k in ("地址变换机构", "页框分配")):
                print(f"  path={path}  code={code!r}  title={title!r}")

        print("\n=== 3.2 虚拟内存管理 section subtree ===")
        for path, node in walk(body.get("chapters")):
            if path.startswith("3.2"):
                title = node.get("title") or ""
                code = node.get("code") or ""
                leaf = "LEAF" if node.get("is_leaf") else ""
                print(f"  {path}  code={code!r}  title={title!r}  {leaf}")

    print("\n=== ACCEPTANCE RESULTS ===")
    for k, v in results.items():
        print(f"  {k} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main_run())
