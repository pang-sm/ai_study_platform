# ZHIXUE_FRONTEND_PRODUCT_SYSTEM_P7C_REPORT

> 范围：**P7-C（LEARNING SPACES · 三空间共享产品语言）**
> 日期：2026-09-21 · 工作树：`main`（**未** commit / push / rebase / merge）
> 后端：**未修改**（见 §8 证据）· P7-A / P7-B 成果：**保留**（见 §1）

---

## 0. 结论摘要

三个 Learning Space 现在说同一种产品语言，但各自保留业务语义：
统一的 breadcrumb / context 条 / tab 语法 / 事实呈现 / 空-错-载状态，
而 Course 是「课程闭环」、11408 是「考试 + 模块 + 真题」、Programming 是「语言 + Run/Test/Submit」。

同时修掉了本轮最大的产品债务：**用户可见界面上成片的 JSON dump 与后端内部字段名**。

---

## 1. 最终 gate 值

| Gate | 值 |
| --- | --- |
| P7B_REGRESSION | `PASS` — `p7b-acceptance` 6/6 复跑通过（含 axe）；P7-B 全部单测保留；**2 处 P7-B 断言按新结构更新**（见 §7） |
| FIRST_USER_LOGIC | `PASS` — Home 不再读 `needs_onboarding` |
| COURSE | `PASS` |
| EXAM_11408 | `PASS` |
| PROGRAMMING | `PASS` |
| SHARED_PAGE_GRAMMAR | `PASS` |
| CONTEXTUAL_NAV | `PASS`（三空间，桌面 + 移动） |
| RAW_UI_CLEANUP | `PASS`（审计命令与结果见 §5） |
| RESPONSIVE | `PASS`（5 surfaces × 1440 / 390 实测，零横向溢出） |
| ACCESSIBILITY | `PASS`（axe 0 violations；1 处真实对比度回归已修，见 §7） |
| CODEX_SPEC_APPLIED | **NO** — `ZHIXUE_P7C_*` / Codex P7-C spec 不存在于工作树（§2） |
| TYPECHECK | `PASS`（`tsc --noEmit`，exit 0） |
| LINT | `PASS`（`eslint .`，exit 0） |
| VITEST | `PASS` — **224 passed / 54 files**（P7-B 基线 214/53 → **+10 tests / +1 file**） |
| BUILD | `PASS`（`vite build`，exit 0） |
| PLAYWRIGHT | `PASS` — P7-A targeted `smoke` + `p7a-auth-surfaces` **10 passed**（无后端环境）；harness 环境 `p7b-acceptance` **6 passed** + 新增 `p7c-spaces` **3 passed** |
| AXE | `PASS` — **0 violations**（`/login`、`/register`、`/`、`/profile`、Workbench、Course ×2、CS408、Programming ×2；含 390px） |
| NO_FAKE_DATA | **YES**（§6） |
| NO_BACKEND_CHANGED | **YES**（§8） |
| USER_WORKTREE_PRESERVED | **YES**（§8） |

## 2. 关于 Codex P7-C spec（与 P7-A / P7-B 同样的结论）

`ZHIXUE_FRONTEND_PRODUCT_SYSTEM_P7C*` / `*P7C*` / `*LEARNING_SPACES*` 在工作树、Desktop、Downloads
（3 层）与未跟踪文件清单中**均不存在**（本轮再次实测）。因此 `CODEX_SPEC_APPLIED = NO`：
本轮执行的是任务书自身逐条要求 + 项目既有权威（Visual Direction / UI_DESIGN_SPEC / tokens.css）
+ **真实 backend 契约**（见 §3 的取证方式）。没有伪造「已套用 Codex spec」。

## 3. 三项裁决

| 裁决 | 结果 |
| --- | --- |
| **A. needs_onboarding** | 已完成。`features/home/space-context.ts` 用三个空间**各自的真实上下文**判断：`GET /course-learning/courses`（已声明课程）、`GET /exam/prep/profile`（后端自己的 `configured` 字段）、`GET /programming/onboarding`（`main_language` / `selected_languages` / `onboarding_completed`）。**任一空间已配置 → 首页进入正常 Daily Learning，不再显示全局设置提示**。`needs_onboarding` 完全不再参与展示判断（它只能作 legacy hint）。**未改任何 backend flag**。 |
| **B. stale governance fact** | 已完成（最小修正）：`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md` 第 5 行的「全新前端 = NOT_STARTED」替换为当前事实 + convergence 阶段说明 + 「SSOT 仍写 NOT_STARTED 属 stale 段，只报告不回写」。**未重写设计文档**，其余内容一字未动。 |
| **C. unused files** | 遵守：`home-page.css` 与 `virtual-memory-visual.tsx` **本轮未删除**，列入 `FINAL_CLEANUP_CANDIDATES`（§9）。 |

