# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3B_BACKEND_REPORT

Task: `PHASE A — THREE_DOMAIN_PRODUCTIZATION_P1_3_GLOBAL_WRONG_SECURITY` +
`PHASE B — THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3B_BACKEND`
Date: 2026-09-20
Scope: (A) fail-closed content resolution on the GLOBAL wrong-answer surface for every space;
(B) Structured Learning Report + Deep Wrong-Cause + Dynamic Planning — no dashboard CRUD, all
of it on the existing LearningEvent / Records / Review / Plan / LearningContext / Capability /
Usage / Gateway stack.
No frontend change, no migration, no schema change, no commit, no deploy.

---

## 1. FILES

**New**

| File | What it is |
|---|---|
| `backend/learning/report.py` | the deterministic report builder + the optional narrative |
| `backend/routers/learning_report.py` | `POST /ai/learning-report` |
| `backend/learning/wrong_analysis.py` | deep wrong-cause analysis (facts vs AI) |
| `backend/learning/plan_adjustment.py` | plan proposal + plan apply (separate actions) |
| `backend/routers/plan_adjustment.py` | `POST /ai/plan-adjustment`, `POST /ai/plan-adjustment/apply` |
| `backend/tests/test_p1_3_global_wrong_security.py` | 9 tests |
| `backend/tests/test_p3b_learning_report.py` | 7 tests |
| `backend/tests/test_p3b_wrong_analysis.py` | 5 tests |
| `backend/tests/test_p3b_plan_adjustment.py` | 6 tests |

**Edited** (all additive): `learning/spaces/exam_prep/wrong_answers.py` (identity gate),
`routers/wrong_answers.py` (namespace dispatch + the analysis endpoint + one enum value),
`usage/capabilities.py`, `ai/pool.py`, `ai/cost.py`, `learning/records/taxonomy.py`,
`learning/records/producers.py`, `prompts.py`, `main.py` (router registration),
`tests/test_bc7_wrong_answer_canonicalization.py` (one CONTRACT CORRECTION, see §4).

---

## 2. P3A_FINAL_CERTIFICATION

```
./.venv/Scripts/python.exe -m pytest -q          (backend/, TEMP DATABASE_URL)
1649 passed, 2 skipped, 0 failed in 1208.44s (0:20:08)
```
Recorded in `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A_BACKEND_REPORT.md` §12 — that report
is frozen. P1.3 + P3B were built on top of that certified tree; nothing in it was reverted.

---

## 3. P1_3_GLOBAL_WRONG_SECURITY

### 3.1 What was actually wrong (forensics)

| # | Defect | Where |
|---|---|---|
| 1 | content resolved from a BARE primary key, with no owner check | `exam_prep/wrong_answers.py::_SourceIndex._load_ai` / `_load_bank` |
| 2 | the GLOBAL `GET /wrong-answers` rendered EVERY state — including `course_learning` ones — through the EXAM resolver, applying the wrong space's resolution rules to a course question | `routers/wrong_answers.py` |
| 3 | an id two public sources claimed for different questions silently preferred one | `_fill_past_paper` (legacy branch) |

### 3.2 What changed

**Namespace dispatch (requirement 4).** `_render_records` / `_render_one` group the states by
`service_namespace` and render each group with the resolver that OWNS its space: course states
→ the P1.2-hardened course resolver, exam states → the exam resolver. The page order is the
caller's order (the records are mapped back by state id), so which resolver a row went to never
changes the list. The detail and PATCH routes dispatch the same way.

**The exam identity gate (requirements 1, 2, 3, 5, 6).** `_chapter_row_for` /
`_past_paper_bank_row` / `_module_matches` / `_public_or_owned`:

* an AI-generated question is resolved ONLY for the state's own learner — and the batch query
  itself is owner-scoped (`username IN (...)`), so another learner's row is never loaded;
* the row's subject must resolve to the STATE's module (through the ONE module resolver the
  exam space already uses; an unresolvable pair falls back to exact equality and a mismatch is
  refused);
