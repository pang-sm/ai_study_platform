# 智学平台总体架构基准（ZHIXUE PLATFORM BASELINE）

> ## ⚠️ 权威状态：已被取代（SUPERSEDED）
>
> **本文档不再是项目 SSOT。** 唯一最高权威是仓库根目录
> **`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`**（ZHIXUE_AI_PRODUCT_REDESIGN_SSOT）。
>
> 冲突时 **SSOT wins**。本文档保留为历史架构基准，仅在 SSOT 未覆盖的细节上作为参考。
>
> 已被 SSOT 明确改写之处（不得再按本文档执行）：
> - 本文档的 `ZhiXue-KT` / `ZhiXue-Ranker` / `ZhiXue-Retriever` / `ZhiXue-CodeDiag`
>   自研模型命名，已被 SSOT §36 的 **13 个 Scientific Component** 取代。
> - 会员 / 额度 / AI 分层，以 SSOT §4–§9、§30–§31 为准。
> - 当前阶段以 SSOT `# 73. SSOT 状态` 为准（`CURRENT_STEP = STEP_7`）。
> - Java 后端路线已取消（`JAVA_BACKEND = CANCELLED`，SSOT §2.1）。

- **文档名称**：智学平台总体架构基准
- **Version**：V1.1
- **Status**：SUPERSEDED by `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`
- **Date**：2026-09-10
- **Scope**：产品架构、AI 架构、数据架构、自研模型路线、扩展原则
- **原则**：后续架构级改动不得静默偏离 SSOT；本文档保留历史记录，不再作为执行依据。

> 相关但不替代本文档的规范：
> - `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md` —— 学习体验与信息架构历史基准（同样已被 SSOT 取代）。
> - `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md` —— 视觉方向基准（从属于 SSOT）。
> - `docs/UI_DESIGN_SPEC.md` —— 前端 UI/UX 的唯一权威规范（视觉层）。
> - `docs/FRONTEND_ARCHITECTURE.md` —— 前端工程架构（React/Vite/Router/Query 层）。
> - `docs/FRONTEND_API_CONTRACT.md` —— 前后端 API 契约说明。
>
> 本文档覆盖上述层面之上的**产品边界、业务结构、AI 能力分层、数据架构与自研模型路线**。

---

## 1. 产品总定位

产品统一名称：**智学平台**。不再以“计算机学习智能体”作为整个产品边界。

总体定位：智学平台面向高校学习者，以三大一级业务场景为核心：

1. 考研学习
2. 课程学习
3. 编程学习

三者共享统一的：

- 用户体系
- AI 能力
- 资料体系
- 知识体系
- 题目体系
- 错题体系
- 学习计划
- 学习记录
- 学习画像
- 会员体系
- 数据体系

**禁止**未来把三大业务重新做成三个互相割裂的网站。

> **用户学习体验（Learning-first）**：三大业务是**三个 Learning Worlds**，但用户进入平台后的第一优先级是
> **「当前学习 / 下一步行动」**，而不是三大业务目录或学习 KPI。三大业务作为**次级探索层**。权威定义见
> `docs/product/ZHIXUE_LEARNING_EXPERIENCE_BASELINE_V1.md`。

---

## 2. 一级产品结构

固定为：

```text
智学平台
│
├── 考研学习
├── 课程学习
└── 编程学习
```

### 2.1 考研学习

```text
考研学习
├── 计算机考研
│   └── 11408
│       ├── 数据结构
│       ├── 计算机组成原理
│       ├── 操作系统
│       └── 计算机网络
├── 数学考研
│   ├── 数学一
│   ├── 数学二
│   └── 数学三
├── 英语考研
│   ├── 英语一
│   └── 英语二
├── 396 经济类联考
├── 199 管理类联考
└── 更多专业考试
```

- **11408**：当前已有成熟内容，应迁移复用。
- **其他考研方向**：先建立框架，**不得虚构已有完整内容**。
- **11408 定位**：考研体系中的**第一个完整垂直实例**，而不是一级产品。

### 2.2 课程学习结构

课程学习分为：

```text
课程学习
├── 公共基础课程
└── 专业课程
```

公共基础课程优先：

```text
数学
├── 高等数学
├── 线性代数
├── 概率论与数理统计
└── 离散数学

物理
└── 大学物理
```

后续可扩展其他理工科公共课程。

专业课程：

```text
专业课程
├── 计算机类
├── 电子信息类
├── 自动化类
├── 电气类
├── 机械类
└── 更多理工科专业
```

- **计算机专业**：已有内容继续保留、迁移、复用。
- **其他专业**：当前只建立扩展框架，不虚构成熟内容。

