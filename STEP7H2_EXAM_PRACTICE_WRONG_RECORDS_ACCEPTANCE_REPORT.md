# STEP7H2_EXAM_PRACTICE_WRONG_RECORDS_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7H2 验收报告
> 范围：CS408 / exam_prep — Practice + Wrong Answers + Records consolidation
> 生成：2026-09-16 · 本轮为 **IMPLEMENTATION**（有代码变更，未 commit / 未 push）

---

## 1. Executive Verdict

```text
STEP7H2_COMPLETE = YES
STEP7H2          = FROZEN
STEP7H3_READY    = YES

CANONICAL_EXAM_NAMESPACE      = exam_prep（延续 H1）
CS408_PRACTICE_SHARED_CORE    = PASS
CHAPTER_PRACTICE_MIGRATED     = PASS
PAST_PAPER_PRACTICE_MIGRATED  = PASS
AI_GENERATED_ATTEMPT_PATH     = PASS

PRACTICE_IDENTITY_REPLAY_SAFE      = PASS
IDENTITY_NAMESPACE_TOKEN_UNCHANGED = YES（exam_prep → exam_11408，H1 冻结未动）

PAST_EXAM_IDENTITY_AUDIT      = PASS
PAST_EXAM_WRONG_SCOPE         = subject:cs_408|module:<m>|year:<y>
MULTI_SUBJECT_COLLISION_SAFE  = PASS

PAST_PAPER_STABLE_KEY         = (subject_key, year, question_number)
PAST_PAPER_BUILDER_DELETE_INSERT = REMOVED
PAST_PAPER_ID_STABILITY       = PASS
PAST_PAPER_BUILDER_IDEMPOTENT = PASS

QUESTION_BANK_COUNT           = 9333
QUESTION_BANK_CONTENT_PRESERVED = YES（指纹与审计基线逐字节相同）

EXAM_WRONG_SHARED_CORE   = PASS
WRONG_REPLAY_DOUBLE_COUNT = NO

EXAM_RECORDS_SHARED_CORE = PASS
EVENT_SUBJECT_KEY        = cs_408
EVENT_MODULE_CONTEXT     = PASS
EXAM_EVENT_DUPLICATION   = NO

EXAM_KNOWLEDGE_UPDATE_EXACTLY_ONCE = PASS（exam practice 不产生 knowledge delta，经审计确认）
STUDENT_TWIN_ELIGIBILITY_EXPANDED  = NO

FREE_USER_EXAM_FACT_PERSISTENCE = PASS
CROSS_USER_ISOLATION / CROSS_NAMESPACE_ISOLATION / CROSS_MODULE_ISOLATION = PASS

REAL_APP_DB_MUTATED = NO
NEW_TABLES          = NONE
FULL_BACKEND_TESTS  = PASS
```

---

## 2. Git / DB Safety

```text
HEAD = ebad5282（与轮次开始时一致，未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

所有需要模块加载的动作（import main / TestClient / pytest / route introspection）均在显式
`DATABASE_URL=sqlite:///<temp>` 下执行；真实 `backend/app.db` **只用只读 sqlite3**
（`file:…?mode=ro`）访问，未建 engine、未 create_all、未迁移、未写入。

**真实库指纹复核**（这是本轮数据安全的最强证据）：对
`(id, subject_key, source_type, year, question_number, stem, standard_answer)` 逐行 sha256：

```text
REAL  backend/app.db            fingerprint = 349a76497c8a5320f822f99809fe9553
COPY  (审计副本, upgrade head)  fingerprint = 349a76497c8a5320f822f99809fe9553   ← 逐字节相同
```

```text
REAL_APP_DB_MUTATED = NO
```

---

## 3. EXAM_PRACTICE_FACT_MATRIX

逐条从当前磁盘事实取得（不按 endpoint 名猜）：

