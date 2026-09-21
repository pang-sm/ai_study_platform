# ZHIXUE_PRECOMMIT_WORKTREE_RECONCILIATION_REPORT

本轮为 **只读整理 + 验证**：未 commit / push / deploy / reset / clean / restore / stash / checkout -- / rebase / merge / pull。
唯一写入：`frontend/src/types/api.ts`（生成文件重生成，见 §6）、本报告文件本身。

---

## 1. Git truth

| key | value |
|---|---|
| `HEAD` | `b3543a34ab0bbe7372e56018a582496307f43e49` |
| `HEAD subject` | `ACCEL_PRODUCT_S10：统一会员迁移 + 竞赛演示环境 + 数据飞轮加固` |
| `BRANCH` | `main` |
| `ORIGIN_DIVERGENCE` | `origin/main...HEAD = 0 0`（**no divergence**，本地与 origin/main 完全同步） |
| `INDEX` | 空（`git diff --cached` 无内容，无任何已暂存改动） |
| `MIGRATION_HEAD` | `20260919_0012`（实跑 `alembic heads` 复核，单一 head；CLAUDE.md 的更新与事实一致） |

### `WORKTREE_COUNTS`

**A. 开工时（reconciliation 起点）**

| 项 | 数量 |
|---|---|
| modified（tracked，` M`） | **73** |
| untracked（展开为文件后，`??`） | **290** |
| deleted（` D` / `D `） | **0** |
| added（已暂存 `A`） | **0** |
| staged（任何状态） | **0** |
| `git status --short` 行数（目录折叠） | 217（= 73 + 144 折叠条目） |
| **唯一变更文件总数** | **363** |

**关键事实：开工时工作树中不存在任何删除。** 363 条变更全部是「修改」或「新增」。

**B. 收尾时（FINAL_CLEANUP 之后，终态）**

| 项 | 数量 |
|---|---|
| modified（` M`） | **73** |
| deleted（` D`） | **3**（FINAL_CLEANUP 授权删除，§7.1） |
| untracked（`??`） | **291**（+1 = 本报告文件） |
| staged | **0**（索引保持为空） |
| `git status --short` 行数（目录折叠） | 221 |
| **唯一变更文件总数** | **367** |
| to-stage | **298**（§12） |
| excluded（scratch） | **69**（§9） |

---

## 2. 变更分类（终态 367 条，零 UNKNOWN）

| 分类 | 数量 |
|---|---|
| `FRONTEND_PRODUCT` | 125（122 + 3 条 ` D`） |
| `SCRATCH`（临时/验收产物，**禁止提交**） | 69 |
| `BACKEND_PRODUCT` | 63 |
| `FRONTEND_TEST` | 52 |
| `BACKEND_TEST` | 33 |
| `SPRINT_REPORT` | 17（16 + 本报告） |
| `SCRIPT_OR_DEPLOY` | 2 |
| `GOVERNANCE` | 2 |
| `GENERATED` | 2 |
| `DOC` | 2 |
| `UNKNOWN_OR_UNEXPLAINED_FILES`（粗分类） | **0** |

**没有任何一条变更无法归属到某个已知 sprint 产物。** 分类为**精确分区**：
367 条全部落在上表之中，`to-stage 298 + excluded 69 = 367`，无重复、无遗漏。

---

## 3. `BACKEND_PRODUCT_FILES`（63）

**AI / Gateway / Router（6）**
`backend/ai/cost.py`, `backend/ai/health.py`(新), `backend/ai/orchestrator.py`, `backend/ai/pool.py`, `backend/ai/router.py`,
`backend/prompts.py`, `backend/rag.py`

**Learning Core（24）**
`backend/learning/adaptive.py`(新), `backend/learning/agenda.py`(新), `backend/learning/deep_study.py`(新),
`backend/learning/feedback.py`(新), `backend/learning/feedback_analytics.py`(新), `backend/learning/plan_adjustment.py`(新),
`backend/learning/report.py`(新), `backend/learning/review.py`(新), `backend/learning/review_schedule.py`(新),
`backend/learning/wrong_analysis.py`(新),
`backend/learning/practice/adapters/course.py`, `backend/learning/practice/service.py`,
`backend/learning/records/contract.py`, `backend/learning/records/native_concept.py`,
`backend/learning/records/producers.py`, `backend/learning/records/service.py`, `backend/learning/records/taxonomy.py`,
`backend/learning/wrong_answers/project.py`, `backend/learning/wrong_answers/service.py`,
`backend/learning/spaces/course_learning/{__init__,context,service,wrong_answers}.py`,
`backend/learning/spaces/exam_prep/wrong_answers.py`,
`backend/learning/spaces/programming/{__init__,agent,ai,context,events,service}.py`(全部新)

**Ops / 运维契约（4，全部新）**
`backend/ops/__init__.py`, `backend/ops/ai_operations.py`, `backend/ops/feature_flags.py`, `backend/ops/workflow_operations.py`

