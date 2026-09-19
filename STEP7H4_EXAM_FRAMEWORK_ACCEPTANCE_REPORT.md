# STEP7H4_EXAM_FRAMEWORK_ACCEPTANCE_REPORT

> 智学AI — Clean-Slate 产品重构 · STEP 7H4 验收报告
> 范围：Multi-track / Multi-subject Exam Preparation catalog foundation
> 生成：2026-09-17 · 本轮为 **RECOVER_AND_FINISH**（上一会话 context 溢出中断；以磁盘事实为唯一 baseline）
> 本轮有代码变更（含恢复 + 修复 + 新增），未 commit / 未 push

---

## 0. 恢复说明（RECOVER_AND_FINISH_STEP7H4）

上一会话在修复 `test_exam_framework.py` 期间因 context length 达到上限中断。
本轮**不从头重做、不按聊天历史猜**，全部以当前磁盘只读事实为准。

### 0.1 H4_RECOVERY_MATRIX

逐文件从磁盘审计（exists / syntax / diff / imports / model / router / migration / tests）：

| 声称被上一会话修改的文件 | 磁盘事实 | 判定 |
| --- | --- | --- |
| `backend/learning/spaces/exam_prep/catalog.py` | 存在，269 行；`CATALOG_VERSION = "v2"`；CONFIG-only；1 ACTIVE subject + 13 FRAMEWORK_ONLY；CS408 4 modules | ✅ 完整且正确 |
| `backend/learning/spaces/exam_prep/knowledge.py` | 存在，261 行；`apply_exam_knowledge_change` / `commit_and_emit` / `emit_transition` / `EXAM_MUTATION_PATHS` | ✅ 完整且正确 |
| `migrations/versions/20260917_0007_create_exam_prep_profiles.py` | 存在；`revision=20260917_0007`；`down_revision=20260915_0006` | ✅ 链正确 |
| exam prep router（真实位置） | `backend/routers/exam_prep.py`，206 行（**不在** `backend/routers/exam/` 下） | ✅ 存在 |
| `backend/main.py` | PATCH 路由 (18531) 已改为调用 canonical writer (18573–18588)；`generate_exam_ai_questions` (21399) 已无 provider 配置判断 | ✅ 已收敛 |
| `backend/tests/test_exam_framework.py` | 存在，415 行 / 51 tests，**磁盘上即为全绿** | ✅ 中断前的修复已落盘 |
| `models.ExamPrepProfile` | 存在（models.py:1359–1386），`__tablename__="exam_prep_profiles"` | ✅ 未遗漏 |
| router 注册 | `main.py:5545 app.include_router(exam_prep_router)` | ✅ 已注册 |

**结论**：上一会话声称的修改全部真实存在于磁盘，且形态正确。**唯一未完成项**是本轮的迁移测试回归
（见 §9）与验收报告本身。

### 0.2 「2 个 test bug」

上一会话称测试运行后发现 2 个 test bug 但在修复时 context overflow。
**本轮实测：recovery 后 `test_exam_framework.py` 51 passed / 0 failed / 0 error / 0 skipped，无需任何修改。**
即修复已在中断前落盘。未复现出任何残留失败，故无「猜到的那两个 bug」可修。

---

## 1. Git / DB Safety

```text
HEAD = ebad5282（与轮次开始时一致，未变）
git 写操作 = NONE（无 commit / push / reset / clean / restore / stash / merge / rebase / pull）
            无新建 worktree
```

所有需要模块加载的动作（import main / TestClient / pytest / route introspection）均在显式
`DATABASE_URL=sqlite:///<temp>` 下执行；真实 `backend/app.db` **只用只读 sqlite3**
（`file:…?mode=ro`）访问，未建 engine、未 create_all、未迁移、未写入。

**真实库指纹复核**：对
`(id, subject_key, source_type, year, question_number, stem, standard_answer, analysis)` 逐行 sha256：