**§8 首个真实下一步（三空间各自）**：Course 无课程 → 学习档案填写关注课程（`PUT /me/profile` 的 `focus_courses`
确实是课程列表的来源，已在 `get_course_learning_selected_courses` 中核实）；11408 无备考上下文 → `/exam/setup`；
Programming 无语言 → `/programming`（**编程 onboarding 前端入口不存在**，见 §9 BACKEND_CONTRACT_BLOCKERS）。

## 4. SHARED PAGE GRAMMAR（§2 / §7）

新增 `frontend/src/components/page/`（6 个原语，全部至少被两个空间使用，没有做「万能组件」）：

| 原语 | 作用 |
| --- | --- |
| `PageHeader` | 页面身份：eyebrow + h1 + description + actions + 可选 breadcrumb |
| `Breadcrumb` | 位置链条（学习空间 › 上下文 › 当前页），末项 `aria-current`，非链接项不是链接 |
| `ContextHeader` | **当前上下文事实条**（当前课程 / 当前语言 / 模块…），任何页面都先回答「我在哪」 |
| `ContextNav` | 三空间共用的 tab 语法：`aria-current` + 下划线 + 移动端横向滚动，**不依赖 hover** |
| `FactList` / `FactValue` | 事实呈现：已知键→中文标签行；**未知键不臆造标签，折叠进「后端原文」**；`null` → `—` 而不是 0；可选 `valueLabels` 只翻译调用方声明的枚举 |
| `LoadingState` / `RawPayload` | 骨架加载（含 sr-only 状态）+ 统一的折叠原文块 |

复用 P7-B 已有：`SectionHeading`、`EmptyState`、`Panel`(plain/focus/ai)、`StatusNote`、`Badge`、`Button`。
新增 `lib/fact-labels.ts`（**键名全部来自真实 payload**：`backend/learning/report.py` 的
`report_period/structured_metrics/…`、course schemas、`WrongAnalysisResult` 的
`error_category/reasoning_gap/…`）与 `lib/format.ts`、`lib/router.ts`。

## 5. RAW UI CLEANUP（§6，系统性审计结果）

审计命令与结果：

| 检查 | 结果 |
| --- | --- |
| `JSON.stringify` 在非测试源码中 | **仅剩 `components/page/raw-payload.tsx` 一处**（所有 raw 输出的唯一出口，永远在折叠块内） |
| snake_case → 空格拼接（内部键名外泄） | **0 处**（P7-A 遗留的 `daily-agenda` facts 拼接已替换为 `FactList`） |
| `<pre>` 的剩余用途 | 仅代码/终端内容：agent patch、stdout/stderr、题面样例输入输出 —— 不是数据 dump |
| `unavailable` 等英文调试措辞 | `displayMetric` 的 `'unavailable'` → `'—'`；后端 `*_semantics` / `notes` 等**英文工程句**不再上屏（其键刻意不建标签，落入折叠原文） |
| 三空间实测 | `p7c-spaces.spec.ts` 断言：**任何含 JSON 片段的最小元素必须位于 `<details>` 之内**，5 个 surface 全过 |

具体收敛：Course 全 9 个页面（原 5 处 `JSON.stringify` + `DataRows` 只显示单个标签）、
`review-page`（metrics/domain_context 原文 + 内部 namespace/source/status）、`learning-intelligence`
（Structured Facts / Before / After / Explicit Apply / AI Narrative / unavailable 等英文标签 →
中文；`report_period`、六个 metric block、highlights/attention、data coverage 全部结构化呈现）、
`adaptive-practice`（`key: value` 拼接 → 事实表）、`DebugAgentSurface`（`JSON.stringify(tests_before/after)`
→ 通过/未通过事实；状态 `completed` → 已完成）。

## 6. 三空间各自的结果

**COURSE**：`course-pages.tsx` / `course-page-shell.tsx` / `course-workspace.tsx` / `course-index.tsx` 重写。
- 每个页面**始终显示当前课程**（ContextHeader，课程名来自该 course 作用域内的 dashboard）；
  breadcrumb `课程学习 › <课程> › <当前工具>`；tab 语法统一（概览/资料/知识结构/学习/练习/错题与复习/计划/记录/学习状态/课程问答）。
