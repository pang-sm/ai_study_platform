# FRONTEND F1C4 — Canonical Wrong-Answer Workspace Acceptance

## Scope

Implemented `/exam/cs408/wrong` within the CS408 workspace and wired the existing `错题` navigation entry. The page uses only the generated canonical `GET /wrong-answers` transport through `frontend/src/features/exam/api/wrong-answers.ts`.

## Product behavior

- Server-side module, status, and offset pagination filters are URL-persistent.
- Records are keyed by canonical `wrong_record_id`; no index, stem, or local deduplication is used as an identity.
- `active` renders as `未订正`; `resolved` renders as `已订正`. Resolved is historical correction, not mastery.
- Chapter and past-paper source labels are user-facing (`章节练习`, `历年真题`). Past-paper detail carries only module/year/question-number context and links to the existing whole-paper workspace.
- Detail renders the canonical snapshot, answers, non-empty analysis, and normalized image resources through `resolveApiResourceUrl()`; a failed image is isolated to that image.
- There are no wrong-answer mutations, manual resolution controls, frontend grading comparisons, knowledge writes, AI calls, or cross-source retry controls.

## Validation evidence

- `npm run check`: passed — TypeScript, ESLint, 19 test files / 68 tests.
- `npm run build`: passed.
- `npm exec -- playwright test tests/e2e/f1c4-real-vqa.spec.ts --project=chromium`: passed against real FastAPI at `127.0.0.1:8958` and an authenticated, migrated TEMP database.
- Real VQA created chapter and past-paper factual wrong records, repeated an incorrect chapter answer, submitted a correct retry and observed `resolved`; it also verified blank choice and subjective self-review do not grow the canonical list, another module has no leak, user B cannot see user A's records, and anonymous canonical access is denied.
- Desktop and mobile screenshots were written to `%TEMP%/f1c4-real/screenshots`; the Playwright run verified no horizontal overflow, no browser console errors, and zero Axe violations in `.wrong-answer`.
- TEMP DB was made from a SQLite backup of `backend/app.db`, then upgraded through `20260919_0009`. Its integrity check returned `ok`; the source database SHA-256 remained `1C1B2D8538D7A3C52A79A64DEC904C69C6EC964B86DECBC6508D0D2A438FE522` and its mtime was unchanged.

## Final gates

| Gate | Result |
| --- | --- |
| WRONG_ROUTE | PASS |
| CANONICAL_WRONG_API_ONLY / LEGACY_WRONG_API_CALLS | PASS / 0 in F1C4 implementation |
| MODULE_FILTER / STATUS_FILTER / PAGINATION | PASS |
| UNANSWERED_WRONG_VISIBLE / SELF_REVIEW_WRONG_VISIBLE | 0 / 0 |
| CHAPTER_CORRECT_RETRY_RESOLUTION_REAL | PASS |
| PAST_PAPER_WRONG_CONTEXT_REAL | PASS |
| CROSS_USER_WRONG_ACCESS / WRONG_MODULE_CROSS_LEAK | 0 / 0 |
| FRONTEND_GRADING_COMPARISON / FRONTEND_WRONG_RECORD_WRITE / FRONTEND_MANUAL_RESOLVE_WRITE | 0 / 0 / 0 |
| DESKTOP_VISUAL_QA / MOBILE_VISUAL_QA / AXE_VIOLATIONS / CONSOLE_ERRORS | PASS / PASS / 0 / 0 |
| BACKEND_FILES_CHANGED / GENERATED_API_CHANGED / REAL_APP_DB_MUTATED | 0 / NO / NO |
