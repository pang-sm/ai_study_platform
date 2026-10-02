import { useProgrammingOnboarding } from './api/programming';
import { normalizeLanguageSlug, languageSlug, type ProgrammingLanguageSlug } from './programming-language';
import { readProgrammingOnboarding } from './programming-onboarding';

/**
 * Which language the page being read is about.
 *
 * One question, two answers, in this order:
 *
 *  1. the `?language=` the address carries — an explicit choice, and the only thing that can
 *     change what the switcher shows;
 *  2. otherwise the language the learner declared in 设置编程学习, so the common case needs no
 *     parameter at all and a learner who has declared one never sees a chooser;
 *  3. otherwise nothing — the page then says it needs a language rather than picking one.
 *
 * The stored value is the canonical spelling (`Python`) and the URL carries the slug (`python`);
 * both arrive here and both leave as the slug, which is what the routes and the API take.
 */
export function useProgrammingLanguage(slugFromUrl?: string): {
  language: ProgrammingLanguageSlug | undefined;
  /** True while the declared context is still being read and the address named nothing. */
  pending: boolean;
} {
  const onboarding = useProgrammingOnboarding();
  const fromUrl = normalizeLanguageSlug(slugFromUrl);
  if (fromUrl) return { language: fromUrl, pending: false };

  const declared = readProgrammingOnboarding(onboarding.data);
  const declaredSlug = declared.languages[0] ? languageSlug(declared.languages[0]) : undefined;
  return { language: declaredSlug, pending: onboarding.isPending };
}

/**
 * The search the space's own pages declare.
 *
 * `language` is optional because the declared context can supply it, and a value this build does
 * not know is DROPPED rather than carried: a stale `?language=javascript` would otherwise be
 * echoed back into every link and read as a choice the learner never made.
 */
export function validateProgrammingSearch(search: Record<string, unknown>): { language?: ProgrammingLanguageSlug } {
  const language = normalizeLanguageSlug(search.language);
  return language ? { language } : {};
}
