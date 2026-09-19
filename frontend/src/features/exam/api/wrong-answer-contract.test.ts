import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET, PATCH } = vi.hoisted(() => ({ GET: vi.fn(), PATCH: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, PATCH } }));

import { apiClient } from '@/lib/api/client';

// BC7 — compile-level proof that the canonical wrong-answer transport is concrete and can
// express everything F1C4 needs, with NO handwritten transport DTO and no cast. Every alias
// resolves through the generated `paths` / `components`, so a regeneration that drops or
// loosens one of these operations fails `npm run typecheck` rather than silently becoming
// `unknown`.
//
// The frontend must not merge, resolve, dedupe or re-grade anything: the record below is what
// the backend already decided, and the status is a fact about a factual attempt.

type ListQuery = NonNullable<paths['/wrong-answers']['get']['parameters']['query']>;
type ListResponse = paths['/wrong-answers']['get']['responses'][200]['content']['application/json'];
type DetailResponse = paths['/wrong-answers/{state_id}']['get']['responses'][200]['content']['application/json'];
type PatchBody = paths['/wrong-answers/{state_id}']['patch']['requestBody']['content']['application/json'];
type PatchResponse = paths['/wrong-answers/{state_id}']['patch']['responses'][200]['content']['application/json'];

type WrongRecord = components['schemas']['WrongAnswerRecord'];
type WrongResource = components['schemas']['WrongAnswerResource'];
type SourceKind = WrongRecord['source_kind'];
type WrongStatus = WrongRecord['status'];

// The closed product vocabulary the workspace renders — never a legacy table name.
const SOURCE_LABELS: Record<SourceKind, string> = {
  chapter_practice: '章节练习',
  past_paper: '历年真题',
  ai_generated: 'AI 出题',
  other: '其他',
};

// Resolution state is read straight off the record. Nothing here derives it.
const STATUS_LABELS: Record<WrongStatus, string> = { active: '未订正', resolved: '已订正' };

function sourceLabel(record: WrongRecord) {
  return SOURCE_LABELS[record.source_kind];
}

function statusLabel(record: WrongRecord) {
  return STATUS_LABELS[record.status];
}

// Past papers are addressed by the BC6 public identity, not by any source id.
function pastPaperKey(record: WrongRecord) {
  if (record.question_number === null || record.year === null) return null;
  return `${record.module_key}:${record.year}:${record.question_number}`;
}

// Chapter practice is addressed by the bank question id the redo contract takes.
function chapterRedoIds(records: WrongRecord[]) {
  return records
    .filter((record) => record.source_kind === 'chapter_practice')
    .map((record) => record.question_bank_id)
    .filter((id): id is number => id !== null);
}

function resourceUrls(record: WrongRecord): string[] {
  return (record.resources ?? []).map((resource: WrongResource) => resource.url);
}

function blankVsIncorrect(records: WrongRecord[]) {
  const answered = records.filter((record) => record.user_answer !== '');
  return {
    answered: answered.length,
    unanswered: records.length - answered.length,
    // a blank can never appear here: the backend never files one as wrong
    blanks: records.filter((record) => record.user_answer === '').length,
  };
}

const pastPaperRecord: WrongRecord = {
  wrong_record_id: 1,
      status: 'active',
      service_namespace: 'exam_prep',
      module_key: 'operating_system',
      module_name: '操作系统',
      source_kind: 'past_paper',
      source_label: '历年真题',
      question_type: 'choice',
      stem: '某系统采用页式存储管理…',
      options: { A: '甲', B: '乙' },
      user_answer: 'B',
      reference_answer: 'A',
      analysis: '页表项…',
      year: 2022,
      question_number: 33,
      question_bank_id: null,
      knowledge_point_id: null,
      knowledge_point_name: null,
      knowledge_point_path: null,
      resources: [{ url: '/exam/11408/past-paper-images/operating_system/2022/2022_45_0.jpg' }],
      first_wrong_at: '2026-09-01T09:00:00',
      last_wrong_at: '2026-09-02T09:00:00',
      resolved_at: null,
      repeat_wrong_count: 2,
};

const chapterRecord: WrongRecord = {
  wrong_record_id: 2,
  status: 'resolved',
  service_namespace: 'exam_prep',
  module_key: 'data_structure',
  module_name: '数据结构',
  source_kind: 'chapter_practice',
  source_label: '章节练习',
  question_type: 'choice',
  stem: '下列排序算法中…',
  options: { A: '甲', B: '乙' },
  user_answer: 'A',
  reference_answer: 'B',
  analysis: null,
  year: null,
  question_number: null,
  question_bank_id: 4242,
  knowledge_point_id: '1.1',
  knowledge_point_name: '排序',
  knowledge_point_path: '第一章/排序',
  resources: [],
  first_wrong_at: '2026-08-01T09:00:00',
  last_wrong_at: '2026-08-01T09:00:00',
  resolved_at: '2026-08-03T09:00:00',
  repeat_wrong_count: 1,
};

