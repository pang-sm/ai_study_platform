export type ApiErrorKind =
  | 'authentication_required'
  | 'capability_required'
  | 'content_unavailable'
  | 'usage_exhausted'
  | 'technical_unavailable'
  | 'network_failure'
  | 'unknown';

export interface NormalizedApiError {
  kind: ApiErrorKind;
  message: string;
}

type ErrorDetail = unknown;

const messages: Record<Exclude<ApiErrorKind, 'content_unavailable' | 'unknown'>, string> = {
  authentication_required: '请登录后继续。',
  capability_required: '当前功能需要升级后使用。',
  usage_exhausted: '本次额度已用完，请稍后再试。',
  technical_unavailable: '服务暂时不可用，请稍后再试。',
  network_failure: '网络连接异常，请检查网络后重试。',
};

function objectDetail(detail: ErrorDetail): { code?: string; message?: string } | undefined {
  if (typeof detail !== 'object' || detail === null) return undefined;
  const value = detail as Record<string, unknown>;
  const nested = value.detail;
  if (typeof nested === 'object' && nested !== null) return objectDetail(nested);
  return {
    code: typeof value.code === 'string' ? value.code : undefined,
    message: typeof value.message === 'string' ? value.message : undefined,
  };
}

export function normalizeApiError(status: number | undefined, detail?: ErrorDetail): NormalizedApiError {
  const structured = objectDetail(detail);
  if (status === 409 && structured?.code === 'EXAM_CONTENT_NOT_AVAILABLE') {
    return { kind: 'content_unavailable', message: structured.message ?? '该科目内容尚未上线。' };
  }
  if (status === 401) return { kind: 'authentication_required', message: messages.authentication_required };
  if (status === 403) return { kind: 'capability_required', message: messages.capability_required };
  if (status === 429) return { kind: 'usage_exhausted', message: messages.usage_exhausted };
  if (status === 502) return { kind: 'technical_unavailable', message: messages.technical_unavailable };
  if (status === undefined || status === 0) return { kind: 'network_failure', message: messages.network_failure };
  return { kind: 'unknown', message: '页面暂时无法加载，请稍后重试。' };
}
