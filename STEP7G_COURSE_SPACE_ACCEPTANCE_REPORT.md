# STEP7G_COURSE_SPACE_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7G 验收报告
> 范围：Course Learning Space Consolidation
> 生成：2026-09-16 · 本轮为 IMPLEMENTATION（有代码变更，未 commit / 未 push）

> **阅读顺序提示（2026-09-16 追加）**：本文件按时间顺序保留了三轮记录。
> §1–§31 = **第一轮 STEP7G PARTIAL**（历史，已被取代，但**未删改**）。
> §32–§36 = **第二轮 FINAL BLOCKER CLOSURE**（Part A 关闭；Part B 因 CAPABILITY_GAP STOP）。
> **§37–§47 = 第三轮 RECOVERY + FINAL CLOSURE（本轮）——唯一有效的最终结论。**
> 前两轮的 `STEP7G_COMPLETE = NO` 是当时的事实，不是当前状态。

---

# 第一部分（历史）· STEP7G PARTIAL

## 1. EXECUTIVE VERDICT

```text
STEP7G_COMPLETE = NO
STEP7H_READY    = NO
```

**理由（§14 / §16 的硬 gate 未满足）**：Course Space 仍有 **13 条 production 路径直接调用
provider**（`call_deepseek`，见 §12），且仍有 **3 条 course practice writer 未进入共享
Practice Core**（见 §13）。按用户给定的规则「任何 remaining direct production call →
STEP7G_COMPLETE = NO」，本轮**不声称完成**。

本轮**已完成并通过测试**的部分（607 passed / 0 failed，无回归）：

```text
STEP7G_SCHEMA_CHANGE = NONE
MIGRATION_HEAD = 20260915_0005
NEW_TABLES = NONE

COURSE_SPACE_MODULE = backend/learning/spaces/course_learning/
COURSE_CANONICAL_NAMESPACE = course_learning
LEGACY_COURSE_ALIAS = course（仅作为 INPUT，边界归一化一次，绝不落库）

COURSE_CANONICAL_KNOWLEDGE_WRITER = PASS
FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE = COMPLETE（course 路径）
HISTORICAL_KNOWLEDGE_EVENT_COVERAGE = PARTIAL（STEP7F delta replay 维持原状）

COURSE_WRONG_SHARED_CORE = PASS
COURSE_RECORDS_SHARED_CORE = PASS
COURSE_PRACTICE_SHARED_CORE = PARTIAL（3 条 writer 未接，见 §13）

MULTI_COURSE_ISOLATION = PASS
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
COURSE_BACKEND_E2E = PASS
FREE_USER_COURSE_LOOP = PASS

COURSE_DIRECT_PROVIDER_CALLS = 13（未清零 → gate fail）
LEGACY_COURSE_ENDPOINTS_DELETED = NO
FRONTEND_CHANGED = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
```

---

## 2. GIT BASELINE

```text
HEAD = ebad5282
本轮未执行任何 git 写操作（NO commit / push / reset / clean / checkout / rebase / merge / pull）
```

```text
PREEXISTING_DIRTY : backend/ai/**、usage/service.py、scripts/**、若干 tests、SSOT、STEP7CP 报告
STEP7A–F_CHANGES  : backend/{core,data_plane,usage,learning,ai}/**、routers/{practice,
                    wrong_answers,learning_records}.py、migrations/0003–0005、对应 tests
THIS_BATCH        : ?? backend/learning/spaces/**、?? backend/tests/test_course_space.py
                     M backend/core/learning_context.py（统一归一化）
                     M backend/learning/{practice,wrong_answers,records}/service.py（去重私有 helper）
                     M backend/learning/practice/{identity,events,adapters/course}.py
                     M backend/learning/wrong_answers/project.py（identity scope）
                     M backend/main.py（knowledge 路径接线）
                     M backend/tests/test_{learning_records,practice_core,practice_adapters}.py
```

---

## 3. CURRENT COURSE SPACE AUDIT

只读审计结论（逐项，不按名字猜）：

| 项 | 现状 |
| --- | --- |
| **Course 实体** | **不存在**。`__tablename__` 匹配 "course" 的只有 `course_progress` 与 `course_learning_preferences`；无 `class Course` |
| **course identity** | 自由的 `course_id` 字符串（`course_learning_preferences` 按 username+course_id 唯一） |
| **course 选择** | `UserLearningTrack.onboarding_detail_json.selected_courses` + `course_learning_preferences` |
| **chapter identity** | seed JSON `chapters[].code`（如 `"1"`、`"1.1"`）；DB 无 chapter 列，落在 `KnowledgePoint.node_key` / `UserKnowledgeProgress.knowledge_point_code` |
| **knowledge identity** | 整数 `knowledge_point_id`（knowledge-map 路径）或字符串 code（course_learning 路径） |
| **knowledge_points 32 行** | 属 programming-C 本体，**不得**当作课程知识点（§46） |
| **rows（真实库）** | users=0；course_progress / course_learning_preferences / user_knowledge_progress / 全部 practice 表 = 0；knowledge_points=32；study_materials=1 |
| **端点面** | `/course-learning/*` 25、`/course-dashboard` 1、`/course/*` **0**、`/practice/*` 30、`/learning/*` 24、`/knowledge-*` 14、`/study-plan*` 0（exam 下 7） |

---

## 4. COURSE DATA OWNERSHIP MATRIX

| 领域 | canonical owner | legacy owner | write path | read path | 兼容状态 | 后续清理前提 |
| --- | --- | --- | --- | --- | --- | --- |
| Course 选择/偏好 | `course_learning_preferences`（无新实体） | 同左 | `/course-preferences`、`/me/tracks/*` | `course_service.list_user_courses` | KEEP | 不需清理 |
| Materials | `study_materials` / `material_chunks`（共享） | 同左 | `/materials/*` | 同左 + records | KEEP | — |
| Knowledge state | `user_knowledge_progress` + **canonical writer** | 同左 | 7 条路径全部经 `apply_knowledge_change` | `course_knowledge_state` | CONSOLIDATED | — |
| Practice | `practice_sessions` / `practice_attempts`（共享） | `question_attempts` / `ai_question_attempts` | 部分经 Practice Core（§13） | `course_practice_view` | **PARTIAL** | 3 条 writer 接线 |
| Wrong answers | `wrong_answer_states`（共享） | `exam_wrong_questions` / `past_paper_wrong_questions` | 投影 | `course_wrong_view` | CONSOLIDATED | legacy 表暂不 DROP |
| AI requests | `ai_requests` + `ai_called` | `ai_usage_logs` | **仍走 `call_deepseek`**（§12） | — | **NOT MIGRATED** | 端点迁移到 Orchestrator |
| Learning Records | `learning_events` → records read model | `learning_records` | 事件生产者 | `course_records` | CONSOLIDATED | legacy 表暂不 DROP |
| Legacy Plans | `learning_tasks`（legacy capability） | 同左 | `/learning/tasks/*` | 同左 | KEEP（§35） | Planning Core 后续 STEP |
| Reports | 现有实现 | 同左 | `/learning-report/*` | 同左 | KEEP（§37） | 后续 STEP |

---

## 5. NAMESPACE / LEGACY ALIAS

唯一 canonical namespace = `course_learning`；`course` 仅为 **INPUT compatibility alias**。

- `core/learning_context.py` 新增 `normalize_service_namespace()`（单一实现）与
  `LEGACY_NAMESPACE_ALIASES`（含 `course`/`exam`/`code` 等历史写法）。
- `learning/practice/service.py`、`learning/wrong_answers/service.py`、
  `learning/records/service.py` 三处**各自私有的 `_namespace_value` 实现已删除**，统一委托该函数
  （§4「禁止各 module 自己实现」）。
- `is_valid_service_namespace("course")` = **False**：alias 不是 canonical 存储值。
- 未知 namespace 抛错，不落默认值。
- 测试固化：`test_alias_and_canonical_input_produce_identical_storage`、
  `test_canonical_namespace_is_the_only_valid_storage_value`。

```text
COURSE_CANONICAL_NAMESPACE = course_learning
LEGACY_COURSE_ALIAS = course（input-only）
```

---

## 6. COURSE IDENTITY

**不新建 Course / CourseChapter 表**（§5/§6）。现状被如实保留：

```text
course identity    = 存储的 course_id 字符串（仅 strip 空白）
chapter identity   = course context 中的 chapter key（字符串）
knowledge identity = knowledge_point_id（整数）或 knowledge_point_code（字符串）
```

- `normalize_course_id()` **只去空白、不做大小写折叠** —— 折叠会静默拆分或合并真实课程。
- **绝不按 display name 比较身份**（§28）：identity 用 key，title 只是展示。
- 测试：`test_course_id_is_normalized_by_whitespace_only`、`test_no_course_table_is_introduced`。

