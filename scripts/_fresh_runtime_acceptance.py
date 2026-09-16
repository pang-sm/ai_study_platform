"""STEP 7A fresh-process runtime acceptance (one-shot, not a permanent artifact).

Starts a NEW Scientific Runtime Service on a dynamically-chosen free port (NOT 8101),
verifies /health + a real StudentTwin inference via the product runtime_client, then
terminates ONLY the process this script started.
"""
import os
import socket
import subprocess
import sys
import time

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

RUNTIME_SVC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scientific_runtime_service"))
RUNTIME_PY = r"D:\ZhixueAI\envs\runtime-service\Scripts\python.exe"
ZHIXUE_RUNTIME_SRC = r"D:\ZhixueAI\runtime_package\v1\src"
ZHIXUE_HOME = r"D:\ZhixueAI"


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    port = free_port()
    env = dict(os.environ)
    env["ZHIXUE_RUNTIME_SRC"] = ZHIXUE_RUNTIME_SRC
    env["ZHIXUE_HOME"] = ZHIXUE_HOME

    proc = subprocess.Popen(
        [RUNTIME_PY, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=RUNTIME_SVC_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pid = proc.pid
    base = f"http://127.0.0.1:{port}"

    import httpx
    health_ok = False
    for _ in range(60):
        try:
            r = httpx.get(base + "/health", timeout=1.0)
            if r.status_code == 200:
                health_ok = True
                break
        except Exception:
            time.sleep(0.25)

    if not health_ok:
        proc.terminate()
        print("FRESH_PROCESS_HEALTH_PASS = NO")
        sys.exit(1)

    from data_plane import runtime_client as rc
    client = rc.StudentTwinRuntimeClient(base_url=base, timeout=15.0)
    request = {
        "contract_version": 1,
        "request_id": "fresh-proc-1",
        "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
        "user_ref": "u-fresh",
        "target_event_id": "e2",
        "events": [
            {"event_id": "e1", "occurred_at": 1000.0, "activity_type": "PRACTICE",
             "item_id": "q1", "concept_ref": "c1", "correct": False,
             "source": "course_practice", "response_time_ms": None, "attempt_no": None, "hints": None},
            {"event_id": "e2", "occurred_at": 1060.0, "activity_type": "PRACTICE",
             "item_id": "q1", "concept_ref": "c1", "correct": True,
             "source": "course_practice", "response_time_ms": None, "attempt_no": None, "hints": None},
        ],
    }
    resp = client.infer(request)
    inference_ok = (
        resp.get("component_id") == "student_twin"
        and resp.get("replayed_events") == 2
        and resp.get("contract_version") == 1
        and "state" in resp and "concepts" in resp["state"]
    )

    # deterministic replay check
    resp2 = client.infer(request)
    determinism_ok = resp2.get("state") == resp.get("state")

    # terminate ONLY our own PID
    proc.terminate()
    try:
        proc.wait(timeout=10)
        exited = proc.returncode is not None
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        exited = proc.returncode is not None

    print(f"FRESH_RUNTIME_PID = {pid}")
    print(f"FRESH_RUNTIME_PORT = {port}")
    print("FRESH_PROCESS_STARTED_BY_THIS_RUN = YES")
    print(f"FRESH_PROCESS_HEALTH_PASS = {'YES' if health_ok else 'NO'}")
    print(f"FRESH_PROCESS_INFERENCE_PASS = {'YES' if inference_ok else 'NO'}")
    print(f"FRESH_PROCESS_DETERMINISM_PASS = {'YES' if determinism_ok else 'NO'}")
    print(f"FRESH_PROCESS_CLEANUP_PASS = {'YES' if exited else 'NO'}")
    print("FRESH_PROCESS_RUNTIME_ACCEPTANCE = "
          + ("PASS" if (health_ok and inference_ok and determinism_ok and exited) else "FAIL"))


if __name__ == "__main__":
    main()
