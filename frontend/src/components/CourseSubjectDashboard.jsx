import { useEffect, useState, lazy, Suspense } from "react";
import ExamChat from "./ExamChat.jsx";
import ExamStudyPlan from "./ExamStudyPlan.jsx";
import KnowledgeLearningPage from "./KnowledgeLearningPage.jsx";
const LearningReportCenter = lazy(() => import("./LearningReportCenter.jsx"));
import "./CourseSubjectDashboard.css";

const COURSE_TRACK = "course_learning";
const EXAM_TARGET_OPTIONS = ["及格", "稳过", "高分", "自定义"];

const NAV_ITEMS = [
  { key: "overview", label: "首页", icon: "◆" },
  { key: "chat", label: "AI 问答", icon: "☵" },
  { key: "materials", label: "资料库", icon: "▣" },
  { key: "knowledge", label: "知识脉络", icon: "⌘" },
  { key: "plan", label: "学习计划", icon: "▤" },
  { key: "report", label: "学习报告", icon: "▧" },
];

const EXAM_CRAM_NAV_ITEMS = NAV_ITEMS.filter((item) => item.key !== "report");

const MATERIAL_CARDS = [
  { key: "slides", label: "课件讲义", tone: "purple", match: ["ppt", "课件", "讲义", "slides"] },
  { key: "exercises", label: "习题集", tone: "blue", match: ["习题", "作业", "exercise", "homework"] },
  { key: "references", label: "参考资料", tone: "green", match: ["教材", "参考", "book", "paper"] },
  { key: "examples", label: "代码示例", tone: "orange", match: ["代码", "示例", "code", "demo"] },
];

const COURSE_QUESTION_TYPE_TEMPLATES = {
  "计算机网络": [
    { title: "协议分层", examples: ["TCP/IP 与 OSI 对比", "各层核心协议", "网络设备工作层次"] },
    { title: "计算题", examples: ["子网划分", "传输时延与传播时延", "CRC 校验"] },
    { title: "流程题", examples: ["TCP 建连与释放", "ARP 解析", "DNS 查询"] },
    { title: "综合分析", examples: ["拥塞控制", "应用层协议对比", "网络故障定位"] },
  ],
  "数据结构": [
    { title: "概念简答", examples: ["线性表与链表", "栈和队列", "图的存储结构"] },
    { title: "算法分析", examples: ["时间复杂度", "递归过程", "查找与排序"] },
    { title: "树图计算", examples: ["二叉树遍历", "哈夫曼树", "最短路径"] },
    { title: "代码题", examples: ["链表操作", "树遍历实现", "排序算法实现"] },
  ],
  "操作系统": [
    { title: "进程线程", examples: ["进程状态转换", "线程模型", "同步互斥"] },
    { title: "调度与死锁", examples: ["调度算法", "银行家算法", "死锁条件"] },
    { title: "存储管理", examples: ["分页分段", "页面置换", "虚拟内存"] },
    { title: "文件系统", examples: ["目录结构", "磁盘调度", "文件分配"] },
  ],
  "数据库系统": [
    { title: "关系模型", examples: ["关系代数", "键与约束", "关系完整性"] },
    { title: "SQL", examples: ["多表查询", "聚合分组", "嵌套查询"] },
    { title: "规范化", examples: ["函数依赖", "范式判断", "模式分解"] },
    { title: "事务与索引", examples: ["并发控制", "恢复机制", "索引选择"] },
  ],
  "编译原理": [
    { title: "语言基础", examples: ["文法与语言", "推导与归约", "二义性判断"] },
    { title: "词法分析", examples: ["正规式", "NFA/DFA", "词法错误处理"] },
    { title: "语法分析", examples: ["FIRST/FOLLOW", "LL(1)", "LR 分析"] },
    { title: "语义与中间代码", examples: ["属性文法", "语义分析", "中间代码生成"] },
  ],
  "Python 程序设计": [
    { title: "语法输出题", examples: ["列表/字典", "函数参数", "异常处理"] },
    { title: "程序阅读", examples: ["循环与递归", "字符串处理", "文件读写"] },
    { title: "代码题", examples: ["数据清洗", "类与对象", "算法实现"] },
    { title: "设计题", examples: ["模块拆分", "输入输出", "边界处理"] },
  ],
  "Java 程序设计": [
    { title: "语法输出题", examples: ["集合框架", "异常处理", "泛型基础"] },
    { title: "程序阅读", examples: ["继承多态", "接口抽象类", "线程基础"] },
    { title: "代码题", examples: ["类设计", "集合处理", "IO 操作"] },
    { title: "设计题", examples: ["封装职责", "对象协作", "异常边界"] },
  ],
  "C语言程序设计": [
    { title: "语法输出题", examples: ["指针与数组", "结构体", "函数调用"] },
    { title: "程序阅读", examples: ["循环递归", "字符串处理", "内存地址"] },
    { title: "代码题", examples: ["数组处理", "链表基础", "文件操作"] },
    { title: "设计题", examples: ["输入校验", "模块函数", "边界条件"] },
  ],
};

