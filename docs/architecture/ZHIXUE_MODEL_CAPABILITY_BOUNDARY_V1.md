# 智学平台模型能力边界基准（ZHIXUE MODEL CAPABILITY BOUNDARY）

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文档从属于 SSOT；冲突时 SSOT wins。
>
> **⚠️ 本文档的部分内容已过时**：
> - 本文档引用的 `ZhiXue-KT` / `ZhiXue-Ranker` / `ZhiXue-Retriever` 等自研模型命名，
>   已被 SSOT §36 的 **13 个 Scientific Component** 取代
>   （`concept_verifier` / `difficulty_prior` / `misconception_v2` / `tutor_policy` / `tutor_guard` /
>   `memory` / `irt` / `planner` / `student_twin` / `execution_router` / `domestic_registry` /
>   `evidence_reliability` / `learner_state`）。
> - 「模型均未完成训练」不再是完整事实：13 个组件当前 `runtime pass = 13 / 13`，
>   但全部为 `RUNTIME_ONLY`（`SHADOW = 0 / ADVISORY = 0 / ACTIVE = 0`）。
>   **`runtime pass != product ready`**，必须通过 SSOT §35 的 Productization Gate。
> - 科学语义以 SSOT §36 为准，本文档不得覆盖。

- **文档名称**：智学平台模型能力边界基准
- **Version**：V1
- **Status**：BASELINE（subordinate to `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`）
- **Date**：2026-09-12
- **Scope**：模型尚未确定时的产品开发边界、能力分类、Learner State 语义、来源溯源、降级策略、数据采集、UI 语义
- **原则**：本文件是「模型能力边界」的参考基准。后续任何 Claude / Codex / 未来 Agent 都必须遵守；与 SSOT 冲突时以 SSOT 为准。

> 本文档是 `docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`（历史架构基准）在「模型能力边界」这一维度的**细化与强制执行层**。历史基准描述**目标架构**（Model Gateway、ZhiXue-KT、ZhiXue-Ranker 等），本文件描述**当前到目标之间，产品与工程不得越过的红线**。现行目标架构以 SSOT §30 / §36 为准。

---

## 1. 核心原则：MODEL-INDEPENDENT FOUNDATION

`scientific component` 相关的产品能力尚未产品化（当前全部为 `RUNTIME_ONLY`），
其产品影响、输入可用性、领域兼容性均未完成验证。

因此必须满足：

```text
NO MODEL          → PRODUCT STILL WORKS
MODEL AVAILABLE   → PRODUCT BECOMES SMARTER
```

**禁止**：

```text
NO MODEL → PRODUCT BREAKS
```

具体约束：

1. **禁止**前端、业务逻辑、数据库直接依赖某个未来模型实现。
2. **禁止**在模型不存在时返回「fake model output」。
3. **禁止**把未验证的模型能力写成「已经部署 / 已经存在」。
4. 模型能力只能作为**可插拔的增强层**叠加在确定性产品逻辑之上，不得成为产品主路径的硬依赖。

---

## 2. 当前能力分类（CURRENT TRUTH）

下面按四类严格区分当前系统「已真实存在」的能力。所有标注 `FUTURE / UNVERIFIED` 的能力**当前一律不存在**。

### A. DETERMINISTIC_PRODUCT_FACT（确定性产品事实，CURRENT）

这些是产品自身的客观事实，与模型无关：

| 事实 | 当前承载位置 |
|---|---|
| curriculum / 知识脉络 | `backend/seed_data/knowledge_maps/*.json`、`exam_question_bank` |
| knowledge point（知识点） | `knowledge_points`（system 行） |
| practice result（练习结果） | `exam_practice_attempts`、`past_paper_attempts`、`question_attempts`、`code_challenge_attempts` |
| wrong question（错题） | `exam_wrong_questions`、`past_paper_wrong_questions` |
| study timestamp（学习时间） | `learning_records.created_at`、`user_knowledge_progress.learned_at / last_studied_at` |
| review_due_at（复习到期时间戳） | `user_knowledge_progress.review_due_at` |
| material（资料） | `study_materials`、`material_chunks` |
| submission（提交） | `programming_exercise_submissions`、`code_challenge_attempts` |
| learning event（学习事件） | `knowledge_progress_events`、`learning_records`、`chat_messages` |

### B. RULE_DERIVED（规则推导，CURRENT）

这些是确定性规则从事实推导出的结果，**不是模型输出**：