```text
REAL backend/app.db  H4_BANKSHA256 = 6f788bca7b76a5b6edbef0d7d0abf0afe5aa28e3f7bc5a9e0011a634de18d5ee
REAL backend/app.db  mtime         = 2026-09-16 21:24（本轮为 09-17，未变）
```

> 说明：H1 报告记录的 `CONTENT_FINGERPRINT_SHA256 = 7b0717…` 未记录序列化方法，本轮无法逐字节复现。
> 因此本轮改用**已记录列集 + 显式序列化**（`\x1f` 连接、`\n` 分行、`ORDER BY id`）重算并可复现。
> 「内容未变」由更强的旁证支撑：mtime 未变、总数与**逐 subject / 逐 source_type 计数与 H1 完全相同**
> （见 §10）。此处如实标注方法学差异，不冒充等价。

```text
REAL_APP_DB_MUTATED = NO
```

---

## 2. Mechanism 边界（H4 是什么 / 不是什么）

H4 是 **framework foundation**，不是内容导入：

- **是**：把考试方向表达为 versioned **CONFIG**（track / subject / module 三个独立概念）、
  给学习者一个**真实的 Exam Prep profile**、给「未上线科目」一个**显式失败**的可用性门。
- **不是**：导入任何非 CS408 的真实内容。STEP7H0 §21 明确「按需导入第一个非 408 科目
  （**需用户明确批准**）」。

**本轮用户决策**：只有 CS408 有真实内容 → `cs_408` = ACTIVE，其余全国统考科目 = FRAMEWORK_ONLY，
**零内容导入**。故 H4 不触发「导入」分支，只交付 framework。

---

## 3. Catalog（CONFIG，非 SQL）

```text
CATALOG_VERSION = v2
CATALOG_STORAGE = CONFIG（backend/learning/spaces/exam_prep/catalog.py）
CATALOG_SQL_TABLES = 0
```

三个概念**保持分离**（不把 track == subject 变成通用规则）：

| 概念 | 语义 | 例 |
| --- | --- | --- |
| `ExamTrack` | 我在准备什么**方向 / 组合** | `cs_408` / `management_joint` / `law_jm_non_law` |
| `ExamSubject` | 实际**考什么**（全国统考科目） | `cs_408` / `math_1` / `politics` |
| `ExamModule` | 该科目的**教学组织** | `data_structure` / `operating_system` |

### 3.1 可用性

```text
ACTIVE          = active          real content exists
FRAMEWORK_ONLY  = framework_only  selectable & representable, NOTHING faked
```

| id | availability | modules | has_questions / past_papers / knowledge_tree |
| --- | --- | --- | --- |
| `cs_408` | **active** | data_structure / computer_organization / operating_system / computer_network | true / true / true |
| politics | framework_only | *(无)* | false / false / false |
| english_1 / english_2 | framework_only | *(无)* | false / false / false |
| math_1 / math_2 / math_3 | framework_only | *(无)* | false / false / false |
| management_aptitude | framework_only | *(无)* | false / false / false |
| economics_joint_aptitude | framework_only | *(无)* | false / false / false |
| law_master_law / law_master_non_law | framework_only | *(无)* | false / false / false |
| education_basics | framework_only | *(无)* | false / false / false |
| psychology_basics | framework_only | *(无)* | false / false / false |
| history_basics | framework_only | *(无)* | false / false / false |

**能力标志由 CONFIG 派生，绝不来自数表行数** —— 一个产品能力不得因为某张表恰好为空而改变。

### 3.2 不虚构

- FRAMEWORK_ONLY 科目**没有** chapters / knowledge points / questions / seed 占位内容。
- `suggested_subjects` 对**除 cs_408 外**的每个 track 均为**空**：仓库内没有权威来源说明
  「某方向需要哪些公共课」（随学位类型 / 院校要求 / 年份变化），catalog **不猜**。
  学习者的 `selected_subjects` 才是真正的 scope。
- **院校自命题**（school / institution / college / major-code / school exam code /
  参考书目 / 院校大纲）在本产品中**永久 OUT OF SCOPE**，catalog 中零表达。

---

## 4. Content Gate（统一失败契约）

