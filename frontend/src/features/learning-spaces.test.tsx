import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

/**
 * The three learning spaces, checked against each other.
 *
 * Each of them must name the context it is in — the course, the exam module, the language — and
 * none of them may show another space's context or the payloads it was rendered from. The second
 * half matters as much as the first: a page that leaks `{"course_id": …}` into its reading
 * surface is not "showing the data", it is showing the transport.
 */

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (url: string) => {
    // Space context, so Home is in daily-learning mode.
    if (url === '/course-learning/courses') return ok([{ id: 'data-structure', name: '数据结构' }]);
    if (url === '/exam/prep/profile') return ok({ configured: true, subjects: [{ id: 'cs408' }] });
    if (url === '/programming/onboarding') return ok({ main_language: 'Python', selected_languages: ['Python'] });

    // Course space
    if (url === '/course-dashboard') return ok({ course_name: '数据结构', next_action: '继续线性表练习' });
    if (url === '/course-learning/courses/{course_id}/materials') {
      return ok({ course_id: 'data-structure', total: 1, items: [{ original_filename: '线性表.pdf', file_size: 2048, chunk_count: 12, parse_status: 'parsed', created_at: '2026-09-20T08:00:00Z' }] });
    }
    if (url === '/course-learning/courses/{course_id}/wrong-answers') {
      return ok({ total: 1, limit: 20, offset: 0, items: [{ wrong_record_id: 9, status: 'active', stem: '顺序表的插入复杂度？', user_answer: 'O(n)', reference_answer: 'O(n)' }] });
    }
    if (url === '/course-learning/courses/{course_id}/practice/workbook') return ok({ course_id: 'data-structure', total: 0, items: [] });
    if (url === '/course-learning/courses/{course_id}/practice/history') return ok({ course_id: 'data-structure', total: 0, items: [] });

    // Exam space
    if (url === '/exam/11408/subjects/{subject_key}/dashboard-summary') return ok({ subject_key: 'data_structure', subject_name: '数据结构', overview: { total_chapters: 8, total_knowledge_points: 64, learned_percent: 25, study_minutes: 20 }, today_plan: [], materials: { lecture_notes: 0, exercises: 0, references: 0, code_examples: 0, total_materials: 0 }, quota: { ai_chat: { used: 0, limit: 1, remaining: 1, unit: '次' }, ai_question: { used: 0, limit: 1, remaining: 1, unit: '次' }, material_upload: { used: 0, limit: 1, remaining: 1, unit: 'MB' } } });
    if (url === '/exam/11408/chapter-practice/outline') return ok({ module_key: 'data_structure', chapters: [] });

    // Programming space
    if (url === '/programming/exercises') return ok({ items: [{ id: 7, title: '两数之和', difficulty: '入门', source_label: '原创题目' }] });

    throw new Error(`unexpected GET ${url}`);
  });
});

/** Anything that looks like a payload must be inside a folded disclosure, never in the prose. */
function assertNoRawPayloadInProse(container: HTMLElement) {
  const jsonish = Array.from(container.querySelectorAll('*')).filter((element) =>
    element.children.length === 0 && /\{"|\[ \{|":[^ ]/.test(element.textContent ?? ''),
  );
  for (const element of jsonish) {
    expect(element.closest('details'), `raw payload outside a disclosure: ${element.textContent?.slice(0, 60)}`).not.toBeNull();
  }
}

describe('course space context', () => {
  it('names the course it is in and keeps its tabs on the current page', async () => {
    renderApp('/course/cs101/materials');

    expect(await screen.findByRole('heading', { level: 1, name: '课程资料' })).toBeInTheDocument();
    // The course is named by the context strip, from the dashboard the backend scopes to this id.
    const context = screen.getByText('当前课程').closest('div') as HTMLElement;
    expect(await within(context).findByText('数据结构')).toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: '课程学习导航' });
    expect(within(nav).getByRole('link', { name: '资料' })).toHaveAttribute('aria-current', 'page');
    for (const label of ['概览', '知识结构', '学习', '练习', '错题与复习', '计划', '记录', '学习状态']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }

    const crumbs = screen.getByRole('navigation', { name: '面包屑' });
    expect(crumbs.textContent).toContain('课程学习');
    expect(crumbs.textContent).toContain('资料');
  });

  it('renders materials as the fields the backend sends, not as a payload', async () => {
    renderApp('/course/cs101/materials');

    expect(await screen.findByText('线性表.pdf')).toBeInTheDocument();
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
    expect(screen.getByText(/12 个片段/)).toBeInTheDocument();
    assertNoRawPayloadInProse(document.body);
  });

  it('does not borrow another space’s context', async () => {
    renderApp('/course/cs101/wrong');

    expect(await screen.findByText('顺序表的插入复杂度？')).toBeInTheDocument();
    expect(screen.queryByText('数据结构知识脉络')).not.toBeInTheDocument();
    expect(screen.queryByText(/当前语言/)).not.toBeInTheDocument();
  });
});

describe('exam space context', () => {
  it('keeps the CS408 tools visible with the current one marked, and names the space', async () => {
    renderApp('/exam/cs408');

    expect(await screen.findByRole('heading', { name: '学习工作区' })).toBeInTheDocument();
    const tabs = screen.getByRole('navigation', { name: 'CS408 工具导航' });
    expect(within(tabs).getByRole('link', { name: '概览' })).toHaveAttribute('aria-current', 'page');
    expect(within(tabs).getByRole('link', { name: '真题' })).toHaveAttribute('href', '/exam/cs408/past-papers');

    const crumbs = screen.getByRole('navigation', { name: '面包屑' });
    expect(crumbs.textContent).toContain('考研学习');
    expect(crumbs.textContent).toContain('CS408');

    // Exam semantics stay exam semantics: modules, not courses, and no course tab strip.
    expect(screen.getByRole('heading', { name: '数据结构' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '课程学习导航' })).not.toBeInTheDocument();
  });
});

describe('programming space context', () => {
  it('keeps the language in view and marks the current tool', async () => {
    renderApp('/programming/python');

    expect(await screen.findByRole('heading', { name: 'Python 练习' })).toBeInTheDocument();
    const context = screen.getByText('当前语言').closest('div') as HTMLElement;
    expect(within(context).getByText('Python')).toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: '编程学习导航' });
    expect(within(nav).getByRole('link', { name: '练习' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: '学习状态' })).toHaveAttribute(
      'href',
      '/programming/python/state',
    );

    const crumbs = screen.getByRole('navigation', { name: '面包屑' });
    expect(crumbs.textContent).toContain('编程学习');
    expect(screen.queryByRole('navigation', { name: 'CS408 工具导航' })).not.toBeInTheDocument();
  });

  it('lists exercises as titles with their own labels, not as a payload', async () => {
    renderApp('/programming/python');

    expect(await screen.findByText('两数之和')).toBeInTheDocument();
    expect(screen.getByText('入门')).toBeInTheDocument();
    assertNoRawPayloadInProse(document.body);
  });
});