| # | fact | legacy durable table | legacy row identity | writer endpoint | reader endpoint | canonical mirror | PracticeSession | PracticeAttempt | Wrong projection | event owner | knowledge side effect | recovery / backfill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | **Chapter practice** | `exam_practice_attempts` | PK `id`（**per-session** 汇总，逐题明细只在 `result_json.results`） | `POST /exam/11408/{k}/chapter-practice/attempts/{id}/submit` (21253) | `GET …/chapter-practice/attempts/{id}` | `mirror_exam_practice_attempt` (21340) | `ensure_legacy_session(source_type="exam_practice_attempt", key=attempt.id)` → **一次练习一个 session** | 每题一条；`correct` 三态；`judge` 保留 | 经 practice spine | practice spine（`question_answered`） | **无** | `learning/practice/backfill.py::backfill_exam_practice_attempts` |
| B | **Past paper** | `past_paper_attempts` | PK `id`；`year` + `attempt_no` | `POST /exam/11408/{k}/past-paper-attempts/{id}/submit` (19729) | `GET …/past-paper-attempts/{id}` | `mirror_past_paper_attempt` (19856) | 同上，`source_type="past_paper_attempt"` → **一次考试一个 session** | 每题一条；`score`/`max_score`/`attempt_no` 保留 | 经 practice spine | practice spine | **无** | `backfill_past_paper_attempts` |
| C | **AI generated questions** | `ai_question_attempts`（**与 course 共用一张表**） | PK `id`；`mode="11408"` | `POST /exam/11408/{k}/ai-questions/attempts/{id}/submit` | `GET …/ai-questions/attempts/{id}` | `mirror_ai_question_attempt` (20939) | `source_type="ai_question_attempt"` | 每题一条；题源 `AI_generated` | 经 practice spine | practice spine（**course 模式**由 `data_plane.emitter` 拥有，见 §11） | **无** | 同 course backfill（`_MODE_MAP` 分流） |
| D | Imported / material generated | `practice_import_jobs` → `questions` | 导入作业 PK | `POST /practice/import-paper/*` | `/practice/papers` | **不在 H2 范围**（属 course 导入管线） | — | — | — | — | — | — |
| E | **Done records** | `exam_question_done_records` | `(username, question_bank_id / ai_question_id)` 聚合 | `_save_done_record`（3 处） | — | **不镜像**（per-user 聚合，只保留最后一次；非 attempt history） | — | — | — | — | 无 | 不适用（INELIGIBLE，见 §10） |
| F | **Wrong questions** | `exam_wrong_questions` / `past_paper_wrong_questions` | `question_bank_id` / `question_id` | chapter submit 21251 / AI submit 20855 / past-paper submit 19762 | `GET /exam/11408/{k}/wrong-questions` | `wrong_answer_states`（canonical） | — | — | 经 `legacy.py` merge，**facts 优先** | — | 无 | `backfill_exam_wrong_questions` / `backfill_past_paper_wrong_questions` |
| G | Favorites | `exam_favorite_questions` | `source_question_id` | 3 条路由 | 同左 | **H2 不动**（无 Favorites Core） | — | — | — | — | 无 | 不适用 |
| H | Knowledge progress | `user_knowledge_progress`（**与 course 共用**） | `course_id = "<module>_11408"` | **仅** `PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}`（直写） | 4 条 exam 只读路由 | 未接 canonical writer（§13） | — | — | — | — | **唯一** knowledge 写入点 | 不适用 |
| I | Learning records / events | `learning_events`（共享） | 事件确定性身份 | 上述 mirror | records read model | 直接写共享事件流 | — | — | — | practice spine | 无 | `recover_events` |

**关键结论**：exam 的「真实作答事实」只有 A / B / C 三种；E 是 per-user 聚合（非 history）、
F 是错题投影、G 是收藏、H 是计划侧状态。三类事实全部 1:1 映射到 canonical
`PracticeSession` + `PracticeAttempt`，且**都不产生 knowledge delta**。

---

## 4. PAST_EXAM_IDENTITY_AUDIT

只读实测（真实库，235 行 `source_type='past_paper'`）：

```text
TOTAL = 235        ACTIVE = 170        SUPERSEDED(is_active=0) = 65
```

| 检查 | 结果 |
| --- | --- |
| A. 同 module + year 内 `(question_number)` 是否唯一 | **ACTIVE 行：170/170 唯一**；全表有 **65 个重复组**（全部是 superseded 的 image-placeholder 世代） |
| B. 同一年不同 module 是否有相同 `question_number` | **0**（CN 33–47 / CO 12–44 / OS 23–46 区间互不相交；2022–2026 每年 34 行 34 个不同题号） |
| C. 不同 year 是否有相同 `source_id` | `source_ref` 形如 `past_paper:2022-Q33`，**含年份** → 无跨年碰撞 |
| D. 未来不同 exam_subject 是否可能碰撞 | **会** —— 每门科目都会有自己的 "2022 第 12 题" → 必须把 subject 编入 scope（见 §9） |

```text
DUPLICATES_WITHIN_MODULE_YEAR          = 65 组 / 65 额外行（全部 is_active=0，全部有 active 对应行，0 孤儿）
COLLISIONS_ACROSS_MODULES_SAME_YEAR    = 0
COLLISIONS_ACROSS_YEARS                = 0
CURRENT_SCOPE_SUFFICIENT               = YES（判据：ACTIVE 行上的稳定键唯一）
```

**65 个重复组的来源（已查明，非猜测）**：`build_computer_organization_past_papers.py`
（docx+图片世代）当初采用「先把旧行 `is_active=False`，再插入新行」的协议，因此每跑一次就
累积一代；其继任者 `…_text.py` 的注释逐字记录了这个事故（“Previously used UPDATE
is_active=False which accumulated one duplicate batch per deploy — the root cause of the
5070-question over-seeding”），并改用 wholesale DELETE —— 修好了重复，却引入了 §6 的 id 漂移。

**本轮不删除这 65 行**：它们可能已被 done / wrong / favorite / attempt 引用。它们已被
正确 deactivate，并在 reconcile 中作为 `duplicate_groups` 上报。

---

## 5. PAST_PAPER_STABLE_KEY_AUDIT

