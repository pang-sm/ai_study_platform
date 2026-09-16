# STEP7CP_PROVIDER_MODEL_POOL_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7C-P 验收报告
> 范围：Provider Onboarding / Live Validation / Model Pool Calibration
> 生成：2026-09-16 · 本轮为 IMPLEMENTATION（有代码变更，未 commit）

---

## 1. EXECUTIVE VERDICT

```text
STEP7CP_COMPLETE = YES
STEP7D_READY     = YES
```

**核心结论：**

1. 6 个 Provider 全部完成 secret 配置（hidden 输入，`.env.local` gitignored），SHA256 指纹审计，全流程无 raw key 泄露。

2. Live validation 完成：6 家 `/models` discovery 全通；minimal smoke 5 家 PASS，Doubao 为 `NO_MODEL_ACCESS`（Ark endpoint-id 模式，需 `ep-xxx` 映射——adapter 已支持 `model_map`）。

3. Pricing Registry v3：DeepSeek/Qwen/Kimi/GLM 采用官方文档定价（verified），MiniMax 采用保守 cost ceiling（unverified）。peak/off-peak 不压扁。

4. ZHIXUE_MODEL_POOL_CALIBRATION_V1 Stage 2 已执行（66 请求，总成本 ≈ ¥0.03），据此重建 Qualified Pool v3（`POOL_QUALIFICATION_LEVEL = FINAL`），5-provider cross-provider fallback。

5. 全量后端回归通过。

---

## 2. PREVIOUS_PARTIAL_RUN（审计链保留）

```text
上一轮（2026-09-16 早）误将「2/6 provider 已配置」写成 COMPLETE。已立即更正：
  STEP7CP_COMPLETE = NO
  STEP7CP_STATUS   = PARTIAL
  STEP7D_READY     = NO

更正动作：SSOT 恢复（用户提供完整副本）+ 4 个 missing key 由用户本地 hidden 输入完成。
本报告为 FINAL_SIX_PROVIDER_RUN，保留上一轮审计事实，不覆盖、不假装上一轮已完成。
```

---

## 3. GIT BASELINE

```text
HEAD = 95b7dccc（feat: add learning event data plane foundation）
WORKTREE 原本 DIRTY；本轮未执行 git 写操作（NO commit / push / reset / clean / checkout）
```

---

## 4. SECRET SECURITY

```text
RAW_SECRET_IN_GIT = NO
RAW_SECRET_IN_TRACKED_FILES = NO
RAW_SECRET_IN_REPORT = NO
RAW_SECRET_IN_DB = NO
```

- `backend/.env.local`（gitignored）为 canonical secret file；`git check-ignore` 确认忽略。
- 已配置 provider 指纹（SHA256 prefix-8，非 key）：deepseek=95a99062、qwen=30cbc775、doubao=597c6878、kimi=72a1e919、glm=b492f9cf、minimax=9cbada25。
- 本轮仅回显 fingerprint + configured 布尔，绝无 raw key / 首尾字符。

---

## 5. PROVIDER ACCOUNT MATRIX（FINAL）

| Provider | Configured | Auth | Discovery | Smoke | Usage | Pricing | Final |
| -------- | ---------- | ---- | --------- | ----- | ----- | ------- | ----- |
| deepseek | yes | PASS | 2 models | PASS | PROVIDER_REPORTED | VERIFIED | QUALIFIED |
| qwen     | yes | PASS | 251 models | PASS | PROVIDER_REPORTED | VERIFIED | QUALIFIED |
| doubao   | yes | PASS | 132 models | NO_MODEL_ACCESS | — | — | endpoint-id required |
| kimi     | yes | PASS | 2 models | PASS | PROVIDER_REPORTED | VERIFIED | QUALIFIED |
| glm      | yes | PASS | 10 models | PASS | PROVIDER_REPORTED | VERIFIED | QUALIFIED |
| minimax  | yes | PASS | 8 models | PASS | PROVIDER_REPORTED | CEILING | QUALIFIED |

```text
PROVIDER_COUNT_CONFIGURED = 6
PROVIDER_COUNT_AUTH_OK   = 6
PROVIDER_COUNT_STAGE1_PASS = 5（doubao 除外，NO_MODEL_ACCESS）
PROVIDER_COUNT_WITH_QUALIFIED_MODELS = 5
```

- `MODEL_EXISTS` ≠ `MODEL_ACCESSIBLE_TO_THIS_ACCOUNT`：Doubao `/models` 返回 132 个目录模型，但 chat completion 报 `InvalidEndpointOrModel.NotFound`（404）——账户为 endpoint-id 模式，需在 Ark 控制台建推理端点后用 `ep-xxx` 映射（`ArkProvider.model_map` 已支持）。

---

## 6. PROVIDER ADAPTERS

```text
deepseek.py（DeepSeek）· qwen.py（DashScope）· ark.py（Doubao，model_map）·
moonshot.py（Kimi）· zhipu.py（GLM）· minimax.py（MiniMax）· fake.py（测试）· common.py
```

