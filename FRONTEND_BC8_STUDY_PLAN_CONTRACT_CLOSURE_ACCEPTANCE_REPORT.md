# FRONTEND_BC8 — CS408 Study Plan Contract Closure

Date: 2026-09-19.
Mode: small backend contract closure, fast-track. **No F1C5 UI was implemented.**

Baseline: `1143 passed / 0 failed` (BC7). Migration head: `20260919_0009`.

> **§37 AMENDED (product decision, 2026-09-19).** The original gate
> `FREE_BASE_PLAN_LOOP = PASS` is formally superseded. The CS408 Study Plan workspace stays a
> paid-tier product surface: `learning_plan` is not ungated, the F1C1 knowledge write is not
> ungated, and the frozen membership policy is unchanged. The replacement gates are
> `BASE_PLAN_ENTITLEMENT_POLICY_PRESERVED = PASS`, `FREE_BASE_PLAN_LOOP = NOT_REQUIRED`,
> `PLAN_WORKSPACE_ACCESS = PAID_ENTITLEMENT`. The amendment waives no technical correctness
> gate. See §6.

```text
FRONTEND_BC8_COMPLETE
CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks (ExamStudyPlanTask)
DB_SCHEMA_CHANGED = NO
MIGRATION_ADDED = NO
REAL_APP_DB_MUTATED = NO
F1C5_FRONTEND_READY = YES
F1C5_ACCESS_MODEL = PAID_WORKSPACE
```

---

## 1. The proven blockers and what happened to each

| | blocker (from F1C5A) | outcome |
| --- | --- | --- |
| B1 | canonical plan list returns a stale task status | **FIXED** — §3 |
| B2 | task status write semantics silently drop the field | **FIXED** — §5 |
| B3 | `PUT /learning/tasks/{id}` writes mastery; F1C5 must not use it | **PINNED** — §8, never routed through |
| B4 | no authoritative "today" boundary | **PRESERVED + PINNED** — §10 |

One further divergence surfaced while closing B1 and is fixed in the same way: the settings
object answered with two different shapes depending on which route asked (§7).

## 2. Canonical owner

```text
CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks (ExamStudyPlanTask)
                             + exam_study_plan_settings (ExamStudyPlanSetting)
```

Unchanged from F1C5A's finding, and now the only surface that is typed. F1C5 consumes
`GET /exam/11408/subjects/{subject_key}/study-plan`. Nothing in BC8 routes F1C5 through
`/learning/tasks`, and no historical plan system was merged.

## 3. Stale list status — FIXED

```text
STATUS_ROOT_CAUSE = main.py:18661 called `_serialize_task(t)` with no `db`.
                    `_serialize_task(task, db=None)` short-circuits to
                    ("not_started", "", "knowledge_map"), so the CANONICAL list reported
                    every task as not-started-no-reason while the four other readers of the
                    same row passed the session and computed the real value.
STATUS_FIX        = that call site now passes `db`, so every reader goes through the same
                    semantic path. One argument; no new abstraction.
```

Measured, one task, one moment, after marking one leaf of its bound section as learned:

| reader | before BC8 | after BC8 |
| --- | --- | --- |
| `GET .../study-plan` (**canonical list**) | `not_started` · reason `""` | `in_progress` · real reason |
| `GET .../study-plan/tasks/summary` | `in_progress` | `in_progress` |
| `GET .../dashboard-summary` `today_plan` | `in_progress` | `in_progress` |
| `POST .../tasks` response | `in_progress` | `in_progress` |
| `PATCH .../tasks/{id}` response | `in_progress` | `in_progress` |

```
SAME_TASK_SAME_MOMENT_STATUS_DIVERGENCE = 0
CANONICAL_PLAN_STATUS                   = PASS
```

## 4. Status source of truth

```text
TASK_STATUS_SOURCE_OF_TRUTH = B. DERIVED from other factual state.
```

Not persisted-and-writable (A), not hybrid (C). `_compute_task_completion` derives
`computed_status` on every read:

| `task_type` | `completed` when | factual owner |
| --- | --- | --- |
| `knowledge` | every leaf of the bound section is `mastered` | `user_knowledge_progress` |
| `chapter_practice` | every bound chapter-bank question is in the done ledger | `exam_question_done_records` |
| `review` | no bound leaf is `review_due` and all are `mastered` | `user_knowledge_progress` |

`ExamStudyPlanTask.status` still exists as a column, is written once at create
(`"not_started"`), and is never updated. The serializer overwrites both `status` and
`computed_status` with the derived value, so the API never exposes the stored stub as a
different number — pinned by `test_status_is_derived_not_stored`.

## 5. Status write contract — FIXED

```text
TASK_STATUS_SEMANTICS = computed_status ∈ { "not_started", "in_progress", "completed" }
                        Closed enum, typed in OpenAPI. Derived; not writable.

STATUS_UPDATE_CONTRACT = there is NO plan-task status write.
                         A body containing `status` is REFUSED with 422
                         (`extra_forbidden`, naming the field) on both create and update.
                         The canonical non-AI operation that moves a task's status is the
                         FACTUAL ACTION for its type, and the task says which via
                         `action_target`:
                            knowledge        → mark its knowledge points learned (F1C1)
                            chapter_practice → practise its questions (F1C2)
                            review           → clear its review-due leaves (F1C1)

STATUS_UPDATE_SILENTLY_DROPS_FIELD = NO
```