### 2.3 编程学习

编程学习保持相对独立的**实践型工作流**。

当前核心语言：**C、C++、Java、Python**。

保留现有能力：

- 学习画像
- 水平评估
- 学习路径
- 知识学习
- AI 出题
- 在线编程
- 代码执行
- AI 反馈
- 错题 / 薄弱点
- 学习记录

**编程不能被强行套成普通“课程资料 + RAG”系统。**

---

## 3. 平台统一学习对象模型

未来新增学科**禁止复制一套前端和后端**。总体内容结构应逐渐抽象为：

```text
LearningDomain
    ↓
Category / Program / Exam
    ↓
Subject
    ↓
Chapter
    ↓
KnowledgePoint
```

以及关联对象：

```text
Resource
Question
KnowledgeRelation
LearningActivity
UserProgress
```

**目标**：新增“信号与系统”“高等数学”“数学一”等内容时，主要通过**配置和数据扩展**，而不是重新开发一套业务系统。

> Status：TARGET / PLANNED（当前后端内容模型尚未完全统一到该抽象；迁移见 §17）。

---

## 4. AI 总体设计原则

智学平台**不得**设计成：

```text
业务页面 → DeepSeek API
```

必须设计成：

```text
业务层
 ↓
AI Capability Layer
 ↓
Model Gateway
 ↓
Provider Adapter
 ↓
第三方 API / 本地模型 / 自研模型
```

核心原则：**业务代码不应该知道具体模型名称。**

业务请求的是**能力**，例如：

```text
CHAT_FAST
STEM_REASONING
QUESTION_GENERATE
ANSWER_EVALUATE
CODE_REVIEW
VISION_READ
OCR_FALLBACK
QUERY_REWRITE
STUDY_PLAN
```

由 Model Router 再决定调用哪一个真实模型。

**禁止**把 `deepseek-*` 等模型名散落在大量业务文件中。

---

## 5. Model Gateway

正式规划：

```text
ModelGateway
├── ModelRegistry
├── TaskRouter
├── ProviderAdapter
├── Retry
├── Timeout
├── Fallback
├── RateLimit
├── CostTracking
├── VersionTracking
└── Observability
```

第三方 API 必须允许替换。今天可能使用 DeepSeek，未来可切换：

- 新 DeepSeek 模型
- 其他商业 API
- 本地开源模型
- 自研模型

业务层原则上无需修改。

> Status：TARGET / PLANNED（当前后端直接调用 provider，尚未抽象 Model Gateway）。

---

## 6. DeepSeek 定位

当前 DeepSeek 只作为**基础智能供应商之一**，**不得成为系统架构本身**。

主要承担：

- 通用问答
- STEM 推理
- AI 出题
- 内容解释
- 总结
- 学习计划辅助
- 代码解释
- 图片理解
- OCR fallback

具体模型版本**不得永久硬编码进本架构文档**。Model Registry 保存当前实际映射。

架构文档只定义抽象槽位：

```text
FAST_LLM
REASONING_LLM
VISION_LLM
```

实际对应哪个 DeepSeek 模型由**配置**决定，API 或模型升级时无需修改业务架构。

---

## 7. Prompt Registry

所有核心 Prompt 必须**逐步集中管理并版本化**，例如：

```text
qa_course_v1
qa_exam_v1
math_explain_v1
question_generate_v1
code_debug_v1
study_plan_v1
```

每次关键 AI 调用未来至少能够记录：

- provider
- model alias
- actual model / version
- task type
- prompt version
- input tokens
- output tokens
- latency
- cost
- success
- fallback_used
- timestamp

**禁止**大量 Prompt 永久散落在 React / FastAPI 业务代码里。

> Status：TARGET / PLANNED（当前 Prompt 分散在 `backend/prompts.py` 等业务文件中，尚未统一 registry 与观测）。

---

## 8. OCR 与文档理解

正式定义：**OCR ≠ Document Understanding**。

资料处理必须设计成 **Document Pipeline**：

```text
上传文件
 ↓
文件类型检测
 ↓
原生文本解析优先
 ↓
必要时 OCR / Vision
 ↓
文档结构恢复
 ↓
标准化 Markdown / JSON
 ↓
Chunk
 ↓
知识点映射
 ↓
Embedding
 ↓
索引
```

对于原生 PDF、DOCX、PPTX：**优先解析其已有文本和结构**，不要把所有文件先转图片再 OCR。**扫描件和图片才进入 OCR / Vision 流程。**

---

## 9. OCR 策略

OCR 采用**可替换 Provider 架构**：

