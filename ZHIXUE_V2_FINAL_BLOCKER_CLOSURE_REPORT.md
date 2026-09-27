# ZHIXUE_V2_FINAL_BLOCKER_CLOSURE_REPORT

**轮次**：V2 Final Blocker Closure —— 只关闭 `MATERIAL_QA_CITATION` 与 `COURSE_QA_TWO_TURN_HISTORY`。
**日期**：2026-09-21 ｜ **未 commit / 未 push / 未 deploy** ｜ `HEAD = 8b4d0b6e`（保留）。
**范围纪律**：未重设计任何页面，未顺手修 P2。

---

## A. MATERIAL → QA REAL E2E

**环境**：canonical isolated harness + TEMP DB（`zhixue-e2e-*`），`backend/app.db` 全程未触碰。
**不 stub**：upload / parser / persistence / indexing / retrieval / citation construction 全部真实后端。
唯一不是真实产品的是**生成器**（见下）。

### 逐层结论（按你给的定位表）

| 层 | 结论 | 证据 |
|---|---|---|
| `UPLOAD` | **PASS** | `UPLOAD_STATUS=BOTH_ACCEPTED (HTTP 200,200)`；`UPLOAD_MULTIPART=YES`（`multipart/form-data; boundary=…`） |
| `PERSISTENCE` | **PASS** | 两份资料出现在课程资料列表；重启 harness 后仍在 |
| `PARSE` | **PASS** | `PARSE_STATUS=BOTH_PARSED`（等待真实解析完成，不是只看 upload 200） |
| `INDEX` | **PASS** | `material_chunks` 有切片，`material_chunks_fts` 有行（直接查库核对） |
| `RETRIEVAL` | **PASS（本轮修复层）** | `RETRIEVAL_SOURCE=RETRIEVED acceptance-fixture-alpha.md` —— **只**检索到 ALPHA |
| `QA EVIDENCE` | **PASS** | `POST /chat` 的 `references` 首位为 alpha，`score 28.1`，`snippet` 含唯一事实；控制组 beta `14.1` 且**未被引用** |
| `CITATION BUILDER` | **PASS** | `引用资料（1）` → `acceptance-fixture-alpha.md` + 该资料原文摘录 |
| `FRONTEND RENDER` | **PASS** | 截图 `material-qa-citation.png`；`RAW_INTERNAL_ID_VISIBLE=NO` |
| **`GENERATOR`** | **BLOCKED** | `answer = "fake response"`（harness 的 FakeProvider 是确定性的常量） |

### 修复的是什么（这是本轮唯一的真实缺陷）

**`backend/rag.py` → `tokenize_query`。** 中文问句检索**从来没有工作过**：

- FTS5 默认 `unicode61` 分词器**不给中文分词的边界** —— 它把一整段连续汉字当成**一个** term。
  实测：`MATCH '线性表'` → **0 行**，`MATCH '顺序表'` → **0 行**。FTS 这一路对中文恒为 0。
- 子串兜底要求「问句里的某个 token 逐字出现在正文里」，而问句被 `[一-鿿]{2,8}` 切成
  8 字长块（如 `顺序表和链表的区别`），正文里当然没有这一整块 → `hit_count = 0` → 无结果。

两条路同时失败，于是**任何自然中文问句都检索不到已经解析、已经建好索引的同门课资料**。

修法：`tokenize_query` 额外产出 **2–4 字滑动 n-gram**（`顺序表` → 顺序 / 序表 / 顺序表）。
长词仍排在前面，FTS 有精确 token 时优先；上限从 12 提到 64，否则 n-gram 会全被截掉。
**未改动索引、未改 schema、未重新索引** —— 只修了查询侧。

修复后实测（同一份资料、同一句问句）：
- `RETRIEVAL_SOURCE=RETRIEVED acceptance-fixture-alpha.md`（修复前：0 命中）
- 对照资料 `acceptance-fixture-beta.md` **不再被引用**（`CONTROL_MATERIAL_CITED=NO`）

### 唯一未通过的一项：`answer contains the unique fact`

harness 跑的是 `FakeProvider`，`complete()` 恒返回 `content="fake response"`，**不读 prompt、不读检索上下文**。
因此「答案包含唯一事实」这一条**在隔离验收环境里无法成立**，我没有把它写成 PASS。
真正需要它成立时，需要一个真实 provider —— 那属于付费调用，不在本轮授权内。