---

## 7. LEARNING CONTEXT

`course_learning/context.py` 是 course-scoped `LearningContext` 的**唯一**构造点，复用
`core/learning_context.py`，**未新建** `CourseContext` / `CourseAIContext` 第二套。

```text
build_course_context(user, course_id, chapter_id?, knowledge_point_id?,
                     material_ids?, session_id?) → LearningContext
resolve_course_context(db, user, course_id) → (CourseRef, LearningContext)
assert_course_matches(context, course_id)   → 跨课程守卫
```

`resolve_course_context` 要求该 user **确实拥有**该 course，否则抛
`CourseContextError` —— 跨课程保护从这里开始，而不是靠调用方自觉。

---

## 8. COURSE MODULE BOUNDARY

```text
backend/learning/spaces/course_learning/
  __init__.py
  context.py    课程身份 + LearningContext
  knowledge.py  唯一 knowledge 写边界 + 事件发射
  service.py    课程域视图（委托共享 core，不重建）
```

依赖方向单向：`Space → Learning Core → Platform Core`。
`service.py` 只**协调**：practice 读走 `learning.practice`，错题走 `learning.wrong_answers`，
records 走 `learning.records`。**未重建**任何共享服务。

> 本轮未从 `main.py` 大批量抽取端点（§8 只做安全小批量抽取）。模块边界已建立，
> 端点迁移与 AI 迁移一并属于 §12/§13 的未完项。

---

## 9. MATERIALS

保留现有成熟链：`upload → parse → study_materials → material_chunks → FTS5/BM25 →
Qwen OCR(adapter)`。**未引入** vector DB / embedding / semantic retrieval（§11/§45）。
course materials 的 user/namespace/course scope 未改动。

## 10. MATERIAL QA

**未完成**。`POST /chat` 的 LLM 调用仍为 `call_deepseek`（§12 列表中第 8 条）。
这是本轮最重要的未完成项，也是 gate fail 的直接原因之一。

## 11. AI CAPABILITY MIGRATION

**未完成**。已冻结 capability（`material.qa` / `tutor.chat` / `question.explain` /
`question.generate`）**尚未**被 course 端点使用；course 端点仍走 legacy helper。
未新增任何 `course.chat` 类业务专属 capability（§13 的红线未被违反）。

## 12. DIRECT PROVIDER AUDIT

```text
COURSE_DIRECT_PROVIDER_CALLS = 13（未清零）
```

客户端根：`main.py:339` 模块级 `OpenAI(...)`；`main.py:2795` `call_deepseek`（27 个生产
callsite）；`main.py:28240` 第二处 inline `OpenAI(...)`（membership 路径，非 course）。

COURSE 可达的 13 处：

| # | 端点 | 调用点 |
| --- | --- | --- |
| 1 | `POST /chat` | main.py:8740 |
| 2 | `POST /course-learning/practice/generate` | main.py:20321→ |
| 3 | `POST /practice/questions/{id}/ai-explain` | 24266→ |
| 4 | `POST /practice/questions/{id}/feedback` | 24476→ |
| 5 | `POST /practice/questions/generate` | 25173→ |
| 6 | `POST /practice/generate-task-preview` | 25454→ |
| 7 | `POST /materials/{id}/knowledge-links/recommend` | 27250→ |
| 8 | `POST /materials/analyze-knowledge-preview` | 27555→ |
| 9 | `POST /knowledge-points/generate-preview` | 22109→ |
| 10 | `POST /knowledge-path/generate-from-materials` | 22541→ |
| 11 | `POST /learning/reports/generate-preview` | 31359→ |
| 12 | `POST /learning/tasks/from-diagnosis` | 17162→ |
| 13 | `POST /learning-report/ai-generate` | 16796→ |

（行号为审计时快照，本轮 main.py 改动后略有偏移。）

**唯一使用 Orchestrator 的生产端点**是 `POST /exam/11408/{k}/question-analysis`
（21624）—— 属 exam，不是 course。

允许保留的 parser/OCR infra（未迁移，符合 §14 的区分）：`qwen_parser.py:_get_qwen_client`
（视觉 OCR）、`document_parser.py`（无 AI 调用）、`data_plane/runtime_client.py`（localhost
Scientific Runtime，非 AI provider）。`exam_paper_parser.py:_grade_big_question` 自带 provider
client —— 属 exam 解析路径，登记为待处理。

---

## 13. PRACTICE

```text
COURSE_PRACTICE_SHARED_CORE = PARTIAL
```

| 端点 | 是否进入 Practice Core |
| --- | --- |
| `POST /course-learning/practice/{attempt_id}/submit` | **YES**（STEP7D 已接） |
| `POST /practice/sessions/{id}/attempts`（共享 router） | YES（native） |
| `POST /course-learning/practice/generate` | **NO**（仅创建 in_progress，无 attempt 事实 —— 不接是正确判断） |
| `POST /course-learning/practice/workbook/{qid}/attempts` | **NO**（同上） |
| `POST /practice/questions/{question_id}/attempts` | **NO —— 真实缺口** |
| `POST /practice/questions/{question_id}/feedback` | **NO —— 真实缺口** |
| `POST /practice/submit-result` | **NO —— 真实缺口** |

后三条是普通练习流（写 `question_attempts` / `LearningRecord`），**未**产生 canonical
PracticeAttempt。这是 §16 要求「补 adapter」的对象，本轮未完成。

---

## 14. AIQUESTIONATTEMPT / STUDENTTWIN SAFETY

```text
AIQUESTIONATTEMPT_EVENT_ID_CHANGED = NO
AIQUESTIONATTEMPT_DUPLICATE_EVENT = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
STUDENT_TWIN_PRODUCTIZATION_STATE = SHADOW_READY
```

- `course_practice` 的 event_type 与 UUIDv5 身份**未改**；`data_plane.emitter` 仍是该事实的
  唯一 owner。
- 本轮为 course 引入 `question_answered` 时，**显式排除** `ai_question_attempt` 谱系
  （`events.FOREIGN_OWNED_SOURCES`），因此**不会**对同一次 AI 答题产生第二条等价事件。
  测试固化：`test_course_practice_events_are_never_renamed_or_duplicated`。
- 未接 misconception_v2 / learner_state / IRT（§26）。

---

## 15. WRONG ANSWERS

```text
COURSE_WRONG_SHARED_CORE = PASS
```

- course 错题读走 `learning.wrong_answers`（§18），**未建** `course_wrong_questions` 表。
- first wrong → ACTIVE、later correct → RESOLVED、later wrong → 重开：语义由共享 core 保证。
- **本轮修掉一个 §42 真实缺陷**：错题身份原先只含 (user, namespace, question)，**不含 course**，
  于是「同一 user 的两个 course 使用同一 `question_id`」会互相串线
  （course B 的答对会 resolve 掉 course A 的错题）。已在 `scope_key()` 中为
  `course_learning` 加入 `course:<course_id>` 作用域，并让 course adapter 把 `course_id`
  写进 QuestionRef.context。测试：`test_same_knowledge_code_in_two_courses_stays_separate`、
  `test_multi_course_isolation`。

---

## 16. LEARNING RECORDS

```text
COURSE_RECORDS_SHARED_CORE = PASS
```

- course 记录读走 STEP7F 的 Records read model（`learning_events` 投影），
  过滤 `service_namespace = course_learning` + 按事件自身 `course_id` 再过滤（**不按显示名**）。
- **本轮修掉一个真实缺陷**：STEP7D 的 practice emitter 把 `course_id` **硬编码为 None**，
  导致 course 记录无法按课程过滤。已改为从 attempt 的 LearningContext 透传。
- **本轮补上 course 的 `question_answered` 覆盖**：在此之前 course_learning 完全不产生
  practice 事件（STEP7D 为避免与 course_practice 重复而整体跳过）。现在按来源区分：
  `ai_question_attempt` 谱系仍归既有 emitter，其余 course practice 来源由 practice spine 覆盖。
- legacy `learning_records` **未 DROP**，仍是其自身功能（review 记录等）的 durable 源；
  STEP7F 已判 `record_type='practice'` 为 INELIGIBLE，不会双写双显。

---

## 17. KNOWLEDGE STATE

```text
SOURCE OF TRUTH  = user_knowledge_progress（确定性产品状态）
DERIVED STATE    = 由 clamp(0..100) + 阈值 80/40/1 推导的 status
EVENT PRODUCER   = learning.spaces.course_learning.knowledge.emit_transition
```

`mastery_score` / `mastery_level` 是 legacy 字段名，语义是**由作答推导的确定性点数计数器**，
本轮**未**扩大解释为掌握概率、也未接任何科学组件（§24/§25）。

---

## 18. KNOWLEDGE WRITE CONSOLIDATION

