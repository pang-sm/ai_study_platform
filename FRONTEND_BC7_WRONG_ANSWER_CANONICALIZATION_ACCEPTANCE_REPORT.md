# FRONTEND_BC7 — CS408 Wrong-Answer Canonicalization

Date: 2026-09-19.
Mode: backend architecture closure, fast-track. **No F1C4 UI was implemented.**

Regression baseline taken from BC6 (`FRONTEND_BC6_PAST_PAPER_PRODUCT_CONTRACT_ACCEPTANCE_REPORT.md`):
**1126 passed / 0 failed**. Every number below was measured, not inferred.

```text
FRONTEND_BC7_COMPLETE
CANONICAL_WRONG_RECORD_OWNER = wrong_answer_states (WrongAnswerState)
REAL_APP_DB_MUTATED = NO
F1C4_FRONTEND_READY = YES
```

---

## 1. The previous dual-store conflict

F1C4A proved the two truths and named the divergence. BC7 closed it by measurement, not by
argument. Everything in this section is a restatement of the F1C4A audit that BC7 had to
answer:

| | served legacy list | canonical store |
| --- | --- | --- |
| reader | `GET /exam/11408/{subject}/wrong-questions` | `GET /wrong-answers` |
| tables | `exam_wrong_questions` + `past_paper_wrong_questions` | `wrong_answer_states` |
| factual resolution | **none** — a correct retry left the row `active` forever | a later correct attempt resolves it |
| blank answer | entered the book (`user_answer=''`) | mirrored the same wrong fact |
| past-paper dedup | **none** — re-sitting duplicated every wrong row | identity-keyed |
| status | manual `active` / `removed` / `mastered` | factual `active` / `resolved` |

The decisive fact: **the write path was wrong, not the read path.** A blank choice graded
`"" == "D"` as `False`, so the wrong answer was *factual* — the projector was faithfully
projecting a lie. Filtering blanks out of a response would have hidden it while leaving the
stored fact corrupt. BC7 fixed the fact.

Frontend regressions that would have been needed under the old contract (merge two stores,
dedupe rows, derive resolution, compare answers) are now **not needed and not permitted**.

## 2. Canonical owner decision

`wrong_answer_states` is the canonical persisted product projection of factual attempts.
It was not chosen because of its name — it was audited against every property §3 requires:

| requirement | support |
| --- | --- |
| chapter-practice identity | `question_source_type=static_question_bank` + `question_source_id` = `exam_question_bank.id` (globally unique) + empty scope |
| normalized past-paper identity | `question_source_type=past_exam` + `question_scope_key = subject:cs_408\|module:<m>\|year:<y>` |
| user / module scoping | `user_id`; **module was NOT first-class** → added (§3) |
| active / resolved state | `status` ∈ {`active`, `resolved`}, factual |
| answer snapshots | `practice_attempts.answer` + `result_json.standard_answer` (factual); legacy `context_json` |
| deterministic upsert key | `uq_wrong_answer_state_identity` (user × namespace × source type × source id × scope) |
| repeat-wrong metadata | `wrong_count` = distinct factual incorrect attempts |

One gap was real: **the module was not a queryable column.** For a past-exam row it was
buried inside `question_scope_key`; for a chapter row the scope is deliberately empty, so
there was nothing to parse at all. A module-scoped read therefore could not be an indexed
`WHERE`. That is what the migration adds — nothing else.

```text
CANONICAL_WRONG_RECORD_OWNER = wrong_answer_states (WrongAnswerState)

WRONG_STORES_FOUND =
  1. exam_wrong_questions        (legacy chapter/AI, compatibility only)
  2. past_paper_wrong_questions  (legacy past papers, compatibility only)
  3. wrong_answer_states         (canonical; the ONLY product truth for F1C4)
```

## 3. Migration

```text
MIGRATION_BEFORE = 20260917_0008
MIGRATION_AFTER  = 20260919_0009     (add module_key to wrong_answer_states)
```

