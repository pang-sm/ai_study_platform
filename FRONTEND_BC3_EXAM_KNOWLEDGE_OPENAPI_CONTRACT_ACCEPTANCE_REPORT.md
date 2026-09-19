# FRONTEND_BC3_EXAM_KNOWLEDGE_OPENAPI_CONTRACT_ACCEPTANCE_REPORT

> 智学AI · Frontend Blocker BC3 — CS408 Knowledge / Study-Plan OpenAPI Contract Closure
> 生成：2026-09-17 · 本轮为 **CONTRACT CLOSURE**（后端声明面变更，无产品语义变更）
> 上游：`FRONTEND_F1C1_CS408_KNOWLEDGE_CONTRACT_GAP.md`（BLOCKED）
> 结论：`FRONTEND_F1C1_BLOCKER_RESOLVED = YES`

---

## 1. Contract Gap

`FRONTEND_F1C1_CS408_KNOWLEDGE_CONTRACT_GAP.md` 记录：Codex 完成 contract audit，
没有实施 F1C1 UI，因为两个既有 endpoint 的 OpenAPI 200 response 是空的：

```text
GET   /exam/11408/subjects/{subject_key}/study-plan
      → 200 application/json = {}          → generated TS = unknown

PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}
      → request 已 typed（ExamStudyPlanKnowledgeItemUpdate）
        200 application/json = {}          → generated TS = unknown
```

根因：FastAPI handler 返回裸 `dict`，没有 `response_model`，OpenAPI 里就没有 schema。
前端政策**禁止手写 transport DTO / unknown cast / 自行猜 TS interface**，
所以必须由冻结的 endpoint 自己声明。

本轮**不是**新功能、**不是** STEP7H 重开、**不是** F1C1 实现 ——
只给两个已冻结的 handler 补 OpenAPI success typing。

---

## 2. Runtime Shape Audit

**方法**：先读真实代码（两个 handler + `_attach_knowledge_map_status` /
`_build_study_plan_tree` / `_serialize_map_progress` / `_serialize_task` /
`learning/spaces/exam_prep/knowledge.py` 的 canonical writer），
再用 temp DB **实跑**取真实响应。**未从 F1C1/F0 文档反推 schema。**

覆盖矩阵（真实执行，非构造）：

| 维度 | 覆盖 |
| --- | --- |
| module | `data_structure` / `computer_organization` / `operating_system` / `computer_network` |
| 用户态 | 全新无 progress · 有 progress · 有 settings 行 · 有 task · 有 chapter-practice |
| progress 状态 | `not_started` / `learning` / `mastered` / `mastered`+已到期 / `mastered`+未到期 / `review_due` |
| nullable | 所有可空列同时为 NULL（`status` / `user_confirmed_status` / `system_suggested_status` / `ai_recommended_status` / `ai_assessment` / `learned_at` / `review_due_at` / `review_interval_days` / `updated_at`；settings 四个可空列） |
| legacy / 未知值 | raw status = `已掌握`、`user_confirmed_status` = `未学习`、raw status = `some_future_state` |
| stale branch | progress 行存在但 code 不在当前 seed（`legacy:ghost`） |
| PATCH | 4 种合法状态 · same-state 重复 · title override · 其它 module · 非法 status / 非法 code / 非叶节点 / 非法 module |
| 认证 | 未认证 401 · free plan 403 |

### 2.1 KNOWLEDGE_RUNTIME_RESPONSE_MATRIX

**顶层（9 键，恒在）**

| field | type | required | nullable |
| --- | --- | --- | --- |
| `course_id` | str | 是 | 否 |
| `course_name` | str | 是 | 否 |
| `subject_key` | str | 是 | 否 |
| `subject_name` | str | 是 | 否 |
| `settings` | object(6) | 是 | 否 |
| `stats` | object(8) | 是 | 否 |
| `review_interval_days` | int | 是 | 否 |
| `chapters` | array | 是 | 否 |
| `tasks` | array | 是 | 否 |

**`settings`**（6 键恒在）

