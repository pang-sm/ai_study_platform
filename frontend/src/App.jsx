import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import ChatMessage from "./components/ChatMessage.jsx";
import CourseDashboard from "./components/CourseDashboard.jsx";
import MarkdownMessage from "./components/MarkdownMessage.jsx";
import {
  COURSE_OPTIONS,
  DEFAULT_SUBJECT,
  getSubjectLabel,
  normalizeSubject,
} from "./courseOptions.js";

const USER_STORAGE_KEY = "ai_study_platform_user";
const ACTIVE_SESSION_STORAGE_KEY = "ai_study_platform_active_session_id";
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
  ".html", ".css", ".json", ".xml", ".yaml", ".yml",
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
  if (normalizedType.includes("text") || normalizedType === "txt") return "文本";
  if (
    normalizedType.includes("code") ||
    normalizedType.includes("python") ||
    normalizedType.includes("java") ||
    normalizedType.includes("javascript") ||
    normalizedType.includes("html") ||
    normalizedType.includes("css") ||
    normalizedType.includes("json") ||
    normalizedType.includes("xml") ||
    normalizedType.includes("yaml") ||
    normalizedType.includes("sql") ||
    normalizedType.includes("shell") ||
    normalizedType.includes("bash") ||
    normalizedType.includes("go") ||
    normalizedType.includes("php") ||
    normalizedType.includes("ruby") ||
    normalizedType.includes("c++") ||
    normalizedType.includes("rust")
  ) {
    return "代码";
  }

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
  const snippet = String(reference?.snippet || "").trim();
  if (!snippet) return "暂无片段预览";
  if (snippet.length <= 180) return snippet;
  return `${snippet.slice(0, 180)}...`;
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

