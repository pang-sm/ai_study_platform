---
name: zhixue-art-direction
description: 智学平台正向视觉方向（Art Direction）执行入口。当任务涉及新页面、页面 redesign、homepage、dashboard、learning center、course page、exam page、programming page、onboarding、profile、content layout 等视觉设计时，必须先读取 docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md 建立 Visual Concept，再开始写代码。
---

# 智学AI 视觉方向（ZhiXue Art Direction）

本 Skill 是智学AI **正向视觉方向**的执行入口。它不复制视觉方向基准，只负责强制「先建立
Visual Concept，再写代码」，并桥接通用 `frontend-design` Skill 与智学AI 品牌。

> **权威层级**：唯一最高权威是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本 Skill、`docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`、`docs/UI_DESIGN_SPEC.md` 及其余
> 次级文件全部从属于 SSOT；冲突时 SSOT wins。
> 前端状态见 SSOT §3 / §38：全新前端 = `NOT_STARTED`，`OLD_FRONTEND_RESURRECTED = NO`。

## 强制流程（写代码之前）

1. 读取 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`（§3 前端原则、§12 用户侧信息架构 TARGET、§73 当前阶段）。
2. 读取 `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md`（学习体验 / IA 参考）。
3. 读取 `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`（视觉方向）。
4. 读取 `docs/UI_DESIGN_SPEC.md`（视觉规则与红线）。
5. 查看相关 `reference/UI/`、`reference/PAGE/`、`reference/LOGO/`（参考与品牌资产，禁改 / 删 / 移 / 覆盖）。
6. 调用并遵守通用 `frontend-design` Skill（distinctive visual identity、avoid SaaS-card kit、两遍法）。
7. 在写代码之前，明确输出内部 **design brief**：

```text
Primary task        —— 用户此刻要完成的一件事
Visual concept      —— 本页面的视觉想法（一句话）
Focal element       —— 页面第一视觉焦点
Composition         —— 构图（对称/非对称、分层、节奏）
Content visual      —— 内容视觉载体（插图/封面/路径/图示）
Surface strategy    —— CANVAS / EDITORIAL / FOCUS / OBJECT 如何分配
Typography strategy —— 层级如何拉开（不只 16/18/20px 小变化）
Interaction character —— hover / focus / motion 的性格
Mobile adaptation   —— 移动端如何重新构图（不是 desktop 纵向堆叠）
```

8. 自检：**这个设计是否可能收敛成 Dashboard？**（KPI tiles / 同款白卡 / 灰进度条 / 网格面板 / 纯文字列表 / 灰底）。若「遮住 Logo 就像 admin/SaaS 后台」，则重新设计。

只有完成以上步骤后才能开始实现。

## 关键禁令

- 禁止直接从 requirements → Card/Grid → JSX。
- 禁止把「不要 AI 插画」误读成「不要任何视觉内容」。
- 禁止所有 section 都包成同款 rounded rectangle 卡片。
- 禁止只用一个主色 + 白卡 + 灰底表达所有层级。
- 禁止恢复旧前端页面，或从旧 frontend 复制 UI（SSOT §3.2）。
- 禁止在 UI 中暴露 scientific component 或伪造模型输出（SSOT §35 / §49 / §72）。
