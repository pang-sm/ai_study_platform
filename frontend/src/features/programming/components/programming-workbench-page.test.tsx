import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

/**
 * 编程工作台, checked against what it is supposed to be: a workbench, not an index of doors.
 *
 * The page's whole promise is an ORDER — the work first, the ways in afterwards — so most of what
 * these cases assert is relative position and provenance: that the first screen names a task the
 * learner can act on, that the task came from this space's own rows of the agenda rather than
 * another space's, and that a language is offered as a direction rather than as a navigation bar.
 */

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

/** One agenda row, with only the fields the page reads. */
function agendaItem(overrides: Record<string, unknown>) {
  return {
    action_type: 'exercise',
    service_namespace: 'programming',
    domain_context: { language: 'Python' },
    source_type: 'programming_exercise',
    source_id: '7',
    title: '两数之和',
    summary: '',
    priority_reason: 'needs_work',
    deep_link: '/programming/Python/exercises/7',
    facts: {},
    status: 'open',
    ...overrides,
  };
}

const AGENDA = {
  items: [
    agendaItem({ facts: { personal_status: 'needs_work' } }),
    agendaItem({ source_id: '9', title: '判断回文数', priority_reason: 'unseen_coverage' }),
    // Another space's row: present in the payload the personal home reads, and not this page's.
    {
      action_type: 'review',
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: 'data_structure' },
      source_type: 'wrong_answer',
      source_id: '3',
      title: '操作系统真题订正',
      summary: '',
      priority_reason: 'due_review',
      deep_link: '/exam/cs408/wrong',
      facts: {},
      status: 'open',
    },
  ],
  total_items: 3,
  source_summary: { wrong_answer: 1, programming_exercise: 2 },
  by_namespace: { programming: 2, exam_prep: 1 },
};

const ONBOARDING = { main_language: 'Python', selected_languages: ['Python'], onboarding_completed: true };

function mockProgrammingHome(programming: Record<string, unknown> = {}) {
  get.mockImplementation(async (url: string) => {
    if (url === '/course-learning/courses') return ok([]);
    if (url === '/exam/prep/profile') return ok({ configured: false, subjects: [] });
    if (url === '/programming/onboarding') return ok(programming);
    if (url === '/programming/home') {
      return ok({
        stats: {
          streak_days: 3,
          momentum: '今日已学习',
          today_practice_count: 2,
          today_submission_count: 1,
          last_activity_date: '2026-09-30',
        },
      });
    }
    if (url === '/learning/agenda') return ok(AGENDA);
    if (url === '/programming/exercises') {
      return ok({
        items: [
          { id: 7, title: '两数之和', difficulty: '入门', source_label: '原创题目', personal_progress: { last_submit_at: '2026-09-30T08:00:00Z', last_submit_passed: false } },
        ],
        total: 60,
        total_pages: 5,
      });
    }
    if (url === '/adaptive/practice') return ok({ candidates: [], reasons: {} });
    throw new Error(`unexpected GET ${url}`);
  });
}

beforeEach(() => {
  get.mockReset();
});

