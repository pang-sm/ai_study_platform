# ACCEL_PRODUCT_S9 — 概念身份传播 + 会员产品面 + 真实数据飞轮加固

```text
ACCEL_PRODUCT_S9_COMPLETE

GOVERNANCE_CURRENT_DOCS_UPDATED = YES  (2 files; SSOT 未改动 — 见 §1 说明)

CHAPTER_PRACTICE_CONCEPT_ID_PROPAGATION = YES
BACKEND_CONCEPT_VALIDATION              = YES  (4 条规则，422，不改写)
DIRECT_PRACTICE_CONCEPT_ID              = NULL
LEGACY_CONCEPT_BACKFILL                 = NONE

CONCEPT_INTERACTION_COVERAGE_BEFORE = 0 / 0      事实侧（本轮之前产品有 0 条学习事件）
                                      3330 / 4375 内容天花板 76.11%
CONCEPT_INTERACTION_COVERAGE_AFTER  = 3 / 4      事实侧（干净验收跑，全部 canonical）
                                      3950 / 4375 内容天花板 90.29%

CN_COLLISIONS_AUTOMAPPED   = 0
CN_CONTENT_REKEY_REPORT    = scripts/audit_cn_content_rekey.py
                             920 题 · 620 已解析 · 300 未解析 · 0 可证明重映射 · 写入 0

RESPONSE_TIME_COLLECTION = NOT_ADDED  (逐题边界不存在；attempt 级跨度被契约拒绝)
HINT_COUNT               = NOT_AVAILABLE

MEMBERSHIP_ROUTE          = /membership
MEMBERSHIP_CURRENT_TIER   = GET /subscription（统一档位）+ GET /membership/entitlements
                            （当前方向备考方案 — 真正决定功能是否开通的那一个）
UPGRADE_FLOW              = 兑换码激活（POST /membership/redeem），是唯一能真正解锁的路径；
                            在线支付 = 有界不可用（不创建永远无法结算的订单）
PLAN_LOCKED_MEMBERSHIP_LINK = YES  （旧的「锁定态不渲染链接」行为已退役）

STUDENT_TWIN_MODE         = USER_VISIBLE_PREVIEW   （未被本轮改动）
EVIDENCE_RELIABILITY_MODE = SHADOW_COLLECTING_DATA （未被本轮改动）
CS408_NATIVE_KT_MODE      = DATA_COLLECTION        （未被本轮改动）
TUTOR_POLICY_MODE         = SHADOW_COLLECTING_DATA （未被本轮改动）

FULL_BACKEND_TESTS   = 1558 passed / 2 skipped / 0 failed  (814.64s)
FRONTEND_TESTS       = 27 files / 111 tests passed；typecheck + lint + build PASS
PRODUCTION_DEPLOYMENT = SUCCEEDED  (run 35486662195 · commit 04947bca)
PRODUCTION_SMOKE      = 公网探针全通过 + 生产机上跑通既有 canary 机制；
                        带登录态的完整走查在**生产形状副本**上 46/46（见 §14 的口径说明）

REAL_APP_DB_MUTATED  = NO   (backend/app.db 只读审计；acceptance 跑在副本上)

BLOCKERS = 见 §16
```

---

## 1. 治理文档（PART A）

**`.claude/rules/frontend-ui.md`** — 「模型能力边界（视觉职责）」一节原本写着
13 个 scientific component 全部 `RUNTIME_ONLY`、`SHADOW = 0 / ADVISORY = 0 / ACTIVE = 0`、
`student_twin` 目标是 `SHADOW_ONLY`、「前端不得暴露任何 scientific component」。
该状态自 `ACCEL_SPRINT_S2` 起即已作废（S8 曾把它作为 stale claim 报告给用户，未自行改写）。

本轮用户明确授权更新，改为：

- CURRENT 表：`student_twin = USER_VISIBLE_PREVIEW` 且是**唯一**可暴露的组件；
  `evidence_reliability` / `tutor_policy` = `SHADOW_COLLECTING_DATA`；
  `cs408_native_kt` = `DATA_COLLECTION`；其余 5 个 = `RESEARCH_ONLY`。
- 硬规则改为：**只允许暴露 `user_visible === true` 的组件**，且判据是能力契约
  `GET /exam/prep/scientific/capabilities` 返回的字段，**不是本文件、也不是硬编码组件名**。
- 历史冻结记录**保留**在「历史冻结记录（不得当作 CURRENT，仅作沿革）」一节，
  原文状态与失效原因都写明了。

**`CLAUDE.md`** —

- `MIGRATION_HEAD = 20260917_0008` → **`20260919_0010`**，并加了一句「以
  `ls migrations/versions/` 为准，不要凭本文件断言」。
- 旧的 `DIVERGED` 断言（AHEAD = 15 / BEHIND = 12、merge base `81277a15`、禁止一切 git 操作）
  已**不再是事实**（实测 `git rev-list --left-right --count origin/main...HEAD` = `0 0`）。
  改为：**开工前现场检查** `git status --short --branch` / `rev-parse HEAD` / `log` /
  `rev-list --left-right --count`，并明确「不要相信本文件里的分支状态」；历史分叉信息
  作为沿革保留。
- 保留并强化长期红线：未经用户明确批准 `NO reset / clean / restore / stash / checkout --`，
  未跟踪的 scratch 目录同样不得删除。

