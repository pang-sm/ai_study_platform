# STEP7CP_PROVIDER_MODEL_POOL_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7C-P 验收报告
> 范围：Provider Onboarding / Live Validation / Model Pool Calibration
> （含 REASONING RESERVATION HARDENING / COLLABORATION-ENDPOINT ISOLATION /
> NON_ARK_REASONING_BILLING_VALIDATION）
> 生成：2026-09-16 · FINAL_SIX_PROVIDER_RUN → HARDENING → NON_ARK_REASONING_FINAL
> 本轮为 IMPLEMENTATION（有代码变更，未 commit / 未 push）

---

## 1. EXECUTIVE VERDICT

```text
SIX_PROVIDER_MODEL_ACCESS        = PASS
PROVIDER_AWARE_RESERVATION       = PASS
REASONING_UNKNOWN_FAILS_CONSERVATIVE = PASS
REASONING_BUDGET_BYPASS          = NO
ADVANCED_WEEKLY_BUDGET_PROTECTED = PASS

DEEPSEEK_REASONING_BILLING_SAFE  = PASS
MINIMAX_REASONING_BILLING_SAFE   = PASS
GLM_REASONING_BILLING_SAFE       = PASS
KIMI_REASONING_BILLING_SAFE      = PASS
QWEN_REASONING_BILLING_SAFE      = PASS
ARK_REASONING_BILLING_SAFE       = PASS

DOUBAO_GENERAL_PRODUCTION_ELIGIBLE                = YES
DOUBAO_AGENT_COLLAB_ENDPOINT_PRODUCTION_ELIGIBLE  = NO
COLLAB_ENDPOINT_HIDDEN_FROM_PRODUCTION_MODEL_API  = PASS

FULL_BACKEND_TESTS = PASS（391 passed / 0 failed）

STEP7CP_FINAL_FROZEN = YES
STEP7D_READY         = YES
```

---

## 2. AUDIT CHAIN（五段历史逐段保留，不覆盖）

```text
[1] Doubao = AUTH_OK / NO_MODEL_ACCESS
    Ark 账户为 endpoint-id 模式：/models 返回 132 个目录模型，但 chat completion 报
    InvalidEndpointOrModel.NotFound（404）。

[2] Endpoint-ID configured → six provider connectivity
    控制台创建两个推理接入点；model_map wiring 完成；双 endpoint live smoke PASS；
    GENERAL_BENCHMARK doubao-general 6/6；AGENT_CAPABILITY_PROBE doubao-agent 3/3。

[3] reasoning reservation risk discovered → provider-aware reservation fixed
    实测 max_tokens=64 仍计费 completion=566（reasoning=520）→
    「max_tokens == 最大计费 completion」假设失效 → reserve 严重低估 → Usage Budget 正确性问题。
    修复 = ai/cost.py ModelCostPolicy（provider/model 级 reservation policy）。

[4] collaboration endpoint → production isolated
    zhixue-doubao-agent 带「协作奖励计划」标记 → 不承载真实学生私有学习数据 →
    deployment_eligibility = BENCHMARK_ONLY（生产 router 与 /ai/models 均不可见）。

[5] NON_ARK_REASONING_BILLING_VALIDATION → 第二个 UNBOUNDED provider（Qwen）被发现并修复
    [3] 的结论当时只覆盖 Ark；deepseek-v4-pro / MiniMax-M3 / glm-5 / kimi-k2.6 仍按
    「max_tokens_covers_reasoning=True」这一未实测假设处理。
    本轮逐模型 live 实测后：
      · 上述四个模型 + deepseek-flash / glm-5.3-flash / MiniMax-M2.7-highspeed = BOUNDED（证实）
      · qwen3.8-flash / qwen3.8-max = UNBOUNDED（新发现；max_tokens=64 实际计费
        completion 105/452 与 197/78）——且 qwen3.8-flash 是 FREE 档主模型
    修复 = 逐模型 reasoning_billing 登记 + UNVERIFIED 一律 fail conservative。

另有一次更早的更正记录（「误将 2/6 provider 写成 COMPLETE」→ STEP7CP_STATUS = PARTIAL），
同样保留，本报告不假装历史已完成。
```