describe('编程工作台 · 今日任务', () => {
  it('leads with a task from this space and leaves another space’s row out', async () => {
    mockProgrammingHome(ONBOARDING);
    renderApp('/programming');

    const today = await screen.findByRole('region', { name: '今日任务' });
    // The focal item is the space's own first row, stated in the words its facts support.
    expect(await within(today).findByRole('heading', { name: '两数之和' })).toBeInTheDocument();
    expect(within(today).getByText('这个练习被标记为需要加强，建议重新做一遍。')).toBeInTheDocument();
    expect(within(today).getByText('编程学习 · Python')).toBeInTheDocument();

    // The rest of the agenda is listed, and the exam row is not: 考研学习 has its own home.
    expect(within(today).getByText('判断回文数')).toBeInTheDocument();
    expect(within(today).queryByText('操作系统真题订正')).not.toBeInTheDocument();
  });

  it('opens the focal task at the address it now lives at, not the one the server still sends', async () => {
    mockProgrammingHome(ONBOARDING);
    renderApp('/programming');

    const action = await screen.findByRole('link', { name: /继续学习/ });
    // The backend still builds `/programming/Python/exercises/7`; the page maps it, so the learner
    // navigates inside the app instead of reloading onto a redirect.
    expect(action).toHaveAttribute('href', expect.stringContaining('/programming/practice/7'));
    expect(action).toHaveAttribute('href', expect.stringContaining('language=python'));
  });

  it('falls back to the exercise last worked on when the agenda has nothing for this space', async () => {
    get.mockImplementation(async (url: string) => {
      if (url === '/course-learning/courses') return ok([]);
      if (url === '/exam/prep/profile') return ok({ configured: false, subjects: [] });
      if (url === '/programming/onboarding') return ok(ONBOARDING);
      if (url === '/programming/home') return ok({ stats: {} });
      if (url === '/learning/agenda') return ok({ items: [], total_items: 0, source_summary: {}, by_namespace: {} });
      if (url === '/programming/exercises') {
        return ok({
          items: [{ id: 7, title: '两数之和', personal_progress: { last_submit_at: '2026-09-30T08:00:00Z', last_submit_passed: false } }],
          total: 60,
          total_pages: 5,
        });
      }
      throw new Error(`unexpected GET ${url}`);
    });
    renderApp('/programming');

    const today = await screen.findByRole('region', { name: '今日任务' });
    expect(await within(today).findByText('继续上次的练习')).toBeInTheDocument();
    expect(within(today).getByRole('heading', { name: '两数之和' })).toBeInTheDocument();
    expect(within(today).getByRole('link', { name: /打开练习/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/programming/workbench/7'),
    );
  });
});

describe('编程工作台 · 学习进度与方向', () => {
  it('reports the recorded counts and never a score', async () => {
    mockProgrammingHome(ONBOARDING);
    renderApp('/programming');

    const progress = await screen.findByRole('region', { name: '学习进度' });
    // The counts arrive from two reads — the address's own figures and the bank's size — so each
    // group is waited for rather than assumed to have landed with the section.
    expect(await within(progress).findByText('3 天')).toBeInTheDocument();
    expect(within(progress).getByText('2 次')).toBeInTheDocument();
    expect(await within(progress).findByText('60 道')).toBeInTheDocument();
    // No mastery, no rate, no percentage: the endpoint holds none, so the page claims none.
    expect(within(progress).queryByText(/掌握|%/)).not.toBeInTheDocument();
  });

  it('offers the four languages as study directions, with the declared one marked', async () => {
    mockProgrammingHome(ONBOARDING);
    renderApp('/programming');

    const directions = await screen.findByRole('region', { name: '学习方向' });
    const links = within(directions).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining('Python'), expect.stringContaining('C++')]),
    );
    // Which language is the learner's own comes from their declared context, so it is waited for.
    expect(await within(directions).findByText('你设置的语言')).toBeInTheDocument();
    // Selecting a direction opens a tool with the language as CONTEXT, not as a path segment.
    expect(within(directions).getByRole('link', { name: /Python/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/programming/practice?language=python'),
    );
  });

  it('names the three modules the space is worked through', async () => {
    mockProgrammingHome(ONBOARDING);
    renderApp('/programming');

    for (const name of ['练习中心', 'AI 编程助手', '成长记录']) {
      expect(await screen.findByRole('link', { name: new RegExp(name) })).toBeInTheDocument();
    }
  });
});

describe('编程学习 · 语言不在路径里时它自己问', () => {
  it('asks which language a tool is about rather than picking one', async () => {
    mockProgrammingHome({ onboarding_completed: false });
    renderApp('/programming/practice');

    expect(await screen.findByRole('heading', { name: '选择学习语言' })).toBeInTheDocument();
    const choices = screen.getAllByRole('link', { name: /C\+\+|Python|Java|^C$/ });
    expect(choices.length).toBeGreaterThanOrEqual(4);
  });

  it('sends a retired address to the page that owns it now', async () => {
    get.mockImplementation(async (url: string) => {
      if (url === '/course-learning/courses') return ok([]);
      if (url === '/exam/prep/profile') return ok({ configured: false, subjects: [] });
      if (url === '/programming/onboarding') return ok(ONBOARDING);
      if (url === '/programming/records') return ok([]);
      if (url === '/programming/records/summary') return ok({ runs: 0 });
      if (url === '/programming/state') return ok({ runs: 0 });
      throw new Error(`unexpected GET ${url}`);
    });

    renderApp('/programming/python/records');

    // 记录 and 学习状态 were two tabs of the language; both are sections of 成长记录 now.
    expect(await screen.findByRole('heading', { level: 1, name: '成长记录' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: '编程学习导航' })).toBeInTheDocument();
  });
});
