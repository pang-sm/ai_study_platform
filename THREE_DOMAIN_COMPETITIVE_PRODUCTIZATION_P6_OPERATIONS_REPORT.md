# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6 — OPERATIONS AND HARDENING

> 范围：**仅 backend / ops / admin 契约**。未新增任何普通学习功能，未重新审计整个项目，
> 未 commit，未 deploy。scope 内没有 schema 迁移（见 §C / §D 的决定）。

**目标**：把既有高级能力变成**可运营、可审计、可安全生产**的系统。

---

## AI_OPERATIONS

**新增（admin-only，只读，聚合）**：
`GET /admin/ai-operations/summary?window_days=1..365`（默认 30）

权限：复用既有 `ai_logs.view`（operator / auditor 已持有）——**不新增权限**。

返回（顶层形状由 `AIOperationsSummary` 声明，越界即 500，测试覆盖）：

| 段 | 内容 |
|---|---|
| `requests` | total / success / failure / denied / held / in_flight / 成功率 / 失败率 / `by_status` |
| `latency` | samples / avg_ms / p50_ms / p95_ms（`started_at → finished_at`） |
| `credits` | estimated_total / actual_total / settled_calls / held_calls |
| `by_capability` / `by_model` / `by_provider` / `by_tier` / `by_service_namespace` | 每桶：requests、success、failure、denied、held、avg_latency_ms、estimated/actual credits |
| `router` | `by_reason_code`、`fallback_count`、`fallback_rate`、`by_status`、`failed_by_error_category` |
| `feedback` | up / down / ratings / down_rate / `by_reason` |
| `availability` | scope、deployment_requirement、failure_threshold、cooldown_seconds、tracked_models、degraded_models、models |
| `bounded` | 扫描上限与是否截断（`requests_truncated` / `events_truncated`） |
| `privacy` | 返回什么 / 永不返回什么，机器可读 |

**数据来源按度量分别声明**（两套来源可能不一致，因此逐项写明）：
`ai_requests`（会计行：状态、档位、credits、provider/model、延迟）+
`learning_events:ai_called`（路由原因码、候选池、fallback——fallback 只有一个记录处）+
`learning_events:ai_feedback_submitted`（**复用**既有 `learning.feedback_analytics` 聚合，不建第二套）+
`ai.health` registry（可用性）。

**状态语义（不混淆）**：`settled`=成功；`released`=失败（确认零计费）；
`reconciliation_pending`=**held**（真实用量待结算，不是失败）；`denied`=策略答复（不是故障）；
`reserved`/`executing`=in-flight。把 held 或 denied 折进 failure 会让失败率说谎。

**隐私边界（测试强制）**：不返回 prompt、回复正文、用户 id、用户名、request_id、
错误正文、文件系统路径、provider 密钥。`by_model` / `by_provider` 按名字聚合是
**用户明确要求**的（§A），也只在这里出现。

---

## WORKFLOW_OPERATIONS

**新增**：`GET /admin/workflow-operations/summary?window_days=…`（同权限）

覆盖五个高级工作流：Deep Study / Debug Agent / Learning Report / Wrong Analysis /
Plan Adjustment。每个工作流两层：

* **accounting**（来自 `ai_requests` of 该 capability）：calls、success/failure/denied/held、
  延迟（samples / avg / max）、estimated 与 actual credits、
  **归一化** `failure_by_category`（闭集：timeout / rate_limited / authentication / …，
  绝不是 provider 错误正文）。
* **activity**（来自该工作流自己的 canonical events）：
  - deep_study → `strong_reasoning_requested` / `strong_reasoning_completed`
  - programming_agent → `programming_agent_started` / `_completed` / `_failed`
    + **`agent` 子块：runs_finished、by_status、iterations、executions、model_steps、
    step_credits、stop_reasons、error_categories**（逐项 requirement：Debug Agent
    的 iterations / execution count 聚合）
  - learning_report → `report_generated`
  - wrong_analysis → `wrong_analysis_generated`
  - plan_adjustment → `plan_adjustment_proposed` / `_applied`