**Routers（12）**
`backend/routers/admin_ops.py`(新), `backend/routers/agenda.py`(新), `backend/routers/course_learning.py`(新),
`backend/routers/deep_study.py`(新), `backend/routers/learning_report.py`(新), `backend/routers/p4_adaptive_feedback.py`(新),
`backend/routers/plan_adjustment.py`(新), `backend/routers/programming.py`(新), `backend/routers/programming_agent.py`(新),
`backend/routers/review.py`(新), `backend/routers/ai_models.py`, `backend/routers/wrong_answers.py`

**Platform（8）**
`backend/main.py`, `backend/membership.py`, `backend/usage/capabilities.py`, `backend/usage/service.py`,
`backend/data_plane/backfill.py`, `backend/data_plane/emitter.py`,
`backend/scripts/e2e_harness.py`(新), `backend/scripts/e2e_seed.py`(新), `backend/scripts/e2e_serve.py`(新),
`backend/scripts/freeze_advanced_api_contract.py`(新)

> **HTTP 面是纯增量**：`git diff` 复核 `main.py` 与全部已改动 router，**移除的 route decorator = 0**。
> 即本轮后端没有删除任何既有 endpoint。

---

## 4. `FRONTEND_PRODUCT_FILES`（122 存量 + 3 条删除 = 125）

**路由树（44）**
`frontend/src/routes/__root.tsx`, `login.tsx`(新), `register.tsx`(新), `reports.tsx`(新), `review.tsx`(新), `profile.tsx`(新),
`course.tsx`(新), `course/index.tsx`(新), `course/setup.tsx`(新), `course/$courseId.tsx`(新) 及
`course/$courseId/{index,study,materials,knowledge,practice,wrong,records,plan,state,ask}.tsx`(全部新),
`exam/setup.tsx`, `exam/cs408/practice.tsx`,
`programming.tsx`(新), `programming/index.tsx`(新), `programming/setup.tsx`(新), `programming/$language.tsx`(新),
`programming/$language/{index,errors,exercises,exercises/index,exercises/$exerciseId,plan,records,state,projects/$projectId}.tsx`(全部新)

**Auth（9，全部新）**
`features/auth/{auth-context.tsx,query-keys.ts,return-to.ts,session-cache.ts}`,
`features/auth/api/{auth.ts,user-profile.ts}`,
`features/auth/components/{auth-layout.tsx,login-page.tsx,register-page.tsx}`

**Learning Spaces — Course（8）**
`features/course/{api/course.ts,course-context.ts}`(新),
`features/course/components/{course-index.tsx,course-page-shell.tsx,course-pages.tsx,course-setup-page.tsx,course-workspace.css,course-workspace.tsx}`

**Learning Spaces — Exam 11408（10）**
`features/exam/components/{cs408-workspace,cs408-practice-workspace,cs408-wrong-answer-workspace,cs408-knowledge-workspace,
cs408-past-paper-workspace,cs408-learning-records-workspace,cs408-study-plan-workspace,cs408-student-twin-workspace,
exam-page-shell,exam-product-pages}.tsx`

**Learning Spaces — Programming（5）**
`features/programming/{api/programming.ts,programming-language.ts,programming-onboarding.ts}`(新),
`features/programming/components/{programming-pages.tsx,programming-setup-page.tsx}`

**Home / Personal Learning Home（8）**
`features/home/{home-page.tsx,learning-worlds.tsx,agenda-api.ts(新),daily-agenda.tsx(新),first-run.tsx(新),
learning-status.tsx(新),recent-learning.tsx(新),space-context.ts(新)}`

**共享学习面（14）**
`features/profile/{api/profile.ts,components/profile-page.tsx,profile-settings.tsx,profile-membership.tsx,
profile-security.tsx,profile-learning-spaces.tsx}`,
`features/review/review-page.tsx`(新), `features/records/{api/learning-records.ts,event-labels.ts}`(新),
`features/advanced/{api/workflows.ts,workflow-adapters.ts}`(新),
`features/learning-intelligence/{api.ts,learning-intelligence-surfaces.tsx,presentation.ts}`(新),
`features/membership/view-models/membership.ts`

**AppShell / Design System（22）**
`components/layout/{app-shell.tsx,error-state.tsx,account-menu.tsx(新),primary-nav.tsx(新)}`,
`components/page/{breadcrumb,context-header,context-nav,fact-list,loading-state,page-header}.tsx`(全部新),
`components/ui/{badge,choice-list,empty-state,panel,password-field,save-row,section-heading,status-note,text-field}.tsx`(全部新),
`components/learning/{adaptive-practice,advanced-learning-surfaces,ai-feedback,p4-api,workflow-adapters}.tsx|.ts`,
`styles/tokens.css`, `main.tsx`, `router.tsx`,
`lib/{api/server-message.ts,fact-labels.ts,format.ts,learner-safe.ts,router.ts}`(新)

---