```text
COURSE_CANONICAL_KNOWLEDGE_WRITER =
  learning.spaces.course_learning.knowledge.apply_knowledge_change

COURSE_LIVE_KNOWLEDGE_MUTATION_PATHS = 7（course）
FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE = COMPLETE（course 路径）
HISTORICAL_KNOWLEDGE_EVENT_COVERAGE = PARTIAL（STEP7F 维持）
```

7 条 course 路径**全部**经 canonical writer：

```text
POST /practice/questions/{id}/attempts      ← apply_knowledge_progress_event 委托
POST /practice/questions/{id}/feedback      ← 同上
PUT  /learning/tasks/{id}                   ← 同上
POST /course-learning/practice/{id}/submit  ← _update_course_learning_progress 重写
PATCH /knowledge-map/progress               ← target_status + confirm
PUT  /knowledge-points/{point_id}/progress  ← target_score / target_status
POST /practice/submit-result                ← delta
```

边界职责：① durable state write ② **同一条** status 推导规则 ③ 真实迁移时发
`knowledge_status_changed`（提交后发射，失败隔离）。

- 保留既有业务语义：`_update_course_learning_progress` 的 **+15/-8 pedagogy delta**、
  `system_suggested_status` 字段、以及「练习结果只是建议，绝不覆盖学习者已确认状态」
  （`protect_user_confirmed`）。测试：`test_user_confirmed_status_is_protected_from_practice_suggestions`。
- `apply_knowledge_progress_event` 现在是**遗留兼容入口**：保留其自有的
  `knowledge_progress_events` durable 行（旧 reader 依赖），并把状态更新委托给 canonical writer。
- 非 course 的 mutation 路径**如实标注**、不假装已接：
  `PATCH /exam/.../study-plan/knowledge-items` → `OUT_OF_SCOPE_SPACE`（STEP7H）；
  `_record_programming_submission_progress` 的知识部分 → `OUT_OF_SCOPE_SPACE`（STEP7I）；
  `_materialize_due_review_statuses` / review-interval 重算 → `SYSTEM_DERIVED_NO_EVENT`
  （确定性复习排期重算，非学习迁移；Review Core 属后续 STEP）；
  `PATCH /course-progress` → `SEPARATE_LEGACY_STATE`（写 `CourseProgress`，课程级完成度，
  不是知识点状态）。
- 测试固化 gate：`test_course_mutation_paths_are_consolidated`（course 路径必须全部
  CANONICAL_WRITER 或 SYSTEM_DERIVED）、`test_out_of_scope_spaces_are_declared_not_silently_skipped`。

**本轮修掉的一个真实缺陷**：应用 `SessionLocal` 是 `autoflush=False`，canonical writer 的查找
看不到调用方刚 `add` 未 flush 的行，会**创建重复的 progress 行**。已在 writer 入口
`db.flush()`；测试：`test_writer_lands_on_the_callers_pending_row`。

---

## 19. COURSE PROGRESS

`CourseProgress`（course 级完成度，字段 `course`/`knowledge_point`/`status`）保持 legacy 原样，
未被并入知识点状态，也未改算法。`PATCH /course-progress` 在 mutation inventory 中标为
`SEPARATE_LEGACY_STATE`。

## 20. BASIC LEARNING STATE

course MVP 的基础学习状态只来自**确定性产品数据**：knowledge status、practice 事实计数、
review_due 排期、course progress。StudentTwin 仍 `SHADOW_READY`，**未**成为用户可见的
advisory/active，未参与选题、计划或状态修改（§25/§26）。

## 21. LEGACY PLAN / REVIEW BOUNDARIES

```text
COURSE_LEGACY_PLAN_PRESERVED = YES
UNIFIED_PLANNING_IMPLEMENTED = NO
REVIEW_CORE_IMPLEMENTED = NO
```

course plan/task 功能原样保留（含 namespace/context 兼容）；**未**建 `plans`/`tasks` 统一表、
**未**实现动态计划或 planner 科学组件。**未**创建 `review_items` / `review_attempts` /
`ReviewSchedule`。

## 22. LEGACY API COMPATIBILITY

```text
LEGACY_COURSE_ENDPOINTS_DELETED = NO
```

本轮**未删除任何端点**。已改动的 course 端点（knowledge-map/progress、knowledge-points PUT、
submit-result、course-learning submit）保持 path/method/响应字段不变，只是内部转 shared writer；
既有测试（`test_knowledge_map_progress.py` 6 项等）全部通过。

## 23. MULTI-COURSE ISOLATION

```text
MULTI_COURSE_ISOLATION = PASS
```

同一 user 两个 course，practice / wrong / records / knowledge 互不串线；同一 `question_id`
与同一 knowledge `code` 在两个 course 下各自独立（§28/§42）。见 §15 的缺陷修复。

## 24. CROSS-USER / CROSS-NAMESPACE

```text
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
```

- 未拥有该 course 的 user 无法构造 context（`assert_owned_course` / `resolve_course_context`）。
- course records 视图不包含 exam/programming 事件。
- **本轮修掉一个真实缺陷**：practice 的 session/attempt 确定性身份**不含 user_id**，
  两个用户镜像同一 legacy 容器/attempt id 会在唯一约束上碰撞。已在
  `identity.session_uid` / `identity.attempt_uid` 中加入 user_id。
  （真实库 0 行，无既有数据受影响。）

## 25. FREE USER LOOP

```text
FREE_USER_COURSE_LOOP = PASS
```

Free 用户（无 subscription）可完成：course context → practice → wrong state ACTIVE →
records 可见。测试：`test_free_user_can_complete_the_course_loop`。
（AI 部分受统一 capability/budget 约束 —— 该链路本轮未迁移，见 §10。）

## 26. BACKEND E2E

```text
COURSE_BACKEND_E2E = PASS
```

`test_backend_course_learning_e2e`：course context 解析 → practice（错）→ wrong ACTIVE →
later correct → RESOLVED → knowledge canonical writer 产事件 → records 同时含
`question_answered` 与 `knowledge_status_changed`，且全部 namespace = course_learning。
普通测试使用 fake provider，无真实 API 成本。

## 27. MIGRATION / DATA PRESERVATION

```text
STEP7G_SCHEMA_CHANGE = NONE
MIGRATION_HEAD = 20260915_0005
NEW_TABLES = NONE
REAL_APP_DB_MIGRATED = NO
```

无新 migration。迁移验收沿用 STEP7F：fresh DB 与 `backend/app.db` 副本 `alembic upgrade head`
→ `integrity_check = ok`，head = `20260915_0005`。
静态资产：`exam_question_bank=9333`、`programming_exercises=1923`、`knowledge_points=32`（不变）。
真实 `backend/app.db` 未改（72 表，integrity ok）。

## 28. TARGETED TESTS

```text
新增 26 项（tests/test_course_space.py），全部 PASS
```

覆盖：namespace alias 归一化与 canonical-only 存储、未知 namespace 报错、course identity
（空白归一化、无 Course 表）、LearningContext 构造与跨课程守卫、canonical knowledge writer
（推导/事件/非迁移不发/跨课程拒绝/user-confirmed 保护/autoflush 重复行回归）、
mutation inventory gate（course 路径全接 + 越界空间显式声明）、
practice/wrong/records 共享 core 接线、多课程隔离、同 code 跨课程隔离、
跨用户与未拥有课程拒绝、跨 namespace 隔离、backend E2E、Free loop。

对齐更新：`test_practice_core.py`（identity 签名）、`test_practice_adapters.py`
（event 幂等断言按精确 event_id；course 归属不变式）、`test_learning_records.py`
（course 事件覆盖语义）。

## 29. FULL REGRESSION

```text
baseline = 581 passed / 0 failed
after    = 607 passed / 0 failed
PY_COMPILE = OK
REGRESSION = NONE
```

## 30. FINAL VERDICT