**不返回学习者源码**：agent 的 iterations / executions 只从已存的 **code-free step trace**
（`learning_events` 载荷里的 index / action / status / latency / tests / patch 的**尺寸**）
计数；patch 文本、diff、源码、prompt、模型回复一律不在返回里（测试扫描强制）。

---

## AGENT_TRACE_STORAGE_DECISION

**结论：YES —— 现有 durable trace 已满足五项要求，保留现有实现，不做迁移、不加表。**

| 要求 | 判定 | 依据（可复验） |
|---|---|---|
| restart recovery | **YES** | 每步模型调用都有独立 `ai_requests` 行，`request_id = "{run_id}:{step_index}:{action}"`（确定性），在进程死亡之前就已提交；run 级事实在 `learning_events`（同样独立提交）。重启后二者都可读回。 |
| workflow detail read | **YES**（本轮补齐读取投影） | 新增 `GET /admin/workflow-operations/agent-runs/{run_id}`：从 `learning_events` 取 code-free 逐步 trace，从 `ai_requests` 取每步 status/latency/credits/provider/model。 |
| pagination | **YES** | 单 run 的 trace 由硬边界限量（`MAX_ITERATIONS=3` / `MAX_EXECUTIONS=4` / `MAX_MODEL_STEPS=7`），无需分页；工作流级列举走既有 cursor 分页（`GET /learning-records`，limit ≤ 200）。 |
| audit | **YES** | 三个 canonical 事件（started/completed/failed）带 `snapshot_completeness=PARTIAL` + `snapshot_missing_fields=["code","prompt"]`，即"缺什么"是**被记录**的；每步另有 `ai_called` 审计事实。 |
| debugging | **YES** | 逐步 status / latency / credits / error_category，加上每次执行的真实测试结果（`tests`），足够定位"第几步、哪一次执行、什么类别失败"。 |

**为什么不需要 dedicated table**：一张 `programming_agent_runs/_steps` 表能表达的，
现有两处存储已经用**不同粒度**表达完了（每步的会计粒度 + run 级的 code-free 轨迹粒度），
且新增表会带来一次跨 sprint 治理成本（见 §D 的 migration 说明）。
**边界（诚实声明）**：patch 文本与最终代码**只在响应里**，服务端不持久化——
§34 禁止把源码写进事件载荷，而本轮不新建 owned store。这不影响上述五项要求，
因为五项要求的对象是**运行的可恢复性与可审计性**，不是源码归档。

**本轮实际改动**：只增加了**只读投影**（`backend/ops/workflow_operations.py::build_agent_run_detail`
+ 一个 admin 路由），零 schema 变更、零写入路径。

---

## WRONG_ANALYSIS_STORAGE_DECISION

**产品需求判定：是真实缺口。** 用户应当能重新打开旧错题看到上一次 AI 错因分析；
当前只能"当次显示、不能恢复"（响应里 `persistence.stored = false` 已如实声明）。

**复用检查（逐条，结论：不可复用）**：

| 候选 | 是否能安全复用 | 原因 |
|---|---|---|
| `ai_requests` | **否** | 该表**没有**响应正文列（只有 request_id / capability / 状态 / credits / provider / model / 时间）。事实核对：`backend/usage/models.py`。 |
| `ai_cost_records` | 否 | 只有 token 与成本。 |
| `chat_messages` | 否 | 属于 ChatSession 的聊天面；把错因分析写进去会让它**出现在学习者的 AI 问答历史里**——那是另一个产品面，不是"安全复用"。 |
| `code_ai_messages` | 否 | 同上，且限定编程面。 |
| `learning_events` | 否 | §34 禁止把正文写进 canonical 事件载荷。 |
| `practice_attempts.result_json.error_analysis` | **否（且明确禁止）** | 那里是**确定性**判分反馈（`_attempt_view` 的 `error_analysis`）。把 AI 假设写进同名字段会**混淆两种来源**，正是 P3B 禁止的事。 |

