export const DEFAULT_RETURN_TO = '/';

const AUTH_ROUTES = ['/login', '/register'];

/**
 * Accepts a post-login destination only when it is an absolute path on THIS origin.
 *
 * `returnTo` arrives from the address bar, so it is attacker-controlled input on a page whose
 * whole purpose is to hand control back to it. Everything that could leave the origin is
 * rejected — absolute URLs, protocol-relative `//host` paths, and backslash variants that
 * some browsers normalise into `//`. A rejected value returns `null` and the caller falls back
 * to Home rather than guessing.
 */
export function sanitizeReturnTo(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const value = raw.trim();
  if (!value.startsWith('/')) return null;
  // `//host` is protocol-relative, and some browsers normalise `/\host` into it. Compared by
  // code point (0x2f = `/`, 0x5c = `\`) so this line carries no escape sequence to mangle.
  const secondCharacter = value.charCodeAt(1);
  if (secondCharacter === 0x2f || secondCharacter === 0x5c) return null;
  // Control characters have no place in a redirect target; check by code point so this needs
  // no escape sequence that a writer or a linter could mangle.
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code < 0x20 || code === 0x7f) return null;
  }
  return value;
}

/**
 * A validated destination, or the caller's own fallback.
 *
 * Auth routes are filtered out so that a completed flow cannot bounce a visitor straight back
 * into a login screen. Setup flows pass their own fallback — the space they just configured —
 * because "back to the space" is the useful answer there, not "back to Home".
 */
export function resolveReturnDestination(raw: unknown, fallback: string): string {
  const sanitized = sanitizeReturnTo(raw);
  if (!sanitized) return fallback;
  const path = sanitized.split(/[?#]/)[0] ?? '';
  if (AUTH_ROUTES.some((route) => path === route || path.startsWith(`${route}/`))) {
    return fallback;
  }
  return sanitized;
}

/** The destination for a completed sign-in. */
export function resolvePostAuthDestination(raw: unknown): string {
  return resolveReturnDestination(raw, DEFAULT_RETURN_TO);
}
