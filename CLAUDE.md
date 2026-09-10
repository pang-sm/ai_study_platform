# CLAUDE.md

智学平台（智学AI）项目。技术栈：前端 React + Vite，后端 FastAPI，数据库 SQLite。

## 当前阶段

- 处于 **前端全量重构** 阶段。正式前端重建基线：commit `979025346210e23faaa3b80caa8bd8ddc8c0bad4`。
- frontend 目前 **尚未初始化**（`frontend/` 不存在）；完成总体设计后从零建立 React/Vite 前端。
- 不得恢复旧前端 UI。

## 核心约束（长期有效）

- 默认 **不得修改 backend**；保留现有 API、数据库、业务逻辑。
- 不因视觉重构删除任何现有真实业务能力。
- frontend 开发必须遵守 `docs/UI_DESIGN_SPEC.md`（UI 的唯一权威规范）。
- UI 以 **学习任务为核心**，不是功能入口集合，也不是 AI 官网。
- 避免 AI-generated visual style（无意义渐变 / Glassmorphism / 发光 / 星空 / 粒子等）。
- 使用统一 Design System；正式初始化 frontend 时先建立统一 design token，再开发具体页面。
- Reference 设计素材位于 `reference/`、`design/`、`design-references/`，不得随意删除、重命名、移动。
- 修改前先检查已有 shared components / tokens，避免重复建设。
- 页面完成后必须执行一次视觉一致性检查（可用 `/frontend-review`）。
- 涉及智学平台产品/技术架构设计或结构性重构时，遵循 `docs/architecture/ZHIXUE_PLATFORM_BASELINE_V1.md`，并使用 `zhixue-platform-baseline` Skill。
