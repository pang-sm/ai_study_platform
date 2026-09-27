import { describe, expect, it } from 'vitest';
import type { components } from '@/types/api';
import {
  EXAM_PLAN_DISCLAIMER,
  activeSubjectEntry,
  combinationReplacesSelection,
  examSlot,
  examTypeLabel,
  planOptions,
  professionalGroups,
  recommendedSubjects,
  subjectContinue,
  toExamPlan,
  type ExamCatalog,
  type ExamPlan,
  type ExamPlanSubject,
  type ExamProfile,
} from '@/features/exam/view-models/exam-plan';

/** The subject the assertions are about, or a failure — never an index that might be absent. */
function byId(plan: ExamPlan, id: string): ExamPlanSubject {
  const found = plan.subjects.find((subject) => subject.id === id);
  if (!found) throw new Error(`no subject ${id} in the plan`);
  return found;
}

type CatalogSubject = components['schemas']['ExamSubjectSummary'];

function subject(
  id: string,
  display_name: string,
  category: string,
  availability: CatalogSubject['availability'] = 'framework_only',
  modules: CatalogSubject['modules'] = [],
): CatalogSubject {
  return {
    id,
    display_name,
    category,
    availability,
    has_questions: availability === 'active',
    has_past_papers: availability === 'active',
    has_knowledge_tree: availability === 'active',
    description: '',
    suggested_tracks: [],
    modules,
  };
}

const cs408 = subject('cs_408', '计算机学科专业基础 408', 'professional', 'active', [
  { id: 'data_structure', display_name: '数据结构' },
  { id: 'computer_organization', display_name: '计算机组成原理' },
  { id: 'operating_system', display_name: '操作系统' },
  { id: 'computer_network', display_name: '计算机网络' },
]);

const catalog: ExamCatalog = {
  catalog_version: 'v2',
  exam_type: 'postgraduate',
  tracks: [
    {
      id: 'cs_408',
      display_name: '计算机 408',
      exam_type: 'postgraduate',
      availability: 'active',
      has_content: true,
      description: '',
      subject_options: ['cs_408'],
      suggested_subjects: ['cs_408'],
    },
    {
      id: 'law_jm_law',
      display_name: '法律硕士（法学）',
      exam_type: 'postgraduate',
      availability: 'framework_only',
      has_content: false,
      description: '',
      subject_options: ['politics', 'english_1', 'law_master_law'],
      suggested_subjects: [],
    },
  ],
  subjects: [
    cs408,
    subject('politics', '思想政治理论', 'public'),
    subject('english_1', '英语（一）', 'public'),
    subject('english_2', '英语（二）', 'public'),
    subject('math_1', '数学（一）', 'public'),
    subject('math_2', '数学（二）', 'public'),
    subject('math_3', '数学（三）', 'public'),
    subject('law_master_law', '法律硕士（法学）全国统考科目', 'professional'),
  ],
  active_subject_ids: ['cs_408'],
  framework_only_subject_ids: ['politics', 'english_1', 'english_2', 'math_1', 'math_2', 'math_3', 'law_master_law'],
};

function profile(overrides: Partial<ExamProfile> = {}): ExamProfile {
  return {
    configured: true,
    exam_type: 'postgraduate',
    selected_track: 'cs_408',
    selected_subjects: ['cs_408'],
    target_exam_year: 2027,
    subjects: [],
    custom_subjects: [],
    ...overrides,
  };
}

describe('exam slot model', () => {
  it('reads each catalogue subject onto the line the plan shows it on', () => {
    expect(examSlot('politics', 'public')).toBe('politics');
    expect(examSlot('english_1', 'public')).toBe('english');
    expect(examSlot('english_2', 'public')).toBe('english');
    expect(examSlot('math_1', 'public')).toBe('math');
    expect(examSlot('math_3', 'public')).toBe('math');
    expect(examSlot('cs_408', 'professional')).toBe('professional');
  });

  it('groups the configuration screen by the same rule the plan uses', () => {
    const options = planOptions(catalog);
    expect(options.politics.map((o) => o.id)).toEqual(['politics']);
    expect(options.english.map((o) => o.id)).toEqual(['english_1', 'english_2']);
    expect(options.math.map((o) => o.id)).toEqual(['math_1', 'math_2', 'math_3']);
    expect(options.professional.map((o) => o.id)).toEqual(['cs_408', 'law_master_law']);
  });
});

describe('exam type label', () => {
  it('names the one type the product supports, and shows an unknown type as itself', () => {
    expect(examTypeLabel('postgraduate')).toBe('全国硕士研究生招生考试（统考）');
    expect(examTypeLabel('some_future_type')).toBe('some_future_type');
  });
});

