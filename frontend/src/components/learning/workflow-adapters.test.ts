import { describe, expect, it } from 'vitest';
import { executionEvidence, reviewAdapterUnavailable } from './workflow-adapters';

describe('P3A workflow adapters', () => {
  it('keeps run, test, and submit evidence distinct without inferring success', () => {
    expect(executionEvidence('test', { stdout: 'ok', stderr: 'failure', passed: false })).toEqual({
      kind: 'test', stdout: 'ok', stderr: 'failure', passed: false,
    });
  });

  it('marks review unavailable until a real aggregate contract is supplied', () => {
    expect(reviewAdapterUnavailable()).toEqual({ available: false, items: [], summary: undefined });
  });
});
