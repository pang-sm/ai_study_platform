import { Link } from '@tanstack/react-router';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useScientificCapabilities, useStudentTwinPreview } from '@/features/exam/api/student-twin';
import { ExamPageShell } from './exam-page-shell';
import './cs408-student-twin-workspace.css';

function ModuleSelector({ moduleKey }: { moduleKey?: string }) {
  return <nav className="student-twin__filters" aria-label="学习状态模块筛选"><span>模块</span><Link to="/exam/cs408/state" search={{ module: undefined }} aria-current={moduleKey ? undefined : 'page'}>全部</Link>{cs408Modules.map((module) => <Link key={module.key} to="/exam/cs408/state" search={{ module: module.key }} aria-current={moduleKey === module.key ? 'page' : undefined}>{module.name}</Link>)}</nav>;
}

/**
 * The state summary, in the product's own words.
 *
 * The runtime's state object is not a contract this frontend owns, so it is read through an
 * allow-list and not by listing what to hide: a key the runtime adds next is not shown until
 * someone decides what it means. Two of the runtime's current keys are deliberately never shown —
 * `user_id` is the learner's internal reference, and `global_ability` is an internal quantity of
 * the engine, which put in front of a learner reads as an ability score. The frozen semantics say
 * this component is a deterministic state replay that is not a mastery score and controls no
 * product decision, so a number like that must not appear.
 */
const STATE_FIELDS: ReadonlyArray<{ key: string; label: string; format?: (value: unknown) => string | undefined }> = [
  { key: 'events_seen', label: '本次计算使用的事件数' },
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
  if (fields.length === 0) return <p className="student-twin__empty">当前范围没有可展示的状态摘要。</p>;
  return <dl className="student-twin__state-fields">{fields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{field.text}</dd></div>)}</dl>;
}

export function Cs408StudentTwinWorkspace({ moduleKey }: { moduleKey?: string }) {
  const scientificCapabilities = useScientificCapabilities();
  const studentTwinVisible = scientificCapabilities.data?.components.some((component) => component.component === 'student_twin' && component.user_visible) ?? false;
  const preview = useStudentTwinPreview(moduleKey, studentTwinVisible);
  const data = preview.data;
  const unavailable = data?.metadata.mode === 'UNAVAILABLE';
  return <ExamPageShell activeItem="cs408" cs408Tab="state" moduleKey={moduleKey}><section className="student-twin" aria-labelledby="student-twin-title">
    <header className="student-twin__header"><p>CS408 / 实验</p><h1 id="student-twin-title">学习状态实验视图</h1><span>自研确定性学习状态引擎</span></header>
    <ModuleSelector moduleKey={moduleKey} />
    <div className="student-twin__technical"><dl><div><dt>数据来源</dt><dd>基于真实作答与学习事件</dd></div><div><dt>计算方式</dt><dd>自研确定性状态引擎</dd></div><div><dt>使用范围</dt><dd>实验性展示</dd></div></dl></div>
    <section className="student-twin__authority" aria-label="实验边界"><p>基于真实学习记录计算；仅用于实验性展示；不控制判分，不修改知识状态、错题或学习计划。</p></section>
    {scientificCapabilities.isPending ? <p className="student-twin__loading">正在确认实验视图…</p> : null}
    {scientificCapabilities.isError ? <section className="student-twin__unavailable"><h2>暂时无法确认学习状态实验是否可展示</h2><p>学习记录和 CS408 其他功能仍可使用。</p></section> : null}
    {!scientificCapabilities.isPending && !scientificCapabilities.isError && !studentTwinVisible ? <section className="student-twin__unavailable"><h2>学习状态实验暂时不可展示</h2><p>学习记录和 CS408 其他功能仍可使用。</p></section> : null}
    {studentTwinVisible && preview.isPending ? <p className="student-twin__loading">正在生成实验预览…</p> : null}
    {studentTwinVisible && preview.isError ? <section className="student-twin__unavailable"><h2>学习状态服务暂时不可用</h2><button type="button" onClick={() => void preview.refetch()}>重试</button></section> : null}
    {studentTwinVisible && data ? <>{unavailable ? <section className="student-twin__unavailable"><h2>学习状态服务暂时不可用</h2><p>学习记录和 CS408 其他功能仍可使用。</p></section> : <><section className="student-twin__evidence" aria-label="本次计算使用的事实依据"><p>本次计算使用的事实依据</p><strong>{data.input_summary.event_count} 条</strong><span>仅统计本次被后端接受用于计算的真实作答与学习事件。</span></section><section className="student-twin__output" aria-labelledby="student-twin-output-title"><h2 id="student-twin-output-title">当前学习状态摘要</h2><StateFields state={data.state} /></section></>}<Link className="student-twin__records-link" to="/exam/cs408/records" search={{ module: moduleKey }}>查看学习记录</Link><a className="student-twin__records-link" href={`/reports?space=exam_11408${moduleKey ? `&module=${encodeURIComponent(moduleKey)}` : ''}`}>查看学习报告</a></> : null}
  </section></ExamPageShell>;
}
