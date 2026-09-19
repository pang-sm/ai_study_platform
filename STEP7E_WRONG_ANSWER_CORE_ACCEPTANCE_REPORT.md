# STEP7E_WRONG_ANSWER_CORE_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7E 验收报告
> 范围：STEP7D FINAL RECONCILIATION（programming durability）+ Unified Wrong Answer Core
> 生成：2026-09-16 · 本轮为 IMPLEMENTATION（有代码变更，未 commit / 未 push）

---

## 1. EXECUTIVE VERDICT

```text
STEP7D_FINAL_FROZEN = YES
STEP7E = FROZEN
STEP7F_READY = YES

PROGRAMMING_DURABLE_SOURCE            = PASS
PROGRAMMING_MIRROR_FAILURE_RECOVERABLE = PASS
PROGRAMMING_DOUBLE_COUNT              = NO

MIGRATION_HEAD = 20260915_0004
NEW_TABLES = wrong_answer_states
REVIEW_TABLES_CREATED = NO

FULL_BACKEND_TESTS = PASS（516 passed / 0 failed；baseline 459）
```

**本轮最重要的一件事：STEP7D 验收报告里那条「durability gap」是**错的**，我把它纠正了。**

---

## 2. GIT BASELINE

```text
HEAD = ebad5282（merge: reconcile local clean-slate frontend/governance with origin backend intelligence）
本轮未执行任何 git 写操作（NO commit / push / reset / clean / checkout / rebase / merge / pull）
```

变更分类：

```text
PREEXISTING_DIRTY（STEP7C-P 遗留，与本轮无关）
  backend/ai/**、backend/usage/service.py、backend/tests/test_{ai_models_api,benchmark,
  pricing_pool_router,provider_adapters,secret_loader}.py、scripts/**、SSOT、STEP7CP 报告

STEP7D（上一轮，未 commit）
  backend/learning/practice/**、backend/routers/practice.py、backend/main.py（+48/−1）、
  migrations/versions/20260915_0003_*、backend/tests/test_practice_{core,adapters,migration,api}.py

THIS_BATCH（STEP7E）
  ?? backend/learning/wrong_answers/{__init__,models,project,service,legacy}.py
  ?? backend/routers/wrong_answers.py
  ?? migrations/versions/20260915_0004_create_wrong_answer_states.py
  ?? backend/tests/test_practice_durability.py
  ?? backend/tests/test_wrong_answers.py
  ?? backend/tests/test_wrong_answers_api.py
   M backend/main.py                     （+2，wrong-answers router 注册）
   M backend/learning/practice/service.py（+12，projection hook）
   M backend/tests/test_practice_migration.py（0004 覆盖）
   M STEP7D_PRACTICE_CORE_ACCEPTANCE_REPORT.md（§24.1 纠正）
```

模型池 / provider / pricing / benchmark **均未改动**。无 frontend 改动。

---

## 3. STEP7D PROGRAMMING DURABILITY RECONCILIATION

### 3.1 结论：原假设不成立

STEP7D 报告 §24 残留观察 ② 声称：

> 「`_record_programming_submission_progress` 的写入位于一个未提交的事务中，`get_db` 关闭时不 commit」

**该结论是错的。** 它来自一段被截断的代码摘录——函数体末尾（main.py:10956）实际有
`db.commit()`，我当时只读到第 10905 行就下了判断。

### 3.2 A1 真实 transaction ownership（逐行追踪）

```text
POST /programming/exercises/{exercise_id}/submit
  │  db = Depends(get_db)          ← 谁创建 Session：FastAPI 依赖，try/finally close
  │
  ├─ _run_official_exercise_tests(...)          ← 沙箱执行，真实判题（不含 DB 写入）
  ├─ _exercise_run_summary(...)                 ← 纯计算，产出 payload
  │
  ├─ _record_programming_exercise_activity(user, exercise, db, "submit", payload)
  │     ├─ upsert programming_exercise_progress（last_submit_at / last_submit_passed /
  │     │   last_public_passed_count / last_public_total_count）
  │     ├─ db.commit()                          ← ★ 持久化点 1
  │     └─ return progress
  │
  ├─ if payload.passed: _record_programming_submission_progress(user, exercise, db)
  │     ├─ early return [] 若无知识点关联（该分支不写任何行）
  │     ├─ insert programming_exercise_submissions（若首次）
  │     ├─ upsert user_knowledge_progress
  │     ├─ db.commit()                          ← ★ 持久化点 2
  │     └─ return updated
  │
  ├─ Practice mirror（独立 SessionLocal，失败隔离）   ← STEP7D 已加
  └─ return payload
      ↓
  get_db finally: db.close()                    ← 无未提交写入可丢

结论：不存在未提交事务；两个 helper 各自 commit，ownership 正确。
```

