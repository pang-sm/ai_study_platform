# CLAUDE.md

智学平台（智学AI）项目。技术栈：前端 React + Vite，后端 FastAPI，数据库 SQLite。

> **权威层级**：本文件是 **执行契约（execution contract）**，不是产品事实来源。
> 唯一产品 / 架构 / 科学语义 / 迁移路线 SSOT 是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文件、`AGENTS.md`、`.claude/**`、`docs/**`、`README.md` **全部从属于它**；任何冲突以 SSOT 为准。
> SSOT 内部的 FROZEN 科学语义不得被任何次级文件改写。

## 当前阶段

- 当前处于 **STEP 7：后端实现 / 重构**（STEP 7 已进入收尾，后端停止继续扩展）。
  - `CURRENT_STEP = STEP_7`
  - `CURRENT_SUBSTEP = STEP_7H5`
  - `NEXT_SUBSTEP = FRONTEND`
  - `NEXT_MAJOR_PHASE = FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION`
  - 权威状态块见 SSOT `# 73. SSOT 状态`。
- `STEP7A` / `STEP7B` / `STEP7C` / `STEP7C-P` / `STEP7D` / `STEP7E` / `STEP7F` /
  `STEP7G`（含 STEP7G-C2）/ `STEP7H0` / `STEP7H1` / `STEP7H2` / `STEP7H3` / `STEP7H4` /
  `STEP7H5` 均已 **FROZEN**；**`STEP7H` 整体 FROZEN**：
  STEP7A = Core Backend Foundation + LearningContext + Data Plane SHADOW-ready（Alembic 基础）；
  STEP7B = Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost；
  STEP7C = External AI Gateway + Qualified Model Pool + Router V0；
  STEP7C-P = Provider Onboarding / Live Validation / Model Pool Calibration；
  STEP7D = Unified Practice Core；
  STEP7E = Unified Wrong Answer Core；
  STEP7F = Records / Data Plane Consolidation；
  STEP7G = Course Learning Space Consolidation（含 STEP7G-C2：Course AI → Unified AI Boundary）；
  STEP7H0 = Exam Prep 域审计 + 架构冻结（只设计不实施）；
  STEP7H1 = Exam Prep canonical namespace + context compatibility foundation；
  STEP7H2 = CS408 Practice / Wrong Answers / Records consolidation（含 H2-C1 并发收尾）；
  STEP7H3 = Exam AI → Unified AIOrchestrator；
  STEP7H4 = Multi-track / Multi-subject Exam Preparation catalog foundation
  （catalog = versioned CONFIG；`cs_408` = ACTIVE，其余 13 个全国统考科目 = FRAMEWORK_ONLY 零内容；
  `exam_prep_profiles` = 真实用户态；Exam knowledge 唯一写入边界收敛）；
  STEP7H5 = Exam Prep / CS408 final backend acceptance + deployment hardening + frontend handoff
  （Exam 运行时 schema 纳入 Alembic：fresh 部署可仅靠 `alembic upgrade head`）。
- **`NEXT_SUBSTEP = FRONTEND`**：后端停止继续扩展，进入全新前端产品实现。
  前端契约见 `STEP7H_FRONTEND_API_HANDOFF.md`（新前端只需读该文件）。
  **`MIGRATION_HEAD = 20260919_0010`**（`migrations/versions/` 中的 Alembic head；以 `ls migrations/versions/` 为准，不要凭本文件断言）。
  注意：本地 `backend/app.db` 是 legacy 开发库，**没有** `alembic_version` / `practice_*` / `learning_events` 表；
  它**不是** Alembic 管理的库，也不代表生产 schema。schema 事实一律以 `alembic heads` + 生产部署流程为准。
  非 408 真实内容导入**仍未发生**，必须等用户明确批准。
- `STEP1`–`STEP6` 已冻结；不得把「当前处于 STEP 6」「下一步做 Scientific Component 产品化设计」「STEP7A 是 NEXT」当作当前状态。
- 全新前端 = **NOT_STARTED**。`frontend/` 目前只有 Clean-Slate 骨架与首页（`routes/`、`features/home/`）。不得恢复旧前端 UI，不得从旧 frontend 复制页面。

