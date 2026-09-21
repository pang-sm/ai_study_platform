import { Link } from '@tanstack/react-router';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules, useCs408DashboardSummaries, type ExamSubjectDashboardSummary } from '@/features/exam/api/dashboard-summary';
import { toCs408ModuleViewModel } from '@/features/exam/view-models/dashboard-summary';
import { ExamPageShell } from './exam-page-shell';

type DashboardResult = {
  isPending: boolean;
  isError: boolean;
  data?: ExamSubjectDashboardSummary;
  refetch: () => Promise<unknown>;
};

/**
 * The three tools of one module, as links.
 *
 * These used to be three inert `span`s inside a box labelled "module entries not yet open" — a
 * control-shaped thing that could not be used. The routes existed the whole time; naming them
 * with the module makes the overview a way into the exam instead of a status board.
 */
function ModuleActions({ moduleKey }: { moduleKey: string }) {
  return (
    <div className="cs408-module__actions">
      <Link to="/exam/cs408/knowledge" search={{ module: moduleKey }}>
        知识脉络
      </Link>
      <Link
        to="/exam/cs408/practice"
        search={{ module: moduleKey, chapter: undefined, concept: undefined, attempt: undefined }}
      >
        章节练习
      </Link>
      <Link
        to="/exam/cs408/past-papers"
        search={{ module: moduleKey, year: undefined, attempt: undefined, question: undefined }}
      >
        真题
      </Link>
    </div>
  );
}

function ModuleRow({ index, result }: { index: number; result: DashboardResult }) {
  const module = cs408Modules[index];
  if (!module || !result) return null;

  if (result.isPending) {
    return (
      <li className="cs408-module">
        <span className="cs408-module__number">{module.number}</span>
        <div>
          <h2>{module.name}</h2>
          <Skeleton className="mt-4 h-4 w-48" />
          <Skeleton className="mt-3 h-4 w-32" />
        </div>
      </li>
    );
  }

  if (result.isError || !result.data) {
    return (
      <li className="cs408-module cs408-module--error">
        <span className="cs408-module__number">{module.number}</span>
        <div>
          <h2>{module.name}</h2>
          <p>此模块暂时无法加载。</p>
          <button type="button" onClick={() => void result.refetch()} aria-label={`重试${module.name}模块`}>
            重试
          </button>
        </div>
      </li>
    );
  }

  const view = toCs408ModuleViewModel(result.data);
  return (
    <li className="cs408-module">
      <span className="cs408-module__number">{module.number}</span>
      <div className="cs408-module__body">
        <h2>{view.subjectName}</h2>
        {view.isNew ? (
          <p className="cs408-module__new">尚未开始学习</p>
        ) : (
          <>
            <p className="cs408-module__progress">知识点已学习比例 {view.learnedPercent}%</p>
            <p className="cs408-module__metadata">
              {view.totalChapters} 章 · {view.totalKnowledgePoints} 个知识点
              {view.studyMinutes > 0 ? ` · 已学习 ${view.studyMinutes} 分钟` : ''}
            </p>
          </>
        )}
        {view.tasks.length ? (
          <div className="cs408-module__tasks">
            <p>今日任务</p>
            <ul>
              {view.tasks.map((task) => (
                <li key={task.id}>
                  <strong>{task.title}</strong>
                  {task.knowledgePointName ? <span>{task.knowledgePointName}</span> : null}
                  <small>
                    {task.status}
                    {task.dueDate ? ` · ${task.dueDate}` : ''}
                  </small>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <ModuleActions moduleKey={module.key} />
      </div>
    </li>
  );
}

export function Cs408Workspace() {
  const summaries = useCs408DashboardSummaries();
  return (
    <ExamPageShell activeItem="cs408" cs408Tab="overview">
      <section className="cs408-workspace" aria-labelledby="cs408-title">
        <header className="cs408-workspace__identity">
          <p>CS408 · 计算机学科专业基础</p>
          <h1 id="cs408-title">学习工作区</h1>
          <span aria-hidden="true" />
        </header>
        <ol className="cs408-module-list">
          {cs408Modules.map((module, index) => (
            <ModuleRow key={module.key} index={index} result={summaries[index] as DashboardResult} />
          ))}
        </ol>
      </section>
    </ExamPageShell>
  );
}
