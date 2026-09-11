# 智学平台页面系统 V1（ZHIXUE PAGE SYSTEM）

- **Version**: V1.0
- **Status**: PROPOSED — ready for human review
- **Date**: 2026-09-11
- **Scope**: 把 Phase 1 的页面责任落实为页面语法、跨页体验、世界视觉语法和首条实施链路。不含具体 UI、前端实现、后端/数据库变更、依赖或部署。
- **Depends on**: `ZHIXUE_PAGE_ARCHITECTURE_V1.md`（Phase 1 BASELINE）

## 1. System decision

页面系统不为 23 个责任节点分别发明一种 UI，而采用七种可复用的 Page Grammar。每个页面先回答一个学习问题，之后才显露辅助工具。所有 grammar 都服从：

```text
CURRENT → NEXT → ACTION → PATH → TOOLS
```

这不是每页都要出现的五段式布局；而是内容优先级。页面只显性展示完成当前任务所需的层级，避免再度成为功能门户或 KPI Dashboard。

## 2. Page Grammar System

| Grammar | Purpose / Primary question | Information hierarchy | Actions | Navigation & density | Desktop / mobile | States | Real pages |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **HOME** | 回到个人学习；“我现在如何立即继续？” | Current → Next → Action → active paths → world summary | Continue Learning；Open Question | Global Shell；低至中密度，单一焦点 | Desktop：编辑式主焦点+简短路径；Mobile：问题、CTA、当前上下文优先 | Empty：探索第一个世界；Loading：保留焦点骨架；Error：重试/探索 | Homepage |
| **HUB** | 汇总同类学习意图；“我现在要管理或发现什么？” | 当前可行动项 → 组织维度 → 辅助筛选/历史 | 选择一个学习对象或队列 | Global Shell，明确二级导航；中密度，不用等大卡片墙 | Desktop：标题/行动区 + list/path；Mobile：当前行动置顶，二级页签或分段控件 | Empty：解释没有什么及下一行动；Loading：列表骨架；Error：保持筛选并重试 | My Learning、Explore、Resources、Review |
| **WORLD** | 选择一种学习模式；“我想在哪个学习世界开始或恢复？” | World identity → current/featured context → catalog entry | 进入 Context / 恢复最近 Context | Global Shell + World Header；中密度 | Desktop：世界叙事与可选 Context；Mobile：当前 Context + 短目录 | Empty：受控可用性；Loading：目录骨架；Error：返回 Explore | Exam World、Course World、Programming World |
| **CONTEXT** | 在一个课程/考试目标/轨道中定位；“我在这里学到哪里、下一步是什么？” | Context identity → Current → Next/Action → Path → contextual tools | Continue / choose a structure item | Context Header + breadcrumb；中密度；不重复 Global Hero | Desktop：强调路径/阶段；Mobile：当前节点与 Next Action 置顶、路径折叠 | Empty：开始路径/注册/选择科目；Loading：头部和路径骨架；Error：返回 World | 11408、Exam Subject、Course Detail、Programming Track、Current Learning |
| **STRUCTURE** | 浏览知识、章节或技能结构；“这部分如何组织，进入哪一节点？” | Parent context → location → nodes/relations → available action | 选择 Node / 继续当前位置 | Context Header + breadcrumb；高信息密度但非文件管理器 | Desktop：结构主视图+关系/进度辅助；Mobile：节点列表+当前位置，关系为抽屉 | Empty：回到 Context；Loading：树/列表骨架；Error：保留父级返回 | Exam Module/Node、Chapter、Programming Skill、Progress |
| **WORKSPACE** | 完成一次具体学习；“我怎样完成当前行动？” | Context → content/task → primary action → state/feedback → tools → next | Learn/Read/Practice/Review 或 Run/Test/Submit | Workspace Shell；专注、高度上下文；工具不替代主内容 | Desktop：普通 Workspace 两栏；Coding 三域；Mobile：内容优先、工具切换为 tab/sheet | Empty：明确不可用原因和父级出口；Loading：内容骨架；Error：保存用户状态并重试 | Learning Workspace、Resource Reader、Coding Workspace、Review Session |
| **UTILITY** | 完成检索/账户/记录任务；“我需要找到或管理什么？” | 当前 query/identity →结果或设置→安全下一步 | Open result / save setting | Global Shell；按用途低到高密度 | Desktop：检索/表单宽度受控；Mobile：query/关键设置先行 | Empty：清楚的零结果/无记录；Loading：局部骨架；Error：保留输入 | Plan、History、Search、Profile |

