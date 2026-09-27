import type { components } from '@/types/api';
import { mathCapability, type MathCapability, type MathTaxonomy } from './math-domain';

/**
 * The exam space's own model, projected from what the backend already returns.
 *
 * STEP 7H4 froze the backend taxonomy as versioned CONFIG — a *track* (how I am preparing),
 * a *subject* (what is examined) and a *module* (how a subject is organised) are three separate
 * things, and the learner's scope is `profile.selected_subjects`, a flat list of subject ids.
 *
 * This file adds no schema and no endpoint. It is the projection that turns that flat list into
 * the product's own model:
 *
 *   ExamPlan             我的考试方案 — exam type, year, direction, and the subject combination
 *   ExamSubjectSelection politics / english variant / math variant / professional subject
 *   Subject              one entry per selected subject, with the capability it really has
 *
 * The slot rule below is a PRESENTATION rule, not an exam rule: it decides which line of the
 * plan a subject is read on. It never decides whether a subject is examined — the learner's own
 * confirmed selection does that. Nothing here writes exam facts the backend has not stated.
 */

export type ExamCatalog = components['schemas']['ExamPrepCatalogResponse'];
export type ExamProfile = components['schemas']['ExamPrepProfileResponse'];
export type ExamTrack = components['schemas']['ExamTrackSummary'];
export type ExamCatalogSubject = components['schemas']['ExamSubjectSummary'];
export type ExamCustomSubject = components['schemas']['CustomExamSubject'];
export type ExamSubjectAvailability = ExamCatalogSubject['availability'];

/** Where a subject sits in the plan: the four things a learner actually chooses. */
export type ExamSlot = 'politics' | 'english' | 'math' | 'professional' | 'other';

export type ExamSlotRole = ExamSlot | 'custom';

/**
 * One part of a subject, as the catalogue names it.
 *
 * Only the identity is kept. The parts used to carry the routes into their own tools as well,
 * which put a second navigation beside the workspace's own strip — the home page listed four
 * papers with three links each, the 408 overview listed the same four again, and neither was
 * where a learner switched paper. Where a subject's parts lead is now decided in one place, and
 * this stays what it is: the names the catalogue publishes.
 */
export type ExamModuleEntry = { key: string; name: string };

/** How much of a subject this build can actually offer — three honest states, never a count. */
export type ExamSubjectMaturity = 'open' | 'framework' | 'custom' | 'unknown';

export type ExamPlanSubject = {
  id: string;
  name: string;
  slot: ExamSlotRole;
  slotLabel: string;
  maturity: ExamSubjectMaturity;
  statusLabel: string;
  statusTone: 'success' | 'neutral' | 'warning' | 'danger';
  /** One fact about this subject's state. Never a progress number we did not measure. */
  note: string;
  /** The subject's own study surface, when this build has one. */
  entry?: string;
  /** The subject's parts. ACTIVE subjects only; a framework-only subject has none. */
  modules: readonly ExamModuleEntry[];
  /**
   * The shared maths model, for the subjects that are one of the three maths papers.
   *
   * One provider serves all three, so nothing here — and nothing downstream — may branch on a
   * maths subject's id. What a surface renders is read off this capability, which is why giving
   * `高等数学` real content later lights up 数学（一）/（二）/（三） together.
   */
  math?: MathCapability;
};

export type ExamPlan = {
  configured: boolean;
  examTypeLabel: string;
  examYear: number | null;
  /** The plan in one line: "2027 全国硕士研究生招生考试（统考）", or the type alone with no year. */
  headline: string;
  directionLabel: string | null;
  /** The combination, as separate names and as one line. */
  subjectNames: readonly string[];
  subjectLine: string;
  subjects: readonly ExamPlanSubject[];
  /** Shown wherever a learner confirms a combination. Mandatory, not decorative. */
  disclaimer: string;
};

/**
 * Where a subject's study entry goes and what it is called — from a recorded fact, never assumed.
 *
 * `search` carries the part the learner left off in, so 继续学习 · 操作系统 opens 操作系统 rather
 * than the subject's front door. It is absent when nothing was recorded, and the label says so.
 */
export type ExamContinue = { href: string; search?: Record<string, unknown>; label: string };

export const EXAM_PLAN_DISCLAIMER = '具体考试科目以目标院校当年招生专业目录为准。';

/**
 * The exam type the product actually supports, in the learner's words.
 *
 * Keyed on the backend's own `exam_type` value. An unrecognised value is shown as itself: a
 * label map that silently invented a name for an unknown type would be the frontend stating an
 * exam fact, and the backend is the only place that fact comes from.
 */
const EXAM_TYPE_LABELS: Readonly<Record<string, string>> = {
  postgraduate: '全国硕士研究生招生考试（统考）',
};

export function examTypeLabel(examType: string): string {
  return EXAM_TYPE_LABELS[examType] ?? examType;
}