`GET /exam/prep/subjects/{subject_id}/content-status` 是「我现在能不能学这门」的**唯一诚实答案**：

```text
ACTIVE subject         → 200 + availability/modules 元数据
FRAMEWORK_ONLY subject → 409 + { code: "EXAM_CONTENT_NOT_AVAILABLE",
                                 subject_id, availability, message }
unknown subject        → 404
```

**刻意不用 404 表达 framework_only**：科目**存在且可选**，只是尚无内容 —— 这是两个不同的答案。

**禁止 `200 + []` 冒充成功**：任何客户端都不能把「尚未上线」误读为「没有数据」。
gate 由 `routers/exam_prep.py::require_subject_content` 统一实现，错误契约单点。

---

## 5. Exam Prep Profile（真实用户态，独立表）

```text
EXAM_PREP_PROFILE_TABLE = exam_prep_profiles
NEW_TABLES              = exam_prep_profiles（1）
```

字段（最小集，全部落地）：

| 字段 | 说明 |
| --- | --- |
| `id` | PK |
| `user_id` | UNIQUE（`uq_exam_prep_profile_user`）→ **每用户一个 CURRENT profile** |
| `exam_type` | 默认 `postgraduate` |
| `selected_track` | 合法 catalog track id |
| `selected_subjects_json` | 合法 catalog subject id 列表 |
| `target_exam_year` | 学习者**目标考试年份**（nullable） |
| `created_at` / `updated_at` | |

**刻意不存在**：`school` / `institution` / `college` / `major` / `major_code` /
`school_exam_code` / 院校大纲 / 参考书目。（可执行断言见 §11 `INSTITUTION_SPECIFIC_FIELDS_ADDED = 0`）

`target_exam_year` 是**目标年份**，与真题的 `question_year` **不同概念**，
也不进任何 practice / wrong / event identity。

### 5.1 Profile API

```text
GET  /exam/prep/profile    → 未配置时 configured=false，各字段显式 null/[]（不伪造 profile）
PUT  /exam/prep/profile    → upsert
GET  /exam/prep/catalog
GET  /exam/prep/catalog/tracks
GET  /exam/prep/catalog/subjects
GET  /exam/prep/subjects/{id}/content-status
```

未额外拆分无意义 API。校验语义：

- `selected_track` 非法 catalog id → **400 fail closed**
- `selected_subjects` 含非法 subject id → **400 fail closed**
- **framework_only subject 允许选择**（目标就是目标，即使内容尚未上线）
- `target_exam_year` 越界 → 400
- **Free 用户也可以保存 profile** —— profile 不是会员权益
- **跨用户隔离**：第二个用户的 profile 与第一个完全独立

---

## 6. Exam Knowledge Canonical Writer（§17–§24）

```text
EXAM_MUTATION_PATHS inventory = 3 条，全部已声明；exam_paths_not_consolidated() == []
```

| path | status | 说明 |
| --- | --- | --- |
| `PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}` | **CANONICAL_WRITER** | 经 `exam_prep.knowledge.apply_exam_knowledge_change` |
| `POST /course-learning/practice/{id}/submit`（exam mode） | SYSTEM_DERIVED_NO_EVENT | legacy 11408 practice submit 派生 course-scoped delta |
| `_materialize_due_review_statuses` / review-interval recompute | SYSTEM_DERIVED_NO_EVENT | 确定性调度重算，非学习 transition |

**H4 之前**：该 PATCH 路由**直接写** `user_knowledge_progress`，使路由成为 exam knowledge
状态 / review 调度 / 事件语义事实上的 owner。**H4 之后**：唯一写入边界在 exam space，路由调用它。

**保留不变（PRESERVE PATCH CONTRACT）**：legacy URL、HTTP method、response contract、
score 阈值（learning 默认 30 / mastered=100）、study-plan 语义、review 算法、
mastery 解释**一律未改**；只是把 direct write 收敛到 canonical writer。
路由自己的校验（subject / entitlement / status / map + leaf check）全部保留。

### 6.1 Knowledge 身份与来源

