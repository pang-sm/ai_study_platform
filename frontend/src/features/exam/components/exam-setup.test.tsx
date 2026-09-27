import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';
import { examProfileKey } from '@/features/exam/api/profile';

const { get, put } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: put } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

const publicSubject = (id: string, display_name: string) => ({
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

const lawMaster = {
  ...publicSubject('law_master_law', '法律硕士（法学）全国统考科目'),
  category: 'professional',
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
      description: '计算机学科专业基础综合（408）',
      subject_options: ['cs_408'],
      suggested_subjects: ['cs_408'],
    },
    {
      id: 'law_jm_law',
      display_name: '法律硕士（法学）',
      exam_type: 'postgraduate',
      availability: 'framework_only',
      has_content: false,
      description: '',
      subject_options: ['politics', 'english_1', 'law_master_law'],
      suggested_subjects: [],
    },
  ],
  subjects: [
    cs408,
    lawMaster,
    publicSubject('politics', '思想政治理论'),
    publicSubject('english_1', '英语（一）'),
    publicSubject('english_2', '英语（二）'),
    publicSubject('math_1', '数学（一）'),
    publicSubject('math_2', '数学（二）'),
  ],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: ['law_master_law', 'politics', 'english_1', 'english_2', 'math_1', 'math_2'],
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

const configured = {
  ...unconfigured,
  configured: true,
  selected_track: 'cs_408',
  selected_subjects: ['cs_408', 'politics', 'english_1', 'math_1'],
  target_exam_year: 2027,
  subjects: [cs408, publicSubject('politics', '思想政治理论'), publicSubject('english_1', '英语（一）'), publicSubject('math_1', '数学（一）')],
};

/** Whether the profile has been saved — the endpoint is a store, so a GET after a PUT answers it. */
let saved = false;

beforeEach(() => {
  saved = false;
  get.mockReset();
  put.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(saved ? configured : unconfigured);
    return ok({});
  });
  put.mockImplementation(async () => {
    saved = true;
    return ok(configured);
  });
});

const next = () => userEvent.click(screen.getByRole('button', { name: '下一步' }));
const previous = () => userEvent.click(screen.getByRole('button', { name: '上一步' }));

/** Walk to the confirmation step, taking the shipped direction's suggested combination. */
async function toConfirmation() {
  await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
  await userEvent.click(screen.getByRole('radio', { name: /计算机 408/ }));
  await userEvent.click(screen.getByRole('button', { name: '使用此组合' }));
  await next();
  await next();
}