```text
Native Parser
      ↓
Local Document OCR
      ↓
Vision API Fallback
```

当前候选：

- PyMuPDF
- python-docx
- python-pptx
- PaddleOCR / PP-Structure / PaddleOCR-VL
- DeepSeek Vision
- DeepSeek OCR 系列（作为未来 benchmark 候选）

**不要**在架构层绑定某一个 OCR 产品。

对于公式、表格、多栏、流程图、计算机结构图、图片题，需保留专门的**视觉理解能力**。

未来应使用自己的真实教材/试卷样本建立 **OCR benchmark**，再决定默认生产组合。

> Status：CURRENT 已有 PyMuPDF / pypdf / python-docx / python-pptx / pytesseract / Qwen 解析；TARGET 建立可替换 provider 层与自有 benchmark（PLANNED）。

---

## 10. RAG 架构

统一使用：

```text
Question
 ↓
Query Understanding
 ↓
Metadata Filter
 ↓
Hybrid Retrieval
 ↓
Reranker
 ↓
Context Builder
 ↓
LLM
 ↓
Answer + Citation
```

检索至少考虑：

```text
Dense Retrieval + Keyword Retrieval + Metadata Filtering + Reranker
```

Embedding / Reranker 与生成 LLM **解耦**。默认架构允许采用开源本地 Embedding 和 Reranker，**不得依赖 DeepSeek 同时承担所有 RAG 环节**。

> Status：CURRENT 已有 `backend/rag.py` 基础能力；TARGET 统一为 Hybrid + Reranker 架构（PLANNED）。

---

## 11. Chunk Metadata

任何进入知识库的 Chunk 必须能够关联：

```text
domain
category
exam / program
subject
chapter
knowledge_point
resource_id
page
section
content_type
owner
visibility
```

`content_type` 至少考虑：

```text
text
formula
table
code
figure
```

**目的**：严格控制不同业务、课程、用户资料之间的**检索隔离**。

---

## 12. 资料范围优先级

课程 AI 问答默认考虑以下上下文优先级：

```text
1. 当前用户明确指定文件
2. 当前课程资料
3. 平台课程知识库
4. 基础模型自身知识
```

回答应尽可能保留**可追踪引用**。

---

## 13. Knowledge Graph

知识图谱必须是平台**长期内容资产**。

基础实体：`KnowledgePoint`

基础关系：

```text
prerequisite
related
contains
similar
next
```

LLM 可以辅助生成候选知识关系，但知识图谱**不能依赖用户每次提问时临时生成**。

Knowledge Graph 未来服务于：

- 知识脉络
- KT
- 推荐
- 学习路径
- 题目匹配
- RAG

> Status：CURRENT 已有 `backend/build_cn_knowledge_map.py` 等知识图谱构建脚本；TARGET 统一实体/关系模型并接入上述能力（PLANNED）。

---

## 14. 自研模型总体原则

不要把“训练自己的模型”理解为从零训练一个通用大语言模型。

智学平台最重要的自研模型应围绕：**认识学生 + 决定下一步学习**。

总体优先级：

```text
1. Knowledge Tracing
2. Next Learning Recommendation
3. RAG Retriever / Reranker 优化
4. Question Difficulty
5. Programming Error Diagnosis
6. Learning Policy / Agent
```

- LLM 主要负责**理解与生成**。
- 自研模型主要负责**学习状态估计和个性化决策**。

> Status：TARGET / PLANNED（当前无自研模型）。

---

## 15. 第一核心自研模型：ZhiXue-KT

Knowledge Tracing 输入学生历史行为，输出知识点掌握概率，例如：

```text
矩阵乘法       0.91
矩阵求逆       0.78
矩阵的秩       0.46
```

它未来应该影响：

- 学习进度
- 知识脉络状态
- 推荐知识点
- 推荐题目
- 复习计划
- 学习路径
- 用户画像

KT 初期必须建立 baseline：**BKT、DKT、SAKT、AKT**，使用真实数据比较，不预先假设某一种模型一定最好。

评价至少考虑：**AUC、Accuracy、NLL、Calibration**。

> Status：TARGET / PLANNED。

---

## 16. 从现在开始为模型训练记录数据

每一次做题/学习事件，应逐步能够形成训练记录：

```text
user_id
subject_id
chapter_id
knowledge_point_id
question_id

correct
score
attempt_count
response_time

hint_used
ai_help_used

difficulty
timestamp
```

未来可增加：

```text
confidence
previous_mastery
days_since_last_seen
```

架构设计必须考虑：**生产数据也是未来训练资产**，不得等未来准备训练模型时才开始设计数据。

