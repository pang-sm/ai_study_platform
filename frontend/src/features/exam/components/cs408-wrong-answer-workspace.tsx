import { useState } from 'react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useWrongAnswers, type WrongAnswerStatusFilter } from '@/features/exam/api/wrong-answers';
import { ExamPageShell } from './exam-page-shell';
import './cs408-wrong-answer-workspace.css';
import './cs408-wrong-answer-workspace.a11y.css';

type Record = components['schemas']['WrongAnswerRecord'];
const statuses: ReadonlyArray<{ value: WrongAnswerStatusFilter; label: string }> = [{ value: 'active', label: '未订正' }, { value: 'resolved', label: '已订正' }, { value: 'all', label: '全部' }];
const sourceLabel = (record: Record) => record.source_kind === 'chapter_practice' ? '章节练习' : record.source_kind === 'past_paper' ? '历年真题' : record.source_label;
const statusLabel = (record: Record) => record.status === 'active' ? '未订正' : '已订正';
const emptyCopy = (status: WrongAnswerStatusFilter) => status === 'active' ? '当前没有未订正错题' : status === 'resolved' ? '暂无已订正记录' : '暂时没有错题';

export function Cs408WrongAnswerWorkspace({ moduleKey, status = 'all', page = 0 }: { moduleKey?: string; status?: WrongAnswerStatusFilter; page?: number }) {
  const query = useWrongAnswers(moduleKey, status, page); const [expanded, setExpanded] = useState<number>();
  const totalPages = query.data ? Math.ceil(query.data.total / query.data.limit) : 0;
  return <ExamPageShell activeItem="cs408"><section className="wrong-answer" aria-labelledby="wrong-answer-title"><header className="wrong-answer__header"><p>CS408 / 错题</p><h1 id="wrong-answer-title">错题档案</h1><span>学习中的事实错题记录</span></header>
    <nav className="wrong-answer__filters" aria-label="错题筛选"><div><span>模块</span><FilterLink label="全部" href={href(undefined, status, 0)} active={!moduleKey} />{cs408Modules.map((module) => <FilterLink key={module.key} label={module.name} href={href(module.key, status, 0)} active={moduleKey === module.key} />)}</div><div><span>状态</span>{statuses.map((item) => <FilterLink key={item.value} label={item.label} href={href(moduleKey, item.value, 0)} active={status === item.value} />)}</div></nav>
    {query.isPending ? <div className="wrong-answer__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-32 w-full" /></div> : null}
    {query.isError ? <section className="wrong-answer__state"><h2>错题档案暂时无法加载</h2><Button variant="secondary" onClick={() => void query.refetch()}>重试</Button></section> : null}
    {query.data ? <><p className="wrong-answer__total">共 {query.data.total} 条错题记录</p>{query.data.items.length ? <ol className="wrong-answer__ledger">{query.data.items.map((record, index) => <LedgerRow key={record.wrong_record_id} record={record} number={query.data!.offset + index + 1} expanded={expanded === record.wrong_record_id} onToggle={() => setExpanded((current) => current === record.wrong_record_id ? undefined : record.wrong_record_id)} />)}</ol> : <section className="wrong-answer__state"><h2>{emptyCopy(status)}</h2></section>}{totalPages > 1 ? <nav className="wrong-answer__pager" aria-label="错题分页"><a aria-disabled={page === 0} href={href(moduleKey, status, Math.max(0, page - 1))}>上一页</a><span>第 {page + 1} / {totalPages} 页</span><a aria-disabled={page + 1 >= totalPages} href={href(moduleKey, status, Math.min(totalPages - 1, page + 1))}>下一页</a></nav> : null}</> : null}
  </section></ExamPageShell>;
}

function FilterLink({ label, href, active }: { label: string; href: string; active: boolean }) { return <a href={href} aria-current={active ? 'page' : undefined}>{label}</a>; }
function href(moduleKey: string | undefined, status: WrongAnswerStatusFilter, page: number) { const params = new URLSearchParams(); if (moduleKey) params.set('module', moduleKey); if (status !== 'all') params.set('status', status); if (page) params.set('page', String(page + 1)); const suffix = params.toString(); return `/exam/cs408/wrong${suffix ? `?${suffix}` : ''}`; }

function LedgerRow({ record, number, expanded, onToggle }: { record: Record; number: number; expanded: boolean; onToggle: () => void }) {
  const chapterContext = record.knowledge_point_path ?? record.knowledge_point_name;
  const context = record.source_kind === 'past_paper' ? `${sourceLabel(record)} · ${record.year ?? ''} · 第 ${record.question_number ?? ''} 题` : chapterContext ? `${sourceLabel(record)} · ${chapterContext}` : sourceLabel(record);
  return <li className={`wrong-answer__row wrong-answer__row--${record.status}`}><button type="button" className="wrong-answer__summary" aria-expanded={expanded} aria-label={`${expanded ? '收起' : '展开'}第 ${number} 条错题记录`} onClick={onToggle}><span className="wrong-answer__number">{String(number).padStart(2, '0')}</span><span className="wrong-answer__identity"><strong>{record.module_name}</strong><small>{context}</small></span><span className="wrong-answer__status">{statusLabel(record)}</span><i aria-hidden="true">{expanded ? '−' : '+'}</i></button><p className="wrong-answer__stem">{record.stem}</p><div className="wrong-answer__answers"><span>你的答案：{record.user_answer || '未作答'}</span><span>正确答案：{record.reference_answer}</span></div>{record.repeat_wrong_count > 1 ? <small className="wrong-answer__repeat">重复答错 {record.repeat_wrong_count} 次</small> : null}{expanded ? <RecordDetail record={record} /> : null}</li>;
}

function RecordDetail({ record }: { record: Record }) { return <section className="wrong-answer__detail" aria-label="错题详情"><h2>{record.stem}</h2>{Object.entries(record.options ?? {}).length ? <ol>{Object.entries(record.options ?? {}).map(([key, value]) => <li key={key}><b>{key}</b>{value}</li>)}</ol> : null}{record.resources?.map((resource, index) => <img key={resource.url} src={resolveApiResourceUrl(resource.url)} alt={`错题图示 ${index + 1}`} onError={(event) => { event.currentTarget.hidden = true; }} />)}{record.analysis?.trim() ? <section><h3>题目解析</h3><p>{record.analysis}</p></section> : null}{record.source_kind === 'past_paper' && record.year !== null ? <a href={`/exam/cs408/past-papers?module=${record.module_key}&year=${record.year}`}>查看原真题</a> : null}</section>; }
