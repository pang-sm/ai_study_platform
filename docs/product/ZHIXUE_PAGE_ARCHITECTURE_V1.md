# 智学平台页面架构 V1（ZHIXUE PAGE ARCHITECTURE）

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文档是**页面层级 / 责任**的参考基准，从属于 SSOT；冲突时 SSOT wins。
>
> **⚠️ 导航结构冲突待决**：本文档 §2.1 冻结的 Global Navigation 为
> `首页 | 我的学习 | 探索 | 资料`，而 SSOT §12（用户侧信息架构 TARGET）为
> `首页 / 学习 / 资料 / 练习 / AI / 计划 / 我的`。
> **以 SSOT §12 为准**；本文档的导航建议不构成最终 IA。
> 在 STEP 9（前端信息架构）正式冻结前，不得把两者中的任一方当作已实现。
>
> **学习空间命名以 SSOT 为准**：`course_learning` / `exam_11408` / `programming`。

- **Version**: V1.0
- **Status**: BASELINE — Phase 1 human-approved（subordinate to `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`）
- **Date**: 2026-09-11
- **Scope**: 前端信息架构、页面层级、导航图与学习主流程；不包含 UI 实现、路由冻结、后端/数据库变更或部署。

> Phase 2 的页面语法、跨页体验和世界视觉语法见 `docs/product/ZHIXUE_PAGE_SYSTEM_V1.md`。本文继续作为页面层级与责任的参考基准。

## 1. 决策摘要

智学是一个 `GLOBAL SHELL → LEARNING WORLD → LEARNING CONTEXT → LEARNING WORKSPACE` 的个人学习空间，而不是功能门户或 KPI Dashboard。全站以同一学习合同组织：

```text
CURRENT（我正在学什么）
  → NEXT（下一步是什么）
  → ACTION（现在做什么）
  → PATH（为何是这一步、后面还有什么）
  → TOOLS（完成行动时所需的能力）
```

三大世界共享这个合同和学习状态，但不共享同一页面外形：Exam 表达目标、阶段与里程碑；Course 表达知识结构与关联；Programming 表达编写、执行和反馈。

### 1.1 现状审计与约束

本设计以仓库真实情况为界：

| 范围 | 审计结论 | 本架构处理 |
| --- | --- | --- |
| 前端 | TanStack Router 当前只有 `/` 与冻结 Homepage；`AppShell` 暂有首页/探索锚点、搜索与账户占位。 | 本文定义目标页面及建议 URL，不声明它们已经实现。 |
| Exam | 后端已有 11408 四科（数据结构、计算机组成原理、操作系统、计算机网络）的计划、章节练习、真题、AI 题、错题、收藏和学习摘要接口。 | 11408 是首个完整 Exam Target；其他考试只给可扩展架构与受控空状态。 |
| Course | 后端已有课程注册/状态、课程列表、资料、资料搜索与预览、知识点/知识图谱、练习 workbook、历史和计划任务等接口。 | 可设计课程学习上下文与资料连续性；统一 Knowledge Graph 仍标为目标演进。 |
| Programming | 后端已有 C/C++/Java/Python 的 onboarding、主页、练习读取/开始、样例运行、测试、运行和提交接口。 | Coding Workspace 以真实执行/测试为中心；不能把 AI 当作代码正确性的来源。 |
| Learning / Review | 后端已有学习任务、学习 dashboard/report、review center、知识点进度、学习记录等接口。 | My Learning、Plan、Review、History 以这些已有能力组织。 |
| Search | 当前有资料搜索；没有覆盖 Course/Exam/KnowledgePoint/ProgrammingSkill/Question 的统一搜索 API。 | 搜索页面与统一 Search Entity 是目标 IA；首期不得伪造跨实体结果。 |
| Next Best Action | 有多处世界级摘要/计划数据，但没有统一 Next Action Service。 | 页面采用 `CURRENT → NEXT` 语义；优先以现有世界级数据组装，统一服务标为后续能力。 |

`Knowledge Graph` 已有构建和读取能力，但其统一实体、关系、RAG 元数据与推荐服务仍是 **PLANNED**；文中不会将其写成全域已上线能力。

## 2. Global Shell 与页面层级

### 2.1 Global Navigation（冻结建议）

```text
左侧： 首页 | 我的学习 | 探索 | 资料
右侧： 搜索 | 个人账户
```

- **学习计划不作为顶级导航。** 它位于 `我的学习 → 学习计划`，因为计划是学习状态的组织方式，而非独立的学习世界。
- 会员可从账户菜单/受限动作触发，不进入主学习导航。
- 保留当前 `首页` 的顶级位置；将当前“探索学习”锚点演进为真正的 `探索` 页面。没有强理由保留“学习计划”顶级入口。
- 深层页不替换 Global Shell；桌面端保留可达的全局导航，移动端收纳为带文字标签的菜单/底部主导航（最多四项）与搜索入口。

