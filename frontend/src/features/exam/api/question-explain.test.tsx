import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

const { POST } = vi.hoisted(() => ({ POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { POST } }));

import { useQuestionExplain } from './question-explain';

describe('question explain mutation', () => {
  it('uses the generated route once even when the client default would retry', async () => {
    POST.mockResolvedValue({ data: undefined, error: { detail: 'provider failed' }, response: { ok: false, status: 502 } as Response });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: 3 } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => useQuestionExplain(), { wrapper });

    result.current.mutate({ moduleKey: 'data_structure', input: { stem: '题干', options: { A: '甲' }, standard_answer: 'A', user_answer: 'B', question_type: 'choice' } });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(POST).toHaveBeenCalledTimes(1);
    expect(POST).toHaveBeenCalledWith('/exam/11408/{subject_key}/question-analysis', {
      params: { path: { subject_key: 'data_structure' } },
      body: { stem: '题干', options: { A: '甲' }, standard_answer: 'A', user_answer: 'B', question_type: 'choice' },
    });
  });
});
