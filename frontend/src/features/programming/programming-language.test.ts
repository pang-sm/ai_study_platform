import { describe, expect, it } from 'vitest';
import { canonicalLanguage, languageSlug } from './programming-language';

describe('programming language identity', () => {
  it.each([
    ['c', 'C'], ['cpp', 'C++'], ['python', 'Python'], ['java', 'Java'],
  ])('maps the route slug %s to the backend canonical language %s', (slug, canonical) => {
    expect(canonicalLanguage(slug)).toBe(canonical);
    expect(languageSlug(canonical)).toBe(slug);
  });
});
