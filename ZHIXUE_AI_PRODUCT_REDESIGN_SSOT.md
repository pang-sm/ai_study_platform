# ZHIXUE_AI_PRODUCT_REDESIGN_SSOT

> 智学AI——计算机学习智能体  
> Clean-Slate 产品重构唯一事实与规划标准（Single Source of Truth）  
> 版本：2026-09-15  
> 用途：以后开启任何新对话时，优先上传本文件；新对话必须先读取本文件，再决定当前处于哪个 STEP。  
> 本文件同时区分：**CURRENT（当前事实） / FROZEN TARGET（已冻结目标） / NEXT（下一步）**。  
> 若未来本地代码、数据库或部署状态发生变化，以新的只读事实审计覆盖 CURRENT；不得反向修改已冻结科学语义。

---

# 0. 使用规则

## 0.1 本文件的优先级

后续任何 AI / Claude / Codex / ChatGPT 在本项目中的工作，必须按以下优先级理解项目：

1. **当前本地工作树与数据库的只读事实审计**
2. **本文件中的 FROZEN TARGET**
3. 当前对话中用户最新明确决策
4. 历史文档 / 历史截图 / 旧前端 / 旧产品逻辑

禁止：

- 根据旧 UI 猜现在的产品；
- 把“规划”写成“已实现”；
- 把“某科学组件能运行”写成“已产品化”；
- 把历史会员体系继续当成未来会员体系；
- 因为 `main.py` 很大就推倒全部后端；
- 因为 Clean Slate 就删除静态题库、知识点、编程题和 Scientific Runtime；
- 恢复旧前端。

---

# 1. 产品总定义

智学AI不是三个网站拼在一起。

正式定义：

> **一个统一账户、统一会员、统一 AI 与学习智能底座之上的多场景个人学习系统。课程学习、计算机考研 11408、编程学习是三个领域化学习空间；资料、AI、练习、错题、复习、计划、学习记录、学习状态与模型能力构成跨场景共享的学习操作系统。**

整体结构：

```text
智学AI
│
├─ 统一账户
├─ 统一会员
├─ 统一 Usage Credits
│
├─ Learning Spaces
│  ├─ course_learning
│  ├─ exam_11408
│  └─ programming
│
├─ Learning Core
│  ├─ materials
│  ├─ knowledge
│  ├─ practice
│  ├─ wrong_answers
│  ├─ review
│  ├─ planning
│  ├─ records
│  └─ reports
│
├─ AI Layer
│  ├─ AI Orchestrator
│  ├─ Capability
│  ├─ Qualified Model Pool
│  ├─ Router
│  └─ External AI Gateway
│
├─ Learner Intelligence
│  ├─ Data Plane
│  ├─ Data Producer
│  └─ Scientific Runtime
│
└─ Platform Core
   ├─ auth
   ├─ users
   ├─ subscription
   ├─ usage
   ├─ payments
   └─ admin
```

核心原则：

```text
三个业务空间
+
一套学习操作系统
```

而不是：

```text
三套学习产品
+
三套会员
+
三套 AI
```

---

# 2. 长期技术栈（FROZEN）

正式技术路线：

```text
React / Vite / TypeScript
        ↓
Python FastAPI Product Backend
        ↓
ordinary business logic
External AI Gateway
Product Data Plane
Python Data Producer Worker
        ↓ localhost HTTP
Python Scientific Runtime Service
        ↓
zhixue_runtime
        ↓
13 scientific components
```

## 2.1 明确取消

```text
JAVA_BACKEND = CANCELLED
```

以后不再讨论 Java 后端重写。

## 2.2 Scientific Runtime 红线

Product Backend 不允许直接 import：

```text
torch
transformers
faiss
zhixue_runtime
```

科学模型必须在独立 Scientific Runtime Service 内运行，并通过 localhost HTTP 调用。

---

# 3. 前端状态与前端原则

## 3.1 CURRENT

2026-09-15 本地审计确认：

```text
OLD_FRONTEND_RESURRECTED = NO
```

当前 `frontend/` 只有新前端基础与新首页：

```text
routes/
  __root.tsx
  index.tsx

features/
  home/
```

旧的：

```text
Course
11408
Programming
Profile
Admin
Login
Register
Dashboard
Materials
Chat
Study Plan
```

完整旧 UI 未恢复。

## 3.2 FROZEN TARGET

未来前端必须基于当前新首页设计语言继续扩展。

禁止：

- 恢复旧页面；
- 从旧 frontend 复制 UI；
- 用旧 Dashboard 作为新首页基础；
- 因后端旧 API 仍存在就恢复对应旧页面。

前端技术偏好：

- React
- Vite
- TypeScript
- TanStack Router
- TanStack Query
- React Hook Form
- Zod
- Tailwind CSS
- Radix Primitives
- openapi-fetch/typescript

原则：

> 硬核、稳定、现代；允许稳定的新能力，不追实验性技术。

---

# 4. 三档统一会员（FROZEN）

所有学习空间统一：

```text
Free
Standard
Advanced
```

禁止：

```text
course membership
11408 membership
programming membership
```

统一四层架构：

```text
Subscription
↓
Capability Permission
↓
Usage Budget
↓
Model / Workflow Router
```

---

# 5. 三档会员的产品定位

## 5.1 Free

Free 必须完成真实基础学习闭环，而不是残废 Demo：

```text
资料
→ 理解
→ 练习
→ 错题
→ 任务
→ 学习记录
```

Free 允许：

- 三个学习空间全部进入；
- 静态题库；
- 基础资料；
- 基础 AI 限量；
- 基础练习；
- 错题；
- 基础计划；
- 学习记录；
- 一次 StudentTwin 初始快照。

## 5.2 Standard

Standard 定位：

> 正常长期学习用户。

核心：

```text
Daily Usage Credits
+
Weekly Usage Credits
```

解锁：

- 更高 AI 用量；
- 强推理；
- 长资料；
- 图片理解；
- 自适应练习；
- 连续学习状态；
- 智能复习；
- AI 学习计划；
- 编程 Agent（有限）；
- 更深入学习报告。

## 5.3 Advanced

Advanced 定位：

> 高频、高成本、自动化学习用户。

会员层：

```text
NO membership daily cap
+
higher weekly Usage Credit cap
```

仍然必须有：

```text
rate limit
abuse protection
concurrency limit
```

高级能力：

- 高模型预算；
- Premium model pool；
- 高级 Agent；
- 自动学习工作流；
- 深度分析；
- 多资料综合；
- Personalized Router；
- 完整 Model Feedback；
- 高成本媒体类教学工作流。

---

# 6. Usage Credits（FROZEN）

不采用 token 数直接面向用户计费。

内部实际成本：

```text
C =
C_input
+ C_output
+ C_cache
+ C_tool
+ C_media
```

文本成本：

```text
C_text =
Tin / 1e6 * Pin
+
Tout / 1e6 * Pout
```

内部统一映射：

```text
Actual Provider Cost
→ Usage Credits
```

可参考：

```text
1 Credit ≈ ¥0.01 平台模型成本
```

但该换算暂不最终冻结，必须等真实 Provider 成本和会员定价确认。

Standard：

```text
daily_remaining >= estimated_cost
AND
weekly_remaining >= estimated_cost
```

Advanced：

```text
weekly_remaining >= estimated_cost
```

Advanced 不代表无限调用。

---

# 7. Usage 执行模型（FROZEN）

AI / Workflow 应采用：

```text
estimate
↓
reserve
↓
execute
↓
actual
↓
settle
```

支持：

```text
refund
partial settlement
provider failure
platform failure
user cancellation
```

必须建设：

```text
usage_budgets
usage_ledger
ai_requests
ai_cost_records
```

不能只维护：

```text
used_today = X
```

---

# 8. 用户侧模型选择（FROZEN）

用户永远不能看到整个 provider registry。

结构：

```text
Capability
↓
Qualified Model Pool
↓
User-visible small model list
```

默认：

```text
自动推荐
```

示例（非最终 benchmark 冻结）：

