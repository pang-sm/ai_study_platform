# 智学平台学习体验与信息架构基准（ZHIXUE LEARNING EXPERIENCE BASELINE）

> ## ⚠️ 权威状态：已被取代（SUPERSEDED）
>
> **本文档不再是项目 SSOT。** 唯一最高权威是仓库根目录
> **`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`**。
>
> 冲突时 **SSOT wins**。本文档保留为历史学习体验 / IA 基准，仅在 SSOT 未覆盖的细节上作为参考。
>
> 已被 SSOT 明确改写之处（不得再按本文档执行）：
> - 用户侧信息架构以 SSOT §12（`首页 / 学习 / 资料 / 练习 / AI / 计划 / 我的`）为准。
> - `LearnerState` 语义以 SSOT §36.13 为准：输出是 **next-response `P(correct)`**，
>   不是 mastery probability。
> - 模型路线以 SSOT §36 的 13 个 Scientific Component 为准（本文档的 `ZhiXue-KT` 阶段划分已过时）。
> - 当前阶段以 SSOT `# 73. SSOT 状态` 为准（`CURRENT_STEP = STEP_7`）。

- **Title**：智学平台学习体验与信息架构基准
- **Version**：V1.0
- **Status**：SUPERSEDED by `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`
- **Date**：2026-09-10
- **Scope**：Learning-first 产品架构、信息层级、Homepage IA、Course IA、Exam IA、Programming IA、LearningContext / LearningNode / LearnerState / LearningAction / NextBestAction、Capability 角色、模型集成方向

> 层级（现行）：`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`（唯一权威）→ 本文档与 `ZHIXUE_PLATFORM_BASELINE`（历史参考）→ `ZHIXUE_VISUAL_DIRECTION`（视觉方向）→ `UI_DESIGN_SPEC`（视觉规则）。

---

## 1. 核心原则：Learning-First Architecture

智学平台首先是 **Personal Learning Space（个人学习空间）**，而不是：

- Feature Portal（功能门户）
- Dashboard
- Module Directory（模块目录）

用户进入平台后，产品首先回答：

1. 我现在正在学什么？
2. 我学到哪里了？
3. 下一步应该做什么？
4. 如何立即继续？
5. 后续学习路径是什么？

**平台能力和功能入口属于 supporting capabilities（辅助能力）。**

---

## 2. 统一产品语法

全平台统一信息语法：

```text
CURRENT   当前状态
   ↓
NEXT      下一步
   ↓
ACTION    立即行动
   ↓
PATH      学习路径
   ↓
TOOLS     辅助工具
```

这个结构必须成为 **首页 / 考研 / 课程 / 编程** 共同的产品语法。

---

## 3. 三大 Learning Worlds（保持不变）

```text
智学平台
├── 考研学习
├── 课程学习
└── 编程学习
```

三大业务**保持不变**，它们是三个 **Learning Worlds**。

- 对于已有学习记录的用户：**Current Learning 与 Next Action 的优先级高于重新选择 Learning World**。
- 三大 Learning World 是 secondary exploration layer（次级探索层），不是首页第一焦点。

---

## 4. Homepage：Personal Learning Home

登录首页正式定义为 **Personal Learning Home**。优先级：

1. Current Learning（当前学习）
2. Next Best Action（下一步最佳行动）
3. Active Learning Paths（进行中的学习路径）
4. Explore ZhiXue（探索三大方向，摘要）
5. Today Actions（今日行动）
6. Supporting Metrics（辅助统计）

**不要**再把「三大业务目录」或「学习 KPI」作为第一视觉焦点。

首页第一屏必须优先服务：**继续学习**。

### Homepage Content Policy

首页只做**摘要**，不展开完整 taxonomy：

```text
考研学习   11408 · 数学 · 英语 · 联考
课程学习   数学物理 · 计算机 · 电子信息 · 自动化
编程学习   C · C++ · Java · Python
```

完整目录进入 **Exam Center / Course Center / Programming Center / Explore**。

---

## 5. Course Learning Architecture

课程页核心结构：

```text
Course
 ↓
Current Learning（当前学到哪）
 ↓
Next Action（下一步行动）
 ↓
Learning Path（学习路径）
 ↓
Supporting Tools（辅助工具）
```

示例（线性代数）：

- 当前：第三章 · 矩阵 → 矩阵的秩
- 下一步：矩阵秩基础练习 → [继续学习]
- Learning Path：行列式 ✓ / 矩阵 ● / 向量组 ○ / 线性方程组 ○ / 特征值 ○
- Supporting Tools：资料 / AI 问答 / 练习 / 错题 / 知识脉络

**Supporting Tools 不能再成为课程首页的第一层内容。**

---

## 6. Exam Learning Architecture

考研页统一：

