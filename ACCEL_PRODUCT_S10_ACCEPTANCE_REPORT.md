# ACCEL_PRODUCT_S10 — UNIFIED MEMBERSHIP MIGRATION + COMPETITION DEMO READINESS + DATA FLYWHEEL STABILIZATION

验收报告。所有断言均给出实测值；无法证明的一律标注为「未证明」而不是「通过」。

---

## 0. 先说事故：`backend/app.db` 被误改，已按字节还原

**发生了**：在准备 DEMO 环境时，我执行了一次 `alembic upgrade head`，**未显式设置
`DATABASE_URL`**。`migrations/env.py` 在环境变量缺失时回退到 `backend/database.py` 的默认值，
即 `backend/app.db`。该命令因此把 10 个 revision 应用到了**真实本地库**上（新增
`alembic_version` 与 data_plane / practice / subscriptions 等表）。

**已做的修复**：

| 项目 | 值 |
|---|---|
| 事故前 SHA256（开工即记录） | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` |
| 事故后 SHA256 | `bd3a13e33b94327579812e6942c5317c3967125e0e6715a78dd8fa1c5635cb04` |
| 还原方式 | 用事故**之前**已复制的字节级副本覆盖回 |
| 还原后 SHA256 | `1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522` |
| `PRAGMA integrity_check` | `ok` |
| 表数量 | 72（与事故前一致） |
| `alembic_version` 表 | 不存在（与事故前一致） |
| `exam_question_bank` 行数 | 9333（未丢失） |
| 被污染副本 | 保留在 `.s10tmp/appdb_mutated_by_alembic.db`，未删除 |

**遗留观察（不是断言）**：`backend/app.db-wal` 在事故后变为 0 字节。事故前该文件已存在，
其内容我在开工时未记录，因此**无法证明**它也回到了事故前状态。我选择保留该文件原样而不是
删除它。如果这个 WAL 在开工时含有未 checkpoint 的已提交数据，那部分数据不在我手上。

**这是本次任务中唯一一次对高风险文件的写入。** 之后的 DEMO 环境全程使用显式
`DATABASE_URL=sqlite:///.../.s10tmp/demo.db`，每次运行后都重新校验 `app.db` 的 SHA256。

---

## 1. PART A — SSOT CURRENT Git 状态

`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` §37.1 与 §68.1 原来硬编码
`AHEAD = 15 / BEHIND = 12 / RELATIONSHIP = DIVERGED`。实测 `git rev-list --left-right
--count origin/main...HEAD` = `0	0`，两者早已同步。

改法（按授权）：

- 两节都不再断言任何 AHEAD / BEHIND / DIVERGED 常量；
- 改为「开工前现场测量」的四条命令清单；
- 历史分叉测量值移入 §37.1「### 沿革」小节，明确标注**旧记录，非 CURRENT**；
- 无破坏性 Git 操作红线**加强**保留（新增 `NO restore` / `NO stash` / `NO checkout --`）；
- 未改写任何历史 freeze 记录。

---

## 2. PART B — 统一会员权威

### B1 现状审计（读 / 写点分类）

| 载体 | 位置 | 分类 |
|---|---|---|
| `subscriptions`（`usage/service.effective_subscription`） | `backend/usage/service.py:54` | **AUTHORITATIVE** |
| `user_service_memberships` 读 → 4 项 legacy 固定额度 | `backend/membership.py:effective_service_plan` | **COMPATIBILITY** |
| `user_service_memberships` 写（legacy 兑换） | `backend/membership.py:redeem_membership_code` | **COMPATIBILITY** |
| `user_service_memberships` 写（管理后台） | `backend/main.py` admin memberships PATCH | **COMPATIBILITY** |
| `user_service_memberships` 写（支付成功） | `backend/payments/service.py:apply_verified_payment` | **COMPATIBILITY** |
| `users.plan` / `plan_expire_at` | `backend/main.py:get_effective_plan` | **COMPATIBILITY**（历史遗留，仅用于开发者/管理员判定） |
| `membership/plans`、`membership/summary`、`membership/recommendation` | `backend/main.py:29287+` | **DEAD**（旧 PLAN_DEFINITIONS 目录页，新前端不调用） |
| `POST /membership/redeem` | `backend/main.py:29417` | **MIGRATION_REQUIRED → 已处理**（兼容入口，同时激活统一档位） |
| `GET /membership/entitlements` | `backend/main.py:29058` | **MIGRATION_REQUIRED → 已处理**（改由统一档位解析） |
| `POST /membership/orders` 系列（按方向下单） | `backend/main.py:29082+` | **COMPATIBILITY**（mock 支付，生产 403） |

