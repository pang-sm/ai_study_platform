# 统一复习推荐中心实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不复制学习事实或复习状态的前提下，为三大学习方向提供可解释、可执行、随真实事实更新的统一复习建议。

**Architecture:** 扩展现有 review projection，新增纯读的确定性推荐计算和用户级暂缓 overlay；领域事实和真实完成结果仍由现有业务服务写入。前端读取推荐 API 并连接既有学习入口。暂缓因现有 review event taxonomy 冻结而使用最小 additive-only 状态表，不复用 `review_scheduled` / `review_completed`。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、LearningEvent/PracticeAttempt/WrongAnswerState、React 19、TanStack Query/Router、OpenAPI TypeScript。

**Spec:** [2026-10-09 统一复习推荐中心规格](../specs/2026-10-09-unified-review-recommendation-center.md)

## Global Constraints

- 当前 SSOT 为 `STEP_7H5 / FRONTEND`；STEP 7H 已冻结，后端停止继续扩展。
- **PHASE GATE PASSED (2026-10-09):** 项目负责人明确批准有限后端扩展；SSOT §74 已记录 `ACCEL_SPRINT_S3 = IN_PROGRESS`。不得扩展 S3 边界或自行改动其冻结条件。
- 数据库只允许 Alembic additive-only；既有数据、review schedule、问题库与内容资产不得重写或删除。
- Product Backend 不直接 import `torch` / `transformers` / `faiss` / `zhixue_runtime`。
- `frontend/src/types/api.ts` 是生成文件；仅通过 `npm run api:generate` 更新。
- 推荐生成不得写事实；浏览/点击开始不得标记完成；完成/掌握遵循来源域真实规则。
- 保留所有未跟踪文件；不得执行 reset、clean、overwrite、rebase、merge、force push 或 stash。
- 禁止读取生产数据库或任何 secret 文件。

## Review Focus

- **编程历史稀疏：** `ProgrammingExerciseSubmission` 当前唯一键是用户×练习，不是历史；只有可靠不同 attempt 才可升级为“持续薄弱”。测试覆盖只有一条真实失败时为单次建议。
- **知识点间隔来源：** 默认 `review_interval_days` 不一定是用户确认周期；无可靠设置时不得生成遗忘预防候选。测试覆盖缺失/默认 interval。
- **scope alias：** 11408 旧 scope 与 canonical exam namespace 不能重复出卡。测试覆盖 alias 合并和隔离。
- **状态过期：** 当前事实解决、计划更改或 snooze 过期后，每次读取都应重新评估。测试覆盖 source state 更新与 UTC 边界。
- **幂等/并发暂缓：** 同 user/key 重复或并发请求不得多建记录，其他用户不得读/覆盖。测试覆盖 unique key 与 owner scoping。

---

## 实施先决条件

- [x] 项目负责人于 2026-10-09 明确批准此功能最小后端范围，并授权按 SSOT §74 更新阶段记录；SSOT 已记录 `ACCEL_SPRINT_S3 = IN_PROGRESS`。此项不重开 STEP7H5 / STEP7H，也不放开其他后端范围。
- [x] 现场执行并记录 Git 状态：`main`，HEAD=`db7ea37e6d960fe5e6e6501057fbd2a2b7f95f39`，`origin/main...HEAD=0 0`；存在既有未跟踪成果，全部保留。
- [x] 只读执行 `backend/.venv/Scripts/python.exe -m alembic heads`，唯一 head=`20261001_0018`；迁移落点为 `migrations/versions/20261009_0019_review_recommendation_snoozes.py`，`down_revision="20261001_0018"`。
- [x] 只读代码审计确认 programming `PracticeAttempt` 每次真实 submit 有独立 source item key 和 sandbox verdict；`programming_exercise_submissions` 是同次 submit 镜像且不计数，`code_tested` 无 verdict。知识点只依赖已有 stored `review_due_at` / schedule，不用默认 interval 推导日期。

## Task 1: 确定性候选投影

**Files:**
- **Create:** `backend/learning/review_recommendations.py`
- **Modify:** `backend/learning/review.py`（仅为推荐提供复用的有界、已 user-scoped 源事实；保持现有 `/review` 响应语义）
- **Test:** `backend/tests/test_review_recommendations.py`
- **Test:** `backend/tests/test_p3a_unified_review.py`（仅必要兼容断言）

