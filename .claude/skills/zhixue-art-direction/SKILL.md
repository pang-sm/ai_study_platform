---
name: zhixue-art-direction
description: 智学平台正向视觉方向（Art Direction）执行入口。当任务涉及新页面、页面 redesign、homepage、dashboard、learning center、course page、exam page、programming page、onboarding、profile、content layout 等视觉设计时，必须先读取 docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md 建立 Visual Concept，再开始写代码。
---

# 智学平台视觉方向（ZhiXue Art Direction）

本 Skill 是智学平台**正向视觉方向**的执行入口。它不复制视觉方向基准，只负责强制「先建立
Visual Concept，再写代码」，并桥接通用 `frontend-design` Skill 与智学平台品牌。

## 强制流程（写代码之前）

1. 读取 `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md`（视觉方向 SSOT）。
2. 读取 `docs/UI_DESIGN_SPEC.md`（视觉规则与红线）。
3. 查看相关 `reference/UI/`、`reference/PAGE/`、`reference/LOGO/`（参考与品牌资产，Logo 不可修改）。
4. 调用并遵守通用 `frontend-design` Skill（distinctive visual identity、avoid SaaS-card kit、两遍法）。
5. 在写代码之前，明确输出内部 **design brief**：

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

6. 自检：**这个设计是否可能收敛成 Dashboard？**（KPI tiles / 同款白卡 / 灰进度条 / 网格面板 / 纯文字列表 / 灰底）。若「遮住 Logo 就像 admin/SaaS 后台」，则重新设计。

只有完成以上步骤后才能开始实现。

## 关键禁令

- 禁止直接从 requirements → Card/Grid → JSX。
- 禁止把「不要 AI 插画」误读成「不要任何视觉内容」。
- 禁止所有 section 都包成同款 rounded rectangle 卡片。
- 禁止只用一个主色 + 白卡 + 灰底表达所有层级。
