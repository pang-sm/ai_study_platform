# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5_LEARNING_ORCHESTRATOR_REPORT

Task: `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5_LEARNING_ORCHESTRATOR`
Date: 2026-09-20
Scope: Daily Learning Orchestrator V1 · priority policy · three-domain continuity · action
completion · explainability · feedback analytics · two P4-blocker decisions (router health
persistence, review storage).
No frontend change, **no migration, no schema change**, no commit, no deploy.

---

## 1. FILES

**New**

| File | What it is |
|---|---|
| `backend/learning/agenda.py` | the DailyAgenda projection + the versioned priority ladder |
| `backend/routers/agenda.py` | `GET /learning/agenda`, `GET /learning/agenda/explain` |
| `backend/learning/feedback_analytics.py` | read-only feedback aggregation (offline Champion/Challenger input) |
| `backend/tests/test_p5_agenda.py` | 10 tests |
| `backend/tests/test_p5_feedback_analytics.py` | 4 tests |
| `backend/tests/test_p5_review_persistence.py` | 5 tests |

**Edited** (all additive): `learning/adaptive.py` (an `emit_event` flag + the exam candidate
filter moved into SQL — see §9), `learning/review.py` (schedules are attached BEFORE the
bucket filter — a real ordering bug found by the §H tests), `ai/health.py` (`describe()`),
`routers/p4_adaptive_feedback.py` (feedback analytics + availability endpoints), `main.py`
(router registration).

---

## 2. P4_FINAL_CERTIFICATION

```
./.venv/Scripts/python.exe -m pytest -q          (backend/, TEMP DATABASE_URL)
1703 passed, 1 failed, 2 skipped in 919.15s (0:15:19)
```

The single failure was **my own P4 adaptive test**, and it was a REAL defect it caught: the
exam candidate source applied its module filter in Python AFTER a bounded id window, so in the
full suite other tests' bank rows crowded this module's rows out of the window. Fixed by
pushing an exact-match module key set into SQL (and keeping the canonical check as defence in
depth); re-verified against the exam-heavy files, then certified again by the P5 full run
(§10). The P4 report is updated with this certification and its fix.

---

## 3. DAILY_AGENDA

`GET /learning/agenda` — "what should I do next", computed from facts that already exist.

**Sources** (every read owner-scoped and bounded):

| source | what it contributes |
|---|---|
| plan tasks | the caller's `exam_study_plan_tasks` attributed by their OWN `subject_key` |
| review items | DUE review items (a stored/computed date has passed) + wrong answers and exercises that are actionable with no date |
| adaptive practice | the P4 selector's candidates, **only for spaces the learner actually uses**, and read as an INPUT (no selection event — see §8) |

**Item**: `action_type` (`review` / `practice` / `plan_task` / `programming`),
`service_namespace`, `domain_context`, `source_type`, `source_id`, `title`, `summary`,
`priority_reason`, `deep_link`, `due_at`, `facts`, `status`, `resolved_by`.

**Response**: `policy_version`, `generated_at`, `items[]`, `total_items`, `source_summary`
(per-source counts, unattributable tasks, deduplicated), `by_namespace`, `by_reason`,
`priority_order`, `filters`, `semantics`.

An item whose domain cannot be established (a plan task whose key this build does not
recognize) is EXCLUDED and counted — never attached to whatever context the caller sent.

---

## 4. PRIORITY_POLICY

`agenda_policy_v1` — one fixed ladder, spelled the same in the code, the response and the
explain endpoint:

```
overdue_plan_task → due_review → repeated_wrong → needs_work
                  → current_plan_task → adaptive_recommendation → unseen_coverage
```

* Ordering inside a rank is deterministic too (earliest due date, then source and id), so the
  SAME stored facts always produce the SAME list in the SAME order — asserted.
* Every item carries its reason code AND the facts behind it (`overdue: true`, `wrong_count`,
  `review_status`, the adaptive reason, …) — the reason is checkable, not decorative.
* **No model decides the order, and no weakness / mastery / readiness is computed.** Those
  words do not appear in the output because no such fact exists; a test scans the payload for
  prediction-shaped keys.
* A knowledge point with no stored date never enters as work; a `scheduled` (future) item waits
  for its date.

---

## 5. THREE_DOMAIN_CONTINUITY

Course, exam and programming items coexist in ONE agenda, and each item's domain comes from
**its own row**: a plan task from its `subject_key`, a review item from its own space, a
practice recommendation from the space that produced it. Consequences, all asserted:

* the namespace filter can only NARROW — it never re-attributes an item;
* a programming `needs_work` item cannot appear under a course filter, and a course item cannot
  be opened through an exam filter (deep links are built from the item's own domain);
* a course plan key resolves to the course's CANONICAL identity (`data_structure` →
  `数据结构`) through the SAME subject map the course space uses, so the deep link addresses
  the course the product actually has;
