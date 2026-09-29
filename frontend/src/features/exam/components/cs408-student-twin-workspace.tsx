import { Link } from '@tanstack/react-router';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules, useCs408DashboardSummaries } from '@/features/exam/api/dashboard-summary';
import { useCs408LearningRecords } from '@/features/exam/api/learning-records';
import { useExamReviewSummary } from '@/features/exam/api/review-summary';
import { useWrongAnswers } from '@/features/exam/api/wrong-answers';
import { useScientificCapabilities, useStudentTwinPreview } from '@/features/exam/api/student-twin';
import { eventTypeLabel } from '@/features/records/event-labels';
import { ExamPageShell } from './exam-page-shell';
import './cs408-student-twin-workspace.css';

/**
 * The state summary, in the product's own words.
 *
 * The runtime's state object is not a contract this frontend owns, so it is read through an
 * allow-list and not by listing what to hide: a key the runtime adds next is not shown until
 * someone decides what it means. Two of the runtime's current keys are deliberately never shown —
 * `user_id` is the learner's internal reference, and `global_ability` is an internal quantity of
 * the engine, which put in front of a learner reads as an ability score.
 */
const STATE_FIELDS: ReadonlyArray<{ key: string; label: string; format?: (value: unknown) => string | undefined }> = [
  {
    key: 'concepts',
    label: '涉及知识点',
    // The refs are internal canonical identities; how many there are is the learner's fact.
    format: (value) => (Array.isArray(value) ? `${value.length} 个` : undefined),
  },
];

function StateFields({ state }: { state: Record<string, unknown> | null | undefined }) {
  const source = state ?? {};
  const fields = STATE_FIELDS.flatMap((field) => {
    const value = source[field.key];
    const text = field.format ? field.format(value) : typeof value === 'number' || typeof value === 'boolean' ? String(value) : undefined;
    return text === undefined ? [] : [{ key: field.key, label: field.label, text }];
  });
  if (fields.length === 0) return null;
  return <dl className="student-twin__state-fields">{fields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{field.text}</dd></div>)}</dl>;
}

