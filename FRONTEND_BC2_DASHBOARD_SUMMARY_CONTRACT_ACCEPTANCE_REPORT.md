# FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_ACCEPTANCE_REPORT

> 智学AI · Frontend Blocker BC2 — CS408 Dashboard Summary OpenAPI Response Contract Closure
> 生成：2026-09-17 · 本轮为 **CONTRACT CLOSURE**（后端声明面变更，无产品语义变更）
> 上游：`FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_GAP.md`（BLOCKED）
> 结论：`FRONTEND_F1B2_BLOCKER_RESOLVED = YES`

---

## 1. 问题

`GET /exam/11408/subjects/{subject_key}/dashboard-summary` 是 F1B2（CS408 workspace）的实际数据源，
但它的 OpenAPI 200 response 是空的：

```text
200 application/json → {}          # FastAPI 裸 dict handler
```

于是 `frontend/src/types/api.ts` 里该 operation 的 200 body 生成成 `unknown`。
前端政策**禁止手写 transport DTO**，所以必须由冻结的 endpoint 自己声明 response model。

本轮**不是**新功能、**不是** STEP7H 重开、**不是** Exam 后端扩展、**不是** F1B2 实现 ——
只给已冻结的 handler 补 OpenAPI success typing。

---

## 2. Git / DB Safety

```text
HEAD = ebad5282（未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree / branch
```

所有 `import main` / `TestClient` / OpenAPI 导出 / alembic 相关动作全部在显式
`DATABASE_URL=sqlite:///<temp>`（`tempfile.mkdtemp()`）下执行。
真实 `backend/app.db` 仅被**只读**打开（`mode=ro`）做过 fingerprint。

```text
REAL backend/app.db
  mtime           = 2026-09-16 21:24:23（本轮为 09-17，改动前后均未变）
  SHA256 改动前   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  SHA256 改动后   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  integrity_check = ok
  表总数           = 72
  exam_question_bank = 9333 · programming_exercises = 1923 · knowledge_points = 32
  alembic_version table = 不存在（真实库从未被迁移，与 STEP7H5 / BC1 记录一致）

REAL_APP_DB_MUTATED = NO
DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
```

> 说明：`backend/app.db-shm`（WAL 索引，.gitignore 第 27 行已忽略）mtime 会因任何
> 只读打开而刷新。`app.db` 本体 mtime 与 SHA256 均未变。

---

## 3. HANDLER AUDIT — 真实 runtime payload

先读 handler（`backend/main.py` 内 `get_exam_subject_dashboard_summary`，非 router），
再用 temp DB **实跑**取真实响应；**未从 F0/F1B2 文档反向猜字段**。

### 3.1 顶层（6 键，恒在）

| field | type | 说明 |
| --- | --- | --- |
| `subject_key` | str | 回显路径参数 |
| `subject_name` | str | `EXAM_SUBJECT_DIRS[subject_key]` |
| `overview` | object | 见 3.2 |
| `today_plan` | list | 见 3.3 |
| `materials` | object | 见 3.4 |
| `quota` | object | 见 3.5 |

### 3.2 `overview` — 4 个 int，单 shape

| field | 来源 | 类型 |
| --- | --- | --- |
| `total_chapters` | `len(raw_chapters)` | int |
| `total_knowledge_points` | `_count_knowledge_map_points()`（递归计数，返回 `int`） | int |
| `learned_percent` | `round(mastered/total*100)` 或 `0` | int |
| `study_minutes` | `sum(_minutes_between(...))` | int |

实测：`{"total_chapters":8,"total_knowledge_points":196,"learned_percent":0,"study_minutes":13}`

### 3.3 `today_plan` — 单 shape 元素，可为空数组

字段顺序即 dict 插入顺序：`id / title / knowledge_point_name / task_type / computed_status / due_date`

| field | 来源 | 类型 |
| --- | --- | --- |
| `id` | `ExamStudyPlanTask.id`（`Column(Integer, primary_key=True)`） | int |
| `title` | `title` | str |
| `knowledge_point_name` | `knowledge_point_name or secondary_knowledge or ""` | str |
| `task_type` | `task_type or "knowledge"` | **自由字符串**（DB 列，非枚举） |
| `computed_status` | `_compute_task_completion(...)[0]` | **闭集**（见 3.6） |
| `due_date` | `due_date or ""` | str |

`id: int` 经实测确认（JSON 里是真整数，不是字符串）。

### 3.4 `materials` — 5 个 int，单 shape

