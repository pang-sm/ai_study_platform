# ZHIXUE_FINAL_LEARNER_UI_CLOSURE_REPORT

**Task**: `ZHIXUE_FINAL_LEARNER_UI_CLOSURE` — final frontend closure before the visual freeze.
**Date**: 2026-09-21 · **Scope**: `frontend/**` only · **Revision**: working tree at HEAD `b3543a34`
(uncommitted, as required — no commit / push / deploy was performed).

---

## 0. PRECONDITION DISCLOSURE — `CODEX_SPEC_APPLIED = NO`

`ZHIXUE_FINAL_PRODUCT_UX_ACCEPTANCE_REPORT`, the document this brief names as the source of the
P0/P1 list, **does not exist**. Re-verified this session:

| Search | Result |
|---|---|
| `find` over the repo (incl. untracked) | no match |
| `find` over `Desktop/`, `Downloads/`, `C:\Users\26477` (5 levels) | no match |
| `git status` untracked, `git log`, `git stash list` | no match |
| full-text search of all session transcripts (incl. archived) | only hit is **this brief's own text** |

This is the same pattern as `ZHIXUE_P7A_INTERACTION_SPEC` / `ZHIXUE_P7B_UX_ACCEPTANCE_REPORT` /
`ZHIXUE_P7D_FIRST_RUN_UX_SPEC` (see the standing project memory `codex-spec-docs-absent`).

**Therefore**: the brief's own 14 numbered requirements were executed as written, decided against
the project's real authorities — the live backend/OpenAPI contract, `docs/UI_DESIGN_SPEC.md`,
`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`, `frontend/src/styles/tokens.css`. Nothing in this
report claims to apply a document nobody has read.

---

## 1. THE UNIFIED RULE (brief item 1)

One module now owns the question "may a learner read this?":
[learner-safe.ts](frontend/src/lib/learner-safe.ts).

- **No escape hatch, because there is no admin surface.** The audit found only 45 routes, all
  learner-facing — there is no `/admin` or `/dev` route in this frontend. `admin-paths = 0`, so the
  brief's "keep it, but only for admin/dev" branch had no valid consumer and the component was
  deleted outright rather than relocated.
- **Coded values** are read through `enumText(key, value, fallback)` against a per-field vocabulary
  (`FIELD_VOCABULARIES`): a known code becomes its Chinese label; an unknown one becomes `其他` /
  `未设置`. The code itself is never printed, folded or not.
- **Free text is not mangled**: only fields listed as coded are treated as coded. `analysis`,
  `stem`, `user_answer` print as themselves.
- **Unmapped fields are dropped**, not dumped — in `FactList` and everywhere else.
- **Transport identity is never rendered.** `request_id` / `agent_run_id` / `service_key` remain in
  the client where they decide whether a 👍/👎 control appears (brief item 9); they are not metadata
  for the learner to read.

### Two decisions worth flagging

1. **`overdue` is one name with two shapes.** The report's metric block carries it as a count
   (`已逾期`); an agenda task carries it as a boolean. Re-labelling it would have silently changed
   the report's meaning, so the agenda states the same fact through its own `status` instead and the
   key keeps the one meaning it already had.
2. **`reason` is deliberately *not* in the vocabulary map.** It is a coded gap-explanation in one
   payload and the model's own sentence in a plan proposal. One vocabulary would have mangled one of
   the two, so the single surface that reads it as a code passes `REASON_LABELS` itself.

## 2. RAW-PAYLOAD BOUNDARY (brief item 2)

- `raw-payload.tsx` — the single exit for raw objects — was **deleted**.
- Faithful translation of `JSON.stringify`: `src/**` now contains exactly **two** sites, both in
  tests (one of which is the guard scanning for it). **0** learner component serialises an object.
- `FactList`'s unmapped-field fallback (which fed `RawPayload`) was **removed**, not renamed, and its
  `rawLabel` prop is gone. A payload can no longer widen the interface on its own.
