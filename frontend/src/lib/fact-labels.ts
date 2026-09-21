/**
 * Chinese labels for the field names the backend actually sends.
 *
 * Every key here was read off the real payload — the report builder in
 * `backend/learning/report.py`, the course schemas in the generated contract — rather than
 * guessed from a spelling. A key that is not in this map is NOT invented a label, and it is NOT
 * shown either: `FactList` drops it. An unmapped field is a transport detail the product has not
 * decided how to say, and a machine name in front of a learner is worse than a shorter answer.
 */
export const FACT_LABELS: Record<string, string> = {
  // --- report period / coverage ---
  days: '统计天数',
  start: '开始',
  end: '结束',
  available_blocks: '本次可用的数据块',
  unavailable: '本学习空间没有的数据块',
  recent_events: '最近学习事件',
  // `notes`, `*_semantics` are deliberately NOT labelled: the backend writes those as English
  // sentences for engineers ("Not a mastery probability, not a readiness score…"). The learner
  // reads the product's own Chinese statement instead, and the server's wording stays in the
  // folded raw block rather than in the interface.
  block: '数据块',
  reason: '原因',

  // --- metric blocks (the block names are the report's own) ---
  activity: '学习活动',
  practice: '练习',
  review: '复习',
  plan: '学习计划',
  materials: '资料',
  programming: '编程',
  knowledge: '知识点',
  wrong_answers: '错题',

  // --- activity ---
  events: '学习事件数',
  active_days: '有学习记录的天数',
  by_event_type: '按事件类型',

  // --- practice ---
  attempts: '练习次数',
  factual_correct: '做对',
  factual_incorrect: '做错',
  ungraded: '未判分',
  graded_attempts: '已判分',
  ungraded_attempts: '未判分',

  // --- review ---
  total: '总数',
  by_status: '按状态',
  by_source: '按来源',
  scheduled: '已安排',
  due: '已到期',
  due_points: '到期知识点',

  // --- plan ---
  completed: '已完成',
  open: '未完成',
  overdue: '已逾期',

  // --- materials ---
  opened: '打开资料',
  asked: '就资料提问',
  distinct_materials: '涉及资料',

  // --- programming ---
  runs: '运行次数',
  tests: '测试次数',
  submissions: '提交次数',
  submissions_passed: '提交通过',
  submissions_failed: '提交未通过',
  distinct_exercises: '涉及练习',

  // --- knowledge progress ---
  total_points: '知识点总数',

  // --- highlight / attention items ---
  rule: '规则',
  origin: '来源',
  metric: '指标',
  text: '内容',
  action_label: '关联入口',
  destination: '目标位置',
  language: '语言',

  // --- review items ---
  title: '标题',
  status: '状态',
  source_type: '来源类型',
  due_at: '到期时间',
  due_source: '复习日期来源',
  review_status: '复习状态',
  last_reviewed_at: '上次复习',

  // --- course materials ---
  subject: '科目',
  file_type: '文件类型',
  original_filename: '文件',
  file_size: '文件大小',
  parse_status: '解析状态',
  parse_progress: '解析进度',
  chunk_count: '片段数',
  created_at: '创建时间',
  updated_at: '更新时间',

  // --- course today plan (the backend supplies its own label fields for the coded ones) ---
  mode_label: '方式',
  due_date: '计划日期',
  urgency_label: '紧迫程度',
  task_type: '任务类型',

  // --- course identity / state ---
  display_name: '课程名称',
  is_started: '是否已开始',
  declared_level: '已声明水平',
  learning_goal: '学习目标',
  course_name: '课程名称',
  chapter: '章节',
  chapter_title: '章节',
  chapter_no: '章序号',
  question_count: '题目数',
  stem: '题干',
  user_answer: '你的作答',
  reference_answer: '参考答案',
  standard_answer: '参考答案',
  analysis: '解析',
  difficulty: '难度',
  question_type: '题型',
  options: '选项',
  correct: '是否正确',
  judge: '评判方式',
  submitted_at: '提交时间',
  started_at: '开始时间',
  answered_at: '作答时间',
  latest_attempt: '最近一次作答',
  knowledge_point: '知识点',
  knowledge_point_title: '知识点',
  material_ids: '关联资料',
  event_count: '事件数',
  last_event_at: '最近事件时间',

  // --- wrong-answer facts + AI analysis result (real field names from the contract) ---
  question: '题目',
  wrong_count: '错误次数',
  state_status: '订正状态',
  first_wrong_at: '首次答错',
  last_wrong_at: '最近答错',
  attempt_history: '作答历史',
  error_category: '错因类别',
  reasoning_gap: '推理断层',
  correct_reasoning: '正确思路',
  next_action: '下一步建议',
  review_recommendation: '复习建议',

  // --- agent workflow measurements ---
  passed: '通过',
  failed: '未通过',
  diagnosis: '诊断',
  tests_before: '测试前',
  tests_after: '测试后',
  explanation: '最终说明',

  // --- plan adjustment proposal (`reason` is already mapped with the report keys) ---
  op: '变更类型',
  plan_snapshot: '当前计划',
  proposed_changes: '建议变更',
  affected_tasks: '涉及任务',

  // --- agenda / adaptive-practice facts ---
  // `overdue` is NOT re-labelled here: the report's metric block uses it as a count (`已逾期`),
  // while an agenda task carries it as a boolean. One key, two shapes — so the agenda states the
  // same fact through its own `status`, and this name keeps the one meaning it already had.
  last_attempt_at: '最近作答时间',
  active_wrong_count: '未订正错题数',

  // --- programming workbench stats (the endpoint's own `stats` block) ---
  streak_days: '连续学习天数',
  momentum: '最近学习节奏',
  today_practice_count: '今天练习次数',
  today_submission_count: '今天提交次数',
  last_activity_date: '最近学习日期',

  // --- learning-event `summary` fields (references and observed metrics only) ---
  passed_count: '通过测试数',
  total_count: '测试总数',
  exit_code: '退出码',
  timed_out: '是否超时',
  score: '得分',
};

