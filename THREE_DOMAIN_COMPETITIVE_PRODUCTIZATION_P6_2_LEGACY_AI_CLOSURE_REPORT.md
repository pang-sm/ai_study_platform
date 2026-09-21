# THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6.2 — LEGACY AI CLOSURE

> 窄范围 closure：只处理 P6.1 已确认的 3 个 blocker（`/chat` 编程分支绕过、challenge submit
> 绕过、`/code/diagnose` 语义误标），外加 §D 的守卫扩充。**未新增学习功能，未改 frontend
> 源码，未改 migration，未 commit / push / deploy，未 reset / clean / restore / stash。**

---

## PROGRAMMING_CHAT_UNIFIED = **YES（三个分支全部在统一链路上）**

`POST /chat` 的分支判定顺序与语义**未变**（exam → programming → else course），变的只是
programming 分支的执行体：它此前是 `check_programming_usage_limit` + `call_deepseek` +
`record_ai_usage`，因此**没有 `ai_requests` 行、没有能力/权限/预算决定、没有可反馈的身份**
（P6.1 只能如实返回 `request_id: null`）。现在它是统一链路上的一次普通请求：

```
Capability → Permission → Usage reserve → Router → Gateway → settle → ai_requests
```

* **能力**：与 course 分支同一条服务端规则 `material.qa`（有引用资料）/ `tutor.chat`（无）——
  客户端依旧不能自己指定能力，因此也不能绕过权限（B11 未被削弱）。
* **适配器**：`learning.spaces.programming.ai.execute_programming_ai`（programming 空间**唯一**的
  AI 门），携带 canonical `LearningContext(service_namespace=programming)`。
  **没有建立 programming-specific AI stack**，没有第二套 orchestrator / gateway / 计费。
* **语言**：取**学习者自己声明的语言**（`programming.service.declared_languages`，即同一份已被
  注入 prompt 的画像）；未声明时用 context 模块的既定默认值。**不从课程显示名猜语言**。
* **行为与契约**：响应原有字段一个不删（`answer` / `references` / `assistant_message_id` /
  `user_message_id` / `branch_id` / `root_message_id` / `version_index` / `session` /
  `rag_sources`），`request_id` 现在是**真实 id**。
* **授权变化（如实报告）**：不再问 legacy 每日配额；由统一 `Subscription → Capability
  Permission → Usage Budget` 决定。因为所选能力属于 **Free 学习闭环**，**Free 档位在本分支
  的可用性没有下降**（这与 P6.1 对 `/code/analyze` 编程分支的收敛后果不同——那条支线请求的是
  `programming.explain`，属 Standard+）。

---

## CODE_CHALLENGE_AI_UNIFIED = **YES（真模型调用统一；确定性判定保持确定性）**

`POST /code/challenges/{challenge_id}/submit` 有**三条真实分支**，本轮按"只有真正需要 AI 的
部分进入统一 Orchestrator"处理：

| 分支 | 触发条件 | 是否需要模型 | 现在 |
|---|---|---|---|
| 无代码 | `code` 为空 | **否** | 保持确定性：固定文案判定，**不建任何 request**，`request_id: null` |
| 语言不符 | 提交语言 ≠ 题目语言 | **否** | 同上 |
| 真实判定 | 其余情况 | **是** | `execute_programming_ai(capability='programming.explain')`，一条 capability + 一次 reserve + 一次 settle + 一行 `ai_requests` |

* **能力选择（决定，非默认）**：`programming.explain`——该端点的产物是"对照题目要求分析学习者
  代码"，与 `/code/analyze` 同一产品动作，且它是编程空间自己的代码分析能力。
  备选 `answer.grade`（语义为"按参考答案评分"）被否决：它当前是考研主观题评分器的能力，
  语义属考试空间，且两者**同为 Standard+**，因此这个选择不产生任何档位差异。
* **未传 `exercise_id`**：`code_challenges.id` **不是** `programming_exercises.id`。把 challenge id
  塞进 context 会让事实挂到学习者从未做过的练习上——宁可留空，不伪造身份。
* **响应契约**：原有 `success` / `status` / `ai_feedback` / `attempt_id` 全部保留，`status` 仍从
  模型回答里读判定词（`大概率通过` 等）；**新增** `request_id`（AI 分支为真实 id，确定性分支
  为 `null`）。前端当前没有任何组件调用该端点（只有生成类型文件提到它），新增字段是 additive。
* **授权变化（如实报告）**：与 `/code/analyze` 同规则，legacy `check_programming_usage_limit`
  不再投票；`programming.explain` 属 Standard+，**Free 档位在该分支会得到 403**——这是统一化的
  既定后果，不是回归。

