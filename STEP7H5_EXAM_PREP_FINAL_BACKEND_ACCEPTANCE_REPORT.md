# STEP7H5_EXAM_PREP_FINAL_BACKEND_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7H5 最终验收报告
> 范围：Exam Prep / CS408 后端最终验收 + 部署加固 + 前端 API 交接
> 生成：2026-09-17 · 本轮为 **IMPLEMENTATION**（有代码变更，未 commit / 未 push）
> 前置：STEP7H0–H4 均已 FROZEN（本轮重新只读复核，结论 = PASS）

---

## 1. Executive Verdict

```text
STEP7H5_COMPLETE = YES
STEP7H5          = FROZEN
STEP7H           = FROZEN
FRONTEND_READY   = YES
```

本轮关闭了三件长期债务，并发现并修复了一个**未被登记的真实隔离缺陷**：

1. **Exam 运行时 schema 终于有了 Alembic 归属**（migration `20260917_0008`）。
   此前 13 张 Exam 运行时表只由 `ensure_*_schema()` 与 `Base.metadata.create_all()` 产生，
   全新部署**无法**仅靠 `alembic upgrade head` 得到可用的 Exam 结构。
2. **前端 API 交接文档落地**（`STEP7H_FRONTEND_API_HANDOFF.md`），后端就此停止扩展。
3. **发现并修复**：`PATCH /knowledge-map/progress` 在 `course_id="<module>_11408"` 时
   ——即 **exam scope**——把考试知识变更记成了 `course_learning` 事件。
   这正是 H1 修过的 D1 类跨空间污染，H4 的 mutation inventory 漏登记了它。已收敛到
   exam canonical writer，并补入 inventory（详见 §12）。

**后端停止继续扩展**：本轮不新增任何产品能力，只做验收 / 加固 / 修复 / 交接。

---

## 2. Git / DB Safety

```text
HEAD = ebad5282（与轮次开始时一致，未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

所有需要模块加载的动作（import main / TestClient / pytest / route introspection）均在显式
`DATABASE_URL=sqlite:///<temp>` 下执行；真实 `backend/app.db` **只用只读 sqlite3**
（`file:…?mode=ro`, `uri=True`）访问，未建 engine、未 create_all、未迁移、未写入。

```text
REAL backend/app.db
  mtime          = 2026-09-16 21:24（本轮为 09-17，未变）
  表总数          = 72（未变）
  alembic_version = 不存在（真实库从未被 Alembic 迁移过）
  exam_prep_profiles = 不存在
  integrity_check = ok
```

```text
REAL_APP_DB_MUTATED = NO
```

**指纹复核**（列集 `id,subject_key,source_type,year,question_number,stem,standard_answer,analysis`，
`\x1f` 连接 / `\n` 分行 / `ORDER BY id`）：

```text
REAL  backend/app.db  H5_BANKSHA256 = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee
LEGACY COPY（upgrade head）        = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee
                                      ↑ 逐字节相同
```

（该值与 H4 报告记录一致，故 H4→H5 题库未变。）

---

## 3. H4 Baseline 复核

```text
H5_BASELINE_RECOVERY = PASS
```

不从上一轮报告采信，逐项从磁盘重新只读复核：

| 复核项 | 磁盘事实 | 结论 |
| --- | --- | --- |
| H0–H4 FROZEN | SSOT §73 状态块 `STEP7H0…STEP7H4 = FROZEN`；CLAUDE.md 已同步 | PASS |
| `0007` 是 migration head（H5 前） | `alembic heads` = `20260917_0007` | PASS |
| H4 tests green | `tests/test_exam_framework.py` 52 passed（在 H5 改动前重跑） | PASS |
| catalog 真实存在 | `learning/spaces/exam_prep/catalog.py` 269 行，`CATALOG_VERSION="v2"`，CONFIG-only | PASS |
| profile 真实存在 | `models.ExamPrepProfile`（models.py:1359）+ migration 0007 + `routers/exam_prep.py` | PASS |
| knowledge writer 真实存在 | `learning/spaces/exam_prep/knowledge.py` 261 行 + `main.py:18531` 路由调用 | PASS |
| 传参一致性 | H1→H2→H3 的 namespace / identity / context 契约未漂移 | PASS |