function App() {
  const [page, setPage] = useState(getSavedUser() ? "profile" : "login");
  const [authMode, setAuthMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState(getSavedUser);
  const [profileForm, setProfileForm] = useState({
    nickname: "",
    grade: "",
    major: "",
    avatar: "avatar_1",
  });

  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [message, setMessage] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [messages, setMessages] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSessionSubject, setActiveSessionSubject] = useState(DEFAULT_SUBJECT);
  const [sidebarOpen, setSidebarOpen] = useState(true);
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
  const [courseProgressSavingKey, setCourseProgressSavingKey] = useState("");

  const fileInputRef = useRef(null);
  const localMessageCounterRef = useRef(0);
  const materialStatusPollersRef = useRef({});

  const currentChatSubject = activeSessionId ? activeSessionSubject : subject;
  const selectedFile = selectedFiles[0]
    ? {
        ...selectedFiles[0],
        type: String(selectedFiles[0].file_type || "").includes("pdf")
          ? "application/pdf"
          : selectedFiles[0].file_type,
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
    })).filter((group) => group.items.length > 0);
  }, [materials]);

  const availableSubjects = useMemo(() => {
    return groupedMaterials.map((g) => g.subject);
  }, [groupedMaterials]);

  const currentFilterSubject = availableSubjects.includes(materialSubjectFilter)
    ? materialSubjectFilter
    : "";

  const currentFilterItems = useMemo(() => {
    if (!currentFilterSubject) return [];
    const group = groupedMaterials.find((g) => g.subject === currentFilterSubject);
    return group?.items || [];
  }, [groupedMaterials, currentFilterSubject]);

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
  const paginatedSearchResults = materialSearchResults.slice(
    (safeSearchPage - 1) * PAGE_SIZE,
    safeSearchPage * PAGE_SIZE
  );

  const canSendMessage = useMemo(() => {
    if (loading) return false;
    if (selectedFiles.length > 0) {
      return (
        Boolean(trimmedMessage) &&
        selectedFiles.every(
          (item) => item.parse_status === "success" && Number(item.chunk_count || 0) > 0
        )
      );
    }
    return Boolean(trimmedMessage);
  }, [loading, selectedFiles, trimmedMessage]);

  const fileLabel = selectedFile
    ? selectedFile.type === "application/pdf"
      ? `PDF：${selectedFile.name}`
      : `图片：${selectedFile.name}`
    : "";

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
      parse_status: data.parse_status || material.parse_status || "pending",
      parse_progress: data.parse_progress ?? material.parse_progress ?? 0,
      chunk_count: data.chunk_count ?? material.chunk_count ?? 0,
      parse_error: material.parse_error || data.parse_error || "",
    };
  };

  const getSelectedFileStatusText = (item) => {
    if (item.uploading) return "上传中";
    if (item.parse_status === "success" && Number(item.chunk_count || 0) > 0) {
      return "已解析，可提问";
    }
    if (item.parse_status === "failed") return "解析失败，请删除后重新上传";
    if (item.parse_status === "partial") return "仅部分解析成功，请删除后重新上传";
    if (item.parse_status === "parsing") return "解析中";
    return "等待解析";
  };

  const selectedFilesBlockReason = useMemo(() => {
    if (selectedFiles.length === 0) return "";
    if (!trimmedMessage) return "请输入问题";
    const blocked = selectedFiles.some(
      (item) => item.parse_status !== "success" || Number(item.chunk_count || 0) <= 0
    );
    return blocked ? "资料正在解析中，解析完成后即可提问。" : "";
  }, [selectedFiles, trimmedMessage]);

  useEffect(() => {
    return () => {
      clearAllMaterialPollers();
    };
  }, []);

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
    const normalizedUser = {
      ...loginUser,
      nickname: loginUser.nickname || "",
      grade: loginUser.grade || "",
      major: loginUser.major || "",
      avatar: loginUser.avatar || "avatar_1",
    };

    setUser(normalizedUser);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(normalizedUser));
    setProfileForm({
      nickname: normalizedUser.nickname,
      grade: normalizedUser.grade,
      major: normalizedUser.major,
      avatar: normalizedUser.avatar,
    });
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
    if (availableSubjects.length > 0) {
      if (!materialSubjectFilter || !availableSubjects.includes(materialSubjectFilter)) {
        setMaterialSubjectFilter(availableSubjects[0]);
        setMaterialCurrentPage(1);
      }
    }
  }, [availableSubjects, materialSubjectFilter]);

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
        return;
      }

      setCourseDashboardData(data);
    } catch (error) {
      console.error("Failed to load course dashboard:", error);
      setTip("暂时无法加载课程工作台。");
      setCourseDashboardData(null);
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
    setPage("profile");
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

    const confirmed = window.confirm(`确认删除“${session.title}”吗？`);
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
        setPage("profile");
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

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      setPage("profile");
      setTip("注册成功，请完善个人资料。");
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

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      await loadProfile(loginUser);
      setPage("profile");
      setTip("");
    } catch (error) {
      console.error("Login failed:", error);
      setTip("无法连接后端服务。");
    }
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

  const pollMaterialStatus = (localId, materialId) => {
    clearMaterialPoller(localId);

    const refreshStatus = async () => {
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

  const uploadSelectedFile = async (file, localId) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("username", user.username);
    formData.append("subject", normalizeSubject(currentChatSubject));

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
      } else if (uploaded.parse_status === "success" && Number(uploaded.chunk_count || 0) > 0) {
        await loadMaterials("");
      }
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
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!isAllowedFile(file)) {
      alert("不支持的文件类型，请选择 PDF、图片、Word(docx)、PPT(pptx)、TXT、Markdown 或代码文件。");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      alert("文件大小不能超过 20MB。");
      return;
    }

    if (!user?.username) {
      setTip("请先登录。");
      logout();
      return;
    }

    const localId = `upload-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setSelectedFiles((prev) => [
      ...prev,
      {
        localId,
        original_filename: file.name,
        file_type: file.type,
        parse_status: "pending",
        parse_progress: 0,
        chunk_count: 0,
        uploading: true,
      },
    ]);
    setTip("");
    uploadSelectedFile(file, localId);
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

  const sendTextMessage = async () => {
    const currentMessage = trimmedMessage;
    const attachedFiles = selectedFiles
      .filter((item) => item.material_id)
      .map((item) => ({
        material_id: item.material_id,
        original_filename: item.original_filename,
        file_type: item.file_type,
        parse_status: item.parse_status,
        chunk_count: item.chunk_count,
      }));
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
          subject: normalizeSubject(currentChatSubject),
          grade: user.grade || "",
          major: user.major || "",
          username: user.username,
          session_id: activeSessionId,
          material_ids: attachedFiles.map((item) => item.material_id),
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
          animateTyping: true,
        }),
      ]);
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
      clearAllMaterialPollers();
      setSelectedFiles([]);
    } catch (error) {
      console.error("Failed to send message:", error);
      appendAssistantError("无法连接后端服务。");
    } finally {
      setLoading(false);
    }
  };

  const sendFileMessage = async () => {
    if (!selectedFile || !user?.username) return;

    const currentQuestion = trimmedMessage;
    setLoading(true);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("username", user.username);
    formData.append("subject", normalizeSubject(currentChatSubject));
    formData.append("question", currentQuestion);
    formData.append("save_to_materials", "true");
    if (activeSessionId) {
      formData.append("conversation_id", String(activeSessionId));
    }

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
        const errorMessage = getUploadErrorMessage(res.status, data);
        alert(errorMessage);
        appendAssistantError(errorMessage);
        if (res.status === 401) {
          logout();
        }
        return;
      }

      if (data.message) {
        setMessages((prev) => [...prev, data.message]);
      }

      if (data.answer) {
        setMessages((prev) => [
          ...prev,
          createLocalMessage({
            id: data.assistant_message_id || undefined,
            role: "assistant",
            content: data.answer,
            references: data.references || [],
            animateTyping: true,
          }),
        ]);
      }

      refreshChatSessionState(data.session);
      await loadChatHistory(user);
      await loadMaterials("");

      setMessage("");
      clearAllMaterialPollers();
      setSelectedFiles([]);
      setTip("附件提问已保存到聊天记录，并已加入个人资料库。");
    } catch (error) {
      console.error("Failed to send file message:", error);
      appendAssistantError("上传请求失败，请重试。");
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!user?.username) {
      setTip("请先登录。");
      logout();
      return;
    }

    if (!canSendMessage) {
      if (selectedFilesBlockReason) {
        setTip("请先输入问题后再发送文件。");
      }
      return;
    }

    setTip("");

    if (false) {
      await sendFileMessage();
      return;
    }

    await sendTextMessage();
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

  if (!user) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-badge">AI 学习平台</div>
          <h1>欢迎使用 AI 学习平台</h1>
          <p className="auth-subtitle">
            登录后即可使用个人资料、个人资料库和历史对话。
          </p>

          <div className="tab-row">
            <button
              className={authMode === "login" ? "tab-button active" : "tab-button"}
              onClick={() => {
                setAuthMode("login");
                setTip("");
              }}
            >
              登录
            </button>
            <button
              className={authMode === "register" ? "tab-button active" : "tab-button"}
              onClick={() => {
                setAuthMode("register");
                setTip("");
              }}
            >
              注册
            </button>
          </div>

          <input
            className="field"
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <input
            className="field"
            placeholder="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {tip && <p className="tip-text">{tip}</p>}

          {authMode === "login" ? (
            <button className="primary-button" onClick={handleLogin}>
              登录
            </button>
          ) : (
            <button className="primary-button" onClick={handleRegister}>
              注册
            </button>
          )}
        </div>
      </div>
    );
  }

  if (page === "profile") {
    return (
      <div className="profile-shell profile-shell--wide">
        <div className="profile-card profile-card--wide">
          <div className="profile-header">
            <div className="profile-avatar" style={{ background: selectedAvatar.background }}>
              {selectedAvatar.label}
            </div>
            <div>
              <div className="section-eyebrow">个人资料</div>
              <h1>个人资料</h1>
              <p className="muted-text">{user.username}</p>
            </div>
          </div>

          <div className="profile-grid">
            <section className="profile-settings">
              <div className="avatar-grid">
                {AVATARS.map((avatar) => (
                  <button
                    key={avatar.id}
                    className={
                      profileForm.avatar === avatar.id ? "avatar-chip active" : "avatar-chip"
                    }
                    style={{ background: avatar.background }}
                    onClick={() =>
                      setProfileForm((prev) => ({ ...prev, avatar: avatar.id }))
                    }
                    title={`头像 ${avatar.label}`}
                  >
                    {avatar.label}
                  </button>
                ))}
              </div>

              <label className="field-label">用户名</label>
              <input className="field" value={user.username} disabled />

              <label className="field-label">昵称</label>
              <input
                className="field"
                placeholder="例如：小明"
                value={profileForm.nickname}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))
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

              <label className="field-label">专业</label>
              <input
                className="field"
                placeholder="例如：软件工程"
                value={profileForm.major}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, major: e.target.value }))
                }
              />

              {tip && <p className="tip-text">{tip}</p>}

              <div className="stack-actions">
                <button className="primary-button" onClick={saveProfile} disabled={profileSaving}>
                  {profileSaving ? "保存中..." : "保存个人资料"}
                </button>
                <button className="dark-button" onClick={() => setPage("dashboard")}>
                  进入课程工作台
                </button>
                <button className="dark-button" onClick={() => setPage("chat")}>
                  进入聊天
                </button>
                <button className="ghost-button" onClick={logout}>
                  退出登录
                </button>
              </div>
            </section>

            <section className="profile-library">
              <div className="panel-title-row">
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

              <div className="library-tip">
                已索引的学习资料会在对应学科问答中作为优先参考内容。
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
                  {availableSubjects.length === 0 ? (
                    <option value="">暂无资料</option>
                  ) : (
                    availableSubjects.map((item) => (
                      <option key={item} value={item}>
                        {getSubjectLabel(item)}
                      </option>
                    ))
                  )}
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
                          <div className="history-meta">{formatDate(material.created_at)}</div>
                          <div className="material-actions">
                            <button
                              className="tiny-button"
                              onClick={() => openMaterialDetail(material.id)}
                            >
                              查看
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
                    点击资料卡片上的“查看”可查看摘要和提取文本。
                  </div>
                ) : (
                  <>
                    <div className="detail-meta">
                      <div>文件：{selectedMaterialDetail.original_filename}</div>
                      <div>学科：{getSubjectLabel(selectedMaterialDetail.subject)}</div>
                      <div>类型：{getFileTypeLabel(selectedMaterialDetail.file_type)}</div>
                      <div>上传时间：{formatDate(selectedMaterialDetail.created_at)}</div>
                    </div>
                    <div className="result-block">
                      <strong>摘要</strong>
                      <p>{selectedMaterialDetail.summary}</p>
                    </div>
                    <div className="result-block">
                      <strong>提取文本</strong>
                      <pre>{selectedMaterialDetail.extracted_text}</pre>
                    </div>
                  </>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-shell">
      {sidebarOpen ? (
        <aside className="sidebar-panel">
          <div className="sidebar-top">
            <button
              className="sidebar-toggle-inline"
              onClick={() => setSidebarOpen(false)}
              title="收起侧栏"
            >
              ✕
            </button>
          </div>

          <div className="sidebar-body">
            <label className="field-label">新建对话学科</label>
            <select
              className="field"
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

            <button className="ghost-button" onClick={startNewConversation}>
              新建对话
            </button>
            <button className="ghost-button" onClick={() => setPage("dashboard")}>
              课程工作台
            </button>
            <button className="ghost-button" onClick={() => setPage("profile")}>
              个人资料
            </button>
            <button className="ghost-button" onClick={openLearningRecordPage}>
              学习记录
            </button>

            <div className="history-block">
              <div className="panel-title-row">
                <h3>{getSubjectLabel(subject)} 历史对话</h3>
              </div>

              <div className="history-list">
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
                        onClick={(event) => renameChatSession(session, event)}
                      >
                        编辑标题
                      </button>
                      <button
                        className="tiny-button danger"
                        onClick={(event) => deleteChatSession(session, event)}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="sidebar-footer">
            <button className="ghost-button" onClick={logout}>
              退出登录
            </button>
          </div>
        </aside>
      ) : (
        <div className="sidebar-collapsed-bar">
          <button
            className="sidebar-toggle-inline"
            onClick={() => setSidebarOpen(true)}
            title="展开侧栏"
          >
            ☰
          </button>
        </div>
      )}

      <main className="workspace-main workspace-main--chat-only">
        {page === "dashboard" ? (
          <CourseDashboard
            course={subject}
            courseOptions={COURSE_OPTIONS}
            dashboard={courseDashboardData}
            loading={courseDashboardLoading}
            savingPointKey={courseProgressSavingKey}
            onCourseChange={setSubject}
            onProgressChange={updateCourseProgress}
            onOpenMaterial={(materialId) => openMaterialDetail(materialId, "profile")}
            onOpenChat={openChatSession}
            onStartAsk={() => openChatPageForCourse(subject)}
            onUploadMaterial={() => openMaterialsPageForCourse(subject)}
            onViewMaterials={() => openMaterialsPageForCourse(subject)}
            onViewLearningRecords={() => openLearningRecordPageForCourse(subject)}
            onNewCourseChat={() => openChatPageForCourse(subject, true)}
            getSubjectLabel={getSubjectLabel}
            getFileTypeLabel={getFileTypeLabel}
            formatDate={formatDate}
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
                  <div className="empty-inline">暂无学习记录，先去聊天页收藏一条回答吧。</div>
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
                      <div className="learning-record-meta">
                        <span>{formatDate(record.created_at)}</span>
                        <span>
                          {record.review_status === "reviewed" ? "已复习" : "待复习"}
                        </span>
                      </div>
                      <div className="learning-record-actions">
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
        ) : (
          <section className="chat-panel chat-panel--wide">
            <div className="panel-header panel-header--chat">
              <div className="subject-pill panel-pill">当前对话</div>
              <div className="subject-pill">学科：{getSubjectLabel(currentChatSubject)}</div>
            </div>

            <div className="messages-board">
              {messages.length === 0 && (
                <div className="empty-state">
                  请选择学科后提问，或点击加号上传图片 / PDF 并附上你的问题。
                </div>
              )}

              {messages.map((msg, index) => (
                <ChatMessage
                  key={msg.id || msg.clientId || index}
                  message={msg}
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
                />
              ))}

              {loading && <div className="message-card assistant">正在思考...</div>}
            </div>

            <div className="composer-panel composer-panel--compact">
              {selectedFile && (
                <div className="attachment-chip-row">
                  <div className="attachment-chip">
                    <span className="attachment-chip-label">{fileLabel}</span>
                    <span className="attachment-chip-status">
                      {getSelectedFileStatusText(selectedFile)}
                      {Number(selectedFile.parse_progress || 0) > 0
                        ? ` ${Math.round(Number(selectedFile.parse_progress || 0))}%`
                        : ""}
                    </span>
                    <button
                      className="attachment-chip-remove"
                      onClick={() => removeSelectedFile(selectedFile.localId)}
                      type="button"
                    >
                      ×
                    </button>
                  </div>
                </div>
              )}

              {false && (
                <div className="composer-hint">请先输入问题后再发送文件。</div>
              )}

              {selectedFilesBlockReason && (
                <div className="composer-hint">{selectedFilesBlockReason}</div>
              )}

              <div className="composer-row composer-row--input">
                <button
                  className="attach-button"
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                  title="选择图片或 PDF"
                >
                  +
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
                  onChange={handleFileChange}
                  className="hidden-file-input"
                />

                <input
                  className="field composer-input"
                  placeholder={
                    selectedFile
                      ? "请输入你想针对该文件提问的问题"
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
        )}
      </main>
    </div>
  );
}

export default App;