describe('设置考试方案', () => {
  it('states the exam and its year at the top, before the steps begin', async () => {
    renderApp('/exam/setup');

    expect(await screen.findByRole('heading', { level: 1, name: '设置考试方案' })).toBeInTheDocument();
    // 考试类型 is not a step: only one type exists, so it is a statement beside the year field.
    expect(screen.getByText('目标考试')).toBeInTheDocument();
    expect(screen.getByText('全国硕士研究生招生考试（统考）')).toBeInTheDocument();
    expect(screen.getByLabelText('目标考试年份')).toBeInTheDocument();
    expect(screen.getByText('第 1 步，共 3 步 · 备考方向与专业课')).toBeInTheDocument();
  });

  it('echoes a year the learner already set, and never resets it', async () => {
    saved = true;
    renderApp('/exam/setup');

    expect(await screen.findByLabelText('目标考试年份')).toHaveValue(2027);

    // Saving a change to the subjects keeps the year the learner set last time.
    await next();
    await next();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['cs_408', 'politics', 'english_1', 'math_1'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('carries a year typed at the top into the plan it confirms', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    await userEvent.type(screen.getByLabelText('目标考试年份'), '2028');
    await next();
    await next();
    expect(screen.getByText('2028 全国硕士研究生招生考试（统考）')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: { selected_track: null, selected_subjects: [], target_exam_year: 2028, custom_subjects: [] },
      }),
    );
  });

  it('says what the 备考方向 is for, and never writes a combination on its own', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    expect(screen.getByText('备考方向')).toBeInTheDocument();
    expect(screen.getByText('用于帮助生成常见考试科目组合，不会自动修改你已经确认的考试科目。')).toBeInTheDocument();
    // Choosing a direction shows the suggestion and selects nothing: the learner confirms the
    // combination by clicking, never by picking a direction.
    await userEvent.click(screen.getByRole('radio', { name: /计算机 408/ }));
    expect(screen.getByText('常见组合')).toBeInTheDocument();
    expect(screen.getByText('思想政治理论 + 英语（一） + 数学（一） + 计算机学科专业基础 408')).toBeInTheDocument();
    expect(screen.getByText(/仅供参考，具体考试科目以目标院校当年招生专业目录为准。?/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ })).not.toBeChecked();

    // Neither public-course line was written either.
    await next();
    expect(screen.getByRole('checkbox', { name: /思想政治理论/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /英语（一）/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /数学（一）/ })).not.toBeChecked();

    await previous();
    await userEvent.click(screen.getByRole('button', { name: '使用此组合' }));
    expect(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ })).toBeChecked();
    await next();
    expect(screen.getByRole('checkbox', { name: /思想政治理论/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /英语（一）/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /数学（一）/ })).toBeChecked();
  });

  it('names the parts of the subject that has them, and not of the ones that do not', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    expect(screen.getByText('数据结构 · 计算机组成原理 · 操作系统 · 计算机网络')).toBeInTheDocument();
    expect(screen.getByText('完整学习功能已开放')).toBeInTheDocument();
    // The framework-only national paper says only that it is a framework.
    expect(screen.getAllByText('内容建设中').length).toBeGreaterThan(0);
  });

  it('asks before a suggested combination would drop what the learner chose', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    // The stored plan holds 数学（一）. Swap it for 数学（二）, then go back and take the suggested
    // combination, which holds 数学（一） and would therefore drop the choice just made.
    await next();
    await userEvent.click(screen.getByRole('radio', { name: /数学（二）/ }));
    await previous();
    await userEvent.click(screen.getByRole('button', { name: '使用此组合' }));

    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText(/数学（二）/)).toBeInTheDocument();
    // Backing out keeps every choice the learner made.
    await userEvent.click(within(dialog).getByRole('button', { name: '保留我的选择' }));
    await next();
    expect(screen.getByRole('radio', { name: /数学（二）/ })).toBeChecked();
  });

  it('applies the combination once the learner confirms the replacement', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    await userEvent.click(screen.getByRole('checkbox', { name: /法律硕士（法学）全国统考科目/ }));
    await userEvent.click(screen.getByRole('button', { name: '使用此组合' }));
    const dialog = await screen.findByRole('alertdialog');
    await userEvent.click(within(dialog).getByRole('button', { name: '替换' }));

    expect(screen.getByRole('checkbox', { name: /法律硕士（法学）全国统考科目/ })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ })).toBeChecked();
  });

  it('confirms the public courses on their own step, one line each', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();

    expect(screen.getByText('第 2 步，共 3 步 · 公共课')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /思想政治理论/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /英语（一）/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /英语（二）/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /数学（一）/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /不考统考数学/ })).toBeInTheDocument();
  });

  it('reads the plan back before it is saved, and can go back to change it', async () => {
    saved = true;
    renderApp('/exam/setup');
    await toConfirmation();

    const confirm = screen.getByRole('region', { name: '确认考试方案' });
    expect(within(confirm).getByText('2027 全国硕士研究生招生考试（统考）')).toBeInTheDocument();
    expect(within(confirm).getByText('备考方向 · 计算机 408')).toBeInTheDocument();
    // The plan reads as the subjects themselves, one per line, not as a dump of the form's fields.
    for (const name of ['思想政治理论', '英语（一）', '数学（一）', '计算机学科专业基础 408']) {
      expect(within(confirm).getByText(name)).toBeInTheDocument();
    }
    expect(within(confirm).getByText('具体考试科目以目标院校当年招生专业目录为准。')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '返回修改' }));
    expect(screen.getByText('第 2 步，共 3 步 · 公共课')).toBeInTheDocument();
  });

  it('saves the plan the learner confirmed and lands back in the exam space', async () => {
    const { router } = renderApp('/exam/setup');
    await toConfirmation();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        // `custom_subjects` is sent even when empty: it is a server-REPLACED list, so omitting it
        // would silently keep a subject the learner had removed.
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['politics', 'english_1', 'math_1', 'cs_408'],
          target_exam_year: null,
          custom_subjects: [],
        },
      }),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe('/exam'));
  });

  it('writes the server’s own answer into the context, so nothing has to be re-fetched', async () => {
    const { queryClient, router } = renderApp('/exam/setup');
    await toConfirmation();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() => expect(queryClient.getQueryData(examProfileKey)).toMatchObject({ configured: true }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/exam'));
  });

  it('swaps the English paper without disturbing anything else', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();
    await userEvent.click(screen.getByRole('radio', { name: /英语（二）/ }));
    await next();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['cs_408', 'politics', 'math_1', 'english_2'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('records an undecided English paper as nothing at all, not as a subject', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();

    // The third option is "not decided yet", not "I am not sitting English" — and picking it
    // writes no id of any kind into the plan.
    await userEvent.click(screen.getByRole('radio', { name: /暂未确定英语科目/ }));
    await next();
    expect(screen.queryByText('英语（一）')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['cs_408', 'politics', 'math_1'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('shows an undecided English paper as undecided when the screen is opened again', async () => {
    get.mockImplementation(async (path: string) => {
      if (path === '/exam/prep/catalog') return ok(catalog);
      if (path === '/exam/prep/profile') {
        return ok({
          ...configured,
          selected_subjects: ['cs_408', 'politics', 'math_1'],
          subjects: [cs408, publicSubject('politics', '思想政治理论'), publicSubject('math_1', '数学（一）')],
        });
      }
      return ok({});
    });
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();

    expect(screen.getByRole('radio', { name: /暂未确定英语科目/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /英语（一）/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /英语（二）/ })).not.toBeChecked();
  });

  it('swaps the maths paper without disturbing anything else', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();
    await userEvent.click(screen.getByRole('radio', { name: /数学（二）/ }));
    await next();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['cs_408', 'politics', 'english_1', 'math_2'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('replaces the professional paper, and stops claiming the old one is open', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    // Swap the studiable paper for a framework-only one: the plan must follow, and must stop
    // saying the old subject is open.
    await userEvent.click(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /法律硕士（法学）全国统考科目/ }));
    await next();
    await next();
    expect(screen.getByText('法律硕士（法学）全国统考科目')).toBeInTheDocument();
    expect(screen.queryByText('计算机学科专业基础 408')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['politics', 'english_1', 'math_1', 'law_master_law'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('drops the maths subject entirely when the learner sits no unified maths', async () => {
    saved = true;
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();
    await userEvent.click(screen.getByRole('radio', { name: /不考统考数学/ }));
    await next();
    // No maths subject is invented to stand for "I do not sit the unified maths paper".
    expect(screen.queryByText('数学（一）')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: 'cs_408',
          selected_subjects: ['cs_408', 'politics', 'english_1'],
          target_exam_year: 2027,
          custom_subjects: [],
        },
      }),
    );
  });

  it('keeps the learner’s own named subject separate from the catalogue', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });

    await userEvent.type(screen.getByLabelText('科目名称'), '数据结构与算法（自命题）');
    await userEvent.click(screen.getByRole('button', { name: '添加科目' }));
    await next();
    await next();
    // Named in the plan the learner owns, and marked as theirs rather than as a national paper.
    expect(screen.getByText('数据结构与算法（自命题）')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: {
          selected_track: null,
          selected_subjects: [],
          target_exam_year: null,
          custom_subjects: ['数据结构与算法（自命题）'],
        },
      }),
    );
  });

  it('lets an empty plan be saved deliberately, and says so rather than blocking it', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    await next();
    await next();

    expect(screen.getByText('还没有选择任何考试科目。保存后考研首页会提示你继续补充。')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: { selected_track: null, selected_subjects: [], target_exam_year: null, custom_subjects: [] },
      }),
    );
  });

  it('returns to the entry that sent the learner here, and only within this origin', async () => {
    const first = renderApp('/exam/setup?returnTo=%2F');
    await toConfirmation();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));
    await waitFor(() => expect(first.router.state.location.pathname).toBe('/'));
    first.unmount();

    const second = renderApp('/exam/setup?returnTo=%2F%2Fevil.example');
    await toConfirmation();
    await userEvent.click(screen.getByRole('button', { name: '确认考试方案' }));
    await waitFor(() => expect(second.router.state.location.pathname).toBe('/exam'));
  });

  it('walks backwards through the steps with 上一步', async () => {
    renderApp('/exam/setup');
    await screen.findByRole('heading', { level: 1, name: '设置考试方案' });
    // The first step has nowhere further back to go.
    expect(screen.queryByRole('button', { name: '上一步' })).not.toBeInTheDocument();

    await next();
    expect(screen.getByText('第 2 步，共 3 步 · 公共课')).toBeInTheDocument();
    await previous();
    expect(screen.getByText('第 1 步，共 3 步 · 备考方向与专业课')).toBeInTheDocument();

    await next();
    await next();
    expect(screen.getByText('第 3 步，共 3 步 · 确认考试方案')).toBeInTheDocument();
  });
});
