# FRONTEND_F0_PRODUCT_UI_ARCHITECTURE

> 智学AI · Frontend F0 Product/UI Architecture
>
> Status: **FROZEN DESIGN — no frontend or backend implementation in F0**
>
> Date: 2026-09-17 · Authority order: `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` → current read-only repository facts → this document.

## 1. Current Frontend Audit

### 1.1 Verified baseline

| Area | Current fact |
| --- | --- |
| Product phase | `NEXT_SUBSTEP = FRONTEND`; new full frontend is `NOT_STARTED`. |
| Runtime / build | React 19.2.8, Vite 8.2.2, TypeScript 5.9.3, Node >=24. |
| Routing | TanStack Router file routes; current route tree contains only `/`. |
| State / forms | TanStack Query v5, React Hook Form, Zod 4. |
| Styling | Tailwind CSS 4 plus `src/styles/tokens.css`; Lucide is the sole icon library. |
| API | `openapi-fetch` client at `src/lib/api/client.ts`; generated contract at `src/types/api.ts`. |
| Quality baseline | Vitest + RTL, Playwright + axe, ESLint jsx-a11y. |
| Existing app UI | Root shell, error/not-found state, Button/Container/Skeleton/Spinner, and the new homepage only. |

The existing routes are exactly:

```text
/                         HomePage
```

There is no restored Course, Exam, Programming, Dashboard, Membership, Profile, login, or admin page. This is correct and must remain so.

### 1.2 Current implementation facts that guide F1

- The global `AppShell` has a dark academic header, the official logo assets, search and account affordances, a mobile menu trigger, and desktop navigation that currently contains only Home and an in-page learning anchor.
- The homepage itself is an editorial **Learning Lab** composition: one concrete learning question, an interactive virtual-memory diagram, a strong continuation cue, then three asymmetric learning-space rows.
- The code-level tokens already carry the shared neutral, semantic, domain-accent, layout, shadow, and motion vocabulary. F1 extends them; it does not replace them or introduce per-page magic values.
- `reference/PAGE/homepage/homepage_v9_*` is a useful historical visual reference, but its light V9 header/layout does not exactly match the current shipped `AppShell` and Learning Lab homepage implementation. **F1 takes the actual current implementation and tokens as the executable visual anchor; the V9 references are secondary evidence, not an instruction to revert the header.**

### 1.3 Audit conclusions and constraints

1. The first application surface must retain the homepage's task-first logic: current context → next action → path → tools.
2. Exam Prep is a single learning space. The frontend must use the canonical product label **考研学习 / Exam Prep**, never elevate legacy 11408 to a top-level product.
3. Only CS408 has real content. Every non-CS408 subject is selectable but framework-only; it never receives invented progress, chapters, question totals, papers, recommendations, or learning analytics.
4. F0 does not change code, dependencies, routes, backend, database, SSOT, or generated API types.

## 2. Existing Homepage Visual Language

### EXISTING_VISUAL_LANGUAGE

| Dimension | Observed, implemented language |
| --- | --- |
| Typography | `Inter, PingFang SC, Microsoft YaHei, system-ui`; display typography is compact and bold with negative tracking; Chinese editorial headings use `clamp()` scale, approximately 48–96px in the hero; page/section/body/meta tokens are 32/24/15/13px. Labels use small uppercase, tracking, and tabular numerals. |
| Color | Warm paper canvas (`lab-paper` / `#e8e5da`) paired with deep ink (`#0c1730`); primary blue supports structure and selection; coral is the high-attention action/coordinate accent. Semantic blue/green/amber/red remain available for product state. |
| Surface | The homepage uses a dark Focus hero, a warm editorial canvas, ruled divisions, and object-like rows. It avoids an all-white card grid. Borders and background contrast do more work than shadows. |
| Spacing / measure | Full-width editorial composition, with a 1344px visual alignment rule; content pages have 1280px, workspace 1440px, and reading 820px tokens. Hero and section spacing are intentionally generous; object rows are dense enough to scan. |
| Shape | Mostly square or lightly rounded interfaces. Existing radii are 6/8/12/16/20px; application pages should favour 8–12px controls/objects and reserve 16–20px for special focus surfaces. |
| Motion | Short, purposeful 150–200ms transitions: selection, diagram-path movement, row hover, and a small upward action response. Reduced-motion rules remove transitions. There is no decorative scroll choreography. |
| Iconography | Lucide for controls; thin, geometry-led inline SVG only for the three learning-space motifs. Icons support labels rather than replacing them. |
| Layout / responsive | Desktop is asymmetric and diagram-led; at 900px it rebalances, and at 640px it becomes a single-column composition with retained hierarchy. Header navigation collapses to a menu. |

