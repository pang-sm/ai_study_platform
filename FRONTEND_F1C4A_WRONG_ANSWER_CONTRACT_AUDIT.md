# FRONTEND_F1C4A — CS408 Wrong-Answer Workspace Contract Audit

Date: 2026-09-19.
Mode: fast contract audit. No frontend UI, no backend redesign, no schema/migration change.

```text
FRONTEND_F1C4A_COMPLETE
F1C4_FRONTEND_READY = NO
BLOCKERS = semantics differ between the served legacy stores and the canonical unified store,
           and correct-retry resolution cannot be represented on the surface F1C4 would consume
REAL_APP_DB_MUTATED = NO
```

Everything below was measured: models and handlers read from source, all six endpoints generated
into OpenAPI, and every write path exercised against a **TEMP copy** of the real database served on
port **8956** with a real `POST /login` session.

---

## 1. Wrong-answer stores found (3)

| # | Table | Model | Role |
| --- | --- | --- | --- |
| 1 | `exam_wrong_questions` | `models.ExamWrongQuestion` (`models.py:1013`) | legacy chapter practice (+ AI-generated questions) |
| 2 | `past_paper_wrong_questions` | `models.PastPaperWrongQuestion` (`models.py:863`) | legacy past papers |
| 3 | `wrong_answer_states` | `learning.wrong_answers.models.WrongAnswerState` | **canonical unified store (STEP 7E)** |

| | 1. exam_wrong_questions | 2. past_paper_wrong_questions | 3. wrong_answer_states |
| --- | --- | --- | --- |
| writer | chapter-practice submit (choice branch) | past-paper submit | `learning.practice.service.record_attempt` → `wrong_answers.project.project_attempt` |
| reader | `GET /exam/11408/{subject}/wrong-questions` | same endpoint | `GET /wrong-answers`, `GET /wrong-answers/{id}` |
| namespace | none | none | `service_namespace` = `exam_prep` |
| question identity | `question_bank_id` (int → `ExamQuestionBank.id`) | `question_id` (**string**: bank id or document id) + `year` + `question_number` | `question_source_type` + `question_source_id` + `question_scope_key` |
| snapshots | `stem_snapshot`, `options_snapshot_json`, `standard_answer_snapshot`, `analysis_snapshot` | `content`, `options`, `standard_answer` (**no analysis**) | **none** — detail reads the live facts |
| status | `active` / `removed` | `active` / `mastered` | `active` / `resolved` |
| mastered flag | yes | yes | `legacy_mastered` only |
| review count | `review_count` | **absent** | `wrong_count` (fact-derived) |
| timestamps | created/updated/resolved_at | created/updated/resolved_at/reviewed_at | first_wrong_at / last_wrong_at / resolved_at |
| resolution semantics | **none factual** — manual only | **none factual** — manual only | **factual**: a later correct attempt resolves it |

The unified model documents its own contract in `learning/wrong_answers/models.py`:

> "Review-ish columns from the legacy tables (`mastered`, `review_count`, `reviewed_at`) are carried
> as LEGACY COMPATIBILITY METADATA. They are not a review system, and they never override the
> correctness of a newer factual attempt."

## 2. Canonical owner

```
CANONICAL_WRONG_RECORD_OWNER = wrong_answer_states (WrongAnswerState) — architectural authority
ACTUALLY_SERVED_TO_F1C4_CANDIDATE = the two legacy tables, via
                                    GET /exam/11408/{subject_key}/wrong-questions
```

Both are live and both are written by the same submit. They are **not** two views of one fact — they
disagree after a correct retry (§7). A frontend cannot merge them without inventing semantics, and
§33 forbids that in the frontend.

## 3. Write path matrix

Measured on the TEMP copy; store counts printed after each step.

| Path | Creates wrong? | Dedup? | review_count | Resolves? |
| --- | --- | --- | --- | --- |
| **A. chapter incorrect choice** | YES — both stores | YES legacy (by `question_bank_id`, `status='active'`); unified by identity | legacy `+1` on repeat | legacy **no**; unified YES |
| **A2. chapter repeat wrong** | updates the existing legacy row | ✅ | `0 → 1` | legacy **no**; unified `wrong_count 1 → 2` |
| **A3. chapter blank (unanswered) choice** | **YES — both stores** ⚠ | n/a | — | — |
| **B. chapter big / self-review** | **NO** — `correct=None` never counts as a factual failure | — | — | — |
| **C. past-paper incorrect objective** | YES — both stores, **one record per question per submit, no dedup** ⚠ | ❌ | no column | legacy **no**; unified YES |
| **C2. past-paper blank questions** | **YES** — all 10 choice questions of the paper, 9 of them with `user_answer=''` ⚠ | ❌ | — | — |
| **D. past-paper repeat** | duplicates every wrong record (10 → 20 on the second submit) ⚠ | ❌ | — | — |
| **E. past-paper self-review big** | **NO** | — | — | — |

