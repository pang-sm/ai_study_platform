# STEP7H_FRONTEND_API_HANDOFF

> 智学AI · Exam Prep / CS408 前端对接契约
> 状态：**FROZEN**（STEP7H5 冻结）· 生成 2026-09-17
> 读者：前端实现方。本文件是 Exam Prep 前端的**唯一契约来源**，无需阅读 `backend/main.py`。
>
> 约束：本文件只描述**已经存在且被验收**的接口。任何未列出的能力都不存在，不得假设。

---

## A. Product IA（信息架构）

```text
Exam Prep
├─ 我的备考          profile：方向 + 科目 + 目标年份
├─ 科目              catalog：全部科目及其 availability
├─ CS408             ACTIVE，唯一有真实内容的科目
│   ├─ 知识脉络      study-plan / knowledge-items
│   ├─ 章节练习      chapter-practice
│   ├─ 真题          past-papers
│   ├─ 错题          wrong-questions
│   ├─ 计划          study-plan（tasks / settings）
│   └─ 学习记录      done-records / dashboard-summary / practice-stats
└─（其他科目）        FRAMEWORK_ONLY：可显示、可选择、**不可进入内容**
```

**首页第一性问题**：每个页面先回答「我在哪 / 学到哪 / 下一步做什么」，不是功能入口集合。

---

## B. ACTIVE vs FRAMEWORK_ONLY

| 科目 | availability | 有内容？ | 可选择？ |
| --- | --- | --- | --- |
| `cs_408` | `active` | 是（题目 / 真题 / 知识脉络） | 是 |
| 其余 13 个 | `framework_only` | **否** | 是（保存目标） |

FRAMEWORK_ONLY 科目（全部 13 个）：

```text
politics, english_1, english_2, math_1, math_2, math_3,
management_aptitude, economics_joint_aptitude,
law_master_law, law_master_non_law,
education_basics, psychology_basics, history_basics
```

判定可用性**只能**读接口返回的 `availability` / `has_questions` / `has_past_papers` /
`has_knowledge_tree`，**不得**在客户端硬编码科目名单，也**不得**用「列表为空」推断未上线。

---

## C. Canonical endpoints（新前端应使用）

全部前缀 `/exam/prep`。认证：**Session Cookie `ai_session`**（与全站一致）。
错误体：`{ "detail": <string 或 object> }`。

### C1. `GET /exam/prep/catalog`

```jsonc
{
  "catalog_version": "v2",
  "exam_type": "postgraduate",
  "tracks":   [ { "id", "display_name", "exam_type", "availability",
                  "has_content", "description",
                  "subject_options": [...], "suggested_subjects": [...] } ],
  "subjects": [ { "id", "display_name", "category", "availability",
                  "has_questions", "has_past_papers", "has_knowledge_tree",
                  "description", "suggested_tracks": [...],
                  "modules": [ { "id", "display_name" } ] } ],
  "active_subject_ids": ["cs_408"],
  "framework_only_subject_ids": [ /* 13 个 */ ]
}
```

- `category`：`public`（公共课）/ `professional`（专业统考）。
- `modules` **仅** ACTIVE 科目非空。
- `suggested_subjects` 对除 `cs_408` 外的 track 为空是**有意为之**，不是缺数据。

### C2. `GET /exam/prep/catalog/tracks` · `GET /exam/prep/catalog/subjects`

同上的两个子集，附 `catalog_version`。

### C3. `GET /exam/prep/subjects/{subject_id}/content-status`

```jsonc
// 200 — ACTIVE
{ "subject_id": "cs_408", "availability": "active",
  "has_questions": true, "has_past_papers": true, "has_knowledge_tree": true,
  "modules": [ { "id": "data_structure", "display_name": "数据结构" } ] }
```

```jsonc
// 409 — FRAMEWORK_ONLY
{ "detail": { "code": "EXAM_CONTENT_NOT_AVAILABLE",
              "subject_id": "math_1", "availability": "framework_only",
              "message": "该科目已开放选择，但内容尚未上线。" } }
```

- 未知科目 → **404**。
- 这是「现在能不能学这门」的**唯一诚实答案**。见 §F。

### C4. `GET /exam/prep/profile`

未配置时（不是错误）：

```jsonc
{ "configured": false, "exam_type": "postgraduate",
  "selected_track": null, "selected_subjects": [], "target_exam_year": null,
  "subjects": [] }
```

