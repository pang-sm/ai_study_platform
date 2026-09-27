import type { components } from '@/types/api';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useCs408LearningRecords } from '@/features/exam/api/learning-records';
import { ExamPageShell } from './exam-page-shell';
import './cs408-learning-records-workspace.css';

type LearningRecord = components['schemas']['RecordView'];

const eventCopy: globalThis.Record<string, { category: string; detail: (record: LearningRecord) => string }> = {
  knowledge_status_changed: { category: '知识学习', detail: () => '知识状态发生变化' },
  question_answered: { category: '章节练习', detail: (record) => record.summary?.correct === true ? '完成一次作答 · 回答正确' : record.summary?.correct === false ? '完成一次作答 · 回答错误' : '完成一次作答 · 未作答 / 未判定' },
  course_practice: { category: '章节练习', detail: (record) => record.summary?.correct === true ? '完成一次练习 · 回答正确' : record.summary?.correct === false ? '完成一次练习 · 回答错误' : '完成一次练习 · 未作答 / 未判定' },
  code_submitted: { category: '编程练习', detail: () => '提交了一次代码' },
  material_opened: { category: '资料学习', detail: () => '打开了一份资料' },
  material_asked: { category: '资料学习', detail: () => '发起了一次资料问答' },
};

function dateParts(timestamp: string | null | undefined) {
  if (!timestamp || !/(Z|[+-]\d\d:\d\d)$/.test(timestamp)) return { day: '时间未记录', time: '' };
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return { day: '时间未记录', time: '' };
  return {
    day: new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' }).format(date),
    time: new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date),
  };
}

function groupByBrowserDate(records: LearningRecord[]) {
  const groups: Array<{ day: string; records: LearningRecord[] }> = [];
  for (const record of records) {
    const day = dateParts(record.occurred_at).day;
    const latest = groups.at(-1);
    if (latest?.day === day) latest.records.push(record); else groups.push({ day, records: [record] });
  }
  return groups;
}

/**
 * The module is chosen in the workspace header above, not here.
 *
 * This page used to draw its own 全部 / 数据结构 / 计算机组成原理 / … row directly under a header
 * that already said which paper was open, so a learner met the same four choices twice on one
 * screen — once as a switcher and once as a filter that did the same thing.
 */
// A record points back at what produced it — but only along an identity the fact actually
// carries. `source.id` is the source attempt's own id and `context.exam_module_id` is the
// module it happened in, so both are asserted together: with either missing there is no
// link, rather than a link assembled from whatever else happens to be nearby.
function sourceHref(record: LearningRecord): { href: string; label: string } | undefined {
  const moduleKey = record.context?.exam_module_id;
  const sourceId = record.source?.id;
  if (!moduleKey || !sourceId) return undefined;
  if (record.source.type === 'exam_practice_attempt') return { href: `/exam/cs408/practice?module=${moduleKey}&attempt=${sourceId}`, label: '查看本次练习' };
  if (record.source.type === 'past_paper_attempt') return { href: `/exam/cs408/past-papers?module=${moduleKey}&attempt=${sourceId}`, label: '查看本次答卷' };
  return undefined;
}

function TimelineRow({ record }: { record: LearningRecord }) {
  const copy = eventCopy[record.event_type];
  if (!copy) return null;
  const timestamp = dateParts(record.occurred_at);
  const module = cs408Modules.find((item) => item.key === record.context?.exam_module_id)?.name;
  const source = sourceHref(record);
  return <li className="learning-records__row"><time dateTime={record.occurred_at ?? undefined}>{timestamp.time}</time><div>
    {module ? <p className="learning-records__module">{module}</p> : null}
    <strong>{copy.category}</strong><p>{copy.detail(record)}</p>
    {source ? <a className="learning-records__source" href={source.href}>{source.label}</a> : null}
  </div></li>;
}

export function Cs408LearningRecordsWorkspace({ moduleKey }: { moduleKey?: string }) {
  const records = useCs408LearningRecords(moduleKey);
  const flatRecords = records.data?.pages.flatMap((page) => page.records) ?? [];
  const groups = groupByBrowserDate(flatRecords);
  // 学习记录 is already named by the tab above, so the body opens on the records themselves.
  // A page name survives only as the region's accessible name.
  return <ExamPageShell cs408Tab="records" moduleKey={moduleKey}><section className="learning-records" aria-labelledby="learning-records-title">
    <h1 id="learning-records-title" className="sr-only">学习记录</h1>
    <a className="learning-records__source" href={`/reports?space=exam_11408${moduleKey ? `&module=${encodeURIComponent(moduleKey)}` : ''}`}>查看当前范围学习报告</a>
    {records.isPending ? <p className="learning-records__state">正在读取学习记录…</p> : null}
    {records.isError ? <section className="learning-records__state"><h2>学习记录暂时无法加载</h2><button type="button" onClick={() => void records.refetch()}>重试</button></section> : null}
    {!records.isPending && !records.isError && flatRecords.length === 0 ? <p className="learning-records__state">还没有学习记录</p> : null}
    {!records.isPending && !records.isError && groups.map((group) => <section className="learning-records__day" key={group.day} aria-label={group.day}><h2>{group.day}</h2><ol>{group.records.map((record) => <TimelineRow key={record.event_id} record={record} />)}</ol></section>)}
    {records.hasNextPage ? <div className="learning-records__more"><button type="button" onClick={() => void records.fetchNextPage()} disabled={records.isFetchingNextPage}>{records.isFetchingNextPage ? '正在加载…' : '加载更多'}</button></div> : null}
  </section></ExamPageShell>;
}
