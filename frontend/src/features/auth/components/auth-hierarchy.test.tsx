import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { POST: post, GET: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const signedOut = { data: undefined, error: { detail: '未登录' }, response: { ok: false, status: 401 } };

beforeEach(() => {
  post.mockReset();
  post.mockImplementation(async (url: string) => {
    if (url === '/auth/register/send-code') return ok({ message: '验证码已发送' });
    if (url === '/auth/register/verify-code') return ok({ message: '邮箱验证成功' });
    return signedOut;
  });
});

/** Document order, without reaching for layout: which node comes first. */
function precedes(first: Node, second: Node) {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('auth surface hierarchy', () => {
  it('separates the product identity from the form, and shows the spaces as structure rather than dead links', async () => {
    renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录', level: 1 });

    const identity = screen.getByRole('complementary');
    for (const space of ['考研学习', '课程学习', '编程学习']) {
      expect(within(identity).getByText(space)).toBeInTheDocument();
    }
    // A signed-out visitor who followed one of these would be bounced straight back here, so the
    // identity column describes the product instead of pretending to navigate it.
    expect(within(identity).queryAllByRole('link')).toHaveLength(0);
    expect(within(identity).getByText(/共享学习工具/)).toBeInTheDocument();

    // The form is one task with one heading and one action. The only other button on the screen
    // is the password's reveal toggle, which acts on that same field rather than competing with
    // the submit; the two sign-in modes are tabs, not buttons.
    const level1 = screen.getAllByRole('heading', { level: 1 });
    expect(level1).toHaveLength(1);
    expect(level1[0]).toHaveTextContent('登录');
    expect(screen.getAllByRole('button')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '登录' })).toHaveAttribute('type', 'submit');
    expect(screen.getByRole('button', { pressed: false })).toHaveAccessibleName('显示密码');

    const form = document.querySelector('form');
    expect(form).not.toBeNull();
    expect(precedes(identity, form as HTMLElement)).toBe(true);
  });

  it('states that no legal documents are published instead of linking to a page that does not exist', async () => {
    renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录', level: 1 });

    const legal = screen.getByText(/用户协议与隐私政策尚未发布/);
    expect(legal).toBeInTheDocument();
    expect(legal.tagName).toBe('P');
    expect(screen.queryByRole('link', { name: /用户协议|隐私政策/ })).not.toBeInTheDocument();
  });

  it('numbers the registration steps, keeps them in order, and offers one primary action per step', async () => {
    renderApp('/register', { user: null });
    await screen.findByRole('heading', { name: '注册', level: 1 });

    const steps = screen.getByRole('list', { name: '注册步骤' });
    expect(within(steps).getAllByRole('listitem')).toHaveLength(2);
    expect(within(steps).getByText('验证邮箱').closest('li')).toHaveAttribute('aria-current', 'step');

    // Step one asks for proof of the address and nothing else.
    expect(screen.getByRole('button', { name: '发送验证码' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '验证邮箱' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '创建账号' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('账号')).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('邮箱'), 'learner@example.com');
    await userEvent.type(screen.getByLabelText('邮箱验证码'), '123456');
    await userEvent.click(screen.getByRole('button', { name: '验证邮箱' }));

    // Step two is the only place account details appear, and the marker moves with it.
    expect(await screen.findByLabelText('账号')).toBeInTheDocument();
    const stepsNow = screen.getByRole('list', { name: '注册步骤' });
    expect(within(stepsNow).getByText('设置账号').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(within(stepsNow).getByText('验证邮箱').closest('li')).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('button', { name: '创建账号' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '发送验证码' })).not.toBeInTheDocument();
  });
});
