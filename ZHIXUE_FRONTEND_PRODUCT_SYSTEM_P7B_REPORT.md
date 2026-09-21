# ZHIXUE_FRONTEND_PRODUCT_SYSTEM_P7B_REPORT

> 范围：**P7-B（FRONTEND ENGINEERING · 产品系统收敛）**
> 日期：2026-09-20 · 工作树：`main`（**未** commit / push / rebase / merge）
> 后端：**未修改**（见 §9 证据）· 旧前端：**未恢复**

---

## 0. 结论摘要

P7-B 把 P7-A 已完成的工程层收敛成一套**统一的、可复用的产品视觉/交互系统**：
Auth 双栏身份—表单分离、Home「焦点优先」层级、Profile 分区导航、AppShell 三端导航、
Programming 三层工具层级、以及支撑它们的 token 与共享原语。

**两项 authority 文件在本轮均未到达工作树**，因此没有「套用 Codex spec」这件事发生——
本轮执行的是**任务书自身逐条列出的要求**（Home 层级、AppShell 三端、Auth 分离、
Programming 三层、Technical Editorial 70% / Academic Dossier 30%）＋项目既有权威
（`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`、`docs/UI_DESIGN_SPEC.md`、`tokens.css`）。
详见 §1。

---

## 1. 关于 `ZHIXUE_P7A_INTERACTION_SPEC` / `ZHIXUE_P7B_UX_ACCEPTANCE_REPORT`

**两份文件不存在**，不是「读取失败」，是确实不在本机：

| 检索 | 结果 |
| --- | --- |
| `find` 全仓库 + Desktop + Downloads + `C:\Users\26477`（4 层） | 无 `*INTERACTION_SPEC*` / `*P7B*` / `*UX_ACCEPTANCE_REPORT*` |
| `git status --porcelain`（含全部未跟踪项） | 无这两个路径 |
| 历史会话全文检索 `INTERACTION_SPEC`（含 archived） | 仅命中 P7-A 会话中**「spec 到达后再作为本轮 spec」**这句前瞻说明 |
| P7-A 会话（1248 条消息）最终报告 | `CODEX_SPEC_APPLIED = NO` —「`ZHIXUE_P7A_INTERACTION_SPEC` 本轮未到达」 |

**本轮做法**：不伪造「已套用 Codex spec」。把任务书把逐条要求（§3–§8 的层级、断点、命名、
设计系统比例）当作本轮 UI/interaction 指令执行——按 SSOT 解析顺序，**当前对话中用户最新明确决策**
高于历史文档与历史 spec；真实 backend/OpenAPI 契约始终最高优先（§7 记录了契约对设计的两次否决）。

---

## 2. 最终 gate 值

| Gate | 值 |
| --- | --- |
| CODEX_SPEC_APPLIED | **NO** — `ZHIXUE_P7A_INTERACTION_SPEC` 不存在于工作树（§1） |
| CODEX_REVIEW_APPLIED | **NO** — `ZHIXUE_P7B_UX_ACCEPTANCE_REPORT` 同样不存在 |
| AUTH_VISUAL | `PASS` |
| HOME_HIERARCHY | `PASS` |
| PROFILE_HIERARCHY | `PASS` |
| APPSHELL | `PASS` |
| PROGRAMMING_UX | `PASS` |
| DESIGN_SYSTEM | `PASS` |
| RESPONSIVE | `PASS`（1440 / 1366 / 1024 / 834 / 390 × 3 surfaces） |
| ACCESSIBILITY | `PASS`（axe 0 violations / 5 个页面状态；2 处真实回归已修，见 §8） |
| GOVERNANCE_STALE_CLAIM_FIXED | **YES**（CLAUDE.md + `.claude/rules/frontend-ui.md`；第三处只报告，见 §6） |
| TYPECHECK | `PASS`（`tsc --noEmit`，exit 0） |
| LINT | `PASS`（`eslint .`，exit 0） |
| VITEST | `PASS` — **214 passed / 53 files**（P7-A 基线 197/48 → **+17 tests / +5 files，未删任何 P7-A 用例**） |
| BUILD | `PASS`（`vite build`，exit 0） |
| PLAYWRIGHT | `PASS` — P7-A targeted `smoke` + `p7a-auth-surfaces` **10 passed**；新增 `p7b-acceptance` **6 passed** |
| AXE | `PASS` — **0 violations**（`/login`、`/register`、`/`、`/profile`、Workbench；含 390px 移动端） |
| NO_FAKE_DATA | **YES**（§7） |
| NO_BACKEND_CHANGED | **YES**（§9） |
| USER_WORKTREE_PRESERVED | **YES**（§9） |

