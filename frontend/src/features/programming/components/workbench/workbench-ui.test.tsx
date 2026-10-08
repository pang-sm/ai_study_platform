import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from '@/test/render-app';

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: post, PUT: put },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const fail = (status: number, detail: unknown) => ({
  data: undefined,
  error: { detail },
  response: { ok: false, status },
});

const BANK = {
  items: [
    { id: 7, title: '两数之和', curriculum_module: '控制流与函数', personal_progress: { personal_status: 'not_started' } },
    { id: 8, title: '回文数', curriculum_module: '控制流与函数', personal_progress: { personal_status: 'not_started' } },
  ],
  total: 2,
  status_counts: { passed: 0, not_started: 2, needs_improvement: 0 },
};

/** What the mock answers for one analysis — set per test to drive success or failure. */
let analyze: (body: Record<string, unknown>) => unknown = () => ok({ answer: '', request_id: 'req-1' });

const startWorkspace = (id: number) =>
  ok({
    exercise: { id, title: '两数之和', starter_files: [{ path: 'main.py', content: '# 在这里编写代码\n' }] },
    project: {
      id: 50 + id,
      entry_file: 'main.py',
      main_class: null,
      language: 'Python',
      files: [{ id: 90 + id, relative_path: 'main.py', filename: 'main.py', content: '# 在这里编写代码\n' }],
    },
    resumed: false,
  });

beforeEach(() => {
  window.localStorage.clear();
  get.mockReset();
  post.mockReset();
  put.mockReset();
  analyze = () => ok({ answer: '先从数组里取出每个数。', request_id: 'req-1' });

  get.mockImplementation(async (url: string) => {
    if (url === '/programming/onboarding') {
      return ok({ main_language: 'Python', selected_languages: ['Python'], onboarding_completed: true });
    }
    if (url === '/programming/exercises') return ok(BANK);
    if (url === '/programming/exercises/{exercise_id}') return ok({ exercise: { id: 7, title: '两数之和', statement: '给定数组，返回下标。' } });
    if (url === '/programming/records') return ok({ records: [], next_cursor: null, has_more: false });
    // The entitled model menu the AI 教练's picker reads — the SAME endpoint AI 问答 uses.
    if (url === '/ai/models') {
      return ok({
        options: [
          { model: 'deepseek-flash', display_name: 'DeepSeek V4', provider: 'deepseek', thinking: false },
          { model: 'qwen3.8-flash', display_name: 'qwen3.8-flash', provider: 'qwen', thinking: false },
        ],
        recommended_model_id: 'deepseek-flash',
      });
    }
    return ok({});
  });

  post.mockImplementation(async (url: string, options?: { body?: Record<string, unknown> }) => {
    if (url === '/programming/exercises/{exercise_id}/start') return startWorkspace(7);
    if (url === '/code/analyze') return analyze(options?.body ?? {});
    return ok({});
  });

  put.mockImplementation(async () => ok({}));
});

const workbenchHeader = () => document.querySelector('.wb__bar') as HTMLElement;
const nav = () => document.querySelector('.wb__nav') as HTMLElement;
const crumbTitle = () => document.querySelector('.wb__crumb-title')?.textContent;
const analyzeCalls = () => post.mock.calls.filter(([url]) => url === '/code/analyze');
const lastAnalyzeBody = () =>
  (analyzeCalls().at(-1) as unknown as [string, { body: Record<string, unknown> }])[1].body;
const modelTrigger = () => screen.findByRole('button', { name: '选择回答使用的模型' });

async function askHint(user: ReturnType<typeof userEvent.setup>) {
  const hint = await screen.findByRole('button', { name: '给我提示' });
  await waitFor(() => expect(hint).toBeEnabled());
  await user.click(hint);
  return hint;
}

/** Pick a concrete model from the coach's own menu, exactly as a learner would. */
async function chooseModel(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(await modelTrigger());
  await user.click(await screen.findByRole('menuitem', { name: label }));
}