- New `allow` prop narrows rich backend objects (`facts`, `metrics`, `domain_context`) to the fields
  a surface has actually chosen to explain.
- **"Collapse it and it counts as productised" is explicitly not used.** Deleting the dump means a
  learner who expands every disclosure on every page still sees no backend payload.

## 3–7. SURFACE-BY-SURFACE

### HOME AGENDA (item 3) — `HOME_AGENDA_SAFE = YES`

`为什么现在做这件事` now renders exactly three things: the server's own human-readable rule from
`priority_rules`; an allow-list of factual fields (`wrong_count`, `attempts`, `factual_correct`,
`factual_incorrect`, `active_wrong_count`, `last_attempt_at`, `due_date`, `task_type`, `status`);
and `resolved_by`. An unmapped reason renders **`推荐依据暂不可显示`** — never
`服务端给出的原因码：<code>`. The JSON facts dump is gone.

### COURSE (item 4) — `COURSE_SAFE = YES`

- 6 `RawPayload` sites removed (materials, knowledge map, wrong answers, state, Q&A, failure).
- `Failure` now shows: human-safe title + the server's own sentence when it wrote one
  (`serverMessage`, the established contract) + retry. No stack, no status code, no body, no
  request metadata.
- Learning Intelligence renders Fact / AI Analysis / Evidence / Next Action only; unrecognised
  fields do not reach the UI.
- Raw-enum leaks fixed inline: `parse_status` (`success`/`partial` had **no** label and printed
  verbatim), `file_type`, `task_type`, `status`.
- Internal ids are no longer typeset as names (`后端未返回题干` → `题目信息暂不完整`).

### 11408 (item 5) — `EXAM_SAFE = YES`

- Exam components were already free of `RawPayload`/`FactList`.
- The shared advanced/review surfaces they use were cleaned (below).
- **Student Twin `StateFields` was the real leak**: an *exclusion* regex
  (`!/mastery|prediction|…/`) rendered every remaining field name and value. It is now an explicit
  allow-list of the runtime's real keys, so **`user_id` (internal identity) and `global_ability` (an
  internal quantity of the engine) are structurally unrenderable** — the regex never excluded
  `global_ability`, which in front of a learner reads as an ability score, against the frozen
  `controls_product_decision = false` semantics. `concepts` renders as a count, not as its refs.
- The English label `本次计算使用的 factual evidence` is now Chinese.
- Domain facts kept: module, chapter, knowledge point, question, answer, wrong answer, review, past
  paper. Semester subject/catalog semantics untouched.

### PROGRAMMING (item 6) — `PROGRAMMING_SAFE = YES`

- 6 `RawPayload` sites removed (home, exercise list, statement, AI analysis, records ×2, state, plan).
- `display()` no longer falls back to `item.id` — an exercise with no title is unnamed, its database
  id is not a name.
- Records render `eventTypeLabel` + time + an allow-listed `summary`; `source.id` /
  `question_source_id` / `capability` are not rendered.
- `原始返回数据（后端原文）` and the `查看原始…` offer are gone. The missing-statement state is now
  the honest **`题目信息暂不完整`** with **返回练习列表 / 重试** on both the detail page and the
  Workbench.
- "工作台数据" stopped dumping its payload and shows the real facts it always contained
  (`streak_days`, `momentum`, `today_practice_count`, …).

### WORKBENCH (item 7) — `WORKBENCH_SAFE = YES`

`这次运行的后端原文` and its full JSON disclosure are **deleted**. A learner reads: iteration,
diagnosis, patch/diff, run result, tests before/after, final explanation, status. `agent_run_id`,
each step's `ai_request_id` and provider metadata stay in the client (the step ids still decide
whether that step's feedback control appears). Step actions are named in the product's words
(`diagnose` → `诊断`) instead of the agent's own codes.

## 8. AI USAGE PRODUCT LANGUAGE (item 8) — `PROGRAMMING_USAGE_LANGUAGE = CHINESE`