### 普通问答

```text
自动
豆包 Seed Mini
Qwen Flash
DeepSeek Flash
```

### 强推理

```text
自动
DeepSeek Pro
Qwen Max
Doubao Pro
```

### Programming Agent

```text
自动
Kimi Code
DeepSeek Pro
Qwen Coder
```

### 图片理解

```text
自动
Qwen VL Flash
Qwen Flash
Qwen Max
```

实际可选模型必须经过 Zhixue Benchmark 后冻结。

---

# 9. Router 路线（FROZEN）

Free：

```text
Task × Cost
```

Standard：

```text
Task × Quality × Cost
```

Advanced：

```text
User × Task × Model × Quality × Cost
```

Router 演进：

```text
V0: Capability + Tier + Budget
V1: + Quality + Cost + Latency + Availability
V2: + User Preference + Feedback History + Task Characteristics
```

禁止一开始为了“智能”就训练复杂 Router。

---

# 10. Model Feedback（FROZEN）

反馈不是 Chat 上随便两个按钮，而是独立数据资产。

建议字段：

```text
user_id
request_id
response_id
workflow_id
capability
task_type
selected_model
router_recommended_model
thumbs_up
feedback_reasons
regenerated
switched_model
switched_to_model
latency_ms
estimated_cost
actual_cost
verifier_score
downstream_result
context
timestamp
```

负反馈可包含：

```text
incorrect
too_shallow
too_complex
too_verbose
too_brief
bad_code
slow
poor_image
other
```

Advanced 用户是 Personalized Router 的核心反馈来源。

训练流程：

```text
collect
→ offline analysis
→ Champion / Challenger
→ validation
→ Router update
```

禁止：

> 用户一次 dislike → 在线立刻训练 Router。

---

# 11. 完整功能地图（FROZEN）

一级功能域：

```text
Account
Subscription
Home
Learning Space
Materials
AI Tutor
Knowledge
Practice
Wrong Answers
Review
Planning
Records
Learner State
Reports
Programming Workbench
AI Workflows
Model Feedback
Data Plane
Scientific Runtime
Admin / Operations
```

---

# 12. 用户侧信息架构（TARGET）

一级入口建议：

```text
首页
学习
资料
练习
AI
计划
我的
```

学习：

```text
学习
├─ 课程学习
├─ 11408
└─ 编程学习
```

资料：

```text
资料
├─ 我的资料
├─ 最近资料
└─ 搜索
```

练习：

```text
练习
├─ 今日练习
├─ 题库
├─ 错题
└─ 复习
```

AI：

```text
AI
├─ AI 学习助手
├─ 历史对话
└─ 高级能力
```

计划：

```text
计划
├─ 今日任务
├─ 学习计划
└─ 学习记录
```

我的：

```text
我的
├─ 学习状态
├─ 学习报告
├─ 会员
├─ 使用额度
└─ 设置
```

原则：

```text
学习场景 != 学习工具
```

---

# 13. Course Learning（TARGET）

Context：

```text
user
service_namespace = course_learning
course
chapter
knowledge_point
```

MVP：

- 创建 / 选择课程
- 课程资料
- 章节
- 知识点
- 资料问答
- AI 概念讲解
- 章节练习
- AI 出题
- 错题
- 基础学习状态
- 学习计划
- 学习记录

V1：

- 长教材理解
- 强推理
- 自适应练习
- 智能复习
- 连续 StudentTwin
- 深度错因
- AI 学习计划

Later：

- 跨资料综合
- 自动学习任务
- 深度状态分析

---

# 14. Exam 11408（TARGET）

Context：

```text
service_namespace = exam_11408
subject
chapter
knowledge_point
```

四科：

```text
data_structure
computer_organization
operating_system
computer_network
```

MVP：

- 四科导航
- 知识脉络
- 章节学习
- 真题
- 章节练习
- 错题
- AI 解析
- AI 出题
- 学习计划
- 学习记录
- 科目进度

V1：

- 薄弱章节
- 真题错因
- 自适应练习
- 智能复习
- 11408 学习报告

Later：

- 冲刺自动规划
- 严格验证后的分数 / 能力预测

---

# 15. Programming（TARGET）

核心闭环：

```text
知识
→ 题目
→ 编码
→ 运行
→ 测试
→ 错误
→ AI反馈
→ 修复
→ 再练习
```

MVP：

- 语言选择
- 编程题库
- 题目详情
- Workbench
- 代码编辑
- 运行
- 测试
- 判题
- 提交记录
- AI 解释（限量）
- AI Debug（限量）
- AI 出题
- 学习记录
- 失败题

V1：

- AI 代码优化
- 编程能力画像
- Programming Agent
- Multi-step Debug Agent

Later：

- 自动测试 → 修复 → 重测
- 项目式编程任务

必须区分：

```text
Workbench != Programming Agent
```

---

# 16. Materials（TARGET）

统一 Material Infrastructure：

```text
Material
MaterialFile
ParsedDocument
MaterialChunk
MaterialAsset
MaterialIndex
```

MVP：

- 上传
- 删除
- 重命名
- 分类
- PDF
- DOCX
- TXT
- OCR
- 文本搜索
- 单资料问答
- 引用原文

V1：

- 图片理解
- 长教材
- 多资料检索
- 跨资料问答

Later：

- 自动章节切分
- AI 自动知识结构提取

---

# 17. AI Tutor（TARGET）

统一：

```text
AI Request
+
Capability
+
LearningContext
```

禁止继续：

```text
course_ai
exam_ai
programming_ai
```

三套逻辑。

Capability 建议：

```text
tutor.chat
tutor.strong_reasoning

material.qa
material.long_context
material.vision

question.generate
question.explain

practice.adaptive

programming.explain
programming.debug
programming.agent

planning.generate
planning.adjust

report.generate

media.diagram
media.comic
media.animation
media.video
```

会员绑定 Capability，不绑定具体 Model。

---

# 18. Knowledge（TARGET）

核心实体：

```text
KnowledgeDomain
KnowledgeNode
KnowledgeEdge
UserKnowledgeState
```

关系：

```text
prerequisite
contains
related
similar
depends_on
```

产品层可展示：

- 学习状态
- 进度
- 薄弱点
- 推荐下一知识点

科学语义红线：

> LearnerState 当前输出是 next-response P(correct)，不能直接叫 mastery probability。

---

# 19. Practice（TARGET）

统一流程：

```text
PracticeSession
↓
Question
↓
Attempt
↓
Result
↓
Explanation
↓
LearningEvent
↓
Student State
```

题目来源：

```text
static_question_bank
past_exam
AI_generated
material_generated
programming_exercise
adaptive
```

MVP：

- 题库
- 章节练习
- 作答
- 评分
- 解析
- AI 解析
- AI 出题
- 历史

V1：

- adaptive selection
- difficulty control
- StudentTwin-driven recommendation

---

# 20. Wrong Answers（TARGET）

推荐模型：

```text
PracticeAttempt
↓
WrongAnswerState
```

不是把 Question 永久标错。

需要保留：

```text
Question
UserAnswer
CorrectAnswer
Context
ErrorAnalysis
ReviewStatus
```

未来应支持：

```text
第一次错
第二次错
第三次对
已复习
再次遗忘
```

---

# 21. Review（TARGET）

统一：

```text
ReviewItem
ReviewSchedule
ReviewAttempt
ReviewHistory
```

复习来源：

```text
知识点
错题
资料笔记
编程失败题
AI生成题
```

MVP：

- 手动加入
- 复习任务
- 固定规则

V1：

- 智能复习
- 动态复习时间
- 表现反馈
- 自动加入今日任务

`memory` scientific component 只有在真实：

```text
interval
rating
lapse
review_history
```

存在后才能产品化。

禁止伪造输入。

---

# 22. Planning（TARGET）

层级：

```text
Goal
↓
Plan
↓
Task
```

MVP：

- 学习目标
- 手动计划
- AI 计划
- 今日任务
- 完成状态

V1：

