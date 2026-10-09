# 智学 AI 统一复习推荐中心设计规格

## 状态与阶段门

- 阶段基线：产品 SSOT `STEP_7H5 / NEXT_SUBSTEP=FRONTEND`；该冻结历史保持不变。
- 产品方向与 SSOT 的共享学习核心、单一事实来源、确定性 review policy、统一 Learning Space 和 additive-only 数据约束兼容。
- **有限阶段例外已授权**：用户于 2026-10-09 按 §74 明确批准统一复习中心所需的只读推荐 API、确定性规则、最小暂缓 overlay 与相关测试，并授权配套前端。SSOT 记录 `ACCEL_SPRINT_S3 = IN_PROGRESS`；不重开 STEP_7H5 / STEP_7H，也不放开其他后端冻结范围。

## 产品目标

统一复习是跨专业学习、11408 和编程空间的主动复习中心。它只读真实事实并生成可解释、可执行、每次读取时重新评估的建议；推荐生成不写学习进度、不写复习计划、不改变掌握状态。真实练习、真实学习行为和现有复习完成规则仍是唯一状态写入者。

页面保留“统一复习”标题及“全部 / 专业学习 / 11408 / 编程”筛选。顶部建议数量必须等于当前筛选下未暂缓的推荐数。卡片仅显示对象名称、课程/方向、简短且可追溯的理由、“开始复习”及可选“暂缓”。移除指定的两段旧文案，不添加长篇说明。没有候选时显示无解释段落的极简空状态。

## 不变量

1. 不创建第二套学习事实、复习排期、掌握状态或练习系统。推荐是现有 review 投影上的只读派生视图。
2. 点击开始、打开知识点/题目、进入工作台均不表示完成；不触发完成 API、不改变知识状态或日期。
3. 只有现有真实学习/练习/作答与复习业务规则可以更新事实和状态。掌握状态沿用来源域规则。
4. 推荐 GET 是纯读取：重复读取不会创建事件、排期、推荐记录或进度更新。
5. 暂缓只抑制该用户该稳定建议身份至过期时间；不得删除或修改错题、学习记录、知识点进度、编程进度及原有复习计划。
6. 所有候选、状态读取和写入均按认证用户隔离；旧的/失效身份不可访问其他用户数据。
7. 相同真实事实以底层稳定 attempt/source identity 计数一次；NULL correctness、self-review 和非判题基础设施错误不得当作错误作答。
8. 推荐理由由固定规则和可审计事实生成，不调用 LLM，不把时间间隔写成“已遗忘”或把建议写成已掌握结论。

## 数据流与职责

```text
已有领域事实（知识进度/学习事件、复习日期与完成结果、PracticeAttempt、WrongAnswerState、编程进度与判题结果）
    → 只读候选投影与身份归一化
    → 稳定去重、证据/紧迫度排序
    → 叠加用户级暂缓有效期
    → GET /review/recommendations → 页面卡片与真实领域 deep link
    → 用户在原学习/练习/错题/编程流程中行动
    → 原领域服务记录真实事实并按其规则更新状态
    → 下一次只读请求重新评估；无后台每日写入任务
```

开始复习不调用复习完成接口。只有存在真实可判定的复习行为时，沿用现有 `/review/{item_id}/complete` 的真实结果契约；答题、错题订正、知识点学习和编程提交优先由原领域入口记录，以免双写同一学习事实。未产生判定结果的知识点浏览不更新复习间隔或掌握状态。

## 暂缓状态设计

审计确认 `LearningEvent` taxonomy 仅有 `review_scheduled` / `review_completed` 两个 active review 事件且 taxonomy 冻结。将暂缓写成 `review_scheduled` 会覆盖其 due 语义；将其伪装成完成事件则会虚构学习结果。因此不复用这些事件。

在获准的后端范围内新增最小 overlay 表 `review_recommendation_snoozes`：

- `id` 主键；`user_id` 外键/索引；`recommendation_key`（稳定身份 hash）；`snoozed_until`、`updated_at`。
- 唯一键 `(user_id, recommendation_key)`，重复暂缓为幂等 upsert，更新暂缓截止时间。
- 表只保存 UI 暂缓状态，不保存候选快照、理由、分数或学习事实；推荐始终从当前领域事实重算。
- 暂缓期限固定 24 小时（UTC）。到期后不需恢复任务或写回，下一次 GET 自然重新纳入；若底层事实已消失/解决，则不再显示。
- snooze API 在写入前重新生成当前候选并校验身份确属当前用户、尚未过期且仍可行动；失效候选返回 404/409，不创建孤立状态。
- 迁移只 `CREATE TABLE` 和所需索引，遵循 Alembic additive-only；不改动既有表或数据。规格阶段检查到当前迁移头为 `20261001_0018`，实施时必须重新核验后选择连续 revision。

