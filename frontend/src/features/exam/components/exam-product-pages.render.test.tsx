import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, PUT: vi.fn() } }));

const profile = {
  configured: true,
  exam_type: 'national_postgraduate',
  selected_track: 'computer_science',
  selected_subjects: ['cs_408'],
  target_exam_year: 2027,
  subjects: [{
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
  }],
};

const catalog = {
  catalog_version: 'test',
  exam_type: 'national_postgraduate',
  tracks: [{ id: 'computer_science', display_name: '计算机科学与技术', exam_type: 'national_postgraduate', availability: 'active', has_content: true, description: '计算机方向', subject_options: ['cs_408'], suggested_subjects: ['cs_408'] }],
  subjects: [],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: [],
};

describe('My Exam page', () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((path: string) => Promise.resolve({
      data: path === '/exam/prep/catalog' ? catalog : profile,
      error: undefined,
      response: { ok: true, status: 200 },
    }));
  });

  it('shows the real selected track beside configured exam identity', async () => {
    renderApp('/exam');

    expect(await screen.findByRole('heading', { name: '全国统考研究生考试' })).toBeInTheDocument();
    expect(screen.getByText(/备考档案/)).toBeInTheDocument();
    expect(screen.queryByText(/EXAM DOSSIER/)).not.toBeInTheDocument();
    expect(screen.getByText(/02 科目范围/)).toBeInTheDocument();
    expect(screen.getByText('目标考试年份 · 2027')).toBeInTheDocument();
    expect(screen.getByText('备考方向 · 计算机科学与技术')).toBeInTheDocument();
  });
});