describe('the workbench top bar', () => {
  it('no longer repeats the space link: 编程学习 lives in the global nav, not the toolbar', async () => {
    renderApp('/programming/workbench?language=python&exercise=7');
    await screen.findByRole('button', { name: '收起题目栏' });

    const header = workbenchHeader();
    // The shell's own 主导航 still offers 编程学习; the toolbar must not repeat it, in any form.
    expect(within(header).queryByText(/编程学习/)).not.toBeInTheDocument();
    expect(within(header).queryByRole('link', { name: /编程学习/ })).not.toBeInTheDocument();
    // And no icon-only back button stands in its place.
    expect(within(header).queryByRole('link', { name: /返回/ })).not.toBeInTheDocument();
    // The leftmost control is the language switcher.
    expect(within(header).getByRole('combobox', { name: '切换编程语言' })).toBeInTheDocument();
  });
});

describe('the题目栏 collapse', () => {
  it('opens expanded, collapses to a rail, keeps the centre, and reopens', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    // Expanded by default: the bank's head and its count are on screen.
    expect(await screen.findByText('共 2 道')).toBeInTheDocument();
    expect(within(nav()).getByText('题目')).toBeInTheDocument();
    const collapse = screen.getByRole('button', { name: '收起题目栏' });
    expect(collapse).toHaveAttribute('title', '收起题目栏');

    await user.click(collapse);

    // Collapsed: the bank is gone and only the way back is left, as a rail with no题 content.
    const expand = await screen.findByRole('button', { name: '展开题目栏' });
    expect(expand).toHaveAttribute('title', '展开题目栏');
    expect(screen.queryByText('共 2 道')).not.toBeInTheDocument();
    expect(screen.queryByText('搜索题目')).not.toBeInTheDocument();

    // The centre column survived the collapse — the code editor is still there.
    expect(screen.getByRole('heading', { name: '代码' })).toBeInTheDocument();
    expect(document.querySelector('.wb__body--rail-collapsed')).not.toBeNull();

    // The preference is remembered on the device.
    expect(window.localStorage.getItem('zhixue:programming:exercise-rail-collapsed')).toBe('1');

    await user.click(expand);

    // Reopened: the bank's head returns and the rail modifier is gone.
    expect(await screen.findByText('共 2 道')).toBeInTheDocument();
    expect(document.querySelector('.wb__body--rail-collapsed')).toBeNull();
  });

  it('remembers a collapsed rail across a reload', async () => {
    window.localStorage.setItem('zhixue:programming:exercise-rail-collapsed', '1');
    renderApp('/programming/workbench?language=python&exercise=7');

    expect(await screen.findByRole('button', { name: '展开题目栏' })).toBeInTheDocument();
    expect(screen.queryByText('共 2 道')).not.toBeInTheDocument();
  });
});

describe('the AI 教练', () => {
  it('does not fire a second request while one is in flight', async () => {
    let release: ((value: unknown) => void) | undefined;
    analyze = () => new Promise((resolve) => { release = resolve; });
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    const hint = await askHint(user);

    expect(await screen.findByText('正在分析…')).toBeInTheDocument();
    // The quick entry is disabled while the answer is on its way, so a second click is a no-op.
    expect(hint).toBeDisabled();
    await user.click(hint);
    expect(analyzeCalls()).toHaveLength(1);

    release?.(ok({ answer: '先想清楚输入与输出。', request_id: 'req-1' }));
    expect(await screen.findByText(/先想清楚输入与输出/)).toBeInTheDocument();
  });

  it('recovers after a failed request: the input works again and the question can be retried', async () => {
    analyze = () => fail(500, { detail: 'boom' });
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    await askHint(user);

    expect(await screen.findByText(/这次分析没有成功/)).toBeInTheDocument();
    // The composer is operable again and no fake answer was invented.
    expect(screen.getByLabelText('向 AI 教练提问')).toBeEnabled();
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();

    // Retrying the same question succeeds once the transient failure clears.
    analyze = () => ok({ answer: '这次成功了。', request_id: 'req-2' });
    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText(/这次成功了/)).toBeInTheDocument();
  });
});