### B2 新权威（FROZEN）

```
subscriptions（一人一档）
   ↓
usage.capabilities.CAPABILITY_TIER_POLICY
   ↓
usage.capabilities.FEATURE_CAPABILITY = {learning_plan: planning.generate,
                                         learning_report: None(基础权益)}
   ↓
membership.get_feature_entitlement → 产品功能
```

`FEATURE_CAPABILITY` 是**唯一**的 功能→档位 映射。已由
`test_bc8r1_entitlement_contract.py::test_the_tier_alone_decides_the_feature` 结构化证明：
改档位即改结论（不写任何行），写付费方向行**不改变**结论。

### B3 learning_plan

- Free：**拒绝**（`required_tier = standard`，`planning.generate`）
- Standard / Advanced：**允许**
- `monthly_sprint` 等 legacy code **不再是独立产品档位**，仅在兑换码存储与管理后台作为内部别名存在；用户界面不再出现（见 PART C）。

### B4 迁移

新增 `migrations/versions/20260919_0011_unified_membership_backfill.py`（纯数据迁移，只 INSERT）。

- 两个来源取**较高档位**：`user_service_memberships`（按方向 catalog rank）与 legacy `users.plan`；
- 只升不降：已有更高档位用户不被降级；
- 幂等：第二次运行为 no-op；
- **无法映射时拒绝执行**并列出 `(user_id, code)`，不猜测；
- fresh 库（无 `users` 表）时为 no-op —— 这正是 `alembic upgrade head` 足以支撑全新部署的原因。

在真实 legacy 库副本上实测：

```
[20260919_0011] legacy rows read: memberships=0 users.plan=0; users derived=0;
                subscriptions inserted=0; unmappable=0
```

（本地 `app.db` 无任何付费会员行，故无行可迁移；迁移逻辑本身由 6 个针对性测试覆盖，
含「不可映射则拒绝」「幂等」「不降级」「fresh 库 no-op」。）

### B5 兑换

**唯一用户可见兑换流 = `POST /subscription/redeem`**（新前端只调用它）。
`POST /membership/redeem` 保留为兼容入口，但走**同一条** `redeem_unified_code` 事务，
因此两条路径不可能对「一个码给了什么」产生分歧。

实测（DEMO 环境）：

```
before = {'tier': 'free',    'plan_allowed': False, 'study_plan_http': 403}
after  = {'redeem_http': 200, 'tier': 'standard', 'plan_allowed': True,
          'study_plan_http': 200}
REDEEM_SUCCESS_WITH_LOCK_STILL_CLOSED = 0
```

### B6 Entitlement API

`GET /membership/entitlements` 保留，但决策已改为读统一档位。契约变化（**RUNTIME_RESPONSE_CHANGED**）：

| 字段 | 变化 |
|---|---|
| `current_plan`（legacy code） | → `current_tier`（unified tier） |
| — | + `policy_version` |
| `features[*].required_plan`（legacy code） | → `required_tier` + `required_capability` |

兼容性证明：新前端与生成类型在同一次提交内更新；后端全量测试通过；
`test_the_legacy_plan_code_is_gone_from_the_schema` 断言旧字段不在 OpenAPI 中。

---

## 3. PART C — 会员前端契约

`frontend/src/features/membership/`：

- **单一档位叙事**：页面只呈现一个 standing（统一档位）+ 政策版本；删除了
  「统一会员档位 / 当前备考方案」双行 `dl` 与「两个体系分别生效」的说明文字
  （那正是「并列会员」的呈现）。
- **档位自检**：若 `/subscription` 的 tier 与 `/membership/entitlements` 的
  `current_tier` 不一致，页面渲染一条 alert —— 页面不会描述一个不是真实锁的锁。
- **权益行**改为 `需要 Standard 及以上`（与档位表同一套词汇），并显示判定 capability id。
- **兑换面板**只显示 backend 返回的 `tier_label` / 时长 / 服务端投影到期日，**不显示任何 legacy code**。
- **在线支付**保持有界不可用（按钮 disabled + 说明），不创建永远无法结算的订单。
- 测试 `membership-page.test.tsx` 新增断言：`document.body.textContent` 不得匹配
  `/monthly|quarterly|full_exam|sprint|boost/`。

---

## 4. PART D — Plan 锁的端到端证明

在 DEMO 环境用真实 HTTP 请求走完：

```
Free → GET /membership/entitlements  learning_plan.allowed = false
     → GET /exam/11408/subjects/computer_network/study-plan  = 403
     → POST /subscription/redeem {DEMO-CS408-STANDARD}       = 200
     → GET /membership/entitlements  current_tier = standard, allowed = true
     → GET /exam/11408/subjects/computer_network/study-plan  = 200
```

