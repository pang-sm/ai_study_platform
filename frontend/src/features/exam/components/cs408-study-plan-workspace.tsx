import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import {
  useCreateCs408PlanTask, useCs408StudyPlans, useDeleteCs408PlanTask, useExamPlanEntitlement,
  useUpdateCs408PlanTask, type Cs408Plan,
} from '@/features/exam/api/cs408-study-plan';
import { tierLabel } from '@/features/membership/view-models/membership';
import { DynamicPlanSurface, InitialPlanDraftSurface, type InitialPlanDraftTask } from '@/features/learning-intelligence/learning-intelligence-surfaces';
import { useInitialPlanProposal } from '@/features/learning-intelligence/api';
import { ExamPageShell } from './exam-page-shell';
import './cs408-study-plan-workspace.css';

type PlanTask = Cs408Plan['tasks'][number];

const statusLabels = { not_started: '未开始', in_progress: '进行中', completed: '已完成' } as const;
const taskTypeLabels: Record<string, string> = { knowledge: '知识学习', chapter_practice: '章节练习', review: '复习' };
const TASK_TYPE_OPTIONS = Object.entries(taskTypeLabels);

/** The one identity a plan task keeps across every paper. */
const taskKey = (task: { subject_key: string; id: number }) => `${task.subject_key}:${task.id}`;

function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function tomorrowIso(): string {
  const next = new Date();
  next.setDate(next.getDate() + 1);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}

/**
 * `2026-10-03` → 今天 / 明天 / `10 月 3 日`.
 *
 * The plan is read by WHEN the work is, so the list is grouped the way a learner thinks about it
 * rather than numbered from the top. A day is named relatively only where that is unambiguous.
 */
function dayLabel(iso: string): string {
  if (!iso) return '未设定日期';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  if (iso === todayIso()) return '今天';
  if (iso === tomorrowIso()) return '明天';
  return `${Number(match[2])} 月 ${Number(match[3])} 日`;
}

/** The plan, ordered by day, each day keeping the server's own order within it. */
function byDay(tasks: PlanTask[]) {
  const days = new Map<string, PlanTask[]>();
  for (const task of tasks) {
    const key = task.due_date || '';
    const bucket = days.get(key);
    if (bucket) bucket.push(task); else days.set(key, [task]);
  }
  return [...days.entries()].sort(([left], [right]) => left.localeCompare(right));
}

/** A draft line the learner is authoring; `id` is absent until it has been saved once. */
type DraftTask = { subject_key: string; title: string; due_date: string; task_type: string };

function actionFor(task: PlanTask) {
  if (task.action_target === 'knowledge_map') return { label: task.computed_status === 'in_progress' ? '继续学习' : '开始学习', to: '/exam/cs408/knowledge' as const, search: { module: task.subject_key } };
  // No `concept`: `ExamStudyPlanTaskItem` carries `knowledge_point_name` (a DISPLAY string)
  // and no code, so the plan knows no canonical concept and must not invent one. The attempt
  // is module-scoped practice, and the concept slot stays NULL.
  if (task.action_target === 'practice_center') return { label: '去练习', to: '/exam/cs408/practice' as const, search: { module: task.subject_key, chapter: undefined, concept: undefined, attempt: undefined } };
  return undefined;
}