const COURSE_TEMPLATE_ALIASES = [
  { match: ["计算机网络", "computer_network", "网络"], key: "计算机网络" },
  { match: ["数据结构", "data_structure"], key: "数据结构" },
  { match: ["操作系统", "operating_system"], key: "操作系统" },
  { match: ["数据库", "database"], key: "数据库系统" },
  { match: ["编译原理", "compiler"], key: "编译原理" },
  { match: ["python"], key: "Python 程序设计" },
  { match: ["java"], key: "Java 程序设计" },
  { match: ["c语言", "c 程序", "c_programming"], key: "C语言程序设计" },
];

const GENERAL_QUESTION_TYPES = [
  { title: "概念简答", examples: ["核心术语", "基本原理", "易混概念"] },
  { title: "计算/推导", examples: ["公式应用", "过程推导", "结果校验"] },
  { title: "应用分析", examples: ["场景判断", "方案比较", "错误定位"] },
  { title: "综合题", examples: ["知识串联", "材料分析", "期末压轴"] },
];

const TASK_TYPE_LABELS = {
  knowledge: "知识整理",
  review: "冲刺复盘",
  chapter_practice: "章节任务",
};

const STATUS_LABELS = {
  completed: "已完成",
  in_progress: "进行中",
  not_started: "未开始",
  review_due: "待复盘",
  overdue: "已逾期",
};

function textValue(...values) {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return "";
}

function parseDateValue(value) {
  const text = textValue(value);
  if (!text) return null;
  const normalized = text.replace(/[./]/g, "-");
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDaysLeft(examDate) {
  const date = parseDateValue(examDate);
  if (!date) return "";
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);
  const days = Math.ceil((date.getTime() - today.getTime()) / 86400000);
  if (days > 0) return `${days} 天`;
  if (days === 0) return "今天";
  return `已过 ${Math.abs(days)} 天`;
}

function normalizeProgressValue(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  if (num <= 1 && num >= 0) return Math.round(num * 100);
  return Math.max(0, Math.min(100, Math.round(num)));
}

function resolveQuestionTemplateKey(courseName, courseId, initialCourseId) {
  const haystack = [courseName, courseId, initialCourseId].filter(Boolean).join(" ").toLowerCase();
  const alias = COURSE_TEMPLATE_ALIASES.find((item) =>
    item.match.some((keyword) => haystack.includes(String(keyword).toLowerCase()))
  );
  return alias?.key || "";
}

function buildExamInfo(dashboard, preference, course, stats, examSettings = {}, examMaterialSummary = {}) {
  const raw = dashboard?.exam_info || dashboard?.examInfo || preference?.exam_info || preference?.examInfo || course?.exam_info || course?.examInfo || {};
  const examDate = textValue(examSettings.exam_date, examSettings.examDate, raw.exam_date, raw.examDate, raw.date, raw.target_date, raw.targetDate);
  const target = textValue(examSettings.target, raw.target, raw.goal, raw.target_score, raw.targetScore, preference?.target, course?.target);
  const rawReviewScope = textValue(raw.review_scope, raw.reviewScope, raw.scope, raw.exam_scope, raw.examScope);
  const reviewScope = examMaterialSummary.scopeText || rawReviewScope;
  const dailyReview = textValue(examSettings.daily_review, examSettings.dailyReview, raw.daily_review, raw.dailyReview, raw.daily_minutes, raw.dailyMinutes);
  const readinessText = textValue(raw.readiness, raw.ready_status, raw.readyStatus, raw.evaluation);
  const readinessPercent = normalizeProgressValue(raw.readiness_percent ?? raw.readinessPercent ?? raw.progress_percent);
  return {
    examDate: examDate || "未设置",
    target: target || "未设置目标",
    reviewScope: reviewScope || "暂未上传考试范围",
    dailyReview: dailyReview || "未填写",
    readiness: readinessText || (readinessPercent === null ? "暂无评估" : `${readinessPercent}%`),
    daysLeft: formatDaysLeft(examDate),
    configured: {
      examDate: Boolean(examDate),
      target: Boolean(target),
      reviewScope: Boolean(reviewScope && reviewScope !== "暂未上传考试范围"),
      dailyReview: Boolean(dailyReview),
    },
  };
}

function getTaskTitle(task) {
  return textValue(task.title, task.name, task.task_title, task.taskTitle, task.content, task.description, "未命名任务");
}

function getTaskMeta(task) {
  const typeLabel = TASK_TYPE_LABELS[task.task_type || task.type] || textValue(task.task_type, task.type, "学习任务");
  const minutes = Number(task.estimated_minutes ?? task.estimatedMinutes ?? task.duration_minutes ?? task.durationMinutes);
  const duration = Number.isFinite(minutes) && minutes > 0 ? `${minutes} 分钟` : "未设置时长";
  return `${typeLabel} · ${duration}`;
}

function getTaskStatus(task) {
  return STATUS_LABELS[task.status] || textValue(task.status_label, task.statusLabel, task.status, "待安排");
}

