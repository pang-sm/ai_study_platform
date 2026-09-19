# FRONTEND_F1C5A — CS408 Study Plan Contract Audit

Date: 2026-09-19.
Mode: fast contract audit. **No frontend UI, no plan-logic redesign, no planner features,
no DB/schema change.** Nothing was implemented.

Backend baseline: `1143 passed / 0 failed`. Migration head: `20260919_0009`.

Everything below was measured: models and handlers read from source, all plan endpoints
generated into OpenAPI, and every read/write exercised against a **TEMP database** with a
real authenticated session. `backend/app.db` was opened `?mode=ro` only.

```text
FRONTEND_F1C5A_COMPLETE
CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks (ExamStudyPlanTask) + exam_study_plan_settings
F1C5_FRONTEND_READY = NO
REAL_APP_DB_MUTATED = NO
```

---

## 1. PLAN_CONCEPT_MATRIX

Eight distinct concepts answer to the word "plan". Only one of them is the CS408 plan.

| # | Concept | Model / table | Endpoints | Reader | Writer | User? | Module? | Persisted? | AI? | Canonical role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Exam study-plan task** | `ExamStudyPlanTask` / `exam_study_plan_tasks` | `GET /exam/11408/subjects/{s}/study-plan`, `POST/PATCH/DELETE .../study-plan/tasks[/{id}]`, `GET /exam/11408/study-plan/tasks/summary` | plan page, exam home, dashboard | **user CRUD only** | yes (`username`) | yes (`subject_key`) | yes | **NO** | **THE CS408 plan** |
| 2 | **Exam plan settings** | `ExamStudyPlanSetting` / `exam_study_plan_settings` | `PATCH .../study-plan/settings` | plan page | user | yes | yes | yes | no | plan configuration |
| 3 | **Exam chapter-practice flag** | `ExamStudyPlanChapterPractice` / `exam_study_plan_chapter_practice` | `PATCH .../study-plan/chapter-practice/{node_code}` | plan tree (`section.chapter_practice_completed`) | user | yes | yes | yes | no | a *section* tick, separate from task status |
| 4 | **Dashboard `today_plan`** | — (derived) | `GET /exam/11408/subjects/{s}/dashboard-summary` | exam home | nobody | yes | yes | **NO** | no | read-time projection, max 3 tasks |
| 5 | **Generic learning task** | `LearningTask` / `learning_tasks` | `GET/POST /learning/tasks`, `PUT /learning/tasks/{id}`, `DELETE`, `PUT/POST /reorder`, `GET /summary` | course + programming | user, review centre, AI diagnosis, AI plan import | yes | course-scoped | yes | **YES** | **course_learning / programming task system** |
| 6 | **AI plan generation** | — (preview) + `LearningTask` (import) | `POST /learning/plans/generate-preview[-advanced]`, `POST /learning/plans/import-tasks` | plan generator UI | import step only | yes | yes | preview: no · import: yes | **YES** | course plan generation |
| 7 | **Course `today_plan`** | — (derived from #1 with `subject_key="course_learning:<id>"`) | `GET /course-learning/today-plan`, `PATCH /course-learning/today-plan/order` | course home | order stored in track detail JSON | yes | course | order: yes | no | course home projection |
| 8 | **Review task** | `LearningTask` (`source="review_center"`) | `POST /review/tasks/create` | task list | user | yes | course | yes | no | manual 复盘 task; **not** F1C1 `review_due` |

Not a plan concept, for the avoidance of doubt: `GET /membership/plans`,
`GET /subscription/plans` (membership catalog) and `POST /admin/users/{u}/plan`
(admin membership grant).

### The shared-table finding

`exam_study_plan_tasks` is **shared across two Learning Spaces**. The course-learning
endpoints (`POST/PATCH/DELETE /course-learning/study-plan/tasks`) write the *same*
`ExamStudyPlanTask` model, disambiguating with `subject_key = "course_learning:<seed_course_id>"`.
`/course-learning/today-plan` reads the same table back with that prefix. So the CS408 plan
owner is a table shared with course learning, and `subject_key` — not the namespace — is the
discriminator.

## 2. CANONICAL PRODUCT OWNER

```text
CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks + exam_study_plan_settings
                             (read through GET /exam/11408/subjects/{subject_key}/study-plan,
                              typed as ExamStudyPlanResponse)
```

F1C5 must consume **only** this. It must not merge `learning_tasks`, must not merge
`/course-learning/today-plan`, and must not read the dashboard `today_plan` as a second task
list — that is a projection of the same rows with different (correct) computed status.

Concretely, the three readers of the *same* `ExamStudyPlanTask` rows are **not
interchangeable** (see §23.1): the canonical plan read is the one that is wrong.

## 3. F1C1 study-plan relationship

```text
F1C1_STUDY_PLAN_ROLE = B. mainly the knowledge hierarchy / progress surface
                          (with a genuine plan-task list attached)
```

Measured, for `subject_key=operating_system`, paid user, empty plan:

```
GET /exam/11408/subjects/operating_system/study-plan
  settings        : {learning_goal:"", start_date:null, daily_hours:"", weekly_days:5,
                     review_strategy:"sequential", show_completed:true}
  stats           : {total_knowledge_points:222, mastered:0, total_sections:18,
                     sections_completed:0, sections_learning:0,
                     sections_not_started:18, overall_progress:0,
                     overall_status:"not_started"}
  chapters        : 5   (the seed knowledge map, enriched per-leaf)
  tasks           : []  (the plan)
```

`ExamStudyPlanChapter` / `ExamStudyPlanSection` each carry
`status · stored_status · user_confirmed_status · system_suggested_status ·
ai_recommended_status · ai_assessment · status_counts · review_due_at · progress ·
learned_at` — that is the F1C1 knowledge surface, and F1C1 already consumes it
(`frontend/src/features/exam/api/study-plan.ts` → `cs408-knowledge-workspace.tsx`).

So the endpoint **does** own a real plan-task list, but most of its payload and its whole
write surface (`PATCH .../knowledge-items/{code}`) belong to F1C1 knowledge. The name is not
evidence of plan ownership; the task list is, and it is genuinely there.

**Consequence for F1C5:** C (module context) and K (deep links into Knowledge) can ride on
the same response, but the plan page must not present the knowledge tree as a plan, and its
own PATCHes must not be confused with the F1C1 knowledge writer. They are different routes
for different things.

## 4. Dashboard `today_plan`

```text
TODAY_PLAN_SOURCE_OF_TRUTH = derived at read time from exam_study_plan_tasks,
                             NOT persisted, NOT user-editable, NOT date-filtered
```

`main.py:19634` — per subject, `ExamStudyPlanTask` filtered by `(username, subject_key)`,
ordered `created_at DESC`, `LIMIT 3`, with `computed_status = _compute_task_completion(t, db)[0]`.

It is **not today's plan**. A task whose `due_date` is `2020-01-01` (six years overdue) was
still returned in `today_plan` exactly as before, with `due_date: "2020-01-01"`. There is no
date predicate anywhere in the query.

```
probe: task due_date set to 2020-01-01
  dashboard today_plan contains it : True
  today_plan[].due_date            : "2020-01-01"
```

The type is `ExamDashboardPlanTask` = `{id, title, knowledge_point_name, task_type,
computed_status, due_date}` — a deliberate *subset* of the full task shape (no
`completion_reason`, no `action_target`).

Not stale in the sense of dead code — it is live and correctly computed. Stale in the sense
that its **name promises a day boundary the backend does not have**.

## 5. PLAN_TASK_IDENTITY

```text
PLAN_TASK_IDENTITY = exam_study_plan_tasks.id  (server-assigned integer)
                     scoped by (username, subject_key)
```

Verified: `id=1`, `username=…`, `subject_key=operating_system`. No array index, no title, no
frontend UUID, no natural key. `title` is free text and not unique. `created_at DESC` is the
only ordering guarantee.

The identity is **not** globally unique: `id=1` in `exam_study_plan_tasks` and `id=1` in
`learning_tasks` are different tasks, and the exam table also holds course rows under the
`course_learning:` prefix. Any F1C5 key/route must carry the module too.

## 6. TASK STATUS SEMANTICS

```text
TASK_STATUS_SEMANTICS =
  computed_status ∈ { "not_started", "in_progress", "completed" }   (closed enum, typed)
  It is COMPUTED PER READ. It is NOT stored and NOT writable.

  A stored `status` column exists on the row and is ALSO returned as `status`,
  but _serialize_task overwrites both with the computed value — the stored column
  is written once ("not_started") at create and never updated by anything.
```

Exact derivation, `_compute_task_completion` (`main.py:19060`), by `task_type`:

| `task_type` | completed when | in_progress when | source of truth |
| --- | --- | --- | --- |
| `knowledge` | **all** leaves of the bound section are `mastered` | ≥1 leaf mastered | `user_knowledge_progress` (F1C1) |
| `chapter_practice` | all chapter-bank questions of the bound section appear in `exam_question_done_records` | ≥1 question practised | `exam_question_done_records` |
| `review` | 0 leaves with `review_due` **and** all mastered | some `review_due`, or some mastered | `user_knowledge_progress` |
| anything else | — | — | falls through to `not_started` |

A task whose `knowledge_point_name` matches no section computes as
`not_started` with reason `等待知识脉络数据加载` — it can never complete.

**There is no completion write.** `PATCH .../study-plan/tasks/{id}` sends
`ExamStudyPlanTaskUpdate`, which has **no `status` field at all**. A body containing
`{"status":"completed"}` returns `200`, the response still reports `computed_status:
not_started`, and the stored column is still `not_started`:

```
PATCH .../tasks/1  body={"status":"completed"}  -> 200
  response.computed_status        : not_started
  DB row ExamStudyPlanTask.status : not_started
```

Pydantic silently drops the unknown field. **This is a trap:** a frontend that PATCHes
`status` gets a 200 and no error, and nothing happens.

```
PLAN_TASK_COMPLETE_IMPLIES_MASTERY = NO
```

The implication runs the *other* way: for `task_type="knowledge"`, mastery produces
completion. Checking a task off cannot set mastery, because there is nothing to check off.

## 7. Module / context

| context | supported? | how |
| --- | --- | --- |
| module (`subject_key`) | **YES** | path segment on every exam plan route; stored on the row; also partitions the table from course rows |
| chapter / section | **PARTIAL** | free-text `knowledge_point_name` matched by exact section title, then by code; no chapter id, no FK |
| knowledge point | **PARTIAL** | the same free-text field resolved against the seed map at read time |
| practice context | **PARTIAL (derived only)** | `action_target = "practice_center"` for `chapter_practice` tasks; no practice session/attempt id on the task |
| past-paper context | **NO** | no field, no task type |
| wrong-answer context | **NO** | no field, no task type |

The `knowledge_point_name` binding is a **string match against seed titles**, not an id. A
task bound to a section that is later renamed silently stops resolving (and then never
completes). No cross-workspace link is invented beyond `action_target`.

`scope_type ∈ {"single","all"}` widens a task from one section to the whole subject.
`task_type` accepts any string; the four known values are `knowledge`, `chapter_practice`,
`review`, and (course-side) others.

## 8. User actions

| action | verdict | evidence |
| --- | --- | --- |
| create task | **READY** | `POST .../study-plan/tasks`, `ExamStudyPlanTaskCreate {username, subject_key, title, knowledge_point_name?, scope_type?, task_type?, due_date?, note?}`; 400 if `knowledge_point_name` empty and `scope_type != "all"` |
| edit task | **READY (partial fields)** | `PATCH .../tasks/{id}` — title / knowledge_point_name / scope_type / task_type / due_date / note. **No status.** |
| delete task | **READY** | `DELETE .../tasks/{id}` — hard delete, returns `{success, deleted_id}` |
| start | **NOT_SUPPORTED** | status is computed |
| complete | **NOT_SUPPORTED** | no writable status; see §6 |
| reopen | **NOT_SUPPORTED** | ditto |
| reorder | **NOT_SUPPORTED** | no `order_index` / `sort_order` on the exam task model |
| schedule date | **PARTIAL** | `due_date` is a free-form `VARCHAR(30)` string |
| due date | **PARTIAL** | same field; best-effort parsed as `YYYY-MM-DD[ HH:MM[:SS]]` for urgency sort only |

Settings are separately writable: `PATCH .../study-plan/settings`
(`learning_goal`, `start_date`, `daily_hours`, `weekly_days`, `review_strategy`,
`show_completed`) — verified persistent across reads.

One round-trip wart: `start_date` is echoed as `""` on the write response and as `null` on
the next read; the model is required but nullable.

## 9. Plan generation

```text
PLANNING_GENERATE_ENDPOINT      = POST /learning/plans/generate-preview
                                  (+ POST /learning/plans/generate-preview-advanced, multipart)
PLANNING_GENERATE_CAPABILITY    = planning.generate
PLANNING_GENERATE_PERSISTENCE   = NONE (preview) — a pure read; verified no db.add / db.commit
                                  in _generate_plan_preview_core (main.py:27227)
                                    and 0 rows written by the probe
PLANNING_GENERATE_FAILURE_ISOLATED = YES
```

`_scoped_ai_content(..., "planning.generate", ...)` → the unified boundary: capability
permission → usage budget → qualified model pool → provider gateway → settlement. It is not
a legacy quota path.

Reachability measured:

```
unified tier = free       -> 403 {"detail": "AI capability unavailable"}
unified tier = standard   -> capability gate PASSED, then 502 (no provider in this env)
```

`usage/capabilities.py::CAPABILITY_TIER_POLICY` — `planning.generate` ∈ {standard, advanced};
**not** in `free`. Unknown capability fails closed.

**Is the plan generated for CS408?** No. `/learning/plans/generate-preview` accepts a
`course_id`; an exam-qualified value (`operating_system_11408`, `11408 操作系统`) is routed
to the exam AI boundary by `_is_exam_ai_scope` — but the **import** step writes
`LearningTask`, the course model, never `ExamStudyPlanTask`. Measured column counts for an
exam-scoped generation + import: `ExamStudyPlanTask = 0`.

### Accept flow

```text
POST /learning/plans/import-tasks
  request  : PlanImportTasksRequest {username, plan_title, items: list}   <- items are UNTYPED
  writes   : LearningTask(source="learning_plan", status="todo", course_id=…,
                          priority=…, due_date=…, task_metadata={related_material_ids,
                          source_evidence, estimated_minutes, reason, exam_analysis})
```

Note `task_metadata` **does** carry `source_evidence` and `reason` — the AI's stated basis is
persisted, which is the right instinct. But it is the course task model.

### Not-a-preview path

`POST /learning/tasks/from-diagnosis` calls `planning.generate` and **writes `LearningTask`
rows directly, with no accept step** (`source="code_diagnosis"`, up to 5 tasks). That is the
programming diagnosis flow, not CS408 — but it is the live counter-example to the preferred
"AI suggestion → user confirmation → canonical plan" rule.

## 10. AI authority boundary

```text
Learning task writes, by path:
  user manual create            -> explicit user action                     OK
  POST /review/tasks/create     -> explicit user action                     OK
  POST /learning/plans/import-tasks -> user accepts a previewed suggestion  OK  (preferred model)
  POST /learning/tasks/from-diagnosis -> AI writes canonical tasks directly NO accept step
```

No LLM path writes `ExamStudyPlanTask`. The CS408 plan is 100 % user-authored; there is no
AI surface for it at all. So for F1C5's target:

```text
AI_CAN_WRITE_CANONICAL_CS408_PLAN = NO
```

If F1C5 wants AI plan suggestions for CS408, that surface does not exist yet and must be
built — and it must not be built by pointing the course preview at the exam table.

## 11. Free / Standard / Advanced

The CS408 plan is gated by a **legacy per-direction membership entitlement**, not by the
unified capability tier:

```
main.py:18602   require_feature_entitlement(current_user, db, "exam_11408", "learning_plan")
```
on **every** exam plan route — including the plain `GET`.

`membership.py::SERVICE_PLAN_CATALOG["exam_11408"]`:

| plan | `learning_plan` |
| --- | --- |
| `free` | **False** |
| `monthly_sprint` (rank 1) | True |
| `quarterly_boost` (rank 2) | True |
| `full_exam` (rank 3) | True |

Measured, free user with no `exam_11408` membership:

```
GET  /exam/11408/subjects/operating_system/study-plan -> 403
     {"detail":{"code":"FEATURE_REQUIRES_UPGRADE","feature":"learning_plan",
                "service_key":"exam_11408","current_plan":"free",
                "required_plan":"monthly_sprint"}}
GET  /exam/11408/study-plan/tasks/summary             -> 403
POST /exam/11408/subjects/{s}/study-plan/tasks        -> 403
GET  /membership/entitlements?service_key=exam_11408  -> 200 {"learning_plan":{"allowed":false,
                                                            "required_plan":"monthly_sprint"}}
```

A free learner cannot **read** their (empty) plan. The honest read of the requirement
"F1C5 base plan workspace must remain useful even if AI generation is unavailable" is
therefore not met by the current backend: the base loop is behind the same paywall as the
AI, one tier lower.

```text
FREE_BASIC_PLAN_LOOP = NOT_POSSIBLE (403 FEATURE_REQUIRES_UPGRADE on the read)
```

Good news for the frontend: `/membership/entitlements?service_key=exam_11408` is a typed,
documented way to know this **before** rendering, and F1C1 already surfaces the same 403
through `ApiRequestError` (`frontend/src/features/exam/api/content-status.ts`). F1C5 can use
the same pattern — it just cannot offer a free plan loop, because the backend does not.

## 12. AI failure isolation

```text
PLANNING_GENERATE_FAILURE_ISOLATED = YES
```

Byte-for-byte snapshot of `(id, title, task_type, status, due_date, note, updated_at,
task count, chapter-practice count, knowledge-progress count, wrong-answer count)` before
and after a failing generation (502, no provider configured): **identical**. The plan page
still served `200`. Generation is a pure read; there is nothing for it to corrupt.

## 13. Today / date semantics

```text
DATE_SEMANTICS = due_date is an unvalidated free-form STRING (VARCHAR(30))
                 parsed best-effort as "%Y-%m-%d %H:%M:%S" | "%Y-%m-%d %H:%M" | "%Y-%m-%d"
                 "today" = datetime.now().date()  -> SERVER LOCAL, no timezone
                 unparseable due_date parses to None -> sorts LAST
                 there is NO date filtering anywhere in the plan reads
```

* `today_plan` ignores dates entirely (§4).
* `tasks/summary` uses `due_date` for **urgency ordering** only (overdue first, then soonest,
  then undated last), still returning 4 items across all dates.
* `GET /exam/11408/subjects/{s}/study-plan` returns every task for the subject, undated or not.
* No client ever sends a date range, and no endpoint accepts one.

**F1C5 must not invent a day boundary.** The backend has no authoritative one. A plan page can
render factual `due_date` values and an overdue marker derived from the same rule the backend
already uses (`due_date < today`, server-local), and should say 逾期 rather than 今天. A
真正的 今天 view does not exist and cannot be derived without inventing semantics.

The comparisons in the backend mix naive and aware datetimes (`datetime.now().date()` vs
`utc_now()`-written rows), which is why a due date is safest treated as a calendar string.

## 14. Completion write — side effects

| write | knowledge status | mastery | learning event | practice | wrong-answer state |
| --- | --- | --- | --- | --- | --- |
| `POST .../study-plan/tasks` (create) | **no** | **no** | **no** | no | no |
| `PATCH .../study-plan/tasks/{id}` (edit) | **no** | **no** | **no** | no | no |
| `DELETE .../study-plan/tasks/{id}` | **no** | **no** | **no** | no | no |
| `PATCH .../study-plan/settings` | no | no | no | no | no |
| `PATCH .../study-plan/chapter-practice/{code}` | **no** | **no** | **no** | no | no |

Measured with `data_plane.LearningEvent` and `user_knowledge_progress` row counts around each
call: **0 delta on every one of them.**

```text
PLAN_TASK_COMPLETION_WRITES_MASTERY = NO
PLAN_TASK_CAN_RESOLVE_WRONG        = NO
```

### The counter-example you must not adopt

The **generic** task system does the opposite:

```
PUT /learning/tasks/{task_id}  body={"status":"done"}
  -> apply_knowledge_progress_event(event_type="task_done", delta=+5, ...)
  -> knowledge mastery_score +5, possible status transition, knowledge event emitted
PUT ... body={"status":"todo"} (reopen)
  -> event_type="task_reopened", delta=-5
```

That is `learning_tasks` (course_learning / programming). If F1C5 reuses
`PUT /learning/tasks/{id}` for the CS408 plan, it inherits a completion→mastery write that
the CS408 model deliberately does not have. **F1C5 must not route through `/learning/tasks`.**

## 15. Knowledge status boundary

```text
PLAN_WORKSPACE_MUTATES_F1C1_KNOWLEDGE = NO
```

The plan task model has no knowledge write path at all. The only knowledge writer reachable
from the study-plan routes is `PATCH .../study-plan/knowledge-items/{item_code}`, which is
F1C1's own route and delegates to the canonical exam knowledge boundary
(`learning.spaces.exam_prep.knowledge.apply_exam_knowledge_change`). Measured: it requires a
real leaf code and 404s for anything not in the subject's seed map, and it writes
`user_knowledge_progress` + emits an event — i.e. it is the knowledge writer, not the plan
writer, even though its path is under `/study-plan/`.

Direction of dependence, confirmed: `task.status ← knowledge status` (read), never the
reverse.

## 16. Wrong-answer boundary

```text
PLAN_TASK_CAN_RESOLVE_WRONG = NO
```

No plan write path touches `wrong_answer_states`, and no exam plan task carries a wrong-answer
reference (§7). BC7's canonical wrong state is changed only by a factual attempt. Unchanged.

## 17. Plan from wrong answers / review_due

```text
WRONG_TO_PLAN  = NO
REVIEW_DUE_TO_PLAN = NO
```

Both verified structurally rather than by absence of a name: the only two writers of
`ExamStudyPlanTask` in the entire backend are the two user-facing create handlers
(`main.py:19305` exam, `main.py:19408` course). There is no scheduled job, no hook, and no
service that turns a canonical wrong record or an F1C1 `review_due` leaf into a plan task.

Do not invent either. F1C5 has no such backend capability, and fabricating it in the frontend
would violate the "LLM/frontend must not silently invent canonical learner state" rule.

## 18. Order / priority

```text
ExamStudyPlanTask has: id, username, subject_key, title, primary_knowledge,
                       secondary_knowledge, knowledge_point_name, scope_type, task_type,
                       status, due_date, note, created_at, updated_at
                       -> NO priority, NO sort_order, NO scheduled_at, NO due_at
```

Ownership of ordering:

* `GET .../study-plan` → `created_at DESC` (newest first)
* `GET /exam/11408/study-plan/tasks/summary` → backend urgency sort (overdue → soonest due →
  earliest created; undated last), capped at 4
* `GET .../dashboard-summary` `today_plan` → `created_at DESC`, capped at 3
* `GET /course-learning/today-plan` → urgency rank, plus a **user-set manual order** stored in
  the track onboarding detail JSON (`today_plan_order`), not on the task row

The exam plan has **no user-owned order** and **no priority**. `LearningTask` does have
`priority` and `order_index` — another reason not to confuse the two models.

Do not invent AI priority, importance score, or recommended order. None exists for CS408.

## 19. Plan list contract

```text
PLAN_LIST_ENDPOINT = GET /exam/11408/subjects/{subject_key}/study-plan
                     response_model = ExamStudyPlanResponse  (TYPED)
```

Fields actually present per task (`ExamStudyPlanTaskItem`, all required):

```
id · username · subject_key · subject_name · title · knowledge_point_name · scope_type ·
task_type · computed_status · completion_reason · action_target · due_date · note ·
created_at · updated_at · status · primary_knowledge · secondary_knowledge
```

`computed_status` and `action_target` are closed enums in the spec:

```
computed_status : "not_started" | "in_progress" | "completed"
action_target   : "knowledge_map" | "practice_center"
```

`completion_reason` is human-readable Chinese produced by the backend (e.g.
`已掌握 1/8 个知识点，等待知识脉络中标记为已学习`) — usable as-is, and the *only* place the
backend explains why a task is not complete. `action_target` is the deep-link primitive:
`knowledge_map` → Knowledge workspace, `practice_center` → Practice workspace.

Not present: task priority, sort order, scheduled date, source, progress fraction, subtasks,
wrong-answer or past-paper references.

## 20. Detail / write contract

| # | Method | Path | Auth | Request | Response | Typed | Side effects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GET | `/exam/11408/subjects/{subject_key}/study-plan` | session + `exam_11408.learning_plan` | query `username` | `ExamStudyPlanResponse` | **yes** | none |
| 2 | PATCH | `.../study-plan/settings` | same | `ExamStudyPlanSettingsUpdate` | `{}` | req yes / **res UNKNOWN** | upsert settings |
| 3 | PATCH | `.../study-plan/knowledge-items/{item_code}` | same | `ExamStudyPlanKnowledgeItemUpdate` | `ExamKnowledgeItemUpdateResponse` | **yes** | **writes F1C1 knowledge** + event |
| 4 | PATCH | `.../study-plan/chapter-practice/{node_code}` | same | `ExamStudyPlanChapterPracticeUpdate` | `{}` | req yes / **res UNKNOWN** | upsert section tick |
| 5 | GET | `/exam/11408/study-plan/summary` | same | query `username` | `{}` | **UNKNOWN** | none |
| 6 | GET | `/exam/11408/study-plan/tasks/summary` | same | query `username` | `{}` | **UNKNOWN** | none |
| 7 | POST | `.../study-plan/tasks` | same | `ExamStudyPlanTaskCreate` | `{}` | req yes / **res UNKNOWN** | insert task |
| 8 | PATCH | `.../study-plan/tasks/{task_id}` | same | `ExamStudyPlanTaskUpdate` | `{}` | req yes / **res UNKNOWN** | update fields (never status) |
| 9 | DELETE | `.../study-plan/tasks/{task_id}` | same | query `username` | `{}` | **UNKNOWN** | hard delete |
| 10 | POST | `/learning/plans/generate-preview` | session + `planning.generate` | `PlanGeneratePreviewRequest` | `{}` | req yes / **res UNKNOWN** | **none** |
| 11 | POST | `/learning/plans/generate-preview-advanced` | same | multipart Form/File | `{}` | **req RAW** / res UNKNOWN | none |
| 12 | POST | `/learning/plans/import-tasks` | session | `PlanImportTasksRequest` (`items` untyped) | `{}` | req **partial** / res UNKNOWN | insert `LearningTask` |
| 13 | GET | `/exam/11408/subjects/{subject_key}/dashboard-summary` | session | query `username` | `ExamSubjectDashboardSummaryResponse` | **yes** | none |

Declared responses are only `200` and `422`. The **403 entitlement** and the **404
cross-user/bad-subject** answers are real and reachable but absent from the spec, so a
generated client cannot tell that 403 means "upgrade required" — the frontend has to
pattern-match the body.

## 21. OpenAPI

```text
PLAN_REQUIRED_REQUEST_UNKNOWN = 1
PLAN_REQUIRED_SUCCESS_UNKNOWN = 6
```

Request side: the only unknown is `PlanImportTasksRequest.items`, generated as
`array<{}>` → `unknown[]` (the accept step's AI payload items). Everything else required by
minimum F1C5 (create / edit / settings / preview) has a concrete request model.
`generate-preview-advanced` has no JSON request body at all (multipart), so it is excluded
from the F1C5 path — the JSON endpoint covers the same need.

Success side: 6 of the required operations answer `200 {}` → `unknown` in the generated
client — settings, chapter-practice, tasks/summary, study-plan/summary, task create, task
edit, task delete, generate-preview, import-tasks. Counting only what F1C5 needs:
**create (7), edit (8), delete (9), settings (2), AI preview (10), AI accept (12) = 6.**

The read contract is genuinely good: `ExamStudyPlanResponse` → `ExamStudyPlanTaskItem` is
fully typed with closed enums, and it is the one thing F1C5 needs most.

**Do not type a semantically broken surface to reach zero.** Two of these should not be typed
until they are fixed:

* `PATCH .../tasks/{id}` must either reject `status` explicitly or accept it — right now a
  typed `ExamStudyPlanTaskUpdate` would bless a request body that silently drops the field
  the frontend is most likely to send (§6);
* `GET /exam/11408/subjects/{subject_key}/study-plan` must compute `computed_status` before
  its 200 can be trusted as the canonical task status (§23.1).

## 22. Pagination / range

```text
PLAN_PAGINATION = NONE — no limit/offset, no cursor, on any plan read
PLAN_FILTERS    = NONE — the only query parameter is username (which must equal the session user)
PLAN_DATE_RANGE = NONE
```

`GET .../study-plan` returns **every** task for `(username, subject_key)` in one response;
`tasks/summary` caps at 4; `today_plan` caps at 3. Real data grows the plan list linearly
with tasks created, and there is no bound.

Practical impact today is small (the real `app.db` holds **0** rows in
`exam_study_plan_tasks`), so this is a future-risk finding, not a current blocker. But it is
the one place where "fetch the plan" can become unbounded, and F1C5 must not work around it
with client-side paging.

## 23. Empty state

Verified for a brand-new paid user with no plan:

```
GET .../study-plan  -> 200
  tasks   : []
  chapters: 5 (the knowledge map, all not_started)
  stats   : zeros, overall_status "not_started"
  settings: defaults (weekly_days 5, review_strategy "sequential", show_completed true)
GET /exam/11408/study-plan/tasks/summary -> 200 {"tasks": []}
GET .../dashboard-summary               -> today_plan: []
```

So an honest empty state is available:
**暂无学习计划** (no plan) on the plan page, and **今天还没有学习任务** is *not* honest until a
real day boundary exists (§13) — the backend has no notion of today for tasks.

No fake AI recommendation, no fabricated progress. `stats` is all zeros and
`chapters` is real seed content — the page must not present the seed tree as a user plan.

## 23.1 The blocker: the canonical read returns a stale status

This is the one thing that must be fixed before any F1C5 UI reads task status.

`main.py:18661`:

```python
tasks = [_serialize_task(t) for t in task_rows]     # <-- no db argument
```

`_serialize_task(task, db=None)` short-circuits to the default tuple
`("not_started", "", "knowledge_map")` when `db is None`. Every other reader passes `db`.

Measured, one task, one moment, task bound to a section with one leaf marked `mastered`:

| reader | `computed_status` | `completion_reason` |
| --- | --- | --- |
| `GET .../study-plan` (**the canonical list**) | **`not_started`** | **`""`** |
| `GET /exam/11408/study-plan/tasks/summary` | `in_progress` | `已掌握 1/8 个知识点…` |
| `GET .../dashboard-summary` `today_plan` | `in_progress` | (field not carried) |
| `POST .../study-plan/tasks` response | `in_progress` | `已掌握 1/8 个知识点…` |
| `PATCH .../study-plan/tasks/{id}` response | `in_progress` | `已掌握 1/8 个知识点…` |

Four readers agree; the canonical one is wrong. A F1C5 built on the typed list would render
every task as 未开始 forever, while the dashboard says otherwise — the same class of defect
as the pre-BC7 wrong-answer split, and equally unfixable in the frontend.

Fixing it is a one-argument change, but it is a behaviour change to a live surface, so it is
reported, not made.

## 24. Ownership

```
cross-user, paid users A and B, same module:
  B GET   .../study-plan          -> 200, tasks: []      (A's task not visible)
  B PATCH .../tasks/{A's id}      -> 404
  B DELETE .../tasks/{A's id}     -> 404
  A's task still exists           -> True
  B GET his own plan after       -> unchanged, empty
```

Every handler filters by `current_user.username`; `request_username` additionally rejects a
body `username` that does not match the session (403 `请求用户与当前登录用户不一致`), verified
by probe. Module isolation verified: tasks created in `operating_system` return `0` from
`data_structure`, `computer_organization`, `computer_network`.

```text
CROSS_USER_PLAN_ACCESS = 0
WRONG_MODULE_CROSS_LEAK (plan) = 0
```

## 25. Real database safety

| measure | value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to baseline |
| size / mtime | `64917504` / `2026-09-16 21:24:23` — identical |
| `integrity_check` | `ok` |
| table count | 72 |
| `exam_study_plan_tasks` / `exam_study_plan_settings` / `learning_tasks` | **0 / 0 / 0 rows** |

All probes ran against a TEMP database; the real file was only ever opened `?mode=ro`.

```text
REAL_APP_DB_MUTATED = NO
```

## 26. Minimum F1C5 product

| | capability | verdict | why |
| --- | --- | --- | --- |
| A | plan / task list | **PARTIAL** | typed `ExamStudyPlanResponse` exists, but `computed_status` on it is stale (§23.1), and there is no pagination |
| B | today view | **NOT_SUPPORTED** | no day boundary exists; `today_plan` is "3 newest tasks" (§4) |
| C | module context | **READY** | `subject_key` on the route, the row, and every task |
| D | task status | **BLOCKED** | status is correct everywhere except the canonical list; no writable status |
| E | complete / reopen | **NOT_SUPPORTED** | no writable status; `PATCH` silently drops it (§6) |
| F | manual create task | **READY** | typed request, works, no side effects |
| G | edit / delete | **PARTIAL** | works; responses untyped; `status` is silently ignored |
| H | AI generate suggestion | **PARTIAL** | capability exists but is course-scoped, requires Standard/Advanced, writes `LearningTask` — not CS408 |
| I | accept AI suggestion | **NOT_SUPPORTED for CS408** | `import-tasks` writes the course task model |
| J | date / range | **PARTIAL** | free-form `due_date` string, backend urgency sort; no range filter, no authoritative today |
| K | deep links | **PARTIAL** | `action_target ∈ {knowledge_map, practice_center}` covers Knowledge and Practice only; **no route to Past Papers or Wrong Answers** |
| L | persistence / reload | **READY** | tasks, settings and section ticks all persist and survive reload |

## 27. Final decision

Not one coherent typed contract. The fragmentation is small and specific, and two of the
three findings are behaviour, not typing:

```text
F1C5_FRONTEND_READY = NO
```

**Required normalization (a small BC8, in this order):**

1. **Fix the stale canonical status** — pass `db` at `main.py:18661`. Without this, no
   frontend can honestly show task status, and the typed list is worse than useless because
   it *looks* trustworthy. This is the F1C5 equivalent of BC7's resolution blocker.
2. **Decide the task status write contract.** Either accept `status` on
   `PATCH .../tasks/{id}` with defined semantics, or reject it explicitly. Today a
   `{"status":"completed"}` body gets a 200 and does nothing — the worst of both. Note that
   "complete" cannot simply be written: the model derives completion from knowledge and
   practice facts, so the honest choices are (a) 403/400 on `status` plus a UI that knows
   completion is earned elsewhere, or (b) a real, fact-backed completion input.
3. **Type the six required success responses** and the `import-tasks.items` element — but
   only after (1) and (2), so the types freeze correct behaviour rather than the current one.
4. **Decide the entitlement question.** The base plan read is 403 for Free. Either F1C5 is a
   paid-tier workspace (then say so in the UI, using `/membership/entitlements`), or the
   `learning_plan` gate on the **read** is revisited. This is a product decision, not a
   contract fix, and I am not making it.
5. **Do not add a day boundary.** If F1C5 wants 今天/逾期, the backend must own the rule
   first. Until then, render factual dates and the backend's own overdue comparison.
6. **Do not route through `/learning/tasks`.** It writes mastery on completion (+5) and
   belongs to course_learning / programming.

**Explicitly not required and not recommended:** merging `learning_tasks` into the exam plan,
reusing `/course-learning/today-plan`, exposing `today_plan` as a second task list, inventing
a priority or recommended order, inventing wrong-answer/review_due-derived tasks, or building
AI plan generation for CS408 before the base loop is honest.

## Not done (per §28)

No calendar sync, no push reminders, no spaced-repetition algorithm, no AI autonomous
scheduling, no mastery optimizer, no recommendation ranking. Nothing was implemented; no
schema or migration was touched.

---

```text
FRONTEND_F1C5A_COMPLETE

CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks + exam_study_plan_settings
                             (ExamStudyPlanTask / ExamStudyPlanSetting, read through
                              GET /exam/11408/subjects/{subject_key}/study-plan)
                             note: the table is SHARED with course_learning via the
                             subject_key prefix "course_learning:<course_id>"

PLAN_CONCEPTS =
- 1. Exam study-plan task        exam_study_plan_tasks            CANONICAL CS408
- 2. Exam plan settings          exam_study_plan_settings         plan configuration
- 3. Exam chapter-practice flag  exam_study_plan_chapter_practice section tick, not task status
- 4. Dashboard today_plan        derived, not persisted           projection of #1, max 3, no date filter
- 5. Generic learning task       learning_tasks                   course_learning/programming ONLY
- 6. AI plan generation          preview + learning_tasks         course-scoped, not CS408
- 7. Course today_plan           derived from #1 with course prefix course home projection
- 8. Review task                 learning_tasks source=review_center  manual, NOT F1C1 review_due

F1C1_STUDY_PLAN_ROLE = B. mainly the knowledge hierarchy / progress surface, with a real
                          plan-task list attached (settings + stats + chapters + tasks)
TODAY_PLAN_SOURCE_OF_TRUTH = derived at read time from exam_study_plan_tasks;
                             not persisted, not user-editable, NOT date-filtered

PLAN_TASK_IDENTITY = exam_study_plan_tasks.id (server integer), scoped by
                     (username, subject_key); not unique across the task tables
TASK_STATUS_SEMANTICS = computed_status ∈ {not_started, in_progress, completed}, COMPUTED
                     per read from user_knowledge_progress / exam_question_done_records;
                     NOT stored, NOT writable. The stored `status` column is written once
                     at create and never updated. knowledge: all bound leaves mastered.
                     chapter_practice: all bound bank questions in done records.
                     review: no review_due leaves and all mastered.

PLAN_LIST_ENDPOINT = GET /exam/11408/subjects/{subject_key}/study-plan
                     -> ExamStudyPlanResponse (TYPED; closed enums for computed_status
                        and action_target)
PLAN_WRITE_ENDPOINTS =
- PATCH /exam/11408/subjects/{subject_key}/study-plan/settings                req TYPED / res UNKNOWN
- PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{code}  req TYPED / res TYPED
- PATCH /exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{code} req TYPED / res UNKNOWN
- POST  /exam/11408/subjects/{subject_key}/study-plan/tasks                   req TYPED / res UNKNOWN
- PATCH /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}         req TYPED / res UNKNOWN (NO status field)
- DELETE /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}        req NONE  / res UNKNOWN

MODULE_CONTEXT = module: YES (subject_key) · chapter/section: PARTIAL (free-text
                 knowledge_point_name matched against seed titles, no id/FK) ·
                 knowledge point: PARTIAL (same field) · practice: PARTIAL (action_target
                 only) · past paper: NO · wrong answer: NO
DATE_SEMANTICS = due_date VARCHAR(30) free-form string, best-effort parsed; today =
                 datetime.now().date() server-local, no timezone; NO date filtering on any
                 plan read; unparseable dates sort last

PLAN_TASK_COMPLETE_IMPLIES_MASTERY = NO  (the implication runs the other way: mastery →
                                          completion; there is no completion write at all)
PLAN_TASK_CAN_RESOLVE_WRONG        = NO

PLANNING_GENERATE_ENDPOINT    = POST /learning/plans/generate-preview (JSON) and
                                POST /learning/plans/generate-preview-advanced (multipart)
PLANNING_GENERATE_CAPABILITY  = planning.generate (usage/capabilities.py: standard + advanced
                                only; free denied; unknown capability fails closed)
PLANNING_GENERATE_PERSISTENCE = NONE for the preview (verified: no db.add/db.commit in
                                _generate_plan_preview_core). The ACCEPT step
                                POST /learning/plans/import-tasks persists LearningTask
                                (source="learning_plan") — the COURSE model, never
                                ExamStudyPlanTask. No AI path writes the CS408 plan.
PLANNING_GENERATE_FAILURE_ISOLATED = YES (byte-identical plan snapshot around a 502)

FREE_BASIC_PLAN_LOOP = NOT_POSSIBLE — every exam plan route, including the READ, is behind
                       require_feature_entitlement(exam_11408, learning_plan), which the free
                       catalog sets to False. Free user: 403 FEATURE_REQUIRES_UPGRADE,
                       required_plan=monthly_sprint.

REVIEW_DUE_TO_PLAN = NO
WRONG_TO_PLAN      = NO

CROSS_USER_PLAN_ACCESS = 0 (GET unchanged, PATCH/DELETE 404)

PLAN_REQUIRED_REQUEST_UNKNOWN = 1   (PlanImportTasksRequest.items -> array<{}> -> unknown[])
PLAN_REQUIRED_SUCCESS_UNKNOWN = 6   (task create / task edit / task delete / settings /
                                     generate-preview / import-tasks all return 200 {})

MINIMUM_F1C5_CAPABILITIES =
A list             = PARTIAL   (typed, but computed_status is STALE on it; no pagination)
B today            = NOT_SUPPORTED (no day boundary exists; today_plan = 3 newest tasks)
C module context   = READY
D task status      = BLOCKED   (canonical list returns not_started for every task)
E complete/reopen  = NOT_SUPPORTED (status not writable; PATCH silently drops it)
F manual create    = READY
G edit/delete      = PARTIAL   (works; responses untyped; status silently ignored)
H AI suggestion    = PARTIAL   (capability exists, course-scoped + Standard/Advanced only)
I accept suggestion= NOT_SUPPORTED for CS408 (import-tasks writes the course task model)
J date/range       = PARTIAL   (free-form due_date string; no range filter)
K deep links       = PARTIAL   (action_target covers Knowledge + Practice only;
                                no Past Papers, no Wrong Answers route)
L persistence/reload = READY

F1C5_FRONTEND_READY = NO
BLOCKERS =
  1. STALE CANONICAL STATUS — main.py:18661 calls _serialize_task(t) without `db`, so
     GET .../study-plan reports computed_status="not_started" and completion_reason=""
     for every task while tasks/summary, today_plan and the POST/PATCH responses all
     compute the real status. One task, one moment: not_started vs in_progress.
     F1C5 cannot honestly render 未开始/进行中/已完成 from the canonical list.
  2. NO TASK STATUS WRITE CONTRACT — ExamStudyPlanTaskUpdate has no `status` field;
     a body containing status=completed returns 200, changes nothing and the stored
     column stays not_started. There is no complete/reopen, and no error either way.
  3. FREE TIER BLOCKED — the base plan read is 403 for Free (learning_plan is False in
     the exam_11408 free catalog), so a plan workspace is paid-only today.
  4. UNTYPED WRITE RESPONSES — 6 required operations return 200 {} (unknown), and
     PlanImportTasksRequest.items is an untyped array.
  5. NO DAY SEMANTICS — no authoritative today; today_plan is not date-filtered.
  6. FRAGMENTED OWNERSHIP — a second task system (learning_tasks) and three projection
     readers exist; the frontend must consume only the canonical one.

REAL_APP_DB_MUTATED = NO
```
