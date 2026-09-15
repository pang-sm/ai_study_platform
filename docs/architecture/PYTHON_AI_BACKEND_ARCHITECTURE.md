# Python AI Backend Architecture

Frozen 2026-09-15.

## Decision

```text
JAVA MIGRATION = CANCELLED
PYTHON + FASTAPI = PRIMARY PRODUCT BACKEND
PYTHON SCIENTIFIC RUNTIME = SEPARATE PROCESS
```

Rationale (technical, not emotional):

- The workload is AI/ML-native. The scientific components (`zhixue_runtime`, StudentTwin,
  IRT, misconception, etc.) live in the Python scientific ecosystem.
- A Java modular monolith would re-implement the Product Data Plane + runtime client
  against the existing SQLite schema without reducing the core complexity.
- Cross-language contract/serialization/identity (UUIDv5, canonical JSON hashing) added
  friction with insufficient benefit at this scale.

## Long-term architecture

```text
React Frontend
       │
       ▼
FastAPI Product Backend (backend/)
       │
       ├───────────────┐
       │               │
       ▼               ▼
Product DB        External AI Gateway
       │          DeepSeek/Qwen/...
       │
       ▼
LearningEvent
       │
       ▼
Data Producer Worker (backend/data_plane/worker.py, manual --once)
       │
       │ localhost typed HTTP
       ▼
Scientific Runtime Service (scientific_runtime_service/, 127.0.0.1:8101)
       │
       ▼
zhixue_runtime  (get_adapter("student_twin"))
       │
   scientific models
```

## Three Python execution boundaries

### Process A — Product Backend (`backend/`)

Owns: auth, users, course learning, 11408, programming, materials, practice, payments,
admin, LearningEvent emission, product APIs, external LLM orchestration.

Must NOT import: `torch`, `transformers`, `faiss`, `zhixue_runtime`, `runtime_src`.

### Process B — Data Producer Worker (`backend/data_plane/worker.py`)

Owns: read LearningEvent → evaluate eligibility → build inference request → call Scientific
Runtime Service → persist ModelVersion / ModelInferenceRun / ModelPrediction.

It is PRODUCT DATA PLANE. It does NOT run scientific formulas in-process.

### Process C — Scientific Runtime Service (`scientific_runtime_service/`)

Owns ONLY: scientific inference. Uses `zhixue_runtime` public API.

Must NOT: access product DB, auth, payments, course business logic, user-facing decisions.

## Ports / binding

| Service | Port | Binding |
|---------|------|---------|
| Product Backend (FastAPI) | 8000 | 127.0.0.1 (nginx front) |
| Scientific Runtime Service | 8101 | 127.0.0.1 ONLY (no public, no nginx proxy) |

## Product Backend structure

```text
backend/
    main.py                 # composition root / compatibility entrypoint (existing)
    core/
        config.py           # centralized env config (no secrets)
    data_plane/
        models.py           # LearningEvent/ModelVersion/ModelInferenceRun/ModelPrediction
        identity.py         # deterministic event/run/prediction identity (UUIDv5)
        snapshots.py        # item snapshot + knowledge-point-ref
        emitter.py          # post-commit LearningEvent emission (Phase 2B1)
        backfill.py         # historical backfill (NOT_APPLIED)
        eligibility.py      # 13-component eligibility matrix
        inference.py        # ModelVersion/InferenceRun/Prediction persistence
        runtime_client.py   # HTTP client to Scientific Runtime Service + event mapping
        worker.py           # DataProducerWorker (manual --once)
```

New code goes OUT of `main.py`; existing stable routes stay for now (incremental
modularization — no big-bang rewrite of the ~20k-line `main.py`).

## Scientific Runtime Service structure

```text
scientific_runtime_service/
    app/
        __init__.py
        main.py             # /health /v1/capabilities /v1/inference/student-twin
        config.py           # frozen release id + provenance constants
        contracts.py        # typed StudentTwin DTOs (contract v1)
        runtime_bridge.py   # get_adapter("student_twin") + deterministic replay
    tests/
    requirements.txt        # numpy + fastapi + uvicorn + pydantic (NO torch/transformers)
    run.py
```

## StudentTwin contract (v1)

Request: `contract_version, request_id, runtime_release_id, user_ref, target_event_id,
events[]`. Each event: `event_id, occurred_at, activity_type, item_id, concept_ref, correct,
response_time_ms, attempt_no, hints`. Optional fields are `null` — never fabricated.

Response: `contract_version, request_id, runtime_release_id, component_id,
scientific_source_class, scientific_source_commit, target_event_id, replayed_events, state,
latency_ms`. `state` comes only from `zhixue_runtime`.

## Runtime packaging

`zhixue-runtime-v1-phase1gr-p1` — ENGINEERING_PACKAGING_ONLY patch: lazy adapter import so
`get_adapter("student_twin")` pulls in only numpy (not torch/transformers/faiss/pandas).

- `scientific_runtime_changed = false`
- `scientific_outputs_changed = false`
- `scientific_source_hashes_changed = false`
- `SCIENTIFIC_OUTPUT_DRIFT = 0`

## Dependency boundary

- Product Backend: `torch=NOT_IMPORTED`, `transformers=NOT_IMPORTED`, `faiss=NOT_IMPORTED`,
  `zhixue_runtime=NOT_IMPORTED` (hard gate, verified in fresh process).
- Scientific Runtime: separate venv (`/opt/zhixue-runtime/`), `numpy` only for StudentTwin.
- Product venv (`backend/.venv`) != Scientific Runtime venv (never merged).

## DB ownership

| Table | Owner |
|-------|-------|
| learning_events | Product Backend (FastAPI emitter) |
| model_versions | Product Data Plane (worker) |
| model_inference_runs | Product Data Plane (worker) |
| model_predictions | Product Data Plane (worker) |

Scientific Runtime Service never touches the product DB.

## Inference ownership

- Eligibility: Product Data Plane (`eligibility.py`) — "should we call a science capability?"
- Event selection / ordering / no-future-leakage: Product Worker.
- Scientific replay → StudentState: Scientific Runtime Service.
- Persistence: Product Data Plane (`inference.py`).

## Deployment

- `ai-backend.service` → Product FastAPI (127.0.0.1:8000)
- `zhixue-runtime.service` → Scientific Runtime FastAPI (127.0.0.1:8101)
- DataProducerWorker = manual `--once` (no scheduler). `DATA_PRODUCER_EXECUTION_ENABLED=false`
  by default (first deploy inference OFF).

## Product safety

StudentTwin is `DATA_PRODUCER` only (`controls_product_decision=false`). It never changes
user-visible behavior, scoring, recommendations, learning plans, or the frontend.
