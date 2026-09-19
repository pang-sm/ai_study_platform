# STEP7D_PRACTICE_CORE_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7D 验收报告
> 范围：Unified Practice Core（Shared Learning Core 第 6 项）
> 生成：2026-09-16 · 本轮为 IMPLEMENTATION（有代码变更，未 commit / 未 push）

---

## 1. EXECUTIVE VERDICT

```text
STEP7D = FROZEN
STEP7E_READY = YES

FULL_BACKEND_TESTS = PASS（459 passed / 0 failed；baseline 391）
MIGRATION_HEAD = 20260915_0003
NEW_TABLES = practice_sessions / practice_attempts
WRONG_ANSWER_STATES_CREATED = NO
```

统一练习主链已建立并跨三个 learning space 接线：

```text
PracticeSession → QuestionRef → PracticeAttempt → Result → (Explanation) → LearningEvent
```

**核心结论：**

1. 新增**恰好两张**物理表（additive-only migration `20260915_0003`），未创建任何 wrong-answer / review / plan / outcome 表。

2. `QuestionRef` 是**指针**而非副本：9333 题题库、1923 道编程题、材料生成的题目全部留在原位，未复制、未改写。

3. 三个 space 各接一条**真实** writer（course AI 答题 / exam 章节练习 + 真题 / programming 真实判题提交），legacy 表仍是 compatibility window 内的 domain source of truth。

4. `correct` 是**三态**（True / False / NULL）：未判分的大题、无裁决的反馈一律 `NULL`，绝不 `bool(None)`、绝不猜。

5. StudentTwin eligibility **未扩大**：Practice Core 自己拥有的事件类型是 `question_answered` / `code_submitted`，而 producer 只消费 `event_type == "course_practice"`；course 事件仍由既有 emitter 独占。

---

## 2. GIT BASELINE

```text
HEAD = ebad5282（merge: reconcile local clean-slate frontend/governance with origin backend intelligence）
本轮未执行任何 git 写操作（NO commit / push / reset / clean / checkout / rebase / merge / pull）
```

工作树变更分类：

```text
PREEXISTING_DIRTY（STEP7C-P 遗留，与本轮无关）
  backend/ai/{benchmark,cost,gateway/__init__,orchestrator,pool,pricing,router,secrets}.py
  backend/ai/providers/{ark,qwen}.py、backend/usage/service.py
  backend/tests/{test_ai_models_api,test_benchmark,test_pricing_pool_router,
                 test_provider_adapters,test_secret_loader}.py
  scripts/{configure_ai_provider_secrets,run_calibration_benchmark,verify_ai_providers}.py
  ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md、STEP7CP_*.md
  ?? backend/tests/test_reservation_policy.py、?? scripts/run_agent_probe.py

THIS_BATCH_CHANGES（STEP7D）
  ?? backend/learning/**                        （新模块）
  ?? backend/routers/practice.py                （新 API）
  ?? backend/tests/test_practice_{core,adapters,migration,api}.py
  ?? migrations/versions/20260915_0003_create_practice_core_tables.py
   M backend/main.py                            （+48 / -1，仅 router 注册 + 5 个 mirror hook）
   M ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md
   M STEP7D_PRACTICE_CORE_ACCEPTANCE_REPORT.md（本文件，新建）
```

模型池 / benchmark / provider pricing / Qwen policy / Doubao 隔离 / credits 换算**均未改动**。

---

## 3. CURRENT PRACTICE AUDIT

只读审计，逐个确认 physical table、model、user scope、question identity、attempt identity、answer/result 表示、correct/score 语义、时间戳、writer/reader callsite、row count。

```text
row counts（backend/app.db，只读，2026-09-16）
  question_attempts               0
  ai_question_attempts            0
  exam_practice_attempts          0
  exam_question_done_records      0
  past_paper_attempts             0
  code_challenge_attempts         0
  programming_exercise_submissions 0
  programming_exercise_progress   0
```

```text
REAL_BACKFILL_ROWS = 0
```

即：**当前没有任何真实历史用户作答行**。本轮 backfill 实现以 deterministic fixtures 验证，
**不声称**「真实历史数据迁移已验证」。

---

## 4. LEGACY_ATTEMPT_SOURCE_MATRIX