describe('the plan', () => {
  it('states the combination as the learner’s own subjects, in slot order', () => {
    const plan = toExamPlan(
      catalog,
      profile({
        selected_subjects: ['cs_408', 'math_1', 'politics', 'english_1'],
        subjects: [cs408, subject('math_1', '数学（一）', 'public'), subject('politics', '思想政治理论', 'public'), subject('english_1', '英语（一）', 'public')],
      }),
    );

    expect(plan.subjectLine).toBe('思想政治理论 · 英语（一） · 数学（一） · 计算机学科专业基础 408');
    expect(plan.subjects.map((s) => s.slot)).toEqual(['politics', 'english', 'math', 'professional']);
    expect(plan.examTypeLabel).toBe('全国硕士研究生招生考试（统考）');
    expect(plan.directionLabel).toBe('计算机 408');
    expect(plan.disclaimer).toBe(EXAM_PLAN_DISCLAIMER);
  });

  it('expresses a plan that takes no unified maths as the absence of a maths subject', () => {
    // 不考统考数学 is not a subject. Nothing is invented to stand for it, and the other three
    // lines still read normally.
    const plan = toExamPlan(
      catalog,
      profile({
        selected_subjects: ['cs_408', 'politics', 'english_2'],
        subjects: [cs408, subject('politics', '思想政治理论', 'public'), subject('english_2', '英语（二）', 'public')],
      }),
    );

    expect(plan.subjectLine).toBe('思想政治理论 · 英语（二） · 计算机学科专业基础 408');
    expect(plan.subjects.some((s) => s.slot === 'math')).toBe(false);
  });

  it('opens a subject only where this build has a study surface for it', () => {
    const plan = toExamPlan(
      catalog,
      profile({
        selected_subjects: ['cs_408', 'law_master_law'],
        subjects: [cs408, subject('law_master_law', '法律硕士（法学）全国统考科目', 'professional')],
      }),
    );

    const cs = byId(plan, 'cs_408');
    const law = byId(plan, 'law_master_law');
    expect(cs.entry).toBe('/exam/cs408');
    expect(cs.maturity).toBe('open');
    expect(cs.statusLabel).toBe('完整学习功能已开放');
    // The parts are the catalogue's own names, and nothing more: how a paper is chosen is the
    // subject's page, not a set of routes hung off each row here.
    expect(cs.modules.map((m) => m.name)).toEqual(['数据结构', '计算机组成原理', '操作系统', '计算机网络']);
    expect(cs.modules.every((m) => Object.keys(m).sort().join() === 'key,name')).toBe(true);

    // A framework-only subject gets the same wording as every other framework-only subject:
    // it is in exactly the same state, and naming one of them as richer would claim content.
    expect(law.maturity).toBe('framework');
    expect(law.statusLabel).toBe('科目框架已建立');
    expect(law.entry).toBeUndefined();
    expect(law.modules).toEqual([]);
  });

  it('keeps a framework-only ACTIVE-adjacent subject out of the study surfaces', () => {
    // Only cs_408 has a surface in this build. A catalogue subject is never pointed at another
    // subject's page, whatever its availability says.
    expect(activeSubjectEntry('cs_408')).toBe('/exam/cs408');
    expect(activeSubjectEntry('law_master_law')).toBeUndefined();
    expect(activeSubjectEntry('math_1')).toBeUndefined();
  });

  it('carries the learner’s own named subject without pretending it is a catalogue one', () => {
    const plan = toExamPlan(
      catalog,
      profile({
        selected_subjects: ['cs_408'],
        subjects: [cs408],
        custom_subjects: [{ id: 'custom_abc', name: '数据结构与算法（自命题）' }],
      }),
    );

    const custom = plan.subjects.at(-1);
    expect(custom?.id).toBe('custom_abc');
    expect(custom?.slot).toBe('custom');
    expect(custom?.maturity).toBe('custom');
    expect(custom?.statusLabel).toBe('自命题专业课');
    expect(custom?.entry).toBeUndefined();
  });

  it('states a stored id the catalogue no longer resolves instead of dropping it', () => {
    const plan = toExamPlan(
      catalog,
      profile({ selected_subjects: ['cs_408', 'retired_subject'], subjects: [cs408] }),
    );

    const retired = plan.subjects.find((s) => s.id === 'retired_subject');
    expect(retired?.maturity).toBe('unknown');
    expect(retired?.statusLabel).toBe('科目已下线');
  });

  it('reads the plan back as the exam it is, headline and subjects', () => {
    const plan = toExamPlan(
      catalog,
      profile({
        selected_subjects: ['cs_408', 'math_1', 'politics', 'english_1'],
        subjects: [cs408, subject('math_1', '数学（一）', 'public'), subject('politics', '思想政治理论', 'public'), subject('english_1', '英语（一）', 'public')],
      }),
    );

    expect(plan.headline).toBe('2027 全国硕士研究生招生考试（统考）');
    expect(plan.subjectNames).toEqual(['思想政治理论', '英语（一）', '数学（一）', '计算机学科专业基础 408']);
    expect(plan.subjectLine).toBe('思想政治理论 · 英语（一） · 数学（一） · 计算机学科专业基础 408');
  });

  it('names the exam without a year when none is set, rather than inventing one', () => {
    const plan = toExamPlan(catalog, profile({ target_exam_year: null }));
    expect(plan.examYear).toBeNull();
    expect(plan.headline).toBe('全国硕士研究生招生考试（统考）');
  });

  it('reports an empty plan as unconfigured, with no subjects and no direction', () => {
    const plan = toExamPlan(catalog, profile({ configured: false, selected_track: null, selected_subjects: [], target_exam_year: null }));
    expect(plan.configured).toBe(false);
    expect(plan.directionLabel).toBeNull();
    expect(plan.subjectLine).toBe('');
    expect(plan.subjectNames).toEqual([]);
  });
});

