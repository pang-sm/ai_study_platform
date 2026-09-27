/**
 * The chat surface's streaming behaviour, seen from the DOM.
 *
 * The transport is mocked (not the component): each test drives the exact handlers the page
 * registered, so what is asserted is the page's own rules — accumulation, terminal state, the
 * Stop/Send switch, the action-row gate — rather than a replay of the wire protocol.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError } from '@/features/exam/api/content-status';

type StreamHandlers = {
  onStart?: (payload: { requestId: string | null; sessionId: number | null }) => void;
  onDelta?: (text: string) => void;
  onDone?: (payload: {
    requestId: string | null;
    sessionId: number | null;
    resolvedModel: string | null;
    references: { filename: string; snippet: string }[];
    finishReason: string | null;
    stopped: boolean;
  }) => void;
  onError?: (error: unknown) => void;
};
type StreamCall = { input: unknown; handlers: StreamHandlers; signal: AbortSignal };

const streamMock = vi.hoisted(() => ({ calls: [] as unknown[] }));
const chatApi = vi.hoisted(() => ({
  useScopedAiSessions: vi.fn(),
  fetchAiSessionTurns: vi.fn(),
  useCourseMaterialsForChat: vi.fn(),
  renameAiSession: vi.fn(),
}));
const libraryApi = vi.hoisted(() => ({ listLibraryMaterials: vi.fn(), uploadLibraryMaterial: vi.fn() }));
const attachmentApi = vi.hoisted(() => ({ uploadChatAttachment: vi.fn() }));

vi.mock('../api/ai-chat-stream', () => ({
  // A run that never settles on its own: the test decides when it ends, via the handlers.
  streamAiChat: (input: unknown, handlers: unknown, signal: unknown) => {
    streamMock.calls.push({ input, handlers, signal });
    return new Promise<void>(() => {});
  },
}));

// Only the network calls are stubbed: the query key the history list invalidates and the turn
// shapes are the real ones.
vi.mock('../api/ai-chat', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  ...chatApi,
}));
vi.mock('../api/attachments', () => attachmentApi);
// The library is the picker's own data source; only its two network calls are stubbed, so the
// query key and the row mapping under test are the real ones.
vi.mock('@/features/library/api/library', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  ...libraryApi,
}));

vi.mock('./model-selector', () => ({ ModelSelector: () => null }));

// The action row's own gate is what matters here, so the component is a visible marker.
vi.mock('@/components/learning/ai-feedback', () => ({
  AiFeedback: () => <button type="button">反馈操作</button>,
}));

vi.mock('@/features/auth/auth-context', () => ({
  useAuth: () => ({ user: null, isAuthenticated: false, isLoading: false, isError: false, refresh: vi.fn() }),
}));

import { ScopedAiChatWorkspace } from './ai-chat-page';

const calls = streamMock.calls as StreamCall[];

type AttachmentFixture = {
  materialId: number;
  filename: string;
  fileType: string;
  fileSize?: number;
  parseStatus: string;
  scopeType: 'course' | 'personal' | 'chat';
  sourceLabel: string;
};

function renderWorkspace() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ScopedAiChatWorkspace scope={{ kind: 'course', courseId: 'cs101', label: '数据结构' }} />
    </QueryClientProvider>,
  );
}

async function askQuestion(user: ReturnType<typeof userEvent.setup>, text: string): Promise<StreamCall> {
  await user.type(screen.getByRole('textbox', { name: '你的问题' }), text);
  await user.click(screen.getByRole('button', { name: '发送' }));
  await waitFor(() => expect(calls.length).toBeGreaterThan(0));
  return calls[calls.length - 1]!;
}

const emit = <K extends keyof StreamHandlers>(
  run: StreamCall,
  event: K,
  ...args: Parameters<NonNullable<StreamHandlers[K]>>
) => {
  const handler = run.handlers[event] as ((...values: unknown[]) => void) | undefined;
  act(() => { handler?.(...(args as unknown[])); });
};

const log = () => screen.getByRole('log').textContent ?? '';

type DonePayload = Parameters<NonNullable<StreamHandlers['onDone']>>[0];
const doneEvent = (over: Partial<DonePayload> = {}): DonePayload => ({
  requestId: 'req-1', sessionId: 12, resolvedModel: 'deepseek-flash', references: [], finishReason: 'stop', stopped: false, ...over,
});

beforeEach(() => {
  calls.length = 0;
  chatApi.useScopedAiSessions.mockReturnValue({ isPending: false, data: [] });
  chatApi.fetchAiSessionTurns.mockResolvedValue([]);
  chatApi.useCourseMaterialsForChat.mockReturnValue({ data: [{ id: 27, filename: '讲义.pdf' }] });
  libraryApi.listLibraryMaterials.mockResolvedValue([]);
});

describe('streaming answers', () => {
  it('appends deltas to the growing answer in order', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onDelta', '第一段');
    expect(log()).toContain('第一段');
    emit(run, 'onDelta', '第二段');

    expect(log()).toContain('第一段第二段');
    expect(document.querySelectorAll('[data-answer-card]').length).toBe(1);
  });

  it('stores the resolved model and references from the done event on that answer', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onDelta', '答案正文');
    emit(run, 'onDone', doneEvent({ references: [{ filename: 'a.pdf', snippet: '引用片段' }] }));

    expect(log()).toContain('答案正文');
    expect(screen.getByText('a.pdf')).toBeInTheDocument();
    expect(screen.getByText('引用片段')).toBeInTheDocument();
    expect(document.querySelector('[data-resolved-model="deepseek-flash"]')).toBeTruthy();
  });

  it('shows a light loading region before the first token', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askQuestion(user, '解释链表');

    expect(screen.getByRole('status', { name: '正在作答' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '反馈操作' })).not.toBeInTheDocument();
  });

  it('swaps the send control for a Stop control while generating, and back once done', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    expect(screen.queryByRole('button', { name: '发送' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '停止生成' })).toBeInTheDocument();

    emit(run, 'onDelta', '答案');
    emit(run, 'onDone', doneEvent());

    expect(screen.queryByRole('button', { name: '停止生成' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();
  });

  it('aborts the request when Stop is pressed and re-enables the composer', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    await user.click(screen.getByRole('button', { name: '停止生成' }));

    expect(run.signal.aborted).toBe(true);
    expect(screen.queryByRole('button', { name: '停止生成' })).not.toBeInTheDocument();
    const send = screen.getByRole('button', { name: '发送' });
    expect(send).toBeDisabled();
    await user.type(screen.getByRole('textbox', { name: '你的问题' }), '下一个问题');
    expect(send).toBeEnabled();
  });

  it('keeps the partial answer on Stop without appending any stop notice, and offers actions', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onStart', { requestId: 'req-1', sessionId: 12 });
    emit(run, 'onDelta', '半句答案');
    await user.click(screen.getByRole('button', { name: '停止生成' }));

    expect(log()).toContain('半句答案');
    expect(log()).not.toContain('停止');
    expect(screen.getByRole('button', { name: '反馈操作' })).toBeInTheDocument();
  });

  it('leaves no empty answer bubble when Stop lands before any text', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    await user.click(screen.getByRole('button', { name: '停止生成' }));

    expect(run.signal.aborted).toBe(true);
    expect(screen.queryByAltText('智学 AI')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '反馈操作' })).not.toBeInTheDocument();
  });

  it('marks the turn failed on an error event instead of showing raw detail', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onError', new Error('boom'));

    expect(screen.getByRole('alert')).toHaveTextContent('这次提问没有得到回答，再试一次通常就好了。');
  });

  it('replaces an infrastructure failure with product copy instead of raw detail', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onError', new ApiRequestError(503, { message: 'provider deepseek returned 502' }));

    const note = screen.getByRole('alert');
    expect(note).toHaveTextContent('AI 服务暂时不可用，稍后重试通常就好了。');
    expect(note).not.toHaveTextContent('deepseek');
  });

  it('hides the action row while streaming and shows it after a terminal event with text', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onDelta', '部分答案');
    expect(screen.queryByRole('button', { name: '反馈操作' })).not.toBeInTheDocument();

    emit(run, 'onDone', doneEvent());
    expect(screen.getByRole('button', { name: '反馈操作' })).toBeInTheDocument();
  });

  it('keeps an interrupted partial answer as a finished one, with its actions', async () => {
    // A provider that broke mid-answer: what was already read is the answer for this turn, and it
    // is finished — not an error card with the text hidden behind a failure notice.
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onStart', { requestId: 'req-interrupted', sessionId: 12 });
    emit(run, 'onDelta', '已经读到的这一段');
    emit(run, 'onError', new ApiRequestError(503, { message: 'stream interrupted' }));

    expect(screen.getByText('已经读到的这一段')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '反馈操作' })).toBeInTheDocument();
    expect(screen.queryByText('AI 服务暂时不可用，稍后重试通常就好了。')).not.toBeInTheDocument();
  });

  it('never shows the action row for an empty answer that still finished', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onDone', doneEvent());

    expect(screen.queryByRole('button', { name: '反馈操作' })).not.toBeInTheDocument();
  });
});

describe('attachments', () => {
  /** One library row, as `/library/materials` lists it. */
  const item = (over: Partial<AttachmentFixture> = {}): AttachmentFixture => ({
    materialId: 8,
    filename: '我的笔记.pdf',
    fileType: 'pdf',
    parseStatus: 'success',
    scopeType: 'personal',
    sourceLabel: '个人资料',
    ...over,
  });
  const fromCourse = (over: Partial<AttachmentFixture> = {}) =>
    item({ scopeType: 'course', sourceLabel: '数据结构', ...over });
  const fromChat = (over: Partial<AttachmentFixture> = {}) =>
    item({ scopeType: 'chat', sourceLabel: '聊天上传', ...over });

  async function openPicker(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: '添加附件' }));
    await user.click(screen.getByRole('menuitem', { name: '从资料库添加' }));
    return screen.findByRole('dialog', { name: '从资料库添加' });
  }

  /** jsdom will not let a real file picker run, so the input is handed a file list directly. */
  function chooseFiles(input: HTMLInputElement, files: File[]) {
    Object.defineProperty(input, 'files', { value: files, configurable: true });
    fireEvent.change(input);
  }

  it('exposes exactly the two attachment sources', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole('button', { name: '添加附件' }));
    expect(screen.getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['上传本地文件', '从资料库添加']);
  });

  it('opens the library dialog, whatever the file came from', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item()]);
    const user = userEvent.setup();
    renderWorkspace();

    await openPicker(user);
    expect(libraryApi.listLibraryMaterials).toHaveBeenCalled();
    expect(screen.getByRole('textbox', { name: '搜索资料库' })).toBeInTheDocument();
  });

  it('lists a course upload, a chat upload and a personal upload together, each named by where it came from', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([
      fromCourse({ materialId: 1, filename: '01_绪论.pdf', fileSize: 12 * 1024 * 1024 }),
      fromChat({ materialId: 2, filename: '聊天里的文件.txt', fileType: 'text', fileSize: 20 * 1024 }),
      item({ materialId: 3, filename: '我的笔记.pdf', fileSize: 2 * 1024 * 1024 }),
    ]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);

    await screen.findByText('01_绪论.pdf');
    // The row says where the file came from in words — never `course` / `chat` / `personal`.
    expect(screen.getByText('PDF · 12 MB · 数据结构')).toBeInTheDocument();
    expect(screen.getByText('文本文件 · 20 KB · 聊天上传')).toBeInTheDocument();
    expect(screen.getByText('PDF · 2.0 MB · 个人资料')).toBeInTheDocument();
    expect(screen.queryByText(/· course/)).not.toBeInTheDocument();
  });

  it('attaches files chosen from different sources in one go', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([
      fromCourse({ materialId: 1, filename: '01_绪论.pdf' }),
      fromChat({ materialId: 2, filename: '聊天里的文件.pdf' }),
      item({ materialId: 3, filename: '我的笔记.pdf' }),
    ]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await screen.findByText('01_绪论.pdf');

    for (const name of ['01_绪论.pdf', '聊天里的文件.pdf', '我的笔记.pdf']) {
      await user.click(screen.getByRole('checkbox', { name: new RegExp(name.replace('.', '\\.')) }));
    }
    expect(screen.getByText('已选择 3 项')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '添加' }));
    const pending = screen.getByLabelText('待发送附件');
    for (const name of ['01_绪论.pdf', '聊天里的文件.pdf', '我的笔记.pdf']) {
      expect(pending).toHaveTextContent(name);
    }
    expect(screen.queryByRole('dialog', { name: '从资料库添加' })).not.toBeInTheDocument();
  });

  it('re-reflects the files already attached when the picker is reopened', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item()]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await user.click(await screen.findByRole('checkbox', { name: /我的笔记\.pdf/ }));
    await user.click(screen.getByRole('button', { name: '添加' }));

    await openPicker(user);
    expect(await screen.findByRole('checkbox', { name: /我的笔记\.pdf/ })).toBeChecked();
  });

  it('lists a file that is still parsing but refuses to choose it', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item({ materialId: 11, filename: '还在解析.pdf', parseStatus: 'parsing' })]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);

    expect(await screen.findByText('还在解析.pdf')).toBeInTheDocument();
    expect(screen.getByText('处理中')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /还在解析\.pdf/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: '添加' })).toBeDisabled();
  });

  it('lists a file whose parse failed, as failed and unchoosable', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item({ materialId: 12, filename: '坏文件.pdf', parseStatus: 'failed' })]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);

    expect(await screen.findByText('坏文件.pdf')).toBeInTheDocument();
    expect(screen.getByText('解析失败')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /坏文件\.pdf/ })).toBeDisabled();
  });

  it('searches every source, and restores the whole list when the query is cleared', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([
      fromCourse({ materialId: 1, filename: '01_绪论.pdf' }),
      item({ materialId: 3, filename: '我的笔记.pdf' }),
    ]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await screen.findByText('01_绪论.pdf');

    // A course upload is found by the same search as a personal one.
    await user.type(screen.getByRole('textbox', { name: '搜索资料库' }), '绪论');
    expect(screen.queryByText('我的笔记.pdf')).not.toBeInTheDocument();
    expect(screen.getByText('01_绪论.pdf')).toBeInTheDocument();

    await user.clear(screen.getByRole('textbox', { name: '搜索资料库' }));
    expect(screen.getByText('我的笔记.pdf')).toBeInTheDocument();
  });

  it('says so when the search matches nothing', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item()]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await screen.findByText('我的笔记.pdf');

    await user.type(screen.getByRole('textbox', { name: '搜索资料库' }), '不存在的名字');
    expect(screen.getByText('没有找到相关资料')).toBeInTheDocument();
  });

  it('reports a library that would not load, and retries it', async () => {
    libraryApi.listLibraryMaterials.mockRejectedValueOnce(new ApiRequestError(500, null));
    libraryApi.listLibraryMaterials.mockResolvedValue([item()]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);

    expect(await screen.findByText('资料库加载失败')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('我的笔记.pdf')).toBeInTheDocument();
  });

  it('refreshes the list after an upload and chooses the file the server finished parsing', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValueOnce([]);
    libraryApi.listLibraryMaterials.mockResolvedValueOnce([item({ materialId: 21, filename: '新讲义.pdf' })]);
    libraryApi.uploadLibraryMaterial.mockResolvedValue(item({ materialId: 21, filename: '新讲义.pdf' }));
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await screen.findByText('资料库中还没有资料');

    // The dialog is portalled onto the document, so the picker's own input is found there.
    const input = document.querySelector<HTMLInputElement>('[role="dialog"] input[type="file"]');
    expect(input).toBeInstanceOf(HTMLInputElement);
    chooseFiles(input!, [new File(['x'], '新讲义.pdf', { type: 'application/pdf' })]);

    expect(libraryApi.uploadLibraryMaterial).toHaveBeenCalled();
    expect(await screen.findByText('新讲义.pdf')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /新讲义\.pdf/ })).toBeChecked();
    expect(screen.getByText('已选择 1 项')).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    libraryApi.listLibraryMaterials.mockResolvedValue([item()]);
    const user = userEvent.setup();
    renderWorkspace();
    await openPicker(user);
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '从资料库添加' })).not.toBeInTheDocument());
  });
});