**Interfaces:**
- Produces `build_recommendations(db, user, *, service_namespace=None, as_of=None, limit=50) -> dict`。
- 响应字段：`policy_version`, `generated_at`, `items`, `total`, `semantics`；每 item 有 stable key、namespace/scope、object title、reason code/text、证据引用、排序 tuple、行动目标。
- 内部 reason enum 固定为 `scheduled_overdue`, `repeated_wrong`, `scheduled_due`, `knowledge_consolidation`, `single_wrong`, `programming_repeated_failure`, `programming_single_failure`；不向 UI 输出虚构的 mastered/forgotten。

- [ ] 写失败测试：相同 `as_of` 与相同事实产生完全相同身份、原因、数量、顺序。
- [ ] 写来源分类测试：显式 overdue、两条不同错误 attempt、单次错误、有效周期到期、单次编程失败；NULL/self-review/infra error 不计错。
- [ ] 写 scope/key 测试：canonical identity 用 scoped code/稳定 ID，不用 title；11408 alias 归一。
- [ ] 写去重测试：同一 question 或 knowledge point 跨 due/wrong/adaptive/program sources 只一条，合并 evidence 且保留最强可执行 target。
- [ ] 写纯度测试：调用候选投影不增加 LearningEvent、不改 progress、不触碰 due date。
- [ ] 按失败输出实现候选抽取、一次性 `as_of`、稳定排序 tuple 和 source-state revalidation；候选有界读取并限于 user id/username。
- [ ] 运行 `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_review_recommendations.py backend/tests/test_p3a_unified_review.py -q`，确保通过。

## Task 2: 暂缓 overlay 与 additive migration

**Files:**
- **Create:** `backend/learning/review_recommendations/models.py`
- **Create:** 当前 head 的 additive-only Alembic migration（优先 `migrations/versions/20261009_0019_review_recommendation_snoozes.py`，仅当先决检查确认 head 未改变）
- **Create:** `backend/learning/review_recommendations/snoozes.py`
- **Test:** `backend/tests/test_review_recommendation_snoozes.py`

**Interfaces:**
- Table `review_recommendation_snoozes`: `id`, `user_id`, `recommendation_key`, `snoozed_until`, `created_at`, `updated_at`; unique `(user_id, recommendation_key)`。
- `active_snoozes(db, user_id, keys, *, as_of) -> dict[str, datetime]`。
- `snooze_current_recommendation(db, user, key, *, as_of) -> datetime`：重新验证 recommendation 当前存在且归属该 user 后幂等 upsert，截止时间 `as_of + 24h`。

- [ ] 写 migration test：空库 upgrade 建表；已有 schema upgrade 只新增目标表/索引；没有 DROP/重建/既有数据更新。
- [ ] 写 store tests：同 user/key 重复 snooze 覆盖期限但只一行；期限严格 24h UTC；已过期不视作 active。
- [ ] 写隔离与 stale tests：其他用户的 key 返回 not found；candidate 已解决/失效返回 not found，不落 orphan row。
- [ ] 写唯一约束并发/重复请求测试；upsert 使用 SQLite/Postgres 支持的安全事务模式，IntegrityError 后重新读取唯一记录。
- [ ] 实现模型、migration 和 store；该表只保存 suppression overlay，不写 review events 或改原复习计划。
- [ ] 使用临时测试数据库升级并执行 `PRAGMA integrity_check`，预期 `ok`；检查 Alembic downgrade 不用于正式回滚方案，线上恢复依赖兼容回滚代码且保留新增数据。

## Task 3: API、过滤、隔离与数量

**Files:**
- **Modify:** `backend/routers/review.py`
- **Modify:** 如需响应 model，仍放在 `backend/routers/review.py`，避免另建无必要 router。
- **Test:** `backend/tests/test_review_recommendations_api.py`
- **Generated:** `frontend/src/types/api.ts`（只用 OpenAPI generator）

**Interfaces:**
- `GET /review/recommendations`: query `service_namespace`, `limit`, `offset`；仅调用 Task 1 read projection + Task 2 snooze overlay；`total` 是过滤/分页前的有效候选总数。
- `POST /review/recommendations/{recommendation_key}/snooze`: 认证用户，无请求 body，返回稳定 key 与 UTC `snoozed_until`。
- GET 不写库；POST 不写学习事实/计划/事件。

- [ ] 写 API 测试：端点 feature gate 沿用 `intelligent_review`；全部/三方向筛选；count 与 items 匹配；无数据返回空数组和 total=0。
- [ ] 写 API 隔离测试：其他用户 key 不存在，namespace filter 不泄漏，跨用户 snooze 不共享。
- [ ] 写调用纯度测试：GET 前后行数与 `review_due_at`、事件数量一致。
- [ ] 写 stale recommendation 测试：先产生候选后将其来源标记 resolved/pass，再 snooze 被拒绝，GET 不返回旧项。
- [ ] 添加 Pydantic schemas/endpoints；`snooze` 路由注册不得被 `/{item_id}/complete` 路由遮挡。
- [ ] 在临时 backend 实例上生成 OpenAPI，再在 frontend 使用 `npm run api:generate` 更新生成类型；审阅 diff 确认仅本 API 变更。
- [ ] 运行上述 API tests 与现有 `test_p4_intelligent_review.py`、`test_p5_review_persistence.py`。