→ 结论：**不存在可安全复用的 AI 响应正文存储**。按任务要求，本轮**提出最小 owned
persistence schema**（不实施，理由见下）。

### 提议的最小 schema（`20260920_0013`，待授权）

```sql
CREATE TABLE ai_analysis_artifacts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id         VARCHAR(64)  NOT NULL UNIQUE,   -- 产出它的 ai_requests 身份
    user_id            INTEGER      NOT NULL,          -- owner；检索一律按 owner 收敛
    capability         VARCHAR(50)  NOT NULL,          -- wrong_answer.analyze
    service_namespace  VARCHAR(50)  NOT NULL,
    subject_type       VARCHAR(40)  NOT NULL,          -- 'wrong_answer_state'
    subject_id         VARCHAR(64)  NOT NULL,          -- 该 state 的 id
    scope_key          VARCHAR(255) NOT NULL,          -- 该 state 所属 course / exam module
    artifact_json      TEXT         NOT NULL,          -- {error_category, reasoning_gap, ...}
    created_at         DATETIME     NOT NULL
);
CREATE INDEX ix_ai_analysis_owner_subject
    ON ai_analysis_artifacts (user_id, subject_type, subject_id, created_at DESC);
```

**契约（与 P3B 语义一致）**：
* 写入：**仅在**一次成功的分析之后、同一请求内；append-only，不 update / 不 delete
  （多次分析 = 多条历史，"最新一条"为展示对象）。
* 读取：`GET /wrong-answers/{state_id}/analysis` 增加"返回该 owner + 该 state 的最近一次分析"；
  所有权按**既有** resolver 规则（他人 state 仍 404）。
* **永不写入确定性学习事实**：`facts` 与 `analysis` 继续分别标注
  `fact_origin=deterministic` / `analysis_origin=ai`，AI 假设不进 `practice_attempts`、
  不进 knowledge / mastery 任何字段。
* 保留策略（需一次产品决定）：每 (user, subject) 保留最近 N 条，或按时间窗清理。

**为什么本轮不实施**：该表需要一次 Alembic revision（`20260920_0013`），会**同时**要求修改
7 个 sprint 冻结的 head-pin 断言（`test_s5` / `test_s9` / `test_s6` / `test_s4` /
`test_practice_migration` / `test_bc7_*` / `test_exam_final_acceptance` 断言
`EXPECTED_HEAD == "20260919_0012"`）。P3A / P3B 已把这件事明确报告为**跨 sprint 治理动作**，
需要用户单独授权。本轮任务是运营/管理契约，不是 schema 迁移，因此**只提出、不实施**。

**本轮实际改动**：新增一个**持有该缺口的测试**
（`test_the_wrong_analysis_gap_is_stated_and_never_written_into_a_learner_fact`），
锁定三件事：`persistence` 块的精确内容（缺口不会被悄悄"说成已存"）、
重新打开会产生**新请求**（无恢复路径）、AI 假设**没有**写进确定性记录。

---

## FEATURE_FLAGS

**复用，不重建**：存储用既有 `system_settings` 键值表（`feature_flag.<name>`），
管理面用既有权限 `feature_flags.manage`（super_admin），审计走既有 `_write_audit_log`。
**没有新表、没有第二套配置系统、没有新权限。**

**七个高风险高级能力可独立关闭**：
`deep_study` / `programming_agent` / `learning_report` / `wrong_analysis` /
`dynamic_planning` / `adaptive_practice` / `intelligent_review`。

**四种模式**：

| 模式 | 语义 | 强制点 |
|---|---|---|
| `OFF` | 所有人关闭（管理员也拒绝） | 入口边界，**先于任何工作**（不检索、不执行、不预留） |
| `INTERNAL` | 仅管理员账号可达（管理员可无付费档位演练） | 入口边界 + entitlement 放行（仅管理员） |
| `TIER` | **默认**：开关层不设限，由统一订阅政策判定（与 P6 之前行为完全一致） | 无 |
| `ALL` | 为该**一个**能力放行 entitlement，所有已登录学习者可达 | 入口边界 + entitlement 放行 |

