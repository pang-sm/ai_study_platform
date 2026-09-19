# STEP7H0_UNIFIED_EXAM_PREP_ARCHITECTURE

> 智学AI — Clean-Slate 产品重构 · STEP 7H0
> 范围：Exam Prep 域审计 + 架构冻结（**不实施**）
> 生成：2026-09-16
> 性质：architecture audit + frozen design（本轮**无实现、无 migration、无前端、无 live provider**）

---

## 1. Executive Verdict

```text
STEP7H0_COMPLETE = YES
STEP7H1_READY    = YES

CURRENT_EXAM_NAMESPACE        = exam_11408
RECOMMENDED_CANONICAL_NAMESPACE = exam_prep（legacy exam_11408 降为 INPUT alias）

NEW_TABLES_PROPOSED_FOR_H1    = NONE
SCHEMA_CHANGE_REQUIRED_FOR_H1 = NONE（仅当目标库已存在 exam canonical 行时才需要 DATA-ONLY 迁移）
```

本轮只读审计，产出：

- current 11408 真实实现（52 条 exam 路由 / 14 张 exam 表 / 263+564 静态资产 / 9333 题库）
- `EXAM_NAMESPACE_IMPACT_MATRIX`：`exam_11408` 这一 token **实际承担了 5 种不同语义**
- `CURRENT_EXAM_DATA_OWNERSHIP_MATRIX`：14 张表的 KEEP/ADAPT 处置
- `EXAM_AI_REACHABILITY_MATRIX`：12 条 exam 可达 provider 调用
- `EXAM_LEGACY_AUTH_MATRIX`
- 3 个 namespace 迁移方案 + 推荐
- STEP7H0–H5 分解

**本轮发现的真实缺陷（8 项）**，其中 1 项是 STEP7G-C2 引入的**跨空间污染**，需要在 H2 前修：

```text
D1 跨空间污染：4 个端点在 exam 请求下把统一账本/事件写成 course_learning
D2 question-analysis 已 orchestrated 但未传 LearningContext → service_namespace = NULL
D3 _grade_big_question：无授权、无计费、结果在题库存在时被丢弃（已发生的付费调用被浪费）
D4 GET /exam/11408/study-plan/tasks/summary 重复注册（第二个 handler 是死代码）
D5 exam_favorite_questions_v2 / ExamFavoriteQuestionV2 = 死表（0 行、0 代码引用）
D6 真题 builder 整表 DELETE+INSERT → exam_question_bank.id 变化 → done/wrong 引用失效
D7 14 张 exam 表全部没有 Alembic 覆盖（只靠 create_all），部署链有缺口
D8 OCR（qwen_parser）在所有 exam 路径上不计费、不记录
```

---

## 2. Current 11408 Reality

### 2.1 规模（只读实测，`backend/app.db` 副本）

```text
exam 路由总数           = 52
  /exam/11408/*         = 47
  /exam-408/*           = 4（schools / target-school / motto / exam-info）
  /me/tracks/exam_408/package = 1
exam 表                 = 14（+ 4 张共享表被 exam 使用）
exam_question_bank      = 9333 行（chapter 9098 / past_paper 235）
其他全部 exam 用户态表   = 0 行
静态资产                = exam_resources 263 文件 + static/exam_papers 564 文件
```

### 2.2 四科的真实存在形式

```text
data_structure / computer_organization / operating_system / computer_network
```

| 层 | 位置 | 证据 |
| --- | --- | --- |
| Python 常量 | `main.py:19436-19441` `EXAM_SUBJECT_DIRS`；`main.py:3076-3081` `EXAM_408_SUBJECT_KEYS`；`main.py:148-153` `EXAM_MATERIAL_SCOPE_NAMES`；`exam_paper_parser.py:21-24` | 唯一的 subject 校验源（**47 条路由全部用它做 gate**） |
| 路由路径参数 | `/exam/11408/{subject_key}/…` | 52 条中的 47 条 |
| 数据库列值 | `exam_question_bank.subject_key` 等 9 张 exam 表 | 见 §3 |
| 派生 scope id | `user_knowledge_progress.course_id = f"{subject_key}_11408"`；`study_materials.course_id='data_structure_11408'` | 与 course_learning **共用同一张表**，用 `_11408` 后缀区分 |
| 静态资产 | `exam_resources/11408/{key}/…`、`seed_data/knowledge_maps/{key}_11408.json` | 4 份知识脉络 JSON（`{course_id, course_name, source, chapters[{code,title,chapter_no,children}]}`） |
| 文件名 | `11408_2022_2026_data_structure_questions_answers.docx` 等 | 见 §4 |

> **关键事实**：`data_structure` 既出现在 **exam 的 module 位置**，也出现在 `subjects.py:64-77`
> `COURSE_LEARNING_ID_MAP` 里作为 **course_learning 的 course id**。两者同名不同域 ——
> 这正是 STEP7G 修掉 `is_exam_408_context` display-name 误判的根因，也是本设计必须
> 用 **track+subject+module** 而非裸字符串消歧的原因。

### 2.3 exam 的「科目」目前其实是「模块」

`exam_question_bank.subject_key` 承载的是 `数据结构 / 计算机组成原理 / 操作系统 / 计算机网络`
—— 即 **408 这一门统考科目内部的四个组成部分**，而不是四门独立考试科目。

现存 FROZEN 代码同样如此解释：

```text
learning/practice/adapters/exam.py:92   LearningContext(subject_key=attempt.subject_key)   # = module
learning/practice/adapters/exam.py:145  LearningContext(subject_key=attempt.subject_key)   # = module
```

**结论**：当前数据模型只有 **一层**（module），而 product target 需要 **三层**
（track → subject → module）。这条「缺一层」是本轮架构升级的核心。

---

## 3. Current DB / Data Ownership

### 3.1 `CURRENT_EXAM_DATA_OWNERSHIP_MATRIX`

`KEEP` = 原样保留；`ADAPT` = 保留数据、加解释层；`MIGRATE` = 需要迁移数据；`DELETE-LATER` = 已死。

| domain | table | rows | identity | readers / writers | namespace 耦合 | subject 耦合 | static? | 处置 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 题库（章节） | `exam_question_bank` (source_type=`chapter`) | 9098 | PK `id`；内容哈希 upsert **保 id** | 47 路由；builder 脚本 | 无（表名即域） | `subject_key` = **module** | ✅ 全局静态（`owner_username` 全 NULL, `visibility=public`） | **KEEP** |
| 题库（真题） | `exam_question_bank` (source_type=`past_paper`) | 235 | 约定 `(subject_key, year, question_number)`，`source_ref="past_paper:{year}-Q{n}"`，**无唯一约束** | 同上 | 无 | `subject_key` = module；`year` = **question_year** | ✅ | **KEEP**（id 不稳定问题见 D6） |
| 章节练习 | `exam_practice_attempts` | 0 | PK `id`（per-session 汇总） | 写入 `POST …/chapter-practice/attempts/*`；读 `GET …/attempts/{id}` | practice adapter 用 `exam_11408` | `subject_key` = module | ❌ 用户态 | **ADAPT** |
| 真题作答 | `past_paper_attempts` | 0 | PK `id`；`year`+`attempt_no` | `POST …/past-paper-attempts/*` | 同上 | module + `year` | ❌ | **ADAPT** |
| AI 出题 | `ai_generated_questions` | 0 | PK `id` | AI 出题/作答路由 | `generation_mode` | `subject_key` = module | ❌ 用户态（也服务 course） | **ADAPT** |
| AI 作答 | `ai_question_attempts` | 0 | PK `id`；`mode` 默认 `"11408"` | 同上；**course adapter 也镜像它** | `mode="11408"` 是**裸标记** | `subject_key` | ❌ | **ADAPT** |
| 错题 v2 | `exam_wrong_questions` | 0 | `question_bank_id`（AI 行为 NULL→按 stem 匹配） | chapter/AI submit 写；`GET …/wrong-questions` 读 | `wrong_answers/legacy.py` 标 `exam_11408` | module | ❌ | **ADAPT** |
| 真题错题 | `past_paper_wrong_questions` | 0 | `question_id`（字符串，来自解析卷） | past-paper submit 写 | 同上 | module + `year` | ❌ | **ADAPT** |
| 收藏 v1 | `exam_favorite_questions` | 0 | `source_question_id` | 3 条路由 | 无 | module | ❌ | **KEEP** |
| 收藏 v2 | `exam_favorite_questions_v2` | 0 | `question_bank_id` | **0 代码引用** | 无 | module | ❌ | **DELETE-LATER**（D5） |
| 完成记录 | `exam_question_done_records` | 0 | `question_bank_id` / `ai_question_id` | `_save_done_record` ← 3 处 | 无 | module | ❌ | **ADAPT**（受 D6 影响） |
| 学习计划-设置 | `exam_study_plan_settings` | 0 | UNIQUE `(username, subject_key)` | study-plan 路由 | 无 | module | ❌ | **KEEP** |
| 学习计划-章节 | `exam_study_plan_chapter_practice` | 0 | UNIQUE `(username, subject_key, section_code)` | 同上 | 无 | module | ❌ | **KEEP** |
| 学习计划-任务 | `exam_study_plan_tasks` | 0 | PK `id` | 同上 | 无 | module | ❌ | **KEEP** |
| 真题卷导入 | `practice_papers` / `practice_import_jobs` | 0 | PK `id` | `/practice/import-paper/*` | 无 | `course_id` | ❌ | **KEEP** |
| 知识进度 | `user_knowledge_progress`（**共享**） | 0 | PK `id`；exam 用 `course_id="<module>_11408"` | exam 路由 + course canonical writer | ❌ **无 namespace 列**，靠 `_11408` 后缀 | module 编码进 `course_id` | ❌ | **ADAPT** |
| 练习/错题/事件 | `practice_sessions` / `practice_attempts` / `wrong_answer_states` / `learning_events` | 0（本地库无此 5 表） | 见 §8 | Practice / Wrong / Records Core | ✅ `service_namespace` / `service_key` | 经 context | ❌ | **ADAPT** |

