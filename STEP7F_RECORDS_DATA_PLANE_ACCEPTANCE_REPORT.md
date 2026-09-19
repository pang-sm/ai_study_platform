# STEP7F_RECORDS_DATA_PLANE_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7F 验收报告
> 范围：Records / Data Plane Consolidation
> 生成：2026-09-16 · 本轮为 IMPLEMENTATION（有代码变更，未 commit / 未 push）

---

## 1. EXECUTIVE VERDICT

```text
STEP7F = FROZEN
STEP7G_READY = YES

STEP7F_SCHEMA_CHANGE = INDEX_ONLY（无新表、无新列）
MIGRATION_HEAD = 20260915_0005
NEW_TABLES = NONE

EVENT_SCHEMA_VERSION = 2（未 bump）
LEARNING_RECORDS_READ_MODEL = PASS
ARBITRARY_CLIENT_EVENT_WRITE = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
COURSE_PRACTICE_IDENTITY_CHANGED = NO
COURSE_PRACTICE_DUPLICATE_EVENT = NO

FULL_BACKEND_TESTS = PASS（581 passed / 0 failed；baseline 516）
```

**核心结论：**

1. **没有新增任何记录表。** Learning Records 是 `learning_events` 的用户可读投影，不是第二张表。

2. **冻结事件 taxonomy。** 7 个 ACTIVE（有真实 producer）+ 4 个 DEFERRED（仅有名字，无 source → 不可发射）。
   `NO SOURCE → NO EVENT` 是可执行的约束，不是口号。

3. **一个事实一个 owner。** `EVENT_OWNERSHIP_MATRIX` 固化 11 类事实的唯一 producer。
   `course_practice` 的身份与名字**未改**，也**没有**再产生第二条等价 `question_answered`。

4. **补上四个缺失的 producer**：`ai_called`、`knowledge_status_changed`、`material_asked`、`material_opened`。

5. **零客户端写入面**：records API 只有 4 个 GET，没有 POST/PUT/PATCH/DELETE。

---

## 2. GIT BASELINE

```text
HEAD = ebad5282（merge: reconcile local clean-slate frontend/governance with origin backend intelligence）
本轮未执行任何 git 写操作（NO commit / push / reset / clean / checkout / rebase / merge / pull）
```

变更分类：

```text
PREEXISTING_DIRTY（STEP7C-P 遗留）
  backend/ai/{benchmark,cost,gateway,orchestrator,pool,pricing,router,secrets,providers/*}.py
  backend/usage/service.py、scripts/**、若干 tests、SSOT、STEP7CP 报告

STEP7D / STEP7E（前两轮，未 commit）
  backend/learning/practice/**、backend/learning/wrong_answers/**、
  backend/routers/{practice,wrong_answers}.py、migrations/0003–0004、对应 tests

THIS_BATCH（STEP7F）
  ?? backend/learning/records/{__init__,taxonomy,envelope,producers,service,backfill}.py
  ?? backend/routers/learning_records.py
  ?? migrations/versions/20260915_0005_learning_events_record_indexes.py
  ?? backend/tests/test_learning_records.py
  ?? backend/tests/test_learning_records_api.py
   M backend/data_plane/models.py             （+2 index 声明，与 0005 对齐）
   M backend/ai/orchestrator.py               （+ai_called producer，单一边界包装）
   M backend/learning/practice/service.py     （practice event 从 router 移到 service）
   M backend/routers/practice.py              （-1，移除重复 emit）
   M backend/main.py                          （知识/材料 producer hook + router 注册）
   M backend/tests/test_practice_migration.py （0005 覆盖）
```

模型池 / provider / pricing / benchmark **未改动**。无 frontend 改动。

---

## 3. CURRENT RECORD SOURCE AUDIT

```text
真实 backend/app.db（只读，2026-09-16）
users = 0
learning_records            = 0 行
knowledge_progress_events   = 0 行
study_materials             = 1 行
material_chunks / chat_sessions / chat_messages / course_progress /
user_knowledge_progress / programming_exercise_progress /
programming_exercise_submissions / learning_tasks / user_learning_paths = 0 行
learning_events             = 表不存在于未迁移的 app.db（STEP7A 由 Alembic/create_all 建立）
```