* the practice source is included only for spaces the learner has real activity in — an agenda
  is advice about work in progress, not a catalogue.

---

## 6. ACTION_COMPLETION

The agenda **copies no business state and owns no completion flag**:

* `resolved_by` states the FACT that changes an item (`review_completion`,
  `plan_task_completion`, `practice_attempt`), not a UI action;
* completing the real action on the item's own surface is the only thing that changes anything
  (asserted: completing a review moves its schedule into the future and completing a plan task
  removes it, on the very next read);
* no second "completed" concept exists anywhere — a test asserts an agenda read writes NOTHING
  (no event, no row) and that two consecutive reads agree.

---

## 7. AGENDA_EXPLAINABILITY

`GET /learning/agenda/explain` — the competition/explainability surface. It answers the three
questions directly:

* **why this, now** → `priority_rules` (the rule behind every reason code) + each item's
  `facts` + its `priority_reason`;
* **on what basis** → the same agenda payload, with `source_summary` showing which sources
  contributed and which rows could not be attributed;
* **why the next item changes** → `why_the_next_read_changes` (the facts the agenda re-reads)
  and `completion_paths` (what makes each kind of item disappear), plus
  `explanation_of_order` stating that the order is the fixed ladder and no model decides it.

---

## 8. FEEDBACK_ANALYTICS

`GET /ai/feedback/analytics?scope=mine|platform&window_days=N` — read-only aggregation over the
ratings P4 collects: totals, `down_rate`, per-reason counts, and buckets by capability, model,
provider and workflow, each with latency and credit sums, plus a per-capability/model view for
Champion/Challenger work.