**结论：`MATERIAL_QA_CITATION = FAIL`（严格按你给的 PASS 条件）**，
但失败的是**生成器层**，不是 citation 链。citation 链的 5 项标准中 4 项 PASS：
`retrieval evidence references uploaded material` ✓、`learner-facing citation references uploaded material` ✓、
`no fabricated source` ✓、`no raw internal id displayed` ✓；未通过的是 `answer contains the unique fact`。

### 过程中被我自己抓出来的两个「假证据」

1. 第一版证据把**答案与引用块一起扫描**，于是报出 `ANSWER_REPEATS_UNIQUE_FACT=YES` ——
   事实确实出现了，但它出现在**引用摘录**里，不是答案里。已把答案文本与引用块分开判定。
2. 第一版对照文件 `beta.md` **自己写了「本文件不包含红杉算法、冻结窗口……」** ——
   它因为提到了那些词而被**正确地**检索到，对照因此失效。去掉元叙述后重新验证，对照才成立。
   （顺带查明：beta 当时命中的 token 只有 `上传 / 资料 / 回答` 三个，来自**问句尾部的指令语**与对照文件的元叙述。）

---

## B. COURSE QA TWO-TURN CHAT

### 先做的 forensic（不猜）

| 问题 | 事实 |
|---|---|
| backend 是否有 conversation / session / history | **有，且完整。** `ChatSession` / `ChatMessage` 表；`GET /chat/history?course=…` → 200（sessions）；`GET /chat/sessions/{id}` → 200（messages，含 assistant 消息自身的 `references`） |
| frontend 是否只保存最后一问 | **不是。** 它保存全部 turns，并把 `session_id` 传回服务端 —— 但**从不回读**（`course.ts` / `course-qa-chat.tsx` 里没有任何 `chat/history` 或 `chat/sessions` 调用） |
| 是否影响单次请求还是全会话 | `if (deep)` 在**发送时**求值 → **只作用于当前 request**，不粘滞 |

**结论**：后端一直有持久 conversation contract，是**前端没有消费它**。所以本轮实现回读，而不是实现 page-session 兜底。

### 本轮改动

- `api/course.ts`：`fetchCourseQaHistory(courseId)` —— `GET /chat/history?course=<id>` 取本课程最近会话 →
  `GET /chat/sessions/{id}` 取消息与引用。按 course 在**服务端**过滤，不会把别的课程的对话带进这一页。
- `course-qa-chat.tsx`：
  - 挂载时**回读**并恢复 transcript（含每轮引用）；
  - 每条回答带**是否使用深度思考**的真实标记（`· 深度思考`），**仅**对本次页面产生的回答标注 ——
    服务端不记录该消息由哪个 capability 生成，恢复的回答**不标**，不猜；
  - **修正列表语义**：assistant 轮此前渲染为 `<ol>` 里的 `<div>`（非法子元素、无 listitem 语义），
    改为 `<li>`。这是本轮由「按顶层 `<li>` 计数」暴露出来的真实缺陷。
  - 不显示模型名 / provider / request_id。

### 证据

```
REQUESTED_URL=http://127.0.0.1:5173/course/%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84/ask
FINAL_URL=http://127.0.0.1:5173/course/%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84/ask
EXPECTED_LANDMARK=课程问答记录
RESTORED_TURNS_AT_MOUNT=14        ← 服务端历史被回读（此前为 0）
MESSAGE_COUNT_AFTER_TURN_1=2      ← 学习者 + 回答
MESSAGE_COUNT_AFTER_TURN_2=4      ← 第一轮完整保留
TURN_1_STILL_VISIBLE=YES
TURN_1_CITATION_STILL_VISIBLE=YES (acceptance-fixture-alpha.md)
TURN_2_CITATION_PRESENT=YES (9 citation blocks)
DEEP_TOGGLE_SCOPE=aria-pressed false->true; 切换前已回答被回溯标记数 = 0
```

刷新后另测：`items 12 → 12`，第一问与回答、3 个引用块（含 alpha 文件名与唯一事实摘录）全部恢复；无 raw internal id。

---

## C. E2E EVIDENCE

