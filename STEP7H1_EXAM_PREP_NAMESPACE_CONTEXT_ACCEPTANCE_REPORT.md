# STEP7H1_EXAM_PREP_NAMESPACE_CONTEXT_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7H1 验收报告
> 范围：Exam Prep canonical namespace + context compatibility foundation
> 生成：2026-09-16 · 本轮为 **IMPLEMENTATION**（有代码变更，未 commit / 未 push）

---

## 1. EXECUTIVE VERDICT

```text
STEP7H1_COMPLETE = YES
STEP7H1          = FROZEN
STEP7H2_READY    = YES

CANONICAL_EXAM_NAMESPACE       = exam_prep
LEGACY_EXAM_ALIAS_NORMALIZATION = PASS
IDENTITY_NAMESPACE_TOKEN        = exam_prep → exam_11408（永久冻结，与环境/数据历史无关）
LEARNING_CONTEXT_SINGLE_MODEL   = PASS（扩展 core.LearningContext，未新建第二套）

D1_CROSS_SPACE_POLLUTION = FIXED（4 条路径 + 兜底守卫）
D2_QUESTION_ANALYSIS_CONTEXT = FIXED
D4_DUPLICATE_ROUTE = FIXED（并额外清掉 1 个同类隐藏重复）

QUESTION_BANK_PHYSICAL_MIGRATION = NO
QUESTION_BANK_COUNT              = 9333
QUESTION_BANK_CONTENT_UNCHANGED  = YES

NEW_TABLES_PROPOSED_FOR_H1    = NONE
SCHEMA_CHANGE_REQUIRED_FOR_H1 = NONE
DATA_MIGRATION_REQUIRED       = NO（pre-flight：目标库 6 张统一表全部 NOT_PRESENT）

REAL_APP_DB_MUTATED = NO
FULL_BACKEND_TESTS  = PASS
```

---

## 2. GIT BASELINE

```text
HEAD = ebad5282（与轮次开始时一致，未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

本轮未触碰 `reference/`、`.github/workflows/`、`frontend/`、`backend/.env*`。

---

## 3. DATABASE SAFETY

本轮**所有**需要模块加载的动作（`import main`、`TestClient`、route introspection、
pytest）均在显式 `DATABASE_URL=sqlite:///<temp>` 下执行，**未依赖 cwd 默认行为**。

```text
真实 backend/app.db 的访问方式 = 只读 sqlite3（file:…?mode=ro）
  未建立 SQLAlchemy engine，未 create_all，未执行 migration，未写入
  实测：72 表 / integrity_check = ok / exam_question_bank = 9333
        programming_exercises = 1923 / knowledge_points = 32
        alembic_version 表不存在

REAL_APP_DB_MUTATED = NO
```

---

## 4. EXAM_CANONICAL_ROW_PREFLIGHT_MATRIX

对真实 `backend/app.db` 的只读统计（STEP7H0 §16 要求的六张表）：

| table | column | 结果 |
| --- | --- | --- |
| `practice_sessions` | `service_namespace` | **NOT_PRESENT** |
| `practice_attempts` | `service_namespace` | **NOT_PRESENT** |
| `wrong_answer_states` | `service_namespace` | **NOT_PRESENT** |
| `learning_events` | `service_key` | **NOT_PRESENT** |
| `ai_requests` | `service_namespace` | **NOT_PRESENT** |
| `usage_ledger` | `service_namespace` | **NOT_PRESENT** |

```text
EXAM_CANONICAL_ALIAS_ROWS_TOTAL = 0（无表 ⇒ 无行；NOT_PRESENT ≠ failure）
DATA_MIGRATION_REQUIRED = NO
```

真实库仍是 pre-STEP7A 的 legacy 基线（5 张统一表尚未建立），因此**没有任何 legacy
namespace 值需要改写**，本轮不产生 migration 文件。

> **注意**：按 §4 的最终裁决，identity token **不采用** H0 文档里的条件式设计。
> 无论数据库是否有旧行，`exam_prep → exam_11408` 的 token 一律冻结（见 §6）。

---

## 5. CANONICAL NAMESPACE

```text
core.learning_context.ServiceNamespace =
  course_learning | exam_prep | programming

VALID_SERVICE_NAMESPACES = {course_learning, exam_prep, programming}
```