---

## CODE_DIAGNOSE_SEMANTICS_CORRECTED = **YES（语义订正，实现一行未改）**

`/code/diagnose` 是**确定性静态诊断**：C 走容器内 `gcc -fsyntax-only`，Python 走
`sys.executable -m py_compile`，其它语言直接 `unsupported`。**它不在这条 AI 链路上**，因此：

| 项目 | 事实 |
|---|---|
| AI request_id | **不返回**（字段不存在，不是 `null`）；没有 `ai_requests` 行可指 |
| AI feedback | **不适用**：没有 AI 产物可评分 |
| AI credits | **不消耗**：`usage_ledger` 零变化（测试持有） |
| 实现 | **未改**（仍是编译器诊断；行号/列号是编译器的真实位置） |

订正的内容（**文档与 frontend-facing 元数据**，不涉及行为）：

* `backend/main.py` `diagnose_code` docstring 改写为显式契约（OpenAPI description 直接来自它）：
  产品语义写明为"代码诊断（静态语法检查）"，并逐条列出"无 `ai_requests` 行 / 无 `request_id` /
  不受 capability-budget 约束 / 无 AI credits / 无可反馈产物"，同时指向真正的 AI 端点
  （`/code/analyze`、`/programming/agent/debug`）与**不收敛的理由**（收敛＝用模型的描述替代
  编译器的判定，并让语法检查在模型不可用时失效，违反 `NO MODEL → PRODUCT STILL WORKS`）。
* `docs/FRONTEND_API_CONTRACT.md`：`AI 诊断` → `代码诊断（静态语法检查，**非 AI**…）`；
  并把 `/code/diagnose` 从"编程 AI"清单移入**新增的"编程确定性能力"清单**
  （`/code/diagnose`、`/code/execute`、`/code/challenges/{id}/run-tests`）。
* 全仓已无 `AI 诊断` / `AI Diagnose` 类误标（grep 实测为空）。

**未做（越界项，如实说明）**：前端 `programming.ts` 仍把 `useCodeCoach('debug')` 映射到
`/code/diagnose` —— 那是**前端源码修改**，本轮明令禁止；语义错配本身已在 P6.1 记录，处置属
前端阶段（改用 `/code/analyze` 或 debug agent，或把该按钮明确为"编译检查"）。

---

## DIRECT_PROVIDER_BYPASSES_REMAINING = **8（已声明，全部有守卫）**

P6.1 的两个 blocker 已归零：`chat`、`submit_code_challenge` **不再是** `call_deepseek` 的调用点。
实测（AST 扫描 `main.py`，非记忆）：

| 剩余调用点 | 所属产品面 | 归属 |
|---|---|---|
| `generate_code_challenge` | `POST /code/challenges/generate` | programming |
| `_repair_generated_challenge_with_ai` | 同上（题目修复） | programming |
| `explain_challenge_failure` | `POST /code/challenges/{id}/explain-failure` | programming |
| `generate_challenge_tests` | `POST /code/challenges/{id}/generate-tests` | programming |
| `generate_learning_diagnosis` | `POST /code/learning-diagnosis` | programming |
| `structure_practice_paper_text` | 无 db/user context 的 legacy 路径 | 非课程 legacy |
| `refine_question_analysis_with_ai` | 非 course / 非 exam 的 `service_key` 分支 | 非课程 legacy |
| `_repair_json_with_ai` | 同上 | 非课程 legacy |

共 **8 个函数 / 8 个调用点**，与守卫声明表 `NON_COURSE_DIRECT_CALLS` **逐一对应、无未声明项、
无过期声明**（守卫双向断言）。这 4 个编程端点是**下一轮同类收敛对象**，本轮按"禁止扩大范围"
未处理——若一并收敛，会把它们的授权从 legacy 配额改为 `Standard+` 能力，属产品政策变更。

---

## 架构守卫扩充（§D）

`tests/test_course_ai_reachability.py` 新增"CLOSED 产品路径"声明与三条可执行断言：

* `CLOSED_ENDPOINTS`（main.py 端点 → 必须到达的统一边界）：
  `chat`（course/exam/programming 三入口）、`analyze_code`、`submit_code_challenge`；
* `CLOSED_MODULES`（模块 → 产品面）：`learning/deep_study.py`（Deep Study）、
  `learning/report.py`（Report）、`learning/wrong_analysis.py`（Wrong Analysis）、
  `learning/plan_adjustment.py`（Plan Adjustment）、
  `learning/spaces/programming/agent.py`（Debug Agent）；