全部 OpenAI-compatible；错误经 `map_openai_error` 规范化为 `GatewayErrorCategory`；provider-specific 兼容仅在 adapter。温度参数兼容：Kimi k2.6 仅接受 `temperature=1`，smoke/benchmark 已改为省略 temperature（`temperature=None`）。

---

## 7. MODEL DISCOVERY（live 2026-09-16）

```text
deepseek: deepseek-flash, deepseek-v4-pro
qwen:     251（qwen-native: qwen3.8-flash/max、qwen3.7-plus/max/flash、coder/vision/...）
doubao:   132（doubao-1-5-*、doubao-1.5-*、thinking-pro 等；endpoint-id 模式）
kimi:     kimi-k2.6, kimi-k2.7-code
glm:      glm-4.5/4.5-air/4.6/4.7/5/5-turbo/5.1/5.2/5.3/5.3-flash
minimax:  MiniMax-M3/M2.7/M2.7-highspeed/M2.5/M2.5-highspeed/M2.1/M2.1-highspeed/M2
```

---

## 8. LIVE CONNECTIVITY（smoke，≤32 tokens）

```text
deepseek/flash 918ms · deepseek/v4-pro 1420ms · qwen3.8-flash 1306ms · qwen3.8-max 1385ms
kimi/k2.6 4041ms · kimi/k2.7-code 1378ms · glm/5.3-flash 930ms · glm/5.3 5971ms · glm/5 1237ms
MiniMax/M3 1117ms · MiniMax/M2.7-highspeed 991ms
```

qwen3.7-plus = AUTH_FAIL（本账户不可达，非 catalog 所有模型都可访问）。

---

## 9. PRICING REGISTRY（v3）

```text
deepseek/deepseek-flash    VERIFIED  ¥1.08 / ¥0.0216(cache) / ¥4.32（peak 2x）
deepseek/deepseek-v4-pro   VERIFIED  ¥4.752 / ¥0.1584 / ¥14.256（peak 2x）
qwen/qwen3.8-flash         VERIFIED  ¥0.8 / ¥0.1 / ¥2.7
qwen/qwen3.8-max           VERIFIED  ¥12 / ¥1.5 / ¥36
kimi/kimi-k2.6             VERIFIED  ¥6.84 / ¥1.152 / ¥28.8
kimi/kimi-k2.7-code        VERIFIED  ¥6.84 / ¥1.368 / ¥28.8
glm/glm-5.3-flash          VERIFIED  ¥0.8 / ¥2.8
glm/glm-5.3                VERIFIED  ¥8 / ¥28
glm/glm-5                  VERIFIED  ¥4 / ¥18
minimax/MiniMax-M3         CEILING   ¥6 / ¥30（unverified）
minimax/MiniMax-M2.7-highspeed CEILING ¥1 / ¥5（unverified）
```

来源：DeepSeek（api-docs.deepseek.com）、Qwen（developer.aliyun.com）、Kimi（platform.kimi.ai）、GLM（docs.bigmodel.cn）；MiniMax 官方 per-model 价未确认 → conservative ceiling。

---

## 10. ZHIXUE CALIBRATION BENCHMARK（Stage 2）

```text
BENCHMARK_VERSION = ZHIXUE_MODEL_POOL_CALIBRATION_V1
STAGE2_BENCHMARK_EXECUTED = YES（11 models × 6 cases，TOTAL_ESTIMATED_COST ≈ ¥0.03）
```

6 个固定 provider-neutral case（中文讲解/11408 解析/资料问答/AI 出题 JSON/编程解释/debugging）。确定性评分（contains/contains_any/json_valid），rule-based，无单一模型作裁判。

```text
qwen3.8-flash          6/6  ⭐  qwen3.8-max            6/6  ⭐
glm-5.3-flash          5/6     MiniMax-M2.7-highspeed 5/6
MiniMax-M3             5/6     deepseek-flash         4/6
deepseek-v4-pro        4/6     glm-5                  4/6
kimi-k2.6              4/6     kimi-k2.7-code         2/6（code 专精，benchmark 无真实代码编译题，排除）
```

> 注：thinking 模型（GLM/Kimi/DeepSeek-v4-pro/MiniMax-M3）在 max_tokens=200 下 reasoning 吃满预算致 content 空，已用 max_tokens=800 重测（+3s 间隔避免 Kimi org rate-limit），上表为公平结果。

---

## 11. QUALIFIED MODEL POOLS（v3 FINAL）

```text
MODEL_POOL_VERSION = v3
POOL_QUALIFICATION_LEVEL = FINAL

FREE:     qwen3.8-flash（primary）· glm-5.3-flash · deepseek-flash
STANDARD: + qwen3.8-max · MiniMax-M2.7-highspeed
ADVANCED: + deepseek-v4-pro · MiniMax-M3 · glm-5 · kimi-k2.6
```