**顺带修正一处失实**：原文写「真实 `backend/app.db` 尚未迁移到 0008」。实测本地
`backend/app.db` 是 legacy 开发库，**没有** `alembic_version` / `practice_*` /
`learning_events` 表，根本不由 Alembic 管理。CLAUDE.md 现在如实写明这一点，
而不是继续断言一个错的迁移状态。

**SSOT 未被改动。** SSOT §37.1 / §68.1 里同样过期的 `DIVERGED` 段落**没有**回写：
按 CLAUDE.md「修改 SSOT 本身的规则」，SSOT 内部的 stale CURRENT 段落属于
「报告给用户并等待决定」的情形，不属 §74 允许更新的五类。**在此报告**，
建议在下次正式 SSOT 更新时一并处理。

---

## 2. 概念身份传播（PART B）

### 2.1 产品决策

学习者从**规范知识叶子**进入章节练习时，产品**已经知道**这个知识点的规范 code，
它必须随 attempt / learning event / 数据集导出一起走，而不是留在客户端手里当摆设。

**概念从不推断**：不从标题、不从路径文本、不从数组下标、不从题干、不用模型。

### 2.2 前端契约（B1）

- 知识树里**唯一**携带规范身份的一层是 **section 行**（`section.code` 就是模块
  knowledge-map seed 发布的叶子 code，也正是题目 `knowledge_point_id` 存的那个字符串）。
  它在 section 行渲染 `知识点练习` 链接：
  `/exam/cs408/practice?module=<module>&chapter=<chapter.code>&concept=<section.code>`。
  两半都是 API 直接发布的规范字段，**前端没有做任何推导**。
- 实践路由新增 `concept` search param；API 模块里**一处**声明映射：
  读用 `concept_code`（规范过滤），写用 `knowledge_point_id`（attempt 真正存的那个槽）。
- `section.code` 是合成码（`_leaf:<path>`，API 给 seed 里没有 code 的节点生成的）
  时**不渲染该链接**：那种节点没有规范身份，没什么可传播的 —— 不是「渲染了再被服务端拒绝」。
- 章节级 `章节练习` 链接**不带** concept，因此直接入口声明 NULL。
- 学习计划的 `去练习` 同样不带 concept：`ExamStudyPlanTaskItem` 只有
  `knowledge_point_name`（展示字符串）没有 code，plan 不知道规范概念，**不得凭空造一个**。

### 2.3 后端校验（B2）

`POST /exam/11408/{subject_key}/chapter-practice/attempts` 的 `knowledge_point_id`
从「任意字符串照单全收」变成**校验后接受**。非空时四条规则全部必须成立：

| # | 规则 | 不成立时 |
|---|---|---|
| 1 | 该模块发布了 knowledge-map seed | 422 `CONCEPT_NOT_CANONICAL_LEAF_OF_MODULE` |
| 2 | 该值是该模块的**规范叶子 code** | 同上 |
| 3 | 所选题目**全部**属于该模块 | 422 `CONCEPT_QUESTION_MODULE_MISMATCH` |
| 4 | 所选题目**全部**携带该概念 | 422 `CONCEPT_QUESTION_SET_MISMATCH` |

`detail` 是结构化的 `{code, message, concept_code, subject_key, mismatched_question_ids?,
other_modules?}`，**值从不被改写、不被就近匹配、不被静默丢弃**。

规则 4 用的是与**读取路径完全相同的一个函数**（`_question_carries_concept`），
它直接读版本化解析器 `science.concept_coverage` 的 `canonical_code`，
所以「服务端刚发出去的题集一定可以被提交」是构造性成立的，而不是靠两边各自实现后碰巧一致。

规则 2 顺带覆盖「属于预期的 CS408 模块」：seed 是**按模块**加载的，
另一个模块的叶子 code 不可能出现在本模块的集合里（测试用 `operating_system` 的 `1.3`
打给 `data_structure` 验证，见 §11）。

**读取路径**同样新增 `concept_code`（与 legacy 的 `knowledge_point_id` 子分组过滤
**是两个不同参数**，后者语义未变）：

- 不是该模块的规范叶子 → **422**。刻意不返回空列表：「这个知识点没有题」与
  「这压根不是一个知识点」是两个不同的回答，只有一个是真的。
- 是规范叶子但没有题 → 200 + `total = 0`（诚实；例如 `computer_network` 第 4 章撞位叶子）。

### 2.4 一个真实的伪造通道被关掉（B3 的隐藏部分）

传播链是
`legacy attempt.knowledge_point_id → cs408_context → PracticeAttempt.context_json →
LearningEvent.knowledge_point_ref_json → kt_dataset.concept_key`。
其中 `native_concept.reference_from_context` 是**逐字拷贝**的。

也就是说：**在 S9 之前，任何客户端往 concept 槽里塞的任意字符串，都会原样变成
学习事件上的「概念引用」，进而变成训练数据集里的 concept key。** 这是本轮顺带关掉的
伪造通道，而它不在原任务书的字面要求里 —— 但它正是 B4「legacy attempt 保持 null」的前提。

新增 `learning/spaces/exam_prep/context.py::canonical_module_concept`：
镜像边界上，只有解析器确认为**本模块规范叶子**的值才进入 concept 引用，其余一律缺席。
原始字符串**不丢失**：它仍然原封不动留在 `QuestionRef` 的 provenance 里。