**须记录的例外（唯一一处既有测试被改动）**：Workbench 工具条按钮文案由英文动作词收敛为产品动作词
（`Run`→`运行`、`Test`→`运行测试`、`Submit`→`提交`，符合 `UI_DESIGN_SPEC §9`「按钮必须使用动作型文字」）。
`programming-pages.test.tsx` 因此有 **1 行查询更新**（`'Test'` → `'运行测试'`），**断言的端点、
语言、question 组成全部保持不变，覆盖未减**。这是本轮唯一触碰 P7-A 测试的位置。

---

## 3. APPSHELL（桌面分组侧栏 / 平板抽屉 / 手机抽屉+底部导航）

`frontend/src/components/layout/{app-shell,primary-nav}.tsx` 重写。

- **单一导航模型**：`LEARNING_SPACES`（3 个学习空间）+ `SHARED_TOOLS`（复习/学习报告/会员）
  在 `primary-nav.tsx` 声明一次；桌面侧栏、抽屉、底部导航**全部由它派生**，
  `BOTTOM_BAR` 由 `inBottomBar` 过滤而来——不可能出现「某处有、某处没有」。
- **视觉分层**：学习空间行带**领域 accent 竖条**（`bg-exam` / `bg-course` / `bg-programming`）
  与常规正文层级；共享学习工具用图标＋次级文字色，位于独立分组标签「共享学习工具」之下。
- **三端行为**（Playwright 实测，非声明）：
  - `>=1024`：`主导航` 侧栏常驻；抽屉控件与底部栏 `hidden`。
  - `768–1023`：侧栏隐藏；顶部控件打开 `主导航（移动）` 面板——`sm:w-80` 的**左侧 sheet**
    （不是全屏接管，页面在右侧仍可读），Escape 关闭。
  - `<768`：额外渲染 `主导航（底部）`：`/` `/exam` `/course` `/programming` `/profile`，
    短标签（首页/考研/课程/编程/我的）+ `aria-label` 完整名称（可见词是可达名称的子串，满足 WCAG 2.5.3）。
- **假控件**：`主导航` 里没有任何无后端能力的入口（P7A 已删除的搜索按钮未复活）；
  Auth 页的品牌标记**不再是链接**——未登录用户点它只会被 guard 弹回登录页，那是死链。
- **a11y**：skip-link → `#main-content`；底部栏高度在 `main` 上以 `pb-16` 让出，内容最后一行不被压住。

## 4. AUTH（身份—表单分离 / 验证流程层级）

`auth-layout.tsx` 重写为 **`lg:` 双栏**：左列 `bg-lab-ink` 身份列（品牌 lockup、一句事实性说明、
三个学习空间与共享工具的结构化清单），右列纸面表单列（`h1` + 说明 + 表单 + footer）。`<768` 折叠为单列。

- 学习空间清单**读 `primary-nav` 的同一份声明**（含 `eyebrow`/`detail`），因此登录页不会描述出与 shell 不同的产品。
  它们渲染为**文本而非链接**（未登录跟过去只会回到登录页）。
- **注册验证流程层级**：新增 `StepIndicator`（`aria-label="注册步骤"`，`aria-current="step"`）——
  ① 验证邮箱 → ② 设置账号；第一步**只有**邮箱 + 「发送验证码」(secondary) + 验证码 + 「验证邮箱」(唯一 Primary)；
  账号字段在第二步才出现。
- **loading / error / success 统一**：全部走 `StatusNote`（`status` vs `alert` 由 tone 决定）。
- **法务**：没有用户协议/隐私政策 endpoint，因此不建假链接，改为在 footer 明说
  「用户协议与隐私政策尚未发布，当前版本不提供对应入口。」测试断言该区域内**零链接**。
- 无「忘记密码」入口（后端无此契约）。

## 5. HOME（焦点优先层级）

顺序 = **Welcome → Focus → Daily Agenda → 待复习 → Recent Learning → Learning Spaces → 会员/用量**。
`home-page.tsx` / `daily-agenda.tsx` / `learning-worlds.tsx` / `learning-status.tsx` / `recent-learning.tsx`。

