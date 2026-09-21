# THREE_DOMAIN_PRODUCTIZATION_P1_2_COURSE_WRONG_SECURITY_REPORT

Task: `THREE_DOMAIN_PRODUCTIZATION_P1_2_COURSE_WRONG_SECURITY_FIX`
Date: 2026-09-20
Scope: course_learning AI practice provenance + wrong-answer question materialization.
No frontend change, no migration, no schema change, no commit, no deploy.

---

## 1. FORENSICS — what was actually wrong

### 1.1 The emitted source identity was false

`learning/practice/adapters/course.py::_MODE_MAP` declared, for `mode="course_learning"`:

```
("questions", MATERIAL_GENERATED)
```

but the course generator writes its question to `ai_generated_questions`
(`main._create_course_learning_attempt` is handed an `AIGeneratedQuestion`, and
`ai_question_attempts.question_ids_json` stores **that** table's primary key).

Consequences, both real:

| # | Effect | Why |
|---|---|---|
| 1 | stem / reference_answer empty | the id was looked up in `questions`, where no such row exists |
| 2 | cross-user / cross-course disclosure | `questions.id` and `ai_generated_questions.id` are **independent** id spaces; where they overlap, the id resolves to a *different* row — another learner's or another course's question |

### 1.2 The materialization had no identity gate

`learning/spaces/course_learning/wrong_answers.py::_CourseQuestionIndex` loaded rows by
**bare primary key** (`id.in_(...)`), with no owner filter and no course filter, and the
table was chosen from the same wrong source type.

### 1.3 The fallback invented an identity

`build_refs` used `_MODE_MAP.get(mode) or (COURSE_LEARNING, "questions", MATERIAL_GENERATED)`
— an unmapped `mode` was silently filed under a source identity the row never stated.

---

## 2. SOURCE_CONTRACT (fix 一)

- **Table**: `ai_generated_questions` for `mode="course_learning"` (and `mode="11408"`,
  unchanged).
- **Canonical type**: `QuestionSourceType.AI_GENERATED` (`"AI_generated"`), resolved through
  the ONE existing mapping `learning/practice/refs.py::resolve_source_type` — the adapter no
  longer re-declares a source type; `_MODE_MAP` now carries only `(namespace, table)`.
- **Provenance preserved verbatim**: `QuestionRef.raw_source = {"table":
  "ai_generated_questions", "mode": "course_learning", "ai_question_attempt_id": <id>}`.
- **Unknown `mode` fails closed**: skipped, counted (`reason="unknown_mode"`) and logged
  (`practice.ai_question_attempt_unknown_mode`) — never defaulted to a table.
- **Unchanged and still correct**: the ordinary course practice flow
  (`question_attempts` → `questions`) keeps `MATERIAL_GENERATED`; that id space is its own.
- **No automatic reinterpretation of stored rows**: no row was rewritten, re-keyed or
  backfilled. Existing `material_generated` rows keep their stored identity.

### Frozen test updated — CONTRACT CORRECTION

`tests/test_practice_adapters.py`
- `test_course_adapter_fans_out_one_attempt_per_question` — the assertion
  `question_source_type == "material_generated"` is replaced by `== "AI_generated"` plus a
  `raw_source["table"] == "ai_generated_questions"` assertion, with an explicit
  **CONTRACT CORRECTION (P1.2)** comment stating that the old assertion disagreed with the
  real storage identity and produced both the empty stem and the cross-table id risk.
- New `test_course_adapter_refuses_an_unknown_mode_instead_of_defaulting`.

`tests/test_course_p1_1_contracts.py`
- `test_p1_course_surfaces_still_answer_under_the_same_identity` — the P1.1
  *characterization* of the blocker (empty stem, `source_kind == "course_material"`) is
  replaced by the successor assertions that test itself promised (`stem == question.stem`,
  `reference_answer == "A"`, `question_id == question.id`, `source_kind == "ai_generated"`),
  marked **CONTRACT CORRECTION (P1.2)**.

(These are the only two frozen assertions touched. `test_question_attempts_backfill_maps_self_result`
still asserts `material_generated` — correctly, because that lineage really is the
`questions` table.)

---

## 3. OWNER_ISOLATION (fix 二)

`_resolve_content` is now the ONE gate a course wrong-answer record goes through. A row is
shown only when ALL of the following hold against stored identity:

1. **declared table** — the state's declared source type names exactly one table
   (`AI_generated` → `ai_generated_questions`, `material_generated` → `questions`); an
   unmapped type names none and resolves nothing;
2. **owner** — `row.username == state.username`, and the batch query is scoped by
   `username IN (...)` so another learner's rows are never even loaded;
3. **course** — `row.subject_key` (AI) / `row.course_id` (`questions`) must be one of the
   state's course's exact identity forms (`course_identity_forms`, a fixed dictionary
   lookup — never a substring, prefix, case-fold or title match);
4. **a stated owner AND course** — a state with neither resolves nothing.

Anything else returns `None`: empty stem, empty reference answer, `question_id = None`, and
the fact (status, the learner's own answer, counts, timestamps) still reported.

**No cross-table fallback exists.** A mismatch is a fact about the data, not a lookup to
retry against the other table. There is no bare-id lookup, no sequential search, no title
matching and no fuzzy matching anywhere in the path.

`question_id` is set **only** for the AI table: it is documented as the id the course redo
contract takes (an AI 题册 question), so a `questions` primary key is no longer emitted into
it — handing the redo contract an id from an unstated table is the same defect class this
task removes.

---

## 4. LEGACY_COMPATIBILITY (fix 三)

A stored course `material_generated` state may be either table's id, because the pre-fix
adapter declared exactly that value for AI questions. The id space is decided by the attempt
**lineage** — `practice_attempts.source_attempt_type`, a stored fact of the canonical attempt
— and only when it is unanimous:

| lineage of every attempt of the state | resolved table | reported `source_kind` |
|---|---|---|
| `ai_question_attempt` (the pre-fix AI lineage) | `ai_generated_questions` (proven) | `ai_generated` |
| `question_attempt` (ordinary course practice) | `questions` (declared) | `course_material` |
| mixed / unknown / absent | **none — fail closed** | stored kind kept, content empty |

The lineage constants are imported from the adapter that writes them
(`learning.practice.adapters.course`), not re-spelled here.

Why the fourth row is deliberate: a colliding id can fold both id spaces into ONE state
identity, so no attempt set proves a table for it. An ambiguous row is left unreadable rather
than tested against both tables until one accepts the id.

Forbidden behaviours, all absent: bare-id guessing, cross-table sequential search, title
matching, fuzzy matching. Pre-fix rows are corrected **in display only**; their stored
identity is untouched, so a question answered both before and after the fix can legitimately
appear as two factual states (merging them would be a data migration, explicitly out of
scope for this fix).

---

## 5. WRONG_ANSWER_RESOLUTION (fix 四)

`GET /course-learning/courses/{course_id}/wrong-answers` and its detail route now return, for
the newly correct facts:

`stem`, `options`, `analysis`, `user_answer`, `reference_answer`, `question_id` (the course
redo contract's AI id), `question_type`, `knowledge_point_*`, `status` (review state),
`first_wrong_at / last_wrong_at / resolved_at`, `repeat_wrong_count`, `source_kind`,
`source_label`, `course_id`.

Isolation asserted by test at three levels: learner A cannot read learner B's question; course
A's path cannot read course B's question (both through the current declaration and through the
legacy lineage path); neither can be reached through the global `/wrong-answers` dispatch of a
course state's own endpoint.

---

## 6. TESTS (fix 五)

New file `backend/tests/test_three_domain_p1_2_course_wrong_security.py` — 13 tests:

| Requirement | Test |
|---|---|
| new course AI attempt emits AI_GENERATED | `test_a_new_course_ai_attempt_is_mirrored_as_ai_generated` |
| 11408 identity undisturbed | `test_the_exam_mode_keeps_its_ai_generated_identity` |
| unknown mode → no identity | `test_an_unknown_attempt_mode_records_no_provenance` (+ adapter test) |
| wrong-answer resolves correct stem / reference / identity | `test_the_wrong_answer_record_resolves_stem_answer_and_question_identity` |
| same PK in both tables cannot collide | `test_the_same_id_in_both_question_tables_cannot_collide` |
| user A cannot resolve user B's question | `test_another_learners_question_is_never_resolved` |
| course A cannot resolve course B's question | `test_another_courses_question_is_never_resolved` |
| wrong source type fails closed | `test_a_wrong_source_type_fails_closed` |
| legacy proven row resolves as the AI question | `test_a_proven_legacy_ai_row_resolves_as_the_ai_question_it_is` |
| legacy ambiguous row fails closed | `test_an_ambiguous_legacy_row_fails_closed` |
| ordinary `questions` row still resolves | `test_an_ordinary_question_attempt_row_still_resolves_from_the_questions_table` |
| legacy path is not a course check bypass | `test_a_question_of_another_course_never_leaks_through_a_legacy_row` |
| submit → wrong state → detail full loop | `test_submit_wrong_answer_wrong_state_wrong_detail_full_loop` |

Every test runs against the TEMP DATABASE_URL that `conftest` installs before `main` is
imported.

**Results**

- new file alone: **13 passed**
- affected existing files (`test_practice_adapters`, `test_course_p1_1_contracts`,
  `test_three_domain_p1_contracts`, `test_course_space`, `test_wrong_answers`,
  `test_wrong_answers_api`, `test_course_ai_migration`): **163 passed**
- full backend suite: see §7.

---

## 7. P1_2_FINAL_SUITE

```
./.venv/Scripts/python.exe -m pytest -q      (backend/, TEMP DATABASE_URL from conftest)
1624 passed, 2 skipped, 0 failed in 2146.55s (0:35:46)
```

No failures, no errors, no xfails. The run is green with the P1.2 change set
(source identity + fail-closed materialization + the two contract-correction updates).

---

## 8. MAIN DB PROTECTION (fix 七)

```
MAIN_DB_SHA_BEFORE = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER  = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SIZE       = 64917504 bytes (before and after)
MAIN_DB_MTIME      = 1789877022 (2026-09-20 12:03:42.878312700 +0800, before and after)
MAIN_DB_TOUCHED    = NO
```

No `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
`push` was run. No frontend file changed. No migration and no schema change was made.

---

## 9. CLAUDE.MD FACT (fix 六)

`MIGRATION_HEAD` `20260919_0010` → `20260919_0012`. Verified against
`ls migrations/versions/` (latest revision `20260919_0012_data_origin_provenance.py`, and no
revision declares it as `down_revision` — it is the head). Only that fact changed.

---

## 10. GATES

```
SOURCE_CONTRACT            = PASS (AI_generated / ai_generated_questions; canonical mapping reused; unknown mode fails closed)
OWNER_ISOLATION            = PASS (owner + course + declared table + stated context, or no content)
LEGACY_COMPATIBILITY       = PASS (lineage-proven read-only resolution; ambiguous fails closed; no reinterpretation of stored rows)
WRONG_ANSWER_RESOLUTION    = PASS (stem / user_answer / reference_answer / review state / question identity; course+user isolated)
TESTS                      = 13 new tests pass; 163 affected existing tests pass; full suite 1624 passed / 2 skipped / 0 failed
MAIN_DB_SHA_BEFORE         = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_SHA_AFTER          = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
MAIN_DB_TOUCHED            = NO
COURSE_WRONG_SECURITY_FIXED = YES
```

## 11. BLOCKERS / FINDINGS

1. **`learning/spaces/exam_prep/wrong_answers.py::_SourceIndex._load_ai` (line ~227) and
   `_load_bank` (line ~202) still materialize question content by BARE primary key with no
   owner check.** The global route `GET /wrong-answers`
   (`routers/wrong_answers.py`, `build_record`/`build_records` of the exam resolver) renders
   COURSE-namespace states too, so a course `AI_generated` state's content is resolved there
   through the exam index — which does not verify the row's owner. Exposure requires a stored
   state whose `question_source_id` was pointed at another learner's `ai_generated_questions`
   row (a mis-pointed legacy/migrated row); the supported write paths validate ownership at
   creation. **Not fixed here**: it is the exam space's frozen resolver (STEP7H2 acceptance),
   outside this task's stated scope. Recommend a P1.3-class fix applying the same
   owner+context gate, or routing course states to the course resolver in the global route.
2. **Pre-fix rows stay `material_generated`.** They now display correctly (proven legacy
   path), but a question answered both before and after this fix can appear as two states
   (one legacy `material_generated`, one `AI_generated`). Merging/re-keying is a data
   migration and was deliberately NOT attempted.
3. **Non-numeric source ids never resolve content** (e.g. synthetic ids like `e2e-ai-1`).
   Both question tables key on INTEGER primary keys, so this is not a regression, but such a
   state reports an empty stem by construction.