```text
PAST_PAPER_STABLE_KEY = (subject_key, year, question_number)
```

| 检查项 | 结果 |
| --- | --- |
| `year` / `question_number` NOT NULL 覆盖 | 235/235（past_paper 行全部有值；`year` 为 NULL 的 9098 行全是 chapter） |
| ACTIVE 行上的唯一性 | **170/170 唯一，0 冲突** |
| 全表唯一性 | 不成立（65 个 superseded 组）→ 因此 reconcile 必须带 **确定性 survivor 规则**，而不是假定唯一 |
| `source_ref` 一致性 | 格式统一 `past_paper:{year}-Q{n:02d}`；但因世代重复而**不唯一** → 不能作为稳定键 |
| chapter 行 | `year`/`question_number` **全为 NULL** → 该键对 chapter 无意义；chapter 的稳定身份是**内容哈希**（既有 `chapter_question_upsert.py`） |

**幸存者规则（写进实现并测试）**：优先取 `is_active` 的行（它才是产品正在服务的那一行），
否则取 `id` 最大者（最近一次导入）。确定性、与行序无关。

---

## 6. D6 —— Builder ID Drift（已修）

### 6.1 缺陷

5 个 ingestion builder 里有 4 个做 **wholesale DELETE + INSERT**（第 5 个做 deactivate+insert）：

```text
computer_organization/past_papers/build_…_text.py:244      .delete()
computer_network/past_papers/build_…_past_papers.py:272    .delete()
operating_system/past_papers/build_…_past_papers.py:385    .delete()
computer_network/chapter_practice/build_…_chapter_questions.py:241  .delete()
computer_organization/past_papers/build_…_past_papers.py:234  .update({"is_active": False}) + INSERT
```

每次重跑都会让 `exam_question_bank.id` 全部改变，而 `exam_question_done_records.question_bank_id`、
`exam_wrong_questions.question_bank_id`、`exam_favorite_questions.source_question_id`、
`past_paper_attempts.result_json[].question_id` 全部引用它 —— **历史引用静默失效**。
（另一个 builder 的 deactivate 协议则反方向出错：累积重复。）

### 6.2 修法

新增 `backend/past_paper_upsert.py`（与既有 `chapter_question_upsert.py` 同形，零新表）：

```text
stable key 命中唯一一行   → UPDATE CONTENT IN PLACE，保留 id
stable key 命中多行       → survivor = is_active 优先，否则 id 最大；更新该行，其余原样保留
stable key 无命中         → INSERT
新 source 已不含的 key    → deactivate（软标记），**永不删除**
```

- 恒等列（`year` / `question_number` / `subject_key` / `source_type`）由 helper 自己写入，
  builder 即使忘记也不会造出无法 reconcile 的行（本轮就是先踩到这个才补的）。
- 返回 `(inserted, updated, deactivated, duplicate_groups, unkeyed)` 并打印 —— stale 与
  重复组**被上报而不是被隐藏**。
- `chapter_question_upsert.py` 同步做**加法式**扩展（可选 `analysis` / `quality_status` /
  `source_ref`），使 CN chapter builder 能改用它；不传这些键的既有 builder 行为**逐字不变**。

### 6.3 验收

```text
PAST_PAPER_BUILDER_DELETE_INSERT = REMOVED（exam_resources 下 build_*.py 已无 target 题库的 .delete()）
PAST_PAPER_ID_STABILITY          = PASS
PAST_PAPER_BUILDER_IDEMPOTENT    = PASS
```

测试固化：同输入连跑两次 → `(inserted, updated) = (2,0)` 然后 `(0,2)`，id 与内容
**逐字节相同**；改内容 → 同 id、新内容；source 少一题 → 该行 deactivate 且**仍然存在**；
survivor 规则在构造的重复组上选中 active 行且不动 superseded 行；另有静态不变式测试
（builder 源码不得对题库做 wholesale delete）。

---

## 7. EXAM PRACTICE ADAPTER

`backend/learning/practice/adapters/exam.py`：

- 三个 mirror 入口（chapter / past paper）与 `course.py` 的 AI-question 分岔，全部经
  **`cs408_context`** 构造 context（不再手写 `LearningContext(...)`）：
  `exam_track_id=cs_408` / `exam_subject_id=cs_408` / `exam_module_id=<legacy subject_key>`，
  并保留 `subject_key = module` 的 legacy mirror。
- `QuestionRef.context` 补齐：`exam_subject_id` / `exam_module_id`（chapter / AI），
  另加 `question_year`（past paper，同时保留 `year` 键兼容既有读取）。
- **tri-state 不变**：`_ungraded_to_none` 保持 `None` 语义，大题/自评永不变成 `False`。
- `track` 只出现在请求上下文，**不进** attempt identity（见 §12）。

---

## 8. PRACTICE IDENTITY

```text
IDENTITY_NAMESPACE_TOKEN_UNCHANGED = YES
IDENTITY_TOKEN_BY_NAMESPACE = {course_learning: course_learning,
                              exam_prep: exam_11408,
                              programming: programming}
```

