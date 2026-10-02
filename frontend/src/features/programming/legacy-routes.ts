import { normalizeLanguageSlug, type ProgrammingLanguageSlug } from './programming-language';

/**
 * Where an address from the programming space's older shapes belongs now.
 *
 * The space has been through two address shapes before this one. Every tool used to hang off the
 * language (`/programming/python/records`), and then the tools became the space's own pages with
 * the language in the search (`/programming/records?language=python`). Both are everywhere a
 * learner's history is stored — bookmarks, pasted links, and the deep links the backend recomputes
 * on every read (`backend/learning/agenda.py`, `backend/learning/review.py`, which build
 * `/programming/{lang}/exercises/{id}` and `/programming/{Language}/plan` on each call).
 *
 * Those two shapes now both land in the WORKSPACE, because that is where every one of those tools
 * lives: 练习中心, the题面, the editor, the AI 助手 and the records are all regions of it. The plan
 * keeps its own page — it is the one capability the workspace does not hold.
 *
 * Nothing in the backend has to change: those links are stored in no table and are recomputed on
 * every read, so a redirect is the whole fix. (Server deep links render as plain `<a href>`, so
 * they arrive as a fresh page load and land here.)
 *
 * `undefined` means the address is not one this module knows: the caller shows a not-found rather
 * than guessing at a destination.
 */
export type LegacyProgrammingTarget = {
  to: string;
  params?: Record<string, string>;
  search: Record<string, unknown>;
};

const WORKBENCH = '/programming/workbench';
const PLAN = '/programming/plan';

/** The tools that became regions of the workspace, and therefore have no page of their own. */
const WORKSPACE_TOOLS = new Set(['practice', 'records', 'state', 'errors', 'ai', 'projects']);

function numericId(value: string | undefined): string | undefined {
  return value !== undefined && /^\d+$/.test(value) ? value : undefined;
}

function workbenchSearch(language: ProgrammingLanguageSlug | undefined, exerciseId?: string): Record<string, unknown> {
  return {
    ...(language ? { language } : {}),
    ...(exerciseId ? { exercise: Number(exerciseId) } : {}),
  };
}

/**
 * `/programming/<splat>` — the part after `/programming/`, with no leading slash.
 *
 * `languageFromSearch` is the `?language=` the address carried, which the older tool-shape links
 * use to name the language the tool was read in. The language-first shape names it in the path and
 * does not need it.
 */
export function legacyProgrammingTarget(
  splat: string,
  languageFromSearch?: ProgrammingLanguageSlug,
): LegacyProgrammingTarget | undefined {
  const segments = splat.split('/').map((segment) => segment.trim()).filter(Boolean);
  const head = segments[0];
  const fromPath = head ? normalizeLanguageSlug(head) : undefined;

  /* --- the language-first shape: /programming/<language>/… --- */
  if (fromPath) {
    const rest = segments.slice(1);

    // The bare language WAS the exercise list.
    if (rest.length === 0) return { to: WORKBENCH, search: workbenchSearch(fromPath) };

    if (rest[0] === 'exercises') {
      if (rest.length === 1) return { to: WORKBENCH, search: workbenchSearch(fromPath) };
      const exerciseId = numericId(rest[1]);
      if (exerciseId && rest.length === 2) {
        return { to: WORKBENCH, search: workbenchSearch(fromPath, exerciseId) };
      }
      return undefined;
    }

    // `projects` was the Workbench's own address before it was named for what it opens.
    if (rest[0] === 'projects' && rest.length === 2) {
      const exerciseId = numericId(rest[1]);
      return exerciseId
        ? { to: WORKBENCH, search: workbenchSearch(fromPath, exerciseId) }
        : undefined;
    }

    if (rest.length !== 1) return undefined;
    const only = rest[0];
    if (only === undefined) return undefined;

    if (only === 'plan') return { to: PLAN, search: { language: fromPath } };
    if (WORKSPACE_TOOLS.has(only)) return { to: WORKBENCH, search: workbenchSearch(fromPath) };
    return undefined;
  }

  /* --- the tool-first shape: /programming/<tool>[/<id>]?language=… --- */
  const tool = head;
  if (!tool) return { to: WORKBENCH, search: workbenchSearch(languageFromSearch) };
  if (tool === 'plan') return { to: PLAN, search: workbenchSearch(languageFromSearch) };
  if (WORKSPACE_TOOLS.has(tool)) {
    // `practice/7` and `projects/7` name an exercise; anything else in this family is the tool
    // itself, whose whole content is a region of the workspace.
    const exerciseId = segments.length === 2 ? numericId(segments[1]) : undefined;
    return { to: WORKBENCH, search: workbenchSearch(languageFromSearch, exerciseId) };
  }
  return undefined;
}