### Homepage-to-application relationship

**Keep:** official logo and header character; warm paper/deep-ink/blue/coral base language; typographic contrast; ruled dividers; explicit current/next-action framing; line-and-node motifs; restrained 150–200ms state motion; focus visibility and reduced-motion behavior.

**Change for application work:** make reading and answer areas quieter; use denser, task-oriented layouts; add persistent but shallow contextual navigation; use stable tables/lists/outline rows where information density needs them; reduce decorative diagrams; use domain indigo only as a small Exam Prep accent.

## 3. Design Problems / Constraints

- A left enterprise sidebar would compete with reading, answering, and the homepage's editorial character.
- A top-only tab system cannot keep CS408 context visible on a long, high-density knowledge or practice page.
- Four giant module cards would turn the only active subject into a directory, not a study workspace.
- “Coming soon” cards conceal a meaningful product fact: a framework-only subject can be added to a profile now, but cannot be studied yet.
- Current backend contract provides factual progress and practice results in specific endpoints; it does **not** provide predictive readiness, admission probability, AI recommendations, or personalized model information.
- The legacy CS408 content API still uses `/exam/11408/*`; user-facing canonical URLs must not mirror that legacy transport path.

## 4. Product Information Architecture

Global navigation is intentionally shallow:

```text
首页
学习
  ├─ 课程学习
  ├─ 考研学习
  └─ 编程学习
资料
学习记录
我的
  ├─ 会员与额度
  └─ 设置
```

`学习` is a space chooser, not a permanent mega-menu. Home always remains the personal entry point. Within a learning space, navigation is contextual and only reveals tools relevant to that space.

The F1 scope starts with the Exam Prep branch. Global Materials, cross-space Records, account, membership, and the Course/Programming branches need their own backend-contract audits before implementation; they are not implicitly approved by this document.

## 5. Global App Shell Options

### A. Top sub-navigation only

Global header followed by an Exam Prep horizontal tab row. My Exam, Subjects, CS408, and CS408 tools are all visible in one or two rows.

- Strength: closest to the homepage; smallest desktop footprint.
- Cost: too many competing items once CS408 tools appear; horizontal overflow is poor on laptop and mobile.

### B. Persistent left sidebar

Global header and a 256px Exam Prep sidebar containing every destination.

- Strength: constant orientation and high navigation density.
- Cost: reads as an enterprise dashboard, reduces answer/read width, and collapses badly on tablets. It conflicts with the editorial homepage anchor.

### C. Mixed contextual rail — **recommended**

Global header contains only product-level routes. An Exam Prep page has a compact context bar (`考研学习 / 我的备考 / 科目`) and, only below the CS408 boundary, a 48–56px icon-and-label rail or compact secondary tab row for `概览 / 知识脉络 / 练习 / 真题 / 错题 / 计划 / 记录`. On desktop the rail may stick inside the content column; on tablet/mobile it becomes a horizontally scrollable labeled subnav or sheet menu.

- Strength: retains learning focus and adequate reading width, makes the active subject explicit, and scales from My Exam to the focused CS408 workspace without a giant sidebar.
- Cost: requires clear active-state and back/breadcrumb rules.

## 6. Recommended Shell

Choose **C: mixed contextual rail**.

```text
Global Header (product scope)
  Logo | 首页 | 学习 | 资料 | 学习记录 | search | membership/account

Page Context Bar (space scope)
  首页 / 学习 / 考研学习    [我的备考] [科目] [CS408]

CS408 only: Subject Context
  计算机学科专业基础 408 · 当前模块/路径
  概览 | 知识脉络 | 练习 | 真题 | 错题 | 计划 | 记录

Main Content (task scope)
```

