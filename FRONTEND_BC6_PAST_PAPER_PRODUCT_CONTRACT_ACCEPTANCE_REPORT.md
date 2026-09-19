# FRONTEND_BC6 — CS408 Past Paper Product Contract Acceptance Report

Date: 2026-09-19.
Mode: backend architecture closure. No frontend UI was implemented.

```text
FRONTEND_BC6_COMPLETE
F1C3_FRONTEND_READY = YES
REMAINING_BLOCKERS = NONE
DB_SCHEMA_CHANGED = NO     MIGRATION_ADDED = NO     REAL_APP_DB_MUTATED = NO
```

BC6 answers the five blockers F1C3A raised, and does it as a product contract rather than an
endpoint patch: one public identity, one normalized question shape, server-side security
projection, submitted-result replay, valid subjective semantics and reachable figures — with both
real sources preserved.

---

## 1. Dual-source architecture

Two real sources exist and **both are kept**. Neither was deleted, migrated or duplicated.

| | bank | document |
| --- | --- | --- |
| Storage | `exam_question_bank` where `source_type='past_paper' AND is_active` | `11408_2022_2026_*.docx` + `cache/exam_papers/11408/{subject}/{year}.ocr.json` |
| Active rows | 170 (co 65 · os 60 · cn 45) | co 65 · os 60 · cn 45 · **ds 65** |
| Internal question id | `ExamQuestionBank.id` (int) | `"{subject}_{year}_{number}"` |
| Owns | computer_organization, operating_system, computer_network | **data_structure** |

Which source answers is decided **per paper**, by the rule the runtime already used — the bank
answers when it has active rows for that `(subject, year)`, otherwise the document source does. That
is reconciliation (the bank rows were derived from the document material), not an arbitrary pick,
and it is why no public key is ever claimed twice.

```
BANK_SOURCE     = exam_question_bank (source_type='past_paper', is_active=1)
DOCUMENT_SOURCE = docx parse + OCR cache; the only source carrying data_structure
SOURCE_NORMALIZATION = exam_past_paper.resolve_paper() — one adapter at the product boundary
```

`data_structure` remains fully dependent on the document source and is unharmed: it resolves
5 papers × 13 questions, served through exactly the same public shape as a bank paper.

## 2. Canonical identity

```
PAST_PAPER_PUBLIC_PAPER_IDENTITY    = (subject_key, year)
PAST_PAPER_PUBLIC_QUESTION_IDENTITY = (subject_key, year, question_number)
```

Every public question carries `subject_key`, `year` and `question_number` as first-class fields.
No source id and no array index reaches the client — asserted by `@ts-expect-error` in the frontend
compile probe (`question.id` does not type-check).

```text
UNMAPPED_PUBLIC_QUESTION_KEYS  = 0
AMBIGUOUS_PUBLIC_QUESTION_KEYS = 0
DUPLICATE_PUBLIC_QUESTION_KEYS = 0
```

Proved two ways: a Python sweep over every paper of every subject asserting uniqueness, and a
runtime sweep. `ExamQuestionBank.id` and the document string id remain internal only.

## 3. Normalized public model

One shape, whichever source answered (`exam_past_paper.PastPaperQuestion`):

```
subject_key · year · question_number · question_type ∈ {choice, big}
stem · options · resources[] · full_score · missing_resources[]
```

`question_type` is closed to `choice` / `big` because that is what the real data contains in both
sources (choice 145 / big 25 on the bank; the document source uses 选择题 / 大题 and maps onto the
same pair). `full_score` is factual paper metadata (2 / 10), not a learner score. `resources`
contains only references that resolve on disk; `missing_resources` names any expected figure that
does not, so "no figure" and "figure broken" are never the same payload.

## 4. Security

Answer-bearing reads now require a session, and the projection happens **server-side, once**, in
`public_question` — the model itself has no answer field, so no source can leak through it.