```text
STEP7F_FROZEN = YES（延续）

STEP7G_SCHEMA_CHANGE = NONE
MIGRATION_HEAD = 20260915_0005
NEW_TABLES = NONE

COURSE_SPACE_MODULE = backend/learning/spaces/course_learning/
COURSE_CANONICAL_NAMESPACE = course_learning
LEGACY_COURSE_ALIAS = course（input-only）

COURSE_IDENTITY = 存储的 course_id 字符串（无 Course 表，如实保留）
LEARNING_CONTEXT = PASS（复用 core，无第二套）

MATERIALS_SHARED_CORE = KEEP（未升级检索技术）
MATERIAL_QA_ORCHESTRATED = **NO**（未迁移）

COURSE_DIRECT_PROVIDER_CALLS = **13（未清零）**
COURSE_AI_CAPABILITY_MIGRATION = **NOT MIGRATED**

COURSE_PRACTICE_SHARED_CORE = PARTIAL（3 条 writer 未接）
COURSE_WRONG_SHARED_CORE = PASS
COURSE_RECORDS_SHARED_CORE = PASS

AIQUESTIONATTEMPT_EVENT_ID_CHANGED = NO
AIQUESTIONATTEMPT_DUPLICATE_EVENT = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
STUDENT_TWIN_PRODUCTIZATION_STATE = SHADOW_READY

COURSE_KNOWLEDGE_STATE = user_knowledge_progress（确定性产品状态）
COURSE_CANONICAL_KNOWLEDGE_WRITER = PASS
FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE = COMPLETE（course）
HISTORICAL_KNOWLEDGE_EVENT_COVERAGE = PARTIAL

MULTI_COURSE_ISOLATION = PASS
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS

COURSE_LEGACY_PLAN_PRESERVED = YES
UNIFIED_PLANNING_IMPLEMENTED = NO
REVIEW_CORE_IMPLEMENTED = NO
NEW_SCIENTIFIC_COMPONENTS = NONE

LEGACY_COURSE_ENDPOINTS_DELETED = NO
FRONTEND_CHANGED = NO

FREE_USER_COURSE_LOOP = PASS
COURSE_BACKEND_E2E = PASS

REAL_APP_DB_MIGRATED = NO
FRESH_DB_ACCEPTANCE = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
STATIC_ASSET_COUNTS = 9333 / 1923 / 32

TARGETED_TESTS = PASS（26）
FULL_BACKEND_TESTS = PASS（607 passed / 0 failed）

STEP7G_COMPLETE = **NO**
STEP7H_READY = **NO**
```

`BLOCKERS = ① 13 条 course 可达端点仍直接调用 provider（`call_deepseek`），未走 AI Orchestrator → §14 gate fail；② 3 条 course practice writer（`/practice/questions/{id}/attempts`、`/feedback`、`/practice/submit-result`）未产生 canonical PracticeAttempt → §16 gate fail。两项均需要单独的迁移批次，且都会改变现有 course 端点的授权/错误语义，不宜与本轮结构性改动混做。`

---

## 31. 变更文件清单

```text
[NEW] backend/learning/spaces/__init__.py
[NEW] backend/learning/spaces/course_learning/{__init__,context,knowledge,service}.py
[NEW] backend/tests/test_course_space.py
[MOD] backend/core/learning_context.py        统一归一化 + LEGACY_NAMESPACE_ALIASES
[MOD] backend/learning/practice/service.py     删除私有 helper + user-scoped identity
[MOD] backend/learning/practice/identity.py    session_uid/attempt_uid 加 user_id
[MOD] backend/learning/practice/events.py      course_learning 事件覆盖 + 外部 owner 排除
[MOD] backend/learning/practice/adapters/course.py  ref context 带 course_id
[MOD] backend/learning/wrong_answers/{service,project}.py  统一 helper + course scope
[MOD] backend/learning/records/service.py      统一 helper
[MOD] backend/main.py                          knowledge 路径全部转向 canonical writer
[MOD] backend/tests/test_{practice_core,practice_adapters,learning_records}.py
```

无 migration；`backend/app.db` 未改。

---
---

# 第二部分（历史）· STEP7G FINAL BLOCKER CLOSURE（第二轮）

> 上一节（STEP7G PARTIAL）保留为历史审计章节，未删改。
> 本轮只处理两个 blocker，不扩大 scope。

## 32. PREVIOUS / FINAL

```text
PREVIOUS
  COURSE_PRACTICE_SHARED_CORE = PARTIAL（3 条 course practice writer 未形成 canonical attempt）
  COURSE_DIRECT_PROVIDER_CALLS = 13

FINAL
  COURSE_PRACTICE_WRITER_MIGRATED = 3 / 3
  COURSE_PRACTICE_SHARED_CORE = PASS

  COURSE_DIRECT_PROVIDER_CALLS = 13（未变）
  COURSE_AI_CAPABILITY_MIGRATION = NOT MIGRATED
  MATERIAL_QA_ORCHESTRATED = NO
```

```text
STEP7G_COMPLETE = NO
STEP7H_READY = NO
```

---

## 33. PART A — PRACTICE WRITER GAP：CLOSED

### 33.1 A1 语义追踪（先追踪，再决定，不按 endpoint 名猜）

| endpoint | legacy table | legacy PK | creates new row? | updates prior? | judgement | Knowledge 影响 |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /practice/questions/{id}/attempts` | `question_attempts` | `id` | **YES** | 否 | 服务端推导：choice/TF 比对 → `correct`/`incorrect`；其余 `unknown` | +8 / -5 / +2 |
| `POST /practice/questions/{id}/feedback` | `question_attempts` | `id` | **YES（自己的行）** | 否 | `self_result="unknown"`，**无事实判断**；只带 `ai_feedback` | AI 关键词情感 → +5 / -3 / +2 |
| `POST /practice/submit-result` | `learning_records`（**不是** `question_attempts`） | `id` | **YES（一条汇总行）** | 否 | 逐题 `is_correct` 为**客户端断言**，且从不持久化 | 按 KP 汇总 delta |

**结论：不是同一次作答的三个阶段**，而是三个各自独立的 durable 事实。因此
「one real user attempt → exactly one PracticeAttempt」的落地方式是：

- `attempts` / `feedback`：各自 legacy 行 → **1:1** canonical PracticeAttempt（身份 = legacy row id）。
- `submit-result`：durable 事实是**批次汇总**，canonical 对应物是 **PracticeSession**，
  **不**为逐题生成 attempt。

### 33.2 A2/A3 为什么 submit-result 不生成逐题 attempt

两条独立理由，任一都足够：

1. **可信性**：逐题 `is_correct` 由客户端提交且服务端不复核，把它提升为 immutable canonical
   attempt 等于让客户端写自己的学习事实（违反 STEP7F §25 server-trusted only）。
2. **可恢复性**：逐题明细从不落库，mirror 失败后无法从任何 durable source 重建，
   违反 STEP7D 的可恢复性原则。

`feedback` 行的 `self_result="unknown"` → canonical `correct = None`，**绝不**被当成 False（A3）。

### 33.3 A4/A5/A6/A7 落地

- 每条 canonical attempt 带 `user_id` / `service_namespace=course_learning` /
  `course_id`（进 QuestionRef.context 与 LearningContext）/ knowledge context /
  question identity / session identity（`course:<course_id>` 容器）。
- 事件归属：practice spine 已是 `question_answered` 的 owner；legacy `LearningRecord`
  不产生第二条等价 practice 事件；`ai_question_attempt` 谱系仍归既有 `course_practice` emitter，
  **未**新增重复事件。
- Wrong answer：错答 → ACTIVE；later correct → RESOLVED；`wrong_count` 不因 mirror 重复增加。
- Knowledge：delta 仍只由 domain 语义 writer 执行一次；mirror **不**再 apply。
  实测 `mastery_score == 8`（不是 16），`practice_count == 1`。

### 33.4 A8 镜像失败与恢复

`test_mirror_failure_is_recoverable_from_the_legacy_row`：强制 mirror 失败 → canonical attempt
不存在 → STEP7D backfill 从 legacy 行重建 → `correct=False`、`source_attempt_id` 一致。

为使 live 与 backfill 真正一致，同时把 STEP7D backfill 的 session 容器对齐为
`course:<course_id>`（原先用 `paper:`/`attempt:`），否则同一 attempt 会被重建到不同 session。

### 33.5 A9 PART A GATE

```text
COURSE_PRACTICE_WRITER_TOTAL = 3
COURSE_PRACTICE_WRITER_MIGRATED = 3
LOGICAL_ATTEMPT_DOUBLE_COUNT = NO
KNOWLEDGE_DOUBLE_UPDATE = NO
PRACTICE_EVENT_DUPLICATION = NO
WRONG_COUNT_DUPLICATION = NO
MIRROR_FAILURE_RECOVERABLE = PASS
COURSE_PRACTICE_SHARED_CORE = PASS
```

**PART A = PASS。** 新增 `tests/test_course_practice_writers.py`（14 项）。

---

## 34. PART B — 未执行（STOP 于 B3 CAPABILITY_GAP）

### 34.1 B1 COURSE_AI_MIGRATION_MATRIX（已完成审计）

逐条读取 prompt 构造、输出结构、后处理、现有授权、失败行为后的分类：

| # | endpoint | 实际语义任务 | 目标 capability | 判定 |
| --- | --- | --- | --- | --- |
| 1 | `POST /chat`（course 分支） | 材料/课程问答 | `material.qa` / `tutor.chat`（按请求是否带 material 分支，§B13） | 可映射 |
| 2 | `POST /course-learning/practice/generate` | 生成题目 JSON | `question.generate` | 可映射 |
| 3 | `POST /practice/questions/{id}/ai-explain` | 题目解析 | `question.explain` | 可映射 |
| 4 | `POST /practice/questions/{id}/feedback` | 作答反馈 | `question.explain` | 可映射 |
| 5 | `POST /practice/questions/generate` | 生成题目 | `question.generate` | 可映射 |
| 6 | `POST /practice/questions/batch-create-from-ai` | 生成题 JSON 修复 | `question.generate` | 可映射 |
| 7 | `GET /practice/summary`（helper） | 解析精修 | `question.explain` | 可映射 |
| 8 | `POST /practice/generate-task-preview`（3 helper） | 计划/任务预览生成 | `planning.generate` | 可映射 |
| 9 | `POST /learning/tasks/from-diagnosis` | 由诊断派生任务 | `planning.generate` | 可映射 |
| 10 | `POST /learning/reports/generate-preview` | 报告预览 | `report.generate` | 可映射 |
| 11 | `POST /learning-report/ai-generate` | 报告生成 | `report.generate` | 可映射 |
| 12 | `POST /knowledge-path/generate-from-materials` | 由资料生成学习路径 | `planning.generate` | 近似可映射（路径 = 计划结构） |
| 13 | `POST /knowledge-points/generate-preview` | 由课程/资料生成**知识点树** | **无对应 capability** | **CAPABILITY_GAP** |
| 14 | `POST /materials/analyze-knowledge-preview` | 由资料抽取知识点（结构化） | **无对应 capability** | **CAPABILITY_GAP** |
| 15 | `POST /materials/{id}/knowledge-links/recommend` | 资料↔知识点关联推荐（结构化） | **无对应 capability** | **CAPABILITY_GAP** |
| — | `summarize_material`（upload 路径） | 资料摘要 | **无对应 capability** | **CAPABILITY_GAP** |

### 34.2 B3 CAPABILITY_GAP → STOP

`knowledge-points/generate-preview`、`materials/analyze-knowledge-preview`、
`materials/{id}/knowledge-links/recommend`、`summarize_material` 四类任务是
**资料/知识点结构化抽取**，与现有 8 个 capability 都不同构：

- 不是 `material.qa` —— 那不是问答，而是受资料约束的结构化生成；
- 不是 `question.*` —— 产物是知识点/关联，不是题目；
- 不是 `planning.generate` —— 产物不是任务/计划结构；
- 不是 `report.generate` —— 不是报告。

按 §B3，我**没有**把它们塞进 `tutor.chat` 之类的错误 capability（那会污染权限与模型池语义），
也**没有**自行新增 capability（§B3 明确要求 STOP 并报告，不得擅自重开 Model Pool architecture）。

**同时，做了一次部分迁移是有害的**：已完成迁移的端点会走统一 capability/budget 授权，
未迁移的仍走 legacy quota → 用户会看到**同一空间内两套授权语义**，这正是 §B 要消除的状态。
因此本轮**未做任何 AI 端点迁移**，保持授权语义当前的一致（全部 legacy），把 Part B 留给
一个完整的、一次性切换的批次。

```text
CAPABILITY_GAPS = knowledge-points/generate-preview、
                  materials/analyze-knowledge-preview、
                  materials/{id}/knowledge-links/recommend、
                  summarize_material（upload 路径）