* **`scope=mine`** (default) is the caller's own ratings.
* **`scope=platform`** is **admin-only** (the product's existing `is_admin_user` gate) and
  **aggregated only**: no user id, no request id, no per-learner row — asserted.
* **It never trains or tunes the router**: `router_mutation: false`, and a test asserts the
  live selection AND the availability signal are identical before and after ratings, including
  three dislikes in a row.
* `GET /ai/feedback/availability` (admin-only) exposes the Router V1 availability state **with
  its scope stated** — see §9.

---

## 9. PRODUCTION_TOPOLOGY & ROUTER_HEALTH_PERSISTENCE_DECISION

**Finding (from the deployment artifacts, not from theory):**

* `deploy` starts and restarts ONE systemd service, `ai-backend`, and the workflow only writes
  drop-in files under `ai-backend.service.d/` — there is no `--workers` anywhere;
* nginx proxies to a SINGLE address (`proxy_pass http://127.0.0.1:8000/`, no upstream block);
* the backend already depends on in-process state for correctness of OTHER features — the
  Docker execution semaphore (`threading.Semaphore(2)`) and the per-minute code-run rate
  limiter — which only bound anything if there is one process.

The base `ai-backend.service` unit is created on the server and is NOT in the repository, so
the run command cannot be read from source. What CAN be stated is the above, and the
consequence:

**Decision: KEEP the process-local availability state** — it is exact for this topology — and
make the assumption VISIBLE instead of implicit:

* `ai.health.describe()` states `scope: "process_local"` and
  `deployment_requirement: "single_backend_process"` at runtime;
* `GET /ai/feedback/availability` (admin-only) exposes it, so an operator can see the scope and
  the currently degraded models;
* the report records the residual uncertainty (a `--workers N` base unit would invalidate it)
  with the minimal remedy if that ever changes: a shared availability store keyed by
  (provider, model) — and NOT Redis, which this project does not use.

---

## 10. REVIEW_STORAGE_DECISION

**Question**: with schedules in the event stream (wrong answers / programming) and in real
columns (knowledge), does the existing projection recover, paginate, query by due and update
correctly?

**Answer, from five tests that use a SEPARATE database session (what a restart sees):**

| requirement | result |
|---|---|
| recover after a restart | YES — a fresh session reads the same due, policy version and reason |
| paginate stably | YES — pages repeat identically and every item is reachable |
| query by due | YES — `status=due` / `status=scheduled` find the items the schedule decides |
| update correctly | YES — the newest schedule wins for an item, and completing a review updates BOTH the knowledge row and the projection |

**Decision: KEEP the event-sourced V1 — no migration.** The only defect found was in the
projection itself (the bucket filter ran before schedules were attached, so `status=due` could
not see an item whose schedule had just made it due); fixed and certified. A `ReviewSchedule`
table would add schema without adding a capability the projection does not already have.

---

## 11. EVENTS / OBSERVABILITY

* **No new event family was added.** An agenda read is a plain projection: it writes nothing,
  emits nothing, and a test asserts exactly that. `daily_agenda_generated` was deliberately NOT
  created — it would be event count without a fact (§I).
* One behaviour was corrected in the same spirit: the adaptive source no longer emits
  `adaptive_practice_selected` when the agenda consumes it as an input (`emit_event=False`).
  A selection fact belongs to the surface the learner asked for; a projection that wrote one on
  every read would be noise.
* ONE FACT ONE OWNER is unchanged: plan tasks, review items and practice attempts keep their
  existing owners, and the agenda only reads them.
* The P4 observability contract (one `ai_requests` row + one `ai_called` fact per model call)
  is untouched by P5; the analytics layer reads the audit stream and writes nothing.

---

## 12. TESTS

**19 new tests**, all green:

* `test_p5_agenda.py` (10): determinism; the priority ladder is factual; repeated wrongs rank
  above single wrongs; three spaces coexist and stay isolated; own-agenda-only; completing the
  real action changes the next read; one question is never listed twice; no prediction-shaped
  field; the explain endpoint answers why; an agenda read writes nothing.
* `test_p5_feedback_analytics.py` (4): aggregation correctness + owner scoping; platform scope
  is admin-only and aggregated; the audit semantics are preserved (and analytics adds no
  event); nothing moves the router.
* `test_p5_review_persistence.py` (5): restart recovery; stable pagination; due querying;
  newest schedule wins; completion updates row and projection together.

---

## 13. FULL_SUITE

```
./.venv/Scripts/python.exe -m pytest -q          (backend/, TEMP DATABASE_URL)
1723 passed, 2 skipped, 0 failed in 654.11s (0:10:54)
```

This is the single certification for the whole chain — P1.3 + P3B + P4 + P5 — over the frozen
tree, with `backend/app.db` byte-identical before and after (see §14). Two earlier runs of the
same suite are recorded honestly in §2 and in the P4 report: both failed ONE test, the adaptive
exam/programming candidate test from P4, and chasing it to green uncovered three real defects in
the candidate scan (module filter applied after a bounded window; oldest-first scan; ascending
sort inside the no-signal group) that only a shared, full-suite database could expose. Each was
reproduced against the full-suite ordering before being fixed, and this run is the proof.

## 14. MAIN DB PROTECTION

```
MAIN_DB_TOUCHED = NO
```

```
MAIN_DB_SHA_BEFORE = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER  = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SIZE       = 64917504 bytes (before and after)
MAIN_DB_MTIME      = 1789877022 (2026-09-20 12:03:42.878312700 +0800, before and after)
```

`backend/app.db` SHA256 `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522`,
size 64917504, mtime 1789877022 — unchanged at the last check before the suite.
No `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
`push` / `commit` / `deploy`. No frontend file was touched by this session. No migration.

---

## 15. FRONTEND READINESS

```
AGENDA_FRONTEND_READY    = YES
FEEDBACK_ANALYTICS_READY = YES (admin surface; needs an admin-only screen or a CLI call)
```

* **Agenda** — typed (`AgendaResponse` + `AgendaItemView`): a home page can render the list with
  each item's reason, due date and facts, and link through `deep_link`. The client must NOT
  cache "completed" locally: the item disappears because its own fact changed, and re-reading is
  how the UI learns that. `resolved_by` tells the client where the real action happens.
* **Explain** — `GET /learning/agenda/explain` is ready for a "为什么推荐这个？" panel.
* **Feedback analytics** — typed and admin-gated; a normal learner never sees the platform view.
  `GET /ai/feedback/availability` is the ops view of Router V1 availability.

---

## 16. BLOCKERS

1. **The deployment topology could not be fully verified from the repository**: the base
   `ai-backend.service` unit lives on the server. The evidence (single service, single nginx
   upstream, other in-process state the product already depends on) supports one process, and
   the decision above is made on that basis — with `describe()` making the assumption
   checkable. If the server unit ever runs multiple workers, availability must become shared.
2. **P4's per-process availability limitation is now documented and visible, not fixed** (see
   §9) — the correct scope for a single-process deployment.
3. **Review schedules for wrong answers / programming items remain in the event stream** (§10:
   verified adequate). A first-class table is NOT proposed.
4. **The agenda's practice source needs an engagement signal and a space scope**: a course
   recommendation requires `course_id`, an exam one requires `exam_module_id`. A caller that
   omits them still gets plan and review items (they come from their own rows) but no practice
   suggestions.
5. **Feedback analytics reads the audit stream**, so its history is bounded by what P4 has
   collected since deployment; there is no backfill for ratings made before the feature.
6. **Carried forward from earlier phases**: the agent's per-step trace has no dedicated table
   (P3A), the wrong-analysis text has no owned store (P3B), `report.generate` is Advanced-only
   (P3B) — all unchanged, all documented where they were introduced.
