# FRONTEND_F1C3A — CS408 Past Paper Contract Audit

Date: 2026-09-19.
Mode: fast contract audit. No frontend UI, no backend redesign, no schema change, no new data.

```text
FRONTEND_F1C3A_COMPLETE
F1C3_FRONTEND_READY = NO
BLOCKERS = 3 hard (PRE_SUBMIT_ANSWER_LEAK, SUBMITTED_RELOAD, IMAGE_SERVING) + 1 missing semantics (SELF_REVIEW)
REAL_APP_DB_MUTATED = NO
```

Everything below was measured, not inferred from docs: rows read from the real `app.db` (read-only),
OpenAPI generated from the live app, and responses captured from a real server on port **8953**
backed by a **TEMP copy** of that database.

---

## 1. Data audit — `source_type = 'past_paper'`

| Measure | Value |
| --- | --- |
| Total rows | **235** |
| Active rows (`is_active = 1`) | **170** |
| Superseded rows (`is_active = 0`) | 65 |

The 65 inactive rows are the reconcile history: every `computer_organization` 2022 question number
exists twice — `id 7104` (`is_active=0`) and `id 7169` (`is_active=1`), both with
`source_ref = "past_paper:2022-Q12"`. **Among active rows the stable key is unique — 0 duplicate
groups.**

### Subjects

| Subject | Active rows | Years |
| --- | --- | --- |
| `computer_organization` | 65 | 2022–2026 |
| `operating_system` | 60 | 2022–2026 |
| `computer_network` | 45 | 2022–2026 |
| `data_structure` | **0** | — |

### Question types

| Type | Active rows |
| --- | --- |
| `choice` | 145 (all 145 have 4 options) |
| `big` | 25 |

### Field integrity (active rows)

| Check | Result |
| --- | --- |
| missing `year` | 0 |
| missing `question_number` | 0 |
| missing `standard_answer` | 0 |
| **empty `analysis`** | **168 of 170** |
| empty `stem` | 0 |
| `source_ref` present / distinct | 170 / 170, format `past_paper:{year}-Q{number}` |
| `visibility` | `public` on all 170; `owner_username` null on all 170 |

### Resource / image presence

There is **no image or asset column** anywhere in `exam_question_bank`. 31 active rows reference a
figure in the stem text (`如题 43 图所示`, `如题图所示`) with no asset attached — **no `<img>`, no
markdown image, no `/uploads/` path, no filesystem path leaks into the payload.**

---

## 2. Canonical identity

**There are two parallel past-paper data sources, and they do not share an identity space.**

| | DB path | Document path |
| --- | --- | --- |
| Source | `exam_question_bank` where `source_type='past_paper'` | `11408_2022_2026_*.docx` + `cache/exam_papers/11408/{subject}/{year}.ocr.json` |
| Coverage | co 65 · os 60 · cn 45 · **ds 0** | co 65 · os 60 · cn 45 · **ds 65** |
| Question id | `ExamQuestionBank.id` — **int** (`7169`) | **string** `{subject}_{year}_{number}` (`data_structure_2022_1`) |
| Type vocabulary | `choice` / `big` + `type: "选择题" / "大题"` | `type: "选择题" / "大题"` only |
| Question key set | `id, number, year, type, stem, content, options, standard_answer, question_type, quality_status, review_notes, image_urls, image_required` | `id, year, number, type, content, options, answer, stem, ocr_quality, need_manual_check, manual_fixed, fix_notes` |

```text
CANONICAL_PAPER_IDENTITY    = (subject_key, year)             -> PastPaperAttempt(subject_key, year, attempt_no)
CANONICAL_QUESTION_IDENTITY = ExamQuestionBank.id             (DB path)
                              "{subject}_{year}_{number}"      (document path) — CONFLICT
```

Neither path leaks a filesystem path or a Chinese-title hash; both are stable. The problem is that
they are *different* stable identities for the same paper, chosen by which endpoint you call.

---

## 3. Endpoint matrix

All seven live in `backend/main.py`. **None is typed.**