`lecture_notes / exercises / references / code_examples / total_materials`，全部 int
（`total_materials = len(mat_rows)`）。

### 3.5 `quota` — **两种真实数值 shape**

handler 里 `quota` 的三项各自形态不同，这不是猜测，是算术决定的：

| key | `used` | `limit` | `remaining` | `unit` |
| --- | --- | --- | --- | --- |
| `ai_chat` | `sum(1 for ...)` → **int** | `int(...)` → int | `max(0, int-int)` → **int** | `"次"` |
| `ai_question` | 同上 → **int** | int | **int** | `"次"` |
| `material_upload` | `round(bytes/1048576, 2)` → **float** | `int(...)` → int | 见下 | `"MB"` |

`material_upload.remaining` 是 `max(0, mat_limit_mb - material_used_mb)`：

* 正常情况 `int - float` = float，`max` 返回该 float → `498.5`
* **超额时** `max(0, 负数)` 返回 **int `0`**，而不是 `0.0`

两者 JSON 文本不同（`0` vs `0.0`），所以按 union 声明，而不是把一种强转成另一种。

实测三种状态：

```text
全新用户     {"used":0.0,  "limit":100, "remaining":100.0, "unit":"MB"}   remaining=float
有数据用户   {"used":1.5,  "limit":500, "remaining":498.5, "unit":"MB"}   remaining=float
超额用户     {"used":900.0,"limit":500, "remaining":0,     "unit":"MB"}   remaining=int
```

（匿名分支 `{"used","limit","remaining"}`（无 `unit`）**不可达**：`get_current_user` 在未认证时
直接 `raise HTTPException(401)`，从不返回 `None`，`if user:` 恒真。因此未为它建模型，
也未改动 handler 里的任何一行。）

### 3.6 `computed_status` 闭集来自源码，不是猜的

`_compute_task_completion` 共 15 条 `return` 语句，第一元只出现：
`not_started` / `in_progress` / `completed`。

---

## 4. Response Models

全部声明在 `backend/main.py`（该 endpoint 的契约所有者；`main.py` 现有的本地 `BaseModel`
风格即如此）。**字段声明顺序刻意等于运行时 dict 插入顺序** —— pydantic 按声明顺序序列化，
这正是字节等价的前提。

| # | model | 用途 |
| --- | --- | --- |
| 1 | `ExamDashboardOverview` | `overview`（4 int） |
| 2 | `ExamDashboardPlanTask` | `today_plan[]` 元素（6 键，含闭集 `computed_status`） |
| 3 | `ExamDashboardMaterials` | `materials`（5 int） |
| 4 | `ExamDashboardCountQuota` | `ai_chat` / `ai_question`（全 int + `unit`） |
| 5 | `ExamDashboardUploadQuota` | `material_upload`（`used: float`，`remaining: int \| float`） |
| 6 | `ExamDashboardQuota` | `{ai_chat, ai_question, material_upload}` |
| 7 | `ExamSubjectDashboardSummaryResponse` | 顶层响应，挂到 `response_model=` |

另加一行 stdlib import：`from typing import Literal`。

### 4.1 拒绝的做法

未使用 `response_model=dict` / `Any` / `Dict[str, Any]` / `RootModel[Any]` / `json_schema_extra` 逃逸 ——
它们会让前端生成类型重新退化为 `unknown`。已用测试断言新模型里**不存在**
`additionalProperties` 与空 schema `{}`。

### 4.2 未做的事

* `task_type` **没有**被写成 enum：它是 DB 自由列，闭集化等于编造约束。
* `computed_status` **只**覆盖源码真实返回的 3 个值，并有防漂移测试（§7 D 项）。
* handler 函数体**一行未改**；路径、method、auth、状态码、DB 查询全部原样。

---

## 5. RUNTIME EQUIVALENCE

```text
RUNTIME_RESPONSE_CHANGED = NO
```

**验证方法（不依赖任何手抄期望值）**：在同一个 temp DB 上，用**同一个 handler 函数**
再挂一个 `FastAPI()` app 且**不带 `response_model`** —— 那就是逐字节的改动前路由；
两个 app 共用同一 session cookie，对同一 URL 各发一次请求，**逐字节比较 JSON 文本**。

覆盖 3 种用户状态 × 4 个 module = **12 组**，全部 byte-identical：

```text
                     data_structure  computer_organization  operating_system  computer_network
全新用户(无数据)          SAME              SAME                 SAME             SAME
有数据用户               SAME              SAME                 SAME             SAME
超额上传用户             SAME              SAME                 SAME             SAME

RUNTIME_RESPONSE_BYTE_IDENTICAL = True
```

