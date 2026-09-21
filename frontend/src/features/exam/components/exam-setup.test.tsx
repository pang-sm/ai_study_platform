import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';
import { examProfileKey } from '@/features/exam/api/profile';

const { get, put } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: vi.fn(), PUT: put } }));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

const catalog = {
  catalog_version: 'test',
  exam_type: 'national_postgraduate',
  tracks: [
    {
      id: 'computer_science',
      display_name: '计算机科学与技术',
      exam_type: 'national_postgraduate',
      availability: 'active',
      has_content: true,
      description: '计算机方向',
      subject_options: ['cs_408'],
      suggested_subjects: ['cs_408'],
    },
  ],
  subjects: [
    {
      id: 'cs_408',
      display_name: '计算机学科专业基础 408',
      category: 'professional',
      availability: 'active',
      has_questions: true,
      has_past_papers: true,
      has_knowledge_tree: true,
      description: '专业基础课',
      suggested_tracks: ['computer_science'],
      modules: [{ id: 'data_structures', display_name: '数据结构' }],
    },
  ],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: [],
};

const unconfigured = {
  configured: false,
  exam_type: null,
  selected_track: null,
  selected_subjects: [],
  target_exam_year: null,
  subjects: [],
};

const configured = {
  ...unconfigured,
  configured: true,
  selected_track: 'computer_science',
  selected_subjects: ['cs_408'],
  target_exam_year: null,
  subjects: catalog.subjects,
};

/**
 * Whether the profile has been saved.
 *
 * The mock has to be stateful, not just per-call: the endpoint is a store, and a GET after a
 * successful PUT answers with what was stored. A mock that always returned "unconfigured" would
 * make a later re-read look like the save had been undone.
 */
let saved = false;

beforeEach(() => {
  saved = false;
  get.mockReset();
  put.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path === '/exam/prep/catalog') return ok(catalog);
    if (path === '/exam/prep/profile') return ok(saved ? configured : unconfigured);
    if (path === '/learning/agenda' || path === '/learning/agenda/explain') return ok({ items: [], total_items: 0 });
    if (path === '/learning-records') return ok({ records: [], has_more: false, next_cursor: null });
    if (path === '/review/summary') return ok({ total: 0, has_stored_due_dates: false });
    throw new Error(`unexpected GET ${path}`);
  });
  put.mockImplementation(async () => {
    saved = true;
    return ok(configured);
  });
});

describe('exam setup', () => {
  it('reuses the exam space’s own setup screen — there is no second one', async () => {
    renderApp('/exam/setup');

    expect(await screen.findByRole('heading', { name: '设置我的备考' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /计算机科学与技术/ })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存备考设置' })).toBeInTheDocument();
  });

  it('saves through the exam profile endpoint and lands back in the exam space', async () => {
    const { router } = renderApp('/exam/setup');
    await screen.findByRole('heading', { name: '设置我的备考' });

    await userEvent.click(screen.getByRole('radio', { name: /计算机科学与技术/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ }));
    await userEvent.click(screen.getByRole('button', { name: '保存备考设置' }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/exam/prep/profile', {
        body: { selected_track: 'computer_science', selected_subjects: ['cs_408'], target_exam_year: null },
      }),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe('/exam'));
  });

  it('writes the server’s own answer into the context, so nothing has to be re-fetched', async () => {
    const { queryClient, router } = renderApp('/exam/setup');
    await screen.findByRole('heading', { name: '设置我的备考' });

    await userEvent.click(screen.getByRole('radio', { name: /计算机科学与技术/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ }));
    await userEvent.click(screen.getByRole('button', { name: '保存备考设置' }));

    // This is the same key the home page and the profile read to decide whether the space is
    // configured, so the save is what makes the space count as set up.
    await waitFor(() =>
      expect(queryClient.getQueryData(examProfileKey)).toMatchObject({ configured: true }),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe('/exam'));
  });

  it('returns to the entry that sent the learner here, and only within this origin', async () => {
    const first = renderApp('/exam/setup?returnTo=%2F');
    await screen.findByRole('heading', { name: '设置我的备考' });
    await userEvent.click(screen.getByRole('radio', { name: /计算机科学与技术/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ }));
    await userEvent.click(screen.getByRole('button', { name: '保存备考设置' }));
    await waitFor(() => expect(first.router.state.location.pathname).toBe('/'));
    first.unmount();

    const second = renderApp('/exam/setup?returnTo=%2F%2Fevil.example');
    await screen.findByRole('heading', { name: '设置我的备考' });
    await userEvent.click(screen.getByRole('radio', { name: /计算机科学与技术/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /计算机学科专业基础 408/ }));
    await userEvent.click(screen.getByRole('button', { name: '保存备考设置' }));
    await waitFor(() => expect(second.router.state.location.pathname).toBe('/exam'));
  });
});