H1 的冻结 token 未被改动。新增测试：

- `exam_11408` 与 `exam_prep` 两种输入 → **相同** `session_uid` / `attempt_uid`；
- 同一 legacy 行经两种拼法各镜像一次 → 只产生 **1 条** canonical attempt；
- mirror 重复执行 3 次 → attempt 数、`wrong_count`、事件数都不变。

```text
PRACTICE_IDENTITY_REPLAY_SAFE = PASS
```

---

## 9. WRONG IDENTITY（past_exam scope）

### 9.1 旧形态

```text
scope_key = "year:<year>"
```

### 9.2 新形态（§8，按实测判别力最小化）

```text
scope_key = "subject:<exam_subject_id>|module:<exam_module_id>|year:<question_year>"
```

判据（全部来自 §4/§5 的实测）：

1. `question_source_id` 是 `exam_question_bank` 的**自增主键**（`qid = str(item.id)`，main.py:19766），
   在整个题库内全局唯一 → scope 不承担「区分同一 subject 内的题」的职责；
2. 它**必须**承担的是**未来第二门统考科目**带来的维度：每门科目都会有 "2022 第 12 题"；
3. `module` 仍然被编码 —— 它**对所有现存引用都可派生**（旧 adapter 把 module 写在
   `subject_key` 里，`scope_key` 读取时回退到该键），所以不会把「旧 attempt」和「新 attempt」
   劈成两套 scope；而省略它会让「同 subject 下两个 module 复用同一题号」失去保护
   （本轮测试正是在这一点上先失败了一次，证明它不是冗余）。
4. `year` 保留：`,question_year` 来自**卷面年份**，与用户的 `target_exam_year` 严格分离（H0 FD-10）。
5. **`exam_track_id` 永不进入 scope**（track 是学习者的组合选择，不是题目事实）—— 测试固化：
   把 track 塞进 ref context 不改变 scope。

### 9.3 兼容（§9）

`recompute()` 新增 `_adopt_legacy_past_exam_scope`：当新 scope 形如
`subject:…|year:Y` 而库中存在同一 `(user, ns, source_type, source_id)` 的
`year:Y` 旧行时，**就地改键采纳**（保留 id 与 provenance），而不是让它变成第二条状态。
若两种形态同时存在则**不静默合并**（谁承载真实历史是审计问题，且唯一约束会拒绝）。

### 9.4 legacy 侧

`learning/wrong_answers/legacy.py` 的 past-paper 回填改为调用**同一个** `past_exam_scope()`
并把 `row.subject_key` 作为 module 传入 —— 单一实现，legacy 导入与 live 投影不可能分歧。

```text
PAST_EXAM_WRONG_SCOPE        = subject:cs_408|module:<m>|year:<y>
MULTI_SUBJECT_COLLISION_SAFE = PASS（cs_408 / math_1 / math_2 / math_3 合成 context 各得独立 scope 与独立状态）
WRONG_REPLAY_DOUBLE_COUNT    = NO
```

---

## 10. LEGACY_WRONG_OWNERSHIP_MATRIX

| legacy 表 | 是否 durable source | 投影方向 | 本轮的处置 |
| --- | --- | --- | --- |
| `exam_wrong_questions` | ✅ 是（compatibility 窗口内的 domain source of truth） | → `wrong_answer_states`（facts 优先，legacy 作 metadata） | **不 DROP、不改写**；端点继续可读 |
| `past_paper_wrong_questions` | ✅ 是 | 同上 | 同上 |
| `exam_question_done_records` | ❌ 不是 attempt history（per-user 聚合，只留最后一次） | 不投影 | 登记为 INELIGIBLE_AS_HISTORY |
| `exam_favorite_questions` | ✅ 是（收藏语义） | 不投影（无 Favorites Core） | 保留；D6 修复后其 `source_question_id` 引用不再因 id 漂移失效 |

**防双写**：legacy 表是**读取兼容 + 一次性 merge 源**，canonical `wrong_answer_states` 是
状态权威。`recompute` 是 RECOMPUTE-not-INCREMENT，因此投影重放不会累加 `wrong_count`
（实测：同一 attempt 投影 3 次，`wrong_count` 恒为 1）。

---

## 11. EXAM_EVENT_OWNERSHIP_MATRIX

| 事实 | canonical event owner | event_type | 说明 |
| --- | --- | --- | --- |
| exam chapter practice attempt | practice spine（`learning/practice/events.py`） | `question_answered` | 无第二个生产者 |
| exam past-paper attempt | practice spine | `question_answered` | 同上 |
| exam AI-question attempt（`mode="11408"`） | practice spine | `question_answered` | 同上 |
| **course** AI-question attempt（`mode="course_learning"`） | `data_plane.emitter.build_course_practice_events` | `course_practice` | practice spine 通过 `FOREIGN_OWNED_SOURCES` **拒绝**重复发 |
| AI 调用 | orchestrator → records producers | `ai_called` | |
| knowledge 状态迁移 | canonical writer 的 emitter | `knowledge_status_changed` | exam 当前无 |