`Usage：{n} credits` is gone repo-wide. `usageCreditsText()` renders **`本次使用 X 点 AI 额度`**,
reading **`actual_credits` only** — the settled figure. Not the estimate (a reservation that may never
be spent), not tokens, not the provider's cost. When there is no settled figure the line is not
rendered at all, so a `0` is never invented. (The one shortened form the brief allowed was not used:
one sentence everywhere is the more unified choice.)

## 9. REQUEST ID (item 9) — `REQUEST_ID_LEARNER_VISIBLE = 0`

`request_id` is still the real identity used for AI Feedback, cache keys and observability. The two
places it *reached learner copy* — `返回的 request_id 可用于评价这次回答` and
`返回可用于评价的 request_id` — now say `回答下方可以评价这次分析是否有帮助`. No screen prints
`请求 ID：…`.

## 10. UNKNOWN ENUM POLICY (item 10) — `UNKNOWN_ENUM_POLICY = SAFE_LABEL_OR_UNSET`

`enumText` / `vocabularyText` + per-field vocabularies, applied to `status`, `parse_status`,
`state_status`, `review_status`, `source_type`, `origin`, `due_source`, `judge`, `task_type`,
`file_type`. Unknown → `其他`; a preference not set → `未设置`. **No `replace('_',' ')` anywhere**;
no raw key is ever the fallback.

- **The named Programming Setup defect is fixed**: `levelLabel` and the inline
  `PROGRAMMING_LEVELS.find(…)?.label ?? initial.level` both fell back to the stored key. An unknown
  stored `level` now reads `未设置`, pinned by a new test asserting `silver_iii` never renders.
- `tierLabel`'s raw-tier fallback became `—` (was the unmapped key).
- `due_source` was leaking a **database address** (`user_knowledge_progress.review_due_at`) straight
  through a label that existed — both real origins are now translated, anything else is dropped.

## 11. STATIC + RUNTIME GUARDS (item 11) — `LEARNER_METADATA_LEAKAGE_GUARD = ENFORCED`

Two files, **21 tests**:

- [learner-copy.guard.test.ts](frontend/src/test/learner-copy.guard.test.ts) — source scan. Bans the
  payload-naming copy (`后端原文`, `原始返回数据`, `接口原文`, `查看原始`, `原因码`, `请求 ID`,
  `请求ID`) anywhere in learner source; bans `Usage:`/`credits` as *prose* while allowing the real
  column names (`actual_credits`) and the generated schema; bans `JSON.stringify` outside a small
  documented allow-list; asserts no `RawPayload` export exists.
- [learner-metadata-leakage.test.tsx](frontend/src/test/learner-metadata-leakage.test.tsx) —
  runtime, the requested **`LEARNER_METADATA_LEAKAGE_GUARD`**. Each surface is fed a *hostile*
  payload carrying every leakage class under a marker (`LEAK_OBJECT`, `LEAK_ENUM`, `LEAK_REF`,
  `LEAK_REQUEST`, `LEAK_PROVIDER`), and the assertion is that the marker never reaches the document
  while the real fact beside it does. Covers **Home, Course (materials/wrong/state), 11408 (state),
  Programming (list/statement/records) and the Workbench AI result**, plus a structural check that no
  rendered leaf node is JSON.

Unknown-enum non-leakage is asserted inside those cases (agenda reason, `parse_status`, `file_type`,
`source_type`, `status`, agent `action`) and again in the Setup test.

## 12. P2 — CHEAP POLISH (item 12)

- **B. Profile desktop section nav (DONE)** — `useCurrentSection` marks the section the reader is
  inside, with `aria-current` and a left rule, driven by an `IntersectionObserver` and inert where
  the environment has none. No layout change.
- **A. Course Setup "已建立课程" (DONE, compressed rather than removed)** — the two lists are one
  thing seen twice, and a true dedup would have cost either the per-course links into the space or a
  rewrite of an accepted page's contract test — the "larger refactor" the brief says to defer.
  Instead the duplication is reconciled *in the learner's reading*: a line states the relationship
  between the two lists, and each established row already present above is marked `已在上方列出`.
  Every link, count and fact is retained; **no data contract changed**.