---

## 4. Exam Runtime Table Audit

### 4.1 方法

不按名字模式猜，**从 exam 路由处理器实际读写的模型反推**，再与真实库、模型声明、Alembic
owner 三方交叉：

- exam 路由块 50 个（`@app.*("/exam…")`）
- 真实库 `backend/app.db` = 72 表
- 模型声明 = 65 表
- Alembic 已覆盖（0001–0007）= 13 表

### 4.2 LEGACY_EXAM_TABLE_ALEMBIC_MATRIX

`migration owner` 列在 H5 **之前**的状态；`H5 action` 是本轮处置。

| table | current model | legacy creation path | row count（real DB） | fresh DB present? | migration owner（H5 前） | schema parity | H5 action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `exam_question_bank` | ExamQuestionBank | `create_all` | **9333** | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_practice_attempts` | ExamPracticeAttempt | `create_all` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_wrong_questions` | ExamWrongQuestion | `create_all` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_question_done_records` | ExamQuestionDoneRecord | `create_all` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_favorite_questions` | ExamFavoriteQuestion | `create_all` + `ensure_exam_favorite_questions_schema` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `past_paper_attempts` | PastPaperAttempt | `create_all` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `past_paper_wrong_questions` | PastPaperWrongQuestion | `create_all` + `ensure_past_paper_wrong_questions_schema` | 0 | 否 | 无 | 列一致；缺 `ix_…_source` | **0008 建 + 补索引** |
| `exam_study_plan_settings` | ExamStudyPlanSetting | `create_all` + `ensure_exam_study_plan_settings_schema` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_study_plan_chapter_practice` | ExamStudyPlanChapterPractice | `create_all` + `ensure_*` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `exam_study_plan_tasks` | ExamStudyPlanTask | `create_all` + `ensure_*` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `ai_generated_questions` | AIGeneratedQuestion | `create_all` + `ensure_ai_generated_questions_schema` | 0 | 否 | 无 | 列/索引一致 | **0008 建** |
| `user_knowledge_progress` | UserKnowledgeProgress | `create_all` + `ensure_user_knowledge_progress_schema` | 0 | 否 | 无 | 列一致 | **0008 建**（SHARED 存储，exam 写） |
| `user_knowledge_review_settings` | UserKnowledgeReviewSetting | `create_all` + `ensure_*` | 0 | 否 | 无 | 列一致 | **0008 建**（SHARED 存储，exam 读） |
| `exam_favorite_questions_v2` | ExamFavoriteQuestionV2 | `create_all` | **0** | 否 | 无 | — | **不建**（DEAD，见 §4.3） |
| `exam_prep_profiles` | ExamPrepProfile | — | 不存在 | **是** | **0007** | — | 已有 owner |
| `knowledge_points` | KnowledgePoint | `create_all` + `ensure_*` | 32 | 否 | 无 | — | SHARED_NOT_EXAM_OWNED |
| `knowledge_progress_events` | KnowledgeProgressEvent | `create_all` + `ensure_*` | 0 | 否 | 无 | — | SHARED_NOT_EXAM_OWNED |
| `material_knowledge_links` | MaterialKnowledgeLink | `create_all` + `ensure_*` | 0 | 否 | 无 | — | SHARED_NOT_EXAM_OWNED |

### 4.3 分类结论

```text
REQUIRED_RUNTIME（exam 直接读写）        = 11
  exam_question_bank / exam_practice_attempts / exam_wrong_questions /
  exam_question_done_records / exam_favorite_questions / past_paper_attempts /
  past_paper_wrong_questions / exam_study_plan_settings /
  exam_study_plan_chapter_practice / exam_study_plan_tasks / ai_generated_questions

COMPATIBILITY_REQUIRED（exam 运行时经共享存储读写）= 2
  user_knowledge_progress（exam knowledge writer 写）
  user_knowledge_review_settings（exam 复习间隔策略读）

DEAD_DELETE_LATER                        = 1
  exam_favorite_questions_v2

SHARED_NOT_EXAM_OWNED                    = 3
  knowledge_points / knowledge_progress_events / material_knowledge_links