function PlanTaskRow({ task, editing, draft, onDraftTitle, onDraftDate, onToggleRemove, removed }: {
  task: PlanTask;
  editing: boolean;
  draft: { title: string; due_date: string };
  onDraftTitle: (value: string) => void;
  onDraftDate: (value: string) => void;
  onToggleRemove: () => void;
  removed: boolean;
}) {
  const action = actionFor(task);
  const type = taskTypeLabels[task.task_type];

  if (editing) {
    return <li className="study-plan__row" data-removed={removed ? 'true' : undefined}>
      <div className="study-plan__task">
        <label className="study-plan__field">
          <span>任务名称</span>
          <input type="text" value={draft.title} maxLength={120} disabled={removed}
                 onChange={(event) => onDraftTitle(event.target.value)} />
        </label>
        <label className="study-plan__field">
          <span>计划日期</span>
          <input type="date" value={draft.due_date} disabled={removed}
                 onChange={(event) => onDraftDate(event.target.value)} />
        </label>
      </div>
      <div className="study-plan__action">
        <Button variant="ghost" onClick={onToggleRemove}>{removed ? '撤销删除' : '删除任务'}</Button>
      </div>
    </li>;
  }

  return <li className="study-plan__row">
    <div className="study-plan__task">
      <h3>{task.title}</h3>
      {(type || task.knowledge_point_name) ? <p>{[type, task.knowledge_point_name].filter(Boolean).join(' · ')}</p> : null}
      <dl>
        <div><dt>状态</dt><dd className={`study-plan__status study-plan__status--${task.computed_status}`}>{statusLabels[task.computed_status]}</dd></div>
        {task.subject_name ? <div><dt>科目</dt><dd>{task.subject_name}</dd></div> : null}
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
    <h2>当前档位暂未开放学习计划</h2>
    <p>
      {requiredTier
        ? <>学习计划需要 {tierLabel(requiredTier)} 及以上档位，当前账号尚未开通。</>
        : <>该功能将在符合当前会员权益时开放。</>}
    </p>
    <Link to="/membership">查看会员档位与权益</Link>
  </section>;
}

/**
 * 学习计划 — the plan is the page, and the assistant is asked for by name.
 *
 * TWO STATES, because "no plan" and "a plan" are different questions and used to be handed the
 * same one. With nothing on the plan there is nothing to ADJUST, so the page offers the two
 * things that actually make a plan: add a task yourself, or have one drawn up. Adjusting appears
 * only once there is something to adjust, and even then the assistant's panel stays folded until
 * the learner opens it.
 *
 * THREE STORES that must never be confused:
 *
 *   CURRENT PLAN     what the server holds — the ledger, always read from the query
 *   DRAFT EDIT       the learner's own unsaved edits — applied only by 保存计划
 *   DRAFT / SUGGESTION  what the assistant proposed — applied only by 保存为我的计划 / 应用调整
 *
 * Keeping them apart is what makes each button mean exactly one thing.
 */