- `EXAM_11408` **已从枚举中移除** —— 它不再是 canonical 存储值。
- `is_valid_service_namespace("exam_prep") = True`
- `is_valid_service_namespace("exam_11408") = False`（作为 canonical validity）
- `normalize_service_namespace("exam_11408") = "exam_prep"`（作为 INPUT alias 仍可用）

`LEGACY_NAMESPACE_ALIASES` 新增/归一：

```text
exam / exam_408 / exam408 / exam-408 / exam_11408 / exam-11408 / 11408 / exam-prep
  → exam_prep
exam_prep → exam_prep（自身，非 legacy alias）
```

**改名范围（遵循 H0 FD-5）**：只改「学习空间」维度。`exam_11408` 作为
**legacy 会员 service_key / legacy 额度桶 key / 资料域标签 / admin·support 分类**的用法
**全部保留未改**（`main.py` 中仍有 58 处，逐条核对均为上述维度）。改名它们会扩大风险面
并掩盖真正的清理目标。

---

## 6. IDENTITY TOKEN（永久冻结）

```text
learning/practice/identity.py
IDENTITY_TOKEN_BY_NAMESPACE = {
    "course_learning": "course_learning",
    "exam_prep":       "exam_11408",
    "programming":     "programming",
}
```

`session_uid()` / `attempt_uid()` 先把 namespace 归一化，再映射到 **冻结 token**，然后
才进入 uuid5 名称。因此：

```text
attempt_uid("exam_11408", …) == attempt_uid("exam_prep", …)   ← 断言通过
session_uid("exam_11408", …) == session_uid("exam_prep", …)
course_learning / programming 的 token 与历史完全一致（uid 不变）
```

```text
IDENTITY_ENVIRONMENT_DEPENDENT = NO
```

**为什么必须冻结而不是条件式**：practice 行身份是永久契约。若 uid 随环境（是否有旧行）
而变，两个环境对同一逻辑事实会得出不同 uid，replay/backfill 就会造出第二条逻辑事实。
冻结 token 让 canonical 名称可以安全演进，而历史身份完全不动。

已固化为测试：`test_identity_token_is_frozen_for_exam_prep`、
`test_legacy_and_canonical_exam_inputs_produce_one_practice_identity`（4 个别名 × session/attempt）、
`test_one_legacy_attempt_never_becomes_two_canonical_attempts`（同一 legacy 行经
`ensure_legacy_session` 以 `exam_11408` 与 `exam_prep` 各镜像一次 → 只有 1 条 canonical attempt）。

---

## 7. LEARNINGCONTEXT EXTENSION

继续只有**一个** canonical `core.LearningContext`，未创建 `ExamLearningContext` /
`ExamAIContext` / `ExamPracticeContext`。新增 3 个 Optional 字段，既有字段全部保留：

```text
exam_track_id    用户备考 track        cs_408
exam_subject_id  实际统考科目          cs_408
exam_module_id   科目内部模块          data_structure
```

字段去向（严格执行 §7 契约）：

| 字段 | core.LearningContext | to_event_context() | learning_events | identity |
| --- | --- | --- | --- | --- |
| `exam_track_id` | ✅ | ❌ **不进** | ❌ **不进** | ❌ |
| `exam_subject_id` | ✅ | ✅ | → `subject_key` 列 | ❌ |
| `exam_module_id` | ✅ | ✅ | → `knowledge_point_ref_json` JSON | ❌ |

```text
LEGACY_SUBJECT_KEY_MIRROR = exam_module_id
EVENT_SUBJECT_KEY         = exam_subject_id
```

`exam_track_id` 不进事件的理由：track 是**用户侧的备考组合选择**，不是事实的属性；
把 track 写进事件会让同一事实因两人选了不同 bundle 而变成两条不同记录。

---

## 8. CS408 MAPPING + EXAM SPACE MODULE

新增（唯一 exam 侧边界）：

```text
backend/learning/spaces/exam_prep/
  __init__.py
  catalog.py    CS408 常量（EXAM_TYPE_POSTGRADUATE / CS408_TRACK / CS408_SUBJECT / CS408_MODULES）
  scope.py      legacy scope id 纯函数适配器（parse / build / resolve），fail closed
  context.py    build_exam_context / cs408_context / cs408_context_from_values / assert_exam_matches
  ai.py         execute_exam_ai（Exam Prep 通往 AIOrchestrator 的唯一门）
```