| 规则结果 | 推导来源 |
|---|---|
| `review_due` 状态 | `learned_at` + `review_interval_days`（固定/用户设定）与当前时间比较，见 `_display_map_progress_status` / `_materialize_due_review_statuses` |
| `mastery_score`（0–100 整数） | 练习通过数/应通过数的规则公式（`100 if mastered else clamp(passed/required*100)`），**不是掌握概率** |
| structural next（课程树下一步） | 知识脉络树内「下一兄弟节点」，见 `getStructuralNextNode` |
| 复习间隔 `review_interval_days` | 默认 7 天或用户显式设置，`user_knowledge_review_settings` |
| 会员套餐推荐 `recommended_plan` | 专业关键词 → 分类 → 套餐的规则映射（带硬编码 confidence），**不是学习推荐** |

> **重要**：`user_knowledge_progress.mastery_score` 的字段名容易误解为「模型掌握概率」。当前它**只是规则分数**（练习正确率），不得在任何 UI / 文档中解释为「模型预测已掌握」。

### C. THIRD_PARTY_AI（第三方 AI，CURRENT）

当前真实接入的第三方模型能力（非自研模型）：

| 能力 | 当前 provider | 主要用途 |
|---|---|---|
| 对话 / 答疑（`chat`） | DeepSeek（OpenAI 兼容） | AI 问答、代码分析、AI Tutor |
| AI 出题（`question_generate` / `challenge_generate`） | DeepSeek | 章节题 / 编程挑战生成 |
| 题目解析反馈（`question_feedback`） | DeepSeek | 题目 AI 讲解 |
| 学习报告生成（`learning_report_generate`） | DeepSeek | 学习报告 |
| 资料-知识点链接推荐（`material_link_recommend`） | DeepSeek | 资料关联知识点 |
| 知识图谱生成（`knowledge_generate`） | DeepSeek | 知识点预览生成 |
| 文档 OCR / 视觉理解 | Qwen（DASHSCOPE） | PDF 扫描件识别、图片题 |

- 统一计量：`ai_usage_logs`（feature / model / tokens / cost / latency）。
- **这些是「理解与生成」能力，不负责「认识学生 + 决定下一步学习」。**
- Model Gateway / 能力抽象层（`CHAT_FAST` / `STEM_REASONING` 等）**当前尚未实现**，是 TARGET（见总体架构 §4/§5/§21）。

### D. FUTURE_MODEL（未来自研模型，FUTURE / UNVERIFIED）

以下能力**当前全部不存在**，均标记 `FUTURE / UNVERIFIED`：

1. Knowledge Tracing 掌握概率
2. 个性化下一步学习推荐（personalized next recommendation）
3. 预测学习收益（predicted learning gain）
4. 预测题目难度（predicted difficulty）
5. 学生能力估计（student ability estimation）
6. 自适应复习间隔（adaptive review interval）
7. 学习路径优化（learning-path optimization）
8. 辍学 / 失败预测（dropout / failure prediction）
9. 编程薄弱点诊断模型（programming weakness diagnosis model）
10. 策略 / RL 学习 Agent（policy / RL learning agent）

**禁止**现有 UI、API、文档声称以上能力已经存在。

---

## 3. 当前 Learner State 语义

当前只允许四个确定性产品状态：

```text
not_started
learning
mastered
review_due
```

每个状态的**真实来源**：

| 状态 | 真实来源（非模型） |
|---|---|
| `not_started` | 无 progress 记录，或显式重置 |
| `learning` | 用户开始学习（打开知识点 / 开始练习 / 首次作答） |
| `mastered` | 产品定义下的「明确完成 / 已学习」（练习达标、任务完成、或用户确认） |
| `review_due` | `mastered/learned` 时间戳 + `review_due_at`（确定性复习规则）到期 |

**禁止**把 `mastered` 解释为「模型预测已掌握」。

**禁止**让 `review_due` 来自未来模型预测。当前 `review_due` 只能来自：

```text
真实 mastered/learned timestamp + review_due_at + 确定性复习规则
```

`model_dependency = NO`。

---

## 4. 未来模型能力（FUTURE / UNVERIFIED 全表）

见 §2.D。补充：`user_knowledge_progress` 中以下字段是**为未来模型预留的 schema 占位**，当前未被任何模型写入，不得在 UI 中展示为「AI 已评估」：

- `ai_recommended_status`
- `ai_assessment`

`system_suggested_status` 当前由**规则**写入（练习达标 → 状态），不是模型。

---

## 5. 产品级契约（PRODUCT-LEVEL CONTRACTS）

未来为模型预留的是**产品需要什么信息**，而不是**某个模型的具体契约**。

| 产品契约 | 描述产品需要的语义 |
|---|---|
| `LearnerStateEstimate` | 用户对某知识点的状态估计（掌握/未掌握/需复习 + 置信度） |
| `NextLearningAction` | 下一步学习行动（哪个知识点 / 哪种行动 / 为什么） |
| `QuestionDifficultyEstimate` | 题目相对难度估计 |
| `LearningRecommendation` | 学习内容推荐 |
| `ProgrammingDiagnosis` | 编程错误 / 薄弱点诊断 |