```
PRE_SUBMIT_ANSWER_LEAK         = 0
PRE_SUBMIT_EXPLANATION_LEAK    = 0
PRE_SUBMIT_GRADING_RESULT_LEAK = 0
ANONYMOUS_STANDARD_ANSWER_DISCLOSURE = 0
```

Measured on a live server, both sources, by walking the whole payload for any of
`standard_answer / answer / analysis / review_notes / correct / judge / score`:

```
question list  (data_structure, document)  -> no protected key
question list  (computer_organization, bank) -> no protected key
attempt detail while in_progress, both       -> no protected key, and no `results` key
anonymous GET past-paper-questions           -> 401
anonymous GET past-papers                    -> 401
anonymous GET past-paper-images/...          -> 401
```

`PRE_SUBMIT_LEAK_TOTAL = 0`, `ANONYMOUS_DISCLOSURE = 0`. The generated schema cannot express a
pre-submit answer either: the test asserts `PastPaperQuestion.model_fields` is disjoint from the
protected set.

## 5. Attempt lifecycle

Past papers keep their **own** attempt subsystem (`PastPaperAttempt`) — chapter-practice semantics
are not reused, and no new table was added.

| Step | Endpoint | Persistence |
| --- | --- | --- |
| create | `POST …/past-paper-attempts` | inserts `PastPaperAttempt(status='in_progress', attempt_no=last+1, total_questions)` |
| save | `POST …/{id}/answers` | writes `answers_json`, keyed by public question number |
| submit | `POST …/{id}/submit` | grades once, writes scores + `result_json`, wrong book, done records, Practice Core mirror |
| detail | `GET …/{id}` | replays `result_json` when submitted; never grades |

Answers are keyed by **public question number** on both the wire and the persisted
`saved_answers`. The adapter maps them into whatever id space the owning source uses, so the
document source's internal ids (`data_structure_2022_1`) never surface.

## 6. Result replay

`PastPaperAttemptDetailResponse.results` is present once `attempt.status == 'submitted'` and is a
byte-for-byte replay of what submit persisted, re-keyed onto the public identity.

```
detail(post) : has_results=True  n_results=13
replay == submit results: True        (document source, data_structure)
replay == submit results: True        (bank source, computer_organization)
```

```text
SUBMITTED_RESULT_REPLAY = PASS
PAST_PAPER_DETAIL_REGRADES = NO
```

Two independent proofs that the read path does not grade: flipping the persisted verdict in
`result_json` and observing the GET return the flipped value (only a replay can), and a source
guard asserting `get_past_paper_attempt` contains no `grade_submission` / `grade_big`.

## 7. Objective grading

Choice questions are graded by the backend, deterministically, with zero provider calls:

```
q12 correct=True  judge=None  score=2/2     (correct answer submitted)
q602 correct=False judge=None score=0/2     (wrong answer submitted)
answer_grade = {applied: false, reason: "deterministic_bank_grading"}
```

```text
OBJECTIVE_GRADING = deterministic, backend-owned, provider-free
```

## 8. Subjective / self-review semantics

**The fabricated midpoint is gone.** A subjective answer is now either authoritatively AI-graded
(real score kept, `judge = ai_graded`) or self-review (`judge = self_review`, `correct = null`,
**`score = null`**). Reference answer and factual `full_score` remain available post-submit.

```
big result : correct=None judge=self_review score=None full_score=10 ref_len=631   (bank)
big result : correct=None judge=self_review score=None full_score=10 ref_len=31    (document)
answer_grade = {applied: false, reason: "answer_grade_unavailable_403"}   (free tier, document path)
```

```text
SUBJECTIVE_NO_AI_GRADE_BEHAVIOR = self_review (correct=null, score omitted)
FAKE_MIDPOINT_SCORE = 0
```

