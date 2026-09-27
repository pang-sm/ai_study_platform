import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

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
  modules: [
    { id: 'data_structure', display_name: '数据结构' },
    { id: 'computer_organization', display_name: '计算机组成原理' },
    { id: 'operating_system', display_name: '操作系统' },
    { id: 'computer_network', display_name: '计算机网络' },
  ],
};

const frameworkSubject = (id: string, display_name: string) => ({
  id,
  display_name,
  category: 'public',
  availability: 'framework_only',
  has_questions: false,
  has_past_papers: false,
  has_knowledge_tree: false,
  description: '',
  suggested_tracks: [],
  modules: [],
});

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
      description: '计算机学科专业基础综合（408）',
      subject_options: ['cs_408'],
      suggested_subjects: ['cs_408'],
    },
  ],
  subjects: [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('english_1', '英语（一）')],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: ['politics', 'english_1'],
};

const configured = {
  configured: true,
  exam_type: 'postgraduate',
  selected_track: 'cs_408',
  selected_subjects: ['cs_408', 'politics', 'english_1'],
  target_exam_year: 2027,
  subjects: [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('english_1', '英语（一）')],
  custom_subjects: [],
};

const unconfigured = {
  configured: false,
  exam_type: 'postgraduate',
  selected_track: null,
  selected_subjects: [],
  target_exam_year: null,
  subjects: [],
  custom_subjects: [],
};

/** A study record naming one of the four 408 papers — the only thing that may support 继续学习. */
function examRecord(moduleId: string) {
  return {
    event_id: `e-${moduleId}`,
    event_type: 'question_answered',
    record_category: 'practice',
    service_namespace: 'exam_prep',
    occurred_at: '2026-09-25T00:00:00+00:00',
    context: { exam_module_id: moduleId },
    source: { kind: 'practice', id: '1' },
    summary: { correct: true },
  };
}

function mockAll({
  profile = configured,
  records = [] as unknown[],
}: { profile?: unknown; records?: unknown[] } = {}) {
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(profile);
    if (path === '/exam/prep/math/taxonomy') return ok(MATH_TAXONOMY);
    if (path === '/learning-records') return ok({ records, has_more: false, next_cursor: null });
    // Whatever the app shell reads on the way here is answered emptily, so a shell query can
    // never be mistaken for a failure of the page under test.
    return ok({});
  });
}

/** The backend's maths taxonomy, as the real endpoint returns it: structures, no exam range. */
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

/** The subject's own surface, found by the one heading that names it. */
function cardOf(region: HTMLElement, name: string): HTMLElement {
  const found = within(region).getByRole('heading', { level: 2, name }).closest('li');
  if (!found) throw new Error(`no subject card for ${name}`);
  return found;
}

beforeEach(() => {
  get.mockReset();
  mockAll();
});