- 按进度调整
- 按错误调整
- 插入智能复习
- 自动重排

Later：

- 持续自动规划

---

# 23. Learning Records（TARGET）

至少覆盖：

```text
MaterialEvent
AIEvent
PracticeEvent
WrongAnswerEvent
ReviewEvent
PlanEvent
ProgrammingEvent
KnowledgeEvent
```

典型 event_type：

```text
question_answered
question_correct
question_wrong
material_opened
material_asked
ai_question_asked
review_completed
code_submitted
code_failed
code_passed
knowledge_status_changed
```

Free 用户也必须完整记录真实关键学习事件。

付费差异体现在分析能力，而不是“不给 Free 保存数据”。

---

# 24. Learner State / StudentTwin（FROZEN）

用户看到：

```text
当前学习状态
薄弱知识
近期变化
需要复习
推荐下一步
```

前端不暴露具体 scientific component。

数据流：

```text
Learning Events
↓
Data Producer
↓
StudentTwin
↓
Learner State
↓
Home / Practice / Plan / Review / Reports / AI Context
```

Free：

```text
initial snapshot = 1 time
```

Standard / Advanced：

```text
continuous update
```

---

# 25. Reports（TARGET）

基础报告来自确定性数据：

```text
学习时间
题量
正确率
课程进度
编程通过数
复习次数
```

智能报告：

```text
Structured Metrics
+
Learner State
+
Scientific Signals
+
LLM explanation
```

正确架构：

```text
DB / Data Plane
↓
Report Data Builder
↓
Structured Report Data
↓
LLM
↓
Narrative
```

禁止让 LLM 直接“凭感觉”描述学习状态。

---

# 26. 高级 AI Workflows（TARGET）

独立于普通 Chat：

```text
AI Workflow
```

例如：

- Strong Reasoning
- Programming Agent
- Interactive Demo
- Best Answer
- Teaching Diagram
- Comic
- Animation
- Video

每个 Workflow：

```text
multi-step
→ multiple model calls
→ independent cost estimate
→ reserve credits
→ execute
→ settle
```

漫画 / 动画 / 视频不进入 MVP。

---

# 27. FastAPI 目标模块架构（FROZEN）

建议：

```text
backend/
└─ app/
   ├─ core/
   ├─ auth/
   ├─ users/
   ├─ subscriptions/
   ├─ usage/
   │
   ├─ learning/
   │  ├─ spaces/
   │  ├─ knowledge/
   │  ├─ practice/
   │  ├─ wrong_answers/
   │  ├─ review/
   │  ├─ planning/
   │  ├─ records/
   │  └─ reports/
   │
   ├─ materials/
   ├─ course_learning/
   ├─ exam_11408/
   ├─ programming/
   │
   ├─ ai/
   │  ├─ gateway/
   │  ├─ routing/
   │  ├─ capabilities/
   │  ├─ workflows/
   │  ├─ feedback/
   │  └─ cost/
   │
   ├─ learner_intelligence/
   ├─ data_plane/
   ├─ scientific/
   ├─ payments/
   └─ admin/
```

最终 `main.py` 只负责：

```text
create_app
middleware
router registration
startup / shutdown
exception handlers
```

---

# 28. 后端四层架构（FROZEN）

## Layer A: Platform Core

```text
auth
users
subscriptions
usage
payments
core
```

## Layer B: Learning Core

```text
materials
knowledge
practice
wrong_answers
review
planning
records
reports
```

## Layer C: Domain Spaces

```text
course_learning
exam_11408
programming
```

## Layer D: Intelligence

```text
ai
learner_intelligence
scientific
data_plane
```

依赖方向：

```text
Domain Spaces
↓
Learning Core
↓
Platform Core
```

智能能力：

```text
Domain / Learning
↓
AI Orchestrator
↓
Gateway
```

或：

```text
Learning
↓
Learner Intelligence
↓
Scientific Runtime Client
```

禁止循环依赖。

---

# 29. LearningContext（FROZEN）

统一 Context：

```text
user_id

service_namespace:
  course_learning
  exam_11408
  programming

course_id?
subject?
chapter_id?
knowledge_point_id?

programming_language?
exercise_id?

material_ids?
session_id?
```

公共能力复用 Context，而不是写：

```text
/course-ai
/exam-ai
/programming-ai
```

三套重复系统。

原则：

> 资源 API 按领域；公共能力 API 按能力。

---

# 30. AI 架构（FROZEN）

完整链：

```text
Capability
↓
Permission / Budget
↓
Model Router
↓
Provider Gateway
↓
Post-processing / Logging
```

示例：

```text
question.explain
↓
Capability Permission
↓
Cost Estimate
↓
Qualified Model Pool
↓
Router
↓
Provider
↓
Result validation
↓
Usage settlement
↓
AI Event
```

---

# 31. AI Gateway 与 AI Orchestrator 区分（FROZEN）

Gateway：

> 怎么调用某个模型。

Orchestrator：

> 为什么调用、调用几次、如何组合。

例如：

```text
Best Answer
=
Model A
+
Model B
+
Verifier
+
Finalizer
```

这是 Orchestrator，不是 Gateway。

---

# 32. Data Plane（FROZEN）

分四类：

```text
Operational State
Event Stream
Derived Features
Scientific State
```

Operational State：

```text
当前计划
错题列表
当前课程
会员状态
```

Event Stream：

```text
question_answered
material_opened
ai_called
review_completed
code_failed
...
```

Derived Features：

```text
accuracy_7d
response_time_mean
hint_rate
review_lapse_count
practice_frequency
```

Scientific State：

```text
StudentTwin snapshot
future scientific outputs
```

---

# 33. Learning Event（TARGET）

统一 Event Envelope：

```text
event_id
user_id
event_type
service_namespace
context
occurred_at
source
payload
schema_version
```

必须有：

```text
schema_version
```

避免产品字段变化让 scientific pipeline 全部失效。

---

# 34. Data Producer（FROZEN）

原则：

```text
Product Event / Product State
↓
Data Producer
↓
Validated Scientific Input
↓
Scientific Runtime
```

Scientific Runtime 不应自己随意查 Product DB。

第一版可以：

```text
Python Worker
+
DB polling / job queue
```

暂不引入 Kafka。

---

# 35. Scientific Runtime Productization Gate（FROZEN）

任何 scientific component 上线必须经过：

```text
Runtime Pass
↓
Input Availability
↓
Ontology Compatibility
↓
Domain Compatibility
↓
Offline Validation
↓
Shadow Mode
↓
Decision Influence
↓
Production
```

状态建议：

```text
RUNTIME_ONLY
SHADOW
ADVISORY
ACTIVE
DISABLED
```

能运行：

```text
!=
```

能产品化。

---

# 36. 13 个 Scientific Components（FROZEN SCIENTIFIC SEMANTICS）

## 36.1 concept_verifier

当前偏向：

```text
Verifier / observation
```

不一定作为直接用户功能。

## 36.2 difficulty_prior

可运行，但产品化前必须验证：

- BGE-M3 preprocessing
- domain compatibility

## 36.3 misconception_v2

定义：

```text
BGE-M3
→ L2 normalize
→ FAISS IndexFlatIP
→ Eedi misconception retrieval
```

score：

```text
cosine-like inner product
```

不是 probability。

产品化前必须做 domain compatibility 验证。

## 36.4 tutor_policy

Action ontology：

```text
focus
generic
probing
telling
```

## 36.5 tutor_guard

Action ontology 同样：

```text
focus
generic
probing
telling
```

绝对不能改写为：

```text
ALLOW / REJECT
```

## 36.6 memory

必须等真实：

```text
review history
interval
rating
lapse
```

存在。

禁止 fabricated input。

## 36.7 IRT

公式：

```text
p = sigmoid(theta - b[item])
theta_new = theta + (correct - p)
```

定义：

> online 1PL-style theta update under fixed item difficulty

不是：

```text
EAP
MAP
MLE
```

## 36.8 planner

需要先解决 product plan ontology 对齐。

## 36.9 student_twin

定义：