### Grammar boundary rules

- HOME 只有个人学习入口的职责；任何完整目录进入 WORLD/HUB。
- HUB 不承担某个具体节点的学习；进入对象后切换到 CONTEXT 或 WORKSPACE。
- WORLD 只负责世界选择和恢复，不展示一个无上下文的工具市场。
- CONTEXT 展示 “为什么是下一步”；STRUCTURE 展示 “可以沿什么结构走”。如果用户已有精确目标，可直接进 WORKSPACE。
- WORKSPACE 只做一次学习/编码行动；完成后给出 `Next`，不自行成为新的导航中心。
- UTILITY 不应吞没学习流；每一搜索、历史或计划结果都有 context-aware 落点。

## 3. Global App Shell

### 3.1 Shell layers

```text
Global Shell      = 全局位置、Search、Profile、四个顶级目的地
Context Header    = 当前世界/目标/课程/科目/轨道、路径与回退
Workspace Shell   = 当前节点、行动状态、上下文工具、完成后的 Next
```

三层按需叠加：Homepage 只有 Global Shell；World/HUB 使用 Global Shell；Context/Structure 使用简化的 Global Shell + Context Header；Workspace 使用紧凑 Global Shell 可达入口和 Workspace Shell。下级页不得同时重复完整顶级导航、巨型 Hero 和大 Context Banner。

### 3.2 Desktop header

- 左侧：Brand V2 `08 Reversed Dark`、`首页 / 我的学习 / 探索 / 资料`；当前项有文字、颜色和位置指示，不只靠色彩。
- 右侧：Search、Profile。会员只从 Profile 或触发权益限制的动作进入。
- Context/Workspace 页面将主内容留给 Context Header；顶栏保持紧凑，不把世界/章节再塞入全局导航。

### 3.3 Mobile header

- 顶部保留 `04 Icon Only transparent` runtime derivative、当前页/上下文短标题、Search 或返回入口；主导航以带文字标签的菜单或不超过四项的底部导航承载。
- 深层页优先显示 Back + Context；不要同时挤入所有 Global Nav 文案。
- 至少 44px 目标尺寸；抽屉、tab、sheet 都须有明确关闭/返回入口和键盘可达路径。

### 3.4 Breadcrumb, Back and deep links

- Breadcrumb 仅在 Context 深度为三层或以上显示，例如 `考研 > 11408 > 操作系统 > 虚拟内存`。它表达语义父级，不重放浏览历史。
- Back 优先回到真实来源，并恢复 query、filter、tab、scroll 和未提交代码；外部/通知/Search deep link 没有来源时，回到语义父级。
- Deep link 必须含 canonical context ID；解析失败、权限不足或内容不可用时给出状态与父级出口，绝不静默跳 Homepage。

## 4. Page depth and paths

**最大有效深度**是从一次明确意图到 Workspace **1–3 次行动**。层级是理解模型，不是强制点击仪式。

| Path | Flow | Intentional skips |
| --- | --- | --- |
| Normal path | Homepage → World → Context → Structure → Workspace | 初次探索时允许经过完整结构 |
| Fast path | Homepage/My Learning Current → Workspace；Explore → Context → Workspace | 已有恢复状态时跳过 World 或 Structure |
| Deep-link path | Search/notification/Resource → correct Context-aware Workspace/Reader | 先抵达目标，再暴露语义父级 |

应避免：`Homepage → Explore → Exam World → 11408 → Subject → Chapter → Node → Workspace` 这种七次点击才能学习的路径。Exam Subject 和 Node 可以承接进入 WORKSPACE；Course Detail 可直接恢复当前 Node；Resource Reader 可直接启动所关联的节点。

## 5. Learning World visual grammar

### 5.1 Shared Academic Lab foundation

全局视觉 token：academic paper canvas、deep ink、coral accent（最重要行动/关键批注）、editorial grid、scientific annotation、strong typography、有限边界与有意义的对象卡。Logo V2 只使用正式资产：Dark desktop header `08 Reversed Dark`；light header `02 Secondary Horizontal`；mobile `04 Icon Only transparent`；favicon `04 Icon`；App/PWA `05 App Icon`。不修改或重绘 Logo。

