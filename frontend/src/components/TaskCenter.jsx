import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

const TASK_TYPE_OPTIONS = [
  { value: "read_material", label: "阅读资料" },
  { value: "ask_ai", label: "AI 问答" },
  { value: "code_practice", label: "代码练习" },
  { value: "challenge", label: "AI 出题练习" },
  { value: "review", label: "复习巩固" },
  { value: "custom", label: "自定义任务" },
  { value: "__other__", label: "其他 / 自定义输入..." },
];

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "todo", label: "未开始" },
  { value: "doing", label: "进行中" },
  { value: "done", label: "已完成" },
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
  const [reordering, setReordering] = useState(false);
  const [actionTaskId, setActionTaskId] = useState(null);

  // Knowledge points tree
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [kpLoading, setKpLoading] = useState(false);
  const [expandedKpIds, setExpandedKpIds] = useState(new Set());
  const [customKpInput, setCustomKpInput] = useState("");

  // Create form state
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createCourse, setCreateCourse] = useState(subject || "");
  const [createType, setCreateType] = useState("custom");
  const [customTypeInput, setCustomTypeInput] = useState("");
  const [createDueDate, setCreateDueDate] = useState("");
  const [selectedKpIds, setSelectedKpIds] = useState([]);

  // Build knowledge tree from flat list
  const kpTree = useMemo(() => {
    const roots = knowledgePoints.filter((kp) => !kp.parent_id);
    const children = knowledgePoints.filter((kp) => kp.parent_id);
    const grouped = {};
    children.forEach((c) => {
      const pid = c.parent_id;
      if (!grouped[pid]) grouped[pid] = [];
      grouped[pid].push(c);
    });
    return roots.map((r) => ({ ...r, children: grouped[r.id] || [] }));
  }, [knowledgePoints]);

  const loadKnowledgePoints = async (courseId) => {
    if (!user?.username || !courseId) {
      setKnowledgePoints([]);
      return;
    }
    setKpLoading(true);
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
    } finally {
      setKpLoading(false);
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

  const moveTask = async (index, direction) => {
    const newTasks = [...tasks];
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= newTasks.length) return;
    [newTasks[index], newTasks[targetIndex]] = [newTasks[targetIndex], newTasks[index]];
    const reordered = newTasks.map((t, i) => ({ id: t.id, order_index: i }));
    setTasks(newTasks);
    setReordering(true);
    try {
      await fetch(`${API_BASE}/learning/tasks/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, items: reordered }),
      });
    } catch (e) {
      console.error("Failed to reorder tasks:", e);
      loadTasks();
    } finally {
      setReordering(false);
    }
  };

  const createTask = async () => {
    if (!createTitle.trim()) return;
    setSaving(true);
    try {
      const effectiveType = createType === "__other__" && customTypeInput.trim()
        ? customTypeInput.trim()
        : createType === "__other__" ? "custom" : createType;
      const body = {
        username: user.username,
        course_id: normalizeSubject(createCourse, "") || "",
        title: createTitle.trim(),
        description: createDescription.trim(),
        task_type: effectiveType,
        status: "todo",
        source: "manual",
        priority: "medium",
      };
      if (createDueDate) body.due_date = createDueDate;
      if (selectedKpIds.length > 0) body.knowledge_point_id = selectedKpIds[0];
      if (customKpInput.trim()) {
        body.description = (createDescription.trim() ? createDescription.trim() + "\n" : "") + "自定义知识点: " + customKpInput.trim();
      }
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
    setCustomTypeInput("");
    setCreateDueDate("");
    setSelectedKpIds([]);
    setCustomKpInput("");
    setExpandedKpIds(new Set());
  };

  const toggleKpExpand = (kpId) => {
    setExpandedKpIds((prev) => {
      const next = new Set(prev);
      if (next.has(kpId)) next.delete(kpId); else next.add(kpId);
      return next;
    });
  };

  const toggleKpSelect = (kpId) => {
    setSelectedKpIds((prev) =>
      prev.includes(kpId) ? prev.filter((id) => id !== kpId) : [...prev, kpId]
    );
  };

  const selectKpBranch = (root) => {
    const allIds = [root.id, ...(root.children || []).map((c) => c.id)];
    setSelectedKpIds((prev) => {
      const existing = new Set(prev);
      const allSelected = allIds.every((id) => existing.has(id));
      if (allSelected) return prev.filter((id) => !allIds.includes(id));
      return [...new Set([...prev, ...allIds])];
    });
  };

  const updateTaskStatus = async (task, newStatus) => {
    setActionTaskId(task.id);
    try {
      const res = await fetch(`${API_BASE}/learning/tasks/${task.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, status: newStatus }),
      });
      const data = await res.json();
      if (res.ok) setTasks((prev) => prev.map((t) => (t.id === task.id ? data.task : t)));
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
      await fetch(`${API_BASE}/learning/tasks/${task.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
    } catch (e) {
      console.error("Failed to delete task:", e);
    } finally {
      setActionTaskId(null);
    }
  };

  const getTaskStatusClass = (status) => {
    if (status === "done") return "task-status-done";
    if (status === "doing") return "task-status-doing";
    return "task-status-todo";
  };

  return (
    <section className="chat-panel chat-panel--wide task-center-panel">
      {/* ── Hero Header Card ── */}
      <div className="task-center-hero">
        <div className="task-hero-left">
          <div className="task-hero-icon">📋</div>
          <div className="task-hero-text">
            <h2 className="task-hero-title">学习任务中心</h2>
            <p className="task-hero-subtitle">管理你的学习任务，规划学习进度，高效达成目标</p>
          </div>
        </div>
        <button
          className="task-btn-primary"
          onClick={() => {
            resetCreateForm();
            setShowCreateModal(true);
          }}
        >
          + 新建任务
        </button>
      </div>

      {/* ── Filters Card ── */}
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
        <div className="task-filter-spacer" />
        <button className="task-btn-refresh" onClick={loadTasks}>
          ↻ 刷新
        </button>
      </div>

      {/* ── Content Area ── */}
      {loading ? (
        <div className="task-center-empty-state">
          <div className="task-empty-icon">⏳</div>
          <p className="task-empty-text">正在加载任务...</p>
        </div>
      ) : tasks.length === 0 ? (
        <div className="task-center-empty-state">
          <div className="task-empty-icon">📝</div>
          <h3 className="task-empty-title">当前筛选条件下没有学习任务</h3>
          <p className="task-empty-desc">创建一个新的学习任务，开启你的学习计划吧！</p>
          <button
            className="task-btn-primary"
            onClick={() => {
              resetCreateForm();
              setShowCreateModal(true);
            }}
          >
            + 创建第一个任务
          </button>
        </div>
      ) : (
        <div className="task-list">
          {tasks.map((task, index) => (
            <div key={task.id} className={`task-card ${task.status === "done" ? "task-card--done" : ""}`}>
              <div className="task-card-sort">
                <button
                  className="task-move-btn"
                  disabled={reordering || index === 0}
                  onClick={() => moveTask(index, -1)}
                  title="上移"
                >▲</button>
                <button
                  className="task-move-btn"
                  disabled={reordering || index === tasks.length - 1}
                  onClick={() => moveTask(index, 1)}
                  title="下移"
                >▼</button>
              </div>
              <div className="task-card-main">
                <div className="task-card-header">
                  <h4 className="task-card-title">{task.title}</h4>
                  <div className="task-card-badges">
                    <span className={`task-status-badge ${getTaskStatusClass(task.status)}`}>
                      {STATUS_LABELS[task.status] || task.status}
                    </span>
                  </div>
                </div>
                {task.description && <p className="task-card-desc">{task.description}</p>}
                <div className="task-card-meta">
                  {task.course_id && <span className="subject-pill small">{getSubjectLabel(task.course_id)}</span>}
                  <span className="subject-pill small">{TASK_TYPE_LABELS[task.task_type] || task.task_type}</span>
                  {task.knowledge_point_title && (
                    <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>{task.knowledge_point_title}</span>
                  )}
                  {task.source && task.source !== "manual" && (
                    <span className="subject-pill small" style={{ background: "#ecfdf5", color: "#065f46" }}>{SOURCE_LABELS[task.source] || task.source}</span>
                  )}
                  {task.due_date && <span className="history-meta">截止：{formatDate(task.due_date)}</span>}
                  <span className="history-meta">创建：{formatDate(task.created_at)}</span>
                  {task.completed_at && <span className="history-meta" style={{ color: "#059669" }}>完成：{formatDate(task.completed_at)}</span>}
                </div>
              </div>
              <div className="task-card-actions">
                {task.status !== "doing" && task.status !== "done" && (
                  <button className="tiny-button" disabled={actionTaskId === task.id} onClick={() => updateTaskStatus(task, "doing")}>标记进行中</button>
                )}
                {task.status !== "done" && (
                  <button className="tiny-button" disabled={actionTaskId === task.id} onClick={() => updateTaskStatus(task, "done")} style={{ color: "#059669" }}>标记完成</button>
                )}
                {task.status === "done" && (
                  <button className="tiny-button" disabled={actionTaskId === task.id} onClick={() => updateTaskStatus(task, "todo")}>改回未完成</button>
                )}
                <button className="tiny-button" disabled={actionTaskId === task.id} onClick={() => deleteTask(task)} style={{ color: "#dc2626" }}>删除</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card task-create-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建学习任务</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>&times;</button>
            </div>

            <div className="task-modal-body">
              <label className="field-label">任务标题 *</label>
              <input className="field" placeholder="请输入任务标题" value={createTitle} onChange={(e) => setCreateTitle(e.target.value)} />

              <label className="field-label">任务描述</label>
              <textarea className="field" rows={2} placeholder="详细说明任务内容（可选）" value={createDescription} onChange={(e) => setCreateDescription(e.target.value)} />

              <div className="task-modal-row">
                <div className="task-modal-col">
                  <label className="field-label">所属课程</label>
                  <select className="field" value={createCourse} onChange={(e) => setCreateCourse(e.target.value)}>
                    <option value="">不绑定课程</option>
                    {courseOptions.map((item) => (<option key={item} value={item}>{getSubjectLabel(item)}</option>))}
                  </select>
                </div>
                <div className="task-modal-col">
                  <label className="field-label">任务类型</label>
                  <select className="field" value={createType} onChange={(e) => { setCreateType(e.target.value); if (e.target.value !== "__other__") setCustomTypeInput(""); }}>
                    {TASK_TYPE_OPTIONS.map((item) => (<option key={item.value} value={item.value}>{item.label}</option>))}
                  </select>
                  {createType === "__other__" && (
                    <input
                      className="field"
                      style={{ marginTop: 8 }}
                      placeholder="请输入自定义任务类型"
                      value={customTypeInput}
                      onChange={(e) => setCustomTypeInput(e.target.value)}
                    />
                  )}
                </div>
              </div>

              <label className="field-label">截止日期（可选）</label>
              <input className="field" type="date" value={createDueDate} onChange={(e) => setCreateDueDate(e.target.value)} />

              {/* Knowledge Point Binding — tree from materials/knowledge base */}
              <div className="task-modal-section">
                <label className="field-label">绑定知识点（可选）</label>
                {!createCourse ? (
                  <p className="task-modal-hint">请先选择所属课程以加载该课程的知识点。</p>
                ) : kpLoading ? (
                  <p className="task-modal-hint">正在加载课程知识点...</p>
                ) : kpTree.length === 0 ? (
                  <p className="task-modal-hint">当前课程暂无知识点。你可以先到知识库上传资料并提取知识点，或下方手动输入。</p>
                ) : (
                  <div className="task-kp-tree">
                    {kpTree.map((root) => {
                      const isExpanded = expandedKpIds.has(root.id);
                      return (
                        <div key={root.id} className="task-kp-node">
                          <div className="task-kp-node-header">
                            <button type="button" className="task-kp-expand-btn" onClick={() => toggleKpExpand(root.id)}>
                              {isExpanded ? "▼" : "▶"}
                            </button>
                            <label className="task-kp-check-label">
                              <input type="checkbox" checked={selectedKpIds.includes(root.id)} onChange={() => selectKpBranch(root)} />
                              <span className="task-kp-name">{root.title}</span>
                            </label>
                          </div>
                          {isExpanded && root.children.length > 0 && (
                            <div className="task-kp-children">
                              {root.children.map((child) => (
                                <label key={child.id} className="task-kp-child-label">
                                  <input type="checkbox" checked={selectedKpIds.includes(child.id)} onChange={() => toggleKpSelect(child.id)} />
                                  <span className="task-kp-child-name">{child.title}</span>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Manual knowledge point input */}
              <label className="field-label">手动输入知识点</label>
              <input className="field" placeholder="输入自定义知识点名称，例如：动态规划、指针操作" value={customKpInput} onChange={(e) => setCustomKpInput(e.target.value)} />
            </div>

            <div className="task-form-actions">
              <button className="ghost-button compact" onClick={() => setShowCreateModal(false)}>取消</button>
              <button className="task-btn-primary" disabled={saving || !createTitle.trim()} onClick={createTask}>
                {saving ? "创建中..." : "创建任务"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
