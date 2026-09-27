# ZHIXUE_PRODUCT_IA_AND_LEARNING_SURFACES_V2_REPORT

**轮次**：产品 IA 与学习面重做（A–O 十五条）
**日期**：2026-09-21
**代码状态**：未提交、未 push、未 deploy。`HEAD = 8b4d0b6e`（保留）；`main` 相对 `origin/main` = ahead 1 / behind 0。
**改动规模**：87 个已跟踪文件被修改，33 个新增未跟踪路径（含本轮产物）。

> **provenance**：`8b4d0b6e 支持生产验收数据隔离` 未被触碰、未被 amend、未被 rebase。
> Auth polish 工作树完整保留（本轮在其之上继续，未 reset / restore / clean / stash / checkout -- / rebase）。

---

## 0. 先读这一段：三件必须由你决定的事

1. **自命题专业课（F）** —— 你要求 Exam Setup 支持选择「自命题专业课」。它**不在后端目录里**，
   而目录是 `STEP7H4` 冻结的 14 个科目（`cs_408` = ACTIVE，其余 13 个 FRAMEWORK_ONLY）。
   加入第 15 个科目等于改冻结契约，我没有单方面改。UI 现在**如实说明它为何不可选**。
   要我加，需要你明确批准解冻目录。
2. **会员额度上限（D）** —— 成本审计的结论是：**价格合理，额度上限失控**。
   Standard 售价 ¥29 却允许 ¥214.50/月 的 provider 成本（7.5×）；Advanced ¥149 对 ¥858（5.8×）。
   我在 `ZHIXUE_MEMBERSHIP_COST_AUDIT.md` 给出建议值，但**没有改** `DAILY_BUDGET` / `WEEKLY_BUDGET`。
3. **底部导航栏（A）** —— 我**移除了移动端底部 bar**（理由见 §A）。这是一次可逆的取舍，如果你要保留，说一声即可恢复。

---

## 1. 报告口径

- 本报告中的**验收数字**全部是本轮现场实测，不是引用历史。
- 截图来自一个**真实浏览器 + 真实 dev server + 桩化 API** 的采集脚本
  （`frontend/scripts/ia-acceptance-shots.mjs`）。**桩化的是数据，不是界面**：
  截图反映的是真实布局、真实 CSS、真实路由，但**数据是 fixture**，不代表线上真实内容。
- 后端行为结论以**后端测试**为准，不以截图为准。

---

## A. GLOBAL SHELL

**做了什么**

- 桌面端**永久左侧栏删除**（`app-shell.tsx` 的 `<aside aria-label="学习空间导航">` 整体移除）。
- 顶部统一导航，一条平铺、无分组：`Logo | 首页 | 考研学习 | 专业学习 | 编程学习 | 复习 | 学习报告 | 会员 | 账号`。
- 删除用户可见的 `学习空间`、`共享学习工具` 分组标题，以及 `一个账号、一套额度，三个学习空间共用。`。
- App header Logo 从 `h-[42px]` 放大到 `h-[54px]`，header 高度 64px → 80px。
- Auth 桌面端品牌区：图标 `size-28` → `size-44`，字标 `text-hero` → `text-display`，
  构图从"左上角一行"改为**垂直锁版居中**（`lg:my-auto`），空白收敛。

**移动端决策（需你确认）**：移动端 = compact top header + 抽屉式响应导航（`主导航（移动）`）。
**底部 5 格 bar 已移除**。理由：(1) 你指定了移动端模型为「compact top header + responsive navigation」；
(2) 抽屉与底部 bar 指向同一批目的地，是两套导航；(3) 释放手机底部条，供课程问答的 sticky composer 使用（K）。
这不是侧栏，但确实是常驻 chrome 的移除——**可逆，等你定**。

**测试影响**：`bottom-nav.test.tsx` 随组件删除（其对象不存在了）；
`tests/e2e/p7b-acceptance.spec.ts` 的 shell 断言改写为「无侧栏、无底部 bar、窄屏折入抽屉」。

---

## B. HOME

- 删除重复的整块「选择你的学习方向」（连同 3 个 SVG motif、编号、模式/范围元数据）。
- Home 现在只有四块，按顺序：**当前重点 → 今日议程 → 最近学习 → 极轻量学习方向快捷入口**。
- `待复习` 计数块与 `会员档位与可用额度` 块**从 Home 移除**：两者在 header 与 /membership 各有一份，
  且今日议程本就包含到期复习项。空出的位置还给了「今天做什么」。
