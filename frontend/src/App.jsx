import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import AppLayout from "./components/AppLayout.jsx";
import ChatMessage from "./components/ChatMessage.jsx";
import CourseDashboard from "./components/CourseDashboard.jsx";
import KnowledgeLearningPage from "./components/KnowledgeLearningPage.jsx";
import CourseMaterialsPage from "./components/CourseMaterialsPage.jsx";
import HomePage from "./components/HomePage.jsx";
import AIQuestionPage from "./components/AIQuestionPage.jsx";
import MaterialPickerModal from "./components/MaterialPickerModal.jsx";
import ProfilePage from "./components/ProfilePage.jsx";
import MembershipPage from "./components/MembershipPage.jsx";

const CodeStudio = lazy(() => import("./components/CodeStudio.jsx"));
const TaskCenter = lazy(() => import("./components/TaskCenter.jsx"));
const PracticeCenter = lazy(() => import("./components/PracticeCenter.jsx"));
const LearningDataCenter = lazy(() => import("./components/LearningDataCenter.jsx"));
const ReviewCenter = lazy(() => import("./components/ReviewCenter.jsx"));
import FeatureUnavailable from "./components/FeatureUnavailable.jsx";
const KnowledgeBaseCenter = lazy(() => import("./components/KnowledgeBaseCenter.jsx"));
const QuotaCenter = lazy(() => import("./components/QuotaCenter.jsx"));
const AdminUsageCenter = lazy(() => import("./components/AdminUsageCenter.jsx"));
const AdminCenter = lazy(() => import("./components/AdminCenter.jsx"));
const LearningReportCenter = lazy(() => import("./components/LearningReportCenter.jsx"));
const SharedReportPage = lazy(() => import("./components/SharedReportPage.jsx"));
const SearchResultsPage = lazy(() => import("./components/SearchResultsPage.jsx"));
import MarkdownMessage from "./components/MarkdownMessage.jsx";
import {
  COURSE_OPTIONS,
  DEFAULT_SUBJECT,
  getSubjectLabel,
  normalizeSubject,
} from "./courseOptions.js";

const USER_STORAGE_KEY = "ai_study_platform_user";
const ACTIVE_SESSION_STORAGE_KEY = "ai_study_platform_active_session_id";
const CURRENT_PAGE_KEY = "ai_study_current_page";
const CURRENT_SUBJECT_KEY = "ai_study_current_subject";
const API_BASE = "/api";
const MAX_FILE_SIZE = 20 * 1024 * 1024;

const AVATARS = [
  { id: "avatar_1", label: "A1", background: "#2563eb" },
  { id: "avatar_2", label: "A2", background: "#059669" },
  { id: "avatar_3", label: "A3", background: "#7c3aed" },
  { id: "avatar_4", label: "A4", background: "#db2777" },
  { id: "avatar_5", label: "A5", background: "#ea580c" },
  { id: "avatar_6", label: "A6", background: "#0f766e" },
];

const TARGET_LEVEL_OPTIONS = [
  "入门了解",
  "课堂跟上",
  "考试掌握",
  "项目实战",
  "深入精通",
  "自定义",
];

const MESSAGE_TRANSLATIONS = {
  "Invalid username or password": "用户名或密码错误",
  "Username already exists": "用户名已存在",
  "Failed to load chat history": "加载聊天记录失败",
  "Cannot load chat history. Please check the backend.": "无法加载聊天记录，请检查后端服务。",
  "Failed to load materials": "加载资料失败",
  "Cannot load materials. Please check the backend.": "无法加载资料，请检查后端服务。",
  "Failed to load material detail": "加载资料详情失败",
  "Cannot load material detail right now.": "暂时无法加载资料详情。",
  "Failed to delete material": "删除资料失败",
  "Cannot delete this material right now.": "暂时无法删除该资料。",
  "Failed to rebuild indexes": "重建索引失败",
  "Cannot rebuild indexes right now.": "暂时无法重建索引。",
  "Please log in first.": "请先登录。",
  "Failed to open chat session": "打开对话失败",
  "Cannot open this chat session right now.": "暂时无法打开该对话。",
  "Failed to delete chat session": "删除对话失败",
  "Cannot delete this chat session right now.": "暂时无法删除该对话。",
  "Failed to rename chat session": "重命名对话失败",
  "Cannot rename this chat session right now.": "暂时无法重命名该对话。",
  "Login expired. Please log in again.": "登录已过期，请重新登录。",
  "Please enter username and password.": "请输入用户名和密码。",
  "Register failed": "注册失败",
  "Registration successful. Please complete your profile.": "注册成功，请完善个人资料。",
  "Login failed": "登录失败",
  "Cannot reach the backend.": "无法连接后端服务。",
  "Failed to save profile": "保存个人资料失败",
  "Profile saved.": "个人资料已保存。",
  "Cannot save your profile right now.": "暂时无法保存个人资料。",
  "Unsupported file type. Please choose PDF, PNG, JPG/JPEG, or WEBP.": "不支持的文件类型，请选择 PDF、PNG、JPG/JPEG 或 WEBP。",
  "File size must be 10MB or smaller.": "文件大小不能超过 10MB。",
  "Upload rejected. Check file type, size, and subject.": "上传被拒绝，请检查文件类型、大小和学科。",
  "File too large. Please upload a file under 10MB.": "文件过大，请上传 10MB 以内的文件。",
  "Upload parameters are invalid. Please try again.": "上传参数无效，请重试。",
  "The backend could not process this file.": "后端暂时无法处理该文件。",
  "Gateway error. The backend service may be unavailable.": "网关错误，后端服务可能不可用。",
  "Upload request failed. Please try again.": "上传请求失败，请重试。",
  "AI reply failed.": "AI 回复失败。",
  "Attachment question saved to chat history and added to your library.": "附件提问已保存到聊天记录，并已加入个人资料库。",
  "Please enter a question before sending the file.": "请先输入问题后再发送文件。",
  "Failed to add this attachment to the library": "添加附件到资料库失败",
  "Cannot add this attachment right now.": "暂时无法添加该附件。",
};

const ALLOWED_FILE_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/webp",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "text/markdown",
  "text/x-python",
  "text/x-java",
  "text/x-c",
  "text/x-c++",
  "text/javascript",
  "text/html",
  "text/css",
  "application/json",
  "application/xml",
  "text/xml",
  "text/x-sh",
  "text/x-sql",
  "application/x-yaml",
  "text/yaml",
  "text/x-go",
  "text/x-php",
  "text/x-ruby",
];

const ALLOWED_EXTENSIONS = new Set([
  ".pdf", ".png", ".jpg", ".jpeg", ".webp",
  ".docx", ".pptx",
  ".txt", ".md", ".markdown",
  ".py", ".java", ".c", ".cpp", ".h", ".hpp",
  ".js", ".jsx", ".ts", ".tsx",
  ".html", ".htm", ".css", ".json", ".xml", ".yaml", ".yml",
  ".sql", ".sh", ".bash", ".go", ".rs", ".php", ".rb",
]);

function isAllowedFile(file) {
  if (ALLOWED_FILE_TYPES.includes(file.type)) return true;
  const ext = (file.name || "").toLowerCase().match(/\.[a-z0-9]+$/)?.[0] || "";
  return ALLOWED_EXTENSIONS.has(ext);
}

const RECORD_TYPE_OPTIONS = [
  { value: "", label: "全部" },
  { value: "wrong_question", label: "错题本" },
  { value: "important", label: "重点" },
  { value: "review", label: "待复习" },
];

const REVIEW_STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "pending", label: "待复习" },
  { value: "reviewed", label: "已复习" },
];

function getSavedUser() {
  try {
    const savedUser = localStorage.getItem(USER_STORAGE_KEY);
    return savedUser ? JSON.parse(savedUser) : null;
  } catch {
    localStorage.removeItem(USER_STORAGE_KEY);
    return null;
  }
}

function getInitialSubject() {
  try {
    const saved = localStorage.getItem(CURRENT_SUBJECT_KEY);
    return COURSE_OPTIONS.includes(saved) ? saved : DEFAULT_SUBJECT;
  } catch {
    return DEFAULT_SUBJECT;
  }
}

function getMaterialSortValue(material, key) {
  if (key === "size") {
    return Number(material?.file_size ?? material?.size ?? material?.fileSize ?? 0) || 0;
  }
  if (key === "chunks") {
    return Number(material?.chunk_count ?? material?.chunks ?? material?.chunkCount ?? 0) || 0;
  }
  if (key === "date") {
    const value = material?.created_at || material?.uploaded_at || material?.upload_time || material?.updated_at || 0;
    const time = new Date(value).getTime();
    return Number.isNaN(time) ? 0 : time;
  }
  return String(material?.original_filename || material?.filename || material?.name || "").trim();
}

function sortMaterialsByMode(items, mode) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (mode === "oldest") {
      return getMaterialSortValue(a, "date") - getMaterialSortValue(b, "date");
    }
    if (mode === "nameAsc") {
      return getMaterialSortValue(a, "name").localeCompare(getMaterialSortValue(b, "name"), "zh-CN");
    }
    if (mode === "nameDesc") {
      return getMaterialSortValue(b, "name").localeCompare(getMaterialSortValue(a, "name"), "zh-CN");
    }
    if (mode === "sizeDesc") {
      return getMaterialSortValue(b, "size") - getMaterialSortValue(a, "size");
    }
    if (mode === "sizeAsc") {
      return getMaterialSortValue(a, "size") - getMaterialSortValue(b, "size");
    }
    if (mode === "chunksAsc") {
      return getMaterialSortValue(a, "chunks") - getMaterialSortValue(b, "chunks");
    }
    if (mode === "chunksDesc") {
      return getMaterialSortValue(b, "chunks") - getMaterialSortValue(a, "chunks");
    }
    return getMaterialSortValue(b, "date") - getMaterialSortValue(a, "date");
  });
  return sorted;
}

function isPrivilegedAccount(user) {
  const role = String(user?.role || user?.profile?.role || "").toLowerCase();
  const plan = String(user?.plan || user?.membership_plan || user?.profile?.plan || "").toLowerCase();
  const username = String(user?.username || "").toLowerCase();
  return (
    user?.is_admin === true ||
    user?.profile?.is_admin === true ||
    role === "admin" ||
    role === "developer" ||
    role === "dev" ||
    plan === "admin" ||
    plan === "developer" ||
    username === "admin"
  );
}

function shouldShowMembershipAd(user) {
  const plan = String(user?.plan || user?.membership_plan || user?.profile?.plan || "free").toLowerCase();
  return !isPrivilegedAccount(user) && (!plan || plan === "free");
}

function formatDate(value) {
  if (!value) return "";
  const textValue = String(value).trim();
  const hasTimezone = /Z$|[+-]\d{2}:?\d{2}$/.test(textValue);
  const normalizedValue = /^\d{4}-\d{2}-\d{2}T/.test(textValue) && !hasTimezone
    ? `${textValue}Z`
    : textValue;
  const date = new Date(normalizedValue);
  if (Number.isNaN(date.getTime())) return textValue;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "未知大小";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getParseStatusLabel(status) {
  if (status === "success") return "已生成 AI 知识索引";
  if (status === "partial") return "部分生成 AI 知识索引";
  if (status === "failed") return "解析失败，原文件仍可下载";
  if (status === "parsing") return "正在解析";
  return "等待解析";
}

function getParseStatusHint(material) {
  const status = material?.parse_status;
  if (status === "success") return "文件已保存，已生成 AI 知识索引。";
  if (status === "partial") return "文件已保存，已生成部分 AI 知识索引。";
  if (status === "failed") return "文件已保存，但解析失败，AI 暂时无法基于该文件问答。";
  if (status === "parsing") return "原文件已保存，正在解析，解析完成后可用于 AI 问答。";
  return "原文件已保存，等待生成 AI 知识索引。";
}

function getFilenameFromDisposition(disposition, fallback) {
  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(disposition || "");
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = /filename="?([^";]+)"?/i.exec(disposition || "");
  return asciiMatch?.[1] || fallback || "download";
}

function getFileTypeLabel(type) {
  const normalizedType = String(type || "").toLowerCase();

  if (normalizedType.includes("pdf")) return "PDF";
  if (
    normalizedType.includes("image") ||
    normalizedType.includes("png") ||
    normalizedType.includes("jpg") ||
    normalizedType.includes("jpeg") ||
    normalizedType.includes("webp")
  ) {
    return "图片";
  }
  if (normalizedType.includes("docx") || normalizedType.includes("word")) return "Word";
  if (normalizedType.includes("pptx") || normalizedType.includes("ppt") || normalizedType.includes("powerpoint") || normalizedType.includes("presentation")) return "PPT";
  if (normalizedType.includes("markdown") || normalizedType.includes("md")) return "Markdown";

  // 具体代码语言优先判断，避免被 text 泛匹配吞掉
  if (normalizedType.includes("html") || normalizedType.includes("htm")) return "HTML";
  if (normalizedType.includes("css")) return "CSS";
  if (normalizedType.includes("javascript") || normalizedType.includes("js")) return "JavaScript";
  if (normalizedType.includes("typescript") || normalizedType.includes("ts")) return "TypeScript";
  if (normalizedType.includes("python") || normalizedType.includes(".py")) return "Python";
  if (normalizedType.includes("java") && !normalizedType.includes("javascript")) return "Java";
  if (normalizedType.includes("c++") || normalizedType.includes("cpp")) return "C++";
  if (normalizedType.includes("rust") || normalizedType.includes(".rs")) return "Rust";
  if (normalizedType.includes("go") || normalizedType.includes("golang")) return "Go";
  if (normalizedType.includes("php")) return "PHP";
  if (normalizedType.includes("ruby") || normalizedType.includes(".rb")) return "Ruby";
  if (normalizedType.includes("sql")) return "SQL";
  if (normalizedType.includes("json")) return "JSON";
  if (normalizedType.includes("xml")) return "XML";
  if (normalizedType.includes("yaml") || normalizedType.includes("yml")) return "YAML";
  if (normalizedType.includes("shell") || normalizedType.includes("bash") || normalizedType.includes("sh")) return "Bash";

  if (normalizedType.includes("code")) return "代码";
  if (normalizedType.includes("text") || normalizedType === "txt") return "文本";

  return type || "";
}

function translateMessage(text) {
  if (!text) return "";
  if (MESSAGE_TRANSLATIONS[text]) return MESSAGE_TRANSLATIONS[text];

  if (text.startsWith("Upload failed. HTTP status:")) {
    return `上传失败，HTTP 状态码：${text.replace("Upload failed. HTTP status:", "").trim()}`;
  }

  return text;
}

function getDisplayMessage(detail, fallback) {
  return translateMessage(detail) || fallback;
}