| source | namespace | 粒度 | 用户范围 | question identity | answer | result 表示 | writer | reader | 事件 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `question_attempts` | course_learning | **per-question** | username | `question_id` → `questions.id` | `user_answer` | `self_result` 串（correct/incorrect/unknown） | `POST /practice/questions/{id}/attempts` (main.py:24214)、`/feedback` (24376) | `/practice/summary`、`/review/center`、`/learning/practice/stats`、admin、report builder | 无（走 KnowledgeProgressEvent） |
| `ai_question_attempts` | course_learning | **per-session** | username | `question_ids_json[]` → `questions.id` | `answers_json {qid: ans}` | `result_json.results[]`（`correct` bool\|None） | `POST /course-learning/practice/generate` (20268)、`/workbook/{qid}/attempts` (20436) | 20288 / 20368 / 20408 / 20451、`data_plane/backfill.py` | **有**：`emitter.build_course_practice_events` (20334) |
| `ai_question_attempts` | exam_11408 | **per-session** | username | `question_ids_json[]` → `ai_generated_questions.id` | `answers_json` | `result_json.results[]`（big → `correct=None`, `judge=self_review`） | `POST /exam/11408/{k}/ai-questions/attempts` (20718) | 20737 / 20763 | 无 |
| `exam_practice_attempts` | exam_11408 | **per-session** | username | `question_ids_json[]` → `exam_question_bank.id` | `answers_json` | `result_json.results[]` | `POST /exam/11408/{k}/chapter-practice/attempts` (21110) | 19195 / 21064 / 21123 | 无 |
| `past_paper_attempts` | exam_11408 | **per-session** | username | 无 `question_ids_json`；题集由年份题库推导 | `answers_json` | `result_json.results[]`（`score`/`full_score`/`correct`（仅选择）） | `POST /exam/11408/{k}/past-paper-attempts` (19510)；submit (19727) | 19401 / 19564 | 无 |
| `exam_question_done_records` | exam_11408 | **per user+question 聚合** | username | `question_bank_id` / `ai_question_id` | `user_answer` | `is_correct` bool\|None | helper `_save_done_record` (21730) ← 3 处调用 | 18849 / 20997 / 21718 | 无 |
| `code_challenge_attempts` | programming | **per-submission** | username | `challenge_id` | `code` | `status` = **AI 文本关键词匹配** | `POST /code/challenges/{id}/submit` (14366) | 14924 / 14984 / 15214 | 无 |
| `programming_exercise_submissions` | programming | per user+exercise（仅首次通过） | username | `exercise_id` | — | `passed_at`（真实通过事实） | helper `_record_programming_submission_progress` (10898) ← submit (12051) | 6644 / 10920 | 无 |
| `programming_exercise_progress` | programming | **per user+exercise 聚合** | username(+user_id) | `exercise_id` | — | `last_submit_passed` / `last_public_passed_count` / `last_public_total_count`（**真实判题**） | helper `_record_programming_exercise_activity` (10968) ← run/test/submit | 6647 / 11165 / 11062 | 无 |

**关键审计发现（决定 programming 适配器选择）**：`code_challenge_attempts.status` 由 AI 散文关键词匹配得出
（`failed`/`partial`/`probable_pass`/`unknown`），**不是执行结果**。若用它作为 `correct` 即为伪造裁决，
故该 source 判为 **INELIGIBLE**。真实判题结果只存在于 `programming_exercise_progress` /
`programming_exercise_submissions`（沙箱实际跑完测试后才写）。

---

## 5. QUESTION REFERENCE MODEL

`backend/learning/practice/refs.py`

```text
QuestionRef(source_type, source_id, service_namespace,
            source_version?, context{}, raw_source{})
```

- canonical `source_type`（SSOT §19 冻结集）：`static_question_bank` / `past_exam` /
  `AI_generated` / `material_generated` / `programming_exercise` / `adaptive`。
- `LEGACY_SOURCE_MAP` 显式登记 legacy 来源 → canonical 类型；**未登记的来源抛错**，
  不会静默落到某个默认值。
- `raw_source` **逐字保留**原始来源（表名、mode、legacy row id、year、attempt_no、language…），
  映射过程不销毁 provenance。
- **未迁移任何题目内容**：`exam_question_bank` = 9333、`programming_exercises` = 1923 保持原位，
  未建「大一统 question 表」。