## 候选范围与可用证据

候选只来自当前用户可归属且可执行的事实。一次读请求按来源有界读取，计算只在内存投影上发生。

| 类型 | 允许依据 | 规则语义/限制 |
|---|---|---|
| 到期复习 | `UserKnowledgeProgress.review_due_at`、现有 review policy 的最新 `review_scheduled`、真实 `review_completed` | 使用已有 due 与周期；GET 不重排期、不修改日期。过期天数来自 due 与当前 UTC 时间差。 |
| 错题纠正 | 当前用户 active `WrongAnswerState` 与归属到不同 `PracticeAttempt.attempt_uid` 的真实错误 | 一次错误只称“订正这道错题”；至少两个不同且判定错误的 attempt 才称“重复错误/持续薄弱”。NULL 和 self-review 不计错。 |
| 遗忘预防/巩固 | 有明确 `last_studied_at` 且已有正值 `review_interval_days` 的知识点；有真实复习历史时采用其最新 interval/due | 只在已有周期到期时推荐；理由说“距离上次有效学习 X 天，建议巩固”，不声称遗忘。无明确时间或间隔则不生成此类候选。 |
| 编程巩固 | 本人编程 exercise 的真实失败判题/提交和现有 exercise catalog | 只把明确 `passed=false` / 判题失败视为失败；超时、编译基础设施故障或未判定结果不可推断薄弱。至少两个不同失败 attempt 才标“反复失败”；单次失败称“继续完成这题”。 |

编程错误次数来自 user-scoped canonical `PracticeAttempt` 的不同 `attempt_uid` 和真实 `correct` verdict；禁止把 `(username, exercise_id)` 唯一的 `programming_exercise_submissions` 与进度行重复计数。`code_tested` / `code_run` 没有 correctness，不能独立证明失败。编程题到知识点只在题目 catalog 有明确 primary/associated knowledge point ID 时关联。无关联时仍可按 exercise 身份推荐，不映射/编造知识点。已掌握知识点不因陈旧错误自动降级；候选状态依赖来源域当前状态和最近真实 attempt。

## 身份、合并、过期与排序

- 知识点身份：`canonical_service_namespace + canonical_scope(course_id 或 exam_module_id) + knowledge_point_code`；code 缺失时才用该 scope 下稳定 `knowledge_point_id`。标题绝不作为身份。exam legacy alias 先使用现有 scope parser 归一到 canonical Exam Prep namespace/module。
- 题目身份：`canonical_namespace + canonical_scope + question_source_type + question_source_id`，与错题投影现有 identity 一致。
- 编程题：若有明确 knowledge point mapping，合并到上述 scoped knowledge identity，并保留题目作为首选执行目标及证据；否则用 `programming + exercise_id`。
- 同身份来源合并为一张卡：保留所有 source evidence，按最高的 actionable evidence 选择一个 reason 与 deep link；理由可以简短地组合两条事实，但不显示技术字段。
- 每次读取时重新验证来源当前状态。wrong state resolved、knowledge 已按权威规则掌握/重学、program 已通过、source 消失/脱离 scope 时不再显示旧建议。建议没有独立生命周期状态。
- 版本化策略 `review_recommendation_v1`；排序使用公开、确定的字典序而非难解释的加权黑箱：①已过期的显式复习计划（逾期天数降序，due_at 升序）；②重复错误/重复判题失败（不同事实次数降序，最近失败时间升序）；③已到期的已记录间隔巩固；④单次 active 错题/单次真实失败纠正。并列依次按更高证据等级、最近真实事实时间、canonical recommendation key 升序。
- 全序 key 确保相同输入与时间产生相同排序。不能用展示标题、数据库返回顺序或随机值打破平局。
- 查询每次用单一 `as_of` UTC 时间，响应携带 `generated_at` 与 `policy_version`；不得将午夜刷新误写入持久学习历史。自然日按用户既有时区约定展示，日期排序/过期比较在 UTC。

