import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { POST: post, GET: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const fail = (status: number, detail: unknown) => ({
  data: undefined,
  error: { detail },
  response: { ok: false, status },
});

const SESSION_USER = { id: 1, username: 'learner_a', nickname: '学习者 A' };

let signedIn = false;

beforeEach(() => {
  signedIn = false;
  post.mockReset();
  post.mockImplementation(async (url: string) => {
    if (url === '/me') return signedIn ? ok({ user: SESSION_USER }) : fail(401, { detail: '未登录' });
    if (url === '/auth/email-login/send-code') return ok({ message: '验证码已发送' });
    if (url === '/auth/email-login') {
      signedIn = true;
      return ok({ message: '登录成功', user: SESSION_USER });
    }
    throw new Error(`unexpected POST ${url}`);
  });
});

async function openEmailCodeMode() {
  renderApp('/login', { user: null });
  await screen.findByRole('heading', { name: '登录', level: 1 });
  await userEvent.click(screen.getByRole('tab', { name: '邮箱验证码登录' }));
}

describe('email code login', () => {
  it('is the second way in, and switching modes swaps the panel and the tab', async () => {
    renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录', level: 1 });

    expect(screen.getByRole('tab', { name: '密码登录' })).toHaveAttribute('aria-selected', 'true');
    // The password form is what is offered first.
    expect(screen.getByLabelText('账号或邮箱')).toBeInTheDocument();
    expect(screen.queryByLabelText('邮箱验证码')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('tab', { name: '邮箱验证码登录' }));
    expect(screen.getByRole('tab', { name: '邮箱验证码登录' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('邮箱', { exact: true })).toBeInTheDocument();
    expect(screen.queryByLabelText('账号或邮箱')).not.toBeInTheDocument();

    // The panel the selected tab names is the panel on screen.
    const panelId = screen.getByRole('tab', { name: '邮箱验证码登录' }).getAttribute('aria-controls');
    expect(document.getElementById(panelId ?? '')).toContainElement(screen.getByLabelText('邮箱验证码'));
  });

  it('moves between the two modes with the arrow keys', async () => {
    renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录', level: 1 });

    screen.getByRole('tab', { name: '密码登录' }).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: '邮箱验证码登录' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: '密码登录' })).toHaveAttribute('aria-selected', 'true');
  });

  it('sends a code to the typed address and says what the server said', async () => {
    await openEmailCodeMode();

    await userEvent.type(screen.getByLabelText('邮箱', { exact: true }), 'learner@example.com');
    await userEvent.click(screen.getByRole('button', { name: '发送验证码' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/email-login/send-code', {
        body: { email: 'learner@example.com' },
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent('验证码已发送');
  });

  it('shows the server’s own sentence when the code cannot be sent', async () => {
    // No SMTP on this deployment is the backend's `503 邮件服务暂未配置`; the screen repeats it
    // rather than inventing a cause it cannot know.
    post.mockImplementation(async (url: string) => {
      if (url === '/auth/email-login/send-code') return fail(503, { detail: '邮件服务暂未配置，请联系管理员' });
      return fail(401, { detail: '未登录' });
    });
    await openEmailCodeMode();

    await userEvent.type(screen.getByLabelText('邮箱', { exact: true }), 'learner@example.com');
    await userEvent.click(screen.getByRole('button', { name: '发送验证码' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('邮件服务暂未配置，请联系管理员');
  });

  it('keeps the send and the verify messages apart', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/auth/email-login/send-code') return fail(429, { detail: '请 60 秒后再试' });
      if (url === '/auth/email-login') return fail(400, { detail: '验证码错误或已过期' });
      return fail(401, { detail: '未登录' });
    });
    await openEmailCodeMode();

    await userEvent.type(screen.getByLabelText('邮箱', { exact: true }), 'learner@example.com');
    await userEvent.click(screen.getByRole('button', { name: '发送验证码' }));
    expect(await screen.findByText('请 60 秒后再试')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('邮箱验证码'), '000000');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    // A wrong code is a different problem from a refused send, so both are readable at once.
    expect(await screen.findByText('验证码错误或已过期')).toBeInTheDocument();
    expect(screen.getByText('请 60 秒后再试')).toBeInTheDocument();
  });

  it('validates locally before it calls the server', async () => {
    await openEmailCodeMode();

    await userEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(await screen.findByText('请输入邮箱地址')).toBeInTheDocument();
    expect(screen.getByText('请输入邮箱验证码')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalledWith('/auth/email-login', expect.anything());
  });

  it('signs in with the code and returns to the requested destination', async () => {
    const { router } = renderApp('/login?returnTo=%2Fprogramming%2Fsetup', { user: null });
    await screen.findByRole('heading', { name: '登录', level: 1 });
    await userEvent.click(screen.getByRole('tab', { name: '邮箱验证码登录' }));

    await userEvent.type(screen.getByLabelText('邮箱', { exact: true }), 'learner@example.com');
    await userEvent.type(screen.getByLabelText('邮箱验证码'), '123456');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/email-login', {
        body: { email: 'learner@example.com', code: '123456' },
      }),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe('/programming/setup'));
  });

  it('offers no password recovery the API does not implement', async () => {
    await openEmailCodeMode();
    expect(screen.queryByRole('link', { name: /忘记密码|找回密码/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /忘记密码|找回密码/ })).not.toBeInTheDocument();
  });
});