按 A1 的要求，**没有**在 helper 内机械地补 `db.commit()`——正确 owner 已经是它自己。

### 3.3 A2 durable fact 完整性

`PROGRAMMING_DURABLE_SOURCE = programming_exercise_progress`

| A2 要求 | 来源 | 是否满足 |
| --- | --- | --- |
| user_id | `programming_exercise_progress.user_id`（另有 username） | ✅ |
| exercise_id | `programming_exercise_progress.exercise_id` | ✅ |
| submission identity | `programming_exercise_progress.id` + `last_submit_at` | ✅（见下方限制） |
| language | `programming_exercises.language`（durable 静态资产） | ✅ |
| submitted_at | `last_submit_at`（真实提交时刻） | ✅ |
| 真实 judge outcome | `last_submit_passed`（bool，沙箱判定） | ✅ |
| 真实 test metadata | `last_public_passed_count` / `last_public_total_count` | ✅ |

**已知限制（PARTIAL，不隐藏）**：该表是 per-(user, exercise) 聚合，只有**最后一次**提交可恢复；
更早的提交被覆盖。因此 canonical rebuild 能重建「最新一次真实判题」，无法重建全部历史。
该限制已登记在 STEP7D 的 backfill 分类中（`earlier_submissions` 为 missing field）。

```text
不得通过 LLM 推断 = YES（judge 结果全部来自沙箱执行）
```

### 3.4 A3 采用的方案

```text
OPTION = NONE_REQUIRED（当前实现已正确）
```

A 方案（修 transaction ownership）不适用——ownership 本来就对。
B 方案（改以 `programming_exercise_submissions` 为 durable fact）未采用：
它只有「首次通过」才写行，且不含 judge 计数，表达力弱于 progress。
C 方案（另一 durable record）不存在。
**未创建任何重复的 programming submission 表。**

### 3.5 A4 SOURCE OF TRUTH vs MIRROR

```text
PROGRAMMING_DURABLE_SOURCE  = programming_exercise_progress（legacy judged fact）
PROGRAMMING_CANONICAL_MIRROR = practice_attempts
```

```text
一次真实提交 → 一条 durable domain 记录 → 一条 canonical PracticeAttempt
programming_exercise_submissions 判为 INELIGIBLE（与 progress 表示同一次提交，
两者都镜像会把一次提交计两次）
PROGRAMMING_DOUBLE_COUNT = NO
```

实测证据：`test_recovery_reproduces_the_same_identity_as_live_mirror` —— live mirror 先跑，
随后 backfill 对同一次提交只产生 `deduped`，canonical 行数仍为 1。

---

## 4. PROGRAMMING RECOVERY TEST

`tests/test_practice_durability.py`（7 项，全部 PASS）：

| 测试 | 证明 |
| --- | --- |
| `test_judged_progress_survives_request_session_close` | 按真实 `get_db` 生命周期（session 关闭且不额外 commit）后，新 session 仍能读到 judged fact |
| `test_pass_submission_row_survives_request_session_close` | submission 行同样持久 |
| `test_failed_submission_is_durable_too` | 失败提交同样持久（不只记录通过） |
| `test_durable_source_carries_every_field_needed_to_rebuild` | A2 全部字段可从 durable source 取得，无需猜 |
| `test_mirror_failure_is_recoverable_from_the_durable_source` | **A5 全序列** |
| `test_recovery_reproduces_the_same_identity_as_live_mirror` | 无 double count |
| `test_ai_prose_status_never_becomes_a_judged_fact` | A6 回归守卫 |

**A5 全序列实测**（`test_mirror_failure_is_recoverable_from_the_durable_source`）：

```text
1. 真实 judge 得到 FAIL（passed=False, 2/4）
2. durable domain record 已 commit
3. 强制 Practice mirror 失败（safe_mirror 捕获 → failed=1, reason=RuntimeError）
4. 请求/域流程按设计完成
5. canonical PracticeAttempt 不存在（list_attempts == []）
6. backfill 从 durable source 重建
7. 重建结果与原事实逐字段一致：
     correct=False（真实判决）· score=2.0/max_score=4.0（真实用例计数）
     submitted_at 相同 · source_attempt_id == progress.id · source_item_key 相同
     question_source_type=programming_exercise · question_source_id == exercise.id
8. 第二次 backfill → inserts 0，canonical 行数仍为 1
```