describe('partial markdown', () => {
  it('renders unclosed emphasis, fences and math without crashing', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    emit(run, 'onDelta', '**未闭合 与 ```py\nprint( 与 $x');

    expect(screen.getByRole('log')).toBeInTheDocument();
    expect(log()).toContain('未闭合');
    // The conversation stays usable: the composer is still live.
    expect(screen.getByRole('button', { name: '停止生成' })).toBeInTheDocument();
  });
});

describe('abort lifecycle', () => {
  it('aborts the running stream when another history session is opened', async () => {
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 5, title: '旧会话', createdAt: new Date().toISOString() }],
    });
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    // The row that opens a conversation, not the menu that acts on it.
    await user.click(screen.getByRole('button', {
      name: (value: string) => value.startsWith('旧会话') && !value.includes('更多操作'),
    }));

    expect(run.signal.aborted).toBe(true);
    await waitFor(() => expect(chatApi.fetchAiSessionTurns).toHaveBeenCalledWith(5, expect.anything()));
  });

  it('aborts the running stream on unmount', async () => {
    const user = userEvent.setup();
    const view = renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    view.unmount();

    expect(run.signal.aborted).toBe(true);
  });

  it('aborts the running stream when a new conversation is started', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const run = await askQuestion(user, '解释链表');

    await user.click(screen.getByRole('button', { name: '新建对话' }));

    expect(run.signal.aborted).toBe(true);
    expect(screen.queryByRole('log')).not.toBeInTheDocument();
  });

  it('drops every event from an abandoned run instead of writing it into the next one', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const first = await askQuestion(user, '第一个问题');

    emit(first, 'onDelta', 'A-第一句');
    expect(log()).toContain('A-第一句');

    await user.click(screen.getByRole('button', { name: '新建对话' }));
    expect(first.signal.aborted).toBe(true);

    // The abandoned run keeps talking; none of it may appear anywhere.
    emit(first, 'onDelta', 'A-迟到');
    emit(first, 'onDone', doneEvent({ requestId: 'A' }));
    expect(screen.queryByText(/A-迟到/)).not.toBeInTheDocument();

    // A fresh question starts its own run, and the old one still cannot write into it.
    const second = await askQuestion(user, '第二个问题');
    emit(second, 'onDelta', 'B-答案');
    emit(first, 'onDelta', 'A-更迟');

    expect(log()).toContain('B-答案');
    expect(log()).not.toContain('A-更迟');
  });
});

