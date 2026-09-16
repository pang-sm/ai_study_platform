# ZHIXUE Real Data Contract V1

## 1. Scope and decision

This is a read-only Phase 4A audit for the first vertical slice only:
`Exam World → 11408 → Operating System → Learning Workspace`.

No frontend integration, backend/database change, migration, endpoint, dependency, UI change, staging, commit, or deployment is part of this document. The visual slice currently renders static **curriculum structure** only; it does not render invented learner history, progress, mastery, questions, or recommendations.

The audit conclusion is that 11408 already has reusable runtime contracts for curriculum, learner progress, chapter practice, past papers, generated questions, attempts, wrong questions, chat scope, and subject-scoped materials. It does **not** have a single canonical API that returns the exact four visual-page contexts, nor a current `NextBestAction` service.

## 2. Truth vocabulary

| Type | Meaning | Rule in the slice |
| --- | --- | --- |
| `CURRICULUM` | Persisted/seeded teaching structure independent of one learner | May render without a learner record. |
| `USER_STATE` | Authenticated learner's persisted status, attempts, dates, tasks, or wrong questions | Never infer when absent. |
| `DERIVED` | Deterministic calculation from curriculum and/or stored state | Label structurally; do not call it AI recommendation. |
| `RECOMMENDATION` | Model/ranker/system choice for an individual | Render only if a future real contract returns it. |

## 3. Sources and active evidence

### 3.1 Curriculum

* The four official 11408 subject keys are defined in `backend/main.py` as `data_structure`, `computer_organization`, `operating_system`, and `computer_network`.
* The authoritative runtime tree for each subject is the corresponding file in `backend/seed_data/knowledge_maps/`, loaded by `_knowledge_map_seed_path(course_id)`. `operating_system_11408.json` includes the memory-management sequence and `3.2.4 页面置换算法`.
* The visual labels `MM-01…MM-04` are presentation identifiers in the frozen slice, **not** identifiers exposed by that seed map. Phase 4B must map visual nodes to actual seed codes/titles rather than persist a second curriculum copy.
* `GET /exam/11408/subjects/{subject_key}/study-plan` loads that tree, attaches user state by `knowledge_point_code`, and returns `chapters`; `GET /exam/11408/study-plan/summary` returns all four subject summaries.

### 3.2 Safe aggregate database audit

The configured default SQLite database is `backend/app.db`. Aggregate counts were queried read-only; no user values were inspected.

| Table | Rows | Key / logical links | Active use relevant to the slice |
| --- | ---: | --- | --- |
| `exam_question_bank` | 9,333 | `id`; `subject_key`, string `knowledge_point_id` | Chapter questions/outline and question-bank endpoints. |
| `exam_practice_attempts` | 13 | `id`; `username`, `subject_key`, KP strings; question IDs JSON | Created/submitted by chapter practice. |
| `exam_wrong_questions` | 296 | `id`; links by `question_bank_id`, `practice_attempt_id` | Written on wrong chapter/AI answers; read by wrong-question API. |
| `past_paper_wrong_questions` | 0 | `id`; `attempt_id`, subject/year/question ID | Read/written by past-paper submit flow. |
| `ai_generated_questions` | 10 | `id`; `username`, subject, KP strings | Per-user generated question persistence. |
| `ai_question_attempts` | 3 | `id`; generated-question IDs JSON | AI question attempt flow. |
| `past_paper_attempts` | 13 | `id`; user/subject/year | Past-paper attempt flow. |
| `exam_question_done_records` | 370 | `id`; `question_bank_id` or `ai_question_id`, user/subject | Tags a question as practiced. |
| `user_knowledge_progress` | 14 | `id`; `knowledge_point_id` or map code, user/course | Study-plan/dashboard state. |
| `knowledge_progress_events` | 12 | `id`; logical `knowledge_point_id`, source type/id | Progress audit trail. |
| `knowledge_points` | 65 | `id`; logical tree `parent_id`, user/course | Generic knowledge-point API; separate from 11408 JSON map. |
| `exam_study_plan_settings` | 0 | unique user + subject | Read/write study-plan settings. |
| `exam_study_plan_chapter_practice` | 0 | unique user + subject + section code | Section completion bridge. |
| `exam_study_plan_tasks` | 6 | `id`; user/subject/KP name | Subject dashboard and plan tasks. |
| `study_materials` | 58 | `id`; user/course/subject scope | Subject-scoped materials/search. |
| `material_knowledge_links` | 26 | `id`; material ID + integer KP ID | Generic material-to-KP linkage, not aligned to the 11408 seed-code contract. |