* public BANK content needs no per-user owner (it is public teaching material) but must still
  prove it is `public` (or the caller's own) and of this state's module; a foreign private row
  is refused;
* the legacy past-paper branch resolves BOTH candidate sources and refuses when they disagree
  about which question the id names — no source is preferred and no lookup falls through to a
  second table because the first one missed;
* a state that states no owner resolves nothing (fail closed, requirement 7).

**The course semantics are untouched** (requirement 8): the course resolver is the one P1.2
froze; the global surface now simply routes to it. A course record is presented in this
surface's union shape by filling the (required, BC7-frozen) module fields with the honest
empty value — a course question has no exam module — and by declaring the two course-specific
fields (`course_id`, `question_id`).

---

## 4. P1_3_TARGETED_TESTS

`tests/test_p1_3_global_wrong_security.py` — 9 tests:

| Requirement | Test |
|---|---|
| global route cannot leak another user's AI question | `test_the_global_route_cannot_show_another_learners_ai_question` |
| exam AI row requires owner/context | `test_an_exam_ai_question_must_belong_to_the_states_module`, `test_a_state_without_an_owner_resolves_nothing` |
| static exam-bank row still works | `test_public_bank_content_still_resolves_but_foreign_private_does_not`, `test_a_bank_row_of_another_module_is_not_shown` |
| colliding PK across tables cannot switch source | `test_a_colliding_id_across_tables_cannot_switch_source` |
| ambiguous legacy state fails closed | `test_a_legacy_past_paper_id_two_sources_disagree_about_fails_closed` |
| course state uses course resolver semantics | `test_a_course_state_is_rendered_by_the_course_resolver`, `test_a_course_state_pointing_at_an_exam_question_resolves_nothing` |

**Targeted + wrong-answer relevant suite** (the run requested before P3B):

```
tests/test_p1_3_global_wrong_security.py   +   the wrong-answer / exam / course / review
surface (test_wrong_answers*, test_bc7_*, test_exam_practice_records, test_exam_prep_namespace,
test_three_domain_p1*, test_course_p1_1_contracts, test_p3a_unified_review, test_course_space)
237 passed, 0 failed in 105.95s
```

P1.2's 13 tests remain green inside that run (requirement: they must).

### CONTRACT CORRECTION (one frozen assertion)

`tests/test_bc7_wrong_answer_canonicalization.py::test_canonical_surface_is_typed_in_openapi`
asserted the `source_kind` enum was exactly `["chapter_practice", "past_paper", "ai_generated",
"other"]`. This surface now serves course records too, and the course resolver distinguishes a
material-generated course question from an unmapped one, so the enum gained `course_material`.
The four BC7 values are unchanged; the assertion is updated with an explicit CONTRACT
CORRECTION comment (the same discipline P1.2 used). The `module_key` / `module_name`
required-ness was preserved rather than relaxed — a course row fills them empty instead.

---

## 5. STRUCTURED_REPORT (B1)

`POST /ai/learning-report` — capability **`report.generate` (REUSED, not re-created)**.

```
DB / Records / Review / State  →  deterministic structured metrics  →  ReportData
                                                                        ↓
                                                          optional LLM narrative
```

* The deterministic half is FREE and needs no entitlement: it is the learner's own data,
  computed by SQL from the caller's rows. The narrative is OFF unless requested
  (`include_narrative`), and it is the only part that spends credits.
* The narrative is composed through the space's own AI boundary with the space's
  `LearningContext` and the `report.generate` capability — the full
  permission → estimate → reserve → router → gateway → settle path.
* **A narrative that cannot be produced is ABSENT and STATED**: the report is returned with
  `narrative: null` and `narrative_error` (`capability_not_permitted` / `http_429` / …). It is
  never simulated, and a failed add-on never withholds the deterministic deliverable.
* `report.generate` is currently **Advanced-only** (a pre-existing policy decision); the report
  is therefore fully available to every tier and the narrative to Advanced.

**Response**: `report_id`, `report_period {days, start, end}`, `context`, `structured_metrics`,
`highlights[]`, `attention_items[]`, `data_coverage`, `narrative` (or null), `narrative_error`,
`generated_at`.

**Highlights / attention items are RULES**: each carries `origin: "deterministic"` and its rule
id (`practice_attempts`, `active_days`, `plan_completed`, `programming_passed`;
`wrong_answers_active`, `review_due`, `plan_overdue`, `practice_incorrect`,
`programming_needs_work`). The AI narrative is the ONLY AI-produced element, it is labelled
`origin: "ai"`, and it is never merged into those arrays.

---

## 6. REPORT_DATA_BUILDER

Per-space blocks, all computed in SQL over the caller's own rows inside the window:

| Block | Source | Availability |
|---|---|---|
| `activity` | `learning_events` (counts by type + distinct study days) | all spaces |
| `practice` | `practice_attempts` (attempts / factual correct / factual incorrect / ungraded) | all spaces |
| `review` | the SAME projection `/review` serves (counts by status and source) | all spaces |
| `plan` | `exam_study_plan_tasks` for the space's own subject key (total / completed / open / overdue) | all spaces |
| `materials` | `material_opened` / `material_asked` events + distinct materials touched | course, exam |
| `programming` | `code_run` / `code_tested` / `code_submitted` events, pass/fail, distinct exercises | programming |

* **MISSING IS NOT ZERO**: a block that does not exist for a space is `null` with
  `{"block", "reason": "not_applicable_in_this_space"}` in `data_coverage.unavailable`. A block
  that applies and is 0 is a real zero (a fact).
* `data_coverage.recent_events` lists the newest events of the window as references + timing —
  never payload text.
* The AI narrative receives EXACTLY the ReportData JSON and nothing else (asserted: a
  distinctive string from the learner's raw study data never appears in the prompt).

---

## 7. DEEP_WRONG_CAUSE (B2)

`POST /wrong-answers/{state_id}/analysis` — new capability **`wrong_answer.analyze`**
(Standard + Advanced, routed through the already qualified explanation profile).

* The state is resolved with the SAME ownership check every wrong-answer read uses, and its
  content through the space's HARDENED resolver (P1.2 course / P1.3 exam) — there is no second
  materialization surface and no second content path.
* **FACTS** (`fact_origin: "deterministic"`): the question (stem / options / reference answer /
  recorded explanation), the learner's own answer, the real attempt history, the recorded state
  and timing, the space context, and the source identity.
* **AI_ANALYSIS** (`analysis_origin: "ai"`): `error_category`, `reasoning_gap`,
  `correct_reasoning`, `next_action`, `review_recommendation` — plus
  `analysis_semantics: "AI 对错因的解释，不是对学习者能力的测量；不写回为学习事实"`.
* **A state whose question cannot be proven is NOT analysed** (409
  `question_content_unavailable`): no empty-stem analysis, no invented reasoning, and no
  cross-user read through the analysis path.
* **Persistence is stated honestly**: the FACT that an analysis happened is durable (the
  canonical `wrong_analysis_generated` event + the `ai_requests` row with its cost/latency);
  the analysis TEXT has no owned store this round —
  `persistence: {"stored": false, "reason": "no_owned_store_for_ai_analysis_text", ...}`
  (see BLOCKERS).

---

## 8. DYNAMIC_PLANNING (B3) + PLAN_PROPOSAL_APPLY

```
POST /ai/plan-adjustment          propose  — WRITES NOTHING
POST /ai/plan-adjustment/apply    apply    — the ONLY action that changes a plan
```

* **Capability** `planning.adjust` (Standard + Advanced, planning profile), user-triggered only:
  there is no background planner and no auto-apply path.
* **The context is facts**: the current plan (tasks with id/title/type/status/due date), the
  review projection, the practice counts and the recent event types of that space — nothing
  else goes to the model.
* **The proposal** carries `plan_identity` (a deterministic fingerprint of the plan's current
  state), `reason`, `proposed_changes[]`, `affected_tasks[]`, `dropped_changes[]`,
  `plan_snapshot`, `usage`, `request_id`. Every change is validated against the plan it just
  read: a closed op set (`create_task`, `update_task`), a bounded count, and — for updates —
  the task MUST be one of this plan's own tasks. Anything else is dropped and reported, never
  applied.
* **The apply** re-verifies, at that moment: ownership (the caller's own tasks, re-checked per
  task) and the plan identity. A mismatch is `409 stale_proposal` — an old proposal can never
  overwrite a plan the learner changed since. The apply needs NO AI (it is a plan edit the
  learner asked for) and spends nothing.

---

## 9. CAPABILITY_USAGE (B4)

| Capability | Tier policy | Model profile | Billed |
|---|---|---|---|
| `report.generate` | advanced (EXISTING, reused) | existing | one call per narrative |
| `wrong_answer.analyze` | standard + advanced (new) | `question.explain` proxy | one call per analysis |
| `planning.adjust` | standard + advanced (new) | `planning.generate` proxy | one call per proposal |

* No new quota system: `ai/pool.py ALL_CAPABILITIES` + the two qualification proxies + the tier
  policy are the ONLY registrations. `POOL_VERSION` / `POOL_QUALIFICATION_LEVEL` are unchanged:
  no model was re-benchmarked and no pool entry was edited.
* Every AI call goes estimate → reserve → execute → settle through `ai.orchestrator`, with the
  space's `LearningContext` (asserted: the analysis's and the narrative's `ai_requests` rows
  carry the right `service_namespace` and a `settled` status).
* **Apply costs nothing** because it calls no model — stated here so the absence of an
  `ai_requests` row for it is not read as a missing settlement.
* `apply` is intentionally NOT capability-gated: the learner can already edit their own plan
  through the existing plan API, so a paid gate there would be arbitrary. Ownership + identity
  are its gates.

---

## 10. EVENTS (B5)

Four new canonical families, all ACTIVE (a real producer exists), all
`student_twin_eligible=False`:

| Event | Category | Namespace(s) | Payload (references only) |
|---|---|---|---|
| `report_generated` | AIEvent | course / exam / programming | report id, period, metric blocks, narrative flag, request id |
| `wrong_analysis_generated` | WrongAnswerEvent | course / exam | state id, question identity, request id |
| `plan_adjustment_proposed` | PlanEvent | course / exam / programming | proposal id, change count, plan identity |
| `plan_adjustment_applied` | PlanEvent | course / exam / programming | proposal id, applied count, plan identity |

* `review_completed` remains **DEFERRED** — as in P3A, no review-completion action exists, so
  emitting it would violate NO SOURCE → NO EVENT. No duplicate family was invented.
* `ai_called` remains the ONE accounting fact per model call; these are the STUDY/PLAN facts.
* §34 respected: no prompt, response, code, analysis text or report text enters an event
  payload (asserted for the analysis event).
* `service_namespace` + domain context are correct per fact (asserted for course and exam).

---

## 11. FULL_BACKEND_SUITE

The P1.3+P3B full run was superseded — deliberately, and only once — by the single final
certification that covers P1.3 + P3B + P4 + P5 together (the task chain asked for one final
full run rather than repeated ~30-minute certifications). That result is recorded in
`THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5_LEARNING_ORCHESTRATOR_REPORT.md` §13.

Before it, the P1.3 + P3B work was verified by its own targeted sets, all green:

```
P1.3 targeted + wrong-answer relevant suite   237 passed, 0 failed
P3B report / wrong-analysis / planning         18 passed, 0 failed
P3A + P3B + P1.3 regression set                52 passed, 0 failed
```

No P1.3 or P3B change was weakened or reverted afterwards.

---

## 12. MAIN DB PROTECTION

```
MAIN_DB_SHA_BEFORE = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER  = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SIZE       = 64917504 bytes (before and after)
MAIN_DB_MTIME      = 1789877022 (2026-09-20 12:03:42.878312700 +0800, before and after)
MAIN_DB_TOUCHED    = NO
```

No `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
`push` / `commit` / `deploy` was run. **No frontend file was touched by this session.** No
migration and no schema change was made (see BLOCKERS §1).

### 12.1 Note on the working tree (an observation, not this task's change)

`frontend/src/types/api.ts` changed three times INSIDE this session's window
(15:30, 16:18 and 16:52 for the sibling home component / generated types) with no write from
this session — the generated type file grew from 773 KB to 795 KB, which is what an
`npm run api:generate` write looks like. The P3A report already recorded the first two; the
16:52 regeneration is recorded here. Whatever it was generated from, the frontend must
re-generate after this backend change set lands to pick up
`POST /ai/deep-study`, `POST /programming/agent/debug`, `GET /review`, `GET /review/summary`,
`POST /ai/learning-report`, `POST /wrong-answers/{state_id}/analysis`,
`POST /ai/plan-adjustment` and `POST /ai/plan-adjustment/apply`.

---

## 13. FRONTEND READINESS

```
REPORT_FRONTEND_READY          = YES (render null blocks as unavailable, never as 0)
WRONG_ANALYSIS_FRONTEND_READY  = YES (facts and analysis must be rendered as two origins)
DYNAMIC_PLANNING_FRONTEND_READY = YES (two-step contract; 409 stale needs a re-propose path)
```

* **Report** — typed (`LearningReportResponse` + `ReportNarrativeView`). The client must render
  a `null` metric block as "该空间暂无此类数据" (with `data_coverage.unavailable` as the reason),
  and must show `narrative_error` when set. `include_narrative` is a client choice.
* **Wrong analysis** — typed (`WrongAnalysisResponse`). `facts` and `analysis` carry different
  origins and the client should keep them visually distinct; `persistence.stored = false` means
  the analysis must be cached client-side if it is to be shown again after a reload.
* **Dynamic planning** — typed (`PlanAdjustmentProposal` / `PlanApplyResponse`). The apply call
  MUST send back `plan_identity`; a `409 stale_proposal` means the plan moved and the client
  should re-propose. `dropped_changes` should be surfaced (the model proposed something the
  server refused).
* `POST /wrong-answers/{state_id}/analysis` lives on the existing wrong-answer surface, so the
  wrong-answer workspace can add its own action without a new resource.

---

## 14. GATES

```
P3A_FINAL_CERTIFICATION      = 1649 passed / 2 skipped / 0 failed (20:08) — frozen
P1_3_GLOBAL_WRONG_SECURITY   = PASS (namespace dispatch + owner/context/table gate; ambiguous legacy refused)
P1_3_TARGETED_TESTS          = 9 new tests + 237 relevant tests green (1 CONTRACT CORRECTION recorded)
STRUCTURED_REPORT            = PASS (deterministic metrics first; narrative optional, labelled, gate-able)
REPORT_DATA_BUILDER          = PASS (6 blocks in SQL; missing ≠ zero; per-user and per-space scoped)
DEEP_WRONG_CAUSE             = PASS (facts vs AI analysis separated; unprovable content refused)
DYNAMIC_PLANNING             = PASS (proposal writes nothing; user-triggered only)
PLAN_PROPOSAL_APPLY          = PASS (apply re-verifies ownership + plan identity; stale → 409)
CAPABILITY_USAGE             = PASS (3 capabilities on the ONE chain; no new quota; apply costs nothing)
EVENTS                       = PASS (4 new families with real producers; §34 respected; review_completed still DEFERRED)
FULL_BACKEND_SUITE           = superseded by the single final certification (P5 report §13); targeted sets green (§11)
MAIN_DB_SHA_BEFORE           = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER            = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_TOUCHED              = NO
REPORT_FRONTEND_READY          = YES
WRONG_ANALYSIS_FRONTEND_READY  = YES
DYNAMIC_PLANNING_FRONTEND_READY = YES
```

---

## 15. BLOCKERS

1. **The wrong-analysis TEXT has no durable store.** §34 forbids AI response text in an event
   payload and this round created no table, so the analysis is returned + recorded as a FACT
   (event + `ai_requests`) and `persistence.stored` says so. Giving it a store means a new
   table + Alembic `20260920_0013` + updating the seven other sprints' frozen head-pin
   assertions — the same cross-sprint governance step P3A reported. Recommendation: decide the
   store once, and take both limitations (this one and the P3A agent trace) in that step.
2. **`report.generate` is Advanced-only** (pre-existing policy). The report itself is free; a
   Standard narrative needs a POLICY decision, not a code change. The endpoint already reports
   `narrative_error: "capability_not_permitted"` rather than failing the report.
3. **`narrative_error: "http_429"` is ambiguous on the course path**: the course AI boundary
   maps every non-denial failure (including a technical one) to 429, so the report cannot tell
   a budget refusal from a provider failure there. Changing that mapping is a change to the
   frozen AI boundary contract; reported instead of changed.
4. **The P3A agent's per-step trace limitation stands** (no dedicated table; patch text is
   response-only). Unchanged by P3B.
5. **Dynamic planning is single-shot per request**: one proposal, one apply. There is no
   multi-round negotiation, no proposal store, and no scheduler — by design for v1.
6. **`main.py` gained four more paths** (the report, the plan proposal, the plan apply and the
   analysis route on the wrong-answer router). Any document pinning the old endpoint count is
   stale by that amount.
7. **No migration was added**, so `MIGRATION_HEAD` remains `20260919_0012` (true as of this
   report). A future trace/analysis store will move it and must update the seven head-pin tests
   in the same change.