describe('re-wording a question', () => {
  const STORED = [
    { id: 'stored-1', role: 'learner', text: '第一个问题', messageId: 501, state: 'done' },
    { id: 'stored-2', role: 'assistant', text: '第一个回答', state: 'done' },
    { id: 'stored-3', role: 'learner', text: '第二个问题', messageId: 502, state: 'done' },
    { id: 'stored-4', role: 'assistant', text: '第二个回答', state: 'done' },
    { id: 'stored-5', role: 'learner', text: '第三个问题', messageId: 503, state: 'done' },
    { id: 'stored-6', role: 'assistant', text: '第三个回答', state: 'done' },
  ];

  const historyRow = () => screen.getByRole('button', {
    name: (value: string) => value.startsWith('旧会话') && !value.includes('更多操作'),
  });
  const historyRows = () => screen.getAllByRole('button', {
    name: (value: string) => value.startsWith('旧会话') && !value.includes('更多操作'),
  });

  async function openConversation(user: ReturnType<typeof userEvent.setup>) {
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 7, title: '旧会话', createdAt: new Date().toISOString() }],
    });
    chatApi.fetchAiSessionTurns.mockImplementation(async (id: number) => (id === 7 ? STORED : []));
    renderWorkspace();
    await user.click(historyRow());
    await screen.findByText('第三个问题');
  }

  const editButton = (question: string) => screen.getByRole('button', { name: `编辑提问：${question}` });
  const editField = () => screen.getByRole('textbox', { name: '修改这条提问' });
  const editAction = (name: string) => within(screen.getByRole('log')).getByRole('button', { name });

  async function reWord(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
    await user.click(editButton(from));
    await user.clear(editField());
    await user.type(editField(), to);
    await user.click(editAction('发送'));
  }

  it('offers the pencil on a question, and never on an answer', async () => {
    const user = userEvent.setup();
    await openConversation(user);

    expect(editButton('第一个问题')).toBeInTheDocument();
    expect(editButton('第二个问题')).toBeInTheDocument();
    // An answer is not a question, so there is nothing to ask again.
    expect(screen.getAllByRole('button', { name: /^编辑提问：/ })).toHaveLength(3);
  });

  it('keeps the pencil in the message own action row, under the bubble', async () => {
    const user = userEvent.setup();
    await openConversation(user);

    const button = editButton('第二个问题');
    const message = button.closest('li')!;
    const bubble = within(message).getByText('第二个问题');

    // Same message as the bubble it belongs to…
    expect(message).toBe(bubble.closest('li'));
    // …and AFTER it in the message: the action row sits below, never beside the text.
    expect(bubble.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The row is right-aligned, so the action lines up with the bubble's own edge.
    expect(button.parentElement!.className).toContain('justify-end');
    // And the bubble is unchanged by it: the text is still the bubble's own direct content.
    expect(bubble.parentElement!.className).toContain('rounded-2xl');
  });

  it('opens the question in place, and cancelling leaves it as it was', async () => {
    const user = userEvent.setup();
    await openConversation(user);

    await user.click(editButton('第二个问题'));
    expect(editField()).toHaveValue('第二个问题');

    await user.clear(editField());
    await user.type(editField(), '改了一半');
    await user.click(editAction('取消'));

    expect(screen.queryByRole('textbox', { name: '修改这条提问' })).not.toBeInTheDocument();
    expect(log()).toContain('第二个问题');
    expect(calls).toEqual([]);
  });

  it('abandons the edit on Escape', async () => {
    const user = userEvent.setup();
    await openConversation(user);

    await user.click(editButton('第一个问题'));
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('textbox', { name: '修改这条提问' })).not.toBeInTheDocument();
    expect(calls).toEqual([]);
  });

  it('re-asks the question in the SAME conversation, naming it as a version', async () => {
    const user = userEvent.setup();
    await openConversation(user);
    calls.length = 0;

    await reWord(user, '第二个问题', '换个问法');

    await waitFor(() => expect(calls.length).toBe(1));
    const run = calls[0]!;
    const input = run.input as { message: string; sessionId?: number; editSourceMessageId?: number };
    expect(input.message).toBe('换个问法');
    // The conversation is the one it was asked in, and the question it re-words is named, so the
    // server records a version instead of a new conversation.
    expect(input.sessionId).toBe(7);
    expect(input.editSourceMessageId).toBe(502);
    // Nothing was re-read and no conversation was created.
    expect(chatApi.fetchAiSessionTurns).toHaveBeenCalledTimes(1);
  });

  it('shows the new version and drops the turns that answered the old one', async () => {
    const user = userEvent.setup();
    await openConversation(user);

    await reWord(user, '第二个问题', '换个问法');

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(log()).toContain('第一个回答');
    expect(log()).toContain('换个问法');
    // Everything from the re-worded question onwards is replaced on screen: those turns answered
    // a question the learner has re-worded.
    expect(log()).not.toContain('第二个问题');
    expect(log()).not.toContain('第二个回答');
    expect(log()).not.toContain('第三个问题');
  });

  it('adds no row to the history list', async () => {
    const user = userEvent.setup();
    await openConversation(user);
    expect(historyRows()).toHaveLength(1);

    await reWord(user, '第二个问题', '换个问法');

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    // One conversation, still: re-wording a question is done INSIDE the conversation it is in.
    expect(historyRows()).toHaveLength(1);
    expect(historyRow()).toBeInTheDocument();
  });

  it('carries the question own attachments into the re-asked version', async () => {
    chatApi.fetchAiSessionTurns.mockImplementation(async (id: number) => (id === 7 ? [
      { id: 'stored-1', role: 'learner', text: '第一个问题', messageId: 501, state: 'done' },
      {
        id: 'stored-2', role: 'learner', text: '第二个问题', messageId: 502, state: 'done',
        attachments: [
          { materialId: 41, filename: '课件.txt', fileType: 'text', parseStatus: 'success' },
          { materialId: 42, filename: '删掉了.txt', fileType: 'text', parseStatus: 'deleted' },
        ],
      },
    ] : []));
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 7, title: '旧会话', createdAt: new Date().toISOString() }],
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(historyRow());
    await screen.findByText('第二个问题');
    calls.length = 0;

    await reWord(user, '第二个问题', '换个问法');

    await waitFor(() => expect(calls.length).toBe(1));
    // The file the question was asked about comes with it; the one that has since been deleted
    // does not — it stays in the history, but is not asked about again.
    expect((calls[0]!.input as { attachmentIds?: number[] }).attachmentIds).toEqual([41]);
  });
});