- Free 保有 tutor.chat / question.explain / material.qa 可用模型（≥3，跨 3 provider）。
- cross-provider fallback：5 provider（deepseek/qwen/glm/minimax/kimi）。
- 排除：Doubao（NO_MODEL_ACCESS）、kimi-k2.7-code（benchmark 2/6 且无代码编译测试）、qwen3.7-plus（AUTH_FAIL）。

---

## 12. ROUTER V0

仍为 `Capability + Tier + Budget + Availability`。auto 顺序改为：qualified quality gate → budget compatible → availability → cost preference（不再 cheapest-only）。`router.ordered_candidates()` 供 orchestrator cross-provider fallback。

---

## 13. FALLBACK MATRIX

```text
free tutor.chat: qwen3.8-flash → glm-5.3-flash → deepseek-flash（跨 3 provider）
advanced programming.debug: qwen3.8-max → MiniMax-M2.7-highspeed → deepseek-v4-pro → MiniMax-M3 → kimi-k2.6
```

fallback 仅可重试错误触发；绝无 tier/budget/qualified bypass（`test_no_tier_bypass`/`test_no_unqualified_model_via_fallback`/`test_no_fallback_on_permanent_error` 固化）。

---

## 14. USER-VISIBLE MODEL OPTIONS

`GET /ai/models?capability=...` 返回 `auto` + qualified 选项；`INTERNAL_PROVIDER_REGISTRY != USER_VISIBLE_MODEL_POOL`（candidate/disabled/failed-smoke/unverified-inaccessible 不暴露）。

---

## 15. BUDGET RECALIBRATION

```text
BUDGET_RECALIBRATION = KEEP（provisional）
```

依据 verified 价格 sanity：qwen3.8-flash 基础回合 ≈ ¥0.001（1 credit 下限），Free daily 100 ≈ 100 回合；数值仍为 PROVISIONAL，生产前 STEP12 再校准。

```text
CREDIT_NORMALIZATION_STATUS = KEEP_PROVISIONAL
```

1 credit ≈ ¥0.01 暂维持；cheap 模型（~¥0.001/回合）低于 1-credit 下限，粒度偏粗，建议后续评估 ¥0.001/credit 但本轮不改。

---

## 16. PRODUCTION SECRET HANDOFF

```text
PRODUCTION_REQUIRED_SECRETS = DEEPSEEK_API_KEY, DASHSCOPE_API_KEY（进入 production pool 的 primary/fallback）
OPTIONAL_PROVIDER_SECRETS = MOONSHOT_API_KEY, ZHIPUAI_API_KEY, MINIMAX_API_KEY（qualified 备用）
                            ARK_API_KEY（需 endpoint-id 映射后才启用）
```

---

## 17. TESTS

```text
TARGETED_TESTS = PASS（0 failed）
新增/更新：test_secret_loader / test_provider_adapters / test_provider_discovery /
test_fallback / test_benchmark / test_pricing_pool_router（v3）/ test_ai_models_api（v3）
```

---

## 18. FULL REGRESSION

```text
FULL_BACKEND_TESTS = PASS（321 passed / 0 failed；另 +1 项 /ai/models permission gate 测试经 targeted run 验证）
  321 baseline（full regression）+ 1 post-regression test（test_ai_models_free_denied_premium_capability）
```

---

## 19. FINAL VERDICT

```text
PROVIDER_COUNT_CONFIGURED = 6
PROVIDER_COUNT_AUTH_OK   = 6
PROVIDER_COUNT_STAGE1_PASS = 5
PROVIDER_COUNT_WITH_QUALIFIED_MODELS = 5

DEEPSEEK = PASS（qualified）
QWEN     = PASS（qualified）
DOUBAO   = AUTH_OK / NO_MODEL_ACCESS（endpoint-id 模式）
KIMI     = PASS（qualified）
GLM      = PASS（qualified）
MINIMAX  = PASS（qualified）

RAW_SECRET_IN_GIT = NO
RAW_SECRET_IN_REPORT = NO
RAW_SECRET_IN_DB = NO

MODEL_POOL_VERSION = v3
POOL_QUALIFICATION_LEVEL = FINAL
PRICING_REGISTRY_VERSION = v3
BENCHMARK_VERSION = ZHIXUE_MODEL_POOL_CALIBRATION_V1
STAGE2_BENCHMARK_EXECUTED = YES

FREE_POOL = qwen3.8-flash, glm-5.3-flash, deepseek-flash
STANDARD_POOL = + qwen3.8-max, MiniMax-M2.7-highspeed
ADVANCED_POOL = + deepseek-v4-pro, MiniMax-M3, glm-5, kimi-k2.6

CROSS_PROVIDER_FALLBACK = YES（5 provider）
BUDGET_RECALIBRATION = KEEP
CREDIT_NORMALIZATION_STATUS = KEEP_PROVISIONAL

SSOT_RESTORED = YES
SSOT_UPDATED = YES

STEP7CP_COMPLETE = YES
STEP7D_READY = YES
```