Raw evidence:

```
A  chapter blank   submit=200 correct=0 wrong=1 mistake_saved=1
     exam_wrong_questions rows: [(4895, user_answer='', '章节练习答错')]
     wrong_answer_states      : [('4895','active',1)]
B  chapter big     submit=200 big_count=1 mistake_saved=0
     stores unchanged in all three tables
C  past paper      submit=200 choice_correct=0 choice_total=10
     pp rows (qn, user_answer): [(23,'A'),(24,''),(25,''),(26,''),(27,''),(28,''),(29,''),(30,''),(31,''),(32,'')]
D  same paper again -> past_paper_wrong_questions 10 -> 20 (identical rows)
E  correct retry    -> pp q23 rows [(1,23,'A','active'),(11,23,'A','active')]   (still active, still duplicated)
```

Two facts here are product-level, not cosmetic:

* **Unanswered questions enter the wrong book.** A blank choice grades `"" == "D"` as `False`, and
  the wrong book records it with `user_answer=''`. This contradicts the summary semantic already
  frozen in F1C2D (blank = 未作答, not 答错). It affects both stores and both graded paths.
* **Past-paper wrong records are never deduped.** Re-sitting a paper duplicates every wrong question,
  so the list grows linearly with attempts.

```text
CHAPTER_PRACTICE_WRONG_WRITE = creates (choice, incl. blank) · dedups · increments review_count
PAST_PAPER_WRONG_WRITE       = creates (choice, incl. blank) · NO dedup · no review_count
SELF_REVIEW_WRONG_WRITE      = none (chapter big and past-paper self-review never enter any store)
```

## 4. Identity

```
WRONG_RECORD_IDENTITY       = per-store surrogate `id`
   exam_wrong_questions.id           (int)
   past_paper_wrong_questions.id     (int)
   wrong_answer_states.id            (int)
   -> NOT unique across stores: id=1 exists in all three. The exam list merges two tables and
      returns a bare `id`, so a client id is ambiguous by construction.
UNDERLYING_QUESTION_IDENTITY = chapter: ExamQuestionBank.id (`question_bank_id`)
                              past paper: `question_id` string + (year, question_number)
                              unified: (question_source_type, question_source_id, question_scope_key)
```

The past-paper row carries the string `question_id` (bank id or document id) **and** the normalized
`year` + `question_number`, so a frontend can build the BC6 public identity without touching the
internal id. The unified store's `question_source_id` is the raw internal id.

## 5. Endpoint matrix

| # | Method | Path | Auth | Request | Response | Typed | Side effects |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GET | `/exam/11408/{subject_key}/wrong-questions` | session | query `source`, `mastered` | `{items[], total}` — legacy rows merged | **untyped `{}`** | none |
| 2 | DELETE | `.../wrong-questions/{wrong_id}` | session | — | `{success, table}` | **untyped** | **hard delete** on past-paper, **soft `status='removed'`** on chapter |
| 3 | PATCH | `.../wrong-questions/{wrong_id}/mastered` | session | raw dict | `{success, mastered}` | **untyped** | sets `mastered` + `status='mastered'` |
| 4 | GET | `/wrong-answers` | session | query `service_namespace`, `status`, `limit`, `offset` | `{states[]}` — canonical | **untyped `{}`** | none |
| 5 | GET | `/wrong-answers/{state_id}` | session | — | state + question + answers + history | **untyped `{}`** | none |
| 6 | PATCH | `/wrong-answers/{state_id}` | session | `StateUpdate{resolved}` | state view | request typed, response **untyped** | sets status/resolved_at |

There is **no dedicated detail endpoint** for the legacy exam surface — the list payload is all a
client gets.

## 6. List contract — fields actually present

Legacy exam list, per item:

```
past_paper branch: id · username · subject_key · source='past_paper' · source_label='真题错题' ·
                   year · question_id · question_number · question_type · stem · options ·
                   standard_answer · user_answer · score · wrong_reason · attempt_id ·
                   status · mastered · resolved_at · created_at · updated_at
chapter branch   : id · username · subject_key · source=practice_type · source_label · ·
                   knowledge_point_id/name/path · question_id(=question_bank_id) · question_type ·
                   stem · options · standard_answer · user_answer · score · wrong_reason ·
                   attempt_id · status · mastered · review_count · created_at · updated_at
```

Present and usable: `id`, module (`subject_key`), source kind (`source_label`, already Chinese),
stem snapshot, `question_type`, `user_answer`, `standard_answer`, `status`, `mastered`,
`created_at`/`updated_at`, chapter context (`knowledge_point_*`), past-paper context (`year`,
`question_number`).

Missing: **any image/resource reference**; `question_number`/`year` on the chapter branch (null);
`analysis` on the past-paper branch (the column does not exist); a stable cross-store id.

## 7. CORRECT RETRY RESOLUTION — the decisive finding

Same question, same user, wrong then correct:

```
exam_wrong_questions : [(4895, status='active',   review_count=0)]   <- unchanged
wrong_answer_states  : [('4895', status='resolved', wrong_count=1)]  <- resolved
```

`project.derive_from_attempts` is unambiguous:

```python
wrongs = [a for a in ordered if a.correct is False]
rights = [a for a in ordered if a.correct is True]
last_wrong = wrongs[-1]
later_correct = [a for a in rights if _chrono_key(a) > _chrono_key(last_wrong)]
status = STATUS_RESOLVED if later_correct else STATUS_ACTIVE
```

So the **canonical** store resolves on a later correct attempt, and a later wrong reopens it.
The **legacy** store, which is what F1C4 would read, is never resolved by anything factual — a
correct retry leaves the row `active` forever.

```text
CORRECT_RETRY_RESOLUTION = PARTIAL
   wrong_answer_states (canonical)   : GUARANTEED
   exam_wrong_questions / past_paper : NO
```

## 8. Status semantics

| Store | Value | Meaning |
| --- | --- | --- |
| exam_wrong_questions | `active` | listed by the endpoint (`status == 'active'` filter) |
| | `removed` | soft-deleted by `DELETE` on the chapter branch |
| past_paper_wrong_questions | `active` | default; **not** filtered by the list query |
| | `mastered` | written by `PATCH …/mastered` |
| both legacy | `mastered` (bool) | manual learner assertion; never cleared by a correct retry |
| wrong_answer_states | `active` | last factual attempt was wrong |
| | `resolved` | a later factual attempt was correct (`resolved_attempt_id` set) |

`resolved` in the canonical store genuinely means "answered correctly later". `mastered` in the
legacy store is a hand-set flag with no factual backing. The two must not be rendered with the same
Chinese label — the legacy one is not evidence.

```text
REVIEW_COUNT_SEMANTICS = exam_wrong_questions.review_count increments ONLY when the same question
                         is answered wrong again (verified 0 -> 1 on a repeat wrong). It is not
                         view count, not retry count, not a review system; it is a misnamed
                         repeat-wrong counter. past_paper_wrong_questions has no such column.
STATUS_SEMANTICS       = legacy: active/removed/mastered (manual) · canonical: active/resolved (factual)
```

## 9. Manual resolution

| Action | Endpoint | Semantics |
| --- | --- | --- |
| mark mastered / unmastered | `PATCH …/wrong-questions/{id}/mastered` | legacy compatibility; sets `mastered` + `status='mastered'` |
| delete | `DELETE …/wrong-questions/{id}` | **hard delete** on past-paper, **soft (`removed`)** on chapter |
| resolved toggle | `PATCH /wrong-answers/{id}` | `service.set_status` — documented as "a compatibility action, not learning evidence: it records what the learner asserted. A later factual incorrect attempt reopens the state" |

So manual resolution exists on both surfaces, but only the canonical one has defined interaction with
facts. `MANUAL_RESOLUTION = AVAILABLE (legacy toggle/delete; canonical resolved toggle)` — and the
legacy `DELETE` is destructive, which §24 warns against exposing casually.

## 10. Snapshot vs live question

```
legacy chapter  : SNAPSHOT — stem/options/standard_answer/analysis stored on the row
legacy past     : SNAPSHOT — content/options/standard_answer stored (no analysis)
canonical       : LIVE — state_detail() reads
                  question / user_answer / correct_answer / error_analysis from the practice facts
                  via attempts_for_question(); only context_json is a stored snapshot
```