Rules:

- Desktop uses the context bar plus a left contextual rail only within CS408 task pages; My Exam and Subjects remain full-width editorial pages.
- A breadcrumb is a location aid, never the primary navigation. It appears from depth three (`考研学习 / CS408 / 真题 / 2025`) onward.
- The user/account menu exposes membership and usage from a global account surface rather than duplicating pricing/usage widgets across pages.
- Search does not become a fake universal command palette in F1; its behavior must wait for an actual search contract.

## 7. Exam Prep IA

```text
/exam                         我的备考 (profile-led landing)
/exam/setup                   选择方向、科目、目标年份
/exam/subjects                全部可选科目与内容状态
/exam/cs408                   CS408 workspace
  /knowledge                  知识脉络
  /practice                   章节练习
  /past-papers                真题
  /wrong                      错题
  /plan                       学习计划
  /records                    学习记录
```

The logical sequence is profile → subject availability → active CS408 learning. It is not `four modules → analytics dashboard`.

## 8. My Exam Page

**Visual idea: an exam dossier with one active study path.**

The page opens with a quiet editorial identity block: `全国统考研究生考试`, target year when set, selected track when set, and a single primary action. When a profile is absent, the action is `设置我的备考`; when CS408 is selected and active, it is `继续学习` and resolves to the most recently actionable module/plan item only when the returned data supports it. Otherwise it is `进入 CS408`.

Below it:

1. **My subjects** — a ruled list, grouped by “可开始学习” and “已加入，内容建设中”; not a same-size card grid.
2. **CS408 focus strip** — four module rows with only real overview fields; entry points to knowledge, practice, or past papers. Do not calculate a cross-module readiness score.
3. **Current tasks** — at most three real tasks from dashboard-summary/study-plan, ordered as returned. Absence becomes an explicit “还没有学习任务” action, never a fabricated recommendation.

No forecast, ranking, admission probability, or progress for framework-only subjects is allowed.

## 9. Subject Selection

**Visual idea: choose an exam scope, not a prepackaged course bundle.**

Use a two-step, reviewable form:

1. Choose an available national unified-exam direction (`selected_track`) or leave it unset.
2. Choose actual `selected_subjects` from the catalog, grouped as public/professional, and set an optional target year.

Track suggestions are visual hints only. They never silently add or remove subjects because `suggested_subjects` is non-authoritative and may be empty. The review footer shows the selected list, a distinct target-year label, and `保存备考设置`. Free users can save this profile.

## 10. Framework-only UX

**State name:** `内容建设中` / `EXAM_CONTENT_NOT_AVAILABLE`.

Framework-only subjects are selectable objects, shown with a quiet availability badge and a concise truth statement:

> 已开放加入我的备考，学习内容将后续开放。

Their button behavior is deterministic:

- In the selector: checkbox/select control remains enabled.
- On My Exam: `查看状态` opens a dedicated content-unavailable page or inline state; it does not enter a fake workspace.
- Direct content URL or a 409 response: render the state with subject name, the profile-selection action, and `返回科目`; do not retry, create placeholder pages, or fall back to CS408.

The unavailable page uses an editorial notice and a small subject-outline motif, not a grey disabled card or red error alert. It contains no metrics, skeleton chapter tree, or fake AI callout.

## 11. CS408 Home

**Visual idea: a focused exam workbench with four connected disciplines.**

The CS408 home is headed by the real subject name and a slim subject-level orientation line. Its primary focus surface identifies the current actionable module and one action (`继续知识学习`, `开始章节练习`, or `进入真题`) based only on actual summary/plan data.

Then show a vertical four-module index, not four large cards:

```text
01 数据结构             [知识脉络] [练习] [真题]
02 计算机组成原理       [知识脉络] [练习] [真题]
03 操作系统             [知识脉络] [练习] [真题]
04 计算机网络           [知识脉络] [练习] [真题]
```

Each row may use factual counts/status returned by its summary. A thin path line and one domain-indigo active marker provide structure. Wrong answers, plan, and records remain contextual tools, not hero tiles.

