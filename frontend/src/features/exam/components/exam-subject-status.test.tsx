import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const conflict = (data: unknown) => ({ data: undefined, error: data, response: { ok: false, status: 409 } });

const NOT_AVAILABLE = {
  detail: { code: 'EXAM_CONTENT_NOT_AVAILABLE', subject_id: 'math_1', availability: 'framework_only', message: '该科目已开放选择，但内容尚未上线。' },
};

const math = {
  id: 'math_1',
  display_name: '数学（一）',
  category: 'public',
  availability: 'framework_only',
  has_questions: false,
  has_past_papers: false,
  has_knowledge_tree: false,
  description: '',
  suggested_tracks: [],
  modules: [],
};

const politics = {
  id: 'politics',
  display_name: '思想政治理论',
  category: 'public',
  availability: 'framework_only',
  has_questions: false,
  has_past_papers: false,
  has_knowledge_tree: false,
  description: '',
  suggested_tracks: [],
  modules: [],
};

const cs408 = {
  id: 'cs_408',
  display_name: '计算机学科专业基础 408',
  category: 'professional',
  availability: 'active',
  has_questions: true,
  has_past_papers: true,
  has_knowledge_tree: true,
  description: '全国统考计算机学科专业基础综合（408）',
  suggested_tracks: ['cs_408'],
  modules: [{ id: 'data_structure', display_name: '数据结构' }, { id: 'operating_system', display_name: '操作系统' }],
};

const catalog = {
  catalog_version: 'v2',
  exam_type: 'postgraduate',
  tracks: [
    {
      id: 'cs_408',
      display_name: '计算机 408',
      exam_type: 'postgraduate',
      availability: 'active',
      has_content: true,
      description: '',
      subject_options: ['cs_408'],
      suggested_subjects: ['cs_408'],
    },
  ],
  subjects: [cs408, math, politics],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: ['math_1', 'politics'],
};

const inPlan = {
  configured: true,
  exam_type: 'postgraduate',
  selected_track: 'cs_408',
  selected_subjects: ['cs_408', 'math_1'],
  target_exam_year: 2027,
  subjects: [cs408, math],
  custom_subjects: [],
};

/** The backend's maths taxonomy: three canonical domains, and no exam range stated. */
const MATH_TAXONOMY = {
  math_taxonomy_version: 'v1',
  math_ready_level: 'L1',
  math_openable: false,
  openable_reason: '知识体系已建立，但考试范围尚未由权威大纲导入，数学学习入口暂不开放。',
  domains: [
    { key: 'calculus', display_name: '高等数学', order: 1, knowledge_map_id: 'calculus', status: 'available', source: '微积分教材', source_reference: '' },
    { key: 'linear_algebra', display_name: '线性代数', order: 2, knowledge_map_id: 'linear_algebra', status: 'available', source: '线性代数讲义', source_reference: '' },
    { key: 'probability_statistics', display_name: '概率论与数理统计', order: 3, knowledge_map_id: 'probability_statistics', status: 'available', source: '概率论与数理统计', source_reference: '' },
  ],
  variants: [
    { id: 'math_1', display_name: '数学（一）', subject_id: 'math_1', order: 1 },
    { id: 'math_2', display_name: '数学（二）', subject_id: 'math_2', order: 2 },
    { id: 'math_3', display_name: '数学（三）', subject_id: 'math_3', order: 3 },
  ],
  coverage_status: 'pending_syllabus_import',
  coverage_note: '考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。',
  coverage_sources: [],
  coverage: [],
};

function mock({ profile = inPlan, status = conflict(NOT_AVAILABLE) as unknown } = {}) {
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(profile);
    if (path === '/exam/prep/math/taxonomy') return ok(MATH_TAXONOMY);
    return status;
  });
}

/**
 * The same learner holding a different maths paper. Built here rather than in the shared fixture
 * so a case can show that 数学（二）is described by the same model as 数学（一）.
 */
function withMathPaper(id: string, name: string) {
  const paper = { ...math, id, display_name: name };
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok({ ...catalog, subjects: [cs408, paper] });
    if (path === '/exam/prep/profile') {
      return ok({ ...inPlan, selected_subjects: ['cs_408', id], subjects: [cs408, paper] });
    }
    if (path === '/exam/prep/math/taxonomy') return ok(MATH_TAXONOMY);
    return conflict(NOT_AVAILABLE);
  });
}

beforeEach(() => {
  get.mockReset();
  mock();
});