```text
REAL_RECORD_BACKFILL_ROWS = 0
REAL_HISTORICAL_BACKFILL_VALIDATED = NO（不声称；算法以 fixtures 验证）
```

**不要因为表名像 event 就判定是 event。** 逐个审计结论：

| table | 真实语义 | namespace | user scope | writer | reader | 是否 event | 处置 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `learning_records` | 学习记录（`record_type` = practice / review / …），含 **整段 question/answer 文本** | 不明确（`subject`） | `user_id` | 20353（practice）、8258（review，素材问答）、22838 | home/review/report 多路 | 否，是 domain record | practice → **INELIGIBLE**；review+素材 → PARTIAL 映射 |
| `knowledge_progress_events` | **掌握度 delta 事件**（event_type=原因，delta=分值），非状态迁移 | course_learning | username | `apply_knowledge_progress_event` 及 2 处直接构造 | 知识图谱/统计 | 否 | PARTIAL（delta 重放） |
| `learning_events` | **canonical event stream**（STEP7A） | 有 | `user_id` | data_plane emitter / practice / records producers | worker、records | **是** | 唯一事件流 |
| `practice_sessions` / `practice_attempts` | 练习 operational state + immutable facts | 有 | `user_id` | Practice Core | practice/records | 否 | 事实源 |
| `wrong_answer_states` | 错题 operational state | 有 | `user_id` | wrong-answer projector | wrong-answers API | 否 | 事实源 |
| `ai_requests` / `ai_cost_records` | AI 请求终态 + 成本 | 无（按 capability） | `user_id` | usage service | orchestrator/审计 | 否 | 事实源 |
| `study_materials` / `material_chunks` | 资料与分块 | 有 | username | materials routes | RAG/阅读 | 否 | 事实源 |
| `chat_sessions` / `chat_messages` | 会话与消息（**含全文**） | 有 | `user_id` | chat route | chat | 否 | 事实源 |
| `programming_exercise_progress` / `_submissions` | 真实判题聚合 / 首次通过 | programming | username(+user_id) | 10968 / 10898 | programming home | 否 | 事实源 |
| `course_progress` / `user_knowledge_progress` | 课程/知识点状态 | course_learning | username | 多路 | 知识图谱 | 否 | 事实源 |
| `learning_tasks` / `user_learning_paths` / `user_learning_tracks` | 计划（legacy 片段） | course_learning | username | 任务路由 | 计划页 | 否 | **不产生 plan event**（DEFERRED） |
| `user_knowledge_review_settings` | 复习间隔设置 | course_learning | username | 设置路由 | 复习 | 否 | **不是** Review Core |

---

## 4. DATA PLANE FOUR-LAYER MAP

```text
Operational State（现在是什么状态）
  subscriptions · practice_sessions · wrong_answer_states · user_knowledge_progress
  programming_exercise_progress · learning_tasks · study_materials
        ↓ 事实已 commit 后由 trusted producer 派生
Event Stream（发生了什么）
  learning_events          ← 本轮唯一 canonical stream
        ↓ 查询时投影
Derived Features（确定性计算）
  learning/records/service.summarize_records（query-time，NO table，NO cache）
        ↓ Data Producer（只消费 eligible）
Scientific State（科学状态）
  model_versions · model_inference_runs · model_predictions · StudentTwin 输出
```

四层未被揉成一张万能表；本轮**没有**为任何 feature 新建物化表。

---

## 5. LEARNING EVENT ENVELOPE

frozen target envelope → 现有 `learning_events` 列的映射（**已完整表达，故未改 schema**）：

| frozen target | 现有列 |
| --- | --- |
| event_id | `event_id`（UUIDv5） |
| user_id | `user_id`（+ `source_user_ref` 供 legacy 溯源） |
| event_type | `event_type` |
| service_namespace | `service_key`（列名为 legacy；canonical 应用层名见 `core/learning_context.py`） |
| context | `course_id` / `subject_key` / `question_id` / `knowledge_point_ref_json` |
| occurred_at | `occurred_at`（UTC epoch） |
| source | `source_type` / `source_attempt_id` / `source_item_key` / `source_item_index` |
| payload | `item_snapshot_json`（+ `item_content_hash`） |
| schema_version | `event_schema_version` |