**`ALL` 到底改了什么（精确边界）**：
* 只放宽**权限判定**一步。评估档位取该能力的**最低已允许档位**（`minimum_tier_for`），
  因此模型选择按能力本身应有的档位评估，而不是"最高档位"。
* **不改**：用量预算、`estimate → reserve → settle` 链路、`ai_requests.tier`
  （仍记录**真实档位**）、模型池资质、结算。
* **不放宽所有权**：他人资料 / 他人错题 / 他人项目仍按原规则拒绝（测试
  `test_an_all_grant_widens_entitlement_but_not_ownership` 断言）。
* 放行**被记录**：该次调用的 `ai_called` 审计事实带 `entitlement_grant: "ALL" | "INTERNAL"`
  （被服务、被释放、待结算、以及**放行后被预算拒绝**的调用都带上——因此"放行了但用户用不起"
  也是一个可统计的信号）。
* 未写任何 subscription 行——不需要迁移、不产生第二会员来源。

**生效方式**：`PUT /admin/feature-flags` 之后**下一个请求**即生效，无需重启、无需部署。

**改动的文件（entitlement 放行的最小穿线）**：
`backend/ops/feature_flags.py`（新）、`backend/ai/orchestrator.py`（放行只查一次：
仅在策略**拒绝**的那条路径上；过闸档位 `gate_tier`）、
`backend/usage/service.py::reserve_credits`（新增可选 `permission_tier`，**只**用于权限判定，
预算封顶/账本/结算/记录档位仍用真实档位）、
`backend/learning/deep_study.py` 与 `backend/learning/spaces/programming/agent.py`
（既有的"先检查后干活"前置检查改为同一组合 `capability_permitted`）、
`backend/routers/ai_models.py`（`GET /ai/models` 的菜单与放行一致，否则会出现"能用但列不出"）、
`backend/learning/records/producers.py`（`ai_called` 载荷新增可选 `entitlement_grant`）。
**默认路径不变**：`permission_tier=None` / 未设置开关 ⇒ 字节级等价于原行为。

---

## PRODUCTION_VERIFICATION_PREP

**新增脚本**：`deploy/verify_production_topology.sh`（**只读**，不 SSH、不 deploy、不重启）。
本机 dry-run 已验证可运行（在非服务器环境如实输出 `UNKNOWN` 并 exit 1）。

检查项（对应 §F 清单）：

1. `systemctl cat ai-backend` → 打印 ExecStart / WorkingDirectory / Environment；
   在 ExecStart 里找 `--workers N>` 或 gunicorn ⇒ **worker 信号**。
2. 活进程树：`systemctl show -p MainPID` + `ps --ppid` + `pgrep -a -f 'uvicorn|gunicorn'`，
   子进程数 > 1 ⇒ **worker 信号**。
3. nginx：`nginx -T` → 找 `upstream` / `proxy_pass`；`:8000` 的 upstream server 数 > 1
   ⇒ **多后端信号**。
4. 后端健康：`curl /api/health`（HTTP 码 + body）。
5. 科学运行时健康：`systemctl is-active zhixue-runtime` + `curl 127.0.0.1:8101/health`。
6. 结论：`SINGLE_PROCESS`（exit 0）或 `MULTI_WORKER` / `UNKNOWN`（exit 1，并把
   **Router availability 共享状态要求升级为 deployment blocker** 写进输出）。

**仓库内可确证的既有事实**（P5 的推断仍然成立，但不等于运行时已验证）：
`deploy/nginx-ai-study-platform.conf.example` 的 `/api/` 是**单个** `proxy_pass
http://127.0.0.1:8000/`（无 `upstream` 块）；`deploy/ai-backend-runtime.conf` 只有环境变量
drop-in；`.github/workflows/deploy.yml` 只做 `systemctl daemon-reload/restart ai-backend`，
**没有 `--workers`**。基础 unit 的 ExecStart **不在仓库里** —— 这正是必须现场执行本脚本的原因。