已配置时 `configured: true`，且 `subjects[]` 是所选科目的完整 catalog 对象（含
`availability` / capability 标志），前端**无需**再查一次 catalog 才能渲染选择结果。

### C5. `PUT /exam/prep/profile`

请求：

```jsonc
{ "selected_track": "cs_408",          // nullable，必须是合法 catalog track id
  "selected_subjects": ["cs_408"],     // 合法 subject id 列表，自动去重
  "target_exam_year": 2027 }           // nullable，目标考试年份
```

响应：同 C4 的已配置形态。

---

## D. CS408 内容接口（既有 `/exam/11408/*`，**本轮不动**）

新前端的 CS408 页面**继续使用这些既有接口**。它们未改名、未迁移，且被 STEP7H5 验收覆盖。
`{k}` = module id（见 §H）。

```text
GET    /exam/11408/subjects/{k}/dashboard-summary      概览 + 今日计划
GET    /exam/11408/subjects/{k}/study-plan             学习计划（需 learning_plan 权益）
PATCH  /exam/11408/subjects/{k}/study-plan/settings    计划设置
PATCH  /exam/11408/subjects/{k}/study-plan/knowledge-items/{code}
PATCH  /exam/11408/subjects/{k}/study-plan/chapter-practice/{node}
GET    /exam/11408/study-plan/summary
GET    /exam/11408/study-plan/tasks/summary
POST   /exam/11408/subjects/{k}/study-plan/tasks
PATCH  /exam/11408/subjects/{k}/study-plan/tasks/{task_id}
DELETE /exam/11408/subjects/{k}/study-plan/tasks/{task_id}
GET    /exam/11408/{k}/chapter-practice/outline
GET    /exam/11408/{k}/chapter-practice/questions
POST   /exam/11408/{k}/chapter-practice/attempts
GET    /exam/11408/{k}/chapter-practice/attempts/{attempt_id}
POST   /exam/11408/{k}/chapter-practice/attempts/{attempt_id}/answers
POST   /exam/11408/{k}/chapter-practice/attempts/{attempt_id}/submit
GET    /exam/11408/{k}/past-papers
GET    /exam/11408/{k}/past-paper-questions
POST   /exam/11408/{k}/past-paper-attempts
GET    /exam/11408/{k}/past-paper-attempts/{attempt_id}
POST   /exam/11408/{k}/past-paper-attempts/{attempt_id}/answers
POST   /exam/11408/{k}/past-paper-attempts/{attempt_id}/submit
GET    /exam/11408/{k}/wrong-questions
PATCH  /exam/11408/{k}/wrong-questions/{wrong_id}/mastered
DELETE /exam/11408/{k}/wrong-questions/{wrong_id}
GET    /exam/11408/{k}/done-records
GET    /exam/11408/{k}/favorites          POST 同路径      DELETE /favorites/{id}
GET    /exam/11408/{k}/question-bank/stats
GET    /exam/11408/{k}/question-bank/questions
GET    /exam/11408/{k}/practice/stats
GET    /exam/11408/{k}/ai-questions
POST   /exam/11408/{k}/ai-questions/generate
PATCH  /exam/11408/{k}/ai-questions/{question_id}
DELETE /exam/11408/{k}/ai-questions/{question_id}
GET    /exam/11408/{k}/ai-questions/{question_id}/raw-response
POST   /exam/11408/{k}/question-analysis
```

**不要**把 `/exam/11408/*` 当作「旧接口」而另建一套；它就是 CS408 的内容面。

---

## E. Content status contract（前端必须实现的分支）

```text
availability == "active"          → 渲染模块与内容入口
availability == "framework_only"  → 渲染为「已开放选择，内容尚未上线」
                                     不得渲染任何题目 / 真题 / 知识脉络占位
```

判定依据**只有**接口字段。三种错误状态必须分开处理：404（不存在）/ 409（未上线）/
200（可用）。

---

## F. 前端必须正确处理的状态

错误体统一是 `{ "detail": ... }`。**`detail` 有两种形态**，必须都处理：

**① 结构化 refusal（既有权益接口，如 study-plan）**

```jsonc
{ "detail": { "code": "FEATURE_REQUIRES_UPGRADE", "feature": "learning_plan",
              "service_key": "exam_11408", "current_plan": "free",
              "required_plan": "monthly_sprint" } }
```

**② 纯字符串（AI 能力边界）** —— 状态码本身承载语义：

```jsonc
{ "detail": "AI capability unavailable" }
```