**证据**：`data_plane/emitter.py` 的 `SERVICE_KEY`/`EVENT_TYPE` 是模块常量
（`course_learning` / `course_practice`），唯一调用点是 `main.py:20422`（**course** 提交流程）。
因此 exam AI-question attempt **没有**第二个 owner，practice spine 是它的合法 owner。

```text
EXAM_EVENT_DUPLICATION = NO（测试：exam AI-question attempt 恰好 1 条 question_answered，
                            且该用户没有任何 course_practice 事件）
```

---

## 12. RECORDS

```text
EXAM_RECORDS_SHARED_CORE = PASS
EVENT_SUBJECT_KEY        = cs_408
EVENT_MODULE_CONTEXT     = PASS
```

事件落法（延续 H1 契约）：

```text
service_key              = exam_prep
subject_key              = cs_408（exam_subject_id，不是 module）
knowledge_point_ref_json = {"knowledge_point_id": …, "exam_module_id": "operating_system"}
exam_track_id            = 不出现
```

records read model（`learning/records/service.py`）本轮做了一处**加法式**改动：domain-context
投影同时暴露 `exam_module_id`（此前只暴露 `knowledge_point_id`），使 exam 记录可按 module 过滤。
对没有该键的历史事件无影响（缺键即不输出）。

E2E 断言：Free 用户在 exam 空间的记录 `service_namespace == exam_prep`、
`context.subject_key == cs_408`、`context.exam_module_id == operating_system`。

---

## 13. EXAM_KNOWLEDGE_MUTATION_MATRIX

对全部 52 条 exam 路由做 AST 审计（谁写 `UserKnowledgeProgress` / 调 `apply_knowledge*`）：

| 路由 | 读写 | 处置 |
| --- | --- | --- |
| `PATCH /exam/11408/{k}/study-plan/knowledge-items/{item_code}` | **写**（`UserKnowledgeProgress` + `mastery_score` 直写，**不经 canonical writer**） | 已登记为 `OUT_OF_SCOPE_SPACE`（space = exam_prep）；H2 **不改**（见下） |
| `GET /exam/11408/{k}/study-plan` | 只读 | — |
| `GET /exam/11408/study-plan/summary` | 只读 | — |
| `GET /exam/11408/{k}/dashboard-summary` | 只读 | — |
| 其余 48 条 | 不触碰 knowledge 状态 | — |

**exam practice（chapter / past paper / AI）完全不产生 knowledge delta**：

```text
mirror 源码中没有 apply_knowledge* / UserKnowledgeProgress（测试固化）
E2E：mirror 前后 user_knowledge_progress 行数不变
```

这是**现状语义**，H2 保持不改（§24：legacy 语义不同就报告并保持，不自行统一）。因此
「exactly once」在本轮的含义是：**没有任何路径把 delta 应用两次** —— mirror 应用 0 次，
唯一的写入点是学习计划的人工编辑，且只写 1 次。

```text
EXAM_KNOWLEDGE_UPDATE_EXACTLY_ONCE = PASS
STUDENT_TWIN_ELIGIBILITY_EXPANDED  = NO（未接任何 scientific component）
```

**未决（交后续 STEP）**：把该 PATCH 接 canonical writer 需要 writer 支持 exam 的
knowledge 身份（exam 知识点来自 seed JSON / 题库列，不在 `KnowledgePoint` 表里），
属结构性改动，不在 H2 范围。

### 13.1 user_confirmed_status

`user_knowledge_progress.user_confirmed_status` 由 course 的 canonical writer 使用；
exam 目前不经过它，因此「practice 建议不得覆盖学习者已确认状态」这条课程原则在 exam 上
**无从违反**（exam 的 practice 根本不写状态）。如实记录，不做统一。

---

## 14. Backfill / Recovery

| 路径 | 结果 |
| --- | --- |
| `learning/practice/backfill.py` | 已写 `exam_prep`（H1 修正）；经 exam adapter → CS408 context；**幂等**（重放同 identity → dedupe） |
| `learning/wrong_answers/legacy.py` | past-paper scope 与 live 共用 `past_exam_scope()`；facts 优先；幂等 |
| mirror 失败 | `safe_mirror` 隔离；legacy 行仍是 durable source，可重放恢复（STEP7D 已固化） |
| 65 个 superseded 题库行 | **不删除**；由 reconcile 上报 `duplicate_groups` |

---

## 15. Multi-subject Forward Compatibility

```text
MULTI_SUBJECT_COLLISION_SAFE = PASS
```

合成测试（**不导入任何真实新科目数据**）：用 `cs_408 / math_1 / math_2 / math_3` 四个
`exam_subject_id` 构造同 `source_id=12`、同 `question_year=2022` 的 past-exam 引用：

```text
4 个不同 scope；4 条互不相同的 wrong state；无合并、无覆盖
```

