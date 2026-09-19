import { describe, expect, it } from 'vitest';
import { resolveApiResourceUrl } from './client';

describe('resolveApiResourceUrl', () => {
  it('resolves normalized API-base-relative resources against the configured backend origin and pathname', () => {
    expect(resolveApiResourceUrl('/exam/11408/past-paper-images/operating_system/2022/q46.jpg', 'http://127.0.0.1:8955/api/v1'))
      .toBe('http://127.0.0.1:8955/api/v1/exam/11408/past-paper-images/operating_system/2022/q46.jpg');
  });
});
