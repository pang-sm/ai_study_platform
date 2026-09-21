# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6.1 — FEEDBACK IDENTITY & E2E HARNESS

> 窄范围 closure。只解决两件事：**AI Feedback request identity 不完整**、
> **缺少隔离的 authenticated E2E backend harness**。未新增学习功能，未改 frontend 源码，
> 未 commit / push / deploy，未 reset / clean / restore / stash。

---

## CODE_ANALYZE_REQUEST_ID = **EXPOSED（真实、owner-scoped、可反馈）**

`POST /code/analyze` 有**两条真实分支**，本轮都收敛到同一身份契约：

| 分支 | 触发条件 | 本轮之前 | 现在 |
|---|---|---|---|
| course | `course_id` 非编程（含空串，即前端 `useCodeCoach('explain')` 的路径） | 已经过统一栈（`_course_ai_content` → `execute_course_ai` → orchestrator），但 **request_id 被丢弃** | 返回该 `ai_requests` 行的真实 `request_id` |
| programming | `course_id ∈ {programming, 编程, 编程学习}` | **绕过统一链路**：`check_programming_usage_limit` + `call_deepseek` + `record_ai_usage`（legacy），**没有 ai_requests 行、没有能力/预算/路由决定** | **收敛到统一链路**：`execute_programming_ai(capability='programming.explain')`，携带 canonical programming `LearningContext` |

改动方式（**additive**，响应原有字段一个不删）：
`backend/main.py` 把 `_course_ai_content` / `_exam_ai_content` 拆成"返回完整结果"的
`_course_ai_result` / `_exam_ai_result`（原函数保留为一行 wrapper，11 个既有调用方零改动），
`/code/analyze` 两条分支都取 `result.request_id` 并加入响应：
`{"success", "answer", "language", "code_truncated", "request_id"}`。

**行为变化（如实报告，故意的）**：programming 分支不再问 legacy 每日配额，改由统一
`Subscription → Capability Permission → Usage Budget` 授权——这正是仓库自己对
课程分支写下的规则（"legacy per-service quota does not get a second vote"）。
后果：`programming.explain` 属 **Standard+** 能力，**Free 档位在该分支会得到 403**
（此前 legacy 配额可能放行）。这是用户明确要求的收敛（"将其收敛到已有统一"），
不是副作用；测试与报告都显式记录。

**禁止项全部满足**：id 不是前端生成的、不是随机的、不是 workflow_id 冒充的——它就是
`ai_requests.request_id`，测试直接回表核对（capability / status=settled / tier / provider /
credits / service_namespace）。

---

## CODE_DIAGNOSE_REQUEST_ID = **NOT_APPLICABLE（该端点不产生任何 AI 请求）**

`POST /code/diagnose` 是**确定性语法诊断**：C 走容器内 `gcc -fsyntax-only`，Python 走
本机 `sys.executable -m py_compile`，其它语言直接返回 `unsupported`。
**它从不创建 `ai_requests` 行，因此没有 request_id 可暴露**；它也不是"绕过了统一链路"
——它根本不在这条链路上。

**没有把它收敛到 AI 栈，理由（这是决定，不是遗漏）**：
1. 收敛 = **凭空新增一次模型调用**（新的计费、新的能力依赖），属于"新增功能"，
   违反本轮约束，也违反 `NO MODEL → PRODUCT STILL WORKS`（语法检查不该因为模型不可用而失效）；
2. 语义会变：今天是"编译器的真实错误行号"，收敛后变成"模型对错误的描述"，
   与"保持现有 endpoint 行为兼容"直接冲突。

因此契约是**显式无声明的**：响应**不含 `request_id` 字段**（不是 `null`，是不存在），
并有测试持有该事实。前端若需要 AI 诊断，应改用真正的 AI 端点
（`/code/analyze`、或 `/programming/agent/debug`）——那是前端决定，不在本轮。

**顺带发现（同类问题，本轮只报告不处理）**：`/code/diagnose` 目前是前端
`useCodeCoach` 的 **"debug"** 动作目标（`programming.ts` 把 `kind==='debug'` 映射到
`/code/diagnose`），但它只接受 `{language, code}`、不做任何 AI 推理。这是
**前后端语义错配**，属于前端阶段的问题。