---

## SECURITY_PRIVACY

**新增测试**：`backend/tests/test_p6_security_privacy.py`（6 条）。逐项对应 §G：

| §G 要求 | 覆盖 |
|---|---|
| cross-user | 他人 state 的错因分析仍 404（且在 `ALL` 放行下仍 404）；他人资料不作为证据 |
| cross-course / cross-module | 由 P1.2 / P3A / P3B 既有测试持有，本轮不重复；新面（ops 读）不按课程/模块切分，故不适用 |
| cross-language | **新增**：编程空间 adaptive 的 `language` 参数隔离（Java 题不进入 Python 选择，反之亦然） |
| admin-only analytics | 三个聚合面（AI ops / workflow ops / feedback platform）非管理员一律 403；auditor 只读角色可取；角色被收回后立即 403 |
| request ownership | feedback 只能评自己的 request（P4 既有 + 本轮聚合面无 request_id） |
| material ownership | **新增**：`ALL` 放行下，他人的 private material 仍被 `excluded` 具名拒绝，其正文不出现在任何响应里 |
| project ownership | 由 P3A 既有测试持有 |
| wrong-answer ownership | 本轮新增"放行不放宽所有权"的断言版本 |
| 不泄露 provider secret / API key | 全 payload 扫描 `api_key` / `sk-` / `bearer ` / `authorization:` / `password` / `token=` |
| 不泄露 prompt internals | 扫描提示词片段（"你是一名" / "严格返回JSON"） |
| 不泄露他人内容 | 两个用户 + 私有资料的交叉请求，断言他人正文不出现 |
| 不泄露内部路径 | 扫描 `C:\` / `/var/` / `uploads/` / `backend/.env` |
| agent trace 无源码 | run detail 扫描 `def ` / `#include` / `content`；patch 只以**尺寸**出现 |

**一处既有事实（非 P6 引入，如实报告）**：模型菜单
（`GET /ai/models`，以及工作流响应里的 `model.options`）**按设计**会给出 provider 与
model 名（`pool.user_visible_options` 的既有契约），这是"让学习者选模型"所必需，
**不是**密钥泄露；P6 的测试据此把"provider 名"与"凭证材料"分开断言，
并额外断言**用户可见的模型标签**（`display_name`）与**答案/引用**中不出现 provider 名。
`provider secret`（密钥本体）在任何响应中都不出现。

---

## API_CONTRACT_FREEZE

**新增**（比赛版本冻结当前高级能力 API）：

* `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.json`（机器可读）
* `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.md`（人可读）
* 生成器：`backend/scripts/freeze_advanced_api_contract.py`

**21 条**冻结入口，覆盖 Deep Study / Debug Agent / Review / Report / Wrong Analysis /
Planning Adjustment / Adaptive / Feedback / Agenda + 本轮 5 条 admin ops。

每条记录：method、path、handler、**参数名（含 in 与是否必填）**、
**请求模型名 + 其顶层字段名**、**响应模型名 + 其顶层字段名**、冻结意图、一句 handler 契约，
以及 `fingerprint`（前 16 位 sha256）+ 总 `surface_fingerprint`。

**它不是 OpenAPI 的副本**，是**漂移探测器**：重跑脚本即可看出哪一条移动了
（字段改名会改 fingerprint，前端据此知道自己踩到了契约变更）。
数据来源是 app **自己的** OpenAPI schema（公开稳定视图），不是靠猜内部结构。
本轮实测：`entries=21 missing=0 surface=572d9e68c9bc5138`。

