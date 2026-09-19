import { Link } from '@tanstack/react-router';
import { Skeleton } from '@/components/ui/skeleton';
import { useCs408StudyPlans, useExamPlanEntitlement, type Cs408Plan } from '@/features/exam/api/cs408-study-plan';
import { ExamPageShell } from './exam-page-shell';
import './cs408-study-plan-workspace.css';

type PlanTask = Cs408Plan['tasks'][number];

const statusLabels = { not_started: '未开始', in_progress: '进行中', completed: '已完成' } as const;
const taskTypeLabels: Record<string, string> = { knowledge: '知识学习', chapter_practice: '章节练习', review: '复习' };

function actionFor(task: PlanTask) {
  if (task.action_target === 'knowledge_map') return { label: task.computed_status === 'in_progress' ? '继续学习' : '开始学习', to: '/exam/cs408/knowledge' as const, search: { module: task.subject_key } };
  if (task.action_target === 'practice_center') return { label: '去练习', to: '/exam/cs408/practice' as const, search: { module: task.subject_key, chapter: undefined, attempt: undefined } };
  return undefined;
}

function PlanTaskRow({ task, number }: { task: PlanTask; number: number }) {
  const action = actionFor(task);
  const type = taskTypeLabels[task.task_type];
  return <li className="study-plan__row">
    <span className="study-plan__number">{String(number).padStart(2, '0')}</span>
    <div className="study-plan__task">
      <strong>{task.subject_name}</strong>
      <h2>{task.title}</h2>
      {(type || task.knowledge_point_name) ? <p>{[type, task.knowledge_point_name].filter(Boolean).join(' · ')}</p> : null}
      <dl>
        <div><dt>状态</dt><dd className={`study-plan__status study-plan__status--${task.computed_status}`}>{statusLabels[task.computed_status]}</dd></div>
        {task.due_date ? <div><dt>计划日期</dt><dd>{task.due_date}</dd></div> : null}
      </dl>
    </div>
    <div className="study-plan__action">{action ? <Link to={action.to} search={action.search}>{action.label}</Link> : null}</div>
  </li>;
}

function LockedPlan({ requiredPlan }: { requiredPlan?: string }) {
  // The outer `.study-plan` region already claims `study-plan-title`. A second landmark
  // pointing at the same id makes the two indistinguishable (axe `landmark-unique`), so the
  // inner panel is a plain container inside that region rather than a second landmark.
  return <section className="study-plan__state">
    <h1 id="study-plan-title">学习计划</h1><h2>当前会员暂未开放学习计划</h2>
    {requiredPlan ? <p>升级当前备考方案后即可使用学习计划。</p> : <p>该功能将在符合当前会员权益时开放。</p>}
  </section>;
}

export function Cs408StudyPlanWorkspace() {
  const entitlement = useExamPlanEntitlement();
  const planFeature = entitlement.data?.features['learning_plan'];
  const allowed = planFeature?.allowed === true;
  const plans = useCs408StudyPlans(allowed);
  const allPlans = plans.flatMap((result) => result.data ? [result.data] : []);
  const tasks = allPlans.flatMap((plan) => plan.tasks);
  const loadingPlans = plans.some((result) => result.isPending);
  const failedPlan = plans.some((result) => result.isError);

  return <ExamPageShell activeItem="cs408"><section className="study-plan" aria-labelledby="study-plan-title">
    {entitlement.isPending ? <><header className="study-plan__header"><h1 id="study-plan-title">学习计划</h1><p>CS408 学习安排</p></header><div className="study-plan__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-40 w-full" /></div></> : null}
    {entitlement.isError ? <section className="study-plan__state"><h1 id="study-plan-title">学习计划</h1><h2>暂时无法确认学习计划权益</h2><p>请检查网络后重试。</p><button type="button" onClick={() => void entitlement.refetch()}>重试</button></section> : null}
    {!entitlement.isPending && !entitlement.isError && !allowed ? <LockedPlan requiredPlan={planFeature?.required_plan} /> : null}
    {allowed ? <><header className="study-plan__header"><p>CS408 / 学习计划簿</p><h1 id="study-plan-title">学习计划</h1><span>按实际学习记录更新任务状态</span></header>
      {loadingPlans ? <div className="study-plan__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /></div> : null}
      {failedPlan ? <section className="study-plan__state"><h2>学习计划暂时无法加载</h2><p>请检查网络后重试。</p><button type="button" onClick={() => plans.forEach((result) => void result.refetch())}>重试</button></section> : null}
      {!loadingPlans && !failedPlan && tasks.length === 0 ? <section className="study-plan__state"><h2>暂无学习计划</h2><p>完成实际学习后，相关任务状态会在这里更新。</p></section> : null}
      {!loadingPlans && !failedPlan && tasks.length > 0 ? <ol className="study-plan__ledger">{tasks.map((task, index) => <PlanTaskRow key={`${task.subject_key}:${task.id}`} task={task} number={index + 1} />)}</ol> : null}
    </> : null}
  </section></ExamPageShell>;
}