/** `2026-09-29T07:37:57Z` → the day it happened. Anything else is shown as it came. */
function recordDay(value: unknown): string {
  if (typeof value !== 'string') return '';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[1]} 年 ${Number(match[2])} 月 ${Number(match[3])} 日` : value;
}

function Figure({ label, value, unit }: { label: string; value: number; unit?: string }) {
  return <div className="student-twin__fact">
    <dt>{label}</dt>
    <dd>{value}{unit ? <span>{unit}</span> : null}</dd>
  </div>;
}

/**
 * 学习状态 — what the learner's own records say about this paper.
 *
 * WHY THIS IS NOT THE ENGINE'S PAGE. It used to render one thing: the state engine's output. When
 * the engine had nothing eligible to replay it answered `UNAVAILABLE`, and the page printed
 * 学习状态服务暂时不可用 — an OUTAGE message for a learner who simply had not practised yet. The
 * page is therefore built on facts the product always holds (knowledge learned, time studied,
 * mistakes, review due, plan), and the engine is an ENHANCEMENT at the bottom that can fail or
 * be empty without taking any of that away.
 */
export function Cs408StudentTwinWorkspace({ moduleKey }: { moduleKey?: string }) {
  // The summaries hook answers for the four papers in a fixed order, so it is indexed by that
  // order and the papers this view wants are selected AFTER — filtering the inputs first would
  // silently pair each paper with the next one's numbers.
  const summaries = useCs408DashboardSummaries();
  const summaryByKey = new Map(cs408Modules.map((module, index) => [module.key, summaries[index]]));
  const modules = moduleKey ? cs408Modules.filter((module) => module.key === moduleKey) : cs408Modules;
  const records = useCs408LearningRecords(moduleKey);
  const wrongAnswers = useWrongAnswers(moduleKey, 'active', 0);
  const review = useExamReviewSummary();

  const scientificCapabilities = useScientificCapabilities();
  const studentTwinVisible = scientificCapabilities.data?.components.some((component) => component.component === 'student_twin' && component.user_visible) ?? false;
  const preview = useStudentTwinPreview(moduleKey, studentTwinVisible);
  const data = preview.data;
  // The engine has no eligible facts to replay. That is a statement about this learner's record,
  // not about the page, so it is shown as an empty state — not as a failure.
  const engineWaiting = data?.metadata.mode === 'UNAVAILABLE';

  const loaded = modules.flatMap((module) => {
    const result = summaryByKey.get(module.key);
    return result?.data ? [result.data] : [];
  });
  const loading = modules.some((module) => summaryByKey.get(module.key)?.isPending);
  const failed = modules.length > 0 && modules.every((module) => summaryByKey.get(module.key)?.isError);

  const totalPoints = loaded.reduce((sum, item) => sum + item.overview.total_knowledge_points, 0);
  const learnedPoints = loaded.reduce((sum, item) => sum + Math.round(item.overview.total_knowledge_points * item.overview.learned_percent / 100), 0);
  const studyMinutes = loaded.reduce((sum, item) => sum + item.overview.study_minutes, 0);
  const todayPlan = loaded.flatMap((item) => item.today_plan);
  const recent = (records.data?.pages.flatMap((page) => page.records) ?? []).slice(0, 3);
  const dueCount = review.data?.by_status?.due ?? 0;

  return <ExamPageShell cs408Tab="state" moduleKey={moduleKey}><section className="student-twin" aria-labelledby="student-twin-title">
    <h1 id="student-twin-title" className="sr-only">学习状态</h1>
    <section className="student-twin__authority" aria-label="使用范围说明"><p>基于你的真实学习记录计算。它不参与判分，也不会改写你的知识状态、错题或学习计划。</p></section>

    <section className="student-twin__overview" aria-labelledby="state-overview-title">
      <h2 id="state-overview-title">你的学习概况</h2>
      {loading ? <div className="student-twin__loading"><Skeleton className="h-24 w-full" /></div> : null}
      {failed ? <p className="student-twin__empty">暂时读不到学习记录。稍后重试，或先去看看学习记录页。</p> : null}
      {!loading && !failed ? <dl className="student-twin__facts">
        <Figure label="已学习知识点" value={learnedPoints} unit={`/ ${totalPoints} 个`} />
        <Figure label="学习时长" value={studyMinutes} unit="分钟" />
        <Figure label="待复习" value={dueCount} unit="项" />
        <Figure label="错题" value={wrongAnswers.data?.total ?? 0} unit="道" />
        <Figure label="今日计划" value={todayPlan.length} unit="项" />
      </dl> : null}
      {!loading && !failed && totalPoints > 0 && learnedPoints === 0 ? (
        <p className="student-twin__empty">还没有开始学习这个科目。选一个知识点开始，这里会记下进度。</p>
      ) : null}
    </section>

    <section className="student-twin__recent" aria-labelledby="state-recent-title">
      <h2 id="state-recent-title">最近学习</h2>
      {records.isPending ? <p className="student-twin__loading">正在读取学习记录…</p> : null}
      {records.isError ? <p className="student-twin__empty">暂时读不到最近的学习记录。</p> : null}
      {!records.isPending && !records.isError && recent.length === 0 ? <p className="student-twin__empty">还没有学习记录。</p> : null}
      {recent.length ? <ul className="student-twin__recent-list">
        {recent.map((record) => <li key={record.event_id}>
          <strong>{eventTypeLabel(record.event_type)}</strong>
          <span>{recordDay(record.occurred_at)}</span>
        </li>)}
      </ul> : null}
    </section>

    <section className="student-twin__output" aria-labelledby="student-twin-output-title">
      <h2 id="student-twin-output-title">学习状态摘要</h2>
      {!scientificCapabilities.isPending && !scientificCapabilities.isError && !studentTwinVisible ? (
        <p className="student-twin__empty">当前暂不展示这一部分。</p>
      ) : null}
      {studentTwinVisible && preview.isPending ? <p className="student-twin__loading">正在读取学习状态…</p> : null}
      {studentTwinVisible && data && !engineWaiting ? <>
        <section className="student-twin__evidence" aria-label="本次状态依据的学习记录">
          <p>本次状态依据的学习记录</p><strong>{data.input_summary.event_count} 条</strong>
          <span>只统计本次真正用到的作答与学习事件。</span>
        </section>
        <StateFields state={data.state} />
      </> : null}
      {/* Either the engine could not be reached, or it had nothing to replay. Both leave the
          learner's own figures above untouched — which is the whole point. */}
      {studentTwinVisible && engineWaiting ? (
        <p className="student-twin__empty">学习记录还不够。完成一次练习后，这里会根据你的作答更新。</p>
      ) : null}
      {studentTwinVisible && preview.isError ? (
        <p className="student-twin__empty">这一部分暂时读不到，上面的学习概况不受影响。</p>
      ) : null}
    </section>

    <Link className="student-twin__records-link" to="/exam/cs408/records" search={{ module: moduleKey }}>查看学习记录</Link>
    <a className="student-twin__records-link" href={`/reports?space=exam_11408${moduleKey ? `&module=${encodeURIComponent(moduleKey)}` : ''}`}>查看学习报告</a>
  </section></ExamPageShell>;
}