**表创建路径（D7）**：

```text
有 legacy ensure_*    ：past_paper_wrong_questions, exam_favorite_questions,
                        ai_generated_questions, exam_study_plan_*   (database.py)
有 Alembic migration  ：无 —— 14 张 exam 表全部没有
仅 create_all         ：exam_question_bank, exam_practice_attempts, exam_wrong_questions,
                        exam_question_done_records, exam_favorite_questions_v2,
                        past_paper_attempts, ai_question_attempts
```

> 14 张 exam 表**没有任何 Alembic 覆盖**。这在部署链上是一个真实缺口：
> 一道只包含 `alembic upgrade` 的流水线不会创建它们，只有启动 `main.py` 才会。
> STEP7H1 不需要修它（属部署 gate），但必须登记。

---

## 4. Protected Assets

```text
PROTECTED_ASSET_MANIFEST

DB（只读引用，禁止 rewrite / 复制 / 重生成 id）
  exam_question_bank        = 9333    （chapter 9098 / past_paper 235）
  programming_exercises     = 1923
  knowledge_points          = 32      ← **属 programming-C ontology，不是 Exam 的知识点**
  study_materials           = 1
  exam_resources（目录）     = 263 文件（205 jpg / 26 json / 10 docx / 8 py / 6 txt / 6 md / 2 jpeg）
  static/exam_papers（目录） = 564 文件
  seed_data/knowledge_maps/{key}_11408.json ×4（38–48 KB）
```

**`knowledge_points` 32 行必须排除在 Exam Catalog 之外**：实测其 `course_id` ∈
`{programming_c: 8, programming_cpp: 8, programming_java: 8, programming_python: 8}`
—— 全部是编程语言课程的知识点，与 exam 无关。任何 Exam 知识树都必须来自
`seed_data/knowledge_maps/*.json` 或题库自身的 `knowledge_point_path`，**不得**读这 32 行。

**文件路径 ≠ 域身份**（§33）：`exam_resources/11408/…`、`static/exam_papers/11408/…`、
`cache/exam_papers/11408/…` 的目录名**不在本轮重命名**，也不需要重命名。canonical
namespace 是逻辑身份，storage path 是物理布局。

---

## 5. EXAM_NAMESPACE_IMPACT_MATRIX

### 5.1 首要结论：`exam_11408` 是一个**重载 token**

只读枚举（非测试代码，14 个文件，共 306 处）：

| 语义维度 | 含义 | 典型证据 | 是否要改名？ |
| --- | --- | --- | --- |
| **A. LEARNING SPACE** | 三学习空间之一；LearningContext / 事件 / Practice / Wrong | `core/learning_context.py:27`；`learning/practice/adapters/exam.py:90,143`；`learning/records/taxonomy.py:64`；`learning/practice/refs.py:36-38`；`learning/wrong_answers/legacy.py:42,57` | ✅ **改名 → `exam_prep`** |
| **B. MEMBERSHIP SERVICE KEY** | legacy 三服务会员的一档 | `membership.py:323,546` `SERVICE_PLAN_CATALOG`；`main.py:788,792,1504,1542,1610,1692-1698`；`models.py:1170`；`payments/service.py:98,124`；`database.py:2320-2332`；`user_service_memberships.service_key` | ❌ **不改名**（随会员统一而消亡，不是空间身份） |
| **C. QUOTA BUCKET KEY** | legacy 固定次数额度桶 | `main.py:2983,2984,3131-3157,19374,21456,21486`；`ai_usage_logs.service_key`；`FEATURE_TO_CORE_QUOTA_KEY` | ❌ **不改名**（随 quota 退役而消亡） |
| **D. MATERIAL DOMAIN / TRACK / ADMIN** | 资料域标签、track 映射、admin/support 分类 | `main.py:195,220,227,236,240,986,993`；`29530` 显示名 `"11408 考研"`；`30296,33432` | ⚠️ **部分**：`TRACK_SERVICE_KEY` 属 A/B 之间，需随 A 调整 |
| **E. QUOTA-AUTH ENTRY POINT** | `check_exam_408_usage_limit` 的 service 参数 | `main.py:3131-3157` | ❌ 属 C |

> **这是本设计最重要的一条**：把 306 处一律 rename 是**错**的。B/C/E 是「旧会员 + 旧额度」
> 维度，按 SSOT §28/§67 它们本就要**整体退役**，不是被改名。把它们一起改，会同时
> 扩大风险面并掩盖真正的清理目标。
>
> 需要改名的只有 **A（+ D 中真正的 track 部分）** —— 规模从 306 降到约 **40–50 处**，
> 且全部是**代码常量**，无一是存储值（存储值另见 §5.2）。

### 5.2 A 维度逐项分类

| 分类 | 位置 | 处理 |
| --- | --- | --- |
| DATABASE_STORAGE | `practice_sessions.service_namespace`、`practice_attempts.service_namespace`、`wrong_answer_states.service_namespace`、`learning_events.service_key`、`ai_requests.service_namespace`、`usage_ledger.service_namespace` | **值迁移**（仅当有行，见 §18/§31） |
| API_INPUT | `core/learning_context.py:93-96` `LEGACY_NAMESPACE_ALIASES`（`exam`/`exam-11408`/`exam_11408`/`11408`） | 保留为 **INPUT alias**，归一化到 `exam_prep` |
| ROUTE_NAME | 47 条 `/exam/11408/{subject_key}/…` | **不改**（§34：route ≠ storage identity） |
| AI_CONTEXT | `main.py` 中 `usage_service="exam_11408"` 的 4 处分支 | 随 A 改名（并修 D1） |
| PRACTICE_CONTEXT | `learning/practice/adapters/exam.py`、`refs.py:36-38` `LEGACY_SOURCE_MAP` | 随 A 改名 |
| WRONG_ANSWER_CONTEXT | `learning/wrong_answers/legacy.py:42,57`（审计登记表，非运行时） | 随 A 改名 |
| LEARNING_EVENT | `learning/records/taxonomy.py:64` `EXAM = …`（**仅 1 个常量**） | 随 A 改名 |
| MEMBERSHIP_LEGACY | B 类全部 | **不改** |
| STATIC_ASSET | `exam_resources/11408/…`、`static/exam_papers/11408/…`、`seed_data/knowledge_maps/*_11408.json`、`*_11408` scope id | **不改路径**；scope id 加 adapter |
| FILE_PATH | `exam_paper_parser.py:16-18` 三个路径常量 | 不改 |
| TEST | 10 个测试文件 | 随 A 更新断言的 namespace 值 |
| FRONTEND_LEGACY | 无（`FRONTEND_CHANGED = NO`，前端已移除） | — |
| OTHER | `learning/spaces/course_learning/knowledge.py:312-313` mutation inventory（已标 `OUT_OF_SCOPE_SPACE`） | 随 A 更新登记文本 |

---

## 6. Exam Domain Vocabulary（FROZEN）

```text
ExamTrack   用户选择的完整备考组合/方向（cs_408 / management_joint / …）
ExamSubject 实际考试科目（politics / english_1 / math_1 / cs_408 / …）
ExamModule  Subject 内部具有独立教学结构的组成部分（cs_408 → data_structure / …）
ExamQuestionSource  题源：static_question_bank / past_exam / ai_generated / material_generated
```