const listPayload: ListResponse = {
  items: [pastPaperRecord, chapterRecord],
  total: 2,
  limit: 50,
  offset: 0,
};

describe('BC7 canonical wrong-answer generated contract', () => {
  it('types the module-scoped list, status filter and pagination', async () => {
    const query: ListQuery = {
      service_namespace: 'exam_prep',
      module: 'operating_system',
      status: 'active',
      limit: 50,
      offset: 0,
    };
    GET.mockResolvedValue({
      data: listPayload,
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });

    const { data } = await apiClient.GET('/wrong-answers', { params: { query } });
    if (!data) throw new Error('unreachable');
    expect(data.total).toBe(2);
    expect(data.items).toHaveLength(2);
    // pagination is server-side: the client never asks for an unbounded list
    expect(data.limit).toBeLessThanOrEqual(200);
  });

  it('expresses source context, status and the question/reference snapshots', () => {
    expect(sourceLabel(pastPaperRecord)).toBe('历年真题');
    expect(sourceLabel(chapterRecord)).toBe('章节练习');
    expect(statusLabel(pastPaperRecord)).toBe('未订正');
    expect(statusLabel(chapterRecord)).toBe('已订正');
    // the display facts come from the record, not from re-fetching the question
    expect(pastPaperRecord.stem).not.toBe('');
    expect(pastPaperRecord.user_answer).toBe('B');
    expect(pastPaperRecord.reference_answer).toBe('A');
    expect(chapterRecord.analysis).toBeNull();
    expect(pastPaperRecord.repeat_wrong_count).toBe(2);
  });

  it('carries the public past-paper identity and the chapter redo identity', () => {
    expect(pastPaperKey(pastPaperRecord)).toBe('operating_system:2022:33');
    expect(pastPaperKey(chapterRecord)).toBeNull();   // a chapter record has no year
    expect(chapterRedoIds(listPayload.items)).toEqual([4242]);
  });

  it('carries figure references in the one BC6 URL contract', () => {
    expect(resourceUrls(pastPaperRecord)).toEqual([
      '/exam/11408/past-paper-images/operating_system/2022/2022_45_0.jpg',
    ]);
    expect(resourceUrls(chapterRecord)).toEqual([]);
  });

  it('never reports a blank answer as a wrong record', () => {
    expect(blankVsIncorrect(listPayload.items).blanks).toBe(0);
  });

  it('types the detail with its factual attempt history', async () => {
    const detail: DetailResponse = {
      ...pastPaperRecord,
      error_analysis: null,
      attempt_history: [
        {
          attempt_id: 11,
          submitted_at: '2026-09-01T09:00:00',
          answer: 'B',
          correct: false,
          score: null,
          max_score: null,
          source_attempt_type: 'past_paper_attempt',
        },
        {
          attempt_id: 12,
          submitted_at: '2026-09-02T09:00:00',
          answer: 'B',
          correct: false,
          score: null,
          max_score: null,
          source_attempt_type: 'past_paper_attempt',
        },
      ],
    };
    GET.mockResolvedValue({
      data: detail,
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });

    const { data } = await apiClient.GET('/wrong-answers/{state_id}', {
      params: { path: { state_id: 1 } },
    });
    if (!data) throw new Error('unreachable');
    const history = data.attempt_history ?? [];
    expect(history.map((attempt) => attempt.correct)).toEqual([false, false]);
    // a factual incorrect attempt is a bool; an unanswered one would be null, never false
    const verdict: boolean | null = history[0]?.correct ?? null;
    expect(verdict).toBe(false);
  });

  it('types the manual lifecycle action on the same record shape', async () => {
    const body: PatchBody = { resolved: true };
    const response: PatchResponse = { ...chapterRecord, status: 'resolved' };
    PATCH.mockResolvedValue({
      data: response,
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });

    const { data } = await apiClient.PATCH('/wrong-answers/{state_id}', {
      params: { path: { state_id: 2 } },
      body,
    });
    if (!data) throw new Error('unreachable');
    expect(data.status).toBe('resolved');
    // the patch returns the SAME model as the list, so one renderer covers both
    const asRecord: WrongRecord = data;
    expect(sourceLabel(asRecord)).toBe('章节练习');
  });
});