* 断言：**每条路径既必须到达统一边界，又必须无法自行触达 provider** ——
  禁止 `call_deepseek` / `OpenAI(` / `AsyncOpenAI` / `chat.completions.*`，以及
  `import openai` / `ai.providers.*` 导入。**判定读 AST 而非文本**，所以注释里提到 legacy
  客户端既不会误报、也无法掩护真实调用。
* **允许** Gateway / Provider layer 自身调用 provider（`ai/providers/*`），以及 `main.py` 中
  **已声明**的 legacy 调用点。
* 双向声明检查照旧：新出现一个 provider 调用点，或某条已声明调用点消失，守卫都会失败。

**守卫非空洞，已实测**：同一判定函数对仍开放的 `explain_challenge_failure` 实测返回
`line 15022: calls call_deepseek`，对三条 CLOSED 端点实测返回空。

---

## TESTS

**新增 `backend/tests/test_p6_2_legacy_ai_closure.py`（7 条）**：

| 测试 | 持有的事实 |
|---|---|
| `test_programming_chat_runs_on_the_unified_stack_and_returns_a_real_id` | 编程问答产生**真实** `ai_requests` 行（capability / `service_namespace=programming` / tier=free / status=settled，**回表核对**）；`usage_ledger` 有 reserve + settle；响应返回真实 `request_id`；legacy `ai_usage_logs` 计数不增；`/ai/feedback` 对该 id 返回 200 |
| `test_programming_chat_carries_the_learners_declared_language` | 声明 `cpp` 的学习者 → `context_json.programming_language == "C++"` |
| `test_challenge_submit_ai_branch_runs_on_the_orchestrator` | AI 分支回表为 `programming.explain` / programming / settled；reserve + settle；`status` 仍从模型回答读出；`ai_feedback` 归一化未变；真实 `request_id` 可反馈 |
| `test_challenge_submit_deterministic_branches_make_no_ai_call` | 空代码 / 语言不符：provider **零调用**、`ai_requests` / `usage_ledger` / legacy 表**全零变化**、`request_id is None`（字段存在但**不伪造**） |
| `test_code_diagnose_creates_zero_ai_requests_and_zero_credits` | diagnose：`ai_requests` 0 行、credits 0 变化、响应**无** `request_id` 字段 |
| `test_code_analyze_still_returns_a_real_owned_request_id` | P6.1 的收敛未被本轮扰动（回归） |
| `test_closed_product_paths_report_zero_forbidden_bypasses` | §D 8 条路径的禁区绕过数 = **0**（枚举完整 + 违规清单为空） |

**守卫与邻近契约套件（实测）**：`test_course_ai_reachability.py`（9 passed）、
`test_p6_1_ai_request_identity.py` + `test_exam_ai_orchestrator.py` + `test_gateway_migration.py` +
`test_course_ai_migration.py` + `test_cross_user_access.py` + `test_course_exam_scope.py`
（**70 passed**）。

**契约指纹未漂移（实测，非声明）**：重跑 `freeze_advanced_api_contract.collect()` →
`entries=21 missing=0 surface=572d9e68c9bc5138`，与 P6 冻结值**完全一致**，逐条 (method, path)
指纹 diff 为空。（P6.2 只改了 CLOSED 端点与 `/code/diagnose` 的 docstring；后者不在
FROZEN_SURFACE 内，前者本就不在其中。）

## FULL_SUITE

**最终实测：`1765 passed, 2 skipped in 860.54s (0:14:20)`，exit 0，零失败零错误。**

与 P6.1 的 `1755 passed, 2 skipped` 相比 **+10**，恰好等于本轮的净新增测试
（`test_p6_2_legacy_ai_closure.py` 7 条 + 守卫新增 3 条），**没有既有测试被跳过、删除或改写为
通过**。（运行时长本次为 14:20，P6.1 记录为 30:18；同一套件两次运行的机器负载差异，
不作为结论。）

---

## MAIN_DB_TOUCHED = **NO**

`backend/app.db` 全程未被打开：测试由 `conftest.py` **强制**把 `DATABASE_URL` 指向
`tempfile.mkdtemp()` 下的临时库（调用方传入的值也会被它覆盖）；契约指纹复核脚本同样显式写入
临时目录；未跑 Alembic，未执行任何 DDL/DML。