**H1 只建立 CS408**（§21）：`math_1 / politics / english_1 / law_jm_law /
management_joint` 等**未**加入 catalog —— 它们属 H4，且需真实内容与用户批准。

Legacy adapter 自动解释（endpoint 不手写映射）：

```text
exam_track_id   = cs_408
exam_subject_id = cs_408
exam_module_id  = 既有 subject_key
LearningContext.subject_key = subject_key（legacy mirror）
```

`cs408_context_from_values()` 接受 endpoint 手上任意一种 legacy 形式并解析 module：
`data_structure_11408` / `data_structure` / `11408 数据结构` / `数据结构`。

**Scope id 适配器（§9）**：

```text
parse_legacy_exam_scope_id("data_structure_11408") → ExamScope(cs_408, cs_408, data_structure)
build_legacy_exam_scope_id("operating_system")     → "operating_system_11408"
```

- 四个 module 全部覆盖（round-trip 测试）
- **非法 scope fail closed**：`algebra_11408` → `ExamScopeError`（不是静默变 None）
- 非 scope 值（`data_structure` / 空串）→ 返回 None，不是错误
- **纯函数**：不读写存储（测试固化）
- **不 rewrite**：`user_knowledge_progress.course_id`、`study_materials.course_id`、
  seed JSON、static 路径全部原样保留

---

## 9. QUESTION BANK —— 零物理迁移

```text
QUESTION_BANK_PHYSICAL_MIGRATION = NO
QUESTION_BANK_ROWS_BEFORE = 9333
QUESTION_BANK_ROWS_AFTER  = 9333
QUESTION_BANK_CONTENT_UNCHANGED = YES
```

只读实测（真实 `backend/app.db`）：

```text
exam_question_bank = 9333
  by subject_key : data_structure 5903 / computer_organization 1330 /
                   operating_system 1180 / computer_network 920
  by source_type : chapter 9098 / past_paper 235
  CONTENT_FINGERPRINT_SHA256 (id,subject_key,source_type,year,question_number,
                              stem,standard_answer,analysis)
                 = 7b0717634939974752b95200f96de959615cbffde2ce2f27e7a4c542ea82d7a4
保护资产（同步复核）：programming_exercises 1923 / knowledge_points 32 ×
  （knowledge_points 属 programming-C ontology，未纳入 Exam catalog）
```

**id / subject_key / source_type / 题面 / year / knowledge_point / source_ref 一律未改。**
目标解释（track=cs_408, subject=cs_408, module=既有 subject_key）**只在 adapter/config 层**。

---

## 10. D1 —— 跨空间污染（已修）

### 10.1 缺陷

4 条路径在 **exam 请求**下：

```text
usage_service = "exam_11408"        ← endpoint 自己的分支判断正确（legacy 日志）
      ↓ 但 AI 调用
_course_ai_content(...) → build_course_context(...) ← service_namespace 硬编码 COURSE_LEARNING
      ↓
ai_requests.service_namespace = "course_learning"     ← ❌
ai_called 事件 service_key    = "course_learning"     ← ❌
```

受影响端点（原样保留 legacy 分支判断，只改 AI 归属）：

```text
POST /practice/questions/generate          （exam 分支）
POST /practice/generate-task-preview       （exam 分支）
POST /learning/reports/generate-preview    （exam 分支）
POST /learning-report/ai-generate          （exam 分支）
```

### 10.2 修法（不是只改字符串）

新增 **space dispatcher**（`main.py`）：

```text
_scoped_ai_content(db, user, capability, messages, *, course_id, exam_scope_values, …)
    is_exam_408_context(*exam_scope_values) → _exam_ai_content(…)   # exam_prep context
    else                                    → _course_ai_content(…) # course_learning context

_exam_ai_content(…)  → learning.spaces.exam_prep.ai.execute_exam_ai
                        ← build cs408 context（track/subject/module）
```

**空间由服务端在这里决定**，用的是 endpoint 自己那套谓词；调用方「顺手拿了哪个 helper」
不再决定事实归属。