```text
LEARNING_EVENT_ENVELOPE = COMPLETE（无缺失硬字段）
```

---

## 6. EVENT TAXONOMY

`backend/learning/records/taxonomy.py`（CONFIG，非 SQL 表）

**ACTIVE（有真实 producer）**

| event_type | category | owner | durable source | StudentTwin |
| --- | --- | --- | --- | --- |
| `course_practice` | PracticeEvent | `data_plane.emitter`（**未改**） | ai_question_attempts | **YES（唯一）** |
| `question_answered` | PracticeEvent | `learning.practice.events` | practice_attempts | NO |
| `code_submitted` | ProgrammingEvent | `learning.practice.events` | practice_attempts（真实判题） | NO |
| `ai_called` | AIEvent | `ai.orchestrator.execute` | ai_requests（终态） | NO |
| `knowledge_status_changed` | KnowledgeEvent | `learning.records.producers` | knowledge_progress_events / user_knowledge_progress | NO |
| `material_asked` | MaterialEvent | `learning.records.producers` | chat_messages / ai_requests | NO |
| `material_opened` | MaterialEvent | `learning.records.producers` | 资料打开动作（按天去重） | NO |

**DEFERRED（仅有名字，无 source → 不可发射；测试固化）**

```text
review_completed · plan_created · task_completed · wrong_answer_resolved
```

```text
EVENT_TAXONOMY = FROZEN（7 ACTIVE / 4 DEFERRED）
```

---

## 7. EVENT OWNERSHIP MATRIX

`taxonomy.ownership_matrix()` 固化「一个事实 → 一个 owner」：

| business fact | event_type | authoritative producer |
| --- | --- | --- |
| ai_question_attempts（AI 答题） | `course_practice` | `data_plane.emitter.build_course_practice_events` |
| practice_attempts（非 AI 答题谱系） | `question_answered` | `learning.practice.events.emit_for_attempt` |
| practice_attempts（真实判题提交） | `code_submitted` | `learning.practice.events.emit_for_attempt` |
| ai_requests（终态） | `ai_called` | `ai.orchestrator.AIOrchestrator.execute` |
| knowledge 状态迁移 | `knowledge_status_changed` | `learning.records.producers.emit_knowledge_status_changed` |
| 素材提问 | `material_asked` | `learning.records.producers.emit_material_asked` |
| 素材打开 | `material_opened` | `learning.records.producers.emit_material_opened` |

```text
PracticeAttempt 与 WrongAnswerState 与 legacy learning_records
不会对同一次答题写三次事件：
  · PracticeAttempt → 一条 practice 事件
  · WrongAnswerState → 0 条（recompute 派生，写事件即重复）
  · legacy learning_records(practice) → 判为 INELIGIBLE，不映射
```

---

## 8. EVENT IDENTITY

```text
event_id = data_plane.identity.event_id(source_type, source_attempt_id, source_item_key)
         = UUIDv5(EVENT_UUID_NAMESPACE, "source_type|source_attempt_id|item_key")
```

- **复用**冻结的 `backend/data_plane/identity.py`，**未造第二套 UUID namespace**。
- 不依赖 `occurred_at`，不使用随机 UUID → backfill 每次运行结果相同。
- 「一次事实、多条子项」用 `source_item_key` 区分（practice 用 `qid:idx`、AI 用 capability、
  素材问用 `material:message`、素材打开用 UTC 日期）。

---

## 9. PRACTICE PRODUCER

审计发现一处**真实缺陷并修复**：STEP7D 把 `emit_for_attempt` 放在 **HTTP router** 里，
因此任何非 HTTP 写入路径（legacy adapters、backfill）都不会产生事件。

修复：把 emit 移到 `learning/practice/service.record_attempt`（唯一写入路径），
router 中的重复调用删除。事件身份未变。

- `question_answered`：payload 含 question/source ref、correct 三态、score/max、
  `source_item_key = qid:idx`；**不含**完整学生答案或整道题内容。
- `code_submitted`：来自真实判题；`code_passed` / `code_failed` 是**派生分类**，不额外写事件。
- `course_learning` **不发** practice 事件（既有 emitter 独占）。

```text
PRACTICE_EVENT_PRODUCER = PASS
```

---

