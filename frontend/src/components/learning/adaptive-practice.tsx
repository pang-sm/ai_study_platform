import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { LoadingState } from '@/components/page/loading-state';
import { FactList } from '@/components/page/fact-list';
import { StatusNote } from '@/components/ui/status-note';
import { useAdaptivePractice, type AdaptiveScope } from './p4-api';
import { normalizeLanguageSlug } from '@/features/programming/programming-language';

/**
 * The five reasons the backend ranks a candidate with — read off `learning/adaptive.py`
 * (`REASON_DUE_REVIEW` … `REASON_UNSEEN_TOPIC`). They are the short title; the sentence a learner
 * actually reads comes from the server's own `reasons` map, so the explanation cannot drift away
 * from the rule that produced it.
 */
const reasonLabels: Record<string, string> = {
  due_review: '到期复习',
  recent_wrong: '最近作答错误',
  needs_work: '多次错误 / 待改进',
  coverage_gap: '尚无学习状态记录',
  unseen_topic: '尚未练习',
};

function hrefFor(scope: AdaptiveScope, id: string, entryHref?: string) {
  if (scope.serviceKey === 'programming') {
    // The language is the page's CONTEXT in the programming space, not a path segment, so it
    // travels in the search — see `searchFor` below.
    return `/programming/practice/${encodeURIComponent(id)}`;
  }
  return entryHref;
}

/** The language a programming practice opens in, as the space's own search parameter. */
function searchFor(scope: AdaptiveScope): Record<string, unknown> {
  if (scope.serviceKey !== 'programming') return {};
  const language = normalizeLanguageSlug(scope.language);
  return language ? { language } : {};
}

/**
 * What separates one candidate from the next.
 *
 * Two candidates from the same knowledge point carry the same `label`, so a list that showed only
 * the label rendered six DIFFERENT questions as six identical rows — a learner reads that as a bug
 * or as padding, and neither is true. The type and the difficulty are the candidate's own fields
 * and they do differ, so they are what the row shows next to the knowledge point.
 */
const QUESTION_TYPE_LABELS: Record<string, string> = {
  choice: '选择题',
  big: '简答题',
};

function candidateDetail(candidate: {
  question_type?: string | null;
  difficulty?: string | null;
}): string | undefined {
  const type = candidate.question_type ? QUESTION_TYPE_LABELS[candidate.question_type] : undefined;
  const parts = [type, candidate.difficulty ?? undefined].filter(Boolean);
  return parts.length ? parts.join(' · ') : undefined;
}

/**
 * Practice the backend picked, with its reason attached.
 *
 * Every candidate names the rule that selected it, and the facts behind that rule are rendered as
 * the fields they are — the previous version joined raw field names into a sentence, which put
 * `last_attempt_at` in front of a learner.
 */
export function AdaptivePractice({ serviceKey, courseId, examModuleId, language, entryHref }: AdaptiveScope & { entryHref?: string }) {
  const scope = { serviceKey, courseId, examModuleId, language };
  const query = useAdaptivePractice(scope);

  if (query.isPending) {
    return (
      <section className="mt-8" aria-label="推荐练习">
        <LoadingState label="正在读取推荐练习…" />
      </section>
    );
  }

  if (query.isError) {
    return (
      <section className="mt-8" aria-label="推荐练习">
        <StatusNote tone="warning">推荐练习暂时无法加载。</StatusNote>
      </section>
    );
  }

  const candidates = query.data?.candidates ?? [];
  return (
    <section className="mt-10" aria-labelledby="adaptive-practice-title">
      <SectionHeading
        id="adaptive-practice-title"
        title="推荐练习"
        description="按你已记录的学习情况推荐；每一项都保留它被选中的原因。"
      />
      {candidates.length ? (
        <ol className="mt-5 space-y-5">
          {candidates.map((candidate, index) => {
            const href = hrefFor(scope, candidate.question_source_id, entryHref);
            const detail = candidateDetail(candidate);
            return (
              <li key={candidate.candidate_id} className="border-l-2 border-border-default pl-4">
                <p className="text-body font-medium text-text-primary">{candidate.label}</p>
                <p className="mt-1 text-metadata text-text-secondary">
                  第 {index + 1} / {candidates.length} 题
                  {candidate.knowledge_point_name ? ` · ${candidate.knowledge_point_name}` : ''}
                  {detail ? ` · ${detail}` : ''}
                </p>
                <details className="mt-2">
                  <summary className="text-body text-text-secondary">为什么推荐这一题</summary>
                  <p className="mt-2 text-body text-text-primary">
                    {reasonLabels[candidate.reason] ?? '推荐依据暂不可显示'}
                  </p>
                  <p className="mt-1 text-body text-text-secondary">
                    {query.data?.reasons?.[candidate.reason] ?? '这项暂时没有可显示的说明。'}
                  </p>
                  <FactList
                    className="mt-3"
                    columns={1}
                    value={candidate.facts}
                    allow={['attempts', 'factual_correct', 'factual_incorrect', 'active_wrong_count', 'last_attempt_at', 'difficulty', 'question_type']}
                  />
                </details>
                {href ? (
                  <Button asChild variant="secondary" className="mt-3">
                    <Link to={href as '/programming'} search={searchFor(scope) as never}>{serviceKey === 'programming' ? '打开练习' : '进入练习入口'}</Link>
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <EmptyState
          className="mt-5"
          title="现在还没有可以推荐的练习。"
          description="没有候选时不补造题目；完成一次练习或复习后，这里会重新给出建议。"
        />
      )}
    </section>
  );
}