```

**D5 `exam_favorite_questions_v2` 复核（§24）**：

```text
rows（real DB）        = 0
运行时代码引用          = 0（唯一出现在 models.py 声明 + 清理/维护脚本的表清单里）
FK 依赖                = 无（真实库中仅其自身索引引用该名）
```

→ 维持 **DELETE-LATER**。**H5 不为它建立 migration coverage，也不 drop 它**。
「表数齐全」不是目标；把它升级成新的 canonical requirement 是错的。

**H5 排除 SHARED_NOT_EXAM_OWNED 的理由**：这三张表属于 course learning / programming
ontology，不由 Exam 拥有；它们的 baseline 属**更广的 legacy baseline**，见 §19 债务 ①。

---

## 5. Migration 0008

```text
file          = migrations/versions/20260917_0008_baseline_exam_legacy_runtime_tables.py
revision      = 20260917_0008
down_revision = 20260917_0007
MIGRATION_HEAD = 20260917_0008
```

**upgrade() 只做两件事**：

- 表**不存在** → `create_table`（含该表全部模型索引）
- 表**已存在** → **原样保留**；只补缺失的模型声明列 / 索引（additive）

**明确不做**：不 DROP、不 rebuild、不重写行、不改 9333 题库、不碰任何 legacy 表定义、
不创建 `exam_favorite_questions_v2`。`downgrade()` = `NotImplementedError`（baseline 性质）。

**0001–0007 未做任何修改**（§10 要求）。本轮全部 migration 硬化只进入 0008。

**同一次 migration 同时支持两种起点**（§9 的最大要求）：

```text
A. fresh empty DB        → 13 张表全部创建 + 索引
B. legacy backend/app.db COPY → 表已存在，原样保留；仅补 past_paper_wrong_questions 的
                                ix_past_paper_wrong_questions_source
