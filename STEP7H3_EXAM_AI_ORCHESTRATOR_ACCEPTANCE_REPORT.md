# STEP7H3_EXAM_AI_ORCHESTRATOR_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7H3 验收报告
> 范围：Exam AI → Unified AI Orchestrator（含 STEP7H2-C1 并发收尾）
> 生成：2026-09-17 · 本轮为 **IMPLEMENTATION**（有代码变更，未 commit / 未 push）

---

## 1. Git / DB Safety

```text
HEAD = ebad5282（未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

所有模块加载（import main / TestClient / pytest / route introspection）均在显式
`DATABASE_URL=sqlite:///<temp>` 下执行；真实 `backend/app.db` 只用只读 sqlite3 访问。

```text
REAL_APP_DB_MUTATED = NO
```

---

## 2. H2-C1 Closure

`STEP7H2_EXAM_PRACTICE_WRONG_RECORDS_ACCEPTANCE_REPORT.md` §22–§26 记录了完整收尾
（原 §19.1 的 flaky 记录保留未删）。

```text
WRONG_CONCURRENCY_ROOT_CAUSE = VERIFIED · 两层
  ① 产品侧：投影的「读事实集合 → 写状态行」不原子。一个 pass 的读可能早于另一条
     attempt 的提交，而它恰好最后写入 → 状态停在 1（实测 178/200 轮出现混合读集，
     1/200 轮真的违反）。
  ② 测试侧：worker 线程读取 fixture session 上**已过期的 User 属性**（`u.id`），
     触发跨线程 lazy refresh → ObjectDeletedError → 该轮 attempt 根本没落库。
     旧断言顺序先查 wrong_count 后查 errors，把它误报成「stale projection」。

修复（产品侧，保留 FROZEN 语义）
  · `recompute()` 改为 compare-and-recompute：每个 pass 读 → 写（applied）→ 用
    **独立新 session** 校验事实集合指纹未变，否则重做（上限 5 次）。
  · 并发首插竞态不再「返回胜者的行」：applied=False 强制重做（行走 UPDATE）。

修复（测试侧）
  · worker 在**测试线程**上先取出 `uid`，不再跨线程触碰 fixture 的 ORM 对象。

STRESS（每批 50 轮/次 × N 次）
  修复前：5/40 runs 失败     修复后：0/30 runs（1500 轮）· 0/40（2000 轮）
```

```text
WRONG_CONCURRENT_DISTINCT_FACTS = PASS
WRONG_REPLAY_IDEMPOTENT          = PASS
WRONG_CONCURRENCY_STRESS         = PASS
STEP7H2                          = FROZEN（恢复）
```

---

## 3. EXAM_AI_REACHABILITY_MATRIX（H3 B1，从当前磁盘重算）

从 route → helper → secondary helper → provider/gateway 的完整可达性（含模块限定调用、
`background_tasks.add_task` 函数引用、跨模块 `exam_paper_parser`）。

| # | endpoint | 分类 | 迁移前 AI 执行 | 迁移后 |
| --- | --- | --- | --- | --- |
| 1 | `POST /chat`（exam 分支） | shared-branch | `call_deepseek` | `_scoped_ai_content` → exam_prep |
| 2 | `POST /chat/upload`（exam 分支） | shared-branch | `call_deepseek` | `_scoped_ai_content` → exam_prep |
| 3 | `POST /exam/11408/{k}/ai-questions/generate` | native | `call_deepseek` | `_exam_ai_content`（`question.generate`） |
| 4 | `POST /exam/11408/{k}/question-analysis` | native | 已 orchestrated（H1 补齐 context） | `execute_exam_ai` |
| 5 | `POST /exam/11408/{k}/past-paper-attempts/{id}/submit` | native | `exam_paper_parser._grade_big_question`（自带 OpenAI client） | `execute_exam_ai`（`answer.grade`） |
| 6 | `GET /exam/11408/{k}/past-paper-questions` 等 2 条 | native | `get_year_questions` → **OCR** | **不变（PARSER_OCR）** |
| 7 | `POST /practice/import-paper/jobs` / `parse`（exam 分支） | shared-branch | `call_deepseek` | `_scoped_ai_content`（`question.generate`）+ OCR infra |
| 8 | `POST /practice/questions/generate`（exam 分支，主生成） | shared-branch | `_course_ai_content`（H1 已修 D1） | 不变 |
| 9 | `POST /practice/questions/generate`（exam 分支，条件精修） | shared-branch | `call_deepseek` | `_scoped_ai_content`（`question.explain`） |
| 10 | `POST /practice/questions/{id}/ai-explain`（条件精修） | shared-branch | `call_deepseek` | `_scoped_ai_content`（`question.explain`） |
| 11 | `POST /learning/plans/generate-preview` / `-advanced`（exam 分支） | shared-branch | `call_deepseek` | `_scoped_ai_content`（`planning.generate`） |
| 12 | 同上的 JSON 修复重试 | shared-branch | `call_deepseek` | `_scoped_ai_content`（`planning.generate`） |
| 13 | `POST /learning/reports/generate-preview` / `POST /learning-report/ai-generate` | shared-branch | `_course_ai_content`（H1 已修 D1） | 不变 |

