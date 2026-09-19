# FRONTEND_F1C6A — CS408 Learning Record Contract Audit

Date: 2026-09-19.
Mode: fast contract audit. **No frontend UI, no schema, no event-tracking redesign.**
Nothing was implemented.

Baseline: `1180 passed / 0 failed`. Migration head: `20260919_0009`.

Everything below was measured — models, writers, readers and the frozen taxonomy read from
source, and every candidate store exercised against a **TEMP copy** of the real database with a
real authenticated session and real business actions.

```text
FRONTEND_F1C6A_COMPLETE
CANONICAL_LEARNING_RECORD_OWNER = learning_events, read through GET /learning-records
F1C6_FRONTEND_READY = NO
REAL_APP_DB_MUTATED = NO
```

---

## 1. Record systems found (9)

| # | Store | Role | Identity | Timestamp | User-facing? | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `learning_events` (data_plane) | **the canonical event stream** | `event_id` UUIDv5 | `occurred_at` UTC epoch float | **YES — this is F1C6's owner** | **CANONICAL** |
| 2 | `learning_records` (legacy) | course Q&A / 复盘 notebook (question, answer, tags, review_status) | int `id` | `created_at` naive | own course screens only | **LEGACY** — and it shares F1C6's URL prefix (§3) |
| 3 | `practice_attempts` + `practice_sessions` (STEP 7D) | the durable fact *behind* practice events | int `id` / `attempt_uid` | `submitted_at` | no (timeline comes from events) | source of record, not a timeline |
| 4 | `exam_practice_attempts` / `past_paper_attempts` | legacy exam session summaries; mirrored into #3 | int `id` | `submitted_at` | no | legacy source |
| 5 | `knowledge_progress_events` | legacy delta ledger behind a knowledge change | int `id` | `created_at` naive | no | source of `knowledge_status_changed` |
| 6 | `user_knowledge_progress` | current knowledge state | int `id` | `updated_at` | no | state, not history |
| 7 | `wrong_answer_states` (STEP 7E) | canonical wrong **projection** | int `id` | `first/last_wrong_at` | no | projection, **no timeline** |
| 8 | `exam_study_plan_tasks` / `exam_study_plan_chapter_practice` | plan state (status is derived) | int `id` | `created_at`/`updated_at` | no | state, **no events at all** |
| 9 | `ai_requests` / `ai_cost_records` / `usage_ledger` | accounting and audit | string uuid | `created_at` | **no** | AUDIT ONLY |

## 2. Canonical owner

```text
CANONICAL_LEARNING_RECORD_OWNER = learning_events (data_plane.LearningEvent),
                                  read as a projection through GET /learning-records
```

A canonical owner **already exists** and is well built: a frozen taxonomy
(`learning/records/taxonomy.py`), one authoritative producer per fact, a privacy-guarded
envelope, a safe serializer, and cursor pagination. F1C6 must not aggregate heterogeneous
tables in the frontend — it does not have to.

**But it is not ready as a CS408 records timeline yet**, for five specific reasons (§7–§11).

One deployment fact: `learning_events` does **not exist** in the real `backend/app.db` — the
whole Phase data-plane schema arrives only with `alembic upgrade head`, which has never been
applied there. So production has **zero** learning records today; the surface is empty by
construction, not by lack of use.

## 3. Two systems share `/learning-records`

The URL prefix F1C6 would naturally use is **contested**, and one legacy route is dead:

```
canonical (routers/learning_records.py, registered first)
  GET    /learning-records                 list          <- F1C6's owner
  GET    /learning-records/summary         summary
  GET    /learning-records/taxonomy        taxonomy reference
  GET    /learning-records/{event_id}      detail        (event_id = UUID string)
legacy (main.py, registered later)
  POST   /learning-records                 create a course notebook record
  GET    /learning-records/stats           SHADOWED
  POST   /learning-records/{record_id}/reviewed
  PATCH  /learning-records/{record_id}     (record_id = INTEGER — a different id space)
  DELETE /learning-records/{record_id}
```

