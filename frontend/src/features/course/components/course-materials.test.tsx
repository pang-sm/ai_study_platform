/**
 * The course space's 资料 page, which is the learner's whole library seen from inside a course.
 *
 * What it lists is every asset the learner owns — a course upload, a chat upload and a personal
 * upload alike — and what it offers per row is what can actually be done with that row: 查看 only
 * where a browser renders the type, 下载 wherever the server will serve it, and 删除 behind a
 * confirmation. The name itself is a label, not a second, invisible way into the preview.
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';
import { ApiRequestError } from '@/features/exam/api/content-status';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseMaterialUpload: vi.fn(),
}));

const library = vi.hoisted(() => ({
  useLibraryMaterials: vi.fn(),
  useLibraryDelete: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => ({
  ...hooks,
  MATERIAL_UPLOAD_ACCEPT: '.pdf',
  materialUploadErrorMessage: () => '上传没有成功。',
}));

// Only the two hooks are stubbed: the real error mapper is what the page shows a learner.
vi.mock('@/features/library/api/library', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  ...library,
}));

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });

/** One library row as `GET /library/materials` lists it. */
function material(over: Record<string, unknown> = {}) {
  return {
    materialId: 22,
    filename: '01_绪论.pdf',
    fileType: 'pdf',
    fileSize: 2 * 1024 * 1024,
    createdAt: '2026-09-21T10:30:00',
    parseStatus: 'success',
    scopeType: 'course',
    sourceLabel: '数据结构',
    canPreview: true,
    previewUrl: '/materials/22/preview',
    canDownload: true,
    downloadUrl: '/materials/22/download',
    ...over,
  };
}

let deleted: number[] = [];

beforeEach(() => {
  deleted = [];
  hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ course_id: 'cs101', course_name: '数据结构' }] }));
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: '数据结构' }));
  hooks.useCourseMaterialUpload.mockReturnValue({ isPending: false, isError: false, isSuccess: false, error: null, mutate: vi.fn() });
  library.useLibraryMaterials.mockReturnValue(settled([material()]));
  library.useLibraryDelete.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    mutate: (materialId: number, options?: { onSettled?: () => void }) => {
      deleted.push(materialId);
      // The mutation is what makes the list the server would return next; the hook is mocked, so
      // the test states that answer itself rather than pretending a server responded.
      library.useLibraryMaterials.mockReturnValue(settled([material()].filter((row) => row.materialId !== materialId)));
      options?.onSettled?.();
    },
  });
});

