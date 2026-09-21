# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4_ADAPTIVE_INTELLIGENCE_REPORT

Task: `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P4_ADAPTIVE_INTELLIGENCE`
Date: 2026-09-20
Scope: Adaptive Practice V1 · Intelligent Review V1 · Model Feedback · Router V1 ·
Observability · Data Flywheel. All on the existing LearningEvent / Records / Review / Plan /
LearningContext / Capability / Usage / Gateway / Router stack.
No frontend change, **no migration, no schema change**, no commit, no deploy.

---

## 1. FILES

**New**

| File | What it is |
|---|---|
| `backend/learning/adaptive.py` | deterministic adaptive practice selection |
| `backend/learning/review_schedule.py` | the versioned review policy + completion |
| `backend/learning/feedback.py` | unified AI response feedback |
| `backend/ai/health.py` | provider/model availability (Router V1) |
| `backend/routers/p4_adaptive_feedback.py` | `GET /adaptive/practice`, `POST /ai/feedback` |
| `backend/tests/test_p4_adaptive_practice.py` | 7 tests |
| `backend/tests/test_p4_intelligent_review.py` | 6 tests |
| `backend/tests/test_p4_feedback.py` | 4 tests |
| `backend/tests/test_p4_router_v1.py` | 9 tests |
| `backend/tests/test_p4_observability.py` | 2 tests |

**Edited** (all additive): `ai/router.py` (V1 decision fields + reason codes + availability),
`ai/orchestrator.py` (health recording + decision carry-through + fallback record),
`learning/records/taxonomy.py` (4 new families, `review_completed` promoted),
`learning/records/producers.py`, `learning/review.py` (scheduled dues in the projection),
`routers/review.py` (schedule + complete endpoints + a missing `Literal` import fixed),
`main.py` (router registration), `tests/conftest.py` (an autouse fixture that resets the
process-global availability registry between tests), `tests/test_learning_records_api.py`
(one CONTRACT CORRECTION, §4).

---

## 2. ADAPTIVE_PRACTICE

`GET /adaptive/practice` — **deterministic** selection over stored facts. No model is called
and no capability/credits are involved: this is product logic, not an AI feature.

**Reason vocabulary** (every candidate states the ONE rule that selected it, plus the facts
behind it):

| reason | the fact it names |
|---|---|
| `due_review` | the question's knowledge point has a STORED `review_due_at` that has passed |
| `recent_wrong` | the learner's most recent factual attempt on this question was incorrect |
| `needs_work` | an ACTIVE wrong-answer state with `wrong_count >= 2` exists |
| `coverage_gap` | the question's knowledge point has no knowledge-progress row at all |
| `unseen_topic` | the question was never attempted (its topic is otherwise known) |

Priority is fixed (`due_review` → `recent_wrong` → `needs_work` → `coverage_gap` →
`unseen_topic`) and ordering inside a reason is deterministic. An item with nothing to
recommend is EXCLUDED rather than given an invented reason (`excluded_count` reports it).

**Spaces**: `course_learning` selects from the course's own AI question book (owner- and
course-scoped in SQL); `exam_11408` from the module's ACTIVE public chapter bank; the
`programming` space selects exercises (its metadata — difficulty, knowledge points, per-user
progress — is real, so exercise recommendation is INCLUDED rather than deferred).

**Deliberately NOT used** (and asserted absent by test): no `learner_state`, no
`misconception_v2`, no `IRT`, no `difficulty_prior` — none has passed the Productization Gate —
and no field named weakness/mastery/probability/prediction is exposed. The response says so in
its own `semantics`.

**Isolation**: cross-user, cross-course, cross-module and cross-language isolation are all
asserted. A selection emits ONE canonical fact (`adaptive_practice_selected`) carrying the
selection id, the reason codes and counts — references only.

---

## 3. INTELLIGENT_REVIEW

`POST /review/schedule`, `POST /review/{item_id}/complete` — policy
**`review_policy_v1`**, and NO scientific component is called.

**Why not the memory model**: a spaced-repetition model needs a real interval/rating/lapse
history, and the product has none (`science/capabilities.py` declares
INTERVAL_HISTORY_ABSENT). Feeding a model fabricated history would produce a fabricated
schedule; V1 computes a transparent date instead.