`migrations/versions/20260919_0009_wrong_answer_module_key.py` — one additive column plus
one index, guarded on inspection so a partially-applied deployment is a no-op:

```
ALTER TABLE wrong_answer_states ADD COLUMN module_key VARCHAR(50) NOT NULL DEFAULT ''
CREATE INDEX ix_wrong_answer_states_user_ns_module (user_id, service_namespace, module_key)
```

`module_key` is deliberately **not** added to `uq_wrong_answer_state_identity`:
uniqueness is already enforced there, and SQLite cannot alter a constraint without
rebuilding the table — which this project forbids. Adding it would be a rebuild for no
behavioural gain. It is a *filter* dimension, not an *identity* dimension.

**Why a real migration was justified.** `wrong_answer_states` is created by revision
`20260915_0004`, but the deployed `backend/app.db` has **no `alembic_version` table at
all** — no revision has ever been applied to it. The table only existed at runtime because
`Base.metadata.create_all` built it at import. That is incidental schema, not managed
schema. `0009` is the first revision that has to *modify* the canonical table, so it also
pins the property that matters: the canonical wrong-answer schema comes from Alembic.

Measured on a TEMP copy of the real 72-table legacy database (read-only source):

```
alembic upgrade head  ->  20260917_0008 -> 20260919_0009        rc=0
head                          = 20260919_0009
tables                        = 72 -> 86   (the chain's own new tables)
wrong_answer_states present   = True
module_key present            = True
exam_question_bank            = 9333 -> 9333   (byte-identical content)
PRAGMA integrity_check        = ok
```

## 4. Historical backfill

`learning/wrong_answers/legacy.py` was rewritten from a row-by-row copy into a grouped
import. Three things were wrong with the old one:

1. it copied blank rows straight into the canonical state;
2. it appended a canonical row per legacy row, so a duplicated past-paper question became a
   duplicated canonical state (the unique key silently absorbed it, but only because the
   upsert key happened to match);
3. it carried no module.

The new import groups by the canonical question identity, skips blank rows, collapses
duplicates, and derives the state chronologically.

**BACKFILL_SOURCE = factual `practice_attempts` first; the legacy wrong tables are a bounded
fallback for questions that have no facts at all.** Where facts exist the facts decide the
status and the count and the legacy row is demoted to `legacy_*` compatibility metadata
(`origin = legacy_merged`). Where no facts exist, the legacy rows decide — ordered
chronologically, the LAST record sets `active` / `resolved`, `first_wrong_at` and
`last_wrong_at` bracket the history, and `wrong_count` is the number of collapsed legacy
records, never the misnamed `review_count`.

Measured on a TEMP copy of the real legacy schema with pollution injected (real rows are
all zero — see §17):

```
LEGACY_CHAPTER_WRONG_ROWS        = 4    (2 real, 2 blank)
LEGACY_PAST_PAPER_WRONG_ROWS     = 6    (2 duplicates, 3 blank, 1 mastered)
LEGACY_BLANK_WRONG_ROWS          = 5
LEGACY_DUPLICATE_WRONG_ROWS      = 7    (raw duplicate rows in the legacy tables)
CANONICAL_DUPLICATE_ROWS_COLLAPSED = 2  (blanks excluded first, then collapsed)
CANONICAL_ACTIVE_ROWS            = 2
CANONICAL_RESOLVED_ROWS          = 1
CANONICAL_BLANK_WRONG_ROWS_AFTER_BACKFILL = 0
CANONICAL_ACTIVE_DUPLICATES      = 0
backfill report                  = {created: 3, updated: 0, merged: 0, skipped: 0,
                                    legacy_blank_rows: 5, legacy_duplicate_rows: 2}
```

Legacy history is **not deleted**. The import is idempotent (re-run → still 3 rows).

## 5. Unanswered semantics

The frozen product semantic is `未作答 != 答错`. It was violated in the **write path**, on
four Exam writers, and all four are fixed:

