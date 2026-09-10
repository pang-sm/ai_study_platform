# 智学平台 UI / UX 设计规范（Single Source of Truth）

> 本文档是智学平台全部前端 UI 的**唯一权威规范**。所有页面、组件、视觉决策都以本文件为准。
>
> 适用范围：前端全量重构阶段及之后所有前端工作。
> 配套执行入口：`.claude/rules/frontend-ui.md`（处理 frontend 代码时的强制流程）、`.claude/skills/frontend-review/`（页面完成后的 UI/UX 审核）。
> 设计 token 落地文件：`frontend/src/styles/tokens.css`。

---

## 0. 产品视觉定位

智学平台面向**高校学生**，核心分三块：

- **考研学习**：11408、数学、英语、政治，及后续其他考试与专业课。
- **课程学习**：数学、物理等通用基础课程；各专业课程；当前计算机专业内容重点保留。
- **编程学习**：编程语言学习、编程练习、在线运行、AI 编程辅助、学习进度与能力反馈。

整体设计语言：**专业、克制、清爽、年轻、学习导向**。

不要做成典型「AI 产品官网」。第一视觉目标**不是**「这个平台 AI 感很强」，而是：

> 「这是一个成熟、好用、知道我下一步该学什么的学习平台。」

---

## 1. UI 参考体系

以下产品**仅作为设计原则参考**，禁止逐像素复制。

| 参考对象 | 借鉴点 |
| --- | --- |
| Brilliant | 整体视觉克制、Typography、大量合理留白、页面节奏、互动学习感 |
| Khan Academy | 学习进度、掌握度、知识点状态、Next Step |
| Coursera | 课程大厅、课程卡片、搜索、分类体系 |
| Quizlet | 练习、错题、轻量 Card、学习工具 |
| Duolingo | **只借鉴** Learning Path / 学习路径 / Progressive Learning；**不照搬**卡通视觉与游戏化美术 |
| MIT OpenCourseWare | 资料库、内容组织、搜索、高信息密度页面 |
| Codecademy | 编程 Workspace、Tutorial + Editor + Result、学习上下文连续性 |

---

## 2. 强制 UI 原则

### 2.1 学习任务优先

每个页面首先要回答：

1. 用户现在在哪里？
2. 用户当前学到哪里？
3. 用户下一步应该做什么？

**不要**优先展示「平台有哪些功能」。

### 2.2 一屏一个主要任务

页面首屏只能存在**非常明确**的 Primary Action，例如：继续学习 / 开始练习 / 上传资料 / 运行代码。不要同时出现大量同权重 CTA。

### 2.3 避免典型 AI-generated UI

禁止无必要使用：

- 满屏蓝紫渐变、大面积 Glassmorphism、backdrop blur 滥用
- 发光边框、Neon Glow、星空、科技网格背景、粒子动画
- AI 机器人插画、大脑发光图片、芯片 / 机械手等泛 AI 素材
- Gradient Button 滥用、Gradient Text 滥用
- Card 套 Card、所有内容都 Card 化
- 大量 emoji 作为 UI icon
- 大量无意义 KPI、无意义 3D 图表
- 管理后台式学生首页

---

## 3. 颜色规范

### 3.1 基础 token

| Token | 值 |
| --- | --- |
| Primary | `#2563EB` |
| Primary Hover | `#1D4ED8` |
| Primary Soft | `#EFF6FF` |
| Success | `#16A34A` |
| Warning | `#F59E0B` |
| Danger | `#DC2626` |
| AI Accent | `#7C3AED` |
| Page Background | `#F8FAFC` |
| Surface | `#FFFFFF` |
| Primary Text | `#111827` |
| Secondary Text | `#4B5563` |
| Muted Text | `#6B7280` |
| Border | `#E5E7EB` |

软背景扩展（用于 badge / 进度底轨 / 提示背景）：Success Soft `#F0FDF4`、Warning Soft `#FFFBEB`、Danger Soft `#FEF2F2`、AI Soft `#F5F3FF`。

### 3.2 语义对照（颜色必须表达状态，而非装饰）

- **蓝色**：当前状态 / 主操作 / 链接 / 普通进度
- **绿色**：已学习 / 已完成 / 掌握 / 正确
- **橙色**：待复习 / 提醒
- **红色**：错误 / 删除 / 危险
- **灰色**：未开始 / Disabled / 次级信息
- **紫色**：仅作为 AI 功能辅助识别