| 情况 | 状态 | 前端动作 |
| --- | --- | --- |
| 未登录 | `401` | 引导登录 |
| framework-only 内容访问 | `409` + `detail.code == "EXAM_CONTENT_NOT_AVAILABLE"` | 显示「内容尚未上线」，**不重试**、不降级、不伪造占位 |
| AI 能力超出当前档位 | `403` | 显示升级引导（`detail` 为字符串） |
| 既有权益不足 | `403` + `detail.code == "FEATURE_REQUIRES_UPGRADE"` | 显示升级引导（用 `detail.feature` 定位） |
| AI 额度 / 预算耗尽 | `429` | 显示「本次额度已用完」，**不是**网络错误、**不重试** |
| AI 技术性不可用 | `502` | 可重试 / 提示稍后再试 |
| 资源不存在 | `404` | 空状态 |
| 未知科目 | `404`（`/exam/prep/subjects/{id}/content-status`） | 返回科目列表 |
| profile 参数非法 | `400` | 表单校验错误 |

**禁止**：把 403/429 当作可重试错误；把 409 当作空数据；把 `detail` 假定为对象或字符串
以外的形态。

> 注：`409` 与 AI 的 `403/429` 是**产品答案**，不是故障。任何把拒绝降级成 fallback 内容
> 的行为都是错的。

---

## G. Profile 契约

```text
exam_type          固定 "postgraduate"（全国统考型研究生招生考试）
selected_track     合法 catalog track id 或 null
selected_subjects  合法 subject id 数组（可含 framework_only）
target_exam_year   用户**目标**考试年份（nullable）
```

- 每用户**一个**当前 profile。
- **Free 用户也可以保存 profile** —— profile 不是会员权益。
- 非法 track / subject id → `400`（fail closed）。
- `target_exam_year` 是**目标年份**，与真题的题目年份（`question_year`）**不是一个概念**，
  不要共用一个字段或组件状态。

**不要**向用户索取或展示：院校 / 学院 / 专业代码 / 院校自命题科目代码 / 参考书目 / 院校大纲。
这些在本产品中**不存在**。

---

## H. CS408 module ID 与显示名（FROZEN）

| module id | 显示名 |
| --- | --- |
| `data_structure` | 数据结构 |
| `computer_organization` | 计算机组成原理 |
| `operating_system` | 操作系统 |
| `computer_network` | 计算机网络 |

科目显示名：`cs_408` → **计算机学科专业基础 408**。

---

## I. 明确禁止的 UI 假设

1. **不得**为非 408 科目显示任何形式的假进度 / 假掌握度。
2. **不得**为非 408 科目显示假知识点、假章节、假真题。
3. **不得**默认所有 408 考生都考同一套公共课组合（目录不猜，用户选什么就是什么）。
4. **不得**提供院校自命题入口（院校 / 学院 / 专业代码 / 参考书目 / 院校大纲）。
5. **不得**在前端暴露 provider / model registry（模型名、供应商、价格表）。
6. **不得**恢复旧三服务会员体系（`course_ai` / `exam_ai` / `programming_ai`）。
7. **不得**用「列表为空」推断功能未上线 —— 只读 `availability`。
8. **不得**在客户端硬编码科目清单；从 catalog 取。
9. **不得**假设 `suggested_subjects` 有值。
10. **不得**把 `target_exam_year` 与真题年份混用。

---

## J. 会员体验（只描述用户可见行为）

Exam Prep 内的 AI 能力对用户按下表呈现。**前端不要内置能力名单**：以接口返回的
`403` + `code` 为准，把「哪些能力在哪个档位可用」交给后端。

| 档位 | 用户可见的 AI 能力（学习侧） |
| --- | --- |
| Free | 答疑 / 题目解析 / 资料问答 |
| Standard | 以上 + 出题、学习计划生成、问答题评分 |
| Advanced | 以上 + 学习报告生成 |

Free 用户的**非 AI** 学习闭环（备考 → 科目 → 章节练习 → 真题 → 错题 → 记录）
必须完整可用；AI 拒绝**不得**影响任何事实写入。

---

## K. 不在本契约内（前端不要依赖）

- 任何 FRAMEWORK_ONLY 科目的内容接口（**不存在**）。
- 任何「AI 推荐 / 预计掌握率 / 智能学习路径」类字段（**未产品化**）。
- provider / 模型 / 计价信息。
- 管理端与运维接口。