`ExamStudyPlanTaskCreate` / `ExamStudyPlanTaskUpdate` gained
`model_config = ConfigDict(extra="forbid")`. Before, `{"status": "completed"}` returned
**200** and changed nothing — the worst of both worlds. Now:

```
PATCH .../tasks/1  {"status":"completed"}  -> 422 extra_forbidden (loc: body.status)
POST  .../tasks    {"status":"completed"}  -> 422 extra_forbidden (loc: body.status)
PATCH .../tasks/1  {"status":"done"}       -> 422 extra_forbidden (loc: body.status)
```

The mirror image is enforced in the contract: `status` is not a property of either request
schema, and `additionalProperties: false` is emitted, so a generated client cannot even
express it — alongside a `// @ts-expect-error` probe in the frontend compile test.

`COMPLETE_TASK` / `REOPEN_TASK` are therefore **not endpoints**. Completion is earned
through the factual action and is reversible by reversing that action (a mastered leaf
returned to `not_started` drops the task back). No completion or reopen endpoint was
invented for F1C5 — §7 explicitly forbids it when the operation is not real.

```
COMPLETE_TASK = PARTIAL  (no task endpoint; earned via the factual action named by action_target)
REOPEN_TASK   = PARTIAL  (same action, reversed)
```

## 6. Entitlement policy — preserved, and §37 amended

BC8 §13 originally asked for the base plan loop to be usable on Free. That requirement was
**formally superseded by a later explicit product decision**, so it is not counted as a
failed gate. Nothing about the entitlement was changed in either direction.

```text
BASE_PLAN_ENTITLEMENT_POLICY_PRESERVED = PASS
FREE_BASE_PLAN_LOOP                    = NOT_REQUIRED   (§13 superseded)
PLAN_WORKSPACE_ACCESS                  = PAID_ENTITLEMENT
F1C5_ACCESS_MODEL                      = PAID_WORKSPACE
```

What "preserved" means, measured — the CS408 Study Plan workspace is a paid surface, and the
F1C1 knowledge write is part of that same surface:

```
FREE user, no exam_11408 membership:
  GET   /exam/11408/subjects/{subject_key}/study-plan            -> 403
  GET   /exam/11408/study-plan/tasks/summary                     -> 403
  POST  /exam/11408/subjects/{subject_key}/study-plan/tasks      -> 403
  PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{code} -> 403
        detail: {"code":"FEATURE_REQUIRES_UPGRADE","feature":"learning_plan",
                 "service_key":"exam_11408","current_plan":"free",
                 "required_plan":"monthly_sprint"}

/membership/entitlements?service_key=exam_11408
  current_plan "free"
  learning_plan {"allowed": false, "required_plan": "monthly_sprint"}

same user after a monthly_sprint grant:
  GET .../study-plan                                             -> 200
```

The membership catalog, the `learning_plan` flag and the F1C1 knowledge gate are all
**untouched**. Frozen by `test_base_plan_entitlement_policy_is_preserved`, which asserts the
free 403s (including on the knowledge write), the catalog value, and that a paid user gets
the whole surface — so a future change to this policy has to be deliberate.

**What F1C5 must do with it (§ interpretive 3):** render the locked/upgrade state from the
existing typed entitlement rather than assuming access.
`GET /membership/entitlements?service_key=exam_11408` returns
`{current_plan, features:{learning_plan:{allowed, required_plan}}}` — typed, already consumed
by F1C1 through `ApiRequestError` (`frontend/src/features/exam/api/content-status.ts`). F1C5
gates its route on that, not on a 403 body.

**This amendment waives no technical gate.** Every technical gate in §20 passes on its own
merits, independently of the access model.

## 7. Settings shape — one contract, one shape

`_exam_plan_settings_payload(setting)` is now the only place the settings object is built,
and both the plan read and the settings write call it. The two branches are both preserved
because both are already frozen by the BC3 contract:

* **no row** → the product's declared defaults (`weekly_days 5`, `sequential`,
  `show_completed true`). A learner who never configured a plan sees a starting point;
* **a row exists** → the stored value, `null` for a genuinely unset column. Coercing a stored
  NULL to `""` would claim the learner chose an empty string.

The **write** used to return the first shape unconditionally, so the same row answered with
`start_date: ""` on the write and `start_date: null` on the next read. It now returns the
second, matching the read. Pinned by `test_settings_read_and_write_share_one_shape`.

## 8. No mastery, no wrong-answer resolution

```text
PLAN_TASK_COMPLETION_WRITES_MASTERY  = 0
PLAN_TASK_COMPLETION_RESOLVES_WRONG  = 0
```

Measured with row counts around every plan write — create, edit, settings, chapter-practice
tick, delete:

```
ExamStudyPlanTask          unchanged (created and deleted back to the same count)
exam_study_plan_chapter_practice   +1  (the section tick, the only row added)
user_knowledge_progress    unchanged        <- no mastery
wrong_answer_states        unchanged        <- no wrong resolution
data_plane LearningEvent   unchanged        <- no event
```

There is no completion write to misuse: §5's whole point is that status is derived, so the
plan table has no path to learner fact at all.