---

## 3. GIT BASELINE

```text
HEAD = ebad5282（merge: reconcile local clean-slate frontend/governance with origin backend intelligence）
本轮未执行任何 git 写操作（NO commit / push / reset / clean / rebase）
```

---

## 4. SECRET / CONFIG SECURITY

```text
RAW_SECRET_IN_GIT           = NO
RAW_SECRET_IN_TRACKED_FILES = NO
RAW_SECRET_IN_REPORT        = NO（只输出 token 计数与 usage 结构，无 key、无 endpoint id）
ARK_API_KEY                 = 未修改
```

- endpoint id 仅存在于 `backend/.env.local`（`.gitignore:18` 确认忽略）。tracked 文件中**不存在**
  任何 `ep-` 推理接入点 id：以实际两个 id 的全量字符串分别 grep（`.py` / `.md` / `.json`）命中均为 **0**
  （本报告此处刻意不写出 id 片段，以免污染后续同名检索）。
- provider 指纹（SHA256 prefix-8，非 key）：deepseek=95a99062、qwen=30cbc775、doubao=597c6878、kimi=72a1e919、glm=b492f9cf、minimax=9cbada25。

---

## 5. A2 — ARK LIVE PARAMETER PROBE（只依据实测）

| 变体（max_tokens=64） | doubao-general completion / reasoning | doubao-agent completion / reasoning |
| --- | --- | --- |
| baseline | 516 / 488 | 1306 / 1268 |
| `thinking={"type":"disabled"}` | **38 / 0** | **48 / 0** |
| `thinking={"type":"enabled"}` | 1228 / 1198 | 1504 / 1465 |
| `thinking={"type":"auto"}` | 400 InvalidParameter | 400 InvalidParameter |
| `thinking.enabled + budget_tokens=32` | 1344 / **1308** | 1367 / **1338** |
| `reasoning_effort="minimal"` | 30 / 0 | 42 / 0 |

```text
THINKING_DISABLE_SUPPORTED  = YES
REASONING_LIMIT_SUPPORTED   = NO（budget_tokens 被接受后被忽略）
MAX_TOKENS_COVERS_REASONING = NO
USAGE_DETAIL                = YES（completion_tokens_details.reasoning_tokens 上报）
```

---

## 6. NON_ARK_REASONING_BILLING_VALIDATION（本轮主体）

**探针方法**：固定 prompt（进程/线程根本区别，≤50 字）、`max_tokens=64`、provider 默认
temperature（不传）、输入尽量一致；每个 provider 走其生产 base_url 与 canonical key，
原始 usage 逐字打印（无 key 输出）。SDK 命名与训练知识**不作为依据**。

### 6.1 逐模型结论

| provider / model | requested max_tokens | input | completion | reasoning | cached | total | finish | raw usage 语义 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek/deepseek-v4-pro | 64 | 100 | **64** | 64 | 0 | 164 | length | `completion_tokens_details.reasoning_tokens`；另有 `prompt_cache_hit/miss_tokens` |
| deepseek/deepseek-flash | 64 | 47 | **64** | 64 | 0 | 111 | length | 同上 |
| glm/glm-5 | 64 | 29 | **64** | 64 | 0 | 93 | length | 同上 |
| glm/glm-5.3-flash | 64 | 29 | **64** | 64 | 0 | 93 | length | 同上 |
| kimi/kimi-k2.6 | 64 | 24 | **64** | 63 | n/a | 88 | length | `prompt_tokens_details` 为 null → cached 未知 |
| minimax/MiniMax-M3 | 64 | 193 | **64** | 0 | 128 | — | length | thinking 以 `<think>…</think>` **内联在 content**，计入 completion |
| minimax/MiniMax-M2.7-highspeed | 64 | 58 | **64** | 未上报 | 未上报 | 122 | length | `completion_tokens_details` 为 null |
| **qwen/qwen3.8-flash** | 64 | 79 | **105 / 452** | 83 / 429 | 0 | 184 / 531 | stop | reasoning 计入 completion_tokens **之上** |
| **qwen/qwen3.8-max** | 64 | 79 | **197 / 78** | 174 / 52 | 0 | 276 / 157 | stop | 同上 |
| doubao/doubao-general | 64 | 56 | **516** | 488 | 0 | 572 | stop | 同 Ark（[3]） |
| doubao/doubao-agent | 64 | 56 | **1306** | 1268 | 0 | 1362 | stop | 同 Ark（[3]） |

