import type { ReactNode } from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { renderApp } from '@/test/render-app';

type StudyPlan = components['schemas']['ExamStudyPlanResponse'];

// The section is the CANONICAL knowledge leaf: its `code` is what the module knowledge-map
// seed publishes, and the same string a chapter-practice question carries as its concept.
// The tests below move it between a real leaf code and the synthetic `_leaf:` code the API
// mints for a seed node that has none, because only one of the two may offer practice.
let sectionCode = '1.1';
// A branch node's own code, so a case can put it in the synthetic (`_leaf:<path>`) shape the API
// mints for a seed node that publishes none.
let nodeCode = 'node-1';

function plan(): StudyPlan {
  return {
    course_id: 'data_structure_11408',
    course_name: '数据结构',
    subject_key: 'data_structure',
    subject_name: '数据结构',
    settings: { learning_goal: null, start_date: null, daily_hours: null, weekly_days: null, review_strategy: null, show_completed: true },
    stats: { total_knowledge_points: 2, mastered: 1, total_sections: 1, sections_completed: 0, sections_learning: 1, sections_not_started: 0, overall_progress: 50, overall_status: 'learning' },
    review_interval_days: 3,
    tasks: [],
    chapters: [{
      code: 'chapter-1', title: '线性表', chapter_no: 1, id: 'chapter-1', is_leaf: false,
      status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
      progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
      status_counts: { not_started: 0, learning: 1, mastered: 1, review_due: 0 }, chapter_completion_rate: 50, section_count: 1, sections_completed: 0, chapter_status: 'learning',
      children: [{
        code: sectionCode, title: '顺序表', id: 'section-1', is_leaf: false,
        status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
        progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
        status_counts: { not_started: 0, learning: 1, mastered: 1, review_due: 0 }, leaf_stats: { total: 2, mastered: 1, learning: 1, not_started: 0, review_due: 0 }, chapter_practice_completed: false, section_status: 'learning', completion_rate: 50,
        children: [{
          code: nodeCode, title: '顺序表操作', id: 'node-1', is_leaf: false,
          status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
          progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
          status_counts: { not_started: 0, learning: 1, mastered: 0, review_due: 0 },
          children: [{
            code: 'leaf-1', title: '插入操作', id: 'leaf-1', is_leaf: true,
            status: 'mastered', stored_status: 'mastered', user_confirmed_status: 'mastered', system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
            progress: { id: 1, course_id: 'data_structure_11408', knowledge_point_code: 'leaf-1', knowledge_point_title: '插入操作', status: 'mastered', stored_status: 'mastered', user_confirmed_status: 'mastered', system_suggested_status: null, ai_recommended_status: null, ai_assessment: null, learned_at: '2026-09-17T00:00:00Z', review_due_at: null, review_interval_days: 3, updated_at: null },
            learned_at: '2026-09-17T00:00:00Z', review_due_at: null, review_interval_days: 3,
            status_counts: { not_started: 0, learning: 0, mastered: 1, review_due: 0 }, children: [],
          }],
        }],
      }],
    }],
  };
}

const mutate = vi.fn((input: { status: string }, options?: { onSuccess?: (response: { status: string }) => void }) => {
  options?.onSuccess?.({ status: input.status });
});
vi.mock('@/features/exam/api/study-plan', () => ({
  useExamStudyPlan: () => ({ data: plan(), isPending: false, isError: false, refetch: vi.fn() }),
  useUpdateExamKnowledgeItem: () => ({ mutate, isPending: false, isError: false }),
}));

// Whatever else the app shell reads on the way to this page is answered emptily, so a shell query
// can never be mistaken for a failure of the page under test.
const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() } }));

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async () => ({ data: {}, error: undefined, response: { ok: true, status: 200 } }));
});

vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: ReactNode }) => children }));

/**
 * Rendered through the router rather than as a bare component: the page carries a real link out
 * to the assistant, which is a route of this app and not an anchor — the same navigation the
 * other two learning spaces use to reach it. The 408 shell is stubbed so the assertions below
 * are about the outline and its tools, not about the frame around them.
 */
async function renderWorkspace() {
  const view = renderApp('/exam/cs408/knowledge?module=data_structure');
  // The route is matched asynchronously, so nothing is on screen when `render` returns.
  await screen.findByRole('heading', { name: '知识脉络' });
  return view;
}

describe('Cs408KnowledgeWorkspace', () => {
  beforeEach(() => { sectionCode = '1.1'; nodeCode = 'node-1'; });

  it('renders the real recursive children hierarchy and keeps chapter semantics separate from knowledge semantics', async () => {
    const user = userEvent.setup();
    await renderWorkspace();

    expect(screen.getByRole('heading', { name: '知识脉络' })).toBeInTheDocument();
    expect(screen.getAllByText('学习中')).toHaveLength(2);
    expect(screen.queryByText('插入操作')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));

    expect(screen.getByRole('heading', { name: '插入操作' })).toBeInTheDocument();
    expect(screen.getAllByText('已学习')).toHaveLength(2);
    expect(screen.queryByText('已掌握')).not.toBeInTheDocument();
    // ONE state block, and the one control that changes it.
    expect(screen.getByText('学习状态')).toBeInTheDocument();
    expect(screen.queryByText('我的学习状态')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '更新' }));
    await user.click(screen.getByRole('button', { name: '待复习' }));
    expect(mutate).toHaveBeenCalledWith({ username: '', subject_key: 'data_structure', course_id: 'data_structure_11408', knowledge_point_code: 'leaf-1', knowledge_point_title: '插入操作', status: 'review_due' }, expect.objectContaining({ onSuccess: expect.any(Function) }));
    expect(screen.getByText('待复习')).toBeInTheDocument();
    expect(screen.queryByText(/data_structure_11408|knowledge_point_id/i)).not.toBeInTheDocument();
  });

  it('shows no internal identity: no code row, and no minted node path anywhere', async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));

    // The node the learner selected is `leaf-1`; a node the seed gives no code is `_leaf:<path>`.
    // NEITHER is on the page: the identity is what the state update and the assistant are given,
    // and it is not something a learner reads.
    expect(screen.queryByText('知识编码')).not.toBeInTheDocument();
    expect(screen.queryByText('leaf-1')).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/_leaf:|knowledge_point_id|_node:/);
  });

  it('carries no deep-reasoning panel: the point has one AI action, and it is the paper chat', async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));

    expect(screen.queryByText(/深度思考/)).not.toBeInTheDocument();
    expect(screen.queryByText(/强推理/)).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: '围绕此知识点问 AI' })).toHaveLength(1);
  });
});