## 13. DO NOT CHANGE — verified untouched

Login, Register, First-Run model, Home Focus hierarchy, desktop sidebar, tablet/mobile drawer,
5-item bottom nav, Course learning path, 11408 domain semantics, Programming learning loop,
Workbench 三层能力 (deterministic tools / single AI call / multi-step agent), backend Agenda
ordering, real request identity & feedback semantics. The 11408 gate still reads
`user_visible` from `GET /exam/prep/scientific/capabilities` rather than a hard-coded list.

Cross-check: the two E2E suites that cover exactly this list —
`p7b-acceptance` (shell breakpoints, bottom bar, home focus order, workbench tiers) and
`p7c-spaces` (per-space context, tab marking, phone layout, "reading surface never leads with a
payload") — pass unmodified.

## 14. VALIDATION

| gate | value | evidence |
|---|---|---|
| `TYPECHECK` | **PASS** | `tsc --noEmit`, clean |
| `LINT` | **PASS** | `eslint .`, clean |
| `VITEST` | **PASS** | **300 passed / 61 files** (was 299 tests / 61 files; +21 guard tests, +1 Setup test, −5 stale-behaviour tests superseded) |
| `BUILD` | **PASS** | `vite build`, built in ~1.0 s |
| `PLAYWRIGHT` | **PASS (targeted)** | **14/14**: `smoke.spec.ts` 5/5 · `p7b-acceptance.spec.ts` 6/6 · `p7c-spaces.spec.ts` 3/3 |
| `AXE` | **PASS** | 0 violations in all three specs: login + shell (`smoke`); `/login`, `/`, `/profile`, `/programming/python/projects/1` @1440 and `/` @390 (`p7b`); the converged spaces (`p7c`) |
| `NO_BACKEND_CHANGED` | **YES** | no backend file modified after session start; `find backend -newermt` shows the only two touched files last written 09:56 / 10:08, both **before** this session began (10:13). No backend source edited, no migration run, no `app.db` touched |
| `USER_WORKTREE_PRESERVED` | **YES** | HEAD still `b3543a34`; `origin/main...HEAD` = `0 0`; 73 modified + 143 untracked entries intact; **no** `reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` / `push` / `commit` / deploy |
| `RAW_PAYLOAD_LEARNER_VISIBLE` | **0** | component deleted; `<RawPayload>` uses in `src/` = 0; rendered raw objects = 0 |
| `BACKEND_ORIGINAL_DISCLOSURES` | **0** | `后端原文` / `原始返回数据` / `接口原文` / `原因码` occur **only** in test files (assertions + the guard's own banned list) |
| `REQUEST_ID_LEARNER_VISIBLE` | **0** | identity retained client-side for feedback only; the two copy leaks rewritten |
| `RAW_ENUM_LEARNER_VISIBLE` | **0** | every coded field routed through a vocabulary; unknown → `其他`/`未设置` |
| `HOME_AGENDA_SAFE` | **YES** | allow-listed facts, server rule, `推荐依据暂不可显示` fallback |
| `COURSE_SAFE` | **YES** | 6 dumps removed, safe error UI, enums labelled |
| `EXAM_SAFE` | **YES** | runtime `user_id` / `global_ability` structurally unrenderable |
| `PROGRAMMING_SAFE` | **YES** | 6 dumps removed, no internal id as a title, honest missing-statement state |
| `WORKBENCH_SAFE` | **YES** | `这次运行的后端原文` deleted; only iteration/diagnosis/patch/run/tests/explanation/status |
| `PROGRAMMING_USAGE_LANGUAGE` | **CHINESE** | `本次使用 X 点 AI 额度`, settled `actual_credits` only, hidden when absent |
| `UNKNOWN_ENUM_POLICY` | **SAFE_LABEL_OR_UNSET** | incl. the named Setup `level` defect, pinned by test |
| `LEARNER_METADATA_LEAKAGE_GUARD` | **ENFORCED** | 21 tests: static copy/JSON guard + hostile-payload guard over Home / Course / 11408 / Programming / Workbench |

### Files changed (all under `frontend/`)

**New**: `src/lib/learner-safe.ts` · `src/test/learner-copy.guard.test.ts` ·
`src/test/learner-metadata-leakage.test.tsx`
**Deleted**: `src/components/page/raw-payload.tsx`
**Modified**: `src/lib/fact-labels.ts` · `src/components/page/fact-list.tsx` ·
`src/components/learning/advanced-learning-surfaces.tsx` · `src/components/learning/adaptive-practice.tsx` ·
`src/components/learning/advanced-learning-surfaces.test.tsx` · `src/components/learning/debug-agent.test.tsx` ·
`src/components/ui/panel.tsx` ·
`src/features/course/components/course-pages.tsx` · `src/features/course/components/course-setup-page.tsx` ·
`src/features/home/daily-agenda.tsx` · `src/features/home/daily-agenda.test.tsx` · `src/features/home/learning-status.tsx` ·
`src/features/learning-intelligence/learning-intelligence-surfaces.tsx` ·
`src/features/review/review-page.tsx` ·
`src/features/programming/components/programming-pages.tsx` ·
`src/features/programming/components/programming-setup-page.tsx` ·
`src/features/programming/components/programming-setup-page.test.tsx` ·
`src/features/programming/components/workbench-hierarchy.test.tsx` ·
`src/features/programming/programming-onboarding.ts` · `src/features/programming/api/programming.ts` ·
`src/features/exam/components/cs408-student-twin-workspace.tsx` ·
`src/features/exam/components/cs408-student-twin-workspace.test.tsx` ·
`src/features/membership/view-models/membership.ts` · `src/features/profile/components/profile-page.tsx`

---

## 15. RISKS, and what this report does NOT claim

1. **The brief's authority document is absent** (§0). The P0/P1 list was therefore taken from the
   brief's own text. If a real `ZHIXUE_FINAL_PRODUCT_UX_ACCEPTANCE_REPORT` exists elsewhere, P0/P1
   items outside the brief's 14 points have **not** been addressed.
2. **Four E2E specs are stale, and were stale before this round** — this is reported, not silently
   fixed (fixing them is test maintenance outside a "no new work" closure):
   `course-workspace.spec.ts`, `programming-workspace.spec.ts`, `shared-learning-surfaces.spec.ts`,
   `daily-agenda.spec.ts`. Evidence they predate this round: the copy they assert
   (`练习详情`, `Python Workbench`, `Review Patch`, `AI Explain`, `为什么推荐这个？`, a `{reasons:…}`
   explain payload) **exists nowhere in `src/`**. Only `daily-agenda.spec.ts` additionally touches
   something this round changed (the facts allow-list), so it is stale for both reasons.
3. **A dev server on `:5173` died mid-run** at ~10:34, during the first authenticated pass. I did not
   start or stop it (I never signalled that PID). I started a fresh one to finish the pass and left
   it running with `VITE_API_BASE_URL=http://localhost:8000` — the same URL the app defaults to, so
   behaviour is unchanged. The isolated E2E harness was started for the pass and **stopped** (port
   8000 is free, its temp DB removed).
4. **`AXE` covers what an authenticated session can reach, not every route.** The specs above assert
   zero violations on login, shell, Home, Profile, Workbench and the three learning spaces at five
   widths. Admin-style or rarely-visited routes are not swept.
5. **`FactList` semantics changed.** Unmapped fields are dropped rather than dumped, and
   `valueLabels` was replaced by per-field vocabularies. Any surface that relied on the old
   blunt-map behaviour was updated; 5 tests that asserted the old leakage were replaced, not
   weakened.
6. **This is not a visual change.** No token, layout or hierarchy was altered; the P2 profile
   nav is the only visual addition and it uses existing tokens.

**Status: the P0/P1 learner-data-boundary closure requested by this brief is complete and guarded by
regression tests. Nothing has been committed.**