---

## DEBUG_AGENT_TOP_LEVEL_FEEDBACK_IDENTITY = **BLOCKED**

按 §A3 的判定顺序：

* **方案 1（直接暴露已存在的 workflow-level ai_requests identity）——不存在。**
  P3A 的真实结构是：**每个 model step 一行** `ai_requests`，`request_id` 为
  `"{run_id}:{step_index}:{action}"`（确定性）；`agent_run_id` 是**工作流标识**，
  不是任何 `ai_requests` 的 id。顶层暴露任意一个 step id 就是"冒充"，被明确禁止。
* **方案 2（用现有能力建一个真实 parent request）——现架构不支持，且会破坏语义。**
  统一 AI 基础设施的执行模型是 **一次 `execute()` = 一个 ai_requests 行 = 一次 reserve +
  一次 settle**，没有 parent/child accounting；`usage_ledger.reference_key` 按
  `request_id + period` 唯一。每个 step 的 credits **已经各自结算**，
  再造一个 parent 行只有两种结局：**重复计费**，或造一个**零计费的假 model 行**——
  后者正是 §A3 明文禁止的 "为了反馈伪造一个假的 model request row"。

**因此保持 blocker，不伪造。** 明确的结论与出路：

* Debug Agent 顶层**不返回** `request_id`（测试断言 `"request_id" not in body`）；
  `agent_run_id` 保持为工作流身份，**不做任何 id 冒充**；
* 反馈**并非不可用**：每步的 `ai_request_id` 本来就在响应 `steps[]` 里，是真实的、
  属于调用者的、**可被 `POST /ai/feedback` 接受**的 id（测试逐步回表 + 逐步反馈成功）；
* 若要"一次评分覆盖整次 run"，需要的是**统一的 parent/child accounting 模型**
  （计费语义变更 + 迁移 + 结算规则），那是一次产品/架构决定，不是本轮可达范围。

---

## FEEDBACK_ROUND_TRIP = **PASS（三处真实闭环 + 所有权不弱化）**

| 场景 | 结果 |
|---|---|
| `/code/analyze`（course 分支） | 200 → `request_id` → feedback 200，`capability=programming.explain`，`trains_router_online=false` |
| `/code/analyze`（programming 分支） | 同上，且 `service_namespace=programming`、`context_json.programming_language` 存在 |
| `/chat`（course 分支） | 答案的真实 `request_id` → feedback 200 |
| Debug Agent 每一步 | 每个 `steps[].ai_request_id` 都能单独反馈成功 |
| **他人 request_id** | **404**（`p61_other` 评 `p61_owner` 的 id → 404；用他人 username 调用 → 403） |

`POST /ai/feedback` 的 owner check 一行未改；新增测试证明它仍然生效。

**额外收口（同类缺陷，本轮一并修，属"所有真正发生 AI request 的 product endpoint"规则）**：
`POST /chat` 的 course / exam 分支**已经**创建 `ai_requests` 行却把 id 丢掉，
而**前端 `CourseAskPage` 本来就在读 `chat.data.request_id`**（读到的是 undefined，
反馈按钮因此形同虚设）。现在返回真实 id；programming 分支（仍走 legacy `call_deepseek`）
如实返回 `request_id: null`——**没有身份就说没有，不伪造**。

---

## E2E_HARNESS = **BUILT（一套，不是第二套 app）**

| 文件 | 角色 |
|---|---|
| `backend/scripts/e2e_harness.py` | **唯一**环境生命周期：temp dir → DATABASE_URL → `APP_ENV`/`DATA_ORIGIN` → `alembic upgrade head` → seed → 起服务 → 健康就绪 → 确定性关停 |
| `backend/scripts/e2e_serve.py` | 服务入口：**只替换 provider 边界**（`ai.orchestrator.default_provider_factory` → `FakeProvider`），其余是**原样**的 `main:app` |
| `backend/scripts/e2e_seed.py` | 最小 seed（见下） |
| `scripts/start-e2e-backend.sh` | §H 的**一条命令**入口（自动挑 venv python） |

