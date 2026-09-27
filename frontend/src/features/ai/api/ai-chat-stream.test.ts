import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { streamAiChat, type ChatStreamHandlers } from './ai-chat-stream';
import type { AiAsk } from './ai-chat';

/** A response whose body is a real byte stream, so chunk boundaries can be chosen by the test. */
function sseResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { 'Content-Type': 'text/event-stream' } });
}

function stubFetch(response: Response | (() => Promise<Response>)) {
  const mock = vi.fn(typeof response === 'function' ? response : () => Promise.resolve(response));
  vi.stubGlobal('fetch', mock);
  return mock;
}

const ask: AiAsk = { message: '解释链表', scope: { kind: 'general' }, thinkingMode: 'standard' };

function collector() {
  const seen: string[] = [];
  const handlers: ChatStreamHandlers = {
    onStart: (payload) => seen.push(`start:${payload.requestId}:${payload.sessionId}`),
    onDelta: (text) => seen.push(`delta:${text}`),
    onDone: (payload) => seen.push(`done:${payload.resolvedModel}:${payload.references.length}:${payload.stopped}`),
    onError: (error) => seen.push(`error:${error instanceof ApiRequestError ? error.status : 'other'}`),
  };
  return { seen, handlers };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('streamAiChat', () => {
  it('streams start, deltas and done in order and reads only the answer text', async () => {
    stubFetch(sseResponse([
      'event: start\ndata: {"request_id":"req-1","session_id":12}\n\n',
      'event: delta\ndata: {"text":"第一段"}\n\n',
      'event: delta\ndata: {"text":"第二段"}\n\n',
      'event: done\ndata: {"request_id":"req-1","session_id":12,"resolved_model":"deepseek-flash","references":[{"filename":"a.pdf","snippet":"片段"}],"finish_reason":"stop","stopped":false}\n\n',
    ]));
    const { seen, handlers } = collector();
    let references: unknown;
    handlers.onDone = (payload) => { references = payload.references; seen.push(`done:${payload.resolvedModel}:${payload.stopped}`); };

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toEqual(['start:req-1:12', 'delta:第一段', 'delta:第二段', 'done:deepseek-flash:false']);
    expect(references).toEqual([{ filename: 'a.pdf', snippet: '片段' }]);
  });

  it('never lets a reasoning channel in a delta payload reach the caller', async () => {
    stubFetch(sseResponse([
      'event: delta\ndata: {"text":"可见答案","reasoning":"内部推理"}\n\n',
      'event: delta\ndata: {"reasoning":"只有推理"}\n\n',
      'event: done\ndata: {"request_id":"r","session_id":1,"resolved_model":"m","references":[],"finish_reason":"stop","stopped":false}\n\n',
    ]));
    const { seen, handlers } = collector();

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toContain('delta:可见答案');
    expect(seen.some((entry) => entry.includes('内部推理'))).toBe(false);
    expect(seen.some((entry) => entry.includes('只有推理'))).toBe(false);
  });

  it('reassembles frames split across byte chunks', async () => {
    stubFetch(sseResponse([
      'event: del',
      'ta\ndata: {"text":"你好"}\n\nevent: done\ndata: {"request_id":"r","session_id":1,"resolved_model":"m","references":[],"finish_reason":"stop","stopped":true}\n\n',
    ]));
    const { seen, handlers } = collector();

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toEqual(['delta:你好', 'done:m:0:true']);
  });

  it('turns a stream error event into an ApiRequestError with a status the copy layer understands', async () => {
    stubFetch(sseResponse(['event: error\ndata: {"category":"provider_error","message":"上游 502"}\n\n']));
    const { seen, handlers } = collector();

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toEqual(['error:503']);
  });

  it('maps a quota category to the rate-limit status, not a generic failure', async () => {
    stubFetch(sseResponse(['event: error\ndata: {"category":"rate_limit","message":"额度"}\n\n']));
    const { seen, handlers } = collector();

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toEqual(['error:429']);
  });

  it('reports a non-ok response as an ApiRequestError carrying its status', async () => {
    stubFetch(new Response(JSON.stringify({ detail: '拒绝' }), { status: 403 }));
    const { seen, handlers } = collector();

    await streamAiChat(ask, handlers, new AbortController().signal);

    expect(seen).toEqual(['error:403']);
  });

  it('passes the caller signal to fetch and stops dispatching once it aborts', async () => {
    const controller = new AbortController();
    const fetchMock = stubFetch(sseResponse([
      'event: delta\ndata: {"text":"一"}\n\n',
      'event: delta\ndata: {"text":"二"}\n\n',
      'event: done\ndata: {"request_id":"r","session_id":1,"resolved_model":"m","references":[],"finish_reason":"stop","stopped":false}\n\n',
    ]));
    const { seen, handlers } = collector();
    handlers.onDelta = (text) => { seen.push(text); controller.abort(); };

    await streamAiChat(ask, handlers, controller.signal);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/chat/stream'),
      expect.objectContaining({ method: 'POST', credentials: 'include', signal: controller.signal }),
    );
    expect(seen).toEqual(['一']);
  });

  it('treats an abort while awaiting the response as a stop, not a failure', async () => {
    const controller = new AbortController();
    const onError = vi.fn();
    const fetchMock = vi.fn((_url: unknown, init?: { signal?: AbortSignal }) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    vi.stubGlobal('fetch', fetchMock);

    const pending = streamAiChat(ask, { onError }, controller.signal);
    controller.abort();

    await expect(pending).resolves.toBeUndefined();
    expect(onError).not.toHaveBeenCalled();
  });
});
