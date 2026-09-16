---
name: zhixue-ui-acceptance
description: 智学平台前端页面与组件完成后的最终 UI 验收流程。涉及页面视觉完成、前端重构验收、视觉一致性、Learning-first、响应式与可访问性检查时使用。
---

# ZhiXue UI Acceptance

## Authority

> **唯一最高权威是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。**
> 本 Skill 从属于 SSOT；冲突时 SSOT wins。
> 前端状态见 SSOT §3 / §38：全新前端 = `NOT_STARTED`，`OLD_FRONTEND_RESURRECTED = NO`。

## Purpose

用于智学AI 前端页面或组件完成后的最终 UI 验收。

这是 Acceptance Skill，不负责决定页面最初应该设计成什么样。

设计阶段应优先遵循：

- `zhixue-art-direction`
- `frontend-design`
- `frontend-ui` rule
- 根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` 与其余项目文档

本 Skill 负责回答：

> 当前实现是否达到智学平台 UI 验收标准？

最终必须输出：

```text
UI_ACCEPTANCE = PASS / FAIL
```

如果 FAIL，必须明确列出 blocker。

## Trigger

以下情况应使用本 Skill：

```text
页面开发完成
页面重构完成
大型组件完成
首页/课程/11408/编程页面准备验收
用户要求检查页面是否符合设计规范
准备提交前端 UI 改动
视觉回归检查
```

以下情况通常不需要：

```text
尚处于纯 brainstorm
尚未形成具体 UI
纯后端任务
纯数据库任务
```

## Acceptance Principles

验收优先级：

```text
Learning task
Information hierarchy
Product semantics
Visual direction
Interaction clarity
Consistency
Responsive behavior
Accessibility
Decorative polish
```

禁止为了“更漂亮”牺牲学习任务清晰度。

## 1. Visual Direction

确认页面符合智学当前视觉方向。

检查：

```text
页面是否有明确 visual idea
是否有自己的学习场景语义
是否延续智学品牌语言
是否避免 generic AI 产品感
是否避免模板化 SaaS dashboard 感
```

如果无法说明：

```text
What is the visual idea of this page?
```

则不能直接 PASS。

## 2. Learning-first

检查首屏是否优先回答：

```text
我现在学到哪里？
下一步学什么？
我现在应该做什么？
```

Current / Next / Action 是否清楚。

学习操作必须优先于：

```text
宣传文案
装饰插画
数据展示
次级业务入口
无实际用途的大 Banner
```

## 3. Surface / Card Eligibility

不是所有内容都应放进 Card。

检查：

```text
Section 是否被错误地全部做成 Card
是否存在 card-inside-card
是否出现大量同权重卡片
是否通过边界、留白、排版即可表达却仍用了卡片
Card 是否真正承担可操作或可分组语义
```

如果页面呈现明显“卡片墙”，应重点审查。

## 4. Brand Intensity

检查品牌元素强度是否合理：

```text
首页可较强
核心 Learning Space 可中等
深层学习页面应更克制
工具/设置/管理页面应更弱
```

不得所有页面都使用同样强度的品牌装饰。

## 5. Typography Hierarchy

检查：

```text
页面标题
Section 标题
正文
辅助说明
Metadata
Button text
```

是否有清晰层级。

禁止：

```text
所有文字接近同一权重
大面积粗体
过多超大标题
为视觉效果牺牲阅读效率
```

## 6. Token Usage

检查：

```text
是否优先使用 frontend/src/styles/tokens.css
是否存在无理由 magic value
色彩、圆角、间距是否与 token 系统一致
是否重复创造已有 token
```

注意：

```text
不得为了验收擅自把当前 token 改回旧 spec。
```

如果发现 token 与 spec 不一致：

```text
TOKEN_DRIFT_REVIEW_REQUIRED = YES
```

说明差异，不自动修改。

## 7. Button Hierarchy

确认：

```text
页面 Primary Action 是否唯一且明显
Secondary Action 是否降级
Tertiary Action 是否不过度抢眼
不应出现多个视觉上同权重的主按钮
```

按钮文案应表达真实动作，不使用模糊营销措辞。

## 8. Card Nesting

重点检查：

```text
card
  └─ card
      └─ card