**没有第二套 app**：`uvicorn.run("main:app")`，一个 app。也**没有生产 flag**——
prod 环境变量切 provider 会是安全漏洞，所以 fake 只存在于测试启动器里。

---

## E2E_AUTH = **PASS（真实 session 契约）**

`POST /login {username, password}` → 200 + `ai_session` cookie（httpOnly / SameSite=Lax /
本地非 secure）→ 带 cookie 的后续请求被授权（`POST /me` 200）；匿名调用 `POST /me` = **401**；
learner 访问 admin 聚合面 = **403**。**没有** localStorage 伪造、没有绕过 session 代码。
前端无需改源码：app 自己读 `VITE_API_BASE_URL`（默认 `localhost:8000`），
所以 `VITE_API_BASE_URL=http://127.0.0.1:<port>` 即可（必须两侧都用 `127.0.0.1`，
否则 SameSite=Lax 不会带上 cookie——契约里写明了）。

---

## E2E_FAKE_PROVIDER = **PASS（走完整统一栈，不是 mock HTTP）**

在**真实运行的服务器**上实测：`/code/analyze` → 200，响应 `request_id=cd3b2c04…`，
回表得到 `capability=programming.explain, status=settled, actual_credits=1,
provider=deepseek, model=deepseek-flash, tier=standard`，
`POST /ai/feedback` 对同一 id 返回 200。即：
**Capability → Permission → Usage reserve → Router（从 Qualified Pool 选型）→ Gateway（Fake）→
settle → ai_requests** 全程真实，只有最后一跳是 double。

---

## E2E_DATA_ORIGIN = **ACCEPTANCE（进程级，写死在 harness 环境里）**

harness 子进程环境固定 `APP_ENV=acceptance`、`DATA_ORIGIN=ACCEPTANCE`；
`data_plane.origin.active_origin()` 因此对**该进程写下的每个事实**盖章 `ACCEPTANCE`。
测试直接查 harness 库：`SELECT data_origin, COUNT(*) FROM learning_events GROUP BY …`
→ **只有 `ACCEPTANCE` 一个值**。

---

## TRAINING_READINESS_UNCHANGED = **PASS**

* harness 库中 `data_origin='LEARNER'` 的 learning_events = **0**；
* `science.kt_native.audit(db)` → `users_with_eligible_interactions = 0`、
  `total_eligible_interactions = 0`；
* `kt_native.evaluate_readiness(...)` → `verdict = FAIL`，
  `failed_checks` 含 `users_with_eligible_interactions`；
* 结论：**E2E 不可能让 readiness 增长一格**（只有 `LEARNER` origin 才可计数，
  且生产环境明确拒绝伪造 origin，测试数据在只读审计里是空桶）。

---

## TESTS

**新增 14 条，全部通过**：

* `backend/tests/test_p6_1_ai_request_identity.py`（6）
  course 分支真实 id + 回表 + 反馈闭环；programming 分支收敛（回表 namespace/context、
  **legacy `ai_usage_logs` 计数不增**）；id 不可借用（404/403）；
  **diagnose 无 AI 请求、无 request_id**；`/chat` 真实 id；
  Debug Agent 顶层无 request_id、逐步 id 真实可反馈。
* `backend/tests/test_p6_1_e2e_harness.py`（8，**真起进程**）
  temp DB + `app.db` 不被打开；健康就绪；真实登录/401/403；
  fake provider 走完整栈 + 反馈闭环；seed 的产品态可达（agenda / wrong-answers）；
  全部事实 `ACCEPTANCE`；readiness 不增长；`stop()` 删掉 temp dir。

**测试基础设施本身的修复（本轮踩到并处理）**：
1. **孤儿服务**：`timeout` / 强杀 harness 父进程时，uvicorn 子进程会活着继续服务。
   已加**心跳看门狗**（父进程每秒 touch 心跳文件，子进程 20s 收不到自我退出）——
   实测强杀父进程后 30s 内服务自动下线、无孤儿进程。
2. **Windows 句柄**：父进程持有 server log 句柄会让 temp dir 删不掉；
   已改为 `stop()` 中先关句柄、再带重试删除。