```text
PROGRAMMING_MIRROR_FAILURE_RECOVERABLE = YES
```

---

## 5. CURRENT WRONG ANSWER AUDIT

```text
exam_wrong_questions              0 rows
past_paper_wrong_questions        0 rows
programming_exercise_progress     0 rows
code_challenge_attempts           0 rows
user_knowledge_review_settings    0 rows
```

```text
REAL_WRONG_BACKFILL_ROWS = 0
REAL_HISTORICAL_MIGRATION_VALIDATED = NO（不声称）
```

当前**没有**真实历史错题行；legacy import 算法以 deterministic fixtures 验证。

现存 legacy 错题结构只有两张表（`exam_wrong_questions` / `past_paper_wrong_questions`）。
**没有** course 错题表，**没有** programming 错题表——programming 的失败语义存在于
`programming_exercise_progress.personal_status = needs_work`（聚合，非历史）。

---

## 6. LEGACY WRONG SOURCE MATRIX

| table/model | namespace | question identity | user scope | status 取值 | mastered/review | source attempt | writer | reader | rows | fidelity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `exam_wrong_questions` | exam_11408 | `question_bank_id`（AI 生成为 null，按 stem 匹配） | username | active / mastered / removed | `mastered`, `review_count`, `resolved_at` | `practice_attempt_id` | chapter submit 21251 / AI submit 20855 | GET `/exam/11408/{k}/wrong-questions` 21649 | 0 | **PARTIAL** |
| `past_paper_wrong_questions` | exam_11408 | `question_id`（字符串，来自解析卷） | username | active / mastered | `mastered`, `reviewed_at`, `resolved_at` | `attempt_id` | past-paper submit 19762 | 同上 21667 | 0 | **PARTIAL** |
| `programming_exercise_progress` | programming | `exercise_id` | username(+user_id) | passed / needs_work / not_started | — | `last_submit_at` | exercise submit 10968 | `/programming/home` 6647 | 0 | **INELIGIBLE_AS_HISTORY** |
| `code_challenge_attempts` | programming | `challenge_id` | username | failed / partial / probable_pass / unknown | — | — | `/code/challenges/{id}/submit` 14366 | `/code/attempts` 14924 | 0 | **INELIGIBLE_AS_CORRECTNESS** |

`INELIGIBLE_AS_HISTORY`（programming_exercise_progress）：不是作答历史，只保留最后一次提交；
programming 的错题状态改由 canonical PracticeAttempt 驱动。
`INELIGIBLE_AS_CORRECTNESS`（code_challenge_attempts）：status 由 AI 散文关键词匹配得出，
不是执行结果，用作 correctness 即为伪造裁决——**不因为做 Wrong Answer Core 而重新启用**（A6）。

legacy 生命周期语义（读代码确认，非猜测）：
`active` → 当前错题；`mastered`（含 `resolved_at`）→ 用户手动掌握；`removed` → 软删除（exam）；
past-paper 的 DELETE 是**物理删除**。

---

## 7. WRONG ANSWER STATE MODEL

`wrong_answer_states` —— 本轮**唯一**新表：

```text
id
user_id (FK users.id) / username / service_namespace
question_source_type / question_source_id / question_scope_key
status                active | resolved
origin                practice | legacy | legacy_merged
wrong_count
first_wrong_attempt_id / latest_wrong_attempt_id / latest_attempt_id / resolved_attempt_id
first_wrong_at / last_wrong_at / resolved_at
context_json          LearningContext snapshot
legacy_source_type / legacy_source_id / legacy_mastered /
legacy_review_count / legacy_reviewed_at
schema_version / created_at / updated_at
UNIQUE(user_id, service_namespace, question_source_type, question_source_id, question_scope_key)
```

**没有** attempt history 表、event 表、review 表。历史一律从 `practice_attempts` 查询（§8）。
**没有** stem / options / standard_answer / analysis 快照列——§7.1 的显示数据全部从
QuestionRef + PracticeAttempt + domain source 读取（见 §9）。

§7.1 显示数据可达性（先审计后决定，未复制整道题）：

