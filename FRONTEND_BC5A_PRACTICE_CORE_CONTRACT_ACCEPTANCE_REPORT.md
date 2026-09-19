# FRONTEND_BC5A — CS408 Chapter Practice Core Contract Acceptance

Date: 2026-09-17.
Scope: backend contract closure only. Exists to unblock `FRONTEND_F1C2B — Answer Desk Foundation`.
No frontend UI was implemented. `F1C1` / `F1B2` UI was not touched.

```text
FRONTEND_BC5A_COMPLETE
F1C2B_BACKEND_CONTRACT_READY = YES
```

---

## 1. Runtime endpoint inventory

All six chapter-practice core endpoints, as they exist in `backend/main.py` at closure time. No
endpoint was invented; the names come from F1C2A and were confirmed against `app.routes`.

| # | Method | Path | Handler | Request model (before → after) | Response model (before → after) |
| --- | --- | --- | --- | --- | --- |
| 1 | GET | `/exam/11408/{subject_key}/chapter-practice/outline` | `get_chapter_practice_outline` | none | `{}` → `ExamChapterPracticeOutlineResponse` |
| 2 | GET | `/exam/11408/{subject_key}/chapter-practice/questions` | `get_chapter_practice_questions` | query only (+ `chapter_code` added) | `{}` → `ExamChapterPracticeQuestionsResponse` |
| 3 | POST | `/exam/11408/{subject_key}/chapter-practice/attempts` | `create_chapter_practice_attempt` | `req: dict` → `ExamPracticeAttemptCreateRequest` | `{}` → `ExamPracticeAttemptCreateResponse` |
| 4 | GET | `/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}` | `get_chapter_practice_attempt` | path/query only | `{}` → `ExamPracticeAttemptDetailResponse` |
| 5 | POST | `.../attempts/{attempt_id}/answers` | `save_chapter_attempt_answers` | `req: dict` → `ExamPracticeWriteRequest` | `{}` → `ExamPracticeAnswerSaveResponse` |
| 6 | POST | `.../attempts/{attempt_id}/submit` | `submit_chapter_attempt` | `req: dict` → `ExamPracticeWriteRequest` | `{}` → `ExamPracticeSubmitResponse` |

Side effects (unchanged by BC5A):

* 1 — none; counts active `source_type == "chapter"` rows for the module.
* 2 — none (read).
* 3 — inserts one `ExamPracticeAttempt` (`practice_type="chapter"`, `status="in_progress"`).
* 4 — none (read of `question_ids_json` + `answers_json`).
* 5 — writes `answers_json`; refused with 404 unless the attempt is still `in_progress`.
* 6 — sets `status="submitted"`, writes `result_json`, one `ExamQuestionDoneRecord` per question,
  then — **failure-isolated after the primary commit** — mirrors into the unified Practice Core and
  creates/updates the unified wrong-answer state. A failed mirror cannot roll back the attempt.

`FRONTEND_WRONG_RECORD_WRITE_REQUIRED = NO` — the wrong book is written by `submit` alone; the
frontend never needs a second wrong-book mutation call (§26).

### PRACTICE_RUNTIME_CONTRACT_MATRIX

Measured from a standalone uvicorn on ports **8944/8945/8946** (never 8000) bound to an explicit
TEMP `DATABASE_URL` copy of `backend/app.db`, authenticated as a real registered user, for
`data_structure` and `operating_system`.