## Task 4: 页面/API 客户端

**Files:**
- **Modify:** `frontend/src/features/advanced/api/workflows.ts`
- **Modify:** `frontend/src/features/advanced/workflow-adapters.ts`
- **Modify:** `frontend/src/features/review/review-page.tsx`
- **Modify:** `frontend/src/test/review.test.tsx`

**Interfaces:**
- query key `['review','recommendations', namespace ?? 'all']`。
- mutation 将 snooze 成功后 invalidate recommendations query。
- adapter 将 API recommendation 转成只含卡片所需字段的 view；不将 server facts 展开到普通卡片。

- [ ] 写页面测试：标题、四筛选、顶部数量来自真实 response；卡片只呈现对象、方向、短事实理由、开始与暂缓。
- [ ] 写文案测试：两段指定原文不再出现在页面；极简空态没有段落，零建议数真实显示。
- [ ] 写交互测试：开始链接符合每空间合法路径且不调用 complete；暂缓调用 mutation 且不伪装完成；失败保留卡片并报告错误。
- [ ] 按现有设计 tokens/components 实现前端；移除手工“完成正确/错误”控件和“安排复习”控件，不删其他模块功能。
- [ ] 运行 `cd frontend && npm run check && npm run build`。

## Task 5: 业务闭环与稳定性回归

**Files:**
- **Modify/Test:** `backend/tests/test_review_recommendations.py`
- **Modify/Test:** `backend/tests/test_review_recommendation_snoozes.py`
- **Modify/Test:** `backend/tests/test_review_recommendations_api.py`
- **Modify/Test:** `frontend/src/test/review.test.tsx`
- **Potential integration test:** `frontend/e2e/review-recommendations.spec.ts`（若该目录/Playwright fixtures 已存在；先复用现有配置）

- [ ] 端到端验证一条真实错题：错误 attempt → recommendation；开始进入错题/练习原流程；真实更正后 active wrong state 按原业务更新，建议下一次读取消失或降级。
- [ ] 端到端验证到期知识点：现有 due 产生建议；打开详情不改状态；真实领域学习/复习结果按现有规则更新，下一次建议重算。
- [ ] 端到端验证编程失败：真实失败可建议对应 exercise；打开工作台不代表完成；真实通过后建议退出。
- [ ] 验证 snooze 在请求中保留原计划；24h 前隐藏、期限边界到时重新出现；来源解决后过期恢复也不产生候选。
- [ ] 全部后端运行项目 venv 的 pytest；确认跨用户、无数据、稳定排序、attempt 去重等覆盖。

## Task 6: UI 验收与发布（仅阶段授权且产品负责人要求部署后）

**Files:**
- **Potential:** `frontend` browser acceptance evidence only；不改部署 workflow 除非验收发现必需缺陷并另行说明。

- [ ] 执行 UI 视觉审核与真实浏览器验收，覆盖四筛选、刷新、空状态、启动路径、暂缓与恢复；确认无控制台错误和错误完成写回。
- [ ] 检查 `git diff --check`、`git status --short --branch`、显式文件清单；保留已有未跟踪文件，绝不 `git add .` / `git add -A`。
- [ ] 根据当前项目安全策略逐个显式 stage 本任务文件；只有在分支状态和操作边界确认无冲突后才提交/推送。若 `main` divergence 或需 rebase/merge/reset/force push，停下并报告，不执行。
- [ ] 部署前生产旧服务持续运行，执行候选构建/依赖/迁移预检；单点切换后必须通过 backend health gate，失败自动回滚；前端仅在健康门后发布。
- [ ] 查询 deploy workflow 结果和远端实际 SHA，要求与本次 release commit 一致；运行公网健康 smoke 和真实浏览器 review flows。
- [ ] 最终报告 CHANGE、TESTS、COMMIT、DEPLOYMENT、PRODUCTION_URL、PRODUCTION_SHA、PUBLIC_SMOKE_TEST、ONLINE_ACCEPTANCE_READY，并说明迁移与回滚结果。

## 执行顺序与当前状态

Task 1→2→3→4→5→6 有接口依赖，不拆分并行。当前按用户选择由本会话原生实施；仅在本计划列明的 S3 范围内推进。部署仍依项目现有提交/推送安全门推进。