## 12. Knowledge UI

### Options compared

| Pattern | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| Graph visualization | Attractive at a glance | Implies relations unavailable in the contract; weak keyboard/mobile navigation | Reject |
| Tree outline | Directly reflects chapter → section → knowledge-point hierarchy; concise and keyboard friendly | Needs a contextual detail view | **Choose** |
| Two-column explorer | Fast scanning at desktop | Too wide/complex for first implementation and mobile | Defer as an enhancement |

Use a structured outline. The left/main outline shows module → chapter → section → knowledge point with real statuses (`not_started`, `learning`, `mastered`, `review_due`) only where the study-plan/knowledge response returns them. Selecting a point opens a right desktop detail panel (or mobile sheet) with path, status, next action, and related chapter-practice entry. The rail context remains visible; the knowledge content itself gets the reading width it needs.

## 13. Practice UI

**Visual idea: a paper-like answer desk.**

Desktop has a slim top context bar (`模块 / 章节 / 第 n 题`) and optional collapsible outline; the question and answers sit in an 820px reading column. The primary action is always `提交答案`. For multiple choice, use large labeled options; for subjective questions, use a labeled text field with remaining context, not a chat interface.

After submission, reveal a separate result region below the answer: correctness/score, reference answer, explanation, related knowledge point, wrong-answer result, and a contextual `让 AI 解释` action when eligible. AI refusal cannot undo the durable answer submission. Mobile hides the outline in a sheet, maintains a sticky safe-area-aware submit bar, and preserves question position after submission.

## 14. Past Papers UI

Show an editorial year selector with the actual available years returned by `/past-papers` (currently 2022–2026 per the handoff) and a single `开始作答` action for the selected paper. Do not emulate a PDF viewer by default.

Paper mode reuses the answer desk but adds paper title/year, a compact numbered-question navigator, autosaved-answer feedback only if the endpoint confirms it, and a `交卷并查看结果` final action. Results distinguish objective correctness from subjective/reference feedback; they do not claim a predictive score. Review routes back to question positions and newly written wrong answers.

## 15. Wrong Answers UI

**Visual idea: a review queue, not a mastery gallery.**

Default to active wrong answers. Filter by source, module, and state only when the backend supplies those values. Each compact object contains question excerpt, type, source/year, knowledge path, last answer, and a direct `重新练习`/`查看解析` action. A separate `已解决` filter represents the endpoint’s `mastered` boolean only as **“标记为已解决”**; it must never be labeled “已掌握”. The detail view keeps source and explanation near the question, without card nesting.

## 16. Plan UI

Plan is a task list with a subject context and optional settings panel, not a forecast. It displays real `tasks`, task type/status/due date, knowledge-item status, and chapter-practice completion. One primary action exists per context: create a task when none exists, or complete/continue the current task.

Planning-generation UI is capability-gated. The client responds to `403` with an upgrade explanation and preserves manually available planning data. It does not show plan generation as a universal default, nor does it expose legacy plan names from a response.

## 17. Records UI

Records are chronological learning history grouped as `今天 / 本周 / 更早`, derived from real done-records and/or the subject summary where fields exist. Each row explains a learner-visible event: completed practice, submitted paper, updated knowledge status, or created/finished task. Raw event IDs, provider IDs, and implementation data never appear. An empty state says why it is empty and links to a real next action.

## 18. AI UX

AI appears in context: answer explanation after a submission, question analysis from a question detail, permitted question generation within Practice, or plan generation within Plan. It is never a floating orb and not a separate mandatory chatbot.

- Default is `自动推荐`; only API-provided qualified choices may be offered later.
- No provider registry, model identifiers, raw cost, or internal credits formula is exposed.
- 403 = capability upgrade state; 429 = usage exhausted state; 502 = technical retry state. These three states have different copy/actions.
- AI output remains subordinate to the durable learning action. A response cannot replace a factual answer, attempt, wrong-answer state, or record.

## 19. Membership / Usage UX

Membership is one shared product surface with Free / Standard / Advanced. It explains learner-visible capabilities and remaining usage only when an actual global contract is available. It must never revive per-space membership plans or display internal provider cost arithmetic.