Measured against the running server:

```
GET /learning-records/stats  ->  404 {"detail":"record not found"}
```

That is the **canonical** handler's error, not the legacy stats payload: `GET
/learning-records/{event_id}` is registered first and swallows `stats` as an event id. The
legacy stats endpoint is unreachable. Two integer/UUID id spaces also coexist under one
prefix, so a frontend holding "a record id" cannot tell which system it belongs to.

## 4. Event taxonomy — the actual current classification

From the frozen `TAXONOMY` (7 ACTIVE, 4 DEFERRED, no UNKNOWN types):

```text
USER_FACING_EVENT_TYPES =
  question_answered          PracticeEvent     course + exam   one factual objective attempt
  course_practice            PracticeEvent     course          the frozen StudentTwin family
  code_submitted             ProgrammingEvent  programming     one judged submission
  knowledge_status_changed   KnowledgeEvent    any             a real learner status transition
  material_opened            MaterialEvent     any             deduped per (user, material, UTC day)
  material_asked             MaterialEvent     any             the learner asked about a material

AUDIT_ONLY_EVENT_TYPES =
  ai_called                  AIEvent           any             accounting/ops: one terminal AI request

INTERNAL_PROJECTION_EVENT_TYPES =
  (none emitted.) wrong_answer_resolved, plan_created, task_completed, review_completed are
  DEFERRED — reserved names with NO producer. Nothing is synthesized for them.
```

### AI audit events are not study history

```text
AI_AUDIT_EVENT_USER_FACING = NO
```

`ai_called` exists for accounting and operations. Its own taxonomy entry says "No prompt, no
response, no model cost detail beyond a coarse class", and the envelope enforces it. It is a
well-behaved audit event.

**But nothing excludes it from the user-facing surface today.** Measured, a real AI call
produced a record that the records API returned alongside genuine study facts:

```
2026-09-19T06:46:06Z  ai_called  cat=AIEvent  ns=exam_prep
   ctx={"exam_module_id":"operating_system","subject_key":"cs_408"}
   summary={"capability":"question.explain","status":"succeeded"}
   source={"type":"ai_request","id":"probe-req-1","item_key":"question.explain"}
```

A learner opening 学习记录 would see "AI 调用 / question.explain / succeeded". That is an ops
fact, not a learning record, and it is the single most important normalization F1C6 needs: the
read surface must exclude `ai_called` (or serve it behind an explicit opt-in), not rely on the
frontend to filter it out.

### What the surface does *not* leak

Credit where it is due — the record view is genuinely sanitized (§21):

```
event_id + event_type + record_category + service_namespace + occurred_at + schema_version
context  { knowledge_point_id?, exam_module_id?, course_id?, subject_key? }
source   { type, id, item_key }        <- a REFERENCE to the domain table
summary  small, per-event-type factual metadata
```

No prompt, no response, no answer text, no source code, no provider/model routing beyond a
coarse capability name, no request body, no filesystem path, no budget numbers.
`envelope.assert_payload_is_safe` actively REJECTS payloads carrying those fields.

## 5. Attempts

```text
PRACTICE_RECORDS  = YES — question_answered, one per factual attempt
PAST_PAPER_RECORDS = YES — same event type, distinguished by summary.question_source_type
```

Real sequence from the probe (chapter practice, one answered-and-wrong objective question):

```
question_answered  cat=PracticeEvent  ns=exam_prep
  ctx={"exam_module_id":"operating_system","subject_key":"cs_408"}
  summary={"correct": false, "question_source_type":"static_question_bank",
           "question_source_id":"7234"}
  source={"type":"exam_practice_attempt","id":"1","item_key":"7234:0"}
