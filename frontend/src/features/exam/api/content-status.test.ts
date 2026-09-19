import { describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET: get } }));

import { ApiRequestError, getExamSubjectContentStatus } from '@/features/exam/api/content-status';

describe('getExamSubjectContentStatus', () => {
  it('uses the generated content-status path and returns its generated response unchanged', async () => {
    const response = { ok: true, status: 200 } as Response;
    const payload = { availability: 'active' };
    get.mockResolvedValue({ data: payload, error: undefined, response });

    await expect(getExamSubjectContentStatus('cs_408')).resolves.toBe(payload);
    expect(get).toHaveBeenCalledWith('/exam/prep/subjects/{subject_id}/content-status', {
      params: { path: { subject_id: 'cs_408' } },
    });
  });

  it('preserves HTTP status and opaque contract detail for the shared error layer', async () => {
    const response = { ok: false, status: 409 } as Response;
    const detail = { code: 'EXAM_CONTENT_NOT_AVAILABLE' };
    get.mockResolvedValue({ data: undefined, error: detail, response });

    await expect(getExamSubjectContentStatus('math_1')).rejects.toEqual(
      new ApiRequestError(409, detail),
    );
  });

  it('does not treat a missing success payload as usable content', async () => {
    const response = { ok: true, status: 200 } as Response;
    get.mockResolvedValue({ data: undefined, error: undefined, response });

    await expect(getExamSubjectContentStatus('cs_408')).rejects.toEqual(
      new ApiRequestError(200, undefined),
    );
  });
});