**三者不得合并为一个枚举**。Track 是「人怎么备考」，Subject 是「考什么科目」，
Module 是「科目内部如何组织」，QuestionSource 是「题从哪来」——四者正交。

---

## 7. ExamTrack / Subject / Module Hierarchy

### 7.1 每级是否需要独立 persisted entity？

| 层 | 结论 | 理由 |
| --- | --- | --- |
| ExamTrack | **CONFIG**（versioned module） | 是产品 taxonomy，不是事实。用户「选了哪个 track」是用户状态（一个字符串），不是一张表 |
| ExamSubject | **CONFIG** | 全国统考科目集合稳定、有官方代码；无用户写入需求 |
| ExamModule | **CONFIG** | 同上；**且现有数据已经把它存在 `subject_key` 里** |
| Chapter | **EXISTING STATIC RESOURCE** | `seed_data/knowledge_maps/*.json` 已有章节树；DB 无 chapter 列 |
| KnowledgePoint | **EXISTING STATIC RESOURCE** | 题库自带 `knowledge_point_id/name/path`（315 个不同 path）；**不得**用 `knowledge_points` 表（那是 programming-C） |

```text
NEW_SQL_TABLES_FOR_CATALOG = 0
```

> YAGNI：**没有任何一层需要新建 SQL 表**。四级 taxonomy 用 versioned config 表达，
> chapter/KP 复用已有静态资源，用户选择存成字符串。

### 7.2 目录形状（设计，不导入内容）

```text
EXAM_TRACK_CATALOG（v1，config）
  postgraduate（考试类型）
    ├ cs_408            subjects: [politics, english_1, math_1, cs_408]
    ├ management_joint  subjects: [management_aptitude, english_2]
    ├ economics_joint   subjects: [economics_joint_aptitude, politics, english_1, math_3]
    ├ law_jm_law        subjects: [politics, english_1, law_master_law_1, law_master_law_2]
    ├ law_jm_non_law    subjects: [politics, english_1, law_master_non_law_1, law_master_non_law_2]
    ├ education         subjects: [politics, english_1, education_basics]
    ├ psychology        subjects: [politics, english_1, psychology_basics]
    └ history           subjects: [politics, english_1, history_basics]

EXAM_SUBJECT_CATALOG（v1，config）
  公共课      politics / english_1 / english_2 / math_1 / math_2 / math_3
  统考专业课  cs_408 / management_aptitude / economics_joint_aptitude
              law_master_law_1|2 / law_master_non_law_1|2
              education_basics / psychology_basics / history_basics
  可扩展位    医学 / 农学 / 其他未来全国统考科目（本轮不列具体代码）

EXAM_MODULE_CATALOG（v1，config；只对已有真实数据的 subject 展开）
  cs_408 → data_structure / computer_organization / operating_system / computer_network
  math_1 → calculus / linear_algebra / probability_statistics
  math_2 → calculus / linear_algebra            （数学二不含概率统计）
  math_3 → calculus / linear_algebra / probability_statistics
  其余 subject → 本轮不展开（无数据，不编造）
```

### 7.3 Track ≠ 固定 Subject 组合（§18 强制要求）

**不得**把 `cs_408 = politics + english_1 + math_1 + 408` 写成不可配置真理。真实世界里：

- 同一 track 的公共课组合可能因院校要求、考生选择、年份政策而不同；
- 部分考生考 `english_2` / `math_2` / `math_3`，取决于学位类型与专业。

因此数据模型必须是：

```text
track.exam_type            考试类型（postgraduate / 未来其他）
track.default_subjects     建议组合（DEFAULT，非强制）
user.selected_subjects     用户实际备考科目（**覆盖 default**）
```

`selected_subjects` 是**用户状态**，`default_subjects` 是**目录建议**。二者不得互相推导。

---

## 8. LearningContext Target（FROZEN）

### 8.1 继续只有一个 canonical LearningContext

**不新建 `ExamLearningContext`**。`core/learning_context.py` 已经证明它能承载空间专属字段
（`programming_language` / `exercise_id` 就是编程空间的字段），扩展它即可。

### 8.2 目标形状

```text
core.LearningContext（扩展，仍是唯一一个）

  user_id
  service_namespace: course_learning | exam_prep | programming     ← exam_11408 不再是取值

  # 通用
  chapter_id?
  knowledge_point_id?
  material_ids?
  session_id?

  # course_learning
  course_id?
  subject_key?

  # exam_prep（新增 3 个 Optional 字段）
  exam_track_id?        cs_408 / management_joint / …
  exam_subject_id?      politics / english_1 / math_1 / cs_408 / …
  exam_module_id?       data_structure / calculus / …

  # programming
  programming_language?
  exercise_id?
```

### 8.3 每个字段的归属与去向

| 字段 | 是否进 core | 是否进 `to_event_context()` | 是否进 identity |
| --- | --- | --- | --- |
| `exam_track_id` | ✅ | ❌ **不进** | ❌ |
| `exam_subject_id` | ✅ | ✅ → `learning_events.subject_key` | ❌ |
| `exam_module_id` | ✅ | ✅ → 事件 context JSON（`knowledge_point_ref_json`） | ❌ |

**`exam_track_id` 为什么不进事件**：track 是**用户侧的备考组合选择**，不是**事实的属性**。
同一个 `cs_408` 事件，无论用户当初选的是哪个 bundle，都是同一个事实。把 track 写进事件
会造成同一事实在不同 track 下产生不同记录 —— 违反「事件是事实」的原则。track 只作为
**请求上下文**（`ai_requests.context_json`，JSON blob，免费携带）与**用户画像**存在。

**`subject_key` 的语义澄清与兼容**：

```text
course_learning: subject_key = 课程学科键（保持现状）
exam_prep:       subject_key = **experiment_subject_id 的 legacy compatibility 镜像**
                 → H2 起 canonical 字段是 exam_subject_id；
                   subject_key 继续被写为 **module**（与历史数据一致），
                   使既有 FROZEN 的 exam adapter / refs context 行为不变。
```

> 若把 exam 的 `subject_key` 直接改成 subject，会**改变 FROZEN 的 exam practice/event
> context 语义**（STEP7D 已冻结「`subject_key` = module」）。因此采用**新增字段 + 保留
> 旧字段镜像**的兼容策略，而非重新解释旧字段。

### 8.4 目标 exam LearningContext 示例

```text
LearningContext(
  user_id=42,
  service_namespace=exam_prep,
  exam_track_id="cs_408",
  exam_subject_id="cs_408",
  exam_module_id="data_structure",
  subject_key="data_structure",          # legacy mirror，兼容 FROZEN adapter
  chapter_id="1.1",
  knowledge_point_id="1.1",
  material_ids=["7"], session_id=None,
)
```

---

## 9. 11408 Compatibility Mapping

```text
CS408_MAPPING（adapter 层解释，不改数据）

  exam_track_id   = cs_408        （唯一存在的 track，隐式）
  exam_subject_id = cs_408        （408 是**一门**统考科目）
  exam_module_id  = subject_key   （data_structure / computer_organization /
                                   operating_system / computer_network）
  exam_type       = postgraduate
```

**证据依据**：

1. `exam_question_bank` 只有一层 `subject_key`，其 4 个取值正是 408 的四部分（§2.3）。
2. FROZEN 的 `learning/practice/adapters/exam.py` 已经把 `attempt.subject_key` 当作
   module 放进 `LearningContext.subject_key` 与 `QuestionRef.context`。
3. `EXAM_408_SUBJECT_KEYS` / `EXAM_SUBJECT_DIRS` 是**校验闸门**而非层级定义。
4. 题库 `knowledge_point_id`（如 `"1.1"`）与 `knowledge_point_path`
   （如 `"3.1 栈"`）是 module 内部层级，证明 module 之上还有一层（= subject）。

**legacy scope id 的解释（不改存储）**：

```text
user_knowledge_progress.course_id = "<module>_11408"
study_materials.course_id         = "<module>_11408"
seed_data/knowledge_maps/<module>_11408.json
```

→ H1 引入纯函数 `parse_legacy_exam_scope_id()` / `build_exam_scope_id()`，
把 `data_structure_11408` ↔ `cs_408:data_structure` 双向映射。**存储值不改**。

---

## 10. 9333 Question Bank Disposition

```text
QUESTION_BANK_9333_DISPOSITION = NO PHYSICAL MIGRATION

QUESTION_IDENTITY_UNCHANGED   = YES
QUESTION_CONTENT_UNCHANGED    = YES
QUESTION_COUNT_UNCHANGED      = 9333
```

**结论：现有 `subject_key` 已足够表达 module，无需 rewrite 任何一行。**

