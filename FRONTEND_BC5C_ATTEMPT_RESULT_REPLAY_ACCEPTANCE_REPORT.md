# FRONTEND_BC5C — Submitted Practice Attempt Authoritative Result Replay Acceptance

Date: 2026-09-18.
Scope: backend contract closure only. Exists to unblock `FRONTEND_F1C2C`.
No frontend UI was implemented. `F1C1` / `F1C2A` / `F1C2B` UI was not touched.

```text
FRONTEND_BC5C_COMPLETE
F1C2C_REFRESH_BLOCKER_RESOLVED = YES
```

---

## 1. Blocker

After a browser refresh, `GET /exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}`
returned the question payload, `standard_answer`, `analysis` and `saved_answers`, but **not** the
server-authoritative per-question `correct` / `judge`. The result page therefore had no way to
reconstruct 回答正确 / 回答错误 / 自行复盘 without re-grading on the client — which is forbidden
(`FRONTEND_GRADING_COMPARISON = 0`).

The blocker was **not** a missing backend fact. It was a missing **replay**: the fact was already
persisted, and simply was not on the wire after reload.

## 2. Persisted result audit

Traced `POST .../attempts/{attempt_id}/submit` (`backend/main.py:21986`) through
`ExamPracticeAttempt` (`backend/models.py:987`) into the real runtime.

The submit handler builds `results` in memory, grades once, and then persists the whole thing:

```python
a.result_json = json.dumps({"correct": correct, "total": total, "choice_total": choice_total,
    "big_count": big_count, "results": results, "mistake_saved": mistake_saved}, ensure_ascii=False)
```

### ATTEMPT_RESULT_PERSISTENCE_MATRIX

Verified against a live server on port 8948 with an explicit TEMP `DATABASE_URL` (not 8000, not the
real DB), reading `result_json` back out of the attempt row.

| Required fact | Persisted? | Location | Exact persisted shape |
| --- | --- | --- | --- |
| `question_id` | **YES** | `result_json.results[].question_id` | `int` = `ExamQuestionBank.id` |
| `question_type` | **YES** | `result_json.results[].question_type` | `"choice"` \| `"big"` |
| `user_answer` | **YES** | `result_json.results[].user_answer` | `str` (already `str(...).strip()`) |
| `correct` | **YES** | `result_json.results[].correct` | `bool` for choice; `null` for big |
| `judge` | **YES (big only)** | `result_json.results[].judge` | `"self_review"`; key absent for choice |
| `standard_answer` | **YES** | `result_json.results[].standard_answer` | `str` |
| `analysis` | **YES** | `result_json.results[].analysis` | `str`, may be `""` |
| `hint` | **YES (big only)** | `result_json.results[].hint` | `str` |
| `stem`, `options` | **YES** | `result_json.results[]` | `str`, `dict[str,str]` |
| counts | **YES** | `result_json.{correct,total,choice_total,big_count,mistake_saved}` + columns `correct_count` / `wrong_count` / `accuracy` | `int` / `float` |
| `status`, `submitted_at` | **YES** | columns | `"submitted"`, `datetime` |

**A.** Yes — per-question `correct` / `judge` are already persisted.
**B.** Exact shape = the same records the submit response returns, verbatim.
**C.** n/a — no reconstruction was needed.

Corroboration: `backend/learning/practice/adapters/exam.py:85` (STEP 7D) already reads the same
`result_json.results` list and maps `correct` → `_ungraded_to_none(item["correct"])` and
`judge` → `result["judge"]`. The persisted per-question record is the project's established
canonical source for this fact — BC5C did not invent one.

## 3. Submit-result ownership

`submit` is, and remains, the **only** grader for this domain:

* it performs the choice comparison (`ua.upper() == sa.upper()`, `main.py:22011`),
* it writes `result_json` **before** the response is built,
* the response body returns the in-memory `results` list that was just persisted.

`RUNTIME_RESPONSE_CHANGED = YES — ADDITIVE SUBMITTED RESULT REPLAY`, submit output itself unchanged.

## 4. Detail replay design

`GET .../attempts/{attempt_id}` is a **read/replay** endpoint, not a grader.