MiniMax 追加验证（排除「completion 与 content 长度单位不一致」的可能）：
`MiniMax-M2.7-highspeed` 64→64（length）、512→453（stop）；`MiniMax-M3` 64→64（length）、
512→512（length）。completion_tokens 随 cap 缩放且从不超出。

### 6.2 判定

| model | MAX_TOKENS_COVERS_REASONING | THINKING_DEFAULT | REASONING_USAGE_REPORTED | RESERVATION_POLICY_SAFE |
| --- | --- | --- | --- | --- |
| deepseek-v4-pro | **YES** | ON（无开关） | YES | YES |
| deepseek-flash | **YES** | ON（无开关） | YES | YES |
| glm-5 | **YES** | ON（无开关） | YES | YES |
| glm-5.3-flash | **YES** | ON（无开关） | YES | YES |
| kimi-k2.6 | **YES** | ON（无开关） | YES | YES |
| MiniMax-M3 | **YES** | PROVIDER_CONTROLLED（内联） | NO（内联计入 content） | YES |
| MiniMax-M2.7-highspeed | **YES** | PROVIDER_CONTROLLED | NO（未上报） | YES |
| **qwen3.8-flash** | **NO** | ON（`enable_thinking` 可关） | YES | **修复后 YES** |
| **qwen3.8-max** | **NO** | ON（`enable_thinking` 可关） | YES | **修复后 YES** |
| doubao-general | NO | ON（可关，生产关） | YES | YES |
| doubao-agent | NO | ON（保留开） | YES | YES |

**BOUNDED 的判定依据（深/GLM/Kimi 类）**：completion_tokens 恰好 == max_tokens，
reasoning_tokens == completion_tokens，且 content 为空、finish_reason=length。三者合起来
只能解释为「completion_tokens 完全由 reasoning 构成、且被 max_tokens 截断」——
即 reasoning 确实被 max_tokens 覆盖，而不是「恰好 64」。

### 6.3 Qwen 修复方式 = OPTION B（不是 A）

Qwen 支持关闭 thinking（实测 `extra_body={"enable_thinking": False}` →
completion 15/21、无 reasoning 字段、有界），因此 §5 允许普通能力默认 thinking OFF。
但**实测该关闭会损失质量**，故未采用：

```text
gen-json-1（question.generate，json_valid 判定）
  qwen3.8-max   thinking OFF · max_tokens=200 → 0/3
  qwen3.8-max   thinking OFF · max_tokens=800 → 2/3
  qwen3.8-max   thinking ON  · max_tokens=200 → 3/3
  qwen3.8-max   thinking ON  · max_tokens=800 → 3/3
  qwen3.8-flash thinking ON  · 两种预算 → 3/3
  qwen3.8-flash thinking OFF → 独立复测 3/3，但在 6-case run 中失败 gen-json-1（1 次）
```

结论：**没有观测到「质量中性」的关闭配置**，因此不基于「其余 5 个 case 通过」把 Qwen
切换到 thinking OFF（那正是 §6 禁止的外推）。Qwen 采用 **OPTION B**：保留 thinking ON
（显式发 `enable_thinking=true`）+ model-specific conservative reserve。

`thinking_budget=0` 被服务端拒绝（must be a positive integer），故不存在「把 reasoning 调到 0」的第三条路。

---

## 7. RESERVATION POLICY（冻结形态）