describe('renaming a conversation', () => {
  async function openRename(user: ReturnType<typeof userEvent.setup>) {
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 7, title: '数据结构哈希表', createdAt: new Date().toISOString() }],
    });
    renderWorkspace();
    await user.click(await screen.findByRole('button', { name: '数据结构哈希表 的更多操作' }));
    await user.click(await screen.findByRole('menuitem', { name: '重命名' }));
    return screen.getByRole('textbox', { name: '对话名称' });
  }

  it('renames in place and sends the new title', async () => {
    chatApi.renameAiSession.mockResolvedValue(undefined);
    const user = userEvent.setup();
    const field = await openRename(user);
    expect(field).toHaveValue('数据结构哈希表');

    await user.clear(field);
    await user.type(field, '哈希表梳理{Enter}');

    await waitFor(() => expect(chatApi.renameAiSession).toHaveBeenCalledWith(7, '哈希表梳理', expect.anything()));
  });

  it('keeps the old name when the field is left empty', async () => {
    const user = userEvent.setup();
    const field = await openRename(user);

    await user.clear(field);
    await user.keyboard('{Enter}');

    expect(chatApi.renameAiSession).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox', { name: '对话名称' })).not.toBeInTheDocument();
    expect(screen.getByText('数据结构哈希表')).toBeInTheDocument();
  });

  it('abandons the rename on Escape', async () => {
    const user = userEvent.setup();
    await openRename(user);

    await user.keyboard('{Escape}');

    expect(chatApi.renameAiSession).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox', { name: '对话名称' })).not.toBeInTheDocument();
  });

  it('reports a rename the server refused', async () => {
    chatApi.renameAiSession.mockRejectedValue(new ApiRequestError(404, { detail: '聊天记录不存在' }));
    const user = userEvent.setup();
    const field = await openRename(user);

    await user.type(field, '改不了{Enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent('聊天记录不存在');
  });
});