| field | type | nullable | 说明 |
| --- | --- | --- | --- |
| `learning_goal` | str | **是** | 有 settings 行时直接透传可空列 |
| `start_date` | str | **是** | 同上 |
| `daily_hours` | str | **是** | 同上 |
| `weekly_days` | int | **是** | 同上（实测 NULL → `null`） |
| `review_strategy` | str | **是** | 同上（DB default 通常填 `sequential`） |
| `show_completed` | bool | 否 | 列 NOT NULL |

**`stats`**（8 键恒在）：`total_knowledge_points` / `mastered` / `total_sections` /
`sections_completed` / `sections_learning` / `sections_not_started` /
`overall_progress` 全部 int；`overall_status` ∈ `{not_started, learning, completed}`。

**树：真实层级 = 4 层（chapter → section → node → leaf）**
（用 seed 实测 depth histogram：data_structure `8/32/93/143`、
computer_organization `7/28/100/169`、operating_system `5/18/84/193`、
computer_network `6/28/94/118`）

| 层 | 键数 | 键集合 |
| --- | --- | --- |
| chapter (depth 0) | 17 | `code,title,children,chapter_no,id,is_leaf,status,stored_status,user_confirmed_status,system_suggested_status,ai_recommended_status,ai_assessment,status_counts,chapter_completion_rate,chapter_status,section_count,sections_completed` |
| section (depth 1) | 16 (+`optional`) | `code,title,children,[optional],id,is_leaf,status,stored_status,user_confirmed_status,system_suggested_status,ai_recommended_status,ai_assessment,status_counts,leaf_stats,chapter_practice_completed,section_status,completion_rate` |
| node (depth ≥2) | 12 (+`optional`, +progress block) | `code,title,children,[optional],id,is_leaf,status,stored_status,user_confirmed_status,system_suggested_status,ai_recommended_status,ai_assessment,[progress,learned_at,review_due_at,review_interval_days],status_counts` |

**`progress` 块**（14 键，仅当该节点有 progress 行）：

| field | type | nullable |
| --- | --- | --- |
| `id` | int | 否 |
| `course_id` | str | 否 |
| `knowledge_point_code` | str | 否 |
| `knowledge_point_title` | str | 否（`or ""`） |
| `status` | enum(4) | 否 |
| `stored_status` | str | 否（`or "not_started"`） |
| `user_confirmed_status` | str | 否（`or <display>`） |
| `system_suggested_status` | str | **是** |
| `ai_recommended_status` | str | **是** |
| `ai_assessment` | str | **是** |
| `learned_at` | str | **是** |
| `review_due_at` | str | **是** |
| `review_interval_days` | int | 否（`or 7`） |
| `updated_at` | str | **是** |

**`tasks[]` 元素**（18 键，来自 `_serialize_task`）：见 §4 `ExamStudyPlanTaskItem`。

**PATCH 200**（5 键恒在）：见 §5。

### 2.2 条件键（必须保留，不能变成凭空出现的 `null`）

实测只有两类键是**真条件键**：

* `optional` —— 只存在于 data_structure 的 **4 个** seed 节点（值恒 `true`），
  其余三个 module 完全没有这个键；
* `progress` + `learned_at` + `review_due_at` + `review_interval_days` ——
  只在节点有 progress 行时一起出现。

模型对这两组一律给 `= None` 默认值，并用 `response_model_exclude_unset=True` 挂载，
**缺键就保持缺键**，不会凭空补一个 `null`（补 `null` 等于新增字段）。

---

## 3. GET Study Plan Response Schema

`GET /exam/11408/subjects/{subject_key}/study-plan`
→ `response_model=ExamStudyPlanResponse, response_model_exclude_unset=True`

