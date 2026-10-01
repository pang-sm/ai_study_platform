/**
 * The 知识结构 page: how a course's knowledge structure comes into being, and what it looks like.
 *
 * Three things this file is really about, because each one is a claim the page makes:
 *
 *   * an empty course offers TWO ways forward and asks for nothing until one is chosen
 *   * a generated structure is a DRAFT — the page says so, and nothing becomes real until the
 *     learner confirms it (the confirm call is what the test watches for, not a re-fetch)
 *   * the page shows the structure itself and nothing besides: no 知识图谱 block, no nested
 *     section titles over the same list
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseKnowledgeStructure: vi.fn(),
  useCourseMaterials: vi.fn(),
  useCourseMaterialUpload: vi.fn(),
  useGenerateKnowledgeStructure: vi.fn(),
  useConfirmKnowledgeStructure: vi.fn(),
  useDiscardKnowledgeStructure: vi.fn(),
  useEditKnowledgeStructurePoint: vi.fn(),
  useDeleteKnowledgeStructurePoint: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => ({
  ...hooks,
  MATERIAL_UPLOAD_ACCEPT: '.pdf',
  materialUploadErrorMessage: () => '上传没有成功。',
  knowledgeStructureErrorMessage: () => '这一步没有完成，请稍后重试。',
}));

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });
const idle = () => ({ isPending: false, isError: false, isSuccess: false, error: null, mutate: vi.fn() });

function point(id: number, title: string, origin = 'source_extracted') {
  return { id, title, description: '', origin };
}

function activeStructure() {
  return {
    course_id: '数据结构',
    display: 'active',
    active: {
      id: 7, version: 1, status: 'active', source_mode: 'selected_materials',
      source_file_ids: [22], title: '来自 1 份资料的知识结构', goal: '',
      point_count: 4, chapter_count: 2,
      created_at: '2026-09-30T10:00:00', confirmed_at: '2026-09-30T10:05:00',
    },
    draft: null,
    chapters: [
      { id: 100, title: '第1章 绪论', description: '', points: [point(1, '数据结构基本概念')] },
      { id: 101, title: '第2章 线性表', description: '', points: [
        point(2, '顺序表'), point(3, '链表'), point(4, '双链表'),
      ] },
    ],
    carry_over: null,
  };
}

function draftStructure() {
  const base = activeStructure();
  return {
    ...base,
    display: 'draft',
    active: null,
    draft: { ...base.active, id: 8, version: 2, status: 'draft', confirmed_at: null,
             source_mode: 'ai_generated', source_file_ids: [] },
    chapters: [
      { id: 200, title: '第1章 绪论', description: '', points: [
        point(11, '数据结构基本概念', 'ai_inferred'),
      ] },
    ],
    carry_over: {
      available: true, has_progress: true, progressed_points: 4,
      matched_progressed_points: 1, unmatched_progressed_points: 3,
      active_point_count: 4, draft_point_count: 1,
      matched_point_count: 1, unmatched_active_points: 3,
    },
  };
}

const emptyStructure = {
  course_id: '数据结构', display: 'none', active: null, draft: null,
  chapters: [], carry_over: null,
};

function material(id: number, filename: string) {
  return { id, original_filename: filename, file_type: 'pdf', file_size: 1024,
           parse_status: 'success' };
}

/** Tick the Nth file in the picker; named so a missing row fails loudly, not silently. */
async function chooseFile(index: number) {
  const boxes = await screen.findAllByRole('checkbox');
  const box = boxes[index];
  if (!box) throw new Error(`expected at least ${index + 1} selectable materials`);
  await userEvent.click(box);
}

let generateInputs: unknown[] = [];
let confirmedIds: number[] = [];
let renamed: unknown[] = [];

beforeEach(() => {
  generateInputs = [];
  confirmedIds = [];
  renamed = [];
  hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ course_id: '数据结构', course_name: '数据结构' }] }));
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: '数据结构' }));
  hooks.useCourseKnowledgeStructure.mockReturnValue(settled(emptyStructure));
  hooks.useCourseMaterials.mockReturnValue(settled({
    course_id: '数据结构',
    items: [material(22, '数据结构课程讲义.pdf'), material(23, 'chapter4_Tree.pdf')],
    total: 2,
  }));
  hooks.useCourseMaterialUpload.mockReturnValue(idle());
  hooks.useGenerateKnowledgeStructure.mockReturnValue({
    ...idle(),
    mutate: (input: unknown) => { generateInputs.push(input); },
  });
  hooks.useConfirmKnowledgeStructure.mockReturnValue({
    ...idle(),
    mutate: (id: number) => { confirmedIds.push(id); },
  });
  hooks.useDiscardKnowledgeStructure.mockReturnValue(idle());
  hooks.useEditKnowledgeStructurePoint.mockReturnValue({
    ...idle(),
    mutate: (input: unknown) => { renamed.push(input); },
  });
  hooks.useDeleteKnowledgeStructurePoint.mockReturnValue(idle());
});

