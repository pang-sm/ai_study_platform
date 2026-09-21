# THREE_DOMAIN_PRODUCTIZATION_P1_1 — COURSE BACKEND CLOSURE REPORT

范围：**只做 backend**，只关闭 Course Learning 前端报告里剩余的真实后端阻塞项
（资料上传 / 练习闭环 / 今日计划）。不做 Programming 新架构，不重写 P1 已完成的能力，
不修改任何 frontend 文件。

---

## GIT_PRECHECK

```text
branch                       main   (tracking origin/main)
HEAD                         b3543a34  ACCEL_PRODUCT_S10：统一会员迁移 + 竞赛演示环境 + 数据飞轮加固
git rev-list --left-right --count origin/main...HEAD   →  0   0   （无分叉）
```

工作树在本轮开始时已包含 **P1 的后端 + 前端未提交改动**，本轮**全部保留、未回退**：

- P1 后端：`routers/course_learning.py`、`routers/programming.py`、
  `learning/spaces/programming/`、`learning/spaces/course_learning/wrong_answers.py`、
  `tests/test_three_domain_p1_contracts.py`、`membership.py`、
  `tests/test_bc8r1_entitlement_contract.py`、`tests/test_feature_entitlements.py`
  以及 `data_plane/` `learning/records/` `learning/practice/` `learning/wrong_answers/` 的 P1 改动。
- P1 前端（**本轮完全未触碰**）：`frontend/src/features/course/`、`frontend/src/routes/course*`、
  `frontend/src/components/layout/app-shell.tsx`、`frontend/src/routeTree.gen.ts`、
  `frontend/tests/e2e/course-workspace.spec.ts`。

本轮未执行：`reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` / `push`。
未创建 commit。未删除任何未跟踪文件或 scratch 目录。

---

## FILES_CHANGED

| 文件 | 改动 | 理由 |
|---|---|---|
| `backend/routers/course_learning.py` | +8 路由（materials 2 / practice 5 / today-plan 1）、+12 响应与请求模型、+2 归属守卫 | 课程作用域下补齐上传、练习闭环、今日计划；全部**委托**既有实现 |
| `backend/learning/spaces/course_learning/context.py` | +`course_identity_forms()` | 课程身份的**唯一**精确拼写集合（只经 `subjects.py` 查表，无模糊匹配） |
| `backend/learning/spaces/course_learning/service.py` | +`course_materials()`、+`course_today_plan()` | 课程作用域的资料读取与今日任务，SQL 层先过滤再分页，只读 |
| `backend/main.py` | `resolve_material_scope` 增 canonical 身份分支；`_material_domain` 认 canonical 身份 | 让"课程身份"成为资料的合法作用域；同门课两种拼写在配额/去重/标签上判为同一门课 |
| `backend/data_plane/emitter.py` | +`course_identity()`；live 事件 `course_id` 由 `None` → 课程身份 | 真实提交此前在课程自己的时间线里不可见（`course_id` 为 NULL） |
| `backend/data_plane/backfill.py` | 同一推导 | live 与 replay 对同一事实的归档必须一致 |
| `backend/learning/practice/adapters/course.py` | 镜像的 `LearningContext` 补 `course_id` | 课程会话此前无法按课程检索（attempt 走 question ref 有课，session 没有） |
| `backend/tests/test_course_p1_1_contracts.py` | **新增** 19 个测试 | 见 TESTS |
| `backend/tests/test_feature_entitlements.py` | 仅 docstring：写明 A 项 contract evolution | 消除"`programming` 无 feature"的过期表述 |
| `backend/tests/test_bc8r1_entitlement_contract.py` | 仅 docstring：同上 | 同上 |
| `docs/FRONTEND_API_CONTRACT.md` | +P1.1 章节 | API 契约变更后同步（`zhixue-api-contract` 规则） |

**未新增任何数据库结构**（无新表 / 新列 / 新索引）→ **不需要 Alembic 迁移**。
`migrations/versions/` 未改动。

---

## A. 正式接受 P1 contract change（已完成，未回退）

- 保留 `backend/membership.py` 的 `SERVICE_FEATURES["programming"] = ("learning_plan",)`。
- 保留 `test_bc8r1_entitlement_contract.py` / `test_feature_entitlements.py` 的新断言。
- 本轮补强"**显式 contract evolution，非 accidental regression**"的表述：两个测试文件的
  docstring 顶部新增 `CONTRACT EVOLUTION (accepted, not a regression)` 段落，写明
  ①是三方向产品化授予某方向一个**它有路由**的功能，②不是第二套会员（档位仍唯一决定），
  ③`programming` 仍**没有** `learning_report`，因为产品没有对应报告面。
