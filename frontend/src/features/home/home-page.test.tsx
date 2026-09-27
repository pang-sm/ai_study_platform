import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp, TEST_USER } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

function agendaItem(overrides: Record<string, unknown>) {
  return {
    action_type: 'review',
    service_namespace: 'exam_prep',
    domain_context: {},
    source_type: 'wrong_answer',
    source_id: '1',
    title: '错题 · 数据结构',
    summary: '累计做错 5 次，尚未订正',
    priority_reason: 'repeated_wrong',
    deep_link: '/exam/cs408/wrong?module=data_structure',
    due_at: null,
    facts: { wrong_count: 5, review_reason: 'wrong_answer_active' },
    status: 'needs_attention',
    resolved_by: 'review_completion',
    ...overrides,
  };
}

/** One item per shape the agenda can return, in the order the backend would rank them. */
const AGENDA = {
  policy_version: 'agenda_policy_v1',
  generated_at: '2026-09-25T10:00:00+00:00',
  items: [
    agendaItem({ domain_context: { exam_module_id: 'data_structure' } }),
    agendaItem({
      service_namespace: 'programming',
      domain_context: { language: 'C', exercise_id: 11 },
      source_type: 'programming_exercise',
      source_id: '11',
      title: '设备序列号校验',
      summary: '标记为需要加强',
      priority_reason: 'needs_work',
      deep_link: '/programming/C/exercises/11',
      facts: { personal_status: 'needs_work', passed_count: 2, total_count: 5 },
    }),
    agendaItem({
      service_namespace: 'programming',
      domain_context: { language: 'C', exercise_id: 12 },
      source_type: 'programming_exercise',
      source_id: '12',
      title: '首个独特字符',
      summary: '标记为需要加强',
      priority_reason: 'needs_work',
      deep_link: '/programming/C/exercises/12',
      facts: { personal_status: 'needs_work' },
    }),
    agendaItem({
      service_namespace: 'programming',
      domain_context: { language: 'Python', exercise_id: 13 },
      source_type: 'programming_exercise',
      source_id: '13',
      title: '设备序列号校验',
      summary: '标记为需要加强',
      priority_reason: 'needs_work',
      deep_link: '/programming/Python/exercises/13',
      facts: { personal_status: 'needs_work' },
    }),
    agendaItem({
      action_type: 'plan_task',
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: 'operating_system' },
      source_type: 'plan_task',
      source_id: '9',
      title: '操作系统真题一套',
      summary: '计划内任务（无截止日期）',
      priority_reason: 'current_plan_task',
      deep_link: '/exam/cs408/plan',
      facts: { status: 'open', task_type: 'review' },
      status: 'open',
    }),
  ],
  total_items: 5,
  source_summary: { plan_tasks: 1, review_items: 4, adaptive_candidates: 0, unattributable_plan_tasks: 0, deduplicated: 0 },
  by_namespace: { exam_prep: 2, programming: 3 },
  by_reason: { repeated_wrong: 1, needs_work: 3, current_plan_task: 1 },
  priority_order: ['overdue_plan_task', 'due_review', 'repeated_wrong', 'needs_work'],
  filters: {},
  semantics: 'ranked by the fixed ladder',
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
    throw new Error(`unexpected GET ${url}`);
  });
}

beforeEach(() => {
  get.mockReset();
  respondWith();
});