> Status：TARGET / PLANNED（需评估现有学习记录与目标事件 schema 的差距）。

---

## 17. 第二核心模型：ZhiXue-Ranker

目标：根据当前学习状态预测“下一步最应该学习什么”。

输入可逐渐包括：

```text
knowledge mastery
prerequisites
history
difficulty
exam importance
remaining time
review status
```

输出：

```text
next_activity_score
```

路线：

```text
Phase 1：规则系统
Phase 2：LightGBM / XGBoost Ranker
Phase 3：Sequential Recommender
Phase 4：Contextual Bandit / Learning Policy
```

**禁止数据不足时直接上复杂 RL。**

> Status：TARGET / PLANNED。

---

## 18. 后续自研模型

统一预留：

```text
ZhiXue-KT
ZhiXue-Ranker
ZhiXue-Retriever
ZhiXue-Reranker
ZhiXue-Difficulty
ZhiXue-CodeDiag
```

模型版本命名必须类似：

```text
ZhiXue-KT-v1
ZhiXue-KT-v2
```

**禁止**使用 `final_model`、`best2`、`new_model_final` 等作为正式生产命名。

---

## 19. 模型训练管线

长期必须建立：

```text
Production
 ↓
Event Log
 ↓
Data Cleaning
 ↓
Dataset Snapshot
 ↓
Train / Val / Test
 ↓
Training
 ↓
Offline Evaluation
 ↓
Model Registry
 ↓
Shadow Evaluation
 ↓
A/B Test
 ↓
Production
```

一次正式实验至少记录：

```text
dataset_version
model_version
training_config
metrics
checkpoint
git_commit
```

**不得**直接拿实时生产数据库跑不可复现训练。

> Status：TARGET / PLANNED。

---

## 20. 三大业务技术模型

### 20.1 考研业务技术模型

考研强调：**考试成绩提升**。总体闭环：

```text
考纲 + 知识图谱 + 真题 + Question Engine + KT + Review Engine + Recommendation + RAG
```

11408 作为**第一套完整验证实例**，未来数学一等考试复用考试级框架。

### 20.2 课程业务技术模型

课程学习强调：**把课程真正学懂**。总体结构：

```text
教材 / PPT / 用户资料
        ↓
Document Pipeline
        ↓
课程知识库
        ↓
知识点结构
        ↓
RAG
        ↓
练习
        ↓
KT
        ↓
学习推荐
```

必须区分**平台公共课程知识库**与**用户个人资料知识库**，**禁止数据串线**。

### 20.3 编程业务技术模型

编程强调：**真正会写代码**。核心：

```text
Learner Profile
 ↓
Learning Path
 ↓
Programming Task
 ↓
Code Sandbox
 ↓
Compile / Execute / Test
 ↓
Result
 ↓
AI Analysis
 ↓
Programming Mastery
```

代码是否正确的真相必须来自**编译器、测试用例、Sandbox**，而不是让 LLM 猜程序对不对。LLM 负责：解释、提示、Debug 辅助、学习建议。

Sandbox 必须考虑：CPU、RAM、timeout、filesystem、network、process isolation。

> Status：CURRENT 已有 `backend/programming_execution.py` 代码执行能力；TARGET 强化隔离与判题（PLANNED 部分）。

---

## 21. 平台 AI 能力层

目标架构：

```text
ZhiXue AI Core
│
├── Knowledge Engine
│   ├── Document Parser
│   ├── OCR
│   ├── RAG
│   ├── Retrieval
│   └── Knowledge Graph
│
├── Generation Engine
│   ├── QA
│   ├── STEM Reasoning
│   ├── Question Generation
│   ├── Evaluation
│   └── Vision
│
├── Learner Engine
│   ├── Knowledge Tracing
│   ├── Recommendation
│   ├── Mastery
│   └── Study Path
│
└── Coding Engine
    ├── Sandbox
    ├── Judge
    └── Code AI
```

> Status：TARGET / PLANNED（当前能力分散在 backend 各模块，尚未收敛为分层 AI Core）。

---

## 22. 数据层

长期概念上划分：

```text
Operational Data
Content Data
Vector Data
Learning Event Data
Model Training Data
Object Storage
```

当前**不要求**立刻拆成多个物理系统。目标技术路线允许逐步从现有数据库演进到：

```text
PostgreSQL + pgvector + Redis + Object Storage
```

**不要为了建立本基准立即迁移数据库**。所有数据库迁移必须以后单独设计、备份、测试和验收。

> Status：CURRENT 为 SQLite；TARGET 为上述演进路线（PLANNED）。

---

## 23. 异步任务