Inside Exam Prep, capability denial uses a contextual non-blocking upgrade panel. It refers to the user’s current action (for example, “学习计划功能需要升级”) and never hard-codes a tier or legacy plan identifier.

## 20. Responsive Strategy

| Breakpoint | Shell | Page behavior |
| --- | --- | --- |
| Desktop >= 1024px | Global header + context bar; CS408 contextual rail may stick | 1280px general content, 1440px workspace, 820px answer/read column; outline + detail panel where useful. |
| Tablet 641–1023px | Context rail turns into horizontal labeled subnav | Two columns collapse deliberately; My Exam uses list rows, not squeezed cards; knowledge detail becomes a drawer. |
| Mobile <= 640px | Header nav in drawer; context navigation in horizontally scrollable tabs/sheet | Single column; subject selection preserves review footer; question submit bar sticks above safe area; outline/filter/detail move to sheets. |

No desktop-only sidebar is permitted. All controls preserve 44px minimum touch targets, visible selected state, and non-color state labels.

## 21. Accessibility

F1 target: retain homepage’s axe-zero-violation standard.

- Semantic landmarks (`header`, `nav`, `main`, `aside` only where complementary), one page `h1`, and ordered headings.
- Keyboard-operable tabs, outline disclosure, filter controls, question navigator, dialogs, and subject selection; visible 2px focus ring supplied by existing base CSS.
- Text plus icon/shape/status label for every state; contrast-compliant body text and non-text boundaries.
- Proper labels and error summaries for profile form fields; validation focuses the first invalid control.
- Answer choices are native controls with explicit checked state; status changes announce via an appropriate live region without interrupting reading.
- `prefers-reduced-motion` disables nonessential transitions; no action requires drag, hover, colour alone, or motion.

## 22. Motion

Use the existing `--duration-fast` (150ms), `--duration-base` (200ms), and `--ease-standard` only for navigation active-state continuity, outline expand/collapse, answer feedback, selection, and skeleton-to-content transition. Avoid page-entry spectacle, looping decoration, and motion in the reading/answer path. Respect the global reduced-motion rule.

## 23. Design System Extension

F1 extends the current token system minimally:

| Primitive | Specification |
| --- | --- |
| Page widths | Use existing `content` 1280px, `dashboard/workspace` 1440px, and `reading` 820px tokens. |
| Surface hierarchy | Canvas = warm page background; Editorial = borderless typography/divider region; Focus = deep ink or restrained exam-indigo action region; Object = white/light surface with 1px border. |
| Borders / radius / shadow | Existing border-default, 6/8/12/16px radius scale, card shadow only on object hover. No new visual values without a justified token change. |
| Navigation | Global text navigation; context tabs use underline/ink/brand state; contextual rail uses icon + label + tooltip, never icon only. |
| Buttons / inputs | Existing Primary/Secondary/Ghost/Danger hierarchy; one primary per visual region; RHF fields with label, help, error, and disabled semantics. |
| Status badge | Compact label + text: Active, 内容建设中, 学习中, 待复习, 已解决. It augments rather than replaces the source status. |
| Empty / error pattern | Editorial explanation, one next action, and only meaningful motif; Skeleton for loading. `EXAM_CONTENT_NOT_AVAILABLE` is a dedicated product state, not generic ErrorState. |
| Content pattern | Ruled list/outline for taxonomy and history; object card only for a subject/task/question that has an independent action. |
| Question container | 820px paper-like reading surface, explicit metadata line, accessible answer controls, one sticky submit action on mobile. |
| Knowledge item | Disclosure row with code/title/path/status/action; expansion does not make state claims beyond response fields. |
| Module navigation | Numbered vertical index with thin path-line and domain-indigo active marker; module name is always textual. |

## 24. Route Tree