```text
deterministic rule-based state engine
```

不是 neural network。

当前产品化优先级最高。

## 36.10 execution_router

未来可用于 execution / routing 决策层。

## 36.11 domestic_registry

属于 Router infrastructure。

不是用户直接功能。

## 36.12 evidence_reliability

输出：

```text
w = reliability weight
```

绝对不能写：

```text
P(correct)
```

产品化前需要真实：

```text
response_time_ms
hints
attempt history
```

等输入。

## 36.13 learner_state

输出：

```text
next-response P(correct)
```

不是 mastery。

目前存在 ontology gap。

---

# 37. CURRENT LOCAL AUDIT — 2026-09-15

以下为 Claude 对：

```text
C:\Users\26477\Desktop\ai_study_platform
```

执行只读事实审计后的 CURRENT。

## 37.1 Git / Worktree

```text
HEAD =
95b7dccc83b5546ee660969447fb6a8a4fcbe060

HEAD message =
feat: add learning event data plane foundation

branch =
main

origin/main =
e1a34a14d821bf989e3cf68e416465bc8fc8f83e

MERGE_BASE =
81277a155dbb87cfda90652be48c44816f984528

AHEAD = 15
BEHIND = 12
RELATIONSHIP = DIVERGED
```

关键状态：

```text
WORKTREE_CLEAN = NO
STAGED = 0
```

本地状态不是简单“main 已同步”。

审计结论（STEP 5A 已逐字节核实）：

> 本地是旧 HEAD + 大量未跟踪 Phase 2–7 代码 + 已清空用户数据的数据库。

两分支在 `81277a15`（pre-frontend-rebuild-20260910）处分叉，沿两条互补轴演进：

- **local HEAD / working tree**：新 TypeScript 前端 + 设计冻结 + auth-v2 改动 + `backend/routers/health.py`
- **origin/main**：Phase 2–7 智能底座（backend/core、backend/ai、完整 data_plane、scientific_runtime_service、deploy/artifacts、phase scripts、workflows）

大量 untracked Phase 文件已确认：

```text
WORKTREE COPY == origin/main blob（逐字节 hash 一致）
```

包括 `backend/core/`、`backend/ai/`、`backend/data_plane/` 额外文件、`scientific_runtime_service/`、`deploy/artifacts/`、phase scripts、workflows。

同时仍有真正 LOCAL_ONLY：

```text
backend/routers/health.py
backend/main.py auth-v2 working-tree changes
backend/schemas.py auth-v2 changes
backend/tests/test_auth_v2.py
backend/scripts/auth_v2_acceptance.py
backend/scripts/clean_user_reset.py
backend/scripts/generate_online_workbench_random_sample.py
```

因此继续保留红线：

```text
NO reset
NO clean
NO overwrite
```

直到后续正式 Git reconciliation。

---

# 38. CURRENT Frontend

```text
OLD_FRONTEND_RESURRECTED = NO
```

当前只有新首页前端。

禁止恢复旧 frontend。

---

# 39. CURRENT Backend

当前仍是 FastAPI 单体。

约（2026-09-16 只读复核）：

```text
359 business HTTP endpoints
  = main.py 349
  + routers/health.py 2
  + routers/ai_models.py 1（STEP7C 新增）
  + routers/subscription.py 7（STEP7B 新增）
3 WebSocket route registrations（2 handler）
4 framework endpoints（openapi / docs / redoc）
63 SQLAlchemy models
45 test files（44 个测试文件 + conftest.py）
322 tests collected
```

统计口径：HTTP endpoint = `main.py` 中 `^@app.<method>(` 装饰器数 + `routers/*.py` 中
`^@router.<method>(` 装饰器数；WebSocket 按注册路径计，
`/api/code/interactive-run` 与 `/code/interactive-run` 指向同一 handler。

其中（`main.py` 内的路由分布，2026-09-15 审计）：

```text
/admin = 72 routes
/exam ≈ 47+
/code = 33
/course-learning = 25
/learning = 24
/practice = 21
/me = 19
/materials = 18
/membership = 15
/programming = 13
```

`main.py` 仍承担大量业务职责。

> 注意区分：§56.3 的 API disposition 矩阵（`BUSINESS_HTTP_ENDPOINTS = 351`）是
> **FROZEN 的冻结分类基线**，不随之后的 endpoint 增加而改变；
> 本节的 `359` 是当前实时计数，两者口径不同，不得互相覆盖。

---

# 40. CURRENT Database

当前：

```text
USER_PHYSICAL_TABLES = 71
SQLITE_INTERNAL_TABLES = 1（sqlite_sequence）
TOTAL_SQLITE_TABLE_ENTRIES = 72

PRAGMA integrity_check = ok
journal_mode = WAL
foreign_keys = OFF（CURRENT；Clean-Slate 目标对新表 enforce FK）

users = 0
user_service_memberships = 0
membership_orders = 0
ai_usage_logs = 0
study_materials = 1（system reference metadata seed）
```

必须保护的静态资产：

```text
exam_question_bank = 9333
programming_exercises = 1923
knowledge_points = 32（programming_c system ontology，见 §40.1）
```

## 40.1 knowledge_points 归属修正

```text
knowledge_points = 32
username = system
course_id = programming_c
node_key = catalog-480:*
```

即 `knowledge_points` 表当前为 **programming_c 系统知识本体 32 节点**，不是 11408 知识点数量证据。11408 知识脉络能力仍存在，但这 32 行不是它的数量证据。

此外保护：

```text
backend/exam_resources/
backend/static/
backend/data/programming_catalog/
```

---

# 41. CURRENT Membership

当前仍是旧体系：

```text
SERVICE_PLAN_CATALOG
↓
3 service memberships
```

服务：

```text
exam_11408
course_learning
programming
```

当前套餐示例：

```text
exam_11408:
free
monthly_sprint
quarterly_boost
full_exam

course_learning:
free
monthly
quarterly
full

programming:
free
...
```

当前额度：

```text
ai_chat_daily_limit
ai_question_daily_limit
material_upload_limit
...
```

即：

> 固定次数 quota，不是 Usage Credits。

CURRENT：

```text
Unified Subscription = MISSING
Usage Credits = MISSING
Usage Ledger = MISSING
Daily Cost Budget = MISSING
Weekly Cost Budget = MISSING
Cost Reservation = MISSING
Cost Settlement = MISSING
```

Legacy：

```text
users.plan
plan_expire_at
course → course_learning alias
exam / exam_408 → exam_11408 alias
/course-learning/register
```

仍有 runtime 引用。

---

# 42. CURRENT Payments

当前已有：

```text
MembershipOrder
PaymentEvent
MembershipGrant
Refund
RevenueLedgerEntry
```

`payments/` 已有 Provider abstraction。

但：

```text
PAYMENT_PROVIDER = mock
```

非 mock provider 当前不可用。

结论：

> Payment infrastructure 有复用价值；真实支付尚未上线。

---

# 43. CURRENT AI

当前 Provider：

```text
DeepSeek
Qwen
```

DeepSeek：

```text
chat
OpenAI SDK
main.py 直接调用
```

Qwen：

```text
OCR / vision
qwen_parser.py
```

不存在：

```text
Doubao
Kimi
Qualified Model Pool
正式 Model Router
统一 fallback
统一 AI Orchestrator
```

已有：

```text
backend/ai/gateway
backend/ai/providers/deepseek.py
```

但：

> Gateway skeleton 存在，main.py 尚未真正接线。

Prompt：

```text
prompts.py
+
部分 main.py / domain code
```

Usage：

```text
input_tokens
output_tokens
cached_tokens
reasoning_tokens
total_tokens
estimated_tokens
estimated_cost
```

但仍不是 Credits。

---

# 44. CURRENT Materials

真实链路：

```text
upload
↓
parse
↓
study_materials
↓
material_chunks
↓
SQLite FTS5 / BM25
↓
scope filter
↓
Qwen OCR when needed
```

支持：

```text
PDF
DOCX
PPTX
XLSX
TXT
Image
```