describe('an empty knowledge structure', () => {
  it('offers two ways forward and no form to fill in yet', async () => {
    renderApp('/course/数据结构/knowledge');

    expect(await screen.findByText('还没有知识结构')).toBeInTheDocument();
    expect(screen.getByText('你可以从已有资料生成，也可以让 AI 根据这门课程生成。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '从资料生成' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI 生成' })).toBeInTheDocument();

    // Nothing is asked for before the learner has chosen a direction.
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/补充要求/)).not.toBeInTheDocument();
  });

  it('lists this course’s own materials to choose from', async () => {
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: '从资料生成' }));

    const rows = await screen.findAllByRole('checkbox');
    expect(rows).toHaveLength(2);
    expect(screen.getByText('数据结构课程讲义.pdf')).toBeInTheDocument();
    expect(screen.getByText('chapter4_Tree.pdf')).toBeInTheDocument();
  });

  it('will not generate from files until at least one is chosen, and says why', async () => {
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: '从资料生成' }));

    const submit = screen.getByRole('button', { name: '生成知识结构' });
    expect(submit).toBeDisabled();
    expect(screen.getByText('请至少选择 1 份资料')).toBeInTheDocument();

    await chooseFile(1);
    expect(submit).toBeEnabled();
    expect(screen.getByText('已选 1 份资料')).toBeInTheDocument();
  });

  it('sends the chosen file ids, not the whole library', async () => {
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: '从资料生成' }));
    await chooseFile(1);
    await userEvent.click(screen.getByRole('button', { name: '生成知识结构' }));

    expect(generateInputs).toEqual([
      { sourceMode: 'selected_materials', materialIds: [23] },
    ]);
  });

  it('points at uploading when the course has no material at all', async () => {
    hooks.useCourseMaterials.mockReturnValue(settled({ course_id: '数据结构', items: [], total: 0 }));
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: '从资料生成' }));

    expect(await screen.findByText('还没有课程资料')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上传资料' })).toBeInTheDocument();
    // Still in the flow: the picker is where the learner came back to, not a different page.
    expect(screen.getByRole('button', { name: '返回' })).toBeInTheDocument();
  });

  it('asks for a goal, not for internal parameters', async () => {
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: 'AI 生成' }));

    expect(await screen.findByText('AI 生成知识结构')).toBeInTheDocument();
    for (const goal of ['期末考试', '系统学习', '自定义']) {
      expect(screen.getByRole('button', { name: goal })).toBeInTheDocument();
    }
    expect(screen.getByLabelText(/补充要求/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '期末考试' }));
    await userEvent.click(screen.getByRole('button', { name: '生成' }));

    expect(generateInputs).toEqual([
      { sourceMode: 'ai_generated', goal: '期末考试', requirement: '' },
    ]);
  });

  it('does not offer the postgraduate exam as a goal for a 专业学习 course', async () => {
    // 考研 has its own space, its own plan and its own progress. Offering it here would make
    // one word mean two different things on two pages of the same product. Scoped to the goal
    // fieldset, because the app's own navigation legitimately names the exam space.
    renderApp('/course/数据结构/knowledge');
    await userEvent.click(await screen.findByRole('button', { name: 'AI 生成' }));
    await screen.findByText('AI 生成知识结构');

    const goals = within(screen.getByRole('group', { name: '学习目标（可选）' }));
    expect(goals.getAllByRole('button').map((button) => button.textContent))
      .toEqual(['期末考试', '系统学习', '自定义']);
  });
});