- 旧行为（`programming` 无 feature）**未恢复**；旧的"空 mapping 合法"仍以**形状**形式被测试覆盖。

---

## MATERIAL_UPLOAD_CONTRACT

**新增**（需登录，路径即身份）：

| Method | Path | 说明 |
|---|---|---|
| GET | `/course-learning/courses/{course_id}/materials` | 课程资料库（只读） |
| POST | `/course-learning/courses/{course_id}/materials` | 上传一个文件（multipart，**仅 `file`**） |

- **身份来源**：用户 = 会话 cookie（`get_current_user`）；课程 = 路径 + `assert_owned_course`。
  请求体没有 `username`、没有 `subject_key`、没有 `course_id`；上传管线里的
  `username/course_id/subject_key/subject/track` 全部由服务端注入。
- **落库身份**：`course_id = subject_key = subject =` 课程 canonical key
  （`course_learning_preferences.course_id`）。**不为课程伪造 subject_key**。
- **复用而非复制**：直接调用既有 `POST /materials/upload` 的实现（配额 → 重复检测 →
  存盘 → 解析 → 后台任务 → 响应形状全部相同）。**没有第二套材料系统**。
  注：因为直接调用，所有 `Form(...)` 字段必须显式传值（`Form` 默认值是注入标记对象，不是值）。
- **两道门都保留**：①课程必须属于调用者（本路由，404）；②课程必须仍在选课里（管线，403）。
- **平台级收敛**：`resolve_material_scope` 新增 canonical 身份分支（此前该拼写返回 400），
  `_material_domain` 认 canonical 身份 → 同门课两种拼写进入**同一个**域，因此
  重复检测与存储配额对两种拼写一致（此前 canonical 拼写会被判成 `legacy`，
  既逃过本域配额又逃过重复检测）。
- **列表读取**：按课程身份的**全部精确拼写**取 `course_id` 与 `subject_key` **同时**命中者，
  因此 exam scope（`*_11408`）与同拼写的 programming 课都不会混入。
  旧的 `GET /materials?course_id=...` 仍**只匹配请求里写的那个拼写**（契约文档已注明）。

---

## PRACTICE_SUBMIT_CONTRACT

**新增**：

| Method | Path | 说明 |
|---|---|---|
| GET | `/course-learning/courses/{course_id}/practice/workbook` | 课程 AI 题册（+ 每题作答历史与 `workbook_status`） |
| GET | `/course-learning/courses/{course_id}/practice/history` | 课程练习历史 |
| POST | `/course-learning/courses/{course_id}/practice/questions/{question_id}/attempts` | 对**本课程**某题开启新作答（"下一题"/重做） |
| POST | `/course-learning/courses/{course_id}/practice/generate` | 为本课程生成一道题并开启作答 |
| POST | `/course-learning/courses/{course_id}/practice/{attempt_id}/submit` | 提交判分 |

- **提交体只有 `answer`**（`extra="forbid"`）：多传 `course_id` / `username` 直接 **422**，
  且被拒请求**不进判分**（测试断言 attempt 仍是 `in_progress`）。
- **跨课程被拒且在判分之前**：`_owned_course_attempt` 先查 attempt（本人 + `mode=course_learning`），
  再要求其存储的课程身份 ∈ 本课程精确身份集合，否则 **404**。course A 的 attempt 无法经
  course B 的路径提交，不会改动任何数据。
- **开始作答同样跨课程被拒**：题号先从课程作用域题册里解析（delegate 本身只按 id 查，因此该检查必须在本路由做）。
- **零复制**：判分、知识状态转移、canonical `LearningRecord`、数据面事件、practice 镜像全部
  是既有实现（`generate_course_learning_practice` / `submit_course_learning_practice` /
  `restart_course_learning_workbook_question` / workbook / history）被**直接调用**。
- **答题前不下发答案**：题册 / 历史 / 开始作答三处均无 `standard_answer` / `analysis`；
  参考答案只在 submit 的 `result` 里出现。
- **生成受统一会员门控**：Free → 标准 `FEATURE_REQUIRES_UPGRADE` 403，不降级成本地伪造题；
  Standard / Advanced → 200，`generation_mode` 如实标注 `ai` / `fallback`。
- **事件侧修复**：`data_plane.emitter` / `backfill` 的 `course_id` 由 `None` 改为课程的
  真实身份（由 attempt 自身推导）。此前真实提交产生的 `course_practice` 事件
  `course_id` 为 NULL，而课程作用域 records / state 正是按该列过滤 →
  **学习者练了题，课程自己的时间线却是空的**。`backfill` 同步修改，保证 live 与 replay 一致；
  事件 id / 事件类型 / 冻结语义均未变。