| 维度 | 现状 | 目标解释 |
| --- | --- | --- |
| track | 隐式（只有 11408） | `cs_408`（config 常量） |
| subject | **缺失** | `cs_408`（config 常量） |
| module | `subject_key` | `exam_module_id = subject_key` |
| 题源 | `source_type` ∈ {chapter, past_paper} | `static_question_bank` / `past_exam`（§19 FROZEN 源类型） |
| question_year | `year`（235 行 2022–2026；章节行为 NULL） | **question_year**，与 `target_exam_year` 严格分离 |
| 章内层级 | `knowledge_point_id/name/path`（315 个 path） | 复用，不迁表 |

**未来新科目（math_1 / politics / …）的题库如何加入**：新增 `subject_key` 取值 +
一个 `exam_subject_id` 映射。**不建新表、不改既有行**。若某天 module 与 subject 的关系需要
多对多（例如 `linear_algebra` 同时属于 math_1/2/3），那是 **config 内部的 module 复用**，
仍然不是数据库关系。

> `linear_algebra` 的跨 subject 复用见 §16（Shared Knowledge Content）。

---

## 11. Practice / Wrong / Records Target

```text
PRACTICE_TARGET      = 继续使用 Unified Practice Core（不创建 ExamPracticeCore）
WRONG_ANSWER_TARGET  = 继续使用 Unified Wrong Answer Core
RECORDS_TARGET       = 继续使用 learning_events + STEP7F records read model
```

### 11.1 Practice

现成链路（STEP7D 已接，FROZEN 不变）：

```text
exam_practice_attempts  → mirror_exam_practice_attempt  → PracticeSession + PracticeAttempt
past_paper_attempts     → mirror_past_paper_attempt     → PracticeSession + PracticeAttempt
```

H2 只做 **namespace / context 层的对齐**，不动镜像语义：

- `service_namespace`：`exam_11408` → `exam_prep`
- `LearningContext` 增加 `exam_track_id/subject_id/module_id`
- `subject_key` 保持写 module（兼容）
- `QuestionRef.context` 增加 `exam_subject_id`（用于 records/wrong 的 subject 过滤）

题源类型（SSOT §19 冻结集）保持不变：
`static_question_bank` / `past_exam` / `AI_generated` / `material_generated`。

### 11.2 Wrong Answers — identity 建议

现状（STEP7E FROZEN）：

```text
UniqueConstraint(user_id, service_namespace, question_source_type, source_id?, scope_key)
scope_key: past_exam → "year:<year>"；course_learning → "course:<course_id>"；其余 ""
```

**建议：不要把 track 塞进 identity。** 理由：

- track 是用户侧选择，把它放进 identity 会让同一道题在换 track 后变成两道错题；
- subject/module 已由 `source_id` + `QuestionRef.context` 决定（题库 id 全局唯一）；
- 真题已用 `year:<year>` 处理跨年份同号问题，这个判别力已经足够。

identity 只增加**一处**：`scope_key` 对 `exam_prep` 的 `past_exam` 保持 `year:<year>`
（与今天一致，因为 §9 已把 subject 固化为 cs_408，`year` 仍足以消歧）。
若未来出现「同一 year + 同一 question_number 出现在两门不同统考科目」，
再引入 `subject:` 前缀 —— **本轮不预加**（YAGNI，且无数据支持）。

### 11.3 Records

```text
所有 exam 新事实继续进 learning_events
service_key = exam_prep
context:
  subject_key        = exam_subject_id（cs_408 / math_1 / …）
  exam_module_id     = module（进 knowledge_point_ref_json 的 JSON）
  chapter_id / knowledge_point_id = 现状
  course_id          = 不用于 exam（exam 无 course 概念）
Free user 同样写真实学习事实（与 course 一致）
```

**不恢复独立 exam learning record architecture**（SSOT §67）。

---

## 12. EXAM_AI_REACHABILITY_MATRIX

按**当前磁盘事实**重算（`main.py` + `exam_paper_parser.py` + `qwen_parser.py`）。

| # | endpoint | helper / 位置 | provider 调用 | semantic task | legacy auth | target capability | 结构化输出 | 现状 context / 持久化 | 迁移难度 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `POST /exam/11408/{k}/ai-questions/generate` (21357) | `generate_exam_ai_questions` → `call_deepseek` 21444 | DeepSeek | **(c) 生成题目 JSON** | ❌ 无 gate，仅事后 `record_ai_usage` | `question.generate` | ✅ 严格 JSON（`_validate_exam_ai_choice_payload`） | `ai_usage_logs`；无 `ai_requests` | 中（非选择题走 mock 分支） |
| 2 | `POST /exam/11408/{k}/past-paper-attempts/{id}/submit` (19737) | `grade_submission` → `_grade_big_question` → **自带 `OpenAI(...)`** (`exam_paper_parser.py:466-486`) | DeepSeek（独立 client） | **(a) 用户作答评分** | ❌ **完全无 gate** | ⚠️ **CAPABILITY_GAP**（见 §24） | `{score, feedback}` | **无任何记录**（D3） | 高 |
| 3 | `GET /exam/11408/{k}/past-paper-questions` (19563) 等 3 处 | `get_year_questions` → `_ocr_year_questions` → `qwen_parser.parse_image_with_qwen` | Qwen-VL-OCR | **(f) 真题卷 OCR 抽取** | ❌ 无 | **PARSER_OCR（不进 orchestrator）** | 结构化 OCR JSON | 无记录（D8） | 不迁移（infra） |
| 4 | `POST /chat`（exam 分支） (8509) | `chat` → `call_deepseek` 8780 | DeepSeek | (a) 辅导问答 | ✅ `check_exam_408_usage_limit` 8759 | `tutor.chat` / `material.qa` | ❌ 自由文本 | `ai_usage_logs` | 低 |
| 5 | `POST /chat/upload`（exam 分支） (8835) | `handle_material_upload` → `call_deepseek` 5387 | DeepSeek (+Qwen OCR) | (a) 资料问答 | 无（走 course/upload 路径） | `material.qa` | ❌ | `ai_usage_logs` 5388 | 低 |
| 6 | `POST /practice/import-paper/jobs` (23862) + `/parse` (23964)（exam 分支） | `structure_practice_paper_text` → `call_deepseek` 23651 | DeepSeek | **(f) 试卷结构化抽取** | ✅ 23636 | `knowledge.structure`（或 `question.generate`，见下） | ✅ JSON | `ai_usage_logs` | 中 |
| 7 | `POST /practice/questions/generate`（exam 分支，精修） (25107) | `refine_question_analysis_with_ai` → `call_deepseek` 24875 | DeepSeek | (b) 解析净化 | ✅ 25185（endpoint 级） | `question.explain` | ❌ 文本 | **无记录** | 低 |
| 8 | `POST /learning/plans/generate-preview`（exam 分支） (26681) | `_generate_plan_preview_core` → `call_deepseek` 26597 | DeepSeek | **(d) 计划生成** | ✅ 26590 | `planning.generate` | ✅ JSON | `ai_usage_logs` 26598 | 中 |
| 9 | 同上（JSON 修复） | `_parse_plan_json` → `_repair_json_with_ai` → `call_deepseek` 26110 | DeepSeek | (g) JSON 修复 | 无（上游已 gate） | `planning.generate` | ✅ JSON | `ai_usage_logs`（`json_repair`） | 低 |
| 10 | `POST /exam/11408/{k}/question-analysis` (21575) | `AIOrchestrator().execute(...)` 21606 | via Gateway | (b) 题目解析 | ❌ 无 | `question.explain` | ❌ | ✅ 统一表，但 **`learning_context=None` → namespace NULL**（D2） | **低（已迁移 90%）** |
| 11 | `POST /practice/questions/generate`（exam 分支，主生成） (25107) | `_course_ai_content` 25209 | via Gateway | (c) 生成题目 | ✅ 25185 | `question.generate` | ✅ JSON | ⚠️ **写成 course_learning**（D1） | 低（改 context） |
| 12 | `POST /practice/generate-task-preview`（exam） (25429) / `POST /learning/reports/generate-preview`（exam）(31337) / `POST /learning-report/ai-generate`（exam）(16664) | `_course_ai_content` 25491 / 31398 / 16775 | via Gateway | (c) / (e) 报告 | ✅ `check_exam_408_usage_limit` / `require_learning_context_feature` | `question.generate` / `report.generate` | ✅ / ❌ | ⚠️ **写成 course_learning**（D1） | 低（改 context） |

```text
EXAM_DIRECT_PROVIDER_CALLS = 9（#1–#9；其中 #3 属 PARSER_OCR 保留）
EXAM_AI_MIGRATION_TARGET   = AIOrchestrator（除 #3 OCR）
```

