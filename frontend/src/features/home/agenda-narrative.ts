/**
 * An agenda item, in the learner's words.
 *
 * The agenda payload is built for machines as well as people. Its `facts` object is assembled
 * from three different sources, so its shape varies with the kind of item, and the rule behind a
 * reason code is written for an engineer (`反复做错的错题状态（wrong_count >= 2）`). Neither
 * belongs on a home page. So nothing in this module prints a payload field name or a reason
 * code: the code SELECTS a sentence, and a fact becomes a sentence only where the product
 * actually recorded the fact behind it.
 *
 * Nothing here is predicted, scored or inferred. There is no mastery, no weakness estimate and
 * no confidence anywhere in this module, because the product holds no verified model output to
 * put in one — a sentence this file cannot build from a stored fact is not built at all.
 */
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { serviceNamespaceLabel } from '@/features/records/event-labels';
import type { components } from '@/types/api';

export type AgendaItem = components['schemas']['AgendaItemView'];
export type AgendaFacts = Record<string, unknown>;

/** The source types the agenda can attribute, as the backend spells them. */
const SOURCE_WRONG_ANSWER = 'wrong_answer';
const SOURCE_PROGRAMMING_EXERCISE = 'programming_exercise';

const MODULE_NAMES: Map<string, string> = new Map(
  cs408Modules.map((module) => [module.key as string, module.name as string]),
);

function numberOf(source: AgendaFacts | undefined, key: string): number | null {
  const value = source?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function textOf(source: Record<string, unknown> | undefined, key: string): string | null {
  const value = source?.[key];
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * What part of a direction this item belongs to, when a stored value names it in the product's
 * own vocabulary. A module key and a language are both real; a course id is a slug, so it is
 * resolved through the catalog the course space already loaded and left out when unknown —
 * printing `operating_system_11408` at a learner would be an internal identifier, not a place.
 */
export function contextLabel(
  item: AgendaItem,
  courseNames?: ReadonlyMap<string, string>,
): string | null {
  const context = item.domain_context;
  const language = textOf(context, 'language');
  if (language) return language;
  const module = textOf(context, 'exam_module_id');
  if (module) return MODULE_NAMES.get(module) ?? null;
  const course = textOf(context, 'course_id');
  if (course) return courseNames?.get(course) ?? null;
  return null;
}

/** The direction this item belongs to, with its part when one is known. */
export function scopeLine(item: AgendaItem, courseNames?: ReadonlyMap<string, string>): string {
  const space = serviceNamespaceLabel(item.service_namespace);
  const context = contextLabel(item, courseNames);
  return context ? `${space} · ${context}` : space;
}

/**
 * The action's destination, or nothing. A copy of the returned link is only followed when it is
 * a path this product serves — an absolute or protocol-relative value would navigate the learner
 * off the platform, so it is refused rather than rendered as a dead or foreign link.
 */
export function localDeepLink(deepLink: string): string | null {
  return deepLink.startsWith('/') && !deepLink.startsWith('//') ? deepLink : null;
}

/**
 * The one sentence that answers "why this, now" — built from the item's own facts, in the order
 * that gives the most specific true statement. The server's own `summary` is the last resort,
 * which is honest: it is real text about a real fact, and it beats inventing a sentence from a
 * fact this item does not carry.
 */
export function decisionSentence(item: AgendaItem): string | null {
  const facts = item.facts;
  const reason = item.priority_reason;
  const wrongCount = numberOf(facts, 'wrong_count') ?? numberOf(facts, 'active_wrong_count');

  if (wrongCount !== null && wrongCount >= 2) {
    return `这道内容已经做错 ${wrongCount} 次，建议优先完成订正。`;
  }

  // Programming work has its own two shapes, and neither is a wrong-answer state.
  if (item.source_type === SOURCE_PROGRAMMING_EXERCISE) {
    if (textOf(facts, 'personal_status') === 'needs_work') {
      return '这个练习被标记为需要加强，建议重新做一遍。';
    }
    const passed = numberOf(facts, 'passed_count');
    const total = numberOf(facts, 'total_count');
    if (passed !== null && total !== null && total > 0) {
      return `最近一次提交没有通过（${passed}/${total} 个用例通过），建议先修好。`;
    }
  }

  if (reason === 'due_review' || textOf(facts, 'knowledge_point_due_at')) {
    return '这个知识点的复习时间已经到了，建议先复习。';
  }

  if (reason === 'needs_work' && item.source_type === SOURCE_WRONG_ANSWER) {
    return '这道题还没有订正，建议先订正。';
  }

  if (facts?.overdue === true) {
    const due = textOf(facts, 'due_date');
    return due
      ? `这项计划任务已经过了截止日期（${due}），建议先处理。`
      : '这项计划任务已经过了截止日期，建议先处理。';
  }

  if (reason === 'adaptive_recommendation') {
    const incorrect = numberOf(facts, 'factual_incorrect');
    if (incorrect !== null && incorrect > 0) {
      return `最近一次作答是错的，这道题累计做错 ${incorrect} 次，建议重新练一遍。`;
    }
    return '这道练习和你已记录的作答有关，建议做一遍。';
  }

  if (reason === 'unseen_coverage') {
    return '这个知识点你还没有学习记录，建议先学一遍。';
  }

  if (reason === 'current_plan_task') {
    return '这是今天计划里还没完成的一项任务。';
  }

  const summary = item.summary?.trim();
  return summary ? summary : null;
}

/** The two short facts worth a badge. Anything the product has no word for gets no badge. */
export function decisionBadges(item: AgendaItem): string[] {
  const badges: string[] = [];
  const wrongCount = numberOf(item.facts, 'wrong_count')
    ?? numberOf(item.facts, 'active_wrong_count');
  if (wrongCount !== null && wrongCount >= 2) badges.push(`错 ${wrongCount} 次`);

  const status = item.status;
  if (status === 'overdue') badges.push('已逾期');
  else if (status === 'due') badges.push('已到期');
  else if (status === 'needs_attention') {
    badges.push(item.source_type === SOURCE_PROGRAMMING_EXERCISE ? '需要加强' : '未订正');
  }
  return badges.slice(0, 2);
}

/**
 * The line under a compact list row: the direction, plus whatever tells two same-named rows
 * apart. Two exercises can carry the same title in the same language — the backend keys them by
 * exercise, not by title — so when a rendered row would otherwise read identically to another,
 * the item's own reference is appended. It is the same reference the row links to.
 */
export function listRowDetail(
  item: AgendaItem,
  courseNames?: ReadonlyMap<string, string>,
): string | null {
  const detail = contextLabel(item, courseNames);
  const summary = item.summary?.trim();
  const parts = [detail, summary].filter((part): part is string => Boolean(part));
  return parts.length ? parts.join(' · ') : null;
}
