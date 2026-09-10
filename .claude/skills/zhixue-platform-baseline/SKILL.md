---
name: zhixue-platform-baseline
description: 智学平台总体产品与技术架构基准入口。当任务涉及产品架构、页面信息架构、前端重构、后端模块、AI API、DeepSeek、Model Gateway、OCR、文档解析、RAG、Embedding、Reranker、Knowledge Graph、学习数据、KT、推荐模型、模型训练、数据库架构、新学科、新考试、编程学习架构等结构性设计与修改时，必须先读取 docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md 再进行设计或修改。
---

# 智学平台架构基准（ZhiXue Platform Baseline）

本 Skill 是智学平台**总体架构基准**的入口。当任务涉及架构级或结构性设计与修改时，
**必须先读取基准文档，再进行设计或修改**。本 Skill 不复制完整架构，只负责强制引路与约束。

## 基准文档

- 唯一权威：`docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`
- 前端视觉规范：`docs/UI_DESIGN_SPEC.md`
- 前端工程架构：`docs/FRONTEND_ARCHITECTURE.md`

## 强制规则

1. 基准文档优先于旧的零散设计说明。
2. 不得静默改变一级产品结构（考研学习 / 课程学习 / 编程学习三大一级业务）。
3. 不得把业务代码直接绑定具体模型供应商（模型名由 Model Gateway / Model Registry 决定）。
4. 不得把 OCR 等同于整个文档解析（必须走 Document Pipeline）。
5. 不得声称 PLANNED 能力已经实现。
6. 新增学科优先采用数据驱动和配置化扩展（不复制一套前后端）。
7. 涉及架构偏离时必须先指出偏离，并说明原因。
8. 不得擅自修改 `reference/LOGO/` 固定资源及文件名。

## 执行流程

1. 读取 `docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`。
2. 确认当前任务涉及的能力处于 CURRENT / TARGET / MIGRATION 的哪一类。
3. 若属 TARGET / PLANNED，明确指出为未实现，不得写成已部署。
4. 若任务要求偏离基准，先指出偏离点与原因，再继续。