所有世界共享排版节奏、表面层级、可访问状态和 motion 原则；领域 accent 仅帮助识别，不能把三者变为三个产品。

### 5.2 Exam — Target / Stage / Milestone / Readiness

| Page family | Visual idea | Persistent semantic anchors | Avoid |
| --- | --- | --- | --- |
| Exam World | 目标的入口与可选备考方向 | target axis、目标身份、最近备考 Context | 通用课程目录卡片 |
| 11408 Target | 四科围绕同一考试目标的准备状态 | stage、subject weight、milestone、readiness、target path | 四个对称 KPI 面板 |
| Subject | 在一门科目中推进备考 | subject position、current stage、chapter/milestone | 只把 Course Home 改标题 |
| Node / Workspace | 将知识或真题行动与考试目标相连 | 考纲/阶段、题型、已完成/待复习、下一次 practice | 在答题时展示大量无关分析 |

Exam 的主视觉是“朝目标推进”的轴线与里程碑，深蓝/靛仅作辅助色。readiness 必须带可解释语境（例如当前阶段、科目或待完成行动），不得孤立成一个分数。

### 5.3 Course — Knowledge / Structure / Prerequisite / Connection / Mastery

| Page family | Visual idea | Persistent semantic anchors | Avoid |
| --- | --- | --- | --- |
| Course World | 学科和课程的知识入口 | course families、当前课程、可恢复路径 | 功能市场 |
| Course Home | 一门课程正在展开的知识结构 | current node、next node、chapter structure | 巨型营销 Hero |
| Chapter | 局部知识结构 | chapter position、node sequence、前置/关联 | 只列出无意义百分比 |
| Node / Workspace | 在一个知识节点理解、阅读、练习 | prerequisite、related knowledge、resource citation、mastery state | 独立图谱炫技页 |

Knowledge Graph 必须以轻量方式进入 Course Home、Chapter、Node 和 Workspace：路径排序、前置提示、关联面板与下一建议都可以利用它；“知识脉络”仅是这套结构的一个可视投影。当前统一图谱/RAG metadata 仍是后续能力，UI 不能假装已有全覆盖关系。

### 5.4 Programming — Task / Code / Run / Test / Feedback / Iterate

| Page family | Visual idea | Persistent semantic anchors | Avoid |
| --- | --- | --- | --- |
| Programming World | 动手学习的入口 | language/track、正在练的技能、下一个练习 | 普通课程网格 |
| Track / Skill | 由技能到可执行任务的渐进 | skill path、exercise readiness、recent outcome | 考试阶段轴线 |
| Coding Workspace | 代码从任务到真实运行结果的迭代 | task, editor, run/test state, feedback, next exercise | IDE clone、四宫格 panel hell |

蓝紫是 Programming 的辅助识别。真实 compiler/run/test 结果优先于 AI；AI 只解释、提示、诊断，不能把“生成完整答案”作为默认路径。

## 6. Hub experience system

### 6.1 My Learning

采用一个 HUB 壳与可分享二级 destinations：`Current | Review | Plan | History | Progress`。

- **Current**：恢复正在进行的 Context，是首要内容。
- **Review**：以现在可以完成的一次复习会话为首要内容。
- **Plan**：任务安排和开始，不做独立生产力产品。
- **History**：可回看、可回到来源的时间线。
- **Progress**：只显示会改变下一决定的路径状态和薄弱处。

这些不是同时塞进一个 Dashboard；在任一时刻只有一个重点队列/行动。

### 6.2 Explore

Explore 是发现层：先显示三个 Learning Worlds，再显示真实可用 Context 或用户可恢复的入口。不能放 AI、错题、资料、会员、计划等功能卡来充当 marketplace。尚未具有成熟内容的方向应显示范围和可用性，不能伪造完整目录。

### 6.3 Resources

Resources 是 `Global Library + Contextual Entry`：全局库提供搜索、过滤、上传/管理和高信息密度列表；Context 中的资料入口只显示能帮助当前节点的资料。Reader 不是终点，必须提供 Ask AI、Related Knowledge、Start Learning。

## 7. Workspace system

### 7.1 Common Learning Workspace