**顺带收口**：5 条新 admin 路由原先声明 `response_model=dict`（`fingerprint` 会退化成
"dict"），已改为**声明顶层形状的 Pydantic 模型**（`AIOperationsSummary` /
`WorkflowOperationsSummary` / `AgentRunDetail` / `FeatureFlagList` / `FeatureFlagUpdateResult`）
——既让冻结指纹有意义，也让每次响应经过真实校验（漏 key 会 500 而不是静默）。

---

## TESTS

**新增 18 条**，全部通过：

* `backend/tests/test_p6_operations_and_hardening.py`（12）
  AI ops 正确性与隐私、workflow ops 五个工作流、run detail 可重建（§C 证据）、
  开关默认 TIER / OFF 次请求生效 / INTERNAL 只放管理员 / 非法输入零写入 /
  `ALL` 放行但预算仍结算且记录真实档位 / `OFF` 强于 `ALL`、
  §D 缺口持有测试。
* `backend/tests/test_p6_security_privacy.py`（6）
  放行不放宽所有权（资料 / 错题）、高级响应无密钥无提示词无路径无他人内容、
  ops 读无源码无 prompt、三个 admin 聚合面 admin-only 且聚合、
  跨语言隔离。

**测试卫生（本轮踩到并处理）**：套件共享一个临时库，因此
① 开关行是**全局**状态 —— 新增 autouse fixture，每个测试后清掉 `feature_flag.%` 行；
② 窗口计数是**累计**的 —— 断言改为**增量**（先取基线再比对），不写绝对值。

---

## FULL_SUITE

**实测（最终修订，未再改动代码）：`1741 passed, 2 skipped in 1146.03s (0:19:06)`，exit 0。**

命令：`backend/` 下 `./.venv/Scripts/python.exe -m pytest -q -p no:warnings`；
`conftest.py` **无条件**把 `DATABASE_URL` 指向临时库，因此全程不碰 `backend/app.db`。

**过程中的一次真实失败与修复（如实记录）**：第一次全量运行有 1 条失败
（`test_ai_operations_summary_is_aggregated_and_correct`，断言 `total == 3` 实测 134）。
原因不是产品缺陷，而是**我的测试写成了绝对值**——套件共享一个临时库，
窗口计数是**累计**的。已把该断言（及同文件另一处）改为**先取基线再比对增量**，
并在修复后的修订上重跑全量：1741 passed / 0 failed。

---

## MAIN_DB_TOUCHED

**NO。**（全量套件前后逐字节一致：SHA256 与 size、mtime 均未变。）

| 时点 | sha256 | size | mtime |
|---|---|---|---|
| before | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |
| after | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |

冻结脚本本身也做了防护：导入 app 会触发 schema bootstrap，因此脚本**强制**把
`DATABASE_URL` 指向临时目录（`setdefault`，不覆盖调用方显式值），并设 `UPLOAD_ROOT`
到临时目录；脚本运行前后 app.db SHA 同样未变。

---

## PRODUCTION_READY_LOCAL =

**部分就绪（PARTIAL）。**

* **就绪**：运营读契约（AI ops / workflow ops / run detail）已可用且 admin-only；
  七个高级工作流可**不部署即关闭**；契约已冻结且可重跑比对；安全/隐私有针对性测试；
  默认行为与 P6 之前完全一致（`TIER` 默认 + `permission_tier=None`）。
* **实测**：`FULL_SUITE = 1741 passed, 2 skipped`（0:19:06，exit 0）；`MAIN_DB_TOUCHED = NO`。
* **未就绪（需授权才能推进）**：
  1. §D 的 `ai_analysis_artifacts` 迁移（需 `20260920_0013` + 7 处 head-pin 更新）；
  2. 生产拓扑**尚未现场验证**（脚本已就绪，但本轮不 SSH）；
  3. `frontend/src/types/api.ts` **未重生成**（本轮 scope 限定 backend/ops/admin，
     前端类型不属于本轮；新增的 5 条路由对前端类型无影响，冻结文档已覆盖契约）。

---

## DEPLOYMENT_BLOCKERS =