**The counter-example stays locked out.** The generic `PUT /learning/tasks/{task_id}` DOES
write mastery on completion (`task_done`, `+5`, plus a knowledge event) and is the
course_learning / programming system. BC8 does not route F1C5 through it and adds no
adapter to it. Pinned by a test asserting the plan mutation never emits a learning event.

## 9. Module context and deep links

```text
MODULE_CONTEXT = READY — `subject_key` on the route, on the row, and on every task item,
                 plus `subject_name`. No cross-module leak: a task created in one CS408
                 module is invisible in the other three.

DEEP_LINK_CONTEXT =
  Knowledge   -> READY   `action_target = "knowledge_map"`, plus the bound
                         `knowledge_point_name` (a section title, matched against the seed
                         map — NOT an id) and the full knowledge tree in the same response.
  Practice    -> READY   `action_target = "practice_center"`.
  Past Papers -> NOT AVAILABLE  no task type, no reference, no id.
  Wrong       -> NOT AVAILABLE  no task type, no reference, no id.
```

No deep-link field was added — §21 forbids inventing them, and F1C5 can link to Knowledge
and Practice from what already exists.

The `knowledge_point_name` binding is a **string match against seed section titles**. A
section renamed in the seed silently stops resolving and the task then never completes. That
is pre-existing and out of BC8's scope, but F1C5 should not present it as a stable
identifier.

## 10. today_plan and date semantics — preserved, not reinterpreted

```text
TODAY_PLAN_IS_TRUE_DAY_BOUNDARY = NO
```

`today_plan` was not renamed, not reinterpreted and not given a date predicate. It remains
the three most recently created tasks for the subject, with a computed status. Pinned by a
test that puts a **2020-01-01** due date and an **undated** task in it and asserts both are
returned as "today":

```
dashboard today_plan -> contains the 2020-01-01 task, with due_date "2020-01-01"; contains
                        the undated task; length <= 3
```

```text
DATE_SEMANTICS =
  due_date is an unvalidated free-form STRING (VARCHAR(30)); parsed best-effort as
  "%Y-%m-%d %H:%M:%S" | "%Y-%m-%d %H:%M" | "%Y-%m-%d"; an unparseable date parses to None
  and sorts LAST.
  The backend's ONLY date comparison is `due_date < datetime.now().date()` — SERVER LOCAL,
  no timezone — used for the urgency order in `/exam/11408/study-plan/tasks/summary`
  (overdue first, then soonest, then undated). It is preserved, not extended.
  There is NO date filter and NO date range on any plan read.
```

F1C5 may therefore render a factual `due_date` and an 逾期 marker derived from the same rule
the backend already uses. It must not render 今天 / 明天 / 本周 — the backend has no such
semantics. `test_overdue_ordering_comes_from_the_backend` pins the ordering it does have.

## 11. planning.generate — separate capability, unchanged

```text
PLANNING_GENERATE_CAPABILITY = planning.generate
   usage/capabilities.py::CAPABILITY_TIER_POLICY — {standard, advanced}; free DENIED;
   unknown capability fails closed. NOT the legacy `learning_plan` entitlement.

PLANNING_GENERATE_PERSISTENCE = NONE for the preview.
   `_generate_plan_preview_core` performs no db.add / db.commit — verified structurally and
   at runtime. The ACCEPT step (`POST /learning/plans/import-tasks`) persists
   LearningTask — the COURSE model, with `task_metadata.source_evidence` and `.reason`
   carried through. No AI path writes ExamStudyPlanTask.

PLANNING_GENERATE_WRITES_LEARNER_FACT = 0
   A real generation runs the whole unified boundary and leaves exactly an audit trail:
   one `ai_requests` row and one `ai_called` learning event (source_item_key
   "planning.generate", service_key "exam_prep"). No task, no knowledge progress, no
   mastery, no wrong-answer state.

PLANNING_GENERATE_FAILURE_ISOLATED = PASS
```

The two authorization layers are provably independent: a paid Exam plan does not grant the
AI capability, and the AI capability does not grant the plan.
`test_planning_generate_is_a_separate_authorized_capability` asserts a user with
`exam_11408.monthly_sprint` **and** unified `free` still gets 403 `AI capability unavailable`.

Two failure classes, both measured, neither reaching a network:

| failure | endpoint answer | plan |
| --- | --- | --- |
| provider double raises inside the gateway (`raise_timeout`) | **502** — reported as a failure, never dressed up as a generated plan | byte-identical |
| unexpected error above the gateway | **200** with the deterministic fallback (`fallback_used: true`) | byte-identical |