```text
ExamStudyPlanResponse
├── course_id / course_name / subject_key / subject_name      str
├── settings         → ExamStudyPlanSettings
├── stats            → ExamStudyPlanStats
├── review_interval_days                                      int
├── chapters         → ExamStudyPlanChapter[]
│     ├── (17 个 chapter 字段，含 chapter_no / chapter_status / section_count …)
│     └── children   → ExamStudyPlanSection[]
│           ├── (16 个 section 字段，含 leaf_stats / section_status / completion_rate)
│           └── children → ExamStudyPlanKnowledgeNode[]   ← 自引用递归
│                 └── children → ExamStudyPlanKnowledgeNode[]
└── tasks            → ExamStudyPlanTaskItem[]
```

字段声明顺序刻意等于**运行时 dict 插入顺序**（见 §7 等价性说明）。

**未创造任何前端想要的字段**：F1C1 文档想要的 module / chapter / leaf 层级、
point code、title、status、review 字段——全部本来就在 payload 里，按实际 shape 声明。
runtime 不返回的字段（如 section 的 `id` 之外的任何人工 id、`children_count` 等）
一个都没有加。

---

## 4. PATCH Knowledge Response Schema

`PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}`
→ `response_model=ExamKnowledgeItemUpdateResponse`

| field | type | 说明 |
| --- | --- | --- |
| `success` | bool | 恒 `true`（失败走 400/401/403/404） |
| `knowledge_point_code` | str | = `item_code` |
| `knowledge_point_title` | str | canonical title（seed title 优先） |
| `status` | enum(4) | **display** status（`_display_map_progress_status`） |
| `stored_status` | str | writer 写进行的 raw status |

实测四种状态、same-state 重复、title override、跨 module 全部返回同一 5 键形状。
**request model 未改动**（`ExamStudyPlanKnowledgeItemUpdate` 原样复用）。

---

## 5. Hierarchy / Status Semantics

**层级**：真实只有 chapter → section → node → leaf 四层，且 node 自引用递归
（`ExamStudyPlanKnowledgeNode.children: list[ExamStudyPlanKnowledgeNode]`），
所以任意 seed 深度都被类型覆盖。
**没有**创造 `section`/`subsection`/`children_count` 这类 backend 不存在的结构。

**状态 vocabularies（全部来自真实代码，闭集，并配防漂移测试）**：

| 字段 | 值域 | 来源 |
| --- | --- | --- |
| 节点 `status` | `not_started / learning / mastered / review_due` | `KNOWLEDGE_LEARNING_STATUSES` + `_compute_aggregate_status` |
| 节点 `status_counts` 键 | 同上 4 个 | `_collect_leaf_statuses` |
| `chapter_status` / `section_status` / `stats.overall_status` | `not_started / learning / completed` | `_build_study_plan_tree` / handler |
| task `computed_status` / `status` | `not_started / in_progress / completed` | `_compute_task_completion` |
| task `action_target` | `knowledge_map / practice_center` | 同上 |
| PATCH `status` | 同节点 status | `_display_map_progress_status` |

**刻意保持开放的字符串**（有实测依据，不是偷懒）：

* `stored_status`（node **和** progress）—— raw 列值直接透传（`progress.status if
  progress else "not_started"`），实测可为 `已掌握` / `some_future_state` / **`null`**；
* `user_confirmed_status`（node 和 progress）—— 实测可为 `未学习` / `learning` / `null`；
* `system_suggested_status` / `ai_recommended_status` —— 自由列，course_learning 空间也会写；
* `task_type` / `scope_type` / `completion_reason` —— 自由列 / 中文自由文案。

把它写成 Literal 等于编造 backend 不存在的约束；前端可见文案映射（未学习/学习中/已学习/待复习）
仍由 frontend 负责，**BC3 未改任何用户文案**。

---

## 6. Nullable / Union Branches

**没有宽/窄 union**：每一层只有一种模型，不存在 BC1 那种「宽 payload 被窄模型匹配」的风险。
因此**没有机械地给所有 model 加 `extra="forbid"`**；只在三层树模型
（`ExamStudyPlanChapter` / `ExamStudyPlanSection` / `ExamStudyPlanKnowledgeNode`）上加，
理由是：这三层的键**部分来自静态 seed 文件**，`extra="ignore"`（pydantic 默认）
会让一个未来新增的 seed 键被**静默裁掉**；`forbid` 让这种情况变成响亮的失败。