---

## 6. PRACTICE SESSION MODEL

`practice_sessions`：`id` / `session_uid`(unique) / `user_id`(FK users.id, NOT NULL) /
`username` / `service_namespace` / `mode` / `source_type` / `source_session_key` /
`session_origin` / `status` / `context_json`(LearningContext snapshot) / `started_at` /
`completed_at` / `created_at` / `updated_at` / `schema_version`。

- `session_origin` = `live`（API 创建）或 `legacy_compat`（legacy 容器镜像）。
- `session_uid` 对 legacy 容器是 **UUIDv5**（namespace + source_type + source_session_key），
  重算恒等 → 重试/重跑不会产生第二个 session。
- `started_at` **可为 NULL**：来源没有真实开始时间时不编造。
- 状态机：`active` → `completed` / `abandoned`；两个终态**不可互相转换、不可隐式恢复**；
  `complete` / `abandon` 各自**幂等**。

---

## 7. PRACTICE ATTEMPT MODEL

`practice_attempts`：`id` / `attempt_uid`(unique) / `session_id`(FK) / `user_id`(FK) /
`username` / `service_namespace` / `question_source_type` / `question_source_id` /
`question_ref_json` / `source_attempt_type` / `source_attempt_id` / `source_item_key` /
`answer` / `correct` / `score` / `max_score` / `result_json` / `submitted_at` /
`response_time_ms` / `attempt_no` / `context_json` / `fact_hash` / `schema_version`。

**Immutable fact principle（§7）**

```text
attempt_uid 对 legacy 镜像 = UUIDv5(namespace, source_attempt_type, source_attempt_id, item_key)
attempt_uid 对 API 直写    = uuid4（这是当下发生的新事实）
fact_hash    = sha256(canonical_json(事实载荷))

同一 source identity 重复导入：
  payload 完全相同 → 返回既有行（attempt_deduped），不重复插入
  payload 不同     → 抛 AttemptConflict（attempt_conflict），拒绝覆盖历史
```

**domain semantics 未被压平**

| 题型 | `correct` | `score` |
| --- | --- | --- |
| 客观题（选择/判断） | True / False | 可空 |
| 大题 / 综合题（无裁决） | **NULL**（保留 `judge=self_review`） | 可空（真题映射 `score` / `full_score`） |
| 编程提交 | True / False（**真实判题**） | `passed_count` / `total_count` |

`correct` 永不 `bool(None)`；`score` 永不被布尔化；编程 `result_json` 保留 `source=execution`。

---

## 8. MIGRATION 0003

```text
revision = 20260915_0003
down_revision = 20260915_0002
新增 = practice_sessions, practice_attempts（exactly two）
additive-only；无 DROP、无 rebuild、无数据重写
downgrade 显式 NotImplementedError（产品表不允许就地销毁学习历史）
```

验收（`tests/test_practice_migration.py`，对**副本**执行真实 Alembic）：

| 场景 | 结果 |
| --- | --- |
| A. fresh 临时 SQLite | `integrity_check = ok`，head = `20260915_0003`，新增表 = 恰好两张 |
| B. 当前 `backend/app.db` 的临时**副本** | `integrity_check = ok`，head = `20260915_0003` |
| 静态资产 | `exam_question_bank = 9333`、`programming_exercises = 1923`、`knowledge_points = 32` **不变** |
| 既有表 | `before.tables ⊆ after.tables`（无删除） |
| 0003 增量隔离 | 先升到 `0002` 再升 head，diff = `{practice_sessions, practice_attempts}` |
| 禁止表 | `wrong_answer_states` / `review_items` / `review_attempts` / `plans` / `tasks` / `learning_outcomes` / `review_schedules` **均未创建** |

```text
FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
STATIC_ASSET_COUNTS = 9333 / 1923 / 32（不变）
```

**真实 `backend/app.db` 未被本轮修改**（72 表，`integrity_check = ok`，无 practice 表）。
未在真实库上盲跑迁移。本地库在下次启动时由既有 `create_all` 机制补齐；正式迁移在部署流程执行。

---

## 9. PRACTICE SERVICE

`backend/learning/practice/service.py` —— canonical service，业务 endpoint 不拼 SQL：

```text
create_session / get_session / list_sessions
ensure_legacy_session（deterministic find-or-create）
record_attempt / get_attempt / list_attempts / session_summary
complete_session / abandon_session
```

