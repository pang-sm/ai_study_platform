import { useEffect, useState } from "react";

const API_BASE = "/api";

const TASK_TYPE_OPTIONS = [
  { value: "read_material", label: "阅读资料" },
  { value: "ask_ai", label: "AI 问答" },
  { value: "code_practice", label: "代码练习" },
  { value: "challenge", label: "AI 出题练习" },
  { value: "review", label: "复习巩固" },
  { value: "custom", label: "自定义任务" },
];

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "todo", label: "未开始" },
  { value: "doing", label: "进行中" },
  { value: "done", label: "已完成" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

const SOURCE_LABELS = {
  manual: "手动创建",
  code_diagnosis: "诊断生成",
  course_plan: "课程计划",
  system: "系统推荐",
};

const TASK_TYPE_LABELS = {
  read_material: "阅读资料",
  ask_ai: "AI 问答",
  code_practice: "代码练习",
  challenge: "AI 出题",
  review: "复习巩固",
  custom: "自定义",
};

const STATUS_LABELS = {
  todo: "未开始",
  doing: "进行中",
  done: "已完成",
};

const PRIORITY_LABELS = {
  low: "低",
  medium: "中",
  high: "高",
};

export default function TaskCenter({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
}) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [courseFilter, setCourseFilter] = useState(subject || "");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionTaskId, setActionTaskId] = useState(null);

  // Knowledge points for binding
  const [knowledgePoints, setKnowledgePoints] = useState([]);

  // Create form state
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createCourse, setCreateCourse] = useState(subject || "");
  const [createType, setCreateType] = useState("custom");
  const [createPriority, setCreatePriority] = useState("medium");
  const [createDueDate, setCreateDueDate] = useState("");
  const [createKnowledgePointId, setCreateKnowledgePointId] = useState("");

  const loadKnowledgePoints = async (courseId) => {
    if (!user?.username || !courseId) {
      setKnowledgePoints([]);
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`
      );
      const data = await res.json();
      if (res.ok) {
        setKnowledgePoints(data.knowledge_points || []);
      }
    } catch (e) {
      console.error("Failed to load knowledge points:", e);
    }
  };

  const loadTasks = async () => {
    if (!user?.username) return;
    setLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      const normalizedCourse = normalizeSubject(courseFilter, "");
      if (normalizedCourse) query.set("course_id", normalizedCourse);
      if (statusFilter) query.set("status", statusFilter);
      const res = await fetch(`${API_BASE}/learning/tasks?${query.toString()}`);
      const data = await res.json();
      if (res.ok) {
        setTasks(data.tasks || []);
      }
    } catch (e) {
      console.error("Failed to load tasks:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const normalizedCourse = normalizeSubject(courseFilter, "");
    loadKnowledgePoints(normalizedCourse);
    loadTasks();
  }, [user?.username, courseFilter, statusFilter]);

  const createTask = async () => {
    if (!createTitle.trim()) return;
    setSaving(true);
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(createCourse, "") || "",
        title: createTitle.trim(),
        description: createDescription.trim(),
        task_type: createType,
        status: "todo",
        source: "manual",
        priority: createPriority,
      };
      if (createDueDate) body.due_date = createDueDate;
      if (createKnowledgePointId) body.knowledge_point_id = parseInt(createKnowledgePointId);
      const res = await fetch(`${API_BASE}/learning/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowCreateModal(false);
        resetCreateForm();
        await loadTasks();
      } else {
        alert(data.detail || "创建失败");
      }
    } catch (e) {
      console.error("Failed to create task:", e);
    } finally {
      setSaving(false);
    }
  };

  const resetCreateForm = () => {
    setCreateTitle("");
    setCreateDescription("");
    setCreateCourse(subject || "");
    setCreateType("custom");
    setCreatePriority("medium");
    setCreateDueDate("");
    setCreateKnowledgePointId("");
  };

  const updateTaskStatus = async (task, newStatus) => {
    setActionTaskId(task.id);
    try {
      const res = await fetch(`${API_BASE}/learning/tasks/${task.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          status: newStatus,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setTasks((prev) =>
          prev.map((t) => (t.id === task.id ? data.task : t))
        );
      }
    } catch (e) {
      console.error("Failed to update task:", e);
    } finally {
      setActionTaskId(null);
    }
  };

  const deleteTask = async (task) => {
    if (!window.confirm(`确认删除任务"${task.title}"吗？`)) return;
    setActionTaskId(task.id);
    try {
      const res = await fetch(
        `${API_BASE}/learning/tasks/${task.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setTasks((prev) => prev.filter((t) => t.id !== task.id));
      }
    } catch (e) {
      console.error("Failed to delete task:", e);
    } finally {
      setActionTaskId(null);
    }
  };

  const getTaskPriorityClass = (priority) => {
    if (priority === "high") return "task-priority-high";
    if (priority === "low") return "task-priority-low";
    return "task-priority-medium";
  };

  const getTaskStatusClass = (status) => {
    if (status === "done") return "task-status-done";
    if (status === "doing") return "task-status-doing";
    return "task-status-todo";
  };

  return (
    <section className="chat-panel chat-panel--wide task-center-panel">
      <div className="panel-header panel-header--chat task-center-header">
        <div>
          <div className="subject-pill panel-pill">学习任务中心</div>
          <h2>学习任务中心</h2>
        </div>
        <button
          className="primary-button compact"
          onClick={() => {
            resetCreateForm();
            setShowCreateModal(true);
          }}
        >
          新建任务
        </button>
      </div>

      <div className="task-center-filters">
        <div className="task-filter-item">
          <label className="field-label">课程筛选</label>
          <select
            className="field"
            value={courseFilter}
            onChange={(e) => setCourseFilter(e.target.value)}
          >
            <option value="">全部课程</option>
            {courseOptions.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>
        </div>
        <div className="task-filter-item">
          <label className="field-label">状态筛选</label>
          <select
            className="field"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <button className="ghost-button compact" onClick={loadTasks}>
          刷新
        </button>
      </div>

      {loading ? (
        <div className="empty-state">加载中...</div>
      ) : tasks.length === 0 ? (
        <div className="empty-inline task-center-empty">
          <p>当前筛选条件下没有学习任务。</p>
          <button
            className="primary-button compact"
            onClick={() => {
              resetCreateForm();
              setShowCreateModal(true);
            }}
          >
            创建第一个任务
          </button>
        </div>
      ) : (
        <div className="task-list">
          {tasks.map((task) => (
            <div key={task.id} className={`task-card ${task.status === "done" ? "task-card--done" : ""}`}>
              <div className="task-card-main">
                <div className="task-card-header">
                  <h4 className="task-card-title">{task.title}</h4>
                  <div className="task-card-badges">
                    <span className={`task-status-badge ${getTaskStatusClass(task.status)}`}>
                      {STATUS_LABELS[task.status] || task.status}
                    </span>
                    <span className={`task-priority-badge ${getTaskPriorityClass(task.priority)}`}>
                      {PRIORITY_LABELS[task.priority] || task.priority}
                    </span>
                  </div>
                </div>
                {task.description && (
                  <p className="task-card-desc">{task.description}</p>
                )}
                <div className="task-card-meta">
                  {task.course_id && (
                    <span className="subject-pill small">
                      {getSubjectLabel(task.course_id)}
                    </span>
                  )}
                  <span className="subject-pill small">
                    {TASK_TYPE_LABELS[task.task_type] || task.task_type}
                  </span>
                  {task.knowledge_point_title && (
                    <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                      {task.knowledge_point_title}
                    </span>
                  )}
                  {task.source && task.source !== "manual" && (
                    <span className="subject-pill small" style={{ background: "#ecfdf5", color: "#065f46" }}>
                      {SOURCE_LABELS[task.source] || task.source}
                    </span>
                  )}
                  {task.due_date && (
                    <span className="history-meta">
                      截止：{formatDate(task.due_date)}
                    </span>
                  )}
                  <span className="history-meta">
                    创建：{formatDate(task.created_at)}
                  </span>
                  {task.completed_at && (
                    <span className="history-meta" style={{ color: "#059669" }}>
                      完成：{formatDate(task.completed_at)}
                    </span>
                  )}
                </div>
              </div>
              <div className="task-card-actions">
                {task.status !== "doing" && task.status !== "done" && (
                  <button
                    className="tiny-button"
                    disabled={actionTaskId === task.id}
                    onClick={() => updateTaskStatus(task, "doing")}
                  >
                    标记进行中
                  </button>
                )}
                {task.status !== "done" && (
                  <button
                    className="tiny-button"
                    disabled={actionTaskId === task.id}
                    onClick={() => updateTaskStatus(task, "done")}
                    style={{ color: "#059669" }}
                  >
                    标记完成
                  </button>
                )}
                {task.status === "done" && (
                  <button
                    className="tiny-button"
                    disabled={actionTaskId === task.id}
                    onClick={() => updateTaskStatus(task, "todo")}
                  >
                    改回未完成
                  </button>
                )}
                <button
                  className="tiny-button"
                  disabled={actionTaskId === task.id}
                  onClick={() => deleteTask(task)}
                  style={{ color: "#dc2626" }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建学习任务</h3>
              <button
                className="modal-close"
                onClick={() => setShowCreateModal(false)}
              >
                &times;
              </button>
            </div>

            <div className="task-modal-body">
              <label className="field-label">任务标题 *</label>
              <input
                className="field"
                placeholder="例如：复习数据结构第三章"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
              />
              <label className="field-label">任务描述</label>
              <textarea
                className="field"
                rows={3}
                placeholder="详细说明任务内容..."
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
              />
              <label className="field-label">所属课程</label>
              <select
                className="field"
                value={createCourse}
                onChange={(e) => setCreateCourse(e.target.value)}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>
              <label className="field-label">任务类型</label>
              <select
                className="field"
                value={createType}
                onChange={(e) => setCreateType(e.target.value)}
              >
                {TASK_TYPE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <label className="field-label">优先级</label>
              <select
                className="field"
                value={createPriority}
                onChange={(e) => setCreatePriority(e.target.value)}
              >
                {PRIORITY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <label className="field-label">绑定知识点（可选）</label>
              <select
                className="field"
                value={createKnowledgePointId}
                onChange={(e) => setCreateKnowledgePointId(e.target.value)}
              >
                <option value="">不绑定知识点</option>
                {knowledgePoints.map((kp) => (
                  <option key={kp.id} value={kp.id}>
                    {kp.title}
                  </option>
                ))}
              </select>
              <label className="field-label">截止日期（可选）</label>
              <input
                className="field"
                type="date"
                value={createDueDate}
                onChange={(e) => setCreateDueDate(e.target.value)}
              />
            </div>

            <div className="task-form-actions">
              <button
                className="ghost-button compact"
                onClick={() => setShowCreateModal(false)}
              >
                取消
              </button>
              <button
                className="primary-button compact"
                disabled={saving || !createTitle.trim()}
                onClick={createTask}
              >
                {saving ? "创建中..." : "创建任务"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
