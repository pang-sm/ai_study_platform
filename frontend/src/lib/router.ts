/**
 * TanStack Router types every `to` as a literal union of the routes it generated. Some
 * navigation is composed at runtime — a breadcrumb trail, a context tab list, a server-supplied
 * destination — and those paths are built from the same route table the links point into. The
 * widening is confined to this one function so no component needs its own cast.
 */
export function routePath(path: string): '/' {
  return path as '/';
}

/**
 * A search value that is an IDENTIFIER (a module, a chapter code, a knowledge point), kept in the
 * type the router parsed it into.
 *
 * The router's default parser JSON-parses a value that looks like JSON, and its serializer runs
 * the same JSON step back over any STRING that still looks like JSON — where "looks like JSON"
 * includes anything starting with a digit. So validating `?chapter=1` into the string `"1"` made
 * the router write the URL back as `?chapter=%221%22`, while `?chapter=1` that stayed the NUMBER
 * `1` is emitted as itself. This keeps the value's own type; a page converts it to the string its
 * API needs at the point of use.
 *
 * It is deliberately NOT a coercion to `String`: that is the bug, not the fix.
 */
export function searchIdentifier(value: unknown): string | number | undefined {
  if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
  const text = typeof value === 'string' ? value.trim() : '';
  return text || undefined;
}

/**
 * The same rule in the OTHER direction: a value about to be put INTO a search param, in the type
 * that keeps the URL the learner would write.
 *
 * A numeric-looking value has to go in as the NUMBER — `chapter: '1'` is quoted by the serializer
 * for the same reason `"1"` is on the way out. It is only converted when the number round-trips to
 * exactly the same string: `"1"` → `1` → `"1"` is the same value, so the URL stays `chapter=1`;
 * `"1.10"` → `1.1` is NOT, so the code stays the string it is. That case still arrives quoted and
 * still loses its trailing zero to the router's own parsing — a code shaped like that does not
 * exist in this content (measured), and corrupting an identity to make a URL prettier would be the
 * worse trade.
 */
export function searchValueOut(value: string | number | undefined): string | number | undefined {
  if (typeof value === 'number') return value;
  const text = (value ?? '').trim();
  if (!text) return undefined;
  const asNumber = Number(text);
  return Number.isFinite(asNumber) && String(asNumber) === text ? asNumber : text;
}