/** Which line of the plan a catalogue subject is read on. */
const SLOT_BY_SUBJECT_ID: Readonly<Record<string, ExamSlot>> = {
  politics: 'politics',
  english_1: 'english',
  english_2: 'english',
  math_1: 'math',
  math_2: 'math',
  math_3: 'math',
};

const SLOT_LABELS: Readonly<Record<ExamSlotRole, string>> = {
  politics: '政治',
  english: '英语',
  math: '数学',
  professional: '专业课',
  other: '其他',
  custom: '自命题专业课',
};

/** Slot order for the plan line and the subject list. The learner's order is kept inside a slot. */
const SLOT_ORDER: readonly ExamSlotRole[] = ['politics', 'english', 'math', 'professional', 'other', 'custom'];

export function examSlot(subjectId: string, category: string | undefined): ExamSlot {
  const known = SLOT_BY_SUBJECT_ID[subjectId];
  if (known) return known;
  return category === 'professional' ? 'professional' : 'other';
}

/**
 * The study surfaces this build actually has, by catalogue subject id.
 *
 * This is a map and not a rule, because "is this subject open?" is answered by the catalogue's
 * `availability` while "where does it open onto?" is a route this frontend owns. The two are
 * deliberately separate: the catalogue can mark a subject ACTIVE before this build has a page
 * for it, and the honest answer there is the subject's own page — never a link to whichever
 * subject happens to have one.
 */
const CS408_ENTRY = '/exam/cs408';

/**
 * Where a paper of 408 opens, which is its knowledge outline.
 *
 * The subject's front door asks which of the four papers to study; a learner who has already been
 * told WHICH one is not asked again — they are put in front of it. That is why resuming names this
 * route rather than the front door: 继续学习 · 操作系统 landing on the four-paper question again
 * would make the record that produced the label pointless.
 */
const CS408_MODULE_ENTRY = '/exam/cs408/knowledge';

const ACTIVE_SUBJECT_SURFACES: Readonly<Record<string, { entry: string; shortName: string }>> = {
  // `shortName` is how this build refers to the subject in a compact action — the same way the
  // route and the tab strip already say `cs408`. The catalogue's own `display_name` is still what
  // the subject is called everywhere it is named in full.
  cs_408: { entry: CS408_ENTRY, shortName: '408' },
};

/** The study entry for a subject this build can open, or undefined when it has none. */
export function activeSubjectEntry(subjectId: string): string | undefined {
  return ACTIVE_SUBJECT_SURFACES[subjectId]?.entry;
}

export function isKnownExamSubject(
  subject: components['schemas']['ExamSubjectSummary'] | components['schemas']['UnknownExamSubject'],
): subject is components['schemas']['ExamSubjectSummary'] {
  return 'display_name' in subject;
}

const MATURITY_COPY: Readonly<Record<ExamSubjectMaturity, { label: string; tone: ExamPlanSubject['statusTone'] }>> = {
  // A subject whose real content exists AND whose surface this build has.
  open: { label: '完整学习功能已开放', tone: 'success' },
  // A subject the catalogue has opened for selection but whose content is not built. The label
  // is the same for every framework-only subject on purpose: they are in exactly the same state,
  // and wording one of them as richer would claim content nobody has shipped.
  framework: { label: '科目框架已建立', tone: 'warning' },
  // The learner's own 自命题 subject. It is not a national one and has no catalogue content.
  custom: { label: '自命题专业课', tone: 'neutral' },
  // A stored id the catalogue no longer resolves. Stated as such rather than dropped.
  unknown: { label: '科目已下线', tone: 'danger' },
};

/**
 * What a framework-only subject says when the catalogue gives it no description.
 *
 * One sentence, the same for all of them: they are in the same state, and a subject worded as
 * richer than its neighbours would be claiming content nobody has written.
 */
const FRAMEWORK_NOTE = '已纳入统一科目框架，学习内容尚未开放。';

function catalogueSubject(profile: ExamProfile, subjectId: string): ExamCatalogSubject | undefined {
  return profile.subjects.find(
    (subject): subject is ExamCatalogSubject => isKnownExamSubject(subject) && subject.id === subjectId,
  );
}

