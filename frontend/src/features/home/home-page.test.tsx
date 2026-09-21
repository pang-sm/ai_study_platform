import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp, TEST_USER } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

const AGENDA = {
  policy_version: 'v1',
  generated_at: '2026-09-20T10:00:00+00:00',
  items: [
    {
      action_type: 'review',
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: 'data_structure' },
      source_type: 'review',
      source_id: 'r-1',
      title: '复习线性表',
      summary: '到期复习项',
      priority_reason: 'due_review',
      deep_link: '/review',
      due_at: null,
      facts: { interval_days: 3 },
      status: 'open',
      resolved_by: 'review_completion',
    },
  ],
  total_items: 1,
  source_summary: { plan_tasks: 0, review_items: 1, adaptive_candidates: 0, unattributable_plan_tasks: 0, deduplicated: 0 },
  by_namespace: { exam_prep: 1 },
  by_reason: { due_review: 1 },
  priority_order: ['overdue_plan_task', 'due_review'],
  filters: {},
  semantics: 'ranked by the fixed ladder',
};

const RECORDS = {
  records: [
    {
      event_id: '11111111-1111-5111-8111-111111111111',
      event_type: 'review_completed',
      record_category: 'ReviewEvent',
      service_namespace: 'exam_prep',
      occurred_at: '2026-09-20T08:30:00+00:00',
      source: { type: 'review_item', id: 'r-0' },
      summary: { status: 'done' },
    },
    {
      event_id: '22222222-2222-5222-8222-222222222222',
      event_type: 'some_future_family',
      record_category: 'PracticeEvent',
      service_namespace: 'course_learning',
      occurred_at: null,
      source: { type: 'attempt', id: 'a-1' },
      summary: null,
    },
  ],
  has_more: false,
  next_cursor: null,
};

/** Empty by default: these are the three reads that decide whether the page is first-run. */
const EMPTY_SPACES: Record<string, unknown> = {
  '/course-learning/courses': ok([]),
  '/exam/prep/profile': ok({ configured: false, subjects: [] }),
  '/programming/onboarding': ok({ main_language: '', selected_languages: [] }),
};

function respondWith(overrides: Record<string, unknown> = {}) {
  get.mockImplementation(async (url: string) => {
    if (url in overrides) return overrides[url];
    if (url in EMPTY_SPACES) return EMPTY_SPACES[url];
    if (url === '/learning/agenda') return ok(AGENDA);
    if (url === '/learning/agenda/explain') {
      return ok({ priority_rules: { due_review: '复习项已到期（存储或策略计算的到期日）' } });
    }
    if (url === '/review/summary') return ok({ total: 1, has_stored_due_dates: true });
    if (url === '/learning-records') return ok(RECORDS);
    if (url === '/subscription') return ok({ tier: 'free', policy_version: 'v1' });
    if (url === '/subscription/plans') {
      return ok({ policy_version: 'v1', plans: { free: { label: '免费版', daily_budget: 5, weekly_budget: 25, capabilities: [] } } });
    }
    if (url === '/usage/summary') {
      return ok({
        tier: 'free',
        periods: {
          daily: { budget: 5, reserved: 0, settled: 1, remaining: 4 },
          weekly: { budget: 25, reserved: 0, settled: 6, remaining: 19 },
        },
      });
    }
    throw new Error(`unexpected GET ${url}`);
  });
}

beforeEach(() => {
  get.mockReset();
  respondWith();
});