## 5. `TEST_FILES`

**`BACKEND_TEST`（33）**
*修改（8）*：`tests/conftest.py`, `test_bc7_wrong_answer_canonicalization.py`, `test_bc8r1_entitlement_contract.py`,
`test_course_ai_reachability.py`, `test_exam_ai_orchestrator.py`, `test_feature_entitlements.py`,
`test_gateway_migration.py`, `test_learning_records_api.py`, `test_practice_adapters.py`
*新增（25）*：`test_course_p1_1_contracts.py`, `test_p1_3_global_wrong_security.py`, `test_p3a_programming_agent.py`,
`test_p3a_strong_reasoning.py`, `test_p3a_unified_review.py`, `test_p3b_learning_report.py`, `test_p3b_plan_adjustment.py`,
`test_p3b_wrong_analysis.py`, `test_p4_adaptive_practice.py`, `test_p4_feedback.py`, `test_p4_intelligent_review.py`,
`test_p4_observability.py`, `test_p4_router_v1.py`, `test_p5_agenda.py`, `test_p5_feedback_analytics.py`,
`test_p5_review_persistence.py`, `test_p6_1_ai_request_identity.py`, `test_p6_1_e2e_harness.py`,
`test_p6_2_legacy_ai_closure.py`, `test_p6_operations_and_hardening.py`, `test_p6_security_privacy.py`,
`test_p7d1_context_isolation.py`, `test_three_domain_p1_2_course_wrong_security.py`, `test_three_domain_p1_contracts.py`

**`FRONTEND_TEST`（52）**
*单元 / 组件 / 测试基础设施（42）*：`src/components/layout/{app-shell,bottom-nav}.test.tsx`,
`src/components/learning/{adaptive-practice,advanced-learning-surfaces,ai-feedback,debug-agent}.test.tsx`,
`src/components/learning/workflow-adapters.test.ts`, `src/components/ui/password-field.test.tsx`,
`src/features/advanced/workflow-adapters.test.ts`, `src/features/auth/{auth-guard.test.tsx,return-to.test.ts,session-cache.test.ts}`,
`src/features/auth/components/{auth-hierarchy,auth-pages,login-email-code}.test.tsx`, `src/features/course/api/course.test.ts`,
`src/features/course/components/{course-setup-page,course-workspace}.test.tsx`, `src/features/exam/api/wrong-answer-contract.test.ts`,
`src/features/exam/components/{cs408-practice-workspace,cs408-student-twin-workspace,cs408-study-plan-workspace,
cs408-workspace,exam-foundation,exam-product-pages.render,exam-setup}.test.tsx`,
`src/features/home/{daily-agenda,home-focus,home-page}.test.tsx`, `src/features/learning-intelligence/presentation.test.ts`,
`src/features/learning-spaces.test.tsx`, `src/features/profile/components/{profile-navigation,profile-page}.test.tsx`,
`src/features/programming/components/{programming-pages,programming-setup-page,workbench-hierarchy}.test.tsx`,
`src/features/programming/programming-language.test.ts`,
`src/test/{app.test.tsx,learner-copy.guard.test.ts,learner-metadata-leakage.test.tsx,render-app.tsx,review.test.tsx}`
*E2E（10）*：`tests/e2e/{smoke.spec.ts, p7a-auth-surfaces, p7b-acceptance, p7c-spaces, p7d-first-run,
course-workspace, daily-agenda, programming-workspace, shared-learning-surfaces, p3b-learning-intelligence}.spec.ts`

---

## 6. `DOC_FILES` / `GENERATED_FILES` / `GOVERNANCE` / `SCRIPT_OR_DEPLOY`

| key | files |
|---|---|
| `DOC_FILES` | `docs/FRONTEND_API_CONTRACT.md`(+155 行, 契约盘点更新), `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`(+6/-9) |
| `GENERATED_FILES` | `frontend/src/types/api.ts`（**本轮已重生成**，见下）, `frontend/src/routeTree.gen.ts` |
| `GOVERNANCE` | `CLAUDE.md`（`MIGRATION_HEAD` 0010→0012、前端状态 NOT_STARTED→已成体系）, `.claude/rules/frontend-ui.md` |
| `SCRIPT_OR_DEPLOY` | `scripts/start-e2e-backend.sh`(新, P6.1 harness 入口), `deploy/verify_production_topology.sh`(新, P6 §F 只读拓扑核查) |

### GENERATED 一致性核查（§5 of the contract）

`frontend/src/types/api.ts` **与当前 backend OpenAPI 不一致（已漂移）**，本轮已重生成：