| writer | file | before | after |
| --- | --- | --- | --- |
| chapter practice submit | `main.py` | `"" == "D"` → `correct=False`, wrong row written | `correct=None`, no tally, no wrong row |
| past-paper submit (bank branch) | `main.py` | same | same fix |
| AI-generated exam question submit | `main.py` | same | same fix |
| chapter + past-paper Practice Core mirror | `learning/practice/adapters/exam.py` | `correct=False` became a canonical fact | blank answer → `correct=None` at the fact boundary |
| AI-question mirror (shared course/exam adapter) | `learning/practice/adapters/ai` path in `course.py` | same | same fix |

The adapter fix is the important one architecturally: it applies at the point where a
legacy row becomes a canonical `PracticeAttempt`, so the FACT is honest and no downstream
reader needs to know the legacy grader was wrong. It is not a read filter.

`ExamChoicePracticeResult.correct` widened from `bool` to `bool | None`, matching
`ExamBigPracticeResult.correct` — "no verdict was applied" is now expressible, and a blank
is `null` rather than an invented failure. The persisted `result_json` and the response and
the BC5C replay all carry the same value, so replay equality holds.

Measured: a past-paper sitting with one answered question and nine blanks produced
`wrong_count = 0` and **zero rows in every wrong store** (was 10 rows, 9 of them blank).

```text
UNANSWERED_WRONG_WRITE = 0
```

## 6. Self-review semantics

An ungraded subjective answer (`judge = self_review`) already wrote nothing, on every path —
BC5A/BC6 froze that. BC7 kept it and added regression coverage so it cannot silently change:

```
chapter big question   -> correct=None, judge=self_review, no wrong row
past-paper big (ungraded) -> judge=self_review, score=None, no wrong row
past-paper big (AI-graded, authoritative incorrect) -> preserved as before
```

No incorrect verdict is ever inferred from the absence of a score.

```text
SELF_REVIEW_WRONG_WRITE = 0
```

## 7. Dedupe / upsert

`uq_wrong_answer_state_identity` is the gate: for one learner and one logical question
there is at most ONE state row, whether it is active or resolved. A repeat wrong recomputes
that row (`wrong_count` 1 → 2); a re-sit of a past paper merges into the same row instead
of appending.

`repeat_wrong_count` is the number of distinct FACTUAL incorrect attempts behind the state.
It is not a view count, not a retry count, and not the legacy `review_count`.

```text
CHAPTER_ACTIVE_DUPLICATES    = 0
PAST_PAPER_ACTIVE_DUPLICATES = 0
ACTIVE_DUPLICATES            = 0
```

## 8. Factual correct-resolution

`project.derive_from_attempts` was already correct; BC7 verified it end to end on both
sources through real HTTP with a real session:

```
chapter:   wrong (active, count=1) -> wrong (still ONE row, count=2) -> correct -> resolved
past paper: wrong (active, count=1) -> re-sit wrong (still ONE row, count=2) -> correct -> resolved
```

```text
CHAPTER_CORRECT_RETRY_RESOLVES    = PASS
PAST_PAPER_CORRECT_RETRY_RESOLVES = PASS
```

## 9. Legacy compatibility

The two legacy tables are **not deleted** and their routes keep working unchanged
(`GET/DELETE/PATCH /exam/11408/{subject}/wrong-questions[/{id}[/mastered]]`). What changed
is their standing:

```text
LEGACY_STORES = exam_wrong_questions, past_paper_wrong_questions
LEGACY_STORE_PRODUCT_AUTHORITY = NO
```

* the canonical read surface reads **nothing** from them — not as a merge input, not as a
  fallback, not for status;
* the legacy writers remain, but they no longer write blanks and no longer influence F1C4;
* where a legacy row and a fact disagree, the fact wins. The regression suite pins this: a
  legacy *blank* row for a question that has a factual wrong answer changes nothing on the
  surface, and a legacy `active` row cannot reopen a factually resolved state.