## 核心约束（长期有效）

- 后端处于 STEP 7 实现 / 重构阶段，原则是 **Preserve Capability ≠ Preserve Architecture**：
  保留既有业务能力、数据库与 API 语义，但模块边界按 SSOT §27 / §28 重构。
  `main.py` = `REFACTOR / EXTRACT`（**不是** DELETE，**也不是** KEEP AS-IS）；禁止 big-bang rewrite。
- 不因视觉重构删除任何现有真实业务能力。
- frontend 开发必须遵守 `docs/UI_DESIGN_SPEC.md`（前端 UI/UX 规则），且该文件从属于 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
- UI 以 **学习任务为核心**，不是功能入口集合，也不是 AI 官网。
- 避免 AI-generated visual style（无意义渐变 / Glassmorphism / 发光 / 星空 / 粒子等）。
- 使用统一 Design System；Design Token 已建立于 `frontend/src/styles/tokens.css`，新增页面继续 token-first，禁止 magic visual value。
- Reference 设计素材位于 `reference/`（含 `reference/LOGO/`、`reference/PAGE/`、`reference/UI/`），不得删除、重命名、移动、覆盖。
  注意：历史上存在过的 `design/` 与 `design-references/` 目录**当前已不存在**，不要再去引用它们。
- 修改前先检查已有 shared components / tokens，避免重复建设。
- 页面完成后必须执行一次视觉一致性检查（可用 `/frontend-review`）。
- 涉及架构 / 结构性重构时使用 `zhixue-platform-baseline` Skill；视觉设计前使用 `zhixue-art-direction` Skill。
- **学习空间命名以 SSOT 为准**：`course_learning` / `exam_11408` / `programming`（不是「三大一级 Learning World」）。

## 产品定位与架构（长期）

- 智学AI **不是三个网站**。它是一个统一账户 + 统一会员 + 统一 Usage Credits 之上的多场景个人学习系统（SSOT §1）。
- 三个 **Learning Space**（`service_namespace`）：`course_learning` / `exam_11408` / `programming`。三者共享 Account、Subscription、Usage Credits、Materials Infra、AI Gateway、Scientific Runtime、Learning Record Infra、Data Plane。
- 共享 **Learning Core**：materials / knowledge / practice / wrong_answers / review / planning / records / reports。
- 层级：Learning Spaces → Learning Core → Platform Core；智能能力经 AI Orchestrator → Gateway 或 Learner Intelligence → Scientific Runtime Client（SSOT §28）。
- **禁止**：三个学习空间拆成三个网站；三套会员；三套 AI；三套 usage 余额（SSOT §67）。
- 产品第一性语法：**CURRENT → NEXT → ACTION → PATH → TOOLS**。首页是 Personal Learning Home，第一屏优先服务「继续学习 / 下一步行动」，三个 Learning Space 是次级探索层，不是首页第一焦点。
- 11408 是 `exam_11408` 空间下的第一个完整垂直实例，不是一级产品；其他方向先建框架，不虚构已有完整内容。
- 会员目标（FROZEN，SSOT §4 / §5）：统一 `Free / Standard / Advanced`，链路 `Subscription → Capability Permission → Usage Budget → Model / Workflow Router`。
  当前 **CURRENT 仍是旧三服务会员 + 固定 quota**（SSOT §41）；不得把旧三服务会员当作目标架构继续扩展。
- 用量目标（FROZEN，SSOT §6 / §7）：**Usage Credits**，执行模型 `estimate → reserve → execute → actual → settle`，配套 `usage_budgets` / `usage_ledger` / `ai_requests` / `ai_cost_records`。不是固定次数 quota。`Advanced` 无 membership daily cap，但仍有 weekly budget / rate limit / abuse / concurrency 限制。

## SSOT 优先级（长期）

**唯一最高权威**：`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`（根目录）。它高于本文件与下列全部次级文件。

解析顺序（SSOT §0.1）：

1. **当前本地工作树与数据库的只读事实审计**
2. **`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` 中的 FROZEN TARGET**
3. 当前对话中用户最新明确决策
4. 历史文档 / 历史截图 / 旧前端 / 旧产品逻辑