## 10. AI PRODUCER

在 `AIOrchestrator.execute` 的**单一公共边界**包装（原 `execute` 改名为 `_execute`），
六条 return 路径一次覆盖：

```text
settled              → succeeded
released             → failed
reconciliation_pending → pending
denied               → denied
already_exists       → 不产生事件（没有发生新的调用）
```

payload 最小：`ai_request_id` / `capability` / `status`（+ provider、credit_class，
失败时加**规范化** `error_category`）。**不含** prompt、response、vendor stack trace、API key。

```text
AI_EVENT_PRODUCER = PASS
FAILED_AI_REQUEST_POLICY = 统一（coarse status + normalized category；ops 细节不入 payload）
```

---

## 11. KNOWLEDGE PRODUCER

`apply_knowledge_progress_event` 现在**返回**迁移信息（old_status / new_status / kp / source），
调用方在**自己 commit 之后**发射事件——durable fact 先于事件。

已接线 callsite（3 处）：`PUT /learning/tasks/{id}`、`POST /practice/questions/{id}/attempts`、
`POST /practice/questions/{id}/feedback`。

- **只在状态真的变化时**发事件（delta 未跨阈值 → 不发）。噪声过滤是语义性的，不是采样。
- 未接线：`PUT /knowledge-points/{id}/progress`（manual_update）与
  `POST /practice/submit-result`（practice_result）——它们直接构造事件行、不经该函数；
  这两条路径由 **backfill 覆盖**，报告如实标注而非假装已接。
- 不写任何 LLM 推断的 mastery。

```text
KNOWLEDGE_EVENT_PRODUCER = PASS（3 个 callsite；2 条路径由 backfill 覆盖）
```

---

## 12. MATERIAL PRODUCER

审计：**材料没有任何打开/阅读追踪**（无 view counter、无 last_opened_at）；所有 GET 都是
零写入的被动读；唯一的真实学习动作是 `POST /chat` 上的素材问答。

- `material_opened`：接在 `GET /materials/{id}`（canonical 打开动作）。
  **去重策略 = 身份本身**：`source_item_key = UTC 日期`，同一用户同一资料同一天只产生一条事件，
  页面刷新不会变成事件。写入走 producer 自己的 session，请求事务零影响。
- `material_asked`：接在 `POST /chat` 用户消息 commit 之后，每个 material 一条；
  payload 只有引用（material_id / capability / message id），**问题文本仍留在 chat_messages**。

```text
MATERIAL_EVENT_PRODUCER = PASS
```

---

## 13. WRONG ANSWER RECORD STRATEGY

```text
WrongAnswerEvent = 本轮不产生
```

- `wrong_answer_states` 是 **operational state**，且由 **recompute** 从 practice attempts 派生；
  每次重算写事件即纯重复。
- `wrong_answer_resolved` 在 taxonomy 中标 **DEFERRED**：目前唯一可能的来源是「用户手动
  resolve」，产品尚未需要该事件。
- 状态可由 practice 事件完整重建：**WrongAnswerState 可重建性不依赖任何新事件**。

---

## 14. LEGACY LEARNING_RECORDS MIGRATION

逐字段审计后分类（**不按表名直接复制**）：

| record_kind | 分类 | 处理 |
| --- | --- | --- |
| `practice` | **INELIGIBLE** | 底层事实已被 practice spine / `course_practice` owner 拥有；映射即重复计数 |
| `review`（含素材引用） | **PARTIAL** | 映射为 `material_asked`，**使用与 live producer 相同的 identity**（`source_id=message_id`、`item_key=material:message_id`）；问题文本不复原 |
| 其他 record_type | **INELIGIBLE** | 无对应 canonical event；durable 行仍是其自身功能的真值 |

```text
LEGACY_LEARNING_RECORDS_BACKFILL = PASS（1 类可映射 / 2 类显式不可映射）
```

---

## 15. KNOWLEDGE_PROGRESS_EVENTS MIGRATION

该表记录的是 **掌握度 delta + 原因**，不是状态迁移。可映射性来自一个事实：
产品自己的 `apply_knowledge_progress_event` 用**确定性规则**从分数推导状态
（`clamp(0..100)`；0→not_started、<40→learning、<80→reviewing、≥80→mastered）。