### 12.1 D1 —— 跨空间污染（**本轮最重要的缺陷**）

`#11 / #12` 四条路径在 **exam 请求**下会：

```text
usage_service = "exam_11408"        ← 分支判断正确（legacy 日志对）
      ↓ 但 AI 调用
_course_ai_content(db, user, cap, msgs, course_id=<exam 的 course_id>)
      ↓ 内部
build_course_context(...)           ← service_namespace 硬编码 COURSE_LEARNING
      ↓
ai_requests.service_namespace = "course_learning"     ← ❌ 错
ai_called 事件 service_key    = "course_learning"     ← ❌ 错
learning_events.course_id     = "11408 数据结构"       ← ❌ 把 exam 域当成 course 存
```

**后果**：exam 的真实学习事实被登记为 course_learning 事实，破坏
`CROSS_NAMESPACE_ISOLATION`，并污染 records/AI 归因。**必须在 H2 修复**
（修法：`_course_ai_content` 增加显式 `learning_context` 参数，由调用方按分支构造；
或在 STEP7H1 引入 `execute_exam_ai` 并让 exam 分支走它）。

### 12.2 D2 —— 唯一已迁移的 exam 端点丢了 context

`question-analysis`（21575）已走 Orchestrator，但**未传 `learning_context`**：

```text
ai_requests.service_namespace = NULL
ai_requests.context_json      = NULL
```

即 STEP7G-C2 对 course 建立的 `AI_REQUEST_CONTEXT_PERSISTENCE` gate，
在 exam 的这一个端点上**尚未成立**。修法成本极低（补一个 `build_exam_context(...)`）。

### 12.3 D3 —— `_grade_big_question`：无授权、无计费、且结果常被丢弃

三件事叠加：

1. **无 gate**：不走 `check_exam_408_usage_limit`，也不走 capability permission；
2. **无记录**：不写 `ai_usage_logs`，不写 `ai_requests`/`usage_ledger`，无 `ai_called`；
3. **结果被丢弃**：`grade_submission` 的产物在 `main.py:19759-19820` 若命中题库行会被覆盖 ——
   **AI 调用已经发生并产生真实成本，但反馈没被使用**（付费调用被浪费）。

`#2` 的判定依据（回答 §26 的 A/B/C 问题）：

```text
输入  = (question, user_answer, standard_answer, subject_key) —— 来自**用户提交的作答**
输出  = (score, feedback) → results[].feedback + wrong_questions[].wrong_reason
落库  = PastPaperAttempt.result_json / PastPaperWrongQuestion / ExamQuestionDoneRecord
        (main.py:19829 / 19835-19847 / 19858)

→ 判定 = **(A) 用户学习作答评分**（不是 B 导入解析，也不是 C 后台内容生产）
```

但**它住在**一个以 (B) 为主的模块里（`exam_paper_parser.py`：`parse_docx_questions`、
`get_subject_past_papers`、`_ocr_year_questions`、`get_year_questions` 全是导入管线，
且**不写 DB**）。因此：

**建议**：把 (A) 的评分调用**从 parser 模块迁出**，成为一个学习侧 AI 边界
（H3 引入 `execute_exam_ai` 后由它承担）；`exam_paper_parser.py` 收敛为纯
parser/OCR infra（(B) 职责），保留 OCR 走 infra，不再持有 LLM 评分 client。

---

## 13. AI Capability Reuse & Gaps

```text
复用（不新增空间专属 capability）：
  tutor.chat / material.qa / question.explain / question.generate
  planning.generate / report.generate / knowledge.structure

禁止新增：exam.chat / exam.question.generate / 408.explain
```

| 场景 | 目标 capability | 判定 |
| --- | --- | --- |
| #1 生成 408 选择题 JSON | `question.generate` | 直接复用 |
| #4 exam 辅导问答 | `tutor.chat` | 直接复用 |
| #5 exam 资料问答 | `material.qa` | 直接复用 |
| #6 试卷结构化抽取 | `knowledge.structure` **或** `question.generate` | ⚠️ 见下 |
| #7 解析净化 | `question.explain` | 直接复用（与 course 一致） |
| #8/#9 计划生成 / JSON 修复 | `planning.generate` | 直接复用（与 course 一致） |
| #10 题目解析 | `question.explain` | 直接复用 |
| #11/#12 生成/报告 | `question.generate` / `report.generate` | 直接复用 |
| **#2 大题 AI 评分** | **无同构 capability** | ⚠️ **CAPABILITY_GAP** |

```text
CAPABILITY_GAPS = 1

  G1  #2 answer grading（对用户作答按参考答案给分 + 反馈）
      与 question.explain 不同构：explain 解释「这道题」，grade 评估「这个作答」，
      产出是 score + feedback（判分），不是解析。
      目标候选：answer.grade（或 question.grade）
      本轮**不新增**（§25）。H3 开始前需用户决策：
        (a) 批准最小新 capability `answer.grade`（需同时给 tier 映射 + pool 继承规则）
        (b) 接受 `question.explain` 作为临时 proxy（类比 STRUCTURED_GENERATION_PROXY_V1）
```

**#6 的歧义**：`structure_practice_paper_text` 是「从文档抽取结构化题目」——
与 course 的 `knowledge.structure` 代理同构（结构化抽取），但产出是**题目**而非知识点树。
建议 H3 时按 **`question.generate`** 归类（产出是题），并在报告中说明选择理由；
若后续与 course 的试卷导入统一，则应两处一致。

---

## 14. EXAM_LEGACY_AUTH_MATRIX

| 授权入口 | 位置 | 作用域 | 行为 | 是否在 AI 执行路径 | 目标处置 |
| --- | --- | --- | --- | --- | --- |
| `check_exam_408_usage_limit` | `main.py:3127` | exam | **403/429 抛出**（core → `resolve_effective_quota`；非 core → `check_usage_limit`） | ✅ #4 8759、#6 23636、#7 25185、#8 26590、#12 31345 | **H3 移除**（AI 路径），随 unified budget |
| `require_feature_entitlement(…,"exam_11408","learning_plan")` | `main.py:1581` | exam study-plan | 403 `FEATURE_REQUIRES_UPGRADE` | ❌ 10 处全是 study-plan **非 AI** CRUD | **H 后续**（会员统一时退役） |
| `require_learning_context_feature(…,"learning_report",…)` | `main.py:1598` | exam/course 报告 | 403 | ✅ #12 31344、`/learning-report/ai-generate` 16672 | **H3 移除**（AI 路径） |
| `check_usage_limit(…,"exam_11408")` | `main.py:3020` | exam 非 core 回落 | 429 | ✅ 经 `check_exam_408_usage_limit` | 同 #1 |
| `record_ai_usage(…, service_key="exam_11408")` | `main.py:3173` | exam | **只记录**，吞异常 | ✅ 多处 | **H3 收敛**（成功事实归 unified，失败簿记保留或删除） |
| `get_exam_408_permissions_for_user` / `get_exam_408_feature_limit` / `resolve_effective_quota` / `get_today_usage` | 3108/3115/`membership.py:463`/2957 | exam | 只读 helper | — | 随上述退役 |

```text
EXAM_LEGACY_AUTH_OWNER（当前）= check_exam_408_usage_limit + require_learning_context_feature
EXAM_LEGACY_AUTH_OWNER（H3 目标）= 0
```

---

## 15. Standardized Exam Scope（FROZEN）

```text
STANDARDIZED_EXAM_SCOPE = 全国统一命题 / 全国统考型研究生招生考试科目
INSTITUTION_SPECIFIC_EXAMS = OUT_OF_SCOPE
```

架构至少能表达：

```text
公共基础  政治 / 英语一 / 英语二 / 数学一 / 数学二 / 数学三
理工重点  计算机学科专业基础 408
热门统考  管理类综合能力 / 经济类综合能力 / 法律硕士(法学) / 法律硕士(非法学)
          教育学专业基础 / 心理学专业基础 / 历史学专业基础
可扩展位  医学统一命题 / 农学统一命题 / 其他未来全国统一命题科目
```

本轮**不导入任何真实内容**：不建知识点、不抓数据、不生成题目、不编造 408 数据。

### 15.1 明确禁止的模型与字段

```text
FORBIDDEN（不得成为 target，即使 legacy 已存在）：
  institution_id / school_id / college / major_code
  institution_exam_code / school_exam_code
  institution_exam_plan / school_specific_subject
  institution_reference_book / institution_syllabus
```

**legacy inventory（只登记，不升级）**：