**兜底守卫**：`_course_ai_content` 自身也检查 `is_exam_408_context(course_id)`，
若命中则转交 exam 边界 —— 一个 course context **永远**不该由 exam scope 构造。
这样其余十几个 course 调用点一并获得保护，避免同类回归。

### 10.3 验收

- 4 条路径 × exam payload → `AIRequest.service_namespace = exam_prep`、
  `context_json.service_namespace = exam_prep`、`exam_subject_id = cs_408`、
  `exam_module_id = data_structure`（参数化测试 4/4）
- 同样 4 条路径 × course payload → 仍为 `course_learning`（反向 4/4）
- 直接调用 `_course_ai_content(course_id="data_structure_11408")` → 落 `exam_prep`

```text
D1_CROSS_SPACE_POLLUTION = FIXED
```

---

## 11. D2 —— question-analysis context（已修）

`POST /exam/11408/{subject_key}/question-analysis` 原本已走 `AIOrchestrator`，但
**未传 `learning_context`**，导致 `ai_requests.service_namespace = NULL`、
`context_json = NULL`。现改为经 `execute_exam_ai` 并传入
`cs408_context(module_key=subject_key)`。

验收（HTTP 级）：

```text
AIRequest.service_namespace = exam_prep
AIRequest.context_json      = {exam_track_id: cs_408, exam_subject_id: cs_408,
                               exam_module_id: data_structure, …}
UsageLedger.service_namespace = exam_prep（reserve/settle 全行）
ai_called 事件 service_key    = exam_prep
```

错误语义顺带对齐（有意为之，已记入报告）：原先无授权时返回 503；现在
capability 拒绝 → 403、budget 拒绝 → 429、reconciliation pending → 502，
与 course 侧一致。未知异常仍回落 503。

```text
D2_QUESTION_ANALYSIS_CONTEXT = FIXED
```

---

## 12. D4 —— 重复路由（已修）

```text
GET /exam/11408/study-plan/tasks/summary    → 注册了两次
  18736 版（多行签名 + docstring + require_feature_entitlement 在 docstring 之前）← 真实可达
  19213 版（单行签名，require_feature_entitlement 在 docstring 之前，docstring 实际失效）← dead
```

FastAPI 按注册顺序匹配 → **18736 版胜出**，19213 版是死代码（其 docstring 因位于
语句之后而未生效）。**保留可达的那一个，删除死的那一个**，API contract 不变。

### 12.1 附带发现并修复：第二个同类重复（D4b）

D4 的路由计数检查暴露出另一处**同类隐藏重复**：

```text
GET /learning-records
  routers/learning_records.py:list_records   ← include_router 在 main.py:5523（先注册）→ 真实可达
  main.py:get_learning_records（legacy LearningRecord 列表）  ← 后被 shadow，dead
```

证据：`app.routes` 中该 path 的第一条 handler 是 `routers.learning_records.list_records`；
`tests/test_learning_records_api.py` 全部断言新契约（`records` / `event_id` / `next_cursor`）
且通过 —— 即新 API 一直是实际生效者。删除**不可达**的 legacy handler 属纯清理，
不改变任何行为。

（`POST /learning-records` 无重复，legacy 创建路径保留。）

```text
D4_DUPLICATE_ROUTE = FIXED
DUPLICATE_METHOD_PATH_REGISTRATIONS = {}   ← 全 app 实测为空
TOTAL_ROUTES = 380
```

---

## 13. answer.grade capability 注册（H3 解阻）

按 §14 批准的策略**只注册配置，不动 grading 流程**：

```text
usage/capabilities.py
  ANSWER_GRADE_PROFILE = "QUESTION_EXPLAIN_PROXY_V1"
  CAPABILITY_TIER_POLICY: free ✗ / standard ✓ / advanced ✓

ai/pool.py
  ALL_CAPABILITIES 增加 "answer.grade"
  CAPABILITY_QUALIFICATION_PROXIES["answer.grade"] = "question.explain"
  ANSWER_GRADE_PROFILE = "QUESTION_EXPLAIN_PROXY_V1"

POOL_VERSION = v4（未变）· 未新开 provider benchmark
```

实测：standard/advanced 下 `answer.grade` 的 qualified model 集合与
`question.explain` **逐项相等**。

