import type { components } from '@/types/api';

/**
 * 考研数学 — the frontend's projection of the taxonomy the BACKEND owns.
 *
 * P3A kept the domain list in this file as a temporary placement; P3B moved it behind
 * `GET /exam/prep/math/taxonomy`, and this module is now a projection and nothing else. There is
 * exactly one statement of what maths is, and it is not here.
 *
 * THE ONE RULE
 * ------------
 * A domain exists once. The three papers (数学（一）/（二）/（三）) decide SCOPE over that one set
 * of domains; they never own content. So nothing in this file may take a paper id as an input to
 * anything but the scope question, and no id of the form `math_1_<topic>` can be produced here.
 * A learner switching 数学（一） → 数学（二） keeps their knowledge, their progress and their
 * records, because all three are addressed by canonical domain ids — which is also why this
 * module never merges or copies the two services' user state (see `COURSE_EXAM_ISOLATION`).
 */

export type MathTaxonomy = components['schemas']['MathTaxonomyResponse'];
export type MathDomainSummary = components['schemas']['MathDomainSummary'];
export type MathVariantSummary = components['schemas']['MathVariantSummary'];
export type MathCoverageEntry = components['schemas']['MathCoverageEntrySummary'];
export type MathCoverageSource = components['schemas']['MathCoverageSourceSummary'];

/** A national exam paper. A paper decides SCOPE; it never owns content. */
export type MathExamVariant = 'math_1' | 'math_2' | 'math_3';

/** A paper's id is a catalogue subject id of the form `math_N`. */
const MATH_SUBJECT_ID = /^math_([123])$/;

/**
 * Whether a catalogue subject is one of the maths papers, and which.
 *
 * A rule rather than a list of three, so it is derived from whatever the catalogue holds and the
 * frontend keeps no copy of the subject ids — the same reason `mathVariantOf` existed before the
 * taxonomy moved to the backend.
 */
export function mathVariantOf(subjectId: string): MathExamVariant | null {
  return MATH_SUBJECT_ID.test(subjectId) ? (subjectId as MathExamVariant) : null;
}

/* ---------------------------------------------------------------- capability */

export type MathDomainView = {
  key: string;
  name: string;
  /** `available` once the canonical knowledge map exists; `pending` until then. */
  knowledgeMapStatus: MathDomainSummary['status'];
  /** The source the domain's structure came from, as the backend records it. */
  source: string;
};

export type MathCoverageView = {
  status: MathTaxonomy['coverage_status'];
  note: string;
  /** Only the entries that belong to this paper. Empty while nothing is established. */
  entries: readonly MathCoverageEntry[];
  sources: readonly MathCoverageSource[];
};

export type MathCapability = {
  subjectId: string;
  variant: MathExamVariant;
  /** The subject's catalogue name, passed in — this module never renames a subject. */
  name: string;
  /**
   * Read from the backend's own gate, never asserted here. The gate needs BOTH a knowledge
   * structure and a verified exam range; while the range is unstated the subject stays
   * `framework`, which is why the maths cards offer no way in.
   */
  maturity: 'open' | 'framework';
  domains: readonly MathDomainView[];
  coverage: MathCoverageView;
  /** One honest sentence about the state, for a card that has no room for more. */
  note: string;
};

/**
 * The maths capability of one catalogue subject, or `null` for anything that is not a maths paper
 * — or when the taxonomy has not arrived, in which case this build cannot state anything about
 * maths and says nothing rather than guessing.
 *
 * All three papers go through this one function: there is no per-variant branch here and none may
 * be added, because a branch is exactly how three copies of one domain start. What differs
 * between the papers is `coverage.entries` — their range — and even that is empty until a
 * syllabus is imported.
 */
export function mathCapability(
  subject: { id: string; display_name: string },
  taxonomy: MathTaxonomy | undefined,
): MathCapability | null {
  const variant = mathVariantOf(subject.id);
  if (!variant || !taxonomy) return null;

  const domains: MathDomainView[] = [...taxonomy.domains]
    .sort((a, b) => a.order - b.order)
    .map((domain) => ({
      key: domain.key,
      name: domain.display_name,
      knowledgeMapStatus: domain.status,
      source: domain.source,
    }));

  const names = domains.map((domain) => domain.name).join('、');

  return {
    subjectId: subject.id,
    variant,
    name: subject.display_name,
    maturity: taxonomy.math_openable ? 'open' : 'framework',
    domains,
    coverage: {
      status: taxonomy.coverage_status,
      note: taxonomy.coverage_note,
      entries: taxonomy.coverage.filter((entry) => entry.variant === variant),
      sources: taxonomy.coverage_sources,
    },
    // The same two words every other framework subject uses — 科目框架已建立 / 学习内容尚未开放.
    // Maths must not describe its own state in a third vocabulary: the subject is a framework,
    // whatever internal structure exists behind it.
    note: taxonomy.math_openable
      ? `考研数学由${names}组成。`
      : `考研数学由${names}组成；学习内容尚未开放。`,
  };
}

/** The domains of a capability, as a plain name list — for a one-line rendering. */
export function mathDomainNames(capability: MathCapability): readonly string[] {
  return capability.domains.map((domain) => domain.name);
}

/**
 * Whether a coverage entry is settled, and how.
 *
 * `null` and `false` are different answers and a surface must not collapse them: `null` means
 * nobody has established whether the item is examined, `false` means an authoritative source says
 * it is not. Every entry the product holds today is `null`.
 */
export function coverageVerdict(entry: MathCoverageEntry): 'included' | 'excluded' | 'unstated' {
  if (entry.included === true) return 'included';
  if (entry.included === false) return 'excluded';
  return 'unstated';
}
