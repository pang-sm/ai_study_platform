---
description: 前端 UI/UX 强制规范 —— 仅对 frontend/ 下的文件生效
paths:
  - frontend/**
---

# 前端 UI/UX 规范

处理 `frontend/**` 下的任何文件时，必须遵守以下流程。视觉规则见
`docs/UI_DESIGN_SPEC.md`，本规则是执行入口。

> **权威层级**：唯一最高权威是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> `docs/UI_DESIGN_SPEC.md`、`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md` 与 `docs/**` 其余文件
> 全部**从属于** SSOT；冲突时 SSOT wins。
> 前端当前状态见 SSOT §3 与 §38：`OLD_FRONTEND_RESURRECTED = NO`，全新前端 = `NOT_STARTED`。

## 处理流程（按顺序）

> 设计任何页面/组件前，必须先建立视觉概念。**禁止直接从 requirements → Card/Grid → JSX。**

1. 读取 `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`（视觉方向）。
2. 读取 `docs/UI_DESIGN_SPEC.md` 中与当前任务相关的规范章节。
3. 确定当前页面/组件的 **Primary User Task**（用户此刻要完成的一件事）。
4. 写出页面 **Visual Concept**（What is the visual idea of this page?）。
5. 确定 **focal element**（页面视觉焦点）。
6. 确定 **content visual**（内容视觉载体：学科插图 / 课程封面 / 路径 / 图示）。
7. 确定 **composition**（构图：对称/非对称、分层、节奏）。
8. 检查当前 Design Token implementation 是否已存在：
   - 若已存在：必须复用现有 token，不得为单个页面创造孤立视觉值；但允许按品牌强度体系 / 领域 accent 建立必要 token。
   - 若处于 frontend 初始化阶段：先根据 `docs/UI_DESIGN_SPEC.md` 建立统一 token system，再开发具体页面。
   - Token implementation 的具体位置由 frontend architecture 决定，不预先固定路径。
9. 检查 `reference/`（含 `reference/LOGO/`、`reference/PAGE/`、`reference/UI/`）中是否有相关设计参考。
   该目录受保护，不得删除 / 重命名 / 移动 / 覆盖。
   注意：历史文档提到过的 `design/`、`design-references/` **当前已不存在**，不要再引用。
10. 优先复用 shared components（若已存在）。
11. 优先复用 design tokens。
12. 不随意新增颜色、圆角、shadow、spacing（遵守品牌强度体系，避免魔法值）。
13. 不使用无意义的 gradient / glass / glow。
14. 不 Card 套 Card；**Section ≠ Card**，只对真正需要边界的对象用 Card。
15. 不使用 emoji 代替 UI icon（统一使用 icon library）。
16. **不为视觉需求修改 backend。** 纯前端任务触碰 `backend/**` 即为 SCOPE_VIOLATION。
    注意：STEP 7 的后端实现 / 重构任务本身是**被授权的**，不受本条限制——本条只禁止
    「为了做 UI 而顺手改后端」。
17. 保持 responsive（Desktop / Tablet / Mobile）。
18. 保持 accessibility（contrast / focus / aria-label / alt / 非颜色状态）。
19. 修改完成后执行 UI checklist（见 `/frontend-review` skill 的 `checklist.md`）。

## 禁止的 AI-generated visual style

满屏蓝紫渐变、大面积 Glassmorphism、backdrop blur 滥用、发光边框、Neon
Glow、星空、科技网格背景、粒子动画、AI 机器人插画、大脑发光图片、芯片/机械手
等泛 AI 素材、Gradient Button/Text 滥用、Card 套 Card、所有内容都 Card 化、
大量 emoji 作图标、大量无意义 KPI、无意义 3D 图表、管理后台式学生首页。

## 文案

语言短、具体、明确、行动导向。禁止「开启智慧学习之旅 / AI 赋能未来 / 解锁学习
潜能」等模板化文案，使用真实学习语境（如「继续昨天的数据结构学习」）。

## 模型能力边界（视觉职责）

设计稿中**不得自行创造**：mastery score、AI recommendation、prediction、
model-generated learner state、掌握率、能力预测等。
除非任务明确提供真实数据 contract，否则一律使用确定性 / 结构性文案与状态
（如「待复习」「下一知识点」「你的练习结果」）。

**当前科学能力状态**：13 个 scientific component 全部为 `RUNTIME_ONLY`；
`SHADOW = 0 / ADVISORY = 0 / ACTIVE = 0`。`student_twin` 的 MVP 目标是
`SHADOW_ONLY`，**没有用户可见功能**，前端不得暴露任何 scientific component。

权威边界见 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` §35 / §36 / §49 / §72；
细化参考见 `docs/architecture/ZHIXUE_MODEL_CAPABILITY_BOUNDARY_V1.md`（从属于 SSOT）。