- 所有函数**同时**按 `user_id` + `service_namespace` 限定；不存在无范围访问器。
- `session_summary` 的计数**从 attempts 现算**，未引入物化聚合列（§37）。
- 拒绝语义是显式异常类型：`SessionNotFound` / `SessionClosed` / `CrossUserAccess` /
  `NamespaceMismatch` / `AttemptConflict`。

---

## 10. LEARNINGCONTEXT

复用 `backend/core/learning_context.py`，**未建立第二套 context 对象**：

- 接受 `LearningContext` 或 namespace 值；`context.service_namespace` 与 session 不一致 → `NamespaceMismatch`。
- session/attempt 保存 `context_json`（canonical JSON snapshot）。
- 未携带 LLM 生成的学习者状态或科学状态。

---

## 11. COURSE ADAPTER

`adapters/course.py` → 镜像 `ai_question_attempts`（course_learning 与 exam 11408 两种 mode，
按 `mode` 解析 namespace 与 question 来源：`questions`→`material_generated`、
`ai_generated_questions`→`AI_generated`）。

- per-session → **按题扇出**为一题一条 canonical attempt。
- `source_item_key = f"{qid}:{idx}"`，与 Data Plane 既有 item key **完全一致**；canonical attempt
  与其 learning event 描述同一 item。
- **不发送 learning event**：`course_practice` 事件的唯一 authoritative owner 是既有
  `data_plane.emitter`（main.py:20334）。
- `status != submitted` → 不镜像；**无 per-question 明细 → 不镜像**（不编造未发生的作答）。
- 接线点：`POST /course-learning/practice/workbook/{id}/attempts` 提交后。

---

## 12. EXAM ADAPTER

`adapters/exam.py`

- **chapter practice**（`exam_practice_attempts`）→ 题源 `static_question_bank`；
  客观题 `correct` bool、大题保持 `NULL` 且保留 `judge`。
- **past paper**（`past_paper_attempts`）→ 题源 `past_exam`；逐题 `score` / `full_score`
  映射为 `score` / `max_score`，并保留 `attempt_no`（同一份卷子的多次作答可区分）、`year`、
  `feedback`。
- 真实 `started_at` / `submitted_at` 透传；不存在则 `NULL`。
- 接线点：chapter submit (main.py 21257 后) 与 past-paper submit (19769 前)。
- 这两个来源今日**没有** emitter，故 Practice Core 是它们的 event owner（见 §15）。

---

## 13. PROGRAMMING ADAPTER

`adapters/programming.py` → 镜像 `programming_exercise_progress`（**真实判题**）。

- `correct` = `last_submit_passed`（沙箱跑完测试后的裁决，非 AI 文本、非 LLM 判断）。
- `score` / `max_score` = `last_public_passed_count` / `last_public_total_count`（真实用例计数）。
- `QuestionRef`：`source_type=programming_exercise`，`raw_source` 保留 `exercise_id`、
  `progress_id`；`context` 保留 `language`。
- session 容器 = exercise 本身（`ensure_legacy_session(source_type="programming_exercise",
  source_session_key=exercise.id)`），单次提交由**请求内的提交时间戳**区分
  （不读聚合行的 `last_submit_at`，否则下一次提交会覆盖身份）。
- 无真实提交时间戳 → **拒绝镜像**（`no_submission_timestamp`），不伪造身份。
- 接线点：exercise submit，且**使用独立 session 镜像**，绝不回滚该请求上未提交的 legacy 写入。
- Workbench / execution sandbox **未重构**。

---

## 14. BACKFILL

`backend/learning/practice/backfill.py` —— 每个来源显式分类（`FULL` / `PARTIAL` / `INELIGIBLE`），
PARTIAL **必须列出缺失字段**，禁止 fabricated value：

