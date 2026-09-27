import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
// Anything inside 408 that this suite does not model fails the way the product handles a real
// failure — with the page's own error state — so the shell under test is still the real one.
const FAILED = { data: undefined, error: { detail: 'unavailable' }, response: { ok: false, status: 500 } };

const cs408 = {
  id: 'cs_408',
  display_name: '计算机学科专业基础 408',
  category: 'professional',
  availability: 'active',
  has_questions: true,
  has_past_papers: true,
  has_knowledge_tree: true,
  description: '',
  suggested_tracks: ['cs_408'],
  modules: [
    { id: 'data_structure', display_name: '数据结构' },
    { id: 'computer_organization', display_name: '计算机组成原理' },
    { id: 'operating_system', display_name: '操作系统' },
    { id: 'computer_network', display_name: '计算机网络' },
  ],
};

const catalog = {
  catalog_version: 'v2',
  exam_type: 'postgraduate',
  tracks: [
    { id: 'cs_408', display_name: '计算机 408', exam_type: 'postgraduate', availability: 'active', has_content: true, description: '', subject_options: ['cs_408'], suggested_subjects: ['cs_408'] },
  ],
  subjects: [cs408],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: [],
};

const profile = {
  configured: true,
  exam_type: 'postgraduate',
  selected_track: 'cs_408',
  selected_subjects: ['cs_408'],
  target_exam_year: 2027,
  subjects: [cs408],
  custom_subjects: [],
};

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(profile);
    if (path === '/exam/prep/math/taxonomy') return ok({ domains: [], variants: [], coverage: [] });
    // The subject's library answers its own shape; a suite about navigation has nothing to say
    // about what is in it, so it is empty and real rather than a failure.
    if (path === '/exam/11408/subjects/{subject_key}/materials') {
      return ok({ subject_key: 'data_structure', course_id: 'data_structure_11408', items: [], total: 0 });
    }
    if (path.startsWith('/exam/11408/')) return FAILED;
    return ok({});
  });
});

describe('every page inside the exam space has a way out', () => {
  const cases: ReadonlyArray<{ path: string; label: string; href: string }> = [
    { path: '/exam/setup', label: '返回', href: '/exam' },
    { path: '/exam/subjects', label: '返回', href: '/exam' },
    { path: '/exam/subjects/math_1', label: '返回', href: '/exam' },
    { path: '/exam/cs408', label: '返回', href: '/exam' },
    { path: '/exam/cs408/knowledge?module=data_structure', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/practice?module=data_structure', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/past-papers?module=data_structure', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/wrong?module=data_structure', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/plan', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/records?module=data_structure', label: '返回 408', href: '/exam/cs408' },
    { path: '/exam/cs408/state?module=data_structure', label: '返回 408', href: '/exam/cs408' },
  ];

  it.each(cases)('$path links $label to $href', async ({ path, label, href }) => {
    renderApp(path);
    const back = await screen.findByRole('link', { name: label });
    expect(back).toHaveAttribute('href', href);
  });

  it('never leaves the destination up to the browser history', async () => {
    // The same page opened by direct URL — the case where a history-based back button has
    // nowhere to go — still states where it returns to.
    renderApp('/exam/cs408/knowledge?module=operating_system');
    expect(await screen.findByRole('link', { name: '返回 408' })).toHaveAttribute('href', '/exam/cs408');
  });
});

describe('the module switcher moves between the four papers without leaving the tool', () => {
  it('is offered on the paper-scoped tools and names the open paper', async () => {
    renderApp('/exam/cs408/knowledge?module=operating_system');

    expect(await screen.findByLabelText('切换 408 学习科目')).toHaveValue('operating_system');
    expect(screen.getByText('408 · 操作系统')).toBeInTheDocument();
    for (const name of ['数据结构', '计算机组成原理', '操作系统', '计算机网络']) {
      expect(screen.getByRole('option', { name })).toBeInTheDocument();
    }
  });

  it('offers no switcher on the subject list, where no paper is open yet', async () => {
    renderApp('/exam/cs408');
    expect(screen.queryByLabelText('切换 408 学习科目')).not.toBeInTheDocument();
  });

  it('stays in 知识脉络 while changing paper', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/exam/cs408/knowledge?module=data_structure');

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/knowledge'));
    expect(router.state.location.search).toMatchObject({ module: 'operating_system' });
  });

  it('stays in 章节练习 while changing paper, without carrying the old chapter', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/exam/cs408/practice?module=data_structure&chapter=3');

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'computer_network');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/practice'));
    // The chapter belonged to the paper that was open; it is not carried onto another one.
    expect(router.state.location.search).toEqual({ module: 'computer_network' });
  });

  it('stays in 真题 while changing paper, without carrying the old paper year', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/exam/cs408/past-papers?module=data_structure&year=2022');

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/past-papers'));
    expect(router.state.location.search).toEqual({ module: 'operating_system' });
  });

  it('stays in AI 对话 while changing paper, and the paper is what the scope changes', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/exam/cs408/ask?module=data_structure');
    await screen.findByRole('link', { name: 'AI 对话' });

    // The conversation is the paper's: the composer asks about the scope the workspace was
    // handed, so a switched paper is a switched scope rather than the same chat under a new
    // heading.
    expect(screen.getByPlaceholderText('问关于数据结构的问题…')).toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/ask'));
    expect(router.state.location.search).toEqual({ module: 'operating_system' });
    expect(await screen.findByPlaceholderText('问关于操作系统的问题…')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'AI 对话' })).toHaveAttribute('aria-current', 'page');
  });

  it('stays in AI 对话 but drops the knowledge point when the paper changes', async () => {
    const user = userEvent.setup();
    const { router } = renderApp(
      '/exam/cs408/ask?module=data_structure&knowledge_point=1.1&knowledge_point_title=线性表',
    );
    await screen.findByRole('link', { name: 'AI 对话' });
    // The point the learner entered from is stated where they type, so they can tell this apart
    // from a conversation about the whole paper.
    expect(screen.getByText(/当前围绕/)).toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/ask'));
    expect(router.state.location.search.module).toBe('operating_system');
    // A node of 数据结构 means nothing inside 操作系统: the paper's own point is not carried over.
    expect(router.state.location.search.knowledge_point).toBeUndefined();
    expect(router.state.location.search.knowledge_point_title).toBeUndefined();
    expect(await screen.findByPlaceholderText('问关于操作系统的问题…')).toBeInTheDocument();
    expect(screen.queryByText(/当前围绕/)).not.toBeInTheDocument();
  });

  it('stays in 资料库 while changing paper, and the library is read for the new one', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/exam/cs408/materials?module=data_structure');
    await screen.findByRole('link', { name: '资料库' });

    await user.selectOptions(await screen.findByLabelText('切换 408 学习科目'), 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/materials'));
    expect(router.state.location.search).toEqual({ module: 'operating_system' });
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        '/exam/11408/subjects/{subject_key}/materials',
        expect.objectContaining({ params: { path: { subject_key: 'operating_system' } } }),
      ),
    );
    expect(screen.getByRole('link', { name: '资料库' })).toHaveAttribute('aria-current', 'page');
  });

  it('offers 全部 only where the whole subject is a real scope, and never on 学习计划', async () => {
    const { unmount } = renderApp('/exam/cs408/records?module=data_structure');
    expect(await screen.findByRole('option', { name: '全部 408' })).toBeInTheDocument();
    unmount();

    // 学习计划 is subject-wide in the backend's own contract — `/exam/11408/subjects/{key}/study-plan`
    // takes no module — so it offers no switcher rather than one that would silently drop a choice.
    renderApp('/exam/cs408/plan');
    expect(await screen.findByRole('navigation', { name: 'CS408 工具导航' })).toBeInTheDocument();
    expect(screen.queryByLabelText('切换 408 学习科目')).not.toBeInTheDocument();
  });
});

