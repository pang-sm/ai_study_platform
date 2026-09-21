import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * LEARNER_METADATA_LEAKAGE_GUARD — the source half.
 *
 * The runtime guard (`learner-metadata-leakage.test.tsx`) proves no screen renders a payload
 * today. This one proves the vocabulary that once leaked cannot come back: the copy that named a
 * payload, the copy that offered to show one, and a direct `JSON.stringify` in a component.
 *
 * It reads source text, so a comment counts. That is deliberate for the banned *copy* — a phrase
 * this product has decided not to say should not be sitting anywhere in the learner's codebase
 * waiting to be pasted back into JSX.
 */

const SRC = join(import.meta.dirname, '..');

/** Copy that names the transport, or offers to disclose it. Never learner-facing. */
const BANNED_COPY = [
  '后端原文',
  '接口原文',
  '原始返回数据',
  '查看原始',
  '原因码',
  '请求 ID',
  '请求ID',
];

/**
 * The English unit words are a different case: `actual_credits` is a real column name and
 * `Usage: …` appears in the generated schema's own docstrings, so the rule is about *display*
 * copy rather than the word. It flags the phrase only where it is prose, not an identifier.
 */
const BANNED_DISPLAY_PROSE: ReadonlyArray<[string, RegExp]> = [
  ['Usage: as a label', /(?<![A-Za-z0-9_])Usage:/],
  ['credits as prose', /(?<![A-Za-z0-9_])credits(?![A-Za-z0-9_])/],
];

/** `types/api.ts` is generated from the backend's OpenAPI document and cannot be hand-edited. */
const GENERATED_OR_SCHEMA = [join('src', 'types', 'api.ts')];

/**
 * `JSON.stringify` is allowed only where it is an implementation detail that no learner reads:
 * a URL query builder, a storage/transport serializer, or a test fixture. A component that
 * renders its result is what this guard is for.
 */
const JSON_STRINGIFY_ALLOWED = [
  join('src', 'lib', 'api'),
  join('src', 'lib', 'utils.ts'),
  join('src', 'features', 'auth'),
  join('src', 'features', 'records', 'event-labels.ts'),
  join('src', 'test'),
  join('src', 'types'),
];

function sourceFiles(directory = SRC): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(entry) && !/\.test\.(ts|tsx)$/.test(entry) ? [path] : [];
  });
}

function shown(path: string) {
  return relative(SRC, path).split(sep).join('/');
}

const HAND_WRITTEN = sourceFiles().filter(
  (path) => !GENERATED_OR_SCHEMA.some((allowed) => path.endsWith(allowed)),
);

describe('LEARNER_METADATA_LEAKAGE_GUARD · source copy', () => {
  it.each(BANNED_COPY)('does not say %s anywhere in learner source', (phrase) => {
    expect(HAND_WRITTEN.filter((path) => readFileSync(path, 'utf8').includes(phrase)).map(shown)).toEqual([]);
  });

  it.each(BANNED_DISPLAY_PROSE)('does not use %s', (_name, pattern) => {
    const hits = HAND_WRITTEN.filter((path) => {
      if (GENERATED_OR_SCHEMA.some((allowed) => path.endsWith(allowed))) return false;
      return pattern.test(readFileSync(path, 'utf8'));
    }).map(shown);
    expect(hits).toEqual([]);
  });

  it('renders no component that serialises an object into the document', () => {
    const offenders = HAND_WRITTEN.filter((path) => {
      if (!readFileSync(path, 'utf8').includes('JSON.stringify')) return false;
      const relativePath = relative(SRC, path);
      return !JSON_STRINGIFY_ALLOWED.some((allowed) => relativePath.startsWith(allowed));
    }).map(shown);

    expect(offenders).toEqual([]);
  });

  it('has no learner-facing component that could disclose a payload', () => {
    // The component that used to be the one exit for raw objects is gone, not merely unused.
    const exportSites = HAND_WRITTEN.filter((path) => /export function RawPayload/.test(readFileSync(path, 'utf8')));
    expect(exportSites.map(shown)).toEqual([]);
  });
});