---

## TODAY_PLAN_CONTRACT

**新增**：`GET /course-learning/courses/{course_id}/today-plan`（只读，需登录）

- **可归属**：计划任务走共享 `course_learning:<course>` key（与 `/courses/{id}/state` 的
  `plan` 块是**同一个**推导，两者不可能不一致）；通用 `learning_tasks` 仅当其
  `course_id` **正好是**本课程身份拼写之一时才返回。
- **不猜**：空 `course_id`、无法识别的课程名、exam scope 一律**不返回**；不做标题匹配、
  不回退到"当前课程"、不做客户端字符串过滤。
- **每项都带 `course_id`**，且等于路径课程；item id 与全局 today-plan **完全相同**
  （`exam_task:{id}` / `task:{id}`），因此两处的 `user_order` 含义一致。
- **只读**：不创建偏好行、不写排序（全局那条 GET 会写偏好 + commit，本路由不写）。
- **不设会员门控**：与既有全局 today-plan 及课程 state 的 plan 块保持一致（今日行动面 Free 可用）。
- 排序规则与全局一致（urgency → user_order → due_date → id，无日期排最后）。

---

## TESTS

**新增** `backend/tests/test_course_p1_1_contracts.py` — 19 个测试，逐条对应要求的 7 项证明：

| 要求 | 测试 |
|---|---|
| 1. 上传身份来自服务端 | `test_material_upload_derives_identity_from_the_session_and_the_path` |
| 2. 不能上传进别人的课程 | `test_a_learner_cannot_upload_into_another_learners_course` |
| 3. 资料保持正确 course_id | `test_course_materials_list_is_scoped_to_the_course`（含 exam scope / programming 同拼写不混入） |
| 4. course A attempt 不能在 course B 提交 | `test_a_course_attempt_cannot_be_submitted_through_another_course`、`test_a_question_from_another_course_cannot_open_an_attempt`、`test_a_submit_body_cannot_name_its_own_course` |
| 5. 提交写入正确 canonical 事件上下文 | `test_submit_writes_the_course_into_the_canonical_facts`（practice attempt 的 question ref + learning event + records + summary + state + 另一课程看不到） |
| 6. today-plan 排除其它课程 | `test_today_plan_lists_only_this_courses_tasks`、`test_today_plan_never_reports_another_learners_tasks` |
| 7. 无法归属的历史任务不被猜进课程 | `test_an_unattributable_task_is_never_guessed_into_a_course` |

另含：完整练习闭环（题 → 答 → 判分 → 反馈 → 下一题）、身份拼写集合、答题前不下发答案、
生成门控 + 真实模型边界（FakeProvider 只替换出网调用）、统一 `learning_plan` 门控未变、
P1 面回归、旧上传契约未破（含同文件重复上传 409）、live 与 backfill 事件身份一致。

**实测（最终树，TEMP DATABASE_URL，全套）**：

```text
1610 passed, 2 skipped, 0 failed  in 1052.47s (17:32)   exit code 0
```

> 过程中发现并修掉一个**测试自身**的顺序依赖：`PracticeAttempt.source_attempt_id` 只在**各自
> 来源表内**唯一，另一来源类型（`question_attempt`）的镜像可能同号，导致全套运行时我的两个测试
> 计数偏大（单独运行通过）。已改为按 canonical 三元组
> `(source_type, source_attempt_id, item_key)` 断言——这本身就是 `data_plane.identity` 的定义。

---

## OPENAPI

- `main.app.openapi()` 生成成功；`/course-learning/courses/{course_id}/...` 下 **8 条新路由全部带
  具名响应模型**（`CourseMaterialListResponse` / `CourseMaterialUploadResponse` /
  `CourseWorkbookResponse` / `CoursePracticeHistoryResponse` / `CourseAttemptStartedResponse` /
  `CourseQuestionGeneratedResponse` / `CoursePracticeSubmitResponse` / `CourseTodayPlanResponse`），
  无 `unknown`、无悬空 `$ref`。
- 请求体模型 `CourseAnswerSubmitRequest` / `CourseQuestionGenerateRequest` 为
  `additionalProperties: false`（多传字段 422）。
- **未修改** `frontend/src/types/api.ts`（生成文件，由 Codex 后续 `npm run api:generate`）。
- 快照仅落在 scratch：`.p11tmp/openapi.json`。

---

## MAIN_DB_SHA_BEFORE

```text
1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522  backend/app.db
mtime 2026-09-20 12:03:42.878312700 +0800   size 64917504
```