| 时点 | sha256 | size | mtime |
|---|---|---|---|
| before | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |
| after | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` | 64917504 | 1789877022 |

**OS temp 中的 harness 残留（如实区分归属）**：`%TEMP%` 下有 **1 个** `zhixue-e2e-*` 目录，
经进程树核对（`Win32_Process`）属于**另一个运行时**在 21:38:39 启动、**当前仍在运行**的
`scripts/e2e_harness.py --json`（父进程为 `C:\Users\26477\.cache\codex-runtimes\...\pwsh.exe`），
**不是本轮产物，已保持原样、未杀进程、未删目录**。本轮 full suite 内运行的
`test_p6_1_e2e_harness.py`（含 `test_shutdown_removes_the_temp_directory`）**全绿**，
即它自己的临时目录被正常删除——本轮 net 新增残留 = **0**。

---

## BACKEND_AI_ARCHITECTURE_FROZEN_READY = **YES（就本轮 3 个 blocker 而言）**

| 判据 | 状态 |
|---|---|
| 三个正式编程 AI 入口（chat / analyze / challenge 判定）全部走统一链 | ✅ |
| 真实 `ai_requests` 身份 + 可反馈 | ✅（回表核对 + feedback 200） |
| 确定性能力**没有**为了"统一"而变成模型调用 | ✅（diagnose、challenge 确定性分支、run-tests、execute） |
| provider 只被 Gateway / Provider layer 直接触达 | ✅（其余 8 处是**已声明**的 legacy 开放点） |
| 守卫可执行、非空洞、双向 | ✅ |
| 契约指纹未漂移 | ✅ `572d9e68c9bc5138` |

---

## BLOCKERS

1. **4 个编程端点仍是 legacy 直连**（`/code/challenges/generate`、
   `{id}/explain-failure`、`{id}/generate-tests`、`/code/learning-diagnosis`）——已声明、有守卫、
   本轮明确不扩大范围。收敛它们的**唯一**真实决策点是能力等级：沿用 `programming.explain`
   即 Free→403（与 `/code/analyze` 一致），若产品希望 Free 保留，需要的是能力政策决定
   （`usage/capabilities.py`），不是恢复 legacy 配额。
2. **3 个非课程 legacy 分支**（`structure_practice_paper_text`、`refine_question_analysis_with_ai`、
   `_repair_json_with_ai`）走的是"无 db/user context"或"其它 service_key"路径，收敛需要先有
   归属空间的 context，属结构性工作。
3. **`/code/diagnose` 的前后端语义错配仍在前端侧**：后端契约已订正（C），前端
   `useCodeCoach('debug')` 的映射要等前端阶段改（本轮禁止 frontend 源码修改）。
4. **`ai:generate` 未重跑**：docstring 改动会进入 OpenAPI description，`frontend/src/types/api.ts`
   属生成文件且是 frontend 路径，本轮禁改；前端阶段跑一次 `npm run api:generate` 即对齐。
5. **Debug Agent 顶层 feedback identity 仍是 BLOCKED**（P6.1 结论，需 parent/child accounting
   的产品决定），本轮未触碰。
6. **P6.1 的 harness / Playwright 接入**仍待前端阶段（后端侧已就绪）。

---

## 改动文件

**新增**

* `backend/tests/test_p6_2_legacy_ai_closure.py`
* `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_2_LEGACY_AI_CLOSURE_REPORT.md`（本文件）

**修改**

* `backend/main.py`
  * `/chat`：编程分支收敛到 `execute_programming_ai`（capability `material.qa`/`tutor.chat`、
    programming `LearningContext`、学习者声明语言）；移除该分支的 legacy 配额检查与
    `record_ai_usage`；三分支结构改为与 `/code/analyze` 一致的 exam / programming / else；
    `request_id` 现为真实 id。
  * `submit_code_challenge`：AI 分支收敛到 `execute_programming_ai`（`programming.explain`）；
    两条确定性分支保持确定性；响应 additive 增加 `request_id`。
  * `diagnose_code`：docstring 订正为显式确定性契约（**实现零改动**）。
* `backend/tests/test_course_ai_reachability.py`：从 `NON_COURSE_DIRECT_CALLS` 删除
  `chat` 与 `submit_code_challenge`（守卫要求撤销过期声明）；新增 §D 的 CLOSED 路径声明 +
  3 条 AST 断言。
* `docs/FRONTEND_API_CONTRACT.md`：`/code/diagnose` 去 AI 误标并移入确定性清单；
  `/chat` 与 `/code/challenges/{id}/submit` 的 `request_id` 契约补记。

**未改**：`frontend/**`、`migrations/**`、`alembic.ini`、任何 schema、`backend/app.db`、
`docs/UI_DESIGN_SPEC.md`、SSOT。
