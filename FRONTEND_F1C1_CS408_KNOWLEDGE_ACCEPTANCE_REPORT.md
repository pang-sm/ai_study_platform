# FRONTEND_F1C1 — CS408 Knowledge Workspace Acceptance Report

## Contract

`GET /exam/11408/subjects/{subject_key}/study-plan` uses generated `ExamStudyPlanResponse`; the knowledge-status PATCH uses generated `ExamKnowledgeItemUpdateResponse`.

`GET_STUDY_PLAN_UNKNOWN = 0`  
`PATCH_KNOWLEDGE_UNKNOWN = 0`  
`HAND_WRITTEN_TRANSPORT_DTOS = 0`

## Delivered workspace

- Route: `/exam/cs408/knowledge?module=<canonical-module-id>`.
- One URL-persistent active module at a time, with safe fallback to data structures.
- Structured recursive chapter → section → node → leaf rendering using typed `children`; no object-key ordering or decorative graph.
- First chapter opens initially; lower levels use semantic disclosure controls.
- Desktop uses a 60/40 editorial outline/detail composition. Mobile makes the outline primary and places selected detail inline.
- Knowledge status labels: 未学习 / 学习中 / 已学习 / 待复习. Chapter and section labels use 未开始 / 学习中 / 已完成. Task mapping remains separate in the shared mapper.
- Leaf status writes are explicit via “更新学习状态”; the mutation sends generated request fields, renders the returned canonical status on refetch, and invalidates only the current module study-plan and dashboard-summary keys.
- Legacy storage identifiers and storage-status fields are not rendered.

## Validation evidence

- `npm run check`: PASS — typecheck, ESLint, 23 unit tests.
- `npm run build`: PASS.
- `npm run test:e2e`: PASS — 5 passed; 6 existing authenticated VQA tests skipped because `EXAM_VQA=1` / temporary backend were not supplied.
- `BACKEND_FILES_CHANGED = 0`.

## Outstanding real-data gate

Real authenticated VQA was attempted with a disposable SQLite database at
`C:\\Users\\26477\\AppData\\Local\\Temp\\zhixue-f1c1-vqa\\f1c1.db`, a real temporary registration/login session, and backend port `8018` (never port 8000; `backend/app.db` was not used).

The current backend cannot start a second process against that authenticated TEMP DB. During startup, `database.ensure_user_service_memberships_schema()` attempts to insert a compatibility membership row without the now-required `status` column and SQLite raises `NOT NULL constraint failed: user_service_memberships.status`. This is a backend startup/schema-compatibility defect, not a frontend contract failure. No backend file, API, schema, migration, or production DB was modified.

Therefore the following are intentionally not claimed:

- Real data-structure and operating-system screenshot set.
- Real PATCH mutation and F1B2 populated dashboard evidence.
- Knowledge-route desktop/tablet/mobile AXE results and console capture.

`FRONTEND_F1C1_COMPLETE = NO` until this backend TEMP-startup defect is closed and the required real-data VQA is run.