`ai/cost.py::ModelCostPolicy` —— provider/model 级 CONFIG，非 SQL 表：

```text
reasoning_billing          NONE / BOUNDED / UNBOUNDED / UNVERIFIED
supports_thinking_control  provider 是否暴露 thinking 开关
reasoning_reserve_tokens   reasoning 可能溢出 max_tokens 时叠加的 conservative 预留
thinking_capabilities      thinking 默认关时，哪些 capability 单独开启
thinking_default_on        thinking 默认开（provider-controlled，可用开关重申）
```

```text
reservation_output_tokens = requested(或 capability 期望) + reserve_if_reasoning_can_escape

reasoning_can_escape =
    reasoning_billing != NONE
    AND NOT (thinking 开关存在 且 本次请求 thinking=off)
    AND reasoning_billing in {UNBOUNDED, UNVERIFIED}
```

- **`UNVERIFIED` 一律 fail conservative**：未注册模型（无实测证据）reservation 直接叠加
  conservative allowance，绝不按 0 reasoning 估算。
- `DEFAULT_REASONING_RESERVE_TOKENS = 2048`：取自最大实测样本（Ark 11 次 thinking-ON 采样
  397–1608 reasoning tokens，最大 1608）的 ≈1.27x。reasoning 无硬上界，故用保守上限而非计算值。
- `estimate_credits(..., capability=...)` 经同一 policy 计算 reserve；router 与 orchestrator
  均传入 capability → 预算判断口径统一。
- orchestrator 用**同一条 policy** 决定实际发送的 thinking 开关
  （`AIRequestSpec.thinking` 三态；QwenProvider → `enable_thinking`，ArkProvider → `thinking.type`）。
  **provider 专有参数只在 adapter 内出现**，endpoint 与业务层无 magic number。

冻结的 execution policy：

| provider | 开关 | 普通能力（tutor.chat / question.explain / material.qa / question.generate / programming.explain / programming.debug / planning.generate / report.generate） | reserve |
| --- | --- | --- | --- |
| deepseek | 无 | provider-controlled（ON） | 无（BOUNDED） |
| glm | 无 | provider-controlled（ON） | 无（BOUNDED） |
| kimi | 无 | provider-controlled（ON） | 无（BOUNDED） |
| minimax | 无 | provider-controlled（内联） | 无（BOUNDED） |
| qwen | `enable_thinking` | **ON**（质量实测要求） | +2048 |
| doubao-general | `thinking.type` | **OFF** | 无 |
| doubao-agent | `thinking.type` | OFF（programming.* 除外，且该 endpoint 非生产） | +2048（programming.*） |

未提前实现 `tutor.strong_reasoning` / advanced workflow 等新 capability API。

---

## 8. SETTLEMENT（actual vs reserve）

| 情形 | 行为 | 测试 |
| --- | --- | --- |
| actual < reserve | settle actual，释放差额，`reserved` 归零 | `test_actual_below_reservation_releases_difference` |
| actual == reserve | 精确结算 | `test_actual_equal_to_reservation_settles_exactly` |
| actual > reserve | **绝不静默**：`reconciliation_pending` + `error_category=reservation_overage`，不返回内容 | `test_actual_above_reservation_is_never_silently_absorbed` |

---

## 9. §7 — 逐模型 weekly budget 证明

四个 Advanced 模型各有一对测试（reserve 是上界 + budget gate 在 provider 调用前拒绝）：

```text
deepseek / deepseek-v4-pro   : reserve = max_tokens（BOUNDED，reasoning_reserved=0）
minimax  / MiniMax-M3        : 同上
glm      / glm-5             : 同上
kimi     / kimi-k2.6         : 同上

test_advanced_model_cannot_bypass_weekly_budget[4 模型]
  Advanced（无 daily cap）· weekly remaining 压到 1 credit → 请求被拒，
  provider factory 调用次数 == 0，router.budget_compatible == False

test_advanced_model_reservation_is_an_upper_bound[4 模型]
  证明 reserve >= 该模型最大可计费 completion 的成本（BOUNDED 下 = max_tokens 输出）

test_thinking_reserve_cannot_bypass_weekly_budget（Qwen/Doubao 型 UNBOUNDED）
  weekly remaining = 3；visible-only reserve = 1 credit（本可放行）；
  thinking-on reserve = 7 credits（> 3 → 拒绝）

test_weekly_budget_rejects_before_any_provider_call
  weekly remaining = 1 → 拒绝，provider 调用 0 次
```

