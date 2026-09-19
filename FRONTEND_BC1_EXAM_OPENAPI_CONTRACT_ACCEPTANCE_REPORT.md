# FRONTEND_BC1_EXAM_OPENAPI_CONTRACT_ACCEPTANCE_REPORT

> 智学AI · Frontend Blocker BC1 — Exam Prep OpenAPI Response Contract Closure
> 生成：2026-09-17 · 本轮为 **CONTRACT CLOSURE**（后端声明面变更，无产品语义变更）
> 上游：`FRONTEND_F1A_FOUNDATION_ACCEPTANCE_REPORT.md` 暴露的 blocker
> 结论：`FRONTEND_F1B_BLOCKER_RESOLVED = YES`

---

## 1. 问题

`frontend/src/types/api.ts` 已经生成了 `/exam/prep/*` 的三组 canonical 路径，
但它们的 **successful response schema = `unknown`**：

```ts
// 修复前（regenerate 之前）
responses: {
    200: { headers: {...}; content: { "application/json": unknown; }; };
};
```

根因：FastAPI handler 返回裸 `dict`，没有 `response_model`，OpenAPI 里就没有 schema。
前端政策**禁止手写 transport DTO**，所以必须由冻结的后端契约自己声明。

本轮**不是**新功能、**不是** STEP7H 重开、**不是** Exam 后端扩展 ——
只补 OpenAPI success typing。

---

## 2. Git / DB Safety

```text
HEAD = ebad5282（未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

所有 `import main` / `TestClient` / OpenAPI 生成动作均在显式
`DATABASE_URL=sqlite:///<temp>` 下执行；真实 `backend/app.db` 只读访问。

```text
REAL backend/app.db
  mtime           = 2026-09-16 21:24（本轮为 09-17，未变）
  integrity_check = ok
  表总数           = 72（未变）
  exam_question_bank = 9333 · programming_exercises = 1923 · knowledge_points = 32
  BANKSHA256      = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee
                    （与 STEP7H5 记录逐字节相同）
  alembic_version = 不存在（真实库从未被迁移）

REAL_APP_DB_MUTATED = NO
DB_SCHEMA_CHANGED   = NO
MIGRATION_ADDED     = NO
```

---

## 3. CURRENT_RUNTIME_RESPONSE_MATRIX

先读 `backend/routers/exam_prep.py` 与 `learning/spaces/exam_prep/catalog.py`，
并用 temp DB 抓取**真实响应**，不从 F0 文档反向猜。

**canonical endpoint 集（从当前真实 router 得出，6 条）**

| method | path | auth | 200 | 错误 |
| --- | --- | --- | --- | --- |
| GET | `/exam/prep/profile` | 需要 | profile payload | 401 |
| PUT | `/exam/prep/profile` | 需要 | profile payload | 400 / 401 / 422 |
| GET | `/exam/prep/catalog` | 公开 | catalog payload | — |
| GET | `/exam/prep/catalog/tracks` | 公开 | tracks payload | — |
| GET | `/exam/prep/catalog/subjects` | 公开 | subjects payload | — |
| GET | `/exam/prep/subjects/{subject_id}/content-status` | 公开 | content-status payload | 404 / 409 |

（§1 点名的 4 条之外，`/catalog/tracks` 与 `/catalog/subjects` 属同一 canonical 面且同样
是 `unknown`，一并闭合 —— 未新增 endpoint，仅声明既有者。）

### 3.1 profile payload（GET/PUT 同形，字段顺序即运行时插入顺序）

| field | type | nullable | required | 说明 |
| --- | --- | --- | --- | --- |
| `configured` | bool | 否 | 是 | 未配置 = `false`，不是错误 |
| `exam_type` | str | 否 | 是 | 恒 `"postgraduate"` |
| `selected_track` | str | **是** | 是（键恒在） | catalog track id |
| `selected_subjects` | list[str] | 否 | 是 | 去重后的 subject id |
| `target_exam_year` | int | **是** | 是（键恒在） | 目标年份，与真题年份无关 |
| `subjects` | list[Subject \| UnknownSubject] | 否 | 是 | **见 3.2** |

### 3.2 `subjects[]` 元素是两个真实分支

| 分支 | 触发 | 形状 |
| --- | --- | --- |
| `ExamSubjectSummary` | subject id 仍在 catalog | **10 键**：`id / display_name / category / availability / has_questions / has_past_papers / has_knowledge_tree / description / suggested_tracks / modules` |
| `UnknownExamSubject` | 存储的 subject id 已不在 catalog | **2 键**：`id / availability`（值 `"unknown"`） |