```text
user + service_namespace=exam_prep + exam_subject_id=cs_408 + exam_module_id=<module> + knowledge_point_code
```

**来源不是 `KnowledgePoint` SQL 表**：

- `seed_data/knowledge_maps/<module>_11408.json`（course map，leaf 校验）
- `exam_question_bank` 的 knowledge metadata

因此 canonical writer **不要求 `knowledge_points` 表有对应行**。
（`knowledge_points` 现有 **32 行** 属于 **programming ontology**，与 Exam catalog 无关。）

**持久兼容**：`UserKnowledgeProgress.course_id` 仍为 `<module>_11408`。
H1 的 legacy scope adapter 已把它解释为 `exam_prep / cs_408 / <module>`；**本轮不 rewrite scope**。

> 实现细节：`SessionLocal` 的 `autoflush=False` 会让 canonical writer 看不到调用方尚未 flush 的行，
> 从而为同一 knowledge point 创建**重复** progress 行 —— 故 writer 入口显式 `db.flush()`。

### 6.2 事件语义

```text
emit              : knowledge_status_changed（仅真实状态迁移）
service_key       : exam_prep
subject_key       : cs_408          ← H1 契约：事件 subject 是 EXAM SUBJECT，不是 module
domain context    : exam_module_id + knowledge point code/id（进 knowledge_point_ref_json）
exam_track_id     : 不进事件、不进任何 identity
```

- **同一状态重复写入 → 不发 duplicate transition**（`is_transition` 门；实测 3 次写入仅 1 条事件）
- event 用**独立 session**，records 故障不会扰动调用方已 commit 的事务（failure-isolated）
- **不接** StudentTwin / IRT / learner_state / misconception / evidence_reliability

---

## 7. Provider-Specific Config 清理（§25）

H3 报告 §19 ⑤ 遗留项：

> 「`generate_exam_ai_questions` 仍读 `DEEPSEEK_API_KEY` 做『未配置则 mock』的快速短路；
> 它是配置门而非执行路径，但 provider 名出现在业务代码里，属后续清理项。」

**H4 已关闭**。`generate_exam_ai_questions` 现直接经 `_exam_ai_content(db, user, "question.generate", …)`
（STEP7H3 统一边界）进入 orchestrator；模型可用性由 **Router / Gateway** 决定，
「模型不可用」是 fallback 已覆盖的**技术失败**，业务层不需要知道配了哪家 vendor。

```text
EXAM_BUSINESS_PROVIDER_SPECIFIC_CONFIG = 0
```

> 边界说明：**provider adapter 自己的 secret 配置未删**（`ai/providers/*`、`ai/secrets.py` 仍是
> provider 名唯一允许出现的地方）；admin 模型配置页 / 健康检查读 env 属平台运维面，不属 exam 业务面。

---

## 8. Migration 0007

```text
revision      = 20260917_0007
down_revision = 20260915_0006          ✅ 链连续（0001→…→0006→0007）
MIGRATION_CHAIN = 0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007
```

`upgrade()` **只做**：`CREATE TABLE exam_prep_profiles` + `uq_exam_prep_profile_user` +
`ix_exam_prep_profiles_user_id`。

**不做**（全部无）：创建 catalog 表 / 创建 14 张 legacy exam 表 / 修改 9333 条题目 /
drop dead table / rename legacy table。`downgrade()` 为 `NotImplementedError`（additive-only）。

实测（全部在 temp 副本上）：

```text
FRESH temp DB → upgrade head   : PASS（head = 20260917_0007）
LEGACY COPY   → upgrade head   : PASS（head = 20260917_0007 / integrity ok / 9333 题保留）
integrity_check                : ok（两库）
REAL backend/app.db            : 未迁移（72 表 / 无 alembic_version / 无 exam_prep_profiles）
```

---

## 9. 本轮修复：迁移测试回归（唯一未完成项）

首次全量回归：**5 failed / 815 passed**，全部集中在 `tests/test_practice_migration.py`。

### 9.1 根因

**测试 bug，非实现 bug。** 该文件把 `head` 当作「正在验证的那个 revision」：

