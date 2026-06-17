import { useEffect, useState, useCallback } from "react";
import ExamStudyPlanTaskModal from "./ExamStudyPlanTaskModal.jsx";
import { getExamSubjectConfig } from "./ExamSubjectDashboard.jsx";

export default function ExamStudyPlan({ user, subjectKey, onNavigate }) {
  const config = getExamSubjectConfig(subjectKey);
  const username = user?.username || "";

  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [expandedSections, setExpandedSections] = useState({});
  const [savingCode, setSavingCode] = useState(null);

  const fetchPlan = useCallback(async () => {
    if (!username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan?username=${encodeURIComponent(username)}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPlanData(data);
    } catch (e) {
      setError(e.message || "加载学习计划失败");
    } finally {
      setLoading(false);
    }
  }, [username, subjectKey]);

  useEffect(() => { fetchPlan(); }, [fetchPlan]);

  const toggleSection = (sectionCode) => {
    setExpandedSections((prev) => ({ ...prev, [sectionCode]: !prev[sectionCode] }));
  };

  const updateKnowledgeItem = async (itemCode, itemTitle, newStatus) => {
    setSavingCode(itemCode);
    try {
      await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/knowledge-items/${encodeURIComponent(itemCode)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username, subject_key: subjectKey,
            course_id: `${subjectKey}_11408`,
            knowledge_point_code: itemCode,
            knowledge_point_title: itemTitle, status: newStatus,
          }),
        }
      );
      await fetchPlan();
    } catch (e) {
      console.error("Failed to update knowledge item:", e);
    } finally {
      setSavingCode(null);
    }
  };

  const toggleChapterPractice = async (sectionCode, sectionTitle, currentCompleted) => {
    setSavingCode(`cp:${sectionCode}`);
    try {
      await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/chapter-practice/${encodeURIComponent(sectionCode)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username, subject_key: subjectKey, section_code: sectionCode,
            section_title: sectionTitle, completed: !currentCompleted,
          }),
        }
      );
      await fetchPlan();
    } catch (e) {
      console.error("Failed to update chapter practice:", e);
    } finally {
      setSavingCode(null);
    }
  };

  const deleteTask = async (taskId) => {
    if (!confirm("确定要删除这个任务吗？")) return;
    try {
      await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/tasks/${taskId}?username=${encodeURIComponent(username)}`,
        { method: "DELETE" }
      );
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

  const stats = planData?.stats || {};
  const chapters = planData?.chapters || [];
  const tasks = planData?.tasks || [];

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

      {/* ── Stage Tasks Section ── */}
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
                        <p className="esp-task-reason">
                          💡 {task.completion_reason}
                        </p>
                      )}
                      {task.due_date && (
                        <span className="esp-task-due">📅 计划完成：{task.due_date}</span>
                      )}
                      {task.note && <p className="esp-task-note">{task.note}</p>}
                    </div>
                    <div className="esp-task-actions">
                      {task.action_target === "practice_center" && (
                        <button type="button" className="esp-task-goto-btn"
                          onClick={() => onNavigate?.("practice")}>
                          前往练习中心
                        </button>
                      )}
                      {task.action_target === "knowledge_map" && (
                        <button type="button" className="esp-task-goto-btn"
                          onClick={() => onNavigate?.("knowledge")}>
                          前往知识脉络
                        </button>
                      )}
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

      {/* Summary chips */}
      <section className="esp-summary-row">
        <div className="esp-summary-chip"><span>二级知识点</span><strong>{stats.total_sections || 0}</strong></div>
        <div className="esp-summary-chip done"><span>已完成</span><strong>{stats.sections_completed || 0}</strong></div>
        <div className="esp-summary-chip learning"><span>学习中</span><strong>{stats.sections_learning || 0}</strong></div>
        <div className="esp-summary-chip pending"><span>未开始</span><strong>{stats.sections_not_started || 0}</strong></div>
      </section>

      {/* Knowledge Point Board */}
      <section className="esp-chapters">
        <h2 className="esp-board-title">📚 知识点推进看板</h2>
        {chapters.length === 0 ? (
          <div className="esp-empty">
            <p>该学科知识脉络数据尚未加载。</p>
            <button type="button" onClick={() => onNavigate?.("knowledge")}>前往知识脉络</button>
          </div>
        ) : (
          chapters.map((chapter) => (
            <ChapterCard key={chapter.code || chapter.title} chapter={chapter}
              expandedSections={expandedSections} onToggleSection={toggleSection}
              onUpdateKnowledgeItem={updateKnowledgeItem}
              onToggleChapterPractice={toggleChapterPractice}
              savingCode={savingCode} />
          ))
        )}
      </section>

      {taskModalOpen && (
        <ExamStudyPlanTaskModal user={user} subjectKey={subjectKey}
          chapters={chapters} editTask={editingTask}
          onSaved={() => { setTaskModalOpen(false); setEditingTask(null); fetchPlan(); }}
          onClose={() => { setTaskModalOpen(false); setEditingTask(null); }} />
      )}
    </div>
  );
}

function ChapterCard({ chapter, expandedSections, onToggleSection, onUpdateKnowledgeItem, onToggleChapterPractice, savingCode }) {
  const sections = chapter.children || [];
  return (
    <div className={`esp-chapter-card${chapter.chapter_status === "completed" ? " completed" : ""}`}>
      <div className="esp-chapter-header">
        <div className="esp-chapter-title-row">
          <span className="esp-chapter-code">{chapter.code ? `第${chapter.code}章` : ""}</span>
          <h3>{chapter.title}</h3>
          <span className={`esp-chapter-badge ${chapter.chapter_status}`}>
            {chapter.chapter_status === "completed" ? "已完成" : chapter.chapter_status === "learning" ? "学习中" : "未开始"}
          </span>
        </div>
        <div className="esp-chapter-meta">
          <span>二级知识点 {chapter.sections_completed || 0}/{chapter.section_count || 0} 完成</span>
          <div className="esp-chapter-bar-wrap">
            <div className="esp-chapter-bar" style={{ width: `${chapter.chapter_completion_rate || 0}%` }} />
          </div>
          <span>{chapter.chapter_completion_rate || 0}%</span>
        </div>
      </div>
      <div className="esp-sections">
        {sections.map((section) => {
          const sectionCode = section.code || section.title;
          const st = section.section_status || "not_started";
          const ls = section.leaf_stats || {};
          const cpDone = section.chapter_practice_completed;
          const isExpanded = expandedSections[sectionCode] || false;
          return (
            <div key={sectionCode} className={`esp-section-card ${st}`}>
              <div className="esp-section-header">
                <button type="button" className="esp-section-expand" onClick={() => onToggleSection(sectionCode)}>
                  <span className={`esp-expand-arrow${isExpanded ? " open" : ""}`}>▶</span>
                </button>
                <div className="esp-section-info">
                  <div className="esp-section-title-row">
                    <strong>{section.title}</strong>
                    <span className={`esp-section-status-tag ${st}`}>
                      {st === "completed" ? "已完成" : st === "learning" ? "学习中" : "未开始"}
                    </span>
                  </div>
                  <div className="esp-section-meta">
                    <span>小知识点 {ls.mastered || 0}/{ls.total || 0}</span>
                    <span className="esp-section-cp">章节练习：{cpDone ? "✅ 已完成" : "⬜ 未完成"}</span>
                  </div>
                  <div className="esp-section-bar-wrap">
                    <div className="esp-section-bar" style={{ width: `${section.completion_rate || 0}%` }} />
                  </div>
                </div>
                <div className="esp-section-actions">
                  <button type="button" className={`esp-cp-btn${cpDone ? " done" : ""}`}
                    disabled={savingCode === `cp:${sectionCode}`}
                    onClick={() => onToggleChapterPractice(sectionCode, section.title, cpDone)}>
                    {savingCode === `cp:${sectionCode}` ? "保存中..." : cpDone ? "练习已完成 ✓" : "标记练习完成"}
                  </button>
                </div>
              </div>
              {isExpanded && (
                <div className="esp-section-children">
                  {(section.children || []).map((child) => (
                    <SubSection key={child.code || child.id || child.title} node={child}
                      onUpdate={onUpdateKnowledgeItem} savingCode={savingCode} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SubSection({ node, onUpdate, savingCode }) {
  const children = node.children || [];
  if (children.length === 0) {
    const st = node.status || "not_started";
    return (
      <div className={`esp-leaf-item ${st}`}>
        <div className="esp-leaf-info">
          <span className="esp-leaf-dot" />
          <span className="esp-leaf-title">{node.title}</span>
          <span className={`esp-leaf-status ${st}`}>
            {st === "mastered" ? "已掌握" : st === "learning" ? "学习中" : "未开始"}
          </span>
        </div>
        <div className="esp-leaf-actions">
          {["not_started", "learning", "mastered"].map((s) => (
            <button key={s} type="button"
              className={`esp-leaf-btn ${s}${st === s ? " active" : ""}`}
              disabled={savingCode === node.code || st === s}
              onClick={() => onUpdate(node.code, node.title, s)}>
              {s === "mastered" ? (savingCode === node.code ? "..." : "已掌握 ✓") :
               s === "learning" ? "学习中" : "未开始"}
            </button>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="esp-sub-section">
      <div className="esp-sub-section-header">
        <span className="esp-sub-section-title">{node.title}</span>
        <span className={`esp-sub-section-status ${node.status || "not_started"}`}>
          {node.status === "mastered" ? "已掌握" : node.status === "learning" ? "学习中" : "未开始"}
        </span>
      </div>
      <div className="esp-sub-section-children">
        {children.map((c) => (
          <SubSection key={c.code || c.id || c.title} node={c} onUpdate={onUpdate} savingCode={savingCode} />
        ))}
      </div>
    </div>
  );
}
