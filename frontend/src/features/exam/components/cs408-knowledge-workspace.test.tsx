import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408KnowledgeWorkspace } from './cs408-knowledge-workspace';

type StudyPlan = components['schemas']['ExamStudyPlanResponse'];

// The section is the CANONICAL knowledge leaf: its `code` is what the module knowledge-map
// seed publishes, and the same string a chapter-practice question carries as its concept.
// The tests below move it between a real leaf code and the synthetic `_leaf:` code the API
// mints for a seed node that has none, because only one of the two may offer practice.
let sectionCode = '1.1';

function plan(): StudyPlan {
  return {
    course_id: 'data_structure_11408',
    course_name: '数据结构',
    subject_key: 'data_structure',
    subject_name: '数据结构',
    settings: { learning_goal: null, start_date: null, daily_hours: null, weekly_days: null, review_strategy: null, show_completed: true },
    stats: { total_knowledge_points: 2, mastered: 1, total_sections: 1, sections_completed: 0, sections_learning: 1, sections_not_started: 0, overall_progress: 50, overall_status: 'learning' },
    review_interval_days: 3,
    tasks: [],
    chapters: [{
      code: 'chapter-1', title: '线性表', chapter_no: 1, id: 'chapter-1', is_leaf: false,
      status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
      progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
      status_counts: { not_started: 0, learning: 1, mastered: 1, review_due: 0 }, chapter_completion_rate: 50, section_count: 1, sections_completed: 0, chapter_status: 'learning',
      children: [{
        code: sectionCode, title: '顺序表', id: 'section-1', is_leaf: false,
        status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
        progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
        status_counts: { not_started: 0, learning: 1, mastered: 1, review_due: 0 }, leaf_stats: { total: 2, mastered: 1, learning: 1, not_started: 0, review_due: 0 }, chapter_practice_completed: false, section_status: 'learning', completion_rate: 50,
        children: [{
          code: 'node-1', title: '顺序表操作', id: 'node-1', is_leaf: false,
          status: 'learning', stored_status: null, user_confirmed_status: null, system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
          progress: null, learned_at: null, review_due_at: null, review_interval_days: null,
          status_counts: { not_started: 0, learning: 1, mastered: 0, review_due: 0 },
          children: [{
            code: 'leaf-1', title: '插入操作', id: 'leaf-1', is_leaf: true,
            status: 'mastered', stored_status: 'mastered', user_confirmed_status: 'mastered', system_suggested_status: null, ai_recommended_status: null, ai_assessment: null,
            progress: { id: 1, course_id: 'data_structure_11408', knowledge_point_code: 'leaf-1', knowledge_point_title: '插入操作', status: 'mastered', stored_status: 'mastered', user_confirmed_status: 'mastered', system_suggested_status: null, ai_recommended_status: null, ai_assessment: null, learned_at: '2026-09-17T00:00:00Z', review_due_at: null, review_interval_days: 3, updated_at: null },
            learned_at: '2026-09-17T00:00:00Z', review_due_at: null, review_interval_days: 3,
            status_counts: { not_started: 0, learning: 0, mastered: 1, review_due: 0 }, children: [],
          }],
        }],
      }],
    }],
  };
}

const mutate = vi.fn((input: { status: string }, options?: { onSuccess?: (response: { status: string }) => void }) => {
  options?.onSuccess?.({ status: input.status });
});
vi.mock('@/features/exam/api/study-plan', () => ({
  useExamStudyPlan: () => ({ data: plan(), isPending: false, isError: false, refetch: vi.fn() }),
  useUpdateExamKnowledgeItem: () => ({ mutate, isPending: false, isError: false }),
}));

vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: ReactNode }) => children }));

function renderWorkspace() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><Cs408KnowledgeWorkspace moduleKey="data_structure" /></QueryClientProvider>);
}

describe('Cs408KnowledgeWorkspace', () => {
  beforeEach(() => { sectionCode = '1.1'; });

  it('renders the real recursive children hierarchy and keeps chapter semantics separate from knowledge semantics', async () => {
    const user = userEvent.setup();
    renderWorkspace();

    expect(screen.getByRole('heading', { name: '数据结构知识脉络' })).toBeInTheDocument();
    expect(screen.getAllByText('学习中')).toHaveLength(2);
    expect(screen.queryByText('插入操作')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /展开 顺序表/ }));
    await user.click(screen.getByRole('button', { name: /展开 顺序表操作/ }));
    await user.click(screen.getByRole('button', { name: '选择 插入操作' }));

    expect(screen.getByRole('heading', { name: '插入操作' })).toBeInTheDocument();
    expect(screen.getAllByText('已学习')).toHaveLength(2);
    expect(screen.queryByText('已掌握')).not.toBeInTheDocument();
    expect(screen.getByText('我的学习状态')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '更新学习状态' }));
    await user.click(screen.getByRole('button', { name: '待复习' }));
    expect(mutate).toHaveBeenCalledWith({ username: '', subject_key: 'data_structure', course_id: 'data_structure_11408', knowledge_point_code: 'leaf-1', knowledge_point_title: '插入操作', status: 'review_due' }, expect.objectContaining({ onSuccess: expect.any(Function) }));
    expect(screen.getByText('待复习')).toBeInTheDocument();
    expect(screen.queryByText(/data_structure_11408|knowledge_point_id/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- ACCEL_PRODUCT_S9
//
// The identity the practice link carries is the section's own canonical `code` — the string
// the module seed publishes and the string a question carries as its concept. It is NEVER
// the section's title, its position in the list, or anything read out of a question.

describe('Cs408KnowledgeWorkspace concept-scoped practice', () => {
  beforeEach(() => { sectionCode = '1.1'; });

  it('offers practice scoped to the canonical leaf, carrying the code and the module chapter', () => {
    renderWorkspace();
    const link = screen.getByRole('link', { name: '知识点练习' });
    expect(link).toHaveAttribute('href', '/exam/cs408/practice?module=data_structure&chapter=chapter-1&concept=1.1');
    // the title is a display string and must not appear as an identity
    expect(link.getAttribute('href')).not.toContain('顺序表');
  });

  it('offers NO practice link for a node the seed gives no canonical code', () => {
    // `_leaf:<path>` is the synthetic code the API mints for such a node. There is nothing
    // to propagate from it, so the action is not offered at all rather than offered and
    // then refused by the server.
    sectionCode = '_leaf:1.1';
    renderWorkspace();
    expect(screen.queryByRole('link', { name: '知识点练习' })).not.toBeInTheDocument();
    // the chapter-wide practice link is unaffected — it addresses the chapter, not a concept
    expect(screen.getByRole('link', { name: '章节练习' })).toBeInTheDocument();
  });

  it('keeps the chapter-wide link free of a concept, so direct entry declares none', () => {
    renderWorkspace();
    const chapterLink = screen.getByRole('link', { name: '章节练习' });
    expect(chapterLink).toHaveAttribute('href', expect.stringContaining('/exam/cs408/practice?module=data_structure&chapter=chapter-1'));
    expect(chapterLink.getAttribute('href')).not.toContain('concept=');
  });
});
