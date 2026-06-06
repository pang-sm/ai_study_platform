import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

const TASK_TYPE_OPTIONS = ["复习资料", "完成练习", "整理笔记", "查漏补缺", "考前复盘", "自定义"];

const TASK_TYPE_LABELS = {
  read_material: "复习资料",
  ask_ai: "AI 问答",
  code_practice: "代码练习",
  challenge: "完成练习",
  review: "复习资料",
  custom: "自定义",
};

const STATUS_COLUMNS = [
  { value: "todo", label: "待开始" },
  { value: "doing", label: "进行中" },
  { value: "done", label: "已完成" },
];

const SOURCE_LABELS = {
  manual: "手动创建",
  code_diagnosis: "诊断生成",
  course_plan: "课程计划",
  system: "系统推荐",
};

const emptyForm = {
  id: null,
  title: "",
  taskType: "复习资料",
  customTaskType: "",
  description: "",
  courseId: "",
  dueDate: "",
  knowledgePointId: "",
  knowledgePointText: "",
  relatedMaterialId: "",
  status: "todo",
};

function getTaskTypeLabel(value) {
  return TASK_TYPE_LABELS[value] || value || "学习任务";
}

function getMaterialTitle(material) {
  return material?.file_name || material?.original_filename || material?.title || "";
}

function isIndexedMaterial(material) {
  return Number(material?.chunk_count || 0) > 0 || material?.parse_status === "success";
}