**既有测试影响：3 个文件、5 条架构守卫测试需要同步（都是"守卫要求你更新声明"，不是回归）**

第一次全量运行如实暴露了它们（`5 failed, 1750 passed`），逐条核实后按守卫的**原意**更新：

| 测试 | 失败原文 | 处理 |
|---|---|---|
| `test_course_ai_reachability.py::test_every_direct_provider_callsite_is_declared_non_course` | "declared callsites no longer exist, drop them: `['analyze_code']`" | 从 `NON_COURSE_DIRECT_CALLS` **删除 `analyze_code`**——收敛后它不再直连 provider，守卫主动要求撤销声明 |
| 同上 `::test_direct_calls_in_course_endpoints_are_guarded_by_another_space` | "analyze_code is declared non-course but has no direct call" | 同上（同一份声明） |
| 同上 `::test_every_course_ai_endpoint_reaches_the_unified_boundary` | "chat does not reach the AI orchestrator boundary" | `AI_BOUNDARY_FNS` 增加 `_course_ai_result` / `_exam_ai_result` / `execute_programming_ai`（同一调用的新入口名） |
| `test_exam_ai_orchestrator.py::test_exam_endpoints_reach_the_exam_boundary` | "chat does not reach the exam boundary" | 同一份边界标记表增加 `_exam_ai_result` |
| `test_gateway_migration.py::test_course_code_analysis_uses_course_orchestrator_boundary` | 403（替身被绕过，走到了真实 orchestrator） | 替身改为 patch `_course_ai_result`（新边界入口），返回带 `.content` / `.request_id` 的 stub；**断言原意不变**（"必须走统一边界、不得碰 legacy client"） |

**这些更新让守卫更强，不是更弱**：`analyze_code` 现在落在
`test_pure_course_endpoints_never_call_a_provider_directly` 的"纯 Course"集合里，
**由测试断言它永不直连 `call_deepseek`**——收敛前它做不到这一点。

最终全量：见 `FULL_SUITE`。

---

## FULL_SUITE

**最终实测（守卫同步后的修订，未再改动代码）：
`1755 passed, 2 skipped in 1818.86s (0:30:18)`，exit 0。**

（第一次全量：`5 failed, 1750 passed, 2 skipped` —— 5 条失败全部是架构守卫的声明过期，
逐条核实并按其原意同步后重跑。见 §TESTS 的表。）

---

## MAIN_DB_TOUCHED = **NO**

全量套件前后逐字节一致（SHA256 / size / mtime 三者均未变）；harness 运行后
OS temp 中残留的 `zhixue-e2e-*` 目录数 = **0**（正常关停路径确实清理了）。

| 时点 | sha256 | size | mtime |
|---|---|---|---|
| before | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |
| after | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |

harness 自身还有双向防护：`DATABASE_URL` 由生命周期写入 temp 目录；`e2e_serve.py`
在启动时**拒绝**任何指向 `app.db` 的 DATABASE_URL（exit 2）；`alembic` 显式接收
`DATABASE_URL`（不带它 alembic 会解析到真实 `backend/app.db`）。

---

## FRONTEND_AUTHENTICATED_E2E_READY = **YES（后端侧就绪，前端零改动）**

一条命令，输出稳定契约：

```bash
bash scripts/start-e2e-backend.sh --json
```

```json
{"base_url": "http://127.0.0.1:<free-port>", "port": 49999,
 "health": "http://127.0.0.1:<port>/api/health",
 "username": "e2e_learner", "password": "e2e-learner-pass-1", "tier": "standard",
 "login_path": "/login", "auth": "session cookie (ai_session); POST /login",
 "data_origin": "ACCEPTANCE", "app_env": "acceptance",
 "database_url": "sqlite:///<temp>/e2e.db", "temp_dir": "<temp>", "log": "<temp>/server.log",
 "frontend": {"vite_api_base_url": "http://127.0.0.1:<port>", "note": "..."},
 "cleanup": "SIGINT/SIGTERM (or stop()) — only this backend, then the temp dir"}
```