### 2.2 四层模型

| 层 | 责任 | 页面例子 | 不负责 |
| --- | --- | --- | --- |
| Global Shell | 跨世界定位、账户、搜索、回到个人学习空间 | 首页、我的学习、探索、资料 | 展开某世界的完整目录或工具面板 |
| Learning World | 选择/恢复一种学习模式 | Exam World、Course World、Programming World | 直接承担具体知识学习 |
| Learning Context | 锚定考试目标、课程、语言/轨道及其路径 | 11408、线性代数、Python Track | 把所有工具平铺成门户 |
| Learning Workspace | 在一个节点完成一次学习行动 | 知识学习、练习、资料阅读、代码执行 | 让用户失去世界/上下文定位 |

## 3. 世界与上下文架构

### 3.1 Exam World

```text
Exam World
  → Exam Target（11408 / 其他考试占位）
    → Exam Subject（数据结构 / 组成原理 / 操作系统 / 计算机网络）
      → Module / Chapter / Knowledge Node
        → Learning Workspace（学习 / 章节练习 / 真题 / 复习）
```

`11408` 是考试目标，不是与 Exam World 并列的一级业务。四科均是 11408 的平级 Subject；每科进入自身路径、章节、知识节点与相应的练习/真题上下文。跨科概览只在 11408 Target 级出现，不能让用户把“11408”误解成一门科目。

### 3.2 Course World

```text
Course World
  → Course
    → Chapter
      → Knowledge Node
        → Learning Workspace（阅读 / 学习 / 练习 / 复习）
```

Knowledge Graph 不是孤立的“图谱功能页”。它是路径排序、前置知识提示、关联知识、下一步推荐、资料归属/RAG 过滤的底层结构；课程上下文可将“知识脉络”作为可见投影。统一图谱的数据模型与跨课程语义仍需后续工程落地。

### 3.3 Programming World

```text
Programming World
  → Language / Track
    → Programming Skill
      → Exercise
        → Coding Workspace（任务 / 编辑器 / 运行与测试 / 反馈）
```

Programming 复用 `LearningContext、LearningNode、LearnerState、LearningAction、NextBestAction`，但 `CODE` 行动的完成信号来自编译、执行和测试结果。其工作台可与普通学习工作台完全不同，AI 只提供提示、解释与诊断，不替代 Sandbox/Judge。

## 4. 页面责任矩阵

所有页面必须有一个主要用户问题和一个主要行动。`CURRENT / NEXT / ACTION / PATH / TOOLS` 只在适用时显性呈现；不能为了齐全把每页做成 Dashboard。