错误契约同样逐字节未变：

```text
Unknown subject → 400（body 也与改动前相同）
未认证          → 401
声明状态码集合   = {200, 422}（与改动前一致，未新增 error model）
```

---

## 6. OpenAPI Schema

```text
OPENAPI_200_RESPONSE_UNKNOWN = 0
```

| | 改动前 | 改动后 |
| --- | --- | --- |
| 200 response schema | `{}` | `$ref → ExamSubjectDashboardSummaryResponse` |
| declared responses | `{200, 422}` | `{200, 422}`（未变） |

已断言的具体 schema 细节：

* `ExamSubjectDashboardSummaryResponse.required` = 6 个字段**全部**；
  `overview` / `materials` / `quota` 是 `$ref`；
  `today_plan` = `array[$ref ExamDashboardPlanTask]`。
* `ExamDashboardPlanTask.computed_status` = **closed enum** `["not_started","in_progress","completed"]`；
  `task_type` 保持 `string`（无 enum）；`id` = `integer`。
* `ExamDashboardCountQuota`：`used` / `limit` / `remaining` 全 `integer`。
* `ExamDashboardUploadQuota`：`used` = `number`，`limit` = `integer`，
  `remaining` = `anyOf[integer, number]`。
* `ExamDashboardQuota`：`ai_chat` / `ai_question` → `$ref ExamDashboardCountQuota`，
  `material_upload` → `$ref ExamDashboardUploadQuota`。

---

## 7. Tests

新增 `backend/tests/test_dashboard_summary_openapi_contract.py` —— **35 passed / 0 failed / 0 skipped**。

| 组 | 要求 | 测试 |
| --- | --- | --- |
| A | 4 个 module runtime shape 不变 | `test_a_runtime_shape_is_unchanged_for_every_module`（4 参数化）+ `test_a_today_plan_entry_shape_is_unchanged` + `test_a_quota_keeps_its_int_and_float_sides` + `test_a_over_cap_upload_remaining_is_still_an_int_zero` |
| B | response_model 前后**逐字节**等价 | `test_b_response_model_round_trips_the_handler_byte_for_byte`（4 参数化）+ 空 payload + 超额 payload 各一条 |
| C | OpenAPI 200 具体化 | `test_c_openapi_200_is_a_concrete_ref_not_empty` + `test_c_before_state_really_was_empty` + `test_c_declared_models_exist_and_are_structured`（7 参数化）+ `test_no_any_or_dict_escape_hatch_in_the_new_models` + `test_c_required_lists_match_the_real_payload_keys` + `test_c_nested_objects_and_arrays_are_typed` + `test_c_upload_quota_models_both_real_number_shapes` + `test_c_computed_status_is_a_closed_enum` + `test_c_computed_status_enum_cannot_drift_from_the_handler` + `test_c_task_type_stays_an_open_string` |
| D | 错误契约不变 | `test_d_error_status_codes_are_unchanged` + `test_d_unauthenticated_is_still_401` + `test_d_no_error_models_were_added` + `test_d_unknown_subject_error_body_is_unchanged` |
| E | 生成 TS 不是 unknown | `test_e_generated_typescript_response_is_not_unknown` + `test_e_generated_operation_200_is_not_unknown` |

两条关键防回归：

* **B 组**用的是「同 handler、同 DB、同 cookie、去掉 `response_model`」的真实 before/after，
  不是抄一遍期望 JSON —— 一个靠改 payload 来「修好类型」的改动会在这里失败。
* `test_c_computed_status_enum_cannot_drift_from_the_handler` 用 `inspect.getsource` 从
  `_compute_task_completion` 重新解析出状态集合，与 schema enum 比对；handler 若新增第四种状态，
  测试会失败，而不是让路由开始 500。

### 7.1 测试结果

```text
TARGETED_TESTS（BC2 + BC1 + exam final/framework/practice_records）
                                    = 201 passed / 0 failed
FULL_BACKEND_TESTS（backend/ pytest 全量）
                                    = 945 passed / 0 failed（558.48s）
  本轮 baseline（BC1）= 910；本轮新增 35  →  945
```

---

## 8. TypeScript Generation

