# FRONTEND_F1A_FOUNDATION_ACCEPTANCE_REPORT

> 智学AI · F1A App Foundation + OpenAPI Contract Refresh + Exam Route/Shell Foundation
>
> Date: 2026-09-17 · Backend: frozen and unmodified

## 1. Baseline / Git Safety

The required baseline was recorded before work:

```text
git status --short       → existing dirty work, including backend changes and Phase 7 untracked files
git diff --name-only     → existing user/backend changes recorded
git diff --stat          → existing user/backend changes recorded
git log -1 --oneline     → ebad5282 merge: reconcile local clean-slate frontend/governance with origin backend intelligence
```

No forbidden Git operation was run. No branch, worktree, stash, commit, reset, clean, restore, merge, rebase, pull, push, or backend mutation occurred.

## 2. Existing Homepage Visual Baseline

Current homepage was served and captured before editing at 1440×900 and 390×844.

```text
F1A_VISUAL_BASELINE
Header: deep-ink academic band; official desktop lockup / mobile icon; subtle divider
Canvas: warm paper for editorial areas; deep ink Focus hero
Typography: large compact Chinese editorial display, small tracked metadata, precise hierarchy
Structure: ruled dividers, blue structural marks, restrained coral focus/action colour
Interaction: short, purposeful selection and hover movement; mobile navigation collapses to controls
```

The post-change homepage was recaptured at 1440×900. Its logo alignment, header height, dark header character, hero typography, canvas colour, primary action, and mobile collapse remain unchanged. The only header content change is that the formerly dead “探索学习” anchor is now the real `/exam` link labeled “考研学习”.

## 3. OpenAPI Regeneration

The frozen backend was started only for type generation with an explicit, unique temporary SQLite `DATABASE_URL` outside the repository. `backend/app.db` was not read or opened.

```text
npm run api:generate = PASS
```

`frontend/src/types/api.ts` now contains these generated canonical paths:

```text
/exam/prep/profile
/exam/prep/catalog
/exam/prep/subjects/{subject_id}/content-status
```

The generated contract also retains the relevant existing CS408 content paths, including dashboard summary, chapter-practice outline, past papers, and wrong questions.

## 4. Exam Generated Contract

All frontend transport access remains through `openapi-fetch` and the generated `paths` type. The new `getExamSubjectContentStatus` helper calls the generated canonical content-status endpoint and returns its generated response unchanged. `ApiRequestError` preserves only HTTP status plus opaque response detail for error normalization; it is not a hand-written backend DTO.

## 5. API Error Model

`features/exam/api/errors.ts` establishes a small, user-safe normalization layer:

| HTTP / detail | Visible state |
| --- | --- |
| 401 | 请登录后继续 |
| 403 | 当前功能需要升级后使用 |
| 409 + `EXAM_CONTENT_NOT_AVAILABLE` | content-unavailable product state |
| 429 | 本次额度已用完，请稍后再试 |
| 502 | 服务暂时不可用，请稍后再试 |
| no status | 网络连接异常，请检查网络后重试 |

It accepts both string and structured `detail`, and does not expose service keys, provider IDs, quota keys, tracebacks, or raw request details.

## 6. Route Foundation

Implemented routes:

```text
/exam
/exam/setup
/exam/subjects
/exam/subjects/$subjectId
/exam/cs408
```

They are intentionally foundation-only: no F1B profile form, catalog, CS408 dashboard, invented metrics, or deeper learning routes have been created. The generated TanStack route tree was refreshed by the configured router plugin.

## 7. AppShell Changes

`AppShell` keeps the existing official branding, header geometry, search/account affordances, colours, and responsive behavior. Its only navigation change replaces the dead in-page learning anchor with an actual typed `/exam` route. No unavailable global route is linked.

## 8. Exam Context Navigation

`ExamPageShell` provides a warm-paper application canvas, compact Exam Prep identity line, and a reusable context navigation bar:

```text
我的备考 | 科目 | CS408
```

The navigation is subordinate to the global header, uses exact-route active semantics, keeps 44px minimum target height, scrolls horizontally without clipping at narrow widths, and has no permanent sidebar or pill overload.

## 9. Availability Primitives

`SubjectAvailabilityBadge` supplies the frozen visible terminology:

```text
active           → 可学习
framework_only   → 内容建设中
```

`ContentUnavailableState` is a first-class editorial state: it accepts a display name, gives the prescribed explanatory copy, supports return-to-subjects and profile-edit actions, and deliberately contains no red alert, fake metrics, disabled chapter tree, or skeleton content.

## 10. Status Terminology

```text
not_started  → 未学习
learning     → 学习中
mastered     → 已学习
review_due   → 待复习

wrong resolved/mastered boolean → 已解决
```

“已掌握” is not used for either knowledge or resolved wrong answers.

## 11. Responsive Behavior

