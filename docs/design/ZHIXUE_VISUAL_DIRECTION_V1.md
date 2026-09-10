# 智学平台视觉方向基准（ZHIXUE VISUAL DIRECTION）

- **Title**：智学平台视觉方向基准
- **Version**：V1.0
- **Status**：BASELINE
- **Date**：2026-09-10

## Purpose

本文件定义：**「智学平台应该呈现怎样的视觉人格与构图语言。」**

它不是产品架构文件、不是 CSS token 文件、不是 component API、也不是单个页面设计。

它的层级位置：

```text
ZHIXUE_PLATFORM_BASELINE（总体架构）
        ↓
ZHIXUE_LEARNING_EXPERIENCE_BASELINE（学习体验/IA）
        ↓
ZHIXUE_VISUAL_DIRECTION（本文档，视觉人格）
        ↓
UI_DESIGN_SPEC（视觉规则与红线）
        ↓
Page（页面设计）
        ↓
Component（组件实现）
```

本文档是**视觉方向 Single Source of Truth**。`docs/UI_DESIGN_SPEC.md` 应引用本文档，
而本文档不复制 UI_DESIGN_SPEC 的工程规则。

> **视觉层级必须遵循学习体验的信息优先级**：`Current > Next > Action > Path > Tools`。
> 视觉设计不能把 Tools / Dashboard metrics / directory 重新放到 Current Learning 前面。
> 权威 IA 见 `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md`。

---

## 1. Visual Concept

正式命名：**ZhiXue Academic Journey（智学 · 学术学习旅程）**

核心定义：智学平台**不是一个学习数据 Dashboard**，而是一个**持续展开的个人学习空间**。

页面应该让学习者感受到：

- 我在哪里
- 我正在学什么
- 下一步是什么
- 我的知识正在如何展开
- 不同学习方向之间有什么结构

核心关键词（正向概念）：

| 英文 | 中文 |
| --- | --- |
| Progression | 进展 |
| Knowledge | 知识 |
| Path | 路径 |
| Structure | 结构 |
| Focus | 专注 |
| Academic | 学术 |
| Exploration | 探索 |

视觉表达必须围绕这些正向概念建立，而不是围绕「数据展示 / 入口清单 / 状态表格」。

---

## 2. Brand Motif（品牌母题）

现有 `reference/LOGO/` 四张 Logo 是品牌视觉源头（**不可修改**）。从 Logo 抽象以下视觉母题：

1. **Open Pages** —— 层叠展开的书页（知识翻开、层层深入）。
2. **Upward Motion** —— 从中心向上的成长感（持续进步）。
3. **Branching** —— 左右展开形成不同学习方向（三大业务）。
4. **Central Path** —— 中心主轴代表持续学习过程（继续学习 / 路径）。
5. **Spark** —— 仅在**非常重要的达成/高光节点**少量使用（达成、里程碑）。

**禁止**简单到处复制 Logo 图标。应抽象 Logo 的 **geometry（几何）、layering（层叠）、
directional movement（方向感）、blue/cyan relationship（蓝青关系）**，形成 UI 语言。

---

## 3. 正向 Art Direction

页面优先使用：

- strong typography hierarchy（强排版层级）
- asymmetric composition where useful（有用的非对称构图）
- layered sections（分层 section）
- visual progression（视觉进展）
- knowledge / path diagrams（知识 / 路径图示）
- course / subject visual objects（课程 / 学科视觉对象）
- meaningful iconography（有含义的图标）
- deliberate whitespace（克制的留白）
- varied content density（有变化的内容密度）
- strong focal area（明确的视觉焦点）

**而不是**：

- identical cards everywhere（到处同款卡片）
- dashboard KPI grids（KPI 网格）
- generic SaaS sections（模板化 SaaS 区块）
- text-only category lists（纯文字分类列表）

设计者必须首先问：**「What is the visual idea of this page?」**

在没有明确 Visual Concept 之前，**禁止直接开始写 JSX / CSS。**

---

## 4. Surface System

建立至少四种 Surface（Section ≠ Card）：

| Surface | 用途 | 视觉特征 |
| --- | --- | --- |
| **CANVAS** | 页面基础背景 | 最浅背景，承载一切 |
| **EDITORIAL** | 标题、说明、内容组织 | 通常**不需要**卡片边框，靠排版与留白组织 |
| **FOCUS** | 最重要的学习行动或阶段 | 更强的品牌视觉权重（品牌蓝/母题），页面焦点 |
| **OBJECT** | 真正独立可操作的学习对象（课程、任务、资料、练习） | 有边界、可点击、有独立视觉载体 |

