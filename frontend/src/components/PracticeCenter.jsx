import { useEffect, useState } from "react";

const API_BASE = "/api";

const TYPE_OPTIONS = [
  { value: "", label: "全部题型" },
  { value: "choice", label: "选择题" },
  { value: "multiple_choice", label: "多选题" },
  { value: "true_false", label: "判断题" },
  { value: "fill_blank", label: "填空题" },
  { value: "short_answer", label: "简答题" },
  { value: "programming", label: "编程题" },
];

const DIFFICULTY_OPTIONS = [
  { value: "easy", label: "简单" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "困难" },
];

const STYLE_OPTIONS = [
  { value: "exam", label: "考试题" },
  { value: "leetcode", label: "算法刷题" },
  { value: "codeforces", label: "竞赛题" },
  { value: "textbook", label: "教材课后题" },
  { value: "interview", label: "面试题" },
  { value: "mixed", label: "混合" },
];

const TYPE_LABELS = {
  choice: "选择题",
  single_choice: "选择题",
  multiple_choice: "多选题",
  true_false: "判断题",
  fill_blank: "填空题",
  short_answer: "简答题",
  programming: "编程题",
};

const DIFFICULTY_LABELS = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
  "基础": "简单",
  "中等": "中等",
  "提高": "困难",
};

const STYLE_LABELS = {
  exam: "考试题",
  leetcode: "算法刷题",
  codeforces: "竞赛题",
  textbook: "教材课后题",
  interview: "面试题",
  mixed: "混合",
};

const SOURCE_LABELS = {
  manual: "手动创建",
  ai: "AI 生成",
  imported: "导入",
  paper_upload: "试卷识别",
  code_studio: "编程助手",
};

const RESULT_LABELS = {
  correct: "正确",
  incorrect: "错误",
  partially_correct: "部分正确",
  unknown: "未知",
};