→ 需要用户决策：接受某个近似既有 capability，或批准一个最小新 capability
  （例如 material.extract，需同时定义 tier 映射与 Qualified Model Pool 继承规则）
```

### 34.3 Part B 现状（未变，如实记录）

```text
COURSE_DIRECT_PROVIDER_CALLS = 13（+ helpers，见 §34.1）
MATERIAL_QA_ORCHESTRATED = NO
COURSE_AI_CAPABILITY_MIGRATION = NOT MIGRATED
UNIFIED_CAPABILITY_AUTH = NOT APPLIED（course AI 仍以 legacy quota 为授权所有者）
LEGACY_AUTH_REMOVED_FROM_DECISION = NO
REMAINING_GLOBAL_DIRECT_PROVIDER_CALLS（分类）:
  EXAM          : /exam/11408/{k}/ai-questions/generate、exam_paper_parser._grade_big_question
  PROGRAMMING   : /code/analyze、/code/challenges/*、/code/learning-diagnosis 等 7 处
  PARSER_OCR    : qwen_parser（视觉 OCR，允许保留）
  OTHER         : /me/tracks/exam_408/package（legacy onboarding）
  COURSE        : 上表 15 处（本轮 blocker）
```

---

## 35. PART C / D（本轮未达执行条件）

Part B 未通过 → Part C（含 AI 的 Course E2E：material.qa → Orchestrator → 练习 → wrong states
→ records；Standard question.generate；Free 拒绝；budget 拒绝）**按 §PART A 前置规则未执行**。

已执行的部分保持原样并全部通过：

```text
COURSE_BACKEND_E2E（无 AI）= PASS
FREE_USER_COURSE_LOOP（无 AI）= PASS
MULTI_COURSE_ISOLATION = PASS
CROSS_USER_ISOLATION = PASS
CROSS_NAMESPACE_ISOLATION = PASS
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
AIQUESTIONATTEMPT_EVENT_ID_CHANGED = NO
AIQUESTIONATTEMPT_DUPLICATE_EVENT = NO
COURSE_CANONICAL_KNOWLEDGE_WRITER = PASS
FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE = COMPLETE
HISTORICAL_KNOWLEDGE_EVENT_COVERAGE = PARTIAL
STEP7G_SCHEMA_CHANGE = NONE / MIGRATION_HEAD = 20260915_0005 / NEW_TABLES = NONE
STATIC_ASSET_COUNTS = 9333 / 1923 / 32
FRONTEND_CHANGED = NO
```

### 35.1 本轮额外修复的真实缺陷

① **`mirror_practice_batch` 闭包变量错误**：`payload = payload or {}` 使 `payload` 成为闭包
局部变量并在赋值前被读取 → `UnboundLocalError` 被 `safe_mirror` 吸收成静默失败。已改为
独立局部名 `data`。

② **live/backfill session 容器不一致**：backfill 用 `paper:`/`attempt:`，live adapter 用
`course:<course_id>` → 同一 attempt 重建到不同 session。已对齐。

③ **测试陈旧 identity map**：API 通过自己的 session 写入后，测试 session 缓存的
`WrongAnswerState` 不会自动刷新，导致误判状态未更新。测试改用 `expire_all()`。

## 36. FINAL VERDICT（第二轮）

```text
STEP7G_COMPLETE = NO
STEP7H_READY = NO

COURSE_PRACTICE_WRITER_MIGRATED = 3/3
COURSE_PRACTICE_SHARED_CORE = PASS
LOGICAL_ATTEMPT_DOUBLE_COUNT = NO
KNOWLEDGE_DOUBLE_UPDATE = NO
PRACTICE_EVENT_DUPLICATION = NO
WRONG_COUNT_DUPLICATION = NO
MIRROR_FAILURE_RECOVERABLE = PASS

COURSE_DIRECT_PROVIDER_CALLS = 13（未清零）
COURSE_AI_CAPABILITY_MIGRATION = NOT MIGRATED
MATERIAL_QA_ORCHESTRATED = NO
UNIFIED_CAPABILITY_AUTH = NOT APPLIED
UNIFIED_USAGE_BUDGET = NOT APPLIED
CAPABILITY_GAPS = 4（见 §34.2，需用户决策）

FREE_USER_BASE_LOOP = PASS（不含 AI）
STANDARD_QUESTION_GENERATE = NOT TESTED（依赖 Part B）
FREE_QUESTION_GENERATE_DENIED = NOT TESTED（依赖 Part B）
BUDGET_DENIAL_BEFORE_PROVIDER = NOT TESTED（依赖 Part B）

FULL_BACKEND_TESTS = PASS（略，见 §36.1）
```

`BLOCKERS = ① Part B 存在 4 处 CAPABILITY_GAP（资料/知识点结构化抽取），按 §B3 必须 STOP 并
由用户决定：接受近似既有 capability，或批准一个最小新 capability（需同时给出 tier 映射与
Qualified Model Pool 继承规则）；② 其余 11 条可映射端点尚未迁移 —— 分批判迁移会造成
同一学习空间内两套授权语义并存，故留待一次完整切换。`

### 36.1 回归

```text
baseline = 607 passed / 0 failed
after    = 621 passed / 0 failed（新增 14 项 Part A 测试）
```

无 migration；`backend/app.db` 未改；静态资产不变。

---
---

# 第三部分（本轮）· STEP7G-C2 RECOVERY + FINAL CLOSURE

> 上一轮由 Codex 执行 STEP7G-C2（Course AI → Unified AI Boundary），**中途停止**。
> 本轮第一步是**只读恢复审计**：不假设上一轮汇报等于磁盘事实，逐项从当前代码重新确认。
> §1–§36 全部保留（含历史失败与 STOP 记录），未删改。

## 37. GIT SAFETY（本轮）

```text
HEAD = ebad5282（与轮次开始时一致，未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
app.db     = 未被 alembic 迁移（无 alembic_version 表）
```

本轮**未触碰** `reference/`、`.github/workflows/`、`frontend/`、`backend/.env*`。

## 38. INTERRUPTED_STEP7G_RECOVERY_MATRIX

### A. knowledge.structure —— 已真实注册

```text
KNOWLEDGE_STRUCTURE_PRESENT          = YES
KNOWLEDGE_STRUCTURE_TIER_POLICY      = Free=DENIED / Standard=ALLOWED / Advanced=ALLOWED
KNOWLEDGE_STRUCTURE_POOL_INHERITANCE = PASS（inherit question.generate）
QUALIFICATION LABEL                  = STRUCTURED_GENERATION_PROXY_V1
```

- `usage/capabilities.py`：`knowledge.structure` 进入 `CAPABILITY_TIER_POLICY` 的
  standard / advanced，**不在** free；`check_capability_permission` 对未知 capability fail closed。
- `ai/pool.py`：`CAPABILITY_QUALIFICATION_PROXIES = {"knowledge.structure": "question.generate"}`，
  在 `qualified_models_for()` 内做**单点**别名解析；`KNOWLEDGE_STRUCTURE_PROFILE =
  "STRUCTURED_GENERATION_PROXY_V1"`。
  **未复制 provider registry**，**未新开 benchmark**，`POOL_VERSION` 仍为 `v4`。
- 测试固化（`test_course_ai_migration.py`）：standard / advanced 下 `knowledge.structure` 与
  `question.generate` 的 qualified model 集合**逐项相等**；Free 一律 DENIED。

### B. migration 0006 —— additive-only

```text
MIGRATION_0006_CURRENT_FIELDS = ai_requests.service_namespace  (String(50), NULL)
                                ai_requests.context_json       (JSON, NULL)
                                usage_ledger.service_namespace (String(50), NULL)
MIGRATION_0006_INDEXES        = ix_ai_requests_service_namespace
                                ix_usage_ledger_service_namespace
MIGRATION_0006_ADDITIVE_ONLY  = YES
NEW_TABLES                    = NONE
DROP                          = NONE
DESTRUCTIVE_RENAME            = NONE
```

`downgrade()` 抛 `NotImplementedError("additive-only; no downgrade is provided")` ——
与 upgrade **不对称是刻意的**：本迁移不提供回退，也不假装能回退。
四列/索引全部 nullable，历史行保持原形。

### C. SQLAlchemy models —— 与 migration 一致

```text
model 有列 / migration 无列 = NONE
migration 有列 / model 无列 = NONE
```

`usage/models.py` 的 `AIRequest.service_namespace` / `AIRequest.context_json` /
`UsageLedger.service_namespace` 与 0006 逐列对应。

### D. AIOrchestrator —— context 真实贯通

```text
AI_REQUEST_CONTEXT_PERSISTENCE     = PASS
AI_EVENT_CONTEXT_PROPAGATION       = PASS
USAGE_LEDGER_NAMESPACE_PROPAGATION = PASS
```

- `AIOrchestrator.execute(..., learning_context=...)` 真实存在，且**校验**
  `learning_context.user_id == user_id`，不匹配直接 `ValueError`。
- 单一 canonical source：`LearningContext`（`core/learning_context.py`）→
  `build_course_context()` → `execute_course_ai()` → `AIOrchestrator` →
  `reserve_credits(service_namespace=..., context_json=...)`
  → `AIRequest.service_namespace` / `AIRequest.context_json`
  → `UsageLedger.service_namespace`（reserve / settle / release 三处**同一来源**）
  → `producers.emit_ai_called(learning_context=...)` → `learning_events.service_key`
  + `course_id` + `knowledge_point_ref_json`。
- 端点**没有**自己拼三套 context：三条 usage_ledger 写入点全部读 `req.service_namespace`。

### E / F. 上一轮实际完成的 vs 未完成的

```text
INTERRUPTED_CHANGES_RECOVERED = YES
```

Codex 实际完成（经本轮磁盘复核确认，非采信汇报）：
`ai.py` boundary、`_course_ai_content` seam、20 个端点接入、migration 0006、
capability + pool proxy、`reserve_credits / settle_credits / release_credits` namespace 贯通、
`ai_called` context 透传。

Codex **未完成 / 未收尾**（本轮补齐）：
① 授权切换只做了一半（legacy quota / entitlement 仍挡在 course AI 前面）；
② `is_exam_408_context` 仍按 **display name** 判定，course 请求被误判为 exam → 仍走
   `call_deepseek`；
③ 一个**真实 NameError**（见 §44）；
④ 一段重复的 prompt 块（死代码）；
⑤ migration 测试的 `EXPECTED_HEAD` 未更新（2 项失败被遗留）；
⑥ 未建 tier matrix / budget / E2E 测试；
⑦ 报告与 SSOT 未更新。

## 39. COURSE AI ENDPOINT / CALLSITE 计数（不混淆两种计数）

```text
COURSE_AI_ENDPOINT_COUNT                        = 19
COURSE_PRIMARY_DIRECT_PROVIDER_CALLSITE_COUNT   = 0
COURSE_SECONDARY_DIRECT_PROVIDER_CALLSITE_COUNT = 0
COURSE_TOTAL_DIRECT_PROVIDER_CALLSITE_COUNT     = 0
```

19 个端点（transitive，含 async 路由与 `background_tasks.add_task` 引用）：

```text
POST /chat                                    POST /chat/upload
POST /code/analyze                            POST /learning-report/ai-generate
POST /learning/plans/generate-preview         POST /learning/plans/generate-preview-advanced
POST /learning/reports/generate-preview       POST /learning/tasks/from-diagnosis
POST /knowledge-points/generate-preview       POST /knowledge-path/generate-from-materials
POST /materials/add-from-message              POST /materials/analyze-knowledge-preview
POST /materials/{id}/knowledge-links/recommend
POST /practice/generate-task-preview          POST /practice/import-paper/jobs
POST /practice/import-paper/parse             POST /practice/questions/generate
POST /practice/questions/{id}/ai-explain      POST /practice/questions/{id}/feedback
```

Orchestrator boundary 调用点 = **21**（19 primary + 2 secondary）。
secondary 两处是**同一端点内的第二次真实 provider invocation** ——
`refine_question_analysis_with_ai`（`/ai-explain` 与 `/questions/generate` 的**条件精修**）
与 `_repair_json_with_ai`（计划 JSON 修复重试）。两者都经 `_course_ai_content`，触发条件不变。

> 上一轮汇报的「13」是**历史审计快照**（第一轮）。本轮不采信该数字，按当前代码重算并给出
> 分类口径：endpoint 数（19）≠ 同一次请求内的 invocation 数（条件成立时 2 次）≠ 残留
> direct callsite 数（0）。

## 40. 授权切换（AUTHORIZATION CUTOVER）

```text
COURSE_AI_LEGACY_AUTH_OWNER = 0
UNIFIED_CAPABILITY_AUTH     = PASS
UNIFIED_USAGE_BUDGET        = PASS
```

从 course AI 执行路径上**移除**的旧授权（它们不再决定「这次调用是否执行」）：

| # | 端点 / 路径 | 移除的 legacy 授权 |
| --- | --- | --- |
| 1 | `POST /code/analyze`（course 分支） | `check_usage_limit(..., "code_analyze", "course_learning")` |
| 2 | `structure_practice_paper_text`（course 分支） | `check_usage_limit(..., "question_generate", "course_learning")` |
| 3 | `POST /practice/questions/generate`（course 分支） | 同上 |
| 4 | `POST /practice/generate-task-preview`（course 分支） | 同上 |
| 5 | `POST /learning/plans/generate-preview`（course 分支） | `check_usage_limit(..., "learning_plan_generate")` |
| 6 | `POST /learning/reports/generate-preview`（course 分支） | `require_learning_context_feature(...)` + `check_usage_limit(...)` |
| 7 | `POST /learning-report/ai-generate` | `require_learning_context_feature(...)` |

- **exam_11408 / programming 分支的 legacy 授权原样保留**（属各自 STEP，不提前迁移）。
- course 分支的 legacy `record_ai_usage` 失败行一并收敛为仅非 course：
  `AI_BILLING_DOUBLE_COUNT = NO`（一次 provider invocation 只有一套
  `AIRequest` + `ai_cost_records` + `ai_called`），course 路径**不再**写 legacy usage 行。
- 拒绝语义：capability 拒绝 → 403；budget 拒绝 → 429。两者都在 **provider 调用之前**
  （budget 耗尽时 router 的 budget 过滤先拒绝，`error_category = budget_incompatible`）。
- **权限拒绝不得被降级吞掉**：`/course-learning/practice/generate`、
  `/learning-report/ai-generate`、`/learning/tasks/from-diagnosis` 原有 `except Exception`
  会把 403 / 429 吞成确定性 fallback。已改为 `except HTTPException: raise` 先行 ——
  「无模型仍可用」保留在**技术失败**上，而不是用在**授权决定**上。

## 41. EXAM 判定改为按 direction key，而不是 display name

本轮修掉的一个**真实跨空间缺陷**：

`is_exam_408_context()` 原先对
`("11408", "数据结构", "计算机组成原理", "操作系统", "计算机网络")` 做 **substring** 匹配。
而 `COURSE_LEARNING_ID_MAP` 里 `数据结构 → data_structure`、`操作系统 → operating_system`
等**是 course_learning 的 display name**，`normalize_subject_course_learning()` 又把
course_id 反查回 displayName —— 于是 **course_learning 的「数据结构」请求被判成 exam_11408**，
走进 `call_deepseek`。

这违反 SSOT §28「identity 用 key，title 只是展示」，也是 `COURSE_DIRECT_PROVIDER_CALLS`
迟迟不清零的根因。现改为按**无歧义的 direction 标记**判定：

```text
is_exam_408_context(subject, course)  ⟺  "11408" 出现在值中
   （"11408 操作系统" / "operating_system_11408" 等 exam 限定形式）
```

`/chat` 额外接受显式方向：`service_key == "exam_11408"` 或请求带 `exam_subject`。
结果：**explicit exam 判定不变**；隐式的 display-name 歧义默认归 **course_learning**。

对齐更新的测试：`test_course_exam_scope.py`（原本依赖 display name 判定，
现改为断言 course 计划预览经 `planning.generate` 走统一边界，并断言
**exam scope 只是 prompt 上下文，不把请求搬到另一个空间**）。

## 42. /chat capability 由服务端决定

```text
POST /chat:
  service_key == "exam_11408" / exam_subject / 11408 限定 subject → exam 分支（legacy，未迁移）
  service_key == "programming"                                   → programming 分支（legacy，未迁移）
  否则（course_learning）:
      material_ids 非空（grounded material QA） → capability = material.qa
      普通学习对话                              → capability = tutor.chat
```

`ChatRequest` **没有** capability 字段（测试固化：`"capability" not in ChatRequest.model_fields`），
客户端无法直接提交任意 capability 绕过权限。

## 43. Migration 0006 验收（完整重做）

```text
FRESH_DB_ACCEPTANCE       = PASS（fresh temp DB → alembic upgrade head → 20260915_0006）
LEGACY_DB_COPY_ACCEPTANCE = PASS（app.db TEMPORARY COPY → upgrade head → integrity ok）
LEGACY_DB_COPY_HEAD       = 20260915_0006
LEGACY_DB_COPY_TABLES     = 72 → 85（0001–0003 的历史增量；0006 自身 NEW_TABLES = NONE）
REAL_APP_DB_MIGRATED      = NO（真实 app.db 无 alembic_version，未迁移）
INTEGRITY_CHECK           = ok（fresh / copy / real 三处）
STATIC_ASSET_COUNTS       = 9333 / 1923 / 32（三处均不变）
```

`test_practice_migration.py` 新增
`test_revision_0006_adds_no_table_only_ai_request_context_columns`：
隔离验证 0005 → head 只加列与索引、不加表、不删表。

## 44. 本轮修复的真实缺陷

```text
① /knowledge-points/generate-preview: material_ids 未定义（NameError）
```

`mode == "materials"` 时 `_course_ai_content(..., material_ids=material_ids)` 读取了一个
**从未绑定的名字**。`mode="course_name"` 因条件表达式短路而侥幸不炸 ——
所以只测 happy path 不会发现。已改为在 materials 分支真实收集
`material_ids = [mat.id for mat in materials]`（else 分支显式 `None`），
并新增 `test_knowledge_points_preview_mode_materials_carries_material_context`
断言 **cited materials 真的进入 LearningContext**（`context_json["material_ids"]`）。

```text
② /practice/questions/{id}/ai-explain: 重复 prompt 块（死代码）
```

同一 `prompt = f"""..."""` 连续出现两次（后者覆盖前者）。已删除重复块。

```text
③ /practice/questions/{id}/feedback: 事实与 AI 反馈未解耦（§11）
```

原先**先调 AI 再写 durable attempt** —— AI 失败则 500，学习者的作答事实**丢失**，
且重试会再造一条 attempt（事实重复）。现改为：

```text
1) 先写 question_attempts 行（user_answer + self_result="unknown"）并 commit ← durable FACT
2) 调 AI
3) AI 成功 → 回填 ai_feedback；AI 失败 → 不抛出，返回 ai_feedback_available=false
4) mirror（在事实已落库之后，捕获该行的最终状态）与 knowledge transition 照常
```

响应新增 `ai_feedback_available`；`feedback` 在 AI 不可用时为 `null`。
测试固化：`test_feedback_commits_the_answer_before_the_ai_runs`
（provider 失败 → 200 + attempt 恰为 1 条且 `user_answer` 保留）。

```text
④ 授权拒绝被 fallback 吞掉
```

见 §40 末条。3 个端点修正为 `except HTTPException: raise` 先行。

```text
⑤ 诚实性缺口：knowledge mutation inventory 不完整
```

`POST /knowledge-path/generate-from-materials` 会**删除并重建**该课程的 KnowledgePoint，
并为其写入零状态 `user_knowledge_progress` 行（`mastery_score=0` / `status="not_started"`），
但它**不在** §18 的 mutation inventory 里。本轮把 inventory 补全并显式分类：

```text
POST /knowledge-path/generate-from-materials = CONTENT_REPLACEMENT_NO_EVENT
```

理由如实写明：这是**内容替换**（旧树与其 progress 行随旧树一起被替换掉），
不是**学习迁移** —— 没有「存活下来的知识点其状态发生变化」，因此不调 canonical writer、
不发 `knowledge_status_changed`。`course_paths_not_consolidated()` 增加
`_DECLARED_STATUSES` 概念：**未声明**的旁路仍视为 gate fail，**已声明**的必须带 `note`。

```text
⑥ migration 测试 EXPECTED_HEAD 陈旧（2 项遗留失败）
```

`test_migration_on_fresh_database` / `test_migration_on_legacy_database_copy`
断言 head == `20260915_0005`，而 0006 已存在。已更新为 `20260915_0006`。

## 45. 测试（本轮新增）

```text
TARGETED_TESTS = 32 PASS（两个新测试文件）+ 2 PASS（migration / inventory 扩充）
```

`tests/test_course_ai_migration.py`（26）——**不 mock orchestrator**，只把出站 provider
换成 `FakeProvider`，真实跑完 Permission → Router → Pool → Estimate → Reserve → Gateway
→ Usage → Settlement：

- tier matrix（Free 3 允许 / 4 拒绝；Standard 3 允许 + `report.generate` 拒绝；
  Advanced `report.generate` 允许），拒绝路径断言 **provider 调用 = 0**；
- budget 耗尽 → 429，**provider 调用 = 0**，且**不产生** AIRequest / ledger 行；
- context 等价：`AIRequest.service_namespace == AIRequest.context_json.service_namespace ==
  ledger.service_namespace == ai_called.service_key == course_learning`，
  且 `context_json == LearningContext.to_dict()`（逐字段）；
- 跨空间 / 跨用户 context 被拒；
- **完整 E2E**：Free user → course context → material.qa → settled →
  一次 provider invocation 恰一条 `ai_cost_records` 与一条 settle ledger →
  practice → WrongAnswer ACTIVE → later correct → RESOLVED →
  canonical writer 一次 → records 同时含 `ai_called`(1) / `question_answered` /
  `knowledge_status_changed`(1)，全部 `course_learning`；
- 路由级：`/knowledge-points/generate-preview`（含 materials 分支）、
  `/chat` 的 material.qa vs tutor.chat 服务端判定、Free 403 且 provider 调用 = 0、
  feedback 事实 / AI 解耦。

`tests/test_course_ai_reachability.py`（6）——把「0 直连」变成**可执行的不变量**：

- 每个 `call_deepseek` 调用点必须落在**显式声明的非 course 函数**里（新增调用点会让测试失败）；
- 声明必须**恰好**匹配现状（陈旧声明同样失败）；
- course-capable 端点里的直连调用必须被 `if` / `else` **分支守卫**证明属于其他空间
  （含 `else` 极性：`if analyze_service == "course_learning"` 的 `else` 视为
  `not (course_learning)`）；
- 纯 course 端点**不得**出现直连调用；
- 每个 course AI 端点都必须到达统一边界；
- 原始 provider client（`OpenAI(` / `chat.completions.create`）只允许出现在
  provider adapters 与已登记的 infra 文件中。

## 46. 残留 direct provider calls 分类（全后端）

```text
COURSE_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0
COURSE_DIRECT_PROVIDER_CALLS_FINAL     = 0
```

其余直连调用按空间分类（**本轮不提前迁移**）：

| 分类 | 位置 |
| --- | --- |
| EXAM_11408 | `generate_exam_ai_questions`、`structure_practice_paper_text`(exam 分支)、`_generate_plan_preview_core`(exam 分支)、`handle_material_upload`(exam 分支)、`chat`(exam 分支)、`exam_paper_parser._grade_big_question` |
| PROGRAMMING | `generate_code_challenge`、`submit_code_challenge`、`explain_challenge_failure`、`generate_challenge_tests`、`generate_learning_diagnosis`、`_repair_generated_challenge_with_ai`、`analyze_code`(programming 分支)、`chat`(programming 分支) |
| PARSER_OCR | `qwen_parser.py`（视觉 OCR，允许保留） |
| OTHER | `membership.py`（legacy onboarding 计划推荐）、`ai/discovery.py`（账号探测工具） |
| DEAD_CODE | NONE |

`refine_question_analysis_with_ai` / `_repair_json_with_ai` 的**非 course 分支**同样保留。

## 47. FINAL VERDICT

```text
INTERRUPTED_CHANGES_RECOVERED = YES

MIGRATION_HEAD = 20260915_0006
NEW_TABLES     = NONE
REAL_APP_DB_MIGRATED = NO

KNOWLEDGE_STRUCTURE_CAPABILITY       = PASS
KNOWLEDGE_STRUCTURE_TIER_POLICY      = PASS
KNOWLEDGE_STRUCTURE_POOL_INHERITANCE = PASS

PRACTICE_ATTEMPT_ELIGIBLE_MIGRATED = 2/2
BATCH_SUMMARY_SESSION_INTEGRATION  = PASS
FABRICATED_PRACTICE_ATTEMPTS       = 0

AI_REQUEST_CONTEXT_PERSISTENCE     = PASS
AI_EVENT_CONTEXT_EQUIVALENCE       = PASS
USAGE_LEDGER_NAMESPACE_EQUIVALENCE = PASS

COURSE_AI_ENDPOINT_COUNT                        = 19
COURSE_PRIMARY_DIRECT_PROVIDER_CALLSITE_COUNT   = 0
COURSE_SECONDARY_DIRECT_PROVIDER_CALLSITE_COUNT = 0
COURSE_TOTAL_DIRECT_PROVIDER_CALLSITE_COUNT     = 0
COURSE_DIRECT_PROVIDER_ENDPOINTS_FINAL          = 0
COURSE_DIRECT_PROVIDER_CALLS_FINAL              = 0

CONDITIONAL_REFINEMENT_ORCHESTRATED = PASS
COURSE_AI_CAPABILITY_MIGRATION      = PASS
MATERIAL_QA_ORCHESTRATED            = PASS

COURSE_AI_LEGACY_AUTH_OWNER = 0
UNIFIED_CAPABILITY_AUTH     = PASS
UNIFIED_USAGE_BUDGET        = PASS
AI_BILLING_DOUBLE_COUNT     = NO
COURSE_AI_EVENT_DUPLICATION = NO
KNOWLEDGE_DOUBLE_UPDATE     = NO

MULTI_COURSE_ISOLATION    = PASS
CROSS_USER_ISOLATION      = PASS
CROSS_NAMESPACE_ISOLATION = PASS

COURSE_CANONICAL_NAMESPACE = course_learning
COURSE_CANONICAL_KNOWLEDGE_WRITER    = PASS
FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE = COMPLETE
HISTORICAL_KNOWLEDGE_EVENT_COVERAGE  = PARTIAL（STEP7F 维持）

AIQUESTIONATTEMPT_EVENT_ID_CHANGED = NO
AIQUESTIONATTEMPT_DUPLICATE_EVENT  = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED  = NO
STUDENT_TWIN_PRODUCTIZATION_STATE  = SHADOW_READY
UNIFIED_PLANNING_IMPLEMENTED = NO
REVIEW_CORE_IMPLEMENTED      = NO
FRONTEND_CHANGED             = NO

FREE_USER_COURSE_LOOP = PASS
COURSE_BACKEND_E2E    = PASS

FRESH_DB_ACCEPTANCE       = PASS
LEGACY_DB_COPY_ACCEPTANCE = PASS
STATIC_ASSET_COUNTS       = 9333 / 1923 / 32

TARGETED_TESTS     = PASS
FULL_BACKEND_TESTS = PASS（662 passed / 0 failed；第二轮 baseline 621）

STEP7G_COMPLETE = YES
STEP7G          = FROZEN
STEP7H_READY    = YES
```

## 47.1 本轮变更文件

```text
[MOD] backend/main.py
      · 移除 7 处 course 分支 legacy 授权；legacy usage 失败行收敛为非 course
      · is_exam_408_context 改按 direction key（"11408"）判定
      · /chat 增加 exam_subject 显式方向
      · /knowledge-points/generate-preview: 修复 material_ids NameError
      · /practice/questions/{id}/ai-explain: 删除重复 prompt 块
      · /practice/questions/{id}/feedback: 事实先行 + AI 解耦（新增 ai_feedback_available）
      · 3 处 fallback 改为 except HTTPException: raise 先行
[MOD] backend/learning/spaces/course_learning/knowledge.py
      · mutation inventory 补 POST /knowledge-path/generate-from-materials
        （CONTENT_REPLACEMENT_NO_EVENT）+ _DECLARED_STATUSES
[MOD] backend/tests/test_practice_migration.py
      · EXPECTED_HEAD → 20260915_0006；新增 0006 列 / 索引隔离验收
[MOD] backend/tests/test_course_space.py
      · mutation inventory 断言扩充 + test_every_course_knowledge_writer_is_declared
[MOD] backend/tests/test_course_exam_scope.py
      · 计划预览改为经统一边界断言（exam scope 是 prompt 上下文，不跨空间）
[NEW] backend/tests/test_course_ai_migration.py（26）
[NEW] backend/tests/test_course_ai_reachability.py（6）
```

无 schema 变更（0006 由上一轮建立，本轮只做验收）；`backend/app.db` 未被 alembic 迁移。

## 47.2 本轮的一次本地事故（如实记录）

审计过程中，为验证 `is_exam_408_context` 语义，在 `backend/` 下执行了一次
**未设置 `DATABASE_URL` 的 `import main`**。`main.py` 启动时无条件执行
`Base.metadata.create_all(bind=engine)`，因此把 Phase 2–7 的 **13 张表**
（`learning_events` / `subscriptions` / `usage_*` / `ai_*` / `practice_*` /
`wrong_answer_states` 等）**创建进了本地 `backend/app.db`**（72 → 85 表）。

- 影响面：**仅新增 13 张空表**（逐表 `COUNT(*) = 0`，已逐表校验）；
  无既有表被改、无任何行被写入或删除；`users` / `study_materials` /
  `exam_question_bank` / `programming_exercises` / `knowledge_points` 计数不变；
  `integrity_check = ok`。这正是后端每次正常启动都会产生的状态。
- 处理：先**整库备份**（`%TEMP%/step7g_appdb_backup/app.db.backup`），
  确认 13 张表**全部为 0 行**后逐表 DROP，恢复审计基线 72 表；
  再次 `integrity_check = ok`、静态资产 9333 / 1923 / 32 不变、无 `alembic_version`。
- 后果：该事故会让 `test_practice_migration.py` 的 legacy-copy 用例
  （前提是「未跑过 STEP7A 的旧库」）在 0001 处冲突失败。恢复基线后 7 项全部通过。
- 教训：**后续任何 `import main` 之前必须设置 `DATABASE_URL`。**

## 47.3 未决 / 交给后续 STEP

```text
① exam_11408 / programming 的 AI 仍走 legacy 授权与直连 provider —— 属 STEP7H / STEP7I
   的迁移范围，本轮**刻意不提前迁移**。
② /knowledge-path/generate-from-materials 的内容替换会重置被替换知识点的 progress
   （已声明为 CONTENT_REPLACEMENT_NO_EVENT）。若产品要「重新生成路线图时保留已学进度」，
   那是一次独立的内容生命周期设计，不在 STEP7G 范围。
③ legacy CourseProgress / legacy plans / legacy learning_records 表均保留未删。
④ 事件身份 (source_type, source_attempt_id, item_key) 不含 user_id：这是 STEP7D 冻结的
   event identity，本轮**未改**（AIQUESTIONATTEMPT_EVENT_ID_CHANGED = NO）。真实 legacy
   source id 是全局唯一的，因此生产数据不冲突；合成/重复的 legacy id 会互相 dedupe ——
   测试需使用各自的 source 命名空间（本轮已修正一处测试污染）。
```