- `EXPECTED_HEAD = "20260915_0006"` —— 硬编码旧 head；
- `test_revision_0004 / 0005 / 0006` 以 `_run_upgrade(legacy_db, "head")` 隔离「本 revision 自身的贡献」，
  而 head 现在是 0007 —— 0007 新建的表被错误归因给 0004 / 0005 / 0006。

实现（0007 必须新建一张表）**是正确的**；把 head 混同于被测 revision 是测试侧缺陷。

### 9.2 修复（只改 test）

1. `EXPECTED_HEAD` → `"20260917_0007"`；
2. `0004 / 0005 / 0006` 三处 `_run_upgrade(…, "head")` → 各自**精确 revision**
   （`20260915_0004` / `0005` / `0006`），本地变量 `at_head` 相应改名 —— 语义比原来更严格；
3. 新增 `test_revision_0007_adds_only_the_exam_prep_profile_table`：
   断言 0006→0007 恰好新增 `exam_prep_profiles` 一张表、不 drop、无 `*catalog*` 表、
   受保护计数不变、必要列与 unique/索引存在。

```text
tests/test_practice_migration.py = 8 passed / 0 failed（原 7 tests）
```

---

## 10. Protected Assets

```text
REAL backend/app.db（只读复核）
  integrity_check                = ok
  表总数                          = 72（未变）
  exam_question_bank             = 9333
    by subject_key : data_structure 5903 / computer_organization 1330 /
                     operating_system 1180 / computer_network 920   ← 与 H1 基线逐项相同
    by source_type : chapter 9098 / past_paper 235                  ← 与 H1 基线逐项相同
  programming_exercises          = 1923
  knowledge_points               = 32（programming ontology，不属 Exam catalog）
  mtime                          = 2026-09-16 21:24（本轮未变）

文件计数（must not decrease）
  exam_resources   = 268（H0 基线 263 → 268，增加，未减少）
  static/exam_papers = 564（未变）
```

**NON_CS408 数据不变量**：

```text
exam_question_bank DISTINCT subject_key = {data_structure, computer_organization,
                                           operating_system, computer_network}
seed_data/knowledge_maps/ 无 math_* / politics / english_* / law_* / management_* /
                          education_* / psychology_* / history_* 任何 *_11408.json
exam_resources/           无新增非 CS408 目录
static/exam_papers/       无新增非 CS408 目录
```

```text
NON_CS408_REAL_QUESTION_ROWS_ADDED     = 0
NON_CS408_KNOWLEDGE_CONTENT_ADDED      = 0
NON_CS408_PAST_PAPER_CONTENT_ADDED     = 0
```

---

## 11. Tests

### 11.1 Targeted

```text
tests/test_exam_framework.py     = 52 passed / 0 failed（恢复时 51，本轮 +1 provider-isolation 断言）
tests/test_practice_migration.py =  8 passed / 0 failed（本轮修复后）
tests/test_exam_prep_namespace.py + test_exam_ai_orchestrator.py
  + test_exam_practice_records.py = 105 passed / 0 failed
tests/test_wrong_answers.py -k concurrent = 3 passed / 0 failed
```

逐条门禁（§19 要求证明者）：

| 断言 | 结果 |
| --- | --- |
| `CATALOG_VERSIONED_CONFIG` | PASS |
| `CS408_CONTENT_STATUS = ACTIVE` | PASS |
| `NON_CS408_CONTENT_STATUS = FRAMEWORK_ONLY` | PASS |
| `NON_CS408_REAL_QUESTION_ROWS_ADDED = 0` | PASS |
| framework-only profile selection | PASS |
| framework-only content gate（409 `EXAM_CONTENT_NOT_AVAILABLE`） | PASS |
| CS408 content access（200 + 4 modules） | PASS |
| profile CRUD | PASS |
| profile cross-user isolation | PASS |
| invalid catalog id rejected | PASS |
| institution-specific fields absent | PASS |
| Exam knowledge canonical writer | PASS |
| same knowledge state repeated → no duplicate event/row | PASS |
| course / exam same knowledge code → isolated | PASS |
| invalid exam module → rejected | PASS |
| invalid knowledge code → rejected（可校验时） | PASS |
| `EXAM_BUSINESS_PROVIDER_SPECIFIC_CONFIG = 0` | PASS |