| # | Method | Path | Handler | Auth | Request | Response | Typed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GET | `/exam/11408/{subject_key}/past-papers` | `get_exam_past_papers` | **none** | path | `{subject_key, subject_name, available, years[], files[{filename}]}` | **untyped `{}`** |
| 2 | GET | `/exam/11408/{subject_key}/past-paper-questions?year=` | `get_past_paper_questions` | **none** | path + `year` | `{subject_key, subject_name, year, questions[]}` | **untyped `{}`** |
| 3 | POST | `/exam/11408/{subject_key}/past-paper-attempts` | `create_past_paper_attempt` | session | `dict` | `{attempt_id, attempt_no, subject_key, year, status, total_questions}` | **untyped `{}`** |
| 4 | GET | `/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}` | `get_past_paper_attempt` | session | path | `{attempt, questions[], saved_answers}` | **untyped `{}`** |
| 5 | POST | `.../past-paper-attempts/{id}/answers` | `save_attempt_answers` | session | `dict{answers: dict}` | `{success, attempt_id}` | **untyped `{}`** |
| 6 | POST | `.../past-paper-attempts/{id}/submit` | `submit_attempt` | session | `dict{answers: list[dict]}` | full result blob | **untyped `{}`** |
| 7 | GET | `/exam/11408/past-paper-images/{subject_key}/{year}/{filename}` | `serve_past_paper_image` | **none** | path | `FileResponse` | **untyped `{}`** |

Adjacent, also untyped: `GET /exam/11408/{subject_key}/wrong-questions?source=past_paper`,
`GET /exam/11408/{subject_key}/practice/stats`.

Side effects: #3 inserts one `PastPaperAttempt`; #5 writes `answers_json`; #6 writes status,
scores, `result_json`, `past_paper_wrong_questions` rows, `exam_question_done_records`, and mirrors
into the Practice Core; #1/#2/#4/#7 are read-only.

Two security observations on the read endpoints: **#1 and #2 require no authentication at all**, and
#1 returns `files[].filename` — the server-side `.docx` filename.

---

## 4. Source isolation

Verified against the live DB rows served by #4 (13 questions of `computer_organization` 2022):

```
served ids source_type breakdown : [('past_paper', 13)]
NON-past_paper rows served       : 0
```

```text
PAST_PAPER_SOURCE_LEAK = 0
```

Both branches of #4 filter `source_type == "past_paper"` and `is_active == True`; the document
fallback is not the shared bank. Isolation holds.

---

## 5. Pre-submit security — **BLOCKED**

`standard_answer` and `review_notes` are emitted by #4 with **no status-based redaction** — the
chapter-practice domain strips them while `in_progress` (BC5A/BC5C), past papers never got that
treatment.

```
GET /exam/11408/computer_organization/past-paper-attempts/{id}   attempt.status = in_progress
  question keys       : [content, id, image_required, image_urls, number, options, quality_status,
                         question_type, review_notes, standard_answer, stem, type, year]
  PRE-SUBMIT LEAK KEYS: ['standard_answer']  ->  {'standard_answer': 'A'}
```

#2 leaks too, and it needs no login at all:

```
GET /exam/11408/data_structure/past-paper-questions?year=2022   (anonymous, 200)
  n=13  leak_keys=['answer']   ->  {'answer': 'B'}
same for computer_organization, operating_system, computer_network
```

```text
PRE_SUBMIT_ANSWER_LEAK         = 13/13 questions on the attempt detail (standard_answer),
                                    13/13 anonymous on the question list (answer)
PRE_SUBMIT_EXPLANATION_LEAK    = review_notes key always present; value empty for 168/170 rows,
                                    non-empty (leaking) for 2
```

Not a typing problem — a real disclosure. Typing the contract would not fix it.

---

## 6. Attempt / submission semantics

Past papers have their **own** attempt subsystem — `PastPaperAttempt`, not
`ExamPracticeAttempt` — so chapter-practice semantics are *not* reused.

| Capability | Endpoint | Persistence | Verdict |
| --- | --- | --- | --- |
| create | #3 | inserts `PastPaperAttempt(status='in_progress', attempt_no=last+1)` | works |
| save | #5 | writes `answers_json`; 400 if not `in_progress` | works |
| submit | #6 | sets `submitted`, writes scores + `result_json` | works |
| **reload** | #4 | `{attempt, questions, saved_answers}` — **no `results`** | **BLOCKED** |

