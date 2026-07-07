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
    const stats = planData?.stats || {};
    const totalPoints = Number(stats.total_knowledge_points || planData?.summary?.knowledge_point_count || 0);
    const mastered = Number(stats.mastered || 0);
    const learning = Number(stats.learning || 0);
    const reviewDue = Number(stats.review_due || 0);
    const overallProgress = Number(stats.overall_progress || 0);
    const courseTasks = tasks.length
      ? tasks
      : chapters.slice(0, 5).map((chapter, index) => ({
          id: chapter.id || chapter.code || index,
          title: `学习 ${chapter.title || `第 ${index + 1} 章`}`,
          knowledge_point_name: chapter.title || courseName,
          computed_status: chapter.status === "completed" ? "completed" : chapter.status === "learning" ? "in_progress" : "not_started",
          completion_reason: `${chapter.leaf_stats?.mastered || 0} / ${chapter.leaf_stats?.total || 0} 个知识点已掌握`,
          note: "根据课程知识脉络推进本章学习。",
        }));

    return (
      <div className="exam-study-plan">
        <header className="exam-subject-header">
          <div>
            <div className="exam-subject-title-row">
              <span className="exam-subject-logo">{config.icon}</span>
              <div>
                <h1>{config.title}</h1>
                <p>学习计划 / 课程知识脉络联动任务</p>
              </div>
            </div>
          </div>
        </header>

        <section className="esp-stats-card">
          <div className="esp-stats-grid">
            <div className="esp-stat-item">
              <span className="esp-stat-label">总体进度</span>
              <strong className="esp-stat-value esp-stat-accent">{overallProgress}%</strong>
            </div>
            <div className="esp-stat-item">
              <span className="esp-stat-label">课程章节</span>
              <strong className="esp-stat-value">{chapters.length}</strong>
            </div>
            <div className="esp-stat-item">
              <span className="esp-stat-label">知识点</span>
              <strong className="esp-stat-value">{totalPoints}</strong>
            </div>
            <div className="esp-stat-item">
              <span className="esp-stat-label">已掌握</span>
              <strong className="esp-stat-value">{mastered}</strong>
            </div>
            <div className="esp-stat-item">
              <span className="esp-stat-label">学习中/待复盘</span>
              <strong className="esp-stat-value">{learning + reviewDue}</strong>
            </div>
          </div>
          <div className="esp-stats-bar-wrap">
            <div className="esp-stats-bar" style={{ width: `${Math.max(0, Math.min(100, overallProgress))}%` }} />
          </div>
        </section>

        <section className="esp-tasks-section">
          <div className="esp-tasks-header">
            <h2>今日学习任务</h2>
          </div>
          {courseTasks.length > 0 ? (
            <div className="esp-tasks-list">
              {courseTasks.map((task) => {
                const cs = task.computed_status || task.status || "not_started";
                return (
                  <div key={task.id || task.title} className={`esp-task-card ${cs}`}>
                    <div className="esp-task-main">
                      <div className="esp-task-info">
                        <strong className="esp-task-title">{task.title}</strong>
                        <div className="esp-task-meta">
                          <span className="esp-task-kp">📖 {task.knowledge_point_name || courseName}</span>
                          <span className={`esp-task-computed-status ${cs}`}>
                            {cs === "completed" ? "已完成" : cs === "in_progress" ? "进行中" : "未开始"}
                          </span>
                        </div>
                        {task.completion_reason && <p className="esp-task-reason">💡 {task.completion_reason}</p>}
                        {task.note && <p className="esp-task-note">{task.note}</p>}
                      </div>
                      <div className="esp-task-actions">
                        <button type="button" className="esp-task-goto-btn" onClick={() => onNavigate?.("knowledge")}>
                          前往知识脉络
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="esp-tasks-empty">
              <p>课程知识脉络尚未生成</p>
              <p>上传资料并生成课程知识脉络后，这里会自动按章节形成学习任务。</p>
            </div>
          )}
        </section>

        <section className="esp-tasks-section">
          <div className="esp-tasks-header">
            <h2>课程学习方向</h2>
          </div>
          <div className="esp-summary-row">
            <div className="esp-summary-chip done">
              <span>已掌握</span>
              <strong>{mastered}</strong>
            </div>
            <div className="esp-summary-chip learning">
              <span>学习中</span>
              <strong>{learning}</strong>
            </div>
            <div className="esp-summary-chip pending">
              <span>待学习</span>
              <strong>{Math.max(0, totalPoints - mastered - learning - reviewDue)}</strong>
            </div>
          </div>
          <div className="esp-chapters">
            {chapters.map((chapter, index) => {
              const stats = chapter.leaf_stats || {};
              const rate = Number(chapter.completion_rate || 0);
              const status = chapter.status || "not_started";
              return (
                <div key={chapter.id || chapter.code || index} className={`esp-chapter-card ${status}`}>
                  <div className="esp-chapter-header">
                    <div className="esp-chapter-title-row">
                      <span className="esp-chapter-code">{chapter.chapter_no || index + 1}</span>
                      <h3>{chapter.title}</h3>
                    </div>
                    <span className={`esp-chapter-badge ${status}`}>
                      {status === "completed" ? "已完成" : status === "learning" ? "进行中" : "未开始"}
                    </span>
                  </div>
                  <div className="esp-chapter-meta">
                    <span>{stats.mastered || 0} / {stats.total || 0} 个知识点已掌握</span>
                    <span>{rate}%</span>
                  </div>
                  <div className="esp-chapter-bar-wrap">
                    <div className="esp-chapter-bar" style={{ width: `${Math.max(0, Math.min(100, rate))}%` }} />
                  </div>
                </div>
              );
            })}
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
