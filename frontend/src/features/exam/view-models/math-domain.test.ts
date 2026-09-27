import { describe, expect, it } from 'vitest';
import type { components } from '@/types/api';
import {
  coverageVerdict,
  mathCapability,
  mathDomainNames,
  mathVariantOf,
  type MathTaxonomy,
} from '@/features/exam/view-models/math-domain';

type MathCoverage = components['schemas']['MathCoverageEntrySummary'];

/** The backend's maths taxonomy, exactly as `GET /exam/prep/math/taxonomy` returns it today. */
const TAXONOMY: MathTaxonomy = {
  math_taxonomy_version: 'v1',
  math_ready_level: 'L1',
  math_openable: false,
  openable_reason: '知识体系已建立，但数学（一）/（二）/（三）的考试范围尚未由权威大纲导入，数学学习入口暂不开放。',
  domains: [
    { key: 'calculus', display_name: '高等数学', order: 1, knowledge_map_id: 'calculus', status: 'available', source: '微积分教材', source_reference: '' },
    { key: 'linear_algebra', display_name: '线性代数', order: 2, knowledge_map_id: 'linear_algebra', status: 'available', source: '线性代数讲义', source_reference: '' },
    { key: 'probability_statistics', display_name: '概率论与数理统计', order: 3, knowledge_map_id: 'probability_statistics', status: 'available', source: '概率论与数理统计', source_reference: '' },
  ],
  variants: [
    { id: 'math_1', display_name: '数学（一）', subject_id: 'math_1', order: 1 },
    { id: 'math_2', display_name: '数学（二）', subject_id: 'math_2', order: 2 },
    { id: 'math_3', display_name: '数学（三）', subject_id: 'math_3', order: 3 },
  ],
  coverage_status: 'pending_syllabus_import',
  coverage_note: '考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。',
  coverage_sources: [
    { id: 'syllabus_national_pending', name: '全国硕士研究生招生考试数学考试大纲', kind: 'official_syllabus', reference: '高等教育出版社', verification_status: 'pending_source', note: '暂无可用权威文本。' },
  ],
  coverage: [],
};

/** The three papers as the catalogue declares them. Names come from the catalogue, not here. */
const PAPERS = [
  { id: 'math_1', display_name: '数学（一）' },
  { id: 'math_2', display_name: '数学（二）' },
  { id: 'math_3', display_name: '数学（三）' },
] as const;

describe('the maths papers are scope over one domain set', () => {
  it('recognises exactly the catalogue’s maths papers, and nothing else', () => {
    expect(PAPERS.map((paper) => mathVariantOf(paper.id))).toEqual(['math_1', 'math_2', 'math_3']);
    for (const notMath of ['cs_408', 'politics', 'english_1', 'math', 'math_4', 'maths_1', '']) {
      expect(mathVariantOf(notMath), notMath).toBeNull();
    }
  });

  it('resolves all three papers onto the SAME canonical architecture', () => {
    const capabilities = PAPERS.map((paper) => mathCapability(paper, TAXONOMY));
    for (const capability of capabilities) {
      expect(capability).not.toBeNull();
      expect(capability?.domains.map((domain) => domain.key)).toEqual([
        'calculus', 'linear_algebra', 'probability_statistics']);
      expect(capability?.domains.map((domain) => domain.name)).toEqual(['高等数学', '线性代数', '概率论与数理统计']);
    }
    // Math1 → Math2 changes the range, not the content: the domains are equal, element for element.
    expect(capabilities[0]?.domains).toEqual(capabilities[1]?.domains);
    expect(capabilities[1]?.domains).toEqual(capabilities[2]?.domains);
    expect(capabilities[0]?.maturity).toBe(capabilities[2]?.maturity);
  });

  it('differs between the papers only in their exam range', () => {
    const one = mathCapability(PAPERS[0], TAXONOMY);
    const two = mathCapability(PAPERS[1], TAXONOMY);
    expect(one?.variant).toBe('math_1');
    expect(two?.variant).toBe('math_2');
    // The only variant-dependent field is the coverage slice, and it is empty for both.
    expect(one?.coverage.entries).toEqual([]);
    expect(two?.coverage.entries).toEqual([]);
  });

  it('never creates a per-paper copy of a domain', () => {
    for (const paper of PAPERS) {
      const capability = mathCapability(paper, TAXONOMY);
      // The variant appears as the paper's own identity — never as a prefix on content.
      expect(JSON.stringify(capability)).not.toMatch(new RegExp(`${paper.id}_`));
      // And every domain key is a canonical domain key, with no paper anywhere in it.
      for (const domain of capability?.domains ?? []) {
        expect(domain.key).not.toMatch(/math_?[123]/);
        expect(domain.key).not.toContain(paper.id);
      }
    }
  });

  it('returns the canonical names in one call, for a caller that has no room for the rest', () => {
    const capability = mathCapability(PAPERS[0], TAXONOMY);
    expect(capability && mathDomainNames(capability)).toEqual(['高等数学', '线性代数', '概率论与数理统计']);
  });

  it('carries the paper’s catalogue name through untouched', () => {
    expect(mathCapability({ id: 'math_2', display_name: '数学（二）' }, TAXONOMY)?.name).toBe('数学（二）');
  });

  it('has no capability at all for a subject that is not a maths paper', () => {
    expect(mathCapability({ id: 'cs_408', display_name: '计算机学科专业基础 408' }, TAXONOMY)).toBeNull();
  });

  it('states nothing when the taxonomy has not arrived', () => {
    // Better to say nothing about maths than to describe it from a copy that may be stale.
    expect(mathCapability(PAPERS[0], undefined)).toBeNull();
  });
});

