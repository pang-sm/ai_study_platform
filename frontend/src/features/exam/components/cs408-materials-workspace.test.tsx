import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: api.get, POST: api.post, DELETE: api.delete, PUT: vi.fn() },
  resolveApiResourceUrl: (url: string) => url,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

const catalog = {
  catalog_version: 'v2',
  exam_type: 'postgraduate',
  tracks: [
    { id: 'cs_408', display_name: '计算机 408', exam_type: 'postgraduate', availability: 'active', has_content: true, description: '', subject_options: ['cs_408'], suggested_subjects: ['cs_408'] },
  ],
  subjects: [{
    id: 'cs_408', display_name: '计算机学科专业基础 408', category: 'professional', availability: 'active',
    has_questions: true, has_past_papers: true, has_knowledge_tree: true, description: '',
    suggested_tracks: ['cs_408'],
    modules: [
      { id: 'data_structure', display_name: '数据结构' },
      { id: 'computer_organization', display_name: '计算机组成原理' },
      { id: 'operating_system', display_name: '操作系统' },
      { id: 'computer_network', display_name: '计算机网络' },
    ],
  }],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: [],
};

const profile = {
  configured: true, exam_type: 'postgraduate', selected_track: 'cs_408',
  selected_subjects: ['cs_408'], target_exam_year: 2027,
  subjects: catalog.subjects, custom_subjects: [],
};

/** ONE material as the module-scoped route answers it. */
const material = (over: Record<string, unknown> = {}) => ({
  id: 41,
  course_id: 'computer_organization_11408',
  subject_key: 'computer_organization',
  subject: '11408 计算机组成原理',
  file_type: 'pdf',
  original_filename: '计算机组成原理讲义.pdf',
  mime_type: 'application/pdf',
  file_size: 2048,
  parse_status: 'success',
  parse_progress: 100,
  chunk_count: 12,
  created_at: '2026-09-25T10:00:00+00:00',
  can_preview: true,
  preview_url: '/materials/41/preview',
  can_download: true,
  download_url: '/materials/41/download',
  ...over,
});

function mockApi({ items = [] as unknown[], fail = false } = {}) {
  api.get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(profile);
    if (path === '/exam/prep/math/taxonomy') return ok({ domains: [], variants: [], coverage: [] });
    if (path === '/exam/11408/subjects/{subject_key}/materials') {
      return fail
        ? { data: undefined, error: { detail: 'unavailable' }, response: { ok: false, status: 500 } }
        : ok({ subject_key: 'computer_organization', course_id: 'computer_organization_11408', items, total: items.length });
    }
    return ok({});
  });
  api.post.mockResolvedValue(ok({ subject_key: 'computer_organization', course_id: 'computer_organization_11408', success: true, material_id: 42 }));
  api.delete.mockResolvedValue(ok({ material_id: 41, deleted: true }));
}

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  api.delete.mockReset();
  mockApi();
});

const PAGE = '/exam/cs408/materials?module=computer_organization';

/** The page's own block, so a query never lands on the app shell's navigation instead. */
const page = () => screen.getByRole('region', { name: '资料库 · 计算机组成原理' });

/** The route is matched asynchronously, so nothing is on screen when `render` returns. */
async function renderPage() {
  const view = renderApp(PAGE);
  await screen.findByRole('region', { name: '资料库 · 计算机组成原理' });
  return view;
}

describe('Cs408MaterialsWorkspace', () => {
  it('reads THIS subject library, and shows an empty one as empty', async () => {
    await renderPage();

    expect(await within(page()).findByText('还没有资料')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(
      '/exam/11408/subjects/{subject_key}/materials',
      expect.objectContaining({ params: { path: { subject_key: 'computer_organization' } } }),
    );
    // Nothing is invented to fill the page: no row, no count, no example file.
    expect(within(page()).queryByRole('listitem')).not.toBeInTheDocument();
    expect(within(page()).queryByText(/\d+\s*(份|个文件|项)/)).not.toBeInTheDocument();
  });

  it('offers ONE upload action on an empty library, and no toolbar beside it', async () => {
    await renderPage();
    await within(page()).findByText('还没有资料');

    // The empty state is the call to action. A second 上传资料 in a toolbar above it would be
    // the same action twice, which the learner has to read twice to find out.
    expect(within(page()).getAllByRole('button', { name: '上传资料' })).toHaveLength(1);
    expect(within(page()).queryByLabelText('搜索资料')).not.toBeInTheDocument();
  });

  it('offers ONE upload action on a library that has files, in its toolbar', async () => {
    mockApi({ items: [material()] });
    await renderPage();
    await within(page()).findByText('计算机组成原理讲义.pdf');

    const uploads = within(page()).getAllByRole('button', { name: '上传资料' });
    expect(uploads).toHaveLength(1);
    // The one that is drawn is the toolbar's, beside the search it belongs with.
    expect(within(page()).getByLabelText('搜索资料')).toBeInTheDocument();
    expect(within(page()).queryByText('还没有资料')).not.toBeInTheDocument();
  });

  it('lists what the server returned, and offers only the actions the server allowed', async () => {
    mockApi({ items: [material(), material({ id: 42, original_filename: '真题回忆.txt', file_type: 'text', can_preview: false, preview_url: null })] });
    await renderPage();

    expect(await within(page()).findByText('计算机组成原理讲义.pdf')).toBeInTheDocument();
    expect(within(page()).getByText('真题回忆.txt')).toBeInTheDocument();

    const rows = within(page()).getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    // A type no browser renders gets no 查看 at all, rather than one that explains itself.
    expect(rows[0]?.textContent).toContain('查看');
    expect(rows[1]?.textContent).not.toContain('查看');
    expect(rows[1]?.textContent).toContain('下载');
  });

  it('uploads into the subject the page is on, and nowhere else', async () => {
    const user = userEvent.setup();
    await renderPage();
    await within(page()).findByText('还没有资料');

    const file = new File(['cpu pipelines'], 'coa.txt', { type: 'text/plain' });
    await user.upload(within(page()).getByLabelText('选择要上传的文件'), file);

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith(
        '/exam/11408/subjects/{subject_key}/materials',
        expect.objectContaining({ params: { path: { subject_key: 'computer_organization' } } }),
      ),
    );
  });

  it('deletes through the one library delete, behind a confirmation', async () => {
    const user = userEvent.setup();
    mockApi({ items: [material()] });
    await renderPage();
    await within(page()).findByText('计算机组成原理讲义.pdf');

    await user.click(within(page()).getByRole('button', { name: /删除/ }));
    // Nothing is removed until the learner has confirmed which file they meant.
    expect(api.delete).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText(/删除“计算机组成原理讲义\.pdf”？/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: '删除' }));
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/library/materials/{material_id}', expect.anything()));
  });

  it('states a failure and offers the retry rather than an empty library', async () => {
    mockApi({ fail: true });
    await renderPage();

    expect(await within(page()).findByText(/资料暂时无法加载/)).toBeInTheDocument();
    expect(within(page()).queryByText('还没有资料')).not.toBeInTheDocument();
  });
});