describe('the project editor', () => {
  it('shows the actual project files and switches the editor to each file', async () => {
    post.mockImplementation(async (url: string, options?: { body?: Record<string, unknown> }) => {
      if (url === '/programming/exercises/{exercise_id}/start') {
        return ok({
          exercise: { id: 7, title: '图书馆', starter_files: [
            { path: 'src/Main.java', content: 'class Main {}' },
            { path: 'src/Book.java', content: 'class Book {}' },
          ] },
          project: {
            id: 57, entry_file: 'src/Main.java', main_class: 'Main', language: 'Java',
            files: [
              { id: 91, relative_path: 'src/Main.java', filename: 'Main.java', content: 'class Main {}' },
              { id: 92, relative_path: 'src/Book.java', filename: 'Book.java', content: 'class Book {}' },
            ],
          },
          resumed: false,
        });
      }
      if (url === '/code/analyze') return analyze(options?.body ?? {});
      return ok({});
    });
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=java&exercise=7');

    const bookTab = await screen.findByRole('tab', { name: 'src/Book.java' });
    expect(screen.getByRole('tab', { name: 'src/Main.java' })).toHaveAttribute('aria-selected', 'true');
    await user.click(bookTab);
    expect(bookTab).toHaveAttribute('aria-selected', 'true');
    const editor = screen.getByRole('textbox', { name: 'Java src/Book.java 代码编辑器' });
    expect(editor).toHaveTextContent('class Book {}');
    await user.click(editor);
    await user.keyboard('{Control>}a{/Control}class Book changed');
    await user.click(screen.getByRole('tab', { name: 'src/Main.java' }));
    await user.click(bookTab);
    expect(editor).toHaveTextContent('class Book changed');
    await user.click(screen.getByRole('button', { name: '保存' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/code/projects/{project_id}/files/{file_id}', expect.objectContaining({
      params: { path: { project_id: 57, file_id: 92 } },
      body: { username: '', content: 'class Book changed' },
    })));
  });

  it('keeps the single-file exercise on the normal single-editor surface', async () => {
    renderApp('/programming/workbench?language=python&exercise=7');

    expect(await screen.findByText('main.py')).toBeInTheDocument();
    expect(screen.queryByRole('tablist', { name: '工程文件' })).not.toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Python 代码编辑器' })).toBeInTheDocument();
  });

  it('saves every changed project file before run, test, and submit', async () => {
    const sequence: string[] = [];
    const originalGet = get.getMockImplementation();
    get.mockImplementation(async (url: string, options?: unknown) => {
      if (url === '/programming/exercises/{exercise_id}') {
        return ok({ exercise: { id: 7, title: '图书馆', public_samples: [{ id: 'case-1' }] } });
      }
      return originalGet?.(url, options);
    });
    post.mockImplementation(async (url: string, options?: { body?: Record<string, unknown> }) => {
      if (url === '/programming/exercises/{exercise_id}/start') {
        return ok({
          exercise: { id: 7, title: '图书馆', starter_files: [], public_samples: [{ id: 'case-1' }] },
          project: {
            id: 57, entry_file: 'src/Main.java', main_class: 'Main', language: 'Java',
            files: [
              { id: 91, relative_path: 'src/Main.java', filename: 'Main.java', content: 'class Main {}' },
              { id: 92, relative_path: 'src/Book.java', filename: 'Book.java', content: 'class Book {}' },
            ],
          },
          resumed: false,
        });
      }
      if (url === '/code/analyze') return analyze(options?.body ?? {});
      if (url.endsWith('/run')) sequence.push('run');
      if (url.endsWith('/test')) sequence.push('test');
      if (url.endsWith('/submit')) sequence.push('submit');
      return ok({});
    });
    put.mockImplementation(async (url: string, options?: { body?: Record<string, unknown>; params?: { path?: { file_id?: number } } }) => {
      if (url === '/code/projects/{project_id}/files/{file_id}') {
        sequence.push(`save:${options?.params?.path?.file_id}:${String(options?.body?.content)}`);
      }
      return ok({});
    });
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=java&exercise=7');

    await screen.findByRole('tab', { name: 'src/Book.java' });
    const userEditor = screen.getByRole('textbox', { name: 'Java src/Main.java 代码编辑器' });
    await user.click(userEditor);
    await user.keyboard('{Control>}a{/Control}class Main changed');
    await user.click(screen.getByRole('tab', { name: 'src/Book.java' }));
    const bookEditor = screen.getByRole('textbox', { name: 'Java src/Book.java 代码编辑器' });
    await user.click(bookEditor);
    await user.keyboard('{Control>}a{/Control}class Book changed');
    for (const action of ['运行', '运行测试', '提交']) {
      sequence.length = 0;
      put.mockClear();
      post.mockClear();
      await user.click(screen.getByRole('button', { name: action }));
      await waitFor(() => expect(post.mock.calls.some(([url]) => url === `/programming/exercises/{exercise_id}/${action === '运行' ? 'run' : action === '运行测试' ? 'test' : 'submit'}`)).toBe(true));
      const projectSaves = put.mock.calls.filter(([url]) => url === '/code/projects/{project_id}/files/{file_id}');
      expect(projectSaves.map(([, options]) => (options as { params: { path: { file_id: number } } }).params.path.file_id)).toEqual([91, 92]);
      const operationIndex = post.mock.calls.findIndex(([url]) => String(url).endsWith(`/${action === '运行' ? 'run' : action === '运行测试' ? 'test' : 'submit'}`));
      expect(projectSaves).toHaveLength(2);
      expect(operationIndex).toBeGreaterThan(-1);
      expect(sequence).toEqual([
        'save:91:class Main changed',
        'save:92:class Book changed',
        action === '运行' ? 'run' : action === '运行测试' ? 'test' : 'submit',
      ]);
    }
  });

  it('removes the coach helper copy while keeping its composer available', async () => {
    renderApp('/programming/workbench?language=python&exercise=7');

    expect(await screen.findByLabelText('向 AI 教练提问')).toBeEnabled();
    expect(screen.queryByText('可以直接用上面的快捷入口，或在下面输入你的问题。教练会结合当前代码与最近一次运行/测试结果回答。')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();
  });

  it('reports a failed project save and does not start the judge action', async () => {
    put.mockRejectedValue(new TypeError('network error'));
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    const run = await screen.findByRole('button', { name: '运行' });
    await user.click(run);

    expect(await screen.findByText('文件保存没有成功，当前内容仍留在编辑器中，请重试。')).toBeInTheDocument();
    expect(post.mock.calls.some(([url]) => url === '/programming/exercises/{exercise_id}/run')).toBe(false);
  });
});