| 需要 | 来源 | 结论 |
| --- | --- | --- |
| Question | `practice_attempts.question_ref_json` | 可重建 ✅ |
| UserAnswer | `practice_attempts.answer` | 可重建 ✅ |
| CorrectAnswer | `practice_attempts.result_json.standard_answer`（adapter 已存） | 可重建 ✅ |
| Context | `practice_attempts.context_json` | 可重建 ✅ |
| ErrorAnalysis | `result_json.feedback` / `analysis`；无则 **null** | 可重建 ✅（绝不让 LLM 猜） |
| ReviewStatus | `wrong_answer_states.status` | 本表 ✅ |

因此 `wrong_answer_states` **不保存快照**。

---

## 8. IDENTITY

```text
identity = (user_id, service_namespace, question_source_type, question_source_id,
            question_scope_key)
```

- `attempt identity != question identity`：同一题可有多条 PracticeAttempt，只有一条状态行。
  实测：3 次错答 → 1 行 state、`wrong_count = 3`、`attempt_history` 长度 3。
- `question_scope_key` 仅对 `past_exam` 生效（`year:<year>`）：真题 `question_id` 来自解析卷，
  不能保证全局唯一；**误合并比分开更糟**，故按年份分区。其余题源全局唯一 → 空 scope。
- 碰撞安全实测：同 `source_id="123"` 在 exam_11408 与 programming 各自成行；
  `static_question_bank/123` 与 `AI_generated/123` 各自成行。

---

## 9. STATE TRANSITIONS

```text
首次错答                → ACTIVE
再次错答                → 保持 ACTIVE，wrong_count +1
此后答对                → RESOLVED（resolved_at / resolved_attempt_id 记录）
RESOLVED 后再错答        → 回到 ACTIVE（重开；resolved_at 清空，历史留在 attempts）
RESOLVED 后再答对        → 保持 RESOLVED
correct = NULL          → 不产生、不解除、不改变任何状态
无任何事实性错答          → 不产生状态行
```

`RESOLVED` 表示「存在时间上更晚的事实性答对」或「用户显式标记」，**不表示**永久掌握、
更不是掌握概率。命名上刻意不用 mastered probability / mastery（§4 红线）。

---

## 10. TRI-STATE CORRECTNESS

| PracticeAttempt.correct | WrongAnswer 投影行为 |
| --- | --- |
| `True` | 可解除既有 ACTIVE 状态 |
| `False` | 创建 / 维持 ACTIVE，`wrong_count` +1 |
| `None` | **不做任何转换** |

绝对禁止 `NULL → False`。实测：
`test_null_correctness_never_creates_a_wrong_state`、
`test_null_correctness_does_not_resolve`、
`test_score_only_attempt_never_becomes_a_wrong_answer`（只有分数、无裁决 → 不进错题）。

```text
TRISTATE_CORRECTNESS_PRESERVED = PASS
```

---

## 11. MIGRATION 0004

```text
revision = 20260915_0004
down_revision = 20260915_0003
新增 = wrong_answer_states（EXACTLY ONE）
additive-only；无 DROP / 无 rebuild；downgrade 显式 NotImplementedError
```

| 场景 | 结果 |
| --- | --- |
| fresh 临时 SQLite | integrity=`ok`，head=`20260915_0004` |
| `backend/app.db` 临时**副本** | integrity=`ok`，head=`20260915_0004` |
| 0004 增量隔离 | 先升 0003 再升 head，diff = `{wrong_answer_states}` |
| 禁止表 | `review_items` / `review_attempts` / `review_schedules` / `wrong_answer_attempt_history` / `wrong_answer_events` / `plans` / `tasks` / `learning_outcomes` 均未创建 |
| 静态资产 | `exam_question_bank=9333`、`programming_exercises=1923`、`knowledge_points=32` 不变 |
| practice 表 | 保持 |

```text
FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
REAL_APP_DB_MIGRATED = NO（按 §35 安全策略，本轮不擅自升级真实库）
STATIC_ASSET_COUNTS = 9333 / 1923 / 32
```

---

## 12. PRACTICE PROJECTION

```text
durable PracticeAttempt（已 commit）
  ↓  （learning/practice/service.py，lazy import + try/except）
WrongAnswer projector / recompute
  ↓
WrongAnswerState
```