describe('the exam range is not stated, because no source states it', () => {
  it('reports the backend’s own pending status and sentence', () => {
    const capability = mathCapability(PAPERS[0], TAXONOMY);
    expect(capability?.coverage.status).toBe('pending_syllabus_import');
    expect(capability?.coverage.note).toBe('考试范围待正式导入，以当年全国硕士研究生招生考试大纲为准。');
  });

  it('holds no coverage claim at all, and never invents one', () => {
    for (const paper of PAPERS) {
      expect(mathCapability(paper, TAXONOMY)?.coverage.entries).toEqual([]);
    }
  });

  it('keeps 未定 and 确认不在范围 apart', () => {
    // `null` means nobody has established the answer; `false` means an authority said no.
    const unstated: MathCoverage = { variant: 'math_1', domain: 'calculus', level: 'chapter', code: '8', included: null, source_id: 's' };
    const excluded: MathCoverage = { ...unstated, included: false };
    const included: MathCoverage = { ...unstated, included: true };
    expect(coverageVerdict(unstated)).toBe('unstated');
    expect(coverageVerdict(excluded)).toBe('excluded');
    expect(coverageVerdict(included)).toBe('included');
  });

  it('carries source metadata for every claim it is given', () => {
    // The invariant a future import has to satisfy: no claim without a resolvable source.
    const claimed: MathCoverage = { variant: 'math_1', domain: 'calculus', level: 'domain', code: '', included: true, source_id: 'syllabus_national_pending' };
    const withClaim: MathTaxonomy = { ...TAXONOMY, coverage: [claimed] };
    const capability = mathCapability(PAPERS[0], withClaim);
    const sourceIds = new Set(capability?.coverage.sources.map((source) => source.id));
    for (const entry of capability?.coverage.entries ?? []) {
      expect(sourceIds.has(entry.source_id), entry.source_id).toBe(true);
    }
  });
});

describe('capability is derived from the backend gate, never asserted here', () => {
  it('reports the maths subjects as frameworks while the taxonomy is not openable', () => {
    for (const paper of PAPERS) {
      const capability = mathCapability(paper, TAXONOMY);
      expect(capability?.maturity).toBe('framework');
      expect(capability?.note).toContain('学习内容尚未开放');
    }
  });

  it('follows the backend when the backend opens the subject', () => {
    // Nothing in the frontend decides this: flipping the backend's gate flips the card.
    const opened: MathTaxonomy = { ...TAXONOMY, math_openable: true, math_ready_level: 'L2' };
    const capability = mathCapability(PAPERS[0], opened);
    expect(capability?.maturity).toBe('open');
    expect(capability?.note).toBe('考研数学由高等数学、线性代数、概率论与数理统计组成。');
  });

  it('reports each domain’s real knowledge-map state', () => {
    const capability = mathCapability(PAPERS[0], TAXONOMY);
    expect(capability?.domains.every((domain) => domain.knowledgeMapStatus === 'available')).toBe(true);
    const pending: MathTaxonomy = {
      ...TAXONOMY,
      domains: TAXONOMY.domains.map((domain) => ({ ...domain, status: 'pending' as const })),
      math_openable: false,
    };
    expect(mathCapability(PAPERS[0], pending)?.domains.every((d) => d.knowledgeMapStatus === 'pending')).toBe(true);
  });

  it('counts no topics anywhere — there is no count to make', () => {
    const capability = mathCapability(PAPERS[0], TAXONOMY);
    expect(JSON.stringify(capability)).not.toMatch(/topicCount|topic_count/);
  });
});

describe('what the model reads', () => {
  it('is a function of the subject and the backend taxonomy alone', () => {
    // No learner, no records, no course state: maths cannot leak one namespace's user state into
    // another because it never takes any. Two calls with the same inputs are one answer.
    const a = mathCapability({ id: 'math_1', display_name: '数学（一）' }, TAXONOMY);
    const b = mathCapability({ id: 'math_1', display_name: '数学（一）' }, TAXONOMY);
    expect(a).toEqual(b);
    expect(JSON.stringify(a)).not.toMatch(/course|progress|mastery|掌握|学习记录/i);
  });
});