```python
def _persisted_attempt_results(attempt):
    if not attempt.result_json:
        return []
    try:
        blob = json.loads(attempt.result_json)
    except (TypeError, ValueError):
        return []
    results = blob.get("results") if isinstance(blob, dict) else None
    return results if isinstance(results, list) else []
```

The handler adds the key only once the attempt is `submitted`:

```python
if a.status == "submitted":
    detail["results"] = _persisted_attempt_results(a)
```

Consequences, all measured:

* pre-submit there is no `results` key at all (`response_model_exclude_unset=True`), so the
  pre-submit shape is byte-identical to BC5A;
* a submitted attempt's `results` is **byte-identical to the submit response's `results`**;
* an attempt with nothing persisted replays `[]` — it never invents a verdict;
* no answer comparison, no normalization and no self-review inference exists on the read path.

## 5. Choice semantics

`question_type = "choice"` → `correct: bool` (the submit-time verdict), `judge` **absent**.
No new enum was introduced. Case folding is performed once, at submit; the reload replays that
decision and preserves the learner's raw answer (`"a"` stays `"a"` next to standard `"A"`).

## 6. Big semantics

`question_type = "big"` → `correct: null`, `judge: "self_review"`, `hint` present, reference answer
present. Preserved exactly from submit. The frontend recovers 自行复盘 from `question_type` /
`judge` — no AI judging, no auto score, no 正确/错误.

## 7. Pre-submit security

Unchanged and re-proved at runtime: while `status == "in_progress"` the payload is exactly
`["attempt", "questions", "saved_answers"]`; every question has no `standard_answer`, no `analysis`,
no `correct`, no `judge`, and there is no `results` key.

```text
PRE_SUBMIT_ANSWER_LEAK         = 0
PRE_SUBMIT_EXPLANATION_LEAK    = 0
PRE_SUBMIT_GRADING_RESULT_LEAK = 0
```

## 8. Question-id reconciliation

Every replayed record carries `question_id` (= `ExamQuestionBank.id`) and its own `user_answer`,
`correct` and `judge`. The frontend keys by `question_id`; array position is never identity.

Proved two ways:

* backend: after shuffling `question_ids_json` **and** reversing the persisted `results` order, the
  `question_id → (user_answer, correct)` mapping is unchanged;
* frontend: `replayByQuestionId(detail)` returns `Record<number, Result>`; reversing the question
  list leaves `7234 → 'a'` and `7235 → '手写作答'`.

This closes the earlier ordering limitation. Server ordering itself was not changed.

## 9. Read-only side effects

`GET` on both `in_progress` and `submitted` attempts performs no write. Measured over repeated GETs
against a live server, snapshotting every table the submit path can touch:

```text
exam_wrong_questions     0 → 0      ATTEMPT_DETAIL_WRONG_SIDE_EFFECTS = 0
user_knowledge_progress  unchanged  ATTEMPT_DETAIL_KNOWLEDGE_WRITES   = 0
learning_events          unchanged
wrong_answer_states      unchanged
practice_attempts        unchanged
exam_question_done_records 2 → 2
exam_practice_attempts     2 → 2    ATTEMPT_DETAIL_READ_IDEMPOTENT   = PASS
```

Repeated responses are byte-identical.

## 10. OpenAPI

`ExamPracticeAttemptDetailResponse` gains one additive, concrete field. The result models were moved
above the detail model so the reference resolves at class-creation time (same objects, same module,
definitions only reordered).

```json
"results": {
  "items": {
    "oneOf": [{"$ref": ".../ExamChoicePracticeResult"}, {"$ref": ".../ExamBigPracticeResult"}],
    "discriminator": {"propertyName": "question_type",
                      "mapping": {"big": ".../ExamBigPracticeResult", "choice": ".../ExamChoicePracticeResult"}}
  },
  "type": "array", "title": "Results"
}
```

`results` is **not** in `required`, so the pre-submit payload stays key-absent. No `Dict[str, Any]`,
no `Any`, no untyped record anywhere in the result transport.

`ExamPracticeSubmitResponse.properties.results.items` is the *same object* — one canonical result
schema shared by submit and detail, asserted by test.

## 11. Generated TypeScript

