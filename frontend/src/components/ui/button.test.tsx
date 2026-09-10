import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './button';

describe('Button', () => {
  it('renders with an accessible name', () => {
    render(<Button>提交答案</Button>);
    expect(screen.getByRole('button', { name: '提交答案' })).toBeInTheDocument();
  });

  it('is keyboard operable', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>提交答案</Button>);

    const button = screen.getByRole('button', { name: '提交答案' });
    button.focus();
    await user.keyboard('{Enter}');

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders as a link via asChild', () => {
    render(
      <Button asChild>
        <a href="/courses">查看课程</a>
      </Button>,
    );
    expect(screen.getByRole('link', { name: '查看课程' })).toHaveAttribute('href', '/courses');
  });
});