`MULTI_ACTION_…`：catalog 仍只装 CS408（`math_1` / `politics` / `law_jm_law` 等**不在** catalog），
导入真实科目内容属 STEP7H4。

---

## 16. Protected Assets

```text
FRESH temp DB      = 13 表 / integrity ok / head 20260915_0006
LEGACY COPY        = 85 表 / integrity ok / head 20260915_0006 / 9333 / 1923 / 32
REAL backend/app.db = 72 表 / integrity ok / 9333 / 1923 / 32 / 无 alembic_version
bank fingerprint（REAL）= bank fingerprint（COPY）= 349a76497c8a5320f822f99809fe9553
```

```text
QUESTION_BANK_COUNT             = 9333
QUESTION_BANK_CONTENT_PRESERVED = YES
NEW_TABLES                      = NONE
NEW_MIGRATION                   = NONE（无 schema 变更；§31 无强制新增索引/列的理由）
```

---

## 17. Tests

新增 `tests/test_exam_practice_records.py`（29 项），覆盖 §33 的 A–S 全矩阵：

| 组 | 覆盖 |
| --- | --- |
| A/B/C | chapter / past-paper / AI-question → `exam_prep` PracticeAttempt + 完整 exam context；三态保持（自评大题 `correct is None`） |
| D/E/F | wrong ACTIVE → RESOLVED → reopen；`wrong_count` 计的是**不同错误作答数**而非投影次数；mirror 重放 3 次 → 1 attempt / 1 事件 / `wrong_count` 不变 |
| G | `exam_11408` 与 `exam_prep` 输入 → 同一 deterministic attempt |
| H | course 与 exam 同 `source_id` 互不串线 |
| I | 两个 module 同题号同年 → 两条独立 wrong state（参数化 4 个 module） |
| J | cs_408 / math_1 / math_2 / math_3 合成 context → 4 个独立 scope，无碰撞 |
| K/L | 事件 `service_key=exam_prep`、`subject_key=cs_408`、module 在 JSON、**无 track**；把 track 塞进 ref context 不改变 scope |
| M/N/O | builder 幂等（id + 内容逐字节相同）、内容更新保 id、消失的题 deactivate 而不删除、survivor 选中 active 行、静态不变式（builder 不得 wholesale delete） |
| P | Free 用户事实全部持久化 |
| Q | AI-question attempt 恰好 1 条 `question_answered`，且无 `course_practice` 事件 |
| R | mirror 不触碰 knowledge 状态（源码 + 行数双重断言）；exam mutation inventory 只有 study-plan 一条 |
| S | 只读复核真实库 9333 / 1923 / 32 + integrity ok |
| E2E | §34 的两条完整链路（chapter 全环 + past-paper 重放幂等） |

对齐更新：`tests/test_wrong_answers.py` 两处 scope 断言改为新形态（其中 past-paper legacy
回填一例显式断言 module 被带出）。

```text
FULL_BACKEND_TESTS = PASS（741 passed / 0 failed；STEP7H1 baseline 712）
```

---

## 18. Full E2E（§34）

**① chapter 全环（Free user, cs_408 / operating_system）**

```text
Free user → chapter practice（答错）
  → PracticeAttempt(exam_prep, static_question_bank, correct=False)
  → WrongAnswerState ACTIVE, wrong_count=1
  → LearningEvent question_answered（service_key=exam_prep, subject_key=cs_408）
  → 再次作答（答对）→ WrongAnswerState RESOLVED（wrong_count 仍为 1）
  → records read model 可见，context = {subject_key: cs_408, exam_module_id: operating_system}
  → knowledge 行数不变（mirror 不写状态）
```

**② past-paper 全环 + 重放**

```text
past_paper_attempts（year=2024, attempt_no=1, module=computer_network）
  → PracticeAttempt(past_exam, source_id=bank PK, context.question_year=2024)
  → WrongAnswerState scope = "subject:cs_408|module:computer_network|year:2024", ACTIVE
  → 重放 3 次 → 1 attempt / 1 事件 / wrong_count 仍为 1
```

无 live provider 调用：本轮全部测试使用本地数据与 FakeProvider（无 AI 调用）。

---

## 19. FINAL GATES