```text
EXAM_AI_ENDPOINT_COUNT              = 24
  （native /exam* 4 + shared endpoints with an exam branch 20）
EXAM_DIRECT_PROVIDER_CALLSITE_COUNT（迁移前，main.py + parser）= 8
   handle_material_upload / chat / generate_exam_ai_questions /
   structure_practice_paper_text / refine_question_analysis_with_ai /
   _repair_json_with_ai / _generate_plan_preview_core /
   exam_paper_parser._grade_big_question
EXAM_SECONDARY_PROVIDER_CALLSITE_COUNT = 2（条件精修 + JSON 修复重试，均已 orchestrated）
EXAM_ORCHESTRATED_CALLSITE_COUNT       = 全部（见下）
PARSER_OCR_CALLSITE_COUNT              = 2（exam_paper_parser._run_ocr_for_question →
                                          qwen_parser.parse_image_with_qwen；1 个 provider 客户端）
```

```text
EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0
EXAM_DIRECT_PROVIDER_CALLS_FINAL     = 0
```

> 计数口径：endpoint 数（24）≠ provider invocation callsite 数（8 → 0）≠ OCR callsite 数（2，保留）。
> `_repair_json_with_ai` / `refine_question_analysis_with_ai` / `structure_practice_paper_text`
> 仍**保留** `call_deepseek`，但只在 **非 course / 非 exam** 的 legacy 分支上（无 db/user 上下文或
> 其他 service_key）。这不构成 exam 可达的直连调用。

---

## 4. CAPABILITY MAPPING（B4）

| 语义 | capability |
| --- | --- |
| exam 辅导对话 | `tutor.chat` |
| grounded 材料问答 | `material.qa` |
| 题目解析 / 解析净化（含条件精修） | `question.explain` |
| 题目生成 / 试卷结构化抽取 | `question.generate` |
| 计划生成 / 计划 JSON 修复 | `planning.generate` |
| 报告生成 | `report.generate` |
| 主观题评分 | `answer.grade` |

**未新增**任何空间专属 capability（无 `exam.chat` / `408.explain` / `exam.question.generate` /
`exam.grade`）。试卷结构化用的是 `question.generate` 而非 `knowledge.structure` —— 产物是
**题目**，不是知识图谱。

---

## 5. execute_exam_ai 边界

```text
Endpoint → authenticated user → canonical Exam LearningContext → execute_exam_ai()
         → AIOrchestrator → Capability Permission → Router → Estimate → Reserve
         → Gateway → actual usage → Settlement → domain postprocess
```

拒绝语义（B13，统一且不互相吞并）：

```text
permission_denied / tier_not_permitted      → 403
budget_reserve_failed / budget_incompatible → 429
no_qualified_model_available                → 502
reconciliation_pending                      → 502
provider 失败（release）                     → 502（可由端点自身的业务 fallback 接住）
```

`_is_exam_ai_scope()` 让**两种拼写**都能路由到 exam 边界（canonical `exam_prep` 与 legacy
方向标记如 `operating_system_11408`），否则持有 canonical 名的调用方会掉到 course 边界。

---

## 6. answer.grade

```text
ANSWER_GRADE_MIGRATED = PASS
tier: Free DENIED / Standard ALLOWED / Advanced ALLOWED
pool proxy: QUESTION_EXPLAIN_PROXY_V1（POOL_VERSION 仍 v4，未新开 benchmark）
```