### 11.2 Wrong Concurrency Regression（H2-C1 未回归）

```text
WRONG_CONCURRENCY_STRESS = PASS（test_concurrent_wrong_attempts_yield_one_state /
                                 test_concurrent_replay_of_one_fact_stays_one /
                                 test_concurrent_wrong_then_correct_resolves_with_full_count）
```

compare-and-recompute 语义**未被 H4 触碰**，未重新设计 Wrong semantics。

### 11.3 Full Backend Regression

```text
pytest -q（backend/，项目 venv，temp DATABASE_URL）
FINAL = 822 passed / 0 failed（baseline 769；+53 = exam_framework 52 + 新增 migration 1）
```

---

## 12. Final Gates

```text
CATALOG_VERSIONED_CONFIG              = PASS
CATALOG_SQL_TABLES                    = 0

CS408_CONTENT_STATUS                  = ACTIVE
NON_CS408_CONTENT_STATUS              = FRAMEWORK_ONLY

NON_CS408_REAL_QUESTION_ROWS_ADDED    = 0
NON_CS408_KNOWLEDGE_CONTENT_ADDED     = 0
NON_CS408_PAST_PAPER_CONTENT_ADDED    = 0

EXAM_PREP_PROFILE_TABLE               = PASS
EXAM_PREP_PROFILE_ISOLATION           = PASS

INSTITUTION_SPECIFIC_FIELDS_ADDED     = 0

FRAMEWORK_ONLY_PROFILE_SELECTION      = PASS
FRAMEWORK_ONLY_CONTENT_GATE           = PASS

CS408_EXISTING_CONTENT_ACCESS         = PASS

EXAM_KNOWLEDGE_CANONICAL_WRITER_CONSOLIDATED = YES
EXAM_KNOWLEDGE_EVENT_SEMANTICS        = PASS

STUDENT_TWIN_ELIGIBILITY_EXPANDED     = NO

EXAM_BUSINESS_PROVIDER_SPECIFIC_CONFIG = 0

QUESTION_BANK_COUNT                   = 9333
QUESTION_BANK_CONTENT_UNCHANGED       = YES

MIGRATION_HEAD                        = 20260917_0007

REAL_APP_DB_MUTATED                   = NO

WRONG_CONCURRENCY_STRESS              = PASS

FULL_BACKEND_TESTS                    = PASS（822 passed / 0 failed）
```

---

## 13. 遗留 / 交接（不阻断 H4 冻结）

① **17 张 legacy exam 表仍无 Alembic baseline**（STEP7H0 R3 🟠 中）：本轮只新增 0007，
   未给既有 14 张 exam 表补 baseline，也未删死表 —— 那属独立步骤，可能需用户批准。

② **真实 `backend/app.db` 未迁移到 0007**（本轮刻意如此）：`exam_prep_profiles` 在生产库尚不存在。
   Profile API 的**代码**已就绪，但线上要可用需要一次正式部署迁移（走既有部署流程，不直改线上）。

③ **FRAMEWORK_ONLY 科目的公共课组合未定义**：`suggested_subjects` 除 cs_408 外全空，
   是**诚实的空**而非遗漏；一旦有权威来源（按学位类型 / 年份）再填。

④ **非 408 真实内容导入仍未发生**，且**必须等用户明确批准**（STEP7H0 §21）。

⑤ **H5 = CS408 full acceptance**：端到端 onboarding → 章节练习 → 真题 → 错题 → 计划 → 记录 → 报告。

---

## 14. Final Verdict

```text
STEP7H4_COMPLETE = YES
STEP7H4          = FROZEN
STEP7H5_READY    = YES

（STEP7H 整体**未** COMPLETE —— 不得声称 STEP7H COMPLETE；H5 未做）
```