| 页面 | Role / 主要问题 | 输入 | Primary Action | Output / 下一页 | 数据需求 | 空状态 | Mobile priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Homepage | 个人学习入口；“我现在应继续什么？” | 登录用户、最近上下文 | Continue Learning / Open Question | 真实 Workspace；探索世界 | 最近活动、世界级下一行动 | 无记录时引导探索一个世界 | Continue CTA、问题、世界摘要 |
| My Learning | 汇总本人正在进行的学习；“哪些学习需要我处理？” | 用户学习状态 | 选择 Current / Plan / Review / History / Progress | 对应二级页或 Workspace | tasks、review、records、progress | “还没有进行中的学习”→探索 | Current 和 Review 优先 |
| Current Learning | 查看正在进行的上下文；“我从哪里接着学？” | 当前 contexts | Continue | 精确 Workspace | 最近节点、状态、可恢复位置 | 无当前项→Explore | 继续列表 |
| Plan | 管理学习计划；“我的可执行安排是什么？” | 用户任务、考试/课程计划 | 开始或调整任务 | Workspace / Plan task detail | learning tasks、11408/course plan | 无计划→从 Context 建立第一项 | 今日/本周任务与开始 |
| Review | 统一复习队列；“现在最该复习哪一个？” | due / wrong / weak / retry 条目 | Start Review | 带节点与题目的 Workspace | review center、wrong questions、practice/history、mastery（可用时） | 无待复习→回到 Current 或 Explore | 下一复习行动 |
| History | 回顾完成记录；“我已完成了什么？” | 活动历史、提交历史 | 打开一次历史学习 | Contextual history / Workspace | learning records、attempt history | 无历史→开始学习 | 时间线与单条恢复 |
| Progress | 查看能影响决定的进展；“哪一条路径需要关注？” | context progress | 进入薄弱/未完成节点 | Context / Workspace | course/exam/prog progress、knowledge map | 无可计算进展→说明开始条件 | 关键节点，非 KPI 网格 |
| Explore | 内容发现；“我想学什么、平台有哪些方向？” | 世界、可用目录 | 选定 World / Context | Exam/Course/Programming World | 可用目录与权益 | 无可用内容→说明范围 | 世界→推荐入口 |
| Resources | 全局资料库；“我需要找哪份资料？” | query、filter、资源 | 阅读资料 / 关联学习 | Resource Reader / Workspace | materials、material search/status | 无资料→上传或回到相关 Context | 搜索、过滤、列表 |
| Exam World | 选择考试目标；“我要备考哪一类考试？” | exam catalog | 进入 Target | Exam Target | 真实 target catalog | 除 11408 外以“暂未开放”受控展示 | 11408 优先 |
| Exam Target (11408) | 组织四科和备考阶段；“11408 下一步该推进哪科？” | target、阶段、科目摘要 | Continue target action / choose subject | Subject / Workspace | 11408 summary、subject dashboards、plan summary | 尚无记录→选择一科开始 | 下一动作、四科路径 |
| Exam Subject | 单科学习上下文；“本科学到哪里、下一步是什么？” | subject | Continue / choose module | Node Workspace / Practice | subject dashboard、outline、stats、plan | 无计划→从目录开始 | 当前节点、章节入口 |
| Exam Module / Node | 进入一个可学习单元；“我先理解、练习还是真题？” | chapter/node、entry intent | Learn / Practice / Past Paper | Workspace | chapter outline、questions、knowledge state | 无题/内容→诚实告知并返回 Subject | 节点、行动选择 |
| Course World | 发现并恢复课程；“我想学哪门课程？” | course catalog、enrollment | 进入 Course | Course Detail | courses、status、entitlement | 无课程→提示可用范围 | 当前课程优先 |
| Course Detail | 课程上下文；“这门课下一知识点是什么？” | course | Continue Learning | Chapter/Node Workspace | course progress、today plan、knowledge map | 未注册/无进度→开始路径 | 当前/下一知识点 |
| Chapter | 结构定位；“本章如何展开？” | course + chapter | 选择 Node | Node Workspace | chapter/node outline、graph relations | 无节点→返回 Course | 节点清单与当前位置 |
| Learning Workspace | 进行非代码学习；“如何完成当前学习动作？” | LearningContext + node + action | 完成 Learn/Read/Practice/Review | Next node/action，或返回 Context | content/materials、question, progress, contextual tools | 内容/题不可用→解释并回节点 | Context、主内容、主行动 |
| Resource Reader | 连续阅读与提问；“这份资料如何帮助当前学习？” | material + optional context/node | Ask AI / Start Learning / Related Knowledge | 同一 Workspace 或相应 Context | preview、knowledge links、context metadata | 解析中/失败→状态与重试路径 | 阅读优先，工具作 tab |
| Programming World | 选择语言/轨道；“我想以什么方向练编程？” | language/track catalog、profile | 进入 Track | Programming Track | programming home/onboarding/packages | 未完成画像→onboarding | 当前轨道/继续编码 |
| Programming Track | 编程学习上下文；“下一项要练的技能是什么？” | language/track | Start next exercise | Coding Workspace | exercises、learner progress（现有范围） | 无练习→说明可用范围 | 下一练习 |
| Coding Workspace | 完成代码任务；“代码为何失败、如何通过测试？” | exercise + execution state | Run / Test / Submit | feedback、next exercise | exercise detail/start/run/test/submit | 载入/执行失败→保留代码与重试 | 任务、编辑、结果 tabs |
| Search | 跨实体定位；“这个课程/知识点/资源/题在哪里？” | query + entity filter | 打开结果 | 正确 Context 或 Reader/Workspace | **目标**统一实体搜索；当前仅 materials search 可真实接入 | 无结果→改写/范围提示 | query 与结果类型 |
| Profile | 账户与个人偏好；“如何管理我的身份和设置？” | user profile | 编辑设置/查看权益 | 留在 Profile 或账户子页 | auth/profile/entitlements | 未完整资料→补齐资料 | 身份与关键设置 |

## 5. Learning Workspace 合同

### 5.1 普通 Learning Workspace

```text
Context：我在哪个世界 / 目标 / 课程 / 科目 / 节点
Learning Content：当前知识、资料或题目
Current Action：Learn / Read / Practice / Review / Exam Practice / Ask AI
Learning State：进度、掌握/待复习、尝试状态（可用范围内）
Contextual Tools：AI Tutor、Resources、Notes、Knowledge Relations、Hints
Next Best Action：完成后下一件具体可做的事
```