- 研发文案清除：`先看服务端给出的下一步…`、`顺序由学习系统的服务端策略给出…`、`服务端没有排定其他优先任务。` 等。

**发现并修掉的真实缺陷（截图暴露）**：最近学习里显示**原始后端代码** `exercise_submitted`、
`summary.status` 的 `done`。已改为：未映射事件类型 → `学习活动`（真实但不泄露标识符），
未映射状态 → 不显示。**这是本轮最有价值的一次修复**：它把"未映射就打印原文"的旧策略改成了
"未映射就不说代码"。

---

## C. PROFILE 学习设置深链

**根因**：`/profile` 的 section 只是页内 `<a href="#id">`，没有任何 URL 状态；
从 `/course/setup`、`/exam/setup`、`/programming/setup` 回来时 `returnTo = '/profile'`，
于是**永远落在页首 = 个人信息**。

**修复**：
- `/profile` 新增 `validateSearch`，`?section=<id>` 是**受校验的** search param（`isProfileSectionId`）。
- 三个 setup 行的 `returnTo` 改为 `/profile?section=learning`。
- 到达后**自动滚动到该 section**（等 profile 数据就绪再滚——在导航同一 tick 里滚会找不到元素，
  那正是原来静默落在顶部的机制）。
- 侧栏分区列表与窄屏 select 都改成**导航**（写入 URL），因此 **active 正确、刷新保持、可分享**。
- Profile 不再依赖 global left sidebar（global sidebar 已不存在）。

---

## D. MEMBERSHIP / PAYMENT

**删除**：兑换码 learner UI 整体移除（`RedemptionRail` + `usePreviewRedemption`/`useRedeem`）；
`1 Credit ≈ ¥0.01 平台成本` 移除。后端 `/subscription/redeem*` 与 `/admin/.../redemption-codes`
**保留不动**（管理员仍在用）。

**成本审计**：产物 `ZHIXUE_MEMBERSHIP_COST_AUDIT.md`（根目录）。核心结论：

| tier | 售价 | 满额度时月 provider 成本上限 | 差额 |
|---|---|---|---|
| free | ¥0 | ¥21.45 | −¥21.45 |
| standard | ¥29.00 | ¥214.50 | **−¥185.50（7.5×）** |
| advanced | ¥149.00 | ¥858.00 | **−¥709.00（5.8×）** |

建议：**价格维持**（典型用量下 4–6× 余量），**weekly 上限下调**（free 70 / standard 225 / advanced 1160）。
**未执行**——这是产品决策。

**支付现实（审计确认）**：只有 `MockPaymentProvider`；`PAYMENT_PROVIDER` 非 mock 直接 RuntimeError；
生产拒绝 mock 支付（403）。因此：

- 会员页重做为**真实 Free / Standard / Advanced 价格与权益对照表**（三列共用一套横线逐行对齐，
  当前档位用列内边线标出，不是三张浮卡）。
- 新增 `/membership/payment`（订单确认页）：**创建订单 = 服务端真实写入 PENDING 行（`activated: false`）**；
  `去支付` **真实调用** `POST /subscription/orders/{id}/pay`，**403 就显示 403**：
  「在线支付还没有开通：**没有产生任何扣款**，你的档位也没有变化。」
  **任何代码路径都不会在客户端把订单标成已支付。**

**契约变更（ADDITIVE，已进 `docs/FRONTEND_API_CONTRACT.md`）**：
`GET /subscription/plans` 的每个档位新增 `price_cents` / `duration_days`，
来源是 `UNIFIED_PLAN_PRICING`——即 `create_pending_order` 计价的**同一个常量**。
这样页面显示的价格**只能是订单会收的价格**。`price_cents = null` 表示该档不可下单（Free），
渲染为「免费」而非「¥0.00」。**数值本身未变**（2900 / 14900 分，30 天）。
`src/types/api.ts` 已用临时库 + 非 8000 端口重新生成（**未触碰 `backend/app.db`**）。

---

## E / M. 学习者文案

**`共享学习核心` 删除**（review 页 + learning-intelligence 页的 eyebrow）。

**全前端清扫**了 `后端` / `服务端` / `服务器` / `结构化事实` / `当前上下文` / `学习空间`，
共 4 轮脚本化替换 + 手工复核。典型改写：

