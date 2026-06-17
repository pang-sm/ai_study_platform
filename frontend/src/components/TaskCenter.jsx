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

const STATUS_LABEL_MAP = {
  todo: "待开始",
  doing: "进行中",
  in_progress: "进行中",
  done: "已完成",
  completed: "已完成",
};

const SOURCE_LABELS = {
  manual: "手动创建",
  code_diagnosis: "诊断生成",
  course_plan: "课程计划",
  learning_plan: "AI 计划",
  system: "系统推荐",
};

const MAX_PLAN_MATERIALS = 10;

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
  const [detailTask, setDetailTask] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);

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
    if (!modalOpen && !planModalOpen && !detailOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [modalOpen, planModalOpen, detailOpen]);

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
      if (selected) {
        return {
          ...prev,
          selectedMaterialIds: prev.selectedMaterialIds.filter((item) => item !== id),
        };
      }
      if (prev.selectedMaterialIds.length >= MAX_PLAN_MATERIALS) {
        return prev;
      }
      return {
        ...prev,
        selectedMaterialIds: [...prev.selectedMaterialIds, id],
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
        const rawDetail = data.detail || "";
        // Mask raw JSON parse errors and show user-friendly message
        if (rawDetail.includes("JSON") || rawDetail.includes("Expecting") || rawDetail.includes("delimiter") || rawDetail.includes("char")) {
          console.error("AI plan generation JSON parse error (original):", rawDetail);
          setPlanError("生成计划失败，AI 输出格式异常，请点击'重新生成'或减少上传文件数量后再试。");
          return;
        }
        setPlanError(rawDetail || "学习计划生成失败，请稍后重试。");
        return;
      }
      setPlanPreview({ ...data, items: Array.isArray(data.items) ? data.items : [] });
    } catch (error) {
      console.error("Failed to generate plan:", error);
      setPlanError("生成计划失败，网络或服务异常，请稍后重试。");
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

  const openDetailModal = (task) => {
    setDetailTask(task);
    setDetailOpen(true);
  };

  const closeDetailModal = () => {
    setDetailOpen(false);
    setDetailTask(null);
  };

  const safeField = (task, ...fields) => {
    for (const f of fields) {
      const val = task?.[f];
      if (val !== undefined && val !== null && val !== "") return val;
    }
    return "";
  };

  const safeArray = (val) => (Array.isArray(val) ? val : []);

  const STATUS_TEXT = {
    todo: "待开始",
    doing: "进行中",
    in_progress: "进行中",
    done: "已完成",
    completed: "已完成",
  };

  const TASK_TYPE_TEXT = {
    review: "复习",
    practice: "练习",
    reading: "阅读资料",
    quiz: "小测",
    summary: "总结",
    code: "编程练习",
    coding: "编程练习",
    material: "阅读资料",
    learning_plan: "AI 计划",
  };

  const SOURCE_TEXT = {
    manual: "手动创建",
    code_diagnosis: "诊断生成",
    course_plan: "课程计划",
    learning_plan: "AI 计划",
    system: "系统推荐",
  };

  const getStatusText = (task) => STATUS_TEXT[task?.status] || task?.status || "待开始";
  const getTaskTypeText = (task) => TASK_TYPE_TEXT[task?.task_type] || task?.task_type || getTaskTypeLabel(task?.task_type);
  const getSourceText = (task) => SOURCE_TEXT[task?.source] || SOURCE_LABELS[task?.source] || task?.source || "手动创建";
  const getTaskTitle = (task) => safeField(task, "title", "name", "task_title") || "未命名任务";
  const getTaskDescription = (task) => safeField(task, "description", "content", "detail");
  const getTaskCourseName = (task, getLabel) => {
    const cid = safeField(task, "course_id", "course", "courseName");
    if (getLabel && cid) return getLabel(cid);
    return cid;
  };
  const getKnowledgePointName = (task) => safeField(task, "knowledge_point_title", "knowledge_point_text", "knowledgePointName", "knowledge_point", "kp_name");
  const getDueDate = (task) => safeField(task, "due_date", "deadline");
  const getEstimatedMinutes = (task) => {
    const meta = task?.metadata;
    if (meta?.estimated_minutes) return Number(meta.estimated_minutes);
    return Number(task?.estimated_minutes) || Number(task?.duration) || Number(task?.minutes) || 0;
  };
  const getRelatedMaterialTitles = (task) => {
    const titles = safeArray(task?.related_material_titles);
    if (titles.length > 0) return titles;
    const singleTitle = safeField(task, "related_material_title", "material_title", "material_filename");
    if (singleTitle) return [singleTitle];
    const meta = task?.metadata;
    if (meta?.material_titles) return safeArray(meta.material_titles);
    return [];
  };
  const getRelatedMaterialIds = (task) => {
    const meta = task?.metadata;
    if (meta?.related_material_ids) return safeArray(meta.related_material_ids);
    if (task?.related_material_id) return [task.related_material_id];
    if (task?.material_ids) return safeArray(task.material_ids);
    return [];
  };
  const getSourceEvidence = (task) => {
    const meta = task?.metadata;
    if (meta?.source_evidence) return safeArray(meta.source_evidence);
    if (task?.source_evidence) return safeArray(task.source_evidence);
    return [];
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
    const isDone = task.status === "done";
    const isDoing = task.status === "doing";
    const courseName = getTaskCourseName(task, getSubjectLabel) || "全部课程";
    const dueDateStr = getDueDate(task) ? formatDate(getDueDate(task)) : "";
    const estMinutes = getEstimatedMinutes(task);
    const timeInfo = dueDateStr || (estMinutes > 0 ? `约${estMinutes}分钟` : "");
    const materialTitles = getRelatedMaterialTitles(task);
    const materialCount = materialTitles.length || getRelatedMaterialIds(task).length || (task.related_material_id ? 1 : 0);

    return (
      <article
        id={`task-row-${task.id}`}
        className={`task-card-v2 ${isDone ? "is-done" : ""} ${highlightTaskId === task.id ? "task-row-highlight" : ""}`}
        key={task.id}
        onClick={() => openDetailModal(task)}
      >
        <div className="task-card-topline">
          <h4>{getTaskTitle(task)}</h4>
          <span className={`task-status-chip task-status-${task.status || "todo"}`}>
            {getStatusText(task)}
          </span>
        </div>
        <div className="task-card-meta-v2">
          <span>{getTaskTypeText(task)}</span>
          {courseName && courseName !== "全部课程" && <span>{courseName}</span>}
          {timeInfo && <span>{timeInfo}</span>}
          {materialCount > 0 && <span>📎 {materialCount}</span>}
        </div>
        <div className="task-card-actions-v2" onClick={(e) => e.stopPropagation()}>
          {isDone ? (
            <>
              <button type="button" className="tiny-button" onClick={() => startPracticeFromTask(task)}>再练一次</button>
            </>
          ) : isDoing ? (
            <>
              <button
                type="button" className="tiny-button"
                disabled={actionTaskId === task.id}
                onClick={() => updateTaskStatus(task, "done")}
              >完成</button>
            </>
          ) : (
            <button
              type="button" className="tiny-button"
              disabled={actionTaskId === task.id}
              onClick={() => updateTaskStatus(task, "doing")}
            >开始</button>
          )}
          <button type="button" className="tiny-button" onClick={(e) => { e.stopPropagation(); openDetailModal(task); }}>详情</button>
          <button
            type="button" className="tiny-button danger"
            disabled={actionTaskId === task.id}
            onClick={() => deleteTask(task)}
          >删除</button>
        </div>
      </article>
    );
  };

  const totalTasks = tasks.length;
  const doneTasks = tasks.filter((task) => task.status === "done" || task.status === "completed").length;
  const progressPercent = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;
  const currentGoalTask = tasks.find((task) => task.status === "doing" || task.status === "in_progress") || tasks[0];
  const currentGoalTitle = currentGoalTask ? getTaskTitle(currentGoalTask) : "第1章 操作系统的核心与系统抽象";
  const minuteValues = tasks.map((task) => getEstimatedMinutes(task)).filter((value) => value > 0);
  const dailyMinutes = Number(planForm.customMinutes) || Number(planForm.dailyMinutes) || (minuteValues.length > 0
    ? Math.round(minuteValues.reduce((sum, value) => sum + value, 0) / minuteValues.length)
    : 60);
  const plannedDays = selectedPlanType?.days || (totalTasks > 0 ? Math.max(1, Math.ceil(totalTasks / 2)) : 7);
  const visiblePlanRows = tasks.slice(0, 5);
  const primaryPlanTask = visiblePlanRows[0];
  const primaryDayRows = primaryPlanTask
    ? [primaryPlanTask, ...(tasksByStatus.todo || []).filter((item) => item.id !== primaryPlanTask.id)].slice(0, 5)
    : [];
  const knowledgeTaskCount = tasks.filter((task) => !/练习|复习/.test(getTaskTypeText(task))).length;
  const practiceTaskCount = tasks.filter((task) => /练习/.test(getTaskTypeText(task))).length;
  const reviewTaskCount = Math.max(totalTasks - knowledgeTaskCount - practiceTaskCount, 0);
  const distributionRows = [
    { label: "知识点学习", value: knowledgeTaskCount, color: "#6f51ff" },
    { label: "练习巩固", value: practiceTaskCount, color: "#62c4e4" },
    { label: "复习巩固", value: reviewTaskCount, color: "#7ed0f0" },
  ];

  const renderPlanAction = (item) => {
    if (item.status === "done" || item.status === "completed") {
      return <button type="button" className="tiny-button" onClick={() => startPracticeFromTask(item)}>再练一次</button>;
    }
    if (item.status === "doing" || item.status === "in_progress") {
      return (
        <button type="button" className="tiny-button" disabled={actionTaskId === item.id} onClick={() => updateTaskStatus(item, "done")}>
          完成
        </button>
      );
    }
    return (
      <button type="button" className="tiny-button" disabled={actionTaskId === item.id} onClick={() => updateTaskStatus(item, "doing")}>
        开始
      </button>
    );
  };

  const planDashboard = (
    <>
      <header className="lp-page-head">
        <div>
          <h2>学习计划</h2>
          <p>制定个性化学习计划，科学安排学习进度</p>
        </div>
      </header>

      <section className="lp-summary-card">
        <div className="lp-current-goal">
          <span>当前学习目标</span>
          <strong>{currentGoalTitle}</strong>
          <small>预计完成时间：2024-06-15</small>
        </div>
        <button type="button" className="lp-edit-goal" onClick={openPlanModal}>编辑目标</button>
        <div className="lp-summary-divider" />
        <div className="lp-stat-card">
          <span>计划学习天数</span>
          <strong>{plannedDays}<small>天</small></strong>
          <p>建议每天 1-2 节</p>
        </div>
        <div className="lp-stat-card">
          <span>每日学习时长</span>
          <strong>{dailyMinutes}<small>分钟</small></strong>
          <p>建议 45-90 分钟</p>
        </div>
        <div className="lp-stat-card">
          <span>总学习任务</span>
          <strong>{totalTasks}<small>个</small></strong>
          <p>知识点 + 练习</p>
        </div>
        <div className="lp-stat-card lp-progress-stat">
          <span>完成进度</span>
          <strong>{progressPercent}<small>%</small></strong>
          <p>{doneTasks} / {totalTasks} 已完成</p>
          <div className="lp-progress-ring" style={{ "--lp-progress": `${progressPercent * 3.6}deg` }}>
            <b>{progressPercent}%</b>
          </div>
        </div>
      </section>

      <div className="lp-content-grid">
        <section className="lp-plan-card">
          <div className="lp-tabs">
            <button type="button" className="active">学习计划</button>
            <button type="button">进度日历</button>
          </div>
          <p className="lp-plan-hint">按章节推进学习路径，循序渐进掌握知识</p>
          {loading ? (
            <div className="task-empty-state-v2 lp-empty-compact">正在加载任务...</div>
          ) : tasks.length === 0 ? (
            <div className="task-empty-state-v2 lp-empty-compact">
              <h3>还没有学习任务</h3>
              <p>可以手动创建任务，也可以让 AI 根据课程进度和资料库生成学习计划。</p>
              <div className="task-empty-actions">
                <button type="button" className="task-btn-primary" onClick={openCreateModal}>创建任务</button>
                <button type="button" className="task-btn-ai" onClick={openPlanModal}>AI 生成计划</button>
              </div>
            </div>
          ) : (
            <div className="lp-chapter-list">
              {visiblePlanRows.map((task, index) => (
                <article
                  id={`task-row-${task.id}`}
                  key={task.id}
                  className={`lp-chapter-item ${index === 0 ? "is-expanded" : ""} ${highlightTaskId === task.id ? "task-row-highlight" : ""}`}
                  onClick={() => openDetailModal(task)}
                >
                  <div className="lp-chapter-head">
                    <span className={`lp-chapter-dot ${task.status === "done" || task.status === "completed" ? "is-done" : task.status === "doing" || task.status === "in_progress" ? "is-doing" : ""}`} />
                    <strong>第{index + 1}章 {getTaskTitle(task)}</strong>
                    <em>{getStatusText(task)}</em>
                    <small>预计 {Math.max(1, Math.ceil((getEstimatedMinutes(task) || dailyMinutes) / Math.max(dailyMinutes, 1)))} 天</small>
                    <small>{task.status === "done" || task.status === "completed" ? 100 : task.status === "doing" || task.status === "in_progress" ? 40 : 0}%</small>
                    <button type="button" onClick={(event) => { event.stopPropagation(); openDetailModal(task); }}>⌄</button>
                  </div>
                  {index === 0 && (
                    <div className="lp-day-list" onClick={(event) => event.stopPropagation()}>
                      {primaryDayRows.map((item, dayIndex) => (
                        <div className="lp-day-row" key={`${item.id}-${dayIndex}`}>
                          <span className={`lp-day-dot ${item.status === "done" || item.status === "completed" ? "is-done" : item.status === "doing" || item.status === "in_progress" ? "is-doing" : ""}`} />
                          <b>Day {dayIndex + 1}</b>
                          <p>{getTaskTitle(item)}</p>
                          <small>{getTaskTypeText(item)}</small>
                          <i />
                          <small>{item.status === "done" || item.status === "completed" ? "1/1" : "0/1"}</small>
                          <div className="lp-row-actions">
                            {renderPlanAction(item)}
                            <button type="button" className="tiny-button danger" disabled={actionTaskId === item.id} onClick={() => deleteTask(item)}>删除</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
              <button type="button" className="lp-adjust-btn" onClick={openPlanModal}>调整计划</button>
            </div>
          )}
        </section>

        <aside className="lp-side-stack">
          <section className="lp-side-card">
            <h3>计划设置</h3>
            <div className="lp-setting-list">
              <div><span>计划类型</span><strong>章节学习（智能）</strong></div>
              <div><span>开始日期</span><strong>2024-05-01（今天）</strong></div>
              <div><span>每日学习时长</span><strong>{dailyMinutes} 分钟</strong></div>
              <div><span>每周学习天数</span><strong>5 天（工作日）</strong></div>
              <div><span>复习安排</span><strong>智能复习（艾宾浩斯）</strong></div>
            </div>
            <button type="button" className="lp-outline-wide" onClick={openPlanModal}>修改计划设置</button>
          </section>
          <section className="lp-side-card">
            <h3>任务类型分布</h3>
            <div className="lp-distribution">
              <div className="lp-donut">
                <strong>{totalTasks}</strong>
                <span>总任务数</span>
              </div>
              <div className="lp-legend">
                {distributionRows.map((row) => (
                  <div key={row.label}>
                    <i style={{ background: row.color }} />
                    <span>{row.label}</span>
                    <strong>{row.value} ({totalTasks > 0 ? Math.round((row.value / totalTasks) * 100) : 0}%)</strong>
                  </div>
                ))}
              </div>
            </div>
          </section>
          <section className="lp-side-card">
            <h3>学习建议</h3>
            <div className="lp-advice-list">
              <div className="purple"><b>循序渐进，稳步提升</b><span>按照计划完成每日任务，不要急于求成，保证学习质量。</span></div>
              <div className="green"><b>及时复习，巩固记忆</b><span>系统将自动安排复习任务，帮助你增强知识记忆效果。</span></div>
              <div className="orange"><b>多做练习，学以致用</b><span>通过练习检验学习效果，发现薄弱环节并及时加强。</span></div>
            </div>
          </section>
        </aside>
      </div>
    </>
  );

  return (
    <section className="chat-panel chat-panel--wide task-center-panel task-center-v2 learning-plan-page">
      {planDashboard}

      {planSuccess && (
        <div className="task-success-banner">
          <span>{planSuccess}</span>
          <button type="button" onClick={() => setPlanSuccess("")}>关闭</button>
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
                <span className="task-plan-label">
                  资料库资料
                  <span className="task-plan-material-count">
                    已选择 {planForm.selectedMaterialIds.length} / {MAX_PLAN_MATERIALS} 份资料
                  </span>
                </span>
                {materialsLoading ? (
                  <p className="task-muted">正在加载资料...</p>
                ) : materials.length === 0 ? (
                  <p className="task-muted">当前课程暂无资料，将根据学习进度降级生成。</p>
                ) : (
                  <>
                    <div className="task-plan-materials">
                      {materials.map((material) => {
                        const selected = planForm.selectedMaterialIds.includes(Number(material.id));
                        const atLimit = !selected && planForm.selectedMaterialIds.length >= MAX_PLAN_MATERIALS;
                        return (
                          <button
                            type="button"
                            key={material.id}
                            className={`task-plan-material ${selected ? "is-selected" : ""}`}
                            onClick={() => togglePlanMaterial(material.id)}
                            disabled={atLimit}
                            title={atLimit ? `最多选择 ${MAX_PLAN_MATERIALS} 份资料，系统会自动提取最相关片段参与生成。` : getMaterialTitle(material)}
                          >
                            <span>{getMaterialTitle(material)}</span>
                            <small>{material.file_type || "资料"} · {isIndexedMaterial(material) ? "已索引" : "未索引"}</small>
                          </button>
                        );
                      })}
                    </div>
                    {planForm.selectedMaterialIds.length >= MAX_PLAN_MATERIALS && (
                      <p className="task-plan-hint" style={{ color: "#b45309", margin: "2px 0 0" }}>
                        最多选择 {MAX_PLAN_MATERIALS} 份资料，系统会自动提取最相关片段参与生成。
                      </p>
                    )}
                  </>
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
                  {planPreview.fallback_used && (
                    <div className="task-plan-fallback-warning">
                      <span>{planPreview.warning || "AI 输出格式异常，已为你生成基础学习计划，可点击重新生成获得更完整计划。"}</span>
                    </div>
                  )}
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

      {detailOpen && detailTask && (
        <div className="task-modal-overlay" role="presentation" onClick={closeDetailModal}>
          <div className="task-modal-card task-detail-modal-card" role="dialog" aria-modal="true" aria-labelledby="task-detail-modal-title" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="task-modal-close" onClick={closeDetailModal} aria-label="关闭">×</button>
            <div className="task-modal-header">
              <h3 id="task-detail-modal-title">任务详情</h3>
            </div>
            <div className="task-modal-body">
              {/* 基本信息 */}
              <div className="task-detail-section">
                <h5>基本信息</h5>
                <h4 className="task-detail-title">{getTaskTitle(detailTask)}</h4>
                <div className="task-detail-row" style={{ marginTop: 10 }}>
                  <span className={`task-detail-tag status-tag ${detailTask.status === "done" ? "" : ""}`} style={detailTask.status === "todo" ? { background: "#f1f5f9", color: "#475569", border: "1px solid #e2e8f0" } : detailTask.status === "doing" ? { background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a" } : {}}>
                    {getStatusText(detailTask)}
                  </span>
                  <span className="task-detail-tag type-tag">{getTaskTypeText(detailTask)}</span>
                </div>
                <p style={{ marginTop: 10 }}>
                  <strong>所属课程：</strong>{getTaskCourseName(detailTask, getSubjectLabel) || "未绑定课程"}
                </p>
                {getEstimatedMinutes(detailTask) > 0 && (
                  <p><strong>预计用时：</strong>{getEstimatedMinutes(detailTask)} 分钟</p>
                )}
                {getDueDate(detailTask) && (
                  <p><strong>截止时间：</strong>{formatDate(getDueDate(detailTask))}</p>
                )}
                {detailTask.source && (
                  <p><strong>来源：</strong>{getSourceText(detailTask)}</p>
                )}
              </div>

              {/* 学习内容 */}
              <div className="task-detail-section">
                <h5>学习内容</h5>
                {getTaskDescription(detailTask) ? (
                  <p style={{ whiteSpace: "pre-wrap" }}>{getTaskDescription(detailTask)}</p>
                ) : (
                  <p className="task-detail-empty">暂无任务描述</p>
                )}
                {detailTask.metadata?.reason && (
                  <p style={{ marginTop: 8 }}><strong>安排原因：</strong>{detailTask.metadata.reason}</p>
                )}
              </div>

              {/* 关联知识点 */}
              <div className="task-detail-section">
                <h5>关联知识点</h5>
                {getKnowledgePointName(detailTask) ? (
                  <p>{getKnowledgePointName(detailTask)}</p>
                ) : (
                  <p className="task-detail-empty">未绑定知识点</p>
                )}
              </div>

              {/* 关联资料 */}
              <div className="task-detail-section">
                <h5>关联资料</h5>
                {(() => {
                  const titles = getRelatedMaterialTitles(detailTask);
                  const ids = getRelatedMaterialIds(detailTask);
                  const singleId = detailTask.related_material_id;
                  const singleTitle = detailTask.related_material_title || detailTask.material_filename || detailTask.material_title;
                  if (titles.length > 0) {
                    return (
                      <>
                        <p>共 {titles.length} 份资料</p>
                        <div className="task-detail-materials">
                          {titles.map((title, idx) => (
                            <div className="task-detail-material-item" key={idx}>
                              <span>📄</span>
                              <span>{title}</span>
                            </div>
                          ))}
                        </div>
                      </>
                    );
                  }
                  if (singleTitle) {
                    return (
                      <div className="task-detail-materials">
                        <div className="task-detail-material-item">
                          <span>📄</span>
                          <span>{singleTitle}</span>
                        </div>
                      </div>
                    );
                  }
                  if (ids.length > 0 || singleId) {
                    return <p>关联资料 ID：{(ids.length > 0 ? ids : [singleId]).join(", ")}</p>;
                  }
                  return <p className="task-detail-empty">未关联资料</p>;
                })()}
              </div>

              {/* AI 生成依据 */}
              <div className="task-detail-section">
                <h5>AI 生成依据</h5>
                {(() => {
                  const evidence = getSourceEvidence(detailTask);
                  const examAnalysis = detailTask.metadata?.exam_analysis;
                  if (evidence.length > 0) {
                    return (
                      <div>
                        {evidence.map((ev, idx) => (
                          <div className="task-detail-evidence" key={idx}>{typeof ev === "string" ? ev : JSON.stringify(ev)}</div>
                        ))}
                      </div>
                    );
                  }
                  if (examAnalysis) {
                    return (
                      <div>
                        {examAnalysis.key_knowledge_points?.length > 0 && (
                          <p><strong>关键知识点：</strong>{examAnalysis.key_knowledge_points.join("、")}</p>
                        )}
                        {examAnalysis.suggestions?.length > 0 && (
                          <div>
                            <strong>复习建议：</strong>
                            {examAnalysis.suggestions.map((s, idx) => (
                              <div className="task-detail-evidence" key={idx}>{s}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  }
                  return <p className="task-detail-empty">暂无生成依据</p>;
                })()}
              </div>
            </div>
            <div className="task-modal-actions">
              {detailTask.status === "done" ? (
                <button type="button" className="task-btn-secondary" onClick={(e) => { closeDetailModal(); startPracticeFromTask(detailTask); }}>再练一次</button>
              ) : detailTask.status === "doing" ? (
                <button type="button" className="task-btn-primary" disabled={actionTaskId === detailTask.id} onClick={() => updateTaskStatus(detailTask, "done")}>完成</button>
              ) : (
                <button type="button" className="task-btn-primary" disabled={actionTaskId === detailTask.id} onClick={() => updateTaskStatus(detailTask, "doing")}>开始</button>
              )}
              <button type="button" className="task-btn-secondary" onClick={() => { closeDetailModal(); openEditModal(detailTask); }}>编辑</button>
              <button type="button" className="task-btn-secondary danger" disabled={actionTaskId === detailTask.id} onClick={() => { closeDetailModal(); deleteTask(detailTask); }} style={{ color: "#dc2626" }}>删除</button>
              <button type="button" className="task-btn-secondary" onClick={closeDetailModal}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