```text
/
├─ /learning                         # later space chooser
├─ /materials                        # later, separate contract audit
├─ /records                          # later global records contract
├─ /account                          # later account/membership contract
└─ /exam
   ├─ /                              # My Exam
   ├─ /setup                         # profile setup/edit
   ├─ /subjects                      # catalog / availability
   ├─ /subjects/$subjectId           # active status or framework-only state
   └─ /cs408
      ├─ /                           # subject workbench
      ├─ /knowledge
      ├─ /practice
      │  └─ /$attemptId              # active chapter practice attempt
      ├─ /past-papers
      │  ├─ /$year                   # paper start/detail
      │  └─ /$year/attempts/$attemptId
      ├─ /wrong
      │  └─ /$wrongId
      ├─ /plan
      └─ /records
```

Frontend URLs remain canonical. The legacy `/exam/11408/*` transport layer is hidden in feature hooks/query functions; it does not determine routes or UI labels.

## 25. Frontend API Usage Matrix

All calls use the shared cookie-capable `openapi-fetch` client and TanStack Query. “Auth” below means the session cookie `ai_session` unless the source endpoint is explicitly public.

| UI surface | Endpoint / method | Auth | Request | Response fields actually used | Error state | Status |
| --- | --- | --- | --- | --- | --- | --- |
| My Exam / setup | `GET /exam/prep/profile` | Yes | — | `configured`, `exam_type`, `selected_track`, `selected_subjects`, `target_exam_year`, `subjects[]` availability flags | 401 login | Ready |
| Subject selector | `GET /exam/prep/catalog` | No contract auth stated | — | version, tracks, subjects, category, availability, content flags, modules, active/framework IDs | generic fetch/network | Ready |
| Save setup | `PUT /exam/prep/profile` | Yes | selected track/subjects/year | same profile payload | 400 form error; 401 login | Ready |
| Subject availability | `GET /exam/prep/subjects/{id}/content-status` | No contract auth stated | subject ID | active flags and `modules[]` | 404 return to subjects; 409 dedicated unavailable state | Ready |
| CS408 module landing | `GET /exam/11408/subjects/{k}/dashboard-summary` | Yes | module ID | `overview` counts/progress/time, `today_plan[]` title/type/status/date, materials only if used | 401 / source error | Ready, response needs generated types |
| CS408 plan / knowledge state | `GET /exam/11408/subjects/{k}/study-plan` | Yes + entitlement | module ID | course/subject labels, settings, tasks, chapter tree, leaf stats/statuses, completion fields | 403 upgrade; 404 empty data; 500 retry | Ready, response needs generated types |
| Knowledge status write | `PATCH /exam/11408/subjects/{k}/study-plan/knowledge-items/{code}` | Yes + entitlement | intended status payload | updated progress/node status | 400 inline; 403 upgrade | Ready, payload/type audit in F1 |
| Chapter practice outline | `GET /exam/11408/{k}/chapter-practice/outline` | Yes | module ID | returned chapter/section/question metadata | 401 / 404 empty | Ready, response needs generated types |
| Chapter practice | `GET /exam/11408/{k}/chapter-practice/questions`; attempt CRUD/submit endpoints | Yes | chapter/node and answer payloads | question stem/options/type/answer state; attempt IDs/status/result/score/explanation as returned | 400 inline; 401; 429 AI only; 502 retry | Ready, payload/type audit in F1 |
| Past paper selector | `GET /exam/11408/{k}/past-papers` | Contract not stated | module ID | actual returned paper/year metadata | 400 unknown module | Ready, response needs generated types |
| Past-paper workspace | questions + attempt create/get/answer/submit endpoints | Yes for attempts | year, attempt ID, answer payload | questions, attempt metadata/status, result list, objective correctness, scores, feedback, wrong count | 400 input; 401; 403/429/502 only on permitted AI grading paths | Ready, payload/type audit in F1 |
| Wrong answers | `GET /exam/11408/{k}/wrong-questions`; patch mastered; delete | Yes | source/mastered filters; wrong ID | source/source label, knowledge path, stem/options, answer, score, reason, status, `mastered`, review/date fields | 400 / 401; destructive action confirm | Ready, response needs generated types |
| Records | `GET /exam/11408/{k}/done-records` | Yes | module ID and documented filters if any | learner-visible type/time/result/source data only | 401 / empty | Ready, response needs generated types |
| AI question/explanation | `GET/POST/PATCH/DELETE /exam/11408/{k}/ai-questions*`; `POST .../question-analysis` | Yes + capability/budget | context/question payload per endpoint | generated question or analysis content, only when returned | 403 upgrade; 429 exhausted; 502 retry | Ready, endpoint-payload audit in F1 |

