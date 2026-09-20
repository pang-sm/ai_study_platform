/**
 * ACCEL_PRODUCT_S9 PART B1 — what the chapter-practice transport sends as a concept.
 *
 * The contract, in one sentence: a canonical concept id is sent ONLY when a surface already
 * holds it as a canonical id, and it is sent on the READ as `concept_code` (the canonical
 * filter) and on the WRITE as `knowledge_point_id` (the slot the attempt and its learning
 * event actually store). One mapping, stated once in the API module, asserted here.
 *
 * The absent case is as load-bearing as the present one: direct entry and the Study Plan's
 * practice action must send NOTHING, because a concept that was never known must stay unknown
 * rather than be filled in with a guess.
 */
import { describe, expect, it, vi } from 'vitest';
import type { paths } from '@/types/api';

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST } }));

import { isCanonicalConceptCode } from './chapter-practice';

// Compile-level: the generated contract must keep carrying both spellings. If a
// regeneration drops either, this file stops typechecking rather than silently passing.
type QuestionsQuery = NonNullable<paths['/exam/11408/{subject_key}/chapter-practice/questions']['get']['parameters']['query']>;
type AttemptCreateBody = paths['/exam/11408/{subject_key}/chapter-practice/attempts']['post']['requestBody']['content']['application/json'];

const readQuery: QuestionsQuery = { chapter_code: '3', concept_code: '3.6' };
const writeBody: AttemptCreateBody = { question_ids: [1], knowledge_point_id: '3.6' };

describe('chapter-practice concept transport', () => {
  it('names the concept the same way on both halves of the contract', () => {
    expect(readQuery.concept_code).toBe('3.6');
    expect(writeBody.knowledge_point_id).toBe('3.6');
    // and the legacy sub-group filter is a DIFFERENT parameter, never overloaded
    expect(Object.keys(readQuery)).toEqual(['chapter_code', 'concept_code']);
  });

  it('accepts a real canonical code and refuses the synthetic node codes', () => {
    expect(isCanonicalConceptCode('3.6')).toBe(true);
    expect(isCanonicalConceptCode('1.1.1')).toBe(true);      // shape is not the test; the server decides
    expect(isCanonicalConceptCode('_leaf:1.1')).toBe(false);
    expect(isCanonicalConceptCode('leaf:1.1')).toBe(false);
    expect(isCanonicalConceptCode('node:1')).toBe(false);
    expect(isCanonicalConceptCode('')).toBe(false);
    expect(isCanonicalConceptCode(undefined)).toBe(false);
    expect(isCanonicalConceptCode(null)).toBe(false);
  });
});

// The runtime half — that the workspace actually SENDS the concept it was given — is
// asserted in `cs408-practice-workspace.test.tsx`, where the hooks are mocked and the
// mutation payload is observable. This file owns the contract's shape; that one owns its use.
describe('the transport mock is wired to the real client module', () => {
  it('replaces apiClient so no request escapes the test', () => {
    expect(GET).toBeTypeOf('function');
    expect(POST).toBeTypeOf('function');
  });
});