```text
CANONICAL_EXAM_NAMESPACE = exam_prep

CS408_PRACTICE_SHARED_CORE = PASS
CHAPTER_PRACTICE_MIGRATED  = PASS
PAST_PAPER_PRACTICE_MIGRATED = PASS
AI_GENERATED_ATTEMPT_PATH  = PASS

PRACTICE_IDENTITY_REPLAY_SAFE      = PASS
IDENTITY_NAMESPACE_TOKEN_UNCHANGED = YES

PAST_EXAM_IDENTITY_AUDIT     = PASS
PAST_EXAM_WRONG_SCOPE        = PASS
MULTI_SUBJECT_COLLISION_SAFE = PASS

PAST_PAPER_STABLE_KEY            = PASS
PAST_PAPER_BUILDER_DELETE_INSERT = REMOVED
PAST_PAPER_ID_STABILITY          = PASS
PAST_PAPER_BUILDER_IDEMPOTENT    = PASS

QUESTION_BANK_COUNT             = 9333
QUESTION_BANK_CONTENT_PRESERVED = YES

EXAM_WRONG_SHARED_CORE    = PASS
WRONG_REPLAY_DOUBLE_COUNT = NO

EXAM_RECORDS_SHARED_CORE = PASS
EVENT_SUBJECT_KEY        = cs_408
EVENT_MODULE_CONTEXT     = PASS
EXAM_EVENT_DUPLICATION   = NO

EXAM_KNOWLEDGE_UPDATE_EXACTLY_ONCE = PASS
STUDENT_TWIN_ELIGIBILITY_EXPANDED  = NO

FREE_USER_EXAM_FACT_PERSISTENCE = PASS

CROSS_USER_ISOLATION      = PASS
CROSS_NAMESPACE_ISOLATION = PASS
CROSS_MODULE_ISOLATION    = PASS

REAL_APP_DB_MUTATED = NO
NEW_TABLES          = NONE

FULL_BACKEND_TESTS = PASS（741 passed / 0 failed；baseline 712，测试数增长）

STEP7H2_COMPLETE = YES
STEP7H2          = FROZEN
STEP7H3_READY    = YES
```

---

## 19.1 一次观察到的 flaky（如实记录，未隐藏）

首次全量回归出现 **1 failed / 740 passed**：
`tests/test_wrong_answers.py::test_concurrent_wrong_attempts_yield_one_state`
（断言 `wrong_count == 2`，实际为 1）。

诊断：该测试用两个线程并发写同一条题的错答，而 wrong-answer 投影是
**recompute-not-increment** —— 每次写入后从「当前可见的全部 canonical attempts」重算。
两个线程的提交与重算交错时，**最后**一次重算有可能只看到自己那一条，于是状态停在 1
（该题下一次作答时会自然收敛到 2）。这是 STEP7E 冻结的投影语义在并发下的**时序特性**，
不是本轮引入：该测试单独运行稳定通过，且本轮对该路径的改动
（`scope_key` 纯函数、`_adopt_legacy_past_exam_scope` 仅对 `past_exam` 生效）都不在这条链路上。

第二次全量回归：**741 passed / 0 failed**，未复现。记为「pre-existing 时序 flaky，
待后续 STEP 决定是否收敛投影可见性」，本轮不改投影语义。

## 20. 变更文件

```text
[NEW] backend/past_paper_upsert.py           稳定键 reconcile（never delete）
[MOD] backend/chapter_question_upsert.py     加法式扩展（可选 analysis / quality_status / source_ref）
[MOD] backend/learning/practice/adapters/exam.py   cs408_context + exam_* ref context + question_year
[MOD] backend/learning/practice/adapters/course.py AI-question 分岔：exam mode 走 CS408 adapter，ref context 不再写 course_id
[MOD] backend/learning/wrong_answers/project.py    past_exam_scope()（subject|module|year）+ legacy scope 采纳
[MOD] backend/learning/wrong_answers/legacy.py     共用 past_exam_scope，带出 module
[MOD] backend/learning/records/service.py          records 投影暴露 exam_module_id（加法）
[MOD] backend/exam_resources/11408/computer_organization/past_papers/build_…_text.py
[MOD] backend/exam_resources/11408/computer_organization/past_papers/build_…_past_papers.py
[MOD] backend/exam_resources/11408/computer_network/past_papers/build_…_past_papers.py
[MOD] backend/exam_resources/11408/operating_system/past_papers/build_…_past_papers.py
[MOD] backend/exam_resources/11408/computer_network/chapter_practice/build_…_chapter_questions.py
[NEW] backend/tests/test_exam_practice_records.py（29）
[MOD] backend/tests/test_wrong_answers.py（2 处 scope 断言）
```

## 21. 剩余问题（交 H3 / H4 / 后续）

```text
① H3：Exam AI → AIOrchestrator（12 条可达 provider 调用，含 answer.grade 的最终落地；
   _grade_big_question 仍在 parser 内直连 provider，本轮未动）。
② H2 遗留（登记未决）：PATCH /exam/11408/{k}/study-plan/knowledge-items/{code} 仍直写
   user_knowledge_progress，未接 canonical writer —— 需要 writer 支持 exam knowledge 身份。
③ H4：多 track / 多 subject catalog 与真实内容导入（需用户批准）。
④ 部署硬化：14 张 exam 表仍无 Alembic 覆盖（D7）。
⑤ D5：exam_favorite_questions_v2 死表仍 DELETE-LATER（本轮未 drop）。
⑥ Parser Infra：OCR 全路径不计费/不记录（D8）。
```

---
---

# H2-C1 · WRONG PROJECTION CONCURRENCY CLOSURE

> §19.1 的 flaky 记录**保留未删**。本节是它的收尾：先定位真因，再关闭，
> 并以 stress 门禁（而非"再跑一次绿了"）作为 correctness 证据。

## 22. 根因（实测，非推断）