- Workspace 始终显示可辨识的 Context；AI、资源、笔记和知识关系保持为与当前节点绑定的工具，不建立新的 Feature Portal。
- `Notes` 是架构槽位：当前仓库未审计到专用笔记 API/前端页面，后续实现前需先定义能力契约。
- “完成”应返回明确的下一行动或保留在节点；不允许落入无上下文的工具页。

### 5.2 Coding Workspace 差异

```text
Context + Task/Instruction | Editor | Execution / Tests / Feedback
                                      ↓
                                   Next Exercise
```

桌面以任务、编辑器、运行/测试结果三栏为主；移动端将任务、编辑器、结果切换为明确 tabs/纵向阶段。AI Feedback 读取当前 exercise、代码和真实运行结果（接口可提供的范围），输出解释、提示与错误诊断；不可默认输出完整解答。

## 6. Resource、Review 与 Search

### 6.1 Resource Architecture

一个 `Resource` 同时有全局发现与上下文用途：

```text
Resource
  ├─ owner / visibility / type / parsing status
  ├─ domain
  ├─ course_id | exam_target | subject | chapter | knowledge_point
  └─ relation: supports / required_for / related_to
```

以上是目标元数据合同；当前已有资料、资料检索、预览及 material-to-knowledge links，跨所有层级的统一 metadata 仍须后端方案支持。

- **Global Resource Library**：用于上传、搜索、过滤和管理资料。
- **Contextual Resource**：在 Course/Exam/Node/Workspace 中按绑定关系出现；点击阅读保留来源 Context。
- Reader 的 `Ask AI` 维持资料+当前 Context；`Start Learning` 进入相关节点 Workspace；`Related Knowledge` 进入该节点/课程或考试上下文，绝不跳到无上下文资源详情页。

### 6.2 Review Architecture

```text
My Learning → Review
  ├─ Review Due
  ├─ Wrong Questions
  ├─ Weak Knowledge
  └─ Practice Again
       → contextual Workspace
```

Wrong Book 不再是默认顶级模块：错题作为 Review 的一种来源，仍可在 Exam Subject/Practice 完成后以“加入复习/查看错题”局部入口出现。原有错题数据和能力不删除；迁移时只调整入口与聚合，不迁移/抹除记录。

### 6.3 Unified Search Entity

目标统一实体为 `Course | Exam | KnowledgePoint | Resource | ProgrammingSkill | Question`。每条结果必须携带：`entity_type、canonical_id、context_ref、display_title、availability`。

| 类型 | 正确落点 |
| --- | --- |
| Course | Course Detail |
| Exam | Exam Target，或 Exam World 中受控的未开放 Target |
| KnowledgePoint | 带 course/exam/subject 上下文的 Node Workspace |
| Resource | Resource Reader，并保留可返回 Context |
| ProgrammingSkill | Programming Track 的该技能 |
| Question | 其所属的 Practice/Exam Workspace |

当前只可将 `Resource` 搜索接入真实 `/materials/search`；其他实体搜索先以架构定义和不可点击/不展示策略处理，直到获得真实查询契约。

## 7. 关键工作流

### 7.1 Continue Learning

```text
Homepage / My Learning Current
  → resolved LearningContext + node + resumable action
  → correct Workspace
  → completion
  → Next Best Action (same context or return to context)
```

“继续学习”不得只跳入世界首页；只有无法恢复精确节点时，才退化到对应 Target/Course/Track 并提示选择下一步。

### 7.2 Explore to Learning

```text
Explore → World → Target/Course/Track → Subject/Chapter/Skill → Workspace
```

未实现的内容只能在目标层显示受控可用性说明，不制造可以进入的伪目录。

### 7.3 Review

```text
My Learning → Review → chosen due/wrong/weak/retry item → contextual Workspace → updated review state → Review queue / Next Action
```

### 7.4 Resource to Learning

```text
Resources → Resource Reader → Ask AI (same context)
                           → Start Learning (bound node Workspace)
                           → Related Knowledge (bound Context)
```

### 7.5 Search to Context

```text
Search → typed entity result → canonical context-aware destination → Back returns to search with query/filter/scroll restored
```

## 8. Page Graph、Back 与 Deep Link

### 8.1 Page Graph

