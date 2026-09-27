# ZHIXUE_CORE_LEARNING_EXPERIENCE_RESTORE_REPORT

**轮次**：`ZHIXUE_CORE_LEARNING_EXPERIENCE_RESTORE`
**日期**：2026-09-22
**范围**：前端产品实现 + STEP 7 AI 能力层的授权功能补齐（见 §9）
**未执行**：commit / push / deploy（按要求）

---

## 0. 门禁值

```text
ACCOUNT_CLICK_TO_PROFILE        = PASS
HOME_COPY_REDUCED               = PASS
EXAM_SUBJECT_SETTINGS           = PASS
EXAM_408_MODULE_CHOOSER         = PASS
PROGRAMMING_EXERCISE_ROOT_CAUSE = DATA_NOT_SEEDED
PROGRAMMING_EXERCISES_VISIBLE   = YES
GLOBAL_AI_CHAT                  = PASS
QUALIFIED_MODEL_SELECTOR        = PASS
EXAM_AI_EXPLANATION             = PASS
PROFESSIONAL_AI_QA              = PASS
PROGRAMMING_AI                  = PASS
VISUAL_CANVAS_UNIFIED           = PASS
REAL_LEARNING_ACTIONS_PRESENT   = PASS
READY_FOR_USER_REVIEW           = YES
```

---

## 1. 编程题库 forensics（第 6 项）

```text
PROGRAMMING_EXERCISES_STILL_EXIST = YES
FORMAL_SOURCE_COUNT               = 240
CURRENT_HARNESS_COUNT             = 1
ROOT_CAUSE                        = DATA_NOT_SEEDED
```

测量依据：

| 量 | 值 | 来源 |
|---|---|---|
| `programming_exercises` 总行数 | 1923 | `backend/app.db` |
| API 可见（`reference_verified` + `starter_verified` + `is_active` + `quality_status='approved'`） | **240** | 与 `list_programming_exercises` 的 filter 完全一致 |
| 分语言 | C 60 / C++ 60 / Java 60 / Python 60 | 同上 |
| 被 filter 排除 | 1683（`is_active=0` 1683；`quality_status` needs_review 198 / rejected 1485） | 同上 |
| e2e harness seed | **1**（`e2e-two-sun`… 实为 `e2e-two-sum`，单一语言） | `backend/scripts/e2e_seed.py:89` |

**没有 QUERY_REGRESSION**：
- `normalize_project_language` 对 `C/c/cpp/C++/python/Python/java/Java` 全部返回正确规范名（实测）。
- 直接以 endpoint 的 filter 查询 `app.db` 返回 240 行，API 亦返回同一集合。
- 前端 `useProgrammingExercises` 只发 `language`，无 filter 丢题；"C → 0 道" 的原因是本地验收库是 harness 临时库，只有 1 道 seed 题目。

**处理**：按要求**没有重新造题**。建立本地人工验收 TEMP DB（见 §8），使用**正式题库**，未写入任何虚假 mastery / readiness / streak。

顺带修掉一个真实缺陷（非本次要求，但同属"题目看得见"）：题面的**公开样例**此前全部渲染成 `—`。后端字段是 `stdin_text` / `expected_stdout`，前端读的是 `input/stdin/output/stdout`，两套名字不相交。修复后 `123456 → -3`、`0000 → 0`、`987654321 → 5` 正常显示。

---

## 2. 账号入口（第 1 项）

- 删除右上角 dropdown（`account-menu.tsx` 的三项悬浮菜单）。
- 顶栏用户名改为**普通链接**指向 `/profile`，`aria-label="打开学习档案：<名字>"`，窄屏只留图标但仍保留可访问名称。
- 文件重命名 `account-menu.tsx` → `account-link.tsx`，`app-shell.tsx` 引用同步。
- Profile 页原本已承担：个人信息 / 学习设置 / 学习数据 / 会员 / 用量 / 账号与安全 / 法务 / 退出登录，无需改动。