```text
CONTEXT  当前世界 / 目标 / 课程 / 科目 / 节点
CONTENT  知识、资料或题目
ACTION   此刻唯一主要行动
STATE    进度、尝试、待复习等真实可得状态
TOOLS    AI Tutor / Resources / Notes / Knowledge Relations / Hints
NEXT     完成后最具体的下一行动
```

**Desktop spatial model**：

```text
Context strip (compact, persistent)
┌──────────── Main learning content + primary action ────────────┬─ Contextual tools ┐
│  content / reader / practice; one focal action                 │ AI / resources /  │
│  state and next follow completion, not compete before it        │ notes / relations │
└────────────────────────────────────────────────────────────────┴────────────────────┘
```

- Context strip 永久可见但紧凑；主内容/主行动永久可见。
- AI Tutor、Resources、Notes、Knowledge Relations、Hints 是 contextual：右侧面板、抽屉或按需 sheet，不能成为横向五个门户按钮。
- Practice 在当前节点需要时成为主内容的行动模式，而非永远固定面板。
- Next Action 在提交/完成反馈之后出现；它保持同一 Context，除非明确推荐跨 Context。

**Mobile spatial model**：Context strip + content/action 连续单列；AI/资源/笔记/关联进入带文字标签的 bottom sheet 或 tabs；不在小屏压缩成多栏。题目/资料和提交行动高于一切工具。

`Notes` 是未来 contextual tool 槽位，当前没有已审计的专用笔记能力；实现前必须另行定义 API 与保存边界。

### 7.2 Coding Workspace

```text
Task (permanent) | Editor (permanent, primary) | Output / Tests (permanent after run)
                  └─ AI Feedback / Error diagnosis (contextual, collapsible)
                                      → Next Exercise (after outcome)
```

- **Permanent**：当前任务和编辑器；已运行后，最近的 Output/Test result。
- **Contextual/collapsible**：任务细节、Hints、Resources、AI Feedback、Error Diagnosis、历史运行输出。
- **Primary actions**：Run、Test、Submit，按任务状态呈现，不要并列成平级 Dashboard 控件。
- **Not an IDE clone**：不复制项目树、全局命令面板、无关调试器或无限侧栏。任务只需要完成学习任务的编辑和结果循环。
- **Mobile**：Task / Code / Result 三个明确 tab；切换不丢失代码和运行结果，AI 位于 Result/Help 的 contextual sheet。

### 7.3 Review workspace

```text
Review Hub → selected item → contextual Learning/Practice Workspace → mastery/attempt update → next review item or return to queue
```

Wrong Questions、Review Due、Weak Knowledge、Practice Again 是同一队列的来源标签，不是四套 UI。Review Session 只呈现当前复习动作和其来源/上下文；完成后更新可用的状态，再推荐下一条，而非把用户抛到错误本首页。

## 8. Search and Resource context restoration

| Entity | Search preview | Destination | Context restoration |
| --- | --- | --- | --- |
| Course | course name、domain、可用状态 | Course Detail | 保留 query/filter；课程 breadcrumb 可见 |
| Exam | target name、scope、可用状态 | Exam Target 或受控未开放 target | 返回 Search；目标父级为 Exam World |
| Exam Subject | subject、所属 target、当前状态 | Exam Subject | 显示 target → subject |
| KnowledgePoint | name、所属 course/exam/subject | 带该 Context 的 Node Workspace | node 的 parent context 与 relation 可见 |
| Resource | name、type、所属 context/citation | Resource Reader | reader 保存 `course_id / exam_context / knowledge_point_id / source citation` |
| ProgrammingSkill | skill、language/track | Programming Track 的 skill position | 显示 track → skill |
| Question | question summary、所属 node/type | 相应 Practice/Exam Workspace | 题目归属和返回 Search 均保留 |

目前仅 Resource 的 `/materials/search` 是真实可接入范围；其余统一检索须在后续获得服务端契约后实现。不能用 Generic Detail Page 作为上述实体的统一去处。

## 9. Transition rules