```

Module ✓, attempt reference ✓, factual `correct` tri-state ✓, question reference ✓. No score
or mastery is invented by the surface. This is exactly the shape F1C6 wants.

Two honest caveats:

* **There is no "session/attempt" record — there is one record per question.** A 12-question
  sitting produces 12 timeline rows. That is truthful (each item is a real fact) but the
  frontend cannot render "一次练习" without grouping, and grouping needs an attempt identity
  the record does carry only as `source.id` + `source.type`.
* **An unanswered past-paper item still produces a record** with `correct: null` and
  `score: 0.0`. The `null` is correct (BC7's 未作答 ≠ 答错). The `0.0` is not: read alone it
  says "scored zero" for a question the learner never answered. A records UI could show
  "0 分" for a blank. Worth tightening, not a blocker.

## 6. Knowledge, wrong answers, plan

```text
KNOWLEDGE_RECORDS = YES — knowledge_status_changed, with old_status → new_status
WRONG_RECORDS     = NO
PLAN_RECORDS      = NO
```

* **Knowledge** is real: `{"new_status":"mastered","old_status":"not_started"}` with
  `context.knowledge_point_id`. A genuine learner transition, not an LLM-inferred mastery claim.
* **Wrong answers produce no timeline.** `wrong_answer_resolved` is DEFERRED by design —
  `WrongAnswerState` is a projection rebuilt from practice facts, so a per-recompute event
  would be pure duplication. There is not even a `wrong_answer_created`. 错题 in a records
  timeline must be derived from `question_answered` records with `correct === false` (which is
  honest), not from a wrong-answer event.
* **Plan produces nothing.** `plan_created` / `task_completed` are DEFERRED. This is correct
  and consistent with BC8: plan status is *derived*, so there is no "task completed" moment the
  backend could honestly stamp. Measured: creating a plan task emitted **0** events.

## 7. Record identity

```text
RECORD_IDENTITY = event_id — a UUIDv5 over (source_type, source_attempt_id, source_item_key)
```

Stable, server-owned, deterministic, and identical between the live emitter and backfill (so a
replayed fact can never become a second record). Never an array index, never a title. The
legacy `learning_records` integer id is a **different id space under the same prefix** (§3).

## 8. Module context — present per record, but not filterable

```text
MODULE_CONTEXT = PARTIAL
  present : every exam record carries context.exam_module_id (data_structure /
            computer_organization / operating_system / computer_network)
  missing : there is NO module filter on the read endpoint
```

Measured — the endpoint accepts these query parameters and nothing else:

```
start_at · end_at · service_namespace · category · event_type · limit · cursor
```

```
GET /learning-records?module=operating_system   ->  200, 16 records (ALL of them)
```

The unknown parameter is **silently ignored** — it returned the same 16 records as the
unfiltered call, including a `course_learning` record whose context is `null`. So:

```text
RECORD_MODULE_CROSS_LEAK = NOT_GUARDED
```

A module-scoped `/exam/cs408/records` cannot be served by this endpoint as it stands. Filtering
client-side would show other modules' records and, worse, produce under-full pages — the next
cursor would already have skipped the filtered-out rows. **This is the second closure item.**

## 9. Timestamps — and a real defect

```text
CANONICAL_TIMESTAMP = occurred_at (UTC epoch float; emitted as ISO-8601 with +00:00)
TIMEZONE_SEMANTICS  = UTC on the read side, DEFECTIVE on the practice write path
DATE_GROUPING_READY = NO
```

The read side is careful: `service._to_epoch` documents "a naive input is read as UTC, never as
server local time". The **write** side does not match it. `learning/practice/events.py:112`:

```python
occurred = (attempt.submitted_at.timestamp()
            if attempt.submitted_at is not None else time.time())