- 从**临时** DB 启动 backend（`DATABASE_URL=sqlite:///…/spec_fresh.db`，端口 8137），取 `/openapi.json`（514,436 bytes）。
- 用项目自带 `openapi-typescript 7.13.0` 重新生成，diff 摘要：`+201 / -17`。
  - `+` 新增 schema：`AIOperationsSummary`、`AgentRunDetail`、`FeatureFlagItem/List/UpdateResult`、`WorkflowOperationsSummary`（即 P6 ops 契约，此前从未进入生成文件）。
  - `-` 仅 17 行，且全部是「被替换的旧 docstring」+ 5 处 `"application/json": { [key: string]: unknown }` 被收紧为显式 shape。
  - **没有任何 endpoint 或 schema 被移除**。
- 重生成后 `TYPECHECK / LINT / VITEST / BUILD` 全部重跑通过（见 §8）。

> **陷阱记录（复现要点）**：端口 **8123 上存在一个本轮之前的遗留 python backend 进程**（pid 24676，非本会话启动）。
> 首次尝试在 8123 起 spec server 时 bind 失败，但从 8123 抓到的 `/openapi.json` 仍然返回 200 且大小 **391,303 bytes**
> —— 与当前代码的 **514,436 bytes** 明显不同。**该遗留 server 是本轮之前的旧 revision，其 spec 不可信。**
> 本轮最终使用的是自己在空闲端口 8137 上、带临时 DB 启动的实例。
> `frontend/package.json` 的 `api:generate` 指向 `http://localhost:8000/openapi.json`（**本次未使用**）。

---

## 7. P7 保护 / 删除计划

### `DO_NOT_DELETE`

- **P7 正式新前端全部保留**（逐个复核存在，且均已在 §3/§4 的变更清单内）：
  `features/auth/**(15)`, `features/course/**(11)`, `features/exam/**(18)`, `features/programming/**(9)`,
  `features/review/**`, `routes/reports.tsx`, `features/profile/**(8)`, `features/home/**(11)`,
  `components/layout/**(6, AppShell)`, `styles/tokens.css`, `types/api.ts`。
- **`frontend/src/features/home/learning-worlds.tsx` 是现役组件，禁止误删。**
  证据：`home-page.tsx:6` `import { LearningSpaces } from './learning-worlds'`；`home-page.tsx:93` `<LearningSpaces />` 真实渲染。
- **全部 69 条 SCRATCH 一律不碰**（见 §9）。本轮**没有删除任何 scratch 目录**；
  全轮唯一的删除动作是用户在 FINAL_CLEANUP 中明确授权的 3 个 orphan 文件（§7.1），
  未执行任何 `reset` / `clean` / `restore` / `stash` / `checkout --`。

### `SAFE_DELETE_FILES`（**已在 FINAL_CLEANUP 执行** — 见 §7.1）

三个候选均**无任何引用**，且均为 **tracked** 文件（删除即产生 `D`）：

| file | tracked | bytes | lines | 外部引用数 |
|---|---|---|---|---|
| `frontend/src/features/home/virtual-memory-visual.tsx` | yes | 2,292 | 29 | **0** |
| `frontend/src/features/home/home-page.css` | yes | 15,413 | 54 | **0** |
| `frontend/src/features/exam/components/exam-foundation-page.tsx` | yes | 1,696 | 28 | **0** |

核查方式：`grep` 覆盖 `frontend/src`、`frontend/tests`、`frontend/*.ts`、`frontend/*.json`、`*.css`、`*.html`、`*.md`（含 `index.css` 的 `@import` 链），
并确认无动态 import / 无测试 mock 该路径。命中仅出现在历史 sprint 报告中（叙述性引用，非代码引用）。

**历史张力（用户已裁决执行）**：`ZHIXUE_FRONTEND_PRODUCT_SYSTEM_P7C_REPORT.md` 记录过一次「裁决 C：要求保留」
`home-page.css` 与 `virtual-memory-visual.tsx`。本轮的独立 grep 复核确认三者当前**仍然零引用**，
用户随后**明确授权**执行删除（FINAL_CLEANUP），故本轮已删除。

### 7.1 FINAL_CLEANUP 执行记录（明确授权后执行）

删除前留存的审计指纹（内容可由 git 历史恢复，commit `b3543a34` 中仍持有这些 blob）：

| file | sha256 | size | git blob |
|---|---|---|---|
| `virtual-memory-visual.tsx` | `21ef3f890044f8fb91565c76549cb11874d567c52ff73bde3c22b7e110f0e9ad` | 2,292 | `a89e96449b4c47f4af865f02408e4d50aca3fdb0` |
| `home-page.css` | `7ae814b4ede62df4947e9f80f144a9e03c15dfafe79c07f085050e0f25c6f0eb` | 15,413 | `3974a3700a585b0e6cbfe7ebb996aac537024382` |
| `exam-foundation-page.tsx` | `e483cdd481816731e2c09ffd90c8a54855b17085b29d57ef4a672699c2b64f57` | 1,696 | `7e0e2f7786468099cc0b1df422e678ada8f873d5` |

