# Mobile IA Refactor Report

## Scope and changes

Only Mobile frontend files were changed. No backend, database, API contract, PC Web, authentication, or production configuration was changed.

- `frontend/src/mobile/MobileApp.jsx`
  - Adds a persisted learning-space state (`course` or `exam`) and space-aware bottom navigation.
  - Rebuilds Profile as the learning-space entry point, with account actions limited to existing APIs.
  - Separates course and 11408 navigation destinations instead of cross-linking course practice to 11408.
  - Renames the course study screen to `知识点` and keeps the real course → chapter → knowledge-point tree.
  - Replaces the knowledge-point metrics modal with a bottom sheet containing only point name, mastery selection, AI explanation, practice, and save.
  - Saves mastery through the existing `PATCH /api/knowledge-map/progress` endpoint and refreshes the map after a successful save.
  - Replaces the mixed AI-mode card group with one context-aware new-chat action plus real-history categories: 全部 / 课程学习 / 11408考研 / 普通AI.
  - Renames visible 11408 `AI预测` labels to `AI智能训练`; the data remains the existing AI-question API.
- `frontend/src/mobile/MobileApp.css`
  - Adds styles for history categories, learning-space cards, and the safe-area bottom-sheet mastery selector.

## New IA

Global Mobile navigation stays five-tab, but routes resolve within the active learning space.

| Learning space | Home | Knowledge / chapter | AI | Practice | Profile |
| --- | --- | --- | --- | --- | --- |
| 课程学习 | `/m` | `/m/learn` (知识点) | `/m/ai?space=course` | `/m/tasks` | `/m/profile` |
| 11408考研中心 | `/m/11408` | `/m/11408?section=plan` | `/m/ai?space=exam` | `/m/11408?section=papers` | `/m/profile` |

Profile is now the only learning-space switch point. It provides two independent entries:

- 课程学习：大学课程学习体系
- 11408考研中心：真题、错题、计划、AI训练

The course practice screen no longer exposes a direct 11408 jump. 11408 keeps its own subject, plan, paper, wrong-question, and AI-training sections.

## Reused APIs

- Account: `GET /api/me/profile`, `PUT /api/me/profile`, `PUT /api/me/password`, `POST /api/me/avatar`, email binding endpoints.
- Courses and knowledge map: `GET /api/course-learning/courses`, `GET /api/knowledge-map`, `PATCH /api/knowledge-map/progress`.
- Course practice: `GET /api/practice/questions`, `POST /api/practice/submit-result`.
- AI: `GET /api/chat/history`, `GET/DELETE /api/chat/sessions/{id}`, `PUT /api/conversations/{id}`, existing `/api/chat` flow.
- 11408: study-plan, task summary, past-paper, wrong-question, and AI-question endpoints already used by Mobile.

## Backend-limited capabilities

- The knowledge-map write API accepts only `not_started`, `learning`, `review_due`, and `mastered`. Therefore the selector exposes their truthful user labels: 未掌握、一般、薄弱、掌握. `熟练` has no distinct persistable server value and is explicitly not fabricated.
- No confirmed profile-signature write field exists in the reused profile API. Profile displays a real returned signature/bio when supplied, otherwise `个性签名暂未提供`.
- The current 11408 paper API supplies paper records but no reusable Mobile paper-attempt/deep-link contract was found in this scope. The page shows returned paper data and does not add inert “开始训练” buttons.
- The server has no conversation-pin endpoint; no local fake pin state was introduced.

## Verification

Commands run from `frontend/`:

- `npm.cmd run build` — PASS. Latest local bundle: `dist/assets/index-BcUNP3E0.js`.
- `npm.cmd exec eslint src/mobile/MobileApp.jsx` — PASS (no output, exit 0).

Browser verification used `http://localhost:5173/m` in the in-app browser:

| Viewport | Route guard | Horizontal overflow | Console errors |
| --- | --- | --- | --- |
| 360×800 | PASS: login screen rendered | None | None |
| 390×844 | PASS: login screen rendered | None | None |
| 412×915 | PASS: login screen rendered | None | None |

Authenticated IA interactions (Profile switching, course data tree, mastery save, 11408 data, and AI history classification) remain **not browser-verified in this run** because this browser had no authenticated existing test session and no credentials were supplied for this task. No authentication was bypassed or injected.

## Result

The Mobile-only IA implementation and static checks are complete. Production deployment was not performed. Authenticated end-to-end browser acceptance remains blocked pending a valid existing test session or user-provided test credentials.