describe('the AI 教练', () => {
  it('sends the newly opened题目 as the exercise_id, never the one before it', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');
    await screen.findByText('共 2 道');

    // Open a different题 from the rail, then ask.
    await user.click(screen.getByRole('button', { name: /回文数/ }));
    await waitFor(() => expect(crumbTitle()).toBe('回文数'));

    await askHint(user);

    await waitFor(() => expect(analyzeCalls()).toHaveLength(1));
    const call = analyzeCalls()[0] as unknown as [string, { body: Record<string, unknown> }];
    expect(call[1].body.exercise_id).toBe(8);
  });

  it('starts a fresh thread when the open题 changes, so the old题 never rides along', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');
    await screen.findByText('共 2 道');

    await askHint(user);
    expect(await screen.findByText(/先从数组里取出每个数/)).toBeInTheDocument();

    // Opening another题 clears the transcript and the history sent with the next question.
    await user.click(screen.getByRole('button', { name: /回文数/ }));
    await waitFor(() => expect(crumbTitle()).toBe('回文数'));
    expect(screen.queryByText(/先从数组里取出每个数/)).not.toBeInTheDocument();

    await askHint(user);
    await waitFor(() => expect(analyzeCalls()).toHaveLength(2));
    const call = analyzeCalls()[1] as unknown as [string, { body: Record<string, unknown> }];
    expect(call[1].body.exercise_id).toBe(8);
    // No turn from the previous题 is carried into the new one's history.
    expect(call[1].body.chat_history ?? []).toEqual([]);
  });
});

