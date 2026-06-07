import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";
const TASK_COURSE_FILTER_KEY = "ai_study_task_center_course_filter";

const TASK_TYPE_OPTIONS = ["复习资料", "完成练习", "整理笔记", "查漏补缺", "考前复盘", "自定义"];

const TASK_TYPE_LABELS = {
  read_material: "复习资料",
  ask_ai: "AI 问答",
  code_practice: "代码练习",
  challenge: "完成练习",
  review: "复习资料",
  practice: "练习",
  reading: "阅读资料",
  quiz: "小测",
  summary: "总结",
  code: "编程练习",
  coding: "编程练习",
  material: "阅读资料",
  learning_plan: "学习计划",
  custom: "自定义",
};

const PLAN_SCENES = [
  { value: "daily", label: "日常学习计划", hint: "结合课程进度、未学知识点和薄弱点生成。" },
  { value: "exam", label: "期末考试复习计划", hint: "结合考试范围、资料库和试卷题型生成。" },
  { value: "weakness", label: "错题薄弱点复盘计划", hint: "优先围绕错题、负向事件和薄弱知识点。" },
  { value: "coding", label: "编程训练计划", hint: "结合编程练习记录和未掌握知识点。" },
];

const PLAN_TYPES = [
  { value: "today", label: "今日计划", days: 1 },
  { value: "three_day", label: "3 天弱计划", days: 3 },
  { value: "seven_day", label: "7 天学习计划", days: 7 },
  { value: "exam", label: "考前冲刺计划", days: 7 },
  { value: "coding", label: "编程训练计划", days: 5 },
];

const DAILY_MINUTES_OPTIONS = [30, 60, 90];

