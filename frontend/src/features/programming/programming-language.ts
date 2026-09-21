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