describe('home page', () => {
  it('greets the learner by name and states the one thing to do now', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [] }) });
    renderApp('/');

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('测试学习者');
    // The greeting is the whole header: the page goes straight to the task from there.
    expect(screen.queryByText(/根据你的学习记录/)).not.toBeInTheDocument();

    const focus = await screen.findByRole('region', { name: '现在先做' });
    // The order is stated by a section heading of the page's own kind, and the task it holds is
    // named *under* it — a level deeper, never competing with it.
    expect(within(focus).getByRole('heading', { name: '现在先做' })).toBeInTheDocument();
    expect(
      within(focus).getByRole('heading', { level: 3, name: '错题 · 数据结构' }),
    ).toBeInTheDocument();
    expect(within(focus).getByText('考研学习 · 数据结构')).toBeInTheDocument();
    expect(within(focus).getByText('这道内容已经做错 5 次，建议优先完成订正。')).toBeInTheDocument();
    expect(within(focus).getByText('错 5 次')).toBeInTheDocument();
    expect(within(focus).getByText('未订正')).toBeInTheDocument();
    expect(within(focus).getByRole('link', { name: /继续学习/ })).toHaveAttribute(
      'href',
      '/exam/cs408/wrong?module=data_structure',
    );
  });

  it('says its reason in one sentence, and stacks no second layer of explanation under it', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [] }) });
    const { container } = renderApp('/');

    const focus = await screen.findByRole('region', { name: '现在先做' });
    // The card answers "what now". Everything a learner might want to interrogate about it is
    // on the surface that owns the item, not folded into the home page.
    expect(within(focus).queryByText('为什么推荐？')).not.toBeInTheDocument();
    expect(focus.querySelector('details')).toBeNull();
    expect(within(focus).queryByText(/智学AI会持续记录/)).not.toBeInTheDocument();

    // The rule text the backend writes for engineers names payload fields. None of it, and none
    // of the item's own machine fields, may reach the learner.
    const text = container.textContent ?? '';
    for (const internal of [
      'wrong_count',
      'task_type',
      'due_source',
      'review_reason',
      'policy_version',
      'agenda_policy_v1',
      'needs_attention',
      'repeated_wrong',
      'current_plan_task',
      'review_completion',
      'data_structure',
      'exercise_id',
    ]) {
      expect(text, `home must not show ${internal}`).not.toContain(internal);
    }
  });

  it('lists the rest of the agenda compactly, telling same-named exercises apart by language', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [] }) });
    renderApp('/');

    const list = await screen.findByRole('region', { name: '今天接下来' });
    // Await the rows, not the section: the section exists while the agenda is still loading, and
    // asserting against that first frame is how a page that renders nothing looks like a pass.
    const rows = await within(list).findAllByRole('listitem');
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent('设备序列号校验');
    expect(rows[0]).toHaveTextContent('C · 标记为需要加强');
    expect(rows[1]).toHaveTextContent('首个独特字符');
    // The same exercise title, in a different language, is a different task — and the row says so.
    expect(rows[2]).toHaveTextContent('设备序列号校验');
    expect(rows[2]).toHaveTextContent('Python · 标记为需要加强');
    // The promoted item is promoted once: the list continues from the second entry.
    expect(within(list).queryByText('错题 · 数据结构')).not.toBeInTheDocument();
    expect(within(rows[0] as HTMLElement).getByRole('link')).toHaveAttribute(
      'href',
      '/programming/C/exercises/11',
    );
  });

  it('asks for the rest of a longer agenda rather than growing the page', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [] }) });
    renderApp('/');

    const list = await screen.findByRole('region', { name: '今天接下来' });
    expect(await within(list).findAllByRole('listitem')).toHaveLength(3);
    expect(within(list).getByRole('button', { name: '还有 1 项' })).toBeInTheDocument();
  });

  it('names an exercise by its reference only when two rows would otherwise read identically', async () => {
    respondWith({
      '/exam/prep/profile': ok({ configured: true, subjects: [] }),
      '/learning/agenda': ok({
        ...AGENDA,
        items: [
          AGENDA.items[0],
          agendaItem({
            service_namespace: 'programming',
            domain_context: { language: 'C', exercise_id: 21 },
            source_type: 'programming_exercise',
            source_id: '21',
            title: '两数之和',
            summary: '标记为需要加强',
            priority_reason: 'needs_work',
            facts: { personal_status: 'needs_work' },
          }),
          agendaItem({
            service_namespace: 'programming',
            domain_context: { language: 'C', exercise_id: 22 },
            source_type: 'programming_exercise',
            source_id: '22',
            title: '两数之和',
            summary: '标记为需要加强',
            priority_reason: 'needs_work',
            facts: { personal_status: 'needs_work' },
          }),
        ],
      }),
    });
    renderApp('/');

    const list = await screen.findByRole('region', { name: '今天接下来' });
    expect(await within(list).findByText('C · 标记为需要加强 · #21')).toBeInTheDocument();
    expect(within(list).getByText('C · 标记为需要加强 · #22')).toBeInTheDocument();
  });

  it('says what is empty instead of inventing work, and still leads into every direction', async () => {
    respondWith({
      '/exam/prep/profile': ok({ configured: true, subjects: [{ id: 'cs_408', display_name: '计算机学科专业基础' }] }),
      '/learning/agenda': ok({ ...AGENDA, items: [], total_items: 0 }),
    });
    renderApp('/');

    expect(await screen.findByText('今天暂时没有需要优先处理的学习任务。')).toBeInTheDocument();
    expect(screen.queryByText('现在先做')).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '今天接下来' })).not.toBeInTheDocument();

    const spaces = screen.getByRole('region', { name: '我的学习方向' });
    expect(await within(spaces).findByText('备考：计算机学科专业基础')).toBeInTheDocument();
    expect(within(spaces).getAllByRole('link').map((link) => link.getAttribute('href')))
      .toEqual(['/exam', '/course', '/programming']);
  });

  it('reports a failed agenda read as a failure, never as a day with nothing in it', async () => {
    respondWith({
      '/exam/prep/profile': ok({ configured: true, subjects: [] }),
      '/learning/agenda': { data: undefined, error: { detail: 'x' }, response: { ok: false, status: 500 } },
    });
    renderApp('/');

    expect(await screen.findByText(/今天的学习建议暂时读不到/)).toBeInTheDocument();
    expect(screen.queryByText('今天暂时没有需要优先处理的学习任务。')).not.toBeInTheDocument();
    // ...and the directions are still reachable, because one failed read is not an outage.
    expect(screen.getByRole('region', { name: '我的学习方向' })).toBeInTheDocument();
  });

  it('leaves the learning log, and the way to it, to the destinations in the header', async () => {
    respondWith({ '/exam/prep/profile': ok({ configured: true, subjects: [] }) });
    renderApp('/');

    const list = await screen.findByRole('region', { name: '今天接下来' });
    await within(list).findAllByRole('listitem');
    expect(screen.queryByRole('region', { name: '最近学习' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '去别的学习方向' })).not.toBeInTheDocument();
    // 学习报告 is a destination in the header on every screen; a second copy of it beside the
    // tasks competed with them, so the section carries no link of its own.
    expect(within(list).queryByRole('link', { name: /学习报告/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: '学习报告' }).length).toBeGreaterThan(0);
  });

  it('names what each direction opens from the context that direction actually holds', async () => {
    respondWith({
      '/course-learning/courses': ok([{ course_id: 'data_structure', course_name: '数据结构' }]),
      '/exam/prep/profile': ok({ configured: true, subjects: [{ id: 'cs_408', display_name: '计算机学科专业基础' }] }),
      '/programming/onboarding': ok({ main_language: 'C', selected_languages: ['C'], onboarding_completed: true }),
    });
    renderApp('/');

    const spaces = await screen.findByRole('region', { name: '我的学习方向' });
    expect(await within(spaces).findByRole('link', { name: /进入备考/ })).toHaveAttribute('href', '/exam');
    expect(within(spaces).getByRole('link', { name: /查看课程/ })).toHaveAttribute('href', '/course');
    expect(within(spaces).getByRole('link', { name: /继续 C 编程/ })).toHaveAttribute(
      'href',
      '/programming',
    );
  });

  it('promises nothing a direction without a context cannot confirm', async () => {
    // No space declares anything, and one read fails outright. Neither may be answered with a
    // wording that claims the learner has something set up.
    respondWith({
      '/programming/onboarding': { data: undefined, error: { detail: 'x' }, response: { ok: false, status: 500 } },
    });
    renderApp('/');

    const spaces = await screen.findByRole('region', { name: '我的学习方向' });
    expect(await within(spaces).findByRole('link', { name: /开始专业学习/ })).toBeInTheDocument();
    expect(within(spaces).getByRole('link', { name: /开始备考/ })).toBeInTheDocument();
    expect(within(spaces).getByRole('link', { name: /进入编程学习/ })).toBeInTheDocument();
    expect(within(spaces).queryByRole('link', { name: /继续 .* 编程/ })).not.toBeInTheDocument();
  });
});