因此 backfill **按时间序重放** delta，逐条算出 old/new status：

- 事件仅在状态**真的变化**时产生（分数微调不产生）。
- payload 带 `derived_from="delta_replay_v1"`，派生方式可审计。
- 分类 **PARTIAL**：绕开该函数直接改状态的路径（`_update_course_learning_progress`、
  `PATCH /knowledge-map/progress`、exam study-plan 路径、系统重算）在此表中**不可见**。

```text
KNOWLEDGE_PROGRESS_BACKFILL = PASS（delta 重放；缺失面已显式登记）
```

---

## 16. BACKFILL / RECONCILIATION

`learning/records/backfill.py`，三个来源，全部 deterministic identity：

```text
learning_records          → material_asked（PARTIAL）
knowledge_progress_events → knowledge_status_changed（PARTIAL，delta 重放）
ai_requests               → ai_called（终止态；与 live 同 identity）
```

- `dry_run=True` 只统计不落库（实测写入 0）。
- 用户不存在 → 跳过并计数，不猜测归属。
- 不自动做破坏性修复。

---

## 17. LIVE-BACKFILL EQUIVALENCE

实测三例：

| 事实 | live | backfill | 结果 |
| --- | --- | --- | --- |
| AI 请求 `bf-req-1` | `ai_called` | `ai_called` | 同一 event_id → 第二次 `emitted=0` |
| 素材提问 message 4242 | `material_asked` | `material_asked` | 同一 event_id → collapse |
| practice attempt | `question_answered` | 从 practice_attempts 重建 | 同一 event_id（STEP7D 已固化） |

```text
LIVE_BACKFILL_EQUIVALENCE = PASS
```

---

## 18. RECORDS READ MODEL

`learning/records/service.py` —— 是 `learning_events` 的投影，**不是第二张表**。

```text
list_records(user_id, start_at?, end_at?, service_namespace?, category?,
             event_type?, limit, cursor) → {records, next_cursor, has_more}
get_record(user_id, event_id)
summarize_records(user_id, start_at?, end_at?, service_namespace?)
```

- 全程 **user-scoped**；namespace / category / event_type / 时间窗口过滤。
- **cursor 分页**：排序 `occurred_at DESC, event_id DESC`，确定性 tie-break。
  cursor 用 `repr(float)` 精确往返 —— 修掉了一个真实缺陷：先前格式化为 6 位小数会
  舍入边界值，导致下一页重复上一页最后一行（测试捕获）。
- 时间语义统一 **UTC**：存储为 UTC epoch，输入 naive 时间按 UTC 解释，绝不按服务器本地时区。

---

## 19. RECORDS API

```text
GET /learning-records            list（filters + cursor）
GET /learning-records/summary    deterministic 统计
GET /learning-records/taxonomy   只读 taxonomy + ownership 参考
GET /learning-records/{event_id} detail + recovery capability
```

仅 4 个 GET。**没有任何写入面**（POST/PUT/PATCH/DELETE 全部非 2xx，测试固化）。
旧 records 相关 endpoint **未删除、未改写**。

---

## 20. PRIVACY

- `envelope.assert_payload_is_safe` 在 build 阶段**拒绝**含 `code` / `prompt` /
  `raw_response` / `full_answer` / `content` / `api_key` / `secret` 等键的 payload。
- read model 的 `_safe_view` 只输出：event_id、event_type、category、namespace、
  occurred_at、schema_version、context、source **引用**、小尺寸 summary。
  **不输出** `item_snapshot_json`、`idempotency_key`、`source_item_index` 等内部字段（测试固化）。
- 完整答案、代码、prompt、response、资料正文一律留在各自 domain 表。

```text
PRIVACY_PAYLOAD_POLICY = PASS
```

---

## 21. FREE-TIER DATA PERSISTENCE

三个 tier 用**同一事实**（一次错答 + 一次 AI 调用）模拟：

```text
free / standard / advanced → 均产生 {question_answered, ai_called}
test_event_persistence_is_independent_of_membership_tier（参数化 3 例）
```

付费差异只在分析 / 连续 StudentTwin / 高级报告 / 自动化，**不在数据是否保存**。

```text
FREE_TIER_EVENT_PERSISTENCE = PASS
```

---