// ---------------------------------------------------------------- practice is a page, not a link

describe('Cs408KnowledgeWorkspace carries no practice entry', () => {
  beforeEach(() => { sectionCode = '1.1'; nodeCode = 'node-1'; });

  it('draws no practice link at any level of the tree', async () => {
    const user = userEvent.setup();
    await renderWorkspace();

    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));

    // 章节练习 is a first-level page of the paper. An entry point on every chapter, section and
    // knowledge point made the tree say "study this" and "practise this" at once, four levels
    // deep — and made the outline answer for a page that is not it.
    expect(screen.queryByRole('link', { name: '知识点练习' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '章节练习' })).not.toBeInTheDocument();
    expect(screen.queryByText('知识点练习')).not.toBeInTheDocument();
    expect(screen.queryByText('章节练习')).not.toBeInTheDocument();
    // The state each level is in is still stated — that is what this page owns.
    expect(screen.getAllByText('学习中').length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------- the knowledge point's AI action

describe('Cs408KnowledgeWorkspace knowledge point AI', () => {
  beforeEach(() => { sectionCode = '1.1'; nodeCode = 'node-1'; });

  /** Select the fixture's leaf, which the plan publishes with a canonical code. */
  async function selectLeaf(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));
  }

  it('offers ONE way into the assistant, for the selected point, carrying the paper and the code', async () => {
    const user = userEvent.setup();
    await renderWorkspace();
    await selectLeaf(user);

    const ask = screen.getByRole('link', { name: '围绕此知识点问 AI' });
    const href = ask.getAttribute('href') ?? '';
    // The paper, the point's canonical CODE (an identity, never its title) and — for the learner
    // to read — the title the page itself is showing.
    expect(href).toContain('/exam/cs408/ask');
    expect(href).toContain('module=data_structure');
    expect(href).toContain('knowledge_point=leaf-1');
    expect(href).toContain('knowledge_point_title=');
    // It is a link, not a chat box: no second conversation opens inside the outline.
    expect(screen.queryByPlaceholderText(/问关于/)).not.toBeInTheDocument();
  });

  it('carries a synthetic node as its code and its title, for the model to read', async () => {
    // `_leaf:<path>` is the code the API mints for a node the seed publishes none for. It is
    // still this node's identity in this module — the state update stores exactly this string —
    // so the action is offered, with the node's own title as the name the model is given: a
    // path is not something a model can reason about, and most of this module's leaves are
    // published this way.
    nodeCode = '_leaf:2.1.1';
    const user = userEvent.setup();
    await renderWorkspace();
    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: '查看 顺序表操作' }));

    expect(screen.getByRole('heading', { name: '顺序表操作' })).toBeInTheDocument();
    const href = screen.getByRole('link', { name: '围绕此知识点问 AI' }).getAttribute('href') ?? '';
    expect(href).toContain(`knowledge_point=${encodeURIComponent('_leaf:2.1.1')}`);
    expect(href).toContain(`knowledge_point_title=${encodeURIComponent('顺序表操作')}`);
  });

});

// ---------------------------------------------------------------- what this page is not

describe('Cs408KnowledgeWorkspace owns nothing but the outline', () => {
  beforeEach(() => { sectionCode = '1.1'; nodeCode = 'node-1'; });

  it('carries no tools of its own, because 对话 and 资料库 are pages of the paper', async () => {
    await renderWorkspace();

    // Both are first-level tabs in the strip above — the same rank as 知识脉络 itself. A tool
    // that also lives in this page's body is a second navigation for one destination, and it
    // made the outline answer for the whole space.
    expect(screen.queryByText(/问 AI/)).not.toBeInTheDocument();
    expect(screen.queryByText('暂未开放')).not.toBeInTheDocument();
    expect(screen.queryByText(/· 工具/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /工具/ })).not.toBeInTheDocument();
  });

  it('draws no visible page title, because the open tab above already names the page', async () => {
    await renderWorkspace();

    // The heading is in the document — a page is a document, and this is what a screen reader
    // announces — but it is not drawn: the tab strip says 知识脉络 by marking that tab.
    const heading = screen.getByRole('heading', { level: 1, name: '知识脉络' });
    expect(heading).toHaveClass('sr-only');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });

  it('says what is open in the column beside the outline', async () => {
    const user = userEvent.setup();
    await renderWorkspace();

    expect(screen.getByText('从目录开始')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));

    // The selected knowledge point replaces the hint, and it is the paper's material that did NOT.
    expect(screen.queryByText('从目录开始')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '插入操作' })).toBeInTheDocument();
  });
});