**禁止**在这些契约中定义具体模型细节：tensor、hidden state、checkpoint、prompt、embedding dimension、specific model API。契约只描述**语义输入输出**。

---

## 6. 来源溯源（SOURCE PROVENANCE）

所有未来 inference-like 结果必须能区分来源。标准来源至少：

```text
USER     用户显式输入/确认
OBSERVED 客观观察到的行为结果
RULE     确定性规则推导
MODEL    模型推断（未来）
```

必要时未来支持 `model_id` / `model_version` / `confidence` / `generated_at`。

**当前不要为了未来字段大规模修改数据库** —— 只定义契约与边界。

---

## 7. 降级策略（FALLBACK STRATEGY）

每个未来模型能力必须同时定义两种状态：

```text
MODEL AVAILABLE   → 使用模型输出（增强）
MODEL UNAVAILABLE → 明确降级（不返回假模型结果）
```

以「Next Action」为例：

| 状态 | 行为 |
|---|---|
| 当前 | deterministic structural next / 用户显式行动 |
| 未来 | 模型推荐 |
| 模型不可用 | 降级到 rule / structural / no recommendation，**不得返回假模型推荐** |

---

## 8. UI 语义边界

### 当前允许的文案

```text
下一知识点
课程中的下一项
待复习
你的练习结果
你已完成
```

### 当前禁止的文案（除非真实模型已验证提供）

```text
AI 为你推荐
最适合你
预计掌握率
根据你的能力预测
智能学习路径
预计提升 XX%
模型判断你已经掌握
```

> 现有 UI（如 exam-slice 的「这是从真实课程树顺序得出的结构性下一步，并非 AI 推荐」）符合本边界，应保持。

---

## 9. 面向未来训练的数据采集

模型未完成 ≠ 现在什么都不做。当前应保证未来训练所需**事实数据**可持续积累。

现有已具备的事件 / 尝试 / 进度数据：

| 数据 | 承载 |
|---|---|
| 练习尝试 / 对错 | `exam_practice_attempts`、`past_paper_attempts`、`question_attempts`、`code_challenge_attempts` |
| 错题 | `exam_wrong_questions`、`past_paper_wrong_questions` |
| 进度状态 / 时间戳 | `user_knowledge_progress` |
| 学习事件 | `knowledge_progress_events`、`learning_records` |
| 对话 / 代码消息 | `chat_messages`、`code_ai_messages` |
| 提交 / 判题 | `programming_exercise_submissions` |
| AI 用量 | `ai_usage_logs` |

未来训练至少要能重建：

```text
user
context
knowledge_point
action
timestamp
outcome
```

对应事件至少覆盖：

```text
knowledge point opened
learning started
practice attempted
answer correct / incorrect
review completed
material opened
AI question asked
code submitted
test passed / failed
```

**缺口**（当前未显式记录，未来逐步补齐，但不要为了未知模型提前制造复杂 feature table）：

- `response_time`（响应时间）
- `hint_used` / `ai_help_used`（是否用了提示 / AI 帮助，当前仅 `ai_usage_logs` 有粒度较粗的 AI 用量）
- 统一的「学习事件」schema（当前事件分散在多张业务表）

**原则**：优先保存 **RAW / SEMANTIC EVENTS**，未来训练时再构造 features。

---

## 10. Phase 4B-2A 边界（Learner State）

下一阶段 **Phase 4B-2A Learner State** 当前只允许实现：

```text
canonical knowledge point
+ authenticated user
+ 真实 user_knowledge_progress
+ 四个确定性产品状态（not_started / learning / mastered / review_due）
```

**禁止**（本阶段不实现）：

```text
Knowledge Tracing
mastery probability
prediction
recommendation
personalized ranking
```

---

## 11. Claude / Codex 职责边界

### Claude（工程实现）

**允许实现**：

- deterministic product logic
- API
- DB
- telemetry（事件 / 用量计量）
- model adapter interface（模型适配接口层，为未来模型预留）

**禁止**：模型不存在时实现 fake model output。

### Codex（视觉设计）

- 只负责视觉设计。
- 设计稿中**不得自行创造**：mastery score、AI recommendation、prediction、model-generated learner state。
- 除非任务明确提供真实数据 contract，否则设计稿一律使用确定性 / 结构性文案。

---

## 12. Change Log

| 版本 | 日期 | 变更 |
|---|---|---|
| V1 | 2026-09-12 | 首次建立模型能力边界基准（MODEL-INDEPENDENT FOUNDATION） |