describe('CourseMaterialsPage', () => {
  it('lists every source the learner uploaded from, each named in their words', async () => {
    library.useLibraryMaterials.mockReturnValue(settled([
      material({ materialId: 22, filename: '01_绪论.pdf', scopeType: 'course', sourceLabel: '数据结构' }),
      material({ materialId: 24, filename: '聊天里的文件.txt', fileType: 'text', scopeType: 'chat', sourceLabel: '聊天上传' }),
      material({ materialId: 31, filename: '我的笔记.pdf', scopeType: 'personal', sourceLabel: '个人资料' }),
    ]));
    renderApp('/course/cs101/materials');

    expect(await screen.findByText('01_绪论.pdf')).toBeInTheDocument();
    // Each row states where its file came from in the learner's words — never `course` / `chat` /
    // `personal`. Scoped to the row, because the course's own name also appears in the switcher.
    const rowOf = (name: string) => screen.getByText(name).closest('li')!;
    expect(within(rowOf('01_绪论.pdf')).getByText('数据结构')).toBeInTheDocument();
    expect(within(rowOf('聊天里的文件.txt')).getByText('聊天上传')).toBeInTheDocument();
    expect(within(rowOf('我的笔记.pdf')).getByText('个人资料')).toBeInTheDocument();
  });

  it('never makes the file name a way into the preview', async () => {
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    // The name is a label: no link, no button, no clickable ancestor.
    expect(screen.queryByRole('link', { name: /01_绪论\.pdf/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /01_绪论\.pdf/ })).not.toBeInTheDocument();
    expect(screen.getByText('01_绪论.pdf').closest('a')).toBeNull();
    expect(screen.getByText('01_绪论.pdf').closest('button')).toBeNull();
  });

  it('offers 查看 / 下载 / 删除 for a file the browser can render', async () => {
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    expect(screen.getByText('PDF · 2.0 MB')).toBeInTheDocument();
    expect(screen.getByText('可用')).toBeInTheDocument();

    const view = screen.getByRole('link', { name: /查看/ });
    expect(view.getAttribute('href')).toContain('/materials/22/preview');
    expect(view).toHaveAttribute('target', '_blank');
    expect(screen.getByRole('link', { name: /下载/ }).getAttribute('href')).toContain('/materials/22/download');
    expect(screen.getByRole('button', { name: /删除/ })).toBeInTheDocument();
  });

  it('lays the header and every row out on ONE grid template', async () => {
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    const templateOf = (element: HTMLElement) =>
      element.className.split(/\s+/).find((name) => name.startsWith('sm:grid-cols-'));
    const header = screen.getByText('名称').parentElement as HTMLElement;
    const row = screen.getByText('01_绪论.pdf').closest('li')!.firstElementChild as HTMLElement;

    // Not two layouts that happen to agree today: the same declaration, so a longer label in one
    // of them cannot pull the columns apart.
    expect(templateOf(header)).toBeTruthy();
    expect(templateOf(row)).toBe(templateOf(header));

    // The actions keep their own column, right-aligned, so a row with fewer buttons does not
    // slide them left.
    const actions = screen.getByRole('button', { name: /删除/ }).parentElement as HTMLElement;
    expect(actions.className).toContain('sm:justify-end');
  });

  it('offers no 查看 for a type no browser previews, and says nothing about it', async () => {
    library.useLibraryMaterials.mockReturnValue(settled([
      material({ materialId: 8, filename: '01_绪论.pptx', fileType: 'pptx', canPreview: false, previewUrl: undefined }),
    ]));
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pptx');

    expect(screen.queryByRole('link', { name: /查看/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /查看/ })).not.toBeInTheDocument();
    // No standing explanation either: the row does not apologise for a control it never offered.
    expect(screen.queryByText(/暂不支持在线预览/)).not.toBeInTheDocument();

    expect(screen.getByRole('link', { name: /下载/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /删除/ })).toBeInTheDocument();
  });

  it('searches every source, not just this course', async () => {
    library.useLibraryMaterials.mockReturnValue(settled([
      material({ materialId: 22, filename: '01_绪论.pdf' }),
      material({ materialId: 24, filename: '聊天里的文件.txt', fileType: 'text', scopeType: 'chat', sourceLabel: '聊天上传' }),
    ]));
    const user = userEvent.setup();
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    await user.type(screen.getByRole('textbox', { name: '搜索资料' }), '聊天');
    expect(screen.queryByText('01_绪论.pdf')).not.toBeInTheDocument();
    expect(screen.getByText('聊天里的文件.txt')).toBeInTheDocument();

    await user.clear(screen.getByRole('textbox', { name: '搜索资料' }));
    expect(screen.getByText('01_绪论.pdf')).toBeInTheDocument();
  });

  it('asks before deleting, and cancelling deletes nothing', async () => {
    const user = userEvent.setup();
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    await user.click(screen.getByRole('button', { name: /删除/ }));
    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('删除“01_绪论.pdf”？');
    expect(dialog).toHaveTextContent(/历史聊天中的文件记录会保留/);

    await user.click(within(dialog).getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    expect(deleted).toEqual([]);
    expect(screen.getByText('01_绪论.pdf')).toBeInTheDocument();
  });

  it('removes the row once the deletion is confirmed', async () => {
    const user = userEvent.setup();
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    await user.click(screen.getByRole('button', { name: /删除/ }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: '删除' }));

    expect(deleted).toEqual([22]);
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('01_绪论.pdf')).not.toBeInTheDocument());
  });

  it('says a deletion failed in words a learner can use', async () => {
    library.useLibraryDelete.mockReturnValue({
      isPending: false,
      isError: true,
      error: new ApiRequestError(500, { detail: '服务器内部错误，请稍后重试。' }),
      mutate: vi.fn(),
    });
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    expect(screen.getByRole('alert')).toHaveTextContent('服务器内部错误，请稍后重试。');
  });

  it('offers the upload as the way out of an empty library', async () => {
    library.useLibraryMaterials.mockReturnValue(settled([]));
    renderApp('/course/cs101/materials');

    expect(await screen.findByText('暂无资料')).toBeInTheDocument();
    expect(screen.getByText(/上传课件、讲义或笔记/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上传资料' })).toBeInTheDocument();
  });

  it('says nothing was found when the search matches nothing', async () => {
    const user = userEvent.setup();
    renderApp('/course/cs101/materials');
    await screen.findByText('01_绪论.pdf');

    await user.type(screen.getByRole('textbox', { name: '搜索资料' }), '不存在的名字');
    expect(screen.getByText('没有找到相关资料')).toBeInTheDocument();
  });

  it('reads as loading while the library is in flight', async () => {
    library.useLibraryMaterials.mockReturnValue({ isPending: true, isError: false, isSuccess: false, data: undefined });
    renderApp('/course/cs101/materials');

    expect(await screen.findByText('正在读取资料…')).toBeInTheDocument();
    expect(screen.queryByText('暂无资料')).not.toBeInTheDocument();
  });

  it('reports a library that would not load, and retries it', async () => {
    const refetch = vi.fn();
    library.useLibraryMaterials.mockReturnValue({ isPending: false, isError: true, isSuccess: false, error: new ApiRequestError(500, null), refetch });
    const user = userEvent.setup();
    renderApp('/course/cs101/materials');

    expect(await screen.findByText(/资料暂时无法加载/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(refetch).toHaveBeenCalled();
  });
});