| 原 | 现 |
|---|---|
| `后端当前没有返回符合此范围的复习事实。` | `这个范围里现在没有要复习的内容。换个范围看看，或者先去完成一次练习。` |
| `后端返回了没有标识的课程，无法安全进入。` | `这门课程缺少标识，暂时无法进入。` |
| `本学习空间没有这类数据。` | `这个方向没有这类数据。` |
| `已按后端策略安排复习；…来自返回事实。` | `已安排复习；日期与间隔来自复习策略。` |
| `这是后端根据当前课程记录给出的下一步。` | `这是根据这门课程已记录的情况给出的下一步。` |

**边界说明（重要）**：`frontend/src/features/legal/{terms,privacy}-page.tsx` **保留**了
`服务器` / `服务端` 的措辞。隐私政策与用户协议**必须**披露数据实际存放与处理的位置，
把它改写成回避「服务器」会**降低**披露的准确性。这是本轮唯一的显式例外，且只限法务文本。

**同一轮发现**：`event-labels.ts` 原本明文写着「未映射的 code 直接显示 code 本身」。
该策略与本轮 M 冲突且已在截图中造成可见泄露（见 §B）。已改为通用且真实的标签。

---

## F. EXAM 信息架构

- **不再默认 408**：
  - `profileAction` 从「有 cs_408 就返回 `进入 CS408`」改为按**实际选中的科目**解析入口；
  - 科目入口从写死的 `/exam/cs408` 改为 `ACTIVE_SUBJECT_ENTRIES` 映射（当前只有 `cs_408`）；
    ACTIVE 但本 build 没有学习页的科目，**保留其自身页面**，不给一个会打开别的科目的按钮。
  - `knowledge` 路由的 `fallbackModule = 'data_structure'` **删除**——原来任何漏带 module 的
    CS408 链接都会静默打开数据结构。现在缺 module 就**问你选哪一门**（`Cs408ModuleChooser`）。
- **Exam Setup** 的科目选择沿用后端目录（公共课 / 专业统考分组），受校验、按真实 availability 标注。
- **Home（/exam）只显示真正选过的科目**（既有行为，已修正动作指向）。
- **未接入内容的科目**：`ContentUnavailableState` 如实说明，不伪造题库。
- **408 四门课**：`/exam/cs408` 仍是模块选择页，且现在**是必经之路**（上面那条 fallback 已删）。
- **重复清理**：
  - `ExamContextNav` 删除硬编码的 `CS408` 顶级项（它是十四个科目之一，不是与"我的备考""科目"并列的一级上下文）；
  - `ExamPageShell` 删除 `考研学习 / 全国统考 · 学习空间` 横幅——它让学习空间在页面开始前自我介绍了三次，
    还把「学习空间」这个产品内部词给学习者看；
  - 面包屑与 tab strip 保留（职责不同：一个说位置，一个说工具）。

**未能按原文完成的一项**：`自命题专业课` 不在后端目录里。见 §0.1。UI 现在**明确说明这一点**，
而不是给一个后端会 400 或背后什么都没有的选项。

---

## G. 章节练习

- **长题号栏删除**。新 `PracticeQuestionNavigator`：**一次 10 个题号**（`01–10`），
  `上一组` / `下一组`，以及 **`跳至第 [N] 题`**（跳转是让分组成为便利而非限制的关键）。
- 分组**跟随当前题**：`上一题/下一题` 跨过边界时题号跟着走。
- **移动端原本 `display:none`**（整条导航在手机上不存在）——现在可用，改为 5 列布局。
- **版式失衡修正**：删除装饰性大号题号（原 `font-size: 2.35rem` 的 `01`）；
  题干从 `clamp(1.35rem, 2.3vw, 1.9rem)` 降到 `clamp(1.05rem, 1.5vw, 1.25rem)`——
  题面是**读**的，不是**看**的。
- 题号按钮的 accessible name 现在带作答状态（`第 1 题（已作答）`）——此前"已作答"只靠边框颜色表达。
- 深度思考面板从页面**顶部**移到练习台**下方**：原来的位置让一个空输入框成为
  "一次只聚焦一道题"的页面的第一屏。

---

## H. 真题

**结论：H 已经由数据契约满足，本轮无需改动，已核验。**