```
after submit:  GET .../past-paper-attempts/{id}
  reload top keys         : ['attempt', 'questions', 'saved_answers']
  RELOAD carries results? : False
  attempt.status          : submitted
```

The authoritative per-question result exists — it is written into `PastPaperAttempt.result_json` and
returned by #6 — but #4 never replays it. So a browser refresh after submit loses 回答正确/回答错误
and the score, exactly the blocker BC5C had to close for chapter practice.

Request shapes are also inconsistent inside this one family: #5 takes `answers` as a **dict**
(`{"<question_id>": "A"}`) while #6 takes `answers` as a **list of `{question_id, user_answer}`**,
and the id inside must be a **string** on the document path (`"data_structure_2022_1"`) and a
**stringified int** on the DB path (`"7169"`).

---

## 7. Grading

| Question type | Owner | Mechanism |
| --- | --- | --- |
| `choice` (145 rows) | **backend, deterministic** | `ua.upper() == sa.upper()`, done inside #6 — zero provider calls |
| `big` (25 rows) | **backend, provisional** | DB path: hard-coded `score = 5`, `full_score = 10`, `feedback: "请自行对照参考答案"`. Document path: keyword-overlap heuristic `_ungraded_big_answer(user_answer, standard)` when the AI grader is refused |

```text
PAST_PAPER_FRONTEND_GRADING_REQUIRED = NO
DETERMINISTIC_GRADING = YES (choice)
SELF_REVIEW = NO
```

**This is the important semantic gap.** Chapter practice treats a big question as
`judge = "self_review"`, `correct = null` — never auto-scored, the learner compares. Past papers give
it a **number**: a flat 5/10 on the bank path regardless of the answer. In the live probe the AI
grader was refused and the payload recorded
`answer_grade: {'applied': False, 'reason': 'answer_grade_unavailable_403'}`, yet the result still
carried `"score": 5`. A past-paper workspace therefore cannot render 自行复盘 from these results, and
must not present that 5 as a judgement of the learner.

---

## 8. Wrong-record and knowledge side effects

Measured on the TEMP copy after one real submit (13 questions of `computer_organization` 2022):