放在这里而不是放在 `science/` 直接调用，是因为 `science/*` 已经 import `learning/*`；
反向 import 会形成环。该函数用**惰性 import**，并复用解析器而不是复述规则 ——
「概念身份只有一个所有者」这条才是重点。

### 2.5 缺席身份（B4）

`NULL` 仍然是完全合法的值，并且是以下四种情况的**诚实编码**：
直接入口、真题、legacy attempt、来源不明确。
`knowledge_point_name` / `knowledge_point_path` 是**展示字符串**，照原样存，永不参与概念解析
（测试钉住了这一点：把叶子的 title 当概念发过去 → 422）。

---

## 3. 数据集影响（PART C）

### 3.1 内容天花板（可测，未变化）

S9 **没有改动任何一行题库**，所以内容侧 before/after 与 S8 完全一致（复现验证）：

```text
ALL 9333 QUESTIONS      concept 5094 (54.58%) -> 5714 (61.22%)   +620
ACTIVE 4375 QUESTIONS   concept 3330 (76.11%) -> 3950 (90.29%)   +620
resolved_by_rule        canonical_leaf_code 5094 · title_echo 205 · source_ref 415
corroboration           rules_disagreed = 0 · chapter 段一致 620 / 620
REFUSED near-matches    7 组 × 5 行 = 35 行（computer_network 第 4 章数值撞位）
```

内容天花板是「题库**能**产出多少概念级事实」的上界，不是「已经产出了多少」。

### 3.2 事实侧（在副本上实测）

在一份**迁移过的生产形状副本**上跑完整验收流程（§12），产出的真实事实流：

```text
CONCEPT_INTERACTION_COVERAGE_BEFORE = 0 / 0
    本轮之前产品有 0 条学习事件（S7 实测 users_with_eligible_interactions = 0，
    S8 复测仍为 0）。事实侧没有可比较的历史，这不是「测出来是 0」，
    是「本来就没有」—— 所以不存在伪造的历史回填（PART C 明确禁止）。

CONCEPT_INTERACTION_COVERAGE_AFTER = 3 / 4 eligible
    events_scanned 51 · users 1 · eligible 4
    module_level 1 · concept_level 3 · non_canonical 0
    excluded CORRECTNESS_NOT_AUTHORITATIVE_BOOLEAN 47

    3 条 concept-level 全部来自「从知识叶子进入」的 attempt；
    1 条 module-level 来自**直接入口**（该 attempt 没有声明概念，NULL）。
    这正是设计意图：有概念的地方有，没有概念的地方诚实为空。
```

**数据集导出随同验证**：

```text
kt_dataset.build(service_namespace="exam_prep")
sequences 2 · interactions 4 · concept_levels {"exam_module_id": 1, "knowledge_point_id": 3}
concept keys ["3.6", "computer_network"] · dataset_hash 321f40d033d4f825
```

**新增测量工具**：`science.kt_dataset.interaction_coverage(db, ...)` —— 只读，
按事实**诚实携带**的最深层级统计（module / concept），并把
`concept_level_before`（上古的「存什么就算什么」读法）与 `concept_level_after`
（只认 canonical）分开报，差额就是写入边界现在关掉的那块伪造面积。
它**不修改**已写事实的数据集语义：改写历史与回填历史是同一类错误，
诚实的处理方式是**测量并报告**。`non_canonical_concept_ids` 会把任何这样的 id
**列出来**（identity，不是内容，不含 PII）。

---

## 4. computer_network 内容重映射候选报告（PART D）

**全部已知撞位继续拒绝。剩余的题一道都不自动映射。**

新增 `scripts/audit_cn_content_rekey.py`（只读，写 0 行）+
`science.concept_coverage.unresolved_identity_report`：

```text
snapshot: .s8tmp/probe.db (真实题库 9333 行)
module  : computer_network
questions examined        : 920
already_resolved          : 620
concept UNRESOLVED        : 300
    by_current_level      : chapter 255 · module_only 45
    by_current_chapter    : 4 → 255 · (none) → 45
    by_reason             : STORED_ID_DOES_NOT_EQUAL_ANY_CANONICAL_LEAF_CODE 255
                            STORED_CONCEPT_ID_IS_EMPTY 45
PROVABLE rekeys available : 0
writes                    : NONE
```

**为什么是 0，而不是「我们没试」**：报告对每一行都跑了产品自己的版本化解析器，
并对每个未解析行都算了一遍 near-match。结论是：

1. **没有任何一行的存留 id 等于某个规范叶子的 title 原文**
   （`stored ids that ARE a canonical leaf title verbatim: []`）。
2. `computer_network` 规范第 4 章只有 **7 个叶子**（4.1 网络层的功能 / 4.2 IPv4 /
   4.3 IPv6 / 4.4 路由算法与路由协议 / 4.5 IP多播 / 4.6 移动IP / 4.7 网络层设备），
   而来源章节是 4.1…4.51 的**另一套编号、另一个粒度**。两者没有一对一关系。
3. 35 行的 near-match（`4.1 异构网络互连` ~ canonical `4.1` 等 7 组）被**列出**而不是丢弃 ——
   那正是更宽松的规则会接受的形状，列出它才让拒绝可审计。