次级参考（全部从属于 SSOT，冲突时 SSOT wins）：

1. `docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`（总体架构参考）；模型能力边界细化见 `docs/architecture/ZHIXUE_MODEL_CAPABILITY_BOUNDARY_V1.md`
2. `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md`（学习体验 / 信息架构参考）
3. `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`（视觉方向参考）
4. `docs/UI_DESIGN_SPEC.md`（前端 UI/UX 规则）
5. `docs/FRONTEND_ARCHITECTURE.md`（前端工程架构边界）、`docs/FRONTEND_API_CONTRACT.md`（后端 API 契约盘点，2026-09-10 快照）

**两份文件不得再被声明为项目 SSOT**：`docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md` 与 `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md` 是历史基准，已被 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` 取代。

**不得把 PLANNED / TARGET 写成 CURRENT**：SSOT 与架构文档中标注 `PLANNED` / `TARGET` / `NOT_IMPLEMENTED` 的能力尚未实现，不得在代码、文档或汇报中当作「已经部署 / 已经存在」。CURRENT 事实以 SSOT §37–§49 的最新只读审计与 `# 73. SSOT 状态` 为准，并允许被新的只读事实审计更新。

## 技术栈（当前）

- 前端：React 19.2 + Vite 8（Rolldown）+ TanStack Router（file-based）+ TanStack Query v5 + React Hook Form + Zod 4 + Tailwind CSS 4（`@tailwindcss/vite`）+ TypeScript 5.9（strict）+ lucide-react + Radix Primitives + openapi-fetch/openapi-typescript。测试：Vitest + RTL + Playwright + @axe-core/playwright；ESLint 9 flat config。
- 后端：FastAPI 单体（`backend/main.py`）+ SQLAlchemy 2.0 + Pydantic v2 + SQLite + **Alembic 1.20**。当前 `351` 条 business HTTP endpoint（+2 WebSocket +4 framework；见 SSOT §39 / §56.3）；Session Cookie 认证（`ai_session`）。科学模型不在 Product Backend 内运行。
- 启动：前端 `npm run dev`（127.0.0.1:5173）；后端在 `backend/` 下用项目 venv：`./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`（生产 Linux 用 `.venv/bin/python`）。
  **注意**：系统 `python` 是 3.11 且未安装 FastAPI；后端一律使用 `backend/.venv`（Python 3.13）。

## 前端架构边界（长期）

- API 访问必须经 `frontend/src/lib/api/client.ts`（openapi-fetch `createClient<paths>`），组件内禁止 `fetch('/api/...')`。
- `frontend/src/types/api.ts` 为**生成文件**，禁止手写/手改；后端契约变化后运行 `npm run api:generate` 重生成。
- 状态归属：Server State → TanStack Query；URL State → TanStack Router；Form State → React Hook Form；本地状态 → useState/useReducer。本轮不引入 Redux / Zustand 等。
- 明确禁用：Next.js / SSR / RSC、GraphQL / Apollo、tRPC、shadcn 完整初始化、Material UI / Ant Design / Bootstrap / Chakra / Mantine、Styled Components / Emotion、Framer Motion。
- 依赖纪律：新增依赖需说明解决什么实际问题；禁用 beta / rc / canary；`package-lock.json` 进 git；不使用 `npm audit fix --force`。

## UI 设计红线（长期）

- 以**学习任务为核心**，不是功能入口集合，也不是 AI 官网。每个页面首先回答：我在哪 / 学到哪 / 下一步做什么。
- 避免 AI-generated visual style：无意义渐变、Glassmorphism、发光 / Neon、星空、粒子、AI 机器人插画、大脑发光图等。
- Section ≠ Card；禁止 card-inside-card；Card 只用于独立可点击对象 / 任务 / 资源。
- 只用 `tokens.css` 的 token，禁止 magic visual value（随机颜色 / 字号 / 圆角 / 阴影 / 间距）。
- 图标统一 lucide-react，禁止混用 Emoji / 随机 SVG。
- 按钮统一 Primary / Secondary / Ghost / Danger，一个视觉区域原则上一个 Primary，使用动作型文案。
- 完整处理 loading（Skeleton 优先）/ empty / error 状态；responsive（Desktop / Tablet / Mobile）；accessibility。
- 页面完成后执行 `frontend-review`（`/frontend-review`）与 `zhixue-ui-acceptance`。Dashboard Detection：删除 Logo 后若仍像典型 admin / SaaS dashboard，则 UI 验收 FAIL。