```text
GLOBAL SHELL
├─ Homepage ───────────────→ Workspace
├─ My Learning
│  ├─ Current Learning ────→ Workspace
│  ├─ Plan ───────────────→ Workspace
│  ├─ Review ─────────────→ Workspace
│  ├─ History ────────────→ Context / historical Workspace
│  └─ Progress ───────────→ Context / Workspace
├─ Explore
│  ├─ Exam World → Exam Target (11408) → Subject → Module/Node → Workspace
│  ├─ Course World → Course → Chapter → Node → Workspace
│  └─ Programming World → Track → Skill → Coding Workspace
├─ Resources → Resource Reader ───────→ Workspace / Context
├─ Search ────────────────────────────→ typed Context destination
└─ Profile
```

**Page count**：23 named page/responsibility nodes（含二级页与专门 Workspace）。这是架构计数，不代表 23 个路由组件；`Current/Plan/Review/History/Progress` 可在同一 My Learning 路由壳中用可分享的子路由实现。

**Dead ends**：设计目标为 0。每个页面至少有一个安全出口：父层 breadcrumb/back、Global Shell、或完成后的 Next Action。资料解析失败、无内容、无结果和未开放 Target 都必须给出恢复动作。

**Duplicate responsibilities**：错误集合统一归 Review；Plan 收纳在 My Learning；知识图谱既是底层能力又可作为 Context 的结构视图，不能复制一个无上下文“图谱门户”。

**Major route conflicts**：当前前端只有 `/`，所以不会与已实现业务路由冲突；此前 Global Nav 的“探索学习”锚点需要升级为页面路由。后端 URL 不等于前端 URL，本文不以 API 字符串驱动 UI 路由。

### 8.2 Back / Breadcrumb 规则

- Context 深度达到三级时展示语义 breadcrumb，例如 `考试 > 11408 > 操作系统 > 虚拟内存`，最后一项为当前节点。
- `Back` 优先恢复实际来源的 query、filter、tab、scroll 和未提交代码；若从通知/搜索/外部 deep link 直达，则回到该实体的语义父级，绝不强制跳 Homepage。
- Workspace 的工具面板、资料阅读、AI 问答属于同一上下文内状态，关闭后返回 Workspace，而非切换成独立主导航目标。

### 8.3 建议 URL（非冻结）

```text
/                         Homepage
/my-learning/{current|plan|review|history|progress}
/explore
/resources  /resources/:resourceId
/exam  /exam/11408  /exam/11408/:subjectKey  /exam/11408/:subjectKey/nodes/:nodeId
/courses  /courses/:courseId  /courses/:courseId/chapters/:chapterId/nodes/:nodeId
/programming  /programming/:language  /programming/:language/skills/:skillId/exercises/:exerciseId
/search  /profile
```

Deep links 必须编码 canonical context，而不是只编码显示名称；权限/可用性检查失败时显示受控状态，并提供父级返回入口。未来实体 ID 或历史兼容需求会影响具体路径，故本阶段不冻结 URL。

## 9. Visual System Guardrails（不含 UI 实现）

使用统一的 **ZHIXUE ACADEMIC LAB / ZhiXue Academic Journey** 语言：editorial grid、academic paper、deep ink、coral accent、scientific annotation、strong typography。全站遵循 `Current > Next > Action > Path > Tools`，避免同款 KPI 卡阵列。

| 页面语法 | 视觉重心 | 不应复制 Homepage 的部分 |
| --- | --- | --- |
| Exam | Target / Stage / Milestone / Path；深蓝/靛辅助色 | 不复用首页 Hero 问题叙事 |
| Course | Knowledge / Structure / Connection；青绿辅助色 | 不把章节目录做成大面积营销卡片 |
| Programming | Code / Run / Feedback；蓝紫辅助色 | 不把编辑器工作台做成普通课程资料页 |
| Resources | 高信息密度、列表与分隔线 | 不把每个文件做成巨型卡片 |
| My Learning / Review | 当前行动与可执行队列 | 不变成学习 KPI Dashboard |

后续 UI 阶段还应落实：页面只有一个主操作、可访问深层导航/键盘焦点、资源/错误/加载的恢复状态、移动端优先显示 Context 与 Action，多栏 Workspace 改为 tabs/stacked，而非压缩成不可用三栏。

## 10. 实施边界与后续依赖

本文件只冻结信息架构和职责。其后分期实现前，需要分别确认：

1. 用已有 API 可组装哪些 `Current/Next`，以及统一 Next Action Service 的最小契约；
2. 统一 Search 的服务端能力与索引范围；
3. Resource 元数据跨 Course/Exam/KnowledgePoint 的实体与权限模型；
4. Notes、统一 Knowledge Graph 与跨世界 mastery 的未实现能力；
5. 路由及页面逐个实现，每次只做一个小功能，且不修改冻结 Homepage 的职责。

本轮没有前端、后端、数据库、依赖或部署改动；不需要 migration。