配套两条测试证明今天没有裁剪：

* `test_ab_seed_keys_are_all_modelled` —— 扫描四个真实 seed 文件每一层的键集，
  断言它们全部落在对应模型的字段里；
* `test_m_round_trip_preserves_every_key` —— 把真实响应的 JSON 再 `model_validate`
  后 `model_dump(exclude_unset=True)`，逐字节回到自身。

**显式 nullable（实测确认，非推测）**：

| 字段 | nullable 依据 |
| --- | --- |
| `settings.learning_goal / start_date / daily_hours / weekly_days / review_strategy` | 列可空 + handler 在有 settings 行时直接透传（实测 NULL → `null`） |
| `settings.show_completed` | 列 NOT NULL → 不可空 |
| node `stored_status` | 实测 `null`（raw `status` 为 NULL 时透传） |
| node `user_confirmed_status` | 实测 `null` |
| node `system_suggested_status` / `ai_recommended_status` / `ai_assessment` | 实测 `null` 与 str 都出现 |
| node `learned_at` / `review_due_at` | 实测 `null` 与 str 都出现 |
| progress `updated_at` / `learned_at` / `review_due_at` | handler 带 `if ... else None` 守卫 |
| task `created_at` / `updated_at` | 同上 |

**反向检查**（§8 点名的风险）：`progress.stored_status` /
`progress.user_confirmed_status` / `progress.review_interval_days` / node
`review_interval_days` / `status_counts` / `leaf_stats` 都由 `or <fallback>` **收敛**过，
不可空 —— 已按不可空声明。

---

## 7. Runtime Equivalence

```text
RUNTIME_RESPONSE_CHANGED = NO
```

**验证方法（不依赖手抄期望值）**：在同一 temp DB 上，用**同样的两个 handler 函数**
再挂一个 `FastAPI()` app 且**不带 `response_model`** —— 那就是逐字节的改动前路由；
两个 app 共用同一 session cookie，对同一 URL 各发一次请求后比较。

硬 gate = **canonical JSON 等价**：`json.dumps(parsed, sort_keys=True)` 逐字符相等。
它**忽略键顺序**但**严格区分类型**（`0` 与 `0.0` 文本不同），比「逐字段等价」更强。

```text
21/21 cases  CANONICAL_EQUIVALENCE = PASS
17/21 cases  BYTE_IDENTICAL
```

| case | 状态码 | canonical | byte |
| --- | --- | --- | --- |
| GET 全新用户 × 4 module | 200/200 | SAME | data_structure ✅ · computer_organization ✅ · operating_system ❌ · computer_network ❌ |
| GET 有数据用户 × 4 module | 200/200 | SAME | 同上 |
| PATCH `learning` / `mastered` / same-state / `review_due` / `not_started` / 第二次 `learning` | 200/200 | SAME | ✅ |
| PATCH 跨 module（computer_network） | 200/200 | SAME | ✅ |
| PATCH title override | 200/200 | SAME | ✅ |
| PATCH 非法 status / 非法 code / 非叶节点 / 非法 module | 400/404/400/400 | SAME | ✅ |
| GET 非法 module | 400/400 | SAME | ✅ |

### 7.1 为什么有 4 个 case 不是逐字节相同（如实说明）

`operating_system` 与 `computer_network` 的 GET **改动前**就与另外两个 module
**键序不同**：这两个 seed 文件的 chapter 键序是
`code, title, chapter_no, children`，另两个是 `code, title, children, chapter_no`
（实测，见下）。**这是改动前就存在的 handler 输出性质，不是 BC3 引入的。**

```text
after  chapter keys: [code, title, children, chapter_no, id, is_leaf, …]
before chapter keys: [code, title, chapter_no, children, id, is_leaf, …]
canonical equal: True
every object has identical key SET: True
first byte divergence at offset 523:  'children':[{…'  vs  'chapter_no':1,'children':[…'
```

