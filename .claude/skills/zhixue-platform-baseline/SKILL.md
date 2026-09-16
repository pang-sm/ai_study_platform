---
name: zhixue-platform-baseline
description: 智学AI 总体产品与技术架构 SSOT 入口。当任务涉及产品架构、页面信息架构、前端重构、后端模块、AI Gateway、Capability Router、Qualified Model Pool、OCR、文档解析、RAG、Data Plane、Scientific Runtime、Learning Context、统一会员、Usage Credits、数据库架构、新学科、新考试、编程学习架构等结构性设计与修改时，必须先读取根目录 ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md 再进行设计或修改。
---

# 智学AI 架构基准入口（ZhiXue Platform Baseline）

本 Skill 是智学AI **总体架构 SSOT** 的强制入口。当任务涉及架构级或结构性设计与修改时，
**必须先读取 SSOT，再进行设计或修改**。本 Skill 不复制完整架构，只负责强制引路与约束。

## 基准文档

- **唯一最高权威**：`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`（仓库根目录）
- 当前阶段权威状态块：SSOT `# 73. SSOT 状态`
- 次级参考（全部从属于 SSOT）：
  - `docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`（总体架构历史基准）
  - `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md`（学习体验 / IA 历史基准）
  - `docs/UI_DESIGN_SPEC.md`、`docs/FRONTEND_ARCHITECTURE.md`、`docs/FRONTEND_API_CONTRACT.md`

> **冲突规则**：SSOT 优先于本 Skill、`CLAUDE.md`、`AGENTS.md`、`.claude/**`、`docs/**` 及
> 任何历史文档。上述两份历史基准**已被 SSOT 取代**，不得再被声明为项目 SSOT。

## 强制规则

1. SSOT 优先于一切次级文档与旧设计说明。
2. **智学AI 不是三个网站**。三个 Learning Space（`course_learning` / `exam_11408` /
   `programming`）共享统一账户、统一会员、统一 Usage Credits、统一 Learning Core、
   统一 AI Layer、统一 Data Plane 与 Scientific Runtime。
   禁止拆成三个网站 / 三套会员 / 三套 AI / 三套 usage 余额。
3. 不得把业务代码绑定具体模型供应商。请求的是 **capability**，由
   `Permission / Budget → Qualified Model Pool → Router → Provider Gateway` 决定真实模型。
   Provider adapter（`backend/ai/providers/*`）是唯一允许出现 provider 名的地方。
4. Scientific Runtime 与 External AI Gateway 必须严格分层。
   Product Backend 不得直接 import `torch` / `transformers` / `faiss` / `zhixue_runtime`。
5. 不得把 OCR 等同于整个文档解析（必须走 Document Pipeline）。
6. 不得声称 `PLANNED` / `TARGET` 能力已经实现，也不得把 `PLANNED` 写成 `CURRENT`。
7. 不得改写 SSOT §36 冻结的科学语义（`student_twin` / `learner_state` / `irt` /
   `tutor_policy` / `tutor_guard` / `evidence_reliability` / `misconception_v2` / `memory`）。
8. `runtime pass != product ready`：任何 scientific component 必须通过 Productization Gate。
9. 新增学科优先采用数据驱动和配置化扩展（不复制一套前后端）。
10. 涉及架构偏离时必须先指出偏离，并说明原因。
11. 不得修改 `reference/`（含 `reference/LOGO/`）固定资源及文件名。
12. 后端处于 STEP 7 实现 / 重构阶段：`Preserve Capability != Preserve Architecture`。

## 执行流程

1. 读取 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`，先从 `# 73. SSOT 状态` 确认当前 STEP。
2. 确认当前任务涉及的能力处于 `CURRENT` / `FROZEN TARGET` / `NEXT` 的哪一类。
3. 若属 `TARGET` / `PLANNED`，明确指出为未实现，不得写成已部署。
4. 若任务要求偏离 SSOT，先指出偏离点与原因，再继续。
5. 若发现 SSOT 自身有过期段落，**报告用户**，不要自行回写。
