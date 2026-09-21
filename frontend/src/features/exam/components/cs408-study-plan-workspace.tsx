import { Link } from '@tanstack/react-router';
import { Skeleton } from '@/components/ui/skeleton';
import { useCs408StudyPlans, useExamPlanEntitlement, type Cs408Plan } from '@/features/exam/api/cs408-study-plan';
import { tierLabel } from '@/features/membership/view-models/membership';
import { ExamPageShell } from './exam-page-shell';
import './cs408-study-plan-workspace.css';
import { DynamicPlanSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';

type PlanTask = Cs408Plan['tasks'][number];

const statusLabels = { not_started: '未开始', in_progress: '进行中', completed: '已完成' } as const;
const taskTypeLabels: Record<string, string> = { knowledge: '知识学习', chapter_practice: '章节练习', review: '复习' };

function actionFor(task: PlanTask) {
  if (task.action_target === 'knowledge_map') return { label: task.computed_status === 'in_progress' ? '继续学习' : '开始学习', to: '/exam/cs408/knowledge' as const, search: { module: task.subject_key } };
  // No `concept`: `ExamStudyPlanTaskItem` carries `knowledge_point_name` (a DISPLAY string)
  // and no code, so the plan knows no canonical concept and must not invent one. The attempt
  // is module-scoped practice, and the concept slot stays NULL.
  if (task.action_target === 'practice_center') return { label: '去练习', to: '/exam/cs408/practice' as const, search: { module: task.subject_key, chapter: undefined, concept: undefined, attempt: undefined } };
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

function LockedPlan({ requiredTier }: { requiredTier?: string }) {
  // The outer `.study-plan` region already claims `study-plan-title`. A second landmark
  // pointing at the same id makes the two indistinguishable (axe `landmark-unique`), so the
  // inner panel is a plain container inside that region rather than a second landmark.
  //
  // ACCEL_PRODUCT_S9: the membership route EXISTS, so the locked state now points at it.
  // Before this, the page deliberately rendered no link because there was no canonical
  // destination — a lock with nowhere to go is a dead end, and inventing a route for it
  // would have been worse. The link goes to `/membership`, which reads the SAME entitlement
  // endpoint this panel does (`GET /membership/entitlements?service_key=exam_11408`), so the
  // requirement stated here and the requirement explained there cannot disagree.
  //
  // ACCEL_PRODUCT_S10: `requiredTier` is now a real UNIFIED TIER (`standard`), the same
  // vocabulary the membership page uses, so the lock names the exact thing the learner has
  // to change. It used to be a legacy plan code that had to be described in words because
  // showing it would have named no product tier.
  return <section className="study-plan__state">
    <h1 id="study-plan-title">学习计划</h1>
    <h2>当前档位暂未开放学习计划</h2>
    <p>
      {requiredTier
        ? <>学习计划需要 {tierLabel(requiredTier)} 及以上档位，当前账号尚未开通。</>
        : <>该功能将在符合当前会员权益时开放。</>}
    </p>
    <Link to="/membership">查看会员档位与权益</Link>
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

  return <ExamPageShell activeItem="cs408" cs408Tab="plan"><section className="study-plan" aria-labelledby="study-plan-title">
    {entitlement.isPending ? <><header className="study-plan__header"><h1 id="study-plan-title">学习计划</h1><p>CS408 学习安排</p></header><div className="study-plan__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-40 w-full" /></div></> : null}
    {entitlement.isError ? <section className="study-plan__state"><h1 id="study-plan-title">学习计划</h1><h2>暂时无法确认学习计划权益</h2><p>请检查网络后重试。</p><button type="button" onClick={() => void entitlement.refetch()}>重试</button></section> : null}
    {!entitlement.isPending && !entitlement.isError && !allowed ? <LockedPlan requiredTier={planFeature?.required_tier} /> : null}
    {allowed ? <><header className="study-plan__header"><p>CS408 / 学习计划簿</p><h1 id="study-plan-title">学习计划</h1><span>按实际学习记录更新任务状态</span></header>
      {loadingPlans ? <div className="study-plan__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /></div> : null}
      {failedPlan ? <section className="study-plan__state"><h2>学习计划暂时无法加载</h2><p>请检查网络后重试。</p><button type="button" onClick={() => plans.forEach((result) => void result.refetch())}>重试</button></section> : null}
      {!loadingPlans && !failedPlan && tasks.length === 0 ? <section className="study-plan__state"><h2>暂无学习计划</h2><p>完成实际学习后，相关任务状态会在这里更新。</p></section> : null}
      {!loadingPlans && !failedPlan && tasks.length > 0 ? <ol className="study-plan__ledger">{tasks.map((task, index) => <PlanTaskRow key={`${task.subject_key}:${task.id}`} task={task} number={index + 1} />)}</ol> : null}
      <DynamicPlanSurface scope={{ service_key: 'exam_11408', course_id: '', exam_module_id: '', language: '' }} />
    </> : null}
  </section></ExamPageShell>;
}
