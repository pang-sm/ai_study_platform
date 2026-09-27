import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type * as DashboardSummaryApi from '@/features/exam/api/dashboard-summary';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const FAILED = { data: undefined, error: { detail: 'unavailable' }, response: { ok: false, status: 500 } };

const summary = (subject_key: string, subject_name: string, learned_percent: number) => ({
  subject_key,
  subject_name,
  overview: { total_chapters: 8, total_knowledge_points: 64, learned_percent, study_minutes: 20 },
  today_plan: [],
  materials: { lecture_notes: 0, exercises: 0, references: 0, code_examples: 0, total_materials: 0 },
  quota: {
    ai_chat: { used: 0, limit: 1, remaining: 1, unit: '次' },
    ai_question: { used: 0, limit: 1, remaining: 1, unit: '次' },
    material_upload: { used: 0, limit: 1, remaining: 1, unit: 'MB' },
  },
});

/**
 * The dashboard endpoint takes the paper as a path parameter, so a mocked client sees ONE url for
 * all four papers and cannot tell them apart by it. The hook is therefore mocked at its own
 * boundary, which is also the only place the four papers are distinguished at all.
 */
const retry = vi.fn();
vi.mock('@/features/exam/api/dashboard-summary', async (importOriginal) => {
  const actual = await importOriginal<typeof DashboardSummaryApi>();
  return {
    ...actual,
    useCs408DashboardSummaries: () => [
      { isPending: false, isError: false, data: summary('data_structure', '数据结构', 25), refetch: retry },
      { isPending: false, isError: false, data: summary('computer_organization', '计算机组成原理', 0), refetch: retry },
      // One paper's summary fails. The others must still be usable, and the failed one must say
      // NOTHING about its state rather than invent one.
      { isPending: false, isError: true, data: undefined, refetch: retry },
      { isPending: false, isError: false, data: summary('computer_network', '计算机网络', 100), refetch: retry },
    ],
  };
});

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
    // Anything inside 408 that this suite does not model fails the way the product handles a real
    // failure, so the workspace under test is still the real one rather than a half-mocked page.
    if (path.startsWith('/exam/11408/')) return FAILED;
    return ok({});
  });
});

/** The one way in for a paper, found by the name it leads with. */
const choice = (name: string) => screen.getByRole('link', { name: new RegExp(`^${name}`) });

describe('Cs408Workspace', () => {
  it('asks which of the four papers to study, and nothing else', async () => {
    renderApp('/exam/cs408');

    expect(await screen.findByRole('heading', { name: '选择学习科目' })).toBeInTheDocument();

    // Four ways in, each a real destination that carries the paper it names — straight into that
    // paper's outline, which is where a paper begins.
    expect(choice('数据结构')).toHaveAttribute('href', '/exam/cs408/knowledge?module=data_structure');
    expect(choice('计算机组成原理')).toHaveAttribute('href', '/exam/cs408/knowledge?module=computer_organization');
    expect(choice('操作系统')).toHaveAttribute('href', '/exam/cs408/knowledge?module=operating_system');
    expect(choice('计算机网络')).toHaveAttribute('href', '/exam/cs408/knowledge?module=computer_network');

    // The state each paper is really in, in one word. A percentage would be a figure the page
    // never needed to show to answer "which one do I study".
    expect(within(choice('数据结构')).getByText('学习中')).toBeInTheDocument();
    expect(within(choice('计算机网络')).getByText('已学习')).toBeInTheDocument();
    // A paper whose summary failed says nothing about its state rather than inventing one.
    expect(choice('操作系统').textContent).toBe('操作系统');
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();

    // The whole page is the four names and the question above them. No line explaining what 408
    // is made of, and no second navigation: the tools live inside a paper.
    expect(screen.queryByText(/由四门科目组成/)).not.toBeInTheDocument();
    for (const tool of ['知识脉络', '章节练习', '真题', '问 AI']) {
      expect(screen.queryByRole('link', { name: tool })).not.toBeInTheDocument();
    }
    // And no 01–04 numbering: the four papers are a choice, not an ordered list.
    expect(screen.queryByText('01')).not.toBeInTheDocument();
    expect(screen.queryByText(/额度|ai_chat|资料总数/i)).not.toBeInTheDocument();
  });

  it('opens a paper on its knowledge outline, which is the first tool of the strip', async () => {
    renderApp('/exam/cs408?module=data_structure');

    // There is no 概览 to land on: the module summary the old tab read is no longer rendered here.
    expect(await screen.findByRole('heading', { name: '知识脉络' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '概览' })).not.toBeInTheDocument();
    expect(screen.queryByText('知识点已学习比例 25%')).not.toBeInTheDocument();

    // One strip, with 知识脉络 marked, and the four papers NOT repeated as links in the body.
    const tabs = screen.getByRole('navigation', { name: 'CS408 工具导航' });
    expect(within(tabs).getByRole('link', { name: '知识脉络' })).toHaveAttribute('aria-current', 'page');
    expect(within(tabs).getByRole('link', { name: '知识脉络' })).toHaveAttribute(
      'href',
      '/exam/cs408/knowledge?module=data_structure',
    );
    expect(screen.queryByRole('link', { name: '计算机组成原理' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('切换 408 学习科目')).toHaveValue('data_structure');
  });
});