```

`submitted_at` comes back from SQLite as a **naive** datetime holding a UTC wall-clock, and
`naive.timestamp()` interprets it as **local time**. On this machine (UTC+8) every
practice-derived record is stamped **8 hours early**. Measured on one run:

```
knowledge_status_changed  occurred_at = 1789800360   (now, correct)
question_answered         occurred_at = 1789771560   (now − 28806s = now − 8h)
```

Both facts happened in the same second. The knowledge producer passes an aware datetime and is
correct; material producers pass `None` → `time.time()` and are correct; only the practice
bridge is wrong.

Three consequences, all of which hit F1C6 directly:

1. **Wrong calendar day.** Any action by a UTC+8 learner between 00:00 and 08:00 local is filed
   under the previous day. A date-grouped timeline would put it on the wrong date.
2. **Machine-dependent.** On a UTC host the bug is invisible; on a UTC+8 host it is 8 hours.
   The same learner data means different things on different deployments.
3. **Cross-family ordering is corrupted.** Practice records are shifted relative to knowledge
   and AI records, so "what did I do first" is wrong whenever the two interleave within 8 hours.

That is why `DATE_GROUPING_READY = NO`: date grouping is only legitimate once one clock is real.

## 10. Pagination, filters, sort

```text
PAGINATION = cursor-based (occurred_at + event_id tie-break); limit default 50, max 200;
             returns {records, next_cursor, has_more}; NO total count
FILTERS    = start_at · end_at (UTC) · service_namespace · category · event_type
             (no module, no source-type, no free-text)
DEFAULT_SORT = occurred_at DESC, event_id DESC   (newest first, deterministic)
```

Measured: `limit=5` → 5 rows + `has_more: true` + a cursor; the next page returned 5 with
**zero overlap**; `limit=500` → 422 (bounded); `cursor=nope` → 400. The list is properly
bounded — this is a real production-grade pagination contract.

Two gaps: **no `total`** (a UI cannot show "共 N 条" without walking pages), and
`GET /learning-records/summary` is **unbounded** — it does `q.all()` over every event for the
user with no window and no limit. Summary is optional for F1C6, but if it is used it must be
bounded or windowed.

## 11. Ownership

```
user A : 16 records      user B : 0 records
A GET own event   -> 200 | B GET A's event id -> 404 | anonymous -> 401
```

Every handler filters by the session user; the detail route matches `(event_id, user_id)`, so a
known id is not a capability.

```text
CROSS_USER_RECORD_ACCESS = 0
```

## 12. Source context and deep links

```text
SOURCE_CONTEXT = PARTIAL — derivable honestly, but not as a ready-made label
  knowledge_status_changed                            -> 知识学习        READY
  question_answered + summary.question_source_type
      = static_question_bank                          -> 章节练习        READY
      = past_exam                                     -> 历年真题        READY
      = AI_generated                                  -> AI 出题         READY
  错题                                                -> NOT A RECORD TYPE
  学习计划                                            -> NOT A RECORD TYPE
