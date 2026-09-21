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