The table models explicitly declare primary keys. Most learner/content links above are logical rather than SQL foreign keys; adapters must therefore validate subject/course ownership and must not equate an integer `KnowledgePoint.id` with a string 11408 map code without an explicit mapping.

## 4. API matrix

All user-state endpoints below use `get_current_user` and validate the requested username against that user. Study-plan endpoints additionally require the `exam_11408` / `learning_plan` entitlement.

| Need | Method/path | Request and relevant response | Source / status | Current visual-slice consumer |
| --- | --- | --- | --- | --- |
| Four-subject 11408 overview | `GET /exam/11408/study-plan/summary` | query `username`; returns `subjects[]` with key/name, section/KP totals, mastered count, `overall_progress`, `has_activity`, completion | JSON seed map + user progress + chapter-practice rows; real | none |
| One subject curriculum + status | `GET /exam/11408/subjects/{subject_key}/study-plan` | query `username`; returns course/subject, settings, stats, review interval, enriched `chapters`, tasks | JSON seed + user progress + plan tables; real | none |
| Subject dashboard | `GET /exam/11408/subjects/{subject_key}/dashboard-summary` | query `username`; overview, recent tasks, material counts and other dashboard fields | seed + state/attempt/task/material tables; real | none |
| Chapter availability | `GET /exam/11408/{subject_key}/chapter-practice/outline` | returns KP-id-to-count map and total | active `exam_question_bank` rows where `source_type=chapter`; real | none |
| Chapter questions | `GET /exam/11408/{subject_key}/chapter-practice/questions` | query `knowledge_point_id`, optional path/children; returns serialized questions and `practiced` | question bank + done records; real | none |
| Chapter attempt | `POST/GET/POST/POST /exam/11408/{subject_key}/chapter-practice/attempts…` | create with selected question IDs/KP metadata; retrieve, save answers, submit result | attempts, done records, wrong questions; real | none |
| Past papers | `GET /exam/11408/{subject_key}/past-papers`, `/past-paper-questions`; attempt endpoints | public listings/questions; authenticated user attempts | resource parser + past-paper attempt/wrong-question tables; real, availability depends on imported asset | none |
| AI questions | `POST /exam/11408/{subject_key}/ai-questions/generate` | `count`, optional KP id/name/path, question type, difficulty, requirement; returns generated/fallback items | generated-question table; provider use logs usage when provider call succeeds/fails | none |
| Wrong questions / done | `GET /exam/11408/{subject_key}/wrong-questions`, `/done-records` | optional source/mastered filters; merged items or records | wrong-question tables + done records; real | none |
| Generic Ask AI | `POST /chat` | `ChatRequest`: course/subject IDs, `exam_subject`, `service_key`, optional material IDs and `knowledge_context` | chat/session/messages plus scoped RAG; real | none |
| Subject resources | `GET /materials`, `GET /materials/search` | `course_id` + `subject_key`; search also needs `q` | accessible study materials/RAG chunks; real at subject/course scope | none |

## 5. Learner state contract

`user_knowledge_progress` provides `status`, `user_confirmed_status`, `mastery_score`, `practice_count`, `task_count`, `last_studied_at`, `learned_at`, `review_due_at`, and `review_interval_days`. The supported display states are exactly `not_started`, `learning`, `mastered`, and `review_due`.