## 10. Normalized read API

ONE surface, typed, canonical.

```text
CANONICAL_WRONG_LIST_ENDPOINT   = GET /wrong-answers
CANONICAL_WRONG_DETAIL_ENDPOINT = GET /wrong-answers/{state_id}
CANONICAL_WRONG_UPDATE_ENDPOINT = PATCH /wrong-answers/{state_id}
```

`WrongAnswerRecord` is a **product record**, not a database row. It carries, where the
facts support them:

```
wrong_record_id · status · service_namespace · module_key · module_name
source_kind · source_label · question_type · stem · options
user_answer · reference_answer · analysis
year · question_number          (past papers)
question_bank_id · knowledge_point_id/name/path   (chapter practice)
resources · first_wrong_at · last_wrong_at · resolved_at · repeat_wrong_count
```

Deliberately **absent**: `question_source_type`, `question_source_id`,
`question_scope_key`, document-source internal ids, OCR cache ids, and the `legacy` block.
The frontend cannot reason about implementation identity because it is not on the wire.

```text
CANONICAL_READ_API = PASS
STATUS_SEMANTICS   = active = 未订正 (the last factual attempt was incorrect)
                     resolved = 已订正 (a LATER factual attempt was correct)
                     A resolved wrong is NOT mastery.
REPEAT_WRONG_COUNT_SEMANTICS = distinct factual incorrect attempts for that question.
                     It does not mean reviews, views or retries.
```

## 11. Module / source filtering

```text
MODULE_FILTER  = ?module=<subject_key>  -> indexed WHERE on wrong_answer_states.module_key
STATUS_FILTER  = ?status=active|resolved|(empty for all); anything else -> 400
SOURCE_CONTEXT = closed vocabulary:
                 chapter_practice 章节练习 · past_paper 历年真题 ·
                 ai_generated AI 出题 · other 其他
```

Verified: `?module=operating_system` returns 1 and `?module=data_structure` /
`?module=computer_network` return 0 for the same learner. The four required CS408 modules
are covered.

```text
WRONG_MODULE_CROSS_LEAK = 0
```

## 12. Public identities

```text
CHAPTER_PUBLIC_CONTEXT    = module_key + question_bank_id
                            (the authoritative chapter question identity the attempt
                             recorded, and the id the chapter redo contract takes)
PAST_PAPER_PUBLIC_CONTEXT = module_key + year + question_number
                            (BC6 frozen identity — no regression to ExamQuestionBank.id
                             or any document internal id)
```

The past-paper question number is taken from the **attempt's own persisted result
envelope**, not re-derived from the content tables, because that is the number the learner
actually answered. The content tables (bank row, or the document cache for a paper the bank
does not own) supply stem, options and analysis only.

## 13. Ownership / security

Every handler scopes by the session user; nothing is reachable by id alone. The two-user
test asserts list, detail and patch all refuse.

```text
ANONYMOUS_WRONG_ACCESS = 0
CROSS_USER_WRONG_ACCESS = 0
```

The wrong book is post-attempt by construction, so returning the reference answer to the
OWNING user is legitimate. There is no `question_id → answer` oracle: the endpoints never
take a bare question id.

`WRONG_RESOLUTION_IMPLIES_MASTERY = NO` — resolving a wrong question writes no knowledge
state. Pinned by a test asserting `user_knowledge_progress` stays empty and that a GET
changes nothing on the state row.

## 14. Resources

Figure questions now carry resources, in the SAME contract BC6 established:

```
/exam/11408/past-paper-images/{subject_key}/{year}/{filename}
```

`exam_past_paper.resources_for(subject, year, question_number)` is a public wrapper over the
exact BC6 resolution (image mapping → on-disk asset scan → document reference), so the wrong
book and the paper cannot drift into two URL formats. A test asserts the wrong record's URLs
are **equal** to the ones the paper itself advertises for the same public identity, using the
real `computer_organization 2022 Q12` figures.