```text
GENERATED_TS_RESPONSE_UNKNOWN       = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

用**仓库既有生成器**（`openapi-typescript@7.13.0`，即 `npm run api:generate` 的同一工具与版本）
从**当前代码**的 OpenAPI 重新生成 `frontend/src/types/api.ts`。**未手改**该文件
（顶部保留 auto-generated 头）。

`frontend/src/types/api.ts` 的 diff 精确等于本次变更：

```text
1 line removed   "application/json": unknown;
94 lines added   7 个 component schema + 1 行具体 $ref
                 ↑ 无任何其它 endpoint 相关改动
```

生成结果：

```ts
responses: {
    200: { content: { "application/json": components["schemas"]["ExamSubjectDashboardSummaryResponse"] } };
    422: { content: { "application/json": components["schemas"]["HTTPValidationError"] } };
};
```

### 8.1 生成方式说明（如实记录）

`package.json` 的 `api:generate` 硬编码 `http://localhost:8000/openapi.json`；
本机 8000 端口存在一个**早先遗留的后端进程**（服务的是改动前代码，BC1 已记录）。
为避免动到不属于本轮的进程，改为：把**当前代码**的 OpenAPI 导出到临时 JSON，
再用同一 `openapi-typescript` 二进制对该文件生成到同一输出路径。

```text
npx openapi-typescript <temp>/bc2_openapi.json -o src/types/api.ts
✨ openapi-typescript 7.13.0 · 273.8ms · exit 0
```

产物与跑 `api:generate` 等价（同工具、同版本、同 spec、同输出）；**未修改 `package.json`**。

### 8.2 前端回归（因为动了前端消费的生成文件）

```text
npm run typecheck → PASS（0 error）
npm run lint      → PASS（0 error）
npm run test:run  → 7 files / 19 tests PASS
```

**本轮未做任何前端 UI 修改**（无视觉、无路由、无 React 组件、无 F1B2 实现、无手写 DTO）。

---

## 9. Changed Files

| file | 变更 | 理由 |
| --- | --- | --- |
| `backend/main.py` | `from typing import Literal`（1 行）；`# ── 11408 Subject Dashboard Summary ──` 段下新增 7 个 response model；`@app.get(...)` 加 `response_model=` | 契约唯一来源（该 endpoint 属于 main.py）；**handler 函数体一行未改** |
| `backend/tests/test_dashboard_summary_openapi_contract.py` | **新建** | 等价性 + OpenAPI + 生成产物断言（35 tests） |
| `frontend/src/types/api.ts` | **重新生成**（自动产物，1 行变 / 94 行增） | 本 blocker 的直接产物；未手改 |
| `FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_ACCEPTANCE_REPORT.md` | **新建** | 本报告 |
| `FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_GAP.md` | 状态由 BLOCKED 改为 RESOLVED | 同一 blocker 的入口文档，需与结论一致 |

**未改**：任何其它 endpoint、handler 逻辑、路由 URL / method / 状态码 / auth、
`models.py`、`schemas.py`、`routers/`、migration、`backend/app.db`、任何前端 UI。

---

## 10. Final Gates

```text
DASHBOARD_SUMMARY_RESPONSE_MODEL     = PASS
RUNTIME_RESPONSE_CHANGED             = NO
OPENAPI_200_RESPONSE_UNKNOWN         = 0
GENERATED_TS_RESPONSE_UNKNOWN        = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO  = 0

DB_SCHEMA_CHANGED                    = NO
MIGRATION_ADDED                      = NO
BACKEND_PRODUCT_SEMANTICS_CHANGED    = NO
REAL_APP_DB_MUTATED                  = NO

TARGETED_TESTS                       = PASS（201 passed / 0 failed）
FULL_BACKEND_TESTS                   = PASS（945 passed / 0 failed）

FRONTEND_F1B2_BLOCKER_RESOLVED       = YES
```

---

## 11. 观察（不属本轮，未处理）

① `frontend/src/types/api.ts` 中仍有 **372** 处 `"application/json": unknown`
   （其它未声明 `response_model` 的 endpoint）。BC2 只闭合 dashboard-summary 这一条；
   是否继续闭合其余属后续 BC 项，需用户决定。

② 本机 **8000 端口遗留后端进程**仍在（BC1 已记录），服务的是改动前代码。
   本轮未终止它。若之后要跑标准 `npm run api:generate`，需先让该进程重启加载新代码。

③ `package.json` 的 `api:generate` 依赖手工启动的 8000 端口后端，
   在 CI / 无守护进程环境下不可直接复现。属既有工程债，未在本轮变更。

④ 跑全量后端测试会刷新 `backend/cache/feasibility_q1.jpg` 的 mtime
   （OCR/feasibility 缓存，内容与 git 状态未变）。属既有测试副作用，与本轮无关。