1. **生产拓扑未验证（P5 遗留，本轮准备好检查能力但未执行）**。
   若 `deploy/verify_production_topology.sh` 报告 `MULTI_WORKER`，
   则 **Router availability 的共享状态要求升级为 deployment blocker**：
   `ai.health` 是进程内状态，多 worker 下"某模型已降级"只在其中一个进程为真，
    `/admin/ai-operations/summary` 的 `availability` 段与降级排序会失真。
   同一条单进程假设也被 in-process Docker semaphore 与代码运行限流器共享。
2. **多 worker 时的另一个隐含影响**：fallback 计数与 reason code 仍准确（来自持久化审计事实），
   **只有** availability 段受影响 —— 这条区分必须写清楚，否则会误判为"ops 数据不可信"。
3. **AI 响应正文无 owned store（§D）**：错因分析不可恢复。不是"运行阻断"，
   是"产品缺口 + 一次待授权的跨 sprint 迁移"。
4. **前端类型未重生成**：新 admin 路由未进入 `frontend/src/types/api.ts`。
   若前端要在管理面消费这些契约，需在**前端阶段**单独执行 `npm run api:generate`
   （注意：`package.json` 的 `api:generate` 指向不可靠的 localhost:8000，需按既有 workaround
   用临时 spec 在非 8000 端口生成）。
5. **`learning_report` 的 OFF 语义**：关闭后整条 `/ai/learning-report` 不可达，
   包括其中的**确定性**报告（本身是 Free 能力）。这是"整条工作流可独立关闭"的直接后果，
   已在契约里写明；若产品希望"只关 AI 叙事、保留确定性报告"，那是一次产品决定，
   不是本轮的实现选择。

---

## 附：本轮改动文件清单

**新增**
* `backend/ops/__init__.py`、`backend/ops/feature_flags.py`、
  `backend/ops/ai_operations.py`、`backend/ops/workflow_operations.py`
* `backend/routers/admin_ops.py`
* `backend/tests/test_p6_operations_and_hardening.py`、`backend/tests/test_p6_security_privacy.py`
* `backend/scripts/freeze_advanced_api_contract.py`
* `deploy/verify_production_topology.sh`
* `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.{json,md}`
* 本报告

**重要前提（工作树状态，如实报告）**：开工时工作树**已经**带有前序 sprint（S8–S10 / P1–P5）
的大量未提交修改（`backend/ai/*`、`backend/learning/**`、`backend/data_plane/*`、
`frontend/**`、若干 report 与 scratch 目录）。**P6 没有回退、重排或清理其中任何一项**，
下面列出的只是 P6 自己动的文件；像 `orchestrator.py` / `main.py` / `wrong_answers.py`
这类文件里，"P6 的改动"只占其 diff 的一小部分。

**修改**
* `backend/main.py`（注册 admin_ops 路由；两行）
* `backend/ai/orchestrator.py`（放行只在拒绝路径查询一次；过闸档位；结果/审计可选字段）
* `backend/usage/service.py`（`reserve_credits` 新增可选 `permission_tier`，仅用于权限判定）
* `backend/learning/records/producers.py`（`ai_called` 载荷新增可选 `entitlement_grant`）
* `backend/learning/deep_study.py`、`backend/learning/spaces/programming/agent.py`
  （既有前置检查改用同一"政策+放行"组合）
* `backend/routers/ai_models.py`（菜单与放行一致）
* 七个工作流入口加边界闸：`routers/deep_study.py`、`routers/programming_agent.py`、
  `routers/learning_report.py`、`routers/plan_adjustment.py`、`routers/wrong_answers.py`、
  `routers/review.py`、`routers/p4_adaptive_feedback.py`
* `docs/FRONTEND_API_CONTRACT.md`（新增 P6 DELTA 段）

**未改**：`MIGRATION_HEAD` = `20260919_0012`（本轮**零** schema 变更）、
`frontend/**`、`migrations/**`、`alembic.ini`、`backend/app.db`。