describe('考研学习 home', () => {
  it('does not restate the space name as a page title, and keeps it in the global navigation', async () => {
    renderApp('/exam');
    await screen.findByRole('region', { name: '我的考试科目' });

    // 考研学习 is where the learner already is — the global navigation says so. The page's own
    // first screen belongs to the subjects, not to a title repeating the nav item above it.
    expect(screen.queryByRole('heading', { name: '考研学习' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: '考研学习' }).length).toBeGreaterThan(0);

    // Nor the retired space-level tab bar.
    expect(screen.queryByRole('navigation', { name: '考研学习导航' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '我的备考' })).not.toBeInTheDocument();
    expect(screen.queryByText('备考档案')).not.toBeInTheDocument();
  });

  it('is one block — the subjects — and no longer carries a 考试方案 summary of them', async () => {
    renderApp('/exam');
    await screen.findByRole('region', { name: '我的考试科目' });

    // The exam, its year, the direction and the caveat were a second telling of what the subject
    // cards already say. The page answers "我考哪几门" once, and the composition of the plan is
    // what 修改考试方案 opens.
    expect(screen.queryByRole('region', { name: '考试方案' })).not.toBeInTheDocument();
    expect(screen.queryByText('全国硕士研究生招生考试（统考）')).not.toBeInTheDocument();
    expect(screen.queryByText(/备考方向/)).not.toBeInTheDocument();
    expect(screen.queryByText('具体考试科目以目标院校当年招生专业目录为准。')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '考试方案' })).not.toBeInTheDocument();
  });

  it('changes the combination from the subjects it changes', async () => {
    renderApp('/exam');
    const subjects = await screen.findByRole('region', { name: '我的考试科目' });

    // One action, on the block it acts on.
    expect(within(subjects).getByRole('link', { name: '修改考试方案' })).toHaveAttribute('href', '/exam/setup');
    // The catalogue index is no longer a second, near-identical way in: 修改考试方案 is the way.
    expect(screen.queryByRole('link', { name: '查看全部可选科目' })).not.toBeInTheDocument();
  });

  it('puts every selected subject on the page, with the studiable one first', async () => {
    renderApp('/exam');
    const subjects = await screen.findByRole('region', { name: '我的考试科目' });

    // All three of the plan's subjects, at once: the learner's own question is 我考哪几门.
    const cards = within(subjects).getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    expect(cards).toEqual(['计算机学科专业基础 408', '思想政治理论', '英语（一）']);
    // And the one this build can open leads, whatever order the catalogue lists them in — a
    // subject with no way in cannot push the way in down the page.
    const cs = cardOf(subjects, '计算机学科专业基础 408');
    const politics = cardOf(subjects, '思想政治理论');
    expect(cs.compareDocumentPosition(politics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('keeps the 408 card to the three things a learner reads it for', async () => {
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    const cs = cardOf(subjects, '计算机学科专业基础 408');
    // Which line of the plan, the subject's name, and the way in.
    expect(within(cs).getByText('专业课')).toBeInTheDocument();
    expect(within(cs).getByRole('heading', { name: '计算机学科专业基础 408' })).toBeInTheDocument();
    expect(within(cs).getByRole('link', { name: '进入 408' })).toHaveAttribute('href', '/exam/cs408');
    // The state badge that repeated what the button already said, and the catalogue's own
    // description of the paper under its name. Both are on the subject's own page.
    expect(within(cs).queryByText('完整学习功能已开放')).not.toBeInTheDocument();
    expect(within(cs).queryByText('全国统考计算机学科专业基础综合（408）')).not.toBeInTheDocument();

    // The card is a way in, not a second index of what is behind the way in.
    for (const name of ['数据结构', '计算机组成原理', '操作系统', '计算机网络']) {
      expect(within(cs).queryByRole('heading', { name })).not.toBeInTheDocument();
      expect(within(cs).queryByText(name)).not.toBeInTheDocument();
    }
    expect(within(cs).queryByRole('link', { name: '知识脉络' })).not.toBeInTheDocument();
    expect(within(cs).queryByRole('link', { name: '错题' })).not.toBeInTheDocument();
  });

  it('shows a framework-only subject as the subject and its way out, and nothing else', async () => {
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    // The same region, the same grid: 思想政治理论 is one of the subjects being sat, not a setting.
    const politics = cardOf(subjects, '思想政治理论');
    // Three things: which line of the plan it sits on, its name, and the page that explains it.
    expect(within(politics).getByText('政治')).toBeInTheDocument();
    expect(within(politics).getByRole('heading', { name: '思想政治理论' })).toBeInTheDocument();
    expect(within(politics).getByRole('link', { name: '查看科目' })).toHaveAttribute(
      'href',
      '/exam/subjects/politics',
    );
    // Not its state — that is on the subject's own page — and not a way into a study surface this
    // subject does not have. What is left of the card is exactly its own text, so anything else
    // that crept back in would show up here.
    expect(politics.textContent).toBe('政治思想政治理论查看科目');
    expect(within(politics).queryByRole('link', { name: /继续学习|进入 408/ })).not.toBeInTheDocument();
    // No progress, no knowledge-point count, no question count: none of it exists.
    expect(politics.textContent).not.toMatch(/知识点|题库|道题|%|掌握|科目框架/);
  });

  it('claims 继续学习 only when a record names the paper the learner left off in, and opens that paper', async () => {
    mockAll({ records: [examRecord('operating_system')] });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    const cs = cardOf(subjects, '计算机学科专业基础 408');
    expect(within(cs).getByRole('link', { name: '继续学习 · 操作系统' })).toHaveAttribute(
      'href',
      '/exam/cs408/knowledge?module=operating_system',
    );
  });

  it('offers plain 进入 408 when there is no study fact to continue from', async () => {
    mockAll({ records: [] });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    const cs = cardOf(subjects, '计算机学科专业基础 408');
    expect(within(cs).getByRole('link', { name: '进入 408' })).toHaveAttribute('href', '/exam/cs408');
    expect(within(cs).queryByText(/继续学习/)).not.toBeInTheDocument();
  });

  it('does not invent a subject, a count or a progress figure an unconfigured learner never had', async () => {
    mockAll({ profile: unconfigured });
    renderApp('/exam');

    expect(await screen.findByText('还没有考试方案。')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '设置考试方案' })).toHaveAttribute('href', '/exam/setup');
    // Nothing to list, so the page draws one empty state and not a second saying the same thing.
    expect(screen.queryByRole('region', { name: '考试方案' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /继续学习|进入 408/ })).not.toBeInTheDocument();
  });

  it('says the plan holds no subject rather than describing an exam nobody is sitting', async () => {
    // Empty state 2: a plan that exists and holds nothing.
    mockAll({ profile: { ...unconfigured, configured: true, target_exam_year: 2028 } });
    renderApp('/exam');

    expect(await screen.findByText('还没有选择考试科目。')).toBeInTheDocument();
    // No 考试方案 summary to carry the year any more, so nothing claims an exam the learner has
    // not named a subject for.
    expect(screen.queryByText(/2028/)).not.toBeInTheDocument();
  });
});