**实测确认两个分支都真实存在**（直接写库构造一个已下线的 subject id → 返回 2 键）。
所以 `subjects` 必须按 union 声明，而不能只声明宽模型 —— 见 §4。

### 3.3 catalog payload

| field | type | required |
| --- | --- | --- |
| `catalog_version` | str（当前 `"v2"`） | 是 |
| `exam_type` | str | 是 |
| `tracks` | list[Track]（8 键：`id/display_name/exam_type/availability/has_content/description/subject_options/suggested_subjects`） | 是 |
| `subjects` | list[Subject]（10 键，同上） | 是 |
| `active_subject_ids` | list[str]（`["cs_408"]`） | 是 |
| `framework_only_subject_ids` | list[str]（13 个） | 是 |

`modules[]` 元素 = `{id, display_name}`（2 键）。

### 3.4 content-status payload（200 分支）

| field | type | nullable | required |
| --- | --- | --- | --- |
| `subject_id` | str | 否 | 是 |
| `availability` | `"active"`（该分支下） | 否 | 是 |
| `has_questions` | bool | 否 | 是 |
| `has_past_papers` | bool | 否 | 是 |
| `has_knowledge_tree` | bool | 否 | 是 |
| `modules` | list[{id, display_name}] | 否 | 是 |

**刻意不存在 `display_name`** —— handler 不返回它。§7 提到「display name」，
但按 §5「只声明真正已经返回的字段」与 §1「增加新字段 = 禁止」，**未添加**。

framework_only 科目**不进入**这个模型：它走 **409 + `EXAM_CONTENT_NOT_AVAILABLE`**。

---

## 4. Response Models

全部声明在 `backend/routers/exam_prep.py`（router 自己拥有它的契约）。
**字段声明顺序刻意与运行时 dict 插入顺序一致**，以保证序列化后字节不变。

| # | model | 用途 |
| --- | --- | --- |
| 1 | `ExamModuleSummary` | `{id, display_name}` |
| 2 | `ExamSubjectSummary` | `catalog.ExamSubjectDefinition.to_dict()`（10 键） |
| 3 | `ExamTrackSummary` | `catalog.ExamTrackDefinition.to_dict()`（8 键） |
| 4 | `UnknownExamSubject` | 已下线 subject id 的退化分支（2 键），`extra="forbid"` |
| 5 | `ExamPrepProfileResponse` | profile GET/PUT 200 |
| 6 | `ExamPrepCatalogResponse` | `/catalog` 200 |
| 7 | `ExamCatalogTracksResponse` | `/catalog/tracks` 200 |
| 8 | `ExamCatalogSubjectsResponse` | `/catalog/subjects` 200 |
| 9 | `ExamContentStatusResponse` | content-status 200 |

另有一个类型别名（不产生 component schema）：

```python
Availability = Literal["active", "framework_only"]
```

—— 来自 CONFIG（`catalog.ACTIVE` / `catalog.FRAMEWORK_ONLY`），不是数表行数。

### 4.1 为什么 `UnknownExamSubject` 需要 `extra="forbid"`

`subjects: list[ExamSubjectSummary | UnknownExamSubject]` 是 pydantic v2 smart union。
两个模型都接受 10 键 dict 会让 union 有歧义 —— 若选中窄模型，完整 subject 会被
**序列化回 2 键**，等于悄悄改契约。`extra="forbid"` 让完整 payload **无法**被判为窄模型。

**已用测试证明**：10 键 subject 回吐 10 键，2 键 ghost 回吐 2 键。

### 4.2 拒绝的做法

未使用 `response_model=dict` / `Any` / `Dict[str, Any]` / `RootModel[Any]` ——
它们会让前端生成类型再次退化为 `unknown`。

---

## 5. RUNTIME EQUIVALENCE

```text
RUNTIME_RESPONSE_CHANGED = NO
OPENAPI_RUNTIME_RESPONSE_EQUIVALENCE = PASS
```

方法：改动**前**在 temp DB 上抓 7 条真实响应（GET profile 未配置 / PUT profile /
GET profile 已配置 / catalog / catalog-tracks / catalog-subjects /
content-status active）存为 baseline；改动**后**用同一脚本、同一用户名重跑，
**逐字节比较**：