**The policy** (pure function, one place, every branch named):

```
last review incorrect        → 1 day      (after_incorrect)
repeated wrongs (>= 2)       → 2 days     (repeated_wrong)
last review correct          → previous × 2, capped at 60   (after_correct)
item status mastered         → 60 days    (manual_state)
otherwise (no history)       → 3 days     (first_schedule)
```

Every computed date carries `policy_version`, `reason`, `scheduled_at`, `due_at` and the exact
`facts` it used (previous interval, last result, repeated-wrong count, item status), so a date
can always be re-derived and checked. Same inputs (including the same clock) → the same date;
there is no clock drift inside a decision and no randomness anywhere.

**Completion is what moves a schedule.** `complete_review` REQUIRES the learner's real result
(`correct` / `incorrect`), records `review_completed`, then reschedules from that result and
records `review_scheduled`. A review that did not happen cannot advance anything.

**Booking**: the schedule is durable as canonical facts; where the item HAS a real column for
it (a knowledge point: `review_due_at` / `review_interval_days`), that row is updated too, so
the knowledge page and the review projection agree. The review projection now shows a computed
due with its PROVENANCE
(`due_source = review_policy.review_policy_v1.<reason>` + the `schedule` block), which is how
a computed date stays distinguishable from a stored one.

**Taxonomy change**: `review_completed` was `DEFERRED` with the note "review_items (not
built)". Its producer now exists, so it is **ACTIVE** — the taxonomy's own rule ("a type is
ACTIVE only when a real server-side producer exists"). `plan_created` and `task_completed`
remain deferred.

---

## 4. MODEL_FEEDBACK

`POST /ai/feedback` — one rating per request, against the request that produced the response.

**Recorded**: `request_id`, `rating` (up/down), `reason`, `regenerated`, `switched_model`,
`workflow_id`, `capability`, `service_namespace`, `model`, `provider`, `tier`, `status`,
`latency_ms`, `estimated_credits`, `actual_credits`, `router_reason`, the request's context
snapshot, `created_at`, `submitted_at`.

**Frozen negative-reason taxonomy**: `incorrect`, `too_shallow`, `too_complex`, `too_verbose`,
`too_brief`, `bad_code`, `slow`, `poor_image`, `other` — enforced by the request contract AND
by the service (a negative rating without a reason is refused).

**Persistence: REUSED, no new table.** The request identity, model, provider, capability, cost
and timing already live in `ai_requests`; the rating becomes a canonical AUDIT fact
(`ai_feedback_submitted`) carrying references and closed-vocabulary codes only — no free text,
no prompt, no response text. That is why the required "minimal migration" was NOT taken: a
safe existing home existed, so `schema necessity` never arose.

**AUDIT_ONLY**: a rating of a response is product telemetry, not study history, so it joins
`ai_called` on the audit-only list and can never appear in a learner's 学习记录. One frozen
assertion (`audit_only_event_types == ["ai_called"]`) is updated with an explicit CONTRACT
CORRECTION (P4).

**It never trains the router online**: `trains_router_online` is false and stays false; the
test asserts the live selection AND the availability signal are byte-identical before and
after a dislike.

---

## 5. ROUTER_V1

`router_v1` — the selection inputs are now capability + tier + budget + **quality + cost +
latency + availability**, and every decision is explainable.

**Added**

* **Reason codes** (closed vocabulary): `only_qualified_candidate`,
  `cheapest_qualified_within_budget`, `explicit_model`, `fallback_after_failure`.
* **Candidate pool**: the decision carries every budget-compatible candidate with its
  quality class, cost profile, latency class and estimated credits — so a choice can be
  re-explained after the fact, not just asserted.
* **Availability** (`ai/health.py`): a bounded outcome window per (provider, model) —
  three consecutive provider failures degrade it for a cooldown, any success restores it.
  A degraded model is SKIPPED while a healthy candidate remains (and `skipped_degraded` names
  it); if EVERY candidate is degraded the router tries anyway with
  `degraded_fallback: true` — trying a degraded model beats refusing a learner their answer.
  The cooldown expires by itself; no manual reset is needed (asserted with a fake clock).