CURRENT：

```text
Embedding = NO
Vector DB = NO
Semantic Vector Retrieval = NO
```

现有 Retrieval：

```text
FTS5 / BM25
```

该能力必须保留作为 MVP 基础。

---

# 45. CURRENT Three Learning Spaces

## 45.1 course_learning

后端仍完整存在：

- CourseLearningPreference
- CourseProgress
- LearningRecord
- KnowledgePoint
- Question
- Practice
- AI question generation
- wrong answers
- study plan
- tasks
- reports

前端已移除。

## 45.2 exam_11408

当前拥有：

```text
exam_question_bank = 9333
past papers
chapter practice
AI generated questions
attempts
wrong questions
favorites
study plans
records
```

前端已移除。

## 45.3 programming

当前拥有：

```text
programming_exercises = 1923
code_projects
code_project_files
subprocess execution
submit
progress
AI diagnosis
AI chats
AI generation
```

前端已移除。

---

# 46. CURRENT Practice / Wrong / Review / Plan

当前状态：

> 三个业务空间各自实现了大量能力，但没有形成统一 Learning Core。

CURRENT 缺失统一：

```text
PracticeSession
ReviewSchedule
StudyPlan abstraction
LearningEvent envelope
```

因此：

```text
现有能力 = 资产
现有边界 = 需要重构
```

---

# 47. CURRENT Code Execution

当前：

```text
subprocess
```

不是：

```text
Docker
sandbox
```

仅有 timeout 等基础限制。

缺失强隔离：

```text
CPU
memory
process
filesystem
network
```

MVP 可复用 Workbench 业务能力。

生产级 execution backend 后续必须升级。

---

# 48. CURRENT Data Plane

当前文件：

```text
backend/data_plane/
  __init__.py
  backfill.py
  eligibility.py
  emitter.py
  identity.py
  inference.py
  models.py
  runtime_client.py
  snapshots.py
  worker.py
```

SQLAlchemy 已定义 5 个 model：

```text
LearningEvent       → learning_events
ModelVersion        → model_versions
ModelInferenceRun   → model_inference_runs
ModelPrediction     → model_predictions
LearningOutcome     → learning_outcomes
```

但当前本地物理 DB：

```text
DATA PLANE CODE FOUNDATION = PRESENT
DATA PLANE PHYSICAL TABLES = NOT CREATED
PRESENT = 0
MISSING = 5
```

其中 `learning_outcomes` 产品语义属于 V1（model 已定义但无 producer），其余 4 张为 StudentTwin 链 MVP 所需。

当前：

```text
event_schema_version = 2
worker = manual --once
automatic production = NO
```

结论：

```text
DATA PLANE = READY FOUNDATION
NOT YET PRODUCTIZED
```

---

# 49. CURRENT Scientific Runtime

服务：

```text
scientific_runtime_service/
127.0.0.1:8101
```

已有：

```text
/health
/v1/capabilities
/v1/inference/student-twin
```

Product Backend direct imports：

```text
torch = NO
transformers = NO
faiss = NO
zhixue_runtime = NO
```

13 个组件：

```text
13 / 13 FRESH_NATIVE_PASS
```

但当前 Product Backend 正式工程链只有：

```text
student_twin
```

且：

```text
controls_product_decision = false
```

其余 12 个：

```text
runtime recovered
+
eligibility frozen as INELIGIBLE
+
no Product Backend client
+
no runtime endpoint
+
no real product input chain
+
no product decision control
```

因此：

```text
runtime ready != product ready
```

---

# 50. 当前最重要的 Legacy Inventory

后续必须审计后再删除：

```text
users.plan
plan_expire_at

course → course_learning
exam / exam_408 → exam_11408

/course-learning/register

旧 course_progress 字段 / 路径
/course-dashboard
旧 quota
旧三服务套餐
旧 service entitlement
```

旧前端：

```text
已删除
```

Java backend：

```text
已取消
```

---

# 51. PRESERVATION CRITICAL ASSETS

后续任何 Clean Slate 重构都禁止误删：

## 数据资产

```text
exam_question_bank
programming_exercises
knowledge_points
真题图片
exam_resources
static
programming_catalog
```

## 解析 / Retrieval

```text
document_parser.py
qwen_parser.py
rag.py
FTS5/BM25
```

## Auth

```text
users
auth_sessions
成熟 Cookie/Session
邮箱登录
跨用户保护
```

## Payments infrastructure

```text
payments/
MembershipOrder
PaymentEvent
MembershipGrant
Refund
RevenueLedgerEntry
```

## Programming

```text
Workbench
code_projects
code_project_files
exercise catalog
submit history
```

## Tests

```text
backend/tests/
```

## Scientific assets

仓库外：

```text
D:\ZhixueAI\runtime_package\v1
D:\ZhixueAI\runtime_src\v1
D:\ZhixueAI\model_assets\v1
13-component acceptance
```

## 新 Phase 代码

尤其：

```text
backend/data_plane/
backend/core/
backend/ai/
scientific_runtime_service/
deploy/artifacts/
```

在弄清 Git 关系前绝对不能 clean。

---

# 52. STEP 4 领域级审计结论（FROZEN）

分类：

```text
A = 已完成并值得保留
B = 已实现但需要重构
C = 可复用的数据 / 算法 / 基础设施
E = 旧产品遗留
F = 尚未实现
```

| Domain | Classification |
|---|---|
| Auth | A |
| User 基础 | A |
| 三方向 Onboarding | B / E |
| 旧三方向 Membership | E |
| Orders / Payment infrastructure | C |
| Old quota | E |
| AI usage logs | C |
| Usage Credits | F |
| Usage Ledger | F |
| Materials | A |
| Parser | A |
| OCR | A / B |
| FTS/BM25 Retrieval | A |
| Semantic Retrieval | F / Later |
| Chat Persistence | A |
| AI Gateway | B |
| Capability Router | F |
| Qualified Model Pool | F |
| Knowledge | A / B |
| Course Practice | A / B |
| 11408 Practice | A |
| Programming Exercises | A |
| Wrong Answers | B |
| Unified Review | F + C |
| Planning | B |
| Learning Records | A / B |
| Reports | B |
| Course Domain | B |
| 11408 Domain | A / B |
| Programming Workbench | A / B |
| Code Execution | B / Later execution rewrite |
| Programming AI Debug | B |
| Programming Agent | F |
| Admin Backend | B |
| Data Plane | A / B |
| Data Producer | A |
| Scientific Runtime | A |
| 13 Scientific Components | STEP 6 individually |

---

# 53. 后端总体处置原则（FROZEN）

最重要结论：

> **后端不是“旧到应该推倒重来”，而是“能力成熟、边界过时”。**

因此：

```text
Preserve Capability
!=
Preserve Architecture
```

例如：

```text
Materials 功能要保留
但 Materials 写在 main.py 里的结构不保留
```

`main.py`：

```text
DELETE = NO
KEEP AS-IS = NO
REFACTOR / EXTRACT = YES
```

---

# 54. 数据库 Clean Slate 原则（FROZEN）

过去为了保护用户数据：

```text
additive-only migration
```

长期有效。

但现在：

```text
users = 0
ordinary user data = 0
financial retention = 0
```

因此现在是一次难得的 schema 清场窗口。

原则：

```text
STATIC / CONTENT / SCIENTIFIC DATA
→ 强保护

OLD USER PRODUCT STRUCTURE
→ 精确审计后可删除
```

禁止：

```text
直接删库重建
```

但也禁止继续无限背：

```text
旧表
旧字段
旧 alias
旧 membership compatibility
```

---

# 55. STEP 5 的精确分类标准（FROZEN 2026-09-15）

每个文件 / 表 / API 必须进入以下一种：

```text
KEEP
KEEP + ADAPTER
REFACTOR
REWRITE
DELETE
DEFER
MISSING
```

定义：

## KEEP

当前实现与未来架构一致，可直接保留。

## KEEP + ADAPTER

实现成熟，但需要适配新 Context / namespace / API。

## REFACTOR