- 课程首页改为**学习闭环**：资料 → 学习 → 练习 → 错题与复习 → 计划 → 记录，六步带真实计数与真实链接，
  并有「下一步」。原来是一堆并列的孤立工具面板。
- 真实字段渲染：资料（文件名/类型/大小/解析状态/片段数/时间）、练习、错题（题面/你的作答/参考答案）、
  今日计划（`mode_label`/`urgency_label` **用后端自带标签**）、记录（事件流 + 汇总）、
  学习状态（`CourseStateResponse` 的五个 block）。
- 空状态都给真实去处；`<a href>` 内部跳转改为 `Link`（课程页面已全部客户端导航）。

**11408**：保留 dossier 视觉语法与业务语义（科目 / 模块 / 真题 ≠ 练习），不复制 Course 布局。
- **CS408 工具 tab 现在存在于每一个 CS408 页面上**（`ExamPageShell` 统一渲染，8 个页面传入自己的 tab），
  且**带着当前模块**跳转（`?module=`），不再从概览掉回第一个模块。
- 删掉一个真实假控件：模块行里 3 个 `aria-label="模块入口暂未开放"` 的死 `span` → 换成**真实链接**
  （知识脉络 / 章节练习 / 真题，带 `module`），并清掉一段永远为空的 `workspaceTools.filter` 死代码。
- breadcrumb `考研学习 › CS408 › <工具>`。

**PROGRAMMING**：Run/Test/Submit 仍是主流程（P7-B 三层结构未动）。
- 语言级 **tab 现在存在**（练习 / 错误与待处理 / 计划 / 记录 / 学习状态），并显示当前语言；
  此前这些页面之间**没有任何共享导航**。
- 编程首页改为：语言入口（主）+ 「一次练习是怎么走的」六步（Exercise → Workbench → Run/Test → Submit →
  需要时求助 → 修改重试）+ 工作台数据折叠；此前首页以一段 JSON 开头。
- Run/Test/Submit 与 代码诊断/AI Debug/Debug Agent 的层级关系在首页与「错误与待处理」页都以文字说明，
  与 P7-B 的工具条层级一致。

## 7. 真实缺陷与回归修复（本轮发现）

1. **axe：breadcrumb 在考试纸面底色上对比度不足**（`#2563eb` on `#e8e5da` = **4.09:1**，13px）。
   原因是 `index.css` 的全局 `a { color: primary }` —— 任何未显式着色的链接在 `lab-paper` 背景上都不过关。
   修法：breadcrumb 链接显式 `text-text-secondary`（5.91:1）+ hover 下划线。
2. **我自己的 P7-B axe 用例存在就绪竞态**：`goto` 只等到 load，React 路由尚未 mount 时 axe 会看到一个
   没有 main/h1 的空文档（实测在 `/register` 上偶发）。已在该用例中先 await h1 再分析（`p7c` 用例本就如此）。
3. `adaptive-practice` 把 `last_attempt_at` 一类内部字段名直接拼给用户看 → 改为事实表（未知键折叠）。
4. `daily-agenda` 用 `replaceAll('_',' ')` 生成"标签" → 改为 `FactList`。
5. `ExamFoundationPage` 的文案「CS408 学习工作区将在后续步骤接入真实学习内容」是**已过期的事实**——
   该组件当前无任何引用（见 §9），文案不再对用户可见。
6. `WrongAnalysisSurface` 旧实现里的「打开后端指定的下一步」分支**永远不会渲染**（`next_action` 是字符串，
   却被当成对象取 href）；现按契约字段 `next_action` 直接呈现建议文本，不做猜测式跳转。

**P7-B 断言更新的 2 处（都是结构按本轮要求改变，覆盖未减）**：
`debug-agent.test.tsx` 的「状态：completed」→「状态：已完成」与「测试前：{json}」→ 事实字段；
`presentation.test.ts` 的 `displayMetric(null)` → `'—'`（原为英文 `unavailable`）。

## 8. 安全与工作树证据

- **NO_BACKEND_CHANGED = YES**：`find backend -name "*.py" -newermt "2026-09-20 23:55"` → **空**。
  本会话只**读取** backend（report builder / course router / adaptive reason codes / programming payload /
  needs_onboarding 判定）以取得真实字段名。