**RECOMPUTE，不是增量累加**——这是本轮的核心设计决定。状态始终从该 (user, namespace,
question) 的**全部** canonical attempts 重新推导，因此一次性获得三个性质：

- **幂等**：没有累加量，同一 attempt 折叠两次不改变任何值（`wrong_count` 是不同错答的
  计数，不是投影执行次数）；
- **顺序无关**：重算内部按 `(submitted_at, id)` 排序，乱序重放与顺序重放收敛到同一行；
- **可重建**：canonical attempts 足以重建任何状态。

失败隔离：projection 异常被捕获、`logger.warning` 记录，已 commit 的 PracticeAttempt 不受影响；
状态可由 rebuild 恢复（§15）。

```text
PRACTICE_PROJECTION = PASS
```

---

## 13. COURSE ADAPTER

course_learning 由 canonical PracticeAttempt 驱动（无独立错题 writer）。

- 错答（`material_generated` 题源）→ ACTIVE；后续答对 → RESOLVED。
- 题源身份保留（`question_source_type = material_generated`），不因题目来源而丢历史。
- **StudentTwin eligibility 未改变**：WrongAnswerState 不产生任何 LearningEvent。

---

## 14. EXAM ADAPTER

- **chapter / general practice**：题源 `static_question_bank`（`exam_question_bank` id）。
- **past paper**：题源 `past_exam`，identity 带 `year:<year>` scope。
- 保护 `exam_question_bank = 9333`：仅引用，未复制、未改写。
- 历史 legacy 错题记录按真实语义 backfill（§16）。

---

## 15. PROGRAMMING ADAPTER

- 由 §3/§4 修好的 durable judged fact 驱动：真实 judge fail → ACTIVE；后续真实 pass → RESOLVED。
- `QuestionRef` 保留 `exercise_id` + `raw_source.progress_id`，`context` 保留 `language`。
- `code_challenge_attempts` 的 AI 散文 status **不驱动**任何状态。
- 保护 `programming_exercises = 1923`（仅引用）。
- Workbench / Programming Agent 边界未动。

---

## 16. LEGACY BACKFILL

`learning/wrong_answers/legacy.py`：

- **exam**：`question_bank_id` 为 null（AI 生成行）或用户不存在的行 → **跳过并计数**，不猜测归属。
- **past paper**：identity 携带 `year:<year>`；`question_id` 为空 → 跳过。
- **dedupe**：若该题已有 canonical facts → 走 `recompute(..., legacy=...)`，**不新建第二行**；
  否则走 legacy-only upsert。
- **conflict policy（§17）**：有 facts 的题由 facts 决定 status；legacy `mastered` /
  `review_count` / `reviewed_at` 只作为兼容元数据保存，**不能覆盖**更新的真实 attempt correctness。
- legacy review 字段是兼容元数据，**不是** Review Core，也不冒充新的智能复习系统。

实测：

```text
test_legacy_exam_wrong_backfill_creates_state
test_legacy_mastered_imports_as_resolved
test_legacy_past_paper_backfill_carries_year_scope
test_legacy_backfill_is_idempotent
test_legacy_does_not_override_newer_canonical_correctness   ← legacy active + 更新的事实答对 → RESOLVED
test_legacy_and_canonical_do_not_double_count              ← 同一题 → 1 行，无重复
test_legacy_rows_without_a_user_are_skipped_not_guessed
test_legacy_matrix_is_audited_not_guessed
```

```text
LEGACY_BACKFILL = PASS
```

---

## 17. CANONICAL REBUILD

`service.rebuild_states(db, user_id=?, service_namespace=?, dry_run=?)`

- 只做 upsert / reconcile，**无 drop-rebuild 式破坏性操作**。
- `dry_run=True` 只统计不落库（实测：dry-run 后状态行数仍为 0；随后真实 rebuild 恢复为 1）。
- 幂等可重复执行。
- 支持 user scope / namespace scope。

```text
CANONICAL_REBUILD = PASS
```

---

## 18. IDEMPOTENCY

| 场景 | 结果 |
| --- | --- |
| 同一 attempt 投影两次 | `wrong_count` 只加一次（`test_attempt_replay_does_not_double_count`） |
| 两条不同错答 | `wrong_count = 2` 且仅 1 行 state |
| rebuild 重复执行 | 行数不变、计数不变 |
| legacy backfill 重复执行 | 行数不变 |

```text
WRONG_COUNT_IDEMPOTENCY = PASS
```

---