**没有 LLM 映射，没有模糊匹配，没有标题相似度，没有位置推断。**
重映射 `exam_question_bank` 是**内容决策**，不是工程决策；本报告把该决策的规模
变成精确数字（300 行），然后停手。

---

## 5. 响应时间采集（PART E）

**结论：不加。** 逐题计时边界在当前 CS408 练习面上**不存在**，因此按任务书要求「不加」。

审计结果写进了 `learning/practice/telemetry.PER_QUESTION_TIMING_BOUNDARY_AUDIT`
（可执行文档，有测试钉住它与真实请求路径一致）：

| 边界 | 是否存在 | 原因 |
|---|---|---|
| `per_item_serve` | **否** | 题干列表**一次响应**返回整套题；attempt 创建时一次性带上全部 question_ids。没有任何「单独交付一道题」的请求，因此没有可记录的逐题交付时刻 |
| `per_item_submit` | **否** | submit 一次请求提交**全部**答案；save 接口接受部分 dict，其条目与「重述已作答内容」无法区分，两者都不是单题作答事件 |
| `attempt_serve` | 是 | `exam_practice_attempts.started_at`（列默认值，INSERT 时写入） |
| `attempt_submit` | 是 | `submitted_at`（submit handler 写入） |

**为什么 attempt 跨度也不收**：`started_at → submitted_at` 是真实测量，但它是
**attempt 跨度**：覆盖整套题、对每道题是同一个数。把它按 `response_time_ms` 落到每道题上，
就是断言 N 个从来没测过的逐题时长。数据集读的就是 `response_time_ms`，
所以那个名字下的跨度会被每一个下游读者当成逐题时长消费 —— S5 的规则
（「一个时长必须同时给出它测量的是哪两个边界」）明确拒绝它。

边界情况（全部写进审计文档并有测试）：

- **页面刷新**：重读同一个 attempt，不产生任何新边界、不产生任何数字。
- **后台标签页**：服务端不可观测，且会**膨胀**任何墙钟跨度 —— 这正是跨度被拒绝而不是
  被「加注说明」的原因。
- **未作答 / 放弃**：`in_progress` 永不写 `submitted_at`，因此**完全没有跨度** ——
  一道被交付但从未完成的题，诚实的编码就是「没有」。
- **重复提交**：submit 要求 `status == in_progress`，第二次是 404，不可能被重复计数。

**实测确认**：验收跑中每一道题的 `response_time_ms` 与 `response_time_source`
都是 NULL（`tests/test_s9_concept_identity.py` 钉住）。

---

## 6. hint_count（PART F）

**`hint_count = NOT_AVAILABLE`。不创建零值字段。**

- 产品**没有**任何提示机制（CS408 章节练习、真题、课程练习、编程题四个面都没有）。
- `practice_attempts` 与 `learning_events` 两张表都**没有** `hint_count` / `hint_source` 列。
- 迁移 `20260919_0010` 的 `NEW_COLUMNS` 精确等于
  `{response_time_source, attempt_index}`，**没有**任何 hint 列 —— 测试直接
  exec 迁移模块读它的 `NEW_COLUMNS`，而不是匹配文本（那份迁移的 docstring 里
  确实**提到** hint，用来解释为什么没有它）。
- `AttemptTelemetry(hint_count=0, hint_source=NO_HINT_MECHANISM)` 会 **raise**：
  在一个没有提示机制的面上存 0，等于断言「有机制、但没用」，那是没做过的观测。

---

## 7. 会员产品面（PART G）

### 7.1 建了什么

新路由 `/membership`（顶部导航新增「会员」入口），页面从**产品自己的**端点读取：

| 区块 | 来源 |
|---|---|
| 统一会员档位 + 政策版本 | `GET /subscription` |
| 当前备考方案（**真正决定功能开通与否的那一个**） | `GET /membership/entitlements?service_key=exam_11408` |
| 当前权益 | 同上（`learning_plan` 的 `allowed` / `required_plan`，逐条列出） |
| 本期额度 | `GET /usage/summary`（真实 Credits，预留 + 已结算 + 剩余） |
| 档位对照 | `GET /subscription/plans`（每日/每周额度 + 能力 id + 中文标签） |
| 激活 | `POST /membership/redeem/preview` → `POST /membership/redeem` |

**视觉概念**（按项目规则先写概念再写代码）：这不是定价页，也不是 SaaS 三宫格，
而是一本**会员账簿**。焦点元素是学习者自己的档位（全页最大字号），
非对称构图 —— 左侧宽栏放「当前权益 / 本期额度 / 档位对照」，
右侧窄栏放唯一的激活路径。档位是**排行行**（tabular 数字 + 能力列表），不是三张一模一样的卡片。
无渐变、无发光、无卡片套卡片，颜色只来自 `tokens.css`。

### 7.2 一个必须报告的发现：两套会员体系当前互不联动

任务书要求「如果 order/payment 后端已经存在，就诚实地接上」。接的过程中实测发现：

```text
POST /membership/redeem   → 写 user_service_memberships（按方向的备考方案）
                            学习计划 / 学习报告的 gate 读的**就是**这一行  →  **锁开了**
POST /subscription/redeem → 激活统一 subscriptions 档位（真实、原子）
                            不写按方向的行  →  **功能仍然锁着**
```