describe('the AI 教练 model selection', () => {
  it('offers the same entitled menu AI 问答 uses and sends the chosen model', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    // Auto by default, labelled with the Router's own recommendation — never a provider name.
    expect(await modelTrigger()).toHaveTextContent('自动（推荐：DeepSeek V4）');

    await chooseModel(user, 'qwen3.8-flash');
    await askHint(user);

    await waitFor(() => expect(analyzeCalls()).toHaveLength(1));
    expect(lastAnalyzeBody().model_id).toBe('qwen3.8-flash');
    // A concrete pick leaves the CLASS preference empty, exactly like the chat contract.
    expect(lastAnalyzeBody().model_preference).toBe('');
    // …and it survives a reload on this device.
    expect(window.localStorage.getItem('programming.coachModel')).toBe('qwen3.8-flash');
  });

  it('keeps Auto as a null model_id, so an untouched device is unchanged', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    await modelTrigger();
    await askHint(user);

    await waitFor(() => expect(analyzeCalls()).toHaveLength(1));
    expect(lastAnalyzeBody().model_id).toBeNull();
  });

  it('switching the model keeps the conversation and the new choice rides the next request', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    await askHint(user);
    expect(await screen.findByText(/先从数组里取出每个数/)).toBeInTheDocument();
    expect(lastAnalyzeBody().model_id).toBeNull();

    await chooseModel(user, 'qwen3.8-flash');
    // The answer already on screen is not thrown away by a model change.
    expect(screen.getByText(/先从数组里取出每个数/)).toBeInTheDocument();

    await askHint(user);
    await waitFor(() => expect(analyzeCalls()).toHaveLength(2));
    expect(lastAnalyzeBody().model_id).toBe('qwen3.8-flash');
    // The earlier turn is still this题's context.
    expect(lastAnalyzeBody().chat_history).toEqual([
      { role: 'user', content: '这道题的解题思路是什么？先给我一个提示，不要直接给出完整代码。' },
      { role: 'assistant', content: '先从数组里取出每个数。' },
    ]);
  });

  it('switching题目 clears that题\'s thread but keeps the chosen model', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');
    await screen.findByText('共 2 道');

    await chooseModel(user, 'qwen3.8-flash');
    await askHint(user);
    expect(await screen.findByText(/先从数组里取出每个数/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /回文数/ }));
    await waitFor(() => expect(crumbTitle()).toBe('回文数'));
    // The new题 starts a fresh thread…
    expect(screen.queryByText(/先从数组里取出每个数/)).not.toBeInTheDocument();
    // …but the model choice is not part of the thread and is still in force.
    expect(await modelTrigger()).toHaveTextContent('qwen3.8-flash');

    await askHint(user);
    await waitFor(() => expect(analyzeCalls()).toHaveLength(2));
    expect(lastAnalyzeBody().model_id).toBe('qwen3.8-flash');
  });
});

describe('the AI 教练 collapse', () => {
  it('opens expanded, collapses to a rail, keeps the conversation, and reopens', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    await askHint(user);
    expect(await screen.findByText(/先从数组里取出每个数/)).toBeInTheDocument();

    const collapse = screen.getByRole('button', { name: '收起 AI 教练' });
    expect(collapse).toHaveAttribute('title', '收起 AI 教练');
    await user.click(collapse);

    // Collapsed: a rail with only the way back, and no chat, composer or picker on screen.
    const expand = await screen.findByRole('button', { name: '展开 AI 教练' });
    expect(expand).toHaveAttribute('title', '展开 AI 教练');
    expect(document.querySelector('.wb__body--coach-collapsed')).not.toBeNull();
    expect(screen.queryByText(/先从数组里取出每个数/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText('向 AI 教练提问')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '选择回答使用的模型' })).not.toBeInTheDocument();
    // The centre column survived it.
    expect(screen.getByRole('heading', { name: '代码' })).toBeInTheDocument();
    expect(window.localStorage.getItem('programming.coachCollapsed')).toBe('1');

    await user.click(expand);

    // Reopened: the conversation is still there, and the modifier is gone.
    expect(await screen.findByText(/先从数组里取出每个数/)).toBeInTheDocument();
    expect(document.querySelector('.wb__body--coach-collapsed')).toBeNull();
  });

  it('never fires an AI request just for collapsing or reopening', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');

    await screen.findByRole('button', { name: '收起 AI 教练' });
    expect(analyzeCalls()).toHaveLength(0);

    await user.click(screen.getByRole('button', { name: '收起 AI 教练' }));
    await user.click(await screen.findByRole('button', { name: '展开 AI 教练' }));

    expect(analyzeCalls()).toHaveLength(0);
  });

  it('remembers a collapsed coach across a reload', async () => {
    window.localStorage.setItem('programming.coachCollapsed', '1');
    renderApp('/programming/workbench?language=python&exercise=7');

    expect(await screen.findByRole('button', { name: '展开 AI 教练' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '收起 AI 教练' })).not.toBeInTheDocument();
  });

  it('collapses both rails at once, leaving only the way back on each side', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench?language=python&exercise=7');
    await screen.findByText('共 2 道');

    await user.click(screen.getByRole('button', { name: '收起题目栏' }));
    await user.click(await screen.findByRole('button', { name: '收起 AI 教练' }));

    expect(document.querySelector('.wb__body--rail-collapsed')).not.toBeNull();
    expect(document.querySelector('.wb__body--coach-collapsed')).not.toBeNull();
    expect(screen.getByRole('button', { name: '展开题目栏' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开 AI 教练' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '代码' })).toBeInTheDocument();
  });
});