**本轮未做的事**（H3 范围）：`exam_paper_parser._grade_big_question` 未迁移、
grading flow 未改、provider call 未动 —— 测试固化
（`test_grading_flow_is_untouched_in_h1` 断言该函数源码中既无 `answer.grade` 也无
`AIOrchestrator`）。这样 H3 开工时不再有产品决策 blocker。

```text
ANSWER_GRADE_CAPABILITY  = REGISTERED
ANSWER_GRADE_TIER_POLICY = Free DENIED / Standard ALLOWED / Advanced ALLOWED
ANSWER_GRADE_POOL_PROXY  = QUESTION_EXPLAIN_PROXY_V1
```

---

## 14. EVENT IDENTITY

```text
EVENT_IDENTITY_ALGORITHM_CHANGED = NO
```

`data_plane.identity.event_id = uuid5(EVENT_UUID_NAMESPACE, f"{source_type}|{source_attempt_id}|{item_key}")`
—— **不含 namespace**，故 `exam_11408 → exam_prep` 不改变任何历史事件身份，也未重生成。

新 exam 事件的落法：

```text
service_key = exam_prep
subject_key = exam_subject_id（cs_408）
knowledge_point_ref_json = {"knowledge_point_id": …, "exam_module_id": "data_structure"}
```

### 14.1 一处真实缺口（本轮修复）

修 D2/D1 时发现：`learning/practice/events.py` 的经验事件桥**直接读存储的 context JSON**
取 `subject_key`，而不是走 `LearningContext.event_subject_key()`。因此按 H1 契约写入的
exam 事件会得到 `subject_key = operating_system`（module），而非 `cs_408`（subject）。

修法：把规则收敛为**一个**函数
`core.learning_context.resolve_event_subject_key(context: dict)`，`LearningContext.event_subject_key()`
与两个 producer（practice 桥、records envelope）全部委托它。对已解析过的 context 幂等，
对 historical 数据无影响（`context` 无 `exam_subject_id` 时原样返回 `subject_key`）。

`knowledge_point_ref_json` 同步改为 `domain_context_json()`（共享实现），在
`knowledge_point_id` 之外携带 `exam_module_id`；该 JSON **不参与任何 identity**
（`event_id` / `idempotency_key` 只取 source triple），故无需 migration；两个既有 reader
（records read model / Scientific Runtime client）都只读已知键，向后兼容。

`exam_track_id` **不在**该 JSON 中（测试固化）。

---

## 15. WRONG ANSWER IDENTITY

```text
TRACK_IN_WRONG_IDENTITY = NO
```

本轮**不**全面改变 Wrong projection，只固定原则：track 永不进 identity
（track 是用户侧选择，写进 identity 会让同一道错题在换 track 后变成两条）。
`scope_key` 对 `past_exam` 仍为 `year:<year>`，与 STEP7E 冻结语义一致；
`exam_prep` 的 `past_exam` 行为不变（`subject` 已固化为 cs_408，`year` 仍足以消歧）。

```text
PAST_EXAM_CROSS_SUBJECT_IDENTITY_RISK = ASSESSED → DEFERRED_TO_H2
```

**H2 gate（已登记，必须验）**：当第二门统考科目（如 `math_1`）进入后，
`past_exam` 的 `source_id` 是"从解析卷来的字符串"，**必须实测它在不同 subject/module 下
是否全局唯一**。若不唯一，H2 必须在 namespace/data migration 之前设计
**subject/module-aware scope**，而不是等到 H4 新科目导入后才撞车。

---

## 16. EXAM_PROFILE 存储兼容性

```text
EXAM_PROFILE_STORAGE_COMPATIBILITY = NEEDS_H4_DESIGN
```

H1 **不新建表**。既有载体 `user_learning_tracks`
（`track_type / plan / package_type / permissions_json / quota_json /
onboarding_detail_json / is_active / status`）**可以**承载
`exam_type / selected_track / selected_subjects / target_exam_year`
（`onboarding_detail_json` 是 JSON），但它的语义是**legacy 会员/方向**载体，
把它直接当作 Exam Prep 的用户画像会把旧会员维度一并继承。