## 22. DATA PRODUCER / STUDENTTWIN SAFETY

- worker 的目标选择与历史查询**都**过滤 `event_type == "course_practice"` →
  `question_answered` / `code_submitted` / `ai_called` / `knowledge_status_changed` /
  material 事件**结构性**被忽略（不是靠注释约定）。
- 实测：写入上述四类事件后 `worker.run_once` 的 `events_scanned == 0`。
- `taxonomy.student_twin_eligible_types() == ("course_practice",)`，测试固化。

```text
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
```

---

## 23. SCIENTIFIC STATE

```text
model_versions / model_inference_runs / model_predictions = 既有 STEP7A contract，未改
NEW_SCIENTIFIC_COMPONENTS = NONE
LEARNING_OUTCOMES_CREATED = NO（仍为 V1）
```

未接 misconception_v2 / learner_state / IRT / evidence_reliability / memory / planner。
未新增 scientific endpoint 或表。

---

## 24. RECOVERY MATRIX

```text
course_practice            FULL     （ai_question_attempts → 既有 data_plane backfill）
question_answered          FULL     （practice_attempts → practice.events）
code_submitted             FULL     （practice_attempts → practice.events）
ai_called                  FULL     （ai_requests → records.backfill）
knowledge_status_changed   PARTIAL  （knowledge_progress_events；部分写入路径不可见）
material_asked             PARTIAL  （可从 chat_messages/ai_requests 重建引用；文本不复原）
material_opened            EVENT_ONLY（无独立 durable source；事件本身即事实）
```

`material_opened` 明确标注**不具备 source backfill**，不虚假声称可恢复。

---

## 25. OBSERVABILITY

结构化计数器（`producers.COUNTERS`，沿用既有 logging 风格，未引入 Prometheus/Kafka）：

```text
events_emitted · events_deduped · events_failed · events_validation_failed
```

日志（结构化、只含 ids / namespace / type / status，**不含答案或代码**）：

```text
records.event_write_failed · records.event_build_failed · records.event_validation_failed
records.backfill_inserted=… skipped=… failed=…
practice.legacy_mirror_failed · knowledge event hook failed · material_* hook failed
```

失败语义（§44）：核心业务 fact 先 commit；event 写入失败**不回滚**业务，被计数并记日志，
且因身份 deterministic 而可由 backfill 恢复。

---

## 26. MIGRATION / DATA PRESERVATION

```text
0005 = 仅两个 index（user_id, occurred_at）/（service_key, occurred_at）
       无新表、无新列、无约束变更、无数据改动
```

| 场景 | 结果 |
| --- | --- |
| fresh 临时 SQLite | integrity=`ok`，head=`20260915_0005` |
| `backend/app.db` 临时副本 | integrity=`ok`，head=`20260915_0005`，85 表 |
| 0005 增量隔离 | 先升 0004 再升 head，表集合 diff = **∅** |
| 第二套记录设施 | `learning_records_v2` / `event_outbox` / `derived_features` / `student_state` / `timeline` / `activity_log` **均未创建** |
| 静态资产 | `exam_question_bank=9333`、`programming_exercises=1923`、`knowledge_points=32` 不变 |
| 既有新表 | `practice_sessions` / `practice_attempts` / `wrong_answer_states` 保持 |

```text
FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
REAL_APP_DB_MIGRATED = NO（按 §49 安全策略，未对真实库执行 upgrade）
STATIC_ASSET_COUNTS = 9333 / 1923 / 32
```

---

## 27. TARGETED TESTS

```text
新增 65 项，全部 PASS
```

| 文件 | 项数 | 覆盖 |
| --- | --- | --- |
| `tests/test_learning_records.py` | 53 | taxonomy（ACTIVE/DEFERRED/owner/eligibility）、envelope（字段完整性/确定性身份/8 类非法输入拒绝/namespace 限制/必填 payload/三态/隐私守卫）、producers（幂等/按天去重/引用不含文本/非迁移不发/失败吸收计数）、practice 事件（含 NULL 三态、course_learning 不发）、worker 忽略非 eligible、read model（user scope/不泄露 payload/cursor 分页/UTC 时间窗/namespace 过滤/detail/recovery）、summary、backfill（delta 重放/跨阈值/未知用户/legacy 三分类/与 live 同 identity/dry-run/幂等）、三 tier 持久化 |
| `tests/test_learning_records_api.py` | 11 | 鉴权、**无写入面**、practice 记录可见、不泄露内部字段、detail、跨用户隔离、过滤、非法过滤 400、分页稳定且 limit 有界、summary、taxonomy |
| `tests/test_practice_migration.py` | +1（共 6） | 0005 不新增表、index 就位、无第二套记录设施 |