function buildCramPrompt(kind, courseName, questionTypes, hasExamMaterials = false) {
  const topics = questionTypes
    .flatMap((type) => [type.title, ...(type.examples || [])])
    .filter(Boolean)
    .slice(0, 10)
    .join("、");
  const materialHint = hasExamMaterials
    ? "请优先结合已上传的考试范围和往年卷；如果资料不足，再按课程常见期末题型补充。"
    : "";
  if (kind === "prediction") {
    return `${materialHint}请根据${courseName}课程的考试突击场景，总结最值得优先复习的高频考点、典型题型和易错点，覆盖${topics}，并按优先级输出。`;
  }
  return `${materialHint}请根据${courseName}课程的期末考试突击场景，生成一套 10 分钟考前自测题，覆盖${topics}，并附参考答案。`;
}

function enrichQuestionType(type) {
  const title = type.title || "";
  if (title.includes("语言基础") || title.includes("协议分层")) {
    return { ...type, tags: ["必背", "简答"], hint: "常考基础概念" };
  }
  if (title.includes("词法") || title.includes("流程")) {
    return { ...type, tags: ["高频", "应用"], hint: "建议优先复习" };
  }
  if (title.includes("语法") || title.includes("计算") || title.includes("推导")) {
    return { ...type, tags: ["高频", "推导"], hint: "常考计算/推导" };
  }
  if (title.includes("语义") || title.includes("综合") || title.includes("代码")) {
    return { ...type, tags: ["综合", "应用"], hint: "常见综合题" };
  }
  return { ...type, tags: ["高频", "简答"], hint: "建议优先复习" };
}

