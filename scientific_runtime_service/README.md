# zhixue-runtime service (Python scientific runtime)

Stateless scientific inference service. It owns **no** product data and **no** product
decisions — it only runs `student_twin` deterministic replay over an event history that
the Java backend already selected and ordered.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | liveness (status, runtime_release_id, component) |
| GET | `/v1/capabilities` | which components this service exposes |
| POST | `/v1/inference/student-twin` | deterministic StudentTwin replay → state |

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