结构化输出校验（B6）：必须能解析出 JSON 对象、`score` 必须是整数且落在 `0..10`；
否则抛 `GradeOutputError`（postprocessing failure）。**已产生的 measured usage 照常 settle**，
不做全额 refund（测试断言 `ai_cost_records` 计数为 1 且 status=settled）。

---

## 7. _grade_big_question 迁移（B5 / D3 关闭）

```text
exam_paper_parser.py 现在：文档解析 / 题目抽取 / OCR infra —— 零 provider 客户端、零模型名
```

- `_grade_big_question` **已删除**（连同其 `OpenAI(...)` 客户端与 `DEEPSEEK_API_KEY` 读取）。
- `grade_submission(..., grade_big=...)` 由调用方**注入**评分器；未注入时使用
  `_ungraded_big_answer()`（纯关键词重叠启发式，明确标注为「AI暂不可用,基础评分」），
  因此 parser 模块**任何路径都不触达 provider**（测试固化）。
- 评分器由 `main._paper_big_answer_grader(db, user, subject_key, attempt, grade_state)`
  构造，落在 Exam 学习 AI 边界（`learning/spaces/exam_prep/ai.py::grade_big_answer`）。

---

## 8. 确定性 vs AI 评分（B5.2）

**旧行为**：`grade_submission`（内含 AI 评分）**无条件**先跑；随后若题库有该科目年份的
active 行，`result` 被确定性结果整块覆盖 → **AI 调用已付费，结果被丢弃**。

**新行为**：先查题库。

```text
IF 题库有 active 行  → 确定性评分（DETERMINISTIC_GRADE_PATH_PROVIDER_CALLS = 0）
ELSE                 → 注入 AI 评分器（AI_GRADE_PATH_PROVIDER_CALLS = 1，结果被真实使用）
```

响应新增 `answer_grade: {applied, reason}`（加法式）：确定性路径报告
`reason="deterministic_bank_grading"`。

```text
DETERMINISTIC_GRADE_PROVIDER_CALLS = 0（测试：bank 命中的提交 → provider 调用 0、AIRequest 0）
AI_GRADE_PROVIDER_CALLS            = 1
AI_GRADE_RESULT_USED               = YES（测试断言返回体里的 score/feedback 就是模型给的那份）
```

**FACT FIRST（B5.1）**：learner 的提交是 durable fact。AI 评分被拒（403/429）或失败时，
端点**不抛错**、不丢提交：`PastPaperAttempt` 仍以确定性暂定分落库并置 `submitted`，
`answer_grade.reason` 说明原因（测试：Free 用户提交后 attempt 仍为 `submitted`，
且 provider 调用 = 0）。canonical PracticeAttempt mirror 仍只发生一次（AI 分数定型之后）。

---

## 9. Legacy Auth Cutover（B7）

从 exam **AI 执行路径**移除的 legacy 授权：

| 位置 | 移除 |
| --- | --- |
| `POST /chat` exam 分支 | `check_exam_408_usage_limit(...,"chat")` |
| `handle_material_upload` exam 分支 | （随分支迁移） |
| `structure_practice_paper_text` exam 分支 | `check_exam_408_usage_limit(...,"question_generate")` |
| `POST /practice/questions/generate` exam 分支 | 同上 |
| `POST /practice/generate-task-preview` exam 分支 | 同上 |
| `POST /learning/plans/generate-preview` exam 分支 | `check_exam_408_usage_limit(...,"learning_plan_generate")` |
| `POST /learning/reports/generate-preview` exam 分支 | `require_learning_context_feature` + `check_exam_408_usage_limit` |
| `POST /learning-report/ai-generate` exam 分支 | `require_learning_context_feature` |

```text
EXAM_AI_LEGACY_AUTH_OWNER = 0（源码中已无 check_exam_408_usage_limit 的任何调用点）
UNIFIED_CAPABILITY_AUTH   = PASS
UNIFIED_USAGE_BUDGET      = PASS
```

**保留**（不属于 H3）：非 AI 的 legacy study-plan CRUD entitlement、legacy 会员/额度 service_key
（随统一会员退役，不做机械重命名）。

---

## 10. Legacy Usage Cutover（B8）

- `generate_exam_ai_questions` 的**成功率 legacy 记账已删除** —— 同一次 provider invocation
  的计费事实只有 `usage_ledger` + `ai_cost_records` 一套。