**AI 紫色不得变成整个网站主色。**

---

## 4. Typography

### 4.1 字体栈

```
Inter, PingFang SC, Microsoft YaHei, system-ui, sans-serif
```

### 4.2 层级

| 层级 | 字号 |
| --- | --- |
| Hero | 48–56px |
| Page Title | 32–36px |
| Section Title | 24–28px |
| Card Title | 17–20px |
| Body | 14–16px |
| Metadata | 12–14px |

字体层级主要依靠 **size + weight + whitespace**，而非大量颜色。避免全页面大量 bold。

---

## 5. Layout 与 Spacing

- 普通页面：max-width **1200–1280px**
- Dashboard / Workspace：最大 **1360–1440px**
- 长文本阅读：**700–850px**
- Desktop 页面左右 padding：**24–48px**
- Section 间距：**48–80px**

建立固定 spacing scale（4px 基数，见 token），**禁止组件任意创造随机间距**。

---

## 6. Radius

统一：

- small：`6px`
- button / input：`8px`
- card：`12px`
- section：`16px`
- special hero：`20px`

禁止项目中随意出现大量 `10 / 14 / 18 / 22 / 24 / 28px` 等随机圆角。

---

## 7. Shadow 与 Border

- 默认优先 **1px border**，而非 heavy shadow。
- Card 默认：浅 border。
- Hover 时：极轻 shadow / border change / 1–2px translate。

禁止：黑色重阴影、大面积漂浮、蓝紫发光、Neon Glow。

---

## 8. Card 使用原则

Card 只用于**独立信息单元**：课程、练习、错题、学习计划、推荐内容、少量统计指标。

以下内容通常**不要**额外套 Card：Page Title、Section Title、Breadcrumb、普通导航、大型 Page Section、大量资料列表。

特别禁止：**Card inside Card inside Card**。

---

## 9. Button

统一四类：**Primary / Secondary / Ghost / Danger**。

- 一个视觉区域原则上**只有一个 Primary**。
- 按钮必须使用动作型文字：继续学习 / 开始练习 / 查看解析 / 上传资料 / 运行代码 / 提交答案。
- 避免：确定 / 好的 / 进入 / 详情 / 点击这里。

---

## 10. Icon

整个网站统一 Icon Library。当前未明确选择时，优先采用 **Lucide Icons**。

禁止混用 Lucide / FontAwesome / Emoji / 随机 SVG 作为同一套 UI icon。

---

## 11. 首页原则

首页核心任务：**帮助用户继续学习**。

结构优先考虑：

1. Continue Learning
2. 今日学习
3. 我的学习
4. 当前课程
5. 待复习
6. 学习数据

首页不要变成「所有功能入口集合」，不要放大量 KPI。

---

## 12. 课程学习

- 课程大厅参考：**Coursera** 信息架构。
- 课程详情参考：**Khan Academy + Brilliant**。

用户进入课程后首屏应优先看到：

1. 课程名称
2. 当前进度
3. 当前章节
4. 下一知识点
5. Continue Learning

然后才是：目录、知识脉络、资料、练习、AI、学习数据。

---

## 13. Learning Path

知识脉络采用专业化 Learning Path。典型状态：

- **未学习**：灰色
- **学习中**：蓝色
- **已学习**：绿色
- **待复习**：橙色

路径视觉可借鉴 Duolingo 的逻辑，但**禁止卡通化**。

---

## 14. 资料库

资料库属于**高信息密度页面**。主体优先 **List View + Divider**，而非巨大 Card Grid。

至少包括：搜索、Filter、文件类型、文件名称、大小、时间、查看、AI 问答、More Actions。大量文件时必须保持高效率。

---

## 15. 资料阅读 + AI

严格贯彻 **Context Continuity**：用户阅读 PDF / PPT / 文档后调用 AI 时，尽量**不跳离当前学习 Workspace**。

推荐布局：

- 左：目录 / 页面
- 中：资料阅读
- 右：AI Assistant

AI 必须明确显示当前引用：当前课程、当前文件、当前知识点。

---

## 16. AI 问答

