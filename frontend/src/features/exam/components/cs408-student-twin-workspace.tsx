import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules, useCs408DashboardSummaries } from '@/features/exam/api/dashboard-summary';
import { useExamReviewSummary } from '@/features/exam/api/review-summary';
import { useScientificCapabilities, useStudentTwinPreview } from '@/features/exam/api/student-twin';
import { useWrongAnswers } from '@/features/exam/api/wrong-answers';
import { ExamPageShell } from './exam-page-shell';
import './cs408-student-twin-workspace.css';

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="student-twin__fact">
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>;
}

/**
 * The one line under the figures: what needs attention first, in the learner's own terms.
 *
 * It is derived from the SAME numbers shown above it, so it can never claim something the figures
 * do not say. Ordered by what the learner should do next, and it stops at the first thing that
 * applies — a status is not a list of everything that could be mentioned.
 */
export function statusSentence(facts: { due: number; wrong: number; today: number; learned: number }): string {
  if (facts.due > 0) return `有 ${facts.due} 项复习已经到期，建议先完成复习。`;
  if (facts.wrong > 0) return `当前有 ${facts.wrong} 道错题待处理。`;
  if (facts.today > 0) return `今天的计划里有 ${facts.today} 项任务。`;
  if (facts.learned > 0) return `已完成 ${facts.learned} 个知识点的学习，暂时没有到期的复习或待处理的错题。`;
  return '';
}

/**
 * 学习状态 — where the learner stands in this paper: four figures and one sentence.
 *
 * ONE QUESTION. The page exists to answer "我现在学到什么状态了？", so it shows the current facts
 * and what needs attention, and nothing else. It is not a report, not a history, not a model
 * explanation, and not a directory of its own features — 学习记录 and 学习报告 are already
 * destinations in the navigation, and repeating them here is what made the page read as a list of
 * links rather than a status. There is also no second, differently-worded copy of "there is no
 * data yet": the zero state says that once and stops.
 *
 * THE ENGINE DOES NOT DECIDE WHETHER THIS PAGE WORKS. Every figure, and the sentence under them,
 * come from records the product always holds, so the page reads the same however the state engine
 * answers. When it has nothing to replay the figures and the sentence are untouched — its only
 * contribution is the closing note, which is simply absent when it has nothing to say.
 */
export function Cs408StudentTwinWorkspace({ moduleKey }: { moduleKey?: string }) {
  // The summaries hook answers for the four papers in a fixed order, so it is indexed by that
  // order and the papers this view wants are selected AFTER — filtering the inputs first would
  // silently pair each paper with the next one's numbers.
  const summaries = useCs408DashboardSummaries();
  const summaryByKey = new Map(cs408Modules.map((module, index) => [module.key, summaries[index]]));
  const modules = moduleKey ? cs408Modules.filter((module) => module.key === moduleKey) : cs408Modules;
  const wrongAnswers = useWrongAnswers(moduleKey, 'active', 0);
  const review = useExamReviewSummary();

  const scientificCapabilities = useScientificCapabilities();
  const studentTwinVisible = scientificCapabilities.data?.components.some((component) => component.component === 'student_twin' && component.user_visible) ?? false;
  const preview = useStudentTwinPreview(moduleKey, studentTwinVisible);
  // The engine has no eligible facts to replay. That is a statement about this learner's record,
  // not about the page, so it removes one clause and nothing else.
  const replayed = preview.data?.metadata.mode === 'UNAVAILABLE' ? undefined : preview.data?.input_summary.event_count;

  const loaded = modules.flatMap((module) => {
    const result = summaryByKey.get(module.key);
    return result?.data ? [result.data] : [];
  });
  const loading = modules.some((module) => summaryByKey.get(module.key)?.isPending);
  const failed = modules.length > 0 && modules.every((module) => summaryByKey.get(module.key)?.isError);

  const totalPoints = loaded.reduce((sum, item) => sum + item.overview.total_knowledge_points, 0);
  const learnedPoints = loaded.reduce((sum, item) => sum + Math.round(item.overview.total_knowledge_points * item.overview.learned_percent / 100), 0);
  const todayCount = loaded.reduce((sum, item) => sum + item.today_plan.length, 0);
  const dueCount = review.data?.by_status?.due ?? 0;
  const wrongCount = wrongAnswers.data?.total ?? 0;

  const facts = { due: dueCount, wrong: wrongCount, today: todayCount, learned: learnedPoints };
  const started = learnedPoints > 0 || dueCount > 0 || wrongCount > 0 || todayCount > 0;

  return <ExamPageShell cs408Tab="state" moduleKey={moduleKey}><section className="student-twin" aria-labelledby="student-twin-title">
    <h1 id="student-twin-title" className="student-twin__title">学习状态</h1>

    {loading ? <div className="student-twin__loading"><Skeleton className="h-20 w-full" /></div> : null}
    {!loading && failed ? <p className="student-twin__note">暂时读不到学习状态，请稍后重试。</p> : null}

    {!loading && !failed ? <>
      <dl className="student-twin__facts">
        <Figure label="已学习">{learnedPoints}<span>/ {totalPoints}</span></Figure>
        <Figure label="待复习">{dueCount}</Figure>
        <Figure label="错题">{wrongCount}</Figure>
        <Figure label="今日计划">{todayCount}</Figure>
      </dl>

      {started ? (
        <section className="student-twin__status" aria-labelledby="student-twin-status-title">
          <h2 id="student-twin-status-title">当前状态</h2>
          <p>{statusSentence(facts)}</p>
          {replayed ? <p className="student-twin__caption">本次状态参考了你最近的 {replayed} 条作答记录。</p> : null}
        </section>
      ) : (
        <p className="student-twin__note">完成一次练习后，这里会更新你的学习状态。</p>
      )}
    </> : null}
  </section></ExamPageShell>;
}
