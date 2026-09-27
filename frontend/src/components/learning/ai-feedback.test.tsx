import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AiFeedback } from './ai-feedback';

const mutate = vi.fn((_body, options?: { onSuccess?: () => void }) => options?.onSuccess?.());
vi.mock('@/components/learning/p4-api', () => ({ useAiFeedback: () => ({ mutate, isPending: false, isError: false, isSuccess: false }) }));

describe('AiFeedback', () => {
  beforeEach(() => {
    mutate.mockClear();
  });

  it('uses compact message actions rather than the old large feedback buttons', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<AiFeedback requestId="" />);
    expect(screen.queryByLabelText('有帮助')).not.toBeInTheDocument();
    rerender(<AiFeedback requestId="req_123" answerText="回答内容" />);
    expect(screen.queryByText('有帮助')).not.toBeInTheDocument();
    expect(screen.queryByText('需要改进')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '复制回答' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '有帮助' }));
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: 'req_123', rating: 'up' }),
      expect.anything(),
    );
  });

  it('collects multiple stable negative reasons and an optional comment', async () => {
    const user = userEvent.setup();
    render(<AiFeedback requestId="req_456" answerText="回答内容" />);

    await user.click(screen.getByRole('button', { name: '需要改进' }));
    expect(screen.getByText('哪里需要改进？')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: '回答不正确' }));
    await user.click(screen.getByRole('checkbox', { name: '解释不清楚' }));
    await user.type(screen.getByLabelText('补充说明（可选）'), '请说明复杂度。');
    await user.click(screen.getByRole('button', { name: '提交' }));

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        request_id: 'req_456',
        rating: 'down',
        reasons: ['incorrect', 'unclear'],
        comment: '请说明复杂度。',
      }),
      expect.anything(),
    );
  });

  it('keeps positive and negative selected states mutually exclusive', async () => {
    const user = userEvent.setup();
    render(<AiFeedback requestId="req_789" answerText="回答内容" />);

    await user.click(screen.getByRole('button', { name: '有帮助' }));
    expect(screen.getByRole('button', { name: '有帮助' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: '需要改进' }));
    await user.click(screen.getByRole('checkbox', { name: '回答不正确' }));
    await user.click(screen.getByRole('button', { name: '提交' }));
    expect(screen.getByRole('button', { name: '需要改进' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '有帮助' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('rates an ANSWER by default, with the answer vocabulary and no context field needed', async () => {
    const user = userEvent.setup();
    render(<AiFeedback requestId="req_answer" />);

    await user.click(screen.getByRole('button', { name: '需要改进' }));
    expect(screen.getByRole('checkbox', { name: '引用或依据有问题' })).toBeInTheDocument();
    // none of the plan-suggestion wording is offered where an answer is being rated
    expect(screen.queryByRole('checkbox', { name: '调整幅度太大' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: '引用或依据有问题' }));
    await user.click(screen.getByRole('button', { name: '提交' }));
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: 'req_answer', rating: 'down',
                                target_type: 'answer', reasons: ['citation_issue'] }),
      expect.anything(),
    );
  });

  it('rates a PLAN SUGGESTION with its own reasons, and none of the answer ones', async () => {
    const user = userEvent.setup();
    render(<AiFeedback requestId="req_plan" target="plan_adjustment" />);

    await user.click(screen.getByRole('button', { name: '需要改进' }));
    // the plan vocabulary is what is offered…
    for (const label of ['调整幅度太大', '时间安排不合理', '没有考虑我的目标或截止时间', '建议太笼统，无法执行']) {
      expect(screen.getByRole('checkbox', { name: label })).toBeInTheDocument();
    }
    // …and the answer vocabulary is not
    for (const label of ['回答不正确', '解释不清楚', '引用或依据有问题']) {
      expect(screen.queryByRole('checkbox', { name: label })).not.toBeInTheDocument();
    }

    await user.click(screen.getByRole('checkbox', { name: '调整幅度太大' }));
    await user.click(screen.getByRole('button', { name: '提交' }));
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: 'req_plan', rating: 'down',
                                target_type: 'plan_adjustment',
                                reasons: ['adjustment_too_large'] }),
      expect.anything(),
    );
  });
});