| source | 分类 | missing fields | 理由 |
| --- | --- | --- | --- |
| `ai_question_attempts` | PARTIAL | response_time_ms, item_score, max_score | per-session，明细仅在 result_json |
| `question_attempts` | PARTIAL | response_time_ms, score, max_score, session_container | per-question 自评串，无 session 列 |
| `exam_practice_attempts` | PARTIAL | response_time_ms, item_score, max_score | per-session |
| `past_paper_attempts` | PARTIAL | response_time_ms | 逐题 score/full_score/attempt_no 保留 |
| `programming_exercise_progress` | PARTIAL | language_at_submit, earlier_submissions, code, per_case_detail | 聚合行：只能恢复**最后一次**提交 |
| `programming_exercise_submissions` | **INELIGIBLE** | — | 与 progress 表示同一次提交；同时镜像会**重复计数** |
| `code_challenge_attempts` | **INELIGIBLE** | — | status 是 AI 散文关键词匹配，非执行结果 |

- 用户已不存在的 legacy 行 → 记为 `unknown_user` 失败计数，不猜测归属。
- `question_attempts` 的 session 容器：能通过 `questions.paper_id` 解析则用 `paper:<id>`，
  否则退化为 per-attempt synthetic container；两者都 deterministic 且标 `legacy_compat`。

```text
BACKFILL = IMPLEMENTED（5 个来源）
BACKFILL_IDEMPOTENCY = PASS（首跑插入 N，重跑插入 0）
REAL_BACKFILL_ROWS = 0（当前无真实历史用户作答行）
REAL_HISTORICAL_MIGRATION_VALIDATED = NO（不声称）
```

---

## 15. LEARNING EVENT BRIDGE

**EVENT_OWNER 冻结**

| 来源 | owner | event_type |
| --- | --- | --- |
| course_learning（AI 答题） | **既有 `data_plane.emitter`** | `course_practice` |
| exam_11408（Practice Core 镜像） | Practice Core | `question_answered` |
| programming（Practice Core 镜像） | Practice Core | `code_submitted` |

- `events.build_event(course_learning attempt)` 返回 **None**；`emit_for_attempt` 返回
  `not_practice_owned` → **不可能出现两条等价事件**。
- event id 由**冻结函数** `data_plane.identity.event_id(source_type, source_attempt_id, item_key)`
  生成 → deterministic，live 与 backfill 一致；UUIDv5 namespace 未改动。
- 事件**只从 durable PracticeAttempt 派生**，不从客户端 payload 派生；含 `event_schema_version`、
  `user_id`、`service_key`、`context`。
- `item_snapshot_json` 明确标 `snapshot_capture_mode=PRACTICE_CORE`、`snapshot_completeness=PARTIAL`、
  `missing_fields=[item_content]` —— 因为 Practice Core **引用**题目而不复制内容。

```text
LEARNING_EVENT_BRIDGE = PASS
COURSE_EVENT_DUPLICATION = NO
```

---

## 16. STUDENTTWIN ELIGIBILITY SAFETY

```text
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
```

- Data Plane producer 只选择 `LearningEvent.event_type == "course_practice"`
  （`data_plane/worker.py` 两处 filter 均如此）。
- Practice Core **不产生** `course_practice` 事件；它产生 `question_answered` / `code_submitted`，
  因此结构性排除在 StudentTwin 之外——不需要修改 worker，也不依赖「记得不要送」。
- `exam_11408` / `programming` 即使已产生 canonical PracticeAttempt，当前仍
  `STUDENT_TWIN_ELIGIBLE = NO`。
- 未触碰 STEP6 冻结的 eligible source 集合（仍只有 course_learning / course_practice /
  AIQuestionAttempt）。
- 测试固化：`test_student_twin_eligibility_is_not_expanded`、`test_course_attempts_are_not_emitted_by_practice_core`。

---

## 17. API

SSOT STEP5 API matrix **未冻结** session 级 practice 路径，故采用 canonical `/practice/` 风格；
未另造第二组等价 endpoint：

```text
POST /practice/sessions
GET  /practice/sessions
GET  /practice/sessions/{id}
GET  /practice/sessions/{id}/summary
POST /practice/sessions/{id}/attempts
GET  /practice/sessions/{id}/attempts
GET  /practice/history
POST /practice/sessions/{id}/complete
POST /practice/sessions/{id}/abandon
```

身份只来自 session cookie（`get_current_user`），**从不**取自 query 参数。

---

## 18. LEGACY COMPATIBILITY

```text
LEGACY_TABLES_DELETED = NO
LEGACY_ENDPOINTS_DELETED = NO
```

- `backend/main.py` 本轮 diff = **+48 / −1**：2 行 router 注册 + 5 处 mirror hook（每处
  `try/except` 包裹）。原有业务逻辑未改写，无 big-bang rename。