describe('科目状态页', () => {
  it('states the subject, its state and what that means for this learner’s plan', async () => {
    renderApp('/exam/subjects/math_1');

    expect(await screen.findByRole('heading', { level: 1, name: '数学（一）' })).toBeInTheDocument();
    expect(screen.getByText('当前状态')).toBeInTheDocument();
    expect(screen.getByText('科目框架已建立')).toBeInTheDocument();
    expect(screen.getByText('已纳入你的 2027 考研方案。')).toBeInTheDocument();
    // Maths HAS a knowledge structure, so this subject must not borrow the sentence written for
    // one that has none.
    expect(screen.getByText(/知识体系已建立；学习内容与练习尚未开放/)).toBeInTheDocument();
    expect(screen.queryByText(/完整知识体系、练习与学习工具尚未开放/)).not.toBeInTheDocument();
  });

  it('keeps the plain framework sentence for a subject with no knowledge structure', async () => {
    get.mockImplementation(async (path: string) => {
      if (path === '/exam/prep/catalog') return ok(catalog);
      if (path === '/exam/prep/profile') return ok({ ...inPlan, selected_subjects: ['cs_408', 'math_1'] });
      if (path === '/exam/prep/math/taxonomy') return ok(MATH_TAXONOMY);
      return conflict(NOT_AVAILABLE);
    });
    renderApp('/exam/subjects/politics');

    expect(await screen.findByRole('heading', { level: 1, name: '思想政治理论' })).toBeInTheDocument();
    expect(screen.getByText(/但完整知识体系、练习与学习工具尚未开放/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '学习模块' })).not.toBeInTheDocument();
  });

  it('shows the plan the subject belongs to, and where to change it', async () => {
    renderApp('/exam/subjects/math_1');
    await screen.findByRole('heading', { level: 1, name: '数学（一）' });

    const planSection = screen.getByRole('region', { name: '考试方案' });
    expect(within(planSection).getByText(/数学（一）/)).toBeInTheDocument();
    expect(within(planSection).getByText('· 已在考试方案中')).toBeInTheDocument();
    expect(within(planSection).getByText('2027 全国硕士研究生招生考试（统考）')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '修改考试方案' })).toHaveAttribute('href', '/exam/setup');
    expect(screen.getByRole('link', { name: '返回科目目录' })).toHaveAttribute('href', '/exam/subjects');
  });

  it('reports no measurement of content that does not exist', async () => {
    renderApp('/exam/subjects/math_1');
    await screen.findByRole('heading', { level: 1, name: '数学（一）' });

    // A count of zero is a measurement; the honest statement is that the content is not built.
    expect(document.body.textContent).not.toMatch(/0 个知识点|0 道题|0%|暂无记录|暂无学习记录|掌握率|预计/);
  });

  it('shows a maths paper as one of three papers over one set of domains, range unstated', async () => {
    renderApp('/exam/subjects/math_1');
    await screen.findByRole('heading', { level: 1, name: '数学（一）' });

    const domains = screen.getByRole('region', { name: '学习模块' });
    // The canonical three, each reporting its REAL state — never a count or a percentage.
    for (const name of ['高等数学', '线性代数', '概率论与数理统计']) {
      expect(within(domains).getByText(name)).toBeInTheDocument();
    }
    expect(within(domains).getAllByText('· 知识体系已建立')).toHaveLength(3);
    // The framework sentence must not claim the knowledge structure is missing when it exists.
    expect(screen.getByText(/知识体系已建立；学习内容与练习尚未开放/)).toBeInTheDocument();

    // Which domains this paper examines is national syllabus data. No source for it exists in
    // this repository, so the page states that instead of filling it in from memory.
    const scope = screen.getByRole('region', { name: '考试范围' });
    expect(within(scope).getByText('考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。')).toBeInTheDocument();

    expect(document.body.textContent).not.toMatch(/0 个知识点|0 道题|0%|暂无学习记录/);
    expect(screen.queryByRole('link', { name: /继续学习|开始学习|进入学习/ })).not.toBeInTheDocument();
  });

  it('describes 数学（二）with the same domains, because it is the same subject', async () => {
    withMathPaper('math_2', '数学（二）');
    renderApp('/exam/subjects/math_2');
    await screen.findByRole('heading', { level: 1, name: '数学（二）' });

    const domains = screen.getByRole('region', { name: '学习模块' });
    for (const name of ['高等数学', '线性代数', '概率论与数理统计']) {
      expect(within(domains).getByText(name)).toBeInTheDocument();
    }
    // Same three domains as 数学（一）: the papers differ in range, not in content.
    expect(within(domains).getAllByText('· 知识体系已建立')).toHaveLength(3);
  });

  it('offers no study entry for a subject that cannot be studied', async () => {
    renderApp('/exam/subjects/math_1');
    await screen.findByRole('heading', { level: 1, name: '数学（一）' });

    // A framework-only subject has nothing to start or continue: the actions are the plan and
    // the catalogue, never a way into content nobody wrote.
    expect(screen.queryByRole('link', { name: /继续学习|开始学习|进入学习/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '修改考试方案' })).toHaveAttribute('href', '/exam/setup');
    expect(screen.getByRole('link', { name: '返回科目目录' })).toHaveAttribute('href', '/exam/subjects');
  });

  it('says a subject is not yet in the plan rather than implying it is', async () => {
    mock({ profile: { ...inPlan, selected_subjects: ['cs_408'] } });
    renderApp('/exam/subjects/math_1');
    await screen.findByRole('heading', { level: 1, name: '数学（一）' });

    expect(screen.getByText('还没有加入你的考试方案。')).toBeInTheDocument();
    expect(screen.getByText('· 未加入考试方案')).toBeInTheDocument();
  });

  it('opens a subject that is actually studiable, with its own parts and entry', async () => {
    mock({ status: ok({ subject_id: 'cs_408', availability: 'active', has_questions: true, has_past_papers: true, has_knowledge_tree: true, modules: [{ id: 'data_structure', display_name: '数据结构' }, { id: 'operating_system', display_name: '操作系统' }] }) });
    renderApp('/exam/subjects/cs_408');

    expect(await screen.findByRole('heading', { level: 1, name: '计算机学科专业基础 408' })).toBeInTheDocument();
    expect(screen.getByText('完整学习功能已开放')).toBeInTheDocument();
    expect(screen.getByText(/由 2 部分组成：数据结构 · 操作系统。/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /进入学习/ })).toHaveAttribute('href', '/exam/cs408');
  });

  it('says a subject is not in the national catalogue instead of guessing', async () => {
    renderApp('/exam/subjects/not_a_subject');

    expect(await screen.findByText('这个科目不在全国统考科目目录中。')).toBeInTheDocument();
  });
});