即：**任何单一 pydantic 字段顺序都不可能同时复现两组 module 的键序**。
§14 明确允许「逐字节**或** canonical JSON 逐字段等价」，本轮采用后者，
并用程序证明差异**仅为键顺序**（每个对象的键集相同、值相同、类型相同，
canonical 文本完全相同）。

---

## 8. Error Equivalence

```text
ERROR_SEMANTICS_CHANGED = NO
```

| 情形 | 改动前 | 改动后 |
| --- | --- | --- |
| 非法 subject（GET / PATCH） | 400 `Unknown subject: …` | 同，body 逐字节相同 |
| 非法 knowledge code | 404 `knowledge point is not in this course map` | 同 |
| 非叶节点 | 400 `Only leaf knowledge points can be manually updated` | 同 |
| 非法 status | 400 `Invalid status: bogus` | 同 |
| 未认证 | 401 | 同 |
| free plan（无 `learning_plan`） | 403 `FEATURE_REQUIRES_UPGRADE` | 同 |
| request body 缺字段 | 422 | 同 |

**未声明任何 error model**：两个 endpoint 的 `responses` 断言 ⊆ `{200, 422}`，
与改动前一致。未顺手重做全局 error schema。

---

## 9. OpenAPI Proof

```text
OPENAPI_SUCCESS_RESPONSE_UNKNOWN = 0
```

| method | path | 改动前 200 schema | 改动后 200 schema |
| --- | --- | --- | --- |
| GET | `/exam/11408/subjects/{subject_key}/study-plan` | `{}` | `$ref → ExamStudyPlanResponse` |
| PATCH | `/exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}` | `{}` | `$ref → ExamKnowledgeItemUpdateResponse` |

新增 11 个 component schema（无基类泄漏、无 `additionalProperties: true`、无空 `{}`）：

```text
ExamStudyPlanResponse · ExamStudyPlanSettings · ExamStudyPlanStats
ExamStudyPlanChapter · ExamStudyPlanSection · ExamStudyPlanKnowledgeNode
ExamStudyPlanTaskItem · ExamKnowledgeProgressDetail
ExamKnowledgeStatusCounts · ExamStudyPlanLeafStats · ExamKnowledgeItemUpdateResponse
```

已断言：nested `$ref` 关系、array item `$ref`、`required` 列表与实际键集一致、
`Literal` enum 值、`optional` / `progress` **不在** required 中。

---

## 10. Generated TypeScript Proof

```text
GENERATED_TS_KNOWLEDGE_RESPONSE_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO     = 0
```

用**仓库既有生成器**（`openapi-typescript@7.13.0`，即 `npm run api:generate` 的同一工具与版本）
从**当前代码**导出的 OpenAPI 重新生成 `frontend/src/types/api.ts`。**未手改**（保留 auto-generated 头）。

diff 精确等于本次变更：

```text
2 lines changed     "application/json": unknown;  →  具体 $ref
347 lines added     11 个 component schema
0                   其它 operation 的任何改动
```

生成结果：

```ts
// GET
200: { content: { "application/json": components["schemas"]["ExamStudyPlanResponse"] } }
// PATCH
200: { content: { "application/json": components["schemas"]["ExamKnowledgeItemUpdateResponse"] } }
```

**生成类型可直接表达真实层级 / 状态 / PATCH 结果**（摘自生成文件）：

```ts
ExamStudyPlanKnowledgeNode: {
    code: string; title: string;
    children: components["schemas"]["ExamStudyPlanKnowledgeNode"][];   // 递归
    optional?: boolean | null;                                         // 真条件键
    is_leaf: boolean;
    status: "not_started" | "learning" | "mastered" | "review_due";    // 闭集
    stored_status: string | null;                                      // 实测可 null
    progress?: components["schemas"]["ExamKnowledgeProgressDetail"] | null;
    status_counts: components["schemas"]["ExamKnowledgeStatusCounts"];
};
ExamStudyPlanSettings: { …, weekly_days: number | null, … };
ExamKnowledgeItemUpdateResponse: {
    success: boolean; knowledge_point_code: string; knowledge_point_title: string;
    status: "not_started" | "learning" | "mastered" | "review_due"; stored_status: string;
};
```