---

## 28. FULL REGRESSION

```text
baseline = 516 passed / 0 failed
after    = 581 passed / 0 failed
PY_COMPILE = OK
REGRESSION = NONE
```

`581 = 516 + 65`

---

## 29. FINAL VERDICT

```text
STEP7E_FROZEN = YES（延续，未改动）

STEP7F_SCHEMA_CHANGE = INDEX_ONLY
MIGRATION_HEAD = 20260915_0005
NEW_TABLES = NONE

LEARNING_EVENT_ENVELOPE = COMPLETE
EVENT_SCHEMA_VERSION = 2
EVENT_TAXONOMY = FROZEN（7 ACTIVE / 4 DEFERRED）
EVENT_OWNERSHIP_MATRIX = FROZEN

PRACTICE_EVENT_PRODUCER = PASS
AI_EVENT_PRODUCER = PASS
KNOWLEDGE_EVENT_PRODUCER = PASS
MATERIAL_EVENT_PRODUCER = PASS

COURSE_PRACTICE_IDENTITY_CHANGED = NO
COURSE_PRACTICE_DUPLICATE_EVENT = NO

LEGACY_LEARNING_RECORDS_BACKFILL = PASS
KNOWLEDGE_PROGRESS_BACKFILL = PASS
BACKFILL_IDEMPOTENCY = PASS
LIVE_BACKFILL_EQUIVALENCE = PASS

LEARNING_RECORDS_READ_MODEL = PASS
LEARNING_RECORDS_API = PASS（4 GET）
ARBITRARY_CLIENT_EVENT_WRITE = NO

FREE_TIER_EVENT_PERSISTENCE = PASS
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
PRIVACY_PAYLOAD_POLICY = PASS

STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
STUDENT_TWIN_PRODUCTIZATION_STATE = SHADOW_READY（未升级为 SHADOW）
NEW_SCIENTIFIC_COMPONENTS = NONE
LEARNING_OUTCOMES_CREATED = NO

REAL_APP_DB_MIGRATED = NO
FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
STATIC_ASSET_COUNTS = 9333 / 1923 / 32

TARGETED_TESTS = PASS（65）
FULL_BACKEND_TESTS = PASS（581 passed / 0 failed）

STEP7F_COMPLETE = YES
STEP7G_READY = YES
```

`BLOCKERS = 无。残留（不阻断）：① knowledge_progress_events 有多条绕开 apply_knowledge_progress_event 直接改状态的路径，其状态迁移在本表中不可见（live producer 只接了 3 个 callsite，其余由 backfill 覆盖，已显式登记）；② material_opened 为 EVENT_ONLY，不具备 source backfill；③ 真实 app.db 仍未迁移，待部署 gate 执行 backup → hash → upgrade head → integrity。`

---

## 30. 变更文件清单

```text
[NEW] backend/learning/records/{__init__,taxonomy,envelope,producers,service,backfill}.py
[NEW] backend/routers/learning_records.py
[NEW] migrations/versions/20260915_0005_learning_events_record_indexes.py
[NEW] backend/tests/test_learning_records.py
[NEW] backend/tests/test_learning_records_api.py
[MOD] backend/data_plane/models.py              +2 index 声明
[MOD] backend/ai/orchestrator.py                +ai_called producer（单一边界）
[MOD] backend/learning/practice/service.py      practice event 移入 service（真实缺陷修复）
[MOD] backend/routers/practice.py               -1 重复 emit
[MOD] backend/main.py                           知识/材料 producer hook + router 注册
[MOD] backend/tests/test_practice_migration.py  0005 覆盖
[MOD] ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md        §73 STEP7F
```

部署时需执行 `alembic upgrade head`（真实库当前无 `alembic_version` 表，见 STEP7D 报告 §8）。