export default function TaskCenter({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
  onStartPractice = () => {},
  searchNavigate,
  onClearSearchNavigate = () => {},
}) {
  const [tasks, setTasks] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [courseFilter, setCourseFilter] = useState(subject || "");
  const [highlightTaskId, setHighlightTaskId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reordering, setReordering] = useState(false);
  const [actionTaskId, setActionTaskId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ ...emptyForm, courseId: subject || "" });
  const [expandedKpIds, setExpandedKpIds] = useState(new Set());
  const [kpLoading, setKpLoading] = useState(false);
  const [materialsLoading, setMaterialsLoading] = useState(false);

  const normalizedFilterCourse = useMemo(
    () => normalizeSubject(courseFilter, "") || "",
    [courseFilter, normalizeSubject]
  );

  const normalizedFormCourse = useMemo(
    () => normalizeSubject(form.courseId, "") || "",
    [form.courseId, normalizeSubject]
  );

  const knowledgeTree = useMemo(() => {
    const points = Array.isArray(knowledgePoints) ? knowledgePoints : [];
    const byParent = new Map();
    points.forEach((point) => {
      const parentId = point.parent_id || null;
      if (!byParent.has(parentId)) byParent.set(parentId, []);
      byParent.get(parentId).push(point);
    });

    let roots = points.filter((point) => !point.parent_id || Number(point.level || 0) === 1);
    if (roots.length === 0 && points.length > 0) roots = points;

    return roots.map((root) => {
      const directChildren = Array.isArray(root.children) ? root.children : [];
      const groupedChildren = byParent.get(root.id) || [];
      const children = directChildren.length > 0 ? directChildren : groupedChildren;
      return { ...root, children: children.filter((child) => child.id !== root.id) };
    });
  }, [knowledgePoints]);

  const tasksByStatus = useMemo(() => {
    return STATUS_COLUMNS.reduce((acc, column) => {
      acc[column.value] = tasks.filter((task) => (task.status || "todo") === column.value);
      return acc;
    }, {});
  }, [tasks]);

  useEffect(() => {
    setCourseFilter(subject || "");
  }, [subject]);

  const [pendingSearchTaskId, setPendingSearchTaskId] = useState(null);

  // Handle search navigation — mark task for highlight after data loads
  useEffect(() => {
    if (!searchNavigate || searchNavigate.page !== "taskCenter" || !searchNavigate.taskId) return;
    setPendingSearchTaskId(searchNavigate.taskId);
    // Clear any course filter to ensure the task is visible
    if (searchNavigate.courseId) setCourseFilter(searchNavigate.courseId);
    onClearSearchNavigate();
  }, [searchNavigate, onClearSearchNavigate]);

  // After tasks load, scroll to and highlight the pending task
  useEffect(() => {
    if (!pendingSearchTaskId || loading) return;
    setHighlightTaskId(pendingSearchTaskId);
    const tid = setTimeout(() => {
      const el = document.getElementById(`task-row-${pendingSearchTaskId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("task-row-highlight");
        setTimeout(() => { if (el) el.classList.remove("task-row-highlight"); }, 2500);
      }
      setHighlightTaskId(null);
      setPendingSearchTaskId(null);
    }, 200);
    return () => clearTimeout(tid);
  }, [tasks, pendingSearchTaskId, loading]);

  useEffect(() => {
    if (!modalOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [modalOpen]);

  useEffect(() => {
    loadTasks();
  }, [user?.username, normalizedFilterCourse]);

  useEffect(() => {
    if (!modalOpen) return;
    loadKnowledgePoints(normalizedFormCourse);
    loadMaterials(normalizedFormCourse);
  }, [modalOpen, normalizedFormCourse, user?.username]);

  const loadTasks = async () => {
    if (!user?.username) return;
    setLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      if (normalizedFilterCourse) query.set("course_id", normalizedFilterCourse);
      const res = await fetch(`${API_BASE}/learning/tasks?${query.toString()}`);
      const data = await res.json();
      if (res.ok) setTasks(data.tasks || []);
    } catch (error) {
      console.error("Failed to load tasks:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadKnowledgePoints = async (courseId) => {
    if (!user?.username || !courseId) {
      setKnowledgePoints([]);
      return;
    }
    setKpLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username, course_id: courseId });
      const res = await fetch(`${API_BASE}/knowledge-points?${query.toString()}`);
      const data = await res.json();
      setKnowledgePoints(res.ok ? data.knowledge_points || [] : []);
    } catch (error) {
      console.error("Failed to load knowledge points:", error);
      setKnowledgePoints([]);
    } finally {
      setKpLoading(false);
    }
  };

  const loadMaterials = async (courseId) => {
    if (!user?.username || !courseId) {
      setMaterials([]);
      return;
    }
    setMaterialsLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username, subject: courseId });
      const res = await fetch(`${API_BASE}/materials?${query.toString()}`);
      const data = await res.json();
      setMaterials(res.ok ? data.materials || [] : []);
    } catch (error) {
      console.error("Failed to load materials:", error);
      setMaterials([]);
    } finally {
      setMaterialsLoading(false);
    }
  };

  const openCreateModal = () => {
    setForm({ ...emptyForm, courseId: normalizedFilterCourse || subject || "" });
    setExpandedKpIds(new Set());
    setModalOpen(true);
  };

  const openEditModal = (task) => {
    const knownType = TASK_TYPE_OPTIONS.includes(task.task_type);
    setForm({
      id: task.id,
      title: task.title || "",
      taskType: knownType ? task.task_type : "自定义",
      customTaskType: knownType ? "" : task.task_type || "",
      description: task.description || "",
      courseId: task.course_id || normalizedFilterCourse || subject || "",
      dueDate: task.due_date ? String(task.due_date).slice(0, 10) : "",
      knowledgePointId: task.knowledge_point_id ? String(task.knowledge_point_id) : "",
      knowledgePointText: task.knowledge_point_text || "",
      relatedMaterialId: task.related_material_id ? String(task.related_material_id) : "",
      status: task.status || "todo",
    });
    setExpandedKpIds(new Set());
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setForm({ ...emptyForm, courseId: subject || "" });
  };

  const updateForm = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const toggleKpExpand = (kpId) => {
    setExpandedKpIds((prev) => {
      const next = new Set(prev);
      if (next.has(kpId)) next.delete(kpId);
      else next.add(kpId);
      return next;
    });
  };

  const selectKnowledgePoint = (point) => {
    updateForm("knowledgePointId", String(point.id));
  };

  const saveTask = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    const taskType = form.taskType === "自定义"
      ? (form.customTaskType.trim() || "自定义")
      : form.taskType;
    const payload = {
      username: user.username,
      title: form.title.trim(),
      description: form.description.trim(),
      task_type: taskType,
      status: form.status || "todo",
      due_date: form.dueDate || null,
      knowledge_point_id: form.knowledgePointId ? Number(form.knowledgePointId) : 0,
      knowledge_point_text: form.knowledgePointText.trim(),
      related_material_id: form.relatedMaterialId ? Number(form.relatedMaterialId) : 0,
    };
    if (!form.id) {
      payload.course_id = normalizedFormCourse;
      payload.source = "manual";
    }
    try {
      const res = await fetch(
        form.id ? `${API_BASE}/learning/tasks/${form.id}` : `${API_BASE}/learning/tasks`,
        {
          method: form.id ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data.detail || "保存任务失败");
        return;
      }
      closeModal();
      await loadTasks();
    } catch (error) {
      console.error("Failed to save task:", error);
      alert("保存任务失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const updateTaskStatus = async (task, nextStatus) => {
    setActionTaskId(task.id);
    try {
      const res = await fetch(`${API_BASE}/learning/tasks/${task.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, status: nextStatus }),
      });
      const data = await res.json();
      if (res.ok) {
        setTasks((prev) => prev.map((item) => (item.id === task.id ? data.task : item)));
      }
    } catch (error) {
      console.error("Failed to update task status:", error);
    } finally {
      setActionTaskId(null);
    }
  };

  const deleteTask = async (task) => {
    if (!window.confirm(`确认删除任务“${task.title}”吗？`)) return;
    setActionTaskId(task.id);
    try {
      const res = await fetch(
        `${API_BASE}/learning/tasks/${task.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) setTasks((prev) => prev.filter((item) => item.id !== task.id));
    } catch (error) {
      console.error("Failed to delete task:", error);
    } finally {
      setActionTaskId(null);
    }
  };

  const moveTask = async (task, direction) => {
    const statusTasks = tasksByStatus[task.status || "todo"] || [];
    const index = statusTasks.findIndex((item) => item.id === task.id);
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= statusTasks.length) return;

    const nextStatusTasks = [...statusTasks];
    [nextStatusTasks[index], nextStatusTasks[targetIndex]] = [nextStatusTasks[targetIndex], nextStatusTasks[index]];
    const nextStatusIds = nextStatusTasks.map((item) => item.id);
    const nextTasks = tasks.map((item) => {
      const orderIndex = nextStatusIds.indexOf(item.id);
      return orderIndex >= 0 ? { ...item, order_index: orderIndex } : item;
    });
    const previousTasks = tasks;
    setTasks(nextTasks);
    setReordering(true);
    try {
      const res = await fetch(`${API_BASE}/learning/tasks/reorder`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizedFilterCourse,
          task_ids: nextStatusIds,
        }),
      });
      if (!res.ok) throw new Error(`Reorder failed: ${res.status}`);
      await loadTasks();
    } catch (error) {
      console.error("Failed to reorder tasks:", error);
      setTasks(previousTasks);
      await loadTasks();
    } finally {
      setReordering(false);
    }
  };

  const shouldShowPracticeEntry = (task) => {
    const typeText = String(task.task_type || "").toLowerCase();
    return (
      typeText.includes("练习") ||
      typeText.includes("practice") ||
      typeText.includes("challenge") ||
      typeText.includes("查漏") ||
      typeText.includes("复盘") ||
      Boolean(task.knowledge_point_id || task.knowledge_point_text)
    );
  };

  const getPracticeStatusLabel = (task) => {
    if (task.status === "done") return "已完成练习 / 已完成任务";
    if (task.related_question_id || task.related_session_id || task.related_challenge_id) return "已关联练习";
    return "未完成";
  };

  const startPracticeFromTask = (task) => {
    onStartPractice({
      fromTask: true,
      taskId: task.id,
      courseId: task.course_id || "",
      courseName: task.course_id ? getSubjectLabel(task.course_id) : "",
      knowledgePointId: task.knowledge_point_id || null,
      knowledgePointTitle: task.knowledge_point_title || "",
      knowledgePointText: task.knowledge_point_text || "",
      relatedMaterialId: task.related_material_id || null,
      relatedMaterialTitle: task.related_material_title || task.material_filename || task.material_title || "",
      taskTitle: task.title || "",
    });
  };

  const renderKnowledgeSelector = () => {
    if (!normalizedFormCourse) {
      return <p className="task-muted">请先选择所属课程。</p>;
    }
    if (kpLoading) {
      return <p className="task-muted">正在加载课程知识点...</p>;
    }
    if (knowledgeTree.length === 0) {
      return <p className="task-muted">当前课程暂无自动提取的知识点，你可以手动输入。</p>;
    }
    return (
      <div className="task-kp-tree">
        {knowledgeTree.map((root) => {
          const expanded = expandedKpIds.has(root.id);
          const selected = String(root.id) === String(form.knowledgePointId);
          return (
            <div className="task-kp-node" key={root.id}>
              <div className="task-kp-row">
                <button
                  type="button"
                  className="task-icon-button"
                  onClick={() => toggleKpExpand(root.id)}
                  aria-label={expanded ? "收起知识点" : "展开知识点"}
                >
                  {expanded ? "⌄" : "›"}
                </button>
                <button
                  type="button"
                  className={`task-kp-select ${selected ? "is-selected" : ""}`}
                  onClick={() => selectKnowledgePoint(root)}
                >
                  {root.title}
                </button>
              </div>
              {expanded && root.children?.length > 0 && (
                <div className="task-kp-children">
                  {root.children.map((child) => (
                    <button
                      type="button"
                      key={child.id}
                      className={`task-kp-child ${String(child.id) === String(form.knowledgePointId) ? "is-selected" : ""}`}
                      onClick={() => selectKnowledgePoint(child)}
                    >
                      {child.title}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderMaterialSelector = () => {
    if (!normalizedFormCourse) {
      return <p className="task-muted">选择课程后可关联该课程资料。</p>;
    }
    if (materialsLoading) {
      return <p className="task-muted">正在加载资料...</p>;
    }
    if (materials.length === 0) {
      return <p className="task-muted">当前课程暂无资料，可先去资料库上传。</p>;
    }
    return (
      <div className="task-material-list">
        {materials.map((material) => {
          const selected = String(material.id) === String(form.relatedMaterialId);
          return (
            <button
              type="button"
              key={material.id}
              className={`task-material-item ${selected ? "is-selected" : ""}`}
              onClick={() => updateForm("relatedMaterialId", selected ? "" : String(material.id))}
            >
              <span className="task-material-title">{getMaterialTitle(material)}</span>
              <span className="task-material-meta">
                {material.file_type || "资料"} · {formatDate(material.created_at)} · {isIndexedMaterial(material) ? "已索引" : "未索引"}
              </span>
            </button>
          );
        })}
      </div>
    );
  };

  const renderTaskCard = (task, index, statusTasks) => {
    const knowledgeLabel = task.knowledge_point_title || task.knowledge_point_text || "未绑定知识点";
    const materialLabel = task.related_material_title || task.material_filename || task.material_title || "";
    const isDone = task.status === "done";
    return (
      <article id={`task-row-${task.id}`} className={`task-card-v2 ${isDone ? "is-done" : ""} ${highlightTaskId === task.id ? "task-row-highlight" : ""}`} key={task.id}>
        <div className="task-card-order">
          <button
            type="button"
            className="task-icon-button"
            disabled={reordering || index === 0}
            onClick={() => moveTask(task, -1)}
            aria-label="上移"
            title="上移"
          >
            ↑
          </button>
          <button
            type="button"
            className="task-icon-button"
            disabled={reordering || index === statusTasks.length - 1}
            onClick={() => moveTask(task, 1)}
            aria-label="下移"
            title="下移"
          >
            ↓
          </button>
        </div>
        <div className="task-card-content">
          <div className="task-card-topline">
            <h4>{task.title}</h4>
            <span className={`task-status-chip task-status-${task.status || "todo"}`}>
              {STATUS_COLUMNS.find((item) => item.value === task.status)?.label || "待开始"}
            </span>
          </div>
          {task.description && <p className="task-card-description">{task.description}</p>}
          <div className="task-card-meta-v2">
            <span>{getTaskTypeLabel(task.task_type)}</span>
            <span>知识点：{knowledgeLabel}</span>
            {materialLabel && <span>来源资料：{materialLabel}</span>}
            {task.due_date && <span>截止：{formatDate(task.due_date)}</span>}
            {task.source && task.source !== "manual" && <span>{SOURCE_LABELS[task.source] || task.source}</span>}
          </div>
        </div>
        <div className="task-practice-status">练习状态：{getPracticeStatusLabel(task)}</div>
        <div className="task-card-actions-v2">
          {shouldShowPracticeEntry(task) && (
            <button
              type="button"
              className="tiny-button task-practice-entry"
              onClick={() => startPracticeFromTask(task)}
            >
              {isDone ? "再练一次" : "去练习"}
            </button>
          )}
          <button type="button" className="tiny-button" onClick={() => openEditModal(task)}>编辑</button>
          {isDone ? (
            <button
              type="button"
              className="tiny-button"
              disabled={actionTaskId === task.id}
              onClick={() => updateTaskStatus(task, "todo")}
            >
              取消完成
            </button>
          ) : (
            <button
              type="button"
              className="tiny-button"
              disabled={actionTaskId === task.id}
              onClick={() => updateTaskStatus(task, "done")}
            >
              完成
            </button>
          )}
          {!isDone && task.status !== "doing" && (
            <button
              type="button"
              className="tiny-button"
              disabled={actionTaskId === task.id}
              onClick={() => updateTaskStatus(task, "doing")}
            >
              开始
            </button>
          )}
          <button
            type="button"
            className="tiny-button danger"
            disabled={actionTaskId === task.id}
            onClick={() => deleteTask(task)}
          >
            删除
          </button>
        </div>
      </article>
    );
  };

  return (
    <section className="chat-panel chat-panel--wide task-center-panel task-center-v2">
      <header className="task-titlebar">
        <div>
          <h2>学习任务</h2>
          <p>把资料、知识点和练习安排成可执行计划</p>
        </div>
        <button type="button" className="task-btn-primary" onClick={openCreateModal}>
          新建任务
        </button>
      </header>

      <div className="task-toolbar">
        <label>
          <span>课程</span>
          <select className="field" value={courseFilter} onChange={(event) => setCourseFilter(event.target.value)}>
            <option value="">全部课程</option>
            {courseOptions.map((item) => (
              <option key={item} value={item}>{getSubjectLabel(item)}</option>
            ))}
          </select>
        </label>
        <button type="button" className="task-btn-secondary" onClick={loadTasks}>刷新</button>
      </div>

      {loading ? (
        <div className="task-empty-state-v2">正在加载任务...</div>
      ) : tasks.length === 0 ? (
        <div className="task-empty-state-v2">
          <h3>还没有学习任务，创建一个任务把学习安排起来。</h3>
          <button type="button" className="task-btn-primary" onClick={openCreateModal}>创建任务</button>
        </div>
      ) : (
        <div className="task-board">
          {STATUS_COLUMNS.map((column) => {
            const statusTasks = tasksByStatus[column.value] || [];
            return (
              <section className="task-board-column" key={column.value}>
                <div className="task-board-column-header">
                  <h3>{column.label}</h3>
                  <span>{statusTasks.length}</span>
                </div>
                <div className="task-board-list">
                  {statusTasks.length === 0 ? (
                    <p className="task-column-empty">暂无任务</p>
                  ) : (
                    statusTasks.map((task, index) => renderTaskCard(task, index, statusTasks))
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <div className="task-modal-overlay" role="presentation">
          <div className="task-modal-card" role="dialog" aria-modal="true" aria-labelledby="task-modal-title">
            <button type="button" className="task-modal-close" onClick={closeModal} aria-label="关闭">×</button>
            <div className="task-modal-header">
              <h3 id="task-modal-title">{form.id ? "编辑学习任务" : "新建学习任务"}</h3>
            </div>
            <div className="task-modal-body">
              <label className="task-form-field">
                <span>任务标题</span>
                <input
                  className="field"
                  value={form.title}
                  placeholder="例如：复习进程调度"
                  onChange={(event) => updateForm("title", event.target.value)}
                />
              </label>

              <label className="task-form-field">
                <span>任务类型</span>
                <select
                  className="field"
                  value={form.taskType}
                  onChange={(event) => updateForm("taskType", event.target.value)}
                >
                  {TASK_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              {form.taskType === "自定义" && (
                <label className="task-form-field">
                  <span>自定义任务类型</span>
                  <input
                    className="field"
                    value={form.customTaskType}
                    placeholder="例如：整理错题"
                    onChange={(event) => updateForm("customTaskType", event.target.value)}
                  />
                </label>
              )}

              {!form.id && (
                <label className="task-form-field">
                  <span>所属课程</span>
                  <select
                    className="field"
                    value={form.courseId}
                    onChange={(event) => updateForm("courseId", event.target.value)}
                  >
                    <option value="">不绑定课程</option>
                    {courseOptions.map((item) => (
                      <option key={item} value={item}>{getSubjectLabel(item)}</option>
                    ))}
                  </select>
                </label>
              )}

              <div className="task-form-field">
                <span>绑定知识点</span>
                {renderKnowledgeSelector()}
              </div>

              <label className="task-form-field">
                <span>手动输入知识点</span>
                <input
                  className="field"
                  value={form.knowledgePointText}
                  placeholder="例如：银行家算法、进程同步、LRU 页面置换"
                  onChange={(event) => updateForm("knowledgePointText", event.target.value)}
                />
              </label>

              <div className="task-form-field">
                <span>关联资料</span>
                {renderMaterialSelector()}
              </div>

              <label className="task-form-field">
                <span>截止时间</span>
                <input
                  className="field"
                  type="date"
                  value={form.dueDate}
                  onChange={(event) => updateForm("dueDate", event.target.value)}
                />
              </label>

              <label className="task-form-field">
                <span>任务描述</span>
                <textarea
                  className="field"
                  rows={3}
                  value={form.description}
                  placeholder="可补充资料章节、练习范围或完成标准"
                  onChange={(event) => updateForm("description", event.target.value)}
                />
              </label>
            </div>
            <div className="task-modal-actions">
              <button type="button" className="task-btn-secondary" onClick={closeModal}>取消</button>
              <button type="button" className="task-btn-primary" disabled={saving || !form.title.trim()} onClick={saveTask}>
                {saving ? "保存中..." : "保存任务"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