| Transition | Continuity to preserve | Motion / state rule |
| --- | --- | --- |
| Homepage Open Question → Workspace | 同一问题标题、学科/节点、进度位置 | 问题从焦点区进入 Context strip；尊重 reduced motion |
| Exam World → 11408 → Subject | target、stage、milestone/axis | 前进时增加 Context specificity；不重置 target identity |
| Course → Chapter → Node | chapter structure、前置/关联 | 将选中的结构节点保留为 Context 与路径位置 |
| Programming Track → Coding Workspace | language、skill、exercise brief | task 进入 workspace，代码状态不在 Back 时丢失 |
| Resources → Reader → Workspace | material citation、source Context、node link | Ask AI/Start Learning 在同一 Context 中展开，而不是转成独立聊天页 |
| Review Hub → Session → next item | review source、当前 item、剩余队列 | 完成状态更新后平滑替换下一个 item；可退出回队列 |

页面进入/退出只使用有意义的空间连续性，且可被用户打断；不以动画掩盖加载。路由变更后焦点移至主内容；Back 还原任务状态。

## 10. Complete Page Matrix

| Page | Grammar | Parent | Entry points | Primary question / action | Next / Back | Required data | Empty state | Mobile priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Homepage | HOME | Global | root, brand | 我现在继续什么？/Continue | Workspace or Explore / n.a. | recent context, next action | 探索世界 | question + CTA |
| My Learning | HUB | Global | nav | 哪些学习需我处理？/choose queue | child/Workspace / previous | learning summaries | 进入 Explore | Current/Review |
| Current Learning | CONTEXT | My Learning | My Learning, notification | 从哪里恢复？/Continue | Workspace / My Learning | resumable context | Explore | list + CTA |
| Plan | UTILITY | My Learning | child nav, context | 我今天做什么？/start task | Workspace / My Learning | learning tasks, plans | create from Context | today tasks |
| Review | HUB | My Learning | child nav, completion | 先复习哪个？/Start Review | Review Session / My Learning | review center, wrong/retry refs | Current/Explore | next item |
| History | UTILITY | My Learning | child nav | 完成过什么？/open record | contextual history/Workspace / My Learning | records, attempts | start learning | timeline |
| Progress | STRUCTURE | My Learning | child nav, context | 哪条路径需关注？/open node | Context/Workspace / My Learning | progress, map where available | explain start condition | attention nodes |
| Explore | HUB | Global | nav, empty state | 我想学什么？/choose world | World / previous | available worlds/contexts | scope explanation | worlds |
| Resources | HUB | Global | nav, contextual link | 找哪份资料？/open reader | Reader/Workspace / previous | materials, search/status | upload or Context | query/list |
| Exam World | WORLD | Explore | Explore, deep link | 备考哪个目标？/open target | Target / Explore | real target catalog | only 11408 enabled | 11408 |
| 11408 Target | CONTEXT | Exam World | World, fast path | 四科下一步？/Continue | Subject/Workspace / Exam World | target/subject summaries | choose subject | next + subjects |
| Exam Subject | CONTEXT | 11408 | Target, search | 本科下一步？/Continue | Node/Workspace / 11408 | subject dashboard/outline/plan | begin from outline | current node |
| Exam Module / Node | STRUCTURE | Subject | Subject, search | 如何学/练本节点？/choose action | Workspace / Subject | outline, questions, state | return Subject | node/action |
| Course World | WORLD | Explore | Explore, deep link | 学哪门课？/open course | Course Detail / Explore | course catalog/status | scope explanation | current course |
| Course Detail | CONTEXT | Course World | World, search | 下一知识点？/Continue | Node Workspace / Course World | course progress/today plan/map | start course path | next node |
| Chapter | STRUCTURE | Course Detail | course, breadcrumb | 本章怎样展开？/open node | Workspace / Course Detail | node outline/relations | return Course | nodes/location |
| Learning Workspace | WORKSPACE | Node/Review/Reader | continue, node, review | 怎样完成学习？/complete action | Next/context / source | context, content, question, state | explain + parent exit | content/action |
| Resource Reader | WORKSPACE | Resources/Context | Resources, contextual link | 资料如何帮助学习？/Ask AI or Start | Workspace/Context / source | preview, links, citation | parsing state/retry | reader |
| Programming World | WORLD | Explore | Explore, deep link | 哪个语言/轨道？/open track | Track / Explore | programming home/onboarding | onboarding/scope | current track |
| Programming Track | CONTEXT | Programming World | World, fast path | 下一练习？/Start | Coding Workspace / World | exercises, track state | no exercise explanation | next exercise |
| Programming Skill | STRUCTURE | Track | Track, search | 练哪项技能？/start exercise | Coding Workspace / Track | skills/exercises | return Track | skill list |
| Coding Workspace | WORKSPACE | Exercise | track/skill/continue | 如何让代码通过？/Run-Test-Submit | next exercise/Track / source | exercise, run/test/submit | retain code + retry | Task/Code/Result |
| Search | UTILITY | Global | Search control, shortcut | 目标在哪里？/open result | typed destination / source | query + available entity index | query refinement | query/results |
| Profile | UTILITY | Global | Profile control | 如何管理账户？/save setting | Profile/child / previous | profile/entitlements | complete profile | identity/settings |