复现工具：一个 200–2500 轮的独立压力探针（每轮两条并发、**不同**的 wrong facts，
完成后用**新 session** 读已提交状态），对 `attempts_for_question` / `_write_projection`
/ verify 读做插桩。

```text
WRONG_CONCURRENCY_ROOT_CAUSE = 两层，实测分离
  (a) 投影的「读事实集合 → 写状态行」不是原子的：
      一个 pass 的读可能早于另一条 attempt 的提交，而**它**又恰好最后写入 →
      状态停在 1。实测 178/200 轮出现混合读集 [1,2]，1/200 轮真的违反不变量。
  (b) flaky 测试本身的 harness 缺陷：
      worker 持有 User ORM 句柄，而 record() 内部多次 commit → expire_on_commit
      使该句柄每次提交后被重新读取，在 SQLite 写竞争下可抛
      ObjectDeletedError → 该轮的 attempt **根本没有落库**，于是状态合法地停在 1。
      旧断言顺序先查 wrong_count、后查 errors，把这个错误**误报**成「stale projection」。
```

**（b）是此前 flaky 的直接原因**：把 `assert errors == []` 提到最前并放大到 2500 轮后，
失败信息明确变成
`round 0: worker error(s) ["ObjectDeletedError: Instance '<User ...>' has been deleted..."]`。
定位后，harness 修复（racer 会话 `expire_on_commit = False`）即消除该噪声。

## 23. 修复（保留 FROZEN 语义）

```text
WRONG_PROJECTION_SEMANTICS = RECOMPUTE-NOT-INCREMENT（未改为 increment）
```

`recompute()` 改为 **compare-and-recompute**，每个 pass 对自己的读**和**写负责：

```text
1. 读事实集合 → stamp = 事实集合的 (id…) 有序指纹
2. 写状态行（applied = 本次写入是否真的落地）
3. 用【独立新 session】再读一次事实集合：
     applied 且 stamp 未变  → 收敛，返回
     否则                   → 重做该 pass（上限 MAX_PROJECTION_PASSES = 5）
```

两个此前真实存在的漏洞（本次由分析+实测确认，非猜测）：

```text
① 并发首插竞态：两个 pass 同时发现「无状态行」→ 同时 INSERT → 一个被唯一约束拒绝。
   旧代码在 IntegrityError 分支 rollback 后**直接返回胜者的行**，自己刚算出的派生值被
   丢弃 → 败者以「未落地的推导」settle。现返回 applied=False，强制重做（此时行走 UPDATE）。
② verify 读会拿到陈旧快照：旧代码在 commit 后用同 session 的 refresh+SELECT 校验，
   而该 SELECT 可能落在 refresh 打开的事务快照里 → 期间提交的 attempt 不可见 →
   陈旧的 pass 自我「验证通过」。现 verify 走**独立 session**，读到的一定是已提交状态。
```

未做（明确禁止项）：blind increment、全局锁、新业务表、改 Wrong semantics、
改 attempt identity。SQLite 语义下正确，且不依赖任何单进程假设（无进程内锁）。

## 24. STRESS 门禁

`tests/test_wrong_answers.py`：

```text
test_concurrent_wrong_attempts_yield_one_state   → 50 轮 × 每轮两条并发不同 wrong facts
   每轮断言：errors == []（先）+ 恰好 1 条状态 + wrong_count == 2
test_concurrent_replay_of_one_fact_stays_one     → 同一 durable fact 并发镜像 → 1 attempt / wrong_count 1
test_concurrent_wrong_then_correct_resolves_with_full_count
                                                 → wrong A + wrong B + correct C → RESOLVED, wrong_count 2
```

连续批次（每批 50 轮/次 × N 次）：

```text
修复前：5/40 runs 失败（2000 轮）
修复后：0/40 runs（2000 轮）；0/60 runs（3000 轮，见 §26 最终记录）
```

```text
WRONG_CONCURRENCY_ROOT_CAUSE      = VERIFIED（两层，均已定位）
WRONG_CONCURRENT_DISTINCT_FACTS   = PASS
WRONG_REPLAY_IDEMPOTENT           = PASS
WRONG_CONCURRENCY_STRESS          = PASS
```

## 25. 术语更正（§13/§19 的模糊表述）

```text
EXAM_PRACTICE_KNOWLEDGE_SIDE_EFFECT_DUPLICATION = NO
EXAM_KNOWLEDGE_CANONICAL_WRITER_CONSOLIDATED    = NO
```

`PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}` 仍**直写**
`user_knowledge_progress`、**未接** canonical writer —— 它属于后续
Exam knowledge consolidation，**不是 H2 已完成能力**。该项**不阻断 H3**。

## 26. H2 冻结恢复

原 §19/§21 的 gate 保持不变，另加：

```text
WRONG_CONCURRENCY_STRESS = PASS
STEP7H2 = FROZEN（恢复）
STEP7H3_READY = YES
```

```text
FULL_BACKEND_TESTS = PASS（见 STEP7H3 报告 §18 的最终回归）
```
