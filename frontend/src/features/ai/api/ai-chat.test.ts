import { describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get, POST: post } }));

import { fetchAiSessionTurns, fetchModelOptions, fetchScopedAiSessions, sendAiChat } from './ai-chat';

describe('fetchScopedAiSessions', () => {
  it('asks the existing history API for only the active exam subject', async () => {
    get.mockResolvedValue({
      response: { ok: true },
      data: { sessions: [{ id: 7, title: '链表', exam_subject: 'data_structure', created_at: '2026-09-22T08:00:00Z' }] },
    });

    await expect(fetchScopedAiSessions({ kind: 'exam', moduleKey: 'data_structure', label: '数据结构' }))
      .resolves.toEqual([{ id: 7, title: '链表', createdAt: '2026-09-22T08:00:00Z' }]);

    expect(get).toHaveBeenCalledWith('/chat/history', {
      params: { query: { exam_subject: 'data_structure', subject_key: 'data_structure' } },
    });
  });
});

describe('scoped session detail', () => {
  it('carries the active course scope when restoring a conversation', async () => {
    get.mockResolvedValue({ response: { ok: true }, data: { messages: [] } });
    await fetchAiSessionTurns(42, { kind: 'course', courseId: 'data_structure', label: '数据结构' });
    expect(get).toHaveBeenCalledWith('/chat/sessions/{session_id}', {
      params: { path: { session_id: 42 }, query: { course: 'data_structure' } },
    });
  });
});

describe('concrete model options', () => {
  it('uses the backend qualified options rather than abstract preferences', async () => {
    get.mockResolvedValue({
      response: { ok: true },
      data: { options: [{ provider: 'gateway', model: 'qwen3.8-flash' }], preferences: [{ key: 'basic', label: '快速' }] },
    });
    await expect(fetchModelOptions('tutor.chat')).resolves.toEqual({
      options: [{ id: 'qwen3.8-flash', label: 'qwen3.8-flash', provider: 'gateway', thinking: false }],
      recommended: null,
    });
  });
});

describe('chat composer contract', () => {
  it('sends deep thinking through the scoped /chat request', async () => {
    post.mockResolvedValue({ response: { ok: true }, data: { answer: '好' }, error: undefined });
    await sendAiChat({
      message: '解释链表', scope: { kind: 'exam', moduleKey: 'data_structure', label: '数据结构' },
      thinkingMode: 'deep', modelId: undefined,
    });
    expect(post).toHaveBeenCalledWith('/chat', expect.objectContaining({
      body: expect.objectContaining({ thinking_mode: 'deep', model_id: null }),
    }));
  });

  it('carries the knowledge point the learner opened, as an id and nothing else', async () => {
    post.mockResolvedValue({ response: { ok: true }, data: { answer: '好' }, error: undefined });
    await sendAiChat({
      message: '这一步为什么是这样',
      scope: {
        kind: 'exam', moduleKey: 'data_structure', label: '数据结构',
        knowledgePoint: '1.1.1', knowledgePointTitle: '数据的逻辑结构',
      },
      thinkingMode: 'standard',
    });
    // The id is what the platform records and the title is what the model is told; no question is
    // composed on the learner's behalf.
    expect(post).toHaveBeenCalledWith('/chat', expect.objectContaining({
      body: expect.objectContaining({
        knowledge_point_id: '1.1.1', knowledge_point_title: '数据的逻辑结构',
        message: '这一步为什么是这样', exam_subject: 'data_structure',
      }),
    }));
  });

  it('sends no knowledge point for a paper-wide conversation or any other scope', async () => {
    post.mockResolvedValue({ response: { ok: true }, data: { answer: '好' }, error: undefined });
    await sendAiChat({
      message: '介绍一下这门课', scope: { kind: 'exam', moduleKey: 'data_structure', label: '数据结构' },
      thinkingMode: 'standard',
    });
    expect(post.mock.calls.at(-1)?.[1]?.body?.knowledge_point_id).toBe('');

    await sendAiChat({
      message: '介绍一下这门课', scope: { kind: 'course', courseId: 'cs101', label: '数据结构' },
      thinkingMode: 'standard',
    });
    expect(post.mock.calls.at(-1)?.[1]?.body?.knowledge_point_id).toBe('');
  });

  it('sends a selected course model through model_id while preserving course material scope', async () => {
    post.mockResolvedValue({ response: { ok: true }, data: { answer: '好' }, error: undefined });
    await sendAiChat({
      message: '解释链表',
      scope: { kind: 'course', courseId: 'cs101', label: '数据结构' },
      thinkingMode: 'standard',
      materialIds: [27],
      attachmentIds: [41, 42],
      modelId: 'qwen3.8-flash',
    });
    expect(post).toHaveBeenCalledWith('/chat', expect.objectContaining({
      body: expect.objectContaining({
        course_id: 'cs101', course: 'cs101', service_key: 'course_learning',
        material_ids: [27], attachment_ids: [41, 42], model_id: 'qwen3.8-flash', model_preference: '',
      }),
    }));
  });
});