## 11. Page graph validation

```text
Homepage ─────────────────────────────────────────→ Learning Workspace
My Learning → Current / Plan / Review / History / Progress ─────→ Context or Workspace
Explore → Exam World → 11408 → Subject → Node ─────────────────→ Learning Workspace
        → Course World → Course → Chapter → Node ──────────────→ Learning Workspace
        → Programming World → Track → Skill ───────────────────→ Coding Workspace
Resources → Reader ─────────────────────────────────────────────→ Contextual Workspace
Search ─────────────────────────────────────────────────────────→ typed Context destination
```

- **Dead ends**: 0 by design. Reader, empty states, unavailable targets and errors all have an action plus semantic parent exit.
- **Circular navigation**: no required loop. Review can advance within a session but always offers queue exit; Context ↔ Workspace is purposeful stateful return, not a trap.
- **Duplicate responsibility**: wrong questions are Review sources; Plan is a My Learning utility; Search is locator only; Knowledge Graph is a cross-context structure capability.
- **Unnecessary intermediate pages**: World and Structure are skippable whenever the user has a resolved context/node. Context is required only when no exact action target exists or when it provides a needed decision.

## 12. First implementation vertical slice (design only)

```text
Homepage → Exam World → 11408 → Operating System → Knowledge Node → Learning Workspace
```

| Segment | Status in the slice | Data boundary |
| --- | --- | --- |
| Homepage | **Required as existing frozen entry** | Visual example exists; real continuation adapter still needed |
| Exam World | **Skippable** for a known 11408/OS learner; required for discovery | No audited unified exam catalog endpoint; render only real 11408 availability |
| 11408 Target | **Required** for target-level orientation and four-subject selection | `/exam/11408/study-plan/summary`, task summary and subject dashboard data exist |
| Operating System Subject | **Required** for subject context when target node is unresolved | `/exam/11408/subjects/{subject_key}/dashboard-summary`, study-plan, outline/practice/stat APIs exist |
| Knowledge Node | **Skippable** for a Continue/deep link with a canonical node; required for first-time structure choice | chapter practice outline/questions and knowledge-point progress are available in scoped forms; unified node adapter may be needed |
| Learning Workspace | **Required** to actually learn/practice | question attempts/submit, AI questions, past papers, wrong questions and learning state endpoints exist, but a single workspace composition adapter is required |

### Do not fake in this slice

- A unified cross-world Next Action Service; use clearly scoped 11408/subject plan or dashboard data until it exists.
- A fully unified knowledge graph/RAG relation set for Operating System; show only relations backed by real data.
- A universal exam catalog or search result set beyond known 11408 data.
- Dedicated Notes persistence or inferred mastery values beyond endpoint-supported state.

### Required future adapters (not this phase)

1. Resolve a canonical `ExamLearningContext` from subject, chapter/node and resume state.
2. Translate existing 11408 dashboard/plan/outline data into `CURRENT / NEXT / ACTION / PATH` view data without changing the backend contract.
3. Map existing question, attempt and submit APIs into a contextual practice action while preserving Subject/Node identity.
4. Define honest loading, unavailable and error payloads for pages whose broad catalog/search API is absent.

## 13. Implementation guardrails

- This system is a design baseline; it does not authorize implementation of any page.
- Each future page change must be a small slice and must state the exact file(s) to be changed before modification.
- Use the existing Academic Lab language without cloning the Homepage deep-ink Hero across internal pages.
- Future page implementation must preserve keyboard navigation, visible focus, semantic labels, state-not-only-by-color, context-preserving Back behavior, and responsive workspace composition.
- No backend or database migration is implied by this document. Any adapter that reveals an API gap must be designed and approved separately.
