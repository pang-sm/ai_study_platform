import { env } from '@/lib/env';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { chatRequestBody, citationsFrom, type AiAsk, type AiCitation } from './ai-chat';
import { createSseParser, type SseFrame } from './sse';

/**
 * `POST /chat/stream` — the same question and scope as `/chat`, answered as a live stream.
 *
 * The backend contract is fixed and this file is its only client:
 *
 *   event: start  data: { request_id, session_id }
 *   event: delta  data: { text }                       ← the ONLY place answer text arrives
 *   event: done   data: { request_id, session_id, resolved_model, references, finish_reason, stopped }
 *   event: error  data: { category, message }
 *
 * `done` always ends a run that can be shown (including a learner stop, `stopped: true`);
 * `error` ends one that cannot. A `delta` is the only carrier of answer text — the server
 * never streams reasoning or hidden tokens, and `deltaText` below reads the `text` field and
 * nothing else, so a payload that happens to carry a reasoning channel cannot leak into the DOM.
 *
 * The caller owns the `AbortController`: aborting the signal cancels the request AND makes every
 * later callback impossible, because the read loop and the dispatch loop both check it.
 */

export type StreamStart = { requestId: string | null; sessionId: number | null; userMessageId: number | null };

export type StreamDone = {
  requestId: string | null;
  sessionId: number | null;
  resolvedModel: string | null;
  references: AiCitation[];
  finishReason: string | null;
  stopped: boolean;
};

export type ChatStreamHandlers = {
  onStart?: (payload: StreamStart) => void;
  /** Only ever called with the answer text of one `delta`, already accumulated by the caller. */
  onDelta?: (text: string) => void;
  onDone?: (payload: StreamDone) => void;
  /** A failure the learner must be told about. Never called for an abort. */
  onError?: (error: unknown) => void;
};

export async function streamAiChat(
  input: AiAsk,
  handlers: ChatStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${env.apiBaseUrl}/chat/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(chatRequestBody(input)),
      signal,
    });
    if (!response.ok) {
      handlers.onError?.(new ApiRequestError(response.status, await readErrorBody(response)));
      return;
    }
    const body = response.body;
    if (!body) {
      handlers.onError?.(new ApiRequestError(503, null));
      return;
    }

    const reader = body.getReader();
    const decoder = new TextDecoder();
    const parser = createSseParser();
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
        if (signal.aborted) return;
        dispatch(frame, handlers);
      }
    }
    if (signal.aborted) return;
    const tail = parser.flush();
    if (tail) dispatch(tail, handlers);
  } catch (error) {
    // A learner stop is not a failure: the caller aborted on purpose and already knows.
    if (signal.aborted || isAbortError(error)) return;
    handlers.onError?.(new ApiRequestError(503, error));
  }
}

function dispatch(frame: SseFrame, handlers: ChatStreamHandlers): void {
  if (frame.event === 'delta') {
    const text = deltaText(frame.data);
    if (text) handlers.onDelta?.(text);
    return;
  }
  const payload = parseJson(frame.data);
  if (frame.event === 'start') handlers.onStart?.(readStart(payload));
  else if (frame.event === 'done') handlers.onDone?.(readDone(payload));
  else if (frame.event === 'error') handlers.onError?.(readStreamError(payload));
}

/** Reads ONLY `text`. Any other channel in the payload is ignored, never rendered. */
function deltaText(raw: string): string {
  const payload = parseJson(raw);
  if (!isRecord(payload)) return '';
  const value = payload.text;
  return typeof value === 'string' ? value : '';
}

function readStart(payload: unknown): StreamStart {
  const record = isRecord(payload) ? payload : {};
  return {
    requestId: str(record.request_id),
    sessionId: num(record.session_id),
    // The stored id of the question being answered — what makes it editable without a reload.
    userMessageId: num(record.user_message_id),
  };
}

function readDone(payload: unknown): StreamDone {
  const record = isRecord(payload) ? payload : {};
  return {
    requestId: str(record.request_id),
    sessionId: num(record.session_id),
    resolvedModel: str(record.resolved_model),
    references: citationsFrom(record.references),
    finishReason: str(record.finish_reason),
    stopped: record.stopped === true,
  };
}

/**
 * A stream `error` becomes the SAME `ApiRequestError` an HTTP failure would, so the chat page's
 * existing `failure()` copy decides what the learner reads. An infrastructure category is mapped
 * to 5xx on purpose: its `message` is provider/plumbing detail, and `failure()` will replace it
 * with the product's own sentence rather than put a vendor's words on screen.
 */
function readStreamError(payload: unknown): ApiRequestError {
  const record = isRecord(payload) ? payload : {};
  const category = str(record.category) ?? '';
  const message = str(record.message);
  return new ApiRequestError(statusForCategory(category), message ? { message } : null);
}

function statusForCategory(category: string): number {
  switch (category) {
    case 'forbidden':
    case 'permission':
    case 'capability':
      return 403;
    case 'rate_limit':
    case 'quota':
    case 'budget':
      return 429;
    case 'invalid_request':
    case 'validation':
      return 400;
    default:
      return 503;
  }
}

async function readErrorBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function isAbortError(error: unknown): boolean {
  return isRecord(error) && error.name === 'AbortError';
}

function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
