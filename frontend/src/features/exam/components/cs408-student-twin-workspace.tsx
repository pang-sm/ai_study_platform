import { Link } from '@tanstack/react-router';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useStudentTwinPreview } from '@/features/exam/api/student-twin';
import { ExamPageShell } from './exam-page-shell';
import './cs408-student-twin-workspace.css';

function ModuleSelector({ moduleKey }: { moduleKey?: string }) {
  return <nav className="student-twin__filters" aria-label="学习状态模块筛选"><span>模块</span><Link to="/exam/cs408/state" search={{ module: undefined }} aria-current={moduleKey ? undefined : 'page'}>全部</Link>{cs408Modules.map((module) => <Link key={module.key} to="/exam/cs408/state" search={{ module: module.key }} aria-current={moduleKey === module.key ? 'page' : undefined}>{module.name}</Link>)}</nav>;
}

function StateFields({ state }: { state: Record<string, unknown> | null | undefined }) {
  if (!state || Object.keys(state).length === 0) return <p className="student-twin__empty">当前范围没有可展示的状态引擎输出。</p>;
  return <dl className="student-twin__state-fields">{Object.entries(state).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : JSON.stringify(value)}</dd></div>)}</dl>;
}

export function Cs408StudentTwinWorkspace({ moduleKey }: { moduleKey?: string }) {
  const preview = useStudentTwinPreview(moduleKey);
  const data = preview.data;
  const unavailable = data?.metadata.mode === 'UNAVAILABLE';
  return <ExamPageShell activeItem="cs408"><section className="student-twin" aria-labelledby="student-twin-title">
    <header className="student-twin__header"><p>CS408 / 实验</p><h1 id="student-twin-title">学习状态实验视图</h1><span>自研确定性学习状态引擎</span></header>
    <ModuleSelector moduleKey={moduleKey} />
    <div className="student-twin__technical"><dl><div><dt>数据来源</dt><dd>真实学习事件</dd></div><div><dt>计算方式</dt><dd>自研确定性状态引擎</dd></div><div><dt>运行位置</dt><dd>Scientific Runtime</dd></div><div><dt>产品权限</dt><dd>仅实验展示，不控制学习决策</dd></div></dl></div>
    {preview.isPending ? <p className="student-twin__loading">正在生成实验预览…</p> : null}
    {preview.isError ? <section className="student-twin__unavailable"><h2>学习状态服务暂时不可用</h2><button type="button" onClick={() => void preview.refetch()}>重试</button></section> : null}
    {data ? <><section className="student-twin__authority" aria-label="实验边界"><p>基于真实学习记录计算；为实验性状态视图；不直接修改知识状态，不影响判分、错题或学习计划。</p></section>
      {unavailable ? <section className="student-twin__unavailable"><h2>学习状态服务暂时不可用</h2><p>学习记录和 CS408 其他功能仍可使用。</p></section> : <section className="student-twin__output" aria-labelledby="student-twin-output-title"><h2 id="student-twin-output-title">状态引擎输出</h2><StateFields state={data.state} /></section>}
      {data.metadata.blockers?.length ? <section className="student-twin__blockers" aria-labelledby="student-twin-blockers-title"><h2 id="student-twin-blockers-title">技术状态</h2><ul>{data.metadata.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></section> : null}
    </> : null}
  </section></ExamPageShell>;
}