## 3. 首页文案（第 2 项）

删除的解释型文案：

| 位置 | 删除内容 |
|---|---|
| `home-page.tsx` | `今天要做的事排在前面；下面是已经真实发生过的学习。`（整段副标题） |
| `daily-agenda.tsx` | `从最该做的开始往下排；完成一项后，这里会自动更新。` |
| `daily-agenda.tsx` | 空态 `当前没有需要优先处理的学习任务。` → `今天还没有安排。` |
| `daily-agenda.tsx` | 空态 `今天没有其他要优先处理的事。` 描述改为行动导向 |
| `first-run.tsx` | 三方向长解释段（三段）删除，标题合并为一句 |
| `recent-learning.tsx` | 空态长句 → `还没有学习记录。` |

**内部 code 泄漏已修复**：`完成什么动作后它会改变：{item.resolved_by}` 会直接渲染 `review_completion` / `task_completion`。该行**整行删除**——它回答的是"系统怎么刷新"，不是学习者的问题；而"打开并完成这项学习"按钮已经说明了要做什么。折叠的"为什么现在做这件事"保留，只显示后端 `priority_rules` 里的自然语言原因。

## 4. 考研（第 3、4 项）

- `/exam` 分组标题修复：此前 eyebrow `内容建设中` 下面的大标题永远写死 `学习路径`，导致 `学习路径` 出现两次；现在是 `1 门科目 / 可开始学习`、`3 门科目 / 内容建设中`。
- **`设置报考科目` 成为显眼主入口**：已配置状态在 dossier 顶部与 `继续学习` 并列；未配置状态入口同义改名为 `设置报考科目` → `/exam/setup`。setup 页支持政治 / 英语一二 / 数学一二三 / 408 / 专业统考 / 自命题专业课。
- `/exam` 展示的是**用户真实报考科目**（当前验收账号：408 + 政治 + 英语一 + 数学一 + 1 门自命题），不默认整个考研 = 408。
- **408 四科 chooser**：`/exam/cs408` 标题改为 `选择学习科目`，先列四门（数据结构 / 计算机组成原理 / 操作系统 / 计算机网络），每门带 `知识脉络 / 章节练习 / 真题`。`继续学习` 仍落在 `/exam/cs408`（chooser），不会直接跳进某一科 workspace。
- 进入模块后 breadcrumb 显示 `考研学习 › CS408 › 数据结构 › 章节练习` —— 学习者能看到 `408 → 数据结构`。

## 5. 专业学习（第 5 项）

- `/course` 精简为：当前专业 + 当前年级 + `调整专业与年级` / `继续学习` / `问 AI` / `本阶段推荐课程` / `我的课程` / `查看完整专业学习框架`。原先内联的五个框架分类详情移除。
- 新建独立页 `/course/framework` = `完整专业学习框架`，五分类全量展示，每门课带 `进入课程` + `问 AI`。
- 推荐课程继续标注 `智学AI推荐`，文案明确 `它是推荐，不是学校官方的培养方案`。
- 课程问答从 tab 末位提到第二位，并在每个课程页的 context header 增加常驻 `问 AI`。

## 6. AI 回到产品中心（第 7、8、9 项）

**全局 AI 学习入口**：顶栏顺序现为
`首页 | AI学习 | 考研学习 | 专业学习 | 编程学习 | 复习 | 学习报告 | 会员`

新建 `/ai` 统一对话页（`frontend/src/features/ai/`）：
- conversation history（读取后端 `ChatSession`，可切换、可开新对话）
- assistant / user 消息、citations（文件名 + 片段，折在回答下）、底部吸底 composer
- `深度思考` toggle → `POST /ai/deep-study`
- 上下文选择：**通用学习 / 考研科目（408 四门）/ 专业课程（5 门）/ 编程语言（C）**，全部来自该账号**真实存在**的上下文，映射 `service_key`（`course_learning` / `exam_11408` / `programming`）
- 课程上下文下可勾选 `引用资料`（`material_ids`）
- 上下文可通过 `?context=<kind>:<value>` 深链传入，供各学习空间跳转