| legacy 位置 | 内容 | 处置 |
| --- | --- | --- |
| `GET /exam-408/schools` (1402) + `EXAM_408_SCHOOLS` 硬编码校名表 | 院校库 | **冻结，不再扩展**；不进入新 IA |
| `PUT /exam-408/target-school` (1412) | 目标院校 → `user_learning_tracks.onboarding_detail_json` | 冻结 |
| `models.py:32` `User.school` | 学校字段 | 保留（账户资料用），**不接入 Exam Prep** |
| `PUT /exam-408/motto` / `/exam-408/exam-info` (1435/1460) | 口号 / 考试时间 / 阶段 | 冻结（与院校无关，但属旧 track 配置） |
| `PUT /me/tracks/exam_408/package` (1497) | 旧 track 套餐 | 冻结（会员维度） |

---

## 16. Course STEM Catalog Relationship —— design only

只做 **catalog 架构**，不导入真实课程内容，不改 STEP7G 已冻结的 Course runtime 语义。

```text
COURSE_LEARNING_SCOPE = STEM-oriented Course Learning

Foundation
  Mathematics      Calculus/Higher Mathematics · Linear Algebra ·
                   Probability & Statistics · Discrete Mathematics · Numerical Methods
  Natural Science  University Physics · Basic Chemistry
  Computing        Programming Fundamentals · Computing Fundamentals

Discipline groups
  Computer Science · Software Engineering · Artificial Intelligence ·
  Electronic Information · Electrical Engineering · Automation/Control ·
  Mechanical Engineering · Civil Engineering · Materials ·
  Chemical Engineering · Mathematics · Statistics
```

**现状**：`subjects.py` 有两个并存的名字系统 ——

```text
COURSE_OPTIONS / SUBJECT_ALIASES   （legacy，13 个中文名，含「数据结构与算法」等历史名）
COURSE_LEARNING_ID_MAP             （17 个 displayName → 英文 course_id）
```

H 后续把 catalog 收敛为 **单一 versioned config**（display + id + 学科组 + 前置关系），
`SUBJECT_ALIASES` 降为纯 **INPUT alias**（与 namespace 的处理方式一致）。
**本轮不实现**，只冻结方向。

---

## 17. Shared Subject / Knowledge Catalog

### 17.1 要解决的真实关系

```text
Course Learning → Linear Algebra                      （一门课）
Exam Prep → Math I  → Linear Algebra                  （数学一的一个 module）
Exam Prep → Math II → Linear Algebra                  （数学二的 module）
Exam Prep → Math III → Linear Algebra                 （数学三的 module）
```

同一份**知识内容**被多个域、多个 subject 引用。

### 17.2 三个选项

```text
OPTION A — 建 SubjectCatalog + KnowledgeCatalog 两张 SQL 表
  表：subject_catalog / knowledge_catalog / knowledge_relations / domain_subject_link …
  优点：查询强、可后台运营、关系显式
  缺点：为「还没有内容」的域先建 3–5 张表；需要 migration + 后台写入面；
        当前 9333 题库 / 4 份知识脉络 JSON 已能工作，新建表立刻产生「两套真相」问题
  判定：**不推荐**（违反 YAGNI，且与「不要为了 Catalog 创建大量 SQL 表」冲突）

OPTION B — 纯 versioned config（Python 模块）+ 域内映射
  形态：EXAM_TRACK_CATALOG / EXAM_SUBJECT_CATALOG / EXAM_MODULE_CATALOG /
        COURSE_CATALOG，全部是代码内 versioned dict，带 CATALOG_VERSION
  知识内容关系：用 **module/subject 常量**表达（shared module key），不建关系表
  优点：零 migration、零新表、可 diff / 可 review / 随代码版本化；
        与现有 ai/pool.py、usage/capabilities.py 的 CONFIG-not-TABLE 原则一致
  缺点：运营改目录需要发版；跨域查询靠代码而非 SQL
  判定：**推荐（MVP）**

OPTION C — config 为主 + 一张轻量 domain-tag 映射表（只存「共享」这一事实）
  形态：config 表达层级；仅当某 module 被多个 subject 共享时，
        用一行记录表达共享关系（`shared_knowledge_node(node_key, owner_domains[])`）
  优点：把「共享」这一**事实**落库，便于未来查询/运营
  缺点：仍需要 migration；而当前**没有任何共享数据**需要表达（数学题库尚未导入）
  判定：**暂不推荐**；当且仅当 H4 真的引入跨 subject 复用的数学内容时再评估
```

### 17.3 推荐 + 原则

```text
SHARED_KNOWLEDGE_STRATEGY = OPTION B（config 表达层级与共享 module key，零新表）

KNOWLEDGE CONTENT MAY BE SHARED
LEARNING STATE MUST NOT BE SHARED AUTOMATICALLY
```

「共享」在 MVP 里表达为 **同一个 module key 常量被多个 subject 的 config 引用**
（例如 `LINEAR_ALGEBRA = "linear_algebra"` 同时出现在 `math_1.modules` / `math_2.modules` /
`math_3.modules` / `course.linear_algebra`）。数据库里**不因此产生任何共享行**。

**学习状态绝不自动共享**（§15 强制）：

```text
practice / wrong_answers / review / records / exam_progress / plan
  → 全部按 service_namespace + subject/module 独立维护
  → Course 的 Linear Algebra 掌握 ≠ Exam Math I 的 Linear Algebra 掌握
  → 未来可作为 evidence/reference；本轮**不做**任何 StudentTwin 跨空间推断
```

---

## 18. Namespace Migration Options

### OPTION A — 保持 canonical `exam_11408`，其他考试另想办法

| 维度 | 评估 |
| --- | --- |
| data migration risk | 无 |
| API compatibility | 完美 |
| event identity | 不变 |
| Practice / Wrong identity | 不变 |
| AI context | 不变 |
| 未来多 track | ❌ **差**：要么 `exam_11408` 被复用成一个语义谎言（数学考生也写 11408），要么为每个考试开新 namespace → 直接违反 SSOT §67「三套 AI / 三套余额」被换成「N 套考试空间」 |
| 测试影响 | 无 |
| 前端影响 | 无 |
| 长期债 | ❌ **高**：正是用户要求消除的「机械延续旧名」 |

### OPTION B — canonical 改 `exam_prep`，`exam_11408` 降为 input alias ⭐

| 维度 | 评估 |
| --- | --- |
| data migration risk | **可测量、可为零**：需要改写的只有 6 张表的 namespace **值**（本地全为 0 行）；identity 另见下 |
| API compatibility | ✅ 保留全部 47+5 条 legacy route；`exam_11408` 仍是合法输入 |
| event identity | ✅ `learning_events.event_id = uuid5(source_type, source_attempt_id, item_key)` —— **不含 namespace**（`data_plane/identity.py:29-31`），**改名不改变事件身份** |
| Practice identity | ⚠️ `session_uid`/`attempt_uid` = `uuid5(NS, f"…|{service_namespace}|…")` —— **含 namespace**（`learning/practice/identity.py:40-53`）。改名会改变 uid → replay 会造出第二条逻辑 attempt |
| Wrong identity | ⚠️ `UniqueConstraint(user_id, service_namespace, …)` 含 namespace → 改名会让同一错题在重放时重复建行 |
| AI context | ✅ 纯改进（顺带修 D1/D2） |
| 未来多 track | ✅ **最佳**：一个空间承载所有全国统考；track/subject 是 context，不是 namespace |
| 测试影响 | 10 个测试文件断言 `exam_11408` → 随改 |
| 前端影响 | 无（前端已移除） |
| 长期债 | ✅ 最低 |

**identity 风险的解法（关键设计决定）**：

```text
IDENTITY_NAMESPACE_TOKEN（冻结契约）

  确定性身份函数不再直接接收「当前 namespace 字符串」，而是接收
  一个 **冻结的 identity token**：

    IDENTITY_TOKEN_BY_NAMESPACE = {
      "course_learning": "course_learning",
      "exam_prep":       "exam_11408",   ← 冻结：使用历史 token，永不改变
      "programming":     "programming",
    }

  效果：canonical namespace 可以是 exam_prep（存储/API/AI/事件都写它），
        而 uuid5 输入仍是 exam_11408 → **已有 attempt/session/wrong 身份完全不变**，
        重放不会产生第二条逻辑事实。

  代价：uid 不再是 namespace 的字面函数（已在 docstring 中说明）。
  收益：namespace 从此可以安全演进，而不牺牲历史身份。
```

> **前置测量（H1 必须执行）**：若目标库 exam canonical 行数 = 0（本地实测 = 0），
> 则 identity token 可直接设为 `exam_prep`，**不需要**冻结 token 这层间接。
> 若 > 0，则必须启用冻结 token。
> 这是**测量决定**，不是假设决定。

### OPTION C — DB 保留 `exam_11408`，逻辑层虚拟 `exam_prep`