- **Focus 是第一视觉焦点**：`AgendaFocus` 取服务端 `/learning/agenda` 排序后的**第一项**，
  用 `Panel tone="focus"`（brand-subtle 面 + 4px brand 左规 + 单一 Primary「打开并完成这项学习」）
  呈现，并展示**服务端自己的** `priority_rules[reason]`。新用户则同一位置显示「先完成两件设置」。
- **Agenda 不重排、不丢失**：`DailyAgenda` 用 `skipFirstItem={!needsSetup}` 只跳过已提为焦点的那一项，
  其余**按服务端顺序原样列出**；提为焦点的那一项在页面上**只出现一次**
  （`home-page-focus.test.tsx` 断言 `getAllByText(…).toHaveLength(1)`，并逐条比对剩余列表顺序）。
  候选为空时不渲染空的焦点面板——空状态由议程区独自负责，避免两块空面板说同一句话。
- **三张空间大卡不再抢首屏**：`learning-worlds.tsx` 从 15KB `lab-index`（196px 行高、`clamp(2.4rem,4.6vw,4.6rem)` 标题、
  全出血）改为 token 化的编号索引行（编号 + accent 竖条 + 46px 主题 SVG + 模式 + 名称 + 范围 + 箭头），
  位于 Recent Learning 之后。
- **会员/用量**移到页面最后，作为最小的一块。

## 6. GOVERNANCE_STALE_CLAIM_FIXED

| 文件 | 处理 |
| --- | --- |
| `CLAUDE.md` | 「全新前端 = NOT_STARTED …只有 Clean-Slate 骨架与首页」→ 改为事实：Clean-Slate 重建**已开始并已成体系**（完整路由树 + 三个学习空间 + 共享学习面 + 统一 Auth/AppShell），当前阶段 = **frontend product-system convergence / refinement**；`OLD_FRONTEND_RESURRECTED = NO` 长期不变 |
| `.claude/rules/frontend-ui.md` | 同一句 stale 声明替换为事实状态 + convergence 阶段；其余规则**一字未改** |
| `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` | **未修改** |
| `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md:5` | **只报告，未改**：同一句 stale 声明（「全新前端 = `NOT_STARTED`」）仍在，需你决定是否一并修正 |

治理文档**未扩写**：两处均为替换，未新增条款、未改产品设计原则。

## 7. DESIGN_SYSTEM / PROGRAMMING_UX / 契约优先

**DESIGN_SYSTEM（Technical Editorial 70% / Academic Dossier 30%）** — `tokens.css` 补齐并**在构建产物中验证生效**：

- 新增 **brand 强度阶梯**（`brand-subtle`/`brand-strong`/`brand-emphasis`）、**FOCUS 面**
  （`focus-surface`/`focus-border`）、**补全语义族 ink**（`primary-ink`/`warning-ink`/`ai-ink`/`neutral-soft`）、
  `--text-heading`、`--tracking-eyebrow`、`--radius-pill`。
- **修掉一个真实的 token 漏洞**：`text-heading` 此前被 **20 处**使用却**从未定义**（静默无效类）；
  现为真实 20px 层级（`--text-heading--line-height: 1.35`）。
- 共享原语：`Badge`（6 语义 tone）、`StatusNote`（统一 loading/notice/error，tone 决定 `status`/`alert`）、
  `EmptyState`（editorial 左规，不做成卡片）、`SectionHeading`（eyebrow/title/description/action 一处声明）、
  `Panel`（`plain`/`focus`/`ai` 三种 surface）。
- **构建验证**：`text-heading` / `tracking-eyebrow` / `rounded-pill` / `bg-focus-surface` /
  `text-primary-ink` / `bg-neutral-soft` / `text-warning-ink` / `w-sidebar` / `bg-ai-soft`
  逐个在 `dist/assets/*.css` 中确认存在（不是「写了就算」）。
- 收敛的两处既有漂移：`exam-product-pages.tsx` 的 `text-danger` → **`text-danger-ink`**
  （该 token 的注释本身就写明 base 色不可作正文，实测 3.83:1 < 4.5:1）；`tokens.css` 为
  `--color-text-muted` 补上**可用背景说明**（仅在 canvas/white 达标，tinted 面上会掉到 ~4.4:1）。

