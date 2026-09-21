import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { LoadingState } from '@/components/page/loading-state';
import { FactList } from '@/components/page/fact-list';
import { StatusNote } from '@/components/ui/status-note';
import { useAdaptivePractice, type AdaptiveScope } from './p4-api';

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
    return `/programming/${encodeURIComponent(scope.language ?? 'python')}/exercises/${encodeURIComponent(id)}`;
  }
  return entryHref;
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
        eyebrow="下一步练习"
        title="推荐练习"
        description="按已记录的学习事实推荐；每一项都保留它被选中的原因。"
      />
      {candidates.length ? (
        <ol className="mt-5 space-y-5">
          {candidates.map((candidate) => {
            const href = hrefFor(scope, candidate.question_source_id, entryHref);
            return (
              <li key={candidate.candidate_id} className="border-l-2 border-border-default pl-4">
                <p className="text-body font-medium text-text-primary">{candidate.label}</p>
                <p className="mt-1 text-metadata text-text-secondary">
                  {candidate.knowledge_point_name ?? candidate.question_type ?? candidate.source_type}
                </p>
                <details className="mt-2">
                  <summary className="text-body text-text-secondary">为什么推荐这一题</summary>
                  <p className="mt-2 text-body text-text-primary">
                    {reasonLabels[candidate.reason] ?? '后端给出的推荐原因'}
                  </p>
                  <p className="mt-1 text-body text-text-secondary">
                    {query.data?.reasons?.[candidate.reason] ?? '后端未提供该原因的说明。'}
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
                    <Link to={href as '/programming'}>{serviceKey === 'programming' ? '打开练习' : '进入练习入口'}</Link>
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <EmptyState
          className="mt-5"
          title="后端当前没有可展示的推荐练习。"
          description="没有候选时不补造题目；完成一次练习或复习后，这里会重新给出建议。"
        />
      )}
    </section>
  );
}