两半都有测试钉住（`test_redeeming_the_required_plan_flips_the_gate_the_locked_state_reports`
与 `test_the_unified_redeem_moves_the_tier_but_opens_no_feature`），
端到端验收里也实测了「兑换后 `learning_plan.allowed` 由 `false` 变 `true`、
学习计划接口由锁变 200」。

**因此页面提供的是能真正解锁的那条路径**。提供统一兑换码那条会「改一个数字、
功能照样锁着」，正是任务书禁止的 fake success flow。

这不是把旧三服务会员当目标架构继续扩展（SSOT §67 禁止的是后者）：SSOT §41 明确
CURRENT 仍是旧三服务会员、统一档位是 FROZEN TARGET，本页把**两个事实都摆出来**，
并写明「学习计划等功能的开通以「当前备考方案」为准」。

### 7.3 在线支付：有界不可用，不是假的成功流程

`POST /subscription/orders` 确实存在，能创建一个 PENDING 订单；但它的唯一支付方式是
`mock`，而 `is_mock_payment_allowed()` 在生产返回 false（403）。
**因此页面不创建订单。** 一个任何可用支付方式都无法结算的订单，会让学习者手里多一条
永远 pending 的记录，还假装那是进展。

页面改为：完整展示档位信息 + 一个禁用按钮（`暂不可用`，`aria-describedby` 指向原因）
+ 一句事实说明。测试直接断言 `POST /subscription/orders` **从未被调用**（DB 计数也验证）。

### 7.4 顺带修掉的契约瑕疵

`GET /usage/summary` 的 `periods.<daily|weekly>` 此前**按值返回两种不同形状**：
有额度上限时是 4 个键，无上限时（Advanced 无每日上限）只有 `budget` + `remaining`。
一个端点按值给两种对象，消费者必须先分支判断形状才能读数字。现在恒定返回 4 个键，
无上限时为 `null`。**纯新增**（缺的两个键现在为 null），不删键、不改义。

`GET /subscription`、`GET /subscription/plans`、`GET /usage/summary`、
`POST /membership/redeem[/preview]` 此前返回裸 `dict`，OpenAPI 里是 `{}` ——
前端拿不到任何类型。S9 为它们声明了响应模型，字段逐一取自真实运行时 payload，
**响应体不变**，只是被契约固定下来（`api.ts` 随之重生成）。

---

## 8. 学习计划锁定态（PART H）

规范会员路由存在之后，锁定态改为：

```text
学习计划 /
当前会员暂未开放学习计划
学习计划需要开通对应的备考方案，当前账号尚未开通。
[查看会员档位与权益]  ->  /membership
```

**旧的「不渲染任何链接」行为已退役**，测试同步更新并说明了原因
（S8 之所以钉住「没有链接」，是因为当时确实**没有**规范目的地；
一个锁却无处可去是死路，而现在有了）。

`required_plan` 是 legacy 套餐 code（`monthly_sprint`），**不是**统一档位。
页面**没有**把它翻译成 `Standard` / `Advanced` —— 那是后端不做的映射。
两处（学习计划锁定态、会员页权益行）都只作文字陈述，不伪造档位名。

---

## 9. 产品数据采集状态（PART I）

`GET /science/status`（ADMIN-ONLY，401/403/200 三个门都实测）新增 `data_collection`：

```text
measured            true（未传 db 会话时 false，且**不出现计数键** —— 没数过 != 数到 0）
scope               exam_prep
users_with_events / users_with_eligible_interactions
eligible_interactions
concept_level_interactions      <- 概念级模型真正能训练的那部分
module_level_interactions
non_canonical_concept_ids
events_scanned / excluded
collection_start_version        ACCEL_SPRINT_S6
per_module                      逐模块同样口径
uncollected_fields              response_time_ms = NOT_COLLECTED (coverage null)
                                hint_count        = NOT_AVAILABLE  (coverage null)
```

**无 PII**：只有计数、没有学习者引用；测试断言 payload 里不出现用户名 / 邮箱 /
password，且 `data_collection` 的值里没有 16 字符的 learner_ref 形状。
验收跑实测该块输出 `{"users_with_events": 1, "eligible_interactions": 4,
"concept_level_interactions": 3}` —— 与 §3.2 的独立测量一致。

---

## 10. 模型路线冻结（PART J）

**本轮没有晋升任何模型。**

```text
student_twin          USER_VISIBLE_PREVIEW     未改动
evidence_reliability  SHADOW_COLLECTING_DATA   未改动
cs408_native_kt       DATA_COLLECTION          未改动
tutor_policy          SHADOW_COLLECTING_DATA   未改动
legacy learner_state  RESEARCH_ONLY            未改动
misconception_v2      RESEARCH_ONLY            未改动
memory / irt / concept_verifier  RESEARCH_ONLY 未改动
```

验收跑实测 `GET /exam/prep/scientific/capabilities` 的 `user_visible` 集合
**恰好等于** `["student_twin"]`，没有任何 shadow / research 组件被暴露。
`/exam/prep/scientific/student-twin` 仍然应答（200）。

`cs408_native_kt` 的 `DATA_READINESS_GATE` **仍然是 FAIL**：本轮把
concept-level 交互从 0 变成 3，但那是**验收流程**产生的 3 条，不是真实学习者数据；
真实门槛（users_with_eligible_interactions ≥ 100 / total_eligible_interactions ≥ 2000）
一条都没接近。**本轮没有、也不能声称这个 gate 有实质进展。**