- 所有既有 course / exam / past-paper / programming endpoint 行为不变。
- 未改写 `main.py` 的 30k 行结构。

**CORE BUSINESS FAILS SAFE（§13）**

```text
legacy 行先 commit → 再镜像
镜像失败 → safe_mirror 吸收 → logger.warning("practice.legacy_mirror_failed ...")
         → 原 durable attempt 不丢
身份 deterministic → 之后可由 backfill 补齐（recoverable / backfillable）
```

---

## 19. ISOLATION

| 维度 | 机制 | 测试 |
| --- | --- | --- |
| cross-user read | 所有读取带 `user_id`；越权 → `SessionNotFound` | `test_user_cannot_read_another_users_session` |
| cross-user write | `_assert_session_usable` 校验 `session.user_id == user.id` | `test_user_cannot_add_attempt_to_another_users_session` |
| cross-user list | `list_sessions` / `list_attempts` 均 user-scoped | `test_session_list_excludes_other_users`、`test_attempt_query_is_user_scoped` |
| cross-namespace | session 与 QuestionRef namespace 必须一致 | `test_course_session_rejects_exam_attempt`、`test_exam_session_rejects_programming_attempt` |
| context 一致性 | `LearningContext.service_namespace` 必须与 session 一致 | `test_context_namespace_must_match_session` |
| API 层 | 越权 session 一律 404（不泄露存在性） | `test_other_user_cannot_read_or_write_a_session` |

```text
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
```

---

## 20. IDEMPOTENCY / CONCURRENCY

```text
ATTEMPT_IDEMPOTENCY = PASS        （同 source identity + 同 fact → 单行，attempt_deduped）
CONFLICT_DETECTION = PASS         （同 identity + 不同 fact → AttemptConflict，拒绝覆盖）
LEGACY_SESSION_DETERMINISM = PASS （UUIDv5，重算恒等，不因 retry 新建 session）
CONCURRENT_MIRROR_SAFETY = PASS   （两线程镜像同一 source attempt → 恰好一行）
```

并发实现沿用既有模式：`attempt_uid` 唯一约束即为 gate，`IntegrityError` → 回读 → dedupe/conflict。
未引入 Redis / Kafka / 消息队列。

---

## 21. DATA PRESERVATION

```text
exam_question_bank      = 9333   （不变）
programming_exercises   = 1923   （不变）
knowledge_points        = 32     （不变）
exam_resources / static / programming_catalog = 未触碰
现有 Data Plane / Usage 表 = 未触碰
backend/app.db（真实）= 72 表，integrity_check = ok，未新增 practice 表
```

---

## 22. TARGETED TESTS

```text
新增 68 项，全部 PASS
TARGETED_TESTS = PASS（0 failed）
```

| 文件 | 项数 | 覆盖 |
| --- | --- | --- |
| `tests/test_practice_core.py` | 28 | session CRUD/状态机/幂等、attempt 语义（三态/null/score-only/多题重复作答/attempt_no）、LearningContext、cross-user、cross-namespace、question source mapping、raw provenance、deterministic identity、attempt 幂等、conflict、**并发镜像** |
| `tests/test_practice_adapters.py` | 25 | course adapter（两种 mode / 扇出 / 未提交跳过 / 幂等）、exam adapter（chapter 三态、past paper score+attempt_no）、programming adapter（真实判题 pass/fail、拒绝无时间戳）、`code_challenge_attempts` 排除、backfill 分类/缺失字段/幂等/孤儿行/不编造、event bridge（owner/幂等/恢复/确定性 id/StudentTwin 不扩大）、mirror 失败可观测 |
| `tests/test_practice_migration.py` | 4 | fresh DB、legacy 副本、0003 增量隔离、静态资产保持 |
| `tests/test_practice_api.py` | 11 | HTTP contract、鉴权、404 越权、409 已关闭、400 未知 namespace/source、summary 真实计数、namespace 过滤 |

---

## 23. FULL REGRESSION

```text
baseline = 391 passed / 0 failed
after    = 459 passed / 0 failed（(0:03:10)）
PY_COMPILE = OK
REGRESSION = NONE
```

`459 = 391 + 68`。无任何既有测试失败；模型池 / provider / pricing 相关测试全绿。

