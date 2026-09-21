import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: post, PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const fail = (status: number, detail: unknown) => ({
  data: undefined,
  error: { detail },
  response: { ok: false, status },
});

let stored: Record<string, unknown> = {};

beforeEach(() => {
  stored = {
    service_key: 'programming',
    onboarding_completed: false,
    plan: 'free',
    main_language: '',
    selected_languages: [],
    level: '',
    problems: [],
  };
  get.mockReset();
  post.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === '/me') return ok({ user: { id: 1, username: 'test_learner', nickname: '测试学习者' } });
    if (url === '/programming/onboarding') return ok(stored);
    if (url === '/programming/home') return ok({});
    if (url === '/learning/agenda' || url === '/learning/agenda/explain') return ok({ items: [], total_items: 0 });
    if (url === '/learning-records') return ok({ records: [], has_more: false, next_cursor: null });
    if (url === '/review/summary') return ok({ total: 0, has_stored_due_dates: false });
    throw new Error(`unexpected GET ${url}`);
  });
  post.mockImplementation(async () => ok({ message: 'programming onboarding saved', onboarding: stored }));
});

describe('programming setup', () => {
  it('offers exactly the languages the runner can execute', async () => {
    renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    for (const language of ['C', 'C++', 'Python', 'Java']) {
      expect(screen.getByRole('checkbox', { name: language })).toBeInTheDocument();
    }
    expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(4);
  });

  it('will not save a context with no language, and says why', async () => {
    renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    expect(screen.getByText('请至少选择一种练习语言。')).toBeInTheDocument();
    expect(screen.getByText('请选择当前水平。')).toBeInTheDocument();
    // The warnings are statements about the form, and the form still submits: the endpoint owns
    // the refusal, and repeating its rules here would be a second opinion.
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/programming/onboarding',
        expect.objectContaining({ body: expect.objectContaining({ selected_languages: [] }) }),
      ),
    );
  });

  it('saves the canonical language name and the stable level key', async () => {
    renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    await userEvent.click(screen.getByRole('checkbox', { name: 'C++' }));
    await userEvent.click(screen.getByRole('radio', { name: '基础' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Debug / 定位错误困难' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/programming/onboarding', {
        body: {
          main_language: 'C++',
          selected_languages: ['C++'],
          level: 'basic',
          problems: ['debugging'],
          plan: 'free',
          onboarding_completed: true,
        },
      }),
    );
  });

  it('echoes the stored plan back instead of resetting it', async () => {
    // With `onboarding_completed: true` the endpoint takes the request's plan as the new one, so
    // omitting it would move a paid learner onto `free` without saying so.
    stored = { ...stored, plan: 'quarterly', selected_languages: ['Python'], main_language: 'Python', level: 'beginner', onboarding_completed: true };
    renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    await userEvent.click(screen.getByRole('checkbox', { name: 'Java' }));
    await userEvent.click(screen.getByRole('button', { name: '保存设置' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/programming/onboarding',
        expect.objectContaining({ body: expect.objectContaining({ plan: 'quarterly' }) }),
      ),
    );
  });

  it('reports a stored language the runner cannot execute rather than dropping it quietly', async () => {
    stored = {
      ...stored,
      main_language: 'JavaScript',
      selected_languages: ['JavaScript'],
      level: 'basic',
      onboarding_completed: true,
    };
    renderApp('/programming/setup');

    expect(await screen.findByText(/平台无法运行的语言：JavaScript/)).toBeInTheDocument();
    // It is not offered as a choice — the selectable languages are the executable four, and it
    // is not among them — so the only way it could survive the save is by being carried silently.
    expect(screen.queryByRole('checkbox', { name: 'JavaScript' })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Java' })).not.toBeChecked();
  });

  it('opens on the stored context and shows it as the current saved state', async () => {
    stored = {
      ...stored,
      main_language: 'Python',
      selected_languages: ['Python', 'Java'],
      level: 'advanced',
      problems: ['ds_algo_weak'],
      onboarding_completed: true,
    };
    renderApp('/programming/setup');

    expect(await screen.findByRole('checkbox', { name: 'Python' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Java' })).toBeChecked();
    expect(screen.getByRole('radio', { name: '进阶' })).toBeChecked();

    const current = screen.getByRole('region', { name: '当前保存的设置' });
    expect(current).toHaveTextContent('Python、Java');
    expect(current).toHaveTextContent('进阶');
  });

  // The stored level is a key from the API's enum. A key this build has no label for is a
  // setting the product cannot name — and naming it by its raw key would put the backend's
  // vocabulary in front of the learner as if it were their own word.
  it('says an unrecognised stored level is unset rather than printing the stored key', async () => {
    stored = {
      ...stored,
      main_language: 'Python',
      selected_languages: ['Python'],
      level: 'silver_iii',
      onboarding_completed: true,
    };
    renderApp('/programming/setup');

    const current = await screen.findByRole('region', { name: '当前保存的设置' });
    expect(current).toHaveTextContent('未设置');
    expect(current).not.toHaveTextContent('silver_iii');
  });

  it('surfaces the server’s refusal', async () => {
    post.mockImplementation(async () => fail(400, { detail: '请选择当前水平' }));
    renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    await userEvent.click(screen.getByRole('checkbox', { name: 'Python' }));
    await userEvent.click(screen.getByRole('radio', { name: '入门' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    expect(await screen.findByText('请选择当前水平')).toBeInTheDocument();
  });

  it('goes back to the space it was opened from', async () => {
    const { router } = renderApp('/programming/setup');
    await screen.findByRole('group', { name: /练习语言/ });

    await userEvent.click(screen.getByRole('checkbox', { name: 'Python' }));
    await userEvent.click(screen.getByRole('radio', { name: '零基础' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/programming'));
  });

  it('returns to a requested destination instead, and never off this origin', async () => {
    const first = renderApp('/programming/setup?returnTo=%2Fprofile');
    await screen.findByRole('group', { name: /练习语言/ });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Python' }));
    await userEvent.click(screen.getByRole('radio', { name: '入门' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    await waitFor(() => expect(first.router.state.location.pathname).toBe('/profile'));
    first.unmount();

    // A protocol-relative target is dropped by the route's validator before the page sees it.
    const second = renderApp('/programming/setup?returnTo=%2F%2Fevil.example');
    await screen.findByRole('group', { name: /练习语言/ });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Python' }));
    await userEvent.click(screen.getByRole('radio', { name: '入门' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    await waitFor(() => expect(second.router.state.location.pathname).toBe('/programming'));
  });
});
