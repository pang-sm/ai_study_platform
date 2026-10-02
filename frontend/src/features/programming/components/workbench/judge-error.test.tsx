import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { renderApp } from '@/test/render-app';
import {
  CODE_EXECUTION_UNAVAILABLE,
  CODE_EXECUTION_UNAVAILABLE_MESSAGE,
  judgeFailureMessage,
} from './judge-error';

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: post, PUT: put },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const refused = (detail: unknown) => ({ data: undefined, error: { detail }, response: { ok: false, status: 503 } });

/** The backend's own sentence for the refusal — the one the UI must NOT pass through. */
const SERVER_MESSAGE = '代码运行服务暂时不可用，请稍后再试。';

describe('the judge failure message', () => {
  it('gives the run environment its own sentence, chosen by the code and never the server text', () => {
    const error = new ApiRequestError(503, { detail: { code: CODE_EXECUTION_UNAVAILABLE, message: SERVER_MESSAGE } });

    expect(judgeFailureMessage(error)).toBe(CODE_EXECUTION_UNAVAILABLE_MESSAGE);
    // The mapping is read off the stable code, so the server's own wording never reaches the learner.
    expect(judgeFailureMessage(error)).not.toBe(SERVER_MESSAGE);
    // And it does not read as a verdict on the code that was submitted.
    expect(judgeFailureMessage(error)).not.toMatch(/错误|失败|不正确/);
  });

  it('reads the code whether or not the body nests it', () => {
    const flat = new ApiRequestError(503, { code: CODE_EXECUTION_UNAVAILABLE });

    expect(judgeFailureMessage(flat)).toBe(CODE_EXECUTION_UNAVAILABLE_MESSAGE);
  });

  it('leaves every other failure to the caller', () => {
    expect(judgeFailureMessage(new ApiRequestError(503, { detail: { code: 'something_else' } }))).toBeUndefined();
    expect(judgeFailureMessage(new ApiRequestError(500, { detail: 'boom' }))).toBeUndefined();
    expect(judgeFailureMessage(new ApiRequestError(401, {}))).toBeUndefined();
    expect(judgeFailureMessage(new Error('network'))).toBeUndefined();
    expect(judgeFailureMessage(undefined)).toBeUndefined();
  });
});

describe('the workbench when the run environment is off', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
    put.mockReset();

    get.mockImplementation(async (url: string) => {
      if (url === '/programming/onboarding') {
        return ok({ main_language: 'Python', selected_languages: ['Python'], onboarding_completed: true });
      }
      if (url === '/programming/exercises') {
        return ok({
          items: [{ id: 7, title: '两数之和', curriculum_module: '控制流与函数' }],
          total: 1,
          status_counts: { passed: 0, not_started: 1, needs_improvement: 0 },
        });
      }
      if (url === '/programming/exercises/{exercise_id}') {
        return ok({ exercise: { id: 7, title: '两数之和', statement: '给定一个整数数组，返回两个数的下标。' } });
      }
      if (url === '/programming/records') return ok({ records: [], next_cursor: null, has_more: false });
      return ok({});
    });

    post.mockImplementation(async (url: string) => {
      if (url === '/programming/exercises/{exercise_id}/start') {
        return ok({
          exercise: { id: 7, title: '两数之和', starter_files: [{ path: 'main.py', content: '# 在这里编写代码\n' }] },
          project: {
            id: 55,
            entry_file: 'main.py',
            main_class: null,
            language: 'Python',
            files: [{ id: 91, relative_path: 'main.py', filename: 'main.py', content: '# 在这里编写代码\n' }],
          },
          resumed: false,
        });
      }
      // 运行 asks the judge to execute the project; SECURITY_S0 answers with the stable refusal.
      if (url === '/programming/exercises/{exercise_id}/run') {
        return refused({ code: CODE_EXECUTION_UNAVAILABLE, message: SERVER_MESSAGE });
      }
      return ok({});
    });
    put.mockImplementation(async () => ok({}));
  });

  it('says the run environment is unavailable instead of the generic failure', async () => {
    const user = userEvent.setup();
    renderApp('/programming/workbench/7?language=python');

    const run = await screen.findByRole('button', { name: /^运行$/ });
    await waitFor(() => expect(run).toBeEnabled());
    await user.click(run);

    expect(await screen.findByText(CODE_EXECUTION_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
    // The generic sentence is replaced, not repeated, and the server's own wording is not shown.
    expect(screen.queryByText(/这次操作没有成功/)).not.toBeInTheDocument();
    expect(screen.queryByText(SERVER_MESSAGE)).not.toBeInTheDocument();
    // It is an environment notice, not a claim that the submitted code was wrong.
    expect(screen.queryByText(/代码错误|编译错误|运行错误/)).not.toBeInTheDocument();
  });
});