**明确规定：Section ≠ Card。** 不得因为布局方便把每个 section 都包装成 rounded rectangle。

---

## 5. Card Eligibility（卡片资格）

Card 只用于：

- 独立可点击对象
- 独立任务
- 独立资源
- 必须明确建立边界的交互单元

以下内容**默认不使用 Card**：

- Section title
- ordinary description（普通说明）
- simple taxonomy（简单分类）
- decorative grouping（装饰性分组）
- general page region（一般页面区域）

新增 frontend review 检查：**「这个 Card 是否真的需要边界？」** 如果 NO，移除 Card。

---

## 6. Color Intensity System（颜色强度体系）

**不要删除现有 semantic colors。** 在其上建立品牌强度体系。

Brand 至少包含五个强度层级（由现有 Logo 蓝 + 蓝青关系推导，具体值由 Design System 落地）：

```text
Brand Subtle   —— 最浅蓝（现 primary-soft 语义）
Brand Soft     —— 浅蓝
Brand Default  —— 主蓝 #2563EB
Brand Strong   —— 深蓝 #1D4ED8
Brand Emphasis —— 更深蓝（仅用于最强焦点/达成）
```

不要只存在一个 `#2563EB`。强度层级让「重要程度」可用颜色表达，而不是所有蓝都一个权重。

同时建立**有限的 domain accents**（仅辅助识别领域，整体仍属统一智学品牌）：

```text
Exam / 考研       → deep blue / indigo family（深蓝/靛）
Course / 课程     → teal family（青绿）
Programming / 编程 → blue-violet family（蓝紫）
```

**禁止让三大业务看起来像三个网站。** Accent 只是识别辅助，不是主题切换。

---

## 7. Typography

Typography 是核心视觉载体。至少定义并拉开层级：

```text
Display（超大，hero 级）
Page Title
Section Title
Object Title（课程/对象标题）
Body
Meta
Label
```

不同层级必须**同时**通过 font-size、weight、line-height、spacing、measure 建立明显差异，
不要只靠 16px / 18px / 20px 的小幅变化。

优先使用项目当前可靠可加载字体，**不要为了视觉效果引入不可控远程字体依赖**。

---

## 8. Content Visuals（内容视觉载体）

明确**允许并鼓励**：

- subject artwork（学科插图）
- course cover（课程封面）
- abstract academic diagrams（抽象学术图示）
- progression path（进展路径）
- milestone nodes（里程碑节点）
- geometric knowledge illustrations（几何知识插图）
- code-oriented visual objects（代码向视觉对象）
- meaningful diagrams（有含义的图表）

这些是 **Content Visuals（内容视觉）**，不是 **decorative filler（装饰填充）**。

仍禁止：

- generic AI robot
- glowing AI brain
- meaningless neural-network background
- stock AI illustration

以后页面**不能**因为「不要 AI 插画」错误推导出「不要任何视觉内容」。

---

## 9. Progress Visualization

学习进度**不能**只存在「percentage + blue progress bar」。

允许根据语境使用：

- path
- milestone
- node
- segmented progress
- compact bar
- ring
- chapter progression
- prerequisite graph

每种方式必须有明确语义。不要为了炫技做复杂数据可视化。

---

## 10. Domain Visual Grammar（三大业务视觉语法）

| 领域 | 核心概念 | 视觉语言 |
| --- | --- | --- |
| 考研 | Target / Milestone / Stage | 目标、阶段、里程碑、路径 |
| 课程 | Knowledge / Structure / Connection | 层次、知识结构、关联、章节 |
| 编程 | Build / Execute / Iterate | 代码、运行、结构、反馈 |

三类必须能被感知为**不同学习模式**，但保持统一品牌语言。

---

## 11. Dashboard Detection

如果页面同时大量存在：

- KPI tiles
- identical white bordered cards
- generic progress bars
- grid panels
- text lists
- gray canvas

即使 spacing 正确、token 正确、responsive 正确、a11y 正确，**仍然不能自动 PASS**。

必须问：**「如果删除 Logo，这个页面是否看起来像任何一个 admin / SaaS dashboard？」**

如果 YES → **Visual Design FAIL。**

---

## Baseline Change Log

| Version | Date | Change | Reason |
| --- | --- | --- | --- |
| V1.0 | 2026-09-10 | Initial baseline | 建立正向视觉方向，修正纯 avoid-list 导致的 dashboard 偏置 |
