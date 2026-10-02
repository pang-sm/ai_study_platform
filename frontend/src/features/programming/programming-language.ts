export const programmingLanguages = {
  c: 'C',
  cpp: 'C++',
  python: 'Python',
  java: 'Java',
} as const;

export type ProgrammingLanguageSlug = keyof typeof programmingLanguages;
export type CanonicalProgrammingLanguage = (typeof programmingLanguages)[ProgrammingLanguageSlug];

export function canonicalLanguage(slug: string): CanonicalProgrammingLanguage | undefined {
  return programmingLanguages[slug as ProgrammingLanguageSlug];
}

export function languageSlug(language: string): ProgrammingLanguageSlug | undefined {
  return (Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, CanonicalProgrammingLanguage]>)
    .find(([, canonical]) => canonical === language)?.[0];
}

/**
 * The slug for a language written either way.
 *
 * The product spells a language in two places and not always the same way: the URL search param
 * and the onboarding form key it by SLUG (`python`), while the stored context and the deep links
 * the backend builds name it CANONICALLY (`Python`). Both are the same language, so both are
 * accepted here and everything downstream works with the slug.
 */
export function normalizeLanguageSlug(value: unknown): ProgrammingLanguageSlug | undefined {
  if (typeof value !== 'string') return undefined;
  const text = value.trim();
  if (!text) return undefined;
  if (text in programmingLanguages) return text as ProgrammingLanguageSlug;
  return languageSlug(text);
}
