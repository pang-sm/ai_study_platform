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

/** Modelled like the real cookie: `/me` answers 401 until a sign-in has succeeded. */
let signedIn = false;

beforeEach(() => {
  signedIn = false;
  post.mockReset();
  post.mockImplementation(async (url: string) => {
    if (url === '/me') {
      return signedIn
        ? ok({ user: SESSION_USER })
        : fail(401, { detail: '未登录' });
    }
    throw new Error(`unexpected POST ${url}`);
  });
});

describe('login page', () => {
  it('validates locally before it calls the server', async () => {
    const { router } = renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录' });

    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByText('请输入账号或邮箱')).toBeInTheDocument();
    expect(screen.getByText('请输入密码')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalledWith('/login', expect.anything());
    expect(router.state.location.pathname).toBe('/login');
  });

  it('shows the server’s own refusal without moving the visitor', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/login') return fail(400, '账号、邮箱或密码错误');
      return fail(401, { detail: '未登录' });
    });
    const { router } = renderApp('/login', { user: null });
    await screen.findByRole('heading', { name: '登录' });

    await userEvent.type(screen.getByLabelText('账号或邮箱'), 'learner_a');
    await userEvent.type(screen.getByLabelText('密码'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('账号、邮箱或密码错误');
    expect(router.state.location.pathname).toBe('/login');
  });

  it('restores the session and returns the visitor to the route that sent them here', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/login') {
        signedIn = true;
        return ok({ message: '登录成功', user: SESSION_USER });
      }
      return ok({ user: SESSION_USER });
    });

    const { router } = renderApp('/login?returnTo=%2Fexam%2Fcs408%2Fpractice', { user: null });
    await screen.findByRole('heading', { name: '登录' });

    await userEvent.type(screen.getByLabelText('账号或邮箱'), 'learner_a');
    await userEvent.type(screen.getByLabelText('密码'), 'correct-password');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/practice'));
  });

  it('falls back to Home when the requested destination left this origin', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/login') {
        signedIn = true;
        return ok({ message: '登录成功', user: SESSION_USER });
      }
      return ok({ user: SESSION_USER });
    });

    const { router } = renderApp('/login?returnTo=%2F%2Fevil.example', { user: null });
    await screen.findByRole('heading', { name: '登录' });

    await userEvent.type(screen.getByLabelText('账号或邮箱'), 'learner_a');
    await userEvent.type(screen.getByLabelText('密码'), 'correct-password');
    await userEvent.click(screen.getByRole('button', { name: '登录' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
  });
});

describe('register page', () => {
  it('verifies the email before it offers account fields, and validates what it asks for', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/auth/register/send-code') return ok({ message: '验证码已发送' });
      if (url === '/auth/register/verify-code') return ok({ message: '邮箱验证成功' });
      if (url === '/register') {
        signedIn = true;
        return ok({ message: '注册成功', user: SESSION_USER });
      }
      return ok({ user: SESSION_USER });
    });

    const { router } = renderApp('/register', { user: null });
    await screen.findByRole('heading', { name: '注册' });

    // Step 1 validates before contacting the server.
    await userEvent.click(screen.getByRole('button', { name: '验证邮箱' }));
    expect(await screen.findByText('请输入邮箱地址')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalledWith('/auth/register/verify-code', expect.anything());

    // A malformed address is refused with the same rule the backend applies.
    await userEvent.type(screen.getByLabelText('邮箱'), 'not-an-email');
    await userEvent.click(screen.getByRole('button', { name: '验证邮箱' }));
    expect(await screen.findByText('请输入有效的邮箱地址')).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText('邮箱'));
    await userEvent.type(screen.getByLabelText('邮箱'), 'learner@example.com');
    await userEvent.click(screen.getByRole('button', { name: '发送验证码' }));
    expect(await screen.findByRole('status')).toHaveTextContent('验证码已发送');

    await userEvent.type(screen.getByLabelText('邮箱验证码'), '123456');
    await userEvent.click(screen.getByRole('button', { name: '验证邮箱' }));

    // The account fields only exist once the address is proven.
    expect(await screen.findByLabelText('账号')).toBeInTheDocument();
    expect(screen.getByText(/邮箱 learner@example\.com 已验证/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '创建账号' }));
    expect(await screen.findByText('请输入账号')).toBeInTheDocument();
    expect(await screen.findByText('密码至少需要 6 位')).toBeInTheDocument();
    expect(await screen.findByText('请再次输入密码')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('账号'), 'learner_b');
    await userEvent.type(screen.getByLabelText('密码'), 'a-good-password');
    await userEvent.type(screen.getByLabelText('确认密码'), 'a-typo-password');
    await userEvent.click(screen.getByRole('button', { name: '创建账号' }));

    // A mistyped confirmation is caught here: the request carries one password, so the server
    // has nothing to compare it against and the account would be unusable if this got through.
    expect(await screen.findByText('两次输入的密码不一致')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalledWith('/register', expect.anything());

    await userEvent.clear(screen.getByLabelText('确认密码'));
    await userEvent.type(screen.getByLabelText('确认密码'), 'a-good-password');
    await userEvent.click(screen.getByRole('button', { name: '创建账号' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/register', {
        body: { username: 'learner_b', password: 'a-good-password', email: 'learner@example.com' },
      }),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
  });
});