```

幂等性：对已在 head 的库再跑一次 `upgrade head` = 无操作，不报错。

---

## 6. Fresh Deployment

```text
FRESH_DB_ALEMBIC_ONLY = PASS
```

完全空的临时 SQLite，**只**执行 `alembic upgrade head`（不先跑 `create_all`）：

```text
head      = 20260917_0008
integrity = ok
表数      = 27
Exam 运行时表 = 13 / 13 全部存在
exam_favorite_questions_v2 = 不存在（正确）
```

进一步证明结构**真的可用**（不经 create_all）：把 engine 绑到该文件，用 ORM 元数据逐表
比对「模型声明列 == Alembic 建成列」，并实际 `query().count()` 读取
`ExamQuestionBank` / `ExamPrepProfile` / `UserKnowledgeProgress` —— 全部成功。

```text
EXAM_SCHEMA_DEPENDS_ON_CREATE_ALL = NO
```

---

## 7. Legacy Upgrade

```text
LEGACY_DB_COPY_UPGRADE = PASS
```

复制 `backend/app.db` 到 temp 后 `alembic upgrade head`：

```text
head      = 20260917_0008
integrity = ok
表数      = 86（72 + 共享/AI 表 + exam_prep_profiles；未减少）
exam_question_bank     = 9333
programming_exercises  = 1923
knowledge_points       = 32
BANKSHA256             = 与真实库逐字节相同
exam_favorite_questions_v2 = 仍在（H5 不 drop）
```

```text
REAL_APP_DB_MIGRATED = NO（真实库未迁移，本轮刻意不动）
```

---

## 8. CS408 Full Backend E2E

```text
CS408_FULL_BACKEND_E2E = PASS
```

覆盖 profile → 科目 → 模块 → 知识 → 章节练习 → 错题 → 纠正 → 记录 → 真题 → 计划 → 报告，
全程 `FakeProvider`，**零 live API**。

| 环节 | 验证 |
| --- | --- |
| profile | `PUT /exam/prep/profile` → `selected_track=cs_408`、`selected_subjects`、`target_exam_year` 往返一致 |
| catalog | `GET /exam/prep/catalog` → `catalog_version=v2`、`active_subject_ids={cs_408}`、4 modules |
| 模块 | module id ↔ display name 冻结（§10 契约表） |
| 知识 | `PATCH /exam/11408/subjects/{k}/study-plan/knowledge-items/{code}` 经 canonical writer；legacy scope id `<module>_11408` 保留 |
| 章节练习 | legacy row → `mirror_exam_practice_attempt` → 1 条 canonical PracticeAttempt，context 含 track/subject/module |
| 错题 | wrong fact → `active`；后续正确 → `resolved`；同一题两条不同错误 → `wrong_count=2` |
| 记录 | `LearningEvent`：`service_key=exam_prep`、`subject_key=cs_408`、domain context 含 `exam_module_id` |
| 真题 | `mirror_past_paper_attempt` → `question_source_type=past_exam`，context 含 `question_year` + `exam_subject_id` |
| 计划 | `GET /exam/11408/subjects/{k}/study-plan`（Free 403，权益保留）；tasks CRUD 路由可达 |
| 报告 | capability `report.generate` 仅 Advanced；见 §9 |

---

## 9. Tier E2E

```text
FREE_EXAM_LOOP                    = PASS
STANDARD_EXAM_AI_LOOP             = PASS
ADVANCED_EXAM_CAPABILITY_LOOP     = PASS
```

**Free**：完整非 AI 学习闭环全部可用（profile / catalog / CS408 内容 / 练习 / 错题 / 记录）。
AI 仅限 `tutor.chat` / `question.explain` / `material.qa`；`question.generate` →
**403 且 provider 调用 = 0**。会员差异**不影响任何事实持久化**。

**Standard**：`question.generate` / `planning.generate` / `answer.grade` 全部通过，
且完整走统一生命周期：

```text
AIRequest.status = settled
AIRequest.service_namespace = exam_prep
AIRequest.context_json → exam_subject_id=cs_408, exam_module_id=<module>
UsageLedger 有对应行
provider 调用 1 次，capability 与请求一致
```

**Advanced**：`report.generate` 允许；同样的 capability 在 Standard 下 **403 且 0 调用**。
**本轮未改任何 membership 语义**。

---

## 10. Framework-only E2E

```text
FRAMEWORK_ONLY_SELECTION    = PASS
FRAMEWORK_ONLY_CONTENT_GATE = PASS
```

- 13 个 FRAMEWORK_ONLY 科目**逐个**验证：`PUT /exam/prep/profile` 保存成功（200），
  返回对象带 `availability="framework_only"`、`has_questions=false`、`modules=[]`。
- 逐个访问 `GET /exam/prep/subjects/{id}/content-status` → **409** +
  `{code: "EXAM_CONTENT_NOT_AVAILABLE", availability: "framework_only"}`。
- **不降级**：响应体不含 `cs_408` / `data_structure` 等 408 标识 → 无静默 fallback 到 408。
- **不伪造**：无 200 + 占位内容，无 LLM 生成内容。
- 本轮**未导入**任何非 408 真题 / 题库 / 知识点 / 章节 / 教材。

---

## 11. Legacy Compatibility

```text
LEGACY_11408_ROUTE_COMPATIBILITY = PASS
```

`/exam/11408/*` 既有路由**未删除、未改名**。10 条代表性读接口逐个验证 **200**：

```text
subjects/{k}/dashboard-summary · {k}/chapter-practice/outline ·
{k}/chapter-practice/questions · {k}/past-papers · {k}/wrong-questions ·
{k}/favorites · {k}/done-records · {k}/question-bank/stats ·
{k}/ai-questions · {k}/practice/stats
```

`GET /exam/11408/subjects/{k}/study-plan` 对 Free 用户仍返回 **403**
（legacy `learning_plan` 权益**刻意保留**，随统一会员退役，不做机械重命名）。
写路径：`PATCH …/study-plan/knowledge-items/{code}` 仍走 canonical writer 且响应契约不变。

---

## 12. Knowledge Final Audit

```text
EXAM_KNOWLEDGE_CANONICAL_WRITER = PASS
```

**AST 扫描**（所有非测试 `.py`）查找对 `mastery_score` / `user_confirmed_status` /
`review_due_at` / `review_interval_days` 的直接写入，共 21 处，全部在**非 exam** 路由：

```text
/code/sessions/{session_id}      （programming）
/knowledge-points/{point_id}     （course_learning）
/knowledge-map/progress          （course_learning —— 见下）
/knowledge-map/review-settings   （course_learning）
```

### 12.1 本轮发现并修复：UNDECLARED exam write path

`PATCH /knowledge-map/progress` 用 `normalize_subject_course_learning(course_id)` 归一，
而 `"<module>_11408"` **不在**归一表里 → 原样保留 → `_knowledge_map_seed_path` 存在 →
**该路由可以带 exam scope 调用**。（`/knowledge-map/review-settings` 甚至显式
`course_id.endswith("_11408")` 特判，证明这条路径确实被 exam 前端使用。）

**实测（修复前）**：

```text
PATCH /knowledge-map/progress {course_id: "data_structure_11408", status: "learning"}
  → 200，行 course_id="data_structure_11408"（数据落在 exam 作用域，这点没错）
  → 但事件 service_key = course_learning, subject_key = None
      ctx = {"knowledge_point_id": "_leaf:1.1.1.1"}
```

即：**一条考试知识变更被记成了课程事件** —— H1 修过的 D1 类跨空间污染的残留，
H4 的 mutation inventory 未登记它（H4 的 `exam_paths_not_consolidated() == []` 是
「inventory 自洽」，不是「AST 穷尽」）。

**修复（`main.py`，`/knowledge-map/progress` 路由内）**：

- 用 `learning.spaces.exam_prep.scope.parse_legacy_exam_scope_id` 判定 course_id 是否为
  exam 作用域（`<module>_11408`）；无法解释的 `_11408` → 404（与既有 `seed_path` 缺失行为一致）
- 是 → 委派 `exam_prep.knowledge.apply_exam_knowledge_change`；否则走原 course writer
- **响应契约不变**（`{success, progress, node}`），**行作用域不变**（`course_id` 仍是 `<module>_11408`），
  **review 调度语义不变**（沿用 `_get_review_interval_days`）

**实测（修复后）**：

```text
PATCH /knowledge-map/progress {course_id: "data_structure_11408", status: "mastered"}
  → 200，响应 shape 不变
  → 事件 service_key = exam_prep, subject_key = cs_408,
      ctx = {"exam_module_id": "data_structure", "knowledge_point_id": "..."}
  → 行 course_id="data_structure_11408", status="mastered", mastery_score=100

PATCH /knowledge-map/progress {course_id: "data_structure", status: "learning"}（course 作用域）
  → 行为完全不变：service_key = course_learning
```

`EXAM_MUTATION_PATHS` 已补入该路径（现 4 条），并保持
`exam_paths_not_consolidated() == []`。

### 12.2 最终 inventory

```text
PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}   CANONICAL_WRITER
PATCH /knowledge-map/progress (course_id='<module>_11408') CANONICAL_WRITER  ← 本轮补入
POST  /course-learning/practice/{id}/submit (exam mode)    SYSTEM_DERIVED_NO_EVENT
_materialize_due_review_statuses / review-interval recompute SYSTEM_DERIVED_NO_EVENT

UNDECLARED_DIRECT_WRITE = 0
```

---

## 13. AI Final Reachability

```text
EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0
EXAM_DIRECT_PROVIDER_CALLS_FINAL     = 0
PARSER_OCR_CLASSIFICATION            = PASS
```

- 解析 `main.py` 的 50 个 exam 路由块，逐一查找
  `call_deepseek` / `DEEPSEEK_API_KEY` / `OpenAI(` / `chat.completions` / `DASHSCOPE`：
  **命中 = 0**。
- `learning/spaces/exam_prep/*.py` + `routers/exam_prep.py` 同样 **0 命中**，并有可执行断言。
- 测试夹具 `no_legacy_exam_provider` 让任何触达 legacy 直连客户端的 exam 路径**直接失败**，
  全部 exam AI 测试在 FakeProvider 下通过。
- `main.py` 中其余 12 处 `call_deepseek(` 均在 **course / programming / admin** 路径，
  非 exam 可达，属 H5 范围外。

**OCR 分类**：`qwen_parser` OCR 是 `PARSER_OCR` 基础设施（资料 / 真题解析），
**未**并入 AIOrchestrator，且**不属** exam 学习核心路径。见 §14。

---

## 14. OCR / D8 分类

```text
D8 = NON_BLOCKING_INFRA_TECH_DEBT
```

判定依据（代码事实）：

| 问题 | 事实 |
| --- | --- |
| 是否阻断 Exam Prep 生产可用？ | **否**。OCR 只服务资料 / 真题解析 infra；用户学习核心（备考 → 科目 → 计算练习 → 真题 → 错题 → 记录）不依赖它。 |
| 是否可被用户无限触发的外部成本？ | **否**。有硬上限：按套餐 `DEFAULT_OCR_LIMIT=20` / `FULL_EXAM_OCR_LIMIT=500` / `ADMIN_OCR_LIMIT=1000`，再取系统天花板 `ai_pdf_scan_max_pages`（`max_pages = min(user_limit, system_ceiling)`）；另有 `MAX_OCR_CHARS=12000`。 |
| 是否有隐蔽的会员绕过？ | **否**。OCR 页数上限**本身就是按套餐**判定（`get_pdf_ocr_page_limit_for_user`），超限直接拒绝。 |
| 是否经统一 usage_ledger / ai_cost_records 记账？ | **没有** —— 这正是 D8 的技术债本身。 |

因此 **不**在 H5 硬塞进 AIOrchestrator，**不**新建第二套会员体系，**不**新增 rate limit
（已有页数上限即最小保护）。D8 保持 documented / bounded / 有 owner，见 §19 债务 ②。

---

## 15. Isolation

```text
CROSS_USER_ISOLATION      = PASS
CROSS_NAMESPACE_ISOLATION = PASS
CROSS_MODULE_ISOLATION    = PASS
```

| 维度 | 验证 |
| --- | --- |
| profile 跨用户 | 用户 B 看不到用户 A 的 `selected_track` / `target_exam_year`（`configured=false`） |
| 练习 / 错题跨用户 | A 的 PracticeAttempt 与 wrong state 对 B 不可见（双向空集） |
| 记录跨用户 | 事件按 `user_id` 隔离 |
| **跨命名空间** | 同名 token `data_structure` 在 course_learning 是 `course_id`、在 exam_prep 是 `exam_module_id`；course 事实不落 exam 查询，反之亦然（§12.1 的修复使该边界在**写**方向也成立） |
| 跨模块 | 同一用户 `computer_network` 的练习不会出现在 `data_structure` 上下文 |
| framework-only vs active | 405 内容门独立于 408 内容可达性；framework-only 科目无任何内容泄漏 |

---

## 16. Protected Assets

```text
REAL backend/app.db（只读复核，H5 前后一致）
  integrity_check      = ok
  表总数                = 72
  exam_question_bank   = 9333
    by subject_key : data_structure 5903 / computer_organization 1330 /
                     operating_system 1180 / computer_network 920
    by source_type : chapter 9098 / past_paper 235
  programming_exercises= 1923
  knowledge_points     = 32
  H5_BANKSHA256        = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee
                         （与 LEGACY COPY upgrade head 后逐字节相同）

文件计数（must not decrease）
  exam_resources     = 268（H4 亦为 268，未减少）
  static/exam_papers = 564（未变）
```

```text
QUESTION_BANK_COUNT             = 9333
QUESTION_BANK_CONTENT_UNCHANGED = YES
STATIC_ASSETS_UNCHANGED         = YES
```

**MIGRATION_HEAD = 20260917_0008** · **REAL_APP_DB_MIGRATED = NO**

### 16.1 路由卫生

```text
DUPLICATE_METHOD_PATH_REGISTRATIONS = 0
```

遍历 `main.app.routes`，按 `(method, path)` 聚合（忽略 HEAD/OPTIONS），重复项 = **空**。

### 16.2 Wrong 并发（H2-C1 未回归）

```text
WRONG_CONCURRENCY_STRESS = PASS（1000 次并发 attempt，0 失败）
```

两个**不同**的错题事实并发争用同一题，投影为 compare-and-recompute：
500 轮 × 2 线程 = **1000 次并发写入**，每轮断言 `(states==1, wrong_count==2)`，
0 失败。另有 H2 原有 3 项并发门禁全部通过。

---

## 17. Frontend API Contract

```text
FRONTEND_API_HANDOFF = COMPLETE
FRONTEND_CHANGED     = NO
```

产出 `STEP7H_FRONTEND_API_HANDOFF.md`（本轮新建，短、稳定、面向前端实现方）。
包含：

```text
A. Product IA（Exam Prep 目录结构）
B. ACTIVE vs FRAMEWORK_ONLY（含 13 个 framework-only 科目 id）
C. Canonical endpoints（/exam/prep/*，含 request/response/auth/errors）
D. CS408 内容接口（既有 /exam/11408/*，明确"新前端继续用这些"）
E. Content status contract（active / framework_only 分支）
F. 前端必须处理的状态（401/403/409/429/502/404/400，detail 的两种形态）
G. Profile 契约（exam_type / selected_track / selected_subjects / target_exam_year）
H. CS408 module id + 显示名（FROZEN）
I. 明确禁止的 UI 假设（10 条）
J. 会员体验（只描述用户可见行为，不暴露后端 registry）
```

**本轮未写任何页面、未调用任何前端代码生成**；只冻结契约。

---

## 18. Tests

```text
TARGETED_TESTS      = tests/test_exam_final_acceptance.py 53 passed / 0 failed
WRONG_CONCURRENCY   = PASS（1000 并发，0 失败）

FULL_RUN_1 = 878 passed / 0 failed（453.02s）
FULL_RUN_2 = 878 passed / 0 failed（479.98s）
FULL_BACKEND_TESTS = PASS（连续两次全绿，无 flaky）
```

H4 baseline = 822。本轮 **+56** = H5 新增 53 项 + `test_practice_migration.py` 新增 3 项。

新增 `backend/tests/test_exam_final_acceptance.py`，覆盖 §31 要求的全部条目：

| 要求 | 测试 |
| --- | --- |
| alembic-only fresh deployment | `test_alembic_only_fresh_deployment_builds_the_exam_runtime_schema` |
| 结构真正可用（不靠 create_all） | `test_alembic_created_exam_schema_is_usable_by_the_orm` |
| legacy copy migration | `test_migration_0008_on_a_legacy_copy_preserves_every_row` |
| dead 表不 drop / 不 baseline | `test_migration_0008_does_not_drop_the_dead_table_on_legacy` |
| migration 幂等 | `test_migration_0008_is_idempotent_on_a_second_head_check` |
| CS408 full E2E | `test_cs408_full_learning_loop` / `..._past_paper_loop...` / `..._knowledge_writes...` |
| Free E2E | `test_free_exam_loop_persists_facts_without_paid_ai` |
| Standard AI E2E | `test_standard_exam_ai_loop_runs_the_full_usage_lifecycle`（3 capability 参数化） |
| Advanced capability E2E | `test_advanced_may_use_report_generate_but_standard_may_not` |
| framework-only 选择 + 内容门 | `test_framework_only_subject_is_selectable_but_content_is_explicitly_absent`（13 参数化） |
| legacy 路由兼容 | `test_legacy_11408_routes_still_answer`（10 参数化）+ 权益保留 |
| canonical API | §B 契约测试 4 项 |
| knowledge writer 收敛 | §12 测试 3 项（含本轮修复的回归测试） |
| AI reachability | `test_exam_business_code_reaches_no_provider_directly` |
| 重复路由审计 | `test_no_duplicate_method_path_registrations` |
| 受保护资产 | `test_protected_assets_are_unchanged` |
| 隔离 | §15 测试 4 项 |
| wrong 并发 | `test_wrong_projection_survives_1000_concurrent_attempts` |

**BLOCKER 级测试 bug 修复记录**（本轮修了 4 个测试自身缺陷，非产品缺陷）：

① `AbstractConcreteBase` 之外：`test_alembic_created_exam_schema_is_usable_by_the_orm`
   原先插入 `User` 行，但 fresh alembic 库**不含** `users` 表（它属更广 baseline）→ 改为
   ORM 查询 exam 表，不依赖非 exam 表。
② `AIRequest` 无 `subject_key` 列（subject 在 `context_json`）→ 改断言 context。
③ `dashboard-summary` 真实路径是 `/exam/11408/subjects/{k}/dashboard-summary`。
④ `context_json` 是 JSON 列（已是 dict）而非字符串。

---

## 19. Remaining Non-blocking Debt

全部为 **NON_BLOCKING_TECH_DEBT**。无 data correctness / schema deployment / namespace /
billing correctness / user-fact loss blocker。

| # | 债务 | owner | reason | future phase |
| --- | --- | --- | --- | --- |
| ① | 更广的 legacy baseline 缺口：约 46 张非 Exam 表（`users` / 资料 / programming / 管理端等）仍无 Alembic owner，fresh 部署仍依赖 `create_all` + `ensure_*` | Backend | H5 只对 Exam 域建立 coverage；把 46 张表一次性 baseline 属高风险且非 Exam 范围 | 独立 migration 硬化轮次（部署硬化） |
| ② | D8：OCR 不经统一 usage_ledger / ai_cost_records 记账（可观测性 / 计费缺口） | Backend / Parser Infra | OCR 只服务资料解析 infra，已有按套餐页数上限（20/500/1000 + 系统天花板），无无限成本、无会员绕过 | Parser Infra 成本核算轮次 |
| ③ | D5 `exam_favorite_questions_v2` 死表仍在（0 行 / 0 引用 / 无 FK） | Backend | 删除需一次独立、可回滚的 migration；H5 不为"清洁"承担风险 | 死表清理轮次 |
| ④ | 真实 `backend/app.db` 未迁移到 `20260917_0008`（`exam_prep_profiles` 在生产库尚不存在） | Deploy | 线上变更必须走既有部署流程，不直改线上；H5 只在副本上验证 | 下一次正式部署 |
| ⑤ | 13 个 FRAMEWORK_ONLY 科目无真实内容（**有意为之**，非缺陷） | Product | 导入非 408 内容**必须等用户明确批准**（STEP7H0 §21） | 内容导入决策轮次 |
| ⑥ | `/exam-408/*`（院校自命题遗留路由：schools / target-school / motto / exam-info）仍存在 | Backend | 未删除以保持 legacy 兼容；但产品层面院校自命题**永久 OUT OF SCOPE**，前端**不得**暴露入口 | 旧产品结构清理轮次 |
| ⑦ | 2 处 `DeprecationWarning`：`datetime.utcnow()`（`learning/**`、`usage/service.py`、`main.py`） | Backend | 不影响正确性；全仓范围替换属独立重构 | 技术债清理轮次 |

---

## 20. Final Freeze

```text
EXAM_RUNTIME_SCHEMA_ALEMBIC_COVERAGE = COMPLETE

EXAM_SCHEMA_DEPENDS_ON_CREATE_ALL = NO

MIGRATION_HEAD = 20260917_0008

FRESH_DB_ALEMBIC_ONLY   = PASS
LEGACY_DB_COPY_UPGRADE  = PASS

REAL_APP_DB_MUTATED = NO

CS408_FULL_BACKEND_E2E = PASS

FREE_EXAM_LOOP                = PASS
STANDARD_EXAM_AI_LOOP         = PASS
ADVANCED_EXAM_CAPABILITY_LOOP = PASS

FRAMEWORK_ONLY_SELECTION    = PASS
FRAMEWORK_ONLY_CONTENT_GATE = PASS

LEGACY_11408_ROUTE_COMPATIBILITY = PASS

EXAM_KNOWLEDGE_CANONICAL_WRITER = PASS

EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0
EXAM_DIRECT_PROVIDER_CALLS_FINAL     = 0

PARSER_OCR_CLASSIFICATION = PASS（PARSER_OCR · D8 = NON_BLOCKING_INFRA_TECH_DEBT）

QUESTION_BANK_COUNT             = 9333
QUESTION_BANK_CONTENT_UNCHANGED = YES

WRONG_CONCURRENCY_STRESS = PASS（1000 并发，0 失败）

DUPLICATE_METHOD_PATH_REGISTRATIONS = 0

CROSS_USER_ISOLATION      = PASS
CROSS_NAMESPACE_ISOLATION = PASS
CROSS_MODULE_ISOLATION    = PASS

FRONTEND_API_HANDOFF = COMPLETE
FRONTEND_CHANGED     = NO

FULL_BACKEND_TESTS = PASS（878 passed / 0 failed，连续两次）

STEP7H5_COMPLETE = YES
STEP7H5          = FROZEN
STEP7H           = FROZEN
FRONTEND_READY   = YES
```

**下一步（唯一正确动作）**：进入 **FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION**。
后端停止继续扩展。