**已验证端到端可出答案**（非空壳）：浏览器内真实提问 → 真实模型回答 → 追问继续同一会话。脚本 `scripts/ai-chat-e2e.mjs`，输出 `a real answer came back, and the follow-up continued the same conversation.`

**模型选择（第 9 项）**：`模型：自动推荐 ▾`
- 下拉项**只**来自后端 `GET /ai/models` 新增的 `preferences` 字段（`{key,label}`），**前端不写死任何 provider / model**。
- 学习者选的是**类别**（自动推荐 / 快速 / 均衡 / 强力 / 深度推理），不是模型名；**具体模型仍由 Router 决定**，entitlement / cost / availability / fallback 全部留在 Router。
- Free 只有 `自动推荐` 一个选项时不渲染控件（一个选项不是选择）。
- 越权不可达：Router 在 `qualified_models_for(tier, capability)` 之上按类别过滤，类别为空即 fail-closed。
- 该 picker 是**真的接进了服务链**，不是装饰：为此补齐了后端偏好透传（`OrderedCandidates` + `select_model` 都接 `preference`），否则会是一个"点了没用"的控件——本项目明令禁止。

## 7. 各学习空间的 AI（第 10、11、12、13 项）

| 空间 | 位置 | 入口 |
|---|---|---|
| 考研 | 知识点 | `知识点深度分析：<知识点>`（新增） |
| 考研 | 章节练习 | `AI 讲解这道题` + `继续追问`（措辞与追问已补） |
| 考研 | 真题 | 每题 `AI 讲解这道题` + `继续追问`（新增） |
| 考研 | 错题 | `WrongAnalysisSurface`（既有） |
| 专业 | 课程 | 首页/框架/课程页 `问 AI` + `课程问答` tab 第二位 |
| 编程 | 首页 | `开始练习` / `进入 Workbench` / `AI 编程问答`（新增三入口） |
| 编程 | 题目页 | `在 Workbench 中开始` + `问 AI 这道题` |
| 编程 | Workbench | 确定性 `代码诊断` / `AI Debug` / `Debug Agent`（语义继续分开，未合并） |

练习题流程符合要求：`作答结果 → 题目解析 → AI 讲解（按钮，非默认展开）→ 深度思考`。追问在**产品唯一对话面** `/ai` 继续——不是第二个聊天窗口。

## 8. 视觉画布统一（第 14 项）

冻结为：
- global header = 深墨蓝（`bg-lab-ink`，原本已如此）
- global canvas = `--color-page-background` `#fbfaf7`
- content surfaces = 同一基础纸色

**实测四个空间的 body 与 shell 背景全部为 `rgb(251, 250, 247)`**（home / exam / course / programming）。

改动：`.exam-shell` 原本整片涂 `--color-lab-paper` `#e8e5da` 暖米色，是全站唯一的分裂点，已改为 `--color-page-background`。Academic Dossier 保留在**局部**（`.exam-dossier` identity 块、题面 surface）。

新增统一的 **space accent** 体系（`src/styles/index.css`）：`--space-accent` 由各空间 shell 设置（exam `#5150a6` / course `#08736f` / programming `#6656c8`），只作用于三处——页面小标签、当前 tab 的 rule、当前 tab 文字。三个空间因此靠 accent 区分，而不是靠换底色。

## 9. 后端改动说明（第 15 项 / SCOPE）

本次**修改了 backend**，且是**授权范围内的功能补齐**，不是"为了 UI 顺手改后端"：