function getReferenceSnippet(reference) {
  const raw = String(reference?.snippet || "").trim();
  if (!raw) return "暂无片段预览";
  // Clean LaTeX / HTML / Markdown artifacts from display text
  let s = raw;
  s = s.replace(/\$\$/g, "").replace(/\$/g, "").replace(/\\[\(\[]/g, "").replace(/\\[\)\]]/g, "");
  s = s.replace(/<[^>]*>/g, "");
  s = s.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
  s = s.replace(/[*_~`]{1,3}/g, "");
  s = s.replace(/\s+/g, " ").trim();
  if (!s) return "暂无片段预览";
  if (s.length <= 180) return s;
  return `${s.slice(0, 180)}...`;
}

function getRecordTypeLabel(recordType) {
  if (recordType === "wrong_question") return "错题本";
  if (recordType === "important") return "重点";
  if (recordType === "review") return "待复习";
  return "学习记录";
}

function getRecordTypeIcon(recordType) {
  if (recordType === "wrong_question") return "📝";
  if (recordType === "important") return "⭐";
  if (recordType === "review") return "⏰";
  return "📘";
}

function getLearningRecordSavedMessage(recordType, duplicated = false) {
  if (duplicated) return "已添加过";
  if (recordType === "wrong_question") return "已加入错题本";
  if (recordType === "important") return "已加入重点";
  if (recordType === "review") return "已加入待复习";
  return "学习记录已保存";
}

function getRecordAnswerPreview(answer) {
  const text = String(answer || "").trim();
  if (text.length <= 180) return text || "暂无回答内容";
  return `${text.slice(0, 180)}...`;
}

const VALID_PAGES = new Set([
  "home", "dashboard", "profile", "membership", "codeStudio",
  "taskCenter", "practiceCenter", "learningDataCenter", "reviewCenter",
  "learningPlanCenter", "knowledgeBaseCenter", "quotaCenter",
  "learningReportCenter", "adminUsageCenter", "adminCenter",
  "materials", "workspaceMaterials", "chat", "records", "history",
  "knowledgeLearning", "searchResults",
  "profileEdit", "onboarding",
  "login", "adminLogin",
]);

function getInitialPage() {
  const savedUser = getSavedUser();
  if (!savedUser) return "login";
  try {
    const savedPage = localStorage.getItem(CURRENT_PAGE_KEY);
    if (savedPage && VALID_PAGES.has(savedPage)) return savedPage;
  } catch { /* ignore */ }
  return "login";
}

function saveCurrentPage(pageName) {
  if (VALID_PAGES.has(pageName)) {
    try { localStorage.setItem(CURRENT_PAGE_KEY, pageName); } catch { /* ignore */ }
  }
}

function clearCurrentPage() {
  try { localStorage.removeItem(CURRENT_PAGE_KEY); } catch { /* ignore */ }
}

function App() {
  const [page, setPageRaw] = useState(getInitialPage);
  const [practiceContext, setPracticeContext] = useState(null);
  const [searchContext, setSearchContext] = useState(null);
  const [searchNavigate, setSearchNavigate] = useState(null);
  const [authMode, setAuthMode] = useState("login");

  const setPage = (nextPage, context = null) => {
    // Feature gating: intercept navigation to disabled features
    const PAGE_FEATURE_MAP = {
      codeStudio: "feature_code_studio_enabled",
      practiceCenter: "feature_practice_center_enabled",
    };
    const gateKey = PAGE_FEATURE_MAP[nextPage];
    if (gateKey && !isFeatureEnabled(gateKey)) {
      alert("该功能暂时维护中，请稍后再试");
      return;
    }

    // Auto-initialize profile form when navigating to profileEdit
    if (nextPage === "profileEdit" && user) {
      setProfileForm({
        nickname: user.nickname || "",
        grade: user.grade || "",
        major: user.major || "",
        avatar: user.avatar || "avatar_1",
      });
      setLearningGoals(Array.isArray(user?.learning_goals) ? [...user.learning_goals] : []);
    }

    if (context?.courseId) {
      setSubject(normalizeSubject(context.courseId));
    }
    if (nextPage === "practiceCenter" && context) {
      setPracticeContext(context);
    } else {
      setPracticeContext(null);
    }
    saveCurrentPage(nextPage);
    setPageRaw(nextPage);
  };
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginTab, setLoginTab] = useState("password"); // "password" | "email"
  const [emailLoginForm, setEmailLoginForm] = useState({ email: "", code: "" });
  const [emailLoginSending, setEmailLoginSending] = useState(false);
  const [emailLoginCountdown, setEmailLoginCountdown] = useState(0);
  const [emailLoginLoading, setEmailLoginLoading] = useState(false);
  const [user, setUser] = useState(getSavedUser);
  const [publicFeatures, setPublicFeatures] = useState(null);
  const [userAnnouncements, setUserAnnouncements] = useState([]);
  const [dismissedAnnounceIds, setDismissedAnnounceIds] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("dismissed_announcements") || "[]"); } catch { return []; }
  });
  const dismissAnnounce = (id) => {
    const next = [...dismissedAnnounceIds, id];
    setDismissedAnnounceIds(next);
    try { sessionStorage.setItem("dismissed_announcements", JSON.stringify(next)); } catch {}
  };

  /** Normalize feature value: missing/error → true (default open), "false"/0 → false, "true"/1 → true */
  function normalizeFeatureValue(value) {
    if (value === undefined || value === null) return true;
    if (value === true || value === 1 || value === "1") return true;
    if (value === false || value === 0 || value === "0") return false;
    if (typeof value === "string") {
      const n = value.trim().toLowerCase();
      if (n === "true") return true;
      if (n === "false") return false;
    }
    return true; // unknown → default open
  }

  function isFeatureEnabled(key) {
    if (!publicFeatures) return true;           // not loaded yet → default open
    return normalizeFeatureValue(publicFeatures[key]);
  }

  /** Guard: if feature disabled, alert and return false. Usage: if (!guardFeature("key", "msg")) return; */
  function guardFeature(key, message) {
    if (!isFeatureEnabled(key)) {
      alert(message || "该功能暂时维护中，请稍后再试");
      return false;
    }
    return true;
  }

  useEffect(() => {
    fetch(`${API_BASE}/settings/public`)
      .then((r) => r.json())
      .then((d) => {
        // Accept both object {key:val} and array [{key,value}]
        if (Array.isArray(d.items)) {
          const m = {};
          d.items.forEach((s) => { m[s.key] = s.value; });
          setPublicFeatures(m);
        } else if (d && typeof d === "object") {
          setPublicFeatures(d);
        } else {
          setPublicFeatures(null);
        }
      })
      .catch(() => setPublicFeatures(null));
    fetch(`${API_BASE}/announcements/active`).then((r) => r.json()).then((d) => setUserAnnouncements(d.items || [])).catch(() => setUserAnnouncements([]));
  }, [user?.username]);

  // Sync to window so other components can read without prop-drilling
  useEffect(() => {
    window.__publicFeatures = publicFeatures;
  }, [publicFeatures]);
  const [profileForm, setProfileForm] = useState({
    nickname: "",
    grade: "",
    major: "",
    avatar: "avatar_1",
  });
  const [learningGoals, setLearningGoals] = useState([]);
  const [onboardingSaving, setOnboardingSaving] = useState(false);

  const [subject, setSubject] = useState(getInitialSubject);
  const [message, setMessage] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [showLibraryRefModal, setShowLibraryRefModal] = useState(false);
  const [libraryRefMaterials, setLibraryRefMaterials] = useState([]);
  const [selectedLibraryMaterials, setSelectedLibraryMaterials] = useState([]);
  const [libraryRefSearchQuery, setLibraryRefSearchQuery] = useState("");
  const [libraryRefLoading, setLibraryRefLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSessionSubject, setActiveSessionSubject] = useState(DEFAULT_SUBJECT);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [tip, setTip] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [reindexLoading, setReindexLoading] = useState(false);
  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [materials, setMaterials] = useState([]);
  const [materialSubjectFilter, setMaterialSubjectFilter] = useState("");
  const [materialSearchQuery, setMaterialSearchQuery] = useState("");
  const [materialSearchLoading, setMaterialSearchLoading] = useState(false);
  const [materialSearchTriggered, setMaterialSearchTriggered] = useState(false);
  const [materialSearchResults, setMaterialSearchResults] = useState([]);
  const [selectedMaterialId, setSelectedMaterialId] = useState(null);
  const [selectedMaterialDetail, setSelectedMaterialDetail] = useState(null);
  const [materialCurrentPage, setMaterialCurrentPage] = useState(1);
  const [materialSortMode, setMaterialSortMode] = useState("newest");
  const [materialListCollapsed, setMaterialListCollapsed] = useState(false);
  const PAGE_SIZE = 5;
  const [addToLibraryState, setAddToLibraryState] = useState({
    messageId: null,
    subject: DEFAULT_SUBJECT,
    loading: false,
  });
  const [learningRecordsLoading, setLearningRecordsLoading] = useState(false);
  const [learningRecords, setLearningRecords] = useState([]);
  const [learningRecordStats, setLearningRecordStats] = useState(null);
  const [learningRecordTypeFilter, setLearningRecordTypeFilter] = useState("");
  const [learningRecordSubjectFilter, setLearningRecordSubjectFilter] = useState("__CURRENT__");
  const [learningRecordReviewFilter, setLearningRecordReviewFilter] = useState("");
  const [selectedLearningRecord, setSelectedLearningRecord] = useState(null);
  const [learningRecordNote, setLearningRecordNote] = useState("");
  const [learningRecordTagsInput, setLearningRecordTagsInput] = useState("");
  const [learningRecordSaving, setLearningRecordSaving] = useState(false);
  const [learningRecordActionState, setLearningRecordActionState] = useState({
    messageKey: "",
    recordType: "",
    loading: false,
  });
  const [courseDashboardLoading, setCourseDashboardLoading] = useState(false);
  const [courseDashboardData, setCourseDashboardData] = useState(null);
  const [coursePreference, setCoursePreference] = useState(null);
  const [courseProgressSavingKey, setCourseProgressSavingKey] = useState("");
  const [pendingAIContext, setPendingAIContext] = useState(null);

  // Learning goal config — lifted from CourseDashboard, read from localStorage
  const GOAL_STORAGE_PREFIX = "ai_study_goal_config_";
  const [goalConfig, setGoalConfig] = useState(() => {
    try {
      const raw = localStorage.getItem(GOAL_STORAGE_PREFIX + subject);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  });

  // Sync goalConfig when subject changes
  useEffect(() => {
    try {
      const raw = localStorage.getItem(GOAL_STORAGE_PREFIX + subject);
      setGoalConfig(raw ? JSON.parse(raw) : null);
    } catch { setGoalConfig(null); }
  }, [subject]);

  const updateGoalConfig = (patch) => {
    setGoalConfig((prev) => {
      const current = prev || { goal: "systematic", difficulty: "standard", depth: "standard", dailyTime: 30, examDays: "7", examCustomDate: "", examPaperUploaded: false };
      const next = { ...current, ...patch };
      try { localStorage.setItem(GOAL_STORAGE_PREFIX + subject, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const fileInputRef = useRef(null);
  const materialsFileInputRef = useRef(null);
  const avatarInputRef = useRef(null);
  const plusMenuRef = useRef(null);
  const localMessageCounterRef = useRef(0);
  const materialStatusPollersRef = useRef({});
  const materialPollCountRef = useRef({});
  const MAX_POLL_COUNT = 150;

  useEffect(() => {
    if (COURSE_OPTIONS.includes(subject)) {
      try { localStorage.setItem(CURRENT_SUBJECT_KEY, subject); } catch { /* ignore */ }
    }
    setCoursePreference(null);
  }, [subject]);

  const currentChatSubject = activeSessionId ? activeSessionSubject : subject;
  const selectedFile = selectedFiles[0]
    ? {
        ...selectedFiles[0],
        name: selectedFiles[0].original_filename,
      }
    : null;
  const trimmedMessage = message.trim();
  const trimmedMaterialSearchQuery = materialSearchQuery.trim();
  const selectedAvatar =
    AVATARS.find((avatar) => avatar.id === profileForm.avatar) || AVATARS[0];

  const visibleSessions = useMemo(() => {
    return chatSessions.filter(
      (session) =>
        normalizeSubject(session.subject || session.course || "", "") === subject
    );
  }, [chatSessions, subject]);

  const groupedMaterials = useMemo(() => {
    return COURSE_OPTIONS.map((item) => ({
      subject: item,
      items: materials.filter(
        (material) => normalizeSubject(material.subject, "") === item
      ),
    }));
  }, [materials]);

  const currentFilterSubject = normalizeSubject(materialSubjectFilter || subject);

  const currentFilterItems = useMemo(() => {
    if (!currentFilterSubject) return [];
    const group = groupedMaterials.find((g) => g.subject === currentFilterSubject);
    return sortMaterialsByMode(group?.items || [], materialSortMode);
  }, [groupedMaterials, currentFilterSubject, materialSortMode]);

  const currentFilterTotalPages = Math.max(1, Math.ceil(currentFilterItems.length / PAGE_SIZE));

  const safeCurrentPage = Math.min(materialCurrentPage, currentFilterTotalPages);

  const paginatedFilterItems = currentFilterItems.slice(
    (safeCurrentPage - 1) * PAGE_SIZE,
    safeCurrentPage * PAGE_SIZE
  );

  const searchTotalPages = Math.max(
    1,
    Math.ceil(materialSearchResults.length / PAGE_SIZE)
  );
  const safeSearchPage = Math.min(materialCurrentPage, searchTotalPages);
  const sortedMaterialSearchResults = useMemo(
    () => sortMaterialsByMode(materialSearchResults, materialSortMode),
    [materialSearchResults, materialSortMode]
  );
  const paginatedSearchResults = sortedMaterialSearchResults.slice(
    (safeSearchPage - 1) * PAGE_SIZE,
    safeSearchPage * PAGE_SIZE
  );

  const validAttachedFiles = useMemo(() => {
    return selectedFiles.filter(
      (item) =>
        (item.parse_status === "success" || item.parse_status === "partial") &&
        Number(item.chunk_count || 0) > 0
    );
  }, [selectedFiles]);

  const hasAnyParsing = useMemo(() => {
    return selectedFiles.some(
      (item) => item.uploading || item.parse_status === "waiting" || item.parse_status === "pending" || item.parse_status === "parsing"
    );
  }, [selectedFiles]);

  const allFilesFailed = useMemo(() => {
    return selectedFiles.length > 0 && selectedFiles.every(
      (item) => item.parse_status === "failed"
    );
  }, [selectedFiles]);

  // Shared report pathname detection — public page, no login required
  const isSharedReportPath = window.location.pathname.startsWith("/shared/reports/");

  const canSendMessage = useMemo(() => {
    if (loading) return false;
    const hasFiles = selectedFiles.length > 0 || selectedLibraryMaterials.length > 0;
    if (hasFiles) {
      if (!trimmedMessage) return false;
      if (hasAnyParsing) return false;
      return validAttachedFiles.length > 0 || selectedLibraryMaterials.length > 0;
    }
    return Boolean(trimmedMessage);
  }, [loading, selectedFiles, trimmedMessage, hasAnyParsing, validAttachedFiles, selectedLibraryMaterials]);

  const createLocalMessage = (messageData) => ({
    clientId: `local-message-${Date.now()}-${localMessageCounterRef.current++}`,
    ...messageData,
  });

  const clearMaterialPoller = (localId) => {
    const timerId = materialStatusPollersRef.current[localId];
    if (timerId) {
      window.clearInterval(timerId);
      delete materialStatusPollersRef.current[localId];
    }
    delete materialPollCountRef.current[localId];
  };

  const clearAllMaterialPollers = () => {
    Object.values(materialStatusPollersRef.current).forEach((timerId) => {
      window.clearInterval(timerId);
    });
    materialStatusPollersRef.current = {};
  };

  const normalizeUploadedMaterial = (data, fallbackFile, localId) => {
    const material = data.material || {};
    return {
      localId,
      material_id: data.material_id || material.id,
      original_filename: data.filename || material.original_filename || fallbackFile?.name || "未命名文件",
      file_type: material.file_type || fallbackFile?.type || "",
      file_size: material.file_size ?? material.size ?? material.fileSize ?? data.file_size ?? data.size ?? data.fileSize ?? fallbackFile?.size ?? 0,
      parse_status: data.parse_status || material.parse_status || "pending",
      parse_progress: data.parse_progress ?? material.parse_progress ?? 0,
      chunk_count: data.chunk_count ?? material.chunk_count ?? 0,
      parse_error: material.parse_error || data.parse_error || "",
    };
  };

  const getSelectedFileStatusText = (item) => {
    if (item.uploading) return "上传中";
    if (item.parse_status === "waiting") return "等待上传";
    if (item.parse_status === "success" && Number(item.chunk_count || 0) > 0) {
      return "已解析，可提问";
    }
    if (item.parse_status === "failed") {
      if (item.parse_error && item.parse_error.includes("超时")) return "解析超时";
      return "解析失败";
    }
    if (item.parse_status === "partial") return "部分解析";
    if (item.parse_status === "parsing") return "解析中";
    return "等待解析";
  };

  const selectedFilesBlockReason = useMemo(() => {
    if (selectedFiles.length === 0) return "";
    if (!trimmedMessage) return "请先输入你想基于这些资料提问的问题。";
    if (hasAnyParsing) return "资料还在解析中，请稍后再提问。";
    if (allFilesFailed) return "本轮资料没有可用于 AI 问答的知识索引，但原文件可能已保存到资料库。";
    return "";
  }, [selectedFiles, trimmedMessage, hasAnyParsing, allFilesFailed]);

  useEffect(() => {
    return () => {
      clearAllMaterialPollers();
    };
  }, []);

  useEffect(() => {
    if (!showPlusMenu) return;
    const handleClick = (e) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target)) {
        setShowPlusMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showPlusMenu]);

  const resolvedLearningRecordSubject =
    learningRecordSubjectFilter === "__CURRENT__"
      ? currentChatSubject
      : normalizeSubject(learningRecordSubjectFilter, "");
  const displayedLearningRecordSubject =
    resolvedLearningRecordSubject || currentChatSubject;

  const currentSubjectRecordCount =
    learningRecordStats?.subject_counts?.[displayedLearningRecordSubject] || 0;

  const getQuestionForAssistantMessage = (messageIndex) => {
    for (let index = messageIndex - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "user") {
        return messages[index].content || "";
      }
    }
    return "";
  };

  const openMaterialDetail = async (materialId, nextPage = null) => {
    if (nextPage) {
      setPage(nextPage);
    }
    await loadMaterialDetail(materialId);
  };

  const saveLoginUser = (loginUser) => {
    const goals = Array.isArray(loginUser.learning_goals) ? loginUser.learning_goals : [];
    const normalizedUser = {
      ...loginUser,
      nickname: loginUser.nickname || "",
      grade: loginUser.grade || "",
      major: loginUser.major || "",
      avatar: loginUser.avatar || "avatar_1",
      onboarding_completed: Boolean(loginUser.onboarding_completed),
      learning_goals: goals,
    };

    setUser(normalizedUser);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(normalizedUser));
    setProfileForm({
      nickname: normalizedUser.nickname,
      grade: normalizedUser.grade,
      major: normalizedUser.major,
      avatar: normalizedUser.avatar,
    });
    setLearningGoals(goals);
  };

  const addLearningGoal = () => {
    setLearningGoals((prev) => [
      ...prev,
      { subject: "", target_level: "课堂跟上", note: "" },
    ]);
  };

  const removeLearningGoal = (index) => {
    setLearningGoals((prev) => prev.filter((_, i) => i !== index));
  };

  const updateLearningGoal = (index, field, value) => {
    setLearningGoals((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const saveOnboarding = async () => {
    if (!user?.username) return;

    const filteredGoals = learningGoals.filter(
      (g) => (g.subject || "").trim() && (g.target_level || "").trim()
    );

    if (filteredGoals.length === 0) {
      setTip("请至少添加一个想学习的科目。");
      return;
    }

    setOnboardingSaving(true);
    setTip("");

    try {
      const res = await fetch(
        `${API_BASE}/me/profile?username=${encodeURIComponent(user.username)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nickname: profileForm.nickname,
            grade: profileForm.grade,
            major: profileForm.major,
            learning_goals: filteredGoals,
            onboarding_completed: true,
          }),
        }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "保存学习信息失败"));
        return;
      }

      saveLoginUser(data.profile);
      setPage("home");
      setTip("");
    } catch (error) {
      console.error("Failed to save onboarding:", error);
      setTip("暂时无法保存学习信息。");
    } finally {
      setOnboardingSaving(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
    setMessages([]);
    setChatSessions([]);
    setMaterials([]);
    setSelectedMaterialId(null);
    setSelectedMaterialDetail(null);
    setActiveSessionId(null);
    clearAllMaterialPollers();
    setSelectedFiles([]);
    setMessage("");
    setMaterialSearchQuery("");
    setMaterialSearchTriggered(false);
    setMaterialSearchResults([]);
    setMaterialSearchLoading(false);
    setLearningRecords([]);
    setLearningRecordStats(null);
    setSelectedLearningRecord(null);
    setLearningRecordNote("");
    setLearningRecordTagsInput("");
    setCourseDashboardData(null);
    setCourseDashboardLoading(false);
    setCourseProgressSavingKey("");
    clearCurrentPage();
    setPage("login");
    setAuthMode("login");
  };

  const loadProfile = async (loginUser) => {
    if (!loginUser?.username) return null;

    const res = await fetch(
      `${API_BASE}/me/profile?username=${encodeURIComponent(loginUser.username)}`
    );
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Failed to load profile");
    }

    const profile = data.profile || loginUser;
    saveLoginUser(profile);
    return profile;
  };

  const loadChatHistory = async (loginUser) => {
    if (!loginUser?.username) return;

    try {
      const res = await fetch(
        `${API_BASE}/chat/history?username=${encodeURIComponent(loginUser.username)}`
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "加载聊天记录失败"));
        return;
      }

      setChatSessions(data.sessions || []);
    } catch (error) {
      console.error("Failed to load chat history:", error);
      setTip("无法加载聊天记录，请检查后端服务。");
    }
  };

  const openLibraryReferenceModal = async () => {
    if (!user?.username) return;
    setShowLibraryRefModal(true);
    setLibraryRefLoading(true);
    setLibraryRefSearchQuery("");
    try {
      const query = new URLSearchParams({ username: user.username });
      const normalizedSubject = normalizeSubject(currentChatSubject);
      if (normalizedSubject) query.set("subject", normalizedSubject);
      const res = await fetch(`${API_BASE}/materials?${query.toString()}`);
      const data = await res.json();
      if (!res.ok) {
        setLibraryRefMaterials([]);
        return;
      }
      setLibraryRefMaterials(data.materials || []);
    } catch (error) {
      console.error("Failed to load materials for reference:", error);
      setLibraryRefMaterials([]);
    } finally {
      setLibraryRefLoading(false);
    }
  };

  const toggleLibraryMaterialSelection = (material) => {
    setSelectedLibraryMaterials((prev) => {
      const exists = prev.find((item) => item.id === material.id);
      if (exists) return prev.filter((item) => item.id !== material.id);
      return [...prev, material];
    });
  };

  const removeSelectedLibraryMaterial = (materialId) => {
    setSelectedLibraryMaterials((prev) => prev.filter((item) => item.id !== materialId));
  };

  const canReferenceMaterial = (material) =>
    (material.parse_status === "success" || material.parse_status === "partial") &&
    Number(material.chunk_count || 0) > 0;

  const getUnreferenceableReason = (material) => {
    const status = (material.parse_status || "").trim();
    if (status === "pending" || status === "parsing") return "正在解析，暂不可引用";
    if (status === "failed") return "解析失败，无法用于 AI 问答";
    if (status === "success" || status === "partial") {
      if (Number(material.chunk_count || 0) <= 0) return "未生成知识索引，无法引用";
      return "";
    }
    return "未生成知识索引，无法引用";
  };

  const loadMaterials = async (targetSubject = materialSubjectFilter) => {
    if (!user?.username) return;

    setMaterialsLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      if (targetSubject) {
        query.set("subject", normalizeSubject(targetSubject));
      }

      const res = await fetch(`${API_BASE}/materials?${query.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "加载资料失败"));
        return;
      }

      setMaterials(data.materials || []);
    } catch (error) {
      console.error("Failed to load materials:", error);
      setTip("无法加载资料，请检查后端服务。");
    } finally {
      setMaterialsLoading(false);
    }
  };

  const loadMaterialDetail = async (materialId) => {
    if (!user?.username) return;

    try {
      const res = await fetch(
        `${API_BASE}/materials/${materialId}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "加载资料详情失败"));
        return;
      }

      setSelectedMaterialId(materialId);
      setSelectedMaterialDetail(data.material || null);
    } catch (error) {
      console.error("Failed to load material detail:", error);
      setTip("暂时无法加载资料详情。");
    }
  };

  useEffect(() => {
    if (materialCurrentPage > 1 && materialCurrentPage > currentFilterTotalPages) {
      setMaterialCurrentPage(Math.max(1, currentFilterTotalPages));
    }
  }, [currentFilterTotalPages, materialCurrentPage]);

  const loadLearningRecords = async () => {
    if (!user?.username) return;

    setLearningRecordsLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      if (resolvedLearningRecordSubject) {
        query.set("subject", normalizeSubject(resolvedLearningRecordSubject));
      }
      if (learningRecordTypeFilter) {
        query.set("record_type", learningRecordTypeFilter);
      }
      if (learningRecordReviewFilter) {
        query.set("review_status", learningRecordReviewFilter);
      }

      const res = await fetch(`${API_BASE}/learning-records?${query.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "加载学习记录失败"));
        setLearningRecords([]);
        setSelectedLearningRecord(null);
        setLearningRecordNote("");
        setLearningRecordTagsInput("");
        return;
      }

      const nextRecords = data.records || [];
      const nextSelected = selectedLearningRecord?.id
        ? nextRecords.find((item) => item.id === selectedLearningRecord.id) || null
        : nextRecords[0] || null;
      setLearningRecords(nextRecords);
      setSelectedLearningRecord(nextSelected);
      setLearningRecordNote(nextSelected?.note || "");
      setLearningRecordTagsInput((nextSelected?.tags || []).join("，"));
    } catch (error) {
      console.error("Failed to load learning records:", error);
      setTip("暂时无法加载学习记录。");
      setLearningRecords([]);
      setSelectedLearningRecord(null);
      setLearningRecordNote("");
      setLearningRecordTagsInput("");
    } finally {
      setLearningRecordsLoading(false);
    }
  };

  const loadLearningRecordStats = async () => {
    if (!user?.username) return;

    try {
      const res = await fetch(
        `${API_BASE}/learning-records/stats?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();

      if (!res.ok) {
        setLearningRecordStats(null);
        return;
      }

      setLearningRecordStats(data);
    } catch (error) {
      console.error("Failed to load learning record stats:", error);
      setLearningRecordStats(null);
    }
  };

  const loadCourseDashboard = async (targetCourse = subject) => {
    if (!user?.username) return;

    const normalizedCourse = normalizeSubject(targetCourse);
    setCourseDashboardLoading(true);
    try {
      const query = new URLSearchParams({
        username: user.username,
        course: normalizedCourse,
      });
      const res = await fetch(`${API_BASE}/course-dashboard?${query.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "加载课程工作台失败"));
        setCourseDashboardData(null);
        setCoursePreference(null);
        return;
      }

      setCourseDashboardData(data);
      setCoursePreference(data.preference || null);
    } catch (error) {
      console.error("Failed to load course dashboard:", error);
      setTip("暂时无法加载课程工作台。");
      setCourseDashboardData(null);
      setCoursePreference(null);
    } finally {
      setCourseDashboardLoading(false);
    }
  };

  const parseTagsInput = (value) =>
    String(value || "")
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean);

  const openLearningRecordPage = async () => {
    setPage("records");
    await Promise.all([loadLearningRecords(), loadLearningRecordStats()]);
  };

  const openLearningRecordPageForCourse = async (targetCourse) => {
    const normalizedCourse = normalizeSubject(targetCourse);
    setSubject(normalizedCourse);
    setLearningRecordSubjectFilter(normalizedCourse);
    setPage("records");
  };

  const openMaterialsPageForCourse = async (targetCourse) => {
    const normalizedCourse = normalizeSubject(targetCourse);
    setSubject(normalizedCourse);
    setMaterialSubjectFilter(normalizedCourse);
    setPage("materials");
    await loadMaterials("");
  };

  const openChatPageForCourse = (targetCourse, forceNew = false) => {
    const normalizedCourse = normalizeSubject(targetCourse);
    setSubject(normalizedCourse);
    setPage("chat");

    if (forceNew || (activeSessionId && activeSessionSubject !== normalizedCourse)) {
      setMessages([]);
      setActiveSessionId(null);
      setActiveSessionSubject(normalizedCourse);
      clearAllMaterialPollers();
      setSelectedFiles([]);
      setMessage("");
      setTip("");
      localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      return;
    }

    if (!activeSessionId) {
      setActiveSessionSubject(normalizedCourse);
    }
  };

  const updateLearningRecordInState = (record) => {
    setLearningRecords((prev) => {
      const exists = prev.some((item) => item.id === record.id);
      if (!exists) return [record, ...prev];
      return prev.map((item) => (item.id === record.id ? record : item));
    });

    setSelectedLearningRecord((prev) => (prev?.id === record.id ? record : prev));
    if (selectedLearningRecord?.id === record.id) {
      setLearningRecordNote(record.note || "");
      setLearningRecordTagsInput((record.tags || []).join("，"));
    }
  };

  const selectLearningRecord = (record) => {
    setSelectedLearningRecord(record);
    setLearningRecordNote(record?.note || "");
    setLearningRecordTagsInput((record?.tags || []).join("，"));
  };

  const removeLearningRecordFromState = (recordId) => {
    setLearningRecords((prev) => prev.filter((item) => item.id !== recordId));
    setSelectedLearningRecord((prev) => (prev?.id === recordId ? null : prev));
    if (selectedLearningRecord?.id === recordId) {
      setLearningRecordNote("");
      setLearningRecordTagsInput("");
    }
  };

  const saveLearningRecord = async ({ messageItem, question, recordType }) => {
    if (!user?.username) return;

    const messageKey = String(messageItem.id || messageItem.clientId || "");
    setLearningRecordActionState({
      messageKey,
      recordType,
      loading: true,
    });

    try {
      const res = await fetch(`${API_BASE}/learning-records`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          subject: currentChatSubject,
          session_id: activeSessionId,
          message_id: messageItem.id || null,
          record_type: recordType,
          question: question || "未找到原问题",
          answer: messageItem.content || "",
          references: messageItem.references || [],
          note: "",
          tags: [],
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "保存学习记录失败"));
        return;
      }

      const savedMessage = getLearningRecordSavedMessage(recordType, Boolean(data.duplicated));
      setTip(savedMessage);
      updateLearningRecordInState(data.record);
      setMessages((prev) =>
        prev.map((item) => {
          const currentKey = String(item.id || item.clientId || "");
          if (currentKey !== messageKey) return item;

          const savedTypes = Array.isArray(item.savedRecordTypes) ? item.savedRecordTypes : [];
          if (savedTypes.includes(recordType)) return item;
          return {
            ...item,
            savedRecordTypes: [...savedTypes, recordType],
          };
        })
      );
      if (page === "records") {
        await loadLearningRecords();
      }
      await loadLearningRecordStats();
    } catch (error) {
      console.error("Failed to save learning record:", error);
      setTip("暂时无法保存学习记录。");
    } finally {
      setLearningRecordActionState({
        messageKey: "",
        recordType: "",
        loading: false,
      });
    }
  };

  const updateLearningRecord = async (recordId, payload, successMessage = "学习记录已更新") => {
    if (!user?.username) return;

    setLearningRecordSaving(true);
    try {
      const res = await fetch(
        `${API_BASE}/learning-records/${recordId}?username=${encodeURIComponent(user.username)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "更新学习记录失败"));
        return;
      }

      updateLearningRecordInState(data.record);
      setTip(successMessage);
      await loadLearningRecords();
      await loadLearningRecordStats();
    } catch (error) {
      console.error("Failed to update learning record:", error);
      setTip("暂时无法更新学习记录。");
    } finally {
      setLearningRecordSaving(false);
    }
  };

  const saveLearningRecordNoteAndTags = async () => {
    if (!selectedLearningRecord?.id) return;

    await updateLearningRecord(
      selectedLearningRecord.id,
      {
        note: learningRecordNote,
        tags: parseTagsInput(learningRecordTagsInput),
      },
      "备注与标签已保存"
    );
  };

  const markLearningRecordReviewed = async (record) => {
    if (!record?.id) return;

    await updateLearningRecord(
      record.id,
      { review_status: "reviewed" },
      "已标记为已复习"
    );
  };

  const deleteLearningRecord = async (recordId) => {
    if (!user?.username) return;

    const confirmed = window.confirm("确认删除这条学习记录吗？");
    if (!confirmed) return;

    try {
      const res = await fetch(
        `${API_BASE}/learning-records/${recordId}?username=${encodeURIComponent(user.username)}`,
        {
          method: "DELETE",
        }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "删除学习记录失败"));
        return;
      }

      removeLearningRecordFromState(recordId);
      setTip("学习记录已删除");
      await loadLearningRecords();
      await loadLearningRecordStats();
    } catch (error) {
      console.error("Failed to delete learning record:", error);
      setTip("暂时无法删除学习记录。");
    }
  };

  const searchMaterials = async (keyword, targetSubject = materialSubjectFilter) => {
    if (!user?.username) return;

    const searchKeyword = keyword.trim();
    if (!searchKeyword) {
      setMaterialSearchTriggered(false);
      setMaterialSearchResults([]);
      setMaterialSearchLoading(false);
      return;
    }

    setMaterialSearchTriggered(true);
    setMaterialSearchLoading(true);
    try {
      const query = new URLSearchParams({
        username: user.username,
        q: searchKeyword,
      });
      if (targetSubject) {
        query.set("subject", normalizeSubject(targetSubject));
      }

      const res = await fetch(`${API_BASE}/materials/search?${query.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "搜索资料失败"));
        setMaterialSearchResults([]);
        return;
      }

      setMaterialSearchResults(data.chunks || []);
    } catch (error) {
      console.error("Failed to search materials:", error);
      setTip("暂时无法搜索资料。");
      setMaterialSearchResults([]);
    } finally {
      setMaterialSearchLoading(false);
    }
  };

  const updateCourseProgress = async (knowledgePoint, status) => {
    if (!user?.username) return;

    const normalizedCourse = normalizeSubject(subject);
    const savingKey = `${normalizedCourse}-${knowledgePoint}`;
    setCourseProgressSavingKey(savingKey);
    try {
      const res = await fetch(`${API_BASE}/course-progress`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course: normalizedCourse,
          knowledge_point: knowledgePoint,
          status,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "保存知识点状态失败"));
        return;
      }

      setCourseDashboardData((prev) =>
        prev
          ? {
              ...prev,
              progress: data.progress || prev.progress,
              recent_learning_at: data.item?.updated_at || prev.recent_learning_at,
              stats: {
                ...(prev.stats || {}),
                progress_percent:
                  typeof data.progress_percent === "number"
                    ? data.progress_percent
                    : prev.stats?.progress_percent || 0,
              },
            }
          : prev
      );
    } catch (error) {
      console.error("Failed to update course progress:", error);
      setTip("暂时无法保存知识点状态。");
    } finally {
      setCourseProgressSavingKey("");
    }
  };

  const handleMaterialSearchChange = (value) => {
    setMaterialSearchQuery(value);
    setMaterialSearchTriggered(false);

    if (!value.trim()) {
      setMaterialSearchResults([]);
      setMaterialSearchLoading(false);
    }
  };

  const deleteMaterial = async (materialId) => {
    if (!user?.username) return;

    const confirmed = window.confirm("确认删除这份资料吗？");
    if (!confirmed) return;

    try {
      const res = await fetch(
        `${API_BASE}/materials/${materialId}?username=${encodeURIComponent(
          user.username
        )}`,
        { method: "DELETE" }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "删除资料失败"));
        return;
      }

      setMaterials((prev) => prev.filter((item) => item.id !== materialId));
      setMaterialSearchResults((prev) =>
        prev.filter((item) => item.material_id !== materialId)
      );
      if (selectedMaterialId === materialId) {
        setSelectedMaterialId(null);
        setSelectedMaterialDetail(null);
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.material_id === materialId ? { ...msg, material_id: null } : msg
        )
      );
    } catch (error) {
      console.error("Failed to delete material:", error);
      setTip("暂时无法删除该资料。");
    }
  };

  const downloadMaterial = async (material) => {
    if (!user?.username || !material?.id) return;

    try {
      const downloadUrl =
        material.download_url || `/materials/${material.id}/download`;
      const separator = downloadUrl.includes("?") ? "&" : "?";
      const res = await fetch(
        `${API_BASE}${downloadUrl}${separator}username=${encodeURIComponent(user.username)}`
      );

      if (!res.ok) {
        let detail = "";
        try {
          const data = await res.json();
          detail = data.detail || "";
        } catch {
          detail = "";
        }

        if (res.status === 404) {
          setTip(detail || "原文件不存在，无法下载。");
        } else if (res.status === 403) {
          setTip("没有权限下载该原文件。");
        } else {
          setTip(detail || "下载失败，请稍后重试。");
        }
        return;
      }

      const blob = await res.blob();
      const filename = getFilenameFromDisposition(
        res.headers.get("Content-Disposition"),
        material.file_name || material.original_filename
      );
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setTip("原文件下载已开始。");
    } catch (error) {
      console.error("Failed to download material:", error);
      setTip("下载失败，请稍后重试。");
    }
  };

  const previewMaterial = (material) => {
    if (!user?.username || !material?.id) return;
    if (!material.can_preview || !material.preview_url) {
      setTip("此类型暂不支持网页内预览，请下载原文件查看。");
      return;
    }

    const separator = material.preview_url.includes("?") ? "&" : "?";
    const url = `${API_BASE}${material.preview_url}${separator}username=${encodeURIComponent(user.username)}`;
    const newWindow = window.open(url, "_blank", "noopener,noreferrer");
    if (!newWindow) {
      setTip("浏览器阻止了新窗口，请允许弹窗后重试，或使用下载原文件。");
    }
  };

  const reindexLibrary = async () => {
    if (!user?.username) return;

    setReindexLoading(true);
    setTip("");

    try {
      const res = await fetch(`${API_BASE}/materials/reindex`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          subject: materialSubjectFilter || null,
          force: false,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "重建索引失败"));
        return;
      }

      setTip(
        `索引重建完成：${data.indexed_material_count} 份资料，${data.indexed_chunk_count} 个分块。`
      );
    } catch (error) {
      console.error("Failed to rebuild indexes:", error);
      setTip("暂时无法重建索引。");
    } finally {
      setReindexLoading(false);
    }
  };

  const reparseMaterial = async (materialId) => {
    if (!user?.username) return;
    setTip("");

    try {
      const res = await fetch(
        `${API_BASE}/materials/${materialId}/reparse?username=${encodeURIComponent(user.username)}`,
        { method: "POST" }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "重新解析失败"));
        return;
      }

      // Update the material in state with the new parse status
      setMaterials((prev) =>
        prev.map((item) =>
          item.id === materialId
            ? { ...item, ...data.material, parse_status: data.parse_status, parse_error: data.parse_error, chunk_count: data.chunk_count }
            : item
        )
      );

      if (selectedMaterialId === materialId) {
        setSelectedMaterialDetail((prev) =>
          prev && prev.id === materialId
            ? { ...prev, ...data.material, parse_status: data.parse_status, parse_error: data.parse_error, chunk_count: data.chunk_count }
            : prev
        );
      }

      setTip(
        data.parse_status === "success"
          ? "重新解析完成。"
          : `重新解析失败：${data.parse_error || "未知错误"}`
      );
    } catch (error) {
      console.error("Failed to reparse material:", error);
      setTip("暂时无法重新解析。");
    }
  };

  const openChatSession = async (session) => {
    if (!user?.username) {
      setTip("请先登录。");
      return;
    }

    try {
      const res = await fetch(
        `${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(
          user.username
        )}`
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "打开对话失败"));
        return;
      }

      const sessionSubject = normalizeSubject(
        data.session.subject || data.session.course || subject
      );
      setActiveSessionId(session.id);
      setActiveSessionSubject(sessionSubject);
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(session.id));
      setSubject(sessionSubject);
      setMessages(data.messages || []);
      clearAllMaterialPollers();
      setSelectedFiles([]);
      setMessage("");
      setPage("chat");
    } catch (error) {
      console.error("Failed to open chat session:", error);
      setTip("暂时无法打开该对话。");
    }
  };

  const deleteChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      setTip("请先登录。");
      return;
    }

    const confirmed = window.confirm(`确认删除"${session.title}"吗？`);
    if (!confirmed) return;

    try {
      const res = await fetch(
        `${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(
          user.username
        )}`,
        { method: "DELETE" }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "删除对话失败"));
        return;
      }

      setChatSessions((prev) => prev.filter((item) => item.id !== session.id));

      if (activeSessionId === session.id) {
        setMessages([]);
        setActiveSessionId(null);
        setActiveSessionSubject(normalizeSubject(subject));
        clearAllMaterialPollers();
        setSelectedFiles([]);
        setMessage("");
        localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      }
    } catch (error) {
      console.error("Failed to delete chat session:", error);
      setTip("暂时无法删除该对话。");
    }
  };

  const renameChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      alert("请先登录。");
      return;
    }

    const inputTitle = window.prompt("请输入新标题", session.title || "");
    if (inputTitle === null) return;

    const title = inputTitle.trim();
    if (!title) return;

    try {
      const res = await fetch(
        `${API_BASE}/conversations/${session.id}?username=${encodeURIComponent(
          user.username
        )}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        }
      );
      const data = await res.json();

      if (!res.ok) {
        alert(getDisplayMessage(data.detail, "重命名对话失败"));
        return;
      }

      setChatSessions((prev) =>
        prev.map((item) =>
          item.id === session.id ? { ...item, title: data.title } : item
        )
      );
    } catch (error) {
      console.error("Failed to rename chat session:", error);
      alert("暂时无法重命名该对话。");
    }
  };

  useEffect(() => {
    if (user?.username) {
      const timer = window.setTimeout(() => {
        loadChatHistory(user);
        loadMaterials("");
      }, 0);

      return () => window.clearTimeout(timer);
    }

    return undefined;
  }, [user?.username]);

  useEffect(() => {
    const restoreActiveSession = async () => {
      if (!user?.username) return;

      const savedSessionId = localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
      if (!savedSessionId) return;

      try {
        const res = await fetch(
          `${API_BASE}/chat/sessions/${savedSessionId}?username=${encodeURIComponent(
            user.username
          )}`
        );
        const data = await res.json();

        if (!res.ok) {
          localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
          setActiveSessionId(null);
          setMessages([]);
          return;
        }

        const sessionSubject = normalizeSubject(
          data.session.subject || data.session.course || subject
        );
        setActiveSessionId(data.session.id);
        setActiveSessionSubject(sessionSubject);
        setSubject(sessionSubject);
        setMessages(data.messages || []);
      } catch (error) {
        console.error("Failed to restore active chat session:", error);
      }
    };

    restoreActiveSession();
  }, [user?.username]);

  useEffect(() => {
    const checkLoginStatus = async () => {
      const savedUser = getSavedUser();
      if (!savedUser?.username) return;

      try {
        const res = await fetch(`${API_BASE}/me`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: savedUser.username }),
        });
        const data = await res.json();

        if (!res.ok) {
          logout();
          setTip(getDisplayMessage(data.detail, "登录已过期，请重新登录。"));
          return;
        }

        const checkedUser = data.user || savedUser;
        saveLoginUser(checkedUser);
        await loadProfile(checkedUser);
        const savedPage = (() => {
          try { return localStorage.getItem(CURRENT_PAGE_KEY); } catch { return null; }
        })();
        if (!checkedUser.onboarding_completed) {
          setPage("onboarding");
        } else if (savedPage && VALID_PAGES.has(savedPage)) {
          setPage(savedPage);
        }
      } catch (error) {
        console.error("Failed to verify login status:", error);
      }
    };

    checkLoginStatus();
  }, []);

  useEffect(() => {
    if (page === "records" && user?.username) {
      const timer = window.setTimeout(() => {
        loadLearningRecords();
        loadLearningRecordStats();
      }, 0);

      return () => window.clearTimeout(timer);
    }

    return undefined;
  }, [
    page,
    user?.username,
    learningRecordTypeFilter,
    learningRecordSubjectFilter,
    learningRecordReviewFilter,
    currentChatSubject,
  ]);

  useEffect(() => {
    if (page === "dashboard" && user?.username) {
      const timer = window.setTimeout(() => {
        loadCourseDashboard(subject);
      }, 0);

      return () => window.clearTimeout(timer);
    }

    return undefined;
  }, [page, user?.username, subject]);

  useEffect(() => {
    if (page === "workspaceMaterials" && user?.username) {
      const normalizedSubject = normalizeSubject(subject);
      setMaterialSubjectFilter(normalizedSubject);
      setMaterialCurrentPage(1);
      loadMaterials(normalizedSubject);
    }
  }, [page, user?.username, subject]);

  const handleRegister = async () => {
    setTip("");

    if (!username.trim() || !password.trim()) {
      setTip("请输入用户名和密码。");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "注册失败"));
        return;
      }

      const loginUser = data.profile || data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      setPage("onboarding");
      setTip("");
    } catch (error) {
      console.error("Register failed:", error);
      setTip("无法连接后端服务。");
    }
  };

  const handleLogin = async () => {
    setTip("");

    if (!username.trim() || !password.trim()) {
      setTip("请输入用户名和密码。");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "登录失败"));
        return;
      }

      const loginUser = data.profile || data.user || { username: data.username || username };
      const isAdmin = loginUser.is_admin || loginUser.plan === "admin" || loginUser.role === "admin"
        || ["super_admin", "operator", "auditor"].includes(loginUser.admin_role);
      saveLoginUser(loginUser);
      await loadProfile(loginUser);
      if (isAdmin) {
        setPage("adminUsageCenter");
      } else if (loginUser.onboarding_completed) {
        setPage("home");
      } else {
        setPage("onboarding");
      }
      setTip("");
    } catch (error) {
      console.error("Login failed:", error);
      setTip("无法连接后端服务。");
    }
  };

  // Email login countdown
  useEffect(() => {
    if (emailLoginCountdown <= 0) return;
    const t = setTimeout(() => setEmailLoginCountdown(c => c-1), 1000);
    return () => clearTimeout(t);
  }, [emailLoginCountdown]);

  const handleEmailSendCode = async () => {
    setTip(""); const e = emailLoginForm.email.trim();
    if (!e || !e.includes("@")) { setTip("请输入有效的邮箱地址"); return; }
    setEmailLoginSending(true);
    try {
      const res = await fetch(`${API_BASE}/auth/email-login/send-code`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:e}),
      });
      const data = await res.json();
      if (!res.ok) { setTip(data.detail||"发送失败"); setEmailLoginSending(false); return; }
      setEmailLoginCountdown(60);
    } catch { setTip("无法连接后端服务。"); }
    finally { setEmailLoginSending(false); }
  };

  const handleEmailLogin = async () => {
    setTip(""); const {email, code} = emailLoginForm;
    if (!email.trim() || !code.trim()) { setTip("请输入邮箱和验证码"); return; }
    setEmailLoginLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/email-login`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:email.trim(), code:code.trim()}),
      });
      const data = await res.json();
      if (!res.ok) { setTip(data.detail||"登录失败"); setEmailLoginLoading(false); return; }
      const loginUser = data.profile || data.user || {};
      saveLoginUser(loginUser);
      await loadProfile(loginUser);
      const isAdmin = loginUser.is_admin || loginUser.plan === "admin" || loginUser.role === "admin"
        || ["super_admin","operator","auditor"].includes(loginUser.admin_role);
      if (isAdmin) setPage("adminUsageCenter");
      else if (loginUser.onboarding_completed) setPage("home");
      else setPage("onboarding");
      setTip("");
    } catch { setTip("无法连接后端服务。"); }
    finally { setEmailLoginLoading(false); }
  };

  const saveProfile = async () => {
    if (!user?.username) {
      logout();
      return;
    }

    setProfileSaving(true);
    setTip("");

    try {
      const res = await fetch(
        `${API_BASE}/me/profile?username=${encodeURIComponent(user.username)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profileForm),
        }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "保存个人资料失败"));
        return;
      }

      saveLoginUser(data.profile);
      setTip("个人资料已保存。");
    } catch (error) {
      console.error("Failed to save profile:", error);
      setTip("暂时无法保存个人资料。");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleAvatarUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !user?.username) return;

    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      setTip("头像仅支持 JPG、PNG、WebP 或 GIF 格式");
      return;
    }
    if (file.size > 3 * 1024 * 1024) {
      setTip("头像文件不能超过 3MB");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("username", user.username);

    try {
      const res = await fetch(`${API_BASE}/me/avatar`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "头像上传失败"));
        return;
      }

      if (data.profile) {
        saveLoginUser(data.profile);
      }
      setTip("头像已更新");
    } catch (error) {
      console.error("Failed to upload avatar:", error);
      setTip("头像上传失败，请稍后重试。");
    }
  };

  const pollMaterialStatus = (localId, materialId) => {
    clearMaterialPoller(localId);
    materialPollCountRef.current[localId] = 0;

    const refreshStatus = async () => {
      const pollCount = (materialPollCountRef.current[localId] || 0) + 1;
      materialPollCountRef.current[localId] = pollCount;

      if (pollCount > MAX_POLL_COUNT) {
        clearMaterialPoller(localId);
        setSelectedFiles((prev) =>
          prev.map((item) =>
            item.localId === localId
              ? {
                  ...item,
                  parse_status: "failed",
                  parse_error: "解析超时，请稍后到资料库查看，或重新上传。",
                  uploading: false,
                }
              : item
          )
        );
        return;
      }

      try {
        const res = await fetch(
          `${API_BASE}/materials/${materialId}/status?username=${encodeURIComponent(user.username)}`
        );
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Failed to load material status");
        }

        setSelectedFiles((prev) =>
          prev.map((item) =>
            item.localId === localId
              ? {
                  ...item,
                  parse_status: data.parse_status,
                  parse_progress: data.parse_progress ?? item.parse_progress,
                  chunk_count: data.chunk_count ?? item.chunk_count,
                  parse_error: data.parse_error || "",
                  uploading: false,
                }
              : item
          )
        );

        if (["success", "failed", "partial"].includes(data.parse_status)) {
          clearMaterialPoller(localId);
          if (data.parse_status === "success" && Number(data.chunk_count || 0) > 0) {
            await loadMaterials("");
          }
        }
      } catch (error) {
        console.error("Failed to poll material status:", error);
      }
    };

    refreshStatus();
    materialStatusPollersRef.current[localId] = window.setInterval(refreshStatus, 2000);
  };

  const uploadSelectedFile = async (file, localId, fileSubject) => {
    if (!guardFeature("feature_material_upload_enabled", "资料上传功能暂时维护中，请稍后再试")) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("username", user.username);
    const uploadSubject = fileSubject || normalizeSubject(currentChatSubject);
    formData.append("subject", normalizeSubject(uploadSubject));

    try {
      const res = await fetch(`${API_BASE}/materials/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${user.username}`,
        },
        body: formData,
      });

      const text = await res.text();
      let data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        data = {};
      }

      if (!res.ok) {
        throw new Error(getUploadErrorMessage(res.status, data));
      }

      const uploaded = normalizeUploadedMaterial(data, file, localId);
      setSelectedFiles((prev) =>
        prev.map((item) => (item.localId === localId ? { ...item, ...uploaded, uploading: false } : item))
      );

      if (["pending", "parsing"].includes(uploaded.parse_status)) {
        pollMaterialStatus(localId, uploaded.material_id);
      }

      // Reload materials list so the new record appears in the library page.
      // Use the upload subject (materials page) if given, otherwise reload all.
      const reloadSubject = fileSubject ? normalizeSubject(fileSubject) : "";
      await loadMaterials(reloadSubject);
    } catch (error) {
      console.error("Failed to upload selected file:", error);
      setSelectedFiles((prev) =>
        prev.map((item) =>
          item.localId === localId
            ? {
                ...item,
                uploading: false,
                parse_status: "failed",
                parse_error: error.message || "上传失败",
              }
            : item
        )
      );
      // Even when upload fails client-side, refresh the materials list
      // in case the backend created the record before the error.
      const reloadSubject = fileSubject ? normalizeSubject(fileSubject) : "";
      await loadMaterials(reloadSubject);
    }
  };

  const handleFileChange = (event, explicitSubject = null) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";

    if (files.length === 0) return;

    if (!user?.username) {
      setTip("请先登录。");
      logout();
      return;
    }

    const skippedReasons = [];
    const fileEntries = [];

    for (const file of files) {
      if (!isAllowedFile(file)) {
        skippedReasons.push(`${file.name}（文件类型不支持）`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        skippedReasons.push(`${file.name}（超过 20MB）`);
        continue;
      }
      const localId = `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      fileEntries.push({
        localId,
        file,
        entry: {
          localId,
          original_filename: file.name,
          file_type: file.type,
          file_size: file.size,
          parse_status: "waiting",
          parse_progress: 0,
          chunk_count: 0,
          uploading: false,
        },
      });
    }

    if (skippedReasons.length > 0) {
      setTip(`以下文件被跳过：${skippedReasons.join("、")}`);
    } else {
      setTip("");
    }

    if (fileEntries.length === 0) return;

    setSelectedFiles((prev) => [...prev, ...fileEntries.map((e) => e.entry)]);

    for (const { file, entry } of fileEntries) {
      setSelectedFiles((prev) =>
        prev.map((item) =>
          item.localId === entry.localId ? { ...item, uploading: true, parse_status: "pending" } : item
        )
      );
      const upSubject = explicitSubject
        ? normalizeSubject(explicitSubject)
        : null;
      uploadSelectedFile(file, entry.localId, upSubject);
    }
  };

  const removeSelectedFile = (localId) => {
    clearMaterialPoller(localId);
    setSelectedFiles((prev) => prev.filter((item) => item.localId !== localId));
  };

  const getUploadErrorMessage = (status, data) => {
    if (status === 400) {
      return getDisplayMessage(data.detail, "上传被拒绝，请检查文件类型、大小和学科。");
    }
    if (status === 401) return "登录已过期，请重新登录。";
    if (status === 413) return "文件过大，请上传 10MB 以内的文件。";
    if (status === 422) return "上传参数无效，请重试。";
    if (status === 500) return getDisplayMessage(data.detail, "后端暂时无法处理该文件。");
    if (status === 502) return "网关错误，后端服务可能不可用。";
    return getDisplayMessage(data.detail, `上传失败，HTTP 状态码：${status}`);
  };

  const appendAssistantError = (content) => {
    setMessages((prev) => [
      ...prev,
      createLocalMessage({ role: "assistant", content, animateTyping: true }),
    ]);
  };

  const finishAssistantTyping = (clientId) => {
    setMessages((prev) =>
      prev.map((item) =>
        item.clientId === clientId ? { ...item, animateTyping: false } : item
      )
    );
  };

  const refreshChatSessionState = (session) => {
    if (!session) return;

    setActiveSessionId(session.id);
    setActiveSessionSubject(session.subject || session.course || subject);
    localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(session.id));

    setChatSessions((prev) => {
      const exists = prev.some((item) => item.id === session.id);
      if (exists) {
        return prev.map((item) => (item.id === session.id ? session : item));
      }
      return [session, ...prev];
    });
  };

  function buildHiddenLearningInstruction(ctx) {
    if (!ctx || ctx.type !== "knowledge_point") return "";
    const goalLabel = ({ overview: "大概了解", systematic: "系统学习", project: "项目实践", exam: "期中/期末速成" })[ctx.goal] || "系统学习";
    const diffLabel = ({ intro: "入门", standard: "标准", advanced: "提高", challenge: "挑战" })[ctx.difficulty] || "标准";
    const depthLabel = ({ brief: "粗略", standard: "标准", detailed: "详细" })[ctx.depth] || "标准";
    const dailyTimeLabel = ctx.dailyTime ? `${ctx.dailyTime} 分钟` : "30 分钟";
    const examDaysLabel = ({ "3": "3 天内", "7": "1 周内", "14": "2 周内", "30": "1 个月内" })[ctx.examDays] || "";
    const routeLabel = ctx.routeSource === "platform" ? "平台推荐路线" : "我的资料路线";

    return [
      "你是学生的学习导师。以下是学生当前的隐藏学习配置。不要在回答中机械复述这些配置，直接据此调整回答方式和深度——",
      `课程：${ctx.courseName}`,
      `当前学习知识点：${ctx.knowledgePointTitle}`,
      `学习目标：${goalLabel}`,
      `学习难度：${diffLabel}`,
      `知识点细度：${depthLabel}`,
      `每日学习时间：${dailyTimeLabel}`,
      `路线来源：${routeLabel}`,
      ctx.examMode ? `考试速成：是，距离考试${examDaysLabel}` : "",
      "",
      "回答要求：",
      goalLabel === "大概了解" ? "- 回答要简短，先讲核心概念，少讲底层细节，少给复杂代码，多用生活类比" : "",
      goalLabel === "系统学习" ? "- 回答结构完整，包含定义、原理、例子、易错点和基础练习" : "",
      goalLabel === "项目实践" ? "- 回答偏实际应用和代码场景，多讲工程使用方式、调试方法和实践建议" : "",
      goalLabel === "期中/期末速成" ? "- 回答偏考试导向，标明考点频率，给出常见题型、速记版总结和复习优先级" : "",
      diffLabel === "入门" ? "- 使用简单语言，少用专业术语，多用类比" : "",
      diffLabel === "挑战" ? "- 可以深入讲解底层原理、边界情况和复杂例子" : "",
      depthLabel === "粗略" ? "- 控制篇幅，只讲核心要点" : "",
      depthLabel === "详细" ? "- 充分展开，补充步骤、例子、易错点和练习题" : "",
      dailyTimeLabel === "15 分钟" ? "- 学习建议要短平快，适合碎片化学习" : "",
      dailyTimeLabel === "90 分钟" ? "- 可以给出更完整的学习任务和练习计划" : "",
      ctx.examMode && examDaysLabel ? `- 考试迫近（${examDaysLabel}），优先高频考点和速记内容` : "",
      "",
      `不要在回答开头说"根据你的学习目标"，直接自然地给出回答。`,
    ].filter(Boolean).join("\n");
  }

  const sendTextMessage = async (overrideText) => {
    // Feature gate: AI chat
    if (!guardFeature("feature_ai_chat_enabled", "AI 问答功能暂时维护中，请稍后再试")) return;

    // Safely extract current message: when overrideText is a valid string use it;
    // otherwise fall back to trimmedMessage (the current input value).
    const currentMessage = (typeof overrideText === "string" && overrideText.trim()) || trimmedMessage;

    if (!currentMessage) {
      setTip("请输入问题后再发送。");
      return;
    }

    // Build hidden learning instruction from pendingAIContext (not saved to history)
    const hiddenInstruction = buildHiddenLearningInstruction(pendingAIContext);

    const attachedFiles = validAttachedFiles.map((item) => ({
      material_id: item.material_id,
      original_filename: item.original_filename,
      file_type: item.file_type,
      parse_status: item.parse_status,
      chunk_count: item.chunk_count,
    }));
    // Chat bubble shows clean user message only
    setMessages((prev) => [
      ...prev,
      createLocalMessage({ role: "user", content: currentMessage, attachments: attachedFiles }),
    ]);
    setLoading(true);
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          hidden_instruction: hiddenInstruction,
          subject: normalizeSubject(currentChatSubject),
          mastery_level: coursePreference?.mastery_level || "",
          learning_goal: coursePreference?.learning_goal || "",
          grade: user.grade || "",
          major: user.major || "",
          username: user.username,
          session_id: activeSessionId,
          material_ids: Array.from(
            new Set([
              ...attachedFiles.map((item) => item.material_id),
              ...selectedLibraryMaterials.map((item) => item.id),
            ])
          ),
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (res.status === 401) {
          logout();
          setTip(getDisplayMessage(data.detail, "登录已过期，请重新登录。"));
        }
        appendAssistantError(getDisplayMessage(data.detail, "AI 回复失败。"));
        return;
      }

      setMessages((prev) => [
        ...prev,
        createLocalMessage({
          id: data.assistant_message_id || undefined,
          role: "assistant",
          content: data.answer,
          references: data.references || [],
          rag_sources: data.rag_sources || [],
          has_bound_materials: attachedFiles.length > 0,
          animateTyping: true,
        }),
      ]);
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
      clearAllMaterialPollers();
      setSelectedFiles([]);
      setSelectedLibraryMaterials([]);
    } catch (error) {
      console.error("Failed to send message:", error);
      appendAssistantError("无法连接后端服务。");
    } finally {
      setLoading(false);
    }
  };

  const editUserMessage = async (messageClientId, newContent) => {
    if (!user?.username) {
      logout();
      return;
    }
    if (!newContent || !String(newContent).trim()) return;

    setTip("");

    let foundIndex = -1;
    let foundMsg = null;

    setMessages((prev) => {
      const idx = prev.findIndex(
        (m) => (m && (m.id || m.clientId)) === messageClientId
      );
      if (idx === -1 || (prev[idx] && prev[idx].role) !== "user") return prev;

      foundIndex = idx;
      foundMsg = prev[idx];

      // Collect assistant messages that follow this user message
      const followingAssistants = [];
      for (let i = idx + 1; i < prev.length && prev[i] && prev[i].role === "assistant"; i++) {
        followingAssistants.push({ ...prev[i] });
      }

      // Build or migrate versions with userContent + assistantMessages
      const oldVersions = Array.isArray(foundMsg.versions) && foundMsg.versions.length > 0
        ? [...foundMsg.versions]
        : [];
      const currentIdx = foundMsg.currentVersionIndex ?? (oldVersions.length > 0 ? oldVersions.length - 1 : 0);

      let existingVersions;
      if (oldVersions.length === 0 || oldVersions[0].userContent == null) {
        existingVersions = oldVersions.length > 0
          ? oldVersions.map((v) => ({
              userContent: v.content || "",
              assistantMessages: [],
              createdAt: v.created_at || foundMsg.created_at || foundMsg.timestamp || new Date().toISOString(),
            }))
          : [{
              userContent: foundMsg.content || "",
              assistantMessages: [],
              createdAt: foundMsg.created_at || foundMsg.timestamp || new Date().toISOString(),
            }];
      } else {
        existingVersions = oldVersions;
      }

      // Save current assistant messages into the current version
      if (existingVersions[currentIdx]) {
        existingVersions[currentIdx] = {
          ...existingVersions[currentIdx],
          assistantMessages: followingAssistants,
        };
      }

      // Create new version
      existingVersions.push({
        userContent: newContent.trim(),
        assistantMessages: [],
        createdAt: new Date().toISOString(),
      });

      const editedMsg = {
        ...foundMsg,
        content: newContent.trim(),
        versions: existingVersions,
        currentVersionIndex: existingVersions.length - 1,
        edited: true,
      };

      return [...prev.slice(0, idx), editedMsg];
    });

    if (!foundMsg || foundIndex === -1) return;

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: newContent.trim(),
          subject: normalizeSubject(currentChatSubject),
          mastery_level: coursePreference?.mastery_level || "",
          learning_goal: coursePreference?.learning_goal || "",
          grade: user.grade || "",
          major: user.major || "",
          username: user.username,
          session_id: activeSessionId,
          material_ids: [],
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (res.status === 401) {
          logout();
          setTip(getDisplayMessage(data.detail, "登录已过期，请重新登录。"));
        }
        appendAssistantError(getDisplayMessage(data.detail, "AI 回复失败。"));
        return;
      }

      const newAssistant = createLocalMessage({
        id: data.assistant_message_id || undefined,
        role: "assistant",
        content: data.answer,
        references: data.references || [],
        rag_sources: data.rag_sources || [],
        animateTyping: true,
      });

      setMessages((prev) => {
        const userIdx = prev.findIndex(
          (m) => (m && (m.id || m.clientId)) === messageClientId
        );
        if (userIdx === -1) return [...prev, newAssistant];

        const userMsg = prev[userIdx];
        const versions = Array.isArray(userMsg.versions) ? [...userMsg.versions] : [];
        const cur = userMsg.currentVersionIndex ?? (versions.length - 1);

        if (versions[cur]) {
          versions[cur] = {
            ...versions[cur],
            assistantMessages: [newAssistant],
          };
        }

        return [
          ...prev.slice(0, userIdx),
          { ...userMsg, versions },
          newAssistant,
        ];
      });
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
    } catch (error) {
      console.error("Failed to edit message:", error);
      appendAssistantError("无法连接后端服务。");
    } finally {
      setLoading(false);
    }
  };

  const switchMessageVersion = (messageClientId, newVersionIndex) => {
    setMessages((prev) => {
      const userIdx = prev.findIndex(
        (m) => (m && (m.id || m.clientId)) === messageClientId
      );
      if (userIdx === -1 || (prev[userIdx] && prev[userIdx].role) !== "user") return prev;

      const userMsg = prev[userIdx];
      const versions = Array.isArray(userMsg.versions) ? userMsg.versions : [];
      if (versions.length <= 1) return prev;
      if (newVersionIndex < 0 || newVersionIndex >= versions.length) return prev;

      const oldIndex = userMsg.currentVersionIndex ?? 0;
      if (oldIndex === newVersionIndex) return prev;

      // Collect current assistant messages
      const currentAssistants = [];
      for (let i = userIdx + 1; i < prev.length && prev[i] && prev[i].role === "assistant"; i++) {
        currentAssistants.push({ ...prev[i] });
      }

      // Save into old version
      const updatedVersions = versions.map((v, i) => {
        if (i === oldIndex) {
          return { ...v, assistantMessages: currentAssistants };
        }
        return v;
      });

      // Restore from target version
      const targetVersion = updatedVersions[newVersionIndex];
      const restored = (Array.isArray(targetVersion.assistantMessages) ? targetVersion.assistantMessages : []).map((a) => ({
        ...a,
        animateTyping: false,
      }));

      const updatedUser = {
        ...userMsg,
        content: targetVersion.userContent || targetVersion.content || userMsg.content,
        versions: updatedVersions,
        currentVersionIndex: newVersionIndex,
      };

      return [...prev.slice(0, userIdx), updatedUser, ...restored];
    });
  };


  const sendMessage = async (overrideText) => {
    const hasOverride = typeof overrideText === "string" && overrideText.trim().length > 0;

    if (!user?.username) {
      setTip("请先登录。");
      logout();
      return;
    }

    if (!hasOverride && !canSendMessage) {
      setTip(selectedFilesBlockReason || "请先输入问题后再发送。");
      return;
    }

    if (loading) {
      setTip("正在处理上一个问题，请稍后...");
      return;
    }

    setTip("");

    // Only pass overrideText when it is a real string (from KP context clicks).
    // When called from button onClick/Enter key, the first argument may be a
    // SyntheticEvent or undefined — forward undefined so sendTextMessage falls
    // back to the current trimmedMessage.
    await sendTextMessage(hasOverride ? overrideText.trim() : undefined);
  };

  const addMessageToLibrary = async (messageItem, selectedSubject) => {
    if (!user?.username || !messageItem?.id) return;

    setAddToLibraryState((prev) => ({
      ...prev,
      messageId: messageItem.id,
      subject: normalizeSubject(selectedSubject),
      loading: true,
    }));

    try {
      const res = await fetch(`${API_BASE}/materials/add-from-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          message_id: messageItem.id,
          subject: normalizeSubject(selectedSubject),
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setTip(getDisplayMessage(data.detail, "添加附件到资料库失败"));
        return;
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageItem.id ? { ...msg, material_id: data.material_id } : msg
        )
      );

      if (!materialSubjectFilter || materialSubjectFilter === selectedSubject) {
        await loadMaterials("");
      }
    } catch (error) {
      console.error("Failed to add attachment to library:", error);
      setTip("暂时无法添加该附件。");
    } finally {
      setAddToLibraryState((prev) => ({
        ...prev,
        messageId: null,
        loading: false,
      }));
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setActiveSessionId(null);
    setActiveSessionSubject(normalizeSubject(subject));
    clearAllMaterialPollers();
    setSelectedFiles([]);
    setMessage("");
    setTip("");
    setPage("chat");
    localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  };

  const loadChatSessions = () => {
    if (user?.username) {
      loadChatHistory(user);
    }
  };

  // Handle search navigation to chat — auto-open conversation
  useEffect(() => {
    if (!searchNavigate || searchNavigate.page !== "chat" || !searchNavigate.conversationId) return;
    // If currently on chat page, open the conversation directly
    if (page === "chat") {
      const sessionId = searchNavigate.conversationId;
      // Construct a mock session object to pass to openChatSession
      const mockSession = { id: sessionId };
      openChatSession(mockSession);
      setSearchNavigate(null);
    } else {
      // Navigate to chat page first; the conversation will be opened on entry
      if (searchNavigate.courseId) setSubject(searchNavigate.courseId);
      setPage("chat");
      // Delay to let page mount, then open conversation
      const tid = setTimeout(() => {
        const sessionId = searchNavigate.conversationId;
        openChatSession({ id: sessionId });
        setSearchNavigate(null);
      }, 400);
      return () => clearTimeout(tid);
    }
  }, [searchNavigate, page]);

  if (isSharedReportPath) {
    return (
      <Suspense fallback={<div className="shared-report-shell"><div className="shared-report-card"><div className="shared-report-loading">加载中...</div></div></div>}>
        <SharedReportPage />
      </Suspense>
    );
  }

  // Admin login page — redirect to unified login
  if (page === "adminLogin") {
    setTip("管理员请使用统一登录入口登录。");
    setPage("login");
    return null;
  }

  if (!user) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-hero">
            <div className="auth-badge">AI 学习平台</div>
            <h1 className="auth-title">让学习更智能，让成长看得见</h1>
            <p className="auth-subtitle">AI 驱动的学习平台，陪伴你的每一步进步</p>

            <div className="auth-demo-card">
              <div className="auth-demo-header">
                <span className="auth-demo-dot" />
                <span>学习概览</span>
              </div>
              <div className="auth-demo-stats">
                <div className="auth-demo-stat"><span className="auth-demo-stat-val">60</span><span className="auth-demo-stat-lbl">分钟学习时长</span></div>
                <div className="auth-demo-stat"><span className="auth-demo-stat-val">78%</span><span className="auth-demo-stat-lbl">当前掌握度</span></div>
              </div>
              <div className="auth-demo-bar"><div className="auth-demo-bar-fill" style={{width:"78%"}} /></div>
              <p className="auth-demo-hint">知识图谱 · 推荐学习路径</p>
            </div>

            <div className="auth-capability-tags">
              <span className="auth-cap-tag">🎯 个性化学习路径</span>
              <span className="auth-cap-tag">📊 学习数据分析</span>
              <span className="auth-cap-tag">💬 智能答疑助手</span>
            </div>
          </div>

          <div className="auth-panel">
            {authMode === "login" ? (<>
              <h2 className="auth-panel-title">欢迎回来</h2>
              <p className="auth-panel-sub">登录后继续你的高效学习之旅</p>

              <div className="auth-subtabs">
                <button className={`auth-subtab ${loginTab==="password"?"auth-subtab--active":""}`} onClick={()=>{setLoginTab("password");setTip("");}}>账号登录</button>
                <button className={`auth-subtab ${loginTab==="email"?"auth-subtab--active":""}`} onClick={()=>{setLoginTab("email");setTip("");}}>验证码登录</button>
              </div>

              <div className="auth-form">
                {loginTab === "password" && (<>
                  <input className="auth-input" placeholder="用户名" value={username} onChange={e=>setUsername(e.target.value)} />
                  <input className="auth-input" placeholder="密码" type="password" value={password} onChange={e=>setPassword(e.target.value)} />
                  {tip && <p className="auth-tip">{tip}</p>}
                  <button className="auth-submit" onClick={handleLogin}>立即登录</button>
                </>)}

                {loginTab === "email" && (<>
                  <input className="auth-input" placeholder="邮箱地址" type="email" value={emailLoginForm.email} onChange={e=>setEmailLoginForm(p=>({...p,email:e.target.value}))} />
                  <div className="auth-code-row">
                    <input className="auth-input auth-code-input" placeholder="验证码" value={emailLoginForm.code} onChange={e=>setEmailLoginForm(p=>({...p,code:e.target.value}))} maxLength={6} />
                    <button className="auth-send-btn" onClick={handleEmailSendCode} disabled={emailLoginSending||emailLoginCountdown>0}>
                      {emailLoginCountdown>0?`${emailLoginCountdown}s 后重试`:"发送验证码"}
                    </button>
                  </div>
                  {tip && <p className="auth-tip">{tip}</p>}
                  <button className="auth-submit" onClick={handleEmailLogin} disabled={emailLoginLoading}>{emailLoginLoading?"登录中...":"立即登录"}</button>
                </>)}

                <div className="auth-bottom-links">
                  <button className="auth-link" onClick={()=>{setAuthMode("register");setTip("");}}>注册账号</button>
                </div>
              </div>
            </>) : (<>
              <h2 className="auth-panel-title">创建你的学习账号</h2>
              <p className="auth-panel-sub">注册后完善学习方向，为你定制专属学习工作台</p>

              <div className="auth-form">
                <input className="auth-input" placeholder="用户名" value={username} onChange={e=>setUsername(e.target.value)} />
                <input className="auth-input" placeholder="密码" type="password" value={password} onChange={e=>setPassword(e.target.value)} />
                {tip && <p className="auth-tip">{tip}</p>}
                <button className="auth-submit" onClick={handleRegister}>注册并继续</button>
                <div className="auth-bottom-links">
                  <button className="auth-link" onClick={()=>{setAuthMode("login");setTip("");}}>← 返回登录</button>
                </div>
              </div>
            </>)}
          </div>
        </div>

        <div className="auth-footer">
          <span>© 2026 AI 学习助手 · 南京大学技术支持</span>
          <span>用户协议</span>
          <span>隐私政策</span>
        </div>
      </div>
    );
  }

  const getUserAvatarElement = (sizeClass = "avatar-circle") => {
    const avatarVal = (user?.avatar || "").trim();
    const avatarUrl = user?.avatar_url || "";
    if (avatarUrl && avatarUrl.startsWith("/me/avatar/")) {
      return (
        <img
          className={sizeClass}
          src={`${API_BASE}${avatarUrl}?username=${encodeURIComponent(user?.username || "")}`}
          alt="头像"
        />
      );
    }
    const avatarObj = AVATARS.find((a) => a.id === avatarVal) || AVATARS[0];
    return (
      <div className={sizeClass} style={{ background: avatarObj.background }}>
        {(user?.nickname || user?.username || "?").charAt(0)}
      </div>
    );
  };

  if (page === "onboarding") {
    return (
      <div className="onboarding-page">
        <div className="onboarding-card">
          <h1 className="onboarding-title">完善你的学习方向</h1>
          <p className="onboarding-subtitle">
            我们会根据你的专业和科目目标，为你定制专属的学习工作台。
          </p>

          <div className="onboarding-form-grid">
            <div>
              <label className="field-label">专业</label>
              <input
                className="field"
                placeholder="例如：软件工程"
                value={profileForm.major}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, major: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="field-label">年级</label>
              <input
                className="field"
                placeholder="例如：大二"
                value={profileForm.grade}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, grade: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="goals-section">
            <div className="goals-header">
              <div>
                <label className="field-label">想学习的科目</label>
                <span className="goals-header-hint">设定你想掌握的科目和程度</span>
              </div>
              <button className="tiny-button" type="button" onClick={addLearningGoal}>
                + 添加科目
              </button>
            </div>

            {learningGoals.length === 0 && (
              <div className="goal-empty-card" onClick={addLearningGoal}>
                <div className="goal-empty-icon">+</div>
                <div className="goal-empty-text">点击这里添加你想学习的第一个科目</div>
                <div className="goal-empty-hint">例如：高等数学、大学英语、程序设计</div>
              </div>
            )}

            {learningGoals.map((goal, index) => (
              <div key={index} className="goal-card">
                <div className="goal-card-header">
                  <span className="goal-card-number">科目 {index + 1}</span>
                  <button
                    className="goal-remove-btn"
                    type="button"
                    onClick={() => removeLearningGoal(index)}
                  >
                    移除
                  </button>
                </div>
                <select
                  className="field"
                  value={goal.subject}
                  onChange={(e) => updateLearningGoal(index, "subject", e.target.value)}
                >
                  <option value="">选择科目</option>
                  {COURSE_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {getSubjectLabel(item)}
                    </option>
                  ))}
                </select>

                <label className="field-label">想掌握到的程度</label>
                <select
                  className="field"
                  value={goal.target_level}
                  onChange={(e) => updateLearningGoal(index, "target_level", e.target.value)}
                >
                  {TARGET_LEVEL_OPTIONS.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>

                <label className="field-label">备注（可选）</label>
                <input
                  className="field"
                  placeholder="例如：希望能独立写后端"
                  value={goal.note}
                  onChange={(e) => updateLearningGoal(index, "note", e.target.value)}
                />
              </div>
            ))}
          </div>

          {tip && <p className="tip-text">{tip}</p>}

          <div className="onboarding-submit-area">
            <p className="onboarding-submit-hint">后续可以在个人主页随时修改</p>
            <button className="onboarding-primary-btn" onClick={saveOnboarding} disabled={onboardingSaving}>
              {onboardingSaving ? "保存中..." : "进入我的学习主页"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const wrapPage = (children) => {
    const visibleAnnouncements = userAnnouncements.filter((a) => !dismissedAnnounceIds.includes(a.id));
    return (
    <AppLayout
      activePage={page}
      onNavigate={setPage}
      isAdmin={!!user?.is_admin}
      showMembershipAd={shouldShowMembershipAd(user)}
      onLogout={logout}
    >
      {visibleAnnouncements.length > 0 && (
        <div className="announce-banner-area">
          {visibleAnnouncements.map((a) => {
            const bg = a.type === "danger" ? "#fef2f2" : a.type === "warning" ? "#fffbeb" : a.type === "success" ? "#f0fdf4" : "#eff6ff";
            const border = a.type === "danger" ? "#fecaca" : a.type === "warning" ? "#fde68a" : a.type === "success" ? "#bbf7d0" : "#bfdbfe";
            const color = a.type === "danger" ? "#991b1b" : a.type === "warning" ? "#92400e" : a.type === "success" ? "#166534" : "#1e40af";
            return (
              <div key={a.id} className="announce-banner" style={{ background: bg, border: `1px solid ${border}`, color }}>
                <div className="announce-banner-body">
                  <strong className="announce-banner-title">{a.title}</strong>
                  <span className="announce-banner-content">{a.content}</span>
                </div>
                <button className="announce-banner-close" onClick={() => dismissAnnounce(a.id)} title="关闭">×</button>
              </div>
            );
          })}
        </div>
      )}
      {children}
    </AppLayout>
    );
  };

  const openPracticeFromTask = (context) => {
    if (!isFeatureEnabled("feature_practice_center_enabled")) {
      alert("璇ュ姛鑳芥殏鏃剁淮鎶や腑锛岃绋嶅悗鍐嶈瘯");
      return;
    }
    setPracticeContext(context);
    saveCurrentPage("practiceCenter");
    setPageRaw("practiceCenter");
  };

  if (page === "home") {
    const avatarObj = AVATARS.find((a) => a.id === (user?.avatar || "")) || AVATARS[0];
    const hasCustomAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

    return wrapPage(
      <HomePage
        user={user}
        page={page}
        setPage={setPage}
        subject={subject}
        setSubject={setSubject}
        avatarObj={avatarObj}
        hasCustomAvatar={hasCustomAvatar}
        apiBase={API_BASE}
        onLogout={logout}
        isAdmin={!!user?.is_admin}
        setSearchContext={setSearchContext}
        setSearchNavigate={setSearchNavigate}
      />
    );
  }

  const handleProfileUpdate = (updatedFields) => {
    if (!user) return;
    const updatedUser = { ...user, ...updatedFields };
    setUser(updatedUser);
    try {
      const stored = localStorage.getItem(USER_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        const merged = { ...parsed, ...updatedFields };
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(merged));
      }
    } catch {
      // ignore
    }
  };

  if (page === "profile") {
    return wrapPage(
      <ProfilePage
        user={user}
        apiBase={API_BASE}
        onLogout={logout}
        setPage={setPage}
        onProfileUpdate={handleProfileUpdate}
      />
    );
  }

  if (page === "membership") {
    return wrapPage(
      <MembershipPage
        user={user}
        apiBase={API_BASE}
        setPage={setPage}
        onPlanUpdate={handleProfileUpdate}
      />
    );
  }

  if (page === "codeStudio") {
    if (!isFeatureEnabled("feature_code_studio_enabled")) {
      return wrapPage(<FeatureUnavailable featureName="编程助手" onGoHome={() => setPage("home")} />);
    }
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">编程学习助手加载中...</div>}>
          <CodeStudio
            user={user}
            subject={subject}
            courseOptions={COURSE_OPTIONS}
            getSubjectLabel={getSubjectLabel}
            normalizeSubject={normalizeSubject}
            formatDate={formatDate}
            searchNavigate={searchNavigate}
            onClearSearchNavigate={() => setSearchNavigate(null)}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "taskCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">学习任务中心加载中...</div>}>
          <TaskCenter
            user={user}
            subject={subject}
            courseOptions={COURSE_OPTIONS}
            getSubjectLabel={getSubjectLabel}
            normalizeSubject={normalizeSubject}
            formatDate={formatDate}
            onStartPractice={openPracticeFromTask}
            searchNavigate={searchNavigate}
            onClearSearchNavigate={() => setSearchNavigate(null)}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "practiceCenter") {
    if (!isFeatureEnabled("feature_practice_center_enabled")) {
      return wrapPage(<FeatureUnavailable featureName="练习中心" onGoHome={() => setPage("home")} />);
    }
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">练习中心加载中...</div>}>
          <PracticeCenter
            user={user}
            subject={subject}
            courseOptions={COURSE_OPTIONS}
            getSubjectLabel={getSubjectLabel}
            normalizeSubject={normalizeSubject}
            formatDate={formatDate}
            setPage={setPage}
            practiceContext={practiceContext}
            onClearPracticeContext={() => setPracticeContext(null)}
            coursePreference={coursePreference}
            searchNavigate={searchNavigate}
            onClearSearchNavigate={() => setSearchNavigate(null)}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "learningDataCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">学习数据中心加载中...</div>}>
          <LearningDataCenter
            user={user}
            getSubjectLabel={getSubjectLabel}
            onNavigate={setPage}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "reviewCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">复盘中心加载中...</div>}>
          <ReviewCenter
            user={user}
            getSubjectLabel={getSubjectLabel}
            setPage={setPage}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "learningPlanCenter") {
    return wrapPage(
      <div className="app-shell">
        <section className="chat-panel chat-panel--wide task-center-panel task-center-v2">
          <div className="task-empty-state-v2">
            <h3>AI 学习计划已整合到任务中心</h3>
            <p className="task-muted">进入任务中心后，可以手动新建任务，也可以使用 AI 生成计划。</p>
            <button type="button" className="task-btn-primary" onClick={() => setPage("taskCenter")}>
              前往任务中心
            </button>
          </div>
        </section>
      </div>
    );
  }

  if (page === "knowledgeBaseCenter") {
    return wrapPage(
      <div className="app-shell">
        <header className="workspace-topbar">
          <div className="workspace-topbar-left">
            <span className="subject-pill panel-pill">知识库中心</span>
          </div>
        </header>
        <Suspense fallback={<div className="empty-state">知识库中心加载中...</div>}>
          <KnowledgeBaseCenter
            user={user}
            getSubjectLabel={getSubjectLabel}
          />
        </Suspense>
      </div>
    );
  }

  if (page === "quotaCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">额度中心加载中...</div>}>
          <QuotaCenter user={user} setPage={setPage} />
        </Suspense>
      </div>
    );
  }

  if (page === "learningReportCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">学习报告加载中...</div>}>
          <LearningReportCenter user={user} />
        </Suspense>
      </div>
    );
  }

  if (page === "searchResults") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">搜索加载中...</div>}>
          <SearchResultsPage
            user={user}
            setPage={setPage}
            searchContext={searchContext}
            onClearSearchContext={() => setSearchContext(null)}
            setSearchNavigate={setSearchNavigate}
          />
        </Suspense>
      </div>
    );
  }

  // ── Admin route protection ──
  const isAdminAuthorized = user && (user.is_admin || user.plan === "admin" || user.role === "admin"
    || ["super_admin", "operator", "auditor"].includes(user.admin_role));
  if ((page === "adminUsageCenter" || page === "adminCenter") && !isAdminAuthorized) {
    return (
      <div className="auth-shell">
        <div className="auth-card" style={{ textAlign: "center", padding: 40 }}>
          <h2>需要管理员权限</h2>
          <p style={{ color: "#64748b", margin: "8px 0 16px" }}>请先通过管理后台登录验证。</p>
          <button className="auth-submit" onClick={() => setPage("adminLogin")}>前往管理后台登录</button>
        </div>
      </div>
    );
  }

  if (page === "adminUsageCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">管理后台加载中...</div>}>
          <AdminUsageCenter user={user} />
        </Suspense>
      </div>
    );
  }

  if (page === "adminCenter") {
    return wrapPage(
      <div className="app-shell">
        <Suspense fallback={<div className="empty-state">管理后台加载中...</div>}>
          <AdminCenter user={user} />
        </Suspense>
      </div>
    );
  }

  if (page === "profileEdit") {
    return (
      <div className="auth-shell">
        <div className="onboarding-card">
          <div className="auth-badge">AI 学习平台</div>
          <h1>编辑学习信息</h1>

          <label className="field-label">昵称</label>
          <input
            className="field"
            placeholder="例如：小明"
            value={profileForm.nickname}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))
            }
          />

          <label className="field-label">专业</label>
          <input
            className="field"
            placeholder="例如：软件工程"
            value={profileForm.major}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, major: e.target.value }))
            }
          />

          <label className="field-label">年级</label>
          <input
            className="field"
            placeholder="例如：大二"
            value={profileForm.grade}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, grade: e.target.value }))
            }
          />

          <div className="goals-header">
            <label className="field-label">想学习的科目</label>
            <button className="tiny-button" type="button" onClick={addLearningGoal}>
              + 添加科目
            </button>
          </div>

          {learningGoals.length === 0 && (
            <div className="goal-empty-card" onClick={addLearningGoal}>
              <div className="goal-empty-icon">+</div>
              <div className="goal-empty-text">点击这里添加你想学习的第一个科目</div>
              <div className="goal-empty-hint">例如：高等数学、大学英语、程序设计</div>
            </div>
          )}

          {learningGoals.map((goal, index) => (
            <div key={index} className="goal-card">
              <div className="goal-card-header">
                <span className="goal-card-number">科目 {index + 1}</span>
                <button
                  className="goal-remove-btn"
                  type="button"
                  onClick={() => removeLearningGoal(index)}
                >
                  移除
                </button>
              </div>
              <select
                className="field"
                value={goal.subject}
                onChange={(e) => updateLearningGoal(index, "subject", e.target.value)}
              >
                <option value="">选择科目</option>
                {COURSE_OPTIONS.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <label className="field-label">想掌握到的程度</label>
              <select
                className="field"
                value={goal.target_level}
                onChange={(e) => updateLearningGoal(index, "target_level", e.target.value)}
              >
                {TARGET_LEVEL_OPTIONS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>

              <label className="field-label">备注（可选）</label>
              <input
                className="field"
                placeholder="例如：希望能独立写后端"
                value={goal.note}
                onChange={(e) => updateLearningGoal(index, "note", e.target.value)}
              />
            </div>
          ))}

          {tip && <p className="tip-text">{tip}</p>}

          <div className="stack-actions">
            <button className="primary-button" onClick={saveOnboarding} disabled={onboardingSaving}>
              {onboardingSaving ? "保存中..." : "保存并返回主页"}
            </button>
            <button className="ghost-button" onClick={() => setPage("home")}>
              返回主页
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (page === "materials") {
    return wrapPage(
      <div className="materials-shell">
        <div className="materials-page-card">
          <div className="materials-page-header">
            <div>
              <div className="section-eyebrow">个人资料库</div>
              <h2>
                我的资料
                {currentFilterSubject && (
                  <span className="material-count">
                    {" "}（{currentFilterItems.length} 条）
                  </span>
                )}
              </h2>
            </div>
            <div className="header-actions">
              <button
                className="ghost-button compact"
                onClick={() => setMaterialListCollapsed((prev) => !prev)}
              >
                {materialListCollapsed ? "展开资料列表" : "收起资料列表"}
              </button>
              <button
                className="ghost-button compact"
                onClick={reindexLibrary}
                disabled={reindexLoading}
              >
                {reindexLoading ? "重建索引中..." : "重建索引"}
              </button>
              <button
                className="ghost-button compact"
                onClick={() => {
                  setMaterialCurrentPage(1);
                  loadMaterials("");
                }}
              >
                刷新
              </button>
            </div>
          </div>

          <div className="library-filter-row">
            <label className="field-label">按学科筛选</label>
            <select
              className="field"
              value={currentFilterSubject}
              onChange={(e) => {
                const next = e.target.value;
                setMaterialSubjectFilter(next);
                setMaterialCurrentPage(1);
                setMaterialListCollapsed(false);
              }}
            >
              {COURSE_OPTIONS.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
            </select>
          </div>

          <div className="library-search-row">
            <label className="field-label">资料搜索</label>
            <div className="library-search-controls">
              <input
                className="field"
                placeholder="在当前学科下搜索资料..."
                value={materialSearchQuery}
                onChange={(e) => handleMaterialSearchChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    setMaterialCurrentPage(1);
                    searchMaterials(materialSearchQuery, currentFilterSubject);
                  }
                }}
              />
              <button
                className="ghost-button compact"
                onClick={() => {
                  setMaterialCurrentPage(1);
                  searchMaterials(materialSearchQuery, currentFilterSubject);
                }}
                disabled={!trimmedMaterialSearchQuery || materialSearchLoading}
              >
                搜索
              </button>
            </div>
          </div>

          {trimmedMaterialSearchQuery && materialSearchTriggered ? (
            materialSearchLoading ? (
              <div className="empty-inline">正在搜索...</div>
            ) : materialSearchResults.length === 0 ? (
              <div className="empty-inline">
                {getSubjectLabel(currentFilterSubject)} 学科下没有匹配的资料。
              </div>
            ) : (
              <div className="search-results">
                {paginatedSearchResults.map((item) => (
                  <div key={`${item.material_id}-${item.chunk_id}`} className="search-result-card">
                    <div className="material-item-head">
                      <span className="subject-pill small">
                        {getSubjectLabel(item.subject)}
                      </span>
                      <span className="muted-text">{getFileTypeLabel(item.file_type)}</span>
                    </div>
                    <div className="material-title">{item.filename}</div>
                    <div className="search-result-snippet">
                      命中片段：{getReferenceSnippet(item)}
                    </div>
                    <div className="history-meta">{formatDate(item.created_at)}</div>
                    <div className="material-actions">
                      <button
                        className="tiny-button"
                        onClick={() => openMaterialDetail(item.material_id)}
                      >
                        查看详情
                      </button>
                    </div>
                  </div>
                ))}
                <div className="pagination-bar">
                  <button
                    className="tiny-button"
                    disabled={safeSearchPage <= 1}
                    onClick={() => setMaterialCurrentPage((p) => Math.max(1, p - 1))}
                  >
                    上一页
                  </button>
                  <span className="pagination-info">
                    {safeSearchPage} / {searchTotalPages}
                  </span>
                  <button
                    className="tiny-button"
                    disabled={safeSearchPage >= searchTotalPages}
                    onClick={() => setMaterialCurrentPage((p) => Math.min(searchTotalPages, p + 1))}
                  >
                    下一页
                  </button>
                </div>
              </div>
            )
          ) : materialsLoading ? (
            <div className="empty-inline">资料加载中...</div>
          ) : groupedMaterials.length === 0 ? (
            <div className="empty-inline">
              暂无资料，请先在聊天页上传图片或 PDF。
            </div>
          ) : materialListCollapsed ? (
            <div className="library-group">
              <div className="library-group-title">
                {getSubjectLabel(currentFilterSubject)}
                <span className="material-count-sub">
                  {" "}（{currentFilterItems.length} 条资料已收起）
                </span>
              </div>
            </div>
          ) : (
            <div className="library-groups">
              <div className="library-group">
                <div className="library-group-title">
                  {getSubjectLabel(currentFilterSubject)}
                </div>
                <div className="material-list material-list--profile">
                  {paginatedFilterItems.map((material) => (
                    <div key={material.id} className="material-item material-item--profile">
                      <div className="material-item-head">
                        <span className="subject-pill small">
                          {getSubjectLabel(material.subject)}
                        </span>
                        <span className="muted-text">
                          {getFileTypeLabel(material.file_type)}
                        </span>
                      </div>
                      <div className="material-title">{material.original_filename}</div>
                      <div className="material-summary">{material.summary}</div>
                      <div className="material-asset-meta">
                        <span>原文件已保存</span>
                        <span>{formatFileSize(material.file_size)}</span>
                        <span>{getParseStatusLabel(material.parse_status)}</span>
                        <span>{Number(material.chunk_count || 0)} 个知识片段</span>
                      </div>
                      <div className="history-meta">{formatDate(material.created_at)}</div>
                      <div className="material-actions">
                        <button
                          className="tiny-button"
                          onClick={() => previewMaterial(material)}
                          disabled={!material.can_preview}
                        >
                          查看原文件
                        </button>
                        <button
                          className="tiny-button"
                          onClick={() => downloadMaterial(material)}
                          disabled={!material.can_download}
                        >
                          下载原文件
                        </button>
                        <button
                          className="tiny-button"
                          onClick={() => openMaterialDetail(material.id)}
                        >
                          查看 AI 索引文本
                        </button>
                        <button
                          className="tiny-button danger"
                          onClick={() => deleteMaterial(material.id)}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {currentFilterTotalPages > 1 && (
                  <div className="pagination-bar">
                    <button
                      className="tiny-button"
                      disabled={safeCurrentPage <= 1}
                      onClick={() => setMaterialCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      上一页
                    </button>
                    <span className="pagination-info">
                      {safeCurrentPage} / {currentFilterTotalPages}
                    </span>
                    <button
                      className="tiny-button"
                      disabled={safeCurrentPage >= currentFilterTotalPages}
                      onClick={() =>
                        setMaterialCurrentPage((p) => Math.min(currentFilterTotalPages, p + 1))
                      }
                    >
                      下一页
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="material-detail-card material-detail-card--profile">
            <div className="panel-title-row">
              <h3>资料详情</h3>
            </div>
            {!selectedMaterialDetail ? (
              <div className="empty-inline">
                点击"查看原文件"在新标签页预览原文件；点击"查看 AI 索引文本"查看解析摘要。
              </div>
            ) : (
              <>
                <div className="detail-meta">
                  <div>文件：{selectedMaterialDetail.original_filename}</div>
                  <div>学科：{getSubjectLabel(selectedMaterialDetail.subject)}</div>
                  <div>类型：{getFileTypeLabel(selectedMaterialDetail.file_type)}</div>
                  <div>上传时间：{formatDate(selectedMaterialDetail.created_at)}</div>
                </div>
                <div className="material-status-note">
                  {getParseStatusHint(selectedMaterialDetail)}
                </div>
                <div className="material-asset-meta material-asset-meta--detail">
                  <span>原文件大小：{formatFileSize(selectedMaterialDetail.file_size)}</span>
                  <span>AI 知识索引：{getParseStatusLabel(selectedMaterialDetail.parse_status)}</span>
                  <span>{Number(selectedMaterialDetail.chunk_count || 0)} 个知识片段</span>
                </div>
                <div className="material-actions material-actions--detail">
                  <button
                    className="tiny-button"
                    onClick={() => previewMaterial(selectedMaterialDetail)}
                    disabled={!selectedMaterialDetail.can_preview}
                  >
                    查看原文件
                  </button>
                  <button
                    className="tiny-button"
                    onClick={() => downloadMaterial(selectedMaterialDetail)}
                    disabled={!selectedMaterialDetail.can_download}
                  >
                    下载原文件
                  </button>
                </div>
                <div className="material-status-note">
                  以下内容是系统从原文件中解析出的 AI 知识索引，用于问答和引用，不等同于原文件排版。
                </div>
                <div className="result-block">
                  <strong>摘要</strong>
                  <p>{selectedMaterialDetail.summary}</p>
                </div>
                <div className="result-block">
                  <strong>AI 知识索引文本</strong>
                  <pre>{selectedMaterialDetail.extracted_text}</pre>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (page === "chat") {
    return wrapPage(
      <>
        <AIQuestionPage
        user={user}
        apiBase={API_BASE}
        subject={subject}
        setSubject={setSubject}
        setPage={setPage}
        COURSE_OPTIONS={COURSE_OPTIONS}
        AVATARS={AVATARS}
        getSubjectLabel={getSubjectLabel}
        activeSessionId={activeSessionId}
        setActiveSessionSubject={setActiveSessionSubject}
        currentChatSubject={currentChatSubject}
        messages={messages}
        loading={loading}
        tip={tip}
        message={message}
        setMessage={setMessage}
        sendMessage={sendMessage}
        canSendMessage={canSendMessage}
        selectedFiles={selectedFiles}
        selectedLibraryMaterials={selectedLibraryMaterials}
        removeSelectedFile={removeSelectedFile}
        removeSelectedLibraryMaterial={removeSelectedLibraryMaterial}
        handleFileChange={handleFileChange}
        formatFileSize={formatFileSize}
        getSelectedFileStatusText={getSelectedFileStatusText}
        selectedFilesBlockReason={selectedFilesBlockReason}
        showPlusMenu={showPlusMenu}
        setShowPlusMenu={setShowPlusMenu}
        plusMenuRef={plusMenuRef}
        openLibraryReferenceModal={openLibraryReferenceModal}
        fileInputRef={fileInputRef}
        addToLibraryState={addToLibraryState}
        setAddToLibraryState={setAddToLibraryState}
        getFileTypeLabel={getFileTypeLabel}
        getReferenceSnippet={getReferenceSnippet}
        addMessageToLibrary={addMessageToLibrary}
        openMaterialDetail={openMaterialDetail}
        finishAssistantTyping={finishAssistantTyping}
        getQuestionForAssistantMessage={getQuestionForAssistantMessage}
        learningRecordActionState={learningRecordActionState}
        saveLearningRecord={saveLearningRecord}
        getRecordTypeLabel={getRecordTypeLabel}
        getRecordTypeIcon={getRecordTypeIcon}
        startNewConversation={startNewConversation}
        chatSessions={chatSessions}
        openChatSession={openChatSession}
        loadChatSessions={loadChatSessions}
        onEditMessage={editUserMessage}
        onVersionChange={switchMessageVersion}
        pendingAIContext={pendingAIContext}
        setPendingAIContext={setPendingAIContext}
        setSearchContext={setSearchContext}
        setSearchNavigate={setSearchNavigate}
      />
        <MaterialPickerModal
          open={showLibraryRefModal}
          onClose={() => setShowLibraryRefModal(false)}
          subjectLabel={getSubjectLabel(currentChatSubject)}
          materials={libraryRefMaterials}
          loading={libraryRefLoading}
          searchQuery={libraryRefSearchQuery}
          onSearchChange={setLibraryRefSearchQuery}
          selectedMaterials={selectedLibraryMaterials}
          onToggleMaterial={toggleLibraryMaterialSelection}
          canReferenceMaterial={canReferenceMaterial}
          getUnreferenceableReason={getUnreferenceableReason}
          getFileTypeLabel={getFileTypeLabel}
          formatFileSize={formatFileSize}
          getParseStatusLabel={getParseStatusLabel}
        />
      </>
    );
  }

  return wrapPage(
    <div className="workspace-shell">
      <div className="workspace-topbar-wrapper">
        <div className="workspace-topbar">
          <div className="workspace-topbar-center">
            <select
              className="field workspace-subject-select"
              value={subject}
              onChange={(e) => {
                setSubject(e.target.value);
                if (!activeSessionId) {
                  setActiveSessionSubject(e.target.value);
                }
              }}
            >
              {COURSE_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {getSubjectLabel(item)}
                </option>
              ))}
            </select>
            {(page !== "dashboard" && page !== "knowledgeLearning" && page !== "workspaceMaterials") && (
              <nav className="workspace-tabs">
                <button
                  className={`workspace-tab ${page === "chat" ? "active" : ""}`}
                  onClick={() => setPage("chat")}
                >
                  AI 问答
                </button>
                <button
                  className={`workspace-tab ${page === "workspaceMaterials" ? "active" : ""}`}
                  onClick={() => { setMaterialSubjectFilter(normalizeSubject(subject)); setMaterialCurrentPage(1); setPage("workspaceMaterials"); loadMaterials(normalizeSubject(subject)); }}
                >
                  资料库
                </button>
                <button
                  className={`workspace-tab ${page === "records" ? "active" : ""}`}
                  onClick={openLearningRecordPage}
                >
                  学习记录
                </button>
                <button
                  className={`workspace-tab ${page === "history" ? "active" : ""}`}
                  onClick={() => setPage("history")}
                >
                  历史对话
                </button>
              </nav>
            )}
          </div>
          {(page !== "dashboard" && page !== "knowledgeLearning" && page !== "workspaceMaterials") && (
            <div className="workspace-topbar-actions">
              <button className="primary-button compact" onClick={startNewConversation}>
                新建对话
              </button>
            </div>
          )}
        </div>
      </div>

      <main className={`workspace-main ${page === "dashboard" || page === "knowledgeLearning" || page === "workspaceMaterials" ? "workspace-main--wide" : "workspace-main--chat-only"}`}>
        {page === "dashboard" ? (
          <CourseDashboard
            user={user}
            course={subject}
            dashboard={courseDashboardData}
            coursePreference={coursePreference}
            onPreferenceChange={setCoursePreference}
            loading={courseDashboardLoading}
            savingPointKey={courseProgressSavingKey}
            setPage={setPage}
            onProgressChange={updateCourseProgress}
            onStartAsk={() => {
              openChatPageForCourse(subject, true);
              setSelectedLibraryMaterials([]);
              setPendingAIContext(null);
            }}
            onOpenCodeStudio={() => setPage("codeStudio")}
            onOpenPracticeCenter={() => setPage("practiceCenter")}
            getSubjectLabel={getSubjectLabel}
            formatDate={formatDate}
            materials={materials}
            loadMaterials={(target) => loadMaterials(normalizeSubject(target || subject))}
            loadDashboard={() => loadCourseDashboard(subject)}
            goalConfig={goalConfig}
            setGoalConfig={updateGoalConfig}
          />
        ) : page === "knowledgeLearning" ? (
          <KnowledgeLearningPage
            user={user}
            course={subject}
            courseOptions={COURSE_OPTIONS}
            getSubjectLabel={getSubjectLabel}
            setPage={setPage}
            onNavigateToAI={(ctx) => {
              openChatPageForCourse(subject, true);
              setSelectedLibraryMaterials([]);
              setPendingAIContext(ctx);
            }}
            materials={materials}
            materialsLoading={materialsLoading}
            loadMaterials={(target) => loadMaterials(normalizeSubject(target || subject))}
            goalConfig={goalConfig}
            searchNavigate={searchNavigate}
            onClearSearchNavigate={() => setSearchNavigate(null)}
          />
        ) : page === "records" ? (
          <section className="chat-panel chat-panel--wide learning-records-panel">
            <div className="panel-header panel-header--chat">
              <div className="subject-pill panel-pill">学习记录</div>
              <div className="subject-pill">
                当前学科：{getSubjectLabel(displayedLearningRecordSubject)}
              </div>
            </div>

            <div className="learning-stats-grid">
              <div className="learning-stat-card">
                <div className="learning-stat-label">错题本</div>
                <div className="learning-stat-value">
                  {learningRecordStats?.wrong_question_count ?? 0}
                </div>
              </div>
              <div className="learning-stat-card">
                <div className="learning-stat-label">重点</div>
                <div className="learning-stat-value">
                  {learningRecordStats?.important_count ?? 0}
                </div>
              </div>
              <div className="learning-stat-card">
                <div className="learning-stat-label">待复习</div>
                <div className="learning-stat-value">
                  {learningRecordStats?.pending_review_count ?? 0}
                </div>
              </div>
              <div className="learning-stat-card">
                <div className="learning-stat-label">当前学科记录</div>
                <div className="learning-stat-value">{currentSubjectRecordCount}</div>
              </div>
            </div>

            <div className="learning-filter-row">
              <div className="learning-filter-item">
                <label className="field-label">类型筛选</label>
                <select
                  className="field"
                  value={learningRecordTypeFilter}
                  onChange={(e) => setLearningRecordTypeFilter(e.target.value)}
                >
                  {RECORD_TYPE_OPTIONS.map((item) => (
                    <option key={item.value || "all"} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="learning-filter-item">
                <label className="field-label">学科筛选</label>
                <select
                  className="field"
                  value={learningRecordSubjectFilter}
                  onChange={(e) => setLearningRecordSubjectFilter(e.target.value)}
                >
                  <option value="__CURRENT__">当前学科</option>
                  <option value="">全部学科</option>
                  {COURSE_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {getSubjectLabel(item)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="learning-filter-item">
                <label className="field-label">复习状态</label>
                <select
                  className="field"
                  value={learningRecordReviewFilter}
                  onChange={(e) => setLearningRecordReviewFilter(e.target.value)}
                >
                  {REVIEW_STATUS_OPTIONS.map((item) => (
                    <option key={item.value || "all"} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="learning-records-layout">
              <div className="learning-records-list">
                {learningRecordsLoading ? (
                  <div className="empty-inline">学习记录加载中...</div>
                ) : learningRecords.length === 0 ? (
                  <div className="empty-inline">
                    <p>当前课程还没有学习记录。</p>
                    <p className="muted-text">在 AI 问答中提问后，系统会自动沉淀知识点和复习建议。</p>
                    <button
                      className="primary-button compact"
                      onClick={() => setPage("chat")}
                    >
                      去 AI 问答
                    </button>
                  </div>
                ) : (
                  learningRecords.map((record) => (
                    <div
                      key={record.id}
                      className={
                        selectedLearningRecord?.id === record.id
                          ? "learning-record-card active"
                          : "learning-record-card"
                      }
                    >
                      <div className="learning-record-head">
                        <div className="record-type-badge">
                          {getRecordTypeIcon(record.record_type)}{" "}
                          {getRecordTypeLabel(record.record_type)}
                        </div>
                        <span className="subject-pill small">
                          {getSubjectLabel(record.subject)}
                        </span>
                      </div>
                      <div className="learning-record-question">{record.question}</div>
                      <div className="learning-record-answer-preview">
                        {getRecordAnswerPreview(record.answer)}
                      </div>
                      {Array.isArray(record.tags) && record.tags.length > 0 && (
                        <div className="learning-record-tags">
                          {record.tags.map((tag) => (
                            <span key={tag} className="knowledge-tag">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="learning-record-meta">
                        <span>{formatDate(record.created_at)}</span>
                        <span>
                          {Array.isArray(record.references) && record.references.length > 0
                            ? "基于资料回答"
                            : "通用问答"}
                        </span>
                        <span>
                          {record.review_status === "reviewed" ? "已复习" : "待复习"}
                        </span>
                      </div>
                      <div className="learning-record-actions">
                        {record.session_id && (
                          <button
                            className="tiny-button"
                            onClick={() => openChatSession({ id: record.session_id })}
                          >
                            查看对话
                          </button>
                        )}
                        <button
                          className="tiny-button"
                          onClick={() => selectLearningRecord(record)}
                        >
                          查看详情
                        </button>
                        {record.review_status === "reviewed" ? (
                          <button className="tiny-button" disabled>
                            已复习
                          </button>
                        ) : (
                          <button
                            className="tiny-button"
                            onClick={() => markLearningRecordReviewed(record)}
                            disabled={learningRecordSaving}
                          >
                            标记已复习
                          </button>
                        )}
                        <button
                          className="tiny-button danger"
                          onClick={() => deleteLearningRecord(record.id)}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="material-detail-card learning-record-detail-card">
                <div className="panel-title-row">
                  <h3>学习记录详情</h3>
                </div>
                {!selectedLearningRecord ? (
                  <div className="empty-inline">点击左侧记录可查看完整问答、引用来源与备注。</div>
                ) : (
                  <>
                    <div className="detail-meta">
                      <div>类型：{getRecordTypeLabel(selectedLearningRecord.record_type)}</div>
                      <div>学科：{getSubjectLabel(selectedLearningRecord.subject)}</div>
                      <div>创建时间：{formatDate(selectedLearningRecord.created_at)}</div>
                      <div>
                        复习状态：
                        {selectedLearningRecord.review_status === "reviewed"
                          ? "已复习"
                          : "待复习"}
                      </div>
                    </div>

                    <div className="result-block">
                      <strong>用户问题</strong>
                      <p>{selectedLearningRecord.question}</p>
                    </div>

                    <div className="result-block">
                      <strong>AI 回答</strong>
                      <MarkdownMessage content={selectedLearningRecord.answer} />
                    </div>

                    {Array.isArray(selectedLearningRecord.references) &&
                      selectedLearningRecord.references.length > 0 && (
                        <div className="reference-section">
                          <div className="reference-title">引用来源</div>
                          <div className="reference-list">
                            {selectedLearningRecord.references.map((reference, index) => (
                              <div
                                key={`${reference.material_id || index}-${index}`}
                                className="reference-card"
                              >
                                <div className="reference-name">
                                  {index + 1}. {reference.filename || "资料片段"}
                                </div>
                                <div className="reference-meta">
                                  学科：{getSubjectLabel(reference.subject)} | 类型：
                                  {getFileTypeLabel(reference.file_type)}
                                </div>
                                <div className="reference-snippet">
                                  命中片段：{getReferenceSnippet(reference)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    <div className="learning-record-editor">
                      <label className="field-label">备注</label>
                      <textarea
                        className="field learning-record-textarea"
                        placeholder="补充这条学习记录的思路、易错点或复习提醒"
                        value={learningRecordNote}
                        onChange={(e) => setLearningRecordNote(e.target.value)}
                      />

                      <label className="field-label">标签</label>
                      <input
                        className="field"
                        placeholder="例如：连接查询，事务，并发控制"
                        value={learningRecordTagsInput}
                        onChange={(e) => setLearningRecordTagsInput(e.target.value)}
                      />

                      <div className="learning-record-detail-actions">
                        <button
                          className="ghost-button compact"
                          onClick={saveLearningRecordNoteAndTags}
                          disabled={learningRecordSaving}
                        >
                          {learningRecordSaving ? "保存中..." : "保存备注与标签"}
                        </button>
                        {selectedLearningRecord.review_status === "reviewed" ? (
                          <button className="ghost-button compact" disabled>
                            已复习
                          </button>
                        ) : (
                          <button
                            className="ghost-button compact"
                            onClick={() => markLearningRecordReviewed(selectedLearningRecord)}
                            disabled={learningRecordSaving}
                          >
                            标记已复习
                          </button>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {tip && <p className="tip-text">{tip}</p>}
          </section>
        ) : page === "history" ? (
          <section className="chat-panel chat-panel--wide workspace-history-panel">
            <div className="panel-header panel-header--chat">
              <div className="subject-pill panel-pill">历史对话</div>
              <div className="subject-pill">学科：{getSubjectLabel(subject)}</div>
            </div>
            <div className="history-list history-list--page">
              {visibleSessions.length === 0 && (
                <div className="empty-inline">该学科下暂无历史对话。</div>
              )}
              {visibleSessions.map((session) => (
                <div
                  key={session.id}
                  className={activeSessionId === session.id ? "history-item active" : "history-item"}
                  onClick={() => openChatSession(session)}
                >
                  <div className="history-subject">
                    {getSubjectLabel(session.subject || session.course)}
                  </div>
                  <div className="history-title">{session.title}</div>
                  <div className="history-meta">{formatDate(session.created_at)}</div>
                  <div className="history-actions">
                    <button
                      className="tiny-button"
                      onClick={(event) => { event.stopPropagation(); renameChatSession(session, event); }}
                    >
                      编辑标题
                    </button>
                    <button
                      className="tiny-button danger"
                      onClick={(event) => { event.stopPropagation(); deleteChatSession(session, event); }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : page === "workspaceMaterials" ? (
          <CourseMaterialsPage
            user={user}
            subject={subject}
            courseOptions={COURSE_OPTIONS}
            getSubjectLabel={getSubjectLabel}
            materials={materials}
            materialsLoading={materialsLoading}
            reindexLoading={reindexLoading}
            currentFilterItems={currentFilterItems}
            paginatedFilterItems={paginatedFilterItems}
            currentFilterTotalPages={currentFilterTotalPages}
            safeCurrentPage={safeCurrentPage}
            materialSearchQuery={materialSearchQuery}
            handleMaterialSearchChange={handleMaterialSearchChange}
            trimmedMaterialSearchQuery={trimmedMaterialSearchQuery}
            materialSearchTriggered={materialSearchTriggered}
            materialSearchLoading={materialSearchLoading}
            materialSearchResults={materialSearchResults}
            paginatedSearchResults={paginatedSearchResults}
            materialSortMode={materialSortMode}
            setMaterialSortMode={setMaterialSortMode}
            safeSearchPage={safeSearchPage}
            searchTotalPages={searchTotalPages}
            materialCurrentPage={materialCurrentPage}
            setMaterialCurrentPage={setMaterialCurrentPage}
            selectedMaterialDetail={selectedMaterialDetail}
            materialsFileInputRef={materialsFileInputRef}
            materialSubjectFilter={materialSubjectFilter}
            handleFileChange={(event) => handleFileChange(event, materialSubjectFilter)}
            loadMaterials={loadMaterials}
            searchMaterials={searchMaterials}
            reindexLibrary={reindexLibrary}
            openMaterialDetail={openMaterialDetail}
            previewMaterial={previewMaterial}
            downloadMaterial={downloadMaterial}
            deleteMaterial={deleteMaterial}
            reparseMaterial={reparseMaterial}
            setPage={setPage}
            searchNavigate={searchNavigate}
            onClearSearchNavigate={() => setSearchNavigate(null)}
          />
        ) : (
          <div className="ai-qa-layout">
            <section className="chat-panel ai-qa-chat">
            <div className="panel-header panel-header--chat">
              <div className="subject-pill panel-pill">当前对话</div>
              <div className="subject-pill">学科：{getSubjectLabel(currentChatSubject)}</div>
            </div>

            <div className="messages-board">
              {messages.length === 0 && (
                <div className="empty-state">
                  在下方输入你的问题，或点击 + 上传资料后基于资料提问。
                </div>
              )}

              {messages.map((msg, index) => (
                <ChatMessage
                  key={msg.id || msg.clientId || index}
                  message={msg}
                  user={user}
                  currentChatSubject={currentChatSubject}
                  addToLibraryState={addToLibraryState}
                  setAddToLibraryState={setAddToLibraryState}
                  subjectOptions={COURSE_OPTIONS}
                  getSubjectLabel={getSubjectLabel}
                  getFileTypeLabel={getFileTypeLabel}
                  getReferenceSnippet={getReferenceSnippet}
                  addMessageToLibrary={addMessageToLibrary}
                  openMaterialDetail={openMaterialDetail}
                  onAnimationComplete={finishAssistantTyping}
                  questionText={getQuestionForAssistantMessage(index)}
                  learningRecordActionState={learningRecordActionState}
                  onSaveLearningRecord={saveLearningRecord}
                  getRecordTypeLabel={getRecordTypeLabel}
                  getRecordTypeIcon={getRecordTypeIcon}
                  onEditMessage={editUserMessage}
                  onVersionChange={switchMessageVersion}
                />
              ))}

              {loading && <div className="message-card assistant">正在思考...</div>}
            </div>

            <div className="composer-panel composer-panel--compact">
              {selectedFiles.length > 0 && (
                <div className="attachment-cards-row">
                  {selectedFiles.map((item) => (
                    <div
                      key={item.localId}
                      className={`attachment-file-card ${item.parse_status === "failed" ? "attachment-file-card--failed" : ""}`}
                    >
                      <div className="attachment-file-card-header">
                        <span className="attachment-file-card-type">
                          {getFileTypeLabel(item.file_type || item.type)}
                        </span>
                        <button
                          className="attachment-file-card-remove"
                          onClick={() => removeSelectedFile(item.localId)}
                          type="button"
                          title="从本次提问移除"
                        >
                          ×
                        </button>
                      </div>
                      <div className="attachment-file-card-name" title={item.original_filename}>
                        {item.original_filename}
                      </div>
                      <div className="attachment-file-card-meta">
                        <span>{formatFileSize(item.file_size)}</span>
                        <span className={`attachment-file-card-status attachment-file-card-status--${item.parse_status}`}>
                          {getSelectedFileStatusText(item)}
                          {Number(item.parse_progress || 0) > 0 && item.parse_status === "parsing"
                            ? ` ${Math.round(Number(item.parse_progress || 0))}%`
                            : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {selectedFilesBlockReason && (
                <div className="composer-hint">{selectedFilesBlockReason}</div>
              )}

              {selectedLibraryMaterials.length > 0 && (
                <div className="library-ref-bar">
                  <div className="library-ref-bar-title">已引用资料库资料</div>
                  <div className="library-ref-bar-list">
                    {selectedLibraryMaterials.map((material) => (
                      <div key={material.id} className="library-ref-chip">
                        <span className="library-ref-chip-name">{material.original_filename}</span>
                        <span className="library-ref-chip-type">{getFileTypeLabel(material.file_type)}</span>
                        <span className="library-ref-chip-source">来自资料库</span>
                        <button
                          className="library-ref-chip-remove"
                          title="从本次提问中移除"
                          onClick={() => removeSelectedLibraryMaterial(material.id)}
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="composer-row composer-row--input">
                <div className="plus-menu-wrapper" ref={plusMenuRef}>
                  <button
                    className="attach-button"
                    type="button"
                    onClick={() => setShowPlusMenu((v) => !v)}
                    disabled={loading}
                    title="添加资料"
                  >
                    +
                  </button>
                  {showPlusMenu && (
                    <div className="plus-menu">
                      <button
                        className="plus-menu-item"
                        type="button"
                        onClick={() => {
                          setShowPlusMenu(false);
                          fileInputRef.current?.click();
                        }}
                      >
                        上传新文件
                      </button>
                      <button
                        className="plus-menu-item"
                        type="button"
                        onClick={() => {
                          setShowPlusMenu(false);
                          openLibraryReferenceModal();
                        }}
                      >
                        引用资料库文件
                      </button>
                    </div>
                  )}
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
                  onChange={handleFileChange}
                  className="hidden-file-input"
                />

                <input
                  className="field composer-input"
                  placeholder={
                    selectedFiles.length > 0
                      ? "请输入你想基于这些资料提问的问题"
                      : "输入你的问题"
                  }
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                />

                <button
                  className="primary-button compact"
                  onClick={sendMessage}
                  disabled={!canSendMessage}
                >
                  {loading ? "发送中..." : "发送"}
                </button>
              </div>
            </div>

            {tip && <p className="tip-text">{tip}</p>}
          </section>
          <aside className="ai-qa-sidebar">
            {(selectedFiles.length > 0 || selectedLibraryMaterials.length > 0) && (
              <div className="ai-qa-sidebar-card">
                <h4 className="ai-qa-sidebar-card-title">本轮已引用资料</h4>
                <div className="ai-qa-ref-list">
                  {selectedFiles.filter(f => !f.uploading).map((item) => (
                    <div key={item.localId} className="ai-qa-ref-item">
                      <span className="ai-qa-ref-icon">📄</span>
                      <span className="ai-qa-ref-name">{item.original_filename}</span>
                    </div>
                  ))}
                  {selectedLibraryMaterials.map((item) => (
                    <div key={item.id} className="ai-qa-ref-item">
                      <span className="ai-qa-ref-icon">📚</span>
                      <span className="ai-qa-ref-name">{item.original_filename}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="ai-qa-sidebar-card">
              <h4 className="ai-qa-sidebar-card-title">推荐提问</h4>
              <div className="ai-qa-suggestions">
                {(() => {
                  const label = getSubjectLabel(currentChatSubject);
                  const suggestions = [
                    `请帮我总结${label}的核心知识点`,
                    `${label}有哪些常见的考点和难点？`,
                    `请举例说明${label}中的一个重要概念`,
                    `帮我整理${label}的知识框架和脉络`,
                    `在学习${label}时需要注意哪些问题？`,
                  ];
                  return suggestions.map((q, i) => (
                    <button
                      key={i}
                      className="ai-qa-suggestion-item"
                      onClick={() => { setMessage(q); }}
                    >
                      {q}
                    </button>
                  ));
                })()}
              </div>
            </div>
          </aside>
        </div>
        )}

        <MaterialPickerModal
          open={showLibraryRefModal}
          onClose={() => setShowLibraryRefModal(false)}
          subjectLabel={getSubjectLabel(subject)}
          materials={libraryRefMaterials}
          loading={libraryRefLoading}
          searchQuery={libraryRefSearchQuery}
          onSearchChange={setLibraryRefSearchQuery}
          selectedMaterials={selectedLibraryMaterials}
          onToggleMaterial={toggleLibraryMaterialSelection}
          canReferenceMaterial={canReferenceMaterial}
          getUnreferenceableReason={getUnreferenceableReason}
          getFileTypeLabel={getFileTypeLabel}
          formatFileSize={formatFileSize}
          getParseStatusLabel={getParseStatusLabel}
        />
      </main>
    </div>
  );
}

export default App;
