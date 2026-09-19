# zhixue-runtime service (Python scientific runtime)

Stateless scientific inference service. It owns **no** product data and **no** product
decisions — it executes the components below over inputs the Product Backend has already
selected, ordered and made real.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | liveness (status, runtime_release_id, component) |
| GET | `/v1/capabilities` | which components this service exposes |
| POST | `/v1/inference/student-twin` | deterministic StudentTwin replay → state |
| POST | `/v1/inference/misconception-v2` | candidate-misconception retrieval → similarity |
| POST | `/v1/inference/tutor-policy` | suggested pedagogical action (focus/generic/probing/telling) |
| POST | `/v1/inference/learner-state` | knowledge tracing → next-response P(correct) |
| POST | `/v1/inference/evidence-reliability` | reliability-weight PANEL (5 variants) |

An endpoint existing here means the component is **reachable** — it does not mean the
product can honestly feed it or show it. Product-facing readiness is reported by the
Product Backend at `GET /exam/prep/scientific/capabilities`.

## Binding

`127.0.0.1:8101` (never exposed to the public internet). Nginx must NOT proxy it.

## Runtime release

`zhixue-runtime-v1-phase1gr-p1` (engineering packaging patch: lazy adapter import).
Scientific source hashes and outputs are unchanged from `zhixue-runtime-v1-phase1gr`.

## Minimal dependency closure

Only `numpy` (+ stdlib `sqlite3`) is required for the StudentTwin execution path.
`torch` / `transformers` / `faiss` / `pandas` are **not** installed and **not** imported
(verified by `tests/test_imports.py` in a fresh process).

## Run

```bash
# dedicated venv (NOT backend/.venv)
ZHIXUE_HOME=/opt/zhixue/.../zhixue-runtime-v1-phase1gr-student-twin \
ZHIXUE_RUNTIME_SRC=/opt/zhixue/.../zhixue-runtime-v1-phase1gr-student-twin/src \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8101
```

## Tests

```bash
.venv/bin/pytest -q
```