describe('home page', () => {
  it('renders the agenda item with the server’s own rule and the backend deep link', async () => {
    renderApp('/');

    expect(await screen.findByText('复习线性表')).toBeInTheDocument();
    expect(screen.getByText(/复习项已到期/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '打开并完成这项学习' })).toHaveAttribute(
      'href',
      '/review',
    );
  });

  it('reports the review queue and the real membership position', async () => {
    renderApp('/');

    const review = await screen.findByRole('region', { name: '待复习' });
    expect(await within(review).findByText('待处理：1')).toBeInTheDocument();

    expect(await screen.findByText('免费版')).toBeInTheDocument();
    expect(screen.getByText(/今日剩余额度：4/)).toBeInTheDocument();
  });

  it('labels known study events and falls back to the raw code for an unknown one', async () => {
    renderApp('/');

    const recent = await screen.findByRole('region', { name: '最近学习' });
    expect(await within(recent).findByText('完成复习')).toBeInTheDocument();
    // An unmapped event type shows as itself rather than as a guess.
    expect(within(recent).getByText('some_future_family')).toBeInTheDocument();
    expect(within(recent).getAllByText(/时间未记录/)).toHaveLength(1);
  });

  it('states the real empty conditions instead of inventing tasks or history', async () => {
    respondWith({
      '/learning/agenda': ok({ ...AGENDA, items: [], total_items: 0 }),
      '/learning-records': ok({ records: [], has_more: false, next_cursor: null }),
    });
    renderApp('/');

    expect(await screen.findByText('当前没有需要优先处理的学习任务。')).toBeInTheDocument();
    expect(
      await screen.findByText(/还没有学习记录。完成一次练习、复习或编程提交后/),
    ).toBeInTheDocument();
  });

  it('asks for a learning context, per space, only when no space has one', async () => {

    renderApp('/', { user: { ...TEST_USER, onboarding_completed: false, needs_onboarding: true } });

    const start = await screen.findByRole('region', {
      name: '先建立一个学习空间，智学AI才能为你形成真实学习安排。',
    });
    // Each space leads to the setup flow that actually establishes its context, and each one is
    // asked to come back here once it has.
    expect(within(start).getByRole('link', { name: '设置课程' })).toHaveAttribute(
      'href',
      '/course/setup?returnTo=%2F',
    );
    expect(within(start).getByRole('link', { name: '设置备考' })).toHaveAttribute(
      'href',
      '/exam/setup?returnTo=%2F',
    );
    expect(within(start).getByRole('link', { name: '设置编程学习' })).toHaveAttribute(
      'href',
      '/programming/setup?returnTo=%2F',
    );
  });

  it('treats one configured space as enough, whatever the legacy account flag says', async () => {
    // `needs_onboarding` is an account-level flag only one legacy route clears; a learner with a
    // declared course is set up, and the home page must stop asking.
    respondWith({ '/course-learning/courses': ok([{ id: 'data-structure', name: '数据结构' }]) });
    renderApp('/', { user: { ...TEST_USER, onboarding_completed: false, needs_onboarding: true } });

    await screen.findByText('复习线性表');
    expect(
      screen.queryByRole('region', { name: '先建立一个学习空间，智学AI才能为你形成真实学习安排。' }),
    ).not.toBeInTheDocument();
  });

  it('does not show the first-user prompt to a learner who has finished setup', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [{ id: 'cs408' }] }) });
    renderApp('/');

    await screen.findByText('复习线性表');
    expect(
      screen.queryByRole('region', { name: '先建立一个学习空间，智学AI才能为你形成真实学习安排。' }),
    ).not.toBeInTheDocument();
  });

  it('reports an empty agenda as an empty agenda, never as a first-run prompt', async () => {
    // The learner has a course, so setup is behind them. What is empty is today's agenda, and
    // sending them back to "set yourself up" would be asking for something already done.
    respondWith({
      '/course-learning/courses': ok([{ id: 'data-structure', name: '数据结构' }]),
      '/learning/agenda': ok({ ...AGENDA, items: [], total_items: 0 }),
    });
    renderApp('/');

    expect(await screen.findByText('当前没有需要优先处理的学习任务。')).toBeInTheDocument();
    expect(
      screen.queryByRole('region', { name: '先建立一个学习空间，智学AI才能为你形成真实学习安排。' }),
    ).not.toBeInTheDocument();
  });
});

/**
 * The first-run matrix, one row at a time.
 *
 * "Configured" is a statement about each space's own context, so each case below configures
 * exactly one and asserts the surface is gone. The legacy account-level flag is held at
 * `needs_onboarding: true` throughout, because it is precisely the flag that used to keep the
 * prompt on screen after a learner had already set themselves up.
 */
describe('first-run home', () => {
  const firstRun = { name: '先建立一个学习空间，智学AI才能为你形成真实学习安排。' };
  const neverSetUp = { ...TEST_USER, onboarding_completed: false, needs_onboarding: true };

  it('shows the surface when no space has a context, with the three real entries', async () => {
    respondWith();
    renderApp('/', { user: neverSetUp });

    const start = await screen.findByRole('region', firstRun);
    for (const label of ['课程学习', '11408 考研学习', '编程学习']) {
      expect(within(start).getByText(label)).toBeInTheDocument();
    }
    expect(within(start).getAllByRole('link')).toHaveLength(3);
  });

  it('leaves first-run behind as soon as one space is configured — course', async () => {
    respondWith({ '/course-learning/courses': ok([{ course_id: 'data_structure', course_name: '数据结构' }]) });
    renderApp('/', { user: neverSetUp });

    await screen.findByText('复习线性表');
    expect(screen.queryByRole('region', firstRun)).not.toBeInTheDocument();
  });

  it('leaves first-run behind as soon as one space is configured — exam', async () => {
    respondWith({
      '/exam/prep/profile': ok({ configured: true, subjects: [{ id: 'cs_408' }] }),
    });
    renderApp('/', { user: neverSetUp });

    await screen.findByText('复习线性表');
    expect(screen.queryByRole('region', firstRun)).not.toBeInTheDocument();
  });

  it('leaves first-run behind as soon as one space is configured — programming', async () => {
    respondWith({
      '/programming/onboarding': ok({ main_language: 'Python', selected_languages: ['Python'], onboarding_completed: true }),
    });
    renderApp('/', { user: neverSetUp });

    await screen.findByText('复习线性表');
    expect(screen.queryByRole('region', firstRun)).not.toBeInTheDocument();
  });

  it('promotes the agenda once a space exists, and does not ask for setup again', async () => {
    respondWith({ '/course-learning/courses': ok([{ course_id: 'data_structure', course_name: '数据结构' }]) });
    renderApp('/', { user: neverSetUp });

    // The server's own first item becomes the page's focal action — the first-run surface and the
    // focal agenda item are alternatives, never both.
    expect(await screen.findByRole('region', { name: '复习线性表' })).toBeInTheDocument();
    expect(screen.queryByRole('region', firstRun)).not.toBeInTheDocument();
  });

  it('does not treat a failed space read as an unconfigured space', async () => {
    respondWith({ '/exam/prep/profile': { data: undefined, error: { detail: 'x' }, response: { ok: false, status: 500 } } });
    renderApp('/', { user: neverSetUp });

    // One space could not be read and the other two answered empty. The page says so rather than
    // presenting a confident "you have nothing set up", which it cannot know.
    const start = await screen.findByRole('region', firstRun);
    expect(within(start).getByText(/暂时无法读取这个学习空间的状态/)).toBeInTheDocument();
  });
});
