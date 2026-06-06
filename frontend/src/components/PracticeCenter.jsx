import { useEffect, useRef, useState } from "react";

const API_BASE = "/api";
const IMPORT_JOB_STORAGE_KEY = "practice_import_job_id";
const IMPORT_JOB_LONG_RUNNING_SECONDS = 180;

const TYPE_OPTIONS = [
  { value: "", label: "全部题型" },
  { value: "choice", label: "选择题" },
  { value: "multiple_choice", label: "多选题" },
  { value: "true_false", label: "判断题" },
  { value: "fill_blank", label: "填空题" },
  { value: "short_answer", label: "简答题" },
];

const DIFFICULTY_OPTIONS = [
  { value: "easy", label: "简单" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "困难" },
];

const OPTION_LABELS = ["A", "B", "C", "D"];

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

const isChoiceLikeType = (type) => ["choice", "single_choice", "multiple_choice", "true_false"].includes(type);

const isAiGeneratedQuestion = (question) => {
  const source = String(question?.source || question?.source_type || "").trim();
  return source === "ai_generated" || source === "ai";
};

const PROGRAMMING_QUESTION_TYPES = new Set([
  "programming",
  "code",
  "coding",
  "code_question",
  "programming_question",
]);

const isProgrammingQuestion = (question) => {
  const type = String(question?.type || question?.question_type || "").trim();
  const source = String(question?.source || question?.source_type || "").trim();
  return PROGRAMMING_QUESTION_TYPES.has(type) || source === "code_studio";
};

const normalizeGenerateCount = (value) => {
  const n = Number(value);
  if (Number.isNaN(n)) return 1;
  return Math.min(10, Math.max(1, Math.floor(n)));
};

const BATCH_OBJECTIVE_TYPES = new Set([
  "choice",
  "single_choice",
  "multiple_choice",
  "true_false",
  "fill_blank",
  "select",
  "judge",
]);

const isBatchObjectiveQuestion = (question) => BATCH_OBJECTIVE_TYPES.has(question?.type);

const getQuestionOptionLabels = (question) => {
  const lines = String(question?.options || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return new Set(
    lines
      .map((line) => {
        const matched = line.match(/^([A-Za-z])[\.\、\)]\s*/);
        return matched ? matched[1].toUpperCase() : "";
      })
      .filter(Boolean)
  );
};

const hasValidObjectiveAnswerStructure = (question) => {
  if (!isBatchObjectiveQuestion(question)) return false;
  if (question?.type === "fill_blank" || question?.type === "true_false" || question?.type === "judge") {
    return Boolean(String(question?.answer || "").trim());
  }
  const labels = getQuestionOptionLabels(question);
  if (!labels.size) return false;
  const answers = question?.type === "multiple_choice" || question?.type === "select"
    ? parseAnswerList(question?.answer)
    : [normalizePracticeAnswer(question?.answer)];
  return answers.length > 0 && answers.every((label) => labels.has(label));
};

const normalizePracticeAnswer = (value = "") => (
  String(value || "")
    .trim()
    .replace(/^[(（]?\s*([A-Za-z])\s*[)）.、]?.*$/, "$1")
    .toUpperCase()
);

const parseAnswerList = (answer) => {
  if (Array.isArray(answer)) return answer.map((item) => normalizePracticeAnswer(item)).filter(Boolean);
  const text = String(answer || "").trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed.map((item) => normalizePracticeAnswer(item)).filter(Boolean);
  } catch {
    // Plain text answer, continue with delimiter parsing.
  }
  if (/^[A-Za-z]{2,}$/.test(text)) return text.toUpperCase().split("");
  return text
    .split(/[,，、;；\s]+/)
    .map((item) => normalizePracticeAnswer(item))
    .filter(Boolean);
};

const normalizeTextAnswer = (answer = "") => (
  String(answer || "")
    .trim()
    .replace(/[，。；：！？]/g, (mark) => ({ "，": ",", "。": ".", "；": ";", "：": ":", "！": "!", "？": "?" }[mark] || mark))
    .replace(/\s+/g, " ")
    .toLowerCase()
);

const normalizeTrueFalseAnswer = (answer = "") => {
  const value = normalizeTextAnswer(answer);
  if (["true", "t", "1", "正确", "对", "是", "yes", "y", "a"].includes(value)) return "true";
  if (["false", "f", "0", "错误", "错", "否", "no", "n", "b"].includes(value)) return "false";
  return value;
};

const getQuestionAnalysis = (question) => question?.explanation || question?.analysis || "";

const gradeObjectiveQuestion = (question, userAnswer) => {
  if (!question || !isBatchObjectiveQuestion(question)) return false;
  const type = question.type;
  const correctAnswer = question.answer;
  if (type === "multiple_choice" || type === "select") {
    const expected = parseAnswerList(correctAnswer).sort().join("|");
    const actual = parseAnswerList(userAnswer).sort().join("|");
    return Boolean(expected) && actual === expected;
  }
  if (type === "true_false" || type === "judge") {
    return normalizeTrueFalseAnswer(userAnswer) === normalizeTrueFalseAnswer(correctAnswer);
  }
  if (type === "fill_blank") {
    const actual = normalizeTextAnswer(userAnswer);
    if (!actual) return false;
    try {
      const parsed = JSON.parse(String(correctAnswer || ""));
      if (Array.isArray(parsed)) return parsed.some((item) => normalizeTextAnswer(item) === actual);
    } catch {
      // Plain text answer, compare directly.
    }
    return normalizeTextAnswer(correctAnswer) === actual;
  }
  return normalizePracticeAnswer(userAnswer) === normalizePracticeAnswer(correctAnswer);
};

const INTERNAL_REASONING_KEYWORDS = [
  "我认为",
  "我可能",
  "我怀疑",
  "让我重新",
  "重新检查",
  "重新计算",
  "鉴于时间",
  "为了配合选项",
  "前面算错",
  "我误解",
  "我搞错",
  "选项不匹配",
  "无法匹配",
  "有点乱",
];

const containsInternalReasoning = (text = "") => (
  INTERNAL_REASONING_KEYWORDS.some((keyword) => String(text || "").includes(keyword))
);

function QuestionAnalysisBlock({ analysis, limit = 800 }) {
  const [expanded, setExpanded] = useState(false);
  const text = String(analysis || "").trim();
  if (!text) return null;

  const shouldCollapse = text.length > limit;
  const displayText = shouldCollapse && !expanded ? `${text.slice(0, limit)}...` : text;
  const hasInternalReasoning = containsInternalReasoning(text);

  return (
    <div className="practice-analysis-block">
      {hasInternalReasoning && (
        <div className="practice-analysis-warning">
          该解析可能包含无效推理内容，建议重新生成解析。
        </div>
      )}
      <p className="practice-analysis-text">{displayText}</p>
      {shouldCollapse && (
        <button
          type="button"
          className="practice-analysis-expand"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收起解析" : "展开全部解析"}
        </button>
      )}
    </div>
  );
}

function AiGeneratedAttemptSummary({ question, attempt }) {
  if (!question || !attempt) return null;
  const isObjective = isChoiceLikeType(question.type);
  const localResult = normalizePracticeAnswer(attempt.user_answer) === normalizePracticeAnswer(question.answer)
    ? "correct"
    : "incorrect";
  const result = isObjective && question.answer
    ? (attempt.self_result && attempt.self_result !== "unknown" ? attempt.self_result : localResult)
    : "unknown";

  return (
    <div className="practice-local-result">
      {isObjective && result !== "unknown" && (
        <div className={`practice-local-result-status practice-local-result-status--${result}`}>
          {result === "correct" ? "正确" : "错误"}
        </div>
      )}
      {!isObjective && (
        <div className="practice-local-result-status practice-local-result-status--unknown">
          已提交，简答题请对照参考答案自查。
        </div>
      )}
      {attempt.user_answer && (
        <div className="practice-local-result-row">
          <span>你的答案：</span>
          <strong>{attempt.user_answer}</strong>
        </div>
      )}
    </div>
  );
}

// Strip common placeholder strings from parsed option content.
const stripPlaceholderContent = (content) => {
  const trimmed = (content || "").trim();
  if (/^[A-Za-z]\s*选项内容$/.test(trimmed)) return "";
  if (/^选项内容$/.test(trimmed)) return "";
  return trimmed;
};

const parseOptionItems = (optionsText = "") => {
  const lines = (optionsText || "").split("\n");
  const parsed = [];

  for (let i = 0; i < lines.length; i++) {
    const text = lines[i].trim();
    if (!text) continue;

    // Match: (A) xxx, A. xxx, A xxx, (e) xxx, e. xxx, etc.
    const match = text.match(/^[(（]?\s*([A-Za-z])\s*[)）.、]?\s*(.*)$/);
    if (match) {
      parsed.push({
        label: match[1].toUpperCase(),
        content: stripPlaceholderContent(match[2]),
      });
    } else {
      parsed.push({
        label: String.fromCharCode(65 + parsed.length),
        content: stripPlaceholderContent(text),
      });
    }
  }

  // Deduplicate by label
  const seen = new Set();
  const deduped = [];
  for (const item of parsed) {
    if (!seen.has(item.label)) {
      seen.add(item.label);
      deduped.push(item);
    }
  }
  return deduped;
};

// Try to extract option lines from raw text (question stem + options mixed).
const extractOptionsFromText = (text) => {
  if (!text) return [];
  const lines = text.split("\n");
  const optionLines = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    // Match option-like lines: (A), A., A, (e), etc.
    if (/^[(\uff08]?\s*[A-Za-z]\s*[)\uff09.\u3001]/.test(trimmed)) {
      optionLines.push(trimmed);
    }
  }

  return optionLines.length > 0 ? parseOptionItems(optionLines.join("\n")) : [];
};

// Normalize options from the full question object.
const normalizeEditableOptions = (question) => {
  if (!question) return OPTION_LABELS.map((label) => ({ label, content: "" }));

  // Priority 1: question.options
  if (question.options != null && question.options !== "") {
    if (Array.isArray(question.options)) {
      const parsed = question.options
        .map((item, index) => {
          if (typeof item === "string") {
            const text = item.trim();
            const match = text.match(/^[(\uff08]?\s*([A-Za-z])\s*[)\uff09.\u3001]?\s*(.*)$/);
            return {
              label: (match?.[1] || String.fromCharCode(65 + index)).toUpperCase(),
              content: stripPlaceholderContent(match?.[2] ?? text),
            };
          }
          return {
            label: String(item?.label || item?.key || String.fromCharCode(65 + index)).toUpperCase(),
            content: stripPlaceholderContent(item?.content ?? item?.text ?? item?.value ?? ""),
          };
        })
        .filter((item) => item.label);
      if (parsed.length > 0) return parsed;
    }

    if (typeof question.options === "object" && !Array.isArray(question.options)) {
      const parsed = Object.entries(question.options)
        .filter(([, v]) => v != null && String(v).trim() !== "")
        .map(([label, content]) => ({
          label: String(label).toUpperCase(),
          content: stripPlaceholderContent(content),
        }));
      if (parsed.length > 0) return parsed;
    }

    if (typeof question.options === "string") {
      const trimmed = question.options.trim();
      if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
        try {
          const obj = JSON.parse(trimmed);
          if (obj != null) {
            const subResult = normalizeEditableOptions({ options: obj });
            if (subResult.some((item) => item.content)) return subResult;
          }
        } catch { /* fall through */ }
      }
      const parsed = parseOptionItems(trimmed);
      if (parsed.some((item) => item.content)) return parsed;
    }
  }

  // Priority 2: question.options_json
  if (question.options_json != null && question.options_json !== "") {
    let obj = question.options_json;
    if (typeof obj === "string") {
      try { obj = JSON.parse(obj); } catch { obj = null; }
    }
    if (obj != null) {
      const subResult = normalizeEditableOptions({ options: obj });
      if (subResult.some((item) => item.content)) return subResult;
    }
  }

  // Priority 3: parse from question.raw_text
  if (question.raw_text) {
    const fromRaw = extractOptionsFromText(question.raw_text);
    if (fromRaw.length > 0) return fromRaw;
  }

  // Priority 4: parse from question.content
  if (question.content) {
    const fromContent = extractOptionsFromText(question.content);
    if (fromContent.length > 0) return fromContent;
  }

  // Priority 5: empty fallback
  return OPTION_LABELS.map((label) => ({ label, content: "" }));
};

