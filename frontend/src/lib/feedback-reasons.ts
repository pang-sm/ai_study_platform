/**
 * The closed vocabularies a negative rating is written in.
 *
 * Rating an ANSWER and rating a PLAN SUGGESTION are different questions, and one shared word list
 * makes them answerable with each other's words: "解释不清楚" cannot describe a schedule, and
 * "学习任务太多" cannot describe an answer. The two sets are therefore separate here for the same
 * reason they are separate in `backend/learning/feedback.py` — the client CHOOSES which list to
 * show, the server DECIDES which list is valid, and only the server's answer counts.
 *
 * The answer list is the frozen one. Its values and wording are unchanged by the plan-adjustment
 * work, and the backend still validates them against the taxonomy they were recorded under.
 */
export type FeedbackTarget = 'answer' | 'plan_adjustment';

const ANSWER_REASONS = [
  ['incorrect', '回答不正确'],
  ['not_answered', '没有回答我的问题'],
  ['unclear', '解释不清楚'],
  ['too_verbose', '太啰嗦'],
  ['too_brief', '太简略'],
  ['citation_issue', '引用或依据有问题'],
  ['other', '其他'],
] as const;

const PLAN_ADJUSTMENT_REASONS = [
  ['adjustment_too_large', '调整幅度太大'],
  ['adjustment_too_small', '调整幅度太小'],
  ['unreasonable_timing', '时间安排不合理'],
  ['too_much_work', '学习任务太多'],
  ['too_little_work', '学习任务太少'],
  ['wrong_priority', '科目或知识点优先级不合理'],
  ['ignored_goal_or_deadline', '没有考虑我的目标或截止时间'],
  ['insufficient_reason', '调整原因不充分'],
  ['too_vague_to_execute', '建议太笼统，无法执行'],
  ['other', '其他'],
] as const;

export type FeedbackReason =
  | (typeof ANSWER_REASONS)[number][0]
  | (typeof PLAN_ADJUSTMENT_REASONS)[number][0];

/**
 * The reasons offered for one target. An unknown target falls back to the answer list, which is
 * what every caller that does not say anything is asking for.
 */
export function resolveFeedbackReasons(
  target: FeedbackTarget = 'answer',
): ReadonlyArray<readonly [FeedbackReason, string]> {
  return target === 'plan_adjustment' ? PLAN_ADJUSTMENT_REASONS : ANSWER_REASONS;
}
