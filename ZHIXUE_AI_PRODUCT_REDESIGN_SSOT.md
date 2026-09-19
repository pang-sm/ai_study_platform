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
│  ├─ exam_prep        （CURRENT：只装载 CS408 / legacy 11408；STEP7H0 FD-5）
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

# 14. Exam Prep —— 由「Exam 11408」升级而来

> STEP7H0（域审计 + 架构冻结）与 STEP7H1（canonical namespace + context 兼容基础）
> 均已冻结。设计见 `STEP7H0_UNIFIED_EXAM_PREP_ARCHITECTURE.md`，
> 实施见 `STEP7H1_EXAM_PREP_NAMESPACE_CONTEXT_ACCEPTANCE_REPORT.md`。
> **CURRENT**：namespace 已是 `exam_prep`；实际装载内容 = CS408（legacy 11408 数据，
> 9333 题零改动）；前端已移除。
> **TARGET**：§14.3 的完整全国统考科目范围（math / politics / law / management /
> education / psychology / history …）已在 STEP7H4 的 catalog 中**可表达、可选择**
> （FRAMEWORK_ONLY），但**真实内容尚未导入** —— 导入必须等用户明确批准（STEP7H0 §21）。

## 14.1 产品定义（FROZEN）

Exam Prep 只支持 **全国统一命题 / 全国统考型研究生招生考试科目**。

```text
INSTITUTION_SPECIFIC_EXAMS = OUT OF SCOPE
```

院校自命题专业课、院校 specific exam code、院校 specific syllabus、院校参考书、
院校专业目录自动解析 —— **均不支持**，且**不得**建立
`institution_id` / `school_id` / `college` / `major_code` / `school_exam_code` /
`institution_exam_plan` / `school_specific_subject` 等模型。
（legacy 存在的院校库/目标院校只做 inventory，冻结不再扩展。）

## 14.2 一级概念降级

```text
CURRENT  11408 = 一级业务空间
TARGET   Exam Prep = 一级业务空间；
         11408 = Exam Prep → Computer Science → CS 408 track
```

```text
Learning
├─ Course Learning
├─ Exam Prep          ← 唯一考试空间
└─ Programming
```

## 14.3 Exam Prep 内部结构（CONFIG，非 SQL 表）

```text
ExamTrack     用户选择的完整备考组合/方向
              cs_408 / management_joint / economics_joint /
              law_jm_law / law_jm_non_law / education / psychology / history

ExamSubject   实际考试科目
              公共课      politics / english_1 / english_2 / math_1 / math_2 / math_3
              统考专业课  cs_408 / management_aptitude / economics_joint_aptitude /
                         law_master_law_1|2 / law_master_non_law_1|2 /
                         education_basics / psychology_basics / history_basics
              可扩展位    医学 / 农学 / 其他未来全国统一命题科目（本轮不列具体代码）

ExamModule    Subject 内部具有独立教学结构的组成部分
              cs_408   → data_structure / computer_organization /
                         operating_system / computer_network
              math_1   → calculus / linear_algebra / probability_statistics
              math_2   → calculus / linear_algebra
              math_3   → calculus / linear_algebra / probability_statistics
```

**三者不得合并为一个枚举**；**不得预设一个 Track = 固定的一组 Subject**
（真实公共课组合可因学位类型/院校要求/年份政策而变，模型必须允许用户覆盖默认组合）。

层级：`ExamTrack → ExamSubject → ExamModule → Chapter → KnowledgePoint`，
**全部不新建 SQL 表**：前三级 = versioned CONFIG；Chapter / KnowledgePoint =
已有静态资源（`seed_data/knowledge_maps/*.json` + 题库自带 `knowledge_point_*`）。
**不得**把 `knowledge_points` 表（32 行，属 programming-C ontology）当作 Exam 知识点。

## 14.4 Context（STEP7H1 已实现）

```text
service_namespace = exam_prep          （canonical；exam_11408 等为 INPUT alias）

exam_track_id?        cs_408
exam_subject_id?      cs_408（事件 subject_key 列取此值）
exam_module_id?       data_structure（LearningContext.subject_key 是其 legacy mirror）
chapter_id?
knowledge_point_id?
material_ids?
session_id?
```

继续使用**唯一一个** canonical `core.LearningContext`，未新建 `ExamLearningContext`。

```text
LEGACY_SUBJECT_KEY_MIRROR = exam_module_id
EVENT_SUBJECT_KEY         = exam_subject_id
exam_track_id             → 不进 learning_events、不进任何 identity
```

新增模块 `backend/learning/spaces/exam_prep/{catalog,scope,context,ai}.py`：
CS408 常量 + legacy scope id 纯函数适配器（fail closed）+ `build_exam_context` /
`cs408_context`（endpoint 不手写映射）+ `execute_exam_ai`。

身份冻结（STEP7H1）：practice 行的确定性 uid key 在**冻结 token** 上 ——
`IDENTITY_TOKEN_BY_NAMESPACE = {course_learning: course_learning,
exam_prep: exam_11408, programming: programming}`。改名不会重识别历史 attempt，
且与环境/数据历史无关。

## 14.5 CURRENT：CS408 / legacy 11408（已实测）

```text
CURRENT COMPLETE DATA TRACK = CS408 / legacy 11408
  exam_question_bank = 9333（chapter 9098 / past_paper 235）
  exam 路由 = 52；exam 表 = 14；静态资产 = exam_resources 263 + static/exam_papers 564
  module 身份 = subject_key（data_structure / computer_organization /
                            operating_system / computer_network）
  CS408 mapping = track cs_408 + subject cs_408 + module=subject_key（adapter 解释，
                  9333 行零改动）
```

## 14.6 能力范围

MVP（CURRENT + 后续）：四科导航 / 知识脉络 / 章节学习 / 真题 / 章节练习 / 错题 /
AI 解析 / AI 出题 / 学习计划 / 学习记录 / 科目进度。

V1：薄弱章节 / 真题错因 / 自适应练习 / 智能复习 / 学习报告。

Later：冲刺自动规划 / 严格验证后的分数与能力预测。

> **尚未实现的能力不得写成已实现**。上列除 CURRENT 部分外均为 TARGET/PLANNED。

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
exam_prep        （CURRENT 存储值 = exam_11408；STEP7H1 起 canonical，见 §14 / §29）
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

> **STEP7H1 更新（已实现，FROZEN）**：考试空间的 canonical `service_namespace`
> 已升级为 **`exam_prep`**；`exam_11408` 及 `exam` / `exam_408` / `11408` 降为
> **INPUT alias**（边界归一化一次，绝不落库）。`is_valid_service_namespace("exam_11408")`
> = False；`normalize_service_namespace("exam_11408")` = `"exam_prep"`。
> 同时新增考试专属可选字段 `exam_track_id?` / `exam_subject_id?` / `exam_module_id?`，
> 见 §14.4 与 `STEP7H1_EXAM_PREP_NAMESPACE_CONTEXT_ACCEPTANCE_REPORT.md`。
> 继续只有**一个** canonical LearningContext，未新建 `ExamLearningContext`。
> **仍不改名**：`exam_11408` 作为 legacy 会员 service_key / legacy 额度桶 key /
> 资料域标签的用法属于另一个维度，随统一会员落地一并退役。

统一 Context：