/**
 * The first-run matrix. "Configured" is a statement about each direction's own context, so each
 * case below configures exactly one and asserts the start prompt is gone. The legacy
 * account-level flag is held at `needs_onboarding: true` throughout, because it is precisely the
 * flag that used to keep the prompt on screen after a learner had already set themselves up.
 */
describe('first-run home', () => {
  const firstRun = { name: '设置任意一个方向，就可以开始学习。' };
  const neverSetUp = { ...TEST_USER, onboarding_completed: false, needs_onboarding: true };

  it('asks a learner with no direction configured to set one up, and promotes nothing', async () => {
    renderApp('/', { user: neverSetUp });

    const start = await screen.findByRole('region', firstRun);
    expect(within(start).getAllByRole('link')).toHaveLength(3);
    expect(screen.queryByText('现在先做')).not.toBeInTheDocument();
  });

  it('leaves first-run behind as soon as one direction holds a context', async () => {
    respondWith({ '/course-learning/courses': ok([{ course_id: 'data_structure', course_name: '数据结构' }]) });
    renderApp('/', { user: neverSetUp });

    await screen.findByText('现在先做');
    expect(screen.queryByRole('region', firstRun)).not.toBeInTheDocument();
  });

  it('does not treat a failed direction read as an unconfigured direction', async () => {
    respondWith({
      '/exam/prep/profile': { data: undefined, error: { detail: 'x' }, response: { ok: false, status: 500 } },
    });
    renderApp('/', { user: neverSetUp });

    const start = await screen.findByRole('region', firstRun);
    expect(within(start).getByText(/暂时读不到这个方向的设置/)).toBeInTheDocument();
  });

  it('says a direction’s status is unreadable rather than showing it as empty', async () => {
    respondWith({
      '/course-learning/courses': ok([{ course_id: 'data_structure', course_name: '数据结构' }]),
      '/programming/onboarding': {
        data: undefined,
        error: { detail: 'x' },
        response: { ok: false, status: 500 },
      },
    });
    renderApp('/');

    const spaces = await screen.findByRole('region', { name: '我的学习方向' });
    expect(await within(spaces).findByText('课程：数据结构')).toBeInTheDocument();
    expect(within(spaces).getByText('暂时读不到这个方向的状态。')).toBeInTheDocument();
  });
});