前端消费方式（**不需要任何源码改动**）：

```bash
VITE_API_BASE_URL=http://127.0.0.1:<port> npm run dev     # 5173 起 dev server
npx playwright test                                        # 用 username/password 真实登录
```

seed 覆盖的最小闭环（§E）：一个 learner（真实密码）＋ 一个真实 `subscriptions` 行
（Standard，**不绕过 entitlement 代码**）＋ 一门课程（`数据结构`）＋ 一道课程题
（并**经产品自己的练习核心**记录一次错误作答 → 错题态 / 复习项 / 课程历史都由产品生成）
＋ 一个 CS408 profile（考试空间可达）＋ 一个编程题目＋项目＋`needs_work` 事实 ＋ 一条计划任务。

**实测记录（本轮真的跑过，不是纸面契约）**：
`bash scripts/start-e2e-backend.sh --json` → 拿到 `port=64757` → `POST /login` 200 +
`ai_session` → `POST /code/analyze` 200（`request_id=cd3b2c04…`）→ 回表
`programming.explain / settled / credits=1 / deepseek / deepseek-flash / standard` →
`POST /ai/feedback` 200。强杀父进程后 30s 内服务自动下线、无孤儿进程、无残留监听端口。

---

## BLOCKERS

1. **`DEBUG_AGENT_TOP_LEVEL_FEEDBACK_IDENTITY = BLOCKED`**（见上）。需要一次
   parent/child accounting 的产品/架构决定，才可能有"整次 run 一个 id"的反馈。
   现状：逐步 id 已可用且被测试覆盖。
2. **`/chat` 与 `/code/challenges/*/submit` 仍有 legacy `call_deepseek` 绕过点**
   （本轮按窄范围只收敛了 `/code/analyze`）。二者都会创建**没有 ai_requests 行**的
   AI 回答（`/chat` 编程分支已如实返回 `request_id: null`）。列为后续同类收敛项。
   *（`/chat` 的 course/exam 分支已在统一栈上，本轮已补出真实 id。）*
3. **`/code/diagnose` 的前后端语义错配**：前端把它当"AI 调试"用，它其实是确定性语法检查。
   属前端阶段决定（改用真实 AI 端点，或明确它是编译器诊断）。
4. **programming 分支的授权变化**：Free 档位现在在该分支得到 403（Standard+ 能力）。
   若产品希望 Free 也能用，需要的是**能力政策决定**（`usage/capabilities.py` 的 tier 表），
   而不是恢复 legacy 配额。
5. **前端 Playwright 尚未接入 harness**：后端契约已就绪（H），但本轮禁止改 frontend 源码，
   因此没有新增 e2e spec、也没有把 `VITE_API_BASE_URL` 接进 `playwright.config.ts`。
   下一轮前端只需按上面的两行命令使用。
6. **强杀 harness 会留下 temp 目录**（父进程来不及清理时）。已在 OS temp 目录内、
   不在仓库；子进程看门狗保证**服务一定下线**。

---

## 改动文件

**新增**
`backend/scripts/e2e_harness.py`、`backend/scripts/e2e_serve.py`、`backend/scripts/e2e_seed.py`、
`scripts/start-e2e-backend.sh`、
`backend/tests/test_p6_1_ai_request_identity.py`、`backend/tests/test_p6_1_e2e_harness.py`、
本报告。

**修改**
`backend/main.py`（`_course_ai_result` / `_exam_ai_result` 拆分；`/code/analyze` 两分支 +
`request_id`；`/chat` 返回真实 `request_id`）；
`backend/tests/test_course_ai_reachability.py`、`backend/tests/test_exam_ai_orchestrator.py`、
`backend/tests/test_gateway_migration.py`（架构守卫的声明/边界名的同步更新，见上表）。

**未改**：`frontend/**`（零改动，P6.1 明确禁止）、`migrations/**`、`alembic.ini`、
`schema`、`backend/app.db`；**P6 冻结契约指纹未漂移**
（`backend/scripts/freeze_advanced_api_contract.py` 重跑：`entries=21 missing=0
surface=572d9e68c9bc5138`，与 P6 记录**完全一致**）。