结论：**能承载，但语义不干净 → 留待 H4 与 onboarding 一起设计**，H1 不重做 onboarding、
不新建表、不动读写路径。

明确禁止进入 target 的字段（即使 legacy 已存在，仅 inventory）：
`target_school / school / college / major_code / school_exam_code / institution_*`。

---

## 17. 测试

```text
TARGETED_TESTS（新增）= tests/test_exam_prep_namespace.py（50 项，见下）
```

覆盖 §24 的 A–L 全矩阵：

| 组 | 内容 |
| --- | --- |
| A/B/C | 8 个别名 → `exam_prep`；`exam_prep` canonical valid；`exam_11408` canonical invalid 但 alias 接受；枚举只有 3 个空间 |
| F | token 冻结断言；4 个别名 × (session_uid, attempt_uid) 与 canonical 相等；同一 legacy attempt 经两种拼法镜像 → **1 条** canonical attempt（不产生第二条） |
| D/L | CS408 context 三层字段 + legacy mirror；4 种 legacy scope 形式全部解析；事件 `subject_key = cs_408` 且 module 在 context JSON；track 不在事件/identity；**事件行级**断言（stored row） |
| scope | 四 module round-trip；非法 scope fail closed；纯函数（不写存储） |
| catalog | 只装 CS408；math/politics/law/management **不在** |
| E | course 的 `data_structure` 与 exam 的 `data_structure` 各自成行、互不串线；source type 解析接受两种拼法 |
| G/I | D1 四条路径 × exam → `exam_prep`；同样四条 × course → `course_learning`；course helper 兜底守卫 |
| H | question-analysis：AIRequest / UsageLedger / ai_called 三者全 `exam_prep` + 完整 context |
| J | 全 app 无重复 (method, path)；study-plan summary 恰 1 个 handler |
| cap | `answer.grade` tier 策略 + pool 继承 + **grading flow 未动** |

对齐更新（非新增）：`test_practice_core / practice_adapters / wrong_answers /
wrong_answers_api / learning_records / learning_records_api / practice_api /
learning_context / course_space / course_ai_migration / course_ai_reachability`
—— namespace 字面量与枚举成员更新为 canonical，`AI_BOUNDARY_FNS` 增加 dispatcher。

> 更新原则：**测试跟随 canonical 值**，而 legacy 别名的归一化由新增的专项测试覆盖
> （不是把旧断言改成"随便哪个都行"）。会员/额度维度（admin / feature_entitlements /
> membership_orders / first_time_guides / knowledge_map_progress）的 `exam_11408`
> **刻意保持原样**，因为它们测的是 legacy service key，不是学习空间。

```text
FULL_BACKEND_TESTS = PASS（712 passed / 0 failed；baseline 662）
```

---

## 18. 本轮变更文件

```text
[MOD] backend/core/learning_context.py
       · ServiceNamespace: EXAM_11408 → EXAM_PREP（"exam_prep"）
       · LEGACY_NAMESPACE_ALIASES 扩充 exam 家族 → exam_prep
       · LearningContext 新增 exam_track_id / exam_subject_id / exam_module_id
       · event_subject_key() + 模块级 resolve_event_subject_key()（单一规则）
[MOD] backend/learning/practice/identity.py
       · IDENTITY_TOKEN_BY_NAMESPACE（冻结）+ identity_token()
       · session_uid / attempt_uid 改用冻结 token
[MOD] backend/learning/practice/refs.py
       · LEGACY_SOURCE_MAP key → exam_prep；resolve_source_type 先归一化
[MOD] backend/learning/practice/events.py
       · subject_key 走 resolve_event_subject_key；domain_context_json 共享
[MOD] backend/learning/records/envelope.py
       · build_event.subject_key 走同一规则；domain_context_json（含 exam_module_id）
[MOD] backend/learning/practice/adapters/{course,exam}.py、
       backend/learning/practice/backfill.py、backend/learning/records/taxonomy.py、
       backend/learning/wrong_answers/legacy.py
       · ServiceNamespace.EXAM_PREP
[MOD] backend/learning/spaces/course_learning/knowledge.py
       · mutation inventory 的 exam 空间名 → exam_prep
[MOD] backend/main.py
       · _exam_ai_content + _scoped_ai_content（space dispatcher）
       · _course_ai_content 增加 exam-scope 兜底守卫
       · D1 四条路径改用 _scoped_ai_content
       · D2 question-analysis 传入 cs408 context（经 execute_exam_ai）
       · D4 删除 dead 重复 handler；D4b 删除 dead legacy GET /learning-records
[MOD] backend/usage/capabilities.py、backend/ai/pool.py
       · answer.grade 注册（tier + pool proxy）
[NEW] backend/learning/spaces/exam_prep/{__init__,catalog,scope,context,ai}.py
[NEW] backend/tests/test_exam_prep_namespace.py（50）
[MOD] backend/tests/（11 个文件的 namespace 对齐 + reachability boundary 声明）
```

