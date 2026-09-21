import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AiFeedback } from './ai-feedback';

const mutate = vi.fn();
vi.mock('@/components/learning/p4-api', () => ({ useAiFeedback: () => ({ mutate, isPending: false, isError: false, isSuccess: false }) }));

describe('AiFeedback', () => {
  it('only appears for a real request id and requires a frozen reason for negative feedback', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<AiFeedback requestId="" />);
    expect(screen.queryByText('有帮助')).not.toBeInTheDocument();
    rerender(<AiFeedback requestId="req_123" />);
    await user.click(screen.getByRole('button', { name: '需要改进' }));
    expect(screen.getByText('请选择需要改进的原因')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '不正确' }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ request_id: 'req_123', rating: 'down', reason: 'incorrect' }));
    expect(screen.getByText(/用于后续质量改进/)).toBeInTheDocument();
  });
});