```text
ADVANCED_WEEKLY_BUDGET_PROTECTED = PASS
REASONING_BUDGET_BYPASS          = NO
REASONING_UNKNOWN_FAILS_CONSERVATIVE = PASS
```

---

## 10. B — 协作奖励计划 PRODUCTION ISOLATION

**事实**：`zhixue-doubao-agent`（Doubao-Seed-Evolving）带「协作奖励计划」标记；火山方舟服务条款
说明该计划属普通「不使用提交内容训练基础模型」规则的**例外情形**。

```text
ai/pool.py deployment_eligibility（CONFIG，非 SQL 表）：
  PRODUCTION / INTERNAL_ONLY / BENCHMARK_ONLY

doubao-general → PRODUCTION     （smoke PASS · benchmark 6/6）
doubao-agent   → BENCHMARK_ONLY （collaboration reward endpoint）
其余全部条目   → PRODUCTION（默认）
```

- `qualified_models_for()` **默认只返回 PRODUCTION**；internal/benchmark 显式传
  `include_non_production=True`。生产 router / orchestrator / `/ai/models` 从不传。
- **禁止 Router normal production auto → doubao-agent**：默认过滤 + explicit 校验双重保证
  （`test_explicit_model_cannot_bypass_production_eligibility`）。
- **benchmark / internal 仍可用**：`run_agent_probe.py` / `run_calibration_benchmark.py`
  直接经 `default_provider_factory` 取 adapter，不经 pool。
- **B4**：未来另建**不含协作奖励计划**的 Seed-Evolving 接入点，重新 smoke/probe 后
  只需把 `deployment_eligibility` 改回 `PRODUCTION`，无需改 Ark adapter。
- **B5**：Doubao Provider 仍在 production model selection 中，由 `doubao-general` 代表。

条款取证状态：官方文档 `docs.volcengine.com/docs/82379/1391869` 正文为 SPA 渲染，
WebFetch ×3 + raw curl ×1 均只得空壳；WebSearch 仅命中论坛（非权威，未采信）；
`agent-browser` 未安装。故隔离策略**不依赖条款解读**——只要存在「训练例外」这一已知语义，
即按不承载真实学生数据处理；条款全文确认后可单向放开。

---

## 11. C — PRODUCTION POOL

```text
MODEL_POOL_VERSION = v4 / POOL_QUALIFICATION_LEVEL = FINAL
PRICING_REGISTRY_VERSION = v4
PRODUCTION_MODEL_POOL_VERSION = v4
PRODUCTION_PROVIDER_COUNT = 6
```

| Provider | Configured | Auth | Discovery | Smoke | Pricing | Qualified | Production |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | yes | PASS | 2 models | PASS | VERIFIED | YES | YES |
| qwen | yes | PASS | 252 models | PASS | VERIFIED | YES | YES |
| doubao | yes | PASS | 133 models | PASS | VERIFIED | YES | YES（doubao-general） |
| kimi | yes | PASS | 2 models | PASS | VERIFIED | YES | YES |
| glm | yes | PASS | 10 models | PASS | VERIFIED | YES | YES |
| minimax | yes | PASS | 8 models | PASS | CEILING | YES | YES |

```text
FREE (3)     : qwen3.8-flash · glm-5.3-flash · deepseek-flash
STANDARD (5) : + qwen3.8-max · MiniMax-M2.7-highspeed
ADVANCED (10): + deepseek-v4-pro · MiniMax-M3 · glm-5 · kimi-k2.6 · doubao-general
```