```

The raw `source_type` string is **not** exposed as a label — only as `source.type`, a machine
reference — so the frontend would map `question_source_type` → a Chinese label itself. That is
presentation, not inference, and it is honest; but a backend-supplied label would be better
(§13 of the brief).

| deep link | verdict | why |
| --- | --- | --- |
| knowledge event → Knowledge | **READY** | `context.knowledge_point_id` + `context.exam_module_id` |
| practice attempt → Practice | **READY** | `source.id` (attempt) + `summary.question_source_id` + module |
| past-paper attempt → Past Papers | **PARTIAL** | module + question number are carried, **year is not** — the past-paper route needs `(module, year, question_number)` |
| wrong event → Wrong Answers | **BLOCKED** | no wrong records exist |
| plan event → Plan | **BLOCKED** | no plan records exist |

## 13. OpenAPI

```text
RECORD_REQUIRED_REQUEST_UNKNOWN = 0    (all inputs are typed Query params)
RECORD_REQUIRED_SUCCESS_UNKNOWN = 2    (list + detail both return {} -> unknown)
```

Measured: every one of the four `GET /learning-records*` operations declares a `200` whose
schema is `{}` — the generated client sees `unknown` for the list, the detail, the summary and
the taxonomy. The *shape* is real and stable (`_safe_view`); only its declaration is missing.

Counting rule: the minimum F1C6 flow needs **list + detail**. `summary` (analytics, and
unbounded) and `taxonomy` (a developer reference) are not part of the minimum, and are reported
separately rather than typed to make a number look better.

## 14. Minimum F1C6 product

| | capability | verdict | why |
| --- | --- | --- | --- |
| A | chronological list | **PARTIAL** | works and is newest-first, but the response is untyped and mixes AI audit rows into study history |
| B | pagination | **READY** | cursor, bounded, deterministic, no overlap |
| C | module filter | **BLOCKED** | no server-side module filter; `?module=` is silently ignored |
| D | record / source type | **PARTIAL** | `event_type` + `category` + `summary.question_source_type` exist; but AI audit rows are not separated and 错题/学习计划 have no type |
| E | factual timestamp | **PARTIAL** | present and UTC on the wire, but practice records are shifted by the local offset |
| F | brief context / summary | **READY** | per-type factual summary, no invented metrics |
| G | deep link | **PARTIAL** | Knowledge + Practice ready; Past Papers lacks the year; Wrong + Plan have no records |
| H | date grouping | **BLOCKED** | follows from E — the clock is not yet trustworthy |
| I | attempt records | **READY** | one record per factual item, with attempt reference |
| J | knowledge records | **READY** | real status transitions only |
| K | wrong records | **BLOCKED** | no wrong event type; derivable from `correct === false` records instead |
| L | plan records | **BLOCKED** | no plan events, by design |

## 15. Final decision

```text
F1C6_FRONTEND_READY = NO
```

The owner exists and is well built — this is **not** a case of needing to merge heterogeneous
stores in the browser. It is a small, specific normalization. **Recommend a small BC9:**

1. **Exclude `ai_called` from the user-facing record list** (or gate it behind an explicit
   audit category the frontend never requests by default). Without this the timeline shows the
   learner ops telemetry.
2. **Add a module filter** (`exam_module_id`) server-side, applied before pagination, so a
   module-scoped page is correct and pages stay full.
3. **Fix the practice timestamp** — a naive `submitted_at` must be treated as UTC
   (`submitted_at.replace(tzinfo=timezone.utc)`), matching what `service._to_epoch` already
   documents on the read side. Until then date grouping is not truthful.
4. **Type the list and detail responses** (`RecordView`), plus the cursor/page envelope. Do
   this *after* 1–3 so the type freezes correct behaviour.
5. **Resolve the `/learning-records` prefix collision** — the legacy `GET
   /learning-records/stats` is currently unreachable and two id spaces share one prefix.
6. Minor, optional: carry the past-paper `year` for a complete public identity; add a `total`;
   stop emitting `score: 0.0` for an unanswered item.

**Not required and not recommended:** a wrong-answer event type, a plan event type, study-time
estimates, streaks, heatmaps, or AI summaries. Wrong and plan are honestly absent, and F1C6 is a
factual history first.

## 16. Real database safety

```
SHA256   1c1b2d85…3fe522   unchanged
size     64917504          unchanged
mtime    2026-09-16 21:24:23 unchanged
tables   72                unchanged      integrity_check = ok
learning_events in the real app.db : TABLE ABSENT (arrives only via alembic upgrade head)
```

All probes ran against `.f1c6tmp/temp.db`; the real file was opened `?mode=ro` only.

```text
REAL_APP_DB_MUTATED = NO
```

## What was NOT done (per §24)

No study-time estimates, no AI summaries, no mastery trends, no readiness scores, no heatmaps,
no streaks, no productivity scores. No UI. No schema, no migration, no event redesign. The
`ai_called` event used for the §26 probe was produced through the **real producer**
(`learning.records.producers.emit_ai_called`) against the TEMP DB — no provider was called and
no credits were spent.

---

```text
FRONTEND_F1C6A_COMPLETE

CANONICAL_LEARNING_RECORD_OWNER = learning_events (data_plane.LearningEvent), read as a
                                  projection through GET /learning-records