/**
 * The home is a read of the profile, so each of these is the same page after a different save.
 * They are the states the setup flow's own tests produce, read back from the other end.
 */
describe('考研学习 home reflects the plan the learner confirmed', () => {
  const withSubjects = (ids: string[], subjects: unknown[]) => ({
    ...configured,
    selected_subjects: ids,
    subjects,
  });

  it('shows the maths paper the learner swapped to, and only that one', async () => {
    mockAll({
      profile: withSubjects(
        ['cs_408', 'politics', 'english_1', 'math_2'],
        [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('english_1', '英语（一）'), frameworkSubject('math_2', '数学（二）')],
      ),
    });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    expect(within(subjects).getByRole('heading', { name: '数学（二）' })).toBeInTheDocument();
    expect(within(subjects).queryByText('数学（一）')).not.toBeInTheDocument();
  });

  it('drops the maths subject entirely when no unified maths is sat', async () => {
    mockAll({
      profile: withSubjects(
        ['cs_408', 'politics', 'english_1'],
        [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('english_1', '英语（一）')],
      ),
    });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    expect(within(subjects).getByRole('heading', { name: '思想政治理论' })).toBeInTheDocument();
    expect(within(subjects).queryByText(/数学/)).not.toBeInTheDocument();
  });

  it('shows a maths paper as the paper it is called, with no way in and nothing about its state', async () => {
    mockAll({
      profile: withSubjects(
        ['cs_408', 'math_1', 'politics'],
        [cs408, frameworkSubject('math_1', '数学（一）'), frameworkSubject('politics', '思想政治理论')],
      ),
    });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    const math = cardOf(subjects, '数学（一）');
    expect(within(math).getByRole('link', { name: '查看科目' })).toHaveAttribute('href', '/exam/subjects/math_1');
    expect(within(math).queryByRole('link', { name: /继续学习|开始学习|进入学习|进入数学/ })).not.toBeInTheDocument();
    // What the maths exam is made of, and what state it is in, are both on the subject's own page.
    // The home says which subjects the learner sits, and nothing more.
    expect(within(math).queryByText(/高等数学|线性代数|科目框架/)).not.toBeInTheDocument();
    expect(math.textContent).not.toMatch(/\d+\s*(个知识点|道题|%)|暂无学习记录/);
  });

  it('drops the English subject entirely while the paper is undecided', async () => {
    mockAll({
      profile: withSubjects(
        ['cs_408', 'politics', 'math_1'],
        [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('math_1', '数学（一）')],
      ),
    });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    expect(within(subjects).queryByText(/英语/)).not.toBeInTheDocument();
  });

  it('shows the English paper the learner swapped to, and only that one', async () => {
    mockAll({
      profile: withSubjects(
        ['cs_408', 'politics', 'english_2', 'math_1'],
        [cs408, frameworkSubject('politics', '思想政治理论'), frameworkSubject('english_2', '英语（二）'), frameworkSubject('math_1', '数学（一）')],
      ),
    });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    expect(within(subjects).getByRole('heading', { name: '英语（二）' })).toBeInTheDocument();
    expect(within(subjects).queryByText('英语（一）')).not.toBeInTheDocument();
  });

  it('stops claiming full learning when the professional paper is a framework only', async () => {
    const law = {
      ...frameworkSubject('law_master_law', '法律硕士（法学）全国统考科目'),
      category: 'professional',
    };
    mockAll({ profile: withSubjects(['law_master_law', 'politics'], [law, frameworkSubject('politics', '思想政治理论')]) });
    renderApp('/exam');

    const subjects = await screen.findByRole('region', { name: '我的考试科目' });
    // Nothing on the page may claim the 408 surface any more — not the badge that used to sit on
    // a card this build can study, and not a route into one it cannot.
    expect(within(subjects).queryByText('完整学习功能已开放')).not.toBeInTheDocument();
    expect(within(subjects).queryByText(/继续学习|进入 408/)).not.toBeInTheDocument();
    const lawCard = cardOf(subjects, '法律硕士（法学）全国统考科目');
    expect(within(lawCard).getByRole('link', { name: '查看科目' })).toHaveAttribute(
      'href',
      '/exam/subjects/law_master_law',
    );
    // A professional line on the card is not a claim about content either.
    expect(lawCard.textContent).toBe('专业课法律硕士（法学）全国统考科目查看科目');
  });
});