| 目的 | 文件 |
|---|---|
| 模型偏好真正生效（第 9 项要求 Router 仍负责选择） | `ai/pool.py`（`preference_class` / `PREFERENCE_LABELS` / `preference_options`）、`ai/router.py`（`select_model` + `ordered_candidates` 的 `preference`）、`ai/orchestrator.py`、三个 space adapter、`schemas.ChatRequest.model_preference`、`main.py` `/chat`、`routers/ai_models.py`（新增 `preferences`） |
| 学习者可见错误边界 | `main.py` 全局 500 / 422 handler |

错误边界这一项是**真实泄漏修复**：provider 无凭据时 `/chat` 曾返回
`服务器内部错误，请稍后重试。详情：Missing credentials. Please pass an \`api_key\` … \`OPENAI_API_KEY\` …`
——把 provider SDK 的错误、它要的环境变量名、以及供应商身份直接放进响应体。现在异常只进日志，响应体只留一句中文；前端再加一层：5xx 不渲染服务端 detail。新增 `backend/tests/test_error_detail_boundary.py`（3 项）钉住这条边界。

无数据库结构变更、**无需迁移**。

## 10. 本地人工验收环境（第 15 项）

- 位置：`.coretmp/zhixue_acceptance.db`（gitignored，**未碰** `backend/app.db` 与生产库；开工前后核对 `backend/app.db` 仍是 0 用户、无 `subscriptions` 表）
- 构建：`cp backend/app.db` → `alembic upgrade head`（正式迁移链，非 legacy 建表）→ `seed_acceptance.py`
- 内容：**全部来自正式内容库**——编程 240 道（240 可见 / 1923 行）、`exam_question_bank` 9333 题、知识点树（文件驱动）；专业 5 门课程；考研 408 + 政治 + 英语一 + 数学一 + 1 门自命题
- 学习者状态：`DATA_ORIGIN=ACCEPTANCE`，Advanced 订阅（以便复核全部 AI 能力）、1 条真实对话历史、2 道编程题为进行中
- **未写入**任何虚假 mastery / readiness / streak
- 当前后端运行在 `127.0.0.1:8021`，与既有 5173 dev server 的 `VITE_API_BASE_URL` 一致

---

## 11. 工程验证（实测，未伪造）

| 项 | 命令 | 结果 |
|---|---|---|
| typecheck | `npx tsc --noEmit` | 通过 |
| lint | `npx eslint .` | 通过 |
| tests | `npx vitest run` | **66 files / 326 tests passed** |
| build | `npm run build` | 通过（789ms） |
| backend tests | `backend/.venv/… -m pytest -q` | **1820 passed, 2 skipped**（1320s） |
| API 类型 | `openapi-typescript` 从 8021 重生成 | 通过（`model_preference` / `preferences` 已入契约） |

## 12. UI 验收（`zhixue-ui-acceptance`）

```text
VISUAL_DIRECTION          = PASS
LEARNING_FIRST            = PASS
SURFACE_CARD_ELIGIBILITY  = PASS
BRAND_INTENSITY           = PASS
TYPOGRAPHY                = PASS
TOKEN_USAGE               = PASS
BUTTON_HIERARCHY          = PASS
CARD_NESTING              = PASS
GRADIENT_USAGE            = PASS
RESPONSIVE                = PASS
STATE_COVERAGE            = PASS
ACCESSIBILITY             = PASS
DASHBOARD_DETECTION       = PASS
BACKEND_SCOPE             = PASS
AI_GENERIC_VISUAL         = PASS
```

测量依据（`scripts/ui-acceptance-pass.mjs`，17 个核心 surface × 1440/768/390）：

- **axe WCAG 2 A/AA：0 violations**，17/17 页面，serious/critical 均为 0
- **横向溢出：0px**，三个断点全部通过
- **每个页面都有可聚焦控件**（14–48 个）
- **卡片密度（`<main>` 内圆角+描边/阴影容器占比）**：home 1/128、exam 各 workspace 0、cs408 0、reports 0；最高是 profile 16/260、review 20/124 —— 不构成卡片墙
- Dashboard 检测：遮住 Logo 后，首页是问候语 + 单一重点 + 列表 + 三个文字入口；AI 页是双栏对话；考研是 dossier + 索引行。**都不像 admin/SaaS 后台**