---

## 11. 测试（PART M）

### 后端

新增两个文件：

```text
backend/tests/test_s9_concept_identity.py            24 tests
    resolver 门 · 端到端传播（leaf → attempt → event → dataset）
    非法概念 / 跨模块概念 / 题目集不一致 / 跨模块题目集 全部 422
    直接入口 NULL 一路走到事件 · legacy 非规范 id 不被提升为概念引用
    不从 title/path/index 推断 · CN 撞位仍被拒
    交互级覆盖测量（canonical vs blind）· 空流报 0 不猜
    重映射候选报告 0 可证明 + 写 0 行 + 无模型无学习者数据
    共享章节读取器与 API 一致（差异已钉住并说明）
    读写的 is-consistent 判定是同一个函数
    响应时间契约与真实请求路径一致 · 放弃 / 重复提交
    hint 无字段（直接读迁移的 NEW_COLUMNS）

backend/tests/test_s9_membership_and_status.py       18 tests
    每个 per-user 端点 401 · 计划目录公开（并说明为何）
    档位与目录具体 · usage 一种形状（有/无上限）
    权益判决与 gate 同源 · 兑换真实激活 · 非法码带真实原因
    跨用户隔离（档位 / 权益 / 码不可重用）
    会员面不创建订单（HTTP + DB 计数）
    兑换必需套餐后锁**真的开** · 统一兑换只动数字不开功能（两半都测）
    /science/status 管理员门 · 采集就绪度计数与真实流一致
    无 PII · 无会话时 measured=false 且无计数键
    迁移：全新库 alembic upgrade head 到唯一 head、integrity ok、无 hint 列
    单一 head · S9 自己没有新增迁移
```

改动既有测试（**契约收紧导致的必要更新，逐条说明**）：

- `test_bc5a_chapter_practice_contract.py::test_attempt_create_response_is_concrete`
  原先发送「整章题目 + 概念 1.1」——那是一份**自相矛盾**的 payload（1.2 和 2.1 的题
  被标成 1.1 的概念），BC5A 把它钉成了可接受，S9 起是 422。该测试的**本意**
  （响应形状具体）不变，改为发送真正属于概念 1.1 的题目集；
  并新增一条「不带概念时整章仍然可以提交」覆盖旧形状。
- `cs408-s8-cross-workspace.test.tsx` 锁定态测试：见 §8。

### 前端

```text
frontend/src/features/membership/components/membership-page.test.tsx   8 tests
    当前档位 / 政策版本 / 两个会员事实并列 · 无上限渲染成「不限」不是 0
    权益判决 · 能力 id 与中文标签同时展示
    不创建订单（never called）· 预览后需显式确认才激活
    后端拒绝原因原样上屏 · 已消费码用后端 message 报告
frontend/src/features/exam/api/concept-identity.test.ts                2 tests
    读写两侧的规范命名（编译期）+ 合成节点码的判据
cs408-practice-workspace.test.tsx（新增 3 条）
    叶子进入时读用 concept_code、写用 knowledge_point_id，且题目集与列表一致
    直接入口两个都不发、页面不提「知识点」
    422 时给出可执行的说明（返回知识脉络），不是「请稍后重试」
cs408-knowledge-workspace.test.tsx（新增 3 条）
    section 行渲染 concept 链接（code + chapter，都不含标题）
    合成码不渲染链接，但章节链接仍在
    章节链接不带 concept（直接入口声明 NULL）
```

### 结果

见文末 §15「最终验证数字」。

---

## 12. 迁移与验收（PART K / L）

### 12.1 迁移（PART L）

**S9 没有 schema 变更，因此没有新增迁移**（有测试断言
`migrations/versions/` 的最后一条仍是 `20260919_0010`）。验证：

```text
全新临时库  alembic upgrade head  →  alembic_version = 20260919_0010
             practice_attempts 含 response_time_source / attempt_index
             无 hint_count 列 · PRAGMA integrity_check = ok
             （0.9 秒，10 个 revision 全部跑通）
head 数      1（`alembic heads` 输出单行，避免 `upgrade head` 有歧义）
```

**迁移演练在副本上做**（生产形状 = legacy `backend/app.db` 内容 + 迁移到 0010）：

```text
cp backend/app.db .s9tmp/prod_copy.db
alembic upgrade head  →  0010
PRAGMA integrity_check →  ok
内容保全              →  exam_question_bank 9333 行（零丢失）· users 0 · learning_events 0
真实 backend/app.db   →  **从未被打开写入**（只读审计）
```

### 12.2 验收（PART K）

新增 `scripts/verify_s9_product_flows.py`：对**运行中的服务**（绑定迁移后的副本，
**不是** localhost 之外的线上）跑真实 HTTP 流程。fixture 只有两样东西直接写库 ——
一个学习者账号和一个兑换码 —— 两者在生产里只能经真实邮箱与真实运营获得，
演练拿不到；**被测流程全部走 HTTP**。

