import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { describe, expect, it, vi } from 'vitest';
import { AdaptivePractice } from './adaptive-practice';

/** The recommendation links into a practice, so it needs a router the way the real page has one. */
function renderAdaptive() {
  const router = createRouter({
    routeTree: createRootRoute({ component: () => <AdaptivePractice serviceKey="programming" language="python" /> }),
    history: createMemoryHistory(),
  });
  return render(<RouterProvider router={router} />);
}

vi.mock('@/components/learning/p4-api', () => ({
  useAdaptivePractice: () => ({ isPending: false, isError: false, data: {
    candidates: [{ candidate_id: 'programming:7', label: '两数之和', source_type: 'exercise', question_source_id: '7', reason: 'needs_work', facts: { incorrect_submissions: 2 } }],
    reasons: { needs_work: '两次提交未通过，建议回到该练习。' },
  } }),
}));

describe('AdaptivePractice', () => {
  it('renders factual reason and a programming deep link without predictive wording', async () => {
    renderAdaptive();
    await screen.findByText('两数之和');
    expect(screen.getByText('两数之和')).toBeInTheDocument();
    expect(screen.getByText('多次错误 / 待改进')).toBeInTheDocument();
    expect(screen.getByText('两次提交未通过，建议回到该练习。')).toBeInTheDocument();
    // A programming recommendation opens the WORKSPACE with that exercise selected: the workspace
    // is one page, so both the language and the exercise ride in its search.
    const link = screen.getByRole('link', { name: '打开练习' });
    expect(link.getAttribute('href')).toMatch(/^\/programming\/workbench\?/);
    expect(link.getAttribute('href')).toContain('language=python');
    expect(link.getAttribute('href')).toContain('exercise=7');
    expect(screen.queryByText(/掌握率|预测|薄弱/)).not.toBeInTheDocument();
  });
});