业务逻辑有价值，但职责边界需要重构。

## REWRITE

产品概念还需要，但旧实现不适合继续沿用。

## DELETE

新产品不再需要。

## DEFER

暂时保留，但不进入 MVP。

## MISSING

当前完全没有，需要新建。

---

# 56. STEP 5 必须产出的三张清单

## 56.1 Python Files

至少：

```text
main.py
membership.py
models.py
database.py
database_schema.py
rag.py
document_parser.py
qwen_parser.py
programming_execution.py
payments/*
backend/ai/*
backend/data_plane/*
scientific_runtime_service/*
```

每个必须给：

```text
classification
target domain
keep reason
migration plan
delete preconditions
tests affected
```

## 56.2 Database

每张表必须给：

```text
KEEP
MIGRATE
MERGE
DROP AFTER MIGRATION
NEW
```

重点：

- users
- auth_sessions
- user_service_memberships
- membership_orders
- payment_events
- membership_grants
- refunds
- revenue_ledger_entries
- ai_usage_logs
- study_materials
- material_chunks
- questions
- attempts
- wrong answers
- plans
- records
- exam_question_bank
- programming_exercises
- knowledge_points
- learning_events
- model_versions
- model_inference_runs
- model_predictions

## 56.3 API

每个旧 endpoint 必须给：

```text
KEEP
MOVE
DEPRECATE
DELETE
NEW
```

原则：

> 资源 API 按领域；公共能力 API 按能力。

---

# 57. STEP 6 Scientific Model 产品化原则（FROZEN）

按产品需要逐个接入，不按“还有哪个模型没接”接入。

流程：

```text
Feature Need
↓
Select Scientific Component
↓
Validate Inputs
↓
Validate Semantics
↓
Shadow
↓
Measure
↓
Advisory
↓
Active
```

优先级：

## 第一优先级

```text
student_twin
```

原因：

- 当前已有正式工程链；
- 真实 Data Producer 基础存在；
- 语义明确；
- 可服务多个产品模块。

## 后续

```text
difficulty_prior
evidence_reliability
memory
irt
learner_state
misconception_v2
planner
tutor_policy
tutor_guard
concept_verifier
execution_router
domestic_registry
```

必须逐个通过 Productization Gate。

---

# 58. MVP 技术实施顺序（FROZEN）

```text
1. Unified Identity
↓
2. Unified Subscription / Capability / Usage
↓
3. Learning Context
↓
4. Materials Core
↓
5. AI Gateway + Capability Router
↓
6. Practice Core
↓
7. Wrong Answers
↓
8. Records / Data Plane
↓
9. Course Space
↓
10. 11408 Space
↓
11. Programming / Workbench
↓
12. Planning
↓
13. Review
↓
14. StudentTwin
↓
15. Reports
↓
16. Advanced AI
```

Data Plane 必须提前建设，不能最后补。

---

# 59. MVP 范围（FROZEN）

必须形成真实完整闭环：

```text
注册 / 登录
↓
课程 / 11408 / 编程
↓
资料 / 知识
↓
AI 学习
↓
练习
↓
错误
↓
错题
↓
计划 / 任务
↓
学习记录
↓
基础学习状态
```

底层必须有：

```text
Free / Standard / Advanced
Unified Subscription
Capability Permission
Usage Credits
External AI Gateway
Model Pools
Data Plane
Data Producer
Scientific Runtime
StudentTwin
```

---

# 60. V1

MVP 稳定后：

```text
强推理
视觉理解
长教材
多资料检索
智能复习
持续 StudentTwin
自适应练习
深度错因
动态学习计划
学习报告
Programming Agent
Model Feedback
Advanced Router
```

---

# 61. Later

暂缓：

```text
漫画讲解
动画讲解
视频讲解
复杂交互式课件
项目级自动 Programming Agent
实时 Personalized Router 在线学习
高度自动化学习 Agent
复杂多模型协同
分数预测
完整 mastery model
```

这些能力不能拖死核心学习闭环。

---

# 62. Admin TARGET

后台至少分：

```text
用户
商业
AI
学习数据
系统
```

用户：

```text
users
subscription
usage
```

商业：

```text
orders
payments
revenue
refund
```

AI：

```text
providers
models
qualified pools
cost
feedback
router
```

学习：

```text
questions
knowledge
materials
data quality
```

系统：

```text
runtime health
workers
jobs
errors
feature flags
```

---

# 63. Feature Flags（TARGET）

至少支持：

```text
OFF
INTERNAL
PERCENTAGE
TIER
ALL
```

尤其 scientific model：

```text
student_twin_enabled
misconception_shadow_enabled
advanced_router_enabled
```

避免模型 bug 时只能重新部署关闭。

---

# 64. Scientific Versioning（TARGET）

每次 scientific inference 至少记录：

```text
component
version
input_schema_version
output_schema_version
```

必须可追溯。

---

# 65. Observability（TARGET）

AI 请求必须贯穿：

```text
request_id
user_id
service_namespace
capability
model
provider
latency
estimated_cost
actual_cost
status
error_type
```

Scientific Runtime：

```text
runtime_request_id
component
version
latency
status
```

---

# 66. 三空间共享与隔离规则（FROZEN）

统一共享：

```text
Account
Subscription
Usage Credits
Materials Infra
AI Gateway
Scientific Runtime
Learning Record Infra
Data Plane
```

业务隔离：

```text
user_id
+
service_namespace
+
domain_context
```

Context：

```text
course_learning
→ course_id
→ chapter
→ knowledge_point

exam_11408
→ subject
→ chapter
→ knowledge_point

programming
→ language
→ topic
→ exercise
```

Credits 全局共享。

业务数据不得串线。

---

# 67. 禁止的未来结构

不再允许：

```text
course_membership
exam_membership
programming_membership
```

不再允许：

```text
course_chat
exam_chat
programming_chat
```

三套重复 AI。

不再允许：

```text
course_usage
exam_usage
programming_usage
```

三套余额。

正确：

```text
AI Request
+ capability
+ service_namespace
+ context
```

以及：

```text
Usage Ledger
+ capability
+ service_namespace
```

---

# 68. 高风险区

## 68.1 Git / Worktree

当前本地 HEAD 与 origin/main 不一致，且有大量 untracked Phase code。

任何代码改动前必须先做：

```text
git facts reconciliation
```

不得 clean。

## 68.2 main.py

351 HTTP endpoints（+ 2 WebSocket）。

拆分必须：

```text
先建立测试
先建 adapter
按领域抽取
逐步保持 API 兼容
```

禁止 big-bang rewrite。

## 68.3 Membership Migration

风险来自：

```text
users.plan
plan_expire_at
SERVICE_PLAN_CATALOG
UserServiceMembership
service aliases
quota
orders
grant
admin
```

必须先建立新 Unified Subscription，再迁移读路径，最后删除旧字段。

## 68.4 Database

72 表。

必须：

```text
保护静态资产
明确 migration map
备份
integrity check
```

## 68.5 Programming Execution

当前 subprocess，不是 sandbox。

## 68.6 AI Provider Coupling

main.py 多处直连 DeepSeek。

必须先接 Gateway，再删除 direct calls。

## 68.7 Scientific Inputs

Data Plane 本地表当前未创建。

StudentTwin productionization 必须先确保：

```text
event write
producer
runtime client
snapshot
```

完整闭环。

---

# STEP 5 FINAL DISPOSITION SUMMARY（FROZEN 2026-09-15）

```text
STEP5_GIT_REALITY_RECONCILED = YES
STEP5_PYTHON_FILE_MATRIX_FROZEN = YES
STEP5_DATABASE_MATRIX_FROZEN = YES
STEP5_API_MATRIX_FROZEN = YES
STEP5_COMPLETE = YES
```

## Python File Matrix（摘要）