```text
SNAPSHOT_BEHAVIOR = PARTIAL — legacy snapshots are historically stable but carry no analysis on the
                    past-paper side; the canonical store holds no snapshot at all and would lose
                    intelligibility if a source question changed.
```

## 11. Module safety, filters, sort, pagination

```
WRONG_MODULE_SCOPE = PASS
   GET /exam/11408/data_structure/wrong-questions -> total=1
   GET /exam/11408/operating_system/wrong-questions -> total=29
   (subject_key is a path segment and a WHERE clause on both branches)
```

| Filter | Legacy exam list | Canonical unified |
| --- | --- | --- |
| module (`subject_key`) | **READY** (path, mandatory) | **NOT_SUPPORTED** (only `service_namespace`) |
| source kind | READY (`source=past_paper,chapter,ai_generated,…`, comma-separated) | NOT_SUPPORTED |
| status | partial (`mastered=true/false` only; no active/resolved filter) | **READY** (`status`) |
| year | NOT_SUPPORTED | NOT_SUPPORTED |
| chapter / knowledge point | NOT_SUPPORTED | NOT_SUPPORTED |
| pagination | **NOT_SUPPORTED** — `limit` is ignored, `total` unchanged | **READY** (`limit` capped at 500, `offset`) |
| sort | `created_at desc` (merged in Python) | `last_wrong_at DESC NULLS LAST, id DESC` |

```text
SERVER_FILTERS = module + source + mastered (legacy) · namespace + status (canonical)
PAGINATION     = NONE on the module-scoped legacy list; limit/offset on the canonical list
DEFAULT_SORT   = legacy: created_at desc · canonical: last_wrong_at desc, id desc
```

Real data today: the real `app.db` holds **0** wrong records in every store, so size is not yet a
problem — but the past-paper duplication means an active paper-sitting user grows the list by 10
rows per attempt with no cap.

## 12. Security

```
anon GET /exam/11408/{subject}/wrong-questions -> 401
anon GET /wrong-answers                        -> 401
anon GET /wrong-answers/{id}                   -> 401
CROSS_USER_WRONG_RECORD_ACCESS = 0   (every handler filters by the session user; nothing is
                                          reachable by id alone)
```

The wrong book is post-attempt by construction, so exposing `standard_answer` here is legitimate —
and it is only reachable for the caller's own rows. No `question_id → answer` disclosure path exists:
the endpoints never take a bare question id.

## 13. Images

```
IMAGE_RESOURCE_CONTRACT = NONE — neither the legacy list payload nor the canonical state carries any
                          resource/image reference. A figure question in the wrong book renders its
                          stem text only.
```

The frontend already owns the correct helper — `resolveApiResourceUrl()` in
`frontend/src/lib/api/client.ts:14`, unit-tested in `client.test.ts` — so F1C4 must reuse it and must
**not** invent a second URL system. It simply has nothing to point it at until the wrong-book payload
carries resource references.

## 14. Deep links and re-do

```
CHAPTER_DEEP_LINK    = READY    — knowledge_point_path + knowledge_point_id + question_bank_id are
                                  all present; the chapter practice desk takes explicit question_ids.
PAST_PAPER_DEEP_LINK = READY    — year + question_number are present, which is exactly the BC6 public
                                  identity the past-paper route consumes
                                  (/exam/cs408/past-papers?module=&year=).
```