---

## 24. FINAL VERDICT

```text
STEP7CP_FINAL_FROZEN = YES（延续，未改动）

MIGRATION_HEAD = 20260915_0003
NEW_TABLES = practice_sessions / practice_attempts
WRONG_ANSWER_STATES_CREATED = NO

PRACTICE_SESSION_CORE = PASS
PRACTICE_ATTEMPT_CORE = PASS
LEARNING_CONTEXT_INTEGRATION = PASS

COURSE_ADAPTER = PASS（ai_question_attempts → Practice Core，无重复事件）
EXAM_ADAPTER = PASS（chapter practice + past paper）
PROGRAMMING_ADAPTER = PASS（真实判题结果，排除 LLM 派生 status）

LEGACY_TABLES_DELETED = NO
LEGACY_ENDPOINTS_DELETED = NO

BACKFILL = IMPLEMENTED（5 来源，分类 FULL/PARTIAL/INELIGIBLE）
BACKFILL_IDEMPOTENCY = PASS
REAL_BACKFILL_ROWS = 0

CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
ATTEMPT_IDEMPOTENCY = PASS
CONCURRENT_MIRROR_SAFETY = PASS

LEARNING_EVENT_BRIDGE = PASS
COURSE_EVENT_DUPLICATION = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO

FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
STATIC_ASSET_COUNTS = 9333 / 1923 / 32

TARGETED_TESTS = PASS（68）
FULL_BACKEND_TESTS = PASS（459 passed / 0 failed）

STEP7D_COMPLETE = YES
STEP7E_READY = YES
STEP7D = FROZEN
```

`BLOCKERS = 无。残留观察（不阻断）：① 真实 app.db 未执行迁移（本轮按 §30 仅在副本验证，未盲跑；alembic_version 表在 app.db 中尚不存在，属 0001/0002 以来的既有状态）。`

### 24.1 CORRECTION（STEP7D FINAL RECONCILIATION, 2026-09-16）

本报告此前记录的残留观察 ② —— 「`_record_programming_submission_progress` 的写入位于一个
未提交的事务中，`get_db` 关闭时不 commit」—— **是错的**。该结论来自一段被截断的代码摘录：
函数体末尾实际有 `db.commit()`（main.py:10956）。

真实 transaction ownership（已逐行追踪并以事务级测试固化）：

```text
submit endpoint
  → _record_programming_exercise_activity(...)      → db.commit()   （progress 持久）
  → _record_programming_submission_progress(...)    → db.commit()   （submission + knowledge progress 持久）
  → Practice mirror（独立 session，失败隔离）
```

因此 STEP7D **不存在** programming durability gap，无需修 helper，也不应机械地在 helper 内加
`db.commit()`。证据：`tests/test_practice_durability.py`（7 项）—— 用真实 `get_db` 生命周期
（session 关闭且不额外 commit）验证 judged fact 仍可被新 session 读到，并端到端验证
「judge → durable commit → mirror 失败 → backfill 重建 → 字段/身份一致 → 重跑插入 0」。

```text
PROGRAMMING_DURABLE_SOURCE = programming_exercise_progress（durable，已实测）
PROGRAMMING_MIRROR_FAILURE_RECOVERABLE = YES（已实测）
PROGRAMMING_DOUBLE_COUNT = NO
```

详见 `STEP7E_WRONG_ANSWER_CORE_ACCEPTANCE_REPORT.md` §3–§4。

---

## 25. 变更文件清单

```text
[NEW] backend/learning/__init__.py
[NEW] backend/learning/practice/{__init__,models,refs,identity,service,events,backfill}.py
[NEW] backend/learning/practice/adapters/{__init__,base,course,exam,programming}.py
[NEW] backend/routers/practice.py
[NEW] backend/tests/test_practice_core.py
[NEW] backend/tests/test_practice_adapters.py
[NEW] backend/tests/test_practice_migration.py
[NEW] backend/tests/test_practice_api.py
[NEW] migrations/versions/20260915_0003_create_practice_core_tables.py
[MOD] backend/main.py                    +48 / −1（router 注册 + 5 个 mirror hook）
[MOD] ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md §73 STEP7D
```

无 schema 改动落在真实库；`backend/app.db` 未改；**部署时需执行 `alembic upgrade head`**。