```text
Exam Target
 ↓
Current Stage
 ↓
Current Learning
 ↓
Next Action
 ↓
Exam Path
 ↓
Supporting Tools
```

示例（2027 计算机考研 · 11408）：

- 当前阶段：基础强化
- 当前：操作系统 · 虚拟内存
- 下一步：完成知识学习 + 8 道真题 → [继续备考]

Exam 特有能力：**真题、考纲权重、阶段规划、薄弱点、复习计划**，继续保留业务特点。

---

## 7. Programming Architecture

编程页统一：

```text
Programming Track
 ↓
Current Skill
 ↓
Next Coding Action
 ↓
Skill Path
 ↓
Execute
 ↓
Feedback
 ↓
Next Action
```

示例（Python）：

- 当前：函数与模块
- 下一步：完成三个函数编程练习 → [继续编程]

核心仍然是：**Sandbox、Compiler、Tests、AI Feedback**。不要把编程强行设计成普通课程。

---

## 8. Learning Experience Core Entities

正式加入以下产品/技术概念（本轮只建立 architecture concept，**不落数据库**）：

- **LearningContext** —— 用户当前学习上下文，如 `course / linear_algebra`、`exam / 11408`、`programming / python`。

- **LearningNode** —— 可学习节点，可以是 Chapter / KnowledgePoint / PracticeSet / ProgrammingSkill / ExamModule / ReviewTask。

- **LearnerState** —— 用户对节点的学习状态，至少支持：
  ```text
  not_started / learning / mastered / review_due
  mastery / last_activity / attempt_count
  ```

- **LearningAction** —— 系统建议或用户执行的学习动作，初始 taxonomy：
  ```text
  LEARN / PRACTICE / REVIEW / READ / CODE / EXAM_PRACTICE / ASK_AI
  ```

---

## 9. Next Best Action

正式定义 **NextBestAction** 作为未来核心能力：

```text
user / context / action_type / target / reason / priority / estimated_time
```

示例：

```text
action_type = REVIEW
target      = 矩阵求逆
reason      = 是当前知识点的前置知识，且近期掌握度下降
estimated_time = 15 min
```

Homepage / Course / Exam / Programming 未来都消费 **Next Action Service**。

---

## 10. Recommendation Evolution

> ⚠️ **本节已过时（historical）**。下文 `ZhiXue-KT` / `ZhiXue-Ranker` 命名已被
> `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` §36 的 13 个 Scientific Component 取代。
> 现行产品化顺序见 SSOT §57（第一优先级 = `student_twin`）与 SSOT §36 最终分类。
> 保留本段仅作历史记录，不得据此设计。

目标路线：

```text
Phase 1   Rule-based Next Action
   ↓
Phase 2   ZhiXue-KT + Rules
   ↓
Phase 3   ZhiXue-KT + ZhiXue-Ranker
   ↓
Phase 4   Learning Policy / Agent
```

不修改现有自研模型路线，只明确它们最终服务 **Next Best Action**，而不是只生成一个掌握度数字。

---

## 11. Capability Layer

AI 问答 / RAG / 资料 / 题目 / 真题 / 错题 / 知识图谱 / Sandbox / 学习计划 / 复习，属于 **Learning Capabilities**，不是整个产品最顶层的学习逻辑。

关系：

```text
Learning Experience
   ↓
Learning Action
   ↓
Capability
```

例如：Next Action = 学习「矩阵的秩」→ 调用 Knowledge Graph + RAG + LLM + Practice 完成整个学习动作。

---

## 12. Knowledge Graph role

Knowledge Graph 不只是一个用户点击的页面功能，它同时是 **Learning Path / Prerequisite / Recommendation / KT context / RAG filtering** 的底层结构。

UI 仍可提供「知识脉络」页面，但架构上它属于**核心数据能力**。

---

## 13. AI / LLM role

LLM 负责：理解、解释、生成、辅导、总结。

学习策略主要由 **Learner State + Knowledge Graph + KT + Recommendation + Rules** 共同决定。

**禁止**把「问 LLM 下一步学什么」作为整个个性化系统的唯一实现。

---

## 14. Global Navigation Target

记录目标 IA：

```text
首页   我的学习   探索   资料   学习计划
右侧：搜索   会员   用户
```

- 「错题」长期可逐步下沉为 Review / Learning Capability；当前已有错题功能**不删除**，具体迁移以后单独设计。
- 本轮不修改前端导航。

---

## 15. User-facing Completeness

面向最终目标产品的信息架构：不展示内部研发状态（已开发 / 未开发 / 即将上线 / 持续开放中）。

正式 production 中未实现的交互，**不得制造假接口或错误可点击行为**。

---

## Baseline Change Log

| Version | Date | Change | Reason |
| --- | --- | --- | --- |
| V1.0 | 2026-09-10 | Initial baseline | 从 module-first 升级为 learning-action-first 的学习体验架构 |