- exam 分支的 `record_ai_usage(..., service_key="exam_11408")` 成功行已全部移除。
- 失败行（失败簿记）保留在非 course/exam 的 legacy 路径上。

```text
EXAM_AI_BILLING_DOUBLE_COUNT = NO
```

---

## 11. Secondary Invocations（B9）

条件精修与 JSON 修复重试都是**真实 provider invocation**：

```text
refine_question_analysis_with_ai → _scoped_ai_content(question.explain)
_repair_json_with_ai             → _scoped_ai_content(planning.generate)
```

触发条件**原样保留**（condition false → 1 次调用；condition true → 2 次调用）。
第二次同样有 AIRequest / reserve / settle / cost record / ai_called，不隐藏为 free postprocess。

```text
EXAM_AI_EVENT_DUPLICATION = NO（每次 invocation 一套事实）
```

---

## 12. Error Semantics（B13）

403 / 429 一律**不进入 fallback**：

- `generate_exam_ai_questions`：`except HTTPException` 中 403/429 直接 `raise`，
  只有技术性 5xx 才走该端点固有的 mock fallback。
- `_paper_big_answer_grader`：403/429 不抛给提交请求，而是**跳过 AI 评分**并回报原因
  （提交事实优先，且这意味着 provider 未被调用，不存在绕过授权）。
- 其余 exam AI 端点不做静默降级（与 course 一致的 `except HTTPException: raise` 先行）。

---

## 13. Settlement（B14）

沿用 STEP7C 冻结语义，未改动 orchestrator：provider 拒绝且无用量 → release；实测用量 →
settle actual；postprocessing 失败 → **settle 已发生**（成本保留）；可能已发出但用量未知 →
reconciliation_pending。`answer.grade` 的 malformed-output 测试断言了第 3 条。

---

## 14. Tier Matrix（B15）

`tests/test_exam_ai_orchestrator.py`，FakeProvider + 真实 Orchestrator lifecycle：

```text
FREE     tutor.chat ✓ / material.qa ✓ / question.explain ✓
         question.generate ✗403 / planning.generate ✗403 / report.generate ✗403 / answer.grade ✗403
         （拒绝路径断言 provider 调用 = 0 且不产生 AIRequest）
STANDARD question.generate ✓ / planning.generate ✓ / answer.grade ✓ / report.generate ✗403
ADVANCED report.generate ✓ / answer.grade ✓
BUDGET   budget 耗尽 → 429，provider 调用 = 0
```

---

## 15. Context / Event Equivalence（B3）

```text
AIRequest.service_namespace       = exam_prep
AIRequest.context_json            = canonical LearningContext
  exam_track_id = cs_408 / exam_subject_id = cs_408 / exam_module_id = <module>
  subject_key = <module>（legacy mirror）
UsageLedger.service_namespace     = exam_prep（reserve/settle 全行）
ai_called.service_key             = exam_prep
ai_called.subject_key             = cs_408
ai_called domain context          = 含 exam_module_id
```

```text
EXAM_AI_CONTEXT_PERSISTENCE          = PASS
EXAM_AI_EVENT_CONTEXT_EQUIVALENCE    = PASS
EXAM_USAGE_LEDGER_NAMESPACE_EQUIVALENCE = PASS
```

---

## 16. Parser / OCR Separation（B20）

```text
qwen_parser（视觉 OCR）        → PARSER_OCR infra，保留自有 vision client，不进 orchestrator
exam_paper_parser._run_ocr_for_question → 调 qwen_parser（OCR step = infra）
exam_paper_parser.grade_submission      → 不再持有 provider（LLM step 已移交边界）
```

```text
PARSER_OCR_CLASSIFICATION            = PASS
PARSER_OCR_MIGRATED_TO_ORCHESTRATOR  = NO（EXPECTED = NO）
D8（OCR billing/observability）= 本轮不解决，继续登记
```

---

## 17. Cross-Space Isolation（B19）

`POST /knowledge-points/generate-preview` 用两个 scope 各调一次：

```text
course_id="data_structure_11408" + course_name="11408 数据结构" → AIRequest.service_namespace = exam_prep
course_id="data_structure"       + course_name="数据结构"        → AIRequest.service_namespace = course_learning
```