const formatOptionItems = (items) =>
  (items || [])
    .filter((item) => (item.content || "").trim())
    .map((item) => `${item.label}. ${item.content.trim()}`)
    .join("\n");

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
  ai_generated: "AI 生成",
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
  practiceContext = null,
  onClearPracticeContext = () => {},
}) {
  const [questions, setQuestions] = useState([]);
  const [papers, setPapers] = useState([]);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [courseFilter, setCourseFilter] = useState(subject || "");
  const [kpFilter, setKpFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedQuestionIds, setSelectedQuestionIds] = useState(() => new Set());
  const [batchPracticeMode, setBatchPracticeMode] = useState(false);
  const [batchQuestions, setBatchQuestions] = useState([]);
  const [batchCurrentIndex, setBatchCurrentIndex] = useState(0);
  const [batchAnswers, setBatchAnswers] = useState({});
  const [batchResult, setBatchResult] = useState(null);
  const practiceStartRef = useRef(Date.now());
  const [batchNotice, setBatchNotice] = useState("");
  const [batchLoading, setBatchLoading] = useState(false);

  // Detail modal
  const [detailQuestion, setDetailQuestion] = useState(null);
  const [userAnswer, setUserAnswer] = useState("");
  const [attempts, setAttempts] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [submittedAttempt, setSubmittedAttempt] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [detailActionLoading, setDetailActionLoading] = useState(false);
  const [showAnswer, setShowAnswer] = useState(false);
  const [paperDetail, setPaperDetail] = useState(null);
  const [paperQuestions, setPaperQuestions] = useState([]);
  const [expandedPaperQuestions, setExpandedPaperQuestions] = useState({});
  const [paperLoading, setPaperLoading] = useState(false);
  const [aiExplainLoadingId, setAiExplainLoadingId] = useState(null);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [editQuestionForm, setEditQuestionForm] = useState(null);
  const [editModuleId, setEditModuleId] = useState("");
  const [editKpId, setEditKpId] = useState("");
  const [editOptionItems, setEditOptionItems] = useState(parseOptionItems(""));
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

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
  const [genCount, setGenCount] = useState(3);
  const [genSourceStyle, setGenSourceStyle] = useState("mixed");
  const [genRequireReasoning, setGenRequireReasoning] = useState(true);
  const [genAvoidTooSimple, setGenAvoidTooSimple] = useState(true);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState("");
  const [genWarnings, setGenWarnings] = useState([]);
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
  const [importWarnings, setImportWarnings] = useState(null);
  const [importJobId, setImportJobId] = useState(null);
  const [importJobStatus, setImportJobStatus] = useState(null);  // pending | processing | succeeded | failed
  const [importJobProgress, setImportJobProgress] = useState("");
  const [importJob, setImportJob] = useState(null);
  const [taskCompleteSyncing, setTaskCompleteSyncing] = useState(false);
  const [taskCompleteMessage, setTaskCompleteMessage] = useState("");

  // Task AI question preview
  const [taskGenCount, setTaskGenCount] = useState(5);
  const [taskGenLoading, setTaskGenLoading] = useState(false);
  const [taskGenError, setTaskGenError] = useState("");
  const [taskGenQuestions, setTaskGenQuestions] = useState([]);

  // AI temporary practice mode
  const [aiTempQuestions, setAiTempQuestions] = useState([]);
  const [aiTempMode, setAiTempMode] = useState(false);
  const [aiTempAnswers, setAiTempAnswers] = useState({});
  const [aiTempCurrentIndex, setAiTempCurrentIndex] = useState(0);
  const [aiTempResult, setAiTempResult] = useState(null);
  const [aiTempSubmitting, setAiTempSubmitting] = useState(false);
  const aiTempStartRef = useRef(Date.now());

  // Mixed practice suggestion
  const RECOMMENDED_PRACTICE_COUNT = 5;
  const [mixedSuggestionDismissed, setMixedSuggestionDismissed] = useState(false);
  const [mixedSupplementQuestions, setMixedSupplementQuestions] = useState([]);

  // Save AI questions to bank
  const [aiSaveSelected, setAiSaveSelected] = useState(() => new Set());
  const [aiSaveModalOpen, setAiSaveModalOpen] = useState(false);
  const [aiSaveQuestions, setAiSaveQuestions] = useState([]);
  const [aiSaveSaving, setAiSaveSaving] = useState(false);
  const [aiSaveError, setAiSaveError] = useState("");
  const [aiSaveResult, setAiSaveResult] = useState(null);

  const toggleAiSaveSelect = (idx) => {
    setAiSaveSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const openAiSaveModal = () => {
    if (aiSaveSelected.size === 0) return;
    const selected = [];
    aiSaveSelected.forEach((idx) => {
      const q = taskGenQuestions[idx];
      if (q) {
        selected.push({
          idx,
          type: q.type,
          stem: q.stem,
          options: q.options || [],
          answer: q.answer,
          analysis: q.analysis,
          original: q,
        });
      }
    });
    setAiSaveQuestions(selected);
    setAiSaveError("");
    setAiSaveResult(null);
    setAiSaveModalOpen(true);
  };

  const closeAiSaveModal = () => {
    setAiSaveModalOpen(false);
    setAiSaveQuestions([]);
    setAiSaveError("");
    setAiSaveResult(null);
    setAiSaveSelected(new Set());
  };

  const updateAiSaveQuestion = (idx, field, value) => {
    setAiSaveQuestions((prev) =>
      prev.map((q, i) => (i === idx ? { ...q, [field]: value } : q))
    );
  };

  const updateAiSaveOption = (qIdx, optIdx, field, value) => {
    setAiSaveQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qIdx) return q;
        const newOptions = [...q.options];
        if (newOptions[optIdx]) {
          newOptions[optIdx] = { ...newOptions[optIdx], [field]: value };
        }
        return { ...q, options: newOptions };
      })
    );
  };

  const removeAiSaveQuestion = (idx) => {
    setAiSaveQuestions((prev) => prev.filter((_, i) => i !== idx));
    setAiSaveSelected((prev) => {
      const next = new Set(prev);
      const removed = aiSaveQuestions[idx];
      if (removed) next.delete(removed.idx);
      return next;
    });
  };

  const handleAiSaveToBank = async () => {
    if (aiSaveQuestions.length === 0) return;
    setAiSaveSaving(true);
    setAiSaveError("");
    setAiSaveResult(null);
    try {
      const body = {
        username: user.username,
        course_id: practiceContext?.courseId || courseFilter || subject || "",
        knowledge_point_id: practiceContext?.knowledgePointId || null,
        source: "ai_task_preview",
        questions: aiSaveQuestions.map((q) => ({
          type: q.type,
          stem: q.stem,
          options: q.options,
          answer: q.answer,
          analysis: q.analysis,
        })),
      };
      const res = await fetch(`${API_BASE}/practice/questions/batch-create-from-ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "保存失败，请稍后重试");
      }
      // Refresh question list so saved questions appear immediately
      let refreshSuccess = false;
      try {
        await loadQuestions();
        refreshSuccess = true;
      } catch {
        // refresh failed, but questions are saved — show partial success
      }
      setAiSaveResult({ ...data, refreshSuccess, currentTotal: refreshSuccess ? null : "unknown" });
    } catch (e) {
      setAiSaveError(e.message || "保存到题库失败，请稍后重试。");
    } finally {
      setAiSaveSaving(false);
    }
  };

  const loadKnowledgePoints = async (courseId) => {
    if (!user?.username || !courseId) {
      setKnowledgePoints([]);
      return [];
    }
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`
      );
      const data = await res.json();
      if (res.ok) {
        const items = data.knowledge_points || [];
        setKnowledgePoints(items);
        return items;
      }
    } catch (e) {
      console.error("Failed to load knowledge points:", e);
    }
    return [];
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
        setQuestions((data.questions || []).filter((item) => !isProgrammingQuestion(item)));
        setPapers(data.papers || []);
      }
    } catch (e) {
      console.error("Failed to load questions:", e);
    } finally {
      setLoading(false);
    }
  };

  // ── Body / html / container scroll lock when any modal/drawer is open ──
  const taskContextActive = Boolean(practiceContext?.fromTask && practiceContext?.taskId);
  const taskKnowledgeLabel = practiceContext?.knowledgePointTitle || practiceContext?.knowledgePointText || "";
  const taskMaterialLabel = practiceContext?.relatedMaterialTitle || "";

  const returnToTaskCenter = () => {
    onClearPracticeContext();
    setPage("taskCenter");
  };

  // ── Task AI Question Generation ──

  const handleTaskGenerateQuestions = async () => {
    if (!user?.username) return;
    setTaskGenLoading(true);
    setTaskGenError("");
    setTaskGenQuestions([]);
    try {
      const body = {
        username: user.username,
        course_id: practiceContext?.courseId || courseFilter || subject || "",
        knowledge_point_id: practiceContext?.knowledgePointId || null,
        knowledge_point_title: practiceContext?.knowledgePointTitle || practiceContext?.knowledgePointText || "",
        task_id: practiceContext?.taskId || null,
        task_title: practiceContext?.taskTitle || "",
        count: taskGenCount,
      };
      const res = await fetch(`${API_BASE}/practice/generate-task-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "AI 生成失败，请稍后重试");
      }
      setTaskGenQuestions(data.questions || []);
    } catch (e) {
      setTaskGenError(e.message || "AI 题目生成失败，请稍后重试。");
    } finally {
      setTaskGenLoading(false);
    }
  };

  // ── Mixed practice: AI supplement ──
  const handleMixedSupplement = async (missingCount) => {
    if (!user?.username || missingCount <= 0) return;
    setTaskGenLoading(true);
    setTaskGenError("");
    setMixedSupplementQuestions([]);
    setTaskGenQuestions([]);
    try {
      const body = {
        username: user.username,
        course_id: practiceContext?.courseId || courseFilter || subject || "",
        knowledge_point_id: practiceContext?.knowledgePointId || null,
        knowledge_point_title: practiceContext?.knowledgePointTitle || practiceContext?.knowledgePointText || "",
        task_id: practiceContext?.taskId || null,
        task_title: practiceContext?.taskTitle || "",
        count: missingCount,
      };
      const res = await fetch(`${API_BASE}/practice/generate-task-preview`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "AI 生成失败，请稍后重试");
      setMixedSupplementQuestions(data.questions || []);
      setTaskGenQuestions(data.questions || []);
    } catch (e) {
      setTaskGenError(e.message || "AI 题目生成失败，请稍后重试。");
    } finally {
      setTaskGenLoading(false);
    }
  };

  // Dismiss mixed suggestion
  const dismissMixedSuggestion = () => {
    setMixedSuggestionDismissed(true);
    setMixedSupplementQuestions([]);
    setTaskGenQuestions([]);
    setTaskGenError("");
  };

  // Reset when task context changes
  useEffect(() => {
    setMixedSuggestionDismissed(false);
    setMixedSupplementQuestions([]);
  }, [practiceContext?.taskId]);

  // ── AI Temp Practice ──

  const startAiTempPractice = () => {
    if (taskGenQuestions.length === 0) return;
    const courseId = practiceContext?.courseId || courseFilter || subject || "";
    const kpId = practiceContext?.knowledgePointId || null;
    const kpTitle = practiceContext?.knowledgePointTitle || practiceContext?.knowledgePointText || "";
    const questions = taskGenQuestions.map((q, idx) => ({
      id: `ai-temp-${idx + 1}`,
      title: q.stem,
      content: q.stem,
      type: q.type,
      options: q.options && q.options.length > 0
        ? q.options.map((opt) => `${opt.label}. ${opt.text}`).join("\n")
        : "",
      answer: q.answer,
      explanation: q.analysis,
      knowledge_point_id: kpId,
      knowledge_point_title: kpTitle,
      course_id: courseId,
      source: "ai_task_preview",
      difficulty: "medium",
    }));
    setAiTempQuestions(questions);
    setAiTempAnswers({});
    setAiTempCurrentIndex(0);
    setAiTempResult(null);
    setAiTempSubmitting(false);
    aiTempStartRef.current = Date.now();
    setAiTempMode(true);
  };

  const exitAiTempPractice = () => {
    setAiTempMode(false);
    setAiTempQuestions([]);
    setAiTempAnswers({});
    setAiTempResult(null);
    setAiTempSubmitting(false);
  };

  const updateAiTempAnswer = (qid, value) => {
    setAiTempAnswers((prev) => ({ ...prev, [qid]: value }));
  };

  const toggleAiTempMultiAnswer = (qid, label) => {
    setAiTempAnswers((prev) => {
      const current = parseAnswerList(prev[qid] || "");
      const next = current.includes(label)
        ? current.filter((l) => l !== label)
        : [...current, label];
      return { ...prev, [qid]: next.sort().join(",") };
    });
  };

  const normalizeJudgeAnswer = (ans) => {
    const s = String(ans || "").trim();
    if (/^(正确|对|true|yes|是|✔|✓|T|Y)$/i.test(s)) return "正确";
    if (/^(错误|错|false|no|否|✘|✗|F|N)$/i.test(s)) return "错误";
    return s;
  };

  const gradeAiTempQuestion = (question, userAnswer) => {
    if (!question || !userAnswer) return { is_correct: false, user_answer: userAnswer || "", correct_answer: question.answer || "" };
    const qtype = question.type;
    const correctAns = String(question.answer || "").trim();
    const userAns = String(userAnswer || "").trim();

    if (qtype === "short_answer") {
      return { is_correct: null, user_answer: userAns, correct_answer: correctAns, note: "简答题不自动判分" };
    }

    if (qtype === "judge" || qtype === "true_false") {
      const normUser = normalizeJudgeAnswer(userAns);
      const normCorrect = normalizeJudgeAnswer(correctAns);
      return { is_correct: normUser === normCorrect, user_answer: userAns, correct_answer: correctAns };
    }

    if (qtype === "multiple_choice" || qtype === "select") {
      const userSet = new Set(parseAnswerList(userAns).filter(Boolean));
      const correctSet = new Set(parseAnswerList(correctAns).filter(Boolean));
      const isCorrect = userSet.size === correctSet.size && [...userSet].every((l) => correctSet.has(l));
      return { is_correct: isCorrect, user_answer: userAns, correct_answer: correctAns };
    }

    // single_choice or default
    const normUser = normalizePracticeAnswer(userAns).toUpperCase();
    const normCorrect = normalizePracticeAnswer(correctAns).toUpperCase();
    return { is_correct: normUser === normCorrect, user_answer: userAns, correct_answer: correctAns };
  };

  const submitAiTempPractice = async () => {
    if (aiTempQuestions.length === 0 || !user?.username) return;

    // Grade all questions
    const details = aiTempQuestions.map((q) => {
      const userAns = aiTempAnswers[q.id] ?? "";
      const result = gradeAiTempQuestion(q, userAns);
      return {
        question: q,
        question_id: q.id,
        is_correct: result.is_correct,
        user_answer: result.user_answer,
        correct_answer: result.correct_answer,
        knowledge_point_id: q.knowledge_point_id || null,
        note: result.note || "",
      };
    });

    const autoGraded = details.filter((d) => d.is_correct !== null);
    const correctCount = autoGraded.filter((d) => d.is_correct).length;
    const totalAuto = autoGraded.length;
    const totalAll = details.length;
    const shortAnswerCount = totalAll - totalAuto;
    const accuracy = totalAuto > 0 ? Math.round(correctCount / totalAuto * 100) : 0;
    const durationSeconds = Math.round((Date.now() - aiTempStartRef.current) / 1000);

    // Build submit payload (only auto-graded questions for correctness tracking)
    const questionResults = details
      .filter((d) => d.is_correct !== null) // skip short_answer for submit-result
      .map((d) => ({
        question_id: d.question_id,
        is_correct: d.is_correct,
        user_answer: d.user_answer,
        correct_answer: d.correct_answer,
        knowledge_point_id: d.knowledge_point_id || null,
      }));

    setAiTempSubmitting(true);
    let recordResult = null;
    try {
      const body = {
        username: user.username,
        course_id: practiceContext?.courseId || courseFilter || subject || "",
        knowledge_point_id: practiceContext?.knowledgePointId || null,
        task_id: practiceContext?.taskId || null,
        duration_seconds: durationSeconds,
        source: "task_ai_temp_practice",
        total_questions: totalAll,
        short_answer_count: shortAnswerCount,
        question_results: questionResults.length > 0 ? questionResults : details.map((d) => ({
          question_id: d.question_id,
          is_correct: false,
          user_answer: d.user_answer,
          correct_answer: d.correct_answer,
          knowledge_point_id: d.knowledge_point_id || null,
        })),
      };
      const res = await fetch(`${API_BASE}/practice/submit-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        recordResult = { error: data.detail || "同步学习记录失败" };
      } else {
        recordResult = {
          success: true,
          record_id: data.record_id,
          summary: data.summary,
          backend_total_questions: data.total_questions,
          backend_graded_questions: data.graded_questions,
          backend_accuracy: data.accuracy,
          backend_short_answer_count: data.short_answer_count,
          backend_kp_updates: data.kp_updates,
        };
      }
    } catch (e) {
      recordResult = { error: e.message || "同步学习记录失败" };
    } finally {
      setAiTempSubmitting(false);
    }

    // Use backend values when available, fall back to local computation
    const finalTotal = recordResult?.backend_total_questions ?? totalAll;
    const finalGraded = recordResult?.backend_graded_questions ?? totalAuto;
    const finalAccuracy = recordResult?.backend_accuracy ?? accuracy;
    const finalShort = recordResult?.backend_short_answer_count ?? shortAnswerCount;
    const finalKpUpdates = recordResult?.backend_kp_updates ?? totalAuto;

    setAiTempResult({
      total: finalTotal,
      auto_graded: finalGraded,
      correct: correctCount,
      incorrect: finalGraded - correctCount,
      short_answer: finalShort,
      accuracy: finalAccuracy,
      duration_seconds: durationSeconds,
      duration_minutes: Math.max(1, Math.round(durationSeconds / 60)),
      details,
      record: recordResult,
      kp_updates: finalKpUpdates,
    });
  };

  const markTaskComplete = async () => {
    if (!taskContextActive || !practiceContext?.taskId || !user?.username) return;
    setTaskCompleteSyncing(true);
    setTaskCompleteMessage("");
    try {
      const res = await fetch(`${API_BASE}/learning/tasks/${practiceContext.taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, status: "done" }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "标记任务完成失败");
      }
      setTaskCompleteMessage("已同步完成学习任务。");
    } catch (error) {
      console.error("Failed to mark task complete:", error);
      setTaskCompleteMessage("同步学习任务失败，请稍后重试。");
    } finally {
      setTaskCompleteSyncing(false);
    }
  };

  useEffect(() => {
    const shouldLock =
      showCreateModal ||
      showGenerateModal ||
      showImportModal ||
      !!editingQuestion ||
      !!paperDetail ||
      !!detailQuestion;

    if (!shouldLock) return;

    const scrollY = window.scrollY;
    const originalBodyOverflow = document.body.style.overflow;
    const originalHtmlOverflow = document.documentElement.style.overflow;
    const originalBodyPosition = document.body.style.position;
    const originalBodyTop = document.body.style.top;
    const originalBodyWidth = document.body.style.width;
    const originalPaddingRight = document.body.style.paddingRight;

    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;

    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = "100%";

    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }

    const possibleScrollContainers = [
      document.querySelector(".workspace-main"),
      document.querySelector(".datacenter-shell"),
      document.querySelector(".app-main"),
      document.querySelector(".main-content"),
      document.querySelector(".page-content"),
      document.querySelector(".practice-workbench"),
    ].filter(Boolean);

    const previousContainerStyles = possibleScrollContainers.map((el) => ({
      el,
      overflow: el.style.overflow,
      overflowY: el.style.overflowY,
    }));

    possibleScrollContainers.forEach((el) => {
      el.style.overflow = "hidden";
      el.style.overflowY = "hidden";
    });

    return () => {
      document.body.style.overflow = originalBodyOverflow;
      document.documentElement.style.overflow = originalHtmlOverflow;
      document.body.style.position = originalBodyPosition;
      document.body.style.top = originalBodyTop;
      document.body.style.width = originalBodyWidth;
      document.body.style.paddingRight = originalPaddingRight;

      previousContainerStyles.forEach(({ el, overflow, overflowY }) => {
        el.style.overflow = overflow;
        el.style.overflowY = overflowY;
      });

      window.scrollTo(0, scrollY);
    };
  }, [showCreateModal, showGenerateModal, showImportModal, editingQuestion, paperDetail, detailQuestion]);

  useEffect(() => {
    if (!practiceContext?.fromTask) return;
    const nextCourse = practiceContext.courseId || "";
    const nextKp = practiceContext.knowledgePointId ? String(practiceContext.knowledgePointId) : "";
    setCourseFilter(nextCourse);
    setKpFilter(nextKp);
    setTypeFilter("");
    setTaskCompleteMessage("");
  }, [practiceContext?.taskId]);

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

  useEffect(() => {
    const savedJobId = window.localStorage.getItem(IMPORT_JOB_STORAGE_KEY);
    if (!savedJobId) return;
    setImportJobId(savedJobId);
    setImportJobStatus("processing");
    setImportJobProgress("正在恢复上次试卷识别任务...");
    setShowImportModal(true);
  }, []);

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
        setSubmittedAttempt(null);
        setShowAnswer(false);
        await loadAttempts(q.id);
      }
    } catch (e) {
      console.error("Failed to load question detail:", e);
    }
  };

  const startPracticeFromPaper = (question) => {
    setPaperDetail(null);
    openDetail(question);
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

  const toggleBatchQuestion = (question) => {
    if (!isBatchObjectiveQuestion(question)) {
      setBatchNotice("简答题暂不支持自动评分组合练习，请选择客观题。");
      return;
    }
    if (!hasValidObjectiveAnswerStructure(question)) {
      setBatchNotice("该题答案结构异常，暂不能加入组合练习。");
      return;
    }
    setBatchNotice("");
    setSelectedQuestionIds((prev) => {
      const next = new Set(prev);
      if (next.has(question.id)) {
        next.delete(question.id);
      } else if (next.size >= 50) {
        setBatchNotice("V1 最多一次选择 50 道题进行组合练习。");
      } else {
        next.add(question.id);
      }
      return next;
    });
  };

  const selectAllCurrentObjectiveQuestions = () => {
    const objectiveQuestions = questions.filter((q) => isBatchObjectiveQuestion(q) && hasValidObjectiveAnswerStructure(q));
    const objectiveIds = objectiveQuestions.slice(0, 50).map((q) => q.id);
    if (objectiveIds.length === 0) {
      setBatchNotice("当前筛选下没有可自动评分的客观题。");
      return;
    }
    setSelectedQuestionIds(new Set(objectiveIds));
    setBatchNotice(objectiveIds.length < objectiveQuestions.length
      ? "已选择前 50 道客观题。"
      : "");
  };

  const clearBatchSelection = () => {
    setSelectedQuestionIds(new Set());
    setBatchNotice("");
  };

  const fetchQuestionDetail = async (questionId) => {
    const res = await fetch(
      `${API_BASE}/practice/questions/${questionId}?username=${encodeURIComponent(user.username)}`
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "加载题目失败");
    return data.question;
  };

  const startBatchPractice = async () => {
    if (selectedQuestionIds.size < 2) {
      setBatchNotice("请至少选择 2 道题进行组合练习。");
      return;
    }
    setBatchLoading(true);
    setBatchNotice("");
    try {
      const selectedIds = Array.from(selectedQuestionIds).slice(0, 50);
      const details = await Promise.all(selectedIds.map(fetchQuestionDetail));
      const objectiveDetails = details.filter((q) => isBatchObjectiveQuestion(q) && hasValidObjectiveAnswerStructure(q));
      if (objectiveDetails.length < 2) {
        setBatchNotice("请至少选择 2 道客观题进行组合练习。");
        return;
      }
      setBatchQuestions(objectiveDetails);
      setBatchCurrentIndex(0);
      setBatchAnswers({});
      setBatchResult(null);
      setBatchPracticeMode(true);
    } catch (e) {
      console.error("Failed to start batch practice:", e);
      setBatchNotice(e.message || "组合练习启动失败，请稍后重试。");
    } finally {
      setBatchLoading(false);
    }
  };

  const updateBatchAnswer = (questionId, value) => {
    setBatchAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const toggleBatchMultiAnswer = (questionId, label) => {
    setBatchAnswers((prev) => {
      const current = Array.isArray(prev[questionId]) ? prev[questionId] : parseAnswerList(prev[questionId]);
      const next = current.includes(label)
        ? current.filter((item) => item !== label)
        : [...current, label];
      return { ...prev, [questionId]: next };
    });
  };

  const submitBatchPractice = async () => {
    if (batchQuestions.length === 0) return;
    const perQuestion = 100 / batchQuestions.length;
    const details = batchQuestions.map((question) => {
      const rawAnswer = batchAnswers[question.id] ?? "";
      const userAnswerValue = Array.isArray(rawAnswer) ? rawAnswer.sort().join(",") : String(rawAnswer || "").trim();
      const isCorrect = gradeObjectiveQuestion(question, userAnswerValue);
      return {
        question,
        user_answer: userAnswerValue,
        correct_answer: question.answer || "",
        is_correct: isCorrect,
        score: Number((isCorrect ? perQuestion : 0).toFixed(2)),
      };
    });
    const correctCount = details.filter((item) => item.is_correct).length;
    const score = Number(details.reduce((sum, item) => sum + item.score, 0).toFixed(2));
    setBatchResult({
      score,
      correct_count: correctCount,
      incorrect_count: details.length - correctCount,
      accuracy: Number(((correctCount / details.length) * 100).toFixed(1)),
      per_question_score: Number(perQuestion.toFixed(2)),
      details,
    });

    try {
      await Promise.all(details.map((item) => fetch(
        `${API_BASE}/practice/questions/${item.question.id}/attempts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            question_id: item.question.id,
            user_answer: item.user_answer,
          }),
        }
      )));
      await loadQuestions();
      // Submit aggregate practice result for learning records
      try {
        const questionResults = details.map((d) => ({
          question_id: d.question.id,
          is_correct: d.is_correct,
          user_answer: d.user_answer,
          correct_answer: d.correct_answer,
          knowledge_point_id: d.question.knowledge_point_id || null,
        }));
        const subRes = await fetch(`${API_BASE}/practice/submit-result`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            course_id: practiceContext?.courseId || practiceCourse || subject || "",
            knowledge_point_id: practiceContext?.knowledgePointId || null,
            task_id: practiceContext?.taskId || null,
            question_results: questionResults,
            duration_seconds: Math.round((Date.now() - (practiceStartRef.current || Date.now())) / 1000),
            source: practiceContext?.taskId ? "task_practice" : "normal_practice",
          }),
        });
        const subData = await subRes.json();
        if (subData.success) {
          setBatchResult((prev) => prev ? { ...prev, synced: true, syncSummary: subData.summary } : prev);
        }
      } catch (e) { console.error("Failed to submit practice result:", e); }
    } catch (e) {
      console.error("Failed to save batch attempts:", e);
    }
  };

  const exitBatchPractice = () => {
    setBatchPracticeMode(false);
    setBatchQuestions([]);
    setBatchCurrentIndex(0);
    setBatchAnswers({});
    setBatchResult(null);
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
        setSubmittedAttempt(data.attempt || null);
        if (isAiGeneratedQuestion(detailQuestion)) {
          setShowAnswer(true);
          setFeedback("");
        }
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
    if (isAiGeneratedQuestion(detailQuestion)) return;
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
    setGenError("");
    setGenWarnings([]);
    try {
      const normalizedCount = normalizeGenerateCount(genCount);
      setGenCount(normalizedCount);
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
        count: normalizedCount,
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
        setGenWarnings(Array.isArray(data.warnings) ? data.warnings : []);
        setShowGenerateModal(false);
        setGenError("");
        await loadQuestions();
      } else {
        // 后端返回错误时，优先展示 detail
        setGenError(data.detail || "生成失败，请稍后重试");
      }
    } catch (e) {
      console.error("Failed to generate questions:", e);
      setGenError("网络异常，未能连接到题目生成服务");
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
        setPaperQuestions((data.questions || []).filter((item) => !isProgrammingQuestion(item)));
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
    if (isAiGeneratedQuestion(question)) return;
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

  // ── Option editing helpers ──
  const updateEditOption = (index, patch) => {
    setEditOptionItems((items) =>
      items.map((item, i) => (i === index ? { ...item, ...patch } : item))
    );
  };

  const addEditOption = () => {
    setEditOptionItems((items) => {
      const usedLabels = new Set((items || []).map((o) => String(o.label || "").toUpperCase()));
      const candidates = ["A", "B", "C", "D", "E", "F", "G", "H"];
      const nextLabel = candidates.find((label) => !usedLabels.has(label)) || String((items || []).length + 1);
      return [...(items || []), { label: nextLabel, content: "" }];
    });
  };

  const removeEditOption = (index) => {
    setEditOptionItems((items) => (items || []).filter((_, i) => i !== index));
  };

  const buildEditFormFromQuestion = (question) => ({
    title: question.title || "",
    type: question.type || "short_answer",
    difficulty: question.difficulty || "medium",
    course_id: normalizeSubject(question.course_id || paperDetail?.course_id || courseFilter || subject || "", ""),
    content: question.content || "",
    answer: question.answer || "",
    explanation: question.explanation || "",
    raw_text: question.raw_text || "",
  });

  const openEditQuestion = async (question) => {
    if (!question) return;
    const form = buildEditFormFromQuestion(question);
    setEditingQuestion(question);
    setEditQuestionForm(form);
    setEditOptionItems(normalizeEditableOptions(question));
    setEditError("");

    let points = knowledgePoints;
    if (form.course_id) {
      points = await loadKnowledgePoints(form.course_id);
    }
    const kpId = question.knowledge_point_id ? String(question.knowledge_point_id) : "";
    const selectedKp = points.find((kp) => String(kp.id) === kpId);
    if (selectedKp?.parent_id) {
      setEditModuleId(String(selectedKp.parent_id));
      setEditKpId(kpId);
    } else {
      setEditModuleId(kpId);
      setEditKpId("");
    }
  };

  const closeEditQuestion = () => {
    setEditingQuestion(null);
    setEditQuestionForm(null);
    setEditError("");
    setEditModuleId("");
    setEditKpId("");
    setEditOptionItems(parseOptionItems(""));
  };

  const updateQuestionInState = (updatedQuestion) => {
    if (!updatedQuestion?.id) return;
    setQuestions((items) => items.map((item) => (item.id === updatedQuestion.id ? { ...item, ...updatedQuestion } : item)));
    setPaperQuestions((items) => items.map((item) => (item.id === updatedQuestion.id ? { ...item, ...updatedQuestion } : item)));
    if (detailQuestion?.id === updatedQuestion.id) {
      setDetailQuestion((current) => ({ ...current, ...updatedQuestion }));
    }
  };

  const saveEditedQuestion = async () => {
    if (!editingQuestion?.id || !editQuestionForm || !user?.username) return;
    if (!editQuestionForm.title.trim() || !editQuestionForm.content.trim()) {
      setEditError("题目标题和题干不能为空");
      return;
    }
    setEditSaving(true);
    setEditError("");
    try {
      const selectedKpId = editKpId || editModuleId;
      const body = {
        username: user.username,
        title: editQuestionForm.title.trim(),
        type: editQuestionForm.type,
        difficulty: editQuestionForm.difficulty,
        course_id: normalizeSubject(editQuestionForm.course_id, ""),
        knowledge_point_id: selectedKpId ? parseInt(selectedKpId, 10) : null,
        content: editQuestionForm.content.trim(),
        options: isChoiceLikeType(editQuestionForm.type) ? editOptionItems.filter((item) => (item.content || "").trim()) : null,
        answer: editQuestionForm.answer.trim() || null,
        explanation: editQuestionForm.explanation.trim() || null,
        raw_text: editQuestionForm.raw_text.trim() || null,
      };
      const res = await fetch(`${API_BASE}/practice/questions/${editingQuestion.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "保存失败");
      updateQuestionInState(data.question);
      closeEditQuestion();
    } catch (e) {
      setEditError(e.message || "保存失败，请稍后重试");
    } finally {
      setEditSaving(false);
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
  const editModuleChildren = editModuleId ? getModuleChildren(editModuleId) : [];
  const goCodeStudio = () => setPage("codeStudio");
  const openGenerateModal = () => {
    setGenCourse(courseFilter || subject || "");
    setGenCourseName("");
    setGenModuleId("");
    setGenKpId("");
    setGenType(PROGRAMMING_QUESTION_TYPES.has(typeFilter) ? "choice" : (typeFilter || "choice"));
    setGenDifficulty("medium");
    setGenCount(3);
    setGenSourceStyle("mixed");
    setGenRequireReasoning(true);
    setGenAvoidTooSimple(true);
    setGenError("");
    setGenWarnings([]);
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
    const savedJobId = window.localStorage.getItem(IMPORT_JOB_STORAGE_KEY);
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
    setImportWarnings(null);
    if (savedJobId) {
      setImportJobId(savedJobId);
      setImportJobStatus("processing");
      setImportJobProgress("正在恢复上次试卷识别任务...");
      setImportJob(null);
    } else {
      setImportJobId(null);
      setImportJobStatus(null);
      setImportJobProgress("");
      setImportJob(null);
    }
    setShowImportModal(true);
  };
  const updateImportDraft = (index, patch) => {
    setImportDrafts((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  const renderTaskCompleteCard = () => {
    if (!taskContextActive) return null;
    return (
      <div className="practice-complete-task-card">
        <div>
          <strong>已完成本次练习，是否标记任务为已完成？</strong>
          {taskCompleteMessage && <p>{taskCompleteMessage}</p>}
        </div>
        <button
          type="button"
          className="primary-button compact"
          disabled={taskCompleteSyncing}
          onClick={markTaskComplete}
        >
          {taskCompleteSyncing ? "同步中..." : "标记任务完成"}
        </button>
      </div>
    );
  };

  const parseImportFile = async () => {
    // 新逻辑：创建异步 job 然后轮询
    if (!importFile || !user?.username) return;
    setImportLoading(true);
    setImportError("");
    setImportDrafts([]);
    setImportSelected({});
    setImportExtractMeta(null);
    setImportWarnings(null);
    setImportJob(null);
    setImportJobStatus("pending");
    setImportJobProgress("正在提交识别任务...");

    try {
      const form = new FormData();
      form.append("username", user.username);
      form.append("course_id", normalizeSubject(importCourse, ""));
      if (importModuleId) form.append("module_id", importModuleId);
      const selectedKpId = importKpId || importModuleId;
      if (selectedKpId) form.append("knowledge_point_id", selectedKpId);
      form.append("file", importFile);

      const url = `${API_BASE}/practice/import-paper/jobs`;
      console.debug("[paper-import:create-job]", { url, fileName: importFile?.name, fileSize: importFile?.size });

      const res = await fetch(url, { method: "POST", body: form });
      const rawText = await res.text();
      const contentType = res.headers.get("content-type") || "";

      let data = null;
      if (contentType.includes("application/json")) {
        data = JSON.parse(rawText);
      } else {
        throw new Error("创建识别任务时收到非 JSON 响应，HTTP " + res.status);
      }

      if (!res.ok) {
        throw new Error(data?.detail || "创建任务失败");
      }

      setImportJobId(data.job_id);
      setImportJob({ job_id: data.job_id, status: data.status, progress_message: data.message });
      window.localStorage.setItem(IMPORT_JOB_STORAGE_KEY, String(data.job_id));
      setImportJobStatus("processing");
      setImportJobProgress("正在提取试卷文本...");
      setImportLoading(false);  // 不再 loading，改轮询
    } catch (error) {
      setImportJobStatus("failed");
      setImportError(error.message || "创建识别任务失败");
      setImportLoading(false);
    }
  };

  // ── 轮询 job 状态 ──
  useEffect(() => {
    if (!importJobId || !["pending", "processing"].includes(importJobStatus)) return;

    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const res = await fetch(`${API_BASE}/practice/import-paper/jobs/${importJobId}`);
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || "查询识别任务失败");
        }
        if (cancelled) return;

        setImportJob(data);
        setImportJobStatus(data.status);
        setImportJobProgress(data.progress_message || "");

        if (data.parse_method || data.total_pages > 0) {
          setImportExtractMeta({
            extract_method: data.parse_method || "local",
            qwen_used: data.parse_method === "qwen" || data.parse_method === "mixed",
            total_pages: data.total_pages || 0,
            parsed_pages: data.parsed_pages || 0,
            page_limit_hit: data.page_limit_hit || false,
          });
        }

        if (data.status === "succeeded" && data.result) {
          const r = data.result;
          const drafts = r.drafts || [];
          setImportDrafts(drafts);
          setImportPaperTitle(r.paper_title || data.result?.paper_title || importFile?.name || "导入试卷");
          setImportOriginalFileName(r.original_file_name || importFile?.name || "");
          setImportSelected(Object.fromEntries(drafts.map((_, idx) => [idx, true])));
          setImportExtractMeta(r.extract_meta || null);
          setImportWarnings(r.warnings || null);
          window.localStorage.removeItem(IMPORT_JOB_STORAGE_KEY);
        }

        if (data.status === "failed") {
          setImportError(data.error_message || "试卷识别失败");
          window.localStorage.removeItem(IMPORT_JOB_STORAGE_KEY);
        }
      } catch (e) {
        if (!cancelled) {
          console.error("[paper-import:poll-error]", e);
          setImportError(e.message || "查询识别任务失败，请稍后重试");
        }
      }
    };

    // 立即轮询一次，然后每 2 秒一次
    poll();
    const timer = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [importJobId, importJobStatus, importFile]);
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

  const importJobStatusLabel = {
    pending: "排队中",
    processing: "识别中",
    succeeded: "已完成",
    failed: "失败",
  }[importJobStatus] || "准备中";
  const importJobElapsedSeconds = Number.isFinite(Number(importJob?.elapsed_seconds))
    ? Number(importJob.elapsed_seconds)
    : importJob?.created_at
    ? Math.max(0, Math.floor((Date.now() - new Date(importJob.created_at).getTime()) / 1000))
    : null;
  const importJobElapsedText = importJobElapsedSeconds === null
    ? ""
    : `${Math.floor(importJobElapsedSeconds / 60)}分${importJobElapsedSeconds % 60}秒`;
  const importJobLongRunning = ["pending", "processing"].includes(importJobStatus)
    && Number(importJobElapsedSeconds || 0) >= IMPORT_JOB_LONG_RUNNING_SECONDS;

  return (
    <section className="chat-panel chat-panel--wide practice-panel">
      {batchPracticeMode && (
        <div className="batch-practice-panel">
          <div className="batch-practice-header">
            <div>
              <span className="subject-pill small practice-source-pill">组合练习</span>
              <h3>客观题组合练习</h3>
            </div>
            <button className="ghost-button compact" type="button" onClick={exitBatchPractice}>
              退出组合练习
            </button>
          </div>

          {!batchResult && batchQuestions.length > 0 && (() => {
            const currentQuestion = batchQuestions[batchCurrentIndex];
            const currentOptions = parseOptionItems(currentQuestion.options || "");
            const currentAnswer = batchAnswers[currentQuestion.id] ?? "";
            const isMultiple = currentQuestion.type === "multiple_choice" || currentQuestion.type === "select";
            const isTextInput = currentQuestion.type === "fill_blank";
            const isTrueFalse = currentQuestion.type === "true_false" || currentQuestion.type === "judge";

            return (
              <>
                <div className="batch-question-nav">
                  {batchQuestions.map((question, index) => (
                    <button
                      key={question.id}
                      type="button"
                      className={`batch-question-nav-item${index === batchCurrentIndex ? " active" : ""}${batchAnswers[question.id] ? " answered" : ""}`}
                      onClick={() => setBatchCurrentIndex(index)}
                    >
                      {index + 1}
                    </button>
                  ))}
                </div>

                <div className="batch-question-card">
                  <div className="batch-question-head">
                    <span>第 {batchCurrentIndex + 1} / {batchQuestions.length} 题</span>
                    <span className={`q-type-badge ${getTypeClass(currentQuestion.type)}`}>
                      {TYPE_LABELS[currentQuestion.type] || currentQuestion.type}
                    </span>
                  </div>
                  <h4>{currentQuestion.title}</h4>
                  <div className="question-content-text">{currentQuestion.content}</div>

                  {isTextInput ? (
                    <input
                      className="field batch-answer-input"
                      value={String(currentAnswer || "")}
                      onChange={(e) => updateBatchAnswer(currentQuestion.id, e.target.value)}
                      placeholder="请输入答案"
                    />
                  ) : (
                    <div className="question-options batch-options">
                      {(isTrueFalse && currentOptions.length === 0
                        ? [{ label: "A", content: "正确" }, { label: "B", content: "错误" }]
                        : currentOptions
                      ).map((option) => {
                        const label = option.label;
                        const checked = isMultiple
                          ? parseAnswerList(currentAnswer).includes(label)
                          : normalizePracticeAnswer(currentAnswer) === label;
                        return (
                          <label key={label} className="question-option-label">
                            <input
                              type={isMultiple ? "checkbox" : "radio"}
                              name={`batch-answer-${currentQuestion.id}`}
                              value={label}
                              checked={checked}
                              onChange={() => {
                                if (isMultiple) {
                                  toggleBatchMultiAnswer(currentQuestion.id, label);
                                } else {
                                  updateBatchAnswer(currentQuestion.id, label);
                                }
                              }}
                            />
                            <span>{label}. {option.content}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="batch-practice-actions">
                  <button
                    className="ghost-button compact"
                    type="button"
                    disabled={batchCurrentIndex === 0}
                    onClick={() => setBatchCurrentIndex((index) => Math.max(index - 1, 0))}
                  >
                    上一题
                  </button>
                  {batchCurrentIndex < batchQuestions.length - 1 ? (
                    <button
                      className="primary-button compact"
                      type="button"
                      onClick={() => setBatchCurrentIndex((index) => Math.min(index + 1, batchQuestions.length - 1))}
                    >
                      下一题
                    </button>
                  ) : (
                    <button className="primary-button compact" type="button" onClick={submitBatchPractice}>
                      提交组合练习
                    </button>
                  )}
                </div>
              </>
            );
          })()}

          {batchResult && (
            <div className="batch-result">
              <div className="batch-score-card">
                <strong>{batchResult.score} / 100</strong>
                <span>总分</span>
                <span>正确 {batchResult.correct_count} 题，错误 {batchResult.incorrect_count} 题，正确率 {batchResult.accuracy}%</span>
              </div>
              <div className="batch-result-list">
                {batchResult.details.map((item, index) => (
                  <div key={item.question.id} className={`batch-result-item ${item.is_correct ? "correct" : "incorrect"}`}>
                    <div className="batch-result-item-head">
                      <strong>{index + 1}. {item.question.title}</strong>
                      <span>{item.is_correct ? "正确" : "错误"} · {item.score} 分</span>
                    </div>
                    <div className="batch-result-row"><span>你的答案：</span><strong>{item.user_answer || "未作答"}</strong></div>
                    <div className="batch-result-row"><span>参考答案：</span><strong>{item.correct_answer || "未提供"}</strong></div>
                    {getQuestionAnalysis(item.question) && (
                      <div className="batch-result-analysis">
                        <strong>解析：</strong>
                        <QuestionAnalysisBlock analysis={getQuestionAnalysis(item.question)} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {renderTaskCompleteCard()}
            </div>
          )}
        </div>
      )}

      {aiTempMode && (
        <div className="batch-practice-panel">
          <div className="batch-practice-header">
            <div>
              <span className="subject-pill small practice-source-pill" style={{ background: "#fef3c7", color: "#92400e" }}>AI 生成临时练习</span>
              <h3>AI 生成临时练习</h3>
              <p style={{ fontSize: 13, color: "#92400e", margin: "4px 0 0" }}>
                这些题尚未加入正式题库，完成后结果会计入学习记录和知识点掌握度。
              </p>
            </div>
            <button className="ghost-button compact" type="button" onClick={exitAiTempPractice}>
              退出练习
            </button>
          </div>

          {!aiTempResult && aiTempQuestions.length > 0 && (() => {
            const q = aiTempQuestions[aiTempCurrentIndex];
            const currentAnswer = aiTempAnswers[q.id] ?? "";
            const isMultiple = q.type === "multiple_choice" || q.type === "select";
            const isJudge = q.type === "judge" || q.type === "true_false";
            const isShort = q.type === "short_answer";
            const options = parseOptionItems(q.options || "");
            const displayOptions = (isJudge && options.length === 0)
              ? [{ label: "A", content: "正确" }, { label: "B", content: "错误" }]
              : options;

            return (
              <>
                <div className="batch-question-nav">
                  {aiTempQuestions.map((question, idx) => (
                    <button
                      key={question.id}
                      type="button"
                      className={`batch-question-nav-item${idx === aiTempCurrentIndex ? " active" : ""}${aiTempAnswers[question.id] ? " answered" : ""}`}
                      onClick={() => setAiTempCurrentIndex(idx)}
                    >
                      {idx + 1}
                    </button>
                  ))}
                </div>

                <div className="batch-question-card">
                  <div className="batch-question-head">
                    <span>第 {aiTempCurrentIndex + 1} / {aiTempQuestions.length} 题</span>
                    <span className={`q-type-badge ${getTypeClass(q.type)}`}>
                      {TYPE_LABELS[q.type] || q.type}
                    </span>
                  </div>
                  <h4 style={{ fontSize: 16, fontWeight: 700, color: "#1e293b", margin: "0 0 10px", lineHeight: 1.6 }}>
                    {q.title}
                  </h4>

                  {isShort ? (
                    <div>
                      <textarea
                        className="field batch-answer-input"
                        style={{ minHeight: 100, width: "100%" }}
                        value={String(currentAnswer || "")}
                        onChange={(e) => updateAiTempAnswer(q.id, e.target.value)}
                        placeholder="请输入你的答案..."
                      />
                      <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 6 }}>
                        💡 简答题暂不自动判分，完成后可查看参考答案和解析。
                      </p>
                    </div>
                  ) : (
                    <div className="question-options batch-options">
                      {displayOptions.map((opt) => {
                        const label = opt.label;
                        const checked = isMultiple
                          ? parseAnswerList(currentAnswer).includes(label)
                          : normalizePracticeAnswer(currentAnswer) === label;
                        return (
                          <label key={label} className="question-option-label">
                            <input
                              type={isMultiple ? "checkbox" : "radio"}
                              name={`ai-temp-answer-${q.id}`}
                              value={label}
                              checked={checked}
                              onChange={() => {
                                if (isMultiple) {
                                  toggleAiTempMultiAnswer(q.id, label);
                                } else {
                                  updateAiTempAnswer(q.id, label);
                                }
                              }}
                            />
                            <span>{label}. {opt.content}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="batch-practice-actions">
                  <button
                    className="ghost-button compact"
                    type="button"
                    disabled={aiTempCurrentIndex === 0}
                    onClick={() => setAiTempCurrentIndex((i) => Math.max(i - 1, 0))}
                  >
                    上一题
                  </button>
                  {aiTempCurrentIndex < aiTempQuestions.length - 1 ? (
                    <button
                      className="primary-button compact"
                      type="button"
                      onClick={() => setAiTempCurrentIndex((i) => Math.min(i + 1, aiTempQuestions.length - 1))}
                    >
                      下一题
                    </button>
                  ) : (
                    <button
                      className="primary-button compact"
                      type="button"
                      onClick={submitAiTempPractice}
                      disabled={aiTempSubmitting}
                    >
                      {aiTempSubmitting ? "提交中..." : "提交练习"}
                    </button>
                  )}
                </div>
              </>
            );
          })()}

          {aiTempResult && (
            <div className="batch-result">
              <div className="batch-score-card" style={{ textAlign: "center" }}>
                <strong style={{ fontSize: 28, color: "#059669" }}>
                  {aiTempResult.auto_graded > 0 ? `${aiTempResult.accuracy}%` : "--"}
                </strong>
                <span style={{ fontSize: 14, color: "#475569" }}>
                  {aiTempResult.auto_graded > 0
                    ? `正确 ${aiTempResult.correct} / ${aiTempResult.auto_graded}`
                    : "无自动判分题"}
                </span>
                <div style={{ marginTop: 8, fontSize: 13, color: "#64748b", display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
                  <span>总题数：{aiTempResult.total}</span>
                  <span>自动判分：{aiTempResult.auto_graded} 题</span>
                  {aiTempResult.short_answer > 0 && <span>简答题：{aiTempResult.short_answer} 题</span>}
                  <span>用时：{aiTempResult.duration_minutes} 分钟</span>
                </div>
                {aiTempResult.record && (
                  <div style={{ marginTop: 8, fontSize: 13 }}>
                    {aiTempResult.record.success ? (
                      <span style={{ color: "#059669" }}>✅ 学习记录已同步</span>
                    ) : (
                      <span style={{ color: "#b91c1c" }}>⚠️ {aiTempResult.record.error}</span>
                    )}
                    <span style={{ marginLeft: 12, color: (aiTempResult.kp_updates ?? aiTempResult.auto_graded) > 0 ? "#059669" : "#94a3b8" }}>
                      {(aiTempResult.kp_updates ?? aiTempResult.auto_graded) > 0
                        ? `知识点掌握度：已更新（${aiTempResult.kp_updates ?? aiTempResult.auto_graded} 个知识点）`
                        : "知识点掌握度：无自动判分题，未更新"}
                    </span>
                  </div>
                )}
              </div>

              <p style={{ fontSize: 13, color: "#b45309", textAlign: "center", margin: "12px 0 0" }}>
                ⚠️ 本次题目未加入正式题库。
              </p>

              <div className="batch-result-list" style={{ marginTop: 16 }}>
                {aiTempResult.details.map((item, idx) => {
                  const isAutoGraded = item.is_correct !== null;
                  const resultClass = isAutoGraded ? (item.is_correct ? "correct" : "incorrect") : "short-answer";
                  return (
                    <div key={item.question.id} className={`batch-result-item ${resultClass}`}>
                      <div className="batch-result-item-head">
                        <strong>{idx + 1}. {item.question.title}</strong>
                        <span>
                          {isAutoGraded ? (item.is_correct ? "✅ 正确" : "❌ 错误") : "📝 简答题（未自动判分）"}
                        </span>
                      </div>
                      <div className="batch-result-row">
                        <span>你的答案：</span>
                        <strong>{item.user_answer || "未作答"}</strong>
                      </div>
                      <div className="batch-result-row">
                        <span>参考答案：</span>
                        <strong>{item.correct_answer || "未提供"}</strong>
                      </div>
                      {item.question.explanation && (
                        <div className="batch-result-analysis">
                          <strong>解析：</strong>
                          <QuestionAnalysisBlock analysis={item.question.explanation} />
                        </div>
                      )}
                      {item.note && (
                        <p style={{ fontSize: 12, color: "#94a3b8", margin: "4px 0 0" }}>{item.note}</p>
                      )}
                    </div>
                  );
                })}
              </div>

              <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 16 }}>
                <button className="ghost-button compact" type="button" onClick={exitAiTempPractice}>
                  返回练习中心
                </button>
                {renderTaskCompleteCard()}
              </div>
            </div>
          )}
        </div>
      )}

      {!aiTempMode && (
      <div className="practice-workbench">
        {taskContextActive && (
          <div className="practice-task-banner">
            <div>
              <span className="practice-task-eyebrow">来自学习任务</span>
              <h3>{practiceContext.taskTitle || "学习任务练习"}</h3>
              <div className="practice-task-meta">
                {practiceContext.courseName && <span>课程：{practiceContext.courseName}</span>}
                {taskKnowledgeLabel && <span>知识点：{taskKnowledgeLabel}</span>}
                {taskMaterialLabel && <span>资料：{taskMaterialLabel}</span>}
                {practiceContext.knowledgePointText && !practiceContext.knowledgePointId && (
                  <span>提示：可按手动知识点筛选或生成题目</span>
                )}
              </div>
            </div>
            <button type="button" className="ghost-button compact" onClick={returnToTaskCenter}>
              返回任务中心
            </button>
          </div>
        )}
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

        {genWarnings.length > 0 && (
          <div className="practice-generate-warning-panel">
            {genWarnings.map((warning, index) => (
              <div key={`${warning}-${index}`} className="practice-generate-warning-item">
                {warning}
              </div>
            ))}
          </div>
        )}

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
              <>
                {/* ── Task AI Generation Card (only when coming from a task) ── */}
                {taskContextActive && (
                  <div className="practice-task-gen-card">
                    <div className="practice-task-gen-header">
                      <span className="practice-task-gen-icon">🤖</span>
                      <div>
                        <h3>当前知识点暂无题目</h3>
                        <p>可让 AI 根据学习任务生成练习题预览，生成后可在下方查看题目和解析，不写入题库。</p>
                      </div>
                    </div>

                    {taskGenQuestions.length === 0 && !taskGenLoading && !taskGenError && (
                      <div className="practice-task-gen-controls">
                        <div className="practice-task-gen-count">
                          <label>生成数量</label>
                          <select value={taskGenCount} onChange={(e) => setTaskGenCount(Number(e.target.value))}>
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                              <option key={n} value={n}>{n} 道</option>
                            ))}
                          </select>
                        </div>
                        <button
                          className="primary-button compact practice-action-button practice-action-button--ai"
                          onClick={handleTaskGenerateQuestions}
                          disabled={taskGenLoading}
                        >
                          ✨ AI 生成练习题
                        </button>
                      </div>
                    )}

                    {taskGenLoading && (
                      <div className="practice-task-gen-loading">
                        <div className="cmp-loading-spinner" />
                        <p>正在生成练习题预览...</p>
                      </div>
                    )}

                    {taskGenError && !taskGenLoading && (
                      <div className="practice-task-gen-error">
                        <p>{taskGenError}</p>
                        <button className="ghost-button compact" onClick={() => { setTaskGenError(""); setTaskGenQuestions([]); }}>
                          重试
                        </button>
                      </div>
                    )}

                    {taskGenQuestions.length > 0 && !taskGenLoading && (
                      <div className="practice-task-gen-result">
                        <div className="practice-task-gen-result-header">
                          <span>✅ 已生成 {taskGenQuestions.length} 道题目预览</span>
                          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                            <span style={{ fontSize: 13, color: "#64748b" }}>已选 {aiSaveSelected.size} 道</span>
                            <button
                              className="primary-button compact"
                              type="button"
                              disabled={aiSaveSelected.size === 0}
                              onClick={openAiSaveModal}
                            >
                              保存选中题到题库
                            </button>
                          </div>
                          <button className="ghost-button compact" onClick={() => { setTaskGenQuestions([]); setTaskGenError(""); }}>
                            重新生成
                          </button>
                        </div>
                        <p className="practice-task-gen-hint">
                          ⚠️ 当前为 AI 生成预览，尚未加入题库。你可以查看题目内容、答案和解析用于复习参考。
                        </p>
                        <div style={{ marginBottom: 16, display: "flex", justifyContent: "center" }}>
                          <button className="primary-button compact" type="button" onClick={startAiTempPractice}>
                            使用这些题开始练习
                          </button>
                        </div>
                        <div className="practice-task-gen-questions">
                          {taskGenQuestions.map((q, idx) => (
                            <div key={idx} className="practice-task-gen-question" style={{ position: "relative" }}>
                              <label className="practice-task-gen-q-check" onClick={(e) => e.stopPropagation()}>
                                <input
                                  type="checkbox"
                                  checked={aiSaveSelected.has(idx)}
                                  onChange={() => toggleAiSaveSelect(idx)}
                                />
                                <span>保存到题库</span>
                              </label>
                              <div className="practice-task-gen-q-header">
                                <span className="practice-task-gen-q-index">第 {idx + 1} 题</span>
                                <span className="practice-task-gen-q-type">
                                  {q.type === "single_choice" ? "单选题" : q.type === "multiple_choice" ? "多选题" : q.type === "judge" ? "判断题" : "简答题"}
                                </span>
                              </div>
                              <div className="practice-task-gen-q-stem">{q.stem}</div>
                              {q.options && q.options.length > 0 && (
                                <div className="practice-task-gen-q-options">
                                  {q.options.map((opt, oidx) => (
                                    <div key={oidx} className={`practice-task-gen-q-option${opt.label === q.answer ? " practice-task-gen-q-option--correct" : ""}`}>
                                      <span className="practice-task-gen-q-opt-label">{opt.label}</span>
                                      <span>{opt.text}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              <div className="practice-task-gen-q-answer">
                                <strong>答案：</strong>{q.answer}
                              </div>
                              <div className="practice-task-gen-q-analysis">
                                <strong>解析：</strong>{q.analysis}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── Standard Empty State ── */}
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
              </>
            ) : (
              <>
                {/* ── Mixed Practice Suggestion Card (case C: 0 < questions < recommended) ── */}
                {taskContextActive && !aiTempMode && questions.length > 0 && questions.length < RECOMMENDED_PRACTICE_COUNT && !mixedSuggestionDismissed && papers.length === 0 && (
                  <div className="practice-mixed-suggestion-card">
                    <div className="practice-mixed-suggestion-header">
                      <span className="practice-mixed-suggestion-icon">📋</span>
                      <div>
                        <h3>题目数量偏少</h3>
                        <p>
                          当前任务绑定的知识点下已有 <strong>{questions.length}</strong> 道题，建议本次练习 <strong>{RECOMMENDED_PRACTICE_COUNT}</strong> 道题。
                          你可以先完成已有题目，也可以让 AI 临时补充 <strong>{RECOMMENDED_PRACTICE_COUNT - questions.length}</strong> 道题，组成一次混合练习。
                        </p>
                      </div>
                    </div>

                    {!taskGenLoading && !taskGenError && mixedSupplementQuestions.length === 0 && (
                      <div className="practice-mixed-suggestion-actions">
                        <button
                          className="ghost-button compact"
                          type="button"
                          onClick={() => {
                            dismissMixedSuggestion();
                          }}
                        >
                          只练题库题
                        </button>
                        <button
                          className="primary-button compact"
                          type="button"
                          onClick={() => handleMixedSupplement(RECOMMENDED_PRACTICE_COUNT - questions.length)}
                        >
                          ✨ AI 补充题目
                        </button>
                        <button
                          className="ghost-button compact"
                          type="button"
                          onClick={() => dismissMixedSuggestion()}
                        >
                          稍后再说
                        </button>
                      </div>
                    )}

                    {taskGenLoading && (
                      <div className="practice-task-gen-loading" style={{ padding: "16px 0" }}>
                        <div className="cmp-loading-spinner" />
                        <p>正在生成补充题目...</p>
                      </div>
                    )}

                    {taskGenError && !taskGenLoading && (
                      <div style={{ padding: "12px 0", color: "#b91c1c", fontSize: 13 }}>
                        <p style={{ margin: "0 0 8px" }}>{taskGenError}</p>
                        <button className="ghost-button compact" onClick={() => dismissMixedSuggestion()}>关闭</button>
                      </div>
                    )}

                    {mixedSupplementQuestions.length > 0 && !taskGenLoading && (
                      <div style={{ marginTop: 12 }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                          <span style={{ fontSize: 14, fontWeight: 600, color: "#059669" }}>
                            ✅ AI 已补充 {mixedSupplementQuestions.length} 道临时题
                          </span>
                          <button className="ghost-button compact" onClick={() => dismissMixedSuggestion()}>关闭</button>
                        </div>
                        <p style={{ fontSize: 13, color: "#b45309", margin: "0 0 12px" }}>
                          ⚠️ 补充题为临时生成，未加入正式题库。可开始混合练习。
                        </p>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button
                            className="primary-button compact"
                            type="button"
                            onClick={startAiTempPractice}
                          >
                            使用 AI 补充题开始练习
                          </button>
                          <button
                            className="ghost-button compact"
                            type="button"
                            onClick={() => dismissMixedSuggestion()}
                          >
                            仅练题库题
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="question-section-card">
                <div className="question-section-head">
                  <h3>练习题列表</h3>
                  <span>共 {totalCount} 条</span>
                </div>
                <div className="batch-select-toolbar">
                  <span className="batch-selected-count">已选 {selectedQuestionIds.size} 道客观题</span>
                  <button type="button" className="ghost-button compact" onClick={selectAllCurrentObjectiveQuestions}>
                    全选当前筛选
                  </button>
                  <button type="button" className="ghost-button compact" onClick={clearBatchSelection}>
                    清空选择
                  </button>
                  <button
                    type="button"
                    className="primary-button compact"
                    disabled={selectedQuestionIds.size < 2 || batchLoading}
                    onClick={startBatchPractice}
                  >
                    {batchLoading ? "加载中..." : "开始组合练习"}
                  </button>
                  {batchNotice && <span className="batch-select-notice">{batchNotice}</span>}
                </div>
                <div className="question-list">
                  {questions.map((q) => (
                    <div key={q.id} className="question-card">
                      <label
                        className="batch-question-check"
                        title={
                          !isBatchObjectiveQuestion(q)
                            ? "简答题暂不支持自动评分组合练习"
                            : hasValidObjectiveAnswerStructure(q)
                              ? "加入组合练习"
                              : "该题答案结构异常，暂不能加入组合练习"
                        }
                      >
                        <input
                          type="checkbox"
                          checked={selectedQuestionIds.has(q.id)}
                          disabled={!isBatchObjectiveQuestion(q) || !hasValidObjectiveAnswerStructure(q)}
                          onChange={() => toggleBatchQuestion(q)}
                        />
                      </label>
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
                              {isAiGeneratedQuestion(q) ? "AI 原创生成" : (SOURCE_LABELS[q.source] || q.source)}
                            </span>
                          )}
                          <span className="history-meta">
                            {formatDate(q.updated_at || q.created_at)}
                          </span>
                        </div>
                      </div>
                      <div className="question-card-actions">
                        {isProgrammingQuestion(q) ? (
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
              </>
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
      )}

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

              {isAiGeneratedQuestion(detailQuestion) && (
                <AiGeneratedAttemptSummary question={detailQuestion} attempt={submittedAttempt} />
              )}

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
                          <QuestionAnalysisBlock analysis={detailQuestion.explanation} />
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
                {!isAiGeneratedQuestion(detailQuestion) && (
                  <>
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
                  </>
                )}
              </div>

              {submittedAttempt && renderTaskCompleteCard()}

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

      {/* Paper Detail Drawer — Exam Style */}
      {paperDetail && (
        <div className="practice-drawer-overlay" onClick={() => setPaperDetail(null)}>
          <div className="practice-detail-drawer practice-exam-paper" onClick={(e) => e.stopPropagation()}>
            {/* ── 试卷头 ── */}
            <div className="exam-paper-header">
              <button className="modal-close" onClick={() => setPaperDetail(null)}>&times;</button>
              <h2 className="exam-paper-title">{paperDetail.title}</h2>
              <div className="exam-paper-meta">
                {paperDetail.course_id && (
                  <span className="subject-pill small practice-course-pill">{getSubjectLabel(paperDetail.course_id)}</span>
                )}
                <span className="subject-pill small practice-source-pill">试卷识别</span>
                <span className="subject-pill small">{paperQuestions.length} 道题</span>
                <span className="history-meta">{formatDate(paperDetail.updated_at || paperDetail.created_at)}</span>
              </div>
            </div>

            {/* ── 试卷正文 ── */}
            <div className="exam-paper-body">
              {paperLoading ? (
                <div className="empty-state">加载试卷中...</div>
              ) : paperQuestions.length === 0 ? (
                <div className="empty-state">暂无题目</div>
              ) : (
                paperQuestions.map((q, idx) => {
                  const isProgramming = q.type === "programming";
                  return (
                    <div key={q.id} className="exam-question" id={`paper-q-${q.id}`}>
                      {/* 题号行 */}
                      <div className="exam-question-head">
                        <span className="exam-question-number">{q.question_order || idx + 1}.</span>
                        <span className={`q-type-badge ${getTypeClass(q.type)}`}>{TYPE_LABELS[q.type] || q.type}</span>
                        {q.difficulty && (
                          <span className="exam-difficulty">{DIFFICULTY_LABELS[q.difficulty] || q.difficulty}</span>
                        )}
                        {q.score && <span className="exam-score">（{q.score}）</span>}
                      </div>

                      {/* 标题 */}
                      {q.title && <h4 className="exam-question-title">{q.title}</h4>}

                      {/* 题干 — 编程题用等宽字体 */}
                      <div className={`exam-question-content${isProgramming ? " exam-question-content--code" : ""}`}>
                        {q.content.split("\n").map((line, li) => (
                          <p key={li}>{line || " "}</p>
                        ))}
                      </div>

                      {/* 选项 */}
                      {q.options && (
                        <div className="exam-options">
                          {q.options.split("\n").filter(Boolean).map((opt, oi) => (
                            <div key={oi} className="exam-option">{opt.trim()}</div>
                          ))}
                        </div>
                      )}

                      {/* 答案与解析 — 默认收起 */}
                      {(q.answer || q.explanation) && (
                        <details className="exam-answer-section">
                          <summary>查看答案与解析</summary>
                          {q.answer && (
                            <div className="exam-answer">
                              <strong>参考答案：</strong>
                              <span>{q.answer}</span>
                            </div>
                          )}
                          {q.explanation && (
                            <div className="exam-explanation">
                              <strong>解析：</strong>
                              <QuestionAnalysisBlock analysis={q.explanation} />
                            </div>
                          )}
                        </details>
                      )}

                      {/* 原始识别文本 — 默认收起 */}
                      {q.raw_text && (
                        <details className="exam-raw-text">
                          <summary>查看原始识别文本</summary>
                          <pre>{q.raw_text}</pre>
                        </details>
                      )}

                      {/* 操作按钮 */}
                      <div className="exam-question-actions">
                        <button className="ghost-button compact" onClick={() => openEditQuestion(q)}>编辑题目</button>
                        <button className="primary-button compact" onClick={() => startPracticeFromPaper(q)}>开始练习</button>
                        {!isAiGeneratedQuestion(q) && (
                          <button
                            className="ghost-button compact"
                            disabled={aiExplainLoadingId === q.id}
                            onClick={() => requestQuestionAiExplain(q, true)}
                          >
                            {aiExplainLoadingId === q.id ? "解析中..." : "AI 解析"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* Question Edit Modal */}
      {editingQuestion && editQuestionForm && (
        <div className="modal-overlay question-edit-overlay" onClick={closeEditQuestion}>
          <div className="modal-card question-edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>编辑题目</h3>
              <button className="modal-close" onClick={closeEditQuestion}>
                &times;
              </button>
            </div>
            <div className="task-modal-body question-edit-body">
              {editError && <div className="practice-import-error">{editError}</div>}

              <label className="field-label">题目标题 *</label>
              <input
                className="field"
                value={editQuestionForm.title}
                onChange={(e) => setEditQuestionForm((form) => ({ ...form, title: e.target.value }))}
                placeholder="请输入题目标题"
              />

              <div className="question-edit-grid">
                <div>
                  <label className="field-label">题型</label>
                  <select
                    className="field"
                    value={editQuestionForm.type}
                    onChange={(e) => setEditQuestionForm((form) => ({ ...form, type: e.target.value }))}
                  >
                    {TYPE_OPTIONS.filter((item) => item.value).map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label">难度</label>
                  <select
                    className="field"
                    value={editQuestionForm.difficulty}
                    onChange={(e) => setEditQuestionForm((form) => ({ ...form, difficulty: e.target.value }))}
                  >
                    {DIFFICULTY_OPTIONS.map((item) => (
                      <option key={item.value} value={item.value}>{item.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <label className="field-label">课程</label>
              <select
                className="field"
                value={editQuestionForm.course_id}
                onChange={async (e) => {
                  const nextCourse = e.target.value;
                  setEditQuestionForm((form) => ({ ...form, course_id: nextCourse }));
                  setEditModuleId("");
                  setEditKpId("");
                  await loadKnowledgePoints(normalizeSubject(nextCourse, ""));
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
                  <p className="practice-kp-empty">当前课程暂无知识点路线，可不绑定知识点。</p>
                ) : (
                  <>
                    <select
                      className="field"
                      value={editModuleId}
                      onChange={(e) => {
                        setEditModuleId(e.target.value);
                        setEditKpId("");
                      }}
                    >
                      <option value="">不绑定知识点模块</option>
                      {knowledgePointModules.map((kp) => (
                        <option key={kp.id} value={kp.id}>{kp.title}</option>
                      ))}
                    </select>

                    <label className="field-label">小知识点（可选）</label>
                    <select
                      className="field"
                      value={editKpId}
                      onChange={(e) => setEditKpId(e.target.value)}
                      disabled={!editModuleId || editModuleChildren.length === 0}
                    >
                      <option value="">{editModuleId ? "仅绑定大模块" : "请先选择知识点模块"}</option>
                      {editModuleChildren.map((kp) => (
                        <option key={kp.id} value={kp.id}>{kp.title}</option>
                      ))}
                    </select>
                  </>
                )}
              </div>

              <label className="field-label">题干内容 *</label>
              <textarea
                className="field practice-edit-question-content"
                rows={12}
                value={editQuestionForm.content}
                onChange={(e) => setEditQuestionForm((form) => ({ ...form, content: e.target.value }))}
                placeholder="请输入题干内容"
              />

              {isChoiceLikeType(editQuestionForm.type) && (
                <div className="practice-edit-options">
                  <label className="field-label">选项</label>
                  {editOptionItems.map((item, index) => (
                    <div key={`opt-${index}-${item.label}`} className="practice-edit-option-row">
                      <input
                        className="field practice-edit-option-label"
                        value={item.label}
                        onChange={(e) => updateEditOption(index, { label: e.target.value })}
                        placeholder="选项标号"
                      />
                      <input
                        className="field practice-edit-option-content"
                        value={item.content}
                        onChange={(e) => updateEditOption(index, { content: e.target.value })}
                        placeholder={`${item.label || "选项"} 内容`}
                      />
                      <button
                        type="button"
                        className="tiny-button danger"
                        onClick={() => removeEditOption(index)}
                        title="删除此选项"
                      >
                        删除
                      </button>
                    </div>
                  ))}
                  <button type="button" className="ghost-button compact" onClick={addEditOption}>
                    ＋ 添加选项
                  </button>
                </div>
              )}

              <label className="field-label">标准答案</label>
              <input
                className="field"
                value={editQuestionForm.answer}
                onChange={(e) => setEditQuestionForm((form) => ({ ...form, answer: e.target.value }))}
                placeholder="请输入标准答案"
              />

              <label className="field-label">解析</label>
              <textarea
                className="field practice-edit-explanation"
                value={editQuestionForm.explanation || ""}
                onChange={(e) => setEditQuestionForm((form) => ({ ...form, explanation: e.target.value }))}
                placeholder="请输入解析"
              />

              {editQuestionForm.raw_text && (
                <>
                  <label className="field-label">原始识别文本</label>
                  <textarea
                    className="field practice-edit-raw-text"
                    value={editQuestionForm.raw_text}
                    onChange={(e) => setEditQuestionForm((form) => ({ ...form, raw_text: e.target.value }))}
                    readOnly
                  />
                </>
              )}
            </div>
            <div className="task-form-actions">
              <button className="ghost-button compact" onClick={closeEditQuestion} disabled={editSaving}>
                取消
              </button>
              <button className="primary-button compact" onClick={saveEditedQuestion} disabled={editSaving}>
                {editSaving ? "保存中..." : "保存修改"}
              </button>
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
              <input
                type="number"
                className="field"
                min="1"
                max="10"
                step="1"
                value={genCount}
                onChange={(e) => setGenCount(normalizeGenerateCount(e.target.value))}
                onBlur={(e) => setGenCount(normalizeGenerateCount(e.target.value))}
              />

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

              {genError && (
                <div className="practice-import-error" style={{ marginTop: 12 }}>
                  生成失败：{genError}
                </div>
              )}
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

              {/* ── 异步识别进度 ── */}
              {importJobStatus && ["pending", "processing"].includes(importJobStatus) && (
                <div className="practice-import-progress">
                  <div className="practice-import-progress-header">
                    <span className="practice-import-progress-spinner" aria-hidden="true">⏳</span>
                    <span>正在识别试卷，请稍候...</span>
                  </div>
                  <div className="practice-import-progress-body">
                    <div className="practice-import-progress-status">状态：{importJobStatusLabel}</div>
                    <div className="practice-import-progress-step">{importJobProgress || "准备中..."}</div>
                    {(importJob?.parse_method || importJobElapsedText) && (
                      <div className="practice-import-progress-meta">
                        {importJob?.parse_method && <>识别方式：{formatExtractMethodLabel({ extract_method: importJob.parse_method, qwen_used: importJob.parse_method === "qwen" || importJob.parse_method === "mixed", file_type: "pdf" })?.label || importJob.parse_method}</>}
                        {importJob?.parse_method && importJobElapsedText && " ｜ "}
                        {importJobElapsedText && <>已耗时：{importJobElapsedText}</>}
                      </div>
                    )}
                    {importExtractMeta?.total_pages > 0 && (
                      <div className="practice-import-progress-meta">
                        已处理 {importExtractMeta.parsed_pages || 0} / {importExtractMeta.total_pages} 页
                        {importExtractMeta.qwen_used && "（Qwen 视觉识别）"}
                      </div>
                    )}
                    {importJob && (
                      <div className="practice-import-progress-meta">
                        已识别题目数：{importJob.question_count || 0}
                      </div>
                    )}
                    {importJob?.error_message && (
                      <div className="practice-import-progress-meta">
                        错误信息：{importJob.error_message}
                      </div>
                    )}
                  </div>
                  <div className="practice-import-progress-hint">
                    {importJobLongRunning
                      ? "识别时间较长，可能正在处理扫描页或等待 AI 返回。你可以继续等待，或关闭弹窗稍后查看。"
                      : "扫描版 PDF 识别可能需要 1～3 分钟，请不要关闭页面"}
                  </div>
                </div>
              )}

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
                    <div className="practice-extract-info-row">
                      <div className={`practice-extract-method-badge ${formatExtractMethodLabel(importExtractMeta).cssClass}`}>
                        <span className="practice-extract-method-icon" aria-hidden="true">
                          {importExtractMeta.qwen_used ? "🤖" : "📄"}
                        </span>
                        <span>{formatExtractMethodLabel(importExtractMeta).label}</span>
                      </div>
                      {importExtractMeta.total_pages > 0 && (
                        <span className="practice-extract-pages">
                          📖 已识别 {importExtractMeta.parsed_pages || "?"} / {importExtractMeta.total_pages} 页
                          {importExtractMeta.page_limit_hit && (
                            <span className="practice-extract-page-limit-hint">（部分页）</span>
                          )}
                        </span>
                      )}
                    </div>
                  )}
                  {importWarnings && importWarnings.length > 0 && (
                    <div className="practice-import-warnings">
                      {importWarnings.map((w, i) => (
                        <div key={i} className="practice-import-warning-item">⚠️ {w}</div>
                      ))}
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
                disabled={!importFile || importLoading || ["pending", "processing"].includes(importJobStatus)}
                onClick={parseImportFile}
              >
                {importLoading || ["pending", "processing"].includes(importJobStatus)
                  ? "识别中..."
                  : importJobStatus === "succeeded"
                  ? "已识别"
                  : "开始识别"}
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

      {/* ── AI Save to Bank Modal ── */}
      {aiSaveModalOpen && createPortal(
        <div className="kam-overlay" onClick={(e) => { if (e.target === e.currentTarget) closeAiSaveModal(); }}>
          <div className="kam-modal" style={{ maxWidth: 780 }}>
            <button className="kam-close" onClick={closeAiSaveModal} aria-label="关闭">×</button>
            <div className="kam-body">
              <h2 className="kam-title" style={{ marginBottom: 8 }}>保存 AI 题目到题库</h2>
              <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 16px" }}>
                编辑确认后保存到正式题库。题干、答案、解析不能为空。
              </p>

              {!aiSaveResult && !aiSaveError && (
                <>
                  {aiSaveQuestions.length === 0 ? (
                    <p style={{ color: "#94a3b8", textAlign: "center", padding: 24 }}>没有待保存的题目</p>
                  ) : (
                    <div style={{ maxHeight: "50vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
                      {aiSaveQuestions.map((q, qIdx) => (
                        <div key={qIdx} className="kam-tree-module" style={{ borderColor: "#e5e7eb" }}>
                          <div className="kam-tree-module-header" style={{ justifyContent: "space-between" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <span style={{ fontWeight: 700, color: "#2563eb" }}>第 {qIdx + 1} 题</span>
                              <span style={{ fontSize: 12, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>
                                {q.type === "single_choice" ? "单选" : q.type === "multiple_choice" ? "多选" : q.type === "judge" ? "判断" : "简答"}
                              </span>
                            </div>
                            <button className="ghost-button compact" style={{ color: "#ef4444", fontSize: 12 }} type="button" onClick={() => removeAiSaveQuestion(qIdx)}>
                              删除
                            </button>
                          </div>
                          <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
                            <div>
                              <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>题型</label>
                              <select className="field" style={{ width: "100%", marginTop: 4 }} value={q.type} onChange={(e) => updateAiSaveQuestion(qIdx, "type", e.target.value)}>
                                <option value="single_choice">单选题</option>
                                <option value="multiple_choice">多选题</option>
                                <option value="judge">判断题</option>
                                <option value="short_answer">简答题</option>
                              </select>
                            </div>
                            <div>
                              <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>题干</label>
                              <textarea className="field" style={{ width: "100%", marginTop: 4, minHeight: 60 }} value={q.stem} onChange={(e) => updateAiSaveQuestion(qIdx, "stem", e.target.value)} />
                            </div>
                            {(q.type === "single_choice" || q.type === "multiple_choice") && (
                              <div>
                                <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>选项</label>
                                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                                  {q.options.map((opt, oIdx) => (
                                    <div key={oIdx} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                      <span style={{ fontWeight: 700, width: 20, color: "#64748b" }}>{opt.label}</span>
                                      <input className="field" style={{ flex: 1 }} value={opt.text || ""} onChange={(e) => updateAiSaveOption(qIdx, oIdx, "text", e.target.value)} />
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            <div>
                              <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>正确答案</label>
                              <input className="field" style={{ width: "100%", marginTop: 4 }} value={q.answer} onChange={(e) => updateAiSaveQuestion(qIdx, "answer", e.target.value)} placeholder={q.type === "judge" ? "正确 或 错误" : q.type === "multiple_choice" ? "如：A,C" : "如：A"} />
                            </div>
                            <div>
                              <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b" }}>解析</label>
                              <textarea className="field" style={{ width: "100%", marginTop: 4, minHeight: 60 }} value={q.analysis} onChange={(e) => updateAiSaveQuestion(qIdx, "analysis", e.target.value)} />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="kam-footer">
                    <span className="kam-footer-hint">共 {aiSaveQuestions.length} 道题待保存</span>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="cmp-btn cmp-btn--ghost" type="button" onClick={closeAiSaveModal} disabled={aiSaveSaving}>取消</button>
                      <button className="cmp-btn cmp-btn--primary" type="button" onClick={handleAiSaveToBank} disabled={aiSaveQuestions.length === 0 || aiSaveSaving}>
                        {aiSaveSaving ? "保存中..." : "确认保存到题库"}
                      </button>
                    </div>
                  </div>
                </>
              )}

              {aiSaveError && !aiSaveResult && (
                <div style={{ padding: 24, textAlign: "center" }}>
                  <p style={{ color: "#b91c1c", margin: "0 0 12px" }}>{aiSaveError}</p>
                  <button className="cmp-btn cmp-btn--ghost" type="button" onClick={() => setAiSaveError("")}>关闭</button>
                </div>
              )}

              {aiSaveResult && (
                <div style={{ padding: 24, textAlign: "center" }}>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
                  <h3 style={{ color: "#059669", margin: "0 0 12px" }}>
                    已保存到题库，当前知识点已有 {totalCount} 道题，可开始正式练习。
                  </h3>
                  <div style={{ display: "flex", justifyContent: "center", gap: 16, marginBottom: 12 }}>
                    <div style={{ background: "#f0fdf4", borderRadius: 10, padding: "10px 18px", border: "1px solid #bbf7d0" }}>
                      <span style={{ fontSize: 22, fontWeight: 800, color: "#059669" }}>{aiSaveResult.created_count}</span>
                      <span style={{ fontSize: 12, color: "#64748b", display: "block" }}>新增</span>
                    </div>
                    <div style={{ background: "#f8fafc", borderRadius: 10, padding: "10px 18px", border: "1px solid #e2e8f0" }}>
                      <span style={{ fontSize: 22, fontWeight: 800, color: "#64748b" }}>{aiSaveResult.skipped_count}</span>
                      <span style={{ fontSize: 12, color: "#64748b", display: "block" }}>跳过重复</span>
                    </div>
                    <div style={{ background: "#eff6ff", borderRadius: 10, padding: "10px 18px", border: "1px solid #bfdbfe" }}>
                      <span style={{ fontSize: 22, fontWeight: 800, color: "#2563eb" }}>{totalCount}</span>
                      <span style={{ fontSize: 12, color: "#64748b", display: "block" }}>当前题库</span>
                    </div>
                  </div>
                  {aiSaveResult.refreshSuccess === false && (
                    <p style={{ color: "#b45309", fontSize: 13, margin: "0 0 16px" }}>
                      题目已保存，但当前列表刷新失败，请手动刷新页面。
                    </p>
                  )}
                  <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
                    <button
                      className="cmp-btn cmp-btn--primary"
                      type="button"
                      onClick={() => {
                        closeAiSaveModal();
                        // Collapse AI preview and let user see the question list
                        setTaskGenQuestions([]);
                        setTaskGenError("");
                        // Scroll to question list
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      关闭并查看题库
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </section>
  );
}