An ungraded subjective answer is also **not** written to the wrong book — it is not a wrong answer.
The genuine AI-grade path is preserved and still uses its real score (the frozen
`test_ai_grade_path_uses_the_result_and_settles_it` asserts `score == 8` and still passes), now
labelled `judge = "ai_graded"` so the frontend can tell the two apart without inferring anything.

`answer_grade` keeps its existing runtime shape (`{applied, reason}`) rather than inventing a new
one — no new enum was added beyond the two judge values, both of which describe states the runtime
already produced.

## 9. Static analysis reality

168 of 170 active bank rows have no analysis, and the document source has none either. Analysis is
therefore optional end-to-end:

```
analysis "BC6 解析一" -> "BC6 解析一"
analysis ""           -> null            (absent, never manufactured)
```

`PastPaperQuestionResult.analysis` is `str | None`, and a submission succeeds regardless.
`STATIC_ANALYSIS_COVERAGE = 2 / 170 bank rows (1.2%); the document source carries none.`

## 10. Image asset matrix

```
FIGURE_REFERENCING_QUESTIONS = 31 bank rows whose stem references 图
                                (235 questions carry at least one asset across both sources)
ASSETS_FOUND                 = 31 of 31; 281 of 281 resource references resolve on disk
ASSETS_GENUINELY_MISSING     = 0
HTTP_RESOURCE_REACHABLE      = PASS  (281 / 281 advertised resources served 200 over HTTP)
MISSING_ASSET_HANDLED_EXPLICITLY = PASS
```

Forensics found the assets in **four** locations, which is why delivery was broken:

| Layout | Subject | Count |
| --- | --- | --- |
| `exam_resources/11408/{s}/past_papers/assets/{year}/q{n}_{i}.jpg` | computer_organization | 80 |
| `exam_resources/11408/{s}/past_papers/images/…` | operating_system, computer_network | 127 |
| `static/exam_papers/11408/{s}/{year}/img_{i}.jpg` | **all four**, incl. data_structure | 564 |

Three delivery defects were repaired with minimal change, none by fabrication:

* **Extension mismatch.** `operating_system`'s curated `image_mapping.json` names `2022_23_0.jpg`
  while the real file is `2022_23_0.jpeg`. Resolution now retries the same stem across the known
  image extensions, so the existing file is delivered.
* **Missing mapping.** `computer_organization` ships 80 assets in a deterministic
  `q{number}_{index}.jpg` layout but has **no `image_mapping.json` at all** — 20 stem-referencing
  questions had no asset reference. Resolution now derives filenames from the on-disk convention,
  anchored to the exact year and question number, when the curated mapping is silent.
* **Cross-source figure (the Q46 recovery).** `operating_system` 2022 Q46 is owned by the **bank**
  source, which had no mapping entry and no `2022_46_*` file — so it looked genuinely absent. The
  **document** source for the same paper references `.../2022/img_14.jpg`, and that file exists on
  disk. Resolution now falls back to the document source's `image_urls` for the same
  `(subject, year, question_number)`. The figure is real, already on disk, and untouched: only the
  resolution order changed, and `2022-46` was added to the curated mapping so the fact is recorded
  where the curated facts live.

Q46 verified end to end:

```
GET /exam/11408/operating_system/past-paper-questions?year=2022  -> q46.resources =
    ["/exam/11408/past-paper-images/operating_system/2022/img_14.jpg"]   missing_resources = []
GET /exam/11408/past-paper-images/operating_system/2022/img_14.jpg  -> 200  image/jpeg  76276 bytes
```

### Honest missing-resource state

Nothing is missing today, but `resources: []` alone was ambiguous — "this question has no figure"
and "its figure is broken" would have looked identical to F1C3. `PastPaperQuestion` therefore
carries `missing_resources: string[]`, and a resource enters `resources` **only when it resolves on
disk**. A future broken reference surfaces in the contract as an explicit missing entry instead of a
404 behind an `<img>`, which is the state F1C3 must render honestly ("该题资源缺失，暂不可作答").
Measured today: `missing_resources` totals 0 across all 235 questions, and **0 advertised resources
fail to serve**.