| Re-do capability | Verdict |
| --- | --- |
| `REDO_CHAPTER_WRONG` | **READY** — `POST …/chapter-practice/attempts` accepts explicit `question_ids` (proven in F1C2D's 重练本次错题) |
| `REDO_PAST_PAPER_WRONG` | **PARTIAL** — `POST …/past-paper-attempts` takes only `year`; it creates a whole-paper attempt, with no subset parameter |
| `CROSS_SOURCE_RETRY` | **INVALID** — one attempt cannot mix chapter-practice questions and past-paper questions: they are different attempt subsystems (`ExamPracticeAttempt` vs `PastPaperAttempt`) with different id spaces. A “重练全部” across both sources is not expressible. |

## 15. OpenAPI

```
WRONG_REQUIRED_REQUEST_UNKNOWN = 1 / 1   (PATCH …/wrong-questions/{id}/mastered takes a raw dict)
WRONG_REQUIRED_SUCCESS_UNKNOWN = 6 / 6   (every wrong-answer endpoint returns `{}`)
```

| Endpoint | Response schema |
| --- | --- |
| `GET /exam/11408/{subject_key}/wrong-questions` | `{}` |
| `DELETE …/wrong-questions/{wrong_id}` | `{}` |
| `PATCH …/wrong-questions/{wrong_id}/mastered` | `{}` (+ raw-dict request) |
| `GET /wrong-answers` | `{}` |
| `GET /wrong-answers/{state_id}` | `{}` |
| `PATCH /wrong-answers/{state_id}` | `{}` (request is typed `StateUpdate`) |

Nothing was tightened: typing a surface whose semantics are still split would only make the split
type-safe.

## 16. Minimum F1C4 capability classification

| | Capability | Verdict | Why |
| --- | --- | --- | --- |
| A | wrong list | **PARTIAL** | works and merges both sources, but untagged types, no pagination, ambiguous `id` |
| B | module filter | **READY** | `subject_key` path segment, verified isolated |
| C | source label | **READY** | `source_label` is already user-facing Chinese |
| D | question preview | **READY** | stem snapshot present on both branches |
| E | answer / reference | **READY** | `user_answer` + `standard_answer` snapshots present |
| F | status | **BLOCKED** | legacy status is manual only and never reflects a correct retry |
| G | detail | **PARTIAL** | no dedicated detail endpoint; the list row is all there is |
| H | image / resource | **BLOCKED** | no resource reference anywhere in the payload |
| I | correct-retry resolution | **BLOCKED** | the served store never resolves; only the unserved canonical store does |
| J | manual resolve | **PARTIAL** | endpoints exist but are compatibility semantics; `DELETE` is destructive on past papers |
| K | deep link | **READY** | both sources carry enough stable context |
| L | re-do wrong question | **PARTIAL** | chapter READY; past paper can only re-sit the whole paper |

## 17. Real database safety

| Measure | Value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to baseline |
| size / mtime | `64917504` / `2026-09-16 21:24:23` — identical |
| `integrity_check` | `ok` |
| table count | 72 |
| protected counts | `exam_question_bank` 9333, `programming_exercises` 1923, `knowledge_points` 32 |
| `exam_wrong_questions` / `past_paper_wrong_questions` | 0 / 0 |
| `wrong_answer_states` | **table absent** |

All write probes ran against `%TEMP%\f1c4a\vqa.db`; the real file was only ever opened `?mode=ro`.

```text
REAL_APP_DB_MUTATED = NO
```

### Deployment observation (not a blocker, but it changes the picture)

`wrong_answer_states` **does not exist in the checked-in `app.db`**. It is created at import by
`Base.metadata.create_all` (`main.py:353`) — starting the app against a copy produced 86 tables
versus the real file's 72. Its Alembic revision (`20260915_0004`) is also unapplied. So the canonical
store has **no production history yet**: every wrong record that exists anywhere today (none) is
legacy, and the canonical table will start empty on the next deploy.

---

# Final decision

Per §33, the condition for a small typing-only BC7 does **not** hold: this is not a case of missing
types over one coherent contract. There are two live stores, the one F1C4 would read has no factual
resolution, and the canonical one has no module filter, no snapshots and no resource references.
Making the frontend merge them would be inventing product semantics in the UI.

```text
CANONICAL_WRONG_RECORD_OWNER = wrong_answer_states (canonical) / legacy tables (served today)
WRONG_RECORD_IDENTITY        = per-store surrogate id (NOT unique across the two merged stores)
UNDERLYING_QUESTION_IDENTITY = chapter: ExamQuestionBank.id · past paper: question_number + year
                               (normalized) · canonical: (source_type, source_id, scope_key)

WRONG_STORES_FOUND =
  1. exam_wrong_questions        (legacy chapter, snapshots, review_count, dedup)
  2. past_paper_wrong_questions  (legacy past papers, snapshots, no review_count, NO dedup)
  3. wrong_answer_states         (canonical unified, fact-derived, no snapshots)

WRONG_LIST_ENDPOINT   = GET /exam/11408/{subject_key}/wrong-questions   (auth, untyped, no paging)
WRONG_DETAIL_ENDPOINT = GET /wrong-answers/{state_id}                   (auth, untyped; the legacy
                        module-scoped surface has NO detail endpoint)

CHAPTER_PRACTICE_WRONG_WRITE = creates (choice, incl. blank) · dedups · review_count++
PAST_PAPER_WRONG_WRITE       = creates (choice, incl. blank) · NO dedup · no review_count
SELF_REVIEW_WRONG_WRITE      = none, on every path

MODULE_SCOPE       = PASS
SOURCE_CONTEXT     = source_label ready (真题错题 / 章节练习错题 / AI 出题错题); module from subject_key;
                     chapter via knowledge_point_*; past paper via year + question_number
SNAPSHOT_BEHAVIOR  = legacy yes (past paper lacks analysis) · canonical no (reads live facts)

STATUS_SEMANTICS       = legacy active/removed/mastered(manual) · canonical active/resolved(factual)
REVIEW_COUNT_SEMANTICS = repeat-wrong counter on the chapter legacy table only; not views, not retries

CORRECT_RETRY_RESOLUTION = PARTIAL (canonical GUARANTEED · served legacy NONE)
MANUAL_RESOLUTION        = AVAILABLE (legacy mastered toggle + destructive delete · canonical toggle)

CROSS_USER_WRONG_RECORD_ACCESS = 0

IMAGE_RESOURCE_CONTRACT = NONE — no resource reference is transported; resolveApiResourceUrl() exists
                          and must be reused, but has nothing to resolve yet

SERVER_FILTERS = module + source + mastered (legacy) · namespace + status + limit/offset (canonical)
PAGINATION     = NONE on the module-scoped legacy list · READY on the canonical list
DEFAULT_SORT   = legacy created_at desc · canonical last_wrong_at desc, id desc

CHAPTER_DEEP_LINK    = READY
PAST_PAPER_DEEP_LINK = READY

REDO_CHAPTER_WRONG    = READY (chapter attempt takes explicit question_ids)
REDO_PAST_PAPER_WRONG = PARTIAL (past-paper attempt takes only `year`; no subset)
CROSS_SOURCE_RETRY    = INVALID (two attempt subsystems; a mixed attempt is not expressible)

WRONG_REQUIRED_REQUEST_UNKNOWN = 1
WRONG_REQUIRED_SUCCESS_UNKNOWN = 6

MINIMUM_F1C4_CAPABILITIES =
  A list = PARTIAL   B module filter = READY   C source label = READY   D preview = READY
  E answer/reference = READY   F status = BLOCKED   G detail = PARTIAL   H image = BLOCKED
  I correct-retry resolution = BLOCKED   J manual resolve = PARTIAL   K deep link = READY
  L redo = PARTIAL

F1C4_FRONTEND_READY = NO

BLOCKERS =
  1. SPLIT AUTHORITY — the module-scoped list F1C4 would consume serves two legacy tables while the
     canonical store (wrong_answer_states) is written in parallel and disagrees with them.
  2. CORRECT_RETRY_RESOLUTION — the served store never marks a retried-correct wrong as resolved, so
     F1C4 cannot honestly show 已订正 / 未订正.
  3. UNANSWERED → WRONG — blank choices are written into the wrong book on both graded paths
     (`user_answer=''`), contradicting the frozen 未作答 ≠ 答错 semantic.
  4. NO DEDUP ON PAST PAPERS — re-sitting a paper duplicates every wrong record.
  5. NO RESOURCE REFERENCE — figure questions in the wrong book cannot render their diagram.
  6. UNTYPED — all six endpoints return `{}`.

REAL_APP_DB_MUTATED = NO
```

## What a BC7 closure would need to provide

One typed, module-scoped read over the **canonical** store, carrying enough display data for F1C4
without the frontend merging anything:

1. module (`subject_key`) and source kind on the canonical row, or a normalized projection that adds
   them;
2. the display facts the canonical list lacks today (stem, user answer, reference answer, question
   type) resolved from the facts at read time;
3. `status` exposed with its factual meaning (`active` / `resolved`), plus the resolving attempt;
4. resource references for figure questions, emitting the same API-base-relative URL contract BC6
   established;
5. typed request/response models, and pagination on the module-scoped list;
6. a decision on unanswered questions — they currently enter the wrong book.

## Not done (per §30)

No spaced-repetition scheduler, no AI wrong-answer summary, no misconception diagnosis, no mastery
score, no automatic study plan, no recommendation engine. Nothing was implemented, and no
schema/migration was added.