function numberValue(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function getCourseMaterials(materials, courseName, subject, getSubjectLabel) {
  const targetNames = new Set([courseName, subject, getSubjectLabel?.(subject)].filter(Boolean));
  return (Array.isArray(materials) ? materials : []).filter((item) => {
    const itemName = getSubjectLabel?.(item.subject) || item.subject;
    return targetNames.has(item.subject) || targetNames.has(itemName);
  });
}

function countMaterialType(materials, type) {
  return materials.filter((item) => {
    const text = `${item.file_type || ""} ${item.file_name || ""} ${item.original_filename || ""} ${item.summary || ""}`.toLowerCase();
    return type.match.some((keyword) => text.includes(keyword.toLowerCase()));
  }).length;
}

function getMaterialSourceType(material) {
  return String(material?.source_type || material?.sourceType || "user_upload").trim();
}

function isIndexedMaterial(material) {
  const status = String(material?.parse_status || "").trim();
  return status === "success" || status === "partial" || Number(material?.chunk_count || 0) > 0;
}

function buildExamMaterialSummary(materials, courseName, subject, getSubjectLabel) {
  const courseMaterials = getCourseMaterials(materials, courseName, subject, getSubjectLabel);
  const examScopes = courseMaterials.filter((item) => getMaterialSourceType(item) === "exam_scope");
  const pastPapers = courseMaterials.filter((item) => getMaterialSourceType(item) === "past_paper");
  const hasIndexedScope = examScopes.some(isIndexedMaterial);
  let scopeText = "暂未上传考试范围";
  if (examScopes.length > 0) {
    scopeText = hasIndexedScope ? "已上传考试范围" : "考试范围已上传，等待解析";
  }
  return {
    examScopes,
    pastPapers,
    scopeCount: examScopes.length,
    pastPaperCount: pastPapers.length,
    total: examScopes.length + pastPapers.length,
    hasExamMaterials: examScopes.length + pastPapers.length > 0,
    hasIndexedScope,
    scopeText,
  };
}

function formatHours(minutes) {
  const mins = numberValue(minutes);
  if (mins <= 0) return "0 小时";
  return `${(mins / 60).toFixed(1)} 小时`;
}

function buildCourseId(courseName, course) {
  return String(course || courseName || "course").trim().replace(/\s+/g, "_");
}

function resolveCourseName(course, getSubjectLabel) {
  if (course && typeof course === "object") {
    return course.courseName || course.courseTitle || course.name || course.title || course.subject || course.courseId || "璇剧▼瀛︿範";
  }
  return getSubjectLabel?.(course) || course || "璇剧▼瀛︿範";
}

function resolveCourseId(course, courseName) {
  if (course && typeof course === "object") {
    return course.courseId || course.id || course.subject || courseName;
  }
  return course || courseName;
}

function getCourseInitials(courseName) {
  const known = {
    计算机网络: "CN",
    数据结构: "DS",
    "Python 程序设计": "PY",
    操作系统: "OS",
    数据库系统: "DB",
    计算机组成原理: "CO",
  };
  return known[courseName] || String(courseName || "CL").trim().slice(0, 2).toUpperCase();
}

function Metric({ label, value }) {
  return (
    <div className="exam-subject-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Quota({ label, value, percent }) {
  return (
    <div className="exam-subject-quota">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <i><b style={{ width: `${percent}%` }} /></i>
    </div>
  );
}

export default function CourseSubjectDashboard({
  user,
  course,
  dashboard,
  coursePreference,
  loading,
  setPage,
  getSubjectLabel,
  materials = [],
  // Content props — if provided, render them; otherwise render fallback overview placeholders
  materialsContent = null,
  knowledgeContent = null,
  reportContent = null,
  planContent = null,
  knowledgeContext = null,
  initialMaterialToReference = null,
  onInitialMaterialReferenced = null,
  panelIntent = null,
  learningGoal = "",
}) {
  const initialCourseName = resolveCourseName(course, getSubjectLabel);
  const initialCourseId = resolveCourseId(course, initialCourseName);
  const panelStorageKey = `course_subject_active_panel_${buildCourseId(initialCourseName, initialCourseId)}`;

  const isExamModeKey = course?.primary_mode === "exam" ||
    course?.primaryMode === "exam" ||
    course?.studyMode === "exam" ||
    course?.mode === "exam" ||
    coursePreference?.primary_mode === "exam";
  const isExamCramMode = isExamModeKey ||
    learningGoal === "考前突击" ||
    learningGoal === "考试突击" ||
    course?.learningGoal === "考前突击" ||
    course?.learningGoal === "考试突击" ||
    course?.learning_goal === "考前突击" ||
    course?.learning_goal === "考试突击" ||
    coursePreference?.learning_goal === "考前突击" ||
    coursePreference?.learning_goal === "考试突击";
  const navItems = isExamCramMode ? EXAM_CRAM_NAV_ITEMS : NAV_ITEMS;
  const allowedPanels = isExamCramMode
    ? ["overview", "chat", "materials", "knowledge", "plan"]
    : ["overview", "chat", "materials", "knowledge", "plan", "report"];

  const normalizePanel = (panel) =>
    allowedPanels.includes(panel)
      ? panel
      : null;

  const getSavedPanel = () => {
    try {
      const raw = localStorage.getItem(panelStorageKey);
      if (raw) {
        const data = JSON.parse(raw);
        return normalizePanel(data?.activePanel) || "overview";
      }
    } catch { /* ignore */ }
    return "overview";
  };

  const [activeSection, setActiveSection] = useState(() =>
    normalizePanel(panelIntent?.panel) || getSavedPanel()
  );
  const [entitlements, setEntitlements] = useState(null);
  const [cramPlanData, setCramPlanData] = useState(null);
  const [cramPlanLoading, setCramPlanLoading] = useState(false);
  const [cramPlanError, setCramPlanError] = useState("");
  const [chatPromptIntent, setChatPromptIntent] = useState(null);
  const [examConfigNoticeOpen, setExamConfigNoticeOpen] = useState(false);
  const [examSettings, setExamSettings] = useState({});
  const [examSettingsForm, setExamSettingsForm] = useState({
    exam_date: "",
    target: "",
    custom_target: "",
    daily_review: "",
  });
  const [examSettingsSaving, setExamSettingsSaving] = useState(false);
  const [examSettingsError, setExamSettingsError] = useState("");
  const [planCreateIntent, setPlanCreateIntent] = useState(null);
  const stats = dashboard?.stats || {};
  const courseName = initialCourseName;
  const courseId = buildCourseId(courseName, initialCourseId);

  // Persist active section
  useEffect(() => {
    try {
      localStorage.setItem(panelStorageKey, JSON.stringify({ activePanel: activeSection, ts: Date.now() }));
    } catch { /* ignore */ }
  }, [panelStorageKey, activeSection]);

  // Handle panel intent navigation
  useEffect(() => {
    if (!panelIntent?.panel) return;
    const nextPanel = normalizePanel(panelIntent.panel);
    if (nextPanel) setActiveSection(nextPanel);
  }, [panelIntent?.nonce, panelIntent?.panel]);

  useEffect(() => {
    if (!user?.username) return;
    let alive = true;
    fetch(`/api/course-learning/entitlements?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (alive) setEntitlements(data); })
      .catch(() => { if (alive) setEntitlements(null); });
    return () => { alive = false; };
  }, [user?.username]);

  useEffect(() => {
    if (!isExamCramMode || !user?.username || !courseId) {
      setExamSettings({});
      return;
    }
    const controller = new AbortController();
    setExamSettingsError("");
    fetch(`/api/course-learning/exam-settings?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setExamSettings(data?.settings || {});
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setExamSettings({});
        setExamSettingsError(err?.message || "考试信息读取失败");
      });
    return () => controller.abort();
  }, [isExamCramMode, user?.username, courseId]);

  const learnedPercent = Math.max(0, Math.min(100, numberValue(stats.progress_percent, 0)));
  const knowledgeCount = numberValue(stats.knowledge_points_count, 0);
  const chapterCount = numberValue(stats.chapter_count || stats.modules_count, 12);
  const studyMinutes = numberValue(stats.weekly_study_minutes || stats.total_study_minutes, 0);
  const aiLimit = numberValue(entitlements?.feature_limits?.chat?.limit, 0);
  const aiRemaining = numberValue(entitlements?.feature_limits?.chat?.remaining, 0);
  const questionLimit = numberValue(entitlements?.feature_limits?.question_generate?.limit, 0);
  const questionRemaining = numberValue(entitlements?.feature_limits?.question_generate?.remaining, 0);
  const uploadLimitMb = numberValue(entitlements?.upload_limits?.single_file_size_mb || entitlements?.permissions?.material_upload_limit_mb, 0);
  const uploadLimitText = uploadLimitMb ? (uploadLimitMb >= 1024 ? `${uploadLimitMb / 1024} GB` : `${uploadLimitMb} MB`) : "未获取";
  const preference = coursePreference || dashboard?.preference || {};
  const focusTag = learningGoal || preference.learning_goal || "平日学习";
  const activeLabel = navItems.find((item) => item.key === activeSection)?.label || "首页";
  const courseContextDisplay = `课程学习 / ${courseName}`;
  const questionTemplateKey = resolveQuestionTemplateKey(courseName, courseId, initialCourseId);
  const questionTypes = (COURSE_QUESTION_TYPE_TEMPLATES[questionTemplateKey] || GENERAL_QUESTION_TYPES).map(enrichQuestionType);
  const realSprintTasks = Array.isArray(cramPlanData?.tasks) ? cramPlanData.tasks.slice(0, 4) : [];

  // Check course_learning membership plan — hide ad if full
  const coursePlan = entitlements?.plan || user?.service_plans?.["course_learning"]?.plan || "free";
  const isCourseFullPlan = coursePlan === "full";

  // Materials for overview
  const courseMaterialsArr = (() => {
    const targetNames = new Set([courseName, initialCourseId, getSubjectLabel?.(initialCourseId)].filter(Boolean));
    return (Array.isArray(materials) ? materials : []).filter((item) => {
      const itemName = getSubjectLabel?.(item.subject) || item.subject;
      return targetNames.has(item.subject) || targetNames.has(itemName);
    });
  })();
  const examMaterialSummary = buildExamMaterialSummary(materials, courseName, courseId, getSubjectLabel);
  const examInfo = buildExamInfo(dashboard, preference, course, stats, examSettings, examMaterialSummary);
  const hasExamMaterials = examMaterialSummary.hasExamMaterials;
  const hasPreciseExamInfo = Boolean(examInfo.configured.examDate && examInfo.configured.reviewScope);

  const planItems = [];

  useEffect(() => {
    if (!allowedPanels.includes(activeSection)) setActiveSection("overview");
  }, [activeSection, allowedPanels]);

  useEffect(() => {
    if (!isExamCramMode || !user?.username) {
      setCramPlanData(null);
      setCramPlanError("");
      setCramPlanLoading(false);
      return;
    }
    const controller = new AbortController();
    setCramPlanLoading(true);
    setCramPlanError("");
    fetch(`/api/course-learning/study-plan?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setCramPlanData(data))
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setCramPlanData(null);
        setCramPlanError(err?.message || "学习计划读取失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setCramPlanLoading(false);
      });
    return () => controller.abort();
  }, [isExamCramMode, user?.username, courseId]);

  const openPlan = () => setActiveSection("plan");

  const openPlanCreate = () => {
    setPlanCreateIntent({ nonce: Date.now() });
    setActiveSection("plan");
  };

  const openMaterials = () => setActiveSection("materials");

  const openExamSettingsNotice = () => {
    const target = textValue(examSettings.target);
    const isPresetTarget = EXAM_TARGET_OPTIONS.includes(target) && target !== "自定义";
    setExamSettingsForm({
      exam_date: textValue(examSettings.exam_date, examSettings.examDate),
      target: isPresetTarget || !target ? target : "自定义",
      custom_target: isPresetTarget ? "" : target,
      daily_review: textValue(examSettings.daily_review, examSettings.dailyReview),
    });
    setExamSettingsError("");
    setExamConfigNoticeOpen(true);
  };

  const saveExamSettings = async () => {
    if (!user?.username) return;
    const target = examSettingsForm.target === "自定义"
      ? examSettingsForm.custom_target.trim()
      : examSettingsForm.target.trim();
    setExamSettingsSaving(true);
    setExamSettingsError("");
    try {
      const res = await fetch("/api/course-learning/exam-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: courseId,
          exam_date: examSettingsForm.exam_date,
          target,
          daily_review: examSettingsForm.daily_review,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setExamSettings(data?.settings || {});
      setExamConfigNoticeOpen(false);
    } catch (error) {
      setExamSettingsError(error?.message || "考试信息保存失败");
    } finally {
      setExamSettingsSaving(false);
    }
  };

  const openAiWithPrompt = (kind) => {
    setChatPromptIntent({
      nonce: Date.now(),
      text: buildCramPrompt(kind, courseName, questionTypes, hasExamMaterials),
    });
    setActiveSection("chat");
  };

  const renderExamCramHeader = (subtitle = "考试突击 · 课程冲刺工作台") => (
    <header className="csd-cram-header">
      <div className="csd-cram-title-block">
        <span className="csd-cram-logo">{getCourseInitials(courseName)}</span>
        <div>
          <h1>{courseName}</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="csd-cram-badges">
        <span>{examInfo.daysLeft ? `距离考试 ${examInfo.daysLeft}` : "未设置考试日期"}</span>
        <span>目标：{examInfo.target}</span>
      </div>
    </header>
  );

  const renderExamCramOverview = () => (
    <div className="csd-cram-page">
      {renderExamCramHeader()}

      <section className="csd-cram-grid csd-cram-grid--top">
        <div className="csd-cram-card">
          <div className="csd-cram-card-head">
            <h2>考试信息</h2>
            <p>用于生成倒计时、复习范围和冲刺建议</p>
          </div>
          <div className="csd-cram-info-grid">
            <div><span>考试日期</span><strong>{examInfo.examDate}</strong></div>
            <div><span>复习范围</span><strong>{examInfo.reviewScope}</strong></div>
            <div><span>每日复习</span><strong>{examInfo.dailyReview}</strong></div>
            <div><span>当前准备度</span><strong>{examInfo.readiness}</strong></div>
          </div>
          {!hasPreciseExamInfo && (
            <div className="csd-cram-config-callout">
              <div>
                <strong>建议先设置考试信息</strong>
                <p>补充考试日期、目标，并上传考试范围后，首页倒计时、冲刺建议和 AI 自测会更准确。</p>
              </div>
              <div className="csd-cram-config-actions">
                <button type="button" onClick={openExamSettingsNotice}>设置考试信息</button>
                {!examMaterialSummary.scopeCount && (
                  <button type="button" className="csd-cram-secondary-button" onClick={openMaterials}>去资料库上传</button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="csd-cram-card csd-cram-self-test">
          <div className="csd-cram-card-head">
            <h2>考前自测入口</h2>
            <p>基于当前课程与考试范围生成快速自测</p>
          </div>
          {!hasExamMaterials && (
            <p className="csd-cram-self-test-note">建议先上传考试范围或往年卷，AI 自测会更贴近考试。</p>
          )}
          {hasExamMaterials ? (
            <>
              <button type="button" onClick={() => openAiWithPrompt("selfTest")}>基于考试资料生成自测</button>
              <button type="button" onClick={() => openAiWithPrompt("prediction")}>基于考试资料预测重点</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => openAiWithPrompt("selfTest")}>生成通用自测</button>
              <button type="button" onClick={openMaterials}>去上传考试资料</button>
            </>
          )}
        </div>
      </section>

      <section className="csd-cram-card">
        <div className="csd-cram-card-head">
          <h2>考前冲刺清单</h2>
          <p>从学习计划中同步你的冲刺任务</p>
        </div>
        <div className="csd-cram-task-list">
          {cramPlanLoading && (
            <div className="csd-cram-empty-state">
              <strong>正在读取学习计划</strong>
              <p>将展示当前课程已有的真实冲刺任务。</p>
            </div>
          )}
          {!cramPlanLoading && cramPlanError && (
            <div className="csd-cram-empty-state">
              <strong>学习计划读取失败</strong>
              <p>{cramPlanError}</p>
              <div className="csd-cram-empty-actions">
                <button type="button" onClick={openPlan}>去学习计划</button>
              </div>
            </div>
          )}
          {!cramPlanLoading && !cramPlanError && realSprintTasks.length === 0 && (
            <div className="csd-cram-empty-state">
              <strong>还没有冲刺任务</strong>
              <p>当前首页会同步展示学习计划中的冲刺任务。你可以先创建 2-4 个阶段任务，用来安排考前复习。</p>
              <div className="csd-cram-empty-actions">
                <button type="button" onClick={openPlan}>去学习计划</button>
                <button type="button" onClick={openPlanCreate}>新建任务</button>
              </div>
            </div>
          )}
          {realSprintTasks.map((task) => (
            <label className="csd-cram-task" key={task.id || getTaskTitle(task)}>
              <input type="checkbox" checked={task.status === "completed"} readOnly />
              <span>
                <strong>{getTaskTitle(task)}</strong>
                <em>{getTaskMeta(task)}</em>
              </span>
              <b>{getTaskStatus(task)}</b>
            </label>
          ))}
        </div>
      </section>

      <section className="csd-cram-card">
        <div className="csd-cram-card-head">
          <h2>高频题型</h2>
          <p>按当前课程整理常见考试题型</p>
        </div>
        <div className="csd-cram-type-grid">
          {questionTypes.map((type) => (
            <article className="csd-cram-type-card" key={type.title}>
              <div className="csd-cram-type-tags">
                {(type.tags || []).map((tag) => <em key={tag}>{tag}</em>)}
              </div>
              <strong>{type.title}</strong>
              {type.examples.map((example) => <span key={example}>{example}</span>)}
              <small>{type.hint}</small>
            </article>
          ))}
        </div>
      </section>

      {examConfigNoticeOpen && (
        <div className="csd-cram-modal-backdrop" role="presentation" onMouseDown={() => setExamConfigNoticeOpen(false)}>
          <section
            className="csd-cram-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="csd-cram-config-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button type="button" className="csd-cram-modal-close" onClick={() => setExamConfigNoticeOpen(false)} aria-label="关闭">×</button>
            <span>考试信息</span>
            <h2 id="csd-cram-config-title">设置考试信息</h2>
            <p>设置会按当前课程保存，不会影响其它课程。复习范围请在资料库的考试资料专区上传。</p>
            <div className="csd-cram-form">
              <label>
                <span>考试日期</span>
                <input
                  type="date"
                  value={examSettingsForm.exam_date}
                  onChange={(event) => setExamSettingsForm((prev) => ({ ...prev, exam_date: event.target.value }))}
                />
              </label>
              <label>
                <span>目标</span>
                <select
                  value={examSettingsForm.target}
                  onChange={(event) => setExamSettingsForm((prev) => ({ ...prev, target: event.target.value }))}
                >
                  <option value="">未设置目标</option>
                  {EXAM_TARGET_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              {examSettingsForm.target === "自定义" && (
                <label>
                  <span>自定义目标</span>
                  <input
                    type="text"
                    value={examSettingsForm.custom_target}
                    maxLength={40}
                    placeholder="例如：85 分以上"
                    onChange={(event) => setExamSettingsForm((prev) => ({ ...prev, custom_target: event.target.value }))}
                  />
                </label>
              )}
              <label>
                <span>每日复习时间（可选）</span>
                <input
                  type="text"
                  value={examSettingsForm.daily_review}
                  maxLength={30}
                  placeholder="例如：1.5 小时"
                  onChange={(event) => setExamSettingsForm((prev) => ({ ...prev, daily_review: event.target.value }))}
                />
              </label>
            </div>
            {examSettingsError && <p className="csd-cram-modal-error">{examSettingsError}</p>}
            <div className="csd-cram-modal-actions">
              <button type="button" className="csd-cram-modal-ghost" onClick={() => setExamConfigNoticeOpen(false)} disabled={examSettingsSaving}>取消</button>
              <button type="button" className="csd-cram-modal-primary" onClick={saveExamSettings} disabled={examSettingsSaving}>
                {examSettingsSaving ? "保存中..." : "保存设置"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );

  const renderOverview = () => (
    <>
      <section className="csd-top-grid">
        <div className="csd-card csd-hero-card">
          <div>
            <h2>开始今天的{courseName}学习</h2>
            <p>坚持学习，稳步提升，攻克每一个课程知识点！</p>
          </div>
          <div className="csd-hero-art" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </div>

        <div className="csd-card csd-overview-card">
          <h3>课程概览</h3>
          <div className="csd-overview-grid">
            <div><span>总章节</span><strong>{chapterCount}<small> 个</small></strong></div>
            <div><span>知识点</span><strong>{knowledgeCount}<small> 个</small></strong></div>
            <div><span>已学习</span><strong>{learnedPercent}<small>%</small></strong><em style={{ width: `${learnedPercent}%` }} /></div>
            <div><span>学习时长</span><strong>{formatHours(studyMinutes)}</strong></div>
          </div>
        </div>
      </section>

      <section className="csd-middle-grid">
        {/* Today's Plan */}
        <div className="csd-card csd-plan-card">
          <h3><span>▤</span> 今日学习计划</h3>
          <div className="csd-plan-list">
            {planItems.length === 0 && (
              <div className="csd-empty-state">
                <strong>暂无今日学习计划</strong>
                <p>当前课程还没有生成学习任务，可在学习计划页查看课程任务空状态。</p>
              </div>
            )}
            {planItems.map((item) => (
              <div className="csd-plan-item" key={item.title}>
                <span className={item.done ? "is-done" : ""}>{item.done ? "✓" : item.index}</span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.desc}</p>
                </div>
                <button type="button" className={item.done ? "is-complete" : ""}>{item.status}</button>
              </div>
            ))}
          </div>
        </div>

        {/* Material Summary */}
        <div className="csd-card csd-material-card">
          <h3><span>▣</span> 资料库概览</h3>
          <div className="csd-material-grid">
            {MATERIAL_CARDS.map((item) => (
              <div className={`csd-material-item csd-material-item--${item.tone}`} key={item.key}>
                <span>■</span>
                <strong>{item.label}</strong>
                <em>{countMaterialType(courseMaterialsArr, item)} 份</em>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="csd-bottom-grid">
        {/* Knowledge Preview */}
        <div className="csd-card csd-knowledge-card">
          <h3><span>⌘</span> 知识脉络</h3>
          <div className="csd-orbit">
            <strong>{courseName}</strong>
            {["课程概念", "课堂资料", "阶段复盘", "学习报告"].map((label, index) => (
              <span className={`csd-node csd-node--${index}${index === 0 ? " is-active" : ""}`} key={label}>
                {label}
              </span>
            ))}
          </div>
        </div>

        {/* Quota */}
        <div className="csd-card csd-quota-card">
          <h3><span>▧</span> 额度剩余</h3>
          {[
            ["AI 问答剩余", aiRemaining, aiLimit],
            ["AI 出题剩余", questionRemaining, questionLimit],
            ["资料上传上限", uploadLimitText, ""],
          ].map(([label, value, total]) => (
            <div className="csd-quota-row" key={label}>
              <span>{label}</span>
              <strong>{total ? `${value} / ${total}` : value}</strong>
              {total ? <em><i style={{ width: `${Math.max(4, Math.min(100, (Number(value) / Number(total || 1)) * 100))}%` }} /></em> : null}
            </div>
          ))}
          <div className="csd-course-task-tag">当前目标：{focusTag}</div>
        </div>
      </section>
    </>
  );

  const renderActiveContent = () => {
    // AI Chat — use mature ExamChat component with course_learning context
    if (activeSection === "chat") {
      return (
        <ExamChat
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          contextDisplay={isExamCramMode ? "考试突击 · AI 复习问答" : courseContextDisplay}
          knowledgeContext={knowledgeContext}
          initialMaterialToReference={initialMaterialToReference}
          onInitialMaterialReferenced={onInitialMaterialReferenced}
          initialPrompt={chatPromptIntent}
        />
      );
    }

    // Materials — use content prop if available, otherwise fallback
    if (activeSection === "materials") {
      if (materialsContent) return materialsContent;
      // Fallback: show minimal materials preview
      return (
        <section className="csd-section">
          <div className="csd-section-header">
            <span>Course Library</span>
            <h2>{courseName} · 资料库</h2>
            <p>当前课程：{courseContextDisplay}</p>
          </div>
          <div className="csd-card csd-library-card" style={{ padding: 26 }}>
            {courseMaterialsArr.length > 0 ? (
              <div className="csd-material-list">
                {courseMaterialsArr.slice(0, 8).map((item) => (
                  <div className="csd-material-row" key={item.id || item.original_filename}>
                    <strong>{item.original_filename || item.file_name || "未命名资料"}</strong>
                    <span>{item.file_type || "course_material"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="csd-empty-state">
                <strong>{courseName} 暂无课程资料</strong>
                <p>上传课程资料后，可用于 AI 问答引用和学习。</p>
              </div>
            )}
          </div>
        </section>
      );
    }

    // Knowledge — use content prop if available, else use KnowledgeLearningPage with course_learning mode
    if (activeSection === "knowledge") {
      if (knowledgeContent) return knowledgeContent;
      return (
        <KnowledgeLearningPage
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          onNavigateToAI={(ctx) => {
            // Navigate to AI chat within CourseSubjectDashboard
            setActiveSection("chat");
          }}
        />
      );
    }

    // Study Plan — use content prop if available, else use ExamStudyPlan with course_learning mode
    if (activeSection === "plan") {
      if (planContent) return planContent;
      return (
        <ExamStudyPlan
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          createTaskIntent={planCreateIntent}
          onNavigate={(target) => {
            // Navigate within CourseSubjectDashboard
            if (target === "knowledge") setActiveSection("knowledge");
          }}
        />
      );
    }

    // Learning Report — use content prop if available, else use LearningReportCenter with course context
    if (activeSection === "report") {
      if (reportContent) return reportContent;
      return (
        <Suspense fallback={<div className="csd-loading">学习报告加载中...</div>}>
          <LearningReportCenter
            user={user}
            mode="course_learning"
            courseName={courseName}
          />
        </Suspense>
      );
    }

    if (isExamCramMode) return renderExamCramOverview();
    return renderOverview();
  };

  return (
    <div className="csd-page">
      <aside className="csd-sidebar" aria-label="课程工作台导航">
        <nav className="csd-nav" aria-label="课程学习功能">
          {navItems.map((item) => (
            <button
              className={`csd-nav-item${activeSection === item.key ? " is-active" : ""}`}
              type="button"
              key={item.key}
              onClick={() => setActiveSection(item.key)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="csd-sidebar-footer">
          {!isExamCramMode && !isCourseFullPlan && (
            <div className="csd-member-card">
              <strong>会员 <span>♛</span></strong>
              <p>解锁专属权益，畅享课程学习特权</p>
              <ul>
                <li>专属学习资源</li>
                <li>AI 问答优先使用</li>
                <li>学习数据深度分析</li>
                <li>更多高级功能</li>
              </ul>
              <button type="button" onClick={() => setPage?.("coursePlan")}>了解会员权益 →</button>
            </div>
          )}

          <button className="csd-back-home" type="button" onClick={() => setPage?.("home")}>
            ↩ 返回主页
          </button>
        </div>
      </aside>

      <main className={`csd-main${isExamCramMode ? " csd-main--cram" : ""}${activeSection === "chat" ? " csd-main--chat" : ""}${activeSection === "materials" ? " csd-main--materials" : ""}${activeSection === "knowledge" ? " csd-main--knowledge" : ""}${activeSection === "plan" ? " csd-main--plan" : ""}${activeSection === "report" ? " csd-main--report" : ""}`}>
        {loading ? (
          <section className="csd-card csd-loading">课程工作台加载中...</section>
        ) : (
          renderActiveContent()
        )}
      </main>
    </div>
  );
}