- **未执行**：`reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` / `push` / `commit` / `deploy`。
- **USER_WORKTREE_PRESERVED = YES**：会话前已存在的 backend `M`、根目录未跟踪 sprint 报告与 `.s*tmp/` scratch
  目录原样保留；本轮**未删除任何文件**。
- dev server：e2e 前后按既定规则**重启**（陈旧 router module graph 会给出与磁盘不符的结果）；
  收尾后 5173 上运行的是普通 `npm run dev`。harness（隔离临时库、`APP_ENV=acceptance`）已关闭。

## 9. FINAL_CLEANUP_CANDIDATES 与 BLOCKERS

**FINAL_CLEANUP_CANDIDATES（本轮不删，仅登记）**
1. `frontend/src/features/home/home-page.css` — 裁决 C 要求保留（15KB，已无引用）
2. `frontend/src/features/home/virtual-memory-visual.tsx` — 裁决 C 要求保留（无消费方）
3. `frontend/src/features/course/components/course-workspace.css` — 本轮重写后**已无引用**（6 行）
4. `frontend/src/features/exam/components/exam-foundation-page.tsx` — **无任何路由引用**，且含过期文案
5. `frontend/src/features/learning-intelligence/presentation.ts` 的 `displayMetric` — 重写后仅剩 1 处调用
   （course shell 的名称兜底），可随下一次清理并入 `format.ts`

**BACKEND_CONTRACT_BLOCKERS（如实记录，前端不伪造）**
1. **`needs_onboarding` 只能由 `POST /programming/onboarding` 清除** —— 这就是裁决 A 的成因；
   现在首页不再依赖它，但**后端仍只有这一条清除路径**，且它同时会把 `learning_direction` 覆盖为「编程能力提升」。
2. **编程 onboarding 没有前端入口** —— `POST /programming/onboarding` 存在，但前端没有任何页面调用它；
   因此「编程语言上下文」目前**无法由用户在界面内建立**（首页只能指向 `/programming` 这一真实页面，
   并如实说明缺少声明入口）。
3. **课程选择也没有前端入口** —— 课程列表来自 `focus_courses` / `default_course_id` 的 fallback，
   用户只能通过学习档案的「关注课程」文本框间接设置；没有课程选择器或搜索。
4. `data_coverage.notes`、`state_semantics`、`metrics_semantics` 等是**英文工程句**，本轮不上屏
   （落入折叠原文）。若要中文展示，需要后端提供中文本地化字段。
5. 法务文档、密码找回、write-only profile 字段、邮箱 bind-once、`capabilities` 无中文名 —— 同 P7-A/P7-B，仍存在。
6. 12+ 个既有 e2e spec 仍需登录 harness（未动）。

**本轮保留的已知非阻塞项**
- 考试子工具内部的部分导航仍是 `<a href>`（整页跳转），例如章节选择器/真题索引/错题筛选。
  功能与 a11y 正常，但未改为客户端导航（属下一轮 polish）。
- 移动端 tab 条横向滚动时右侧标签会被裁切（可滚动、当前 tab 始终可见）；可选加渐隐提示。

## 10. 本轮改动的文件清单（49 个：48 frontend + 1 docs）

**新增（11）**
`components/page/{page-header,breadcrumb,context-header,context-nav,fact-list,loading-state,raw-payload}.tsx`、
`lib/fact-labels.ts`、`lib/format.ts`、`lib/router.ts`、
`features/home/space-context.ts`、`features/learning-spaces.test.tsx`、`tests/e2e/p7c-spaces.spec.ts`

**修改（38）**
`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`（裁决 B，3 行）、
course（`course-page-shell/course-pages/course-workspace/course-index` + 其测试）、
exam（`exam-page-shell` + 8 个 cs408 workspace + 2 个测试）、
programming（`programming-pages` + 其 2 个测试 + `api/programming.ts` + 2 个 route 文件）、
`home/{home-page,daily-agenda}` + 2 个 home 测试、
`review/review-page.tsx`、`learning-intelligence/{learning-intelligence-surfaces,presentation,presentation.test}`、
`components/learning/{advanced-learning-surfaces,adaptive-practice,adaptive-practice.test,debug-agent.test}`、
`tests/e2e/p7b-acceptance.spec.ts`（axe 就绪竞态修复）

**自建临时脚手架（已删除）**：`zz-check.mjs`。截图证据留在 `frontend/test-results/p7c/`（`.gitignore` 内）。