```text
user_id

service_namespace:
  course_learning
  exam_prep
  programming

course_id?
subject?
chapter_id?
knowledge_point_id?

exam_track_id?        （exam_prep）
exam_subject_id?      （exam_prep；事件 subject_key 列取此值）
exam_module_id?       （exam_prep；同时是 context.subject_key 的 legacy mirror）

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

> **STEP7H0 澄清（重要）**：本节出现的 `exam_11408` 是 **legacy 会员 service_key /
> 额度桶 key**，**不是**学习空间 namespace。二者今天共用同一个字符串，但语义不同：
> 学习空间 namespace 将升级为 `exam_prep`（§14 / §29 / STEP7H0 FD-5），
> 而 legacy 会员 service_key **不改名** —— 它随「统一会员」落地而**退役**，
> 不是被改名。审计时不得把两者混为一谈（见 STEP7H0 §5.1 EXAM_NAMESPACE_IMPACT_MATRIX）。

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

## 45.2 exam_11408（= TARGET 的 Exam Prep；CURRENT 只承载 CS408）

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

**STEP7H0 实测补充（CURRENT，只读审计 2026-09-16）**：

```text
exam 路由 = 52（/exam/11408/* 47 + /exam-408/* 4 + /me/tracks/exam_408/package 1）
exam 表   = 14（另共享 practice_sessions/attempts、wrong_answer_states、
               user_knowledge_progress、learning_events）
行数      = exam_question_bank 9333（chapter 9098 / past_paper 235）；其余 exam 用户态表全为 0
静态资产  = backend/exam_resources 263 文件 + backend/static/exam_papers 564 文件
            + seed_data/knowledge_maps/*_11408.json ×4
NEXT      = STEP7H1（canonical namespace → exam_prep）；详见
            STEP7H0_UNIFIED_EXAM_PREP_ARCHITECTURE.md
```

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

已有 endpoint（ACCEL_SPRINT_S4 端点清单审计后的 CURRENT；端点存在 ≠ 组件已产品化）：

```text
/health
/v1/capabilities
/v1/inference/student-twin
/v1/inference/misconception-v2
/v1/inference/tutor-policy
/v1/inference/learner-state
/v1/inference/evidence-reliability
```

`/v1/capabilities` 报告的服务侧组件集合（= 5）：

```text
student_twin
misconception_v2
tutor_policy
learner_state
evidence_reliability
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

但当前 Product Backend 正式工程链仍只有：

```text
student_twin
```

且：

```text
controls_product_decision = false
```

Product Backend 侧另有 4 个**只读 / 非用户可见**的科学面（SHADOW 或 gated capability report）
与 student_twin 并存：

```text
student_twin          PREVIEW                    user_visible
misconception_v2      SHADOW_NOT_USER_VISIBLE    available, 非用户可见
tutor_policy          SHADOW                     available=false（缺真实 turn-state 字段）
learner_state         SHADOW_NOT_USER_VISIBLE    available=false（ontology / calibration）
evidence_reliability  SHADOW_NOT_USER_VISIBLE    available=false（8 条独立 blocker）
```

以上 5 条的权威产品面读数由
`GET /exam/prep/scientific/capabilities` 报告（product-facing readiness，不是端点清单）。

其余 8 个（`memory` / `irt` / `concept_verifier` / `difficulty_prior` / `planner` /
`tutor_guard` / `execution_router` / `domestic_registry`）：

```text
runtime recovered
+
eligibility verdict frozen by data_plane.eligibility（BLOCKED / NOT_APPLICABLE）
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

exam_11408            （CURRENT；TARGET = exam_prep，STEP7H1）
→ subject             （TARGET 细化为 exam_track_id → exam_subject_id → exam_module_id）
→ chapter
→ knowledge_point

programming
→ language
→ topic
→ exercise
```

Credits 全局共享。

业务数据不得串线。

> **STEP7H0 补充（TARGET）**：考试空间的域上下文升级为
> `exam_track_id → exam_subject_id → exam_module_id`。
> `exam_track_id` **不进** learning_events、**不进**任何 identity（track 是用户侧备考组合选择，
> 不是事实属性）；`exam_subject_id` → 事件 `subject_key` 列；`exam_module_id` → 事件 context JSON。

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
CURRENT: USER_VISIBLE_PREVIEW = 1（student_twin）/ RUNTIME_ONLY = 12
         SHADOW_BRIDGE_ONLY = 2（misconception_v2 · tutor_policy —— 仅存在 SHADOW 桥，
                                 不是产品化晋升）
         ADVISORY = 0 / ACTIVE = 0
```

> **ACCEL_SPRINT_S2 修订（2026-09-19，机制 §74-1 用户明确改变产品方向）。**
> 本块其余内容为 STEP6（2026-09-15）冻结记录，其 FROZEN 科学语义不变；
> 但 `student_twin` 的产品化目标已由用户显式改变，故上面一行 CURRENT 计数与下面的
> MVP 分类同步更新。旧值（`RUNTIME_ONLY = 13` / `MVP SHADOW_ONLY`）不再作为 CURRENT。

## 13-component final classification

```text
MVP（USER_VISIBLE_PREVIEW）:
  student_twin        （ACCEL_SPRINT_S2：MVP_TARGET 由 SHADOW_ONLY 改为
                       USER_VISIBLE_PREVIEW；用户可见功能 = 学习状态实验视图）

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
CURRENT = USER_VISIBLE_PREVIEW
MVP_TARGET = USER_VISIBLE_PREVIEW
MVP_USER_VISIBLE_FEATURE = 学习状态实验视图
MVP_ADVISORY = NO
MVP_ACTIVE = NO

HARD_INVARIANTS（永久，不可被任何次级文件改写）
  controls_product_decision = false
  writes_learner_fact = false

用户可见语义（唯一允许的表述）
  确定性学习状态引擎（实验）

禁止表述
  AI掌握度预测 / 神经网络模型 / 掌握概率 / 考试预测

StudentTwin runtime pass != product ready
（runtime pass 仍是必要条件；产品化状态由上面的 MVP_TARGET 描述）

INPUT_DOMAIN_ELIGIBILITY（ACCEL_SPRINT_S2 产品决策，2026-09-19）
  一个事实事件可以进入 StudentTwin，当且仅当它携带
  「权威的二元正确性事实」：
    1. 事件家族允许（course_practice / question_answered）；
    2. user_answer 非空；
    3. correct 恰为 true 或 false；
    4. judge 不是 self_review。
  未作答  → NOT eligible
  self_review → NOT eligible
  correct = null → NOT eligible
  不得从 score 反推正确性。

  这是 **输入域产品化决策**，不是科学算法变更：
  StudentTwin 公式 / 状态转移规则 / runtime release id / 模型资产
  全部保持不变。

  question_answered 不得被改名为 course_practice，二者仍是两个家族。

AIQuestionAttempt / ai_question_attempts（course_practice）
  = StudentTwin-eligible canonical source（STEP6/7A 冻结，继续有效）

QuestionAttempt / question_attempts（question_answered）
  = ordinary practice flow
  = 自 ACCEL_SPRINT_S2 起 MAY be StudentTwin eligible，
    但必须逐事件满足上面的 INPUT_DOMAIN_ELIGIBILITY；
    家族级 eligible 是必要条件，不是充分条件。

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

当前 STEP = `STEP_7`；`CURRENT_SUBSTEP = STEP_7H5`；`NEXT_SUBSTEP = FRONTEND`。

**STEP7H0 / STEP7H1 / STEP7H2 / STEP7H3 / STEP7H4 / STEP7H5 均已 FROZEN；
STEP 7H **整体 FROZEN**，Exam Prep / CS408 后端验收完成。当前唯一正确动作：
进入 `NEXT_MAJOR_PHASE = FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION`
（全新前端产品实现）。**后端停止继续扩展。**
（H5 已关闭三项长期债务：Exam 运行时 schema 的 Alembic 归属
（migration `20260917_0008`，13 张表，fresh 部署可仅靠 `alembic upgrade head`）、
前端 API 交接文档 `STEP7H_FRONTEND_API_HANDOFF.md`、以及一个 H4 漏登记的隔离缺陷
（`PATCH /knowledge-map/progress` 带 exam scope 时把考试事实记成 course_learning 事件）。
**非 408 真实内容导入仍未发生，必须等用户明确批准。**）**

已完成并冻结的子步骤：

```text
STEP7A   = FROZEN   Core Backend Foundation + LearningContext + Data Plane SHADOW-ready
STEP7B   = FROZEN   Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost
STEP7C   = FROZEN   External AI Gateway + Qualified Model Pool + Router V0 + Real Cost Integration
STEP7C-P = FROZEN   Provider Onboarding / Live Validation / Model Pool Calibration
STEP7D   = FROZEN   Unified Practice Core
STEP7E   = FROZEN   Unified Wrong Answer Core
STEP7F   = FROZEN   Records / Data Plane Consolidation
STEP7G   = FROZEN   Course Learning Space Consolidation
                    （含 STEP7G-C2：Course AI → Unified AI Boundary）
STEP7H0  = FROZEN   Exam Prep 域审计 + 架构冻结（只设计不实施）
STEP7H1  = FROZEN   Exam Prep canonical namespace + context compatibility foundation
STEP7H2  = FROZEN   CS408 Practice / Wrong Answers / Records consolidation
STEP7H3  = FROZEN   Exam AI → Unified AIOrchestrator
STEP7H4  = FROZEN   Multi-track / Multi-subject Exam Preparation catalog foundation
STEP7H5  = FROZEN   Exam Prep / CS408 final backend acceptance + deployment hardening
                    （STEP 7H 整体 FROZEN；NEXT_MAJOR_PHASE = FRONTEND）
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
CURRENT_SUBSTEP = STEP_7H5
NEXT_SUBSTEP = FRONTEND

上一阶段：
STEP 1–6 已冻结。

STEP 7 进行中，已冻结的子步骤：
- STEP7A：Core Backend Foundation + LearningContext + Data Plane SHADOW-ready
- STEP7B：Unified Subscription + Capability Permission + Usage Budget/Ledger + Cost
- STEP7C：External AI Gateway + Qualified Model Pool + Router V0
- STEP7C-P：Provider Onboarding / Live Validation / Model Pool Calibration
- STEP7D：Unified Practice Core
- STEP7E：Unified Wrong Answer Core
- STEP7F：Records / Data Plane Consolidation
- STEP7G：Course Learning Space Consolidation（含 STEP7G-C2 Course AI → Unified AI Boundary）
- STEP7H0：Exam Prep 域审计 + 架构冻结（只设计不实施；产出
  `STEP7H0_UNIFIED_EXAM_PREP_ARCHITECTURE.md`）
- STEP7H1：Exam Prep canonical namespace + context compatibility foundation
  （exam_prep / CS408 adapter / 冻结 identity token / D1·D2·D4 修复 / answer.grade 注册）
- STEP7H2：CS408 Practice / Wrong Answers / Records consolidation
  （三作答事实 1:1 接 Practice Core / past_exam scope 加 subject+module / D6 builder 修复）
  + H2-C1 并发收尾（wrong projection compare-and-recompute；stress 门禁）
- STEP7H3：Exam AI → Unified AIOrchestrator
  （全部 exam 可达 AI 走 execute_exam_ai；answer.grade 落地；_grade_big_question 迁出 parser；
   exam 侧 legacy auth/billing 退出 AI 决策）
- STEP7H4：Multi-track / Multi-subject Exam Preparation catalog foundation
  （catalog = versioned CONFIG；cs_408 = ACTIVE，其余 13 个全国统考科目 = FRAMEWORK_ONLY 零内容；
   content gate 显式 EXAM_CONTENT_NOT_AVAILABLE；exam_prep_profiles = 真实用户态；
   Exam knowledge 唯一写入边界收敛；migration HEAD = 20260917_0007）
- STEP7H5：Exam Prep / CS408 final backend acceptance + deployment hardening + frontend handoff
  （Exam 运行时 schema 的 Alembic 基线 migration 20260917_0008；
   前端 API 交接文档 STEP7H_FRONTEND_API_HANDOFF.md；
   修复 H4 漏登记的 exam scope → course_learning 事件隔离缺陷；
   **STEP 7H 整体 FROZEN，后端停止扩展，进入前端阶段**）

已完成的既有冻结：
- 13 Scientific Component 产品化设计冻结
  （student_twin = MVP；**MVP_TARGET 已于 ACCEL_SPRINT_S2 由 SHADOW_ONLY 改为
   USER_VISIBLE_PREVIEW，用户可见功能 = 学习状态实验视图**）
- Git Reality 已澄清（DIVERGED；untracked==origin；LOCAL_ONLY 已识别）
- Python file disposition 已冻结
- Database migration matrix 已冻结（71 表）
- API disposition matrix 已冻结（351 HTTP endpoint）

当前正处于 STEP 7 后端实现 / 重构进行中（BACKEND_IMPLEMENTATION = IN_PROGRESS）。

下一步：
**STEP 7H 已整体 FROZEN（H0–H5），后端停止继续扩展。**
`NEXT_MAJOR_PHASE = FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION`
（全新前端产品实现；契约见 `STEP7H_FRONTEND_API_HANDOFF.md`）。
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
CURRENT_SUBSTEP = STEP_7H5
NEXT_SUBSTEP = FRONTEND

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

STEP7C-P = FROZEN（Provider Onboarding / Live Validation / Model Pool Calibration /
                  Reasoning Reservation Hardening / Collaboration-Endpoint Isolation）
STEP7C-P_NOTES = PROVIDERS_CONFIGURED=6 / AUTH_OK=6 / QUALIFIED=6；
                 审计链（逐段保留，不覆盖历史）：
                 [1] Doubao = AUTH_OK / NO_MODEL_ACCESS（Ark endpoint-id 模式，账户不可调用
                     catalog 模型名；/models 返回 132 个目录模型但 chat 报 404）
                 [2] Endpoint-ID configured → six provider connectivity：
                     doubao-general（Doubao-Seed-2.1-pro）/ doubao-agent（Doubao-Seed-Evolving）
                     两个推理接入点在 Ark 控制台创建；endpoint id 只存在于 backend/.env.local
                     （gitignored），源码零硬编码；default_provider_factory / discovery /
                     benchmark 统一读 ai.secrets.ark_endpoint_map()（无第二套 Ark 配置）；
                     live smoke 双 endpoint PASS；GENERAL_BENCHMARK doubao-general 6/6、
                     doubao-agent 6/6（参考）；AGENT_CAPABILITY_PROBE doubao-agent 3/3
                 [3] reasoning reservation risk discovered → provider-aware reservation fixed：
                     实测 max_tokens=64 仍计费 completion=566（reasoning=520）→ 旧
                     「max_tokens == 最大计费 completion」假设失效，reserve 严重低估；
                     Ark live parameter probe：THINKING_DISABLE_SUPPORTED=YES、
                     REASONING_LIMIT_SUPPORTED=NO（thinking.enabled+budget_tokens=32 仍产出
                     1308 reasoning tokens，字段被忽略）、MAX_TOKENS_COVERS_REASONING=NO；
                     修复 = ai/cost.py ModelCostPolicy（provider/model 级 reservation policy：
                     reasoning_billing（NONE/BOUNDED/UNBOUNDED/UNVERIFIED）/
                     supports_thinking_control / reasoning_reserve_tokens /
                     thinking_capabilities / thinking_default_on），
                     PROVIDER_AWARE_RESERVATION=YES；doubao-general 生产路径改用 thinking OFF：
                     在 ZHIXUE_MODEL_POOL_CALIBRATION_V1 6-case calibration 中 thinking ON/OFF
                     同为 6/6（输出 token 为 ON 时的 1/8）——
                     该结论仅限该 calibration，不外推为一般质量等价；
                     doubao-agent 保留 thinking ON + conservative reserve
                     （2048 tokens ≈ 观测最大值 1608 的 1.27x）；
                     REASONING_BUDGET_BYPASS=NO、ADVANCED_WEEKLY_BUDGET_PROTECTED=YES；
                     actual > reserve 不再静默 → error_category=reservation_overage
                 [5] NON_ARK_REASONING_BILLING_VALIDATION（本轮新增，逐模型 live 实测）：
                     固定 prompt + max_tokens=64 + provider 默认 temperature，实测结论——
                     BOUNDED（max_tokens 确实封顶总计费 completion）：
                       deepseek-v4-pro 与 deepseek-flash 与 glm-5 与 glm-5.3-flash
                       （completion=64=max_tokens、reasoning=64、content 空、finish=length）、
                       kimi-k2.6（64/64，reasoning 63）、
                       MiniMax-M3（64=64 且 512=512，thinking 以 <think> 内联在 content 内）、
                       MiniMax-M2.7-highspeed（64=64、453<=512，未上报 reasoning 字段）
                     UNBOUNDED（新发现，本轮最重要的更正）：
                       qwen3.8-flash（max_tokens=64 → completion 105/452，reasoning 83/429）、
                       qwen3.8-max（同 → 197/78，reasoning 174/52）——
                       即 max_tokens 只约束可见回答，reasoning 计在 completion_tokens 之上；
                       qwen3.8-flash 是 FREE 档主模型，故这是真实预算漏洞而非理论风险；
                       修复方式 = OPTION B（非 A）：实测「关闭 thinking」会损失质量
                       （qwen3.8-max 在 gen-json-1 question.generate 上 thinking OFF
                       0/3（mt=200）与 2/3（mt=800），thinking ON 3/3；
                       qwen3.8-flash 在 6-case run 中 thinking OFF 亦失败 gen-json-1），
                       故 Qwen 保留 thinking ON（enable_thinking=true）+ conservative reserve，
                       不基于「其余 5 个 case 通过」外推为质量无损；
                       QwenProvider 新增 enable_thinking 开关映射
                     UNVERIFIED → fail conservative：未注册模型 reservation 一律叠加
                     conservative reasoning allowance，禁止按 0 reasoning 估算；
                     regression test 固化：每个生产池模型必须已有实测 verdict
                     （禁止依赖 fail-conservative 默认值「碰巧」安全）；
                     四个 Advanced 模型逐一证明 cannot bypass weekly budget
                     （reserve >= 最大可计费 completion，且 budget gate 在 provider 调用前拒绝）
                     [4] collaboration endpoint → production isolated：zhixue-doubao-agent
                     接入点带「协作奖励计划」标记，该计划属「不使用提交内容训练基础模型」
                     规则的例外情形 → 不承载真实学生私有学习数据；
                     ai/pool.py 新增 deployment_eligibility（PRODUCTION / INTERNAL_ONLY /
                     BENCHMARK_ONLY，CONFIG 非 SQL）；doubao-agent = BENCHMARK_ONLY
                     （benchmark / internal 可用，生产 router 与 GET /ai/models 均不可见，
                     explicit model 亦不可绕过）；doubao-general = PRODUCTION，
                     Doubao Provider 仍进入 production model selection（不因隔离而移除）
                 MODEL_POOL_VERSION=v4（POOL_QUALIFICATION_LEVEL=FINAL，Doubao 仅 ADVANCED，
                 high_cost + thinking）；PRODUCTION_MODEL_POOL_VERSION=v4（生产候选 6 provider）；
                 PRICING_REGISTRY_VERSION=v4（DeepSeek/Qwen/Kimi/GLM/Doubao=OFFICIAL_DOC
                 verified，MiniMax=CONSERVATIVE_CEILING；Doubao=6.0/1.2/30.0 CNY per 1M，无峰谷）；
                 cross-provider fallback（6 provider）；BUDGET_RECALIBRATION=KEEP（provisional）；
                 CREDIT_NORMALIZATION_STATUS=KEEP_PROVISIONAL；
                 DEEPSEEK_REASONING_BILLING_SAFE=YES / MINIMAX_REASONING_BILLING_SAFE=YES /
                 GLM_REASONING_BILLING_SAFE=YES / KIMI_REASONING_BILLING_SAFE=YES（实测 BOUNDED）；
                 ARK_REASONING_BILLING_SAFE=YES（UNBOUNDED 已由 thinking OFF / reserve 覆盖）；
                 QWEN_REASONING_BILLING_SAFE=YES（UNBOUNDED 已由 thinking ON + reserve 覆盖）；
                 REASONING_UNKNOWN_FAILS_CONSERVATIVE=YES；
                 NON_ARK_THINKING_MODELS_REASONING_BILLING=VERIFIED（[5] 已逐模型实测，
                 不再有按未验证假设处理的模型）；
                 ARK_COLLAB_REWARD_PLAN_TERMS=UNVERIFIED_OFFICIAL_TEXT（官方正文不可机读；
                 按条款例外情形一律隔离，不依赖条款解读）

STEP7D = FROZEN（Unified Practice Core）
STEP7D_NOTES = 统一练习主链 PracticeSession → QuestionRef → PracticeAttempt → Result →
               (Explanation) → LearningEvent，覆盖 course_learning / exam_11408 / programming；
               MIGRATION_HEAD=20260915_0003（additive-only）；
               NEW_TABLES=practice_sessions / practice_attempts（**恰好两张**）；
               WRONG_ANSWER_STATES_CREATED=NO（wrong_answer_states / review_* / plans / tasks /
               learning_outcomes 均未创建，属后续 STEP）；
               QuestionRef = **指针非副本**：题源类型取 SSOT §19 冻结集
               （static_question_bank / past_exam / AI_generated / material_generated /
               programming_exercise / adaptive），legacy 来源显式映射且 raw_source 逐字保留；
               exam_question_bank=9333 / programming_exercises=1923 / knowledge_points=32
               未迁移、未复制、未改写；
               PracticeAttempt 视为不可变历史事实：attempt_uid 对 legacy 镜像为 UUIDv5
               （namespace, source_attempt_type, source_attempt_id, source_item_key），
               重导同 identity + 同 fact → dedupe，同 identity + 异 fact → AttemptConflict
               拒绝覆盖；correct 为**三态** True/False/NULL，未判分大题与无裁决场景一律 NULL，
               永不 bool(None)、永不猜；
               legacy adapters（course=ai_question_attempts，exam=exam_practice_attempts +
               past_paper_attempts，programming=programming_exercise_progress）以 try/except
               失败隔离接入 main.py（+48/−1，仅 router 注册 + 5 处 hook），
               legacy durable 行仍是 compatibility window 的 domain source of truth；
               programming 取**真实判题**结果（last_submit_passed + 真实用例计数），
               code_challenge_attempts 判为 INELIGIBLE（status 是 AI 散文关键词匹配，
               用作 correctness 即伪造裁决）；programming_exercise_submissions 判为 INELIGIBLE
               （与 progress 同一次提交，同时镜像会重复计数）；
               BACKFILL 已实现（5 来源，FULL/PARTIAL/INELIGIBLE 分类 + 缺失字段显式登记），
               BACKFILL_IDEMPOTENCY=PASS；REAL_BACKFILL_ROWS=0（当前无真实历史用户作答行，
               不声称真实历史迁移已验证）；
               EVENT_OWNER 冻结：course_practice 事件的唯一 owner 仍是既有 data_plane.emitter；
               Practice Core 只为自己拥有的来源发 question_answered / code_submitted，
               event_id 沿用冻结的 deterministic UUIDv5 函数；
               STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO（producer 只消费 event_type=course_practice，
               Practice Core 结构性排除；exam/programming 即使产生 PracticeAttempt 仍
               STUDENT_TWIN_ELIGIBLE=NO）；
               CROSS_USER_ISOLATION / CROSS_NAMESPACE_ISOLATION / ATTEMPT_IDEMPOTENCY /
               CONCURRENT_MIRROR_SAFETY = PASS；
               FRESH_DB + LEGACY_DB_COPY 迁移验收 PASS（integrity_check=ok，静态资产不变）；
               真实 backend/app.db 未在本轮修改（未盲跑迁移）；
               TARGETED_TESTS=68 PASS；FULL_BACKEND_TESTS=459 passed / 0 failed（baseline 391）

STEP7D_FINAL_RECONCILIATION = DONE（programming durability）
STEP7D_RECONCILIATION_NOTES = STEP7D 报告曾记载「_record_programming_submission_progress 的写入
               在一个最终未 commit 的事务中」——该结论**是错的**（源于一段被截断的代码摘录）。
               逐行追踪真实 transaction ownership 后确认：
               _record_programming_exercise_activity 末尾 db.commit()（main.py:10930 附近）
               与 _record_programming_submission_progress 末尾 db.commit()（main.py:10956）
               各自持久化；get_db 的 close 不丢任何已提交写入。
               故不存在 durability gap，**未**机械地在 helper 内补 commit，
               亦未创建重复的 programming submission 表。
               PROGRAMMING_DURABLE_SOURCE=programming_exercise_progress（含 user_id/exercise_id/
               language(取自静态 exercise)/submitted_at/last_submit_passed/真实用例计数）；
               PROGRAMMING_CANONICAL_MIRROR=practice_attempts；一次真实提交 → 一条 canonical
               attempt（PROGRAMMING_DOUBLE_COUNT=NO）；
               PROGRAMMING_MIRROR_FAILURE_RECOVERABLE=YES（judge → durable commit → mirror 失败
               → backfill 重建，字段/身份逐项一致，重跑插入 0）；
               已知 PARTIAL：该表为 per-(user,exercise) 聚合，仅最后一次提交可重建；
               code_challenge_attempts 的 status 仍是 AI 散文关键词匹配，
               恒为 INELIGIBLE AS CORRECTNESS SOURCE

STEP7E = FROZEN（Unified Wrong Answer Core）
STEP7E_NOTES = PracticeAttempt → WrongAnswerState（用户 × canonical question 的**动态错误状态**，
               不是 Question.is_wrong、不是 attempt 历史的副本、不是科学预测）；
               MIGRATION_HEAD=20260915_0004；NEW_TABLES=wrong_answer_states（**EXACTLY ONE**）；
               REVIEW_TABLES_CREATED=NO（review_items / review_attempts / review_schedules /
               wrong_answer_attempt_history / wrong_answer_events 均未创建；
               历史一律从 practice_attempts 查询）；
               identity=(user_id, service_namespace, question_source_type, question_source_id,
               question_scope_key)；attempt identity ≠ question identity；
               question_scope_key 仅对 past_exam 生效（year:<year>），因为真题 question_id
               来自解析卷、不保证全局唯一，误合并比分开更糟；
               WrongAnswerState **不保存题目快照**：Question（question_ref_json）/
               UserAnswer（answer）/ CorrectAnswer（result_json.standard_answer）/
               Context（context_json）/ ErrorAnalysis（result_json.feedback|analysis，无则 null）
               全部从 canonical facts + domain source 读取；
               状态机：首次错 → ACTIVE；再错 → ACTIVE 且 wrong_count+1；此后对 → RESOLVED；
               RESOLVED 后再错 → 回到 ACTIVE（重开）；correct=NULL → 不做任何转换；
               三态严格保留（永不 bool(None)），score-only attempt 不进错题；
               **RECOMPUTE 而非增量累加**：状态始终由该 (user,namespace,question) 的全部
               canonical attempts 按 (submitted_at, id) 重算 → 幂等 / 顺序无关 / 可重建三位一体；
               WRONG_COUNT = 不同错答 attempt 计数（非投影调用次数、非 legacy review_count）；
               legacy MERGE：exam_wrong_questions + past_paper_wrong_questions → wrong_answer_states
               （不 DROP legacy 表，legacy endpoint 行为不变）；
               CONFLICT POLICY：有 canonical facts 的题由 facts 决定 status，
               legacy mastered/review_count/reviewed_at 仅作 legacy_* 兼容元数据，**不得覆盖**
               更新的真实 attempt correctness；无 facts 时才由 legacy 决定；
               无法排序/无用户归属的行 → 跳过并计数，不猜测；
               CANONICAL_REBUILD 支持 dry-run，upsert/reconcile，无破坏性操作；
               API = GET /wrong-answers、GET /wrong-answers/{id}、PATCH /wrong-answers/{id}
               （仅 3 个；SSOT 未冻结本模块 exact path）；
               TRISTATE_CORRECTNESS_PRESERVED / WRONG_COUNT_IDEMPOTENCY / RESOLUTION_REOPEN /
               OUT_OF_ORDER_REPLAY / CROSS_USER_ISOLATION / CROSS_NAMESPACE_ISOLATION /
               SOURCE_COLLISION_SAFETY / CONCURRENCY_SAFETY / LEGACY_BACKFILL /
               CANONICAL_REBUILD / BACKFILL_IDEMPOTENCY = 全部 PASS；
               STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO（WrongAnswer 投影不写任何 LearningEvent）；
               REVIEW_CORE_IMPLEMENTED=NO；SCIENTIFIC_WRONG_DIAGNOSIS_IMPLEMENTED=NO
               （未接 misconception_v2 / learner_state / IRT / evidence_reliability）；
               FRESH_DB + LEGACY_DB_COPY 迁移验收 PASS；REAL_APP_DB_MIGRATED=NO；
               STATIC_ASSET_COUNTS=9333/1923/32；
               TARGETED_TESTS=57 PASS；FULL_BACKEND_TESTS=516 passed / 0 failed（baseline 459）

STEP7F = FROZEN（Records / Data Plane Consolidation）
STEP7F_NOTES = 把零散的 record/event 来源收敛为统一、可信、可版本化的
               learning_events + Records read model + Data Producer boundary；
               不是重新实现 STEP7A Data Plane，而是 CONSOLIDATE / PRODUCTIZE /
               MIGRATE PRODUCERS / BACKFILL LEGACY / FREEZE TAXONOMY；
               STEP7F_SCHEMA_CHANGE=INDEX_ONLY；MIGRATION_HEAD=20260915_0005；
               NEW_TABLES=NONE（**未新增任何记录表**：Learning Records 是 learning_events
               的投影，不是第二张表；learning_records_v2 / event_outbox / derived_features /
               student_state / timeline / activity_log 均未创建）；
               0005 只加两个 index（user_id+occurred_at、service_key+occurred_at），
               无新列、无约束变更、无数据改动；
               LEARNING_EVENT_ENVELOPE=COMPLETE（frozen target 九要素全部由既有列表达：
               service_namespace→service_key、payload→item_snapshot_json、
               source→source_type/source_attempt_id/source_item_key/source_item_index、
               schema_version→event_schema_version），故未改 envelope；
               EVENT_SCHEMA_VERSION=2（**未 bump**）；
               EVENT_TAXONOMY=FROZEN：ACTIVE=course_practice / question_answered /
               code_submitted / ai_called / knowledge_status_changed / material_asked /
               material_opened；DEFERRED（只有名字、无 source、不可发射，测试固化）=
               review_completed / plan_created / task_completed / wrong_answer_resolved；
               原则 NO SOURCE → NO EVENT；
               EVENT_OWNERSHIP_MATRIX=FROZEN（一个事实一个 authoritative producer；
               PracticeAttempt / WrongAnswerState / legacy learning_records 不会对同一次
               答题写三次事件：WrongAnswerState 写 0 条，legacy learning_records(practice)
               判 INELIGIBLE）；
               EVENT IDENTITY 复用冻结的 data_plane.identity（UUIDv5），未造第二套 namespace，
               不依赖 occurred_at、不用随机 UUID；
               COURSE_PRACTICE_IDENTITY_CHANGED=NO / COURSE_PRACTICE_DUPLICATE_EVENT=NO
               （course_practice 的名字与 event_id 未改，也未额外产生等价 question_answered；
               其 Records 分类由 read-model category 表达，不复制事实）；
               新增 4 个 producer：ai_called（orchestrator.execute 单一公共边界，覆盖六条
               return 路径；失败请求统一记录为 coarse status + 规范化 error_category，
               ops 细节不入 payload）、knowledge_status_changed（apply_knowledge_progress_event
               返回迁移信息，调用方 commit 后再发射；3 个 callsite 已接，另 2 条直接构造事件行的
               路径由 backfill 覆盖并如实标注）、material_asked（POST /chat，只带引用）、
               material_opened（GET /materials/{id}，身份按 (user, material, UTC 日) 去重）；
               修复 STEP7D 遗留真实缺陷：practice event 原先只在 HTTP router 发射，
               非 HTTP 写入路径（legacy adapters / backfill）不会产生事件 →
               已移入 practice service 的唯一写入路径；
               LEGACY BACKFILL：learning_records（practice=INELIGIBLE、
               review+素材=PARTIAL 映射为 material_asked 且与 live 同 identity、
               其他=INELIGIBLE）、knowledge_progress_events（PARTIAL，按产品自身
               clamp+阈值规则做 chronological delta replay，payload 标
               derived_from=delta_replay_v1）、ai_requests（PARTIAL，与 live 同 identity）；
               BACKFILL_IDEMPOTENCY=PASS / LIVE_BACKFILL_EQUIVALENCE=PASS / dry-run 不落库；
               LEARNING_RECORDS_READ_MODEL=PASS（list/get/summary，全部 user-scoped，
               cursor 分页 occurred_at DESC + event_id tie-break，UTC 语义统一）；
               LEARNING_RECORDS_API=PASS（仅 4 个 GET：/learning-records、
               /summary、/taxonomy、/{event_id}）；ARBITRARY_CLIENT_EVENT_WRITE=NO
               （无任何写入面，测试固化）；
               PRIVACY_PAYLOAD_POLICY=PASS（envelope 拒绝 code/prompt/response/full_answer/
               api_key 等键；read model 不输出 item_snapshot_json 等内部字段）；
               FREE_TIER_EVENT_PERSISTENCE=PASS（三 tier 同一事实均落事件；
               付费差异只在分析/连续 StudentTwin/高级报告/自动化，不在是否保存）；
               STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO（worker 目标选择与历史查询均过滤
               event_type=course_practice，非 eligible 事件结构性被忽略，实测
               events_scanned=0）；STUDENT_TWIN_PRODUCTIZATION_STATE=SHADOW_READY（未升级）；
               RECOVERY_CAPABILITY_MATRIX=course_practice/question_answered/code_submitted/
               ai_called=FULL，knowledge_status_changed/material_asked=PARTIAL，
               material_opened=EVENT_ONLY（明确不具备 source backfill，不虚假声称可恢复）；
               NEW_SCIENTIFIC_COMPONENTS=NONE / LEARNING_OUTCOMES_CREATED=NO
               （仍为 V1；未接 misconception_v2 / learner_state / IRT / evidence_reliability /
               memory / planner）；
               FRESH_DB + LEGACY_DB_COPY 迁移验收 PASS；REAL_APP_DB_MIGRATED=NO；
               STATIC_ASSET_COUNTS=9333/1923/32；
               TARGETED_TESTS=65 PASS；FULL_BACKEND_TESTS=581 passed / 0 failed（baseline 516）

STEP7G = FROZEN（Course Learning Space Consolidation + STEP7G-C2 Course AI → Unified AI Boundary）
STEP7G_STATUS = STEP7G_COMPLETE=YES / STEP7H_READY=YES
STEP7G_C2_DONE = **STEP7G-C2** 把全部 Course production AI 接到统一执行边界：
              Endpoint → authenticated user → canonical LearningContext → AIOrchestrator →
              Capability Permission → Router → Estimate → Reserve → Gateway → Actual Usage →
              Settle → domain postprocess；
              MIGRATION_HEAD=20260915_0006；NEW_TABLES=NONE（0006 additive-only：
              只加 ai_requests.service_namespace / ai_requests.context_json /
              usage_ledger.service_namespace 三列 + 两个 namespace index；nullable，
              历史行保持原形；downgrade 显式 NotImplementedError，不假装可回退）；
              REAL_APP_DB_MIGRATED=NO；
              FRESH_DB + LEGACY_DB_COPY 迁移验收 PASS；STATIC_ASSET_COUNTS=9333/1923/32；
              COURSE_AI_ENDPOINT_COUNT=19；Orchestrator boundary 调用点=21
              （19 primary + 2 secondary：/ai-explain 与 /questions/generate 的**条件精修**
              refine_question_analysis_with_ai，以及计划 JSON 修复重试 _repair_json_with_ai，
              二者同样经 _course_ai_content，触发条件不变）；
              COURSE_PRIMARY/SECONDARY/TOTAL_DIRECT_PROVIDER_CALLSITE_COUNT = 0 / 0 / 0；
              COURSE_DIRECT_PROVIDER_ENDPOINTS_FINAL=0 / COURSE_DIRECT_PROVIDER_CALLS_FINAL=0；
              AI_REQUEST_CONTEXT_PERSISTENCE / AI_EVENT_CONTEXT_EQUIVALENCE /
              USAGE_LEDGER_NAMESPACE_EQUIVALENCE = PASS（AIRequest.service_namespace ==
              AIRequest.context_json.service_namespace == usage_ledger.service_namespace ==
              ai_called.service_key，四者同一 canonical source，无端点自拼 context）；
              CAPABILITY **knowledge.structure** = 已批准并注册：Free=DENIED /
              Standard=ALLOWED / Advanced=ALLOWED，qualified pool **继承 question.generate**
              （CAPABILITY_QUALIFICATION_PROXIES 单点别名解析），qualification label =
              STRUCTURED_GENERATION_PROXY_V1 —— 这是**产品 capability**，
              **未新开 provider benchmark、未改 Pool v4（POOL_VERSION 仍为 v4）**；
              四条 knowledge structure 路由（/knowledge-points/generate-preview、
              /knowledge-path/generate-from-materials、
              /materials/{id}/knowledge-links/recommend、
              /materials/analyze-knowledge-preview）保留原 JSON contract / schema validation /
              preview semantics / domain validation，preview **不写** mastery / StudentTwin；
              /chat capability 由**服务端**判定（material-bound → material.qa，
              普通学习对话 → tutor.chat；exam / programming 分支维持 legacy），
              ChatRequest **无** capability 字段，客户端无法提交任意 capability 绕过权限；
              AUTHORIZATION CUTOVER：COURSE_AI_LEGACY_AUTH_OWNER=0 —— 从 course AI 执行路径
              移除 7 处 legacy 授权（check_usage_limit ×5 + require_learning_context_feature ×2）；
              exam_11408 / programming 分支的 legacy 授权**刻意保留**（属 STEP7H/7I）；
              course 路径不再写 legacy record_ai_usage 行；
              AI_BILLING_DOUBLE_COUNT=NO / COURSE_AI_EVENT_DUPLICATION=NO /
              KNOWLEDGE_DOUBLE_UPDATE=NO；
              权限拒绝**不得被降级吞掉**：3 个原先把 403/429 吞成确定性 fallback 的端点
              改为 except HTTPException: raise 先行（「无模型仍可用」只适用于技术失败，
              不适用于授权决定）；
              MATERIAL_QA_ORCHESTRATED=PASS / COURSE_AI_CAPABILITY_MIGRATION=PASS；
              FULL_BACKEND_TESTS=662 passed / 0 failed（第二轮 baseline 621）；
STEP7G_DONE = STEP7G_SCHEMA_CHANGE=NONE（course space 本体）/ C2 新增 0006 见上；NEW_TABLES=NONE；
              新模块 backend/learning/spaces/course_learning/{context,knowledge,service,ai}.py；
              COURSE CANONICAL NAMESPACE=course_learning，legacy alias "course" 仅作 INPUT，
              在 core.learning_context.normalize_service_namespace **统一归一化一次**
              （practice/wrong_answers/records 三处私有 _namespace_value 已删除，
              禁止各 module 自建 alias 逻辑）；
              COURSE IDENTITY = 存储的 course_id 字符串（**不新建 Course/CourseChapter 表**，
              如实保留现状）；chapter = context 中的 chapter key；identity 绝不按 display name 比较；
              LearningContext 复用 core，无第二套 CourseContext；
              COURSE CANONICAL KNOWLEDGE WRITER =
              learning.spaces.course_learning.knowledge.apply_knowledge_change；
              course 的 7 条 knowledge mutation 路径**全部**经该 writer（durable write +
              同一条 clamp/阈值 80-40-1 推导规则 + 真实迁移时发 knowledge_status_changed）；
              保留既有语义（+15/-8 pedagogy delta、system_suggested_status、
              「练习建议绝不覆盖学习者已确认状态」protect_user_confirmed）；
              apply_knowledge_progress_event 降级为遗留兼容入口（保留其 legacy 事件行）；
              non-course mutation 路径如实标注 OUT_OF_SCOPE_SPACE(exam→STEP7H /
              programming→STEP7I) 或 SYSTEM_DERIVED_NO_EVENT(review 排期重算)；
              FUTURE_LIVE_KNOWLEDGE_EVENT_COVERAGE=COMPLETE(course)；
              HISTORICAL_KNOWLEDGE_EVENT_COVERAGE=PARTIAL(STEP7F 维持)；
              COURSE_WRONG_SHARED_CORE / COURSE_RECORDS_SHARED_CORE = PASS；
              MULTI_COURSE / CROSS_USER / CROSS_NAMESPACE ISOLATION = PASS；
              COURSE_BACKEND_E2E / FREE_USER_COURSE_LOOP = PASS；
              AIQUESTIONATTEMPT_EVENT_ID_CHANGED=NO / DUPLICATE_EVENT=NO /
              STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO / STUDENT_TWIN_PRODUCTIZATION_STATE=SHADOW_READY；
              LEGACY_COURSE_ENDPOINTS_DELETED=NO / LEGACY_COURSE_PLAN_PRESERVED=YES /
              UNIFIED_PLANNING_IMPLEMENTED=NO / REVIEW_CORE_IMPLEMENTED=NO /
              NEW_SCIENTIFIC_COMPONENTS=NONE / FRONTEND_CHANGED=NO；
              REAL_APP_DB_MIGRATED=NO；FRESH_DB + LEGACY_DB_COPY 验收 PASS；
              STATIC_ASSET_COUNTS=9333/1923/32；
              TARGETED_TESTS=26 PASS；FULL_BACKEND_TESTS=607 passed / 0 failed（baseline 581）
STEP7G_C2_NOTES = 本轮（C2 recovery + closure）修复的真实缺陷：
              ① /knowledge-points/generate-preview 在 mode=materials 时读取**未定义**的
                 material_ids → NameError（mode=course_name 因条件表达式短路而不炸，
                 只测 happy path 不会发现）；已改为真实收集 material_ids 并加材料上下文测试；
              ② /practice/questions/{id}/ai-explain 有一段**重复的 prompt 块**（死代码）；
              ③ /practice/questions/{id}/feedback 原先**先调 AI 再写 durable attempt** ——
                 AI 失败则学习者作答事实丢失、重试会重复造 attempt；已改为
                 FACT 先落库 → 再调 AI → 成功回填 ai_feedback / 失败返回
                 ai_feedback_available=false（响应新增该字段），mirror 与 knowledge
                 transition 照常（测试：test_feedback_commits_the_answer_before_the_ai_runs）；
              ④ **is_exam_408_context 原先按 display name 判定** ——
                 COURSE_LEARNING_ID_MAP 里「数据结构 / 操作系统 / 计算机组成原理 / 计算机网络」
                 同时是 course_learning 的 displayName 与 exam 的 subject 关键词，于是
                 course 请求被判成 exam 并走进 call_deepseek（这是 calls 迟迟不清零的根因，
                 违反 SSOT §28「identity 用 key，title 只是展示」）；已改为按 direction 标记
                 "11408" 判定（"11408 操作系统" / "operating_system_11408"），
                 /chat 另接受显式 service_key=exam_11408 / exam_subject；
                 explicit exam 判定不变，隐式 display-name 歧义默认归 course_learning；
              ⑤ **knowledge mutation inventory 不完整**：POST /knowledge-path/generate-from-materials
                 会删旧树并重建、为其写零状态 user_knowledge_progress 行，却不在 inventory 中；
                 已补为 CONTENT_REPLACEMENT_NO_EVENT（内容替换 ≠ 学习迁移：没有存活知识点
                 发生状态变化，故不调 writer、不发 knowledge_status_changed），
                 course_paths_not_consolidated() 引入 _DECLARED_STATUSES ——
                 **未声明**旁路仍算 gate fail，**已声明**必须带 note；
              ⑥ migration 测试 EXPECTED_HEAD 陈旧（2 项遗留失败）→ 更新为 20260915_0006，
                 并新增 0006 列/索引隔离验收；
              NEW_TESTS = tests/test_course_ai_migration.py（26，**不 mock orchestrator**，
              只换出站 provider 为 FakeProvider：tier matrix、budget 拒绝且 provider 调用=0、
              四者 context 等价、跨空间/跨用户拒绝、完整 Course AI E2E、/chat 服务端判定）
              + tests/test_course_ai_reachability.py（6，把「0 直连」变成可执行不变量：
              直连调用点必须落在显式声明的非 course 函数内且被分支守卫证明属于他空间；
              原始 provider client 只允许出现在 adapters 与已登记 infra）；
              RECOVERED_FROM_INTERRUPTION = YES（上一轮 Codex 中途停止，本轮先做只读恢复审计，
              再补齐授权切换 / exam 判定 / 缺陷修复 / 测试 / 报告 / SSOT）
STEP7G_HISTORY_PARTIAL = （历史，已被本轮取代，保留不擦除）第一轮：course space 本体完成，
              但 COURSE_DIRECT_PROVIDER_CALLS=13、COURSE_PRACTICE_SHARED_CORE=PARTIAL →
              当时 STEP7G_COMPLETE=NO / STEP7H_READY=NO
STEP7G_HISTORY_BLOCKERS = （历史）① 13 条 course 可达端点直接调 provider → §14 gate fail；
              ② 3 条 course practice writer 未产生 canonical PracticeAttempt → §16 gate fail

STEP7G_ROUND2 = （历史，保留）PART A（Practice writer gap）已 CLOSED；PART B 当时未执行（STOP 于 CAPABILITY_GAP）
STEP7G_ROUND2_NOTES = A1 语义追踪结论：三条 endpoint 不是同一次作答的三个阶段，而是三个
              各自独立的 durable 事实 —— attempts 与 feedback 各写自己的 question_attempts
              行（feedback 的 self_result="unknown"，无事实判断 → canonical correct=NULL，
              绝不 False）；submit-result 的 durable 事实是 learning_records 里的一条
              **批次汇总**行，逐题 is_correct 为**客户端断言且从不持久化**；
              因此 attempts/feedback 按 legacy row id **1:1** mirror，submit-result 只
              产生 canonical **PracticeSession**（不为逐题造 attempt：客户端断言不可提升为
              immutable 事实，且无 durable source 可恢复，两条理由任一即足够）；
              A9 全部 PASS：COURSE_PRACTICE_WRITER_MIGRATED=3/3、COURSE_PRACTICE_SHARED_CORE=PASS、
              LOGICAL_ATTEMPT_DOUBLE_COUNT=NO、KNOWLEDGE_DOUBLE_UPDATE=NO（实测 mastery_score=8
              而非 16）、PRACTICE_EVENT_DUPLICATION=NO、WRONG_COUNT_DUPLICATION=NO、
              MIRROR_FAILURE_RECOVERABLE=PASS；为使 live 与 backfill 一致，STEP7D backfill 的
              session 容器对齐为 course:<course_id>；
              PART B **未迁移任何端点**：B3 审计发现 4 处 CAPABILITY_GAP ——
              POST /knowledge-points/generate-preview、POST /materials/analyze-knowledge-preview、
              POST /materials/{id}/knowledge-links/recommend、summarize_material（upload 路径）
              属「资料/知识点结构化抽取」，与现有 8 个 capability 均不同构；按 §B3 既不得塞进
              错误 capability，也不得擅自新增 → STOP 并报告，等待用户决策（接受近似既有
              capability，或批准最小新 capability 并同时给出 tier 映射与 Qualified Model Pool
              继承规则）；且**分批判迁移会造成同一学习空间内两套授权语义并存**，故整体留待
              一次完整切换；
              本轮另修 3 个真实缺陷：mirror_practice_batch 闭包变量 UnboundLocalError 被
              safe_mirror 吸收成静默失败；live/backfill session 容器不一致；测试陈旧
              identity map 导致误判；
              TARGETED_TESTS=14 PASS；FULL_BACKEND_TESTS=621 passed / 0 failed（baseline 607）
STEP7G_CAPABILITY_GAP_RESOLUTION = 上一轮 STOP 等待的决策已由用户批准并落地：
              新增产品 capability **knowledge.structure**（不是新 benchmark），
              tier 映射 Free=DENIED / Standard=ALLOWED / Advanced=ALLOWED，
              Qualified Model Pool **继承 question.generate**
              （CAPABILITY_QUALIFICATION_PROXIES，单点解析），
              qualification label = STRUCTURED_GENERATION_PROXY_V1；
              至此前一轮「4 处 CAPABILITY_GAP」以**一个** capability 收口，
              未新开 provider benchmark，未改 Pool v4
STEP7G_FIXES_DISCOVERED = （历史，保留）第一轮审计+测试发现并修复的真实缺陷：
              ① 错题身份未含 course → 同一 user 两个 course 的同名 question 互相串线
                 （scope_key 加 course:<course_id>，course adapter 写 course_id 进 ref context）；
              ② STEP7D practice emitter 把 course_id 硬编码 None → course 记录无法按课程过滤；
              ③ course_learning 之前完全不产生 practice 事件 → 现按来源区分覆盖
                 （ai_question_attempt 谱系仍归既有 course_practice emitter，
                 其余 course practice 来源由 practice spine 覆盖）；
              ④ practice session/attempt 确定性身份未含 user_id → 跨用户 unique 冲突风险；
              ⑤ SessionLocal autoflush=False 导致 canonical writer 看不到调用方未 flush 的行，
                 会创建**重复** progress 行 → writer 入口 db.flush()

STEP7H0 = FROZEN（Unified Exam Prep 域审计 + 架构冻结 —— **只设计，不实施**）
STEP7H0_NOTES = 产出文档 STEP7H0_UNIFIED_EXAM_PREP_ARCHITECTURE.md（22 节 + 20 条 FD）；
              本轮**零代码变更、零 schema 变更、零 migration、零前端、零 live provider**；
              真实 backend/app.db 未被审计代码触碰（复制到 temp 后只读 sqlite3 查询，
              REAL_APP_DB_MIGRATED=NO，72 表 / integrity ok / exam_question_bank 9333）；
              CURRENT EXAM 事实（只读实测）：
                exam 路由=52（/exam/11408/* 47 + /exam-408/* 4 + /me/tracks/exam_408/package 1）；
                exam 表=14（另共享 practice_sessions/attempts、wrong_answer_states、
                user_knowledge_progress、learning_events）；
                行数：exam_question_bank=9333（chapter 9098 / past_paper 235），
                其余 exam 用户态表**全部为 0**；
                静态资产：exam_resources 263 文件 + static/exam_papers 564 文件 +
                seed_data/knowledge_maps/*_11408.json ×4；
                knowledge_points=32 实测属 programming-C ontology（programming_c/cpp/java/python
                各 8），**不得**当作 Exam 知识点；
              **EXAM_NAMESPACE_IMPACT_MATRIX 核心结论**：exam_11408 是**重载 token**，
              同时承担 5 种语义 —— A=LEARNING SPACE（要改名）/ B=MEMBERSHIP SERVICE KEY /
              C=QUOTA BUCKET KEY / D=MATERIAL DOMAIN+TRACK+ADMIN / E=QUOTA-AUTH ENTRY；
              **B/C/E 属旧会员+旧额度维度，本就要退役，不是被改名** ——
              需要改名的只有 A（+D 的真 track 部分），规模由 306 处降到约 40–50 处且全是代码常量；
              NAMESPACE_MIGRATION_OPTION = **OPTION B**（canonical → exam_prep，
              exam/exam_408/exam_11408/11408 降为 INPUT alias 归一化一次）；
              推荐依据（代码事实）：LearningEvent.event_id = uuid5(source_type,
              source_attempt_id, item_key) **不含 namespace**（data_plane/identity.py:29-31）
              → 改名不改事件身份；唯一敏感的是 practice/wrong identity
              （session_uid/attempt_uid 含 service_namespace，wrong 的 UniqueConstraint 亦含），
              解法 = **冻结 identity token**（canonical 存 exam_prep，uuid5 输入保持 exam_11408），
              前置条件 = H1 必须**测量**目标库 exam canonical 行数（本地实测=0）；
              NEW_TABLES_PROPOSED_FOR_H1=NONE / SCHEMA_CHANGE_REQUIRED_FOR_H1=NONE；
              EXAM_TRACK/SUBJECT/MODULE/CHAPTER/KNOWLEDGE_POINT **全部不新建 SQL 表**
              （前三级=versioned CONFIG，后两级=已有静态资源）；不建 SubjectCatalog/
              KnowledgeCatalog（SHARED_KNOWLEDGE_STRATEGY=OPTION B，config 表达共享 module key）；
              KNOWLEDGE CONTENT MAY BE SHARED / LEARNING STATE MUST NOT BE SHARED AUTOMATICALLY
              （Course 掌握 ≠ Exam 掌握；本轮不做 StudentTwin 跨空间推断）；
              CS408_MAPPING = track cs_408 + subject cs_408 + module=subject_key（adapter 解释）；
              QUESTION_BANK_9333_DISPOSITION = **NO PHYSICAL MIGRATION**（零改动）；
              LEARNING_CONTEXT_TARGET = 继续唯一一个 core.LearningContext，新增
              exam_track_id/exam_subject_id/exam_module_id；exam_track_id **不进** events、
              **不进**任何 identity（track 是用户侧备考组合选择，非事实属性）；
              PRACTICE/WRONG/RECORDS TARGET = 继续复用 Unified Practice Core /
              Wrong Answer Core / learning_events，仅 namespace 与 context 对齐；
              EXAM_DIRECT_PROVIDER_CALLS=9（另 1 条 OCR 属 PARSER_OCR 保留）；
              EXAM_AI_MIGRATION_TARGET=AIOrchestrator；CAPABILITY_GAPS=1
              （G1 answer grading，无同构 capability，H3 前需用户决策，本轮不新增）；
              STANDARDIZED_EXAM_SCOPE=全国统一命题/全国统考型研究生招生考试科目；
              INSTITUTION_SPECIFIC_EXAMS=OUT_OF_SCOPE（禁建 institution_id/school_id/
              school_exam_code/institution_exam_plan/school_specific_subject 等模型）；
              STEP7H_DECOMPOSITION = H0 域/身份冻结 → H1 namespace+context 兼容基础
              → H2 11408/CS408 接 Practice/Wrong/Records → H3 Exam AI 接 Orchestrator
              → H4 多 track/多 subject catalog 基础 → H5 CS408 全量验收；
              **本轮发现并登记 8 项真实缺陷（供 H1/H2/H3 消化）**：
              D1🔴 4 端点跨空间污染（exam 请求经 _course_ai_content 把
              ai_requests/ai_called 写成 course_learning）→ H1 必修；
              D2🟠 question-analysis 已 orchestrated 但未传 LearningContext →
              service_namespace=NULL；D3🟠 _grade_big_question 无授权/无计费/结果在题库
              命中时被丢弃（付费调用被浪费），判定为 (A) 用户作答评分、H3 从 parser 迁出；
              D4🟡 GET /exam/11408/study-plan/tasks/summary 重复注册（死 handler）；
              D5🟡 exam_favorite_questions_v2 死表（0 行/0 代码引用）；
              D6🟠 真题 builder 整表 DELETE+INSERT → question id 漂移；
              D7🟠 14 张 exam 表**无 Alembic 覆盖**（只靠 create_all）；
              D8🟡 OCR 全路径不计费/不记录（属 Parser Infra 成本核算）；
              FRONTEND_CHANGED=NO

STEP7H1 = FROZEN（Exam Prep canonical namespace + context compatibility foundation）
STEP7H1_NOTES = 实施报告 STEP7H1_EXAM_PREP_NAMESPACE_CONTEXT_ACCEPTANCE_REPORT.md；
              CANONICAL_EXAM_NAMESPACE=**exam_prep**（ServiceNamespace.EXAM_11408 已从枚举移除）；
              legacy alias exam / exam_408 / exam408 / exam-408 / exam_11408 / exam-11408 /
              11408 / exam-prep → exam_prep（边界归一化一次，绝不落库）；
              is_valid_service_namespace("exam_prep")=True / ("exam_11408")=False；
              **仍不改名**：exam_11408 作为 legacy 会员 service_key / 额度桶 key / 资料域标签 /
              admin·support 分类的用法（main.py 余 58 处逐条核对均在上述维度）；
              IDENTITY_NAMESPACE_TOKEN **永久冻结**（非条件式）：
              IDENTITY_TOKEN_BY_NAMESPACE={course_learning: course_learning,
              exam_prep: exam_11408, programming: programming} ——
              practice session_uid/attempt_uid 先归一化再取 token 再入 uuid5，
              故 exam_11408 与 exam_prep 输入产生**同一**身份，
              IDENTITY_ENVIRONMENT_DEPENDENT=NO（不依赖目标库是否有旧行）；
              LEARNING_CONTEXT_SINGLE_MODEL=PASS：继续只有 core.LearningContext，
              新增 Optional exam_track_id / exam_subject_id / exam_module_id；
              LEGACY_SUBJECT_KEY_MIRROR=exam_module_id（context.subject_key 保持 module，
              兼容 FROZEN 的 STEP7D exam adapter）；EVENT_SUBJECT_KEY=exam_subject_id
              （learning_events.subject_key = cs_408）；exam_module_id 进事件 context JSON
              （knowledge_point_ref_json，经共享 domain_context_json；不参与任何 identity）；
              **exam_track_id 不进 learning_events、不进任何 identity**；
              新模块 backend/learning/spaces/exam_prep/{catalog,scope,context,ai}.py；
              CS408_MAPPING=PASS（track cs_408 + subject cs_408 + module=既有 subject_key）；
              scope.py 为纯函数适配器（parse/build/resolve，非法 scope **fail closed**），
              **不 rewrite** user_knowledge_progress.course_id / study_materials.course_id /
              seed JSON / static 路径；
              QUESTION_BANK_PHYSICAL_MIGRATION=NO；QUESTION_BANK_COUNT=9333
              （chapter 9098 / past_paper 235；CONTENT_FINGERPRINT_SHA256=
              7b0717634939974752b95200f96de959615cbffde2ce2f27e7a4c542ea82d7a4）；
              EXAM_CANONICAL_ROW_PREFLIGHT：6/6 统一表 NOT_PRESENT（alias rows=0）
              → DATA_MIGRATION_REQUIRED=NO；NEW_TABLES=NONE；SCHEMA_CHANGE=NONE；
              **D1_CROSS_SPACE_POLLUTION=FIXED**（4 条 course-capable 端点在 exam 请求下
              经 _course_ai_content 把 ai_requests/ai_called 写成 course_learning）——
              修法 = 新增 space dispatcher `_scoped_ai_content`（空间由服务端按同一谓词决定）
              + `_course_ai_content` 兜底守卫（course context 永不由 exam scope 构造）；
              **D2_QUESTION_ANALYSIS_CONTEXT=FIXED**（question-analysis 原本已 orchestrated 但
              learning_context=None → namespace NULL；现经 execute_exam_ai 传入 CS408 context，
              错误语义对齐 course：403/429/502）；
              **D4_DUPLICATE_ROUTE=FIXED**（GET /exam/11408/study-plan/tasks/summary 重复注册，
              删除 shadowed 的死 handler；并附带清掉同类隐藏重复
              GET /learning-records 的 shadowed legacy handler = D4b）→
              全 app duplicate (method,path) = 空集；TOTAL_ROUTES=380；
              ANSWER_GRADE_CAPABILITY=REGISTERED（tier: Free DENIED / Standard ALLOWED /
              Advanced ALLOWED；pool proxy QUESTION_EXPLAIN_PROXY_V1；
              POOL_VERSION 仍 v4，未新开 provider benchmark）；
              **未迁移** _grade_big_question（H3），grading flow 未动（测试固化）；
              EVENT_IDENTITY_ALGORITHM_CHANGED=NO（event_id 不含 namespace）；
              本轮另修一处真实缺口：practice 事件桥直接读存储 context 取 subject_key
              → 收敛为唯一函数 core.learning_context.resolve_event_subject_key()，
              LearningContext.event_subject_key() 与两个 producer 全部委托它；
              PAST_EXAM_CROSS_SUBJECT_IDENTITY_RISK=ASSESSED → **DEFERRED_TO_H2**
              （H2 必须实测 past_exam 的 source_id 在不同 subject/module 下是否全局唯一，
              不唯一则先设计 subject/module-aware scope）；
              EXAM_PROFILE_STORAGE_COMPATIBILITY=NEEDS_H4_DESIGN（H1 不新建表、不重做 onboarding）；
              REAL_APP_DB_MUTATED=NO（真实 app.db 只读 sqlite3：72 表 / integrity ok /
              9333 / 1923 / 32 / 无 alembic_version）；
              TARGETED_TESTS=50 PASS（tests/test_exam_prep_namespace.py）；
              FULL_BACKEND_TESTS=712 passed / 0 failed（STEP7H0 baseline 662）

STEP7H2 = FROZEN（CS408 / exam_prep Practice + Wrong Answers + Records consolidation）
STEP7H2_NOTES = 实施报告 STEP7H2_EXAM_PRACTICE_WRONG_RECORDS_ACCEPTANCE_REPORT.md；
              **三作答事实全部接入 Unified Practice Core**（CHAPTER / PAST_PAPER /
              AI_GENERATED_ATTEMPT_PATH = PASS）：chapter practice（exam_practice_attempts）、
              真题（past_paper_attempts）、AI 出题作答（ai_question_attempts，mode="11408"，
              与 course **共用一张表**，经 _MODE_MAP 分流）各自 1:1 mirror 为
              PracticeSession + PracticeAttempt；per-session 汇总行 → 一次练习/一次考试一个 session，
              逐题明细只在 result_json.results，**不伪造 attempt**；
              tri-state 保持（大题/自评 correct=NULL，永不 False）；
              **done records 判为 INELIGIBLE_AS_HISTORY**（per-user 聚合，只留最后一次，非 attempt history）；
              context：exam_track_id/subject_id/module_id 由 cs408_context 统一构造，
              LearningContext.subject_key 保持 legacy module mirror；
              QuestionRef.context 携带 exam_subject_id / exam_module_id /（真题）question_year；
              **PAST_EXAM_IDENTITY_AUDIT**（只读实测 235 行）：ACTIVE 170 / SUPERSEDED 65；
              同 module+year 内 ACTIVE 唯一 170/170，跨 module 同年碰撞 0，跨年碰撞 0；
              65 个重复组全部是 image-placeholder 世代的 superseded 行（is_active=0，
              全部有 active 对应行、0 孤儿，来源已定位为旧 builder 的 deactivate+insert 协议），
              **不删除**（可能已被 done/wrong/favorite/attempt 引用）；
              **PAST_PAPER_STABLE_KEY = (subject_key, year, question_number)**
              （chapter 行为 year/qnum NULL，其稳定身份是既有内容哈希）；
              **PAST_EXAM_WRONG_SCOPE = subject:<exam_subject_id>|module:<exam_module_id>|year:<question_year>**
              （旧形态 year:<y>；判据：question_source_id 是题库自增 PK 全局唯一，
              scope 需承担的是「未来第二门统考科目」维度；module 仍编码因为对所有现存引用
              都可从 subject_key 派生，省略它会让同 subject 下两 module 复用题号失去保护；
              exam_track_id **永不进入** scope）；recompute 新增 legacy scope **就地采纳**
              （不产生第二条状态；两种形态并存时不静默合并）；legacy 回填与 live 投影共用
              同一个 past_exam_scope()；
              **D6 修复**：新增 backend/past_paper_upsert.py（稳定键 reconcile：命中→原地更新保 id，
              多行→survivor=active 优先否则 id 最大且其余原样保留，未命中→插入，
              新 source 不存在的 key→deactivate 但**永不删除**；恒等列由 helper 自写），
              4 个 wholesale DELETE 的 builder + 1 个 deactivate 累积的 builder 全部改为 reconcile；
              chapter_question_upsert 加法式扩展（可选 analysis/quality_status/source_ref），
              CN chapter builder 随之接入；
              **PAST_PAPER_BUILDER_DELETE_INSERT = REMOVED**；
              ID 稳定性/幂等性测试：同输入两次 → (2,0) 后 (0,2)、id 与内容逐字节相同；
              改内容 → 同 id 新内容；source 少一题 → deactivate 且行仍存在；
              EXAM_WRONG_SHARED_CORE=PASS / WRONG_REPLAY_DOUBLE_COUNT=NO；
              EVENT_SUBJECT_KEY=cs_408 / EVENT_MODULE_CONTEXT=PASS / EXAM_EVENT_DUPLICATION=NO
              （data_plane.emitter 是 course-only：SERVICE_KEY/EVENT_TYPE 为模块常量且唯一调用点
              在 course 提交流程；exam AI-question attempt 无第二 owner）；
              records 投影**加法式**暴露 exam_module_id；
              **EXAM_KNOWLEDGE_UPDATE_EXACTLY_ONCE=PASS**：AST 审计 52 条 exam 路由，
              practice（chapter/真题/AI）**不产生任何 knowledge delta**（现状语义，H2 保持不改），
              唯一 knowledge 写入点仍是 PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}
              （直写，未接 canonical writer，已登记 OUT_OF_SCOPE_SPACE，需 writer 支持 exam
              knowledge 身份后才能迁移）；STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO；
              FREE_USER_EXAM_FACT_PERSISTENCE=PASS；CROSS_USER/CROSS_NAMESPACE/CROSS_MODULE
              ISOLATION=PASS；MULTI_SUBJECT_COLLISION_SAFE=PASS（合成 cs_408/math_1/math_2/math_3
              context 各得独立 scope，**未导入任何真实新科目数据**）；
              REAL_APP_DB_MUTATED=NO；NEW_TABLES=NONE；无新 migration；
              QUESTION_BANK_COUNT=9333 / QUESTION_BANK_CONTENT_PRESERVED=YES
              （REAL 与 COPY 的题库指纹逐字节相同 = 349a76497c8a5320f822f99809fe9553）；
              TARGETED_TESTS=29 PASS（tests/test_exam_practice_records.py）；
              FULL_BACKEND_TESTS=741 passed / 0 failed（STEP7H1 baseline 712）

H2_C1 = CLOSED（Wrong projection concurrency closure）
H2_C1_NOTES = **根因（实测两层）**：① 产品侧 —— 投影的「读事实集合 → 写状态行」不原子，
              一个 pass 的读可能早于另一条 attempt 的提交而它恰好最后写入 → 状态停在 1
              （实测 178/200 轮出现混合读集 [1,2]，1/200 轮真的违反）；② 测试侧 —— worker
              线程读取 fixture session 上**已过期的 User 属性**（`u.id`）触发跨线程 lazy
              refresh → ObjectDeletedError → 该轮 attempt 根本没落库，旧断言顺序
              （先查 wrong_count 后查 errors）把它误报成「stale projection」。
              **修复（保留 RECOMPUTE-NOT-INCREMENT）**：`recompute()` 改为
              compare-and-recompute —— 每个 pass 读 → 写（返回 applied）→ 用**独立新
              session** 校验事实集合指纹未变，否则重做（上限 5 次）；并发首插竞态不再
              「返回胜者的行」，applied=False 强制重做（行走 UPDATE）。未使用 blind
              increment / 全局锁 / 新表，未改 Wrong semantics 与 attempt identity；
              verify 走独立 session 是因为 commit 后同 session 的 refresh+SELECT 可能落在
              该 refresh 打开的事务快照里 → 陈旧的 pass 会自我「验证通过」。
              测试侧：worker 在测试线程上先取 `uid`。
              STRESS：修复前 5/40 runs 失败（2000 轮）→ 修复后 0/30 runs（1500 轮）、0/40（2000 轮）；
              `tests/test_wrong_answers.py` 强化为 50 轮 stress + replay + wrong/wrong/correct，
              每轮先断言 errors 再断言状态（避免再次误报）。
              EXAM_PRACTICE_KNOWLEDGE_SIDE_EFFECT_DUPLICATION=NO /
              EXAM_KNOWLEDGE_CANONICAL_WRITER_CONSOLIDATED=NO（PATCH study-plan
              knowledge-items 仍直写，属后续 Exam knowledge consolidation，不阻断 H3）

STEP7H3 = FROZEN（Exam AI → Unified AIOrchestrator）
STEP7H3_NOTES = 实施报告 STEP7H3_EXAM_AI_ORCHESTRATOR_ACCEPTANCE_REPORT.md；
              EXAM_AI_ENDPOINT_COUNT=24（native /exam* 4 + 带 exam 分支的 shared 端点 20）；
              EXAM_DIRECT_PROVIDER_CALLSITE_COUNT（迁移前）=8（main.py 7 + exam_paper_parser 1）；
              EXAM_SECONDARY_PROVIDER_CALLSITE_COUNT=2（条件精修 + JSON 修复重试，均已 orchestrated）；
              PARSER_OCR_CALLSITE_COUNT=2（保留）；
              **EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL=0 / EXAM_DIRECT_PROVIDER_CALLS_FINAL=0**；
              全部 exam 学习 AI 走 execute_exam_ai → AIOrchestrator；新增 `_exam_ai_content`
              与 `_is_exam_ai_scope()`（canonical `exam_prep` 与 legacy 方向标记两种拼写都
              路由到 exam 边界，否则持有 canonical 名的调用方会掉到 course 边界）；
              CAPABILITY 复用既有集合，**未新增**空间专属 capability；试卷结构化用
              `question.generate`（产物是题目，不是知识图谱）；
              **D3 关闭**：`exam_paper_parser._grade_big_question` 已删除（连同其 OpenAI client
              与 DEEPSEEK_API_KEY 读取）；parser 模块收敛为 document parsing / 题目抽取 / OCR
              infra，**零 provider 客户端**；`grade_submission(..., grade_big=...)` 由调用方注入
              评分器，未注入时用纯启发式 `_ungraded_big_answer`（明确标注），任何路径都不触达 provider；
              **B5.2 无浪费调用**：先查题库 → 有 active 行则确定性评分
              （DETERMINISTIC_GRADE_PROVIDER_CALLS=0），无行才调 AI
              （AI_GRADE_PROVIDER_CALLS=1 且结果被真实使用，AI_GRADE_RESULT_USED=YES）；
              旧行为是「无条件先跑 AI 评分，随后被确定性结果整块覆盖」= 付费后丢弃；
              **FACT FIRST**：AI 评分被拒（403/429）或失败时端点不抛错、不丢提交 ——
              PastPaperAttempt 仍以确定性暂定分落库并置 submitted，响应新增
              `answer_grade:{applied,reason}`；canonical mirror 仍只发生一次；
              ANSWER_GRADE_MIGRATED=PASS（Free DENIED / Standard ALLOWED / Advanced ALLOWED；
              pool proxy QUESTION_EXPLAIN_PROXY_V1；POOL_VERSION 仍 v4，未新开 benchmark）；
              结构化输出校验：score 必须为整数且 0..10，否则 GradeOutputError（postprocessing
              failure）；**已产生的 measured usage 照常 settle，不全额 refund**；
              **EXAM_AI_LEGACY_AUTH_OWNER=0** —— 源码中已无 check_exam_408_usage_limit 的
              任何调用点；`require_learning_context_feature` 退出 exam AI 路径；
              非 AI 的 legacy study-plan CRUD entitlement 与 legacy 会员/额度 service_key
              **刻意保留**（随统一会员退役，不做机械重命名）；
              EXAM_AI_BILLING_DOUBLE_COUNT=NO（generate_exam_ai_questions 的 legacy 成功率
              记账已删除；一次 provider invocation 只有 usage_ledger + ai_cost_records 一套事实）；
              EXAM_AI_EVENT_DUPLICATION=NO（每次 invocation 一套 AIRequest/settle/ai_called，
              含二次精修与修复重试）；
              EXAM_AI_CONTEXT_PERSISTENCE / EXAM_AI_EVENT_CONTEXT_EQUIVALENCE /
              EXAM_USAGE_LEDGER_NAMESPACE_EQUIVALENCE = PASS（service_namespace=exam_prep、
              subject_key=cs_408、domain context 含 exam_module_id）；
              COURSE_EXAM_NAMESPACE_ISOLATION=PASS（同名 token `data_structure` 在两空间
              分别是 course_id 与 exam_module_id，不串线）；
              PARSER_OCR_CLASSIFICATION=PASS / PARSER_OCR_MIGRATED_TO_ORCHESTRATOR=NO（EXPECTED=NO）；
              D8（OCR 计费/可观测）本轮不解决，继续登记；
              STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO；REAL_APP_DB_MUTATED=NO；
              TARGETED_TESTS=26 PASS（tests/test_exam_ai_orchestrator.py）；
              FULL_BACKEND_TESTS=769 passed / 0 failed（H2 baseline 741）；
              REMAINING = ① Exam knowledge canonical writer 未收敛；② D7 14 张 exam 表无
              Alembic 覆盖；③ D5 favorite v2 死表；④ D8 OCR 计费；⑤
              generate_exam_ai_questions 仍读 DEEPSEEK_API_KEY 做「未配置则 mock」短路
              （配置门，非执行路径，属后续清理）；⑥ H4 多 track/subject catalog（需用户批准）
```

```text
STEP7H4 = FROZEN（Multi-track / Multi-subject Exam Preparation catalog foundation）
STEP7H4_NOTES = 实施报告 STEP7H4_EXAM_FRAMEWORK_ACCEPTANCE_REPORT.md；
              **本轮为 RECOVER_AND_FINISH**（上一会话 context length 上限中断；
              以磁盘事实为唯一 baseline，未重做、未按聊天历史猜）；
              H4_RECOVERY_MATRIX：上一会话声称的 catalog.py / knowledge.py /
              migration 20260917_0007 / routers/exam_prep.py / models.ExamPrepProfile /
              main.py PATCH 收敛 / test_exam_framework.py **全部真实存在且形态正确**；
              「2 个 test bug」在磁盘上已修复（recovery 后 51 passed / 0 failed，无需改动）；
              **CATALOG_VERSION=v2；CATALOG_STORAGE=CONFIG；CATALOG_SQL_TABLES=0**
              （catalog = learning/spaces/exam_prep/catalog.py，versioned config 可 diff）；
              Track / Subject / Module **三个概念保持分离**（不把 track==subject 变通用规则）：
                ExamTrack = 我准备什么方向/组合；ExamSubject = 实际考什么（全国统考科目）；
                ExamModule = 该科目的教学组织；
              **可用性（H4 的承重规则）**：
                ACTIVE = active（真实内容已上线）；FRAMEWORK_ONLY = framework_only
                （可选、可表达，**零伪造**）；
              CS408_CONTENT_STATUS=ACTIVE（cs_408，4 modules：data_structure /
              computer_organization / operating_system / computer_network）；
              NON_CS408_CONTENT_STATUS=FRAMEWORK_ONLY，共 13 个：politics / english_1 /
              english_2 / math_1 / math_2 / math_3 / management_aptitude /
              economics_joint_aptitude / law_master_law / law_master_non_law /
              education_basics / psychology_basics / history_basics；
              能力标志（has_questions / has_past_papers / has_knowledge_tree）
              **由 CONFIG 派生，绝不来自数表行数** —— 产品能力不得因某表恰为空而改变；
              非 CS408 科目**无 chapters / 无 knowledge points / 无 questions / 无 seed 占位**；
              `suggested_subjects` 除 cs_408 外**全部为空**（仓库无权威来源说明某方向需要哪些
              公共课；catalog 不猜，学习者的 selected_subjects 才是真正 scope）；
              **院校自命题永久 OUT OF SCOPE**（school / institution / college / major-code /
              school exam code / 参考书目 / 院校大纲零表达）；
              **CONTENT GATE（单一诚实答案）**：GET /exam/prep/subjects/{id}/content-status
                ACTIVE → 200 + 元数据；FRAMEWORK_ONLY → **409 + EXAM_CONTENT_NOT_AVAILABLE**
                （刻意不用 404：科目存在且可选，只是尚无内容）；unknown → 404；
                **禁止 200 + [] 冒充成功**；
              **EXAM_PREP_PROFILE_TABLE=exam_prep_profiles（NEW_TABLES=1）**；
                字段：id / user_id UNIQUE(uq_exam_prep_profile_user) / exam_type /
                selected_track / selected_subjects_json / target_exam_year / created_at /
                updated_at；**每用户一个 CURRENT profile**；
                INSTITUTION_SPECIFIC_FIELDS_ADDED=0；
                target_exam_year 是**目标年份**，与真题 question_year 不同概念，
                **不进任何 practice/wrong/event identity**；
              Profile API：GET/PUT /exam/prep/profile、GET /exam/prep/catalog(/tracks|/subjects)、
                GET /exam/prep/subjects/{id}/content-status；
                **FRAMEWORK_ONLY subject 允许选择**（目标就是目标，即使内容尚未上线）；
                非法 track / subject id → 400 fail closed；**Free 用户也可保存**；
                EXAM_PREP_PROFILE_ISOLATION=PASS（跨用户完全独立）；
              **EXAM_KNOWLEDGE_CANONICAL_WRITER_CONSOLIDATED=YES**：
                H4 前 PATCH /exam/11408/{k}/study-plan/knowledge-items/{code} **直接写**
                user_knowledge_progress（路由成为 exam knowledge 状态/review 调度/事件语义的
                事实 owner）；H4 后唯一写入边界 = learning/spaces/exam_prep/knowledge.py，
                路由调用之；**PRESERVE PATCH CONTRACT**：legacy URL / method / response /
                score 阈值（learning 默认 30、mastered=100）/ study-plan 语义 / review 算法 /
                mastery 解释**一律未改**；
                EXAM_MUTATION_PATHS 共 3 条全部已声明，exam_paths_not_consolidated()==[]；
                **知识身份**：user + service_namespace=exam_prep + exam_subject_id=cs_408 +
                exam_module_id=<module> + knowledge_point_code；
                **来源不是 KnowledgePoint SQL 表**，而是
                seed_data/knowledge_maps/<module>_11408.json（leaf 校验）+
                exam_question_bank knowledge metadata → **不要求 knowledge_points 有对应行**
                （knowledge_points 32 行属 programming ontology，与 Exam catalog 无关）；
                持久兼容：UserKnowledgeProgress.course_id 仍为 `<module>_11408`，
                **不 rewrite scope**；writer 入口显式 db.flush()（SessionLocal autoflush=False
                否则会创建重复 progress 行）；
              **EXAM_KNOWLEDGE_EVENT_SEMANTICS=PASS**：emit knowledge_status_changed 仅限
                真实状态迁移；service_key=exam_prep；subject_key=**cs_408**（H1 契约：事件
                subject 是 EXAM SUBJECT 而非 module）；domain context 含 exam_module_id +
                knowledge point code；**exam_track_id 不进事件、不进 identity**；
                同一状态重复写入**不发 duplicate transition**；event 独立 session、
                failure-isolated；**不接** StudentTwin / IRT / learner_state / misconception；
              **EXAM_BUSINESS_PROVIDER_SPECIFIC_CONFIG=0**（关闭 H3 §19 ⑤ 遗留）：
                generate_exam_ai_questions 不再读 DEEPSEEK_API_KEY 做「未配置则 mock」短路，
                直接经 _exam_ai_content → orchestrator；模型可用性由 Router / Gateway 决定；
                **provider adapter 自身 secret 配置未删**（ai/providers/*、ai/secrets.py
                仍是 provider 名唯一允许出现处）；admin 模型配置页 / 健康检查读 env 属运维面；
              **MIGRATION_HEAD=20260917_0007**（20260917_0007 Create Date 2026-09-17，
                down_revision=20260915_0006，链 0001→…→0006→0007 连续）；
                0007 **只** CREATE exam_prep_profiles + uq_exam_prep_profile_user +
                ix_exam_prep_profiles_user_id；**不**建 catalog 表 / **不**建 14 张 legacy
                exam 表 / **不**改 9333 题 / **不** drop dead table / **不** rename legacy 表；
                downgrade() = NotImplementedError（additive-only）；
                实测：FRESH temp DB upgrade head PASS；LEGACY COPY upgrade head PASS
                （head=20260917_0007 / integrity ok / 9333 题保留）；
              **REAL_APP_DB_MUTATED=NO**（真实 backend/app.db 72 表 / 无 alembic_version /
                无 exam_prep_profiles / integrity ok / mtime 2026-09-16 21:24 未变）；
                **真实库未迁移到 0007** —— Profile API 代码已就绪，线上可用需一次正式部署迁移；
              受保护资产（只读复核）：exam_question_bank=9333（逐 subject
                data_structure 5903 / computer_organization 1330 / operating_system 1180 /
                computer_network 920；逐 source_type chapter 9098 / past_paper 235
                —— 与 H1 基线**逐项相同**）/ programming_exercises=1923 /
                knowledge_points=32；exam_resources=268 文件（H0 基线 263，增加未减少）/
                static/exam_papers=564 文件（未变）；
                **H4_BANKSHA256 = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee**
                （列集 id+subject_key+source_type+year+question_number+stem+standard_answer
                +analysis，`\x1f` 连接 / `\n` 分行 / ORDER BY id；H1 的 7b0717… 未记录序列化
                方法，本轮无法逐字节复现，改用可复现方法并如实标注）；
              NON_CS408_REAL_QUESTION_ROWS_ADDED=0 /
                NON_CS408_KNOWLEDGE_CONTENT_ADDED=0 / NON_CS408_PAST_PAPER_CONTENT_ADDED=0；
              **本轮唯一修复 = 迁移测试回归（test bug，非实现 bug）**：
                首次全量 5 failed / 815 passed，全在 tests/test_practice_migration.py ——
                该文件把 `head` 当作「正被测的 revision」（EXPECTED_HEAD 硬编码 0006；
                0004/0005/0006 三处以 `upgrade head` 隔离「本 revision 自身贡献」，
                而 head 现已 0007 → 0007 的新表被错误归因给旧 revision）；
                修复（只改 test）：EXPECTED_HEAD→20260917_0007；三处改用**精确 revision**；
                新增 test_revision_0007_adds_only_the_exam_prep_profile_table
                （断言 0006→0007 恰好新增一张表、不 drop、无 *catalog* 表、受保护计数不变、
                必要列与索引存在）；
              STUDENT_TWIN_ELIGIBILITY_EXPANDED=NO；WRONG_CONCURRENCY_STRESS=PASS
                （H2-C1 compare-and-recompute 未被触碰，未重设计 Wrong semantics）；
              TARGETED_TESTS：test_exam_framework.py 52 PASS（恢复时 51，+1 provider-isolation
                断言）/ test_practice_migration.py 8 PASS（原 7）/
                H1–H3 exam 三件套 105 PASS / test_wrong_answers.py -k concurrent 3 PASS；
              FULL_BACKEND_TESTS=**822 passed / 0 failed**（H3 baseline 769；
                +53 = exam_framework 52 + 新增 migration 1）；
              REMAINING = ① 17 张 legacy exam 表仍无 Alembic baseline（H0 R3 🟠）；
              ② 真实 app.db 未迁移到 0007（需一次正式部署迁移）；
              ③ FRAMEWORK_ONLY 科目公共课组合未定义（诚实的空，非遗漏）；
              ④ 非 408 真实内容导入仍未发生，**必须等用户明确批准**（H0 §21）；
              ⑤ H5 = CS408 full acceptance（onboarding → 章节练习 → 真题 → 错题 → 计划 →
              记录 → 报告）—— **STEP7H 整体未 COMPLETE，不得声称 STEP7H COMPLETE**
                ［H4 冻结时的状态；**已被 STEP7H5 取代**：H5 完成后 STEP7H 已整体 FROZEN，
                见本 §73 的 STEP7H5 条目］
```

```text
STEP7H5 = FROZEN（Exam Prep / CS408 final backend acceptance + deployment hardening
                  + frontend API handoff）—— **STEP 7H 到此整体 FROZEN**
STEP7H5_NOTES = 实施报告 STEP7H5_EXAM_PREP_FINAL_BACKEND_ACCEPTANCE_REPORT.md；
              前端交接 STEP7H_FRONTEND_API_HANDOFF.md（面向实现方，短且稳定）；
              本轮**不新增任何产品能力**，只做验收 / 加固 / 修复 / 交接；
              **EXAM_RUNTIME_SCHEMA_ALEMBIC_COVERAGE = COMPLETE**：
                新增 migration **20260917_0008**（baseline_exam_legacy_runtime_tables，
                down_revision=20260917_0007）；0001–0007 **未做任何修改**；
                覆盖 exam 路由实际读写的 13 张表（11 张 exam 自有 + 2 张 exam 运行时读写的
                共享存储 user_knowledge_progress / user_knowledge_review_settings）；
                表集由 exam 路由处理器**实测反推**，非按名字模式猜测；
                **不**覆盖 exam_favorite_questions_v2（0 行 / 0 运行时引用 / 无 FK，
                = DEAD_DELETE_LATER，不因「表数齐全」升级为 canonical requirement）；
                **不**覆盖 knowledge_points / knowledge_progress_events /
                material_knowledge_links（SHARED_NOT_EXAM_OWNED，属更广 legacy baseline）；
                同一 migration **同时**支持 fresh 空库（建表+索引）与 legacy app.db COPY
                （表已存在则**原样保留**，仅补缺失的模型声明列/索引，additive）；
                无 DROP / 无 rebuild / 无行重写 / 不动 9333 题库；downgrade=NotImplementedError；
              **MIGRATION_HEAD = 20260917_0008**；
              **FRESH_DB_ALEMBIC_ONLY = PASS**：全新空库只跑 `alembic upgrade head`
                → head=0008 / integrity ok / 27 表 / 13 张 Exam 运行时表全部存在 /
                死表不存在；并用 ORM 元数据逐表比对「模型声明列 == alembic 建成列」
                且实际 query() 成功 → **EXAM_SCHEMA_DEPENDS_ON_CREATE_ALL = NO**；
              **LEGACY_DB_COPY_UPGRADE = PASS**：app.db COPY upgrade head → head=0008 /
                integrity ok / 86 表（未减少）/ 9333 / 1923 / 32 /
                **BANKSHA256 与真实库逐字节相同**；
              **REAL_APP_DB_MUTATED = NO**（真实库 72 表 / 无 alembic_version /
                无 exam_prep_profiles / integrity ok / mtime 2026-09-16 21:24 未变 /
                REAL_APP_DB_MIGRATED = NO，线上迁移走既有部署流程）；
              **本轮发现并修复一个 H4 漏登记的真实隔离缺陷**：
                `PATCH /knowledge-map/progress` 的 course_id 经
                normalize_subject_course_learning 归一，而 "<module>_11408" 不在归一表里
                → 原样保留 → seed 存在 → **该路由可带 exam scope 调用**
                （/knowledge-map/review-settings 甚至显式特判 `_11408`，证明该路径确被使用）；
                修复前：行落在 exam 作用域（course_id 正确），但事件被记为
                **service_key=course_learning / subject_key=None** —— 考试知识变更被记成
                课程事件，即 H1 修过的 D1 类跨空间污染残留；
                修复：用 learning.spaces.exam_prep.scope.parse_legacy_exam_scope_id 判定，
                exam scope → 委派 exam_prep.knowledge.apply_exam_knowledge_change；
                响应契约 / 行作用域（`<module>_11408`）/ review 调度语义**全部不变**；
                course scope 行为**完全不变**（实测仍为 service_key=course_learning）；
                EXAM_MUTATION_PATHS 由 3 条补为 **4 条**，
                exam_paths_not_consolidated()==[]，**UNDECLARED_DIRECT_WRITE = 0**；
              **CS408_FULL_BACKEND_E2E = PASS**（profile → catalog → module → 知识 →
                章节练习 → 错题 active → 纠正 → resolved → 记录 → 真题 → 计划）；
              **FREE_EXAM_LOOP = PASS**（非 AI 闭环完整可用；付费 capability 403 且
                provider 调用=0；会员差异不影响任何事实持久化）；
              **STANDARD_EXAM_AI_LOOP = PASS**（question.generate / planning.generate /
                answer.grade 走满 estimate→reserve→execute→actual→settle；
                AIRequest.service_namespace=exam_prep、context 含 cs_408+module；
                UsageLedger 有行）；
              **ADVANCED_EXAM_CAPABILITY_LOOP = PASS**（report.generate 仅 Advanced；
                Standard 同 capability 403 且 0 调用）；**未改任何 membership 语义**；
              **FRAMEWORK_ONLY_SELECTION = PASS / FRAMEWORK_ONLY_CONTENT_GATE = PASS**
                （13 个科目逐个：可选可存 200；content-status 一律 **409 +
                EXAM_CONTENT_NOT_AVAILABLE**；响应体**不含**任何 408 标识 → 无静默 fallback；
                无 200+占位；无 LLM 生成内容）；
              **LEGACY_11408_ROUTE_COMPATIBILITY = PASS**（10 条代表性读接口全 200；
                legacy 路由未删除未改名；study-plan 对 Free 仍 403，legacy 权益刻意保留）；
              **EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0 / EXAM_DIRECT_PROVIDER_CALLS_FINAL = 0**
                （50 个 exam 路由块逐一扫描 call_deepseek / DEEPSEEK_API_KEY / OpenAI( /
                chat.completions / DASHSCOPE → 0 命中；exam_prep 包与 routers/exam_prep.py
                同样 0 命中并有可执行断言；main.py 其余 12 处 call_deepseek 均在
                course/programming/admin 非 exam 路径）；
              **PARSER_OCR_CLASSIFICATION = PASS**；**D8 = NON_BLOCKING_INFRA_TECH_DEBT**
                （OCR 只服务资料/真题解析 infra，非 exam 学习核心路径；有按套餐页数上限
                20/500/1000 + 系统天花板 ai_pdf_scan_max_pages + MAX_OCR_CHARS=12000，
                无无限成本、无会员绕过；未并入 Orchestrator、未新建第二套会员体系）；
              **QUESTION_BANK_COUNT = 9333 / QUESTION_BANK_CONTENT_UNCHANGED = YES**
                （逐 subject 5903/1330/1180/920，逐 source_type 9098/235，与 H1 基线逐项相同；
                H5_BANKSHA256=6f788bca7b76a5b6bedbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee）；
                exam_resources 268 文件 / static/exam_papers 564 文件（未减少）；
              **WRONG_CONCURRENCY_STRESS = PASS**（500 轮 × 2 线程 = **1000 次并发写入**，
                每轮断言 states==1 且 wrong_count==2，0 失败；H2-C1 语义未改动）；
              **DUPLICATE_METHOD_PATH_REGISTRATIONS = 0**；
              **CROSS_USER_ISOLATION / CROSS_NAMESPACE_ISOLATION / CROSS_MODULE_ISOLATION
                = PASS**（跨用户 profile/练习/错题/记录；course_learning vs exam_prep 同名
                token 不串线（写方向亦已成立）；同空间跨 module 不串线）；
              **FRONTEND_API_HANDOFF = COMPLETE / FRONTEND_CHANGED = NO**
                （交接文档含 IA / ACTIVE vs FRAMEWORK_ONLY / canonical endpoints /
                CS408 既有内容接口 / 状态契约 / 错误契约（detail 的两种形态）/
                profile 契约 / module id+显示名 / 10 条禁止的 UI 假设 /
                会员体验（不暴露后端 registry））；
              TESTS：新增 backend/tests/test_exam_final_acceptance.py（**53 PASS**）；
                test_practice_migration.py 由 8 → **11 PASS**（新增 0008 三项）；
                修复 3 个测试自身缺陷（fresh alembic 库无 users 表 / AIRequest 无
                subject_key 列（在 context_json）/ dashboard-summary 真实路径带 subjects/
                context_json 已是 dict）—— 均为 test bug，非产品缺陷；
              FULL_BACKEND_TESTS = **878 passed / 0 failed，连续两次**
                （FULL_RUN_1 453s / FULL_RUN_2 479s，无 flaky；H4 baseline 822，+56）；
              REMAINING（**全部 NON_BLOCKING_TECH_DEBT**，无 data correctness /
                schema deployment / namespace / billing correctness / user-fact loss blocker）
                = ① 约 46 张非 Exam 表仍无 Alembic owner（fresh 部署仍依赖 create_all +
                ensure_*），属更广 legacy baseline，需独立硬化轮次；
                ② D8 OCR 不经统一 usage_ledger / ai_cost_records 记账；
                ③ D5 exam_favorite_questions_v2 死表仍在（需独立可回滚 migration）；
                ④ 真实 app.db 未迁移到 0008（走正式部署流程）；
                ⑤ 13 个 FRAMEWORK_ONLY 科目无真实内容（**有意为之**，须用户批准才导入）；
                ⑥ /exam-408/* 院校自命题遗留路由仍存在（保持 legacy 兼容，前端不得暴露入口）；
                ⑦ datetime.utcnow() DeprecationWarning（2 类位置，不影响正确性）；
              **STEP7H5_COMPLETE=YES / STEP7H5=FROZEN / STEP7H=FROZEN / FRONTEND_READY=YES**；
              **NEXT_MAJOR_PHASE = FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION**；
              **后端停止继续扩展**
```

## ACCEL SPRINT 记录（前端阶段内的加速后端产品化）

```text
ACCEL_SPRINT_S1 = COMPLETE（2026-09-19）
ACCEL_SPRINT_S1_SCOPE = F1C6 Learning Record 契约收口 + Scientific Runtime 产品桥 V1
ACCEL_SPRINT_S1_REPORT = ACCEL_SPRINT_S1_RECORDS_AND_SCIENTIFIC_BRIDGE_REPORT.md
ACCEL_SPRINT_S1_NOTES =
  - 时间语义统一：naive persisted datetime = UTC，6 处转换收敛到 core/timeutil.py
    （SAME_REAL_MOMENT_EVENT_TIME_DRIFT = 0s）
  - AI 审计事实（ai_called）不再出现在用户学习记录：服务端排除 + include_audit 显式 opt-in，
    事实本身保留；AI_AUDIT_EVENT_USER_FACING = NO
  - /learning-records 前缀歧义消除（detail 只匹配 canonical UUID；legacy /stats 恢复可达）；
    新增 canonical exam 时间线 GET /exam/prep/records（SQL 侧 module 过滤）
  - 未作答不再暴露 score=0（UNANSWERED_SCORE_ZERO = 0）；summary 改为 SQL 聚合（有界）
  - records / scientific 全部有 concrete OpenAPI 模型（*_UNKNOWN = 0）
  - Scientific Runtime 桥 = backend/science/（唯一 HTTP client；Product Backend 零重依赖导入）

ACCEL_SPRINT_S2 = COMPLETE（2026-09-19）
ACCEL_SPRINT_S2_SCOPE = StudentTwin CS408 产品化 Gate 收口 + SSOT 治理更新
ACCEL_SPRINT_S2_REPORT = ACCEL_SPRINT_S2_STUDENT_TWIN_CS408_PRODUCTIZATION_REPORT.md
ACCEL_SPRINT_S2_NOTES =
  - **产品决策（用户明确）**：CS408 事实性 question_answered 事件 MAY 为 StudentTwin eligible，
    当且仅当携带权威二元正确性事实（见 § 36 / StudentTwin 冻结状态 INPUT_DOMAIN_ELIGIBILITY）
  - 规则落点 = data_plane.eligibility.student_twin_input_eligibility（同时被 worker 与
    product preview 消费；家族级 eligible 是必要非充分条件）
  - 科学侧零改动：公式 / 状态转移 / runtime release id / 模型资产全部不变
    （RUNTIME_RELEASE_ID_CHANGED = NO）
  - MISCONCEPTION_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE（未晋升；
    RUNTIME_PROVISIONED != PRODUCT_ELIGIBLE）
  - TUTOR_POLICY_PRODUCT_MODE = SHADOW（未晋升；turn-state 仍不可诚实构造）
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

> **智学AI正在从“已有大量后端能力、旧三方向会员、旧 AI 直连架构”迁移为“统一会员 + Usage Credits + 三 Learning Space + Shared Learning Core + AI Router/Gateway + Data Plane + Scientific Runtime”的 Clean-Slate 产品。现有成熟业务与静态资产优先保护，旧产品边界、旧会员和旧额度模型逐步淘汰。STEP 5 的 Python 文件 / 数据库 / API 处置矩阵已冻结，STEP 6 已冻结。当前处于 STEP 7（后端实现 / 重构）进行中：STEP7A / STEP7B / STEP7C / STEP7C-P / STEP7D / STEP7E / STEP7F / STEP7G（含 STEP7G-C2）/ STEP7H0 / STEP7H1 / STEP7H2（含 H2-C1）/ STEP7H3 / STEP7H4 / STEP7H5 均已 FROZEN；CURRENT_SUBSTEP = STEP_7H5，NEXT_SUBSTEP = FRONTEND。考试空间已完成从「只有 11408」到统一 Exam Prep 的 canonical namespace 升级（canonical = exam_prep；exam_11408 为 INPUT alias；只支持全国统考型研究生招生考试科目，院校自命题 OUT OF SCOPE；当前实际装载 CS408，其 chapter / 真题 / AI 出题三条作答事实已全部接入 Unified Practice / Wrong / Records）；H4 已交付多 track / 多 subject 的 Exam Prep **framework**（catalog = versioned CONFIG，`cs_408` = ACTIVE，其余 13 个全国统考科目 = FRAMEWORK_ONLY **零内容**，非 408 真实内容导入必须等用户明确批准）；H5 已把 Exam 运行时 schema 纳入 Alembic（HEAD=20260917_0008，fresh 部署可仅靠 `alembic upgrade head`）并交付前端 API 交接文档。**STEP 7H 整体 FROZEN，后端停止继续扩展；NEXT_MAJOR_PHASE = FRONTEND_REBUILD / FRONTEND_PRODUCT_IMPLEMENTATION。`main.py` 走 REFACTOR / EXTRACT。**