```text
get_profile_unconfigured   SAME
put_profile                SAME
get_profile_configured     SAME
catalog                    SAME   (5556 bytes)
catalog_tracks             SAME   (1835 bytes)
catalog_subjects           SAME   (3450 bytes)
content_status_active      SAME   ( 328 bytes)

RUNTIME_RESPONSE_BYTE_IDENTICAL = True
```

错误码同样未变：

```text
framework_only content-status → 409
unknown subject content-status → 404
未认证 profile                → 401
非法 track / subject / year   → 400
```

**未声明任何 error model**（§8：本轮只闭合 success typing）。
对 6 个 endpoint 断言 `responses ⊆ {200, 422}`，确保没人顺手加了错误 schema。

---

## 6. OpenAPI Schema

```text
OPENAPI_SUCCESS_RESPONSE_UNKNOWN = 0
```

改动后 6 条 endpoint 的 200 response 一律是具体 `$ref`：

| method | path | 200 schema |
| --- | --- | --- |
| GET | `/exam/prep/profile` | `$ref → ExamPrepProfileResponse` |
| PUT | `/exam/prep/profile` | `$ref → ExamPrepProfileResponse` |
| GET | `/exam/prep/catalog` | `$ref → ExamPrepCatalogResponse` |
| GET | `/exam/prep/catalog/tracks` | `$ref → ExamCatalogTracksResponse` |
| GET | `/exam/prep/catalog/subjects` | `$ref → ExamCatalogSubjectsResponse` |
| GET | `/exam/prep/subjects/{subject_id}/content-status` | `$ref → ExamContentStatusResponse` |

schema 细节（已断言）：

- `ExamPrepProfileResponse.required` = 6 个字段**全部**（键恒在，值可为 null）；
  `selected_track` / `target_exam_year` 为 `anyOf [string|integer, null]`；
  `selected_subjects` = `array[string]`；
  `subjects` = `array[anyOf $ref ExamSubjectSummary | $ref UnknownExamSubject]`。
- `availability` 在 `ExamSubjectSummary` / `ExamTrackSummary` / `ExamContentStatusResponse`
  中均为 **closed enum `["active", "framework_only"]`**。
- `has_questions` / `has_past_papers` / `has_knowledge_tree` = `boolean`。
- `modules` = `array[$ref ExamModuleSummary]`。
- `ExamContentStatusResponse` **不含** `display_name`。

---

## 7. TypeScript Generation

```text
GENERATED_TS_EXAM_RESPONSE_UNKNOWN = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO = 0
```

用**仓库既有生成器**（`openapi-typescript@7.13.0`，即 `npm run api:generate` 的同一工具与版本）
从当前代码的 OpenAPI 重新生成 `frontend/src/types/api.ts`。
**未手改**该文件（它是 auto-generated，顶部有 `Do not make direct changes` 头）。

```text
get_exam_prep_profile_...            → components["schemas"]["ExamPrepProfileResponse"]
put_exam_prep_profile_...            → request: ExamPrepProfileUpsert
                                       200:     components["schemas"]["ExamPrepProfileResponse"]
get_exam_prep_catalog_...            → components["schemas"]["ExamPrepCatalogResponse"]
get_exam_prep_tracks_...             → components["schemas"]["ExamCatalogTracksResponse"]
get_exam_prep_subjects_...           → components["schemas"]["ExamCatalogSubjectsResponse"]
get_subject_content_status_...       → components["schemas"]["ExamContentStatusResponse"]
```

### 7.1 生成方式说明（如实记录）

`package.json` 的 `api:generate` 硬编码 `http://localhost:8000/openapi.json`，
但**本机 8000 端口已被一个早先遗留的后端进程占用，且该进程服务的是改动前的旧代码**
（实测其 `/openapi.json` 中 `ExamPrepProfileResponse` 出现 0 次）。
为避免动到不属于本轮的进程，改为：把**当前代码**的 OpenAPI 导出到临时 JSON，
再用同一 `openapi-typescript` 二进制对该文件生成到同一输出路径。

```text
npx openapi-typescript <temp>/bc1_openapi.json -o src/types/api.ts
✨ openapi-typescript 7.13.0 · 250.3ms · exit 0
```

产物与跑 `api:generate` 等价（同工具、同版本、同 spec、同输出），
且**未修改 `package.json`**。

### 7.2 前端回归（因为改动了一个前端消费的文件）

```text
npm run typecheck → PASS（0 error）
npm run lint      → PASS（0 error）
npm run test:run  → 5 files / 14 tests PASS
```

**本轮未做任何前端 UI 修改**（无视觉、无路由、无 React 组件、无 F1B 实现）。

---