## 26. Frontend Backend Contract Gaps

### FRONTEND_BACKEND_CONTRACT_GAP

1. **Generated OpenAPI type drift:** `frontend/src/types/api.ts` does not currently contain `/exam/prep/*`, although the frozen backend router and handoff document do. Before F1, run the documented `npm run api:generate` against the running frozen backend and commit only the generated type update after review. This is a frontend integration prerequisite, not a reason to change the backend.
2. **Legacy endpoint schemas are not fully enumerated in the handoff:** the handoff intentionally lists stable CS408 endpoints but not all request/response field schemas. F1 must derive these from regenerated OpenAPI types and confirm them against the frozen handoff before building each feature hook. No client DTOs may be hand-written.
3. **Global product navigation contracts are not part of this Exam handoff:** search, Materials, cross-space Records, account, membership/usage balance, Course Learning, and Programming require their own endpoint/authorization audits. Their routes are reserved architecture, not F1 implementation commitments.
4. **Unified membership presentation versus legacy entitlement error:** current CS408 plan refusal can expose legacy service/plan identifiers. F1 must translate a structured `FEATURE_REQUIRES_UPGRADE` into user-facing capability copy and must not display those internal/legacy values. A globally authoritative membership/usage display contract is still required before building the account page.
5. **“Continue learning” resolver:** dashboard-summary exposes overview and up to three plan tasks, but the handoff does not define one canonical resume target across modules. F1 should select a conservative deterministic route from returned task/status data or use `进入 CS408`; a cross-module resume API would be a later contract enhancement, not an invented frontend heuristic.

## 27. Page-by-page Implementation Order

1. Regenerate and review OpenAPI types; add query/error primitives for structured/string `detail` errors.
2. Extend the root shell to real global navigation and create the Exam Prep route/layout/context-bar foundation.
3. Implement catalog, profile setup, My Exam, and the dedicated framework-only state.
4. Implement CS408 home and the shared subject contextual rail.
5. Implement knowledge outline and plan using the real study-plan contract.
6. Implement chapter practice attempt flow and its result/AI/error states.
7. Implement past-paper selection, attempt, submission, result, and review.
8. Implement wrong answers and records.
9. Add integrated AI affordances only in the above contexts and wire capability/budget states.
10. Run type/lint/unit/build/E2E/axe and visual review at desktop/tablet/mobile before freezing F1.

## 28. Frozen Frontend Decisions

1. The F1 app shell is mixed contextual rail, not a permanent enterprise sidebar or a top-tabs-only system.
2. User-facing Exam Prep URLs use `/exam`; legacy `/exam/11408/*` remains an implementation transport boundary for CS408 only.
3. `/exam` is profile-led “我的备考”; `/exam/cs408` is the active focused workspace.
4. Framework-only is a first-class honest availability state, selectable but never simulated as study content.
5. CS408 knowledge navigation is an accessible structured outline, not a decorative graph.
6. Practice and past papers prioritize reading and answering; post-submission explanation is secondary.
7. AI is contextual, capability-gated, provider-hidden, and cannot block durable learning writes.
8. F1 inherits homepage typography, base color language, spacing discipline, header/brand assets, and restrained motion—but uses a denser, quieter application rhythm.
9. No code, backend change, migration, dependency, or SSOT state update is authorized by F0.

---

## F0 Completion Record

```text
FRONTEND_F0_COMPLETE = YES
FRONTEND_F1_READY = YES, subject to the five documented contract prerequisites
FRONTEND_IMPLEMENTATION_CHANGED = NO
BACKEND_CHANGED = NO
DATABASE_MIGRATION_REQUIRED = NO
BLOCKERS = No design blocker. F1 may not start API implementation until regenerated
           `/exam/prep/*` types are reviewed; global non-Exam routes remain out of scope
           until their separate backend-contract audits are complete.
```