## MAIN_DB_SHA_AFTER

```text
1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522  backend/app.db
mtime 2026-09-20 12:03:42.878312700 +0800   size 64917504
```

## MAIN_DB_TOUCHED = NO

SHA256 与 mtime 逐字节未变。所有 import `main` / TestClient / pytest / OpenAPI 的进程一律使用
临时 `DATABASE_URL`（`tests/conftest.py` 的 mkdtemp；本轮手工 smoke 用 `.p11tmp/smoke.db`），
未对 `backend/app.db` 执行任何读写。

---

## READINESS

| 标记 | 值 | 依据 |
|---|---|---|
| COURSE_MATERIALS_FRONTEND_READY | **YES** | 列表 + 上传（仅 file）可用；身份服务端派生；跨用户/跨课程 404；OpenAPI 已类型化 |
| COURSE_PRACTICE_FRONTEND_READY | **YES** | 题册 → 开新作答 → 提交判分 → 反馈 → 下一题全程可用；答题前无答案泄漏；跨课程 404 |
| COURSE_TODAY_PLAN_FRONTEND_READY | **YES** | 每项带 `course_id`；不可归属任务不返回；item id 与全局一致 |
| COURSE_FULL_BACKEND_LOOP_READY | **YES** | 上述三者 + P1 的 records/wrong-answers/state 共用**同一个**课程身份；闭环有 19 个测试与全套回归背书。**唯一保留项见 BLOCKERS #1**（错题本的题干/参考答案内容解析），不影响闭环本身可用性 |

---

## BLOCKERS

### #1（未修，按协议上报）错题内容按裸 id 跨表解析 → 题干/参考答案为空，且有串号风险

**现象**（已由测试固定）：真实提交经 practice 镜像后，课程错题记录的 `stem` 与
`reference_answer` 为**空**。我的测试里以**特征化断言**记录（`== ""`）并在测试内注明"修好该映射后
应改为 `== question.stem` / `== "A"`"。

**根因**（两条并存）：

1. `backend/learning/practice/adapters/course.py:35-36` 把 course 模式映射为
   `("questions", QuestionSourceType.MATERIAL_GENERATED)`，而课程 AI 题册实际写在
   `ai_generated_questions`（`AIGeneratedQuestion`）。
2. `backend/learning/spaces/course_learning/wrong_answers.py:167-173` 的 `_load_material`
   按 **id** 查 `models.Question`（另一张表），且**不带 username / course 过滤**。

**后果**：①题干与参考答案解析不到 → 错题本内容为空；②`questions.id` 与
`ai_generated_questions.id` 各自自增、大量重叠，一旦命中即显示**别人的**题目正文
（`questions` 有 `username` 列而查询未过滤）——即课堂错题页可能展示他人的题面。

**为什么停在这里**：改它要动**冻结的 canonical 来源类型语义**（`practice_attempts.question_source_type`
对新写入行改变），且 `tests/test_practice_adapters.py:69` 正固定着 `material_generated`。
按本任务协议，contract / security / semantic 级问题**报告而不擅自改**。

**建议修法**（最小）：把 `_MODE_MAP["course_learning"]` 改成
`("ai_generated_questions", QuestionSourceType.AI_GENERATED)` —— 该映射**已存在于**冻结表
`learning/practice/refs.py: LEGACY_SOURCE_MAP`，于是 `_load_ai` 按 PK 取到**本人**题面；
同时相应更新 `tests/test_practice_adapters.py:69`（属显式契约订正，与 A 项同类）。
替代方案：给 `_load_ai` / `_load_material` 加 owner 过滤（消除串号但题干仍为空）。

**当前可用降级**：错题记录带 `question_id` / `question_source_id`，课程题册接口带
`stem` / `options`，前端可据此水合题面（`COURSE_PRACTICE_FRONTEND_READY` 因此仍为 YES）。

### #2（提示，非阻塞）前端需把资料读取切到课程作用域路由

`GET /materials?course_id=<canonical>` 现在不再 400，但它**只匹配请求里写的那一个拼写**，
看不到该课程另一种拼写下的历史资料；`/courses/{id}/materials` 会一并列出。
建议 Codex 后续统一改用课程作用域路由（契约文档已注明差异）。

### #3（观察，非本轮范围）CLAUDE.md 的 `MIGRATION_HEAD` 已过期

CLAUDE.md 写 `MIGRATION_HEAD = 20260919_0010`，实际 `migrations/versions/` 最新为
`20260919_0012_data_origin_provenance.py`。本轮无迁移，未改动该文件；仅按"不得把 TARGET 写成
CURRENT"的原则报告，等待用户决定是否回写。