## 11. Resource delivery contract

One URL format for every source and both environments:

```
/exam/11408/past-paper-images/{subject_key}/{year}/{filename}      (relative to the API base URL)
```

Deliberately relative, so the *same* string works locally (`baseUrl = http://127.0.0.1:8000`) and
behind nginx (`baseUrl = /api`, which strips the prefix — `deploy/nginx-ai-study-platform.conf.example`
proxies `/api/` to `127.0.0.1:8000/`). The historical `/static/exam_papers/...` and
`/api/exam/...` forms are normalized into this one shape by the adapter.

```text
HTTP 200 image/jpeg  data_structure/2022/img_0.jpg            (document source)
HTTP 200 image/jpeg  computer_organization/2022/q12_0.jpg     (bank, derived)
HTTP 200 image/jpeg  operating_system/2022/2022_23_0.jpg      (bank, extension repaired)
HTTP 200 image/jpeg  computer_network/2022/2022_q34_1.jpg     (bank, curated)
```

**The `/static/exam_papers` mount stays commented out.** The nginx example serves the SPA at `/` and
proxies only `/api/`, so uncommenting it would not have fixed production and would have added a
second URL format. Delivery goes through the application route instead, which works in both
environments.

Safety: the filename must match `^[A-Za-z0-9._-]+$`, the subject must be known, and the resolved
path must stay inside its allowed root. No filesystem path is ever returned to the client.

```
traversal: 404  ..%2F..%2Fapp.db · ....//app.db · %2e%2e%2fmain.py · main.py · x.txt
```

## 12. OpenAPI

```
PAST_PAPER_REQUIRED_SUCCESS_UNKNOWN = 0
PAST_PAPER_REQUIRED_REQUEST_UNKNOWN = 0
```

| Endpoint | Response model | Request model |
| --- | --- | --- |
| `GET …/past-papers` | `PastPaperIndexResponse` | — |
| `GET …/past-paper-questions` | `PastPaperQuestionsResponse` | — (query `year`) |
| `POST …/past-paper-attempts` | `PastPaperAttemptCreateResponse` | `PastPaperAttemptCreateRequest` |
| `GET …/past-paper-attempts/{id}` | `PastPaperAttemptDetailResponse` | — |
| `POST …/{id}/answers` | `PastPaperAnswerSaveResponse` | `PastPaperWriteRequest` |
| `POST …/{id}/submit` | `PastPaperSubmitResponse` | `PastPaperWriteRequest` |
| `GET …/past-paper-images/…` | `image/jpeg · png · webp · gif` | — |

14 new schemas. No `Any`, no `dict[str, Any]`, no unknown core transport. The image route declares
binary content types rather than an empty JSON schema.

## 13. Generated TypeScript

`frontend/src/types/api.ts` regenerated with the project's own `openapi-typescript 7.13.0` from a
**current** spec served on port **8954** with an explicit TEMP `DATABASE_URL` — never 8000, and
`package.json` untouched. The whole diff is past-paper: 22 removed lines are exactly the old
`unknown` bodies and stale docstrings, 302 added lines are the new schemas. No unrelated drift.

`HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0` — the compile probe
(`src/features/exam/api/past-paper-contract.test.ts`, 5 tests) resolves every alias through the
generated `paths` / `components` and proves the types can express the paper index, a normalized
pre-submit question, attempt create, answer save, submit result, submitted replay and a resource
reference. `@ts-expect-error` proves a pre-submit question carries no `standard_answer`, no
`analysis`, no `correct` and no source `id`.

## 14. Runtime VQA

Live server on port **8954**, TEMP copy of the real DB, real `POST /login` session, both sources:

| | data_structure (document) | computer_organization (bank) |
| --- | --- | --- |
| paper index | 2022–2026, 13 q each, source=document | 2022–2026, 13 q each, source=bank |
| question list | 200, 13 q, no leak | 200, 13 q, no leak |
| create | 200, total=13 | 200, total=13 |
| pre-submit detail | no leak, no `results` | no leak, no `results` |
| save | 200 | 200 |
| submit | 200, self_review 2, `answer_grade_unavailable_403` | 200, self_review 2, `deterministic_bank_grading` |
| big result | correct=None judge=self_review score=None | correct=None judge=self_review score=None |
| replay | `results` == submit results | `results` == submit results |
| keyed by | question numbers 1…13 | question numbers 12…44 |
| figure | 200 image/jpeg | 200 image/jpeg |

## 15. Database safety

| Measure | Value |
| --- | --- |
| SHA256 | `1c1b2d85…3fe522` — identical to baseline |
| size | `64917504` — identical |
| mtime | `2026-09-16 21:24:23` — identical |
| `integrity_check` / `quick_check` | `ok` / `ok` |
| table count | 72 |
| protected counts | `exam_question_bank` 9333, `programming_exercises` 1923, `knowledge_points` 32 |
| `exam_practice_attempts` / `exam_wrong_questions` | 0 / 0 |
| `past_paper_attempts` / `past_paper_wrong_questions` | 0 / 0 |
| `app.db-wal` | 0 bytes |

All write probes ran against `%TEMP%\f1c3a\vqa.db`; the real file was only ever opened `?mode=ro`.
`migrations/versions/` is untouched (newest file 2026-09-17, before this task).

```text
DB_SCHEMA_CHANGED = NO     MIGRATION_ADDED = NO     REAL_APP_DB_MUTATED = NO
```

## 16. Tests

New: `tests/test_bc6_past_paper_contract.py` — **24 tests** covering the full 20-item matrix:
identity uniqueness across both sources, both sources exercised, factual index, anonymous refusal,
pre-submit leak on the list and the detail for both sources, schema-level leak prevention,
deterministic objective grading, self-review fallback with no midpoint, ungraded ≠ wrong,
optional analysis, submitted replay, no-regrade tamper proof + source guard, empty pre-submit
results, safe resource URL, reachable figure, traversal rejection, source isolation, wrong-record
ownership, no mastery write, attempt ownership, public-number keying, concrete OpenAPI.

Final full backend regression: **1126 passed / 0 failed** (baseline 1099 + 27 BC6).

Adjusted (contract changed by design, not weakened):
`tests/test_exam_ai_orchestrator.py` — three submits moved from the old list body
`[{"question_id", "user_answer"}]` to the normalized `{"<question_number>": "answer"}`; the
boundary-hygiene test's allowed markers now accept `exam_past_paper` (the shared adapter the read
endpoints delegate to). Its assertions about `answer_grade`, the AI score being used, zero provider
calls on the deterministic path and the free-tier refusal all still hold unchanged.

Frontend: `src/features/exam/api/past-paper-contract.test.ts` (5 tests).

## 17. Final gates