`doubao-agent` 不在生产池（BENCHMARK_ONLY），仍在 `QUALIFIED_POOL` 供 internal 使用。
未为「六家齐全」降低 capability quality gate；Doubao 入池依据是 6/6，不是供应商数量要求。

---

## 12. D — /ai/models 验收

```text
FULL_REGISTRY_USER_VISIBLE = NO
COLLAB_ENDPOINT_HIDDEN_FROM_PRODUCTION_MODEL_API = PASS
```

| capability (advanced) | n | providers | doubao-general | doubao-agent |
| --- | --- | --- | --- | --- |
| tutor.chat | 6 | 5 | 可见 | 隐藏 |
| question.explain | 8 | 5 | 可见 | 隐藏 |
| material.qa | 6 | 5 | 可见 | 隐藏 |
| question.generate | 8 | 5 | 可见 | 隐藏 |
| programming.debug | 8 | 6 | 可见 | **隐藏** |
| programming.explain | 6 | 5 | 可见 | **隐藏** |
| planning.generate | 7 | 5 | 未声称 | 隐藏 |
| report.generate | 4 | 4 | 未声称 | 隐藏 |

Free / Standard 均不含任何 Doubao 条目（advanced-only）。

---

## 13. TESTS

```text
TARGETED_TESTS     = PASS
FULL_BACKEND_TESTS = PASS（391 passed / 0 failed / 185.77s）
PY_COMPILE         = OK
```

`backend/tests/test_reservation_policy.py`（39 项）覆盖：

```text
ordinary non-thinking estimate / 未注册模型 fail-conservative（含「不得按 0 reasoning 估算」）
thinking-model conservative estimate / reserve 严格大于 visible-only
conservative reserve 覆盖 Ark 实测最坏样本（64 请求 / 1504 计费）
conservative reserve 覆盖 Qwen 实测溢出（64 请求 / 452 计费）
BOUNDED 参数化（7 个模型：completion <= max_tokens、reserve == max_tokens、不发送开关）
Qwen UNBOUNDED + thinking_default_on + reserve 生效
每个生产池模型必须已有实测 verdict（禁止依赖 fail-conservative 默认值碰巧安全）
doubao-general 生产 thinking OFF；doubao-agent programming.* 保留 thinking + reserve
Ark thinking budget 参数未被依赖（回归守卫）
orchestrator 实际发送 policy 的 thinking 开关 / 无开关 provider 不发送该参数
reserve > actual → release；actual == reserve → exact；actual > reserve → reservation_overage
§7 四模型 cannot bypass weekly budget + reservation 是上界
Advanced 无 daily cap / weekly 受保护
```

`test_provider_adapters.py` 新增：Qwen `enable_thinking` 映射、未指定时不发开关（Qwen / Ark）。
`test_pricing_pool_router.py` / `test_ai_models_api.py`：生产池排除内部 endpoint、internal 可达、
生产候选覆盖 6 provider、eligibility 元数据、explicit 不可绕过、协作 endpoint 全 capability 隐藏。

live probe 独立执行，普通 pytest **不调用真实 provider**。

---

## 14. RISK / 后续 hardening 项（不阻断 STEP7CP）

1. **Qwen reserve 是保守上界而非精确值。** 实测溢出为 105–452 tokens（max_tokens=64 时）；
   在更大 max_tokens 下 reasoning 可能更长，2048 未必永远覆盖。已有
   `reservation_overage` 异常通道兜底；若生产观测到该异常频率上升，应提高
   `DEFAULT_REASONING_RESERVE_TOKENS`，而非放宽异常通道。

2. **`max_tokens=None` 时的预留口径**（既有行为，本轮未改）：orchestrator 在调用方不传
   `max_tokens` 时按 `DEFAULT_MAX_TOKENS=2000` 预留，但发给 provider 的 `max_tokens` 仍为
   未设置 → provider 用自身默认上限。若该默认上限 > 2000，存在同族低估。建议后续把
   二者统一（或对无 `max_tokens` 的请求显式使用同一上界）。**本轮未改动**，以免影响
   已验证行为。