Regenerated with the project's own tool and version (`openapi-typescript 7.13.0`, same as
`npm run api:generate`) from a **current** spec served by a standalone uvicorn on port **8947** with
an explicit TEMP `DATABASE_URL` — never the unreliable `localhost:8000`. `package.json` unchanged;
`api.ts` not hand-edited.

The entire regenerated diff is the BC5C change and nothing else:

```diff
-        /** ExamPracticeAttemptDetailResponse */
+        /** ExamPracticeAttemptDetailResponse
+         * @description Attempt detail: ... (docstring) */
             saved_answers: { [key: string]: string };
+            /** Results */
+            results?: (components["schemas"]["ExamChoicePracticeResult"] | components["schemas"]["ExamBigPracticeResult"])[];
```

### One pre-existing library interaction, identified and handled

`openapi-typescript-helpers`' `Readable<T>` mapped type drops any property whose
`NonNullable<T[K]>` extends `$Write<any>`. For a `null`-typed property `NonNullable<null>` is
`never`, and `never` extends everything, so **`null`-only properties are stripped from every read
response**. In this contract the only such property is `correct` on a big question.

Verified this is **pre-existing, not introduced by BC5C**: the existing
`POST .../submit` response read through `apiClient` loses exactly the same property today.

Handled without weakening the contract and without a cast: `correct: null` stays on the wire and in
the generated schema; `ChapterPracticeAttempt` is now *derived* from the request instead of
annotated, so it is the type the client actually delivers, still generated-only:

```ts
export type ChapterPracticeAttempt = Awaited<ReturnType<typeof requestAttempt>>;
```

Nothing is lost: a big question is identified by `question_type` and carried by
`judge: 'self_review'`, and its `correct` is always `null`, so it is never read.

```text
GENERATED_TS_ATTEMPT_RESULT_UNKNOWN     = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO     = 0
```

## 12. Real runtime QA

Standalone uvicorn on port **8948**, explicit TEMP `DATABASE_URL`, real HTTP client with a cookie
jar, a real seeded user authenticated through `POST /login`. 31/31 checks passed.

* **A. choice** — create → answer `A` → submit → GET: `results` identical to submit; `correct: true`,
  `user_answer: "A"`, `standard_answer: "A"`, `analysis: "qa-analysis"`.
* **B. big** — create → answer free text → submit → GET: identical; `correct: null`,
  `judge: "self_review"`, `user_answer`/`standard_answer` replayed.