以下任务以后不得长期阻塞普通 HTTP 请求：

- 大 PDF 解析
- OCR
- Embedding
- 知识点抽取
- 大规模索引
- 批量题目处理
- 部分模型推理

目标结构：

```text
API
 ↓
Task Queue
 ↓
Document Worker / OCR Worker / Embedding Worker / Knowledge Worker
```

具体 Celery / RQ / 其他实现以后根据实际情况评估，不在本轮强制落地。

> Status：TARGET / PLANNED。

---

## 24. 统一学习闭环

智学平台核心长期闭环必须保持：

```text
用户
 ↓
学习行为
 ↓
Event Tracking
 ↓
Learner Profile
 ↓
Knowledge Tracing
 ↓
Mastery Estimation
 ↓
Recommendation
 ↓
学习 / 练习 / 复习
 ↓
产生新的学习行为
 ↓
再次更新
```

三大业务前端表现不同，但底层逐渐共享：

```text
User、Knowledge、Resource、Question、Activity、Mastery、Recommendation、AI
```

---

## 25. 当前与目标架构严格区分

本文档严格区分三类状态：

### CURRENT（当前仓库已真实存在的能力）

- 后端：FastAPI（单体 `backend/main.py`）+ SQLite（SQLAlchemy）+ Pydantic v2。
- AI 调用：DeepSeek（OpenAI 兼容 client）、Qwen OCR（DASHSCOPE）。
- 文档处理：PyMuPDF、pypdf、python-docx、python-pptx、pytesseract，以及 `qwen_parser.py` 等解析脚本。
- RAG：`backend/rag.py` 基础能力。
- 编程执行：`backend/programming_execution.py` 代码执行/判题。
- 知识图谱：`backend/build_cn_knowledge_map.py` 等构建脚本。
- 内容：11408 考研（成熟）、计算机课程（已有）、编程 C/C++/Java/Python。
- 前端：React + Vite（已 bootstrap，尚无业务页面）。

### TARGET（未来目标架构）

- AI 能力分层：AI Capability Layer → Model Gateway → Provider Adapter。
- 自研模型：ZhiXue-KT、ZhiXue-Ranker、ZhiXue-Retriever / Reranker / Difficulty / CodeDiag。
- 数据层：PostgreSQL + pgvector + Redis + Object Storage（逐步演进）。
- 异步任务队列（Document/OCR/Embedding/Knowledge Worker）。
- 统一学习对象模型（LearningDomain → … → KnowledgePoint）。
- 可替换 OCR / Vision Provider 架构 + 自有 OCR benchmark。

### MIGRATION（从 CURRENT 到 TARGET 的路线）

1. 先抽象 AI 调用层（能力语义 + Model Gateway），不迁移业务功能。
2. 收敛 Prompt Registry 与调用观测（provider/model/version/tokens/latency/cost）。
3. 统一学习事件数据 schema（为 KT/Ranker 蓄数据）。
4. 建立 OCR / Document Pipeline 可替换层与自有 benchmark。
5. 建立 KT baseline（BKT/DKT/SAKT/AKT）与 Ranker 规则系统起步。
6. 数据库演进（PostgreSQL + pgvector + Redis）需单独设计、备份、测试、验收。

**所有未实现部分均标注 `PLANNED`，不得在文档中写成“当前已经部署”。**

---

## 26. reference 目录规则

```text
reference/
└── LOGO/
```

主要用于保存设计和视觉参考图。Logo 文件名固定为：

```text
zhixue_logo_main_horizontal.png
zhixue_logo_icon.png
zhixue_logo_vertical.png
zhixue_logo_horizontal_simple.png
```

- 不要擅自重命名。
- 不要让 Claude 重新生成、覆盖或修改这些 Logo。
- 以后新的设计参考图片继续放在 `reference/` 下按类别建立子目录（如 `reference/UI/`、`reference/PAGE/`、`reference/ICON/`、`reference/STYLE/` 等）；除非实际需要，不空建目录。
- 架构长文档不要放进 `reference/LOGO/`。

---

## Baseline Change Log

| Version | Date | Change | Reason | Compatibility Impact | Migration Impact |
| --- | --- | --- | --- | --- | --- |
| V1.0 | 2026-09-10 | Initial baseline | 建立总体架构 Single Source of Truth | — | — |
| V1.1 | 2026-09-10 | Homepage and learning-flow IA changed from module-first to learning-action-first | User testing / design iterations showed module-first IA encouraged dashboard-like layouts and increased decision cost | Three-domain product structure and technical architecture unchanged | Future pages should prioritize Current → Next → Action → Path → Tools |