```text
=== S9 product-flow acceptance ===   46 passed, 0 failed

概念身份     叶子 3.6 题目列表 200（50 题）
             非规范 id 4.50 → 422
             规范撞位叶子 4.2 → 200 且 total = 0（撞位行没有被伪造成链接）
             非法概念 → 422 · 跨模块概念 → 422
             attempt 建立 → 提交 → 结果回放 → 直接入口 NULL
学习记录     summary 计数与刚写入的练习一致（51 events / 4 graded）
             未自动判分的题**不**被计为答错（ungraded = attempts - graded）
             记录页出现本次 attempt 的 50 条记录
             每条记录的 context 都带 exam_module_id = computer_network
             且 knowledge_point_id = 3.6
学生孪生     capabilities 的 user_visible 恰好 = ["student_twin"]
             student-twin 预览 200
会员         锁定 → 各端点 200 → 兑换必需套餐 → **锁开** → 学习计划 200
             同一码不可重兑 · 未知码带真实原因
跨用户隔离   他人的 attempt 404 · 档位/权益各自独立 · 码不可被他人重用
科学状态     匿名 401 · 普通用户 403 · 管理员 200
             采集就绪度已报告 · 未采集字段如实陈述 · 无学习者身份泄漏
```

---

## 13. 生产部署（PART N）

部署流水线的顺序本身即任务书要求的顺序，已在 `.github/workflows/deploy.yml` 中：

```text
stop writers → backup → integrity_check ok → alembic upgrade head
             → post-migration integrity_check → schema preflight
             → restart backend → 前端 → runtime → public HTTPS 验证
```

迁移**严格早于**新后端启动，失败则**不启动**应用并提示从已验证的备份恢复。

见 §14（部署结果）。

---

## 14. 部署结果与线上验收

### 14.1 部署

```text
commit                 04947bca   ACCEL_PRODUCT_S9：概念身份传播 + 会员产品面 + 数据飞轮加固
workflow run           35486662195  status=completed  conclusion=success
backup                 app.db.before-catalog-reform.20260920_113014.db   (39M)
pre-migration check    [deploy] Persistent database integrity_check: ok
migration              [deploy] Migration proceeds under backup: …20260920_113014.db
post-migration check   [deploy] Post-migration integrity_check: ok
schema preflight       [schema-check] OK: AT_HEAD revision=20260919_0010
PRODUCTION REVISION    20260919_0010   （AT_HEAD；本轮无新迁移，符合预期）
backend                [deploy] backend health ok
runtime                [deploy] zhixue-runtime health ok
https                  [deploy] HTTPS health ok · HTTP redirect verified: 308 -> https://…
```

顺序与任务书 PART N 要求完全一致：**backup → migration → schema preflight →
backend/runtime/frontend → 线上验证**，且迁移严格早于新后端启动。

### 14.2 线上验收（公网探针，`https://101.32.190.42`）

| 探针 | 结果 | 说明 |
|---|---|---|
| `GET /api/health` | 200 `{"status":"ok"}` | |
| `GET /api/exam/prep/subjects/cs_408/content-status` | 200 | 考试域回归正常 |
| `GET /api/exam/prep/catalog` | 200 `catalog_version=v2` | |
| `GET /api/science/status` | **401** | 管理员门生效 |
| `GET /api/subscription` | **401** | 会员面按登录态拒绝匿名 |
| `GET /api/usage/summary` | **401** | 同上 |
| `GET /api/membership/entitlements` | **401** | 同上 |
| **`GET /api/subscription/plans`** | **200 + 新契约** | 见下 |
| `http://…/` | 308 → `https://…/` | 强制 HTTPS |
| `assets/index-BSuSrbDu.js` / `index-BnPkasm3.css` | 200 | **与本地构建产物哈希逐字节相同** |
| `assets/membership-DMMJAbTn.js` / `membership-C8-ncojl.css` | 200 | 新会员页分块已在线上 |

`/api/subscription/plans` 是**公开**端点，也是本轮新增响应模型的端点之一。
线上返回体逐字段等于声明的模型（`policy_version` + 三个档位的
`label` / `daily_budget` / `weekly_budget` / `capabilities`，且 Advanced 的
`daily_budget` 为 `null`）—— 这是「新后端代码确实在线上跑、且按新契约应答」的直接证据，
不需要登录态，也不写任何数据。

**前端 = 同一份产物**：线上 `index.html` 引用的两个 bundle 哈希与本地
`npm run build` 的输出**完全一致**。也就是说线上服务的前端，就是本地通过
typecheck / lint / 111 单测 / 构建的那一份，不是「另一个版本」。

### 14.3 生产机上的既有 canary

触发了仓库自带的 `StudentTwin Production Canary`（`workflow_dispatch` 手动专用、
不重新部署、幂等、不接受任意输入），它在**生产机**上用生产库与回环 runtime 执行：

```text
run 35486819956   conclusion=success
[canary] running verify_student_twin_production_canary.py
NO_ELIGIBLE_FULL_LIVE_EVENT      （脚本设计的「暂无可验证事件」出口，exit 0）
```

即：canary 通道、生产库、生产 runtime 都通；生产上确实**还没有**一条符合条件的
FULL / LIVE 事实可供回放 —— 与 §3.2「事实侧本来就没有历史」是同一个事实。

### 14.4 带登录态的走查：口径必须说清楚

带登录态的完整产品走查（§12.2 的 **46 / 46**）是在**生产形状的副本**上做的 ——
副本 = 真实 `backend/app.db` 的内容 + 迁移到 0010，与线上同一 revision、同一份题库。