```text
FRONTEND_BC6_COMPLETE

PAST_PAPER_PUBLIC_PAPER_IDENTITY    = (subject_key, year)
PAST_PAPER_PUBLIC_QUESTION_IDENTITY = (subject_key, year, question_number)

SOURCE_NORMALIZATION = exam_past_paper adapter at the product boundary; per-paper source selection
BANK_SOURCE          = exam_question_bank — computer_organization, operating_system, computer_network
DOCUMENT_SOURCE      = docx + OCR cache — data_structure (preserved, not migrated, not duplicated)

UNMAPPED_PUBLIC_QUESTION_KEYS  = 0
AMBIGUOUS_PUBLIC_QUESTION_KEYS = 0
DUPLICATE_PUBLIC_QUESTION_KEYS = 0
PUBLIC_IDENTITY_NORMALIZED     = PASS

PRE_SUBMIT_ANSWER_LEAK         = 0
PRE_SUBMIT_EXPLANATION_LEAK    = 0
PRE_SUBMIT_GRADING_RESULT_LEAK = 0
ANONYMOUS_STANDARD_ANSWER_DISCLOSURE = 0

SUBMITTED_RESULT_REPLAY    = PASS
PAST_PAPER_DETAIL_REGRADES = NO

OBJECTIVE_GRADING               = deterministic, backend-owned, provider-free
SUBJECTIVE_NO_AI_GRADE_BEHAVIOR = self_review (correct=null, score omitted, reference answer kept)
FAKE_MIDPOINT_SCORE             = 0

STATIC_ANALYSIS_COVERAGE = 2 / 170 bank rows; optional and nullable end-to-end

FIGURE_REFERENCING_QUESTIONS = 31 (stem references 图); 235 questions carry assets overall
ASSETS_FOUND                 = 31 of 31 stem-referencing; 281 / 281 references resolve
ASSETS_GENUINELY_MISSING     = 0
HTTP_RESOURCE_REACHABLE      = PASS
ALL_RENDERABLE_ASSETS_HTTP_REACHABLE = PASS  (281 / 281 advertised resources serve 200)
MISSING_ASSET_HANDLED_EXPLICITLY = PASS  (PastPaperQuestion.missing_resources)
IMAGE_RESOURCE_CONTRACT      = /exam/11408/past-paper-images/{subject}/{year}/{filename}, API-base relative

YEAR_INDEX          = READY
PAPER_QUESTION_LIST = READY
ATTEMPT_CREATE      = READY
ANSWER_SAVE         = READY
SUBMIT              = READY
ATTEMPT_RELOAD      = READY

WRONG_RECORD_BEHAVIOR             = backend-owned on submit (past_paper_wrong_questions)
CORRECT_ANSWER_AUTO_MARK_MASTERED = NO

PAST_PAPER_REQUIRED_SUCCESS_UNKNOWN = 0
PAST_PAPER_REQUIRED_REQUEST_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0

DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
REAL_APP_DB_MUTATED = NO

TARGETED_TESTS     = 27 BC6 passed
FULL_BACKEND_TESTS = 1126 passed / 0 failed   (baseline 1099 + 27 BC6)

FRONTEND_TYPECHECK   = PASS
FRONTEND_LINT        = PASS
FRONTEND_UNIT_TESTS  = PASS (15 files / 52 tests)
FRONTEND_BUILD       = PASS

F1C3_FRONTEND_READY = YES
REMAINING_BLOCKERS  = NONE
```

---

## Q46 closure (was the only reported blocker)

`operating_system` 2022 Q46 was reported absent by the first BC6 pass. The second pass found it:
the **bank** row had no mapping and no `2022_46_*` asset, but the **document** source for the same
paper references `/static/exam_papers/11408/operating_system/2022/img_14.jpg`, and that file exists.
Resolution now consults the document source for the same `(subject, year, question_number)`, and
`2022-46` was added to the curated `image_mapping.json` (+3 lines; the rest of the file diff is
pre-existing CRLF drift, byte-preserved).

No substitute image was drawn, no question was removed, and no asset file was moved or modified —
`exam_resources` still holds 207 images and `static/exam_papers` still holds 564.

## Carried forward (not blockers)

1. `PastPaperSubmitResponse` keeps `answer_grade: {applied, reason}` — the runtime shape that already
   existed — rather than a new flat field, so the frozen AI-orchestrator assertions still hold.
2. `judge` gained one value (`ai_graded`) beside the existing `self_review`. Both describe states the
   runtime already produced; no enum was invented for convenience, and the frontend can distinguish
   "graded by the model" from "not graded" without inferring it from a score.
3. The document source's docx parse is consulted by `available_papers` to discover years. If the
   docx or cache were ever removed, `data_structure` would lose its paper index — the dependency is
   intentional and unchanged from before BC6.
