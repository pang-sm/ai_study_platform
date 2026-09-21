/**
 * Chinese labels for the ACTIVE user-facing event types of the frozen STEP 7F taxonomy
 * (`EVENT_SCHEMA_VERSION = 2`).
 *
 * An unmapped code falls through to the raw code rather than to a guess, so a new event type
 * shows up as itself instead of being silently mislabelled. Audit-only families
 * (`ai_called`, `ai_feedback_submitted`) are absent on purpose: the records endpoint never
 * returns them unless explicitly asked, and this screen never asks.
 */
export const EVENT_TYPE_LABELS: Record<string, string> = {
  course_practice: '课程练习作答',
  question_answered: '完成一次练习作答',
  code_submitted: '提交代码',
  exercise_started: '开始练习',
  code_run: '运行代码',
  code_tested: '运行测试',
  strong_reasoning_requested: '发起深度思考',
  strong_reasoning_completed: '完成深度思考',
  programming_agent_started: '启动 Debug Agent',
  programming_agent_completed: 'Debug Agent 完成',
  programming_agent_failed: 'Debug Agent 未完成',
  report_generated: '生成学习报告',
  wrong_analysis_generated: '生成错题分析',
  plan_adjustment_proposed: '提出计划调整',
  plan_adjustment_applied: '应用计划调整',
  review_completed: '完成复习',
  knowledge_status_changed: '知识点状态变化',
  material_asked: '就资料提问',
  material_opened: '打开资料',
  adaptive_practice_selected: '选择自适应练习',
  review_scheduled: '安排复习',
};

export const SERVICE_NAMESPACE_LABELS: Record<string, string> = {
  course_learning: '课程学习',
  exam_prep: '考研学习',
  exam_11408: '考研学习',
  programming: '编程学习',
};

export function eventTypeLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType;
}

export function serviceNamespaceLabel(namespace: string): string {
  return SERVICE_NAMESPACE_LABELS[namespace] ?? namespace;
}