/** The three spaces' own names, for any payload that carries a namespace. */
export const NAMESPACE_LABELS: Record<string, string> = {
  course_learning: '课程学习',
  exam_prep: '考研学习',
  exam_11408: '考研学习',
  programming: '编程学习',
};

/** Review / task / record statuses that really appear in these payloads. */
export const STATUS_LABELS: Record<string, string> = {
  active: '待处理',
  resolved: '已解决',
  due: '已到期',
  scheduled: '已安排',
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  open: '未完成',
  skipped: '已跳过',
  overdue: '已逾期',
  submitted: '已提交',
  ok: '正常',
  warning: '有警告',
  error: '有错误',
  parsed: '已解析',
  success: '已解析',
  partial: '部分解析',
  parsing: '解析中',
  pending: '待处理',
  failed: '未成功',
  timeout: '超时',
  running: '进行中',
};

/** `action` on one step of the bounded agent's trace. A closed vocabulary, observed per step. */
export const AGENT_ACTION_LABELS: Record<string, string> = {
  tests_before: '记录修复前的测试结果',
  diagnose: '诊断',
  propose_patch: '提出修改',
  run_tests: '运行测试',
  explain: '给出说明',
};

/** `judge` on a graded attempt. `self_review` is the honest one: the product did not grade it. */
export const JUDGE_LABELS: Record<string, string> = {
  self_review: '自行核对',
  ai_graded: 'AI 判分',
};

/** `task_type` on a plan task. */
export const TASK_TYPE_LABELS: Record<string, string> = {
  knowledge: '知识点学习',
  review: '复习',
  practice: '练习',
  custom: '自定义',
};

/** `file_type` on a study material — an extension, not a word. */
export const FILE_TYPE_LABELS: Record<string, string> = {
  pdf: 'PDF',
  docx: 'Word 文档',
  pptx: 'PPT',
  image: '图片',
  text: '文本文件',
  code: '代码文件',
};