```text
IMAGE_RESOURCE_CONTRACT = the BC6 application-relative contract, reused verbatim
                          (resolveApiResourceUrl() on the frontend already resolves it)
```

## 15. OpenAPI / generated TypeScript

`frontend/src/types/api.ts` regenerated with the project's own tool and version
(`openapi-typescript 7.13.0`), from a spec served by a standalone uvicorn on port **8958**
with an explicit TEMP `DATABASE_URL` — never port 8000, never the real database.
`package.json` was not modified.

Diff against the pre-BC7 file is surgical:

```
added schemas : WrongAnswerRecord · WrongAnswerResource · WrongAnswerAttemptView
                WrongAnswerListResponse · WrongAnswerDetailResponse
changed       : ExamChoicePracticeResult.correct  boolean -> boolean | null
paths         : none added, none removed, none renamed
```

**Unrelated working-tree drift: none.** Every changed line in the regenerated file is
attributable to this task.

```text
WRONG_REQUIRED_REQUEST_UNKNOWN = 0
WRONG_REQUIRED_SUCCESS_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

Compile probe: `frontend/src/features/exam/api/wrong-answer-contract.test.ts` resolves every
type through the generated `paths` / `components` — list, module filter, status, source
context, question/reference snapshots, resolution state, public past-paper identity, chapter
redo identity, resource refs, detail history, patch. No cast, no handwritten DTO, no `any`.
A regeneration that loosens any of them fails `npm run typecheck`.

### Scope note on the legacy compatibility routes

`GET /exam/11408/{subject}/wrong-questions` and its `DELETE` / `PATCH .../mastered`
siblings remain **deliberately untyped**. They are compatibility routes (§22), they are not
the F1C4 contract, and their `id` is ambiguous by construction (F1C4A §4: the same integer
exists in two merged tables). Typing that ambiguity would endorse it. The gates
`WRONG_REQUIRED_*` therefore count the canonical surface, which is 0 / 0. **If you want the
legacy routes typed too, that is a separate decision and I have not made it for you.**

## 16. Runtime matrix

Executed through real HTTP with a real authenticated session.

```
chapter
 1  answer wrong                     -> 200
 2  canonical active count           = 1
 3  repeat wrong                     -> 200
 4  canonical active count           = 1        (NOT 2)
 5  repeat_wrong metadata            = 2        (wrong_count, fact-derived)
 6  answer correctly                 -> 200
 7  same canonical record            = resolved, resolved_at set
 8  submit blank choice              -> 200, correct=null, wrong_count=0
 9  canonical wrong count            unchanged; legacy wrong table also 0
10  submit big / self_review         -> 200, judge=self_review
11  canonical wrong count            unchanged