AI **不应该照抄 ChatGPT 页面**。AI 是学习流程中的能力，而非整个产品本体。

- AI 回答优先采用自然文档布局。
- 不要给每条 AI 回答套巨大 Card。
- 紫色只作轻度 AI 识别。

---

## 17. 考研学习

考研页面属于**目标导向型 UI**。首屏优先：当前备考阶段、当前总体进度、今日任务、下一步行动。

11408 首页重点：数据结构、计算机组成原理、操作系统、计算机网络。显示：掌握度、知识点进度、待复习、练习正确率、Continue Learning。

---

## 18. 练习

练习页保持**高度专注**。

- 顶部：学科 / 知识点 / 当前题数
- 中间：题目
- 下方：选项或输入
- 主要操作：**提交答案**

答题后再展开：正确答案、解析、对应知识点、AI 讲解。禁止在答题过程中展示大量无关工具。

---

## 19. 错题

参考 **Quizlet** 的轻量信息卡。展示：科目、知识点、题目摘要、错误次数、上次答题、当前掌握状态。

操作：重新练习、查看解析。支持筛选。

---

## 20. 编程学习

参考 **Codecademy Workspace**。Desktop 优先：

- 左：任务 / 教程
- 中：代码编辑器
- 右：运行结果 / Test Result

AI 作为上下文工具：给我提示、解释错误、解释代码。**不要默认以「生成完整答案」为核心**。

---

## 21. Progress

统一 Progress component。高度 **6–8px**，不要渐变。

- 普通：蓝
- 掌握：绿
- 待复习：橙

---

## 22. Dashboard

所有指标必须：**名称 + 数值 + 上下文**。

例如：「本周学习 5h 47m，较上周 +12%」，而不是单独显示 `347`。

只展示真正帮助学习决策的数据。

---

## 23. Empty / Loading / Error

必须统一：EmptyState、Skeleton、ErrorState、Toast。

- Loading 优先 **Skeleton**，不要到处使用整页 spinner。
- Empty State 必须包含：当前为什么为空 + 用户下一步可以做什么。

---

## 24. Responsive

至少支持 Desktop / Tablet / Mobile。移动端**不是简单缩小桌面**：

- Sidebar → Drawer
- 多栏 Workspace → Tabs / Stacked
- Course Cards：3 → 2 → 1

---

## 25. Accessibility

至少保证：

- 足够 contrast
- keyboard focus
- icon button 有 aria-label / tooltip
- 图片有 alt
- 状态不能只依靠颜色表达
- 点击区域足够
- 表单错误有文字说明

---

## 26. UI 文案

语言：短、具体、明确、行动导向。

禁止大量 AI 模板化文案：「开启智慧学习之旅 / AI 赋能未来 / 解锁学习潜能 / 探索无限可能 / 科技赋能教育」。

推荐真实学习语境：「继续昨天的数据结构学习」「还有 3 个知识点待复习」「今天计划完成 20 道练习」。

---

## 27. Reference 规范

项目现有 `reference/`，以后所有视觉参考图片放这里；Logo 相关素材保留原有命名与目录结构（`reference/LOGO/`）。

严格要求：不随意重命名、不删除、不移动、不修改原始参考图。

Reference 只用于设计方向、布局、比例、氛围参考，禁止逐像素复制第三方网站。

---

## 28. Design Tokens（代码级防漂移）

所有 UI 开发优先使用 token（`frontend/src/styles/tokens.css`）。

禁止类似 `border-radius: 13px`、`color: #2761ef`、`margin-top: 37px` 这种无依据 magic visual values。确实需要特殊值时，必须有明确原因。

---

## 29. 视觉一致性检查清单（页面完成后执行）

详见 `.claude/skills/frontend-review/checklist.md`，或直接运行 `/frontend-review`。核心项：

1. 是否违反 Design Tokens（随机颜色 / 字号 / 圆角 / shadow / spacing）
2. 是否出现无意义 gradient / glass / glow
3. 是否 Card abuse / Card nesting
4. 是否 emoji 当图标
5. typography hierarchy / spacing 是否一致
6. button hierarchy 是否清晰、Primary 是否唯一
7. 页面是否「功能优先」而非「学习任务优先」
8. loading / empty / error 是否统一
9. responsive / accessibility 是否达标
10. 是否错误修改 backend