| 维度 | 评估 |
| --- | --- |
| data migration risk | 无 |
| API compatibility | 无 |
| event identity | 不变 |
| Practice / Wrong identity | 不变 |
| AI context | 需在两处维护「逻辑名 vs 存储名」映射 |
| 未来多 track | ⚠️ 中：新考试写什么？写 `exam_11408`（谎言）还是 `exam_prep`（两套存储值并存，破坏隔离） |
| 测试影响 | 中（每个断言都要区分逻辑名/存储名） |
| 长期债 | ❌ 中高：**存储与产品语义长期不一致**，且必然在某次查询里被忘记 |

### 18.1 推荐

```text
NAMESPACE_MIGRATION_OPTION = OPTION B
```

理由（基于代码事实，非偏好）：

1. **事件身份不含 namespace**（`data_plane/identity.py:29-31`）→ 唯一真正敏感的是
   practice/wrong identity，而它有明确的**冻结 token** 解法，成本 1 个常量。
2. **本地 exam canonical 行 = 0**，且 5 张统一表在真实库中根本不存在（当前 head 只到 legacy）
   → 迁移面可为零。
3. **B 是唯一能承载多 track 且不产生 namespace 爆炸的方案**；A/C 都会在「第二门考试」
   到来时被迫做同样的决定，而那时数据只会更多。
4. B 顺带覆盖 D1/D2 —— 因为 D1 的根因正是「没有 exam 侧的统一 AI 边界」。

---

## 19. Recommended Architecture（FROZEN）

```text
Learning Space（service_namespace）
  course_learning | exam_prep | programming          ← exam_11408 不再是取值
  legacy input alias: exam / exam_408 / exam_11408 / 11408 → exam_prep（归一化一次）

Exam Prep 域层级（全部 CONFIG，零新表）
  ExamTrack   → ExamSubject → ExamModule → Chapter → KnowledgePoint
   Config       Config        Config       static JSON  题库列/静态 JSON

用户态
  exam_profile: exam_type / selected_track / selected_subjects[] / target_exam_year?
                 （selected_subjects 可覆盖 track.default_subjects）

AI
  Endpoint → authenticated user → canonical LearningContext(exam_prep, track/subject/module)
           → AIOrchestrator → Capability Permission → Router → Estimate → Reserve
           → Gateway → Actual Usage → Settle → domain postprocess
  例外（不进 orchestrator）：OCR（qwen_parser）= PARSER_OCR infra

Practice / Wrong / Records / Events
  全部复用共享 Core；namespace = exam_prep；
  subject_key = exam_subject_id（事件列）；module 进事件 context JSON；
  track **不进** 事件、**不进** identity

题源（SSOT §19 冻结集，不变）
  static_question_bank / past_exam / AI_generated / material_generated

Storage
  exam_question_bank 9333 行**零改动**；目录路径保持 11408 命名；
  scope id 用纯函数双向映射；14 张 exam 表保持 legacy 名
```

### 19.1 Target Year 与 Question Year（§20）

```text
TWO DISTINCT SEMANTICS — 禁止共用一个字段

question_year  = 题目/真题本身的年份
                 现状：exam_question_bank.year（235 真题行 2022–2026；章节行为 NULL）
                 位置：题库数据（已有，不改）

target_exam_year = 用户计划参加考试的年份
                 位置：exam_profile.target_exam_year（用户态）
                 用途：计划/报告的时间语境、大纲版本对齐
                 本轮只设计，**不做任何预测**
```

`target_exam_year` **不进** LearningContext 的必需字段，也不进任何 identity；
需要时由计划/报告用例显式读取用户画像。

### 19.2 User Exam Profile（§19）

```text
exam_profile（用户态；H1 只设计，落点见 §20）
  exam_type            postgraduate（未来可加其他统考类型）
  selected_track       cs_408 / management_joint / …
  selected_subjects    [politics, english_1, math_1, cs_408]   ← 可覆盖 track default
  target_exam_year?    2027

明确不含（即使 legacy 有）：target_school / institution major / school exam code
```

onboarding 流程目标：

```text
选择考研 → 选择方向(track) → 选择实际备考统考科目(subjects) → 进入统一 Exam Prep
```

---

## 20. Migration Strategy

### 20.1 H1 是否需要 schema change？

```text
SCHEMA_CHANGE_REQUIRED_FOR_H1 = NONE
NEW_TABLES_PROPOSED_FOR_H1    = NONE
```

不需要新增 `exam_track_id` / `exam_subject_id` / `exam_module_id` **列**，理由：

| 需求 | 承载方式 | 证据 |
| --- | --- | --- |
| track | `ai_requests.context_json`（JSON）+ 用户画像 | LearningContext 扩展字段，JSON 免费 |
| subject | `learning_events.subject_key`（**已有列**） | column 已存在且语义合适 |
| module | 事件 context JSON（`knowledge_point_ref_json`）+ `QuestionRef.context` | JSON，无 migration |
| scope id | 纯函数双向映射 `<module>_11408` ↔ `cs_408:<module>` | 不新增列 |
| 用户选择 | `exam_profile`（见 20.2） | 不是新的领域表 |

### 20.2 `exam_profile` 的落点（最小方案）

**不新建 `exam_profiles` 表**。复用已有的用户画像载体（`user_learning_tracks`）或
`learning_context` 的通用用户画像读取路径，把 exam 选择存为 JSON 字段。
若 H1 实测发现 `user_learning_tracks` 不适合承载，再评估一张单表 —— **不预先建**。

### 20.3 namespace 值迁移（仅在需要时）

```text
H1 PRE-FLIGHT（必须，先测量再决定）：
  for table, col in ((practice_sessions, service_namespace),
                     (practice_attempts, service_namespace),
                     (wrong_answer_states, service_namespace),
                     (learning_events, service_key),
                     (ai_requests, service_namespace),
                     (usage_ledger, service_namespace)):
      count rows where col in ('exam_11408','exam','exam_408','11408')

  IF 全部为 0  → 无需迁移；identity token 直接用 exam_prep
  ELSE         → alembic DATA-ONLY 迁移（无 DDL）：
                   UPDATE <t> SET <col>='exam_prep' WHERE <col> IN (…)
                 且 identity token **冻结为 exam_11408**
```

典型 alembic 形态（H1 落地时）：

```python
# data-only, no DDL; additive-only 原则不受影响（不新增/删除任何列或表）
def upgrade():
    for table, col in TABLES:
        op.execute(f"UPDATE {table} SET {col} = 'exam_prep' "
                   f"WHERE {col} IN ('exam_11408','exam','exam_408','11408')")
```

（若真实库根本没有这些表，则迁移为空操作且不得失败 —— 迁移必须对「表不存在」幂等。）

---

## 21. STEP7H Implementation Decomposition

```text
STEP7H0  Exam Prep domain / identity freeze                        ← 本轮（设计）
         产出：本文件；无代码变更

STEP7H1  canonical namespace + context compatibility foundation
         · core.LearningContext 扩展 exam_track_id/subject_id/module_id
         · ServiceNamespace: EXAM_PREP = "exam_prep"；legacy 别名归一化
         · 冻结 identity token（按 §20.3 pre-flight 结果二选一）
         · 修 D1（4 端点跨空间污染）+ D2（question-analysis context）
         · 修 D4（重复路由）
         · 验收：namespace 等价测试 + identity 不变测试 + 全量回归 0 failed
         · NEW_TABLES = 0；SCHEMA = 0（除非 pre-flight 要求 data-only 迁移）

STEP7H2  11408 / CS408 → unified Exam Practice / Wrong / Records
         · exam adapter 接 exam_prep；QuestionRef.context 增 exam_subject_id
         · records 事件 context 对齐（subject_key=subject，module 进 JSON）
         · wrong scope_key 保持 year:<year>
         · 验收：exam practice → wrong ACTIVE → correct → RESOLVED → records
                 + CROSS_NAMESPACE_ISOLATION（exam 不被 course/programming 命中）

STEP7H3  Exam AI → Unified AIOrchestrator
         · 引入 learning/spaces/exam_prep/ai.py:execute_exam_ai()
         · 迁移 §12 的 #1 #4 #5 #6 #7 #8 #9 #10 #11 #12（除 #3 OCR）
         · 移除 exam AI 路径上的 legacy auth（EXAM_LEGACY_AUTH_OWNER → 0）
         · 先决：G1（answer grading capability）需用户决策
         · 验收：tier matrix / budget 拒绝且 provider 调用=0 / 直连调用=0
                 (可复用 STEP7G 的 reachability gate 模式)

STEP7H4  Multi-track / multi-subject catalog foundation
         · EXAM_TRACK_CATALOG / EXAM_SUBJECT_CATALOG / EXAM_MODULE_CATALOG（config）
         · exam_profile onboarding（选 type → track → subjects）
         · 按需导入第一个非 408 科目（**需用户明确批准**）
         · 验收：catalog 完整性 + 多 track 隔离 + 无数据串线

STEP7H5  CS408 full acceptance
         · 端到端：onboarding → 章节练习 → 真题 → 错题 → 计划 → 记录 → 报告
         · 冻结 STEP7H；STEP7I（programming）准备
```