function toPlanSubject(subject: ExamCatalogSubject, mathTaxonomy?: MathTaxonomy): ExamPlanSubject {
  const slot = examSlot(subject.id, subject.category);
  const surface = ACTIVE_SUBJECT_SURFACES[subject.id];
  // A maths paper's state comes from the shared maths model, not from a branch on its id: the
  // three papers are one subject with three exam ranges, and the model decides whether any of it
  // can be studied. When no study surface exists AND the taxonomy says the subject is not
  // openable, it stays a framework.
  const math = mathCapability(subject, mathTaxonomy);
  // A subject is only "open" when content exists AND this build has somewhere to put the learner.
  // An ACTIVE catalogue subject with no surface states that its content is open and links to its
  // own page, which says what is there — it does not borrow another subject's page.
  const maturity: ExamSubjectMaturity = surface || math?.maturity === 'open' ? 'open' : 'framework';
  const copy = MATURITY_COPY[maturity];
  return {
    id: subject.id,
    name: subject.display_name,
    slot,
    slotLabel: SLOT_LABELS[slot],
    maturity,
    statusLabel: copy.label,
    statusTone: copy.tone,
    // The maths model's own sentence is more specific than the generic framework one, and it is
    // the model's to write.
    note: math && maturity === 'framework' ? math.note : subject.description || (maturity === 'framework' ? FRAMEWORK_NOTE : ''),
    entry: surface?.entry,
    modules: surface ? subject.modules.map((module) => ({ key: module.id, name: module.display_name })) : [],
    math: math ?? undefined,
  };
}

function toPlanCustomSubject(subject: ExamCustomSubject): ExamPlanSubject {
  const copy = MATURITY_COPY.custom;
  return {
    id: subject.id,
    name: subject.name,
    slot: 'custom',
    slotLabel: SLOT_LABELS.custom,
    maturity: 'custom',
    statusLabel: copy.label,
    statusTone: copy.tone,
    note: '平台未内置这门科目的题库与真题，可用自己上传的资料建立学习内容。',
    modules: [],
  };
}

function toPlanUnknownSubject(subjectId: string): ExamPlanSubject {
  const copy = MATURITY_COPY.unknown;
  return {
    id: subjectId,
    name: subjectId,
    slot: 'other',
    slotLabel: SLOT_LABELS.other,
    maturity: 'unknown',
    statusLabel: copy.label,
    statusTone: copy.tone,
    note: '这门科目已不在全国统考科目目录中。在考试方案里重新确认你的科目。',
    modules: [],
  };
}

/**
 * The learner's exam plan, or `undefined` when there is no configured profile.
 *
 * Ordering is by slot, then by the learner's own selection order inside a slot — the plan reads
 * the way an exam is listed, while still being the learner's list rather than a re-sorted one.
 */
export function toExamPlan(
  catalog: ExamCatalog,
  profile: ExamProfile,
  /** The backend's maths taxonomy, when it has arrived. Absent means maths stays unstated. */
  mathTaxonomy?: MathTaxonomy,
): ExamPlan {
  const subjects: ExamPlanSubject[] = profile.selected_subjects.map((subjectId) => {
    const known = catalogueSubject(profile, subjectId);
    if (known) return toPlanSubject(known, mathTaxonomy);
    const custom = profile.custom_subjects.find((item) => item.id === subjectId);
    return custom ? toPlanCustomSubject(custom) : toPlanUnknownSubject(subjectId);
  });

  // A custom subject the learner saved is part of the plan even if it is not in
  // `selected_subjects` — the two are separate fields on purpose, and dropping one here would
  // hide a subject the learner can see in the setup screen.
  for (const custom of profile.custom_subjects) {
    if (!subjects.some((subject) => subject.id === custom.id)) subjects.push(toPlanCustomSubject(custom));
  }

  const ordered = subjects
    .map((subject, index) => ({ subject, index }))
    .sort((a, b) => {
      const slot = SLOT_ORDER.indexOf(a.subject.slot) - SLOT_ORDER.indexOf(b.subject.slot);
      return slot !== 0 ? slot : a.index - b.index;
    })
    .map((entry) => entry.subject);

  const track = catalog.tracks.find((item) => item.id === profile.selected_track);
  const typeLabel = examTypeLabel(profile.exam_type);
  const subjectNames = ordered.map((subject) => subject.name);

  return {
    configured: profile.configured,
    examTypeLabel: typeLabel,
    examYear: profile.target_exam_year,
    headline: profile.target_exam_year ? `${profile.target_exam_year} ${typeLabel}` : typeLabel,
    directionLabel: track?.display_name ?? null,
    subjectNames,
    subjectLine: subjectNames.join(' · '),
    subjects: ordered,
    disclaimer: EXAM_PLAN_DISCLAIMER,
  };
}

/**
 * What a subject's study entry says, and where it goes.
 *
 * "继续学习" is a claim about the learner, so it is only made when a recorded fact supports it:
 * `resumeModuleKey` is the newest `exam_module_id` the record stream actually holds. Without one
 * the same destination is offered, named for what it is — entering the subject, not resuming
 * anything. The two never disagree about where they lead; they differ in what they claim.
 *
 * The destination carries the paper, not a guessed tool inside it. A record says which of the four
 * papers the learner worked in but not which tool they used — chapter practice and past papers both
 * record as `question_answered` — so choosing a tool on the learner's behalf would be an inference.
 * What is not an inference is where a paper BEGINS: every paper begins at its own knowledge
 * outline, which is a decision about 408 rather than a claim about this learner's last click. The
 * paper itself is the field the record carries, and that is what the destination names.
 */
