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
      ? `PDF: ${selectedFile.name}`
      : `Image: ${selectedFile.name}`
    : "";

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
        setTip(data.detail || "Failed to load chat history");
        return;
      }

      setChatSessions(data.sessions || []);
    } catch (error) {
      console.error("Failed to load chat history:", error);
      setTip("Cannot load chat history. Please check the backend.");
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
        setTip(data.detail || "Failed to load materials");
        return;
      }

      setMaterials(data.materials || []);
    } catch (error) {
      console.error("Failed to load materials:", error);
      setTip("Cannot load materials. Please check the backend.");
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
        setTip(data.detail || "Failed to load material detail");
        return;
      }

      setSelectedMaterialId(materialId);
      setSelectedMaterialDetail(data.material || null);
    } catch (error) {
      console.error("Failed to load material detail:", error);
      setTip("Cannot load material detail right now.");
    }
  };

  const deleteMaterial = async (materialId) => {
    if (!user?.username) return;

    const confirmed = window.confirm("Delete this study material?");
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
        setTip(data.detail || "Failed to delete material");
        return;
      }

      setMaterials((prev) => prev.filter((item) => item.id !== materialId));
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
      setTip("Cannot delete this material right now.");
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
        setTip(data.detail || "Failed to rebuild indexes");
        return;
      }

      setTip(
        `Indexes rebuilt: ${data.indexed_material_count} materials, ${data.indexed_chunk_count} chunks.`
      );
    } catch (error) {
      console.error("Failed to rebuild indexes:", error);
      setTip("Cannot rebuild indexes right now.");
    } finally {
      setReindexLoading(false);
    }
  };

  const openChatSession = async (session) => {
    if (!user?.username) {
      setTip("Please log in first.");
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
        setTip(data.detail || "Failed to open chat session");
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
      setTip("Cannot open this chat session right now.");
    }
  };

  const deleteChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      setTip("Please log in first.");
      return;
    }

    const confirmed = window.confirm(`Delete "${session.title}"?`);
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
        setTip(data.detail || "Failed to delete chat session");
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
      setTip("Cannot delete this chat session right now.");
    }
  };

  const renameChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user?.username) {
      alert("Please log in first.");
      return;
    }

    const inputTitle = window.prompt("Enter a new title", session.title || "");
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
        alert(data.detail || "Failed to rename chat session");
        return;
      }

      setChatSessions((prev) =>
        prev.map((item) =>
          item.id === session.id ? { ...item, title: data.title } : item
        )
      );
    } catch (error) {
      console.error("Failed to rename chat session:", error);
      alert("Cannot rename this chat session right now.");
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
          setTip(data.detail || "Login expired. Please log in again.");
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
      setTip("Please enter username and password.");
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
        setTip(data.detail || "Register failed");
        return;
      }

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      setPage("profile");
      setTip("Registration successful. Please complete your profile.");
    } catch (error) {
      console.error("Register failed:", error);
      setTip("Cannot reach the backend.");
    }
  };

  const handleLogin = async () => {
    setTip("");

    if (!username.trim() || !password.trim()) {
      setTip("Please enter username and password.");
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
        setTip(data.detail || "Login failed");
        return;
      }

      const loginUser = data.user || { username: data.username || username };
      saveLoginUser(loginUser);
      await loadProfile(loginUser);
      setPage("profile");
      setTip("");
    } catch (error) {
      console.error("Login failed:", error);
      setTip("Cannot reach the backend.");
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
        setTip(data.detail || "Failed to save profile");
        return;
      }

      saveLoginUser(data.profile);
      setTip("Profile saved.");
    } catch (error) {
      console.error("Failed to save profile:", error);
      setTip("Cannot save your profile right now.");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    if (!ALLOWED_FILE_TYPES.includes(file.type)) {
      alert("Unsupported file type. Please choose PDF, PNG, JPG/JPEG, or WEBP.");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      alert("File size must be 10MB or smaller.");
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
      return data.detail || "Upload rejected. Check file type, size, and subject.";
    }
    if (status === 401) return "Login expired. Please log in again.";
    if (status === 413) return "File too large. Please upload a file under 10MB.";
    if (status === 422) return "Upload parameters are invalid. Please try again.";
    if (status === 500) return data.detail || "The backend could not process this file.";
    if (status === 502) return "Gateway error. The backend service may be unavailable.";
    return data.detail || `Upload failed. HTTP status: ${status}`;
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
          setTip(data.detail || "Login expired. Please log in again.");
        }
        appendAssistantError(data.detail || "AI reply failed.");
        return;
      }

      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
      refreshChatSessionState(data.session);
      await loadChatHistory(user);
    } catch (error) {
      console.error("Failed to send message:", error);
      appendAssistantError("Cannot reach the backend.");
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
        setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
      }

      refreshChatSessionState(data.session);
      await loadChatHistory(user);
      await loadMaterials(materialSubjectFilter);

      setMessage("");
      setSelectedFile(null);
      setTip("Attachment question saved to chat history and added to your library.");
    } catch (error) {
      console.error("Failed to send file message:", error);
      appendAssistantError("Upload request failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!user?.username) {
      setTip("Please log in first.");
      logout();
      return;
    }

    if (!canSendMessage) {
      if (selectedFile && !trimmedMessage) {
        setTip("Please enter a question before sending the file.");
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
        setTip(data.detail || "Failed to add this attachment to the library");
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
      setTip("Cannot add this attachment right now.");
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
          <div className="auth-badge">AI Study Platform</div>
          <h1>Your AI Study Platform</h1>
          <p className="auth-subtitle">
            Log in to access your profile, library, and chat history.
          </p>

          <div className="tab-row">
            <button
              className={authMode === "login" ? "tab-button active" : "tab-button"}
              onClick={() => {
                setAuthMode("login");
                setTip("");
              }}
            >
              Login
            </button>
            <button
              className={authMode === "register" ? "tab-button active" : "tab-button"}
              onClick={() => {
                setAuthMode("register");
                setTip("");
              }}
            >
              Register
            </button>
          </div>

          <input
            className="field"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <input
            className="field"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {tip && <p className="tip-text">{tip}</p>}

          {authMode === "login" ? (
            <button className="primary-button" onClick={handleLogin}>
              Login
            </button>
          ) : (
            <button className="primary-button" onClick={handleRegister}>
              Register
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
              <h1>Personal Profile</h1>
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
                    title={avatar.id}
                  >
                    {avatar.label}
                  </button>
                ))}
              </div>

              <label className="field-label">Account</label>
              <input className="field" value={user.username} disabled />

              <label className="field-label">Nickname</label>
              <input
                className="field"
                placeholder="For example: Alex"
                value={profileForm.nickname}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))
                }
              />

              <label className="field-label">Grade</label>
              <input
                className="field"
                placeholder="For example: Sophomore"
                value={profileForm.grade}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, grade: e.target.value }))
                }
              />

              <label className="field-label">Major</label>
              <input
                className="field"
                placeholder="For example: Software Engineering"
                value={profileForm.major}
                onChange={(e) =>
                  setProfileForm((prev) => ({ ...prev, major: e.target.value }))
                }
              />

              {tip && <p className="tip-text">{tip}</p>}

              <div className="stack-actions">
                <button className="primary-button" onClick={saveProfile} disabled={profileSaving}>
                  {profileSaving ? "Saving..." : "Save Profile"}
                </button>
                <button className="dark-button" onClick={() => setPage("chat")}>
                  Open Chat
                </button>
                <button className="ghost-button" onClick={logout}>
                  Log Out
                </button>
              </div>
            </section>

            <section className="profile-library">
              <div className="panel-title-row">
                <div>
                  <div className="section-eyebrow">Library</div>
                  <h2>My Study Library</h2>
                </div>
                <div className="header-actions">
                  <button
                    className="ghost-button compact"
                    onClick={reindexLibrary}
                    disabled={reindexLoading}
                  >
                    {reindexLoading ? "Reindexing..." : "Rebuild Index"}
                  </button>
                  <button
                    className="ghost-button compact"
                    onClick={() => loadMaterials(materialSubjectFilter)}
                  >
                    Refresh
                  </button>
                </div>
              </div>

              <div className="library-tip">
                Indexed study materials can be used as subject-specific background for answers.
              </div>

              <div className="library-filter-row">
                <label className="field-label">Filter by subject</label>
                <select
                  className="field"
                  value={materialSubjectFilter}
                  onChange={(e) => {
                    const next = e.target.value;
                    setMaterialSubjectFilter(next);
                    loadMaterials(next);
                  }}
                >
                  <option value="">All subjects</option>
                  {SUBJECT_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              {materialsLoading ? (
                <div className="empty-inline">Loading materials...</div>
              ) : groupedMaterials.length === 0 ||
                groupedMaterials.every((group) => group.items.length === 0) ? (
                <div className="empty-inline">
                  No study materials yet. Upload an image or PDF from the chat page first.
                </div>
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
                                View
                              </button>
                              <button
                                className="tiny-button danger"
                                onClick={() => deleteMaterial(material.id)}
                              >
                                Delete
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
                  <h3>Material Detail</h3>
                </div>
                {!selectedMaterialDetail ? (
                  <div className="empty-inline">
                    Click "View" on a material card to inspect the summary and extracted text.
                  </div>
                ) : (
                  <>
                    <div className="detail-meta">
                      <div>File: {selectedMaterialDetail.original_filename}</div>
                      <div>Subject: {selectedMaterialDetail.subject}</div>
                      <div>Type: {selectedMaterialDetail.file_type}</div>
                      <div>Uploaded: {formatDate(selectedMaterialDetail.created_at)}</div>
                    </div>
                    <div className="result-block">
                      <strong>Summary</strong>
                      <p>{selectedMaterialDetail.summary}</p>
                    </div>
                    <div className="result-block">
                      <strong>Extracted Text</strong>
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
        {sidebarOpen ? "Hide" : "Show"}
      </button>

      {sidebarOpen && (
        <aside className="sidebar-panel">
          <div className="sidebar-top">
            <div>
              <div className="section-eyebrow">Study Hub</div>
              <h2>AI Study Assistant</h2>
            </div>
            <p className="muted-text">{user.username}</p>
          </div>

          <div className="sidebar-user-card">
            <div>Grade: {user.grade || "Not set"}</div>
            <div>Major: {user.major || "Not set"}</div>
          </div>

          <label className="field-label">New conversation subject</label>
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
            New Conversation
          </button>
          <button className="ghost-button" onClick={() => setPage("profile")}>
            Profile
          </button>

          <div className="history-block">
            <div className="panel-title-row">
              <h3>{subject} History</h3>
            </div>

            <div className="history-list">
              {visibleSessions.length === 0 && (
                <div className="empty-inline">No history for this subject yet.</div>
              )}

              {visibleSessions.map((session) => (
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
                      Rename
                    </button>
                    <button
                      className="tiny-button danger"
                      onClick={(event) => deleteChatSession(session, event)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button className="ghost-button" onClick={logout}>
            Log Out
          </button>
        </aside>
      )}

      <main className="workspace-main workspace-main--chat-only">
        <section className="chat-panel chat-panel--wide">
          <div className="panel-header">
            <div>
              <div className="section-eyebrow">Conversation</div>
              <h2>Current Chat</h2>
            </div>
            <div className="subject-pill">Subject: {currentChatSubject}</div>
          </div>

          <div className="context-banner">
            This conversation will prioritize your personal materials from {currentChatSubject}.
          </div>

          <div className="messages-board">
            {messages.length === 0 && (
              <div className="empty-state">
                Pick a subject and ask a question, or click the plus button to upload an image or
                PDF with your question.
              </div>
            )}

            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className={msg.role === "user" ? "message-card user" : "message-card assistant"}
              >
                <div className="message-role">{msg.role === "user" ? "You" : "AI"}</div>
                <div className="message-text">{msg.content}</div>

                {msg.attachment_type && (
                  <div className="attachment-card">
                    <div className="attachment-meta">
                      <span className="subject-pill small">{msg.attachment_type}</span>
                      <span>{msg.attachment_filename || "Unnamed attachment"}</span>
                    </div>
                    {msg.extracted_text && (
                      <div className="attachment-preview">
                        {msg.extracted_text.slice(0, 240)}
                        {msg.extracted_text.length > 240 ? "..." : ""}
                      </div>
                    )}

                    {msg.material_id ? (
                      <button className="ghost-button compact" disabled>
                        Added to Library
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
                                : currentChatSubject
                            )
                          }
                          disabled={
                            addToLibraryState.loading && addToLibraryState.messageId === msg.id
                          }
                        >
                          {addToLibraryState.loading && addToLibraryState.messageId === msg.id
                            ? "Adding..."
                            : "Add to Library"}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && <div className="message-card assistant">AI is thinking...</div>}
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
              <div className="composer-hint">Please enter a question before sending the file.</div>
            )}

            <div className="composer-row composer-row--input">
              <button
                className="attach-button"
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                title="Choose image or PDF"
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
                    ? "Enter the question you want to ask about this file..."
                    : "Type your question..."
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
                {loading ? "Sending..." : "Send"}
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