### 10.1 生成方式说明（如实记录）

`package.json` 的 `api:generate` 硬编码 `http://localhost:8000/openapi.json`；
本机 8000 端口存在一个**早先遗留的后端进程**（服务的是改动前代码，BC1/BC2 已记录）。
延续 BC1/BC2 已验收的等价方式：

```text
npx openapi-typescript <temp>/bc3_openapi.json -o src/types/api.ts
✨ openapi-typescript 7.13.0 · 251.8ms · exit 0
```

同工具、同版本、同 spec 来源、同输出路径；**未修改 `package.json`**。

---

## 11. DB Safety

```text
REAL backend/app.db
  mtime           = 2026-09-16 21:24:23（改动前后均未变；本轮为 09-17）
  SHA256 改动前   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  SHA256 改动后   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  integrity_check = ok
  表总数           = 72
  exam_question_bank = 9333 · programming_exercises = 1923 · knowledge_points = 32
  alembic_version table = 不存在（真实库从未被迁移）

REAL_APP_DB_MUTATED = NO
DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
```

所有 `import main` / `TestClient` / OpenAPI 导出 / pytest 均在显式
`DATABASE_URL=sqlite:///<temp>`（`tempfile.mkdtemp()`）下执行。
真实 `app.db` 仅被**只读**打开（`mode=ro`）做 fingerprint。

Git：`HEAD = ebad5282`（未变）；无 commit / push / reset / clean / restore / stash /
merge / rebase / pull / worktree。

---

## 12. Protected Semantics

```text
STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
BACKEND_PRODUCT_SEMANTICS_CHANGED = NO
```

新增测试直接**通过 PATCH 路由**（不是直接调 writer）断言：

* `service_namespace` = `exam_prep`；
* event `subject_key` = `cs_408`（**不是** module）；
* `knowledge_point_ref_json.exam_module_id` = 被修改的 module，且 **无** `exam_track_id`；
* legacy scope id = `<module>_11408`（row `course_id`）；
* writer 的 `knowledge_point_id = 0` 哨兵未变；
* same-state 重复写入 **不产生第二个 event**。

未改动：`learning/spaces/exam_prep/knowledge.py`（canonical writer）、
`EXAM_NAMESPACE` / `EXAM_SUBJECT_ID`、`resolve_exam_scope_id`、
StudentTwin 任何 eligibility 判定、任何 AI / 模型路径。
`knowledge_points` 仍为 **32**（programming ontology），exam knowledge 仍来自
静态 seed knowledge maps，与 `KnowledgePoint` SQL entity 无关。

---

## 13. Backend Tests

新增 `backend/tests/test_exam_knowledge_openapi_contract.py` —— **58 passed / 0 failed / 0 skipped**。