## 19. CONCURRENCY

两个线程同时为同一题写入错答：

```text
最终 = 恰好 1 行 WrongAnswerState，wrong_count = 2，无异常逃逸
（test_concurrent_wrong_attempts_yield_one_state）
```

实现沿用既有模式：identity 唯一约束即 gate，`IntegrityError` → 回读 → 重算。
未引入 Redis / Kafka / 消息队列。

```text
CONCURRENCY_SAFETY = PASS
```

---

## 20. ISOLATION

| 维度 | 测试 |
| --- | --- |
| A 不能读 B 的错题状态 | `test_cross_user_isolation`、`test_cross_user_isolation_over_api` |
| A 不能解除 B 的状态 | `test_cross_user_cannot_resolve_another_users_state`（且 B 的状态未被改动） |
| 列表按当前用户范围 | API 越权用户看到 `[]` |
| 跨 namespace | `test_cross_namespace_filter`（exam 状态不被 programming 过滤命中） |
| 同 source_id 跨 namespace | `test_source_id_collision_across_namespaces_keeps_states_separate` |
| 同 source_id 跨 source_type | `test_source_id_collision_across_source_types_keeps_states_separate` |

API 层越权一律 404（不泄露存在性）。

```text
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
SOURCE_COLLISION_SAFETY = PASS
```

---

## 21. REVIEW BOUNDARY

```text
REVIEW_CORE_IMPLEMENTED = NO
```

- 未创建 `review_items` / `review_attempts` / `review_schedules`（migration 测试断言）。
- legacy 的 `mastered` / `review_count` / `reviewed_at` 只作为 `legacy_*` 兼容元数据保存。
- `legacy_review_count` **不等于** canonical `wrong_count`（实测二者分别为 4 与 1）。
- 未实现 dynamic review / memory scientific component。

`delete wrong state` 与 `resolve wrong state` 语义不同：canonical API 只提供 resolve/unresolve
（保留历史证据），不提供物理删除；legacy 的 delete/patch endpoint 行为未改动。

---

## 22. SCIENTIFIC / STUDENTTWIN SAFETY

```text
SCIENTIFIC_WRONG_DIAGNOSIS_IMPLEMENTED = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
```

- 未接 `misconception_v2` / `learner_state` / `IRT` / `evidence_reliability`。
- WrongAnswerState 是产品事实状态，不是科学预测；未写任何 LLM 推断的错因。
- `error_analysis` 无既有来源时返回 `null`（实测），绝不让 LLM 猜。
- WrongAnswer 投影**不写任何 LearningEvent**（`test_wrong_answer_projection_does_not_touch_learning_events`
  断言 `learning_events` 行数不变）→ StudentTwin 输入集合未被扩大。
- 未实施 STEP7F Records / Data Plane migration。

---

## 23. API

SSOT 未冻结本模块 exact path（只有 `wrong_answers` 模块处置），故采用 canonical `/wrong-answers/`：

```text
GET   /wrong-answers                     list（支持 service_namespace / status 过滤）
GET   /wrong-answers/{state_id}          detail（含 state + 显示数据 + attempt_history）
PATCH /wrong-answers/{state_id}          {"resolved": bool} 生命周期更新
```

仅 3 个 endpoint（§23「不要构建十几个 endpoint」）。身份只来自 session cookie。

**legacy compatibility（§29 不删除）**：`GET /exam/11408/{k}/wrong-questions`、
`DELETE .../{wrong_id}`、`PATCH .../{wrong_id}/mastered` **行为未改动**，
实测仍正常响应（`test_legacy_exam_wrong_endpoint_still_works`）。

---

## 24. DATA PRESERVATION

```text
exam_question_bank     = 9333（不变）
programming_exercises  = 1923（不变）
knowledge_points       = 32（不变）
practice_sessions / practice_attempts = 保持（0004 不动它们）
exam_wrong_questions / past_paper_wrong_questions = 未 DROP、未改写
```

```text
LEGACY_WRONG_TABLES_DELETED = NO
LEGACY_ENDPOINTS_DELETED = NO
REAL_APP_DB_MIGRATED = NO
```

---

## 25. TARGETED TESTS

```text
新增 57 项，全部 PASS
```

