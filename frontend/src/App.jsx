import { useEffect, useState } from "react";

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

function getSavedUser() {
  try {
    const savedUser = localStorage.getItem(USER_STORAGE_KEY);
    return savedUser ? JSON.parse(savedUser) : null;
  } catch (error) {
    localStorage.removeItem(USER_STORAGE_KEY);
    return null;
  }
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

  const [course, setCourse] = useState("Python");
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [hoveredHistoryAction, setHoveredHistoryAction] = useState(null);
  const [tip, setTip] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);

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
    setActiveSessionId(null);
    setPage("login");
    setAuthMode("login");
  };

  const loadProfile = async (loginUser) => {
    if (!loginUser || !loginUser.username) return null;

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
    if (!loginUser || !loginUser.username) return;

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
      console.error("加载聊天记录失败：", error);
      setTip("无法加载聊天记录，请确认后端正在运行");
    }
  };

  const openChatSession = async (session) => {
    if (!user || !user.username) {
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

      setActiveSessionId(session.id);
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(session.id));
      setCourse(data.session.course);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("加载单条聊天记录失败：", error);
      setTip("无法加载该聊天记录，请确认后端正在运行");
    }
  };

  const deleteChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user || !user.username) {
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
        localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
      }
    } catch (error) {
      console.error("删除聊天记录失败：", error);
      setTip("无法删除聊天记录，请确认后端正在运行");
    }
  };

  const renameChatSession = async (session, event) => {
    event.stopPropagation();

    if (!user || !user.username) {
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
        prev.map((item) =>
          item.id === session.id ? { ...item, title: data.title } : item
        )
      );
    } catch (error) {
      console.error("重命名历史对话失败：", error);
      alert("无法重命名历史对话，请确认后端正在运行");
    }
  };

  useEffect(() => {
    if (user && user.username) {
      loadChatHistory(user);
    }
  }, [user?.username]);

  useEffect(() => {
    const restoreActiveSession = async () => {
      if (!user || !user.username) return;

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

        setActiveSessionId(data.session.id);
        setCourse(data.session.course);
        setMessages(data.messages || []);
      } catch (error) {
        console.error("恢复当前聊天失败：", error);
      }
    };

    restoreActiveSession();
  }, [user?.username]);

  useEffect(() => {
    const checkLoginStatus = async () => {
      const savedUser = getSavedUser();
      if (!savedUser || !savedUser.username) return;

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
        console.error("登录状态校验失败：", error);
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
      console.error("注册错误：", error);
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
      console.error("登录错误：", error);
      setTip("无法连接后端，请确认 FastAPI 正在运行");
    }
  };

  const saveProfile = async () => {
    if (!user || !user.username) {
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
      console.error("保存个人资料失败：", error);
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

  const sendMessage = async () => {
    if (!message.trim() && !selectedFile) return;

    if (!user || !user.username) {
      setTip("请先登录后再使用 AI 聊天");
      logout();
      return;
    }

    if (selectedFile) {
      await sendFileMessage();
      return;
    }

    const userMessage = { role: "user", content: message };
    const currentSessionId = activeSessionId;

    setMessages((prev) => (currentSessionId ? [...prev, userMessage] : [userMessage]));
    setLoading(true);

    const currentMessage = message;
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMessage,
          course,
          grade: user.grade || "",
          major: user.major || "",
          username: user.username,
          session_id: currentSessionId,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (res.status === 401) {
          logout();
          setTip(data.detail || "登录状态无效，请重新登录");
        }

        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.detail || "AI 回复失败" },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);

      if (data.session) {
        setActiveSessionId(data.session.id);
        localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(data.session.id));

        setChatSessions((prev) => {
          const exists = prev.some((session) => session.id === data.session.id);
          if (exists) {
            return prev.map((session) =>
              session.id === data.session.id ? data.session : session
            );
          }
          return [data.session, ...prev];
        });
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "无法连接后端，请确认 FastAPI 正在运行" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendFileMessage = async () => {
    if (!selectedFile || !user || !user.username) return;

    const currentMessage = message.trim();
    const currentFile = selectedFile;
    const currentSessionId = activeSessionId;
    const userContent = `上传文件：${currentFile.name}${
      currentMessage ? `\n问题：${currentMessage}` : ""
    }`;

    setMessages((prev) =>
      currentSessionId
        ? [...prev, { role: "user", content: userContent }]
        : [{ role: "user", content: userContent }]
    );
    setLoading(true);
    setMessage("");

    const formData = new FormData();
    formData.append("file", currentFile);
    formData.append("message", currentMessage);
    formData.append("username", user.username);
    if (currentSessionId) {
      formData.append("conversation_id", String(currentSessionId));
    }

    try {
      const res = await fetch(`${API_BASE}/chat/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${user.username}`,
        },
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        alert(data.detail || "上传失败");
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.detail || "上传失败" },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
      setSelectedFile(null);

      if (data.session) {
        setActiveSessionId(data.session.id);
        localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, String(data.session.id));

        setChatSessions((prev) => {
          const exists = prev.some((session) => session.id === data.session.id);
          if (exists) {
            return prev.map((session) =>
              session.id === data.session.id ? data.session : session
            );
          }
          return [data.session, ...prev];
        });
      }
    } catch (error) {
      console.error("文件上传失败：", error);
      alert("上传失败，请确认后端正在运行");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "上传失败，请确认后端正在运行" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const selectedAvatar =
    AVATARS.find((avatar) => avatar.id === profileForm.avatar) || AVATARS[0];

  if (!user) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>AI 学习助手</h1>
          <p style={styles.subtitle}>登录后进入个人主页</p>

          <div style={styles.tabs}>
            <button
              style={authMode === "login" ? styles.activeTab : styles.tab}
              onClick={() => {
                setAuthMode("login");
                setTip("");
              }}
            >
              登录
            </button>
            <button
              style={authMode === "register" ? styles.activeTab : styles.tab}
              onClick={() => {
                setAuthMode("register");
                setTip("");
              }}
            >
              注册
            </button>
          </div>

          <input
            style={styles.input}
            placeholder="账号"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <input
            style={styles.input}
            placeholder="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {tip && <p style={styles.tip}>{tip}</p>}

          {authMode === "login" ? (
            <button style={styles.primaryButton} onClick={handleLogin}>
              登录
            </button>
          ) : (
            <button style={styles.primaryButton} onClick={handleRegister}>
              注册
            </button>
          )}
        </div>
      </div>
    );
  }

  if (page === "profile") {
    return (
      <div style={styles.profilePage}>
        <div style={styles.profileCard}>
          <div style={styles.profileHeader}>
            <div
              style={{
                ...styles.profileAvatar,
                background: selectedAvatar.background,
              }}
            >
              {selectedAvatar.label}
            </div>
            <div>
              <h1 style={styles.profileTitle}>个人主页</h1>
              <p style={styles.profileSubtitle}>{user.username}</p>
            </div>
          </div>

          <div style={styles.avatarGrid}>
            {AVATARS.map((avatar) => (
              <button
                key={avatar.id}
                style={{
                  ...styles.avatarOption,
                  background: avatar.background,
                  outline:
                    profileForm.avatar === avatar.id
                      ? "3px solid #111827"
                      : "3px solid transparent",
                }}
                onClick={() =>
                  setProfileForm((prev) => ({ ...prev, avatar: avatar.id }))
                }
                title={avatar.id}
              >
                {avatar.label}
              </button>
            ))}
          </div>

          <label style={styles.label}>账号</label>
          <input style={styles.input} value={user.username} disabled />

          <label style={styles.label}>昵称</label>
          <input
            style={styles.input}
            placeholder="例如：小明"
            value={profileForm.nickname}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))
            }
          />

          <label style={styles.label}>年级</label>
          <input
            style={styles.input}
            placeholder="例如：大二"
            value={profileForm.grade}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, grade: e.target.value }))
            }
          />

          <label style={styles.label}>专业</label>
          <input
            style={styles.input}
            placeholder="例如：软件工程"
            value={profileForm.major}
            onChange={(e) =>
              setProfileForm((prev) => ({ ...prev, major: e.target.value }))
            }
          />

          {tip && <p style={styles.tip}>{tip}</p>}

          <div style={styles.profileActions}>
            <button
              style={styles.primaryButton}
              onClick={saveProfile}
              disabled={profileSaving}
            >
              {profileSaving ? "保存中..." : "保存个人信息"}
            </button>
            <button style={styles.chatEntryButton} onClick={() => setPage("chat")}>
              进入聊天
            </button>
            <button style={styles.secondaryButton} onClick={logout}>
              退出登录
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.chatPage}>
      <button
        style={styles.sidebarToggle}
        onClick={() => setSidebarOpen((prev) => !prev)}
      >
        {sidebarOpen ? "<" : ">"}
      </button>

      {sidebarOpen && (
        <div style={styles.sidebar}>
          <h2>AI 学习助手</h2>

          <p>当前用户：{user.username}</p>
          <p>年级：{user.grade || "未填写"}</p>
          <p>专业：{user.major || "未填写"}</p>

          <button style={styles.secondaryButton} onClick={() => setPage("profile")}>
            个人主页
          </button>

          <select
            style={styles.input}
            value={course}
            onChange={(e) => setCourse(e.target.value)}
          >
            <option value="Python">Python</option>
            <option value="Java">Java</option>
            <option value="数据结构">数据结构</option>
            <option value="计算机网络">计算机网络</option>
            <option value="操作系统">操作系统</option>
            <option value="数据库">数据库</option>
            <option value="前端开发">前端开发</option>
            <option value="后端开发">后端开发</option>
            <option value="算法">算法</option>
          </select>

          <button
            style={styles.secondaryButton}
            onClick={() => {
              setMessages([]);
              setActiveSessionId(null);
              localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
            }}
          >
            新对话
          </button>

          <h3 style={styles.historyTitle}>历史记录</h3>

          <div style={styles.historyList}>
            {chatSessions.length === 0 && (
              <div style={styles.historyEmpty}>暂无历史记录</div>
            )}

            {chatSessions.map((session) => (
              <div
                key={session.id}
                style={
                  activeSessionId === session.id
                    ? styles.activeHistoryItem
                    : styles.historyItem
                }
                onClick={() => openChatSession(session)}
              >
                <div style={styles.historyRow}>
                  <div style={styles.historyContent}>
                    <div style={styles.historyCourse}>[{session.course}]</div>
                    <div style={styles.historyText}>{session.title}</div>
                  </div>

                  <div style={styles.historyActions}>
                    <button
                      style={
                        hoveredHistoryAction === `rename-${session.id}`
                          ? styles.renameHistoryButtonHover
                          : styles.renameHistoryButton
                      }
                      onClick={(event) => renameChatSession(session, event)}
                      onMouseEnter={() =>
                        setHoveredHistoryAction(`rename-${session.id}`)
                      }
                      onMouseLeave={() => setHoveredHistoryAction(null)}
                      title="重命名这条历史对话"
                    >
                      编辑
                    </button>

                    <button
                      style={styles.deleteHistoryButton}
                      onClick={(event) => deleteChatSession(session, event)}
                      title="删除这条历史记录"
                    >
                      x
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button style={styles.secondaryButton} onClick={logout}>
            退出登录
          </button>
        </div>
      )}

      <div style={styles.chatMain}>
        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.empty}>请选择课程，然后开始提问。</div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              style={msg.role === "user" ? styles.userMsg : styles.aiMsg}
            >
              <strong>{msg.role === "user" ? "你" : "AI"}：</strong>
              <div style={styles.msgText}>{msg.content}</div>
            </div>
          ))}

          {loading && <div style={styles.aiMsg}>AI 正在思考...</div>}
        </div>

        <div style={styles.inputArea}>
          {selectedFile && (
            <div style={styles.selectedFileRow}>
              <span>已选择：{selectedFile.name}</span>
              <button
                style={styles.cancelFileButton}
                onClick={() => setSelectedFile(null)}
              >
                取消文件
              </button>
            </div>
          )}

          <div style={styles.inputBar}>
            <label style={styles.fileButton}>
              文件
              <input
                type="file"
                accept=".pdf,image/png,image/jpeg,image/webp"
                style={styles.hiddenFileInput}
                onChange={handleFileChange}
              />
            </label>

            <input
              style={styles.chatInput}
              placeholder={selectedFile ? "输入关于文件的问题，可留空" : "输入你的问题..."}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  sendMessage();
                }
              }}
            />

            <button
              style={styles.sendButton}
              onClick={sendMessage}
              disabled={loading}
            >
              {loading ? "发送中..." : "发送"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    background: "#f3f4f6",
    fontFamily: "Arial, sans-serif",
  },
  card: {
    width: "360px",
    background: "white",
    padding: "32px",
    borderRadius: "16px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.1)",
  },
  title: {
    margin: 0,
    textAlign: "center",
  },
  subtitle: {
    textAlign: "center",
    color: "#666",
  },
  tabs: {
    display: "flex",
    gap: "10px",
    marginBottom: "16px",
  },
  tab: {
    flex: 1,
    padding: "10px",
    border: "1px solid #ddd",
    background: "#f9fafb",
    borderRadius: "8px",
    cursor: "pointer",
  },
  activeTab: {
    flex: 1,
    padding: "10px",
    border: "none",
    background: "#2563eb",
    color: "white",
    borderRadius: "8px",
    cursor: "pointer",
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "12px",
    marginBottom: "12px",
    borderRadius: "8px",
    border: "1px solid #ddd",
  },
  label: {
    display: "block",
    color: "#374151",
    fontSize: "14px",
    fontWeight: 700,
    marginBottom: "6px",
  },
  tip: {
    color: "#dc2626",
    fontSize: "14px",
  },
  primaryButton: {
    width: "100%",
    padding: "12px",
    border: "none",
    borderRadius: "8px",
    background: "#2563eb",
    color: "white",
    cursor: "pointer",
  },
  chatEntryButton: {
    width: "100%",
    padding: "12px",
    border: "none",
    borderRadius: "8px",
    background: "#111827",
    color: "white",
    cursor: "pointer",
  },
  profilePage: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#eef2ff",
    fontFamily: "Arial, sans-serif",
    padding: "24px",
  },
  profileCard: {
    width: "460px",
    maxWidth: "100%",
    background: "white",
    padding: "28px",
    borderRadius: "16px",
    boxShadow: "0 18px 40px rgba(15,23,42,0.16)",
  },
  profileHeader: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
    marginBottom: "20px",
  },
  profileAvatar: {
    width: "72px",
    height: "72px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "white",
    fontWeight: 800,
    fontSize: "22px",
  },
  profileTitle: {
    margin: 0,
    fontSize: "26px",
  },
  profileSubtitle: {
    margin: "6px 0 0",
    color: "#6b7280",
  },
  avatarGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(6, 1fr)",
    gap: "8px",
    marginBottom: "20px",
  },
  avatarOption: {
    width: "42px",
    height: "42px",
    border: "none",
    borderRadius: "50%",
    color: "white",
    cursor: "pointer",
    fontWeight: 800,
  },
  profileActions: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    marginTop: "10px",
  },
  chatPage: {
    minHeight: "100vh",
    display: "flex",
    background: "#f3f4f6",
    fontFamily: "Arial, sans-serif",
  },
  sidebarToggle: {
    position: "fixed",
    top: "16px",
    left: "16px",
    zIndex: 1000,
    width: "40px",
    height: "40px",
    border: "none",
    borderRadius: "10px",
    background: "#2563eb",
    color: "white",
    fontSize: "18px",
    cursor: "pointer",
    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
  },
  sidebar: {
    width: "260px",
    background: "white",
    padding: "72px 24px 24px",
    borderRight: "1px solid #e5e7eb",
  },
  secondaryButton: {
    width: "100%",
    padding: "10px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    background: "white",
    cursor: "pointer",
    marginBottom: "12px",
  },
  historyTitle: {
    marginTop: "20px",
    marginBottom: "10px",
    fontSize: "16px",
  },
  historyList: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginBottom: "16px",
  },
  historyEmpty: {
    color: "#888",
    fontSize: "14px",
    padding: "8px 0",
  },
  historyItem: {
    width: "100%",
    textAlign: "left",
    padding: "10px",
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    background: "#f9fafb",
    cursor: "pointer",
    userSelect: "none",
  },
  activeHistoryItem: {
    width: "100%",
    textAlign: "left",
    padding: "10px",
    border: "1px solid #2563eb",
    borderRadius: "8px",
    background: "#dbeafe",
    cursor: "pointer",
    userSelect: "none",
  },
  historyCourse: {
    fontSize: "12px",
    color: "#2563eb",
    marginBottom: "4px",
  },
  historyText: {
    fontSize: "14px",
    color: "#111827",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  chatMain: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
  },
  messages: {
    flex: 1,
    padding: "24px",
    overflowY: "auto",
  },
  empty: {
    color: "#666",
    textAlign: "center",
    marginTop: "120px",
  },
  userMsg: {
    background: "#dbeafe",
    padding: "12px",
    borderRadius: "12px",
    marginBottom: "12px",
    marginLeft: "20%",
  },
  aiMsg: {
    background: "white",
    padding: "12px",
    borderRadius: "12px",
    marginBottom: "12px",
    marginRight: "20%",
    border: "1px solid #e5e7eb",
  },
  msgText: {
    whiteSpace: "pre-wrap",
    marginTop: "6px",
  },
  inputBar: {
    display: "flex",
    gap: "12px",
    padding: "16px",
    background: "white",
    borderTop: "1px solid #e5e7eb",
  },
  inputArea: {
    background: "white",
    borderTop: "1px solid #e5e7eb",
  },
  selectedFileRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    padding: "10px 16px 0",
    color: "#374151",
    fontSize: "14px",
  },
  fileButton: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0 14px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    background: "#f9fafb",
    color: "#374151",
    cursor: "pointer",
    fontSize: "14px",
  },
  hiddenFileInput: {
    display: "none",
  },
  cancelFileButton: {
    border: "none",
    background: "transparent",
    color: "#dc2626",
    cursor: "pointer",
    fontSize: "14px",
  },
  chatInput: {
    flex: 1,
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ddd",
  },
  sendButton: {
    padding: "0 24px",
    border: "none",
    borderRadius: "8px",
    background: "#2563eb",
    color: "white",
    cursor: "pointer",
  },
  historyRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
  },
  historyContent: {
    flex: 1,
    minWidth: 0,
  },
  historyActions: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexShrink: 0,
  },
  renameHistoryButton: {
    height: "24px",
    border: "1px solid #e5e7eb",
    borderRadius: "6px",
    background: "transparent",
    color: "#6b7280",
    cursor: "pointer",
    fontSize: "12px",
    lineHeight: "20px",
    padding: "0 6px",
  },
  renameHistoryButtonHover: {
    height: "24px",
    border: "1px solid #fecaca",
    borderRadius: "6px",
    background: "#fee2e2",
    color: "#dc2626",
    cursor: "pointer",
    fontSize: "12px",
    lineHeight: "20px",
    padding: "0 6px",
  },
  deleteHistoryButton: {
    width: "24px",
    height: "24px",
    border: "none",
    borderRadius: "6px",
    background: "#fee2e2",
    color: "#dc2626",
    cursor: "pointer",
    fontSize: "16px",
    lineHeight: "20px",
  },
};

export default App;