```text
main.py                  = REFACTOR / EXTRACT（!= DELETE，!= REWRITE）
models.py                = REFACTOR BY DOMAIN
schemas.py               = REFACTOR BY DOMAIN
database.py / database_schema.py = REFACTOR toward core DB + formal migrations
document_parser.py       = KEEP
qwen_parser.py           = KEEP + ADAPTER
rag.py                   = KEEP + ADAPTER
programming_execution.py = KEEP for MVP
payments/*               = KEEP / KEEP + ADAPTER
backend/core/*           = KEEP
backend/ai/*             = KEEP / KEEP + ADAPTER
backend/data_plane/*     = KEEP / KEEP + ADAPTER
scientific_runtime_service/* = KEEP
backend/routers/health.py = KEEP
membership.py            = 非整文件 DELETE；legacy 3-service catalog/quota = REWRITE；
                           redemption/entitlement/payment integration = preserve + adapt
```

## Database Matrix（摘要；处置 ≠ 已执行）

```text
KEEP = 29
MIGRATE = 25
MERGE = 14
DROP_AFTER_MIGRATION = 1
DEFER = 2
UNRESOLVED = 0
TOTAL = 71

NEW_PHYSICAL_TABLES_PROPOSED = 20（MVP 16 + V1 4）

当前：NO schema migration executed / NO table dropped / NO new target table created
```

MVP 目标表：subscriptions / usage_budgets / usage_ledger / ai_requests / ai_cost_records / learning_events / model_versions / model_inference_runs / model_predictions / practice_sessions / practice_attempts / wrong_answer_states / review_items / review_attempts / plans / tasks

V1：learning_outcomes / review_schedules / model_feedback / capability_permission_overrides

## API Matrix（摘要；处置 ≠ 已迁移）

```text
BUSINESS_HTTP_ENDPOINTS = 351
WEBSOCKET_ENDPOINTS = 2
FRAMEWORK_ENDPOINTS = 4

KEEP = 259
MOVE = 68
DEPRECATE = 24
DELETE = 0
UNRESOLVED = 0
TOTAL = 351

NEW_API_COUNT = 10（MVP 8 + V1 2）
```

当前所有 path 仍存在，未迁移。

## 存储决策

```text
Capability Permission  = MVP CONFIG（global tier→capability）；V1 optional per-user override table
Feature Flags          = KEEP + EVOLVE app_runtime_flags（不新建 feature_flags 表）
Qualified Model Pool   = CONFIG（非用户 SQL 数据）
Review MVP             = review_items + review_attempts（manual add / task / fixed rule / completion）
Planning MVP           = plans.goal_text + tasks.plan_id（概念 Goal→Plan→Task 不变，MVP 不建独立 goals 表）
```

## 重要区分：TARGET ≠ CURRENT

```text
Unified Subscription  = FROZEN TARGET / NOT IMPLEMENTED
Usage Credits         = FROZEN TARGET / NOT IMPLEMENTED
20 proposed DB tables = FROZEN TARGET / NOT CREATED
10 proposed APIs      = FROZEN TARGET / NOT IMPLEMENTED
shared learning core  = FROZEN TARGET / NOT MIGRATED
```

---

# STEP 6 SCIENTIFIC PRODUCTIZATION SUMMARY（FROZEN 2026-09-15）

```text
STEP6_SCIENTIFIC_PRODUCTIZATION_PLAN = FROZEN
STEP6_COMPLETE = YES

COMPONENT_COUNT = 13
CURRENT: RUNTIME_ONLY = 13 / SHADOW = 0 / ADVISORY = 0 / ACTIVE = 0
```

## 13-component final classification

```text
MVP（SHADOW_ONLY）:
  student_twin

V1_CANDIDATES:
  evidence_reliability
  memory

LATER:
  learner_state
  irt
  tutor_policy
  tutor_guard
  misconception_v2
  planner
  difficulty_prior

RESEARCH_OR_INFRA:
  concept_verifier
  execution_router
  domestic_registry
```

## StudentTwin 冻结状态

```text
CURRENT = RUNTIME_ONLY
MVP_TARGET = SHADOW_ONLY
MVP_USER_VISIBLE_FEATURE = NONE
MVP_ADVISORY = NO
MVP_ACTIVE = NO

StudentTwin runtime pass != product ready

AIQuestionAttempt / ai_question_attempts
  = current only StudentTwin-eligible canonical source

QuestionAttempt / question_attempts
  = ordinary practice flow
  = NOT StudentTwin eligible

EVENT_RELIABILITY_DESIGN_FROZEN = YES
STEP7_BACKFILL_EXTENSION_REQUIRED = NO
```

> 详细证据见 `STEP6_SCIENTIFIC_PRODUCTIZATION_FINAL_REPORT.md`。

---

# 69. 12 STEP 总路线（FROZEN）

```text
STEP 1
三档用户 + 权益
✅ FROZEN

STEP 2
完整功能地图
✅ FROZEN

STEP 3
总体产品 / 技术架构
✅ FROZEN

STEP 4
本地现有实现领域级审计
✅ FROZEN

STEP 5
精确文件 / 数据库 / API 处置矩阵
✅ FROZEN

STEP 6
13 个 Scientific Component 产品化设计
✅ FROZEN

STEP 7
后端实现 / 重构
⏳ IN PROGRESS ← CURRENT（STEP7A/7B/7C/7C-P 已 FROZEN；NEXT = STEP_7D）

STEP 8
API Acceptance

STEP 9
前端信息架构

STEP 10
完整交互页面

STEP 11
E2E

STEP 12
Production Deployment + Public Verification
```

禁止跳 STEP。

---

# 70. 当前下一步（NEXT）

当前 STEP = `STEP_7`；`CURRENT_SUBSTEP = STEP_7C-P`；`NEXT_SUBSTEP = STEP_7D`。

**当前唯一正确动作：STEP 7D。**

已完成并冻结的子步骤：

```text
STEP7A   = FROZEN   Core Backend Foundation + LearningContext + Data Plane SHADOW-ready
STEP7B   = FROZEN   Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost
STEP7C   = FROZEN   External AI Gateway + Qualified Model Pool + Router V0 + Real Cost Integration
STEP7C-P = FROZEN   Provider Onboarding / Live Validation / Model Pool Calibration
```

### STEP 7A 完成标准（历史记录，已全部 PASS）

```text
STEP6_SSOT_WRITEBACK
FORMAL_MIGRATION_FOUNDATION
LEARNING_CONTEXT
DATA_PLANE_4_TABLES
STUDENT_TWIN_MODE
EMITTER
WORKER_SCHEDULABLE
BACKFILL_RECOVERY
RUNTIME_HTTP
PREDICTION_PERSISTENCE
CROSS_USER_ISOLATION
SERVICE_NAMESPACE_ISOLATION
SHADOW_NO_DECISION_INFLUENCE
FRESH_DB
LEGACY_DB_COPY
TARGETED_TESTS
FULL_BACKEND_REGRESSION
```

仍未接入的部分（属 STEP 7D 及之后）：

```text
其余 12 个 scientific component 的产品化接入
```

已在本轮 STEP 7 内实现、**不得再写成「未实现」**：

```text
StudentTwin SHADOW-ready foundation
Unified Subscription / Capability Permission / Usage Budget / Usage Ledger / Cost
External AI Gateway / Qualified Model Pool / Router V0
Provider Onboarding / Live Validation / Model Pool Calibration
```

---

# 71. 新对话启动模板

以后新对话收到本文件后，应首先回答：

```text
已读取 ZHIXUE_AI_PRODUCT_REDESIGN_SSOT。

CURRENT_STEP = STEP_7
CURRENT_SUBSTEP = STEP_7C-P
NEXT_SUBSTEP = STEP_7D

上一阶段：
STEP 1–6 已冻结。

STEP 7 进行中，已冻结的子步骤：
- STEP7A：Core Backend Foundation + LearningContext + Data Plane SHADOW-ready
- STEP7B：Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost
- STEP7C：External AI Gateway + Qualified Model Pool + Router V0
- STEP7C-P：Provider Onboarding / Live Validation / Model Pool Calibration

已完成的既有冻结：
- 13 Scientific Component 产品化设计冻结（student_twin = MVP SHADOW_ONLY）
- Git Reality 已澄清（DIVERGED；untracked==origin；LOCAL_ONLY 已识别）
- Python file disposition 已冻结
- Database migration matrix 已冻结（71 表）
- API disposition matrix 已冻结（351 HTTP endpoint）

当前正处于 STEP 7 后端实现 / 重构进行中（BACKEND_IMPLEMENTATION = IN_PROGRESS）。

下一步：
STEP 7D。
```