- 执行前复核：三者 external_refs **= 0**；全仓库无 `import.meta.glob`（已排除按模式引用的可能）。
- 执行方式：**普通 `rm`（逐文件），不是 `git rm`** → 删除生效但**索引保持为空**（`git diff --cached` = 0）。
- 结果：3 条 ` D` 新增；`learning-worlds.tsx` **保留未动**（对照项已核验存在）；69 条 scratch **未触碰**（复核仍为 12 目录条目 / 69 文件）。
- 删除后重跑前端四道 gate：**全部通过**（见 §10）。

**不建议本轮做的改名**：`learning-worlds.tsx` → `learning-spaces.tsx` 是**零风险**的（全仓库仅 1 处 import，
即 `home-page.tsx:6`，且无测试 mock 该路径），但属纯命名洁癖、且会把一个 rename 混进体积已极大的发布提交。
按契约「不为命名洁癖阻塞提交」**留到以后**作为独立小提交处理。

---

## 8. `UNKNOWN_OR_UNEXPLAINED_FILES`

粗分类结果为 **0 条无法归属**。两条需要显式标注的「已解释但不进提交」项：

| file | 判定 | 处置 |
|---|---|---|
| `backend/file` | **0 字节空文件**，mtime 2026-09-17 11:06，零引用，无任何代码/文档解释其来源（形态像一次 shell 重定向误操作） | **不进入提交**（列 SCRATCH）。未删除。 |
| `test-results/.last-run.json` | 内容 `{"status":"failed","failedTests":[]}`，mtime 2026-09-19 10:27。是**从仓库根目录误跑 Playwright** 留下的产物：`frontend/.gitignore` 忽略 `test-results`，但**根 `.gitignore` 不忽略**，因此它出现在 untracked 里 | **不进入提交**（列 SCRATCH）。未删除。 |

> 二者都不是「无法解释是谁生成」的产品文件；不存在无法归属的产品文件进入提交的风险。

---

## 9. `SCRATCH`（69 条，禁止提交、禁止删除）

| 目录 | 说明 |
|---|---|
| `.s8tmp/ .s9tmp/ .s10tmp/ .bc7tmp/ .bc8tmp/ .bc8r1tmp/ .f1c5qa/ .f1c6tmp/ .p11tmp/` | 历史 sprint scratch（CLAUDE.md 明令保护） |
| `frontend/.f1c5qa/screenshots/` (5 png)、`frontend/.f1c6tmp/screenshots/` (7 png) | 历史 sprint 验收截图 |
| `test-results/.last-run.json` | 见 §8 |
| `backend/file` | 见 §8 |

这 69 条 **全部 untracked 且未被 .gitignore 覆盖**（`test-results/` 位于根目录，未被忽略）。
**因此本仓库严禁 `git add -A` / `git add .`**：那会把历史 scratch 一并扫进发布提交。
必须按显式路径 stage。

---

## 10. Final validation

| gate | 结果 |
|---|---|
| `BACKEND_FULL_SUITE` | **PASS** — **1779 passed, 2 skipped, 0 failed**（1017.58s / 16:57，exit 0）；见 §10.1 |
| `FRONTEND_TYPECHECK` | **PASS** — `tsc --noEmit`，exit 0，无输出（**删除后复跑**） |
| `FRONTEND_LINT` | **PASS** — `eslint .`，exit 0，无输出（0 problems，**删除后复跑**） |
| `FRONTEND_VITEST` | **PASS** — `vitest run`：**61 files / 300 tests passed（0 failed）**（**删除后复跑**） |
| `FRONTEND_BUILD` | **PASS** — `vite build`，exit 0（**删除后复跑**） |
| `PLAYWRIGHT` | **PASS**（详见 §10.2） |
| `AXE` | **PASS** — 0 violations（详见 §10.2） |
| `MAIN_DB_TOUCHED` | **NO**（详见 §11） |

### 10.1 后端 full pytest

命令：`backend/` 下 `./.venv/Scripts/python.exe -m pytest -q`（项目 venv，Python 3.13）。
`conftest.py` 在 import `database` **之前**即强制 `os.environ["DATABASE_URL"] = sqlite:///<临时目录>/test.db`，
因此整套测试不可能落到 `backend/app.db`。

**结果（FINAL）：**

```
1779 passed, 2 skipped, 8166 warnings in 1017.58s (0:16:57)
EXIT=0
```

- **0 failed / 0 error** → 无回归，**不需要修任何 regression，也不需要重跑**。
- 2 skipped 为既有的环境性 skip，非本轮引入。
- 数量对照：`ACCEL_PRODUCT_S10` 历史实测 1578 passed / 2 skipped；本轮 +201 passed，
  与本轮新增的 25 个 test 文件一致（`test_p3a_*` / `test_p4_*` / `test_p5_*` / `test_p6_*` / `test_p7d1_*` 等）。
- warnings 8166 条为既有 `datetime.utcnow()` DeprecationWarning 等，非本轮新增，不阻塞。
- 说明：该结果跑在**删除 3 个 orphan 之前**的工作树上；这三个文件是纯前端死文件，
  对后端套件无任何影响（后端不引用 `frontend/`）。删除后的前端四道 gate 已复跑通过。

