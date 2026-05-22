import { useEffect, useMemo, useState } from "react";
import "./App.css";

const USER_STORAGE_KEY = "ai_study_platform_user";
const ACTIVE_SESSION_STORAGE_KEY = "ai_study_platform_active_session_id";
const API_BASE = "/api";

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
  "数据结构",
  "计算机网络",
  "操作系统",
  "数据库",
  "前端开发",
  "后端开发",
  "算法",
];

const EMPTY_UPLOAD_RESULT = {
  extracted_text: "",
  answer: "",
  original_filename: "",
  subject: "",
  file_type: "",
};

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
  const [uploadSubject, setUploadSubject] = useState("Python");
  const [uploadQuestion, setUploadQuestion] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);

  const [messages, setMessages] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSessionSubject, setActiveSessionSubject] = useState("Python");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [tip, setTip] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);

  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [materials, setMaterials] = useState([]);
  const [materialSubjectFilter, setMaterialSubjectFilter] = useState("");
  const [selectedMaterialId, setSelectedMaterialId] = useState(null);
  const [selectedMaterialDetail, setSelectedMaterialDetail] = useState(null);

  const [uploadResult, setUploadResult] = useState(EMPTY_UPLOAD_RESULT);
  const [addToLibraryState, setAddToLibraryState] = useState({
    messageId: null,
    subject: "Python",
    loading: false,
  });

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
    setUploadResult(EMPTY_UPLOAD_RESULT);
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
      throw new Error(data.detail || "加载个人资料失败");
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
        setTip(data.detail || "加载聊天记录失败");
        return;
      }

      setChatSessions(data.sessions || []);
    } catch (error) {
      console.error("加载聊天记录失败:", error);
      setTip("无法加载聊天记录，请确认后端正在运行");
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
        setTip(data.detail || "加载资料库失败");
        return;
      }

      setMaterials(data.materials || []);
    } catch (error) {
      console.error("加载资料库失败:", error);
      setTip("无法加载资料库，请确认后端正在运行");
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
        setTip(data.detail || "加载资料详情失败");
        return;
      }

      setSelectedMaterialId(materialId);
      setSelectedMaterialDetail(data.material || null);
    } catch (error) {
      console.error("加载资料详情失败:", error);
      setTip("无法加载资料详情，请稍后重试");
    }
  };

  const deleteMaterial = async (materialId) => {
    if (!user?.username) return;

    const confirmed = window.confirm("确定要删除这条学习资料吗？");
    if (!confirmed) return;

    try {
      const res = await fetch(
        `${API_BASE}/materials/${materialId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(data.detail || "删除资料失败");
        return;
      }

      setMaterials((prev) => prev.filter((item) => item.id !== materialId));
      if (selectedMaterialId === materialId) {
        setSelectedMaterialId(null);
        setSelectedMaterialDetail(null);
      }
      setMessages((prev) =>
        prev.map((msg) => (msg.material_id === materialId ? { ...msg, material_id: null } : msg))
      );
    } catch (error) {
      console.error("删除资料失败:", error);
      setTip("无法删除资料，请稍后重试");
    }
  };

  const openChatSession = async (session) => {
    if (!user?.username) {
      setTip("请先登录后再查看聊天记录");
      return;
    }

    try {
      const res = await fetch(
        `${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(data.detail || "加载该聊天记录失败");
        return;
      }

      const sessionSubject = data.session.subject || data.session.course || "Python";
      setActiveSessionId(session.id);
      setActiveSessionSubject(sessionSubject);
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(session.id));
      setSubject(sessionSubject);
      setUploadSubject(sessionSubject);
      setMessages(data.messages || []);
      setUploadResult(EMPTY_UPLOAD_RESULT);
      setPage("chat");
    } catch (error) {
      console.error("加载聊天记录失败:", error);
      setTip("无法加载该聊天记录，请确认后端正在运行");
    }
  };

  const deleteChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      setTip("请先登录后再删除聊天记录");
      return;
    }

    const confirmed = window.confirm(`确定要删除「${session.title}」吗？`);
    if (!confirmed) return;

    try {
      const res = await fetch(
        `${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await res.json();

      if (!res.ok) {
        setTip(data.detail || "删除聊天记录失败");
        return;
      }

      setChatSessions((prev) => prev.filter((item) => item.id !== session.id));

      if (activeSessionId === session.id) {
        setMessages([]);
        setActiveSessionId(null);
        setActiveSessionSubject(subject);
        localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      }
    } catch (error) {
      console.error("删除聊天记录失败:", error);
      setTip("无法删除聊天记录，请确认后端正在运行");
    }
  };

  const renameChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      alert("请先登录后再重命名历史对话");
      return;
    }

    const inputTitle = window.prompt("请输入新的对话标题", session.title || "");
    if (inputTitle === null) return;

    const title = inputTitle.trim();
    if (!title) return;

    try {
      const res = await fetch(
        `${API_BASE}/conversations/${session.id}?username=${encodeURIComponent(user.username)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title }),
        }
      );
      const data = await res.json();

      if (!res.ok) {
        alert(data.detail || "重命名历史对话失败");
        return;
      }

      setChatSessions((prev) =>
        prev.map((item) => (item.id === session.id ? { ...item, title: data.title } : item))
      );
    } catch (error) {
      console.error("重命名历史对话失败:", error);
      alert("无法重命名历史对话，请确认后端正在运行");
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
          `${API_BASE}/chat/sessions/${savedSessionId}?username=${encodeURIComponent(user.username)}`
        );
        const data = await res.json();

        if (!res.ok) {
          localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
          setActiveSessionId(null);
          setMessages([]);
          return;
        }

        const sessionSubject = data.session.subject || data.session.course || "Python";
        setActiveSessionId(data.session.id);
        setActiveSessionSubject(sessionSubject);
        setSubject(sessionSubject);
        setUploadSubject(sessionSubject);
        setMessages(data.messages || []);
      } catch (error) {
        console.error("恢复当前聊天失败:", error);
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
          setTip(data.detail || "登录状态已失效，请重新登录");
          return;
        }

        const checkedUser = data.user || savedUser;
        saveLoginUser(checkedUser);
        await loadProfile(checkedUser);
        setPage("profile");
      } catch (error) {
        console.error("登录状态校验失败:", error);
      }
    };

    checkLoginStatus();
  }, []);

  const handleRegister = async () => {
    setTip("");

    if (!username.trim() || !password.trim()) {
      setTip("请填写账号和密码");
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
        setTip(data.detail || "注册失败");
        return;
      }

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      setPage("profile");
      setTip("注册成功，请完善个人资料");
    } catch (error) {
      console.error("注册错误:", error);
      setTip("无法连接后端，请确认 FastAPI 正在运行");
    }
  };

  const handleLogin = async () => {
    setTip("");

    if (!username.trim() || !password.trim()) {
      setTip("请输入用户名和密码");
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
        setTip(data.detail || "登录失败");
        return;
      }

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      await loadProfile(loginUser);
      setPage("profile");
      setTip("");
    } catch (error) {
      console.error("登录错误:", error);
      setTip("无法连接后端，请确认 FastAPI 正在运行");
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
        setTip(data.detail || "保存个人资料失败");
        return;
      }

      saveLoginUser(data.profile);
      setTip("个人资料已保存");
    } catch (error) {
      console.error("保存个人资料失败:", error);
      setTip("无法保存个人资料，请确认后端正在运行");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    const allowedTypes = [
      "application/pdf",
      "image/png",
      "image/jpeg",
      "image/webp",
    ];

    if (!allowedTypes.includes(file.type)) {
      alert("文件类型不支持，请选择 PDF、PNG、JPG/JPEG 或 WEBP 文件");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert("文件不能超过 10MB");
      return;
    }

    setSelectedFile(file);
  };

  const getUploadErrorMessage = (status, data) => {
    if (status === 400) return data.detail || "上传文件不符合要求，请检查文件类型、大小和学科";
    if (status === 401) return "登录状态失效，请重新登录";
    if (status === 413) return "文件太大，请上传 10MB 以内的文件";
    if (status === 422) return "上传参数错误，请重新选择文件后再试";
    if (status === 500) return data.detail || "后端处理文件失败，请稍后重试";
    if (status === 502) return "服务器网关错误，后端服务可能未启动";
    return data.detail || `上传失败，HTTP 状态码：${status}`;
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

  const sendMessage = async () => {
    if (!message.trim()) return;

    if (!user?.username) {
      setTip("请先登录后再使用 AI 聊天");
      logout();
      return;
    }

    const currentMessage = message.trim();
    setMessages((prev) => [...prev, { role: "user", content: currentMessage }]);
    setLoading(true);
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          subject,
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
          setTip(data.detail || "登录状态无效，请重新登录");
        }
        appendAssistantError(data.detail || "AI 回复失败");
        return;
      }

      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
    } catch (error) {
      console.error("发送消息失败:", error);
      appendAssistantError("无法连接后端，请确认 FastAPI 正在运行");
    } finally {
      setLoading(false);
    }
  };

  const sendMaterialUpload = async () => {
    if (!selectedFile || !user?.username) return;

    const currentSessionId = activeSessionId;
    const effectiveQuestion = uploadQuestion.trim();

    setLoading(true);
    setUploadResult(EMPTY_UPLOAD_RESULT);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("username", user.username);
    formData.append("subject", uploadSubject);
    formData.append("question", effectiveQuestion);
    formData.append("save_to_materials", "false");
    if (currentSessionId) {
      formData.append("conversation_id", String(currentSessionId));
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
        if (effectiveQuestion) {
          appendAssistantError(errorMessage);
        } else {
          setTip(errorMessage);
        }
        if (res.status === 401) {
          logout();
        }
        return;
      }

      setUploadResult({
        extracted_text:
          data.message?.extracted_text || data.extracted_text_preview || "",
        answer: data.answer || "",
        original_filename:
          data.message?.attachment_filename || selectedFile.name,
        subject: uploadSubject,
        file_type: data.message?.attachment_type || "",
      });

      if (data.message) {
        setMessages((prev) => [...prev, data.message]);
      }

      if (data.answer) {
        setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
      }

      refreshChatSessionState(data.session);
      await loadChatHistory(user);

      setSelectedFile(null);
      setUploadQuestion("");
    } catch (error) {
      console.error("文件上传失败:", error);
      const errorMessage = "上传请求失败，请检查网络或稍后重试";
      alert(errorMessage);
      if (effectiveQuestion) {
        appendAssistantError(errorMessage);
      } else {
        setTip(errorMessage);
      }
    } finally {
      setLoading(false);
    }
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
        setTip(data.detail || "加入资料库失败");
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
      console.error("加入资料库失败:", error);
      setTip("无法加入资料库，请稍后重试");
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
    setUploadResult(EMPTY_UPLOAD_RESULT);
    localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  };

  const groupedMaterials = useMemo(() => {
    return SUBJECT_OPTIONS.map((item) => ({
      subject: item,
      items: materials.filter((material) => material.subject === item),
    })).filter((group) => group.items.length > 0 || !materialSubjectFilter || materialSubjectFilter === group.subject);
  }, [materials, materialSubjectFilter]);

  const selectedAvatar =
    AVATARS.find((avatar) => avatar.id === profileForm.avatar) || AVATARS[0];

  if (!user) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-badge">AI Study Platform</div>
          <h1>你的 AI 学习平台</h1>
          <p className="auth-subtitle">登录后进入个人主页、学习资料库和历史对话。</p>

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
            placeholder="账号"
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
              <div className="section-eyebrow">Profile</div>
              <h1>个人主页</h1>
              <p className="muted-text">{user.username}</p>
            </div>
          </div>

          <div className="profile-grid">
            <section className="profile-settings">
              <div className="avatar-grid">
                {AVATARS.map((avatar) => (
                  <button
                    key={avatar.id}
                    className={profileForm.avatar === avatar.id ? "avatar-chip active" : "avatar-chip"}
                    style={{ background: avatar.background }}
                    onClick={() => setProfileForm((prev) => ({ ...prev, avatar: avatar.id }))}
                    title={avatar.id}
                  >
                    {avatar.label}
                  </button>
                ))}
              </div>

              <label className="field-label">账号</label>
              <input className="field" value={user.username} disabled />

              <label className="field-label">昵称</label>
              <input
                className="field"
                placeholder="例如：小明"
                value={profileForm.nickname}
                onChange={(e) => setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))}
              />

              <label className="field-label">年级</label>
              <input
                className="field"
                placeholder="例如：大二"
                value={profileForm.grade}
                onChange={(e) => setProfileForm((prev) => ({ ...prev, grade: e.target.value }))}
              />

              <label className="field-label">专业</label>
              <input
                className="field"
                placeholder="例如：软件工程"
                value={profileForm.major}
                onChange={(e) => setProfileForm((prev) => ({ ...prev, major: e.target.value }))}
              />

              {tip && <p className="tip-text">{tip}</p>}

              <div className="stack-actions">
                <button className="primary-button" onClick={saveProfile} disabled={profileSaving}>
                  {profileSaving ? "保存中..." : "保存个人信息"}
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
                  <div className="section-eyebrow">Library</div>
                  <h2>我的学习资料库</h2>
                </div>
                <button
                  className="ghost-button compact"
                  onClick={() => loadMaterials(materialSubjectFilter)}
                >
                  刷新
                </button>
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
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              {materialsLoading ? (
                <div className="empty-inline">资料加载中...</div>
              ) : groupedMaterials.length === 0 || groupedMaterials.every((group) => group.items.length === 0) ? (
                <div className="empty-inline">还没有学习资料。你可以先去聊天页上传图片或 PDF。</div>
              ) : (
                <div className="library-groups">
                  {groupedMaterials.map((group) => (
                    <div key={group.subject} className="library-group">
                      <div className="library-group-title">{group.subject}</div>
                      <div className="material-list material-list--profile">
                        {group.items.map((material) => (
                          <div key={material.id} className="material-item material-item--profile">
                            <div className="material-item-head">
                              <span className="subject-pill small">{material.subject}</span>
                              <span className="muted-text">{material.file_type}</span>
                            </div>
                            <div className="material-title">{material.original_filename}</div>
                            <div className="material-summary">{material.summary}</div>
                            <div className="history-meta">{formatDate(material.created_at)}</div>
                            <div className="material-actions">
                              <button
                                className="tiny-button"
                                onClick={() => loadMaterialDetail(material.id)}
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
                  <div className="empty-inline">点击资料卡片的“查看”按钮查看完整提取文本和摘要</div>
                ) : (
                  <>
                    <div className="detail-meta">
                      <div>文件：{selectedMaterialDetail.original_filename}</div>
                      <div>学科：{selectedMaterialDetail.subject}</div>
                      <div>类型：{selectedMaterialDetail.file_type}</div>
                      <div>上传时间：{formatDate(selectedMaterialDetail.created_at)}</div>
                    </div>
                    <div className="result-block">
                      <strong>摘要</strong>
                      <p>{selectedMaterialDetail.summary}</p>
                    </div>
                    <div className="result-block">
                      <strong>完整提取文本</strong>
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
              <div className="section-eyebrow">Study Hub</div>
              <h2>AI 学习助手</h2>
            </div>
            <p className="muted-text">{user.username}</p>
          </div>

          <div className="sidebar-user-card">
            <div>年级：{user.grade || "未填写"}</div>
            <div>专业：{user.major || "未填写"}</div>
          </div>

          <label className="field-label">新对话学科</label>
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
                {item}
              </option>
            ))}
          </select>

          <button className="ghost-button" onClick={startNewConversation}>
            新建对话
          </button>
          <button className="ghost-button" onClick={() => setPage("profile")}>
            个人主页
          </button>

          <div className="history-block">
            <div className="panel-title-row">
              <h3>历史对话</h3>
            </div>

            <div className="history-list">
              {chatSessions.length === 0 && <div className="empty-inline">暂无历史记录</div>}

              {chatSessions.map((session) => (
                <div
                  key={session.id}
                  className={activeSessionId === session.id ? "history-item active" : "history-item"}
                  onClick={() => openChatSession(session)}
                >
                  <div className="history-subject">{session.subject || session.course}</div>
                  <div className="history-title">{session.title}</div>
                  <div className="history-meta">{formatDate(session.created_at)}</div>
                  <div className="history-actions">
                    <button
                      className="tiny-button"
                      onClick={(event) => renameChatSession(session, event)}
                    >
                      编辑
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
              <div className="section-eyebrow">Conversation</div>
              <h2>当前对话</h2>
            </div>
            <div className="subject-pill">
              学科：{activeSessionId ? activeSessionSubject : subject}
            </div>
          </div>

          <div className="chat-upload-card">
            <div className="panel-title-row">
              <h3>图片 / PDF 问答</h3>
              <span className="muted-text">上传后会保留在聊天和历史记录中</span>
            </div>

            <label className="field-label">学科</label>
            <select className="field" value={uploadSubject} onChange={(e) => setUploadSubject(e.target.value)}>
              {SUBJECT_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <label className="field-label">问题（可选）</label>
            <input
              className="field"
              placeholder="例如：请解释这页笔记的核心知识点"
              value={uploadQuestion}
              onChange={(e) => setUploadQuestion(e.target.value)}
            />

            <div className="upload-actions">
              <label className="file-trigger">
                选择图片或 PDF
                <input
                  type="file"
                  accept=".pdf,image/png,image/jpeg,image/webp"
                  onChange={handleFileChange}
                  hidden
                />
              </label>
              {selectedFile && <span className="selected-file-name">{selectedFile.name}</span>}
              <button
                className="primary-button compact"
                onClick={sendMaterialUpload}
                disabled={loading || !selectedFile}
              >
                上传
              </button>
            </div>
          </div>

          <div className="messages-board">
            {messages.length === 0 && (
              <div className="empty-state">
                选择学科后开始提问，或者上传图片/PDF 进行问答。附件不会自动进资料库，可在消息里手动加入。
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={msg.id || index} className={msg.role === "user" ? "message-card user" : "message-card assistant"}>
                <div className="message-role">{msg.role === "user" ? "你" : "AI"}</div>
                <div className="message-text">{msg.content}</div>

                {msg.attachment_type && (
                  <div className="attachment-card">
                    <div className="attachment-meta">
                      <span className="subject-pill small">{msg.attachment_type}</span>
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
                              : activeSessionSubject || subject
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
                              {item}
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
                                : activeSessionSubject || subject
                            )
                          }
                          disabled={
                            addToLibraryState.loading && addToLibraryState.messageId === msg.id
                          }
                        >
                          {addToLibraryState.loading && addToLibraryState.messageId === msg.id
                            ? "加入中..."
                            : "加入资料库"}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && <div className="message-card assistant">AI 正在思考...</div>}
          </div>

          {(uploadResult.extracted_text || uploadResult.answer) && (
            <div className="result-card">
              <div className="panel-title-row">
                <h3>最近上传结果</h3>
                <span className="muted-text">
                  {uploadResult.original_filename} · {uploadResult.subject}
                </span>
              </div>
              <div className="result-block">
                <strong>提取文本预览</strong>
                <pre>{uploadResult.extracted_text || "暂无提取文本"}</pre>
              </div>
              {uploadResult.answer && (
                <div className="result-block">
                  <strong>AI 回答</strong>
                  <p>{uploadResult.answer}</p>
                </div>
              )}
            </div>
          )}

          <div className="composer-panel">
            <div className="composer-row">
              <input
                className="field"
                placeholder="输入你的问题..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
              />
              <button className="primary-button compact" onClick={sendMessage} disabled={loading}>
                发送
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