past paper (real 2022 computer_organization questions where noted)
12  answer objective wrong           -> 200
13  canonical active                 = 1
14  re-sit (702 + 703 left blank)    -> 200, choice_correct=1, self_review_count=1
15  canonical active                 = 1        (no duplicate), wrong_count 1 -> 2
16  answer the same question right   -> 200
17  canonical record                 = resolved
```

Two executions of the whole matrix are pinned as tests, plus the blank/self-review pair and
the figure case.

## 17. Database safety

`backend/app.db` opened read-only throughout; every write probe went to a TEMP copy.

```
SHA256     1c1b2d85…3fe522      unchanged
size       64917504             unchanged
mtime      2026-09-16 21:24:23  unchanged
tables     72                   unchanged
integrity_check = ok    quick_check = ok
exam_question_bank = 9333       unchanged
exam_wrong_questions = 0 · past_paper_wrong_questions = 0
wrong_answer_states = ABSENT    (still arrives only via migration)
```

```text
REAL_APP_DB_MUTATED = NO
```

The real database holds **zero** wrong-answer rows of any kind, so the historical backfill
is a genuine no-op on production data today:

```
LEGACY_BLANK_WRONG_ROWS (real app.db)           = 0
LEGACY_DUPLICATE_WRONG_ROWS (real app.db)       = 0
CANONICAL_ACTIVE_ROWS (real app.db)             = 0
CANONICAL_RESOLVED_ROWS (real app.db)           = 0
```

The polluted-copy numbers in §4 are the ones that demonstrate the semantics.

### create_all masking

BC7 does **not** remove `Base.metadata.create_all` from the product — it is the runtime
safety net for many legacy tables and removing it is out of scope. What BC7 does is prove
the canonical wrong-answer path does not *depend* on it:

> take the real legacy 72-table database → `alembic upgrade head` → **disable
> `MetaData.create_all` entirely in a subprocess** → start the real app → register, log in,
> record an incorrect attempt → `GET /wrong-answers` returns the expected canonical record.

```text
WRONG_STATE_REQUIRES_CREATE_ALL_TO_EXIST = NO
```

## 18. Regression

```
BC7 targeted suite            = 16 passed  (tests/test_bc7_wrong_answer_canonicalization.py)
wrong-answer core             = 40 passed  (tests/test_wrong_answers.py)
wrong-answer HTTP contract    = 12 passed  (tests/test_wrong_answers_api.py)
targeted Exam suites
  test_bc5a_chapter_practice_contract        PASS
  test_bc5c_attempt_result_replay_contract   PASS
  test_bc6_past_paper_contract               PASS
  test_exam_practice_records                 PASS
  test_exam_final_acceptance                 PASS
  test_practice_migration                    PASS
  test_exam_openapi_contract                 PASS
  test_exam_prep_namespace                   PASS
  test_exam_knowledge_openapi_contract       PASS
  test_exam_framework / ai_orchestrator      PASS
full backend regression                    = 1143 passed / 0 failed
```

Baseline 1126 → 1143 = +16 BC7 tests and +1 module-filter test in the wrong-answer API
suite. No test was deleted to make anything pass; the four legacy fixtures
that had to change did so because they asserted a blank answer was a wrong answer, which is
the very behaviour BC7 removes.

```
FULL_BACKEND_TESTS = PASS  (1143 passed / 0 failed)
```

Frontend (after regeneration):

```
FRONTEND_TYPECHECK     = PASS
FRONTEND_LINT          = PASS
FRONTEND_UNIT_TESTS    = PASS   (18 files / 63 tests; was 17 / 56)
FRONTEND_BUILD         = PASS
```

## 19. Final gates

```
CANONICAL_WRONG_STORE                  = PASS
LEGACY_STORE_PRODUCT_AUTHORITY         = NO
UNANSWERED_WRONG_WRITE                 = 0
SELF_REVIEW_WRONG_WRITE                = 0
CHAPTER_ACTIVE_DUPLICATES              = 0
PAST_PAPER_ACTIVE_DUPLICATES           = 0
CHAPTER_CORRECT_RETRY_RESOLVES         = PASS
PAST_PAPER_CORRECT_RETRY_RESOLVES      = PASS
WRONG_RESOLUTION_IMPLIES_MASTERY       = NO
WRONG_STATE_REQUIRES_CREATE_ALL_TO_EXIST = NO
CANONICAL_BLANK_WRONG_ROWS_AFTER_BACKFILL = 0
WRONG_MODULE_CROSS_LEAK                = 0
ANONYMOUS_WRONG_ACCESS                 = 0
CROSS_USER_WRONG_ACCESS                = 0
CANONICAL_READ_API                     = PASS
WRONG_REQUIRED_REQUEST_UNKNOWN         = 0
WRONG_REQUIRED_SUCCESS_UNKNOWN         = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO    = 0
REAL_APP_DB_MUTATED                    = NO
FULL_BACKEND_TESTS                     = PASS
FRONTEND_TYPECHECK                     = PASS
FRONTEND_LINT                          = PASS
FRONTEND_UNIT_TESTS                    = PASS
FRONTEND_BUILD                         = PASS