| Capability | Endpoint | Runtime `status`/`source_type` type | required? | nullable? | closed set? | source | side effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chapter discovery | `…/chapter-practice/outline` | `subject_key: string`, `knowledge_points: {string:int}`, `total: int`, **`chapters: [ExamPracticeChapter]`** | all always present | no | chapter_code digits | active chapter rows + module seed | none |
| Chapter question list | `…/chapter-practice/questions` | `items: [ExamPracticeQuestion]`, `total: int`, `debug_info` **only when `total == 0`** | `items`,`total` | `debug_info` absent | `question_type`: `choice\|big` | active chapter rows only | none |
| Attempt creation | `…/chapter-practice/attempts` | `attempt_id: int`, `status: "in_progress"`, `total_questions: int` | all | no | yes | inserts `ExamPracticeAttempt` | attempt row |
| Attempt detail | `…/attempts/{attempt_id}` | `attempt{id,status,total_questions,knowledge_point_path,started_at}`, `questions: [ExamPracticeAttemptQuestion]`, `saved_answers: {string:string}` | `attempt`,`questions`,`saved_answers` | `knowledge_point_path`,`started_at`, and per question `year`, `question_number`, `difficulty`, `quality_status`, `created_at`, `knowledge_point_*` | `status`: `in_progress\|submitted`; `question_type`: `choice\|big` | attempt + question rows | none |
| Answer save | `…/attempts/{id}/answers` | `success: bool` | yes | no | yes | `answers_json` | answer write |
| Submit | `…/attempts/{id}/submit` | `total_questions`,`choice_total`,`big_count`,`correct_count`,`wrong_count`,`mistake_saved_count`: int, `accuracy: float`, `results: [ExamChoicePracticeResult\|ExamBigPracticeResult]` | all | no | discriminated on `question_type` | grading + records | status, result, done records, practice mirror, wrong answer |
| Resume/reload | `…/attempts/{attempt_id}` | same as detail; `saved_answers` replays the stored map | — | — | — | `question_ids_json` + `answers_json` | none |

Every pre-existing runtime field kept its name, JSON type and nullability. The one intentional
removal and the one additive field are separated in §13.

---

## 2. Canonical chapter identity — forensic

### Candidates evaluated

| Priority | Candidate | Verdict |
| --- | --- | --- |
| 1 | F1C1 `chapter.code` | **ADOPTED** — it *is* the level-1 code the practice rows derive |
| 2 | `chapter_no` scoped by canonical module | Same value as (1); exposed alongside it as `chapter_no` |
| 3 | `knowledge_point_id` (sub-chapter) | **REJECTED as canonical** — not uniform across modules (see below) |
| — | Chinese title / array index / frontend hash / new UUID | Forbidden by §5; not used |

### Why candidate 3 fails

The chapter-question rows tag `knowledge_point_id` at **different depths in different modules**:

| Module | group level actually used | distinct groups |
| --- | --- | --- |
| `data_structure` | section code (`1.1`, `2.3`, …) | 31 |
| `computer_organization` | section code (`1.1` … `7.3`) | 28 |
| `operating_system` | section code (`1.1` … `5.3`) | 18 |
| `computer_network` | **mixed**: leaf code + title (`1.1.1 计算机网络的概念`), section code + title (`3.1 数据链路层的功能`), and chapter-4 codes that exist in **neither** the seed's sections nor its leaves (`4.8` … `4.51`) | 142 |

44 of the 142 `computer_network` groups carry a code that is not in that module's knowledge map at
all. A sub-chapter identity is therefore not a knowledge-map identity and cannot be canonical.

### Why candidate 1 is correct

`_question_chapter_code()` takes the level-1 segment of the row's knowledge-point code. That value:

* equals `chapter.code` / `chapter.chapter_no` in the module seed (`{module}_11408.json`);
* is what F1C1's study-plan already exposes (`chapters[].code`, `chapter_no`, `title`);
* is uniform across all four modules;
* is URL-safe (digits only) and unique within a module.

The serializer already computed this value for every question as `chapter_id`; BC5A hoisted it into
one helper so the **filter** and the **exposed field** can never disagree.

### Identity coverage (§6)

Read-only over the real `backend/app.db`, computed with the runtime helper itself
(`_question_chapter_code`), for all 4205 active chapter rows:

| Module | knowledge chapters (seed) | practice chapter groups | mapped groups | unmapped groups | ambiguous groups | chapters without questions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data_structure` | 8 | 31 | 31 | **0** | **0** | none |
| `computer_organization` | 7 | 28 | 28 | **0** | **0** | none |
| `operating_system` | 5 | 18 | 18 | **0** | **0** | none |
| `computer_network` | 6 | 142 | 142 | **0** | **0** | none |
| **total** | 26 | 219 | 219 | **0** | **0** | — |

```text
UNMAPPED_CHAPTER_GROUPS  = 0
AMBIGUOUS_CHAPTER_GROUPS = 0
```

No content rewrite and no DB migration were needed, so §6's STOP condition was not reached.

---

## 3. Four-module mapping proof

Runtime, all four modules, all 26 chapters, from the real bank (§34):

| Module | chapters | outline total | list total | Σ chapter counts | every chapter returns only its own rows | source types seen | question types seen |
| --- | ---: | ---: | ---: | ---: | :---: | --- | --- |
| `data_structure` | 8 | 1010 | 1010 | 1010 | yes | `chapter` | `choice`,`big` |
| `computer_organization` | 7 | 1200 | 1200 | 1200 | yes | `chapter` | `choice`,`big` |
| `operating_system` | 5 | 1120 | 1120 | 1120 | yes | `chapter` | `choice`,`big` |
| `computer_network` | 6 | 875 | 875 | 875 | yes | `chapter` | `choice`,`big` |

`GET …/questions?chapter_code=<N>` returns exactly the rows whose `chapter_id == N` for every one of
the 26 chapters, with `total == chapters[N].question_count` in each case.

`CANONICAL_CHAPTER_IDENTITY      = chapter_code (level-1 code, scoped by subject_key)`
`CHAPTER_IDENTITY_URL_SAFE        = YES (digits only)`
`CHAPTER_IDENTITY_MAPPING_COMPLETE= YES (4205/4205 rows, 26/26 chapters)`

---

## 4. Pre-submit leak audit

Inspected the actual runtime byte payload **before** typing anything.

### Found

`GET …/chapter-practice/questions` returned `{**_serialize_question_bank(item), "practiced": …}`.
`_serialize_question_bank` includes `standard_answer` and `analysis`, and the list endpoint never
stripped them:

| Module | items | non-empty `standard_answer` | non-empty `analysis` |
| --- | ---: | ---: | ---: |
| `data_structure` | 1010 | **1010 / 1010** | 0 / 1010 |
| `operating_system` | 1120 | **1120 / 1120** | 0 / 1120 |

So the correct answer was readable straight off the chapter-question network response.

```text
PRE_SUBMIT_ANSWER_LEAK      = PRESENT (4205/4205 rows)  →  0 after correction
PRE_SUBMIT_EXPLANATION_LEAK = key exposed, empty for all current chapter rows  →  0 after correction
```

### Compatibility investigation (§10)

| Question | Finding |
| --- | --- |
| Does an active consumer depend on it? | **No.** No frozen frontend code calls `/chapter-practice/*` (verified by grep over `frontend/src` and `frontend/tests`); no backend test asserts the field; the real `exam_practice_attempts` table is empty. |
| Does post-submit already provide it? | **Yes.** `submit` returns `standard_answer` + `analysis` per result, and the submitted attempt detail returns them per question. |
| Does a safe projection exist? | **Yes**, and the codebase already intended it: `get_chapter_practice_attempt` pops `standard_answer`/`analysis` while `status != "submitted"`. The list endpoint was an inconsistent omission. |

### Smallest safe correction applied

`_serialize_practice_question()` — the pre-submit projection used by the question list only. It drops
`standard_answer` and `analysis`; **everything else is byte-identical**. The attempt-detail handler's
existing pre-submit `pop()` was left exactly as it was.

Not done, on purpose: the question was **not** merely typed with the leak inside it, and the payload
was not rewritten into a new shape.

---

## 5. Question payload

Pre-submit `ExamPracticeQuestion` shape actually served (19 keys, all always present):

```text
id, subject_key, source_type, visibility, knowledge_point_id, knowledge_point_name,
knowledge_point_path, knowledge_points, chapter_id, chapter_name, year, question_number,
question_type, stem, options, difficulty, quality_status, created_at, practiced
```

Nullability taken from the real table (9333 rows): `year` is null on every chapter row, `question_number`
on 3330 of 4205, `knowledge_point_path` is an empty string on all 875 `computer_network` rows.
`knowledge_point_id`/`name`/`path` are typed `str | null` because the columns are nullable and an
attempt can outlive a deactivation; no reachable active chapter row is actually null.

Question text is **plain text** — no HTML, no Markdown, no JSON wrapper was found in any chapter
stem, option or analysis value.

```text
QUESTION_RENDERING_FORMAT = plain text
```

No chapter question carries an image, file reference or embedded figure field; nothing was invented
and no storage redesign was done. Asserted by test that no payload value contains a filesystem path.

```text
QUESTION_PAYLOAD = ExamPracticeQuestion (19 keys, no answer, no explanation)
QUESTION_TYPES   = Literal["choice","big"]
```

`Literal["choice","big"]` is not an assumption: the **entire** `exam_question_bank` table (9333/9333
rows) holds only `choice` and `big`, and `source_type` only `chapter` / `past_paper`. AI-generated
questions live in a different table, so they cannot enter an `ExamQuestionBank`-backed attempt
(verified live: `attempts` with AI ids → `400 no valid questions found`).

---

## 6. Question type semantics

| Type | Grading | Reference shown | Wrong record |
| --- | --- | --- | --- |
| `choice` | server-side, deterministic | post-submit | created / updated on incorrect |
| `big` | **none** — self-review | post-submit | never |

---

## 7. Practice request models

```python
class ExamPracticeAttemptCreateRequest(BaseModel):
    question_ids: list[int] = Field(default_factory=list)   # defaulted so an omitted/empty
    username: str | None = None                            # list keeps the handler's own 400
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    knowledge_point_path: str | None = None

class ExamPracticeWriteRequest(BaseModel):                 # shared by answers + submit
    answers: dict[str, str] = Field(default_factory=dict)
    username: str | None = None
```

* No `dict`, `Dict[str, Any]` or `Any` on the transport surface. The remaining typed map is
  `answers`, whose **value side is closed to `str`** because the server coerces with `str(...)` before
  grading and the only known producer sends option letters / free text.
* Accepted runtime input is preserved: the legacy `username` echo still works, a bare `{}` body still
  saves an empty answer set, and omitting `question_ids` still answers **400** (not 422).
* `request_username` already accepted an object with attributes, so the legacy username-spoofing
  403/404 semantics are unchanged (their test still passes).

`PRACTICE_WRITE_REQUESTS_TYPED = PASS`

---

## 8. Attempt lifecycle

```text
ATTEMPT_IDENTITY  = ExamPracticeAttempt.id   (no new session table was added)
ATTEMPT_PERSISTENCE = PASS
ATTEMPT_RELOAD      = PASS
```

* creation → `status="in_progress"`, `question_ids_json` snapshot, `total_questions`
* answer persistence → `answers_json` (only while `in_progress`)
* submit → `status="submitted"`, `submitted_at`, `correct_count`, `wrong_count`, `accuracy`, `result_json`
* reload → detail replays `question_ids_json` + `answers_json`; the question set and the saved answers
  both survive a re-read
* resubmit → **404** (one-time), unchanged

Fact-first persistence: the attempt row, the result, and the done records are committed **before** the
practice-core mirror runs, and the mirror is wrapped in its own `try/except` that only logs. A mirror
failure cannot remove the persisted attempt. No AI participates in this path.

`QUESTION_ORDER_STABILITY = CURRENT_BEHAVIOR` — the stored id set exists, but retrieval uses
`IN (...)` and does not restore the stored order. Deliberately **not** fixed here (§22); F1C2D decides.

---

## 9. Deterministic grading

Proved with `main._exam_ai_content` monkeypatched to raise:

* `"a"` against standard `"A"` → **correct** (case-insensitive)
* `"B"` against standard `"b"` → **correct**
* `"D"` against standard `"A"` → **incorrect**
* no provider/orchestrator call is reachable from the submit path at all

```text
DETERMINISTIC_GRADING                = PASS
DETERMINISTIC_GRADE_PROVIDER_CALLS   = 0
FRONTEND_DETERMINISTIC_GRADING_REQUIRED = NO
```

The frontend never needs the correct answer to grade — it does not receive it pre-submit.

---

## 10. Big / self-review

Actual runtime semantics, now typed as `ExamBigPracticeResult`:

* the learner's free text is submitted and persisted (`user_answer`)
* `correct` is `null`
* `judge` is the literal `"self_review"`
* the static reference answer is returned as `standard_answer`
* `hint` is `"请自行对照参考答案"`
* the question never enters the wrong book and never counts toward `choice_total` / `accuracy`
* `answer.grade` is **not** introduced — F1C2 does not need it for the current bank

```text
BIG_SELF_REVIEW_SEMANTICS = PASS
```

---

## 11. Wrong-record behaviour

Unchanged and re-proved:

| Scenario | Observed |
| --- | --- |
| first incorrect `choice` | exactly **1** active `ExamWrongQuestion` for the user/question; `mistake_saved_count` +1 |
| repeated incorrect | still **1** active row; `review_count` increments (0 → 1), no duplicate |
| `big` answer | **no** wrong record at all |
| submit response | returns only the counts |

```text
WRONG_RECORD_BEHAVIOR             = unchanged (upsert one active row, review_count on repeat)
FRONTEND_WRONG_RECORD_WRITE_REQUIRED = NO
CORRECT_RETRY_AUTO_RESOLVES_WRONG = not guaranteed by this endpoint
```

Per §25 the response was **not** given `wrong_recorded` / `resolved` fields it does not guarantee —
asserted by test that those keys are absent, so F1C2B must not claim "已记录到错题 / 已解决" from this
contract. The unified wrong-answer **adapter** does resolve on a later correct answer
(`test_practice_adapters`), but the legacy endpoint itself does not state that, so BC5A does not
type it as a guarantee. Wrong storage was not redesigned.

---

## 12. Knowledge-status boundary

`UserKnowledgeProgress` count is **0** after a fully correct chapter submission.

```text
CORRECT_ANSWER_AUTO_MARK_MASTERED = NO
```

The practice mirror writes `service_namespace = exam_prep` / subject `cs_408` events only. Behaviour
untouched.

---

## 13. Runtime equivalence

Method: fresh TEMP copy of `app.db` → standalone uvicorn (8944 before / 8945 after) → identical probe
script → canonical JSON path-by-path diff.

```text
total differing paths: 4941   (volatile ids/timestamps: 54, structural: 4887)
```

| Difference class | Paths | Verdict |
| --- | ---: | --- |
| `outline.chapters` | 2 | **ADDITIVE** — new field, no existing key touched |
| `questions*.items[*].standard_answer` / `.analysis` | 4885 | **SECURITY CONTRACT CORRECTION** — removed |
| `wrong_questions` row ordering | 14 | pre-existing `IN (...)` non-determinism; endpoint is outside BC5A scope |
| attempt ids / timestamps | 54 | volatile |
| probe-script artifact | 1 | not a product payload |

Everything else is **byte-identical**, including:

* `POST …/submit` for both modules — canonical JSON equality holds exactly
  (`results` choice/big key sets, counts, `accuracy`, `mistake_saved_count` all equal)
* `POST …/attempts` (modulo `attempt_id`), `…/answers` `{"success": true}`
* `GET …/attempts/{id}` pre-submit, post-submit and after answer-save (modulo id/timestamp)
* resubmit `404 {"detail":"Attempt not found"}`

```text
RUNTIME_RESPONSE_CHANGED = YES — SECURITY CONTRACT CORRECTION
   removed:   standard_answer, analysis   (chapter question list only)
   added:     outline.chapters            (additive)
   added:     optional query chapter_code (additive, empty default)
```

Both runtime changes are reported here rather than hidden under "typing". Compatibility proof: the
only consumer of these endpoints going forward is F1C2B, which does not exist yet; the earlier
section (§4) records why no other consumer breaks.

---

## 14. OpenAPI

All six core operations now declare concrete schemas:

```text
GET  …/chapter-practice/outline               200 → ExamChapterPracticeOutlineResponse
GET  …/chapter-practice/questions             200 → ExamChapterPracticeQuestionsResponse
POST …/chapter-practice/attempts              body ExamPracticeAttemptCreateRequest
                                              200 → ExamPracticeAttemptCreateResponse
GET  …/chapter-practice/attempts/{attempt_id} 200 → ExamPracticeAttemptDetailResponse
POST …/attempts/{attempt_id}/answers           body ExamPracticeWriteRequest
                                              200 → ExamPracticeAnswerSaveResponse
POST …/attempts/{attempt_id}/submit            body ExamPracticeWriteRequest
                                              200 → ExamPracticeSubmitResponse
```

Notable generated facts:

* `results` → `oneOf` + `discriminator: {propertyName: question_type}` over `ExamChoicePracticeResult` /
  `ExamBigPracticeResult`
* `question_type` → `enum ["choice","big"]`; attempt `status` → `enum ["in_progress","submitted"]`
* `ExamPracticeAttemptQuestion.required` lists 18 fields — `standard_answer` / `analysis` are
  genuinely optional (absent pre-submit), and `ExamPracticeQuestion` declares neither field at all
* `additionalProperties: false` throughout (`extra="forbid"`)
* error contracts unchanged: `422 HTTPValidationError`, plus the pre-existing untyped
  `400 / 401 / 403 / 404`

```text
PRACTICE_CORE_SUCCESS_UNKNOWN = 0
PRACTICE_CORE_REQUEST_UNKNOWN = 0
```

Spelled-out exception: `ExamChapterPracticeOutlineResponse.knowledge_points` stays a typed
`dict[str, int]` — the key set is open module content (226 real `knowledge_point_id` values), so it
cannot be closed into a model. `chapters` is the typed level above it.

---

## 15. Generated TypeScript

Regenerated with the repo's existing generator — `openapi-typescript@7.13.0`, the same tool and
version `npm run api:generate` uses — from the **current source** spec fetched off a live backend on
port **8946**:

```bash
npx openapi-typescript <temp>/openapi.json -o src/types/api.ts
✨ openapi-typescript 7.13.0 · 275.5ms · exit 0
```

`package.json` was **not** changed (its `api:generate` still points at stale `localhost:8000`, as
BC1–BC4 recorded). `api.ts` was not hand-edited; the auto-generated header is intact.

Diff attribution: the regenerated file also carries **pre-existing** drift that predates BC5A — the
working tree's backend had already added 29 operations (exam-prep catalog, practice sessions,
subscription/usage, learning records, wrong answers) and renamed
`get_learning_records_learning_records_get` → `list_records_learning_records_get`, none of which this
task touched. Verified: no frozen frontend file references the renamed or removed operation. The
BC5A-attributable delta is the six chapter-practice operations plus their schemas.

### Generated type probe (§33)

Made permanent as `frontend/src/features/exam/api/practice-contract.test.ts` (4 tests, passing). It
resolves every alias through the generated `paths` / `components` and demonstrates, with **zero casts
and zero handwritten DTOs**, access to:

* canonical chapter identity — `chapter.chapter_code`, `chapter_no`, `chapter_title`, `question_count`
* question id / type / stem / options — `question.id`, `.question_type`, `.stem`, `.options`
* attempt id and reloaded state — `detail.attempt.id`, `.attempt.status`, `.saved_answers[id]`
* submit grading state — `correct_count`, `wrong_count`, `accuracy`, and the narrowed union
  (`question_type === 'big'` → `judge`, `hint`; else → `analysis`)
* post-submit static explanation — `AttemptQuestion.analysis`

The pre-submit leak is enforced at **type level** with `@ts-expect-error` on
`question.standard_answer` / `question.analysis` / `question.correct`: those directives only pass
because the fields genuinely do not exist, so a future contract that puts the answer back on the
pre-submit payload breaks `npm run typecheck` loudly.

```text
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

---

## 16. Real runtime QA

Standalone uvicorn processes (ports **8944 / 8945 / 8946**, never 8000) with explicit TEMP
`DATABASE_URL` copies of the real bank; a real registered+verified user; `data_structure` and
`operating_system` exercised end to end.

| Scenario | Result |
| --- | --- |
| chapter outline | 200; `chapters` sums to `total` for all 4 modules |
| chapter question list | 200; source `chapter` only; no answer / explanation |
| chapter-scoped load (`chapter_code=1`) | 200; only chapter-1 rows |
| choice attempt (create → detail → save → detail) | 200; saved answers replay |
| correct choice | `correct: true` |
| incorrect choice | `correct: false`; wrong upsert; `review_count` on repeat |
| big / self-review attempt | `correct: null`, `judge: "self_review"`, static reference returned |
| attempt reload (pre and post) | 200; question set + saved answers intact |
| resubmit | 404 |

```text
PAST_PAPER_LEAK_IN_CHAPTER_PRACTICE = 0
```

(Server logs: 0 × HTTP 500 across every probe run.)

---

## 17. DB safety

`backend/app.db` was opened **only** through SQLite URI `mode=ro`. All live runs used TEMP copies.

| Check | Before | After |
| --- | --- | --- |
| SHA256 | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | identical |
| mtime | 2026-09-16 21:24:23.896 | identical |
| size | 64,917,504 | identical |
| `PRAGMA integrity_check` | `ok` | `ok` |
| table count | 72 | 72 |
| `exam_question_bank` | 9333 | 9333 |
| `programming_exercises` | 1923 | 1923 |
| `knowledge_points` | 32 | 32 |

```text
REAL_APP_DB_MUTATED = NO
DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
```

No `chapter_code` column was added to the 9333 questions. The identity is derived from existing
static knowledge-map metadata (per §7) and from the page's own module scope.

---

## 18. Tests

New: `backend/tests/test_bc5a_chapter_practice_contract.py` — **37 passed**, covering all 25 items
required by §36: canonical chapter identity coverage, all four module mappings, no
ambiguous/unmapped chapter, outline schema, question-list schema, concrete request models, all four
write/detail success responses, choice deterministic grading, provider calls = 0, big self-review,
incorrect wrong upsert, repeated wrong, no knowledge-mastery side effect, `source_type` chapter only,
past-paper excluded, answer leak = 0, explanation leak = 0, post-submit explanation, nullable
analysis, attempt reload, pinned pre-submit key set (runtime-equivalence for the typed portions),
and the real DB untouched.

New: `frontend/src/features/exam/api/practice-contract.test.ts` — **4 passed** (§15).

Regression:

```text
TARGETED_TESTS     = 37 passed / 0 failed
FULL_BACKEND_TESTS = 1049 passed / 0 failed   (baseline 1012 + 37 new)

FRONTEND_TYPECHECK   = PASS
FRONTEND_LINT        = PASS
FRONTEND_UNIT_TESTS  = PASS (11 files / 28 tests)
FRONTEND_BUILD       = PASS
```

---

## 19. Final gates

```text
CANONICAL_CHAPTER_IDENTITY            = PRESENT
CHAPTER_IDENTITY_URL_SAFE             = YES
CHAPTER_IDENTITY_MAPPING_COMPLETE     = YES
UNMAPPED_CHAPTER_GROUPS               = 0
AMBIGUOUS_CHAPTER_GROUPS              = 0

CANONICAL_QUESTION_IDENTITY           = ExamQuestionBank.id

CHAPTER_OUTLINE_TYPED                 = PASS
CHAPTER_QUESTION_LIST_TYPED           = PASS
PRACTICE_WRITE_REQUESTS_TYPED         = PASS
ATTEMPT_CREATE_TYPED                  = PASS
ATTEMPT_DETAIL_TYPED                  = PASS
ANSWER_SAVE_TYPED                     = PASS
SUBMIT_TYPED                          = PASS
QUESTION_PAYLOAD_TYPED                = PASS

PRE_SUBMIT_ANSWER_LEAK                = 0
PRE_SUBMIT_EXPLANATION_LEAK           = 0
PAST_PAPER_LEAK_IN_CHAPTER_PRACTICE   = 0

DETERMINISTIC_GRADING                 = PASS
DETERMINISTIC_GRADE_PROVIDER_CALLS    = 0
BIG_SELF_REVIEW_SEMANTICS             = PASS
ATTEMPT_PERSISTENCE                   = PASS

FRONTEND_WRONG_RECORD_WRITE_REQUIRED  = NO
CORRECT_ANSWER_AUTO_MARK_MASTERED     = NO

PRACTICE_CORE_SUCCESS_UNKNOWN         = 0
PRACTICE_CORE_REQUEST_UNKNOWN         = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO   = 0

DB_SCHEMA_CHANGED                     = NO
MIGRATION_ADDED                       = NO
REAL_APP_DB_MUTATED                   = NO

FULL_BACKEND_TESTS                    = PASS
FRONTEND_TYPECHECK                    = PASS
FRONTEND_LINT                         = PASS
FRONTEND_UNIT_TESTS                   = PASS
FRONTEND_BUILD                        = PASS

F1C2B_BACKEND_CONTRACT_READY          = YES
```

---

## Files changed

| File | Change |
| --- | --- |
| `backend/main.py` | `Annotated`/`Field` imports; `_parse_question_source_meta` + `_question_chapter_code` helpers (serializer refactored onto them); `_serialize_practice_question` pre-submit projection; `_chapter_seed_meta` + `_chapter_catalog`; the BC5A model block; all six handlers typed, `chapter_code` query added, outline `chapters` added |
| `backend/tests/test_bc5a_chapter_practice_contract.py` | new — 37 tests |
| `frontend/src/types/api.ts` | regenerated (not hand-edited) |
| `frontend/src/features/exam/api/practice-contract.test.ts` | new — permanent compile-level contract probe |

Out of scope and untouched, as required: `question.explain`, `answer.grade`, unseen-first ordering,
server-side 10/20/random selection, session analytics, practice summary, new session DB entity,
`F1C1` UI, `F1B2` UI. Nothing was committed, merged, rebased or pushed.

## Carried forward (not blockers)

1. `QUESTION_ORDER_STABILITY = CURRENT_BEHAVIOR` — the attempt restores the question **set**, not the
   stored order. F1C2D decides whether a bounded ordering fix is needed.
2. `UNSEEN_FIRST_SUPPORTED = NO` (per-question `practiced` only) and `SESSION_SIZE_SUPPORT = NONE`
   (no `limit` / page / seed) — both deliberately deferred to F1C2D.
3. `CORRECT_RETRY_AUTO_RESOLVES_WRONG` is demonstrated by the unified adapter tests but is **not**
   stated by this endpoint, so it is not in the typed contract; the frontend must not claim it.
4. `ExamPracticeAttemptCreateRequest` still accepts any active question-bank id, so a caller could put
   a `past_paper` row into a chapter attempt. The response model tolerates it (both types are
   `choice|big`), and no UI path does this. Closing it would change currently-accepted input, which
   §15 forbids, so it is left as-is and recorded here.
5. The regenerated `api.ts` also carries the pre-existing working-tree drift (29 unrelated
   operations) described in §15. That is not a BC5A change and not a regression.
