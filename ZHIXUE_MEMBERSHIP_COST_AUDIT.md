# ZHIXUE_MEMBERSHIP_COST_AUDIT

**一次只读成本审计，2026-09-21。** 范围：真实 model provider 成本、capability routing、daily/weekly 预算、
Standard / Advanced 的预期成本，以及 payment / order 后端的真实能力。

> **权威层级**：本文件是**审计报告**，不是产品事实来源。唯一 SSOT 是
> `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。本文件中的每一个数字都注明代码出处；与 SSOT 冲突时以 SSOT 为准。
> 本文件**只记录事实与建议**，没有改价、没有改预算。

---

## 0. 结论摘要

| 项 | 事实 |
|---|---|
| 当前 Standard 售价 | **¥29.00 / 30 天**（`backend/usage/service.py` `UNIFIED_PLAN_PRICING`） |
| 当前 Advanced 售价 | **¥149.00 / 30 天**（同上） |
| Credit 口径 | `1 credit = ¥0.01 provider cost`（`backend/usage/service.py:35`，`backend/ai/cost.py:16`） |
| Standard 预算上限 | 每日 1,000 credits / 每周 5,000 credits |
| Advanced 预算上限 | 每日不限 / 每周 20,000 credits |
| **满额度时的 provider 成本** | Standard ≈ **¥217 / 月**、Advanced ≈ **¥869 / 月** |
| **即：售价低于成本上限** | Standard 差 **¥188**（7.5×）、Advanced 差 **¥720**（5.8×） |
| 支付后端 | **只有 mock**；生产拒绝 mock，**没有任何真实收款能力** |
| 兑换码 | 真实存在，但**只能由管理员生成** |

**核心发现：当前的 daily / weekly 预算不是价格，是额度许可。** 它允许的 provider 支出远超售价所能覆盖的量。
在真实支付接入之前，这不是立即的现金损失（因为收不到钱），但一旦接入支付，就是每卖一份亏一份的结构。

---

## 1. 真实 Provider 成本

出处：`backend/ai/pricing.py`（`PRICING_VERSION = "v4"`，`USD_CNY = 7.2`）。
单位：**CNY / 1M tokens**，格式 `input / cached-input / output`（off-peak；peak 见括号）。

| model id | input | cached | output |
|---|---|---|---|
| `deepseek-flash` | 1.08（peak 2.16） | 0.0216 | 4.32（peak 8.64） |
| `deepseek-v4-pro` | 4.752（peak 9.504） | 0.1584 | 14.256（peak 28.512） |
| `qwen3.8-flash` | 0.80 | 0.10 | 2.70 |
| `qwen3.8-max` | 12.00 | 1.50 | 36.00 |
| `kimi-k2.6` | 6.84 | 1.152 | 28.80 |
| `kimi-k2.7-code` | 6.84 | 1.368 | 28.80 |
| `glm-5.3-flash` | 0.80 | 0 | 2.80 |
| `glm-5.3` | 8.00 | — | 28.00 |
| `glm-5` | 4.00 | — | 18.00 |
| `doubao-general` | 6.00 | 1.20 | 30.00 |
| `doubao-agent` | 6.00 | 1.20 | 30.00（**BENCHMARK_ONLY**，不参与路由） |
| `minimax-m3` | 6.00 | — | 30.00（`CONSERVATIVE_CEILING`，未核实） |
| `minimax-m2.7-highspeed` | 1.00 | — | 5.00（同上） |

Provider adapters：`backend/ai/providers/` = deepseek / qwen / ark / moonshot / zhipu / minimax / fake。

### 1.1 Credit 怎么算

`backend/ai/cost.py:205-209`：

```
credits = max(1, round(provider_cost_cny / 0.01))
```

**`max(1, …)` 是一个对成本有实质影响的下限**：任何一次调用，哪怕 provider 成本只有 ¥0.0003，
也记作 **1 credit = ¥0.01**。小额调用因此被系统性高估——这是保守的（对平台有利），
但它同时意味着「credits 数」不等于「provider 成本」，审计两者的关系时必须分开看。

---

## 2. Capability routing

- **Qualified Model Pool**：`backend/ai/pool.py` `QUALIFIED_POOL`，每个 model 声明
  `eligible_tiers` + `capabilities`；`doubao-agent` = `BENCHMARK_ONLY`，不参与生产路由。
- **Router**：`backend/ai/router.py`（`router_v1`）`select_model` —— **cheapest-first + health**。
- **Business 层只声明 capability**（`tutor.chat` / `question.explain` / `programming.debug` …），
  不知道 model 名；provider adapter 是唯一允许出现 provider 名的地方。
- **Reasoning 预留**：`DEFAULT_REASONING_RESERVE_TOKENS = 2048`（`backend/ai/cost.py:67`），
  `ai/cost.py:121-187` 的 reasoning reserve policy。

### 2.1 单次调用成本量级（按 router 会选中的最便宜合格模型估算）

假设 `deepseek-flash`（最便宜的一档）：

| 场景 | in tokens | out tokens | provider 成本 | credits |
|---|---|---|---|---|
| 普通课程问答 / 学习对话 | 2,000 | 500 | ¥0.0022 + ¥0.0022 = **¥0.0043** | 1（被 `max(1,…)` 抬到 1） |
| 题面讲解 | 1,500 | 700 | ¥0.0016 + ¥0.0030 = **¥0.0046** | 1 |
| 生成练习题（长输出） | 1,500 | 3,000 | ¥0.0016 + ¥0.0130 = **¥0.0146** | 1（round(1.46)=1） |
| 生成学习报告 | 8,000 | 2,500 | ¥0.0086 + ¥0.0108 = **¥0.0194** | 2 |

假设 `deepseek-v4-pro`（深度思考 / strong reasoning 会走到更强的一档）：

| 场景 | in tokens | out tokens | provider 成本 | credits |
|---|---|---|---|---|
| 深度思考（含 2,048 reasoning reserve，检索资料 ~10k） | 12,000 | 2,500 | ¥0.0570 + ¥0.0356 = **¥0.0926** | 9 |
| Debug Agent（多步，约 5 次调用） | 25,000 | 6,000 | ¥0.1188 + ¥0.0855 = **¥0.2043** | 20 |

> **这是量级估算，不是实测。** 真实平均 token 数必须从 `ai_requests` + `ai_cost_records`
> 的 `actual_credits` 汇总得到；本次审计**没有**读生产库，因此不给「实测平均」这种数字。

---

## 3. Daily / Weekly 预算（现状）

出处：`backend/usage/service.py:49-50`。

| tier | daily credits | weekly credits | daily ¥ 上限 | weekly ¥ 上限 |
|---|---|---|---|---|
| free | 100 | 500 | ¥1.00 | ¥5.00 |
| standard | 1,000 | 5,000 | ¥10.00 | ¥50.00 |
| advanced | **无上限** | 20,000 | — | ¥200.00 |

### 3.1 满额度时的一个月 provider 成本

一个月按 30 天计；weekly 生效周期按 30/7 = **4.29 周**。

| tier | 约束 | 月 credits 上限 | **月 provider 成本上限** | 售价 | 差额 |
|---|---|---|---|---|---|
| free | weekly 500 × 4.29 = 2,145 | 2,145 | **¥21.45** | ¥0 | −¥21.45 |
| standard | min(1,000×30, 5,000×4.29) = min(30,000, 21,450) | 21,450 | **¥214.50** | ¥29.00 | **−¥185.50** |
| advanced | weekly 20,000 × 4.29 | 85,800 | **¥858.00** | ¥149.00 | **−¥709.00** |

**读法**：这不是「平台每月亏这些钱」——绝大多数学习者用不到上限。它说的是
**「一个学习者如果真用满额度，平台最多亏多少」**。这个数字必须小于售价，否则额度就不是风控，
而是补贴承诺。

---

## 4. 建议

### 4.1 建议月价（回答「根据真实成本给出建议月价」）

按 **售价 ≥ 3 × 预期 provider 成本** 定价（3× 覆盖基础设施、支付手续费、退款与波动）。
「预期用量」显式假设如下，全部按 §2.1 的单次成本推算：

- **Standard 典型用量**：每天 20 次普通问答 + 每周 2 次深度思考
  → 600 + 8.6×9 = **677 credits ≈ ¥6.8 / 月**
- **Advanced 典型用量**：每天 60 次普通问答 + 每周 6 次深度思考 + 每周 4 次 Debug Agent
  → 1,800 + 25.7×9 + 17.2×20 = **2,376 credits ≈ ¥23.8 / 月**

| tier | 预期月度 provider 成本 | 3× 目标 | **建议月价** | 当前价 |
|---|---|---|---|---|
| Standard | ≈ ¥6.8 | ≈ ¥20.4 | **¥29**（维持） | ¥29 |
| Advanced | ≈ ¥23.8 | ≈ ¥71.4 | **¥149**（维持） | ¥149 |

**结论：现有价格本身是合理的**，对典型用量有 4×–6× 的余量。问题不在价格，在额度上限。

### 4.2 建议额度上限（这才是要改的地方）

**设计目标**（本轮明确）：

1. 重度但正常的用户不受影响；
2. P95 月度 provider 成本 ≤ 售价的 **35–40%**；
3. 合法极端使用（每天打满）不得超过售价的 **约 1.5×** —— 当前是 5×–7×。

「合法极端」= 上限之外的任何使用都不被允许，所以 `MAX_LEGAL = weekly × 4.286 × ¥0.01`。

| tier | 售价 | 目标 MAX_LEGAL | 反推 weekly | **建议 weekly** | 建议 daily | 现在 weekly |
|---|---|---|---|---|---|---|
| free | ¥0 | ≈ ¥3.0 | 70 | **70** | 20 | 500 |
| standard | ¥29 | ≈ ¥45（1.5×） | 1,050 | **1,000** | **200** | 5,000 |
| advanced | ¥149 | ≈ ¥224（1.5×） | 5,226 | **5,000** | 不限（保持） | 20,000 |

**说明**：Standard 的 daily 200 在 weekly 1,000 之下不构成约束（200×30 = 6,000 > 4,286），
它的作用是挡住「一天烧完一周」。Advanced 保持每日不限——weekly 已经收紧，而这正是它相对
Standard 的差异点之一。

#### 输出（本轮要求的具体数值）

```
RECOMMENDED_STANDARD_DAILY  = 200   credits   (当前 1,000)
RECOMMENDED_STANDARD_WEEKLY = 1,000 credits   (当前 5,000)
RECOMMENDED_ADVANCED_WEEKLY = 5,000 credits   (当前 20,000)
```

#### 成本分布（按 §2.1 的单次成本建模）

用量画像显式写出，便于复核：

- **P50**（有付费、当周活跃的中位用户）：每天 8 次普通问答 + 每周 1 次深度思考
  → 240 + 4.29×9 = **279 credits**
- **P95**（重度但正常）：每天 25 次普通问答 + 每周 3 次深度思考 + 每周 1 次 Debug Agent
  → 750 + 4.29×27 + 4.29×20 = **952 credits**
- **Advanced P95**（按更高强度估）：每天 80 次 + 每周 10 次深度 + 每周 5 次 Agent
  → 2,400 + 386 + 429 = **3,215 credits**

```
EXPECTED_P50_COST  = ¥2.79 / month   (Standard, 9.6% of 售价)
EXPECTED_P95_COST  = ¥9.52 / month   (Standard, 32.8% of 售价  —— 落在 35–40% 目标内)
MAX_LEGAL_COST     = Standard  ¥42.86 / month  (1.48× 售价，当前 ¥214.50 = 7.4×)
                     Advanced  ¥214.30 / month (1.44× 售价，当前 ¥858.00 = 5.8×)
                     Free      ¥3.00 / month