- 后端 `PastPaperQuestion` 返回结构化 `year / question_number / stem / options`；
  `resources[].url` **是逐题裁剪图**（磁盘实测 1025×109 / 1025×242 等），**不存在整张试卷扫描字段**。
- 前端逐题渲染，`img` 上有限宽（`max-width:100%; height:auto`），图加载失败即隐藏。
- 视觉上把题面降到阅读字号（与 G 同一规则）；题号身份行从 section-title 降到正文。

---

## I. 专业学习

- learner-facing `课程学习` → `专业学习`；内部 `course_learning` 身份**未动**。
- **SSOT display naming 已同步**（2 处：§顶层定义句 + 学习导航树）。历史 phase 报告未回写。
- **Setup 已要求 专业 + 当前年级**（既有），本轮新增的是「**智学AI推荐学习框架**」：
  - 填好专业+年级后点「生成推荐学习框架」→ **先写 profile（专业/年级）再读推荐**
    （`GET /membership/recommendation` 读的是账号上的专业，不是表单里的；
    顺序反了就会按上一个专业回答，比不回答更糟）；
  - 后端返回的 `suggested_courses` 被归入**五个band**：数学基础 / 物理基础 / 专业基础 / 专业核心 / 方向课程；
  - **按年级重排显示顺序**（低年级先基础、高年级先核心），并在文案里说明这是**排序**而非对学习者的判断；
  - **默认全选、必须按「加入我的课程」才写入**——推荐未经确认不会出现在课程列表里；
  - 明确标注 **智学AI推荐学习框架**，并写明「它是推荐，不是学校官方的培养方案」；
  - 无法归类的课程名进入 `方向课程`，且说明该分类是阅读辅助。
- 专业名称归一：复用后端已有的 `normalize_major`，页面显示「专业已记为『X』」当它与输入不同时。

---

## J. 资料上传（真实缺陷修复）

**根因（确定）**：`useCourseMaterialUpload` 传的是 **plain object** `{ file }`。
`openapi-fetch` 的 `defaultBodySerializer` 只对**已经是 FormData** 的 body 放行，
其余一律 `JSON.stringify` 并设 `Content-Type: application/json`。
Starlette 只在 `multipart/form-data` 下解析 multipart，于是必填的 `file` 部分**根本不存在**，
FastAPI 在进入 handler 之前就返回 **422** → `requireData` 抛错 → UI 显示
「上传未成功，后端没有接受这个文件。」

**即：每一次上传都失败，与文件无关。** 原代码注释「openapi-fetch forwards File correctly」是错的。

**修复**：显式 `bodySerializer` 构造 FormData。

**顺带修掉的三件事**：
- UI **明确列出真实约束**：支持 PDF、图片（PNG/JPG/WebP）、Word(.docx)、PPT(.pptx)、TXT、Markdown、
  常见代码文件，单文件最大 20MB（并与后端 `ALLOWED_EXTENSIONS` / `MAX_NEW_TYPE_SIZE` 对齐）；
  file input 加 `accept`。
- 错误改为**显示服务端原文**（`serverMessage`）：格式不支持、扩展名与类型不匹配、
  旧版 .doc/.ppt、文件过大、重复文件、配额超限，各有各的话。
- 选择文件后清空 input，否则同一个文件重试时**不触发 change**，看起来像"点了没反应"。

**验收（诚实说明）**：`upload → parse → 列表 → 课程问答可用` 这条链路的
**传输层修复**已由代码与单元测试确认；但**端到端跑通需要真实后端与真实文件**，
本轮的可视化验收用的是桩化 API，**没有**完成一次真实上传-解析-引用闭环。
这一项按你的标准应记为**未完成端到端验证**，我把它列在 §O 的未验证项里。

---

## K. 课程问答

- 从「一次性问答」改为**真正的对话**：消息历史、学习者消息（右，主色浅底）、
  回答（整行，AI 面板）、**资料引用**（折在回答下：文件名 + 片段）、**底部 sticky composer**。
- **会话真实延续**：首轮不带 `session_id`，服务端开一个；之后把 `session_id` 传回去，
  `ChatSession` / `ChatMessage` 是服务端存储 —— 追问「那这一章的结论呢」现在知道「这一章」指什么。