## 后端修改红线（长期）

- 后端处于 STEP 7 实现 / 重构阶段。**不得再以「backend 默认不得修改」作为规则**：
  保留能力与 API 语义，但允许并鼓励按 SSOT §27 / §28 抽取模块（`backend/app/` 目标边界）。
- 不因视觉重构删除任何现有真实业务能力；不得删除 SSOT §51 的 PRESERVATION CRITICAL ASSETS。
- 后端分层（SSOT §28）：Layer A Platform Core / Layer B Learning Core / Layer C Domain Spaces / Layer D Intelligence。禁止循环依赖。
- AI 分层（SSOT §30 / §31）：`Capability → Permission / Budget → Qualified Model Pool → Router → Provider Gateway → settlement / logging`。
  - **Gateway** = 怎么调用模型；**Orchestrator** = 为什么调用、调用几次、如何组合。两者必须区分。
  - 业务代码不得知道具体模型名；请求的是 capability（如 `tutor.chat` / `question.explain` / `programming.debug`）。Provider adapter（`backend/ai/providers/*`）是唯一允许出现 provider 名的地方；**禁止**把 `deepseek-*` / `qwen-*` 等模型名散落在业务文件中。
- Prompt 不得大量散落在 React / FastAPI 业务代码里，逐步收敛到 `backend/prompts.py` 等集中位置（长期目标 Prompt Registry）。
- 新增/改动 API 后更新 `docs/FRONTEND_API_CONTRACT.md` 并重跑 `api:generate`（见 `zhixue-api-contract` Skill）。
- 禁止恢复 `course_ai` / `exam_ai` / `programming_ai` 三套重复公共能力系统（SSOT §29 / §67）。公共能力 API 按 capability，资源 API 按领域。

## 模型能力边界（长期）

- 权威边界见 SSOT §35（Productization Gate）、§36（13 个 Scientific Component 的 FROZEN 科学语义）、§49、§72。
- 13 个 scientific component 中，当前 `runtime pass = 13 / 13`，但 **runtime ready ≠ product ready**。
  当前 `USER_VISIBLE_PREVIEW = 1`（`student_twin`）、`RUNTIME_ONLY = 12`、`ADVISORY = 0`、`ACTIVE = 0`。
  仅 `student_twin` 有正式 Product Backend 链，且 `controls_product_decision = false`、`writes_learner_fact = false`；
  其 `MVP_TARGET = USER_VISIBLE_PREVIEW`，用户可见功能 = **学习状态实验视图**（确定性学习状态引擎（实验），
  **不是**掌握度预测 / 神经网络 / 掌握概率）。权威状态见 SSOT「StudentTwin 冻结状态」。
  `misconception_v2` 与 `tutor_policy` 只有 SHADOW 桥，**未晋升**（`RUNTIME_PROVISIONED ≠ PRODUCT_ELIGIBLE`）。
- 任何 scientific component 上线必须通过 Productization Gate：
  `Runtime Pass → Input Availability → Ontology Compatibility → Domain Compatibility → Offline Validation → Shadow → Decision Influence → Production`。
- 禁止改写 FROZEN 科学语义：
  - `student_twin` = deterministic rule-based state engine ≠ neural network
  - `learner_state` = next-response `P(correct)` ≠ mastery probability
  - `evidence_reliability` = reliability weight ≠ `P(correct)`
  - `IRT` = online 1PL-style theta update under fixed item difficulty ≠ EAP / MAP / MLE
  - `tutor_policy` / `tutor_guard` ontology = `focus / generic / probing / telling`；**不得**改写成 `ALLOW / REJECT`
  - `misconception_v2` score = cosine-like inner product（BGE-M3 + L2 normalize + FAISS IndexFlatIP），不是 probability
  - `memory` 必须有真实 `interval / rating / lapse / review_history`，**禁止 fabricated input**
