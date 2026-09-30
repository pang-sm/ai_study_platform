/**
 * 学习: the workspace around ONE knowledge point of the learner's own structure.
 *
 * What this file is really about, because each is a claim the page makes:
 *
 *   * the outline is the ACTIVE structure and nothing else — a course with no structure shows one
 *     sentence and one way forward, not a screen of zeroes
 *   * opening a point is FREE: nothing is generated until the learner asks, so stepping through
 *     the outline to find a topic never spends anything
 *   * the four states are the product's own, and reading an explanation is not a learning fact
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseKnowledge: vi.fn(),
  useCourseKnowledgeStructure: vi.fn(),
  useCourseKnowledgePointStudyContent: vi.fn(),
  useGenerateCourseKnowledgePointStudyContent: vi.fn(),
  useUpdateKnowledgePointStatus: vi.fn(),
}));

vi.mock('@/features/course/api/course', async (importOriginal) => {
  // The status vocabulary is real data, not a stub: a test that re-declared the four states could
  // pass while the page and the server disagreed about what they are called.
  const actual = (await importOriginal()) as {
    KNOWLEDGE_STATUSES: readonly string[];
    isKnowledgeStatus: (value: unknown) => boolean;
    knowledgeStatusLabel: (status: string | undefined) => string;
  };
  return {
    ...hooks,
    KNOWLEDGE_STATUSES: actual.KNOWLEDGE_STATUSES,
    isKnowledgeStatus: actual.isKnowledgeStatus,
    knowledgeStatusLabel: actual.knowledgeStatusLabel,
  };
});

const COURSE = '数据结构';
const URL = `/course/${encodeURIComponent(COURSE)}/study`;

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });
const idle = () => ({ isPending: false, isError: false, isSuccess: false, error: null, mutate: vi.fn() });

function point(id: number, title: string, status = 'not_started') {
  return { id, parent_id: 100, title, description: '', status, order_index: id, level: 2 };
}

function activeStructure() {
  return {
    course_id: COURSE,
    display: 'active',
    active: { id: 7, version: 1, status: 'active', source_mode: 'ai_generated',
              source_file_ids: [], title: '结构', goal: '',
              point_count: 3, chapter_count: 1, created_at: null, confirmed_at: null },
    draft: null,
    chapters: [],
    carry_over: null,
  };
}

function pointsPayload() {
  return {
    success: true,
    knowledge_points: [
      { id: 100, parent_id: null, title: '第2章 线性表', description: '', status: 'not_started',
        order_index: 0, level: 1 },
      point(1, '顺序表'),
      point(2, '链表'),
      point(3, '双链表'),
    ],
    roots: [100],
  };
}

function studyContent(pointId: number, citations: { filename: string; snippet: string }[] = []) {
  return {
    isPending: false, isError: false, isSuccess: true,
    data: { knowledgePointId: pointId, content: `## ${pointId} 的讲解\n\n正文`, citations },
    refetch: vi.fn(),
  };
}

/** A point with no stored explanation yet. */
function noContent() {
  return { isPending: false, isError: false, isSuccess: true, data: null, refetch: vi.fn() };
}

function mutateSpy() {
  const mutate = vi.fn();
  return { isPending: false, isError: false, mutate };
}

beforeEach(() => {
  vi.clearAllMocks();
  hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ id: COURSE, name: COURSE }] }));
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: COURSE }));
  hooks.useCourseKnowledge.mockReturnValue(settled(pointsPayload()));
  hooks.useCourseKnowledgeStructure.mockReturnValue(settled(activeStructure()));
  hooks.useCourseKnowledgePointStudyContent.mockImplementation((_course: string, id?: number) =>
    id === undefined ? { ...idle(), refetch: vi.fn() } : studyContent(id));
  hooks.useGenerateCourseKnowledgePointStudyContent.mockReturnValue(mutateSpy());
  hooks.useUpdateKnowledgePointStatus.mockReturnValue(mutateSpy());
});