**PROGRAMMING_UX（三层，不再同级竞争）** — `programming-pages.tsx`：

| 层 | 内容 | 视觉 |
| --- | --- | --- |
| 1 确定性工具 | `开始练习` / `运行` / `运行测试` / `运行代码诊断` / **`提交`** | 独立 `role="group"`，**唯一** filled Primary = 提交，其余 outlined |
| 2 AI 辅助（单次） | `AI Debug` + 失败测试快捷入口 | `Panel tone="ai"`，明确写「一次真实 AI 调用，会消耗额度」 |
| 3 高级工作流 | `Debug Agent` | **折叠**在 `<details>`（「高级工作流：Debug Agent（多步诊断与修补，逐步结算）」） |

- 题面从 `JSON.stringify` 改为**渲染后端真实字段**（`title`/`statement`/`input_format`/`output_format`/
  `constraints`/`public_samples`/`difficulty`/`source_label`），**提示与背景知识默认折叠**（提示不能替学习者答题），
  原始 payload 保留在「原始返回数据（后端原文）」折叠区内——**不丢数据、不换语义**。
- P7-A 的 endpoint 分离（诊断=/code/diagnose 编译器，AI Debug=/code/analyze，Agent=/programming/agent/debug）
  **原样保留**，全部既有断言仍在。

**真实契约对设计的两次否决（记录）**：

1. 设计上想给 Workbench 用「练习 `#id`」标题 → `/programming/exercises/{id}` 的响应在 OpenAPI 里是
   `unknown`（后端返回 dict），因此题面只能**按已知字段尽力渲染 + 原文兜底**，不臆造字段名。
2. E2E harness 的隔离库**没有编程练习题**（`GET /programming/exercises?language=Python` → 200 / count=0），
   所以 Workbench 的真实题面渲染由单测（用真实 serializer 字段构造的 payload）覆盖，e2e 只覆盖层级与折叠。

## 8. RESPONSIVE / ACCESSIBILITY（实测，非声明）

`tests/e2e/p7b-acceptance.spec.ts`（**opt-in**，需 harness + 全新 dev server，见文件头三步命令）：

- 6 个用例覆盖：三端导航切换（5 个宽度逐一断言 sidebar/drawer/bottom bar 的 visible/hidden）、
  手机底部栏 5 个目的地、**3 surfaces × 5 宽度零横向溢出**、Home 焦点槽位置链路
  （focus < agenda < recent < spaces < membership）、Workbench 三层纵向关系 + agent 默认折叠、axe。
- 断点：**1440 / 1366 / 1024 / 834 / 390**（1024 为侧栏边界，834 落在 768–1023，390 < 768）。

**axe 发现并修掉的 2 处真实回归**（都是本轮引入的）：

1. **link-in-text-block**：Profile「学习计划」行内链接改用 `text-primary-ink` 后，与周围
   `text-text-secondary` 对比度仅 **1.15:1**（<3:1），且无下划线 → WCAG 1.4.1 失败。
   修法：正文内链接加 `underline`（并在代码里注明原因）。