| 要求 | 测试 |
| --- | --- |
| A. GET concrete response schema | `test_a_get_study_plan_success_schema_is_concrete` |
| B. PATCH concrete response schema | `test_b_patch_knowledge_success_schema_is_concrete` |
| （防伪）改动前确实是空 schema | `test_a_b_before_state_really_was_empty` |
| 模型结构化 / 无 Any-Dict 逃逸 / required 与实际一致 / 层级与 enum | `test_ab_declared_models_exist_and_are_structured`（11 参数化）· `test_ab_no_any_or_dict_escape_hatch` · `test_ab_required_lists_match_the_real_payload_keys` · `test_ab_hierarchy_is_typed_recursively` · `test_ab_status_enum_is_closed` · `test_ab_legacy_status_columns_stay_open_strings` |
| 防漂移（enum 与 handler 源码比对） | `test_ab_status_enum_cannot_drift_from_the_handler` · `test_ab_task_enum_cannot_drift_from_the_serializer` |
| 无 error model | `test_ab_no_error_models_were_added` |
| C. 4 module GET runtime validation | `test_c_every_module_returns_the_declared_top_level_shape`（4 参数化） |
| D. empty / new-user response | `test_d_new_user_payload_is_empty_but_fully_typed` |
| E. populated response | `test_e_populated_payload_carries_progress_tasks_and_settings` |
| F. 全部状态枚举变体 | `test_f_all_four_statuses_are_reachable_and_keep_their_shape` |
| G. nullable 分支 | `test_g_nullable_branches_are_preserved` · `test_g_stale_progress_codes_are_not_injected_into_the_tree` |
| H. PATCH status update | `test_h_patch_update_returns_the_declared_shape` · `test_h_patch_accepts_every_declared_status`（4 参数化）· `test_h_patch_mastered_then_due_surfaces_as_review_due_through_get` |
| I. PATCH same-state | `test_i_patch_same_state_is_idempotent` |
| J. invalid module error unchanged | `test_j_invalid_module_errors_are_unchanged` |
| K. invalid knowledge code error unchanged | `test_k_invalid_knowledge_code_errors_are_unchanged` · `test_k_unauthenticated_is_still_401` · `test_k_unentitled_is_still_403` |
| L. before/after response equivalence | `test_l_get_payload_is_canonically_equivalent_to_the_untyped_route`（4 参数化）· `test_l_populated_get_is_canonically_equivalent` · `test_l_patch_response_is_canonically_equivalent`（4 参数化）· `test_l_error_bodies_are_canonically_equivalent` |
| M. no field stripping | `test_m_no_field_is_stripped_by_the_response_model` · `test_m_round_trip_preserves_every_key` · `test_ab_seed_keys_are_all_modelled` |
| 受保护语义 | `test_typed_patch_route_still_emits_the_canonical_exam_event` · `test_repeat_write_of_the_same_status_emits_nothing` |
| 生成 TS 不是 unknown | `test_generated_typescript_knowledge_responses_are_not_unknown` |

```text
TARGETED_TESTS（BC3 + BC1 + BC2 + exam final/framework/practice_records/prep_namespace）
                                          = 309 passed / 0 failed
FULL_BACKEND_TESTS（backend/ pytest 全量）
                                          = 1003 passed / 0 failed
  本轮 baseline（BC2）= 945；本轮新增 58  →  1003
```

---

## 14. Frontend Regression

```text
FRONTEND_TYPECHECK    = PASS（0 error）
FRONTEND_LINT         = PASS（0 error）
FRONTEND_UNIT_TESTS   = PASS（9 files / 22 tests）
FRONTEND_BUILD        = PASS
```

**本轮未做任何 F1C1 UI 实现**（无页面、无路由、无组件、无查询、无 mutation、无 CSS）。

### 14.1 Compile-level probe（§19，已删除）

临时新建 `frontend/src/types/__bc3_compile_probe.ts`，用 `tsc --noEmit` 证明
generated type 真的可用，**检查后已删除**，未留下文件。它验证了：

* `GetBody` / `PatchBody` **不是 `unknown`、也不是 `any`**（`IsAny<T>` 类型级断言）；
* 可访问真实层级字段：`chapters[].children[].children[].{code,title,status,is_leaf,status_counts,optional}`，
  以及递归的 `leaf.children[0]?.children[0]?.status`；
* 条件 `progress` 块可在无 cast 的情况下按 `if (leaf.progress)` 读取；
* `settings.weekly_days`、`stats.overall_status`、`task.computed_status`、
  `task.action_target`、PATCH 的 5 个字段全部可读。

**反向证明**（证明类型不是 `any`）：故意写入三处非法访问，`tsc` 全部报错 ——

```text
TS2339  Property 'this_field_does_not_exist' does not exist on type '{ course_id: string; … }'
TS2367  … '"not_started" | "learning" | "mastered" | "review_due"' and '"bogus_status"' have no overlap
TS2339  Property 'no_such_patch_field' does not exist on type '{ success: boolean; … }'
```

确认后删除该文件，再跑一次 `typecheck` 仍为 PASS。

---

## 15. Changed Files