依赖与调整说明：

- H1 必须在 H2 之前（H2 的 context 依赖 H1 的字段）。
- H3 与 H2 无强依赖，可并行；但 H3 的 D1 修复与 H1 重叠，故 D1 放 H1。
- H4 依赖用户对「导入哪门新科目」的明确决策 —— 不得自行导入。
- **一阶段一验收，禁止 big-bang**。

---

## 22. Risks / Blockers

| # | 风险 | 等级 | 缓解 |
| --- | --- | --- | --- |
| R1 | **D1 跨空间污染**：exam 事实被写成 course_learning | 🔴 高 | H1 必修；修前不得宣称 exam namespace 已收敛 |
| R2 | practice/wrong identity 含 namespace，改名破坏去重 | 🔴 高 | §20.3 pre-flight + 冻结 identity token |
| R3 | 14 张 exam 表无 Alembic 覆盖 | 🟠 中 | H1 登记；部署 gate 前补 baseline migration（不属 H1） |
| R4 | D3 `_grade_big_question` 无授权/无计费/结果被丢弃 | 🟠 中 | H3 迁移 + 去掉无效覆盖路径 |
| R5 | D6 真题 builder 整表重写 → question id 变化 → done/wrong 引用失效 | 🟠 中 | H2 设计：真题 identity 改用 `(subject_key, year, question_number)` 作为稳定引用，而非自增 id |
| R6 | G1 answer-grading capability 缺失 | 🟡 低 | H3 前用户决策 |
| R7 | 生产库行数未知（本地 = 0） | 🟡 低 | H1 pre-flight 必须**测量**而非假设 |
| R8 | `data_structure` 等同名 token 跨域（course id vs exam module） | 🟠 中 | H1 的三层 context 正是解法；测试需覆盖同名不串线 |
| R9 | OCR 全程不计费/不记录（D8） | 🟡 低 | 登记；由 Parser Infra 的独立成本核算处理，不混入 AI 账本 |
| R10 | `user_knowledge_progress` 用 `_11408` 后缀与 course **共用一张表**，无 namespace 列 | 🟠 中 | H2 评估：或加 nullable `service_namespace`，或继续用 scope id 派生；**不预先决定** |

**Blockers for H1**：无（H1 可在 D1/D2/D4 修复后独立验收）。

---

## 23. Frozen Decisions

```text
FD-1  Exam Prep 只支持全国统一命题/全国统考型研究生招生考试科目；
      院校自命题、院校 code、院校大纲、院校参考书 = OUT OF SCOPE。
      不建立 institution_id/school_id/school_exam_code/institution_exam_plan/
      school_specific_subject 任何模型（legacy 只做 inventory）。

FD-2  新一级业务概念 Exam Prep；11408 降级为
      Exam Prep → Computer Science → CS 408 track。

FD-3  ExamTrack / ExamSubject / ExamModule 三者分离，不得合并为一个枚举；
      不得预设 track ≡ 单一固定 subject 组合。

FD-4  Track / Subject / Module / Chapter / KnowledgePoint **全部不新建 SQL 表**：
      前三级 = versioned CONFIG；Chapter/KnowledgePoint = 已有静态资源
      （seed_data/knowledge_maps/*.json + 题库自带 knowledge_point_*）。

FD-5  canonical service_namespace = exam_prep；
      legacy exam / exam_408 / exam_11408 / 11408 = **INPUT alias**，
      在 core.learning_context.normalize_service_namespace 归一化一次。
      `exam_11408` 作为 **legacy 会员/额度 service_key** 的用法**不改名**，
      随会员统一而退役（它从来不是空间身份）。

FD-6  继续只有 **一个** canonical LearningContext；
      扩展 exam_track_id / exam_subject_id / exam_module_id；
      不新建 ExamLearningContext。

FD-7  exam_track_id **不进** learning_events、**不进** 任何 identity；
      exam_subject_id → 事件 subject_key 列；
      exam_module_id → 事件 context JSON。

FD-8  exam 的 `subject_key` 继续镜像 module（兼容 FROZEN 的 STEP7D adapter），
      canonical 字段是新字段；不重新解释旧字段语义。

FD-9  exam_question_bank 9333 行 **零改动**：
      不迁移、不复制、不重生成 id、不改 subject_key 取值。
      CS408 mapping 在 adapter/config 层解释。

FD-10 Question Year 与 Target Exam Year 严格分离，不得共用一个字段。

FD-11 知识内容可共享（同一 module key 被多个 subject 引用），
      但**学习状态绝不自动共享**；不做任何 StudentTwin 跨空间推断。

FD-12 Shared catalog strategy = OPTION B（config，零新表）；
      不建 SubjectCatalog / KnowledgeCatalog SQL 表。

FD-13 AI capability 复用现有 7 个；不新增空间专属 capability；
      G1（answer grading）登记为 CAPABILITY_GAP，H3 前由用户决策。

FD-14 OCR（qwen_parser）属 PARSER_OCR infra，**不进入** AIOrchestrator。
      `exam_paper_parser._grade_big_question` 判定为 (A) 用户作答评分，
      H3 从 parser 模块迁出；parser 模块收敛为纯导入/OCR infra。

FD-15 路由不变：47 条 `/exam/11408/*` + 5 条 legacy 路由**全部保留**；
      未来可增 `/exam/...`，本轮不删不改名。

FD-16 静态资产路径不变：`exam_resources/11408/…`、`static/exam_papers/11408/…`、
      `seed_data/knowledge_maps/*_11408.json` 保持命名；
      scope id `*_11408` 用纯函数双向映射。

FD-17 namespace 迁移 = OPTION B；执行前必须 **测量** 目标库 exam canonical 行数；
      非零时启用冻结 identity token（uuid5 输入保持 exam_11408）。

FD-18 H1 的 NEW_TABLES = 0、SCHEMA_CHANGE = 0（除测量要求的 data-only 迁移）。

FD-19 Free 用户在 Exam Prep 中同样产生真实学习事实（与 course 一致）。

FD-20 本轮不导入任何真实考试内容；不抓取、不生成、不编造。
```

---

## 24. 已发现缺陷清单（供 H1/H2/H3 消化）

```text
D1  🔴 4 端点跨空间污染（exam 请求 → course_learning 统一账本/事件）  → H1
D2  🟠 question-analysis 未传 LearningContext → namespace NULL        → H1
D3  🟠 _grade_big_question：无 gate / 无计费 / 结果被丢弃             → H3
D4  🟡 GET /exam/11408/study-plan/tasks/summary 重复注册（死 handler）→ H1
D5  🟡 exam_favorite_questions_v2 死表（0 行 / 0 代码引用）           → DELETE-LATER
D6  🟠 真题 builder 整表 DELETE+INSERT → question id 漂移            → H2
D7  🟠 14 张 exam 表无 Alembic 覆盖                                   → 部署 gate
D8  🟡 OCR 全路径不计费/不记录                                        → Parser Infra
```

---

## 25. 本轮不做的事（明确边界）

```text
NO implementation / NO migration / NO frontend / NO STEP7I
NO production deployment / NO real DB mutation / NO live provider calls / NO secrets
NO content import（不建知识点、不抓考研网站、不导入数学/法硕题、不生成虚假真题、不造教材）
NO new capability（G1 只登记）
NO route rename / NO static asset rename
NO new SQL tables for the catalog
```

**FRONTEND_CHANGED = NO**。未来 IA 建议（仅建议，不写代码）：

```text
考研备考
├─ 我的备考        （track / subjects / target_year / 倒计时）
├─ 公共课          （政治 / 英语 / 数学）
├─ 专业统考        （408 / 管综 / 法硕 / 教育 / 心理 / 历史 …）
├─ 真题
├─ 练习
├─ 错题
├─ 计划
└─ 学习记录
```

---

## 26. Git / DB Safety（本轮）

```text
HEAD = ebad5282（未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree

数据库：
  真实 backend/app.db **未被审计代码触碰**（未 import main、未建连接、未迁移）
  审计方式 = 复制到 %TEMP%/step7h0/audit.db 后用 sqlite3 只读查询
  audit.db: integrity_check = ok；72 表；exam_question_bank = 9333
  REAL_APP_DB_MIGRATED = NO
```