**没有**在生产上注册一次性账号跑这一遍，原因是这会**写一条真实用户行**并向一个真实
邮箱**发一封真实邮件**（生产已配置 SMTP 且要求邮箱验证码注册）。用一个真实用户的账号
更不可以。这与 S8 的处理一致，也是本项目一贯口径。

线上可独立证实的三件事合起来覆盖了这次走查要证明的核心：
① 后端是按新契约应答的（`/api/subscription/plans`）；
② 前端是与本地测试过的**同一份**产物（bundle 哈希）；
③ 新面的授权边界正确（三个 per-user 端点 401、`/science/status` 401）。

**仍缺的一项**（列入 §16 blockers）：在生产上以一个真实登录态走完
「知识叶子 → 练习 → 提交 → 记录 → 会员锁定 → 兑换 → 解锁」。
需要用户提供账号，或明确批准创建一个一次性账号（会发一封真实邮件）。

---

## 15. 最终验证数字

```text
后端全量测试（backend/，项目 venv，-p no:randomly）
    1558 passed / 2 skipped / 0 failed      814.64s
    基线为 S8 的 1516 passed / 2 skipped；净增 42 项（S9 新增 24 + 18）

前端（frontend/）
    npm run typecheck   PASS
    npm run lint        PASS
    npm run test:run    27 files / 111 tests passed   （S8 为 25 files / 94 tests）
    npm run build       PASS（index-BSuSrbDu.js / index-BnPkasm3.css）

契约
    frontend/src/types/api.ts 重新生成；与 HEAD 的差异 = 本轮新增的参数、模型与
    一处说明性 docstring，**无既有内容的意外漂移**
    routeTree.gen.ts 仅新增 /membership（+21 行 / -0 行）

迁移
    全新库 alembic upgrade head → 20260919_0010 · integrity_check ok · 无 hint 列
    alembic heads → 唯一 head
    副本演练：题库 9333 行零丢失 · users 0 · learning_events 0
    backend/app.db **只读**，未被打开写入

验收
    scripts/verify_s9_product_flows.py   46 passed / 0 failed
```

---

## 16. BLOCKERS

1. **生产上的带登录态完整走查未做**（§14.4）。需要一个真实账号或用户明确批准创建
   一次性账号（会发真实邮件、写真实用户行）。其余线上证据（新契约应答、bundle 逐字节
   一致、授权边界、生产机 canary 通道）已齐备。
2. **SSOT 内部仍有 stale CURRENT 段落**：§37.1 / §68.1 的 `DIVERGED`（AHEAD 15 /
   BEHIND 12 / merge base `81277a15`）已不再成立，实测 `origin/main...HEAD = 0 0`。
   CLAUDE.md 已按授权更正，但**SSOT 未被回写** —— 按项目规则，SSOT 内部的 stale
   段落属「报告给用户并等待决定」，不属 §74 允许更新的五类。**请决定是否在下次正式
   SSOT 更新时一并处理。**
3. **`DATA_READINESS_GATE` 仍是 FAIL**，且本轮**没有**实质推进。本轮把
   concept-level 交互从 0 变成 3，但那 3 条是**验收流程**在副本上产生的，
   不是真实学习者数据；真实门槛（users_with_eligible_interactions ≥ 100 /
   total_eligible_interactions ≥ 2000）一条都没接近。不得把它读成进展。
4. **`computer_network` 仍有 300 题没有概念身份**（255 题停在 chapter、45 题停在 module）。
   本轮**证明**了其中 0 题可以从现有内容唯一重映射 —— 这 300 题需要一次**内容决策**
   （重写来源编号或补充内容），不是工程可以解决的。规模已精确到行（§4）。
5. **两套会员体系互不联动**（§7.2）。会员页提供的是真正能解锁的那条路径，
   但「统一档位」与「按方向备考方案」目前各走各的。统一是 FROZEN TARGET（SSOT §4/§5/§41），
   本轮如实呈现了两者，**没有**做统一迁移 —— 那是独立的一步。
6. **`response_time_ms` 仍无生产者**，`hint_count` 仍 `NOT_AVAILABLE`（§5/§6）。
   两者都是**有意的缺席**，并已在契约、审计文档、`/science/status` 与数据集契约中
   如实标注为「未采集 / 不适用」，而不是 0。
7. **`tutor_policy` 仍无回合状态**：running tutor 不选择任何教学动作，
   记录一个没被选择过的动作就是伪造。本轮未改动。
8. **本轮产生的 scratch 目录仍未清理**（`.s9tmp/` 为本轮新增，另有历史遗留的
   `.bc7tmp/`、`.bc8tmp/`、`.bc8r1tmp/`、`.f1c5qa/`、`.f1c6tmp/`、`.s8tmp/`、
   `frontend/.f1c5qa/`、`frontend/.f1c6tmp/`、`test-results/`、`backend/file`）。
   它们**全部未提交**（本次 38 个文件全部按显式路径 stage，已核验不含 `.db`/`.env`/scratch）。
   本机权限层会拒绝 `rm -rf`，因此无法在会话内清理 —— 与前几轮相同。
9. **`.s9tmp/` 内的证据文件**（`cn_rekey_report.json`、`concept_coverage_s9.json`、
   验收副本与日志）是临时的；可复现的产物是
   `scripts/audit_cn_content_rekey.py`、`scripts/audit_concept_coverage.py`、
   `scripts/verify_s9_product_flows.py` 三个脚本，报告里的数字都由它们产生。