## 8. Tests

新增 `backend/tests/test_exam_openapi_contract.py` —— **32 passed / 0 failed / 0 skipped**。

覆盖 §13 的 A–I：

| 要求 | 测试 |
| --- | --- |
| A. GET profile runtime shape 不变 | `test_a_get_profile_runtime_shape_is_unchanged` |
| B. PUT profile runtime shape 不变 | `test_b_put_profile_runtime_shape_is_unchanged` |
| C. GET catalog runtime shape 不变 | `test_c_catalog_runtime_shape_is_unchanged`（含 tracks/subjects 子路径） |
| D. content-status runtime shape 不变 | `test_d_content_status_runtime_shape_is_unchanged` |
| E. OpenAPI success schema 具体 | `test_e_openapi_success_schema_is_concrete`（6 参数化）+ `test_e_declared_model_exists_and_is_structured`（6 参数化）+ 3 条字段细节断言 |
| F. 生成 TS 不是 unknown | `test_f_generated_typescript_response_is_not_unknown`（6 参数化） |
| G. framework-only 响应仍被类型化（且仍 409） | `test_g_framework_only_subject_keeps_its_409_and_is_not_typed_as_success` |
| H. CS408 active 响应被类型化 | `test_h_cs408_active_content_status_is_typed_and_matches_runtime` |
| I. 非法 subject 错误不变 | `test_i_error_status_codes_are_unchanged` / `test_i_unauthenticated_profile_is_still_401` |

额外两条防回归断言：

- `test_profile_subject_object_is_never_narrowed` —— union 不得把完整 subject 压成 2 键；
- `test_no_error_models_were_added_to_these_endpoints` —— 本轮只闭 success typing。

### 8.1 FULL_BACKEND_TESTS

```text
本轮 baseline（STEP7H5）= 878 passed / 0 failed
本轮新增               = 32
本轮结果               = 910 passed / 0 failed（1583.86s）
```

---

## 9. Changed Files

| file | 变更 | 理由 |
| --- | --- | --- |
| `backend/routers/exam_prep.py` | 新增 9 个 response model + `Availability` 字面量；6 条路由挂 `response_model` | 契约唯一来源；handler 未改一行 |
| `backend/tests/test_exam_openapi_contract.py` | **新建** | 等价性 + OpenAPI + 生成产物断言 |
| `frontend/src/types/api.ts` | **重新生成**（自动产物） | 本 blocker 的直接产物；未手改 |
| `FRONTEND_BC1_EXAM_OPENAPI_CONTRACT_ACCEPTANCE_REPORT.md` | **新建** | 本报告 |

**未改**：`main.py`、`models.py`、任何 handler 逻辑、任何路由 URL / method / 状态码 /
auth、catalog、migration、`backend/app.db`、任何前端 UI。

---

## 10. Final Gates

```text
EXAM_PREP_PROFILE_RESPONSE_MODEL        = PASS
EXAM_PREP_CATALOG_RESPONSE_MODEL        = PASS
EXAM_PREP_CONTENT_STATUS_RESPONSE_MODEL = PASS

RUNTIME_RESPONSE_CHANGED                = NO

OPENAPI_SUCCESS_RESPONSE_UNKNOWN        = 0
GENERATED_TS_EXAM_RESPONSE_UNKNOWN      = 0
HAND_WRITTEN_FRONTEND_TRANSPORT_DTO     = 0

BACKEND_PRODUCT_SEMANTICS_CHANGED       = NO
DB_SCHEMA_CHANGED                       = NO
MIGRATION_ADDED                         = NO

REAL_APP_DB_MUTATED                     = NO

FULL_BACKEND_TESTS                      = PASS（910 passed / 0 failed）

FRONTEND_F1B_BLOCKER_RESOLVED           = YES
```

---

## 11. 观察（不属本轮，未处理）

① `backend/file` 是一个 **0 字节游离文件**（untracked，mtime 2026-09-17 11:06），
   属上一轮 H5 期间我自己的一个 shell 误产物，非项目内容。本轮**未触碰**，交由用户决定删除。

② 本机 **8000 端口存在一个早先遗留的后端进程**，服务的是改动前的代码。
   本轮未终止它（它可能是有意留下的 dev server）。若之后要跑标准
   `npm run api:generate`，需要先让该进程重启以加载新代码。

③ `package.json` 的 `api:generate` 依赖一个手工启动的 8000 端口后端，
   在 CI / 无守护进程环境下不可直接复现。属既有工程债，未在本轮变更。