* **C. refresh** — four repeated GETs byte-identical, no table grew.
* errors preserved: 404 unknown attempt, 400 unknown subject, 400 empty `question_ids`, 400 omitted
  `question_ids` (the request model defaults the field so the handler's own domain 400 survives),
  422 wrong field type, 422 wrong answer value type.
* ownership: a second real user gets 404, anonymous gets 401.

## 13. DB safety

`backend/app.db` is unchanged across the whole task:

| Measure | Before | After |
| --- | --- | --- |
| SHA256 | `1c1b2d85…3fe522` | `1c1b2d85…3fe522` (identical) |
| mtime | `1789565063.8964841` | `1789565063.8964841` |
| size | `64917504` | `64917504` |
| `PRAGMA integrity_check` | `ok` | `ok` |
| table count | 72 | 72 |
| `exam_question_bank` | 9333 | 9333 |
| `programming_exercises` | 1923 | 1923 |
| `knowledge_points` | 32 | 32 |
| `exam_practice_attempts` | 0 | 0 |

No table, column or index was added. `MIGRATION_HEAD` is still `20260917_0008`; every file under
`migrations/versions/` predates this session (latest mtime 2026-09-17 11:05).

```text
DB_SCHEMA_CHANGED    = NO
MIGRATION_ADDED      = NO
REAL_APP_DB_MUTATED  = NO
```

## 14. Tests

New: `backend/tests/test_bc5c_attempt_result_replay_contract.py` — 24 tests covering the full
23-item matrix plus the no-second-grader proof.

The no-regrade proof is behavioural and decisive: after a correct submit, the persisted
`result_json` verdict is flipped in the database, then the detail is re-read. A GET that re-compared
`user_answer` against `standard_answer` would answer `True` (the learner really did answer `A` and
the standard really is `A`); the endpoint answers `False`, i.e. it replays the stored fact. This is
reinforced by a narrow-boundary spy proving `results` comes from `_persisted_attempt_results`, by an
AI-boundary monkeypatch, and by a source guard asserting the handler holds no `.upper()` / `.strip()`
comparison primitive.

Frontend: `src/features/exam/api/practice-contract.test.ts` gains a BC5C describe block —
compile-level proof that the generated contract exposes `question_id`, `user_answer`, `correct`,
`judge`, `standard_answer`, `analysis`, that a big result's `correct` is `null` and not an unflagged
boolean, that `@ts-expect-error` holds on the pre-submit question's `correct`/`judge`, and that the
replay survives a reordered question list. No cast, no handwritten DTO, no answer comparison.

## 15. Final gates

```text
AUTHORITATIVE_RESULT_PERSISTED     = PASS   (already persisted by submit; verified in the row)
SUBMITTED_ATTEMPT_RESULT_REPLAY    = PASS   (byte-identical to submit results)

ATTEMPT_DETAIL_REGRADES            = NO     (persistence-flip proof + spy + source guard)

QUESTION_ID_KEYED_RESULT           = PASS
QUESTION_INDEX_AS_IDENTITY         = NO

CHOICE_CORRECT_RELOAD              = PASS
CHOICE_INCORRECT_RELOAD            = PASS
BIG_SELF_REVIEW_RELOAD             = PASS

PRE_SUBMIT_ANSWER_LEAK             = 0
PRE_SUBMIT_EXPLANATION_LEAK        = 0
PRE_SUBMIT_GRADING_RESULT_LEAK     = 0

ATTEMPT_DETAIL_WRONG_SIDE_EFFECTS  = 0
ATTEMPT_DETAIL_KNOWLEDGE_WRITES    = 0
ATTEMPT_DETAIL_READ_IDEMPOTENT     = PASS

ATTEMPT_OWNERSHIP_ISOLATION        = PASS   (other user 404, anonymous 401, real HTTP)

ATTEMPT_DETAIL_TYPED               = PASS
GENERATED_TS_ATTEMPT_RESULT_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0

DB_SCHEMA_CHANGED                  = NO
MIGRATION_ADDED                    = NO
REAL_APP_DB_MUTATED                = NO

RUNTIME_RESPONSE_CHANGED           = YES — ADDITIVE SUBMITTED RESULT REPLAY
ERROR_SEMANTICS_CHANGED            = NO

FULL_BACKEND_TESTS                 = PASS   (1099 passed / 0 failed; baseline 1075 + 24 new)
FRONTEND_TYPECHECK                 = PASS
FRONTEND_LINT                      = PASS
FRONTEND_UNIT_TESTS                = PASS   (13 files / 41 tests)
FRONTEND_BUILD                     = PASS

F1C2C_REFRESH_BLOCKER_RESOLVED     = YES
BLOCKERS                           = NONE
```

---

## Files changed

| File | Change |
| --- | --- |
| `backend/main.py` | `ExamPracticeAttemptDetailResponse` gains `results: list[ExamPracticeSubmitResult]`; result models moved above it; new `_persisted_attempt_results`; detail handler returns `results` only when `status == "submitted"` |
| `backend/tests/test_bc5c_attempt_result_replay_contract.py` | **new** — 24 tests |
| `frontend/src/types/api.ts` | regenerated (additive `results?` + docstring only) |
| `frontend/src/features/exam/api/chapter-practice.ts` | `ChapterPracticeAttempt` derived from the request instead of annotated |
| `frontend/src/features/exam/api/practice-contract.test.ts` | BC5C describe block added |

Not changed: submit handler, grading algorithm, wrong-record behaviour, knowledge status, attempt
creation, question source/filter, AI explain, membership/usage/router, `migrations/`, `alembic.ini`,
`package.json`, DB schema.

## Carried forward (not blockers)

* The `Readable` `null`-property stripping is an upstream `openapi-typescript-helpers` behaviour that
  also affects `POST .../submit`. It silently removes `correct` from a big result on the client read
  type. Harmless today (the value is always `null` and never read), but worth remembering if a
  future contract ever needs a meaningful `null`-typed field on the wire.
* `F1C2C` UI implementation is still **NOT_STARTED** — BC5C only closed the transport contract.