- **深度思考开关**：关闭 = 普通课程问答（`POST /chat`）；打开 = **既有强推理工作流**
  `POST /ai/deep-study`（capability `tutor.strong_reasoning`），不是第二个聊天端点。
  开关有 `aria-pressed`，旁注说明打开时会更慢。
- **不暴露**：模型名、provider、request_id 一律不出现在文档里；
  request_id 只用于决定是否显示 👍/👎（沿用 `learner-safe.ts` 既定规则）。

---

## L. 编程

**删除**：「一次练习是怎么走的」6 步流程、`连续学习天数`、`今天练习次数`、`今天提交次数`、
以及整个「工作台数据」统计块（零值统计随之消失）。

**首页现在**：`继续最近练习`（从当前语言的练习列表里，取最近有过运行的、且尚未通过的那一道；
没有就**不显示这张卡**，不编造"进行中"）→ 语言入口 C → C++ / Python / Java →
当前语言的四个工具入口（练习 / 错题 / 记录 / 学习状态）。

**Workbench 未改动**：Run/Test → Submit → Diagnosis / AI Debug / Debug Agent 原样保留。

---

## N. 视觉系统

**问题（实测）**：每一个 CS408 页面和课程工作区都在用 `clamp(2.5rem, 5vw, 4.5rem)` 的 h1
（最大 72px），而同一页的标签是 13px——5:1 的比例，读起来是展示页而不是产品。
`exam-dossier__title` 最大到 **76px**，`exam-dossier__index`（纯装饰序号）最大到 **72px**。

**做了什么**：全部页面标题统一到 **`--text-page-title`（2rem）**，行高 1.2，字距 -.02em；
装饰性序号降到正文级；页面 h1 全部保留（此前会员页**根本没有 h1**——现在当前档位就是 h1）。
涉及 9 个 CSS 文件。题面/图例另按"可读"规则降到 `clamp(1.05rem, 1.5vw, 1.25rem)`。

**保留**：Technical Editorial / Academic Dossier 的方向、纸色画布、细规则线、tab 条。

---

## O. 验收

### 全部闸门（本轮现场实测）

| 闸门 | 结果 |
|---|---|
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS**（0 error / 0 warning） |
| `npm run test:run`（串行 `--no-file-parallelism`） | **308 passed / 62 files** |
| `npm run build` | **PASS** |
| `npm run check:api-origin` | **PASS**（122 个产物文件，无 loopback origin） |
| Playwright — 未加 harness 的规格 | **12 passed** |
| Playwright — 带认证 harness | **28 passed / 9 skipped** |
| Playwright — `p7b-acceptance`（本轮 shell 验收） | **6 / 6 PASS** |
| 截图 + axe（17 面 × 1440/390 = 34 张） | **无侧栏 / 无禁用文案 / 无 serious·critical axe** |
| 后端 `pytest -k "subscription or usage or membership or plan_catalog or entitlements or redeem"` | **116 passed** |

**关于并行测试的诚实说明**：`npx vitest run`（默认并行）在本机会出现
**1–4 条随机 timeout**（5000ms 上限；实测有的用例耗时 5243ms）。
串行 308/308 全绿，且**每次失败的用例都不同** → 判定为**机器负载导致的超时，不是逻辑失败**。
以下两条同时成立，我按串行结果作为权威数字：串行全绿；并行失败集合每次不同。

**关于 4 条 Playwright 失败的诚实说明**：`shared-learning-surfaces` / `programming-workspace` /
`practice-null-correct-smoke` / `p3b-learning-intelligence` 这 4 条**从未登录、也从不 stub `/me`**，
却期望渲染受保护页面。`HEAD` 的 `__root.tsx` 已经要求所有受保护路由必须有 session
（`ensureQueryData(sessionQuery)` → 无 session 则 redirect 到 `/login`），
所以这 4 条**在未改动的版本上同样不可能通过**。判定为**先于本轮存在的过期规格**，
未修改、未弱化守卫。

### 硬性 FAIL 条件逐条核对

| 条件 | 结果 |
|---|---|
| 任何截图仍出现 global left sidebar | **否**。34 张全部通过；检测器判据是「`<aside>` 内含 ≥4 个顶级导航链接」，而非"存在 aside"（考试设置页的步骤栏与确认块是页内 aside，属于正当用途） |
| 任何 learner copy 出现「后端当前没有返回」类研发语言 | **否**。34 张页面文本逐字扫描了 20 个禁用词；唯一例外是法务文本中的「服务器」（§E/M 已说明并说明理由） |