export function Cs408StudyPlanWorkspace({ moduleKey }: { moduleKey?: string } = {}) {
  const entitlement = useExamPlanEntitlement();
  // `features` is a mapping whose key set depends on the direction — index it only after a
  // presence check, because `data?.features[...]` still throws on a payload with no `features`.
  const planFeature = entitlement.data?.features?.['learning_plan'];
  const allowed = planFeature?.allowed === true;
  const plans = useCs408StudyPlans(allowed);
  const allPlans = plans.flatMap((result) => result.data ? [result.data] : []);
  const tasks = allPlans.flatMap((plan) => plan.tasks);
  const loadingPlans = plans.some((result) => result.isPending);
  const failedPlan = plans.some((result) => result.isError);

  const createTask = useCreateCs408PlanTask();
  const updateTask = useUpdateCs408PlanTask();
  const deleteTask = useDeleteCs408PlanTask();

  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { title: string; due_date: string }>>({});
  const [removed, setRemoved] = useState<Record<string, true>>({});
  const [added, setAdded] = useState<DraftTask[]>([]);

  // The assistant's two surfaces, each opened by the learner rather than laid out by default.
  const initialPlan = useInitialPlanProposal();
  const [drawingUp, setDrawingUp] = useState(false);
  const [initialGoal, setInitialGoal] = useState('');
  const [draftTasks, setDraftTasks] = useState<InitialPlanDraftTask[]>();
  const [adjusting, setAdjusting] = useState(false);

  const [chosenModule, setChosenModule] = useState<string>();
  const adjustModule = chosenModule ?? (moduleKey || undefined) ?? tasks[0]?.subject_key ?? cs408Modules[0].key;
  const moduleName = cs408Modules.find((module) => module.key === adjustModule)?.name;

  const emptyPlan = tasks.length === 0;
  const saving = createTask.isPending || updateTask.isPending || deleteTask.isPending;
  // Only tasks whose draft differs from the server's copy are sent, so 保存计划 writes the
  // learner's edits and nothing else.
  const changedTasks = tasks
    .map((task) => ({ task, draft: drafts[taskKey(task)] }))
    .filter((row): row is { task: PlanTask; draft: { title: string; due_date: string } } =>
      Boolean(row.draft) && (row.draft!.title.trim() !== row.task.title || row.draft!.due_date !== (row.task.due_date || '')));

  // A plan is a schedule, so a task without a day is not saveable — the server refuses it too.
  const incomplete = [
    ...changedTasks.filter((row) => !row.draft.due_date),
    ...added.filter((task) => !task.due_date),
  ];
  const emptyAdded = added.filter((task) => !task.title.trim());
  const saveBlockedReason = incomplete.length
    ? '请先为每个任务选择计划日期。'
    : emptyAdded.length
      ? '请先填写新任务的名称。'
      : null;

  const beginEdit = () => {
    setDrafts(Object.fromEntries(tasks.map((task) => [taskKey(task), { title: task.title, due_date: task.due_date || '' }])));
    setRemoved({});
    setAdded([]);
    setEditing(true);
  };

  const discardEdit = () => {
    setDrafts({});
    setRemoved({});
    setAdded([]);
    setEditing(false);
  };

  /** Add a line to the MANUAL draft. It authors; it does not write — 保存计划 does. */
  const addTaskRow = () => {
    if (!editing) beginEdit();
    setAdded((current) => [...current, { subject_key: adjustModule, title: '', due_date: todayIso(), task_type: 'knowledge' }]);
  };

  const save = async () => {
    const removals = Object.keys(removed).map((key) => {
      const task = tasks.find((item) => taskKey(item) === key)!;
      return deleteTask.mutateAsync({ subject_key: task.subject_key, task_id: task.id });
    });
    const updates = changedTasks
      .filter((row) => !removed[taskKey(row.task)])
      .map((row) => updateTask.mutateAsync({
        username: row.task.username, subject_key: row.task.subject_key, task_id: row.task.id,
        title: row.draft.title.trim(), due_date: row.draft.due_date,
      }));
    const creations = added.map((task) => createTask.mutateAsync({
      username: '', subject_key: task.subject_key, title: task.title.trim(),
      due_date: task.due_date, task_type: task.task_type, scope_type: 'all',
    }));
    const results = await Promise.allSettled([...removals, ...updates, ...creations]);
    if (results.some((result) => result.status === 'rejected')) return;
    setDrafts({});
    setRemoved({});
    setAdded([]);
    setEditing(false);
  };

  const generateInitialPlan = () => {
    initialPlan.mutate(
      { scope: { service_key: 'exam_11408', course_id: '', exam_module_id: adjustModule, language: '' }, goal: initialGoal },
      // A task the model could not date arrives with `due_date: null` and stays in the draft with
      // an empty day: it is the learner's to fill, not the client's to invent.
      { onSuccess: (proposal) => setDraftTasks((proposal.tasks ?? []).map((task) => ({
        title: task.title, task_type: task.task_type, due_date: task.due_date ?? '',
      }))) },
    );
  };

  /**
   * Write the DRAFT through the ordinary task endpoint — the same one a hand-typed task uses, so
   * the row that lands is validated by the same rules. Rows that did NOT land stay in the draft:
   * a retry must not write a second copy of the ones that did.
   */
  const saveDraft = async () => {
    const rows = draftTasks ?? [];
    const results = await Promise.allSettled(rows.map((task) => createTask.mutateAsync({
      username: '', subject_key: adjustModule, title: task.title.trim(),
      due_date: task.due_date, task_type: task.task_type, scope_type: 'all',
    })));
    const notSaved = rows.filter((_, index) => results[index]?.status === 'rejected');
    if (notSaved.length) {
      setDraftTasks(notSaved);
      return;
    }
    setDraftTasks(undefined);
    setDrawingUp(false);
    setInitialGoal('');
  };

  const closeInitialPlan = () => {
    setDraftTasks(undefined);
    setDrawingUp(false);
  };

  // The page carries no visible title: the 学习计划 tab above already names it, and a second
  // "学习计划" headline would spend the first screen restating the learner's own click. What
  // the body owes them is the plan itself — the tasks, their real status, and the day each
  // one is planned for.
  return <ExamPageShell cs408Tab="plan"><section className="study-plan" aria-labelledby="study-plan-title"><h1 id="study-plan-title" className="sr-only">学习计划</h1>
    {entitlement.isPending ? <div className="study-plan__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-40 w-full" /></div> : null}
    {entitlement.isError ? <section className="study-plan__state"><h2>暂时无法确认学习计划权益</h2><p>请检查网络后重试。</p><button type="button" onClick={() => void entitlement.refetch()}>重试</button></section> : null}
    {!entitlement.isPending && !entitlement.isError && !allowed ? <LockedPlan requiredTier={planFeature?.required_tier} /> : null}
    {allowed ? <>
      {loadingPlans ? <div className="study-plan__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /></div> : null}
      {failedPlan ? <section className="study-plan__state"><h2>学习计划暂时无法加载</h2><p>请检查网络后重试。</p><button type="button" onClick={() => plans.forEach((result) => void result.refetch())}>重试</button></section> : null}
      {!loadingPlans && !failedPlan ? <>
        <div className="study-plan__toolbar">
          <h2 className="study-plan__heading">当前计划</h2>
          {!editing && !drawingUp ? (
            <div className="study-plan__toolbar-actions">
              <Button variant="secondary" onClick={addTaskRow}>添加任务</Button>
              {emptyPlan
                ? <Button onClick={() => setDrawingUp(true)}>生成初始计划</Button>
                : <>
                  <Button variant="secondary" onClick={beginEdit}>编辑计划</Button>
                  <Button variant="secondary" onClick={() => setAdjusting((current) => !current)}>调整计划</Button>
                </>}
            </div>
          ) : editing ? (
            <div className="study-plan__toolbar-actions">
              <Button onClick={() => void save()} disabled={saving || saveBlockedReason !== null}>{saving ? '正在保存…' : '保存计划'}</Button>
              <Button variant="secondary" onClick={discardEdit} disabled={saving}>放弃修改</Button>
            </div>
          ) : null}
        </div>

        {saveBlockedReason && editing ? <StatusNote tone="danger" className="mt-3">{saveBlockedReason}</StatusNote> : null}
        {createTask.isError || updateTask.isError || deleteTask.isError ? (
          <StatusNote tone="danger" className="mt-3">保存失败，计划未改变。请检查网络后重试。</StatusNote>
        ) : null}

        {/* The plan, by the day it is planned for. */}
        {!editing && emptyPlan && !drawingUp ? (
          <section className="study-plan__state">
            <h3>暂无学习计划</h3>
            <p>可以自己添加任务，也可以生成一个初始计划。</p>
          </section>
        ) : null}
        {tasks.length > 0 && !editing ? <div className="study-plan__days">{byDay(tasks).map(([day, rows]) => (
          <section className="study-plan__day" key={day || 'undated'}>
            <h3 className="study-plan__day-label">{dayLabel(day)}</h3>
            <ol className="study-plan__ledger">{rows.map((task) => <PlanTaskRow
              key={taskKey(task)} task={task} editing={false}
              draft={{ title: task.title, due_date: task.due_date || '' }}
              removed={false} onDraftTitle={() => {}} onDraftDate={() => {}} onToggleRemove={() => {}}
            />)}</ol>
          </section>
        ))}</div> : null}
        {tasks.length > 0 && editing ? <ol className="study-plan__ledger">{tasks.map((task) => <PlanTaskRow
          key={taskKey(task)} task={task} editing
          draft={drafts[taskKey(task)] ?? { title: task.title, due_date: task.due_date || '' }}
          removed={Boolean(removed[taskKey(task)])}
          onDraftTitle={(value) => setDrafts((current) => ({ ...current, [taskKey(task)]: { ...(current[taskKey(task)] ?? { due_date: task.due_date || '' }), title: value } }))}
          onDraftDate={(value) => setDrafts((current) => ({ ...current, [taskKey(task)]: { ...(current[taskKey(task)] ?? { title: task.title }), due_date: value } }))}
          onToggleRemove={() => setRemoved((current) => {
            const next = { ...current };
            if (next[taskKey(task)]) delete next[taskKey(task)]; else next[taskKey(task)] = true;
            return next;
          })}
        />)}</ol> : null}

        {editing ? <section className="study-plan__add" aria-label="添加计划任务">
          <h3>添加任务</h3>
          {added.map((task, index) => <div className="study-plan__row" key={index}>
            <div className="study-plan__task">
              <label className="study-plan__field">
                <span>任务名称</span>
                <input type="text" value={task.title} maxLength={120} placeholder="例如：完成操作系统第 3 章复习"
                       onChange={(event) => setAdded((current) => current.map((item, at) => at === index ? { ...item, title: event.target.value } : item))} />
              </label>
              <label className="study-plan__field">
                <span>计划日期</span>
                <input type="date" value={task.due_date}
                       onChange={(event) => setAdded((current) => current.map((item, at) => at === index ? { ...item, due_date: event.target.value } : item))} />
              </label>
              <label className="study-plan__field">
                <span>科目</span>
                <select value={task.subject_key}
                        onChange={(event) => setAdded((current) => current.map((item, at) => at === index ? { ...item, subject_key: event.target.value } : item))}>
                  {cs408Modules.map((module) => <option key={module.key} value={module.key}>{module.name}</option>)}
                </select>
              </label>
              <label className="study-plan__field">
                <span>类型</span>
                <select value={task.task_type}
                        onChange={(event) => setAdded((current) => current.map((item, at) => at === index ? { ...item, task_type: event.target.value } : item))}>
                  {TASK_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
            </div>
            <div className="study-plan__action">
              <Button variant="ghost" onClick={() => setAdded((current) => current.filter((_, at) => at !== index))}>移除</Button>
            </div>
          </div>)}
          <Button variant="secondary" onClick={addTaskRow}>添加一条任务</Button>
        </section> : null}

        {/* Drawing up a first plan: only where there is no plan to adjust. */}
        {drawingUp ? <InitialPlanDraftSurface
          goal={initialGoal}
          onGoalChange={setInitialGoal}
          scopeLabel={moduleName}
          onGenerate={generateInitialPlan}
          generating={initialPlan.isPending}
          generateError={initialPlan.isError ? initialPlan.error : undefined}
          draft={draftTasks}
          onDraftTitle={(index, value) => setDraftTasks((current) => (current ?? []).map((task, at) => at === index ? { ...task, title: value } : task))}
          onDraftDate={(index, value) => setDraftTasks((current) => (current ?? []).map((task, at) => at === index ? { ...task, due_date: value } : task))}
          onRegenerate={generateInitialPlan}
          onCancel={closeInitialPlan}
          onSave={() => void saveDraft()}
          saving={createTask.isPending}
          saveError={createTask.isError}
        /> : null}

        {/* Adjusting: only where a plan exists, and only once the learner asks for it. */}
        {!emptyPlan ? <DynamicPlanSurface
          open={adjusting}
          onOpenChange={setAdjusting}
          scope={{ service_key: 'exam_11408', course_id: '', exam_module_id: adjustModule, language: '' }}
          scopeSelect={{
            label: '调整科目',
            value: adjustModule,
            options: cs408Modules.map((module) => ({ value: module.key, label: module.name })),
            onChange: setChosenModule,
          }}
        /> : null}
      </> : null}
    </> : null}
  </section></ExamPageShell>;
}