export function subjectContinue(subject: ExamPlanSubject, resumeModuleKey?: string): ExamContinue | null {
  const surface = ACTIVE_SUBJECT_SURFACES[subject.id];
  if (!subject.entry || !surface) return null;

  const module = resumeModuleKey ? subject.modules.find((entry) => entry.key === resumeModuleKey) : undefined;
  return module
    ? { href: CS408_MODULE_ENTRY, search: { module: module.key }, label: `继续学习 · ${module.name}` }
    : { href: subject.entry, label: `进入 ${surface.shortName}` };
}

/* ---------------------------------------------------------------- configuration options */

export type ExamSubjectOption = {
  id: string;
  name: string;
  availability: ExamSubjectAvailability;
};

export type ExamPlanOptions = {
  politics: readonly ExamSubjectOption[];
  english: readonly ExamSubjectOption[];
  math: readonly ExamSubjectOption[];
  /** Catalogue subjects on the professional line, 408 among them. */
  professional: readonly ExamSubjectOption[];
};

const toOption = (subject: ExamCatalogSubject): ExamSubjectOption => ({
  id: subject.id,
  name: subject.display_name,
  availability: subject.availability,
});

/**
 * The four lines of the configuration screen, read off the catalogue.
 *
 * Grouped by the same slot rule the plan uses, so the screen and the plan can never disagree
 * about which line a subject belongs on.
 */
export function planOptions(catalog: ExamCatalog): ExamPlanOptions {
  const bySlot = (slot: ExamSlot) =>
    catalog.subjects.filter((subject) => examSlot(subject.id, subject.category) === slot).map(toOption);
  return {
    politics: bySlot('politics'),
    english: bySlot('english'),
    math: bySlot('math'),
    professional: bySlot('professional'),
  };
}

/**
 * 不考统考数学 is the ABSENCE of a maths paper, not a paper.
 *
 * It is an empty id on purpose. Giving it a subject id would put a subject into
 * `selected_subjects` that no exam contains, and every reader of that list — the plan, the
 * records, the availability gate — would have to special-case it.
 */
export const NO_UNIFIED_MATH = '';

/**
 * A starting combination for a direction, as a suggestion the learner edits and confirms.
 *
 * The catalogue is the authority here: for every direction it declares, `subject_options` is the
 * backend's own statement of what that direction holds, and it is used as-is. `cs_408` is the one
 * direction whose `subject_options` is deliberately narrow (the backend refuses to guess which
 * public courses a direction requires), so the one direction this build ships carries an explicit
 * starting combination instead. It is offered as a filled-in suggestion with the 招生专业目录
 * disclaimer beside it — never applied silently, and never presented as an exam rule.
 */
const RECOMMENDED_SUBJECT_PRESET: Readonly<Record<string, readonly string[]>> = {
  cs_408: ['politics', 'english_1', 'math_1', 'cs_408'],
};

export function recommendedSubjects(track: ExamTrack | undefined): readonly string[] {
  if (!track) return [];
  if (track.subject_options.length > 1) return track.subject_options;
  return RECOMMENDED_SUBJECT_PRESET[track.id] ?? [];
}

/** The maths paper the learner picked, or `undefined` when they take no unified maths. */
export function selectedMath(options: ExamPlanOptions, selected: readonly string[]): string | undefined {
  return options.math.find((option) => selected.includes(option.id))?.id;
}

/**
 * The professional line, split into the three things a learner has to tell apart.
 *
 * `primary` is the subject this build can actually study — taken from the same surface map that
 * answers "where does this open onto", so a subject can never be listed as studiable here and
 * have no page there. `national` is every other national standardized paper: real, selectable,
 * and honestly described as a framework with no content yet. The learner's own 自命题 subjects
 * are the third thing and are not catalogue entries at all, so they are not in this list.
 */
export function professionalGroups(options: ExamPlanOptions): {
  primary: readonly ExamSubjectOption[];
  national: readonly ExamSubjectOption[];
} {
  return {
    primary: options.professional.filter((option) => activeSubjectEntry(option.id) !== undefined),
    national: options.professional.filter((option) => activeSubjectEntry(option.id) === undefined),
  };
}

/**
 * Whether applying `next` would remove or replace something the learner already chose.
 *
 * Used to decide whether a recommendation has to be confirmed before it is applied: a suggestion
 * that only ADDS to an empty or untouched selection needs no warning, one that would drop a
 * subject the learner picked does.
 */
export function combinationReplacesSelection(
  current: readonly string[],
  next: readonly string[],
): boolean {
  const kept = new Set(next);
  return current.some((id) => !kept.has(id));
}
