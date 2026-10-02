/**
 * Reads the human-readable message out of an error body shaped like `{ "detail": ... }`.
 *
 * The backend uses two shapes — a plain string, and an object that carries `code` / `message`
 * (sometimes nested one level deeper). Where the server has already written a sentence for the
 * learner, the UI shows THAT sentence instead of inventing a second one; where it has not, the
 * caller's own fallback is used.
 */
export function serverMessage(detail: unknown, depth = 0): string | null {
  if (depth > 3) return null;
  if (typeof detail === 'string') {
    const text = detail.trim();
    return text || null;
  }
  if (typeof detail !== 'object' || detail === null) return null;
  const value = detail as Record<string, unknown>;
  if (typeof value.message === 'string' && value.message.trim()) return value.message.trim();
  if ('detail' in value) return serverMessage(value.detail, depth + 1);
  return null;
}

/**
 * Reads the STABLE MACHINE CODE out of an error body shaped like `{ "detail": ... }`.
 *
 * Some refusals are decided by the deployment rather than by the request — `code_execution_unavailable`
 * is one — and the server names them with a stable `code` beside a human `message`. A caller that must
 * react to the KIND of refusal reads the code here; it never branches on the message text, which the
 * server is free to reword. `detail` may nest (FastAPI wraps it once), so it is walked the same way
 * `serverMessage` walks it.
 */
export function serverErrorCode(detail: unknown, depth = 0): string | null {
  if (depth > 3) return null;
  if (typeof detail !== 'object' || detail === null) return null;
  const value = detail as Record<string, unknown>;
  if (typeof value.code === 'string' && value.code.trim()) return value.code.trim();
  if ('detail' in value) return serverErrorCode(value.detail, depth + 1);
  return null;
}