前端 `LockedPlan` 现在显示 `学习计划需要 Standard 及以上档位`，链接指向 `/membership`，
后者读**同一个** entitlement 端点。

---

## 5. PART E — 支付边界

未新增支付提供商。`POST /subscription/orders` 仍只创建 PENDING 订单，唯一支付方式是
`mock`，生产运行时 403。会员页明确写「在线支付尚未开通」且按钮不可点击。
兑换码是当前唯一生效的开通机制。

**已知边界（报告，不掩盖）**：管理后台把某个方向**降级**为 free 时，统一档位**不会下降**
（`raise_unified_tier` 单调只升）。理由是统一档位可由兑换、支付、迁移等多条路径授予，
从管理后台的方向行去降低它，会等同于静默取消用户通过**另一条**路径买到的订阅。
退款路径有独立的重算逻辑（`payments/service._recompute_unified_tier_after_refund`，
只重算 `source='order'` 的订阅，不动兑换/迁移来源）。

---

## 6. PART F — DEMO / ACCEPTANCE 环境

`scripts/seed_demo_environment.py`，两个独立账号：

| 账号 | 用途 | 档位 |
|---|---|---|
| `demo_cs408` | 录制 / 演示 | 保持 **Free**（这样演示里有一个真实的锁可开） |
| `demo_acceptance` | 自动验收 | 由 rehearsal 兑换后转 Standard |

实测产物（真实 HTTP 调用）：

```
study_plan_status = 403     questions_available = 50
attempt_id = 1              submit_status = 200
wrong_answers = 1           learning_records = 200
student_twin_status = 200
```

环境变量：`DATA_ORIGIN=DEMO`（`backend/data_plane/origin.py`）。
生产环境**拒绝**该变量：`active_origin()` 在 `is_production_runtime()` 为真时返回
`UNCLASSIFIED`（fail-closed），因此误配的生产实例即使被写入 demo 数据，那些数据也不会被当成
真实学习数据。

---

## 7. PART G — 数据集排除

新增 `migrations/versions/20260919_0012_data_origin_provenance.py`：
`learning_events` 与 `practice_attempts` 各加一个可空 `data_origin`（+ 索引）。

- 取值（闭集）：`LEARNER` / `DEMO` / `ACCEPTANCE` / `TEST` / `BACKFILL_SYNTHETIC`
- **无默认值**：忘记打标的行是 NULL → 报为 `UNCLASSIFIED` → 排除（fail-closed）
- 历史行回填为 `LEARNER`，理由写在迁移 docstring 里（**可核验**：这两个表的写入者只有
  live Practice Core、live emitter / producers、以及 re-project 真实源行的 backfill；
  S10 之前不存在 demo/test 写入者）

`science/kt_dataset.py` 的 `build()`（训练导出）与 `interaction_coverage()`（诊断）
在**任何**资格规则之前做 origin 门禁，并按 origin 分别计数。

实测（DEMO 库）：

```
excluded = {'DATASET_ORIGIN_DEMO': 2}
demo_interactions = 2
real_eligible_interactions = 0
DEMO_DATA_USED_FOR_MODEL_TRAINING = NO
```

`science/kt_native.audit()` 的 readiness 输入来自 `build()`，因此
**只有真实学员事实能满足 DATA_READINESS_GATE**；audit 输出新增
`dataset_origin_policy` 明示这一点。

---

## 8. PART H — 真实数据 vs DEMO 诊断分离

`science/status.data_collection_status()` 现在分别报告：

```
real_users_with_events / real_eligible_interactions / real_concept_level_interactions
demo_users / demo_interactions / test_interactions / synthetic_backfill_interactions
unclassified_interactions / rows_by_origin / real_vs_demo_separated = true
```

`users_with_events` 与 `eligible_interactions` 保留原名，但**等于** `real_*`（非 LEARNER
事实在计数前已被丢弃），并断言 `users_with_events == real_users_with_events`。

**demo/test 数字永不与 real 相加。**

---

## 9. PART I — 计算机网络 300 条未解析题：人工整理工件

新增 `scripts/build_cn_curation_worklist.py`，产物：

- `s10_artifacts/cn_unresolved_curation_worklist.json`
- `s10_artifacts/cn_unresolved_curation_worklist.csv`

实测（只读本地 `app.db`）：