export default function PracticeCenter({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
  setPage = () => {},
}) {
  const [questions, setQuestions] = useState([]);
  const [papers, setPapers] = useState([]);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [courseFilter, setCourseFilter] = useState(subject || "");
  const [kpFilter, setKpFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  // Detail modal
  const [detailQuestion, setDetailQuestion] = useState(null);
  const [userAnswer, setUserAnswer] = useState("");
  const [attempts, setAttempts] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [detailActionLoading, setDetailActionLoading] = useState(false);
  const [showAnswer, setShowAnswer] = useState(false);
  const [paperDetail, setPaperDetail] = useState(null);
  const [paperQuestions, setPaperQuestions] = useState([]);
  const [expandedPaperQuestions, setExpandedPaperQuestions] = useState({});
  const [paperLoading, setPaperLoading] = useState(false);
  const [aiExplainLoadingId, setAiExplainLoadingId] = useState(null);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createType, setCreateType] = useState("choice");
  const [createModuleId, setCreateModuleId] = useState("");
  const [createTitle, setCreateTitle] = useState("");
  const [createContent, setCreateContent] = useState("");
  const [createOptions, setCreateOptions] = useState("");
  const [createAnswer, setCreateAnswer] = useState("");
  const [createExplanation, setCreateExplanation] = useState("");
  const [createCourse, setCreateCourse] = useState(subject || "");
  const [createKpId, setCreateKpId] = useState("");
  const [createDifficulty, setCreateDifficulty] = useState("medium");
  const [createSaving, setCreateSaving] = useState(false);

  // AI generate modal
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [genCourse, setGenCourse] = useState(subject || "");
  const [genCourseName, setGenCourseName] = useState("");
  const [genModuleId, setGenModuleId] = useState("");
  const [genKpId, setGenKpId] = useState("");
  const [genType, setGenType] = useState("choice");
  const [genDifficulty, setGenDifficulty] = useState("medium");
  const [genCount, setGenCount] = useState(5);
  const [genSourceStyle, setGenSourceStyle] = useState("mixed");
  const [genRequireReasoning, setGenRequireReasoning] = useState(true);
  const [genAvoidTooSimple, setGenAvoidTooSimple] = useState(true);
  const [genLoading, setGenLoading] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importCourse, setImportCourse] = useState(subject || "");
  const [importModuleId, setImportModuleId] = useState("");
  const [importKpId, setImportKpId] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [importDrafts, setImportDrafts] = useState([]);
  const [importSelected, setImportSelected] = useState({});
  const [importPaperTitle, setImportPaperTitle] = useState("");
  const [importOriginalFileName, setImportOriginalFileName] = useState("");
  const [importLoading, setImportLoading] = useState(false);
  const [importSaving, setImportSaving] = useState(false);
  const [importError, setImportError] = useState("");
  const [importExtractMeta, setImportExtractMeta] = useState(null);

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

  const loadQuestions = async () => {
    if (!user?.username) return;
    setLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      const normalizedCourse = normalizeSubject(courseFilter, "");
      if (normalizedCourse) query.set("course_id", normalizedCourse);
      if (kpFilter) query.set("knowledge_point_id", kpFilter);
      if (typeFilter) query.set("type", typeFilter);
      const res = await fetch(`${API_BASE}/practice/questions?${query.toString()}`);
      const data = await res.json();
      if (res.ok) {
        setQuestions(data.questions || []);
        setPapers(data.papers || []);
      }
    } catch (e) {
      console.error("Failed to load questions:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const normalizedCourse = normalizeSubject(courseFilter, "");
    loadKnowledgePoints(normalizedCourse);
  }, [user?.username, courseFilter]);

  useEffect(() => {
    loadQuestions();
  }, [user?.username, courseFilter, kpFilter, typeFilter]);

  useEffect(() => {
    if (showCreateModal) {
      const normalizedCourse = normalizeSubject(createCourse, "");
      loadKnowledgePoints(normalizedCourse);
    }
  }, [showCreateModal, createCourse]);

  useEffect(() => {
    if (showGenerateModal) {
      const normalizedCourse = normalizeSubject(genCourse, "");
      loadKnowledgePoints(normalizedCourse);
    }
  }, [showGenerateModal, genCourse]);

  useEffect(() => {
    if (showImportModal) {
      const normalizedCourse = normalizeSubject(importCourse, "");
      loadKnowledgePoints(normalizedCourse);
    }
  }, [showImportModal, importCourse]);

  const openDetail = async (q) => {
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${q.id}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok) {
        setDetailQuestion(data.question);
        setUserAnswer("");
        setFeedback("");
        setShowAnswer(false);
        await loadAttempts(q.id);
      }
    } catch (e) {
      console.error("Failed to load question detail:", e);
    }
  };

  const loadAttempts = async (questionId) => {
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${questionId}/attempts?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok) {
        setAttempts(data.attempts || []);
      }
    } catch (e) {
      console.error("Failed to load attempts:", e);
    }
  };

  const submitAnswer = async () => {
    if (!userAnswer.trim()) return;
    setDetailActionLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${detailQuestion.id}/attempts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            question_id: detailQuestion.id,
            user_answer: userAnswer.trim(),
          }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        await loadAttempts(detailQuestion.id);
      }
    } catch (e) {
      console.error("Failed to submit answer:", e);
    } finally {
      setDetailActionLoading(false);
    }
  };

  const requestFeedback = async () => {
    if (!userAnswer.trim()) return;
    setFeedbackLoading(true);
    setFeedback("");
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${detailQuestion.id}/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            user_answer: userAnswer.trim(),
          }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        setFeedback(data.feedback || "");
        await loadAttempts(detailQuestion.id);
      }
    } catch (e) {
      console.error("Failed to get AI feedback:", e);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const createQuestion = async () => {
    if (createType === "programming") {
      setPage("codeStudio");
      return;
    }
    if (!createTitle.trim() || !createContent.trim()) return;
    setCreateSaving(true);
    try {
      const selectedKpId = createKpId || createModuleId;
      const body = {
        username: user.username,
        course_id: normalizeSubject(createCourse, ""),
        knowledge_point_id: selectedKpId ? parseInt(selectedKpId) : null,
        type: createType,
        title: createTitle.trim(),
        content: createContent.trim(),
        options: createOptions.trim() || null,
        answer: createAnswer.trim() || null,
        explanation: createExplanation.trim() || null,
        difficulty: createDifficulty,
        source: "manual",
      };
      const res = await fetch(`${API_BASE}/practice/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowCreateModal(false);
        resetCreateForm();
        await loadQuestions();
      } else {
        alert(data.detail || "创建失败");
      }
    } catch (e) {
      console.error("Failed to create question:", e);
    } finally {
      setCreateSaving(false);
    }
  };

  const resetCreateForm = () => {
    setCreateType("choice");
    setCreateModuleId("");
    setCreateTitle("");
    setCreateContent("");
    setCreateOptions("");
    setCreateAnswer("");
    setCreateExplanation("");
    setCreateCourse(subject || "");
    setCreateKpId("");
    setCreateDifficulty("medium");
  };

  const generateQuestions = async () => {
    if (genType === "programming") {
      setPage("codeStudio");
      setShowGenerateModal(false);
      return;
    }
    setGenLoading(true);
    try {
      const selectedKpId = genKpId || genModuleId;
      const selectedKp = selectedKpId
        ? knowledgePoints.find((kp) => String(kp.id) === String(selectedKpId))
        : null;
      const body = {
        username: user.username,
        course_id: normalizeSubject(genCourse, ""),
        course_name: genCourseName || getSubjectLabel(genCourse),
        knowledge_point_id: selectedKpId ? parseInt(selectedKpId) : null,
        knowledge_point_title: selectedKp?.title || "",
        type: genType,
        difficulty: genDifficulty,
        count: genCount,
        source_style: genSourceStyle,
        require_reasoning: genRequireReasoning,
        avoid_too_simple: genAvoidTooSimple,
      };
      const res = await fetch(`${API_BASE}/practice/questions/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowGenerateModal(false);
        await loadQuestions();
        alert(data.message || "生成成功");
      } else {
        alert(data.detail || "生成失败");
      }
    } catch (e) {
      console.error("Failed to generate questions:", e);
    } finally {
      setGenLoading(false);
    }
  };

  const deleteQuestion = async (q) => {
    if (!window.confirm(`确认删除题目"${q.title}"吗？`)) return;
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${q.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        await loadQuestions();
        if (detailQuestion?.id === q.id) setDetailQuestion(null);
      }
    } catch (e) {
      console.error("Failed to delete question:", e);
    }
  };

  const openPaperDetail = async (paper) => {
    if (!paper?.id || !user?.username) return;
    setPaperLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/practice/papers/${paper.id}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok) {
        setPaperDetail(data.paper);
        setPaperQuestions(data.questions || []);
        setExpandedPaperQuestions({});
      }
    } catch (e) {
      console.error("Failed to load paper detail:", e);
    } finally {
      setPaperLoading(false);
    }
  };

  const deletePaper = async (paper) => {
    if (!window.confirm(`确认删除试卷"${paper.title}"及其题目吗？`)) return;
    try {
      const res = await fetch(
        `${API_BASE}/practice/papers/${paper.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        if (paperDetail?.id === paper.id) setPaperDetail(null);
        await loadQuestions();
      }
    } catch (e) {
      console.error("Failed to delete paper:", e);
    }
  };

  const requestQuestionAiExplain = async (question, fromPaper = false) => {
    if (!question?.id || !user?.username) return;
    setAiExplainLoadingId(question.id);
    try {
      const res = await fetch(`${API_BASE}/practice/questions/${question.id}/ai-explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "AI 解析失败");
      const nextQuestion = data.question || { ...question, explanation: data.explanation, answer: data.answer };
      if (fromPaper) {
        setPaperQuestions((items) => items.map((item) => (item.id === question.id ? nextQuestion : item)));
      }
      if (detailQuestion?.id === question.id) {
        setDetailQuestion(nextQuestion);
        setShowAnswer(true);
      }
    } catch (e) {
      alert(e.message || "AI 解析失败");
    } finally {
      setAiExplainLoadingId(null);
    }
  };

  const getTypeClass = (type) => {
    if (type === "choice" || type === "single_choice" || type === "multiple_choice" || type === "true_false") return "q-type-choice";
    if (type === "short_answer") return "q-type-short";
    if (type === "fill_blank") return "q-type-short";
    return "q-type-prog";
  };

  const isSameLocalDay = (dateLike) => {
    if (!dateLike) return false;
    const date = new Date(dateLike);
    if (Number.isNaN(date.getTime())) return false;
    const today = new Date();
    return date.getFullYear() === today.getFullYear() &&
      date.getMonth() === today.getMonth() &&
      date.getDate() === today.getDate();
  };

  const isQuestionCompleted = (q) => {
    const status = String(q.status || q.practice_status || q.state || "").toLowerCase();
    return Boolean(q.completed || q.is_completed || q.done || q.finished) ||
      status === "completed" ||
      status === "done" ||
      status === "finished" ||
      Number(q.completed_attempts || 0) > 0;
  };

  const totalCount = questions.length;
  const todayCount = questions.filter((q) =>
    isSameLocalDay(q.last_attempt_at || q.last_practiced_at || q.updated_at || q.created_at)
  ).length;
  const completedCount = questions.filter(isQuestionCompleted).length;
  const pendingCount = Math.max(totalCount - completedCount, 0);
  const selectedCourseLabel = courseFilter ? getSubjectLabel(courseFilter) : "全部课程";
  const selectedKnowledgePointLabel = kpFilter
    ? (knowledgePoints.find((kp) => String(kp.id) === String(kpFilter)) || {}).title || "已选知识点"
    : "全部知识点";
  const selectedTypeLabel = (TYPE_OPTIONS.find((item) => item.value === typeFilter) || TYPE_OPTIONS[0]).label;
  const knowledgePointMap = new Map(knowledgePoints.map((kp) => [String(kp.id), kp]));
  const knowledgePointModules = knowledgePoints
    .filter((kp) => !kp.parent_id || !knowledgePointMap.has(String(kp.parent_id)) || Number(kp.level || 0) <= 1)
    .sort((a, b) => (Number(a.order_index || a.sort_order || 0) - Number(b.order_index || b.sort_order || 0)) || String(a.title || "").localeCompare(String(b.title || ""), "zh-CN"));
  const getModuleChildren = (moduleId) =>
    knowledgePoints
      .filter((kp) => String(kp.parent_id || "") === String(moduleId))
      .sort((a, b) => (Number(a.order_index || a.sort_order || 0) - Number(b.order_index || b.sort_order || 0)) || String(a.title || "").localeCompare(String(b.title || ""), "zh-CN"));
  const createModuleChildren = createModuleId ? getModuleChildren(createModuleId) : [];
  const genModuleChildren = genModuleId ? getModuleChildren(genModuleId) : [];
  const goCodeStudio = () => setPage("codeStudio");
  const openGenerateModal = () => {
    setGenCourse(courseFilter || subject || "");
    setGenCourseName("");
    setGenModuleId("");
    setGenKpId("");
    setGenType(typeFilter || "choice");
    setGenDifficulty("medium");
    setGenCount(5);
    setGenSourceStyle("mixed");
    setGenRequireReasoning(true);
    setGenAvoidTooSimple(true);
    setShowGenerateModal(true);
  };
  const openCreateModal = () => {
    resetCreateForm();
    setCreateCourse(courseFilter || subject || "");
    setShowCreateModal(true);
  };
  const clearFilters = () => {
    setCourseFilter("");
    setKpFilter("");
    setTypeFilter("");
  };
  const importModuleChildren = importModuleId ? getModuleChildren(importModuleId) : [];

  const formatExtractMethodLabel = (meta) => {
    if (!meta) return null;
    const ft = meta.file_type || "";
    const method = meta.extract_method || "local";
    const qwenUsed = meta.qwen_used || false;

    if (ft === "pdf" || ft === "docx" || ft === "txt" || ft === "md") {
      if (qwenUsed && method === "qwen") return { label: "Qwen 视觉识别 + DeepSeek", cssClass: "extract-method-qwen" };
      if (qwenUsed && method === "mixed") return { label: "文本提取 + Qwen 视觉补充 + DeepSeek", cssClass: "extract-method-mixed" };
      if (ft === "pdf") return { label: "PDF 文本提取 + DeepSeek", cssClass: "extract-method-local" };
      if (ft === "docx") return { label: "Word 文本提取 + DeepSeek", cssClass: "extract-method-local" };
      return { label: "文本提取 + DeepSeek", cssClass: "extract-method-local" };
    }
    if (ft === "image") {
      if (qwenUsed && method === "qwen") return { label: "Qwen 视觉识别 + DeepSeek", cssClass: "extract-method-qwen" };
      if (qwenUsed && method === "mixed") return { label: "OCR 识别 + Qwen 视觉补充 + DeepSeek", cssClass: "extract-method-mixed" };
      return { label: "OCR 文字识别 + DeepSeek", cssClass: "extract-method-local" };
    }
    return { label: "文本提取 + DeepSeek", cssClass: "extract-method-local" };
  };

  const openImportModal = () => {
    setImportCourse(courseFilter || subject || "");
    setImportModuleId("");
    setImportKpId("");
    setImportFile(null);
    setImportDrafts([]);
    setImportSelected({});
    setImportPaperTitle("");
    setImportOriginalFileName("");
    setImportError("");
    setImportExtractMeta(null);
    setShowImportModal(true);
  };
  const updateImportDraft = (index, patch) => {
    setImportDrafts((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };
  const parseImportFile = async () => {
    if (!importFile || !user?.username) return;
    setImportLoading(true);
    setImportError("");
    try {
      const form = new FormData();
      form.append("username", user.username);
      form.append("course_id", normalizeSubject(importCourse, ""));
      const selectedKpId = importKpId || importModuleId;
      if (selectedKpId) form.append("knowledge_point_id", selectedKpId);
      form.append("file", importFile);

      const url = `${API_BASE}/practice/import-paper/parse`;
      console.debug("[paper-import:request]", {
        url,
        fileName: importFile?.name,
        fileSize: importFile?.size,
        course: importCourse,
        moduleId: importModuleId,
        pointId: importKpId,
      });

      const res = await fetch(url, {
        method: "POST",
        body: form,
      });

      const contentType = res.headers.get("content-type") || "";
      const rawText = await res.text();
      console.debug("[paper-import:response]", {
        status: res.status,
        contentType,
        bodyPreview: rawText.slice(0, 500),
      });

      // ── 安全 JSON 解析 ──
      let data = null;
      if (contentType.includes("application/json")) {
        try {
          data = JSON.parse(rawText);
        } catch (parseErr) {
          console.error("[paper-import:json-parse-error]", parseErr.message, rawText.slice(0, 300));
          throw new Error(
            "试卷识别接口返回的 JSON 格式异常，可能是后端服务出现问题。请稍后重试或联系管理员。" +
              " 错误详情：" + parseErr.message
          );
        }
      } else if (rawText.trim().startsWith("<")) {
        // 收到了 HTML 响应 — 通常是 nginx 错误页或 SPA index.html
        if (rawText.includes("413") || rawText.includes("Request Entity Too Large")) {
          throw new Error("试卷文件过大，服务器上传限制导致请求被拒绝（HTTP 413）。请压缩 PDF 或上传更小的文件。");
        } else if (rawText.includes("502") || rawText.includes("Bad Gateway")) {
          throw new Error("后端服务暂时不可用（HTTP 502）。请稍后重试或联系管理员检查后端服务状态。");
        } else if (rawText.includes("504") || rawText.includes("Gateway Time-out")) {
          throw new Error("试卷识别超时（HTTP 504）。文件可能较大或服务器繁忙，请重试或换一个更小的文件。");
        } else if (rawText.includes("404") || rawText.includes("Not Found")) {
          throw new Error("试卷识别接口不存在（HTTP 404）。可能是接口路径变更，请联系管理员。");
        } else {
          throw new Error(
            "试卷识别接口返回了非 JSON 响应（可能是 HTML），HTTP " +
              res.status +
              "。这通常表示后端接口报错、地址错误或服务器代理异常。请检查后端服务或部署状态。" +
              " 响应预览：" + rawText.slice(0, 200)
          );
        }
      } else {
        throw new Error(
          "试卷识别接口返回了未知格式的响应（HTTP " +
            res.status +
            "），content-type: " +
            contentType +
            "。响应预览：" + rawText.slice(0, 300)
        );
      }

      if (!res.ok) {
        throw new Error(data?.detail || data?.message || "识别失败，HTTP " + res.status);
      }

      const drafts = data.drafts || [];
      setImportDrafts(drafts);
      setImportPaperTitle(data.paper_title || data.original_file_name || importFile.name || "导入试卷");
      setImportOriginalFileName(data.original_file_name || importFile.name || "");
      setImportSelected(Object.fromEntries(drafts.map((_, idx) => [idx, true])));
      setImportExtractMeta(data.extract_meta || null);
    } catch (error) {
      const errMsg = error.message || "识别失败，请稍后重试";
      if (errMsg.includes("Invalid \\escape") || errMsg.includes("JSON") || errMsg.includes("转义")) {
        setImportError(
          "试卷题目识别失败，可能是公式或特殊符号导致解析失败。请重试，或先上传文字版 PDF/TXT。错误详情：" +
            errMsg
        );
      } else {
        setImportError(errMsg);
      }
    } finally {
      setImportLoading(false);
    }
  };
  const confirmImportDrafts = async () => {
    const selectedDrafts = importDrafts.filter((_, idx) => importSelected[idx]);
    if (selectedDrafts.length === 0 || !user?.username) return;
    setImportSaving(true);
    setImportError("");
    try {
      const res = await fetch(`${API_BASE}/practice/import-paper/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(importCourse, ""),
          paper_title: importPaperTitle || importOriginalFileName || "导入试卷",
          original_file_name: importOriginalFileName,
          questions: selectedDrafts,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "导入失败");
      setShowImportModal(false);
      await loadQuestions();
      if (data.paper) openPaperDetail(data.paper);
    } catch (error) {
      setImportError(error.message || "导入失败，请稍后重试");
    } finally {
      setImportSaving(false);
    }
  };

  return (
    <section className="chat-panel chat-panel--wide practice-panel">
      <div className="practice-workbench">
        <div className="practice-hero">
          <div className="practice-hero-copy">
            <span className="practice-hero-icon" aria-hidden="true">
              🎯
            </span>
            <div>
              <h2>练习中心</h2>
              <p>按课程、知识点和题型生成练习，巩固薄弱知识点</p>
            </div>
          </div>
          <div className="practice-hero-actions">
            <button
              className="ghost-button compact practice-action-button"
              onClick={openCreateModal}
            >
              ＋ 手动录入
            </button>
            <button
              className="ghost-button compact practice-action-button"
              onClick={openImportModal}
            >
              ⤴ 上传试卷识别
            </button>
            <button
              className="primary-button compact practice-action-button practice-action-button--ai"
              onClick={openGenerateModal}
            >
              ✨ AI 生成题目
            </button>
          </div>
        </div>

        <div className="practice-overview-grid">
          <div className="practice-stat-card">
            <span className="practice-stat-icon practice-stat-icon--total" aria-hidden="true">▣</span>
            <div>
              <strong>{totalCount}</strong>
              <span>题目总数</span>
              <em>共保存 {totalCount} 道题</em>
            </div>
          </div>
          <div className="practice-stat-card">
            <span className="practice-stat-icon practice-stat-icon--today" aria-hidden="true">▤</span>
            <div>
              <strong>{todayCount}</strong>
              <span>今日练习</span>
              <em>今日完成 {completedCount > 0 ? completedCount : 0} 道</em>
            </div>
          </div>
          <div className="practice-stat-card">
            <span className="practice-stat-icon practice-stat-icon--done" aria-hidden="true">✓</span>
            <div>
              <strong>{completedCount}</strong>
              <span>已完成</span>
              <em>累计完成 {completedCount} 道</em>
            </div>
          </div>
          <div className="practice-stat-card practice-stat-card--hint">
            <span className="practice-stat-icon practice-stat-icon--pending" aria-hidden="true">💡</span>
            <div>
              <strong>{pendingCount > 0 ? pendingCount : "暂无"}</strong>
              <span>{pendingCount > 0 ? "待练习" : "练习记录"}</span>
              <em>{pendingCount > 0 ? "继续完成待练题" : "生成一组题开始吧"}</em>
            </div>
          </div>
        </div>

        <div className="practice-workbench-grid">
          <main className="practice-main-column">
            <div className="practice-filter-card">
              <div className="task-center-filters practice-filters">
                <div className="task-filter-item practice-filter-item">
                  <label className="field-label">课程筛选</label>
                  <select
                    className="field"
                    value={courseFilter}
                    onChange={(e) => { setCourseFilter(e.target.value); setKpFilter(""); }}
                  >
                    <option value="">全部课程</option>
                    {courseOptions.map((item) => (
                      <option key={item} value={item}>
                        {getSubjectLabel(item)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="task-filter-item practice-filter-item practice-filter-item--wide">
                  <label className="field-label">知识点筛选</label>
                  <select
                    className="field"
                    value={kpFilter}
                    onChange={(e) => setKpFilter(e.target.value)}
                  >
                    <option value="">全部知识点</option>
                    {knowledgePoints.map((kp) => (
                      <option key={kp.id} value={kp.id}>
                        {kp.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="task-filter-item practice-filter-item">
                  <label className="field-label">题型筛选</label>
                  <select
                    className="field"
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    {TYPE_OPTIONS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button className="ghost-button compact practice-refresh-button" onClick={loadQuestions}>
                  ↻ 刷新
                </button>
              </div>
              <div className="practice-filter-summary">
                <span>当前筛选：{selectedCourseLabel} / {selectedKnowledgePointLabel} / {selectedTypeLabel}</span>
                <button type="button" onClick={clearFilters}>清空筛选</button>
              </div>
            </div>

            {!loading && papers.length > 0 && (
              <div className="question-section-card practice-paper-section">
                <div className="question-section-head">
                  <h3>试卷列表</h3>
                  <span>共 {papers.length} 张</span>
                </div>
                <div className="practice-paper-list">
                  {papers.map((paper) => (
                    <div key={paper.id} className="practice-paper-card">
                      <div className="practice-paper-icon" aria-hidden="true">卷</div>
                      <div className="practice-paper-main">
                        <h4>{paper.title}</h4>
                        <div className="question-card-meta">
                          {paper.course_id && (
                            <span className="subject-pill small practice-course-pill">
                              {getSubjectLabel(paper.course_id)}
                            </span>
                          )}
                          <span className="subject-pill small practice-source-pill">试卷识别</span>
                          <span className="subject-pill small practice-difficulty-pill">{paper.question_count || 0} 道题</span>
                          <span className="history-meta">{formatDate(paper.updated_at || paper.created_at)}</span>
                        </div>
                      </div>
                      <div className="question-card-actions">
                        <button className="primary-button compact question-start-button" onClick={() => openPaperDetail(paper)}>
                          查看试卷
                        </button>
                        <button className="tiny-button" onClick={() => openPaperDetail(paper)}>
                          继续编辑
                        </button>
                        <button className="tiny-button" onClick={() => openPaperDetail(paper)}>
                          AI 复习建议
                        </button>
                        <button className="tiny-button danger" onClick={() => deletePaper(paper)}>
                          删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {loading ? (
              <div className="empty-state practice-loading">加载中...</div>
            ) : questions.length === 0 && papers.length === 0 ? (
              <div className="empty-inline practice-empty">
                <div className="practice-empty-left">
                  <div className="practice-empty-icon" aria-hidden="true">📋</div>
                  <h3>还没有匹配的练习题</h3>
                  <p>你可以根据当前课程和知识点生成一组练习，也可以手动创建题目</p>
                  <div className="practice-empty-actions">
                    <button
                      className="primary-button compact practice-action-button practice-action-button--ai"
                      onClick={openGenerateModal}
                    >
                      ✨ AI 生成题目
                    </button>
                    <button
                      className="ghost-button compact practice-action-button"
                      onClick={openCreateModal}
                    >
                      ＋ 新建题目
                    </button>
                  </div>
                </div>
                <div className="practice-empty-tips">
                  <div className="practice-tip-card">
                    <span>🎯</span>
                    <div>
                      <strong>选择具体知识点</strong>
                      <p>选择更具体的知识点，生成更精准</p>
                    </div>
                  </div>
                  <div className="practice-tip-card">
                    <span>📊</span>
                    <div>
                      <strong>从基础题开始</strong>
                      <p>先从基础题开始，逐步提高难度</p>
                    </div>
                  </div>
                  <div className="practice-tip-card">
                    <span>🏆</span>
                    <div>
                      <strong>完成后查看解析</strong>
                      <p>做完练习后，查看解析，巩固知识</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="question-section-card">
                <div className="question-section-head">
                  <h3>练习题列表</h3>
                  <span>共 {totalCount} 条</span>
                </div>
                <div className="question-list">
                  {questions.map((q) => (
                    <div key={q.id} className="question-card">
                      <div className="question-card-main">
                        <h4 className="question-card-title">{q.title}</h4>
                        <div className="question-card-meta">
                          {q.course_id && (
                            <span className="subject-pill small practice-course-pill">
                              {getSubjectLabel(q.course_id)}
                            </span>
                          )}
                          {q.knowledge_point_title && (
                            <span className="subject-pill small practice-kp-pill">
                              {q.knowledge_point_title}
                            </span>
                          )}
                          <span className={`q-type-badge ${getTypeClass(q.type)}`}>
                            {TYPE_LABELS[q.type] || q.type}
                          </span>
                          {q.difficulty && (
                            <span className="subject-pill small practice-difficulty-pill">{DIFFICULTY_LABELS[q.difficulty] || q.difficulty}</span>
                          )}
                          {q.source_style && (
                            <span className="subject-pill small practice-style-pill">
                              {STYLE_LABELS[q.source_style] || q.source_style}
                            </span>
                          )}
                          {q.source && (
                            <span className="subject-pill small practice-source-pill">
                              {q.source === "ai" ? "AI 原创生成" : (SOURCE_LABELS[q.source] || q.source)}
                            </span>
                          )}
                          <span className="history-meta">
                            {formatDate(q.updated_at || q.created_at)}
                          </span>
                        </div>
                      </div>
                      <div className="question-card-actions">
                        {q.type === "programming" || q.source === "code_studio" ? (
                          <button className="primary-button compact question-start-button" onClick={goCodeStudio}>
                            去编程助手练习
                          </button>
                        ) : (
                          <>
                            <button className="primary-button compact question-start-button" onClick={() => openDetail(q)}>
                              开始练习
                            </button>
                            <button className="tiny-button" onClick={() => openDetail(q)}>
                              查看详情
                            </button>
                          </>
                        )}
                        <button
                          className="tiny-button danger"
                          onClick={() => deleteQuestion(q)}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </main>

          <aside className="practice-side-column">
            <div className="practice-side-card practice-ai-card">
              <div className="practice-side-card-title">
                <span>🤖</span>
                <h3>AI 练习助手</h3>
              </div>
              <p>根据当前课程和知识点，AI 帮你智能生成练习题</p>
              <button className="primary-button compact practice-side-action" onClick={openGenerateModal}>
                ✨ AI 生成题目
              </button>
            </div>

            <div className="practice-side-card">
              <h3>题库来源</h3>
              <div className="practice-source-actions">
                <button type="button" onClick={openCreateModal}>手动录入题目</button>
                <button type="button" onClick={openImportModal}>上传试卷识别</button>
                <button type="button" onClick={openGenerateModal}>AI 生成题目</button>
              </div>
            </div>

            <div className="practice-side-card">
              <h3>推荐练习方式</h3>
              <ol className="practice-steps">
                <li>
                  <span>1</span>
                  <div>
                    <strong>先选择知识点</strong>
                    <p>选择具体知识点，生成更精准</p>
                  </div>
                </li>
                <li>
                  <span>2</span>
                  <div>
                    <strong>生成 3~5 道题</strong>
                    <p>建议每次练习 3~5 道题目</p>
                  </div>
                </li>
                <li>
                  <span>3</span>
                  <div>
                    <strong>做完查看解析</strong>
                    <p>巩固知识，总结错题点</p>
                  </div>
                </li>
              </ol>
            </div>

            <div className="practice-side-card">
              <div className="practice-side-card-title">
                <span>☷</span>
                <h3>当前筛选</h3>
              </div>
              <div className="practice-current-filter">
                <div><span>课程：</span><strong>{selectedCourseLabel}</strong></div>
                <div><span>知识点：</span><strong>{selectedKnowledgePointLabel}</strong></div>
                <div><span>题型：</span><strong>{selectedTypeLabel}</strong></div>
              </div>
              <button className="practice-clear-link" type="button" onClick={clearFilters}>清空筛选</button>
            </div>

            <div className="practice-side-card">
              <h3>快捷入口</h3>
              <div className="practice-quick-grid">
                <button type="button">题型分布</button>
                <button type="button">知识点分布</button>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* Detail Drawer */}
      {detailQuestion && (
        <div className="practice-drawer-overlay" onClick={() => setDetailQuestion(null)}>
          <div className="practice-detail-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{detailQuestion.title}</h3>
              <button className="modal-close" onClick={() => setDetailQuestion(null)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <div className="question-detail-meta">
                <span className={`q-type-badge ${getTypeClass(detailQuestion.type)}`}>
                  {TYPE_LABELS[detailQuestion.type] || detailQuestion.type}
                </span>
                {detailQuestion.difficulty && (
                  <span className="subject-pill small">{DIFFICULTY_LABELS[detailQuestion.difficulty] || detailQuestion.difficulty}</span>
                )}
                {detailQuestion.course_id && (
                  <span className="subject-pill small">
                    {getSubjectLabel(detailQuestion.course_id)}
                  </span>
                )}
                {detailQuestion.knowledge_point_title && (
                  <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                    {detailQuestion.knowledge_point_title}
                  </span>
                )}
              </div>

              <div className="question-detail-content">
                <div className="question-content-text">
                  {detailQuestion.content}
                </div>

                {["choice", "single_choice", "multiple_choice", "true_false"].includes(detailQuestion.type) && detailQuestion.options && (
                  <div className="question-options">
                    {(detailQuestion.options || "").split("\n").filter(Boolean).map((opt, i) => (
                      <label key={i} className="question-option-label">
                        <input
                          type="radio"
                          name="choice_answer"
                          value={opt.trim().charAt(0)}
                          checked={userAnswer === opt.trim().charAt(0)}
                          onChange={(e) => setUserAnswer(e.target.value)}
                        />
                        <span>{opt.trim()}</span>
                      </label>
                    ))}
                  </div>
                )}

                {["short_answer", "fill_blank"].includes(detailQuestion.type) && (
                  <textarea
                    className="field"
                    rows={4}
                    placeholder="请输入你的答案..."
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                  />
                )}
              </div>

              {(detailQuestion.answer || detailQuestion.explanation) && (
                <div className="question-answer-section">
                  <button
                    type="button"
                    className="practice-answer-toggle"
                    onClick={() => setShowAnswer((v) => !v)}
                  >
                    {showAnswer ? "隐藏答案与解析" : "查看答案与解析"}
                  </button>
                  {showAnswer && (
                    <>
                      {detailQuestion.answer && (
                        <>
                          <strong>参考答案：</strong>
                          <p>{detailQuestion.answer}</p>
                        </>
                      )}
                      {detailQuestion.explanation && (
                        <>
                          <strong>解析：</strong>
                          <p>{detailQuestion.explanation}</p>
                        </>
                      )}
                    </>
                  )}
                </div>
              )}

              <div className="question-detail-actions">
                <button
                  className="primary-button compact"
                  disabled={detailActionLoading || !userAnswer.trim()}
                  onClick={submitAnswer}
                >
                  {detailActionLoading ? "提交中..." : "提交答案"}
                </button>
                <button
                  className="ghost-button compact"
                  disabled={feedbackLoading || !userAnswer.trim()}
                  onClick={requestFeedback}
                >
                  {feedbackLoading ? "AI 分析中..." : "AI 反馈"}
                </button>
                <button
                  className="ghost-button compact"
                  disabled={aiExplainLoadingId === detailQuestion.id}
                  onClick={() => requestQuestionAiExplain(detailQuestion)}
                >
                  {aiExplainLoadingId === detailQuestion.id ? "解析中..." : "AI 解析"}
                </button>
              </div>

              {feedback && (
                <div className="ai-feedback-box">
                  <strong>AI 反馈：</strong>
                  <div
                    className="ai-feedback-content"
                    dangerouslySetInnerHTML={{ __html: feedback.replace(/\n/g, "<br>") }}
                  />
                </div>
              )}

              {attempts.length > 0 && (
                <div className="attempts-section">
                  <h4>作答历史</h4>
                  {attempts.map((a) => (
                    <div key={a.id} className="attempt-item">
                      <div className="attempt-meta">
                        <span className={`attempt-result attempt-result--${a.self_result || "unknown"}`}>
                          {RESULT_LABELS[a.self_result] || "未知"}
                        </span>
                        <span className="history-meta">
                          {formatDate(a.created_at)}
                        </span>
                      </div>
                      {a.user_answer && (
                        <div className="attempt-answer">
                          <span className="history-meta">你的答案：</span>
                          {a.user_answer}
                        </div>
                      )}
                      {a.ai_feedback && (
                        <div className="attempt-feedback">
                          <span className="history-meta">AI 反馈：</span>
                          <div
                            className="ai-feedback-content"
                            dangerouslySetInnerHTML={{ __html: a.ai_feedback.replace(/\n/g, "<br>") }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Paper Detail Drawer */}
      {paperDetail && (
        <div className="practice-drawer-overlay" onClick={() => setPaperDetail(null)}>
          <div className="practice-detail-drawer practice-paper-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{paperDetail.title}</h3>
                <div className="question-card-meta">
                  {paperDetail.course_id && (
                    <span className="subject-pill small practice-course-pill">{getSubjectLabel(paperDetail.course_id)}</span>
                  )}
                  <span className="subject-pill small practice-source-pill">试卷识别</span>
                  <span className="subject-pill small practice-difficulty-pill">{paperQuestions.length} 道题</span>
                  <span className="history-meta">{formatDate(paperDetail.updated_at || paperDetail.created_at)}</span>
                </div>
              </div>
              <button className="modal-close" onClick={() => setPaperDetail(null)}>
                &times;
              </button>
            </div>
            <div className="practice-paper-toc">
              {paperQuestions.map((q, idx) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setExpandedPaperQuestions((prev) => ({ ...prev, [q.id]: !prev[q.id] }))}
                >
                  {q.question_order || idx + 1}
                </button>
              ))}
            </div>
            <div className="practice-paper-question-list">
              {paperLoading ? (
                <div className="empty-state">加载试卷中...</div>
              ) : paperQuestions.map((q, idx) => {
                const expanded = Boolean(expandedPaperQuestions[q.id]);
                return (
                  <div key={q.id} className="practice-paper-question">
                    <button
                      type="button"
                      className="practice-paper-question-head"
                      onClick={() => setExpandedPaperQuestions((prev) => ({ ...prev, [q.id]: !expanded }))}
                    >
                      <span>第 {q.question_order || idx + 1} 题</span>
                      <strong>{q.title}</strong>
                      <em>{expanded ? "收起" : "展开"}</em>
                    </button>
                    {expanded && (
                      <div className="practice-paper-question-body">
                        <div className="question-detail-meta">
                          <span className={`q-type-badge ${getTypeClass(q.type)}`}>{TYPE_LABELS[q.type] || q.type}</span>
                          {q.difficulty && <span className="subject-pill small practice-difficulty-pill">{DIFFICULTY_LABELS[q.difficulty] || q.difficulty}</span>}
                          {q.knowledge_point_title && <span className="subject-pill small practice-kp-pill">{q.knowledge_point_title}</span>}
                        </div>
                        <div className="question-content-text">{q.content}</div>
                        {q.options && (
                          <div className="question-options">
                            {q.options.split("\n").filter(Boolean).map((opt, optIdx) => (
                              <div key={optIdx} className="question-option-label">{opt.trim()}</div>
                            ))}
                          </div>
                        )}
                        {(q.answer || q.explanation) && (
                          <div className="question-answer-section">
                            {q.answer && <p><strong>答案：</strong>{q.answer}</p>}
                            {q.explanation && <p><strong>解析：</strong>{q.explanation}</p>}
                          </div>
                        )}
                        {q.raw_text && (
                          <details className="practice-raw-text">
                            <summary>查看原始识别文本</summary>
                            <pre>{q.raw_text}</pre>
                          </details>
                        )}
                        <div className="question-detail-actions">
                          <button className="ghost-button compact" onClick={() => openDetail(q)}>编辑 / 练习</button>
                          <button
                            className="ghost-button compact"
                            disabled={aiExplainLoadingId === q.id}
                            onClick={() => requestQuestionAiExplain(q, true)}
                          >
                            {aiExplainLoadingId === q.id ? "解析中..." : "AI 解析"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建题目</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <label className="field-label">课程</label>
              <select
                className="field"
                value={createCourse}
                onChange={(e) => {
                  setCreateCourse(e.target.value);
                  setCreateModuleId("");
                  setCreateKpId("");
                }}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <div className="practice-kp-picker">
                <label className="field-label">知识点模块（可选）</label>
                {knowledgePointModules.length === 0 ? (
                  <p className="practice-kp-empty">
                    当前课程暂无知识点路线，可先在知识点学习中生成路线，或不绑定知识点。
                  </p>
                ) : (
                  <>
                    <select
                      className="field"
                      value={createModuleId}
                      onChange={(e) => {
                        setCreateModuleId(e.target.value);
                        setCreateKpId("");
                      }}
                    >
                      <option value="">不绑定知识点模块</option>
                      {knowledgePointModules.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>

                    <label className="field-label">小知识点（可选）</label>
                    <select
                      className="field"
                      value={createKpId}
                      onChange={(e) => setCreateKpId(e.target.value)}
                      disabled={!createModuleId || createModuleChildren.length === 0}
                    >
                      <option value="">
                        {createModuleId ? "仅绑定大模块" : "请先选择知识点模块"}
                      </option>
                      {createModuleChildren.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>

              <label className="field-label">题型 *</label>
              <select
                className="field"
                value={createType}
                onChange={(e) => setCreateType(e.target.value)}
              >
                {TYPE_OPTIONS.filter((o) => o.value).map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              {createType === "programming" ? (
                <div className="practice-code-guide">
                  <strong>编程题请前往编程助手创建和练习。</strong>
                  <p>编程题需要运行环境、测试用例和代码反馈，已在编程助手中集中处理。</p>
                  <button className="primary-button compact" type="button" onClick={goCodeStudio}>
                    前往编程助手
                  </button>
                </div>
              ) : (
                <>
                  <label className="field-label">难度</label>
                  <select
                    className="field"
                    value={createDifficulty}
                    onChange={(e) => setCreateDifficulty(e.target.value)}
                  >
                    {DIFFICULTY_OPTIONS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>

                  <label className="field-label">题目标题 *</label>
                  <input
                    className="field"
                    placeholder="例如：数组排序的时间复杂度"
                    value={createTitle}
                    onChange={(e) => setCreateTitle(e.target.value)}
                  />

                  <label className="field-label">题目内容 *</label>
                  <textarea
                    className="field"
                    rows={4}
                    placeholder="输入题面内容..."
                    value={createContent}
                    onChange={(e) => setCreateContent(e.target.value)}
                  />

                  {createType === "choice" && (
                    <>
                      <label className="field-label">选项（每行一个，格式：A. xxx）</label>
                      <textarea
                        className="field"
                        rows={4}
                        placeholder={"A. 选项一\nB. 选项二\nC. 选项三\nD. 选项四"}
                        value={createOptions}
                        onChange={(e) => setCreateOptions(e.target.value)}
                      />
                    </>
                  )}

                  <label className="field-label">参考答案</label>
                  <input
                    className="field"
                    placeholder="选择题填选项字母（A/B/C/D），简答题填参考答案"
                    value={createAnswer}
                    onChange={(e) => setCreateAnswer(e.target.value)}
                  />

                  <label className="field-label">解析（可选）</label>
                  <textarea
                    className="field"
                    rows={3}
                    placeholder="题目解析..."
                    value={createExplanation}
                    onChange={(e) => setCreateExplanation(e.target.value)}
                  />
                </>
              )}
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
                disabled={createSaving || (createType !== "programming" && (!createTitle.trim() || !createContent.trim()))}
                onClick={createQuestion}
              >
                {createType === "programming" ? "前往编程助手" : (createSaving ? "创建中..." : "创建题目")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Generate Modal */}
      {showGenerateModal && (
        <div className="modal-overlay" onClick={() => setShowGenerateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>AI 生成题目</h3>
              <button className="modal-close" onClick={() => setShowGenerateModal(false)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <label className="field-label">课程</label>
              <select
                className="field"
                value={genCourse}
                onChange={(e) => {
                  setGenCourse(e.target.value);
                  setGenModuleId("");
                  setGenKpId("");
                }}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <div className="practice-kp-picker">
                <label className="field-label">知识点模块（可选）</label>
                {knowledgePointModules.length === 0 ? (
                  <p className="practice-kp-empty">
                    当前课程暂无知识点路线，可先在知识点学习中生成路线，或不绑定知识点。
                  </p>
                ) : (
                  <>
                    <select
                      className="field"
                      value={genModuleId}
                      onChange={(e) => {
                        setGenModuleId(e.target.value);
                        setGenKpId("");
                      }}
                    >
                      <option value="">不指定知识点模块</option>
                      {knowledgePointModules.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>

                    <label className="field-label">小知识点（可选）</label>
                    <select
                      className="field"
                      value={genKpId}
                      onChange={(e) => setGenKpId(e.target.value)}
                      disabled={!genModuleId || genModuleChildren.length === 0}
                    >
                      <option value="">
                        {genModuleId ? "仅使用大模块" : "请先选择知识点模块"}
                      </option>
                      {genModuleChildren.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>

              <label className="field-label">题型</label>
              <select
                className="field"
                value={genType}
                onChange={(e) => setGenType(e.target.value)}
              >
                {TYPE_OPTIONS.filter((item) => item.value).map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              {genType === "programming" && (
                <div className="practice-code-guide">
                  <strong>编程题请前往编程助手生成。</strong>
                  <p>编程题需要测试用例、代码运行和反馈流程，建议在编程助手中完成。</p>
                  <button className="primary-button compact" type="button" onClick={goCodeStudio}>
                    前往编程助手
                  </button>
                </div>
              )}

              <label className="field-label">难度</label>
              <select
                className="field"
                value={genDifficulty}
                onChange={(e) => setGenDifficulty(e.target.value)}
              >
                {DIFFICULTY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="field-label">题型风格</label>
              <select
                className="field"
                value={genSourceStyle}
                onChange={(e) => setGenSourceStyle(e.target.value)}
              >
                {STYLE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="field-label">生成数量</label>
              <select
                className="field"
                value={genCount}
                onChange={(e) => setGenCount(Number(e.target.value))}
              >
                <option value={3}>3 道</option>
                <option value={5}>5 道</option>
                <option value={10}>10 道</option>
              </select>

              <div className="practice-generate-note">
                AI 会参考经典计算机学习题型风格生成原创题，不会直接复制网站原题。
              </div>

              <label className="practice-toggle-row">
                <input
                  type="checkbox"
                  checked={genRequireReasoning}
                  onChange={(e) => setGenRequireReasoning(e.target.checked)}
                />
                <span>生成综合题 / 多步推理题</span>
              </label>

              <label className="practice-toggle-row">
                <input
                  type="checkbox"
                  checked={genAvoidTooSimple}
                  onChange={(e) => setGenAvoidTooSimple(e.target.checked)}
                />
                <span>避免简单概念题</span>
              </label>
            </div>
            <div className="task-form-actions">
              <button
                className="ghost-button compact"
                onClick={() => setShowGenerateModal(false)}
              >
                取消
              </button>
              <button
                className="primary-button compact"
                disabled={genLoading}
                onClick={generateQuestions}
              >
                {genType === "programming" ? "前往编程助手" : (genLoading ? "生成中..." : "开始生成")}
              </button>
            </div>
          </div>
        </div>
      )}

      {showImportModal && (
        <div className="modal-overlay" onClick={() => setShowImportModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>上传试卷识别题目</h3>
              <button className="modal-close" onClick={() => setShowImportModal(false)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <label className="field-label">课程</label>
              <select
                className="field"
                value={importCourse}
                onChange={(e) => {
                  setImportCourse(e.target.value);
                  setImportModuleId("");
                  setImportKpId("");
                }}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <div className="practice-kp-picker">
                <label className="field-label">知识点模块（可选）</label>
                {knowledgePointModules.length === 0 ? (
                  <p className="practice-kp-empty">
                    当前课程暂无知识点路线，可先在知识点学习中生成路线，或不绑定知识点。
                  </p>
                ) : (
                  <>
                    <select
                      className="field"
                      value={importModuleId}
                      onChange={(e) => {
                        setImportModuleId(e.target.value);
                        setImportKpId("");
                      }}
                    >
                      <option value="">不指定知识点模块</option>
                      {knowledgePointModules.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>

                    <label className="field-label">小知识点（可选）</label>
                    <select
                      className="field"
                      value={importKpId}
                      onChange={(e) => setImportKpId(e.target.value)}
                      disabled={!importModuleId || importModuleChildren.length === 0}
                    >
                      <option value="">
                        {importModuleId ? "仅使用大模块" : "请先选择知识点模块"}
                      </option>
                      {importModuleChildren.map((kp) => (
                        <option key={kp.id} value={kp.id}>
                          {kp.title}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>

              <label className="field-label">试卷文件</label>
              <input
                className="field"
                type="file"
                accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp"
                onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              />
              <div className="practice-upload-guide">
                <strong>支持 PDF、图片、Word、TXT、Markdown</strong>
                <p>文件只用于本次试卷识别，不会自动加入资料库。识别后可勾选并编辑题目草稿再导入。</p>
              </div>

              {importError && <div className="practice-import-error">{importError}</div>}

              {importDrafts.length > 0 && (
                <div className="practice-draft-list">
                  <label className="field-label">试卷名称</label>
                  <input
                    className="field"
                    value={importPaperTitle}
                    onChange={(e) => setImportPaperTitle(e.target.value)}
                    placeholder="请输入试卷名称"
                  />
                  <h4>识别结果草稿</h4>
                  {importExtractMeta && formatExtractMethodLabel(importExtractMeta) && (
                    <div className={`practice-extract-method-badge ${formatExtractMethodLabel(importExtractMeta).cssClass}`}>
                      <span className="practice-extract-method-icon" aria-hidden="true">
                        {importExtractMeta.qwen_used ? "🤖" : "📄"}
                      </span>
                      <span>{formatExtractMethodLabel(importExtractMeta).label}</span>
                    </div>
                  )}
                  {importDrafts.map((draft, idx) => (
                    <div key={idx} className="practice-draft-card">
                      <label className="practice-draft-check">
                        <input
                          type="checkbox"
                          checked={Boolean(importSelected[idx])}
                          onChange={(e) => setImportSelected((prev) => ({ ...prev, [idx]: e.target.checked }))}
                        />
                        <span>导入这道题</span>
                      </label>
                      <input
                        className="field"
                        value={draft.title || ""}
                        onChange={(e) => updateImportDraft(idx, { title: e.target.value })}
                        placeholder="题目标题"
                      />
                      <textarea
                        className="field"
                        rows={3}
                        value={draft.question_text || ""}
                        onChange={(e) => updateImportDraft(idx, { question_text: e.target.value })}
                        placeholder="题干"
                      />
                      <div className="practice-draft-grid">
                        <select
                          className="field"
                          value={draft.type || "short_answer"}
                          onChange={(e) => updateImportDraft(idx, { type: e.target.value })}
                        >
                          {TYPE_OPTIONS.filter((item) => item.value).map((item) => (
                            <option key={item.value} value={item.value}>{item.label}</option>
                          ))}
                        </select>
                        <select
                          className="field"
                          value={draft.difficulty || "medium"}
                          onChange={(e) => updateImportDraft(idx, { difficulty: e.target.value })}
                        >
                          {DIFFICULTY_OPTIONS.map((item) => (
                            <option key={item.value} value={item.value}>{item.label}</option>
                          ))}
                        </select>
                      </div>
                      <textarea
                        className="field"
                        rows={2}
                        value={draft.options || ""}
                        onChange={(e) => updateImportDraft(idx, { options: e.target.value })}
                        placeholder="选项（如有）"
                      />
                      <input
                        className="field"
                        value={draft.answer || ""}
                        onChange={(e) => updateImportDraft(idx, { answer: e.target.value })}
                        placeholder="答案"
                      />
                      <textarea
                        className="field"
                        rows={2}
                        value={draft.explanation || ""}
                        onChange={(e) => updateImportDraft(idx, { explanation: e.target.value })}
                        placeholder="解析"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="task-form-actions">
              <button className="ghost-button compact" onClick={() => setShowImportModal(false)}>
                取消
              </button>
              <button
                className="ghost-button compact"
                disabled={!importFile || importLoading}
                onClick={parseImportFile}
              >
                {importLoading ? "识别中..." : "开始识别"}
              </button>
              <button
                className="primary-button compact"
                disabled={importDrafts.length === 0 || importSaving}
                onClick={confirmImportDrafts}
              >
                {importSaving ? "导入中..." : "导入题库"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