const PLAN_TASK_TYPE_LABELS = {
  review: "复习",
  practice: "练习",
  reading: "阅读资料",
  quiz: "小测",
  code: "编程练习",
  coding: "编程练习",
  material: "阅读资料",
  summary: "总结",
  learning_plan: "学习计划",
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
  learning_plan: "AI 计划",
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

const emptyPlanForm = {
  planScene: "daily",
  planType: "today",
  courseId: "",
  dailyMinutes: 60,
  customMinutes: "",
  goal: "",
  examScopeText: "",
  selectedMaterialIds: [],
  scopeFiles: [],
  paperFiles: [],
};

function getTaskTypeLabel(value) {
  return TASK_TYPE_LABELS[value] || value || "学习任务";
}

function getPlanTaskTypeLabel(value) {
  return PLAN_TASK_TYPE_LABELS[value] || getTaskTypeLabel(value);
}

function getSavedTaskCourseFilter(fallback = "") {
  try {
    return localStorage.getItem(TASK_COURSE_FILTER_KEY) || fallback;
  } catch {
    return fallback;
  }
}

function saveTaskCourseFilter(courseId) {
  try {
    localStorage.setItem(TASK_COURSE_FILTER_KEY, courseId || "");
  } catch {
    // ignore storage failures
  }
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
  const [courseFilter, setCourseFilter] = useState(() => getSavedTaskCourseFilter(subject || ""));
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
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [planForm, setPlanForm] = useState({ ...emptyPlanForm, courseId: subject || "" });
  const [planPreview, setPlanPreview] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planImporting, setPlanImporting] = useState(false);
  const [planError, setPlanError] = useState("");
  const [planSuccess, setPlanSuccess] = useState("");

  const normalizedFilterCourse = useMemo(
    () => normalizeSubject(courseFilter, "") || "",
    [courseFilter, normalizeSubject]
  );

  const normalizedFormCourse = useMemo(
    () => normalizeSubject(form.courseId, "") || "",
    [form.courseId, normalizeSubject]
  );

  const normalizedPlanCourse = useMemo(
    () => normalizeSubject(planForm.courseId, "") || "",
    [planForm.courseId, normalizeSubject]
  );

  const selectedPlanType = useMemo(
    () => PLAN_TYPES.find((item) => item.value === planForm.planType) || PLAN_TYPES[0],
    [planForm.planType]
  );

  const planItems = Array.isArray(planPreview?.items) ? planPreview.items : [];

  const planTotalMinutes = useMemo(() => {
    if (Number.isFinite(Number(planPreview?.total_minutes))) return Number(planPreview.total_minutes);
    return planItems.reduce((sum, item) => sum + (Number(item?.estimated_minutes) || 0), 0);
  }, [planItems, planPreview?.total_minutes]);

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
    setCourseFilter(getSavedTaskCourseFilter(subject || ""));
  }, [subject]);

  useEffect(() => {
    saveTaskCourseFilter(courseFilter);
  }, [courseFilter]);

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
    if (!modalOpen && !planModalOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [modalOpen, planModalOpen]);

  useEffect(() => {
    loadTasks();
  }, [user?.username, normalizedFilterCourse]);

  useEffect(() => {
    if (!modalOpen) return;
    loadKnowledgePoints(normalizedFormCourse);
    loadMaterials(normalizedFormCourse);
  }, [modalOpen, normalizedFormCourse, user?.username]);

  useEffect(() => {
    if (!planModalOpen) return;
    loadMaterials(normalizedPlanCourse);
  }, [planModalOpen, normalizedPlanCourse, user?.username]);

  const loadTasks = async (courseOverride = normalizedFilterCourse) => {
    if (!user?.username) return;
    setLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      if (courseOverride) query.set("course_id", courseOverride);
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

  const openPlanModal = () => {
    setPlanForm({ ...emptyPlanForm, courseId: normalizedFilterCourse || subject || "" });
    setPlanPreview(null);
    setPlanError("");
    setPlanModalOpen(true);
  };

  const closePlanModal = () => {
    if (planLoading || planImporting) return;
    setPlanModalOpen(false);
    setPlanPreview(null);
    setPlanError("");
  };

  const updatePlanForm = (field, value) => {
    setPlanForm((prev) => ({ ...prev, [field]: value }));
    setPlanPreview(null);
    setPlanError("");
  };

  const updatePlanFiles = (field, files) => {
    setPlanForm((prev) => ({
      ...prev,
      [field]: [...prev[field], ...Array.from(files || [])].slice(0, 3),
    }));
    setPlanPreview(null);
    setPlanError("");
  };

  const removePlanFile = (field, index) => {
    setPlanForm((prev) => ({
      ...prev,
      [field]: prev[field].filter((_, itemIndex) => itemIndex !== index),
    }));
    setPlanPreview(null);
    setPlanError("");
  };

  const togglePlanMaterial = (materialId) => {
    setPlanForm((prev) => {
      const id = Number(materialId);
      const selected = prev.selectedMaterialIds.includes(id);
      return {
        ...prev,
        selectedMaterialIds: selected
          ? prev.selectedMaterialIds.filter((item) => item !== id)
          : [...prev.selectedMaterialIds, id].slice(0, 5),
      };
    });
    setPlanPreview(null);
    setPlanError("");
  };

  const getPlanMinutes = () => {
    if (planForm.dailyMinutes === 0) {
      const customValue = parseInt(planForm.customMinutes, 10);
      return Number.isFinite(customValue) && customValue > 0 ? customValue : 60;
    }
    return planForm.dailyMinutes;
  };

  const generatePlanPreview = async () => {
    if (!user?.username) return;
    setPlanLoading(true);
    setPlanError("");
    setPlanSuccess("");
    try {
      const formData = new FormData();
      formData.append("username", user.username);
      formData.append("course_id", normalizedPlanCourse);
      formData.append("plan_type", planForm.planType);
      formData.append("plan_scene", planForm.planScene);
      formData.append("days", String(selectedPlanType.days));
      formData.append("goal", planForm.goal.trim());
      formData.append("daily_minutes", String(getPlanMinutes()));
      formData.append("exam_scope_text", planForm.examScopeText.trim());
      formData.append("selected_material_ids", JSON.stringify(planForm.selectedMaterialIds));
      planForm.scopeFiles.forEach((file) => formData.append("scope_files", file));
      planForm.paperFiles.forEach((file) => formData.append("paper_files", file));

      const res = await fetch(`${API_BASE}/learning/plans/generate-preview-advanced`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPlanError(data.detail || "学习计划生成失败，请稍后重试。");
        return;
      }
      setPlanPreview({ ...data, items: Array.isArray(data.items) ? data.items : [] });
    } catch (error) {
      console.error("Failed to generate plan:", error);
      setPlanError("学习计划生成失败，请稍后重试。");
    } finally {
      setPlanLoading(false);
    }
  };

  const importPlanTasks = async () => {
    if (!user?.username || planItems.length === 0) return;
    setPlanImporting(true);
    setPlanError("");
    try {
      const res = await fetch(`${API_BASE}/learning/plans/import-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          plan_title: planPreview?.plan_title || "AI 学习计划",
          items: planItems,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPlanError(data.detail || "创建任务失败，请稍后重试。");
        return;
      }
      const count = Number(data.created_count || data.count || planItems.length);
      setPlanSuccess(`已生成 ${count} 个学习任务`);
      setPlanModalOpen(false);
      setPlanPreview(null);
      const nextCourseFilter = normalizedPlanCourse || normalizedFilterCourse;
      if (nextCourseFilter && nextCourseFilter !== normalizedFilterCourse) {
        saveTaskCourseFilter(nextCourseFilter);
        setCourseFilter(nextCourseFilter);
      }
      await loadTasks(nextCourseFilter);
    } catch (error) {
      console.error("Failed to import plan tasks:", error);
      setPlanError("创建任务失败，请稍后重试。");
    } finally {
      setPlanImporting(false);
    }
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
          <p>把资料、知识点和练习安排成可执行计划。</p>
        </div>
        <div className="task-title-actions">
          <button type="button" className="task-btn-primary" onClick={openCreateModal}>
            + 新建任务
          </button>
          <button type="button" className="task-btn-ai" onClick={openPlanModal}>
            ✨ AI 生成计划
          </button>
        </div>
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

      {planSuccess && (
        <div className="task-success-banner">
          <span>{planSuccess}</span>
          <button type="button" onClick={() => setPlanSuccess("")}>关闭</button>
        </div>
      )}

      {loading ? (
        <div className="task-empty-state-v2">正在加载任务...</div>
      ) : tasks.length === 0 ? (
        <div className="task-empty-state-v2">
          <h3>还没有学习任务</h3>
          <p>可以手动创建任务，也可以让 AI 根据课程进度和资料库生成学习计划。</p>
          <div className="task-empty-actions">
            <button type="button" className="task-btn-primary" onClick={openCreateModal}>创建任务</button>
            <button type="button" className="task-btn-ai" onClick={openPlanModal}>✨ AI 生成计划</button>
          </div>
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

      {planModalOpen && (
        <div className="task-modal-overlay" role="presentation">
          <div className="task-modal-card task-plan-modal-card" role="dialog" aria-modal="true" aria-labelledby="task-plan-modal-title">
            <button type="button" className="task-modal-close" onClick={closePlanModal} aria-label="关闭">×</button>
            <div className="task-modal-header">
              <h3 id="task-plan-modal-title">AI 生成学习计划</h3>
              <p>选择课程、目标和时间，系统会自动拆分为学习任务。</p>
            </div>
            <div className="task-modal-body">
              <div className="task-plan-group">
                <h4>基础设置</h4>
                <p>当前学习进度默认参与生成，AI 会优先考虑未学知识点和薄弱点。</p>
              </div>

              <div className="task-plan-section">
                <span className="task-plan-label">计划场景</span>
                <div className="task-plan-options task-plan-scene-options">
                  {PLAN_SCENES.map((item) => (
                    <button
                      type="button"
                      key={item.value}
                      className={`task-plan-option task-plan-scene-option ${planForm.planScene === item.value ? "is-selected" : ""}`}
                      onClick={() => updatePlanForm("planScene", item.value)}
                      title={item.hint}
                    >
                      <strong>{item.label}</strong>
                      <small>{item.hint}</small>
                    </button>
                  ))}
                </div>
              </div>

              <div className="task-plan-section">
                <span className="task-plan-label">计划类型</span>
                <div className="task-plan-options">
                  {PLAN_TYPES.map((item) => (
                    <button
                      type="button"
                      key={item.value}
                      className={`task-plan-option ${planForm.planType === item.value ? "is-selected" : ""}`}
                      onClick={() => updatePlanForm("planType", item.value)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <label className="task-form-field">
                <span>课程范围</span>
                <select
                  className="field"
                  value={planForm.courseId}
                  onChange={(event) => {
                    setPlanForm((prev) => ({
                      ...prev,
                      courseId: event.target.value,
                      selectedMaterialIds: [],
                    }));
                    setPlanPreview(null);
                    setPlanError("");
                  }}
                >
                  <option value="">全部课程</option>
                  {courseOptions.map((item) => (
                    <option key={item} value={item}>{getSubjectLabel(item)}</option>
                  ))}
                </select>
              </label>

              <div className="task-plan-section">
                <span className="task-plan-label">每日学习时间</span>
                <div className="task-plan-options task-plan-time-options">
                  {DAILY_MINUTES_OPTIONS.map((minutes) => (
                    <button
                      type="button"
                      key={minutes}
                      className={`task-plan-option ${planForm.dailyMinutes === minutes ? "is-selected" : ""}`}
                      onClick={() => {
                        setPlanForm((prev) => ({
                          ...prev,
                          dailyMinutes: minutes,
                          customMinutes: "",
                        }));
                        setPlanPreview(null);
                        setPlanError("");
                      }}
                    >
                      {minutes} 分钟
                    </button>
                  ))}
                  <label className={`task-plan-custom ${planForm.dailyMinutes === 0 ? "is-selected" : ""}`}>
                    <span>自定义</span>
                    <input
                      type="number"
                      min="10"
                      max="240"
                      value={planForm.customMinutes}
                      placeholder="分钟"
                      onChange={(event) => {
                        setPlanForm((prev) => ({
                          ...prev,
                          dailyMinutes: 0,
                          customMinutes: event.target.value,
                        }));
                        setPlanPreview(null);
                        setPlanError("");
                      }}
                    />
                  </label>
                </div>
              </div>

              <label className="task-form-field">
                <span>学习目标</span>
                <input
                  className="field"
                  value={planForm.goal}
                  placeholder="例如：复习 C 语言基础，准备期末考试"
                  onChange={(event) => updatePlanForm("goal", event.target.value)}
                />
              </label>

              <div className="task-plan-group">
                <h4>学习依据</h4>
                <p>
                  {planForm.planScene === "exam"
                    ? "可以补充考试范围、选择课程资料，并上传往年卷或模拟卷。"
                    : "资料和考试范围为可选项，不填写也会根据学习进度生成。"}
                </p>
              </div>

              <div className="task-plan-section">
                <span className="task-plan-label">资料库资料</span>
                {materialsLoading ? (
                  <p className="task-muted">正在加载资料...</p>
                ) : materials.length === 0 ? (
                  <p className="task-muted">当前课程暂无资料，将根据学习进度降级生成。</p>
                ) : (
                  <div className="task-plan-materials">
                    {materials.slice(0, 8).map((material) => {
                      const selected = planForm.selectedMaterialIds.includes(Number(material.id));
                      return (
                        <button
                          type="button"
                          key={material.id}
                          className={`task-plan-material ${selected ? "is-selected" : ""}`}
                          onClick={() => togglePlanMaterial(material.id)}
                        >
                          <span>{getMaterialTitle(material)}</span>
                          <small>{material.file_type || "资料"} · {isIndexedMaterial(material) ? "已索引" : "未索引"}</small>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {planForm.planScene === "exam" && (
                <>
                  <label className="task-form-field">
                    <span>考试范围</span>
                    <textarea
                      className="field"
                      rows={3}
                      value={planForm.examScopeText}
                      placeholder="例如：第 1-6 章，重点包括变量、循环、数组、函数、指针、结构体。"
                      onChange={(event) => updatePlanForm("examScopeText", event.target.value)}
                    />
                  </label>

                  {!planForm.examScopeText.trim() && planForm.scopeFiles.length === 0 && (
                    <p className="task-plan-hint">未提供考试范围，将根据课程资料和学习进度生成复习计划。</p>
                  )}

                  <div className="task-plan-upload-grid">
                    <div className="task-plan-upload">
                      <span className="task-plan-label">考试范围文件</span>
                      <input
                        type="file"
                        multiple
                        aria-label="上传考试范围文件"
                        accept=".pdf,.docx,.pptx,.txt,.md,image/*"
                        onInput={(event) => {
                          updatePlanFiles("scopeFiles", event.currentTarget.files);
                        }}
                        onChange={(event) => {
                          updatePlanFiles("scopeFiles", event.target.files);
                          event.target.value = "";
                        }}
                      />
                      <div className="task-plan-file-list">
                        {planForm.scopeFiles.map((file, index) => (
                          <span key={`${file.name}-${index}`}>
                            {file.name}
                            <button type="button" onClick={() => removePlanFile("scopeFiles", index)}>移除</button>
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="task-plan-upload">
                      <span className="task-plan-label">往年卷 / 模拟卷</span>
                      <input
                        type="file"
                        multiple
                        aria-label="上传往年卷或模拟卷"
                        accept=".pdf,.docx,.txt,.md,image/*"
                        onInput={(event) => {
                          updatePlanFiles("paperFiles", event.currentTarget.files);
                        }}
                        onChange={(event) => {
                          updatePlanFiles("paperFiles", event.target.files);
                          event.target.value = "";
                        }}
                      />
                      <div className="task-plan-file-list">
                        {planForm.paperFiles.map((file, index) => (
                          <span key={`${file.name}-${index}`}>
                            {file.name}
                            <button type="button" onClick={() => removePlanFile("paperFiles", index)}>移除</button>
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )}

              {planError && <div className="task-plan-error">{planError}</div>}

              {planPreview && (
                <div className="task-plan-preview">
                  <div className="task-plan-preview-header">
                    <div>
                      <h4>{planPreview.plan_title || "生成计划预览"}</h4>
                      <p>
                        已生成 {planItems.length} 个任务，预计学习时间 {planTotalMinutes || getPlanMinutes()} 分钟。
                      </p>
                      {Array.isArray(planPreview.key_knowledge_points) && planPreview.key_knowledge_points.length > 0 && (
                        <div className="task-plan-preview-tags">
                          {planPreview.key_knowledge_points.slice(0, 8).map((item, index) => (
                            <span key={`${item}-${index}`}>{item}</span>
                          ))}
                        </div>
                      )}
                      {Array.isArray(planPreview.question_type_analysis) && planPreview.question_type_analysis.length > 0 && (
                        <div className="task-plan-analysis">
                          <strong>题型分析</strong>
                          {planPreview.question_type_analysis.map((item, index) => (
                            <span key={index}>{item.type || "未知题型"}：{item.count ?? 0}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="task-plan-preview-list">
                    {planItems.length === 0 ? (
                      <p className="task-muted">本次没有生成可创建的任务，请调整目标后重新生成。</p>
                    ) : (
                      planItems.map((item, index) => {
                        const courseLabel = item?.course_id ? getSubjectLabel(item.course_id) : "全部课程";
                        const minutes = Number(item?.estimated_minutes) || getPlanMinutes();
                        const knowledgeLabel = item?.knowledge_point_name || item?.knowledge_point_title || item?.knowledge_point_text || item?.knowledge_point || "";
                        return (
                          <article className="task-plan-preview-item" key={`${item?.title || "task"}-${index}`}>
                            <div className="task-plan-preview-index">{index + 1}</div>
                            <div className="task-plan-preview-main">
                              <h5>{item?.title || `学习任务 ${index + 1}`}</h5>
                              {item?.description && <p>{item.description}</p>}
                              {item?.reason && <p className="task-plan-preview-reason">安排原因：{item.reason}</p>}
                              <div className="task-plan-preview-meta">
                                <span>{courseLabel}</span>
                                <span>{minutes} 分钟</span>
                                <span>{getPlanTaskTypeLabel(item?.task_type)}</span>
                                {knowledgeLabel && <span>知识点：{knowledgeLabel}</span>}
                                {Array.isArray(item?.related_material_ids) && item.related_material_ids.length > 0 && <span>关联资料：{item.related_material_ids.length} 份</span>}
                              </div>
                            </div>
                          </article>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="task-modal-actions">
              <button type="button" className="task-btn-secondary" onClick={closePlanModal} disabled={planLoading || planImporting}>
                取消
              </button>
              {planPreview ? (
                <>
                  <button type="button" className="task-btn-secondary" onClick={generatePlanPreview} disabled={planLoading || planImporting}>
                    {planLoading ? "生成中..." : "重新生成"}
                  </button>
                  <button type="button" className="task-btn-primary" onClick={importPlanTasks} disabled={planImporting || planItems.length === 0}>
                    {planImporting ? "创建中..." : "确认创建任务"}
                  </button>
                </>
              ) : (
                <button type="button" className="task-btn-primary" onClick={generatePlanPreview} disabled={planLoading}>
                  {planLoading ? "生成中..." : "生成计划预览"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