async function renderStudy(path = URL) {
  const result = renderApp(path);
  await screen.findByRole('heading', { level: 1, name: '学习' });
  return result;
}

/* ------------------------------------------------------------------ EMPTY */

describe('a course with no structure', () => {
  beforeEach(() => {
    hooks.useCourseKnowledgeStructure.mockReturnValue(settled({
      course_id: COURSE, display: 'none', active: null, draft: null, chapters: [], carry_over: null,
    }));
    hooks.useCourseKnowledge.mockReturnValue(settled({ success: true, knowledge_points: [], roots: [] }));
  });

  it('offers one way forward instead of a screen of zeroes', async () => {
    await renderStudy();

    expect(screen.getByText('还没有知识结构')).toBeInTheDocument();
    expect(screen.getByText('先建立知识结构，再开始按知识点学习。')).toBeInTheDocument();

    const cta = screen.getByRole('link', { name: '建立知识结构' });
    expect(cta).toHaveAttribute('href', `/course/${encodeURIComponent(COURSE)}/knowledge`);
  });

  it('shows no counts, no empty material block and no explanation of its own', async () => {
    await renderStudy();

    expect(screen.queryByText(/可学知识点/)).not.toBeInTheDocument();
    expect(screen.queryByText(/可引用资料/)).not.toBeInTheDocument();
    expect(screen.queryByText(/上传资料后/)).not.toBeInTheDocument();
    expect(screen.queryByText('知识点学习')).not.toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ ACTIVE STRUCTURE */

describe('the outline', () => {
  it('is the active structure: its chapters, its points, in its order', async () => {
    await renderStudy();

    const nav = screen.getByRole('navigation', { name: '知识点' });
    expect(within(nav).getByText('第2章 线性表')).toBeInTheDocument();
    const titles = within(nav).getAllByRole('button')
      .map((button) => button.textContent ?? '')
      .filter((label) => label.includes('表') || label.includes('链表'));
    expect(titles.join('|')).toMatch(/顺序表[\s\S]*链表[\s\S]*双链表/);
  });

  it('shows each point with its state, and never as a percentage', async () => {
    hooks.useCourseKnowledge.mockReturnValue(settled({
      success: true,
      knowledge_points: [
        { id: 100, parent_id: null, title: '第2章 线性表', description: '', status: 'not_started',
          order_index: 0, level: 1 },
        point(1, '顺序表', 'not_started'),
        point(2, '链表', 'learning'),
        point(3, '双链表', 'mastered'),
        point(4, '循环链表', 'review_due'),
      ],
      roots: [100],
    }));

    await renderStudy();

    const nav = screen.getByRole('navigation', { name: '知识点' });
    for (const label of ['未学习', '学习中', '已学习', '待复习']) {
      expect(within(nav).getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(within(nav).queryByText(/%/)).not.toBeInTheDocument();
  });

  it('follows a new active version without a reload', async () => {
    const { unmount } = await renderStudy();
    unmount();

    hooks.useCourseKnowledge.mockReturnValue(settled({
      success: true,
      knowledge_points: [
        { id: 200, parent_id: null, title: '第3章 树', description: '', status: 'not_started',
          order_index: 0, level: 1 },
        { id: 9, parent_id: 200, title: '二叉树的遍历', description: '', status: 'not_started',
          order_index: 0, level: 2 },
      ],
      roots: [200],
    }));

    await renderStudy();

    const nav = screen.getByRole('navigation', { name: '知识点' });
    expect(within(nav).getByText('二叉树的遍历')).toBeInTheDocument();
    expect(within(nav).queryByText('顺序表')).not.toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ SELECTION */

describe('which point is open', () => {
  it('takes the point named in the URL', async () => {
    await renderStudy(`${URL}?knowledge_point_id=2`);
    expect(screen.getByRole('heading', { level: 2, name: '链表' })).toBeInTheDocument();
  });

  it('opens the point the learner is already in the middle of when the URL names none', async () => {
    hooks.useCourseKnowledge.mockReturnValue(settled({
      success: true,
      knowledge_points: [
        { id: 100, parent_id: null, title: '第2章 线性表', description: '', status: 'not_started',
          order_index: 0, level: 1 },
        point(1, '顺序表', 'mastered'),
        point(2, '链表', 'learning'),
        point(3, '双链表', 'review_due'),
      ],
      roots: [100],
    }));

    await renderStudy();
    expect(screen.getByRole('heading', { level: 2, name: '链表' })).toBeInTheDocument();
  });

  it('falls back to the first point of the structure, and writes that choice into the URL', async () => {
    const { router } = await renderStudy();

    expect(screen.getByRole('heading', { level: 2, name: '顺序表' })).toBeInTheDocument();
    await waitFor(() => {
      expect(router.state.location.search.knowledge_point_id).toBe(1);
    });
  });

  it('switches to the point the learner picked', async () => {
    const user = userEvent.setup();
    await renderStudy();

    const nav = screen.getByRole('navigation', { name: '知识点' });
    await user.click(within(nav).getByRole('button', { name: /双链表/ }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: '双链表' })).toBeInTheDocument();
    });
  });
});

/* ------------------------------------------------------------------ STATUS */

describe('the four states', () => {
  it('writes the chosen state through the product\'s own progress route', async () => {
    const user = userEvent.setup();
    const update = mutateSpy();
    hooks.useUpdateKnowledgePointStatus.mockReturnValue(update);

    await renderStudy(`${URL}?knowledge_point_id=2`);
    const group = screen.getByRole('group', { name: '这个知识点的学习状态' });
    await user.click(within(group).getByRole('button', { name: /已学习/ }));

    expect(update.mutate).toHaveBeenCalledWith({ pointId: 2, status: 'mastered' });
  });

  it('does not re-send a state the point is already in', async () => {
    const user = userEvent.setup();
    const update = mutateSpy();
    hooks.useUpdateKnowledgePointStatus.mockReturnValue(update);
    hooks.useCourseKnowledge.mockReturnValue(settled({
      success: true,
      knowledge_points: [
        { id: 100, parent_id: null, title: '第2章 线性表', description: '', status: 'not_started',
          order_index: 0, level: 1 },
        point(1, '顺序表', 'learning'),
      ],
      roots: [100],
    }));

    await renderStudy(`${URL}?knowledge_point_id=1`);
    const group = screen.getByRole('group', { name: '这个知识点的学习状态' });
    await user.click(within(group).getByRole('button', { name: /学习中/ }));

    expect(update.mutate).not.toHaveBeenCalled();
  });

  it('shows the stored state after a reload', async () => {
    hooks.useCourseKnowledge.mockReturnValue(settled({
      success: true,
      knowledge_points: [
        { id: 100, parent_id: null, title: '第2章 线性表', description: '', status: 'not_started',
          order_index: 0, level: 1 },
        point(1, '顺序表', 'review_due'),
      ],
      roots: [100],
    }));

    await renderStudy(`${URL}?knowledge_point_id=1`);

    const group = screen.getByRole('group', { name: '这个知识点的学习状态' });
    expect(within(group).getByRole('button', { name: /待复习/ })).toHaveAttribute('aria-pressed', 'true');
    for (const other of ['未学习', '学习中', '已学习']) {
      expect(within(group).getByRole('button', { name: new RegExp(other) })).toHaveAttribute('aria-pressed', 'false');
    }
  });
});

/* ------------------------------------------------------------------ MATERIAL */

describe('the explanation', () => {
  it('is not generated until the learner asks for it', async () => {
    const generate = mutateSpy();
    hooks.useGenerateCourseKnowledgePointStudyContent.mockReturnValue(generate);
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => noContent());

    await renderStudy();

    expect(generate.mutate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '开始学习' })).toBeInTheDocument();
  });

  it('is generated on the click, for the point being studied', async () => {
    const user = userEvent.setup();
    const generate = mutateSpy();
    hooks.useGenerateCourseKnowledgePointStudyContent.mockReturnValue(generate);
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => noContent());

    await renderStudy(`${URL}?knowledge_point_id=3`);
    await user.click(screen.getByRole('button', { name: '开始学习' }));

    expect(generate.mutate).toHaveBeenCalledWith({ pointId: 3 });
  });

  it('is not generated for a point the learner is only passing through', async () => {
    const user = userEvent.setup();
    const generate = mutateSpy();
    hooks.useGenerateCourseKnowledgePointStudyContent.mockReturnValue(generate);

    await renderStudy();
    const nav = screen.getByRole('navigation', { name: '知识点' });
    // The state mark contributes its own word to the row's accessible name, so this picks 链表
    // and not 双链表.
    await user.click(within(nav).getByRole('button', { name: '未学习链表' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2, name: '链表' })).toBeInTheDocument();
    });

    expect(generate.mutate).not.toHaveBeenCalled();
  });

  it('shows the stored explanation and the files that grounded it', async () => {
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => studyContent(1, [
      { filename: '计算机组成原理讲义.pdf', snippet: '顺序表用连续空间存放元素。' },
    ]));

    await renderStudy();

    expect(screen.getByRole('heading', { name: '学习内容' })).toBeInTheDocument();
    // The explanation itself, rendered from the stored markdown.
    expect(screen.getByText('正文')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '关联资料' })).toBeInTheDocument();
    expect(screen.getByText('计算机组成原理讲义.pdf')).toBeInTheDocument();
  });

  it('hides the material block entirely when nothing grounded the answer', async () => {
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => studyContent(1, []));

    await renderStudy();

    expect(screen.getByRole('heading', { name: '学习内容' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '关联资料' })).not.toBeInTheDocument();
    expect(screen.queryByText(/暂无可引用资料/)).not.toBeInTheDocument();
    expect(screen.queryByText(/暂无资料/)).not.toBeInTheDocument();
  });

  it('is usable in a course with no materials at all', async () => {
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => noContent());

    await renderStudy();

    expect(screen.getByRole('button', { name: '开始学习' })).toBeInTheDocument();
    expect(screen.queryByText(/可引用资料/)).not.toBeInTheDocument();
  });

  it('never shows internal vocabulary about how the content was produced', async () => {
    hooks.useCourseKnowledgePointStudyContent.mockImplementation(() => studyContent(1, [
      { filename: '讲义.pdf', snippet: '顺序表用连续空间存放元素。' },
    ]));

    await renderStudy();

    for (const forbidden of ['chunk', 'RAG', '置信度', '检索', '相似度', 'Student Twin', 'Scientific Runtime']) {
      expect(screen.queryByText(new RegExp(forbidden, 'i'))).not.toBeInTheDocument();
    }
  });
});

/* ------------------------------------------------------------------ ACTION */

describe('what the learner can do next', () => {
  it('hands the assistant the point being studied', async () => {
    await renderStudy(`${URL}?knowledge_point_id=2`);

    const link = screen.getByRole('link', { name: '围绕此知识点问 AI' });
    const href = link.getAttribute('href') ?? '';
    expect(href).toContain(`/course/${encodeURIComponent(COURSE)}/ask`);
    expect(href).toContain('knowledge_point_id=2');
    expect(href).toContain('knowledge_point_title=');
  });

  it('sends practice to the chapter the point sits under, never to a made-up point mapping', async () => {
    await renderStudy(`${URL}?knowledge_point_id=2`);

    const href = screen.getByRole('link', { name: '开始练习' }).getAttribute('href') ?? '';
    expect(href).toContain(`/course/${encodeURIComponent(COURSE)}/practice`);
    expect(href).toContain('chapter=');
    expect(href).not.toContain('knowledge_point_id');
  });
});