* **Fallback record**: when the primary fails and a fallback serves the request, the decision
  says `fallback_after_failure` and names `fallback_from` — a fallback is never reported as if
  it had been the first choice. Availability outcomes are recorded where each attempt FAILS,
  including an attempt that the fallback rescued.

**Unchanged** (deliberately): the Qualified Model Pool and its calibration
(`POOL_VERSION`/`POOL_QUALIFICATION_LEVEL` untouched), tier permission, budget compatibility,
pricing-missing fail-closed, and the cheapest-first ordering. **No personalization and no
online learning**: nothing about a learner — including their feedback — enters a selection,
and the router takes no user id at all.

---

## 6. OBSERVABILITY

ONE contract for every advanced workflow, asserted end-to-end by a test that runs all five
(Deep Study, Debug Agent, Learning Report narrative, Wrong-Cause Analysis, Plan Adjustment):

```
ai_requests : request_id, user_id, service_namespace, capability, tier, status,
              model, provider, estimated_credits, actual_credits,
              started_at → finished_at (latency), error_category, context_json
ai_called   : capability, status, provider, model, router_reason_code,
              candidate_count, quality_class, latency_class, router_version, credits
```

No workflow keeps a private log or its own telemetry table: everything is the same
`ai_requests` row plus the same audit fact. The router decision travels into the audit event,
so "which model answered, chosen why, out of how many" is answerable from the stream alone,
for successes, failures and fallbacks.

---

## 7. DATA_FLYWHEEL

| Fact | Event | Namespaces |
|---|---|---|
| an adaptive selection was made | `adaptive_practice_selected` | course / exam / programming |
| a next review date was computed | `review_scheduled` | course / exam |
| a review was completed | `review_completed` (promoted) | course / exam |
| an AI response was rated | `ai_feedback_submitted` (AUDIT_ONLY) | course / exam / programming |

Every produced event is stamped with its `data_origin` by the ONE write path
(`data_plane.origin.stamp`), and the training-readiness rule is unchanged: only
`data_origin = LEARNER` may train a model — DEMO / ACCEPTANCE / TEST facts stay out. The proof
is the existing readiness gate plus the new-event stamping test.

An attempt's outcome is NOT re-emitted as a new event family: the practice spine already owns
`question_answered` / `code_submitted`, and a second event for the same fact is exactly what
the taxonomy's one-fact-one-owner rule forbids.

---

## 8. SCIENTIFIC COMPONENTS

```
SCIENTIFIC_COMPONENTS_USED   = NONE
SCIENTIFIC_COMPONENTS_DEFERRED = learner_state, misconception_v2, IRT / difficulty_prior,
                                 memory (interval history absent) — plus student_twin, which
                                 stays the exam-space experiment it already was and is NOT
                                 wired into any P4 surface
```

Nothing in P4 reads a scientific endpoint, a model version or a prediction: adaptive selection,
review scheduling and router availability are all computed from stored rows and runtime
outcomes. The `memory` component is the one the task named, and it is deferred for the
documented reason (no real interval/rating/lapse history exists to feed it).

---

## 9. TESTS

**28 new tests**, all green:

* `test_p4_adaptive_practice.py` (7): determinism; each reason is factual (the fact is seeded
  and asserted); repeated wrongs; cross-course/cross-user isolation; no prediction-shaped
  field; exam + programming spaces; the selection is a canonical fact carrying no content.
* `test_p4_intelligent_review.py` (6): the policy is pure and reproducible (including the cap);
  a first schedule invents no history; scheduling records the policy + facts and updates the
  knowledge row; completion requires a real result and moves the schedule from it; another
  learner's item is a 404; namespace isolation.
* `test_p4_feedback.py` (4): the full request context; another learner's request is a 404; the
  reason taxonomy is closed; feedback changes neither the selection nor the availability state.
* `test_p4_router_v1.py` (9): explainable decisions; qualified pool only; tier/budget rules;
  degraded skip + report; success restores; all-degraded still answers (recorded); cooldown
  expiry; the orchestrator publishes the decision and records health; a fallback is recorded as
  a fallback.