**学习动作审计**（`scripts/learning-action-audit.mjs`，13 个核心页面）：每个页面都存在匹配的真实学习动作，无 banned copy。

## 13. 已知缺口（如实列出，未粉饰）

1. **模型回答的 Markdown 按纯文本渲染**。后端 system prompt 明确要求 Markdown（`backend/prompts.py` "Markdown 格式规范（必须严格遵守）"），前端用 `whitespace-pre-wrap` 原样输出，所以 `**加粗**` 会显示成字面星号。这是既有问题（课程问答一直如此），现在因 AI 成为主入口而更显眼。修法二选一：加 `react-markdown`（需你批准新依赖），或让 prompt 改吐纯文本。**本轮未动**。
2. **模型偏好按"类别"而非"模型"**。这是刻意的：`STEP7H_FRONTEND_API_HANDOFF.md` §I.5 禁止把 provider/model 暴露给前端。若你要的是"在已批准模型里点名具体某个"，需要先明确放开该禁令。
3. **本地 `.env` 只配了 DeepSeek / Qwen 的 key**（无 MiniMax 等）。因此手动选 `均衡`（standard 类）会由该 provider 承接并报 500；`自动推荐` 正常。这是本地密钥覆盖不全，非代码缺陷——生产配齐即无此现象。且 500 现已不泄漏任何内部信息。
4. **深度思考不支持编程上下文**（`DeepStudyRequest.service_key` 是 `Literal["course_learning","exam_11408"]`）。编程上下文中该开关**不渲染**，而不是渲染后悄悄降级。
5. **`/exam/cs408/practice` 的"推荐练习"**：六条候选是六个**不同**题目（`candidate_id` 不同），但同属知识点 8.7 `外部排序`，此前每行只显示 label 故看起来像重复六次。已补 `第 N / M 题 · 知识点 · 题型 · 难度` 使其可辨。根因是候选来自同一知识点、覆盖面提醒把它整组选出，不是数据错误。
6. **未跑 e2e（Playwright 项目测试套件）**。本轮用专门的证据脚本 + 验收脚本覆盖了真实浏览器行为，但 `npm run test:e2e` 未执行。

---

## 14. 改动文件清单

**新增（前端）**
`src/features/ai/api/ai-chat.ts`、`src/features/ai/components/{ai-chat-page,model-selector}.tsx`、`src/routes/ai.tsx`

**重命名**
`src/components/layout/account-menu.tsx` → `account-link.tsx`

**主要修改（前端）**
`components/layout/{app-shell,primary-nav,app-shell.test}.tsx`、`components/page/context-nav.tsx`、`components/learning/adaptive-practice.tsx`、`styles/index.css`、`features/home/{home-page,daily-agenda,first-run,recent-learning}.tsx` + 测试、`features/exam/components/{exam-product-pages.css,exam-page-shell,cs408-practice-workspace(+css,+test),cs408-knowledge-workspace,cs408-past-paper-workspace(+css)}`、`features/course/{api/course.ts,components/course-qa-chat.tsx,course-page-shell.tsx}`、`features/programming/{api/programming.ts,components/programming-pages.tsx}`、`features/advanced/workflow-adapters.ts`、`src/types/api.ts`(生成)

**新增（后端测试）**
`backend/tests/test_error_detail_boundary.py`、`backend/tests/test_model_preference_selection.py`

**新增（证据脚本）**
`frontend/scripts/{core-experience-shots,core-restore-evidence,ai-chat-e2e,ai-chat-viewport,ui-acceptance-pass,learning-action-audit,_mobile_shots}.mjs`

**未执行**：commit / push / deploy。