两个脚本已更新为输出结构化证据（上文字段均由其直接产出）：
- `frontend/scripts/material-e2e.mjs` —— `REQUESTED_URL` / `FINAL_URL` / `EXPECTED_LANDMARK` /
  `UPLOAD_STATUS` / `PARSE_STATUS` / `MATERIAL_VISIBLE` / `RETRIEVAL_SOURCE` / `QA_ANSWER` /
  `CITATION_LABEL` / `CONTROL_MATERIAL_CITED` / `RAW_INTERNAL_ID_VISIBLE` / `ANSWER_REPEATS_UNIQUE_FACT` /
  `CITATION_EXCERPT_CONTAINS_FACT` / `UPLOAD_MULTIPART`
- `frontend/scripts/qa-two-turn.mjs` —— 上表 B 的全部字段，另加 `RESTORED_TURNS_AT_MOUNT`
- 用例资料：`frontend/.iaaccept/acceptance-fixture-alpha.md`（含 `ZX_ACCEPTANCE_FACT_921`）与
  `acceptance-fixture-beta.md`（**纯内容对照**）

**没有任何一项 PASS 仅凭截图。** 截图仅作为补充（`material-qa-citation.png`、`course-qa-two-turn.png`）。

---

## D. REGRESSION

```
backend targeted (pytest tests/test_p3a_strong_reasoning.py)   9 passed
backend full suite        1801 passed, 2 skipped, 0 failed   (12:16)
Alembic heads             20260921_0014 —— 恰好 1 个 head
frontend typecheck        PASS
frontend lint             PASS (0 error / 0 warning)
frontend vitest (bounded) 318 passed / 64 files
frontend build            PASS
check:api-origin          PASS (124 artifacts, no loopback)

backend/app.db  fingerprint  BEFORE md5=5ed902ecab1d468792bbc87a91caa4eb size=64917504 mtime=Sep 20 12:03
                             AFTER  md5=5ed902ecab1d468792bbc87a91caa4eb size=64917504 mtime=Sep 20 12:03
                             → UNCHANGED（字节一致）
```

本轮后端改动：`backend/rag.py`（查询分词）、`backend/tests/test_p3a_strong_reasoning.py`（新增回归测试）。
**无 schema 变更**，故 Alembic 无新 revision。

新增回归测试 `test_a_natural_chinese_question_retrieves_the_material_that_answers_it`：
断言**自然语言中文问句**能检索到应回答它的资料、该资料**排第一**、同门课的无关对照资料**不被引用**，
并直接断言 n-gram 存在（`红杉` / `冻结` / `窗口`）。

---

## E. 输出

```
MATERIAL_UPLOAD            = PASS
MATERIAL_PARSE             = PASS
MATERIAL_INDEX             = PASS
MATERIAL_RETRIEVAL         = PASS
MATERIAL_QA_CITATION       = FAIL   (仅"answer contains the unique fact"一项不成立；失败层 = GENERATOR，
                                     原因是 harness 的 FakeProvider 恒返回常量。citation 链本身 4/5 PASS。)

COURSE_QA_TURN_1           = 2 条（学习者 + 回答），引用指向 acceptance-fixture-alpha.md
COURSE_QA_TURN_2           = 4 条（累计），第二轮引用同样渲染
TURN_1_PRESERVED_AFTER_TURN_2 = YES
TURN_1_CITATION_PRESERVED     = YES (acceptance-fixture-alpha.md)
COURSE_QA_TWO_TURN_HISTORY = PASS
PERSISTENT_COURSE_QA_HISTORY = YES   (挂载回读服务端会话；刷新后 transcript 与引用均恢复)

P0_REMAINING = 无
P1_REMAINING =
- GENERATOR：隔离 harness 只有 FakeProvider，无法验证"答案引用资料并复述其中事实"。
  需要真实 provider 才能关闭 MATERIAL_QA_CITATION 的最后一项；非 UI、非检索问题。
- 检索精度（P2 级，未修）：中文 n-gram 匹配对通用词（如"资料""回答"）区分度低，
  若对照资料恰好含这些词会被一并召回。修复后已用真实对照验证不触发；如后续引入同课大量资料，需重新评估阈值。

READY_FOR_USER_VISUAL_REVIEW = YES
```

**两点必须点名**：`MATERIAL_QA_CITATION` 是 **FAIL**，不是 PASS —— 我没有拿到「答案包含唯一事实」。
`COURSE_QA_TWO_TURN_HISTORY` 与 `PERSISTENT_COURSE_QA_HISTORY` 均为 **PASS / YES**，
且是**真的**持久（服务端存、页面回读），不是 page-session 兜底。