describe('a generated structure is only a proposal', () => {
  beforeEach(() => {
    hooks.useCourseKnowledgeStructure.mockReturnValue(settled(draftStructure()));
  });

  it('states that it is a draft and what confirming would do to existing progress', async () => {
    renderApp('/course/数据结构/knowledge');

    expect(await screen.findByText('这是一份草稿，还没有生效')).toBeInTheDocument();
    const note = screen.getByText(/确认后，学习和练习就会按这份结构记录/);
    expect(note).toHaveTextContent('1 个已学过的知识点能对上，进度会保留');
    expect(note).toHaveTextContent('有 3 个已学过的知识点不在新结构里');
  });

  it('offers exactly 使用这个知识结构 / 重新生成 / 取消, and confirms only on the first', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('这是一份草稿，还没有生效');

    expect(screen.getByRole('button', { name: '使用这个知识结构' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新生成' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '取消' })).toBeInTheDocument();
    // Nothing was made active by merely looking at the draft.
    expect(confirmedIds).toEqual([]);

    await userEvent.click(screen.getByRole('button', { name: '使用这个知识结构' }));
    expect(confirmedIds).toEqual([8]);
  });

  it('lets a point be renamed before it is accepted', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('这是一份草稿，还没有生效');

    await userEvent.click(screen.getByRole('button', { name: '改名' }));
    const field = screen.getByLabelText('知识点名称');
    await userEvent.clear(field);
    await userEvent.type(field, '数据结构的基本概念');
    await userEvent.click(screen.getByRole('button', { name: '保存知识点名称' }));

    await waitFor(() => expect(renamed).toEqual([
      { structureId: 8, pointId: 11, title: '数据结构的基本概念' },
    ]));
  });

  it('marks a point the model supplied itself, when the rest came from the learner’s files', async () => {
    const mixed = draftStructure();
    hooks.useCourseKnowledgeStructure.mockReturnValue(settled({
      ...mixed,
      draft: { ...mixed.draft!, source_mode: 'selected_materials' },
      chapters: [{ id: 200, title: '第1章 绪论', description: '', points: [
        point(11, '数据结构基本概念', 'source_extracted'),
        point(12, '算法与复杂度', 'ai_inferred'),
      ] }],
    }));
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('这是一份草稿，还没有生效');

    // The file-backed point carries no marker; the one the model added on its own does.
    expect(within(screen.getByText('数据结构基本概念').closest('li')!).queryByText('AI 补充')).toBeNull();
    expect(within(screen.getByText('算法与复杂度').closest('li')!).getByText('AI 补充')).toBeInTheDocument();
  });

  it('carries no per-row marker when the whole structure is AI-generated', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('这是一份草稿，还没有生效');

    // Every row would say the same thing, which is a statement about the structure, not the row.
    expect(screen.queryByText('AI 补充')).not.toBeInTheDocument();
  });

  it('does not let a draft be studied from — a draft is not the course yet', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('这是一份草稿，还没有生效');

    // The rows are things to rename, move or delete. Opening one would be opening a point the
    // learner is not studying from, so a draft's points are plain text.
    expect(screen.queryByRole('link', { name: '数据结构基本概念' })).not.toBeInTheDocument();
  });
});

describe('an active knowledge structure', () => {
  beforeEach(() => {
    hooks.useCourseKnowledgeStructure.mockReturnValue(settled(activeStructure()));
  });

  it('shows the chapters and their points, with the counts as facts', async () => {
    renderApp('/course/数据结构/knowledge');

    expect(await screen.findByText('第1章 绪论')).toBeInTheDocument();
    expect(screen.getByText('第2章 线性表')).toBeInTheDocument();
    expect(screen.getByText('数据结构基本概念')).toBeInTheDocument();
    expect(screen.getByText('双链表')).toBeInTheDocument();
    expect(screen.getByText('4 个')).toBeInTheDocument();
    expect(screen.getAllByText('2 个').length).toBeGreaterThan(0);
  });

  it('offers 重新生成 rather than the two sources, until it is asked for', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('第1章 绪论');

    expect(screen.getByRole('button', { name: '重新生成' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '从资料生成' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '重新生成' }));
    expect(screen.getByRole('button', { name: '从资料生成' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI 生成' })).toBeInTheDocument();
    // The current structure is not edited while a replacement is being chosen.
    expect(screen.queryByRole('button', { name: '改名' })).not.toBeInTheDocument();
  });

  it('is not editable — a structure in use is changed by switching versions', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('第1章 绪论');
    expect(screen.queryByRole('button', { name: '改名' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument();
  });

  it('does not carry a 知识图谱 block, on any state of the page', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('第1章 绪论');
    expect(screen.queryByText(/知识图谱/)).not.toBeInTheDocument();
    expect(screen.queryByText(/知识点与脉络/)).not.toBeInTheDocument();
  });

  it('names the way in: a point opens the study workspace, carrying its own id', async () => {
    renderApp('/course/数据结构/knowledge');
    await screen.findByText('第1章 绪论');

    // This page is the ONLY entry to the workspace, so a point's name has to be the door. What
    // travels is the point's own id — never its chapter, and never a title the workspace would
    // have to match back to a point.
    expect(screen.getByRole('link', { name: '顺序表' })).toHaveAttribute(
      'href',
      `/course/${encodeURIComponent('数据结构')}/study?knowledge_point_id=2`,
    );
  });
});