```

这种结构原则上应避免。

允许嵌套时必须有明确的信息层级理由。

## 9. Gradient Abuse

检查：

```text
是否使用不必要渐变
是否存在 AI 产品常见紫蓝渐变套路
渐变是否真正承担品牌或空间语义
```

无理由渐变应视为问题。

## 10. Responsive

至少检查：

```text
Desktop
Tablet
Mobile
```

重点：

```text
内容优先级是否保持
主要操作是否仍然明显
是否横向溢出
表格/图表是否降级合理
Header / navigation 是否合理变化
是否只是简单缩小 Desktop 页面
```

## 11. Loading / Empty / Error

任何依赖异步数据的核心区域，应考虑：

```text
loading
empty
error
```

不得只实现 happy path。

状态视觉应与主页面一致，不另起一套风格。

## 12. Accessibility

至少检查：

```text
semantic HTML
button/link 语义
keyboard accessibility
focus state
form label
contrast
icon accessible name
reduced motion（若存在显著动画）
```

不得只依赖颜色传达关键状态。

## 13. Dashboard Detection

这是硬性检查。

执行以下判断：

```text
删除 Logo 和品牌名称后，这个页面是否仍然像一个典型 admin/SaaS dashboard？
```

如果答案是 YES：

```text
DASHBOARD_DETECTION = FAIL
```

通常意味着：

```text
卡片过多
KPI 化严重
数据优先于学习任务
左侧导航 + 卡片网格模板化
generic SaaS 视觉语言过重
```

除非该页面本身确实是后台管理页面，否则不能 PASS。

## 14. Backend Scope Check

UI 修改后检查是否意外修改：

```text
backend/
API semantics
database schema
authentication
unrelated business logic
```

如果本任务明确为纯前端，出现无理由 backend 改动：

```text
SCOPE_VIOLATION = YES
```

注意：**后端在 STEP 7 本身处于被授权的实现 / 重构阶段**（`main.py` = REFACTOR / EXTRACT）。
本项只惩罚「UI 任务顺手改后端」。若当前任务本身就是 STEP 7 后端任务，则不适用本项。

## 15. AI-generic Detection

检查是否出现典型 AI-generated UI 痕迹：

```text
紫蓝渐变
过量 glow
大量 glassmorphism
无意义浮动球体
大面积 rounded cards
图标 + 标题 + 描述三列模板
过量 dashboard widgets
空洞 Hero 文案
“未来感”装饰压过产品语义
所有模块长得像同一组件复制
```

如果明显存在：

```text
AI_GENERIC_VISUAL = FAIL
```

## Runtime Verification

Shell 和浏览器环境可用时，应执行：

```bash
npm run check
npm run build
```

必要时：

```bash
npm run test:e2e
```

并进行实际页面视觉检查。

如果 Shell 或浏览器不可用，不得伪造结果。

明确标记：

```text
RUNTIME_UI_VALIDATION_PENDING = YES
```

## Acceptance Output

最终必须输出：

```text
ZHIXUE_UI_ACCEPTANCE_REPORT

VISUAL_DIRECTION = PASS / FAIL
LEARNING_FIRST = PASS / FAIL
SURFACE_CARD_ELIGIBILITY = PASS / FAIL
BRAND_INTENSITY = PASS / FAIL
TYPOGRAPHY = PASS / FAIL
TOKEN_USAGE = PASS / FAIL
BUTTON_HIERARCHY = PASS / FAIL
CARD_NESTING = PASS / FAIL
GRADIENT_USAGE = PASS / FAIL
RESPONSIVE = PASS / FAIL / NOT_VERIFIED
STATE_COVERAGE = PASS / FAIL
ACCESSIBILITY = PASS / FAIL / NOT_VERIFIED
DASHBOARD_DETECTION = PASS / FAIL
BACKEND_SCOPE = PASS / FAIL
AI_GENERIC_VISUAL = PASS / FAIL

BLOCKERS =
- ...

RUNTIME_UI_VALIDATION_PENDING = YES / NO

UI_ACCEPTANCE = PASS / FAIL
```

只有不存在 blocker 时才能输出：

```text
UI_ACCEPTANCE = PASS
```

不得为了“总体看起来还不错”忽略硬性失败项。