2. **contrast 4.4:1**：Workbench AI 面板里 `text-text-muted`(#6b7280) 落在 `bg-ai-soft`(#f5f3ff) 上
   只有 **4.4:1**（<4.5:1）。修法：tinted 面内改用 `text-text-secondary`，并把这条约束写进 `tokens.css`。
3. 另修：Auth 的 `<footer>` 原本嵌在 `<main>` 内，**不构成 `contentinfo` landmark**
   （`smoke.spec.ts` 的 `getByRole('contentinfo')` 会失败）→ footer 移出 main（同其他页面一致）。

## 9. 安全、工作树与 dev server 证据

- **NO_BACKEND_CHANGED = YES**：本轮写入的 28 个文件**全部**在 `frontend/` 与两个治理文件内
  （`find . -newermt … | sort` 全量列出，见 §11）；`find backend -name "*.py" -newermt "2026-09-20 22:45"` → **空**。
  本会话只**读取** backend（endpoint / serializer / CORS / onboarding 审计）。
- **未执行**：`reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` / `push` / `commit` / `deploy`。
- **USER_WORKTREE_PRESERVED = YES**：会话开始前已存在的全部 backend `M`、根目录未跟踪 sprint 报告、
  `.s*tmp/` 与 `.f1c*tmp/` scratch 目录**原样保留**；未删除任何既有文件。
- **dev server：确实重启了（必须记录）**：原本常驻 `127.0.0.1:5173` 的 Vite（PID 7816）在
  route option 变更后保留**陈旧 router 模块图**，会给出与磁盘代码不符的 e2e 结果
  （P7-A 已实测过一次）。本轮按其结论：**停掉该进程 → 以全新进程重启**（e2e 用 harness 端口，
  收尾后已恢复为普通 `npm run dev`）。当前 5173 上运行的是**本轮新起的、无 harness 绑定的 dev server**。
- **CORS 事实**：`allow_origins` 只含 `localhost:5173` / `127.0.0.1:5173`（无环境变量可扩展），
  所以 e2e 必须跑在 5173，不能换端口规避。
- **未重跑 `api:generate`**：本轮无 API 契约变更（前端只读既有契约）。

## 10. 需要你裁决 / 仍存在的产品阻塞（不改后端，如实记录）

1. **`needs_onboarding` 只能由 `POST /programming/onboarding` 清除**。它是 legacy 编程 onboarding 路由；
   Profile 里填了 `learning_direction`、备考设置也选好了，`needs_onboarding` **仍为 true**，
   Home 会一直显示「先完成两件设置」——**提示说的两件事做不到它要求的效果**。
   这是前端无法修的契约事实（无统一 onboarding 端点）。e2e 因此必须先调该路由才能看到
   Home 的「当前重点」形态（测试里已注明）。
2. **法务文档不存在**（无 `/legal` `/terms` `/privacy`）：只在 footer 陈述未发布，不链假页面。
3. **无密码找回契约**：未创建假流程。
4. **6 个 write-only profile 字段**（`school`/`learning_stage`/`ai_answer_style`/`answer_detail_level`/
   `material_reference_preference`/`daily_study_minutes`）仍全后端无读取方，**未**重新呈现。
5. **邮箱 bind-once**、**邮件/短信服务可能未配置**（503）——前端显示服务端原文，不假装成功。
6. **`/subscription/plans` 的 capabilities 无中文名映射**：不展示，不自造中文名。
7. **12+ 个既有 e2e spec 相对 auth guard 已过期**（需登录 harness）：本轮**未修改**，
   仍在 P7-A 记录的「待迁移」清单里。
8. **两处未被引用的历史残留**（本轮**未删除**，等你决定）：
   `frontend/src/features/home/home-page.css`（15KB，改用 token 后已无人 import）与
   `frontend/src/features/home/virtual-memory-visual.tsx`（无任何消费方）。
9. **唯一残留的非 token 尺寸**：`app-shell.tsx` 品牌 lockup 的 `h-[42px]`（P7-A 既有值，本轮未动）。
10. `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md:5` 的 stale 声明（见 §6）。

## 11. 本轮改动的文件清单（28 个，全部 frontend + 2 治理）

**新增（9）**
`frontend/src/components/ui/{badge,status-note,empty-state,panel,section-heading}.tsx`、
`frontend/src/features/auth/components/auth-hierarchy.test.tsx`、
`frontend/src/features/home/home-focus.test.tsx`、
`frontend/src/features/profile/components/profile-navigation.test.tsx`、
`frontend/src/components/layout/bottom-nav.test.tsx`、
`frontend/src/features/programming/components/workbench-hierarchy.test.tsx`、
`frontend/tests/e2e/p7b-acceptance.spec.ts`

**修改（17）**
`CLAUDE.md`、`.claude/rules/frontend-ui.md`、
`frontend/src/styles/tokens.css`、
`frontend/src/components/layout/{app-shell,primary-nav}.tsx`、
`frontend/src/features/auth/components/{auth-layout,login-page,register-page}.tsx`、
`frontend/src/features/home/{home-page,daily-agenda,learning-status,recent-learning,learning-worlds}.tsx`、
`frontend/src/features/profile/components/profile-page.tsx`、
`frontend/src/features/programming/components/{programming-pages,programming-pages.test}.tsx`、
`frontend/src/features/exam/components/exam-product-pages.tsx`（1 行 token 修正）

**自建临时脚手架（已全部删除）**：`playwright.p7b.config.ts`、`zz-debug.mjs`、`zz-shot.mjs`、
`tests/e2e/zz-p7b-acceptance.spec.ts`。
截图证据留在 `frontend/test-results/p7b/`（`.gitignore` 内）。