```text
NEW_TABLES = NONE
SCHEMA_CHANGE = NONE
NEW_MIGRATION = NONE
```

---

## 19. FINAL GATES

```text
CANONICAL_EXAM_NAMESPACE = exam_prep

LEGACY_EXAM_ALIAS_NORMALIZATION = PASS

IDENTITY_NAMESPACE_TOKEN      = exam_prep → exam_11408
IDENTITY_ENVIRONMENT_DEPENDENT = NO

LEARNING_CONTEXT_SINGLE_MODEL = PASS

EXAM_TRACK_CONTEXT   = PASS
EXAM_SUBJECT_CONTEXT = PASS
EXAM_MODULE_CONTEXT  = PASS

LEGACY_SUBJECT_KEY_MIRROR = exam_module_id
EVENT_SUBJECT_KEY         = exam_subject_id

CS408_MAPPING = PASS

QUESTION_BANK_PHYSICAL_MIGRATION = NO
QUESTION_BANK_COUNT              = 9333
QUESTION_BANK_CONTENT_UNCHANGED  = YES

D1_CROSS_SPACE_POLLUTION     = FIXED
D2_QUESTION_ANALYSIS_CONTEXT = FIXED
D4_DUPLICATE_ROUTE           = FIXED

ANSWER_GRADE_CAPABILITY  = REGISTERED
ANSWER_GRADE_TIER_POLICY = Free DENIED / Standard ALLOWED / Advanced ALLOWED
ANSWER_GRADE_POOL_PROXY  = QUESTION_EXPLAIN_PROXY_V1

EXAM_CANONICAL_ROW_PREFLIGHT = 6/6 表 NOT_PRESENT（alias rows = 0）
DATA_MIGRATION_REQUIRED      = NO
NEW_TABLES_PROPOSED_FOR_H1   = NONE
SCHEMA_CHANGE_REQUIRED_FOR_H1 = NONE

PAST_EXAM_CROSS_SUBJECT_IDENTITY_RISK = ASSESSED → DEFERRED_TO_H2

REAL_APP_DB_MUTATED = NO

TARGETED_TESTS     = PASS（50 新增）
FULL_BACKEND_TESTS = PASS（712 passed / 0 failed；baseline 662）

STEP7H1_COMPLETE = YES
STEP7H1          = FROZEN
STEP7H2_READY    = YES
```

---

## 20. 未决 / 交给后续 STEP

```text
① H2 gate：past_exam 的 source_id 在不同 subject/module 下是否全局唯一 —— 必须实测；
   不唯一则先设计 subject/module-aware scope，再谈 namespace/数据迁移。
② H2：真题 builder 整表 DELETE+INSERT 导致 exam_question_bank.id 漂移（D6）——
   建议把真题的稳定引用改为 (subject_key, year, question_number)，而非自增 id。
③ H3：_grade_big_question 迁移（D3：无授权 / 无计费 / 结果在题库命中时被丢弃），
   已批准的 capability = answer.grade，本处仍走 provider 直连。
④ H4：EXAM_PROFILE 落点设计（§16）、多 track/subject catalog、第一门非 408 科目的
   真实内容导入 —— 均需用户明确批准。
⑤ 部署硬化：14 张 exam 表无 Alembic 覆盖（D7）。
⑥ Parser Infra：OCR 全路径不计费/不记录（D8）。
⑦ D5：exam_favorite_questions_v2 死表 → DELETE-LATER（本轮未 drop）。
⑧ exam_11408 的 legacy 会员/额度维度未动，随统一会员落地一并退役。
```