```
unresolved rows: 300
by reason: {'STORED_CONCEPT_ID_IS_EMPTY': 45,
            'STORED_ID_DOES_NOT_EQUAL_ANY_CANONICAL_LEAF_CODE': 255}
rows with a candidate shortlist (chapter established): 255
rows with NO chapter (empty shortlist): 45
auto-selected leaves: 0 (enforced)
```

每行字段：`question_id`、`source_ref`、`current_canonical_chapter`、`current_level`、
`reason`、`near_match_leaf_code`、`stem_excerpt`（80 字，不含答案）、
`candidate_leaves`（**仅限该行所在章节**的 canonical leaf，含标题）、`selected_leaf = null`。

脚本在写出前断言**没有任何一行带上 `selected_leaf`**；一旦未来某条规则开始自动填空，
脚本会直接失败而不是把一个映射当成整理结果交付。**没有自动映射任何一条。**

---

## 10. PART J — response_time / hint 保持不变

未做任何产品改动。实测 `science.status.data_collection_status()`：

```
response_time_ms = {"state": "NOT_COLLECTED", "coverage": None}
hint_count       = {"state": "NOT_AVAILABLE", "coverage": None}
```

新增测试 `test_uncollected_telemetry_is_still_reported_as_uncollected` 钉住这两项。

---

## 11. PART K — 科学模型路线图冻结（未晋升任何组件）

`test_the_frozen_scientific_modes_are_unchanged` + `test_the_proof_matrix_...` 实测：

```
student_twin          = PREVIEW  (USER_VISIBLE_PREVIEW)   user_visible = true
evidence_reliability  ≠ PREVIEW   SHADOW_COLLECTING_DATA
tutor_policy          ≠ PREVIEW   SHADOW_COLLECTING_DATA
learner_state         ≠ PREVIEW
misconception_v2      ≠ PREVIEW
memory / irt / concept_verifier ≠ PREVIEW
user_visible 组件总数 = 1
```

S10 **没有**改动 `science/capabilities.py` 的 REGISTRY 中任何 mode。

---

## 12. PART L — 技术证明矩阵

`science.status.technical_proof_matrix()`（新增），已挂到 `GET /science/status`
（admin-only）的 `technical_proof_matrix` 键。实测 13 行，每行：

```
component / self_developed / self_developed_basis / learned_model / model_family /
runtime_endpoint / product_mode / real_model_test / checkpoint_provenance /
artifact_digests / user_visible / controls_product_decision / writes_learner_fact /
category / blockers
```

外加 `external_inference` 块：`self_developed = false` —— 产品的 LLM 推理不是 13 个
scientific component 之一，只经 AI Gateway 按 capability 调用。这正是竞赛演示需要
当面说清的那条界线。

`self_developed = true` 的依据写在载荷里（不是默认值）：「implemented in this
repository's science/ package」—— 这是关于 REGISTRY 的事实；某个组件内部嵌了三方模型
（如 `misconception_v2` 用 BGE-M3）由 `checkpoint_provenance` / `artifact_digests` 单独记录。

---

## 13. PART M — 端到端产品验收（DEMO 环境，真实 HTTP）

`scripts/seed_demo_environment.py` 一次运行完成，**20 passed / 0 failed**：

注册/登录 → Knowledge（50 题可见）→ Practice（提交 200）→ 错题（1 条）→
Wrong Answers → Study Plan（先 403 后 200）→ Learning Records（200）→
Student Twin（200）→ Membership → redeem → Plan 解锁。

另跑 `scripts/verify_s9_product_flows.py`（S9 的 41 项端到端流程）作为回归：
**41 passed / 0 failed**，含跨用户隔离与 admin 权限门。

无任何伪造状态转换。

---

## 14. PART N — 生产

**未执行生产部署**，原因见下（BLOCKERS §1）。生产库
`/var/lib/ai_study_platform/app.db` 本次**未被读写**。
未创建任何生产验收账号。

---

## 15. PART O — 测试

### 后端全量（`backend/.venv`，真实 venv）

```
1578 passed, 2 skipped, 0 failed in 604.42s
```

注意：`CLAUDE.md` 写的是「322 tests」；实测 collection = **1560 → 1578**（S10 新增
`test_s10_membership_and_provenance.py`）。见 BLOCKERS §3。

PART O 要求的各项，落点如下：