describe('the tool strip is the only navigation inside a paper', () => {
  it('offers every page of a paper, in the order the product reads a learning space', async () => {
    renderApp('/exam/cs408/knowledge?module=operating_system');
    const tabs = await screen.findByRole('navigation', { name: 'CS408 工具导航' });

    expect(tabs.contains(screen.getByRole('link', { name: '知识脉络' }))).toBe(true);
    expect(screen.getByRole('link', { name: '知识脉络' })).toHaveAttribute('aria-current', 'page');
    // 概览 is gone: a paper is not a place to read a summary of itself, and every paper begins at
    // the outline a learner can act on.
    expect(screen.queryByRole('link', { name: '概览' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '概览' })).not.toBeInTheDocument();
    // 对话 and 资料库 lead, at the same rank as the tools beside them — the order 专业学习 reads
    // in, where 课程问答 and 资料 open the strip.
    expect(within(tabs).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'AI 对话', '资料库', '知识脉络', '章节练习', '真题', '错题', '学习计划', '学习记录', '学习状态',
    ]);
    expect(screen.getByRole('link', { name: 'AI 对话' })).toHaveAttribute(
      'href',
      '/exam/cs408/ask?module=operating_system',
    );
    expect(screen.getByRole('link', { name: '资料库' })).toHaveAttribute(
      'href',
      '/exam/cs408/materials?module=operating_system',
    );
  });

  it('does not draw a strip before a paper is chosen', async () => {
    renderApp('/exam/cs408/knowledge');
    // The tool cannot be read without a paper, so it asks for one and offers no tabs.
    expect(await screen.findByRole('heading', { name: '选择学习科目' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'CS408 工具导航' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^数据结构/ })).toHaveAttribute(
      'href',
      '/exam/cs408/knowledge?module=data_structure',
    );
  });

  it('sends an old ?module= link to the outline rather than to a 概览 page that no longer exists', async () => {
    const { router } = renderApp('/exam/cs408?module=computer_organization');

    await waitFor(() => expect(router.state.location.pathname).toBe('/exam/cs408/knowledge'));
    expect(router.state.location.search).toEqual({ module: 'computer_organization' });
  });
});