| 文件 | 项数 | 覆盖 |
| --- | --- | --- |
| `tests/test_practice_durability.py` | 7 | A1–A6：durability、字段完整性、mirror 失败恢复全序列、无 double count、AI 散文不作为判题 |
| `tests/test_wrong_answers.py` | 38 | 生命周期（ACTIVE/RESOLVED/重开）、三态、score-only、五个 space、identity/碰撞、隔离、乱序重放、rebuild 幂等 + dry-run、并发、legacy 四种情形、review 边界、学生孪生边界 |
| `tests/test_wrong_answers_api.py` | 11 | HTTP contract、鉴权、过滤、越权 404、跨 namespace 碰撞、legacy endpoint 仍可用 |
| `tests/test_practice_migration.py` | +1（共 5） | 0004 增量恰好一张表、禁止表未创建、静态资产保持 |

---

## 26. FULL REGRESSION

```text
baseline = 459 passed / 0 failed
after    = 516 passed / 0 failed
PY_COMPILE = OK
REGRESSION = NONE
```

`516 = 459 + 57`（durability 7 + wrong_answers 38 + wrong_answer API 11 + migration 净增 1）。

---

## 27. FINAL VERDICT

```text
STEP7D_FINAL_FROZEN = YES

PROGRAMMING_DURABLE_SOURCE = PASS（programming_exercise_progress，已实测持久）
PROGRAMMING_MIRROR_FAILURE_RECOVERABLE = PASS
PROGRAMMING_DOUBLE_COUNT = NO

MIGRATION_HEAD = 20260915_0004
NEW_TABLES = wrong_answer_states
REVIEW_TABLES_CREATED = NO

WRONG_ANSWER_CORE = PASS
PRACTICE_PROJECTION = PASS

COURSE_WRONG_ADAPTER = PASS
EXAM_WRONG_ADAPTER = PASS
PROGRAMMING_WRONG_ADAPTER = PASS

LEGACY_WRONG_TABLES_DELETED = NO

TRISTATE_CORRECTNESS_PRESERVED = PASS
WRONG_COUNT_IDEMPOTENCY = PASS
RESOLUTION_REOPEN = PASS
OUT_OF_ORDER_REPLAY = PASS

CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
SOURCE_COLLISION_SAFETY = PASS
CONCURRENCY_SAFETY = PASS

LEGACY_BACKFILL = PASS
CANONICAL_REBUILD = PASS
BACKFILL_IDEMPOTENCY = PASS

STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
REVIEW_CORE_IMPLEMENTED = NO
SCIENTIFIC_WRONG_DIAGNOSIS_IMPLEMENTED = NO

FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
REAL_APP_DB_MIGRATED = NO
STATIC_ASSET_COUNTS = 9333 / 1923 / 32

TARGETED_TESTS = PASS（57 = 7 durability + 38 wrong-answer + 11 API + 1 migration）
FULL_BACKEND_TESTS = PASS（516 passed / 0 failed）

STEP7E_COMPLETE = YES
NEXT_SUBSTEP_READY = YES（STEP7F = Records / Data Plane consolidation）
```

`BLOCKERS = 无。残留（不阻断）：① programming 的 durable source 是 per-(user,exercise) 聚合，只有最后一次提交可重建，更早的提交无法恢复（已在 backfill 分类中登记为 PARTIAL）；② 真实 app.db 仍未迁移（按 §35 安全策略，待部署 gate 执行 backup → hash → upgrade head → integrity）；③ exam_wrong_questions 中 AI 生成行（question_bank_id 为 null）无法映射到稳定 question identity，backfill 跳过并计数。`

---

## 28. 变更文件清单

```text
[NEW] backend/learning/wrong_answers/{__init__,models,project,service,legacy}.py
[NEW] backend/routers/wrong_answers.py
[NEW] migrations/versions/20260915_0004_create_wrong_answer_states.py
[NEW] backend/tests/test_practice_durability.py
[NEW] backend/tests/test_wrong_answers.py
[NEW] backend/tests/test_wrong_answers_api.py
[MOD] backend/main.py                          +2（wrong-answers router 注册）
[MOD] backend/learning/practice/service.py     +12（projection hook，lazy + 失败隔离）
[MOD] backend/tests/test_practice_migration.py 0004 覆盖
[MOD] STEP7D_PRACTICE_CORE_ACCEPTANCE_REPORT.md §24.1 纠正（durability 结论）
[MOD] ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md       §73 STEP7E
```

部署时需执行 `alembic upgrade head`（真实库当前 head 仍为「无 alembic_version」，见 STEP7D 报告 §8）。