`_display_map_progress_status` gives `review_due` precedence when a mastered item has passed `review_due_at`; otherwise it uses user-confirmed status before stored status. This is real, usable state for a seed-map node only when the row's `course_id` and `knowledge_point_code` align with that map. An absent row means neutral `not_started`, not an actual learning history.

The generic `/knowledge-points/{point_id}/progress` endpoint operates on user-owned integer `knowledge_points`; it must not be used as a shortcut for the 11408 seed code model. Phase 4B should use the 11408 study-plan endpoints for 11408 page status.

## 6. Page and adapter contracts (design only)

Adapters belong under a future `frontend/src/features/learning/` boundary (or equivalent feature-local location), converting API payloads to visual data. They must return loading/error/empty states separately from data. No adapter is created in Phase 4A.

### `ExamWorldData`

| Field | Source / type | Nullable and fallback |
| --- | --- | --- |
| `exams` | Static product catalog; `CURRICULUM` | The catalog may contain the real 11408 entry while no global exam-catalog API exists. Do not invent user enrollment. |
| `primaryExam` | static 11408 entry | Always available as structural entry. |
| `learnerSummary` | 11408 summary endpoint; `USER_STATE`/`DERIVED` | `null` until authenticated request succeeds; API failure shows safe entry/retry, not progress. |

### `ExamContextData`

| Field | Source / type | Nullable and fallback |
| --- | --- | --- |
| `examKey`, `title`, `subjects[]` | summary + fixed 11408 product metadata; `CURRICULUM` | Subject order must derive from backend keys/explicit adapter order. |
| `subjectTotals` | study-plan summary; `DERIVED` | Null on failed user-state API; retain structural subject list. |
| `currentFocus` | no canonical persisted current-focus field | `null` for user state. The frozen OS/memory focus is only a route/curriculum presentation default. |
| `nextStructuralNode` | deterministic selected seed-map sequence; `DERIVED` | May show "结构下一步", never "recommended". |

### `SubjectContextData`

| Field | Source / type | Nullable and fallback |
| --- | --- | --- |
| `subject`, `chapters`, `nodes` | subject study-plan `chapters`; `CURRICULUM` | Required for a successful response; preserve last safe structural data only as non-user content. |
| `nodeState` | enriched study-plan state; `USER_STATE` | Each value nullable/neutral when there is no user row. |
| `chapterPractice` | plan chapter-practice/status and chapter outline; `USER_STATE` + `CURRICULUM` | No question count is fabricated; unavailable matching becomes `null`. |
| `structuralNext` | seed order; `DERIVED` | Not a recommendation. |

### `WorkspaceContextData`

| Field | Source / type | Nullable and fallback |
| --- | --- | --- |
| `exam`, `subject`, `chapter`, `knowledgePoint` | route-to-seed resolver; `CURRICULUM` | Resolver failure is an invalid/unsupported context, not a guessed node. |
| `practiceAvailability` | chapter outline/questions; `CURRICULUM` | `null` on mismatch/empty; disable entry with explanation. |
| `materialsScope` | `{ course_id: 'operating_system_11408', subject_key: 'operating_system' }`; `CURRICULUM` | Subject-level materials only. |
| `aiScope` | chat fields `service_key='exam_11408'`, `exam_subject`, course/subject IDs; `CURRICULUM` context | The chat schema accepts `knowledge_context`, but no verified dedicated chapter/KP scope contract exists. Include context in the user-visible adapter/request, not as claimed retrieval filtering. |
| `nextStructuralNode` | seed sequence; `DERIVED` | Current visual copy remains structural. |

### `LearnerStateData`