### 10.2 PLAYWRIGHT / AXE（本轮实际执行）

**前置（严格遵守本轮第 1–4 条约束）**

1. 确认 `frontend/src/types/api.ts` 已在 11:13 重生成 → 起 fresh server 前先确认 5173 由谁占用。
2. `5173` 原被 **pid 28240** 占用（`node vite.js --force`，本项目 `frontend/`，10:39:20 启动）。
   本轮在用户明确批准后，**仅 `taskkill //PID 28240 //F`，未使用 `/T`，未触碰任何 backend / harness / uvicorn 进程**。
   随后确认 5173 已释放。
3. **约束确认（为什么必须是 5173，不能换端口）**：
   - `backend/main.py:447` 硬编码 `allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]` 且 `allow_credentials=True` → 其他端口一律被 CORS 拦截；
   - `frontend/vite.config.ts` 为 `strictPort: true` + `port: 5173`；
   - session cookie 为 `SameSite=Lax`，**hostname 必须一致**（`localhost` 与 `127.0.0.1` 属不同 site），
     故 harness 与页面统一使用 `127.0.0.1`。
4. 启动隔离 harness：`bash scripts/start-e2e-backend.sh --json --port 8000`
   → `base_url=http://127.0.0.1:8000`，`data_origin=ACCEPTANCE`，`app_env=acceptance`，
   `database_url=sqlite:///…/zhixue-e2e-qtbg_xc0/e2e.db`（**隔离临时库，非 app.db**）。
5. 在其上启动**全新** `VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev`（Vite v8.2.2，ready in 1263ms，监听 127.0.0.1:5173）。

**执行结果**

| 套件 | 结果 |
|---|---|
| `p7b-acceptance.spec.ts`（**含 AXE**） | **6 passed / 0 failed** — 其中 `axe reports no violations on the converged surfaces` ✅ |
| `p7c-spaces.spec.ts`（**含 AXE**） | **3 passed / 0 failed** — 含 `axe reports no violations on the converged spaces` ✅ |
| `p7d-first-run.spec.ts` | **11 passed / 1 skipped** — 含 `the sign-in screens have no axe violations` ✅ |
| `smoke.spec.ts` + `p7a-auth-surfaces.spec.ts` | **10 passed / 0 failed**（在「API 不可达」条件下，见下） |

**一次被发现并已澄清的假失败（重要，避免上报为回归）**

首次在 **harness 存活**时跑 `smoke.spec.ts` + `p7a-auth-surfaces.spec.ts`，出现 **2 failed**，均为
「受保护路由在 API 不可达时的诚实失败」用例（期望出现 `重试` / `出错了`）。
**这不是产品缺陷，而是前置条件不匹配**：这两个 spec 的自身文件头即写明
「These specs … deliberately need NO backend」（`p7a-auth-surfaces.spec.ts:5`）——
它们的断言前提是 API **不可达**；而当时 harness 正在 8000 上正常服务，于是应用给出了「可连通但未登录」的正确行为，
自然不出现「不可达」的报错态。

**验证方式**：关闭 harness（确认 8000 已释放）后，在同一台 fresh Vite server 上原样重跑，
**10 passed / 0 failed**。即：产品在两种条件下都正确——
API 不可达 → 诚实报错 + 重试，且不为未识别访客渲染任何学习面；
API 可达但无 session → 不出现报错态。

**未执行的部分（有意为之）**：`course-workspace` / `daily-agenda` / `programming-workspace` /
`shared-learning-surfaces` / `p3b-learning-intelligence` 等 **ungated** spec 在 P7-A 引入 auth guard 后即已 **stale**
（写入时尚不存在全局登录门槛，无 `test.skip` 门控）。它们**不属于本轮的 targeted authenticated 验收集**，
本轮不对其改动、也不把其失败计入结论；须另行迁移到 harness 上（属独立工作项）。

### 10.3 进程与端口收尾（严格执行本轮第 5–6 条）

- 本轮临时进程已在验收后全部关闭：harness（pid 38164，`e2e_serve.py`，先 `TaskStop` 父 bash 未回收子进程，再按身份核验后 `taskkill //PID … //F`）、
  临时 spec backend（pid 32712，8137）、本轮 fresh Vite（pid 40636）。
- 端口 `5173 / 8000 / 8137` 现均 **free**。
- **已按要求在 5173 恢复普通 `npm run dev`**（pid 35908，不带 `VITE_API_BASE_URL`）。
  注意：无该变量时应用回落到默认 `http://localhost:8000`（`src/lib/env.ts`），
  而 harness 的 base_url 是 `127.0.0.1`；`localhost` ≠ `127.0.0.1` 属不同 site，`SameSite=Lax` 会导致 cookie 不被发送。
  **下次跑 harness 验收时必须重新以 `VITE_API_BASE_URL=http://127.0.0.1:<port> npm run dev` 起 server。**