/** `highlights[].origin`, `narrative.origin`, `wrong_analysis.*_origin`. */
export const ORIGIN_LABELS: Record<string, string> = {
  deterministic: '确定性规则',
  ai: 'AI 生成',
  deterministic_reason_rules: '确定性规则',
  computed: '由学习事实计算',
};

/** `data_coverage.unavailable[].reason`. */
export const REASON_LABELS: Record<string, string> = {
  not_applicable_in_this_space: '该学习空间没有这类数据',
  no_data_in_window: '本周期内没有数据',
  insufficient_data: '数据不足',
};

/** `by_source` keys. */
export const SOURCE_LABELS: Record<string, string> = {
  wrong_answer: '错题',
  programming_exercise: '编程练习',
  review_item: '复习项',
  plan_task: '计划任务',
  knowledge_point: '知识点',
  study_plan: '学习计划',
  course_study_plan: '课程学习计划',
  learning_tasks: '学习任务',
};

/** `review_status` values that appear on review projections. */
export const REVIEW_STATUS_LABELS: Record<string, string> = {
  due: '已到期',
  scheduled: '已安排',
  unscheduled: '未安排',
  none: '未安排',
  completed: '已完成',
};

/**
 * `due_source` says which stored column a review date came from. The backend's own value is a
 * column reference (`user_knowledge_progress.review_due_at`) or a policy id — a database address,
 * not a sentence — so the two origins it can name are translated and anything else is dropped.
 */
export const DUE_SOURCE_LABELS: Record<string, string> = {
  'user_knowledge_progress.review_due_at': '来自知识点复习日期',
  'review_policy.review_policy_v1': '由复习策略安排',
};

/**
 * Which of these field names carry a *coded* value, and the vocabulary that value comes from.
 *
 * This is the difference between an enum and prose: `status` is one of a closed set of codes, so
 * a code the vocabulary does not know is a code this product cannot say and must not print —
 * whereas `analysis` is a sentence the backend wrote, and prints as itself. Only fields listed
 * here are treated as coded; every other string is free text.
 *
 * `reason` is deliberately absent: it is a report's coded gap in one payload and the model's own
 * sentence in a plan proposal, so a single vocabulary would mangle one of the two. The one surface
 * that reads it as a code passes `REASON_LABELS` itself.
 */
export const FIELD_VOCABULARIES: Record<string, Record<string, string>> = {
  status: STATUS_LABELS,
  state_status: STATUS_LABELS,
  parse_status: STATUS_LABELS,
  review_status: REVIEW_STATUS_LABELS,
  source_type: SOURCE_LABELS,
  origin: ORIGIN_LABELS,
  due_source: DUE_SOURCE_LABELS,
  judge: JUDGE_LABELS,
  task_type: TASK_TYPE_LABELS,
  file_type: FILE_TYPE_LABELS,
};

function lookup(map: Record<string, string>, key: string): string | undefined {
  return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : undefined;
}

export function factLabel(key: string): string | undefined {
  return lookup(FACT_LABELS, key);
}

export function statusLabel(value: string): string | undefined {
  return lookup(STATUS_LABELS, value);
}

export function originLabel(value: string): string | undefined {
  return lookup(ORIGIN_LABELS, value);
}

export function sourceLabel(value: string): string | undefined {
  return lookup(SOURCE_LABELS, value);
}

export function namespaceLabel(value: string): string | undefined {
  return lookup(NAMESPACE_LABELS, value);
}

export function reasonLabel(value: string): string | undefined {
  return lookup(REASON_LABELS, value);
}

export function reviewStatusLabel(value: string): string | undefined {
  return lookup(REVIEW_STATUS_LABELS, value);
}

/**
 * A known label, or the caller's own fallback — never the raw machine name. Surfaces that show
 * a status pass their domain's map first so a value the shared map does not know still reads as
 * something the product chose to say.
 */
export function labelled(
  lookupTable: Record<string, string>,
  value: string | null | undefined,
  fallback = '—',
): string {
  if (value === null || value === undefined || value === '') return fallback;
  return lookup(lookupTable, value) ?? fallback;
}
