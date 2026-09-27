import { describe, expect, it } from 'vitest';
import { resolveFeedbackReasons } from './feedback-reasons';

describe('resolveFeedbackReasons', () => {
  it('gives an unknown or absent target the answer vocabulary', () => {
    expect(resolveFeedbackReasons()).toEqual(resolveFeedbackReasons('answer'));
    expect(resolveFeedbackReasons().map(([value]) => value)).toContain('incorrect');
  });

  it('keeps the answer wording exactly as it was before contexts existed', () => {
    expect(resolveFeedbackReasons('answer')).toEqual([
      ['incorrect', '回答不正确'],
      ['not_answered', '没有回答我的问题'],
      ['unclear', '解释不清楚'],
      ['too_verbose', '太啰嗦'],
      ['too_brief', '太简略'],
      ['citation_issue', '引用或依据有问题'],
      ['other', '其他'],
    ]);
  });

  it('gives a plan suggestion its own vocabulary', () => {
    expect(resolveFeedbackReasons('plan_adjustment')).toEqual([
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
    ]);
  });

  it('shares only the word that means "none of the above"', () => {
    const answer = new Set(resolveFeedbackReasons('answer').map(([value]) => value));
    const plan = resolveFeedbackReasons('plan_adjustment').map(([value]) => value);
    expect(plan.filter((value) => answer.has(value))).toEqual(['other']);
  });
});