### 关键截图

全部 34 张在 `frontend/.iaaccept/shots/`，命名 `<宽度>-<面>.png`。
本轮随报告附上 6 张：`1440-home`、`1440-membership`、`1440-chapter-practice`、
`1440-course-qa`、`390-home`、`1440-login`。

### **未验证 / 未完成项（不掩盖）**

1. **资料上传的真实端到端闭环未跑**（J）：需要真实后端 + 真实文件；本轮可视化验收用桩化 API。
   传输层修复与单元测试已完成，**但"上传→解析→出现在资料列表→课程问答可引用"这条链路我没有实测过**。
2. **自命题专业课不可选**（F）：需你批准解冻考试目录（§0.1）。
3. **会员额度上限未调整**（D）：审计已给建议值，未执行。
4. **成本审计未读生产库**：第 4 节的"预期成本"是量级估算，不是实测分布。
5. **`f1c*` / `exam-vqa` 等规格未运行**：它们需要额外 flag（`F1C1_VQA_BACKEND`、
   `EXAM_VQA`、`ACCEL_VQA_API`）与对应 harness，本轮未提供。
6. **本次未提交**：按你的要求停在「报告 + 截图」，等你人工看完再决定提交。

---

## 改动清单（按面）

**Shell / 导航**
`components/layout/app-shell.tsx`、`primary-nav.tsx`、`account-menu.tsx`、
`features/auth/components/auth-layout.tsx`

**Home**
`features/home/home-page.tsx`、`space-shortcuts.tsx`（新，替代 `learning-worlds.tsx`）、
`daily-agenda.tsx`、`first-run.tsx`、`recent-learning.tsx`、`learning-status.tsx`

**Profile**
`routes/profile.tsx`、`features/profile/components/profile-page.tsx`、`profile-sections.ts`（新）、
`profile-learning-spaces.tsx`、`profile-settings.tsx`、`profile-membership.tsx`

**Membership / 支付**
`features/membership/components/membership-page.tsx`、`payment-page.tsx`（新）、
`membership-page.css`、`api/subscription.ts`、`view-models/membership.ts`、
`routes/membership/payment.tsx`（新）
后端：`usage/service.py`、`routers/subscription.py`（均 additive）

**Exam**
`features/exam/view-models/profile.ts`、`components/exam-context-nav.tsx`、`exam-page-shell.tsx`、
`exam-product-pages.tsx`、`cs408-knowledge-workspace.tsx`、`cs408-module-chooser.tsx`（新）、
`cs408-practice-workspace.tsx`、`practice-question-navigator.tsx`（新）、
`routes/exam/cs408/knowledge.tsx`、`routes/exam/cs408/practice.tsx`

**Course / 专业学习**
`features/course/api/course.ts`、`components/course-pages.tsx`、`course-setup-page.tsx`、
`course-framework-panel.tsx`（新）、`course-qa-chat.tsx`（新）、`course-framework.ts`（新）、
`course-index.tsx`、`course-workspace.tsx`

**Programming / 记录 / 情报**
`features/programming/components/programming-pages.tsx`、`api/programming.ts`、
`features/records/event-labels.ts`、`components/learning/adaptive-practice.tsx`、
`features/learning-intelligence/learning-intelligence-surfaces.tsx`、`features/review/review-page.tsx`、
`lib/fact-labels.ts`

**视觉（N）**
`cs408-{practice,knowledge,learning-records,past-paper,student-twin,study-plan,wrong-answer}-workspace.css`、
`course-workspace.css`、`exam-product-pages.css`

**文档 / 产物**
`ZHIXUE_MEMBERSHIP_COST_AUDIT.md`（新）、`docs/FRONTEND_API_CONTRACT.md`（新增一节）、
`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`（**仅 display naming 2 处**）、
`frontend/scripts/ia-acceptance-shots.mjs`（新）、`frontend/.iaaccept/shots/`（新，34 张）

**SSOT 修改声明**：只改了 `课程学习` → `专业学习` 两处显示命名，依据是你本轮「当前产品 SSOT 的
display naming 同步更新」的明确指示（SSOT §74 的"用户明确改变产品方向"）。
SSOT 中其他 stale 的 CURRENT / NEXT 段落**未回写**（按治理规则只报告）。