保留的重要 CURRENT：

```text
Git diverged；NO reset / NO clean
新前端 only（旧前端未恢复）；全新前端 = NOT_STARTED
71 user physical DB tables（+ sqlite_sequence = 72）
static assets protected（9333 / 1923 / 32）
legacy three-service membership 仍为 CURRENT（目标 = 统一 Free / Standard / Advanced）
Unified Subscription / Usage Budget / Usage Ledger 已建立（STEP7B）；BUDGET_AMOUNTS_STATUS = PROVISIONAL
External AI Gateway 已接线（STEP7C）；question-analysis 已迁移到 orchestrator
Data Plane：learning_events / model_* 4 张表已建（STEP7A）
Scientific Runtime 13/13 runtime pass；仅 StudentTwin 有正式 Product Backend 链（RUNTIME_ONLY）
```

如果新对话直接提出新的实现任务，也必须先判断该任务属于哪个 STEP。

---

# 72. 最终项目红线

永远不得违反：

1. Java Backend 已取消。
2. 不恢复旧前端。
3. 不建立三个独立会员。
4. 不把三个学习空间拆成三个网站。
5. 不直接把 402 个模型展示给用户。
6. Product Backend 不直接加载 scientific heavy models。
7. Scientific Runtime 与 External AI 必须分层。
8. Scientific component 能运行不代表能产品化。
9. 不改变 IRT / Tutor Policy / Tutor Guard / Misconception / Evidence Reliability / LearnerState / StudentTwin 的科学语义。
10. 不为了接模型伪造产品输入。
11. 不删除 11408、Programming、Knowledge 静态资产。
12. 不因 main.py 很大而全量重写成熟业务。
13. 不让 LLM 凭空生成学习状态。
14. Workbench 与 Programming Agent 必须分开。
15. Free 用户真实学习数据仍应保存。
16. Usage entitlement 与 budget 必须分开。
17. Advanced 不等于无限资源。
18. Router personalization 不做单次反馈在线训练。
19. 生产最终必须部署真实公网并验收，不能停在 localhost。
20. 当前 Git / untracked Phase 代码关系未澄清前，禁止 reset / clean / overwrite。

---

# 73. SSOT 状态

```text
PRODUCT_DIRECTION_FROZEN = YES
MEMBERSHIP_MODEL_FROZEN = YES
FUNCTION_MAP_FROZEN = YES
TARGET_ARCHITECTURE_FROZEN = YES
DOMAIN_LEVEL_AUDIT_FROZEN = YES

FILE_LEVEL_MIGRATION_PLAN = FROZEN
DB_MIGRATION_PLAN = FROZEN
API_MIGRATION_PLAN = FROZEN

STEP5_DISPOSITION_MATRIX = FROZEN

SCIENTIFIC_PRODUCTIZATION_PLAN = FROZEN
STEP6_COMPLETE = YES
BACKEND_IMPLEMENTATION = IN_PROGRESS
NEW FULL FRONTEND = NOT_STARTED
PRODUCTION_REDEPLOY = NOT_STARTED

CURRENT_STEP = STEP_7
CURRENT_SUBSTEP = STEP_7C-P
NEXT_SUBSTEP = STEP_7D

STEP7A = FROZEN（Core Backend Foundation + LearningContext + Data Plane SHADOW-ready）
STEP7A_NOTES = Alembic 基础建立；learning_events/model_* 4 表已建；student_twin_mode
               = OFF/INTERNAL/ADVISORY，经 app_runtime_flags（env > DB > OFF）解析；
               fresh-process runtime acceptance PASS；StudentTwin = SHADOW_READY

STEP7B = FROZEN（Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost）
STEP7B_NOTES = subscriptions/usage_budgets/usage_ledger/ai_requests/ai_cost_records 5 表已建；
               capability permission = CONFIG；reserve→settle→release 幂等 + 并发安全；
               6 个 canonical API；STEP7C 前 Final Reconciliation 闭环——订单改 pending→支付→激活
               （apply_verified_payment unified 分支，复用 membership_orders audit trail）、兑换码改真实
               redemption_codes 表（无 production demo codes）、cost/refund 语义按 provider 实际计费优先
               （settlement matrix + reconciliation_pending）

STEP7C = FROZEN（External AI Gateway + Qualified Model Pool + Router V0 + Real Cost Integration）
STEP7C_NOTES = backend/ai/{gateway,pricing,pool,router,cost,orchestrator} + providers/{deepseek,qwen,fake}；
               qualified model pool / pricing registry / router = CONFIG（无新 SQL 表，HEAD 保持 20260915_0002）；
               AIOrchestrator 统一 permission→router→estimate→reserve→gateway→cost→settle；
               GET /ai/models 上线；question-analysis endpoint 迁移到 orchestrator；
               Scientific Runtime 与 External Gateway 严格分离；BUDGET_AMOUNTS_STATUS = PROVISIONAL

STEP7C-P = FROZEN（Provider Onboarding / Live Validation / Model Pool Calibration）
STEP7C-P_NOTES = 6 Provider 全部配置（deepseek/qwen/doubao/kimi/glm/minimax，canonical env 名冻结）；
                 PROVIDERS_CONFIGURED=6 / AUTH_OK=5 / QUALIFIED=5（Doubao=NO_MODEL_ACCESS，
                 Ark endpoint-id 模式需 ep-xxx 映射）；live /models discovery + minimal smoke 全过；
                 ZHIXUE_MODEL_POOL_CALIBRATION_V1 Stage 2 已执行（qwen3.8-flash/max 6/6，
                 glm-5.3-flash/MiniMax 5/6，deepseek/glm-5/kimi-k2.6 4/6）；MODEL_POOL_VERSION=v3
                 （POOL_QUALIFICATION_LEVEL=FINAL）；PRICING_REGISTRY_VERSION=v3（DeepSeek/Qwen/
                 Kimi/GLM=OFFICIAL_DOC verified，MiniMax=CONSERVATIVE_CEILING）；
                 cross-provider fallback（5 provider）；BUDGET_RECALIBRATION=KEEP（provisional）；
                 CREDIT_NORMALIZATION_STATUS=KEEP_PROVISIONAL
```

---

# 74. 本文件更新规则

只有以下情况允许更新本文件：

1. 用户明确改变产品方向；
2. 完成一个 STEP 并冻结；
3. 新的本地事实审计证明 CURRENT 已变化；
4. Scientific Runtime / Productization 状态经过正式验收变化；
5. Production Deployment 状态发生正式变化。

每次更新必须：

```text
保留 FROZEN scientific semantics
更新 CURRENT facts
更新 CURRENT STEP
更新 completed STEP
```

不得把旧 CURRENT 留作新事实。

---

# END

当前唯一标准结论：

> **智学AI正在从“已有大量后端能力、旧三方向会员、旧 AI 直连架构”迁移为“统一会员 + Usage Credits + 三 Learning Space + Shared Learning Core + AI Router/Gateway + Data Plane + Scientific Runtime”的 Clean-Slate 产品。现有成熟业务与静态资产优先保护，旧产品边界、旧会员和旧额度模型逐步淘汰。STEP 5 的 Python 文件 / 数据库 / API 处置矩阵已冻结，STEP 6 已冻结。当前处于 STEP 7（后端实现 / 重构）进行中：STEP7A / STEP7B / STEP7C / STEP7C-P 均已 FROZEN，CURRENT_SUBSTEP = STEP_7C-P，NEXT_SUBSTEP = STEP_7D。不是立即开发页面，也不是直接重写后端；`main.py` 走 REFACTOR / EXTRACT。**