| Viewport | Verified behavior |
| --- | --- |
| 1440×900 desktop | Header, context navigation, page width, ruled editorial shell, and homepage composition render correctly. |
| 1024×768 tablet | Context links remain labelled, visible, and unclipped; no permanent rail appears. |
| 390×844 mobile | Brand collapses to icon, context nav remains labelled and horizontally usable, and unavailable state buttons wrap safely with 44px targets. |

## 12. Accessibility

- One page heading per route; semantic `nav` with an accessible name.
- Exact active route receives `aria-current="page"`; parent route no longer incorrectly announces as current.
- The context-navigation list role was removed because links are not permitted children of an ARIA list without listitem roles.
- The small Exam label uses the stronger primary-blue token so its warm-paper contrast exceeds WCAG AA.
- Existing visible focus rings and reduced-motion baseline remain in effect.

## 13. Tests / Build

```text
npm run check
  typecheck = PASS
  lint      = PASS
  unit      = PASS (5 files, 14 tests)

npm run build = PASS
npm run test:e2e = PASS (5 Chromium tests)
```

Focused coverage includes generated-path content-status access, structured/string API error normalization, route availability, exact context-nav active state, availability terminology, dedicated unavailable state, terminology mapping, responsive overflow, browser navigation interaction, console health, and axe.

## 14. Browser Visual QA

Browser plugin was not available; the repository’s configured Playwright workflow was used.

| Surface | Result |
| --- | --- |
| Homepage, desktop | PASS — no visual regression against the captured Learning Lab baseline. |
| `/exam`, desktop | PASS — compact contextual shell retains the product’s header and editorial paper surface. |
| `/exam/subjects`, tablet | PASS — labelled navigation remains visible and active state is clear. |
| `/exam/subjects/math_1`, mobile | PASS — dedicated content-unavailable state has no fake study content and actions remain usable. |

The browser interaction test exercised `/exam/subjects → CS408 → framework-only URL → 返回科目`, asserted URL/state transitions, checked console errors, and reported `AXE_VIOLATIONS = 0`.

## 15. Backend Contract Gaps

### FRONTEND_BACKEND_CONTRACT_GAP — typed response schemas

The regenerated `/exam/prep/profile`, `/exam/prep/catalog`, and `/exam/prep/subjects/{subject_id}/content-status` successful responses are present but emitted as `unknown` by the frozen OpenAPI document because the backend endpoints do not declare response models. F1A therefore does not hand-write duplicate transport DTOs or parse/display catalog/profile fields. The content-status query boundary is intentionally opaque and ready for generated schemas.

**FUTURE_AUTH_SURFACE:** no new login page was built. A protected query can normalize 401, but a product-level login destination is not implemented in this Clean-Slate frontend and must be designed/audited separately.

## 16. Changed Files

```text
frontend/src/components/layout/app-shell.tsx
frontend/src/features/exam/api/content-status.ts
frontend/src/features/exam/api/content-status.test.ts
frontend/src/features/exam/api/errors.ts
frontend/src/features/exam/components/content-unavailable-state.tsx
frontend/src/features/exam/components/exam-context-nav.tsx
frontend/src/features/exam/components/exam-foundation-page.tsx
frontend/src/features/exam/components/exam-foundation.test.tsx
frontend/src/features/exam/components/exam-page-shell.tsx
frontend/src/features/exam/components/subject-availability-badge.tsx
frontend/src/features/exam/view-models/status-labels.ts
frontend/src/routes/exam.tsx
frontend/src/routes/exam/**
frontend/src/routeTree.gen.ts                 # router-generated
frontend/src/types/api.ts                     # OpenAPI-generated
frontend/src/test/setup.ts
frontend/tests/e2e/smoke.spec.ts
FRONTEND_F1A_FOUNDATION_ACCEPTANCE_REPORT.md
```

`BACKEND_FILES_CHANGED = 0` by F1A. Existing unrelated backend modifications and untracked Phase 7 files were preserved untouched.

## 17. Final Gates

```text
OPENAPI_TYPES_REGENERATED = PASS
EXAM_PREP_GENERATED_TYPES = PASS
HAND_WRITTEN_TRANSPORT_DTOS = 0
BACKEND_FILES_CHANGED = 0

EXAM_ROUTE_FOUNDATION = PASS
EXAM_APP_SHELL = PASS
EXAM_CONTEXT_NAV = PASS
FRAMEWORK_ONLY_PRIMITIVE = PASS
EXAM_CONTENT_NOT_AVAILABLE_STATE = PASS
KNOWLEDGE_STATUS_VISIBLE_MAPPING = PASS
WRONG_RESOLVED_VISIBLE_MAPPING = PASS

HOMEPAGE_VISUAL_REGRESSION = NO
RESPONSIVE_FOUNDATION = PASS
AXE_VIOLATIONS = 0

TYPECHECK = PASS
LINT = PASS
UNIT_TESTS = PASS
BUILD = PASS
E2E = PASS

FRONTEND_F1A_COMPLETE = YES
FRONTEND_F1B_READY = BLOCKED_BY_TYPED_EXAM_RESPONSE_CONTRACT
BLOCKERS = Generated Exam Prep success responses are unknown; do not hand-write DTOs.
```
