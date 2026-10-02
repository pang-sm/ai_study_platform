import { normalizeLanguageSlug, type ProgrammingLanguageSlug } from './programming-language';

/**
 * Where an address that names a language in the PATH now belongs.
 *
 * The programming space used to hang every tool off the language — `/programming/python/records`
 * — which made the language a navigation dimension instead of the context a page is read in. The
 * tools are now the space's own pages and the language rides in the search: `/programming/records
 * ?language=python`, the same shape the 408 space has used for its papers since the module
 * switcher was introduced.
 *
 * Every old address must still land somewhere real, and not only for bookmarks: the backend
 * builds deep links in the OLD form. `backend/learning/agenda.py` returns
 * `/programming/{lang}/exercises/{id}`, `/programming/{lang}/plan` and `/programming/{lang}/errors`,
 * and `backend/learning/review.py` returns `/programming/{language}/exercises/{id}` — with the
 * language spelled CANONICALLY (`Python`). Those links are stored in no table and are recomputed
 * on every read, so a redirect is the whole fix and nothing in the backend has to change. (Server
 * deep links render as plain `<a href>`, so they arrive as a fresh page load and land here.)
 *
 * `undefined` means the address is not one this module knows: the caller shows a not-found rather
 * than guessing at a destination.
 */
export type LegacyProgrammingTarget = {
  to: string;
  params?: Record<string, string>;
  search: Record<string, unknown>;
};

/** `/programming/<splat>` — the part after `/programming/`, with no leading slash. */
export function legacyProgrammingTarget(splat: string): LegacyProgrammingTarget | undefined {
  const segments = splat.split('/').map((segment) => segment.trim()).filter(Boolean);
  const language: ProgrammingLanguageSlug | undefined = normalizeLanguageSlug(segments[0]);
  if (!language) return undefined;

  const rest = segments.slice(1);
  const searchWithLanguage = { language };
  const numericId = (value: string | undefined): string | undefined =>
    value !== undefined && /^\d+$/.test(value) ? value : undefined;

  // The bare language WAS the exercise list: `/programming/python`.
  if (rest.length === 0) return { to: '/programming/practice', search: searchWithLanguage };

  if (rest[0] === 'exercises') {
    if (rest.length === 1) return { to: '/programming/practice', search: searchWithLanguage };
    const exerciseId = numericId(rest[1]);
    if (exerciseId && rest.length === 2) {
      return {
        to: '/programming/practice/$exerciseId',
        params: { exerciseId },
        search: searchWithLanguage,
      };
    }
    return undefined;
  }

  // `projects` was the Workbench's own address before it was named for what it opens.
  if (rest[0] === 'projects' && rest.length === 2) {
    const exerciseId = numericId(rest[1]);
    if (exerciseId) {
      return {
        to: '/programming/workbench/$exerciseId',
        params: { exerciseId },
        search: searchWithLanguage,
      };
    }
    return undefined;
  }

  if (rest.length !== 1) return undefined;

  // `errors` and `state` were their own tabs; the review material and the recorded facts are not
  // capabilities of their own, so they live in 成长记录 now rather than keeping a page each.
  if (rest[0] === 'records' || rest[0] === 'state' || rest[0] === 'errors') {
    return { to: '/programming/records', search: searchWithLanguage };
  }
  if (rest[0] === 'plan') return { to: '/programming/plan', search: searchWithLanguage };

  return undefined;
}