describe('the study entry of the subject that is open', () => {
  const open = () =>
    toExamPlan(catalog, profile({ selected_subjects: ['cs_408', 'math_1'], subjects: [cs408, subject('math_1', '数学（一）', 'public')] }));

  it('claims 继续学习 only for a paper a record actually names, and opens that paper', () => {
    const cs = byId(open(), 'cs_408');
    // The named paper opens directly: every paper begins at its own knowledge outline, so a
    // learner who left off in 操作系统 is not asked which of the four they meant.
    expect(subjectContinue(cs, 'operating_system')).toEqual({
      href: '/exam/cs408/knowledge',
      search: { module: 'operating_system' },
      label: '继续学习 · 操作系统',
    });
  });

  it('offers the same destination without the claim when nothing was recorded', () => {
    const cs = byId(open(), 'cs_408');
    // No paper to open, so no `search`: the subject's front door is where a learner with no
    // recorded work has to choose one anyway.
    expect(subjectContinue(cs, undefined)).toEqual({ href: '/exam/cs408', label: '进入 408' });
  });

  it('ignores a module key the subject does not have', () => {
    // A record from another subject's module must not name a paper inside this one.
    const cs = byId(open(), 'cs_408');
    expect(subjectContinue(cs, 'algebra')).toEqual({ href: '/exam/cs408', label: '进入 408' });
  });

  it('offers no study entry for a subject this build cannot open', () => {
    const math = byId(open(), 'math_1');
    expect(subjectContinue(math, 'operating_system')).toBeNull();
    expect(subjectContinue(math, undefined)).toBeNull();
  });
});

describe('the professional line, split by what can actually be studied', () => {
  it('separates the subject this build can open from the national papers it cannot', () => {
    const groups = professionalGroups(planOptions(catalog));
    expect(groups.primary.map((option) => option.id)).toEqual(['cs_408']);
    expect(groups.national.map((option) => option.id)).toEqual(['law_master_law']);
  });
});

describe('whether a suggested combination would cost the learner something', () => {
  it('needs no warning when the suggestion only adds', () => {
    expect(combinationReplacesSelection([], ['politics', 'cs_408'])).toBe(false);
    expect(combinationReplacesSelection(['cs_408'], ['cs_408', 'math_1'])).toBe(false);
  });

  it('needs one when the suggestion would drop a subject the learner chose', () => {
    expect(combinationReplacesSelection(['cs_408', 'math_2'], ['politics', 'math_1', 'cs_408'])).toBe(true);
    expect(combinationReplacesSelection(['math_2'], ['math_1'])).toBe(true);
  });
});

describe('the recommended combination', () => {
  it('uses the catalogue’s own subject options where the direction declares them', () => {
    const law = catalog.tracks.find((track) => track.id === 'law_jm_law');
    expect(recommendedSubjects(law)).toEqual(['politics', 'english_1', 'law_master_law']);
  });

  it('offers a starting combination for the one shipped direction the catalogue leaves narrow', () => {
    const cs = catalog.tracks.find((track) => track.id === 'cs_408');
    expect(recommendedSubjects(cs)).toEqual(['politics', 'english_1', 'math_1', 'cs_408']);
  });

  it('recommends nothing without a direction, rather than guessing one', () => {
    expect(recommendedSubjects(undefined)).toEqual([]);
  });
});