describe('stepping between versions of a question', () => {
  // Every stored turn carries its own id, as the server reports them.
  const EDITED_ID = 503;
  const ORIGINAL_ID = 401;

  const NEWER = [
    { id: 'stored-1', role: 'learner', text: '第一个问题', messageId: 501, state: 'done' },
    { id: 'stored-2', role: 'assistant', text: '第一个回答', messageId: 502, state: 'done' },
    {
      id: 'stored-3', role: 'learner', text: '换个问法', messageId: EDITED_ID, state: 'done',
      version: { index: 2, total: 2, hasPrevious: true, hasNext: false, previousMessageId: ORIGINAL_ID },
    },
    { id: 'stored-4', role: 'assistant', text: '换后的回答', messageId: 504, state: 'done' },
  ];
  const OLDER = [
    { id: 'stored-1', role: 'learner', text: '第一个问题', messageId: 501, state: 'done' },
    { id: 'stored-2', role: 'assistant', text: '第一个回答', messageId: 502, state: 'done' },
    {
      id: 'stored-3o', role: 'learner', text: '第二个问题', messageId: ORIGINAL_ID, state: 'done',
      version: { index: 1, total: 2, hasPrevious: false, hasNext: true, nextMessageId: EDITED_ID },
    },
    { id: 'stored-4o', role: 'assistant', text: '第二个回答', messageId: 402, state: 'done' },
  ];

  const historyRow = () => screen.getByRole('button', {
    name: (value: string) => value.startsWith('旧会话') && !value.includes('更多操作'),
  });
  const historyRows = () => screen.getAllByRole('button', {
    name: (value: string) => value.startsWith('旧会话') && !value.includes('更多操作'),
  });
  const previous = () => screen.getByRole('button', { name: /^上一个版本/ });
  const next = () => screen.getByRole('button', { name: /^下一个版本/ });
  const rowOf = (question: string) => screen.getByText(question).closest('li')!;

  async function openVersionedConversation(user: ReturnType<typeof userEvent.setup>) {
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 7, title: '旧会话', createdAt: new Date().toISOString() }],
    });
    chatApi.fetchAiSessionTurns.mockImplementation(
      async (_id: number, _scope: unknown, versionMessageId?: number) =>
        (versionMessageId === ORIGINAL_ID ? OLDER : NEWER),
    );
    renderWorkspace();
    await user.click(historyRow());
    await screen.findByText('换个问法');
    return user;
  }

  it('offers no arrows and no counter for a question with one version', async () => {
    chatApi.useScopedAiSessions.mockReturnValue({
      isPending: false,
      data: [{ id: 7, title: '旧会话', createdAt: new Date().toISOString() }],
    });
    chatApi.fetchAiSessionTurns.mockResolvedValue([
      { id: 'stored-1', role: 'learner', text: '第一个问题', messageId: 501, state: 'done' },
      { id: 'stored-2', role: 'assistant', text: '第一个回答', state: 'done' },
    ]);
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(historyRow());
    await screen.findByText('第一个问题');

    expect(screen.queryByRole('button', { name: /^上一个版本/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^下一个版本/ })).not.toBeInTheDocument();
    // No "1 / 1" either: a choice of one is not a choice.
    expect(screen.queryByText(/\d+ \/ \d+/)).not.toBeInTheDocument();
    // The pencil is still there, which is all a single-version question offers.
    expect(screen.getByRole('button', { name: '编辑提问：第一个问题' })).toBeInTheDocument();
  });

  it('counts the versions of a re-worded question', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);

    expect(within(rowOf('换个问法')).getByText('2 / 2')).toBeInTheDocument();
    expect(within(rowOf('换个问法')).getByRole('button', { name: /^上一个版本/ })).toBeEnabled();
    // There is nothing after the newest version.
    expect(within(rowOf('换个问法')).getByRole('button', { name: /^下一个版本/ })).toBeDisabled();
  });

  it('shows the previous version, whole, when asked for it', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);
    calls.length = 0;

    await user.click(previous());

    // The branch that was replaced: its question AND the answer that belonged to it.
    await screen.findByText('第二个问题');
    expect(log()).toContain('第二个回答');
    expect(log()).not.toContain('换个问法');
    expect(log()).not.toContain('换后的回答');
    expect(within(rowOf('第二个问题')).getByText('1 / 2')).toBeInTheDocument();
    expect(within(rowOf('第二个问题')).getByRole('button', { name: /^上一个版本/ })).toBeDisabled();
    expect(within(rowOf('第二个问题')).getByRole('button', { name: /^下一个版本/ })).toBeEnabled();
    // Reading a version asks for it by MEssage id; nothing was asked of the model.
    expect(chatApi.fetchAiSessionTurns).toHaveBeenLastCalledWith(7, expect.anything(), ORIGINAL_ID);
    expect(calls).toEqual([]);
  });

  it('goes back to the newer version again', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);
    await user.click(previous());
    await screen.findByText('第二个问题');

    await user.click(next());

    await screen.findByText('换个问法');
    expect(log()).toContain('换后的回答');
    expect(log()).not.toContain('第二个问题');
    expect(chatApi.fetchAiSessionTurns).toHaveBeenLastCalledWith(7, expect.anything(), EDITED_ID);
  });

  it('stays in the same conversation, with one row in the history list', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);
    expect(historyRows()).toHaveLength(1);

    await user.click(previous());
    await screen.findByText('第二个问题');
    await user.click(next());
    await screen.findByText('换个问法');

    expect(historyRows()).toHaveLength(1);
    expect(historyRow()).toBeInTheDocument();
  });

  it('asks the next question from the version on screen', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);
    await user.click(previous());
    await screen.findByText('第二个问题');
    calls.length = 0;

    await user.type(screen.getByRole('textbox', { name: '你的问题' }), '从旧版本继续');
    await user.click(screen.getByRole('button', { name: '发送' }));

    await waitFor(() => expect(calls.length).toBe(1));
    const input = calls[0]!.input as { sessionId?: number; continueFromMessageId?: number };
    // Same conversation, continued from the version being read — not from the newest one. The
    // id is the last message of the view, which is what names the branch the question joins.
    expect(input.sessionId).toBe(7);
    expect(input.continueFromMessageId).toBe(402);
  });

  it('still edits a question after switching versions', async () => {
    const user = userEvent.setup();
    await openVersionedConversation(user);
    await user.click(previous());
    await screen.findByText('第二个问题');
    calls.length = 0;

    await user.click(screen.getByRole('button', { name: '编辑提问：第二个问题' }));
    const field = screen.getByRole('textbox', { name: '修改这条提问' });
    await user.clear(field);
    await user.type(field, '又改一次');
    await user.click(within(screen.getByRole('log')).getByRole('button', { name: '发送' }));

    await waitFor(() => expect(calls.length).toBe(1));
    const input = calls[0]!.input as { message: string; sessionId?: number; editSourceMessageId?: number };
    expect(input.message).toBe('又改一次');
    // Editing the version on screen names THAT version as the one being re-worded.
    expect(input.sessionId).toBe(7);
    expect(input.editSourceMessageId).toBe(ORIGINAL_ID);
  });
});
