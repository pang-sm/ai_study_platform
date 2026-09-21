import { Link } from '@tanstack/react-router';
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

function FilterNav({ moduleKey }: { moduleKey?: string }) {
  return <nav className="learning-records__filters" aria-label="学习记录模块筛选"><span>模块</span>
    <Link to="/exam/cs408/records" search={{ module: undefined }} aria-current={moduleKey ? undefined : 'page'}>全部</Link>
    {cs408Modules.map((module) => <Link key={module.key} to="/exam/cs408/records" search={{ module: module.key }} aria-current={moduleKey === module.key ? 'page' : undefined}>{module.name}</Link>)}
  </nav>;
}

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
  return <ExamPageShell activeItem="cs408" cs408Tab="records" moduleKey={moduleKey}><section className="learning-records" aria-labelledby="learning-records-title">
    <header className="learning-records__header"><p>CS408 / Learning Activity Ledger</p><h1 id="learning-records-title">学习记录档案</h1><span>按真实学习事件编排</span></header>
    <FilterNav moduleKey={moduleKey} /><a className="learning-records__source" href={`/reports?space=exam_11408${moduleKey ? `&module=${encodeURIComponent(moduleKey)}` : ''}`}>查看当前范围学习报告</a>
    {records.isPending ? <p className="learning-records__state">正在读取学习记录…</p> : null}
    {records.isError ? <section className="learning-records__state"><h2>学习记录暂时无法加载</h2><button type="button" onClick={() => void records.refetch()}>重试</button></section> : null}
    {!records.isPending && !records.isError && flatRecords.length === 0 ? <p className="learning-records__state">暂无学习记录</p> : null}
    {!records.isPending && !records.isError && groups.map((group) => <section className="learning-records__day" key={group.day} aria-label={group.day}><h2>{group.day}</h2><ol>{group.records.map((record) => <TimelineRow key={record.event_id} record={record} />)}</ol></section>)}
    {records.hasNextPage ? <div className="learning-records__more"><button type="button" onClick={() => void records.fetchNextPage()} disabled={records.isFetchingNextPage}>{records.isFetchingNextPage ? '正在加载…' : '加载更多'}</button></div> : null}
  </section></ExamPageShell>;
}