两次 request_id 不同、命名空间不同。同名 token（`data_structure`）在两个空间下分别是
course_id 与 exam_module_id，**不串线**。

```text
COURSE_EXAM_NAMESPACE_ISOLATION = PASS
```

---

## 18. Tests

```text
新增 tests/test_exam_ai_orchestrator.py（26）：tier 矩阵（含 budget）、answer.grade 校验与
  越界/非 JSON 输出、context 等价、parser 无 provider 客户端、grade_submission 默认路径无 provider、
  确定性评分 0 调用 / AI 评分 1 调用且结果被使用、Free 用户提交在评分被拒时仍 durable、
  exam 端点可达边界、无 legacy quota gate、OCR 留在 infra、cross-space。

tests/test_wrong_answers.py 并发三件套强化（50 轮 stress + replay + wrong/wrong/correct）。

对齐更新：test_course_ai_reachability（直连清单：exam 分支全部迁出）、
  test_exam_prep_namespace（H1 的「grading 未动」断言更新为 H3 已迁移）、
  test_gateway_migration（边界改为 _scoped_ai_content）。
```

```text
FULL_BACKEND_TESTS = PASS（769 passed / 0 failed；H2 baseline 741）
```

---

## 19. Remaining Issues（交后续）

```text
① Exam knowledge canonical writer 未收敛（PATCH /exam/11408/{k}/study-plan/knowledge-items）
   —— 需 writer 支持 exam knowledge 身份。不阻断 H3。
② D7：14 张 exam 表仍无 Alembic 覆盖（部署硬化阶段）。
③ D5：exam_favorite_questions_v2 死表仍 DELETE-LATER。
④ D8：OCR 全路径不计费/不记录（Parser Infra）。
⑤ `generate_exam_ai_questions` 仍读 DEEPSEEK_API_KEY 做「未配置则 mock」的快速短路；
   它是配置门而非执行路径，但 provider 名出现在业务代码里，属后续清理项。
⑥ H4：多 track / 多 subject catalog 与真实内容导入（需用户批准）。
```

---

## 20. Final Verdict

```text
STEP7H2_C1: WRONG_CONCURRENCY_ROOT_CAUSE = VERIFIED
            WRONG_CONCURRENT_DISTINCT_FACTS = PASS
            WRONG_REPLAY_IDEMPOTENT = PASS
            WRONG_CONCURRENCY_STRESS = PASS（0/30 runs，1500 轮）
            STEP7H2 = FROZEN

STEP7H3: EXAM_AI_REACHABILITY_AUDIT = PASS
         EXAM_DIRECT_PROVIDER_ENDPOINTS_FINAL = 0
         EXAM_DIRECT_PROVIDER_CALLS_FINAL     = 0
         PARSER_OCR_CLASSIFICATION = PASS
         EXAM_AI_CAPABILITY_MIGRATION = PASS
         EXAM_AI_LEGACY_AUTH_OWNER = 0
         UNIFIED_CAPABILITY_AUTH = PASS
         UNIFIED_USAGE_BUDGET = PASS
         ANSWER_GRADE_MIGRATED = PASS
         DETERMINISTIC_GRADE_PROVIDER_CALLS = 0
         AI_GRADE_RESULT_USED = YES
         EXAM_AI_CONTEXT_PERSISTENCE = PASS
         EXAM_AI_EVENT_CONTEXT_EQUIVALENCE = PASS
         EXAM_USAGE_LEDGER_NAMESPACE_EQUIVALENCE = PASS
         EXAM_AI_BILLING_DOUBLE_COUNT = NO
         EXAM_AI_EVENT_DUPLICATION = NO
         FREE_ANSWER_GRADE_DENIED = PASS
         STANDARD_ANSWER_GRADE = PASS
         BUDGET_DENIAL_BEFORE_PROVIDER = PASS
         COURSE_EXAM_NAMESPACE_ISOLATION = PASS
         PARSER_OCR_MIGRATED_TO_ORCHESTRATOR = NO（EXPECTED = NO）
         STUDENT_TWIN_ELIGIBILITY_EXPANDED = NO
         REAL_APP_DB_MUTATED = NO
         FULL_BACKEND_TESTS = PASS（769 passed / 0 failed；baseline 741）

STEP7H3_COMPLETE = YES
STEP7H3          = FROZEN
STEP7H4_READY    = YES
```