| 要求 | 测试 |
|---|---|
| single membership authority | `test_bc8r1_entitlement_contract.py::test_the_tier_alone_decides_the_feature` |
| unified redeem opens feature | `test_s9_membership_and_status.py::test_redeem_success_never_leaves_the_feature_locked` |
| legacy membership cannot override unified | `test_feature_entitlements.py::test_a_legacy_direction_row_alone_opens_nothing` |
| Free denied | `test_bc8r1_...::test_membership_policy_is_free_denied_and_every_paid_tier_allowed` |
| Standard allowed | 同上 + `test_s10_...::test_the_tier_is_the_only_thing_that_decides_a_feature` |
| Advanced allowed | 同上 |
| budget semantics unchanged | `test_s10_...::test_budget_semantics_are_unchanged_by_the_membership_migration` |
| cross-user isolation | `test_bc8r1_...::test_one_user_never_sees_another_users_tier`、`test_feature_entitlements.py::test_a_tier_is_per_learner_and_does_not_leak` |
| demo data excluded from training export | `test_s10_...::test_demo_facts_are_excluded_from_the_training_dataset` |
| real-vs-demo diagnostics separated | `test_s10_...::test_admin_diagnostics_report_real_and_demo_separately` |
| Plan unlock flow | `test_s9_...::test_redeem_success_never_leaves_the_feature_locked`（HTTP 层）+ DEMO rehearsal（真实服务） |
| migration compatibility | `test_s10_...` 的 5 个 migration 测试 + `test_s6_deployment_gate.py`（35 passed，含真实 legacy 库副本 rehearsal） |
| OpenAPI concrete | `test_bc8r1_...::test_the_success_response_is_concrete_in_openapi`、`::test_the_redeem_endpoints_declare_concrete_models` |

另外新增了 Tier↔Plan 往返（`test_the_tier_to_plan_mapping_is_its_own_inverse`）、
origin fail-closed（`test_a_null_origin_is_not_real_data`）、
生产拒绝 DEMO（`test_the_process_origin_refuses_to_be_demo_in_production`）、
未采集遥测保持未采集（`test_uncollected_telemetry_is_still_reported_as_uncollected`）、
科学模式冻结（`test_the_frozen_scientific_modes_are_unchanged`）、
证明矩阵（`test_the_proof_matrix_covers_every_component_and_names_who_may_see_it`）。

### 前端

```
npm run check   → 28 test files, 119 tests passed; typecheck 0 error; eslint 0 problem
npm run build   → ✓ built in 648ms
```

### 端到端（真实 HTTP，DEMO 环境）

```
scripts/seed_demo_environment.py    → 20 passed, 0 failed
scripts/verify_s9_product_flows.py  → 41 passed, 0 failed   (S9 回归)
```

---

## 16. 迁移与 HEAD

```
MIGRATION_HEAD = 20260919_0012
新增: 20260919_0011_unified_membership_backfill.py   (纯数据迁移，只 INSERT)
      20260919_0012_data_origin_provenance.py        (两个可空列 + 1 索引)
```

两者都：additive-only、在真实 legacy 库副本上跑通、`PRAGMA integrity_check = ok`、
`downgrade()` 抛 `NotImplementedError`（与链上其余 revision 一致；恢复路径是迁移前备份快照，
S6 PART E 演练的就是这条）。

**是否需要迁移：需要。** 生产库必须执行 `alembic upgrade head`（即 PART N 的部署流程），
否则 `subscriptions` 不会成为权威（0011 未跑 → 老付费用户档位为空）且新代码在写入
`data_origin` 时会因列缺失而失败。**本次未执行**（见 BLOCKERS §1）。

---

## 17. BLOCKERS

1. **未执行生产部署。** 本次任务的 PART N 要求 backup → migration → preflight → deploy →
   smoke，但同一份任务书里没有给出部署授权，而 `CLAUDE.md` 的长期红线把「直改线上 /
   绕过既有部署流程」列为禁止项。两个新 migration 已在**真实 legacy 库副本**上验证可跑，
   但我没有把它推到线上。**需要用户明确批准后执行。**
2. **`backend/app.db` 事故（见 §0）**：已按字节还原，SHA256 与开工记录一致。WAL 状态无法
   证明回到原样（事故前未记录），保留原文件未删除。
3. **`CLAUDE.md` 测试数量已过期**：文件写「默认 collection = 45 个测试文件 / 322 tests」，
   实测 `pytest` 收集 **1560** 项。未擅自改写 —— 这是执行契约里的 CURRENT 陈述，与
   PART A 授权的 SSOT 范围不同，交由用户决定。
4. **管理后台降级不降低统一档位**（§5 已知边界）。
5. **`/membership/catalog`、`/membership/plans`、`/membership/summary` 等旧方向目录端点保留**
   仍会返回 legacy plan code。新前端不调用它们（前端用 `/subscription/plans`），因此
   「legacy code 不出现给用户」在**产品表面**成立，但旧端点本身未删除（Preserve
   Capability）。若要彻底移除，属下一步独立任务。