| Field | Source / type | Nullable and fallback |
| --- | --- | --- |
| `status`, `userConfirmedStatus`, `masteryScore`, `learnedAt`, `reviewDueAt`, `reviewIntervalDays`, `lastStudiedAt` | 11408 study-plan enrichment / `user_knowledge_progress`; `USER_STATE` | Entire object is `null` when no row. UI uses neutral curriculum-only state. |
| `attemptSummary`, `wrongCount`, `done` | practice/wrong/done APIs; `USER_STATE`/`DERIVED` | Null/empty only after successful source-specific response; never synthesize. |

## 7. AI and resources

`POST /chat` supports an exam-aware scope via `service_key`, `exam_subject`, `subject_key`, `course_id`, and optional explicit `material_ids`; it creates chat history and uses subject/course scoped RAG. Its schema also accepts `knowledge_context`, but the audited handler does not establish a dedicated validated chapter/knowledge-point retrieval filter. The Workspace adapter can carry `memory_management` / `virtual_memory` as contextual metadata/text, but cannot claim that retrieval is knowledge-point filtered.

The exam AI-question generator supports string KP id/name/path in its request and persists them. Its provider-success/failure path calls `record_ai_usage` with `service_key='exam_11408'`. It may return a clearly marked fallback/mock result when a provider/key is unavailable; Phase 4B must expose that fact or avoid presenting it as real AI output.

Materials endpoints have verified course/subject filters. There is no audited `GET` endpoint that lists resources filtered by the 11408 seed-code node or by the workspace KP. `material_knowledge_links` exists but is keyed to generic integer KPs, so it is not yet a safe bridge to a string 11408 map code.

## 8. Fallback policy

1. API success with a matching learner row: render the returned `USER_STATE`.
2. API success with no learner row: render neutral curriculum-only state (`not_started`/empty user fields), without percentages, history, scores, or recommendations.
3. API failure: show explicit error/retry and retain only safe structural curriculum content where independently available.
4. Never turn an absent API response into fake progress, attempt history, mastery, material relevance, or model recommendation.

## 9. Known gaps

* No global exam-catalog endpoint; use a small static product catalog with the real 11408 entry.
* No canonical persisted "current focus" or unified `NextBestAction`; the current OS/virtual-memory focus and page-replacement next node can only be structural/route-derived.
* No one-to-one public adapter from the visual `MM-*` labels to seed-map codes.
* 11408 curriculum uses seed JSON and string codes while generic KPs/material links use integer IDs; a mapping decision is required before KP-level resource retrieval.
* The current visual slice itself has no API calls. Existing generated `frontend/src/types/api.ts` declares the endpoints, but no slice consumer invokes them.
* Chapter-practice availability is queryable, but a Virtual Memory UI mapping must first resolve to an actual question-bank `knowledge_point_id`/path.

## 10. Phase 4B integration order

1. **P0 — curriculum resolver:** map 11408 summary and OS study-plan tree to `ExamWorldData`, `ExamContextData`, and `SubjectContextData`; retire duplicate visual structure only after output parity is proven.
2. **P0 — workspace resolver:** resolve route context to actual seed node codes/titles, then use chapter outline to determine whether a practice entry is available.
3. **P1 — learner state:** map enriched study-plan states to `LearnerStateData` with neutral/error behavior; do not choose a personal current node yet.
4. **P1 — practice and Ask AI:** wire chapter-practice flows and a scope-aware chat adapter. Preserve provider-fallback transparency.
5. **P2 — review/material bridge:** expose wrong/done records and review dates; add KP-level resource filtering only after resolving the integer/string key mismatch.
6. **Future:** introduce a separately audited state-aware next action and then model recommendation. Neither belongs in the first integration.

Phase 4B can begin with existing APIs and frontend adapters. No backend/database change is required for P0/P1 subject curriculum, status, practice availability, or AI request scope. A minimal backend/data mapping change is likely required before claiming true knowledge-point-level materials or a unified personalized next action.

## 11. Phase 4A change record

Only this audit document was created. No UI, frontend runtime code, backend code, database, dependency, Git index, commit, or deployment changed.
