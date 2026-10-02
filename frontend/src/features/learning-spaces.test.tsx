import { screen, waitFor, within } from '@testing-library/react';
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
      return ok({ course_id: 'data-structure', total: 1, items: [{ original_filename: '线性表.pdf', file_type: 'pdf', file_size: 2048, chunk_count: 12, parse_status: 'success', created_at: '2026-09-20T08:00:00Z' }] });
    }
    // 资料 reads the learner's whole library, not this course's own list.
    if (url === '/library/materials') {
      return ok({ materials: [{
        id: 22, filename: '线性表.pdf', file_type: 'pdf', size: 2048, parse_status: 'success',
        created_at: '2026-09-20T08:00:00Z', scope_type: 'course', source_label: '数据结构',
        can_preview: true, preview_url: '/materials/22/preview', can_download: true, download_url: '/materials/22/download',
      }] });
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
    if (url === '/adaptive/practice') return ok({ candidates: [], reasons: {} });

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
    renderApp('/course/data-structure/materials');

    // The library IS what the tab named 资料 opens on. 资料 is stated by the tab strip, so a
    // second page-sized heading saying it again would be naming the page twice.
    expect(await screen.findByRole('textbox', { name: '搜索资料' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: '资料' })).not.toBeInTheDocument();
    // The course is named by the selector the learner can change it from. The name is not
    // repeated beside it.
    const switcher = await screen.findByRole('combobox', { name: '切换课程' });
    await waitFor(() => expect(switcher).toHaveValue('data-structure'));
    expect(within(switcher).getByRole('option', { name: '数据结构' })).toBeInTheDocument();
    // The switcher is what names the page's own course. A 资料 row states 来源 per file — a
    // statement about where that file came from, not a second title for the page.
    expect(screen.queryByRole('heading', { level: 1, name: '数据结构' })).not.toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: '专业学习导航' });
    expect(within(nav).getByRole('link', { name: '资料' })).toHaveAttribute('aria-current', 'page');
    // No 概览: the course's surfaces are the work, and 课程问答 leads them.
    expect(within(nav).queryByRole('link', { name: '概览' })).not.toBeInTheDocument();
    for (const label of ['课程问答', '知识结构', '练习', '错题与复习', '计划', '记录']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('renders materials as the fields the backend sends, not as a payload', async () => {
    renderApp('/course/cs101/materials');

    expect(await screen.findByText('线性表.pdf')).toBeInTheDocument();
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
    expect(screen.getByText('可用')).toBeInTheDocument();
    expect(screen.queryByText(/个片段/)).not.toBeInTheDocument();
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
    // Inside a paper, which is where the tools exist: 408 is four papers, and a tool belongs to
    // one of them.
    renderApp('/exam/cs408/knowledge?module=data_structure');

    expect(await screen.findByRole('heading', { name: '知识脉络' })).toBeInTheDocument();
    const tabs = screen.getByRole('navigation', { name: 'CS408 工具导航' });
    expect(within(tabs).getByRole('link', { name: '知识脉络' })).toHaveAttribute('aria-current', 'page');
    expect(within(tabs).getByRole('link', { name: '真题' })).toHaveAttribute(
      'href',
      '/exam/cs408/past-papers?module=data_structure',
    );

    // Which paper is open, and the way out — stated once each, beside the strip. The exam space
    // carries no breadcrumb: a trail, a back link and a tab strip are three navigations for one
    // workspace, and the trail said nothing the header does not.
    expect(screen.getByText('408 · 数据结构')).toBeInTheDocument();
    expect(screen.getByLabelText('切换 408 学习科目')).toHaveValue('data_structure');
    expect(screen.getByRole('link', { name: '返回 408' })).toHaveAttribute('href', '/exam/cs408');
    expect(screen.queryByRole('navigation', { name: '面包屑' })).not.toBeInTheDocument();

    // Exam semantics stay exam semantics: modules, not courses, and no course tab strip.
    expect(screen.queryByRole('navigation', { name: '专业学习导航' })).not.toBeInTheDocument();
  });
});

describe('programming space context', () => {
  it('keeps the language in view and marks the current tool', async () => {
    renderApp('/programming/practice?language=python');

    expect(await screen.findByRole('heading', { name: 'Python 练习' })).toBeInTheDocument();
    // The language is a CONTEXT, named once by the control that changes it — not a second
    // navigation level beside the tool strip.
    expect(screen.getByLabelText('切换编程语言')).toHaveValue('python');
    expect(screen.getByText('编程学习 · Python')).toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: '编程学习导航' });
    expect(within(nav).getByRole('link', { name: '练习中心' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: '成长记录' })).toHaveAttribute(
      'href',
      '/programming/records?language=python',
    );
    // The three modules the space is worked through, and the two retired tabs are not among them.
    expect(within(nav).getByRole('link', { name: 'AI 编程助手' })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: '错误与待处理' })).toBeNull();
    expect(within(nav).queryByRole('link', { name: '学习状态' })).toBeNull();

    // Exam semantics stay exam semantics.
    expect(screen.queryByRole('navigation', { name: 'CS408 工具导航' })).not.toBeInTheDocument();
  });

  it('lists exercises as titles with their own labels, not as a payload', async () => {
    renderApp('/programming/practice?language=python');

    expect(await screen.findByText('两数之和')).toBeInTheDocument();
    expect(screen.getByText('入门')).toBeInTheDocument();
    assertNoRawPayloadInProse(document.body);
  });
});