F1C4_FRONTEND_READY                    = YES
```

---

## Files changed

| file | change |
| --- | --- |
| `backend/main.py` | blank objective answer → no verdict, no wrong row (chapter, past-paper, AI-question writers); `ExamChoicePracticeResult.correct: bool \| None`; done-record `is_correct` honest for blanks |
| `backend/learning/practice/adapters/exam.py` | `_ungraded_to_none(value, answer)` — blank answer → `correct=None` at the canonical fact boundary |
| `backend/learning/practice/adapters/course.py` | same rule on the shared AI-question mirror |
| `backend/learning/wrong_answers/models.py` | `module_key` column + `ix_wrong_answer_states_user_ns_module` |
| `backend/learning/wrong_answers/project.py` | `module_of` / `_module_of`; module persisted from the facts |
| `backend/learning/wrong_answers/legacy.py` | grouped backfill: blank exclusion, duplicate collapse, module, chronological status |
| `backend/learning/wrong_answers/service.py` | `module_key` filter + `count_states` for pagination |
| `backend/learning/spaces/exam_prep/wrong_answers.py` (new) | the normalized record projection |
| `backend/routers/wrong_answers.py` | typed list / detail / patch contract |
| `backend/exam_past_paper.py` | `resources_for` + `document_question_by_internal_id` (public wrappers over the BC6 primitives) |
| `migrations/versions/20260919_0009_wrong_answer_module_key.py` (new) | the additive migration |
| `backend/tests/test_bc7_wrong_answer_canonicalization.py` (new) | 16 targeted tests |
| `backend/tests/test_wrong_answers_api.py` | updated to the normalized contract |
| `backend/tests/test_wrong_answers.py`, `test_exam_practice_records.py`, `test_exam_final_acceptance.py` | legacy fixtures given a real answer (they previously asserted a blank *is* a wrong answer); migration head assertions |
| `backend/tests/test_practice_migration.py` | head assertions use `EXPECTED_HEAD` |
| `frontend/src/types/api.ts` | regenerated |
| `frontend/src/features/exam/api/wrong-answer-contract.test.ts` (new) | compile probe |

## Not done (per §30 / scope)

No F1C4 UI. No spaced-repetition scheduler, no review table, no AI wrong-answer summary, no
misconception diagnosis, no mastery score, no recommendation engine, no "重练全部" across
sources. No manual "已订正" writer was added: resolution is factual-attempt-driven and needs
no learner action. No legacy wrong table was dropped.

## Known follow-ups (not BC7 blockers)

1. **`cs408-practice-workspace.tsx` renders a blank choice as 回答错误.** It reads
   `result.correct ? '回答正确' : '回答错误'`, so a `null` verdict falls into the wrong
   branch even though the component's own summary already counts it as `unanswered`. This is
   the practice workspace (F1C2D's), not F1C4, and it was the same before BC7 — but the
   backend now supplies an honest `null`, so the card can and should say 未作答. Left alone
   deliberately: BC7 was explicitly barred from implementing frontend work.
2. **`REDO_PAST_PAPER_WRONG` is whole-paper only.** `POST .../past-paper-attempts` takes a
   `year`, with no subset parameter, so a past-paper wrong record can be re-sat only as the
   whole paper. `REDO_CHAPTER_WRONG` is exact (`question_ids`). Reported honestly; no mixed
   synthetic attempt was invented.
3. **Chapter wrong records carry no figure resources.** Chapter bank rows have no
   year/question_number, so the BC6 on-disk figure convention cannot resolve for them.
   `resources` is an honest empty list. Past-paper figures work and are tested.
4. **`backend/app.db` is still un-migrated.** `MIGRATION_HEAD` is now `20260919_0009`, but
   the deployed database has no `alembic_version` at all. A real deployment needs the
   baseline stamp before `alembic upgrade head` — the existing deployment process, not BC7.

---

```text
FRONTEND_BC7_COMPLETE