3. **MiniMax reasoning 未上报**：M2.7-highspeed 的 `completion_tokens_details` 为 null，
   M3 的 thinking 内联在 content。二者 billable output 均等于 completion_tokens 且被
   max_tokens 封顶，故安全；但「reasoning 占比」不可观测，无法据此做质量分析。

4. **协作奖励计划条款全文未获取**（§10）。当前策略保守（隔离），条款确认后可单向放开。

---

## 15. 变更文件清单

```text
本轮（NON_ARK_REASONING_BILLING_VALIDATION）
backend/ai/cost.py                         reasoning_billing 四态 + thinking_default_on
                                           + 逐模型实测登记 + UNVERIFIED fail-conservative
backend/ai/providers/qwen.py               enable_thinking 开关映射
backend/tests/test_reservation_policy.py   BOUNDED 参数化 / Qwen / fail-conservative /
                                           §7 四模型 budget 证明 / 生产池 verdict 完整性
backend/tests/test_provider_adapters.py    Qwen 与 Ark 的 thinking 开关映射与「不发送」
ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md         §73 审计链 [5] + 判定 + 质量措辞更正

上一轮（REASONING RESERVATION HARDENING）—— 保留
backend/ai/cost.py / ai/pool.py / ai/router.py / ai/orchestrator.py
backend/ai/gateway/__init__.py / ai/providers/ark.py / usage/service.py
scripts/run_calibration_benchmark.py

更早（PROVIDER ONBOARDING）—— 保留
backend/ai/secrets.py / ai/pricing.py / ai/benchmark.py / ai/providers/ark.py
scripts/verify_ai_providers.py / scripts/configure_ai_provider_secrets.py
scripts/run_agent_probe.py
```

`backend/app.db` 未改；无 schema 变更；**不需要迁移**（HEAD 仍为 `20260915_0002`）。

---

## 16. FINAL VERDICT

```text
DEEPSEEK_REASONING_BILLING_SAFE = PASS（BOUNDED，实测证实）
MINIMAX_REASONING_BILLING_SAFE  = PASS（BOUNDED，实测证实）
GLM_REASONING_BILLING_SAFE      = PASS（BOUNDED，实测证实）
KIMI_REASONING_BILLING_SAFE     = PASS（BOUNDED，实测证实）
QWEN_REASONING_BILLING_SAFE     = PASS（UNBOUNDED → OPTION B：thinking ON + reserve）
ARK_REASONING_BILLING_SAFE      = PASS（UNBOUNDED → thinking OFF / reserve）

ADVANCED_WEEKLY_BUDGET_PROTECTED     = PASS
REASONING_UNKNOWN_FAILS_CONSERVATIVE = PASS
REASONING_BUDGET_BYPASS              = NO
PROVIDER_AWARE_RESERVATION           = PASS

SIX_PROVIDER_MODEL_ACCESS = PASS
DOUBAO_GENERAL_PRODUCTION_ELIGIBLE                = YES
DOUBAO_AGENT_COLLAB_ENDPOINT_PRODUCTION_ELIGIBLE  = NO
COLLAB_ENDPOINT_HIDDEN_FROM_PRODUCTION_MODEL_API  = PASS

MODEL_POOL_VERSION            = v4
PRODUCTION_MODEL_POOL_VERSION = v4
PRODUCTION_PROVIDER_COUNT     = 6

FULL_REGISTRY_USER_VISIBLE = NO
RAW_SECRET_IN_GIT = NO / ENDPOINT_ID_IN_SOURCE = NO
FULL_BACKEND_TESTS = PASS（391 passed / 0 failed）
MIGRATION_REQUIRED = NO

STEP7CP_FINAL_FROZEN = YES
STEP7D_READY         = YES
```

`BLOCKERS = 无阻断项。残留项（见 §14）：Qwen reserve 为保守上界而非精确值；max_tokens=None 时的预留口径为既有行为未在本轮改动；MiniMax reasoning 占比不可观测；协作奖励计划条款全文未获取。`