| Table | After submit |
| --- | --- |
| `past_paper_wrong_questions` | **7** (created by #6) |
| `exam_wrong_questions` | 0 — separate table, untouched |
| `exam_question_done_records` | 13 |
| `user_knowledge_progress` | **0** |
| `knowledge_progress_events` | **0** |

```text
WRONG_RECORD_BEHAVIOR = backend-owned. #6 inserts/updates past_paper_wrong_questions
                        (its own table, with status/mastered/resolved_at) + one done record per
                        question + a failure-isolated Practice Core mirror. No frontend write needed.
CORRECT_ANSWER_AUTO_MARK_MASTERED = NO
```

No knowledge-point status is written by past-paper submission — the product rule holds. Note the
wrong record has its own `mastered` column; that is wrong-book mastery, not knowledge mastery.

The wrong book is readable through the shared
`GET /exam/11408/{subject_key}/wrong-questions?source=past_paper` (untyped).

---

## 9. Images / resources — **BLOCKED**

```
GET /exam/11408/past-paper-images/data_structure/2022/img_0.jpg      -> 404 {"detail":"Image not found"}
GET /static/exam_papers/11408/data_structure/2022/img_0.jpg          -> 404 {"detail":"Not Found"}
GET /exam/11408/past-paper-images/operating_system/2022/x.jpg        -> 404 {"detail":"Image not found"}
```

Three independent reasons:

1. The document path emits `image_urls` such as `/static/exam_papers/11408/data_structure/2022/img_0.jpg`,
   but the FastAPI mount for `/static/exam_papers` is **commented out** in `main.py:19768-19773`
   ("served via nginx, not FastAPI mount"). In this environment nothing serves it.
2. The dedicated route #7 returns 404 for `data_structure` — `exam_resources/11408/data_structure/past_papers/`
   does not exist on disk at all (no `images/`, no `assets/`).
3. `image_mapping.json` — the file #4 uses to attach images to bank rows — exists only for
   `computer_network` and `operating_system`.

```text
IMAGE_RESOURCE_CONTRACT = BLOCKED. No working image route for the frontend.
   DB path  : image_urls[] resolved from exam_resources/11408/{subject}/past_papers/image_mapping.json
              (present for cn + os only; empty list otherwise) + image_required flag
   Doc path  : image_urls stripped by the serving code, and the URLs it would emit point at an
              unmounted /static path
   No filesystem path is leaked to the client.
```

31 active rows reference figures in their stems; with no asset route those questions cannot be shown
faithfully.

---

## 10. OpenAPI types

| Required capability | Operation | Success unknown? | Request unknown? |
| --- | --- | --- | --- |
| year index | #1 | YES (`{}`) | n/a |
| question list | #2 | YES (`{}`) | n/a |
| attempt create | #3 | YES (`{}`) | YES (`additionalProperties: true`) |
| attempt detail | #4 | YES (`{}`) | n/a |
| answer save | #5 | YES (`{}`) | YES |
| submit | #6 | YES (`{}`) | YES |
| image | #7 | YES (`{}`) | n/a |
| wrong book | wrong-questions | YES (`{}`) | n/a |

```text
PAST_PAPER_REQUIRED_SUCCESS_UNKNOWN = 8 / 8
PAST_PAPER_REQUIRED_REQUEST_UNKNOWN = 3 / 3
```

Nothing was tightened: every gap above is a real disclosure or a missing payload, and typing a
leaking contract would only make the leak type-safe.

---

## 11. Capability classification for F1C3

| | Capability | Verdict | Why |
| --- | --- | --- | --- |
| A | year / paper index | **PARTIAL** | #1 works and covers all four subjects, but is auth-free, untyped, sources years from a `.docx` parser rather than the bank, and returns the server-side filename |
| B | paper question browsing | **BLOCKED** | #2 leaks `answer` anonymously; #4 leaks `standard_answer` pre-submit |
| C | answer desk | **BLOCKED** | inherits B, plus two question shapes and two id spaces depending on the path |
| D | save | **PARTIAL** | #5 persists, but dict-vs-list request and untyped |
| E | submit | **PARTIAL** | #6 persists correctly, but untyped and takes a different `answers` shape than #5 |
| F | deterministic grading | **READY** | choice grading is backend-owned and provider-free |
| G | self-review | **BLOCKED** | no `self_review` / `correct: null` semantics exist; big gets a provisional numeric score |
| H | submitted reload | **BLOCKED** | #4 never returns `results` |
| I | result summary | **BLOCKED** | depends on H |
| J | wrong-record integration | **PARTIAL** | backend writes and a read endpoint exists, but the table is past-paper-specific and the endpoint is untyped |
| K | images / resources | **BLOCKED** | no working image route; `data_structure` has no assets at all |

---

## 12. Real database safety

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

All write probes ran against a **copy** at `%TEMP%\f1c3a\vqa.db`; the real file was only ever opened
`?mode=ro`.

```text
REAL_APP_DB_MUTATED = NO
```

---

## 13. Final output

```text
FRONTEND_F1C3A_COMPLETE

PAST_PAPER_ROWS = 235 total / 170 active (65 superseded is_active=0)
SUBJECTS        = computer_organization 65, operating_system 60, computer_network 45,
                  data_structure 0   (+ a document/OCR source that does cover data_structure)
YEARS           = 2022, 2023, 2024, 2025, 2026
QUESTION_TYPES  = choice 145, big 25

CANONICAL_PAPER_IDENTITY    = (subject_key, year)  [PastPaperAttempt: subject_key + year + attempt_no]
CANONICAL_QUESTION_IDENTITY = ExamQuestionBank.id (DB path)  vs  "{subject}_{year}_{number}"
                              (document path)  -> CONFLICT

PAST_PAPER_ENDPOINTS =
  GET  /exam/11408/{subject_key}/past-papers                            (no auth, untyped)
  GET  /exam/11408/{subject_key}/past-paper-questions?year=             (no auth, untyped)
  POST /exam/11408/{subject_key}/past-paper-attempts                    (auth, untyped)
  GET  /exam/11408/{subject_key}/past-paper-attempts/{attempt_id}       (auth, untyped)
  POST /exam/11408/{subject_key}/past-paper-attempts/{id}/answers       (auth, untyped)
  POST /exam/11408/{subject_key}/past-paper-attempts/{id}/submit        (auth, untyped)
  GET  /exam/11408/past-paper-images/{subject_key}/{year}/{filename}    (no auth, untyped)

YEAR_INDEX       = PARTIAL  (works, all 4 subjects, docx-sourced, auth-free, leaks source filename)
QUESTION_LIST    = BLOCKED  (anonymous `answer` leak on all 4 subjects)
ATTEMPT_CREATE   = PARTIAL  (persists; untyped dict request)
ANSWER_SAVE      = PARTIAL  (persists; dict body, untyped)
SUBMIT           = PARTIAL  (persists; list body, different shape from save, untyped)
ATTEMPT_RELOAD   = BLOCKED  (detail returns no `results`)

DETERMINISTIC_GRADING      = YES (choice: backend ua.upper()==sa.upper(), provider-free)
SELF_REVIEW                = NO  (big gets a provisional score, DB path hard-coded 5/10)
FRONTEND_GRADING_REQUIRED  = NO

PRE_SUBMIT_ANSWER_LEAK      = NONZERO — 13/13 on the attempt detail (`standard_answer`)
                                        and 13/13 anonymous on the question list (`answer`)
PRE_SUBMIT_EXPLANATION_LEAK = `review_notes` always present; empty for 168/170, leaks for 2
PAST_PAPER_SOURCE_LEAK      = 0

WRONG_RECORD_BEHAVIOR           = backend-owned on submit: past_paper_wrong_questions (own table)
                                  + exam_question_done_records + Practice Core mirror
CORRECT_ANSWER_AUTO_MARK_MASTERED = NO (user_knowledge_progress 0, knowledge_progress_events 0)

IMAGE_RESOURCE_CONTRACT = BLOCKED — /static/exam_papers mount commented out; dedicated route 404s;
                          data_structure has no assets; image_mapping.json only for cn + os
                          (no filesystem path leaked to the client)

PAST_PAPER_REQUIRED_SUCCESS_UNKNOWN = 8 / 8
PAST_PAPER_REQUIRED_REQUEST_UNKNOWN = 3 / 3

F1C3_FRONTEND_READY = NO

BLOCKERS =
  1. PRE_SUBMIT_ANSWER_LEAK — #4 returns standard_answer (and review_notes) for an in_progress
     attempt with no status-based redaction; #2 returns `answer` anonymously. Fix owed in the
     backend; typing alone would not close it.
  2. SUBMITTED_RELOAD — #4 never replays the authoritative results that #6 already persists in
     `result_json`. Without it there is no refresh-safe result view (the BC5C blocker, again).
  3. IMAGE_SERVING — no reachable image route; 31 figure-bearing questions cannot be shown.
  4. SELF_REVIEW_MISSING — big questions are given a provisional numeric score instead of the
     frozen `judge: self_review` / `correct: null` semantics used by chapter practice.
  Secondary: two parallel sources with conflicting question identities and two different question
  shapes; all 7 endpoints untyped; #1/#2 unauthenticated; dict-vs-list `answers` in one family.

REAL_APP_DB_MUTATED = NO
```

## Notes for the F1C3 decision

* The real, useful dataset for a first release is the **bank path**, which has `computer_organization`,
  `operating_system` and `computer_network` — not `data_structure`. A `data_structure` paper exists
  only on the document/OCR path, which carries its own id space and its own leak.
* 168 of 170 active rows have **no analysis**, so a first release cannot rely on static 题目解析 for
  past papers; only AI explain could fill it, and that is an `F1C2C`-style explicit mutation.
* Per the scope rules, none of this audit added timed-exam mode, countdown, score prediction, rank,
  mastery estimation, AI mock papers, institution papers, or new seeds. Everything reported is
  existing real data and existing behaviour.