```

**P95 对照**：新上限下 P95 用量（952 credits / 月 = 约 222/周）远低于 1,000/周，
因此**上限不会打到正常重度用户**；它只在真的极端使用时生效。

#### 这些数字的性质（必须一并读）

- **是建模值，不是实测分布。** 单次成本来自 `ai/pricing.py` 的 v4 价表与
  `max(1, round(cost/0.01))` 规则（§1.1 / §2.1），**没有**读生产 `ai_cost_records`。
- **未部署。** 本轮只输出建议；把新预算写进 `DAILY_BUDGET` / `WEEKLY_BUDGET` 需要你确认。
- **下调上限是产品决策**：它改变学习者可感知的能力边界，不是纯配置调整。

**现行 free 额度的成本（¥21.45 / 月）比 Standard 售价减去 3× 成本后的全部余量还高**——
一个未付费账号当前被允许消耗的成本，接近一份付费订阅能负担的两倍。这一项应当最先处理。

> **这是建议，不是决定。** 下调额度是产品决策，会改变用户可感知的能力边界；
> 本审计不擅自修改 `DAILY_BUDGET` / `WEEKLY_BUDGET`。

### 4.3 支付

**当前没有真实收款能力。** 事实：

- `backend/payments/` 只有 `MockPaymentProvider`；refund / query 返回 `NOT_AVAILABLE_LOCAL`。
- `payments/registry.py`：`PAYMENT_PROVIDER` 默认 `"mock"`；任何其他值直接
  `RuntimeError("No approved payment provider adapter is configured")`。
- Mock 支付在 `APP_ENV ∉ {local, dev, test}` 时返回 **403**（`is_mock_payment_allowed`）。
- 代码库中不存在 alipay / wechat pay / stripe / invoice 的任何字样。

因此 learner UI **不得模拟支付成功**。`/membership/payment` 的 `去支付` 会真实调用
`POST /subscription/orders/{id}/pay`，并在 403 时如实显示「在线支付还没有开通：没有产生任何扣款」。

### 4.4 兑换码

`redemption_codes` 表真实存在，`POST /admin/membership/redemption-codes` 生成（权限
`redeem_code.create`，明文只显示一次），learner 端 `POST /subscription/redeem` 消费。
**它是管理员发行、管理员交付的机制** —— 对学习者来说，一个只能输入管理员给的码的输入框不是路径。
learner UI 已按本轮要求移除该入口；后端端点保留（管理员仍在用）。

---

## 5. 本次审计**没有**做的事

- 没有读生产库，因此**没有**真实 `actual_credits` 分布、真实平均 token 数、真实日活/付费分布。
  第 4 节的「预期成本」是量级估算，不是实测。
- 没有修改任何价格、预算或 provider 配置。
- `minimax-m3` / `minimax-m2.7-highspeed` 的定价在代码中标注为 `CONSERVATIVE_CEILING`（未核实），
  未参与本次估算。

## 6. 建议的下一步（等用户决定）

1. 用生产 `ai_cost_records` + `ai_requests` 跑一次真实的 monthly cost per tier 分布。
2. 依据分布决定是否按 §4.2 收紧 weekly 上限。
3. 若要真正开通支付，需要一个已批准的 provider adapter + `PAYMENT_PROVIDER` 配置 + 回调验签；
   在此之前保持「不模拟成功」。
