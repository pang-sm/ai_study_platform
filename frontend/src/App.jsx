import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const USER_STORAGE_KEY = "ai_study_platform_user";
const ACTIVE_SESSION_STORAGE_KEY = "ai_study_platform_active_session_id";
const API_BASE = "/api";
const MAX_FILE_SIZE = 10 * 1024 * 1024;

const AVATARS = [
  { id: "avatar_1", label: "A1", background: "#2563eb" },
  { id: "avatar_2", label: "A2", background: "#059669" },
  { id: "avatar_3", label: "A3", background: "#7c3aed" },
  { id: "avatar_4", label: "A4", background: "#db2777" },
  { id: "avatar_5", label: "A5", background: "#ea580c" },
  { id: "avatar_6", label: "A6", background: "#0f766e" },
];

const SUBJECT_OPTIONS = [
  "Python",
  "Java",
  "Data Structures",
  "Computer Networks",
  "Operating Systems",
  "Databases",
  "Frontend Development",
  "Backend Development",
  "Algorithms",
];

const SUBJECT_LABELS = {
  Python: "Python",
  Java: "Java",
  "Data Structures": "数据结构",
  "Computer Networks": "计算机网络",
  "Operating Systems": "操作系统",
  Databases: "数据库",
  "Frontend Development": "前端开发",
  "Backend Development": "后端开发",
  Algorithms: "算法",
};

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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getSubjectLabel(subject) {
  return SUBJECT_LABELS[subject] || subject || "";
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

  const [subject, setSubject] = useState("Python");
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSessionSubject, setActiveSessionSubject] = useState("Python");
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
  const [addToLibraryState, setAddToLibraryState] = useState({
    messageId: null,
    subject: "Python",
    loading: false,
  });

  const fileInputRef = useRef(null);

  const currentChatSubject = activeSessionId ? activeSessionSubject : subject;
  const trimmedMessage = message.trim();
  const trimmedMaterialSearchQuery = materialSearchQuery.trim();
  const selectedAvatar =
    AVATARS.find((avatar) => avatar.id === profileForm.avatar) || AVATARS[0];

  const visibleSessions = useMemo(() => {
    return chatSessions.filter(
      (session) => (session.subject || session.course || "") === subject
    );
  }, [chatSessions, subject]);

  const groupedMaterials = useMemo(() => {
    return SUBJECT_OPTIONS.map((item) => ({
      subject: item,
      items: materials.filter((material) => material.subject === item),
    })).filter(
      (group) =>
        group.items.length > 0 ||
        !materialSubjectFilter ||
        materialSubjectFilter === group.subject
    );
  }, [materials, materialSubjectFilter]);

  const canSendMessage = useMemo(() => {
    if (loading) return false;
    if (selectedFile) return Boolean(trimmedMessage);
    return Boolean(trimmedMessage);
  }, [loading, selectedFile, trimmedMessage]);

  const fileLabel = selectedFile
    ? selectedFile.type === "application/pdf"
      ? `PDF：${selectedFile.name}`
      : `图片：${selectedFile.name}`
    : "";

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
    setSelectedFile(null);
    setMessage("");
    setMaterialSearchQuery("");
    setMaterialSearchTriggered(false);
    setMaterialSearchResults([]);
    setMaterialSearchLoading(false);
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
        query.set("subject", targetSubject);
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
        query.set("subject", targetSubject);
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

      const sessionSubject = data.session.subject || data.session.course || subject;
      setActiveSessionId(session.id);
      setActiveSessionSubject(sessionSubject);
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(session.id));
      setSubject(sessionSubject);
      setMessages(data.messages || []);
      setSelectedFile(null);
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
        setActiveSessionSubject(subject);
        setSelectedFile(null);
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
      loadChatHistory(user);
      loadMaterials(materialSubjectFilter);
    }
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

        const sessionSubject = data.session.subject || data.session.course || subject;
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

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      alert("不支持的文件类型，请选择 PDF、PNG、JPG/JPEG 或 WEBP。");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      alert("文件大小不能超过 10MB。");
      return;
    }

    setSelectedFile(file);
    setTip("");
  };

  const removeSelectedFile = () => {
    setSelectedFile(null);
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
    setMessages((prev) => [...prev, { role: "assistant", content }]);
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
    setMessages((prev) => [...prev, { role: "user", content: currentMessage }]);
    setLoading(true);
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          subject: currentChatSubject,
          grade: user.grade || "",
          major: user.major || "",
          username: user.username,
          session_id: activeSessionId,
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
        {
          role: "assistant",
          content: data.answer,
          references: data.references || [],
        },
      ]);
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
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
    formData.append("subject", currentChatSubject);
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
          {
            role: "assistant",
            content: data.answer,
            references: data.references || [],
          },
        ]);
      }

      refreshChatSessionState(data.session);
      await loadChatHistory(user);
      await loadMaterials(materialSubjectFilter);

      setMessage("");
      setSelectedFile(null);
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
      if (selectedFile && !trimmedMessage) {
        setTip("请先输入问题后再发送文件。");
      }
      return;
    }

    setTip("");

    if (selectedFile) {
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
      subject: selectedSubject,
      loading: true,
    }));

    try {
      const res = await fetch(`${API_BASE}/materials/add-from-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          message_id: messageItem.id,
          subject: selectedSubject,
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
        await loadMaterials(materialSubjectFilter);
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
    setActiveSessionSubject(subject);
    setSelectedFile(null);
    setMessage("");
    setTip("");
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
                  <h2>我的资料</h2>
                </div>
                <div className="header-actions">
                  <button
                    className="ghost-button compact"
                    onClick={reindexLibrary}
                    disabled={reindexLoading}
                  >
                    {reindexLoading ? "重建索引中..." : "重建索引"}
                  </button>
                  <button
                    className="ghost-button compact"
                    onClick={() => loadMaterials(materialSubjectFilter)}
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
                  value={materialSubjectFilter}
                  onChange={(e) => {
                    const next = e.target.value;
                    setMaterialSubjectFilter(next);
                    loadMaterials(next);
                  }}
                >
                  <option value="">全部学科</option>
                  {SUBJECT_OPTIONS.map((item) => (
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
                    placeholder="搜索我的资料..."
                    value={materialSearchQuery}
                    onChange={(e) => handleMaterialSearchChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        searchMaterials(materialSearchQuery, materialSubjectFilter);
                      }
                    }}
                  />
                  <button
                    className="ghost-button compact"
                    onClick={() => searchMaterials(materialSearchQuery, materialSubjectFilter)}
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
                  <div className="empty-inline">未找到相关资料。</div>
                ) : (
                  <div className="search-results">
                    {materialSearchResults.map((item) => (
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
                  </div>
                )
              ) : materialsLoading ? (
                <div className="empty-inline">资料加载中...</div>
              ) : groupedMaterials.length === 0 ||
                groupedMaterials.every((group) => group.items.length === 0) ? (
                <div className="empty-inline">
                  暂无资料，请先在聊天页上传图片或 PDF。
                </div>
              ) : (
                <div className="library-groups">
                  {groupedMaterials.map((group) => (
                    <div key={group.subject} className="library-group">
                      <div className="library-group-title">{getSubjectLabel(group.subject)}</div>
                      <div className="material-list material-list--profile">
                        {group.items.map((material) => (
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
                    </div>
                  ))}
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
      <button className="sidebar-toggle" onClick={() => setSidebarOpen((prev) => !prev)}>
        {sidebarOpen ? "收起" : "展开"}
      </button>

      {sidebarOpen && (
        <aside className="sidebar-panel">
          <div className="sidebar-top">
            <div>
              <div className="section-eyebrow">学习中心</div>
              <h2>AI 学习助手</h2>
            </div>
            <p className="muted-text">{user.username}</p>
          </div>

          <div className="sidebar-user-card">
            <div>年级：{user.grade || "未设置"}</div>
            <div>专业：{user.major || "未设置"}</div>
          </div>

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
            {SUBJECT_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>

          <button className="ghost-button" onClick={startNewConversation}>
            新建对话
          </button>
          <button className="ghost-button" onClick={() => setPage("profile")}>
            个人资料
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

          <button className="ghost-button" onClick={logout}>
            退出登录
          </button>
        </aside>
      )}

      <main className="workspace-main workspace-main--chat-only">
        <section className="chat-panel chat-panel--wide">
          <div className="panel-header">
            <div>
              <div className="section-eyebrow">对话</div>
              <h2>当前对话</h2>
            </div>
            <div className="subject-pill">学科：{getSubjectLabel(currentChatSubject)}</div>
          </div>

          <div className="context-banner">
            当前对话会优先参考你在 {getSubjectLabel(currentChatSubject)} 学科下的个人资料。
          </div>

          <div className="messages-board">
            {messages.length === 0 && (
              <div className="empty-state">
                请选择学科后提问，或点击加号上传图片 / PDF 并附上你的问题。
              </div>
            )}

            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className={msg.role === "user" ? "message-card user" : "message-card assistant"}
              >
                <div className="message-role">{msg.role === "user" ? "我" : "AI"}</div>
                <div className="message-text">{msg.content}</div>

                {msg.attachment_type && (
                  <div className="attachment-card">
                    <div className="attachment-meta">
                      <span className="subject-pill small">
                        {getFileTypeLabel(msg.attachment_type)}
                      </span>
                      <span>{msg.attachment_filename || "未命名附件"}</span>
                    </div>
                    {msg.extracted_text && (
                      <div className="attachment-preview">
                        {msg.extracted_text.slice(0, 240)}
                        {msg.extracted_text.length > 240 ? "..." : ""}
                      </div>
                    )}

                    {msg.material_id ? (
                      <button className="ghost-button compact" disabled>
                        已加入资料库
                      </button>
                    ) : (
                      <div className="attachment-actions">
                        <select
                          className="field attachment-subject-select"
                          value={
                            addToLibraryState.messageId === msg.id
                              ? addToLibraryState.subject
                              : currentChatSubject
                          }
                          onChange={(e) =>
                            setAddToLibraryState((prev) => ({
                              ...prev,
                              messageId: msg.id,
                              subject: e.target.value,
                            }))
                          }
                        >
                          {SUBJECT_OPTIONS.map((item) => (
                            <option key={item} value={item}>
                              {getSubjectLabel(item)}
                            </option>
                          ))}
                        </select>
                        <button
                          className="tiny-button"
                          onClick={() =>
                            addMessageToLibrary(
                              msg,
                              addToLibraryState.messageId === msg.id
                                ? addToLibraryState.subject
                                : currentChatSubject
                            )
                          }
                          disabled={
                            addToLibraryState.loading && addToLibraryState.messageId === msg.id
                          }
                        >
                          {addToLibraryState.loading && addToLibraryState.messageId === msg.id
                            ? "添加中..."
                            : "加入资料库"}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {msg.role === "assistant" &&
                  Array.isArray(msg.references) &&
                  msg.references.length > 0 && (
                    <div className="reference-section">
                      <div className="reference-title">参考资料</div>
                      <div className="reference-list">
                        {msg.references.map((reference, referenceIndex) => (
                          <div
                            key={`${reference.material_id}-${referenceIndex}`}
                            className="reference-card"
                          >
                            <div className="reference-name">
                              {referenceIndex + 1}. {reference.filename}
                            </div>
                            <div className="reference-meta">
                              学科：{getSubjectLabel(reference.subject)} | 类型：
                              {getFileTypeLabel(reference.file_type)}
                            </div>
                            <div className="reference-snippet">
                              命中片段：{getReferenceSnippet(reference)}
                            </div>
                            <button
                              className="tiny-button"
                              onClick={() => openMaterialDetail(reference.material_id, "profile")}
                            >
                              查看资料
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            ))}

            {loading && <div className="message-card assistant">正在思考...</div>}
          </div>

          <div className="composer-panel composer-panel--compact">
            {selectedFile && (
              <div className="attachment-chip-row">
                <div className="attachment-chip">
                  <span className="attachment-chip-label">{fileLabel}</span>
                  <button
                    className="attachment-chip-remove"
                    onClick={removeSelectedFile}
                    type="button"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}

            {selectedFile && !trimmedMessage && (
              <div className="composer-hint">请先输入问题后再发送文件。</div>
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
                accept=".pdf,image/png,image/jpeg,image/webp"
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
      </main>
    </div>
  );
}

export default App;