| file | 变更 | 理由 |
| --- | --- | --- |
| `backend/main.py` | 在 `_build_study_plan_tree` 之后、GET handler 之前**新增 11 个 response model + 4 个 `Literal` 别名**（约 200 行）；GET decorator 加 `response_model=…, response_model_exclude_unset=True`；PATCH decorator 加 `response_model=…` | 契约唯一来源（这两个 endpoint 仍在 main.py）；**两个 handler 函数体一行未改**，未搬 route |
| `backend/tests/test_exam_knowledge_openapi_contract.py` | **新建** | 等价性 + OpenAPI + 生成产物 + 受保护语义断言（58 tests） |
| `frontend/src/types/api.ts` | **重新生成**（自动产物，2 行改 / 347 行增） | 本 blocker 的直接产物；未手改 |
| `FRONTEND_BC3_EXAM_KNOWLEDGE_OPENAPI_CONTRACT_ACCEPTANCE_REPORT.md` | **新建** | 本报告 |
| `FRONTEND_F1C1_CS408_KNOWLEDGE_CONTRACT_GAP.md` | 状态由 BLOCKED 改为 RESOLVED | 同一 blocker 的入口文档，需与结论一致 |

**未改**：canonical exam writer、`learning/spaces/exam_prep/**`、`routers/**`、
`schemas.py`（request model 原样复用）、`models.py`、任何其它 endpoint、
任何 handler body、migration、`backend/app.db`、任何前端 UI。

---

## 16. Final Gates

```text
GET_STUDY_PLAN_RESPONSE_MODEL          = PASS
PATCH_KNOWLEDGE_RESPONSE_MODEL         = PASS
KNOWLEDGE_HIERARCHY_TYPED              = PASS
KNOWLEDGE_STATUS_TYPED                 = PASS
PATCH_RESULT_TYPED                     = PASS

RUNTIME_RESPONSE_CHANGED               = NO
ERROR_SEMANTICS_CHANGED                = NO

OPENAPI_SUCCESS_RESPONSE_UNKNOWN       = 0
GENERATED_TS_KNOWLEDGE_RESPONSE_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO    = 0

BACKEND_PRODUCT_SEMANTICS_CHANGED      = NO
DB_SCHEMA_CHANGED                      = NO
MIGRATION_ADDED                        = NO
STUDENT_TWIN_ELIGIBILITY_EXPANDED      = NO
REAL_APP_DB_MUTATED                    = NO

TARGETED_TESTS                         = PASS（309 passed / 0 failed）
FULL_BACKEND_TESTS                     = PASS（1003 passed / 0 failed / 518.02s）

FRONTEND_TYPECHECK                     = PASS
FRONTEND_LINT                          = PASS
FRONTEND_UNIT_TESTS                    = PASS
FRONTEND_BUILD                         = PASS

FRONTEND_F1C1_BLOCKER_RESOLVED         = YES
```

---

## 17. 观察（不属本轮，未处理）

① `frontend/src/types/api.ts` 中仍有大量其它 endpoint 的 `"application/json": unknown`
   （未声明 `response_model` 的历史路由）。BC3 只闭合 F1C1 依赖的这两条；
   是否继续闭合其余属后续 BC 项，需用户决定。

② 本机 **8000 端口遗留后端进程**仍在（BC1 起已记录），服务的是改动前代码。
   本轮未终止它；`api.ts` 因此采用 BC1/BC2 已验收的「当前代码导出 spec + 同版本生成器」方式。

③ 四个 seed knowledge map 的 chapter 键序不一致（两个是 `children` 在前，两个是
   `chapter_no` 在前），导致 GET 无法对全部 module 做到逐字节一致。
   这是**改动前就存在**的静态内容性质；若希望四个 module 字节统一，
   需要单独立项调整 seed 文件（属内容变更，不属本轮 contract closure）。

④ 跑全量后端测试会刷新 `backend/cache/**` 的 mtime（OCR/feasibility 缓存）。
   属既有测试副作用，与本轮无关。
