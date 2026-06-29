import { useEffect, useState, useCallback } from "react";
import ExamStudyPlanTaskModal from "./ExamStudyPlanTaskModal.jsx";
import { getExamSubjectConfig } from "./ExamSubjectDashboard.jsx";

export default function ExamStudyPlan({
  user,
  subjectKey,
  onNavigate,
  mode = "exam_11408",       // "exam_11408" | "course_learning"
  courseName = "",            // used in course_learning mode
  courseId = "",
}) {
  const isCourseMode = mode === "course_learning";
  const config = isCourseMode
    ? { title: courseName || "课程学习", icon: "CL", hero: "", subtitle: "", tags: [] }
    : getExamSubjectConfig(subjectKey);
  const username = user?.username || "";

  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);

  const fetchPlan = useCallback(async () => {
    if (!username) return;
    if (isCourseMode) {
      setLoading(true);
      setError("");
      try {
        const targetCourse = courseId || courseName || "course";
        const apiPath = `/api/course-learning/study-plan?username=${encodeURIComponent(username)}&course_id=${encodeURIComponent(targetCourse)}`;
        const res = await fetch(apiPath);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setPlanData(data);
      } catch (e) {
        setError(e.message || "加载课程学习计划失败");
      } finally {
        setLoading(false);
      }
      return;
    }
    setLoading(true);
    setError("");
    try {
      const apiPath = `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan?username=${encodeURIComponent(username)}`;
      const res = await fetch(apiPath);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPlanData(data);
    } catch (e) {
      setError(e.message || "加载学习计划失败");
    } finally {
      setLoading(false);
    }
  }, [username, subjectKey, isCourseMode, courseName, courseId]);

  useEffect(() => { fetchPlan(); }, [fetchPlan]);

  const deleteTask = async (taskId) => {
    if (!confirm("确定要删除这个任务吗？")) return;
    if (isCourseMode) {
      // course_learning: task API not yet implemented
      return;
    }
    try {
      const apiPath = `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/tasks/${taskId}?username=${encodeURIComponent(username)}`;
      await fetch(apiPath, { method: "DELETE" });
      await fetchPlan();
    } catch (e) {
      console.error("Failed to delete task:", e);
    }
  };

  if (loading) {
    return (
      <div className="esp-loading">
        <div className="esp-loading-spinner" />
        <p>加载学习计划中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="esp-error">
        <p>⚠️ {error}</p>
        <button type="button" onClick={fetchPlan}>重试</button>
      </div>
    );
  }

  const chapters = planData?.chapters || [];
  const tasks = planData?.tasks || [];

  if (isCourseMode) {
    return (
      <div className="exam-study-plan">

        <section className="esp-tasks-section">
          <div className="esp-tasks-header">
            <h2>今日学习任务</h2>
          </div>
          <div className="esp-tasks-empty">
            <p>暂无学习计划</p>
            <p>当前课程还没有计划任务。后续可基于资料学习、章节复习和课程练习生成课程学习计划。</p>
          </div>
        </section>

        <section className="esp-tasks-section">
          <div className="esp-tasks-header">
            <h2>课程学习方向</h2>
          </div>
          <div className="esp-tasks-empty">
            <p>资料学习、章节复习、课程练习暂无待办。</p>
          </div>
        </section>
      </div>
    );
  }

  const TASK_TYPE_LABELS = {
    knowledge: "知识点学习",
    chapter_practice: "章节练习",
    review: "阶段复习",
  };
  const STATUS_LABELS = {
    completed: "已完成",
    in_progress: "进行中",
    not_started: "未开始",
  };

  return (
    <div className="exam-study-plan">
      <header className="exam-subject-header">
        <div>
          <div className="exam-subject-title-row">
            <span className="exam-subject-logo">{config.icon}</span>
            <div>
              <h1>{config.title}</h1>
              <p>学习计划 / 知识点联动任务</p>
            </div>
          </div>
        </div>
      </header>

      {/* Stage Tasks Section */}
      <section className="esp-tasks-section">
        <div className="esp-tasks-header">
          <h2>📋 阶段学习任务</h2>
          <button type="button" className="esp-add-task-btn"
            onClick={() => { setEditingTask(null); setTaskModalOpen(true); }}>
            + 新建任务
          </button>
        </div>

        {tasks.length === 0 ? (
          <div className="esp-tasks-empty">
            <p>还没有阶段学习任务</p>
            <button type="button"
              onClick={() => { setEditingTask(null); setTaskModalOpen(true); }}>
              创建第一个任务
            </button>
          </div>
        ) : (
          <div className="esp-tasks-list">
            {tasks.map((task) => {
              const cs = task.computed_status || task.status || "not_started";
              const isChapterPractice = task.task_type === "chapter_practice";
              const actionLabel = isChapterPractice ? "前往练习中心" : "前往知识脉络";
              const actionTarget = isChapterPractice ? "practice" : "knowledge";
              return (
                <div key={task.id} className={`esp-task-card ${cs}`}>
                  <div className="esp-task-main">
                    <div className="esp-task-info">
                      <strong className="esp-task-title">{task.title}</strong>
                      <div className="esp-task-meta">
                        <span className="esp-task-kp">
                          {task.scope_type === "all" ? "📚 全部范围" : `📖 ${task.knowledge_point_name || task.secondary_knowledge || "未指定"}`}
                        </span>
                        <span className={`esp-task-type-tag ${task.task_type}`}>
                          {TASK_TYPE_LABELS[task.task_type] || task.task_type}
                        </span>
                        <span className={`esp-task-computed-status ${cs}`}>
                          {STATUS_LABELS[cs] || cs}
                        </span>
                      </div>
                      {task.completion_reason && (
                        <p className="esp-task-reason">💡 {task.completion_reason}</p>
                      )}
                      {task.due_date && (
                        <span className="esp-task-due">📅 计划完成：{task.due_date}</span>
                      )}
                      {task.note && <p className="esp-task-note">{task.note}</p>}
                    </div>
                    <div className="esp-task-actions">
                      <button type="button" className="esp-task-goto-btn"
                        onClick={() => onNavigate?.(actionTarget)}>
                        {actionLabel}
                      </button>
                      <button type="button" className="esp-task-edit-btn"
                        onClick={() => { setEditingTask(task); setTaskModalOpen(true); }}>
                        编辑
                      </button>
                      <button type="button" className="esp-task-del-btn"
                        onClick={() => deleteTask(task.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {taskModalOpen && (
        <ExamStudyPlanTaskModal user={user} subjectKey={subjectKey}
          chapters={chapters} editTask={editingTask}
          mode={mode} courseName={courseName}
          onSaved={() => { setTaskModalOpen(false); setEditingTask(null); fetchPlan(); }}
          onClose={() => { setTaskModalOpen(false); setEditingTask(null); }} />
      )}
    </div>
  );
}