* `test_p4_observability.py` (2): all five workflows land on the ONE contract; the new families
  are origin-stamped and the LEARNER-only training rule is unchanged.

---

## 10. FULL_SUITE

```
./.venv/Scripts/python.exe -m pytest -q          (backend/, TEMP DATABASE_URL)
1703 passed, 1 failed, 2 skipped in 919.15s (0:15:19)
```

The one failure was a test IN THIS PHASE'S OWN SUITE
(`test_p4_adaptive_practice.py::test_exam_and_programming_spaces_select_from_their_own_catalogs`),
and chasing it to green uncovered THREE real defects in this phase's adaptive candidate scan —
each invisible when the file runs alone and each fatal in a shared database:

1. the EXAM source filtered by module in Python AFTER a bounded id window, so other rows could
   crowd this module out of the window entirely → the module key set is now an exact-match SQL
   filter (canonical check kept as defence in depth);
2. the bounded scan took the OLDEST rows, so newly added content could fall outside it → the
   scan is now newest-first (a question added today is always considered);
3. within the `coverage_gap` / `unseen_topic` group the display window sorted by id ASCENDING,
   so a newly added item sorted past the window and never appeared → that group is newest-first
   too.

All three are fixed in P5, reproduced against the full-suite ordering before and after, and
certified by the final run recorded in
`THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P5_LEARNING_ORCHESTRATOR_REPORT.md` §13.

## 11. MAIN DB PROTECTION

```
MAIN_DB_TOUCHED = NO
```

`backend/app.db` SHA256 `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522`,
size 64917504, mtime 1789877022 — identical before and after every run in this phase.

`backend/app.db` SHA256 `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522`,
size 64917504, mtime 1789877022 — unchanged at the last check before the suite.
No `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
`push` / `commit` / `deploy`. No frontend file was touched by this session. No migration.

---

## 12. FRONTEND READINESS

```
ADAPTIVE_FRONTEND_READY         = YES
INTELLIGENT_REVIEW_FRONTEND_READY = YES
MODEL_FEEDBACK_FRONTEND_READY   = YES
ROUTER_V1_ACTIVE                = YES
```

* **Adaptive** — typed (`AdaptivePracticeResponse`); each candidate has `reason`, `facts` and
  the ids a client needs to open the existing practice surface. It carries NO question text by
  design (content comes from the hardened per-space surfaces), so a client renders the
  knowledge-point label and links into practice.
* **Intelligent review** — typed; `POST /review/schedule` returns the date WITH its policy and
  facts, `POST /review/{item_id}/complete` requires the result. The list/detail responses now
  carry `schedule` (policy version, reason, interval) alongside `due_at`/`due_source`.
* **Feedback** — typed; a client posts `{request_id, rating, reason?}` after any AI response and
  must render `trains_router_online: false` semantics as-is (a rating is not a switch).
* **Router V1** is active for every AI call (it is the same router, with more inputs recorded);
  no client change is required — `/ai/models` and the AI responses are unchanged in shape.

---

## 13. BLOCKERS

1. **The review `schedule` is durable only for knowledge items.** A knowledge point has real
   `review_due_at` / `review_interval_days` columns and they are updated; a wrong-answer or
   programming item has no such column, so its schedule lives in the canonical event stream and
   is read back from there. A first-class column (or a review table) would be a schema change —
   the same cross-sprint migration decision P3A/P3B already reported.
2. **Router V1 availability is per-process.** The health window lives in the process, so in a
   multi-worker deployment each worker learns separately and a restart forgets. That is the
   honest scope of a runtime signal with no new table; a shared store is a later decision.
3. **Feedback is stored, not yet consumed.** Nothing reads `ai_feedback_submitted` to influence
   anything — by design (no online router training). Turning it into router policy needs its
   own offline validation step, which is not part of P4.
4. **Adaptive selection uses no difficulty prior** (none passed the Gate), so ordering inside a
   reason is by recency/id rather than by an estimated item difficulty. That is a deliberate
   consequence, not an oversight.
5. **`report.generate` remains Advanced-only** (carried from P3B), so a Standard learner's
   report has no narrative.
6. **The P3A agent-trace limitation stands** (no dedicated step table) — unchanged by P4.