- 铁律：`NO MODEL → PRODUCT STILL WORKS`（模型不可用产品仍可用，模型可用则变强）；禁止 `NO MODEL → PRODUCT BREAKS`。禁止前端/业务逻辑/数据库直接依赖未产品化的模型。
- 禁止在模型未产品化时实现 fake model output；禁止 UI/文案声称「AI 为你推荐 / 预计掌握率 / 根据你的能力预测 / 智能学习路径 / 模型判断已掌握」。

## 数据库安全原则（长期）

- SQLite。**当前正式 migration strategy = Alembic**（STEP7A 建立）：
  `alembic.ini` + `migrations/env.py` + `migrations/versions/`，当前 HEAD = `20260915_0002`。
- `backend/database.py` 的 `ensure_*_schema()` 与 `backend/database_schema.py` 的 `ensure_database_schema()` 是 **legacy 机制**，仅保留用于既有表的幂等保障，**不再是唯一迁移入口**，也不得与 Alembic 同时声称自己是唯一机制。新 schema 变更走 Alembic。
- **additive-only 长期有效**：允许 `CREATE TABLE IF NOT EXISTS`、`ALTER TABLE ADD COLUMN`、`CREATE INDEX IF NOT EXISTS`。
- **禁止** `DROP`、rebuild 既有表、批量重写既有用户数据、直接删库重建。
- **禁止**继续无限背负旧表、旧字段、旧 alias、旧 membership compatibility（SSOT §54）。
- 原则（SSOT §54）：`STATIC / CONTENT / SCIENTIFIC DATA → 强保护`；`OLD USER PRODUCT STRUCTURE → 精确审计后可删除`。
- 必须保护：`exam_question_bank`、`programming_exercises`、`knowledge_points`、`exam_resources`、`static`、`programming_catalog`（SSOT §40 / §51）。
- 动库前备份，动库后 `PRAGMA integrity_check` 必须返回 `ok`。
- 本地 `backend/app.db` 与生产库（`/var/lib/ai_study_platform/app.db`）严格区分；生产库只走既有部署流程，不直改线上。详见 `zhixue-db-migration` Skill。

## 修改前工作流程（长期）