- `127.0.0.1:8123` 上的遗留 python backend（pid 24676）**非本轮启动，未触碰、未 kill**。

---

## 11. `MAIN_DB_TOUCHED`

**NO。**

`backend/app.db` 指纹在**本轮全部验证动作之前与之后完全一致**：

| | SHA256 | size | mtime |
|---|---|---|---|
| BEFORE | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64,917,504 | 2026-09-20 12:03:42 |
| AFTER（full suite + 全部前后端 gate + FINAL_CLEANUP 之后复核） | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64,917,504 | 2026-09-20 12:03:42 |

**字节级一致（含 mtime）。** 后端 1779 项测试跑完 16:57 之后，`app.db` 仍未被触碰。

保护机制（本轮实测确认）：
- 后端 full suite：`conftest.py` 强制临时 `DATABASE_URL`；
- OpenAPI 取 spec：显式 `DATABASE_URL=…/spec_fresh.db`；
- `alembic heads`：显式 `DATABASE_URL=…/head_check2.db`；
- e2e harness：自建临时库 `zhixue-e2e-*/e2e.db`。
- **本轮没有任何一次操作使用默认 DATABASE_URL**（即未出现裸跑 alembic/uvicorn 而落到真实 `app.db` 的情况）。

工作树污染核查：本轮 e2e 结束后 `git status --short` 与开工时**逐字节一致（217 行，diff 为空）**。
Playwright 产物落在 `frontend/test-results/`（已被 `frontend/.gitignore` 忽略）。

---

## 12. `PROPOSED_COMMITS`（**未执行，仅建议**）

### 建议：3 个本地提交（`PROPOSED_LOCAL_COMMITS`），**一次 push 落地**

| # | 提交 | 文件数 | 内容 |
|---|---|---|---|
| 1 | `后端：统一学习平台域 + AI 工作流与契约（P1–P6.2 / P7-D.1）` | **98** | `BACKEND_PRODUCT`(63) + `BACKEND_TEST`(33) + `SCRIPT_OR_DEPLOY`(2) |
| 2 | `前端：统一产品体系（Auth + 三学习空间 + 共享学习面 + AppShell）+ 清理 3 个死文件` | **179** | `FRONTEND_PRODUCT`(125，含 3 条 ` D`) + `FRONTEND_TEST`(52) + `GENERATED`(2) |
| 3 | `治理与文档：CLAUDE.md / 前端 UI 规则 + 验收报告 + 契约文档` | **21** | `GOVERNANCE`(2) + `DOC`(2) + `SPRINT_REPORT`(17，含本报告) |

合计 **298** 条 to-stage（+ 69 条 SCRATCH 全部**不提交** = **367** 条唯一变更）。

### `STAGING_MANIFEST`（三组，逐路径；**镜像文件见 `/tmp/zx_recon/G{1,2,3}.txt`**）

> 前提：`git status --short` 现为 `73 M / 3 D / 291 ??` = 367 条唯一变更。
> 划分经**精确分区校验**：`partition=367 行, duplicates=0, missing=0, extra=0` —— 无遗漏、无重复、无归属不明。

**GROUP 1 — backend product + backend tests（98）**
`backend/` 下全部 63 个 product 文件 + 33 个 test 文件（逐条见 §3 / §5），外加：
`deploy/verify_production_topology.sh`, `scripts/start-e2e-backend.sh`
（说明：这两者是后端/部署侧基础设施 —— P6.1 harness 入口与 P6 §F 拓扑核查，故归入本组，而非 docs 组。）

**GROUP 2 — frontend product + frontend tests + generated（179）**
`frontend/` 下 122 个 product 文件 + 52 个 test 文件（逐条见 §4 / §5）+ `frontend/src/types/api.ts`, `frontend/src/routeTree.gen.ts`，
**外加 3 条删除**：
`frontend/src/features/home/virtual-memory-visual.tsx`（` D`）、
`frontend/src/features/home/home-page.css`（` D`）、
`frontend/src/features/exam/components/exam-foundation-page.tsx`（` D`）

**GROUP 3 — governance / docs / reports（21）**
`.claude/rules/frontend-ui.md`, `CLAUDE.md`,
`docs/FRONTEND_API_CONTRACT.md`, `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`,
以及 16 个 sprint 报告 + `ZHIXUE_PRECOMMIT_WORKTREE_RECONCILIATION_REPORT.md`（本报告，新增）。

### 建议 staging 命令（**本轮未执行**）

```bash
# GROUP 1 — 用 /tmp/zx_recon/G1.txt 逐行喂给 git add（-z 语义下每行一个路径）
xargs -a /tmp/zx_recon/G1.txt git add --
git commit -m "后端：统一学习平台域 + AI 工作流与契约"

# GROUP 2（含 3 条删除；`git add -A -- <路径>` 才能记录删除）
xargs -a /tmp/zx_recon/G2.txt git add -A --
git commit -m "前端：统一产品体系 + 清理 3 个死文件"

# GROUP 3
xargs -a /tmp/zx_recon/G3.txt git add --
git commit -m "治理与文档：CLAUDE.md / 前端 UI 规则 + 验收报告 + 契约文档"

# 排除项自检：staged 前后都必须为 0
xargs -a /tmp/zx_recon/EXCL.txt git status --short --  # 必须无输出
```