RECORD_SYSTEMS =
- 1. learning_events               CANONICAL event stream (owner)
- 2. learning_records  (legacy)    course Q&A notebook; shares the /learning-records prefix
- 3. practice_attempts / sessions  durable fact behind practice events
- 4. exam_practice_attempts / past_paper_attempts  legacy session summaries
- 5. knowledge_progress_events     delta ledger behind knowledge events
- 6. user_knowledge_progress       current state, not history
- 7. wrong_answer_states           projection, no timeline
- 8. exam_study_plan_tasks / chapter_practice  state, no events at all
- 9. ai_requests / ai_cost_records / usage_ledger  accounting

AI_AUDIT_EVENT_USER_FACING = NO   (and currently NOT excluded — the closure item)

USER_FACING_EVENT_TYPES        = question_answered · course_practice · code_submitted ·
                                 knowledge_status_changed · material_opened · material_asked
AUDIT_ONLY_EVENT_TYPES         = ai_called
INTERNAL_PROJECTION_EVENT_TYPES = none emitted (wrong_answer_resolved / plan_created /
                                 task_completed / review_completed are DEFERRED, no producer)

RECORD_IDENTITY = event_id (UUIDv5 over source_type + source_attempt_id + source_item_key)
MODULE_CONTEXT  = PARTIAL — context.exam_module_id on every exam record; NO server module filter
SOURCE_CONTEXT  = PARTIAL — 知识学习 / 章节练习 / 历年真题 / AI 出题 derivable;
                            错题 and 学习计划 have no record type

CANONICAL_TIMESTAMP = occurred_at (UTC epoch → ISO-8601 +00:00)
TIMEZONE_SEMANTICS  = UTC-correct on the READ side; DEFECTIVE on the practice WRITE path
                      (naive submitted_at.timestamp() = local-time inference, 8h shift on UTC+8)
DATE_GROUPING_READY = NO (follows from the write-side defect)

RECORD_LIST_ENDPOINT = GET /learning-records
PAGINATION = cursor (occurred_at + event_id), limit 50 default / 200 max, has_more + next_cursor,
             NO total; /learning-records/summary is unbounded
FILTERS    = start_at · end_at · service_namespace · category · event_type
             (no module, no source type)
DEFAULT_SORT = occurred_at DESC, event_id DESC

KNOWLEDGE_RECORDS  = YES      PRACTICE_RECORDS = YES     PAST_PAPER_RECORDS = YES
WRONG_RECORDS      = NO       PLAN_RECORDS     = NO

KNOWLEDGE_DEEP_LINK  = READY
PRACTICE_DEEP_LINK   = READY
PAST_PAPER_DEEP_LINK = PARTIAL (year not carried)
WRONG_DEEP_LINK      = BLOCKED (no wrong records)
PLAN_DEEP_LINK       = BLOCKED (no plan records)

CROSS_USER_RECORD_ACCESS = 0

RECORD_REQUIRED_REQUEST_UNKNOWN = 0
RECORD_REQUIRED_SUCCESS_UNKNOWN = 2   (list + detail; summary/taxonomy reported separately)

MINIMUM_F1C6_CAPABILITIES =
A chronological list = PARTIAL · B pagination = READY · C module filter = BLOCKED
D source type = PARTIAL · E timestamp = PARTIAL · F context = READY · G deep link = PARTIAL
H date grouping = BLOCKED · I attempts = READY · J knowledge = READY
K wrong = BLOCKED · L plan = BLOCKED

F1C6_FRONTEND_READY = NO
BLOCKERS =
  1. AI audit rows (ai_called) are served in the user-facing record list
  2. no server-side module filter (?module= is silently ignored)
  3. practice-derived records are timestamped by local-time inference (wrong day on UTC+8)
  4. list and detail responses are untyped (200 {})
  5. the /learning-records prefix is shared by two systems with two id spaces, and the legacy
     GET /learning-records/stats route is unreachable (shadowed by /{event_id})
  → recommend a small BC9; the owner, the identity, the taxonomy and the pagination are sound

REAL_APP_DB_MUTATED = NO
```