1. **先读 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`**，判断任务属于哪个 STEP，再读对应次级文档与 `docs/FRONTEND_ARCHITECTURE.md`、`docs/FRONTEND_API_CONTRACT.md`。
2. 检查是否已有 shared components / tokens / 相似页面 / 已有后端能力，避免重复建设。
3. **明确列出将要修改的文件与理由**，再动手（用户要求每次改动须清楚说明要改哪个文件）。
4. 纯前端改动不得顺手修改 backend（SCOPE_VIOLATION）；但 STEP 7 的后端重构任务是**被授权且必需**的，不受此限。涉及架构 / 结构性重构先走 `zhixue-platform-baseline` Skill；视觉设计前先走 `zhixue-art-direction` Skill 建立 Visual Concept。

## 修改后验证流程（长期）

- 前端（在 `frontend/`）：`npm run check`（= typecheck + lint + test:run）+ `npm run build`；涉及页面/视觉改动再跑 `frontend-review` / `zhixue-ui-acceptance`；必要时 `npm run test:e2e`。
- 后端（在 `backend/`，**必须用项目 venv**）：`./.venv/Scripts/python.exe -m py_compile <files>` 再 `./.venv/Scripts/python.exe -m pytest`。
  直接用系统 `python -m pytest backend/tests` **会失败**（Python 3.11，无 FastAPI）。
  **测试数量会变化，不在本文件写死。** 每次运行现场测量并报告实测结果；不要引用本文件里的历史数字。
  历史记录（仅作沿革，已过期）：本文件曾写「45 个测试文件 / 322 tests」；`ACCEL_PRODUCT_S10`（2026-09-20）
  实测为 **1578 passed, 2 skipped**。该数字同样会过期，不得当作当前事实。
- 数据库改动：先备份 → Alembic 迁移 → `PRAGMA integrity_check` = ok，并说明「是否需要迁移」。
- 汇报：改了哪些文件、实现什么、如何测试、有无风险（含是否需要迁移）。

## Git 工作流程（长期）

> **Git 状态不再由本文件断言，必须每次开工前现场检查。**
> 历史记录：SSOT §37.1 / §68.1 曾记录 `DIVERGED`（AHEAD = 15 / BEHIND = 12，merge base = `81277a15`）。
> 该分叉**已经 reconcile**，本地 `main` 与 `origin/main` 已同步；上句只作为历史保留，不得当作 CURRENT。
> 开工前一律执行并据此判断（**不要相信本文件里的分支状态**）：
>
> ```
> git status --short --branch
> git rev-parse --abbrev-ref HEAD
> git log --oneline -5
> git rev-list --left-right --count origin/main...HEAD
> ```
>
> **长期红线（无论分叉与否都成立）**：未经用户明确批准，`NO reset` / `NO clean` /
> `NO restore` / `NO stash` / `NO checkout --`（即不得丢弃、覆盖或隐藏任何未提交工作）。
> 工作树中的未跟踪目录（历史 sprint 的 scratch 目录）同样不得删除。

正式流程：

`git status` → `git add <指定文件>` → 中文 commit message（deploy 以 commit message 作为 Actions 标题，须写清楚，如「优化登录注册页面样式」）→ `git pull origin main --rebase` → `git push origin main` → 确认触发 GitHub Actions 自动部署。

禁止（长期）：`--force`、`git reset --hard`、`git clean`、只建分支不 push、绕过 Actions 直改线上、未验证即声称修复、删除未跟踪 Phase 文件。

## 高风险文件（长期）

- `backend/app.db`、`backend/.env`、`backend/.env.local`、根 `.env`：数据库与密钥，禁止直接改 / 读 / 输出。
  `.env.local` 与 `.env` 受同等保护——**任何 secret 规则必须同时覆盖 `.env.local`**。
- `backend/database.py`、`backend/database_schema.py`：legacy schema 入口，只增不改。
- `migrations/`、`alembic.ini`：**正式 migration 入口**，改动即影响 schema 版本链。
- `backend/main.py`：单体入口 + 351 条 business HTTP endpoint。处于 `REFACTOR / EXTRACT` 阶段，不是「默认不改」，但禁止 big-bang rewrite。
- `backend/models.py`、`backend/schemas.py`：按域 REFACTOR。
- `backend/data_plane/`、`backend/core/`、`backend/ai/`、`scientific_runtime_service/`、`deploy/artifacts/`：新 Phase 代码，Git 关系澄清前**绝对不能 clean**（SSOT §51）。
- `frontend/src/types/api.ts`：生成文件，禁手改。
- `frontend/src/styles/tokens.css`：token 源头实现，与 `docs/UI_DESIGN_SPEC.md` 对齐，禁漂移。
- `reference/`（含 `reference/LOGO/`）：品牌与设计参考，禁改 / 删 / 移 / 覆盖。
- `.github/workflows/`：生产部署与审计，勿误触发。

## 项目专属 Skill 优先（长期）

项目专属 Skill 优先于通用 Skill；通用 Skill（如 frontend-design、fastapi、webapp-testing）只是辅助执行方法，**不得覆盖项目规范，更不得覆盖 SSOT**。核心专属 Skill：`zhixue-platform-baseline`（架构）、`zhixue-art-direction`（视觉方向）、`frontend-review`（页面后视觉审核）、`zhixue-ui-acceptance`（UI 最终验收）、`zhixue-api-contract`（API 契约）、`zhixue-db-migration`（数据库安全迁移）、`project-deploy`（改码 → 验证 → 提交 → 部署全流程）。

## 修改 SSOT 本身的规则（长期）

`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` 是治理标准，**不得为了迁就次级文件而修改它**。只有 SSOT §74 列出的情形才允许更新：用户明确改变产品方向、完成并冻结一个 STEP、新的只读事实审计证明 CURRENT 已变化、Scientific Runtime / Productization 状态经正式验收变化、Production Deployment 状态正式变化。

若发现 SSOT 内部存在 stale 的 CURRENT / NEXT 段落，**报告给用户并等待决定**，不要自行回写。