**绝对禁止 `git add -A`（无路径）/ `git add .`** —— 69 条 SCRATCH 未被 gitignore 覆盖，会被整体扫入。

### 为什么是这个切法（而非 P1/P2/P3 机械切）

- **依赖方向是单向的**：前端的大量新模块（agenda / review / report / programming / p4）调用的是提交 1 里**新增**的
  `backend/routers/*`，且 `types/api.ts` 正是由提交 1 的契约生成。顺序必须是 **1 → 2**，不能倒置。
- **可以拆的前提（本轮已复核）**：工作树**零删除**，且后端 **HTTP 面纯增量（移除的 endpoint = 0）**，
  所以提交 1 落地后仍是「旧前端 + 新后端」的兼容组合，不会出现 endpoint 消失型断裂。
- **提交 3 无运行时效用**，可最先或最后落地，放在最后是因为它描述的是提交 1+2 完成后的状态。

### 拆分成立的必要条件（重要）

`.github/workflows/deploy.yml` 的触发是 `on: push: branches: [main]`，即**每次 push 触发一次部署，作用于该次 push 的 tip**。
因此：

- 这三个提交**必须在同一次 push 中落地**（`git pull --rebase` → **单次** `git push origin main`），
  部署只会跑一次、且作用于最终树 —— 这是安全的。
- **中间提交（提交 1 之后、提交 2 之前）的状态从未被独立验证过**：
  本轮所有 gate 都是在**合并后的工作树**上跑的，没有任何 gate 跑在「只有后端的提交点」上。
- 因此：**若团队的流程无法保证「一次 push」，或需要让每个提交点自身可独立部署/可独立回滚，则应当改为
  单个 atomic release commit**（理由：只有合并树被验证过，任何中间点都是未验证状态；
  而 `deploy.yml` 会对每次 push 都部署，可能把未验证的中间态推上生产）。

### 落地时的硬性注意

- 提交信息用中文（`deploy.yml` 以 commit message 作为 Actions 列表标题）。
- GROUP 2 必须用 `git add -A -- <路径>`（否则 3 条删除不会被记录）。
- 三个提交**必须同一次 push**（见下）。

---

## 13. `READY_TO_STAGE` / `READY_TO_COMMIT`

### `READY_TO_STAGE = YES`

- **`FILES_TO_STAGE_COUNT` = 298**（G1=98 / G2=179 / G3=21）
- **`FILES_EXCLUDED_COUNT` = 69**（逐条见 §9；分区校验 duplicates=0 / missing=0 / extra=0）
- 索引当前为**空**（0 staged），三组命令尚未执行 —— 已按要求**在真正 `git add` 前停止**。

### `READY_TO_COMMIT = YES`

- 后端 full suite **1779 passed / 2 skipped / 0 failed**（exit 0，无回归）。
- 前端删除后四道 gate 全部通过；PLAYWRIGHT 与 AXE 通过。
- 工作树可完全解释（367 条唯一变更，0 条 UNKNOWN）；索引为空；`app.db` 未被触碰。
- 唯一附带条件：三个提交需**同一次 push**（§12）。

## 14. `BLOCKERS`

| # | 项 | 状态 |
|---|---|---|
| 1 | ~~后端 full pytest~~ | **CLOSED — 1779 passed / 0 failed** |
| 2 | 5 个 ungated e2e spec（`course-workspace` / `daily-agenda` / `programming-workspace` / `shared-learning-surfaces` / `p3b-learning-intelligence`）在 P7-A auth guard 后已 stale，未迁移到 harness | **OPEN / 已知**，本轮有意不处理、不计入结论；建议作为独立工作项 |
| 3 | ~~`SAFE_DELETE_FILES` 三项删除~~ | **CLOSED — 用户授权后已执行**（§7.1） |
| 4 | `learning-worlds.tsx` 改名（可选） | **OPEN / 低优先**，零风险但纯命名，建议独立小提交；本轮未做 |
| 5 | `backend/file`、根 `test-results/` 两条游离产物 | **已解释**，不阻塞；不提交即可。是否清理由用户决定 |
| 6 | 遗留 `127.0.0.1:8123` python backend（pid 24676） | **已报告**，非本轮引入、未触碰 |
| 7 | 三个提交必须一次 push（中间提交点未被独立验证） | **需流程保证**；否则改为 atomic release commit（§12） |

---

*报告生成时间：2026-09-21（本地时区）。本版为终版：后端 full suite 已完成，FINAL_CLEANUP 已执行，后端删除后前端 gate 已复跑。*