CANONICAL_WRONG_RECORD_OWNER = wrong_answer_states (WrongAnswerState)

CANONICAL_SOURCE_OF_TRUTH    = practice_attempts (factual), projected into
                               wrong_answer_states; display data read from the same
                               factual attempts plus the immutable question source

LEGACY_STORES =
  1. exam_wrong_questions        (compatibility only)
  2. past_paper_wrong_questions  (compatibility only)
LEGACY_STORE_PRODUCT_AUTHORITY = NO

MIGRATION_BEFORE = 20260917_0008
MIGRATION_AFTER  = 20260919_0009

BACKFILL_SOURCE = factual practice_attempts first; legacy wrong tables as a bounded
                  fallback for questions with no facts
LEGACY_BLANK_WRONG_ROWS       = 0 on the real app.db (5 on the polluted probe copy)
LEGACY_DUPLICATE_WRONG_ROWS   = 0 on the real app.db (7 raw / 2 collapsed on the probe)
CANONICAL_ACTIVE_ROWS         = 0 on the real app.db
CANONICAL_RESOLVED_ROWS       = 0 on the real app.db

UNANSWERED_WRONG_WRITE  = 0
SELF_REVIEW_WRONG_WRITE = 0

CHAPTER_WRONG_UPSERT    = PASS   (repeat wrong updates one row)
PAST_PAPER_WRONG_UPSERT = PASS   (re-sit updates one row)

CHAPTER_CORRECT_RETRY_RESOLVES    = PASS
PAST_PAPER_CORRECT_RETRY_RESOLVES = PASS

ACTIVE_DUPLICATES = 0   (chapter 0 · past paper 0)

STATUS_SEMANTICS = active = 未订正 (last factual attempt incorrect)
                   resolved = 已订正 (a later factual attempt correct)
                   resolving does NOT mean mastery
REPEAT_WRONG_COUNT_SEMANTICS = distinct factual incorrect attempts; not reviews,
                               not views, not retries, not the legacy review_count

CANONICAL_WRONG_LIST_ENDPOINT   = GET /wrong-answers
CANONICAL_WRONG_DETAIL_ENDPOINT = GET /wrong-answers/{state_id}

MODULE_FILTER  = ?module=<subject_key> (indexed column; four CS408 modules covered)
STATUS_FILTER  = ?status=active|resolved|empty
SOURCE_CONTEXT = chapter_practice 章节练习 · past_paper 历年真题 ·
                 ai_generated AI 出题 · other 其他
PAGINATION     = limit/offset + total (limit default 50, max 200)
DEFAULT_SORT   = last_wrong_at DESC NULLS LAST, id DESC

CHAPTER_PUBLIC_CONTEXT    = module_key + question_bank_id
PAST_PAPER_PUBLIC_CONTEXT = module_key + year + question_number (BC6 frozen)

IMAGE_RESOURCE_CONTRACT = the BC6 application-relative contract, reused verbatim

ANONYMOUS_WRONG_ACCESS  = 0
CROSS_USER_WRONG_ACCESS = 0

WRONG_REQUIRED_REQUEST_UNKNOWN = 0
WRONG_REQUIRED_SUCCESS_UNKNOWN = 0

DB_SCHEMA_CHANGED   = YES (one additive column + one index on wrong_answer_states)
MIGRATION_ADDED     = YES (20260919_0009)
REAL_APP_DB_MUTATED = NO

TARGETED_TESTS     = 16 BC7 passed / 68 wrong-answer tests passed
                     (16 BC7 + 40 core + 12 HTTP)
FULL_BACKEND_TESTS = 1143 passed / 0 failed

FRONTEND_TYPECHECK  = PASS
FRONTEND_LINT       = PASS
FRONTEND_UNIT_TESTS = PASS
FRONTEND_BUILD      = PASS

F1C4_FRONTEND_READY = YES

BLOCKERS = none
```