## API 契约提案

- `GET /review/recommendations?service_namespace=...&limit=...`：纯读，响应含 `items`, `total`, `generated_at`, `policy_version`, `semantics`。每个 item 含稳定 `recommendation_key`、kind、canonical namespace、scope、对象标题、所属方向标签、reason code/text、可追溯 evidence references/counts/timestamps、priority tuple、action target/deep link、可选 `snoozed_until`（仅必要内部 contract 字段）。请求过滤沿用 review namespace 语义，全部筛选由同一候选集合派生。
- `POST /review/recommendations/{recommendation_key}/snooze`：空请求；固定 snooze 24h；用户认证、当前候选验证、幂等 upsert；响应 `recommendation_key`, `snoozed_until`。不触碰计划/排期/学习事实。
- 不新增完成接口。原 `/review/{item_id}/complete` 仅在已发生的真实复习并获得真实结果后调用；原练习/错题/编程流程维持写入权。
- OpenAPI 类型经 `frontend` 既有 `npm run api:generate` 生成，禁止手改 `frontend/src/types/api.ts`。

## 页面规格

- 保留标题和四筛选项；移除两句指定旧文案。无 hero 长文、说明段或演示数字。
- 顶部显示“今日建议 N 条”，N 来自当前过滤、当前 as-of、排除有效 snooze 后的服务器响应 `total`。
- 按服务返回的稳定 priority 顺序展示推荐卡。卡片仅渲染对象、所属课程/方向、简洁事实理由、“开始复习”、可选“暂缓”。不显示到期日期/指标详情/底层 reason code，除非它是理由的必要部分。
- CTA 使用现有真实入口：course knowledge/wrong/practice、exam knowledge/wrong/practice、program exercise 工作台。不能链接到仅占位或不存在的路径；不能点击即完成。
- 暂缓后乐观更新/刷新推荐和真实数量；API 失败时保留原卡并显示简洁错误状态。
- 空状态只有短标题（如“现在没有复习建议”），无段落、无伪造卡片、无“先去练习”前置要求。

## 风险与决策边界

1. 当前仅有按 §74 授权的 ACCEL_SPRINT_S3 有限后端范围；实现超出所列边界须再次审查。
2. 暂缓必须新增 overlay migration，因为冻结 event taxonomy 不能承载此事实。
3. `ProgrammingExerciseSubmission` 有 `(username, exercise_id)` 唯一索引，不能据此计算重复提交；canonical `PracticeAttempt` 的每次真实 submit 使用时间戳 item key，具备独立 attempt identity，判题结果来自 sandbox。只计此 canonical history 一次。
4. `UserKnowledgeProgress.review_due_at` 是已持久化的复习决定。不得从可能是默认值的 `review_interval_days` 自行另造 due 日期；仅用已存 due/scheduled event 产生候选。没有有效时间/due 时不发遗忘预防建议。
5. 默认 24 小时暂缓是产品实现参数；若用户要求其他时长，可在编码前改规格，不能后台猜测。

## 验收标准

- API 测试证明推荐只读、候选可追溯、重复读不写数据、策略同输入稳定。
- 到期、单次偶错、重复错、间隔巩固、单次/重复编程判题分别按规则分类；self-review/NULL/infra error 不增加弱项证据。
- 同一知识点/题目跨来源只出现一条卡，身份不依赖标题，canonical/legacy scope 正确。
- 排序全序符合版本化 tuple；翻页/重复读取稳定；来源修复后建议立即消失。
- snooze 不改变 `review_due_at`/事件/复习状态；同用户同身份重复请求幂等；跨用户隔离；过期后恢复且不重复计学习事实。
- 完成 review 只接受真实结果；开始链接/知识页浏览不写完成状态；原课程、11408、编程业务闭环回归通过。
- 空数据和单次低证据场景不制造薄弱/遗忘结论；过滤后数量来自实际候选。
- 前端 `npm run check`、`npm run build`、浏览器真实端到端验收通过。
- 后端使用项目 venv 执行变更测试及全量 pytest；schema 用 Alembic additive-only 迁移，在隔离数据库验证迁移和 `PRAGMA integrity_check=ok`。
- 生产发布只有在阶段授权、所有测试、代码审阅、明确提交/推送授权规则完成后进行；保持旧服务运行期间做预检、单点切换、health gate、失败自动回滚，最后真实浏览器验收并核对线上 SHA。
