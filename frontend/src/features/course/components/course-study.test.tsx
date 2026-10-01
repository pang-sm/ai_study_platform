/**
 * 学习: the workspace around ONE knowledge point of the learner's own structure.
 *
 * What this file is really about, because each is a claim the page makes:
 *
 *   * the point comes from the ACTIVE structure and nothing else — a course with no structure
 *     shows one sentence and one way forward, not a screen of zeroes
 *   * the page holds ONE point and owns no way to change it: 知识结构 is the only entry, so the
 *     workspace never grows a second list of points beside the one being read
 *   * opening a point is FREE: nothing is generated until the learner asks
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

describe('the point on screen', () => {
  it('states the chapter it sits under, and holds exactly that one point', async () => {
    await renderStudy();

    expect(screen.getByRole('heading', { level: 2, name: '顺序表' })).toBeInTheDocument();
    expect(screen.getByText('第2章 线性表')).toBeInTheDocument();
    // 知识结构 is the ONLY entry to this workspace, so there is no second list of points here.
    // One point is open, and its siblings are what 返回知识结构 is for.
    expect(screen.queryByRole('navigation', { name: '知识点' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /双链表/ })).not.toBeInTheDocument();
  });

  it('offers the way back to where a point is chosen', async () => {
    await renderStudy();

    const back = screen.getByRole('link', { name: '返回知识结构' });
    expect(back).toHaveAttribute('href', `/course/${encodeURIComponent(COURSE)}/knowledge`);
  });

  it('never states the point as a percentage', async () => {
    await renderStudy();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('follows a new active version instead of holding a superseded point', async () => {
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

    expect(screen.getByRole('heading', { level: 2, name: '二叉树的遍历' })).toBeInTheDocument();
    expect(screen.queryByText('顺序表')).not.toBeInTheDocument();
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

  it('holds no switcher of its own: the URL is the whole selection', async () => {
    await renderStudy(`${URL}?knowledge_point_id=3`);

    expect(screen.getByRole('heading', { level: 2, name: '双链表' })).toBeInTheDocument();
    // Nothing on the page can move to another point — that happens on 知识结构, which links here.
    expect(screen.queryByRole('combobox', { name: '选择知识点' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '知识点' })).not.toBeInTheDocument();
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

  it('is not generated for a point whose explanation is already stored', async () => {
    const generate = mutateSpy();
    hooks.useGenerateCourseKnowledgePointStudyContent.mockReturnValue(generate);

    await renderStudy(`${URL}?knowledge_point_id=2`);

    // Reading a stored explanation is free: only the learner pressing 开始学习 spends anything.
    expect(screen.getByText('正文')).toBeInTheDocument();
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

  it('sends practice the point ITSELF, so the page never asks which point again', async () => {
    // The point is the active structure's own node id — the identity the practice server
    // resolves the scope from. The chapter TITLE it used to send was presentation, and the
    // generator filed questions under whatever chapter the question bank happened to hold.
    await renderStudy(`${URL}?knowledge_point_id=2`);

    const href = screen.getByRole('link', { name: '开始练习' }).getAttribute('href') ?? '';
    expect(href).toContain(`/course/${encodeURIComponent(COURSE)}/practice`);
    expect(href).toContain('point=2');
    expect(href).not.toContain('chapter=');
  });
});