Provider spend: **zero**. Every AI test replaces only
`ai.orchestrator.default_provider_factory` with `ai.providers.FakeProvider` (§31's "provider
double below the orchestrator"), so the real capability permission, router, qualified model
pool, estimate → reserve → gateway → settle lifecycle still runs. An autouse guard makes any
direct `main.call_deepseek` fail loudly.

## 12. Write contracts

```text
MANUAL_TASK_CREATE = READY — already a coherent operation; typed, not added
TASK_EDIT          = READY — fields only (title / knowledge_point_name / scope_type /
                             task_type / due_date / note). No status, by design.
TASK_DELETE        = READY — hard delete
```

No CRUD was expanded (§19). The only change to these three is that their responses are now
typed and their requests refuse an unknown field.

## 13. The six untyped write responses, classified

| # | operation | classification | why |
| --- | --- | --- | --- |
| 1 | `PATCH .../study-plan/settings` | **REQUIRED_FOR_F1C5 — TYPED** | part of the base plan workspace |
| 2 | `PATCH .../study-plan/chapter-practice/{node_code}` | **REQUIRED_FOR_F1C5 — TYPED** | the section tick shown in the plan tree |
| 3 | `POST .../study-plan/tasks` | **REQUIRED_FOR_F1C5 — TYPED** | manual create |
| 4 | `PATCH .../study-plan/tasks/{task_id}` | **REQUIRED_FOR_F1C5 — TYPED** | edit |
| 5 | `DELETE .../study-plan/tasks/{task_id}` | **REQUIRED_FOR_F1C5 — TYPED** | delete |
| 6 | `POST /learning/plans/generate-preview` | **OPTIONAL — NOT TYPED** | course-scoped AI surface; a separate capability (§11), not the F1C5 base loop. Its request is already typed; its response is a loose preview bag whose shape is not the CS408 plan contract. |
| — | `POST /learning/plans/import-tasks` | **OPTIONAL — NOT TYPED** | same; it writes the COURSE task model and `items` is an untyped array |
| — | `GET /learning/tasks*`, `PUT /learning/tasks/{id}` | **DO_NOT_TYPE** | the course/programming task system. Typing it would make it look like an F1C5 option; it is not one (§8). |
| — | `POST /course-learning/study-plan/tasks` and its siblings | **DO_NOT_TYPE** | the same `ExamStudyPlanTask` table, but a different Learning Space, out of F1C5 scope (§2). |

Two summary surfaces were typed as a bonus because they were free to type and are already
correct: `GET /exam/11408/study-plan/summary` and `GET /exam/11408/study-plan/tasks/summary`.

## 14. OpenAPI

```text
PLAN_REQUIRED_REQUEST_UNKNOWN = 0
PLAN_REQUIRED_SUCCESS_UNKNOWN = 0
```

The minimum canonical F1C5 flow, all concrete:

```
GET    /exam/11408/subjects/{subject_key}/study-plan
                                 req NONE                          200 ExamStudyPlanResponse
POST   /exam/11408/subjects/{subject_key}/study-plan/tasks
                                 req ExamStudyPlanTaskCreate       200 ExamStudyPlanTaskMutationResponse
PATCH  /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}
                                 req ExamStudyPlanTaskUpdate       200 ExamStudyPlanTaskMutationResponse
DELETE /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}
                                 req NONE                          200 ExamStudyPlanTaskDeleteResponse
PATCH  /exam/11408/subjects/{subject_key}/study-plan/settings
                                 req ExamStudyPlanSettingsUpdate   200 ExamStudyPlanSettingsMutationResponse
PATCH  /exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{node_code}
                                 req ExamStudyPlanChapterPracticeUpdate
                                                                   200 ExamStudyPlanChapterPracticeResponse
```

Not typed, reported separately as required by §25: the two `/learning/plans/*` AI endpoints
(`unknown`), the `/learning/tasks*` system (`unknown`), and the `/course-learning/study-plan/*`
siblings (`unknown`). None of them is on the F1C5 path.

Two features of the read contract worth naming, because they carry the semantics:

```
ExamStudyPlanTaskItem.computed_status : enum ["not_started","in_progress","completed"]
ExamStudyPlanTaskItem.action_target   : enum ["knowledge_map","practice_center"]
```
Both are closed enums and both are `required`. `completion_reason` is backend-authored
Chinese explaining *why* a task is not complete — the UI never has to infer it.

Also closed here: the write schemas reject unknown fields
(`additionalProperties: false`), so `status` cannot be expressed in a generated client.

## 15. Generated TypeScript

`frontend/src/types/api.ts` regenerated with the project's own tool and version
(`openapi-typescript 7.13.0`), from a spec served by a standalone uvicorn on port **8961**
with an explicit TEMP `DATABASE_URL` — never port 8000, never the real database.
`package.json` was not modified.

The diff is exactly the BC8 change, nothing else:

```
added schemas   : ExamStudyPlanTaskMutationResponse · ExamStudyPlanTaskDeleteResponse
                  ExamStudyPlanSettingsMutationResponse · ExamStudyPlanChapterPracticeResponse
                  ExamStudyPlanTasksSummaryResponse · ExamStudyPlanSubjectsSummaryResponse
                  ExamStudyPlanSubjectSummary
removed         : seven `"application/json": unknown` success responses
added           : their seven concrete `$ref`s
paths           : none added, none removed, none renamed
everything else : untouched (wrong-answers, practice, past-paper, knowledge surfaces)
```

Compile probe: `frontend/src/features/exam/api/study-plan-contract.test.ts` resolves every
type through the generated `paths` / `components` — plan list, task identity, derived status,
the reason, module context, action target, factual dates and the overdue rule, task create /
edit / delete, settings, the summary — plus a `// @ts-expect-error` proof that a `status`
cannot be sent. No cast, no handwritten DTO, no `any`.

```text
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

## 16. Ownership

```
two paid users, same module:
  B GET    .../study-plan            -> 200, tasks: []      (A's task not visible)
  B PATCH  .../tasks/{A's id}        -> 404
  B DELETE .../tasks/{A's id}        -> 404
  A's task still exists               -> True
  a body username that is not the session user -> 403
  tasks created in operating_system   -> invisible in data_structure,
                                         computer_organization, computer_network
```

```text
CROSS_USER_PLAN_ACCESS = 0
```

## 17. Runtime matrix (§29)

Full flow, real HTTP, real session, TEMP DB:

```
A  create a CS408 plan task through the legal endpoint           -> 200, typed envelope
B  read it via the canonical list                                -> computed_status in_progress
C  read the same task via tasks/summary and the dashboard        -> in_progress
D  statuses match                                                -> SAME_TASK_DIVERGENCE = 0
E  canonical status mutation: PATCH with `status` is REFUSED     -> 422; the real mutation is
                                                                    the factual knowledge action
F  reload the canonical list                                     -> still in_progress
G  status persists and stays truthful                            -> yes; stored column still
                                                                    "not_started" (derived)
H  no mastery write                                              -> user_knowledge_progress
                                                                    unchanged by plan writes
I  no wrong-answer mutation                                      -> wrong_answer_states unchanged
J  a second user cannot access it                                -> 0 / 404 / 404
```

## 18. Database safety

```
SHA256     1c1b2d85…3fe522      identical to baseline
size       64917504             identical
mtime      2026-09-16 21:24:23  identical
tables     72                   identical
integrity_check = ok
exam_study_plan_tasks rows = 0  (the deployed DB has no plan data at all)
```

```text
DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
REAL_APP_DB_MUTATED = NO
```

No schema change was needed, so none was made: the whole closure is semantics, typing and two
one-line fixes. `MIGRATION_HEAD` remains `20260919_0009`, pinned by a test.

## 19. Tests

New: `backend/tests/test_bc8_study_plan_contract.py` — 23 tests covering, per §34:

```
canonical list uses the DB-aware serializer                    ✓
same row / same moment status consistency (list, summary, dashboard, write responses) ✓
status write does not silently discard the field (422, three shapes)  ✓
the status enum is the only one that exists                     ✓
canonical status is derived, not stored                         ✓
completion does not write mastery                               ✓
completion does not resolve wrong state                         ✓
settings read and write share one shape                         ✓
user isolation + body-username identity + module isolation      ✓
plan surface stays behind its entitlement (decision pinned)     ✓
base plan operations need no AI provider                        ✓
planning.generate is independently authorized                   ✓
AI generation failure isolates the plan (both failure classes)  ✓
generation writes no learner fact                              ✓
today_plan is not a day boundary + backend urgency ordering     ✓
generated OpenAPI concrete for the required surfaces            ✓
real app.db untouched; no revision added                        ✓
```

Frontend: `frontend/src/features/exam/api/study-plan-contract.test.ts` — 4 tests, compile +
runtime probe of the generated contract.

## 20. Final gates

```
CANONICAL_PLAN_STATUS                     = PASS
SAME_TASK_SAME_MOMENT_STATUS_DIVERGENCE   = 0
STATUS_UPDATE_SILENTLY_DROPS_FIELD        = NO
PLAN_TASK_COMPLETION_WRITES_MASTERY       = 0
PLAN_TASK_COMPLETION_RESOLVES_WRONG       = 0
TODAY_PLAN_IS_TRUE_DAY_BOUNDARY           = NO

BASE_PLAN_ENTITLEMENT_POLICY_PRESERVED    = PASS     ← amended §37
FREE_BASE_PLAN_LOOP                       = NOT_REQUIRED  (§13 superseded)
PLAN_WORKSPACE_ACCESS                     = PAID_ENTITLEMENT
PLANNING_GENERATE_SEPARATE_CAPABILITY     = PASS

PLANNING_GENERATE_FAILURE_ISOLATED        = PASS
PLANNING_GENERATE_WRITES_LEARNER_FACT     = 0
CROSS_USER_PLAN_ACCESS                    = 0
PLAN_REQUIRED_REQUEST_UNKNOWN             = 0
PLAN_REQUIRED_SUCCESS_UNKNOWN             = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO       = 0
DB_SCHEMA_CHANGED                         = NO
MIGRATION_ADDED                           = NO
FULL_BACKEND_TESTS                        = PASS
FRONTEND_TYPECHECK                        = PASS
FRONTEND_LINT                             = PASS
FRONTEND_UNIT_TESTS                       = PASS
FRONTEND_BUILD                            = PASS
REAL_APP_DB_MUTATED                       = NO

F1C5_FRONTEND_READY                       = YES
F1C5_ACCESS_MODEL                         = PAID_WORKSPACE
  — every technical gate passes and the final frozen-tree backend regression is 0 failed.
    The workspace is a paid surface by product policy, preserved rather than waived: F1C5
    renders its locked/upgrade state from the typed membership entitlement.
```

---

## Files changed

| file | change |
| --- | --- |
| `backend/main.py` | `_serialize_task(t, db)` at the canonical list (B1); `_exam_plan_settings_payload` shared by the read and the write (B5); seven new response models; `response_model` on 8 plan operations |
| `backend/schemas.py` | `ConfigDict(extra="forbid")` on `ExamStudyPlanTaskCreate` / `ExamStudyPlanTaskUpdate` (B2) |
| `backend/tests/test_bc8_study_plan_contract.py` (new) | 23 targeted tests |
| `frontend/src/types/api.ts` | regenerated |
| `frontend/src/features/exam/api/study-plan-contract.test.ts` (new) | compile probe |

## Not done

No F1C5 UI. No new endpoint, no CRUD expansion, no schema change, no migration, no
entitlement change, no calendar, no reminder, no scheduling algorithm, no ranking, no AI
plan generation for CS408. `today_plan` was left exactly as it was.

## Open items for you

1. **`knowledge_point_name` is a string match against seed section titles**, not an id. A seed
   rename silently breaks a task's binding and it then never completes. Pre-existing; worth a
   real id in a later step.
2. **`today_plan`** is still named as if it were a day. It is not, and F1C5 must not render it
   as 今天. Renaming or replacing it is a dashboard change, out of BC8's scope.
3. **`ExamStudyPlanTask.status`** is now a pure create-time stub that no code reads (every
   reader sees the derived `computed_status`). Removing the column would be a schema change,
   so BC8 left it; it is worth deleting whenever the next schema revision happens.
4. **The AI preview/import endpoints are still untyped** (`/learning/plans/generate-preview`
   response, `import-tasks` response and its untyped `items` array). They are the
   course_learning AI surface, not the F1C5 path, so BC8 deliberately did not type them —
   a separate small closure if you want them. See §21 for the frozen F1C5 AI decision.

---

# BC8-R1 — ENTITLEMENT TYPE CLOSURE

Date: 2026-09-19.
Mode: narrow backend contract fix. **No F1C5 UI. No membership redesign. No tier-policy
change. No `learning_plan` value change. No generic learning-task change.**

## 21. The blocker

`GET /membership/entitlements` generated as:

```ts
responses: { 200: { content: { "application/json": unknown } } }
```

So F1C5 could not read the entitlement it is required to gate on. Reading
`features.learning_plan.allowed` would have needed a hand-written transport DTO, a type
assertion, or an `any`/`unknown` cast — all forbidden. That is a typing gap, not a product
one: the endpoint already returned the right values.

## 22. The response that actually exists

Measured from the running endpoint (`?service_key=exam_11408`) across every tier and
direction, before any model was written — the shape below is observed, not designed:

```json
{
  "service_key": "exam_11408",
  "current_plan": "free",
  "features": {
    "learning_plan":   { "allowed": false, "required_plan": "monthly_sprint" },
    "learning_report": { "allowed": true,  "required_plan": "free" }
  }
}
```

| probe | `current_plan` | `learning_plan` |
| --- | --- | --- |
| free | `free` | `{allowed: false, required_plan: "monthly_sprint"}` |
| `monthly_sprint` | `monthly_sprint` | `{allowed: true, required_plan: "monthly_sprint"}` |
| `quarterly_boost` | `quarterly_boost` | `{allowed: true, required_plan: "monthly_sprint"}` |
| `full_exam` | `full_exam` | `{allowed: true, required_plan: "monthly_sprint"}` |
| `course_learning` | `free` | `{allowed: false, required_plan: "monthly"}` |
| `programming` | `free` | — `features` is `{}` |
| `exam` / `exam_408` (legacy aliases) | `free` | same as `exam_11408`, `service_key` resolved to `exam_11408` |
| unknown key | `400` | |

Two facts drove the model shape:

* **the key set is not fixed** — `programming` is a valid canonical direction whose feature
  mapping is genuinely empty, so a closed record with required `learning_plan` /
  `learning_report` fields would describe a shape that does not exist;
* **`required_plan` is direction-specific** — `monthly_sprint` under `exam_11408`,
  `monthly` under `course_learning` — so it is a string, not a shared enum.

## 23. The response model

```python
class MembershipFeatureEntitlement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool
    required_plan: str

class MembershipEntitlementsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_key: str
    current_plan: str
    features: dict[str, MembershipFeatureEntitlement]
```

attached to the route with `response_model=MembershipEntitlementsResponse`.

`features` is a **typed mapping**, which §5 permits when feature names are dynamic. It is the
honest model here: the generated client gets

```ts
features: { [key: string]: components["schemas"]["MembershipFeatureEntitlement"] };
```

so `entitlement.features.learning_plan` is `MembershipFeatureEntitlement | undefined` under
`noUncheckedIndexedAccess`, and `?.allowed` is the correct read rather than a workaround. A
closed model would have made the access *look* unconditionally safe while `programming`
returns nothing — the type would have lied in the direction of convenience.

`current_plan` stays `str`: it is the membership's free-form plan code, and the value space
differs by direction. `service_key` was **not** renamed — the aliases (`exam`, `exam_408`)
still resolve to `exam_11408` and the parameter is unchanged, because this is a typing
closure, not a namespace migration.

Nothing about the runtime response changed. The endpoint returns the identical bytes; only
its declared schema became concrete.

## 24. Policy preserved

```text
MEMBERSHIP_POLICY_CHANGED = NO
FREE_PLAN_POLICY = DENIED
PAID_PLAN_POLICY = ALLOWED
```

Verified in both layers and in both directions:

```
free user:  entitlements -> current_plan "free", learning_plan.allowed false,
                            required_plan "monthly_sprint"
            GET .../study-plan -> 403            (the paid workspace stays paid)
paid user:  entitlements -> current_plan "monthly_sprint", learning_plan.allowed true
            GET .../study-plan -> 200
```

`SERVICE_FEATURE_QUOTAS` and the `exam_11408` catalog are asserted **byte-identical** by
test (`free: False, monthly_sprint: True, quarterly_boost: True, full_exam: True`). No
entitlement value, no tier, no gate was touched.

## 25. Generated TypeScript

`frontend/src/types/api.ts` regenerated from a spec served by a standalone uvicorn on port
**8963** with an explicit TEMP `DATABASE_URL`. `package.json` unmodified.

The entire diff:

```
added schemas : MembershipEntitlementsResponse · MembershipFeatureEntitlement
changed       : GET /membership/entitlements 200  unknown -> MembershipEntitlementsResponse
removed       : nothing
everything else: untouched
```

Two new schemas, one `unknown` removed. Nothing else in the file moved.

## 26. Compile probe

`frontend/src/features/exam/api/entitlement-contract.test.ts` resolves the response through
the generated `paths` and reads the entitlement with no assertion:

```ts
type EntitlementsResponse =
  paths['/membership/entitlements']['get']['responses'][200]['content']['application/json'];

entitlement.features.learning_plan?.allowed        // boolean | undefined
entitlement.features.learning_plan?.required_plan  // string  | undefined
```

It also proves the type is genuinely concrete rather than `any`, with `@ts-expect-error`
directives that would go *unused* (and fail `npm run typecheck`) if the response were still
`unknown`: assigning `.allowed` to a string, reading a non-existent field, and dropping the
optional chain are each compile errors.

```text
HAND_WRITTEN_ENTITLEMENT_DTO = 0
ENTITLEMENT_TYPE_ASSERTION   = 0
```

The probe contains exactly one `as` — `as Response`, on the mocked fetch response — which is
the shared idiom of every existing probe in this directory (3–6 occurrences each). No
assertion touches entitlement data.

## 27. Readiness chronology

Preserved exactly; the earlier audits are **not** rewritten as if they had passed.

| step | what it was | result at the time |
| --- | --- | --- |
| **F1C5A** | pre-implementation contract audit | `F1C5_FRONTEND_READY = NO` — the canonical plan list returned a stale status, the status write silently dropped its field, the surface was fragmented |
| **BC8** | semantic closure | stale status fixed, status write contract closed, required responses typed, policy pinned. Superseded F1C5A's `NO`. |
| **BC8-R1** | entitlement typing closure | `GET /membership/entitlements` typed. No semantic change. |
| **now** | — | `F1C5_FRONTEND_READY = YES` with `F1C5_ACCESS_MODEL = PAID_WORKSPACE` |

F1C5A's `NO` remains accurate **for its date and scope**: it was a pre-BC8 audit, and BC8 +
BC8-R1 closed exactly the blockers it named. Its readiness line is historical and superseded,
not wrong.

## 28. F1C5 AI generation — deferred

```text
F1C5_INITIAL_AI_GENERATION = DEFERRED
F1C5_AI_GENERATION_REQUIRED = NO
GENERIC_LEARNING_GENERATION_API_FOR_F1C5 = FORBIDDEN
```

Frozen for the record: no CS408-specific typed `planning.generate` contract exists, and the
only available generation surface (`/learning/plans/generate-preview` → `import-tasks`)
belongs to the generic learning-task system that §8 forbids F1C5 from using — its completion
path writes mastery. BC8-R1 therefore creates **no** new AI endpoint. `planning.generate`
remains a separate capability under the unified AI boundary, unchanged.

This is not a blocker: per §14 the minimum F1C5 is the typed membership gate, the paid
locked/unlocked state, the canonical plan read with derived status and factual dates,
`action_target` navigation, and no direct status write.

## 29. BC8-R1 gates

```
MEMBERSHIP_ENTITLEMENT_SUCCESS_UNKNOWN = 0
LEARNING_PLAN_ALLOWED_TYPED            = PASS
LEARNING_PLAN_REQUIRED_PLAN_TYPED      = PASS
HAND_WRITTEN_ENTITLEMENT_DTO           = 0
ENTITLEMENT_TYPE_ASSERTION             = 0
MEMBERSHIP_POLICY_CHANGED              = NO
FREE_PLAN_POLICY                       = DENIED
PAID_PLAN_POLICY                       = ALLOWED
F1C5_INITIAL_AI_GENERATION             = DEFERRED
GENERIC_LEARNING_GENERATION_API_FOR_F1C5 = FORBIDDEN
DB_SCHEMA_CHANGED                      = NO
MIGRATION_ADDED                        = NO
REAL_APP_DB_MUTATED                    = NO
TARGETED_TESTS                         = PASS  (14 BC8-R1)
FULL_BACKEND_TESTS                     = PASS  (1180 passed / 0 failed)
FRONTEND_TYPECHECK                     = PASS
FRONTEND_LINT                          = PASS
FRONTEND_UNIT_TESTS                    = PASS  (21 files / 76 tests)
FRONTEND_BUILD                         = PASS

F1C5_FRONTEND_READY                    = YES
```

Files changed by BC8-R1: `backend/main.py` (two response models + `response_model`),
`backend/tests/test_bc8r1_entitlement_contract.py` (new, 14 tests),
`frontend/src/types/api.ts` (regenerated),
`frontend/src/features/exam/api/entitlement-contract.test.ts` (new, 4 tests).

---

```text
FRONTEND_BC8_COMPLETE

CANONICAL_CS408_PLAN_OWNER = exam_study_plan_tasks (ExamStudyPlanTask)
                             + exam_study_plan_settings

STATUS_ROOT_CAUSE = main.py:18661 called _serialize_task(t) with no db, short-circuiting the
                    canonical list to ("not_started", "", "knowledge_map")
STATUS_FIX        = that call site now passes db; all readers share one semantic path

TASK_STATUS_SOURCE_OF_TRUTH = DERIVED from factual state (user_knowledge_progress /
                              exam_question_done_records), not persisted, not writable
TASK_STATUS_SEMANTICS = computed_status ∈ {not_started, in_progress, completed} |
                        knowledge: all bound leaves mastered |
                        chapter_practice: all bound questions practised |
                        review: no review_due leaves and all mastered

STATUS_UPDATE_CONTRACT = NO plan-task status write. A `status` field is refused with 422
                         (extra_forbidden) on create and update. The canonical non-AI status
                         operation is the factual action for the task's type, named by
                         action_target.
COMPLETE_TASK = PARTIAL (no endpoint; earned via the factual action)
REOPEN_TASK   = PARTIAL (same action, reversed)

PLAN_TASK_COMPLETION_WRITES_MASTERY = 0
PLAN_TASK_COMPLETION_RESOLVES_WRONG = 0

TODAY_PLAN_IS_TRUE_DAY_BOUNDARY = NO (preserved, not reinterpreted)
DATE_SEMANTICS = due_date is a free-form VARCHAR(30) string, best-effort parsed; the only
                 comparison is due_date < datetime.now().date(), server-local, used for the
                 urgency order; no date filter, no range, no timezone

BASE_PLAN_ENTITLEMENT_POLICY_PRESERVED = PASS
FREE_BASE_PLAN_LOOP = NOT_REQUIRED (§13 formally superseded by the later product decision)
PLAN_WORKSPACE_ACCESS = PAID_ENTITLEMENT
F1C5_ACCESS_MODEL = PAID_WORKSPACE

PLANNING_GENERATE_CAPABILITY = planning.generate (standard + advanced only; free denied;
                               separate from the learning_plan entitlement)
PLANNING_GENERATE_PERSISTENCE = NONE for the preview; the accept step persists LearningTask
                               (the COURSE model) — no AI path writes ExamStudyPlanTask
PLANNING_GENERATE_FAILURE_ISOLATED = PASS (502 on provider failure / 200 fallback on an
                                     unexpected error; the plan is byte-identical either way)
PLANNING_GENERATE_WRITES_LEARNER_FACT = 0 (one ai_requests row + one ai_called audit event;
                                     no task, no mastery, no wrong state)

MANUAL_TASK_CREATE = READY (typed, not added)
TASK_EDIT          = READY (fields only, no status)
TASK_DELETE        = READY

PLAN_LIST_ENDPOINT = GET /exam/11408/subjects/{subject_key}/study-plan
                     -> ExamStudyPlanResponse (typed, closed enums for computed_status and
                        action_target, backend-authored completion_reason)
PLAN_WRITE_ENDPOINTS =
- POST   /exam/11408/subjects/{subject_key}/study-plan/tasks
             req ExamStudyPlanTaskCreate / 200 ExamStudyPlanTaskMutationResponse
- PATCH  /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}
             req ExamStudyPlanTaskUpdate / 200 ExamStudyPlanTaskMutationResponse
- DELETE /exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}
             200 ExamStudyPlanTaskDeleteResponse
- PATCH  /exam/11408/subjects/{subject_key}/study-plan/settings
             req ExamStudyPlanSettingsUpdate / 200 ExamStudyPlanSettingsMutationResponse
- PATCH  /exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{node_code}
             req ExamStudyPlanChapterPracticeUpdate / 200 ExamStudyPlanChapterPracticeResponse

MODULE_CONTEXT = READY (subject_key + subject_name on route, row and item; 0 cross-module leak)
DEEP_LINK_CONTEXT = Knowledge READY (action_target=knowledge_map) - Practice READY
                    (practice_center) - Past Papers NOT AVAILABLE - Wrong Answers NOT AVAILABLE

CROSS_USER_PLAN_ACCESS = 0

PLAN_REQUIRED_REQUEST_UNKNOWN = 0
PLAN_REQUIRED_SUCCESS_UNKNOWN = 0
  (left untyped and reported separately: /learning/plans/* AI preview+import,
   /learning/tasks*, /course-learning/study-plan/*)

DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
REAL_APP_DB_MUTATED = NO

TARGETED_TESTS     = 23 BC8 backend + 4 frontend probe
FULL_BACKEND_TESTS = 1166 passed / 0 failed

FRONTEND_TYPECHECK  = PASS
FRONTEND_LINT       = PASS
FRONTEND_UNIT_TESTS = PASS (20 files / 72 tests)
FRONTEND_BUILD      = PASS

F1C5_FRONTEND_READY = YES
F1C5_ACCESS_MODEL   = PAID_WORKSPACE
BLOCKERS = none
```
