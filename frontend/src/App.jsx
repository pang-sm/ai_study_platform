import { useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function App() {
  const [page, setPage] = useState("login");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [grade, setGrade] = useState("");
  const [major, setMajor] = useState("");

  const [user, setUser] = useState(null);

  const [course, setCourse] = useState("Python");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  const [tip, setTip] = useState("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    setTip("");

    if (!username || !password || !grade || !major) {
      setTip("请填写账号、密码、年级和专业");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
          grade,
          major,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setTip(data.detail || "注册失败");
        return;
      }

      setUser(data.user);
      setTip("注册成功，已进入学习助手");
    } catch (error) {
      setTip("无法连接后端，请确认 FastAPI 正在运行");
    }
  };

  const handleLogin = async () => {
    setTip("");

    if (!username || !password) {
      setTip("请填写账号和密码");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setTip(data.detail || "登录失败");
        return;
      }

      setUser(data.user);
      setTip("登录成功");
    } catch (error) {
      setTip("无法连接后端，请确认 FastAPI 正在运行");
    }
  };

  const sendMessage = async () => {
    if (!message.trim()) return;
    if (!user) {
      setTip("请先登录");
      return;
    }

    const userMessage = {
      role: "user",
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    const currentMessage = message;
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: currentMessage,
          course,
          grade: user.grade,
          major: user.major,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.detail || "AI 回复失败",
          },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "无法连接后端，请确认 FastAPI 正在运行",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    setMessages([]);
    setTip("已退出登录");
  };

  if (!user) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>AI 学习助手</h1>
          <p style={styles.subtitle}>数据库登录注册版</p>

          <div style={styles.tabs}>
            <button
              style={page === "login" ? styles.activeTab : styles.tab}
              onClick={() => setPage("login")}
            >
              登录
            </button>
            <button
              style={page === "register" ? styles.activeTab : styles.tab}
              onClick={() => setPage("register")}
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

          {page === "register" && (
            <>
              <input
                style={styles.input}
                placeholder="年级，例如：大一"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
              />

              <input
                style={styles.input}
                placeholder="专业，例如：软件工程"
                value={major}
                onChange={(e) => setMajor(e.target.value)}
              />
            </>
          )}

          {tip && <p style={styles.tip}>{tip}</p>}

          {page === "login" ? (
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

  return (
    <div style={styles.chatPage}>
      <div style={styles.sidebar}>
        <h2>AI 学习助手</h2>

        <p>当前用户：{user.username}</p>
        <p>年级：{user.grade}</p>
        <p>专业：{user.major}</p>

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

        <button style={styles.secondaryButton} onClick={logout}>
          退出登录
        </button>
      </div>

      <div style={styles.chatMain}>
        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.empty}>
              请选择课程，然后开始提问。
            </div>
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

        <div style={styles.inputBar}>
          <input
            style={styles.chatInput}
            placeholder="输入你的问题..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                sendMessage();
              }
            }}
          />

          <button style={styles.sendButton} onClick={sendMessage}>
            发送
          </button>
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
  chatPage: {
    minHeight: "100vh",
    display: "flex",
    background: "#f3f4f6",
    fontFamily: "Arial, sans-serif",
  },
  sidebar: {
    width: "260px",
    background: "white",
    padding: "24px",
    borderRight: "1px solid #e5e7eb",
  },
  secondaryButton: {
    width: "100%",
    padding: "10px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    background: "white",
    cursor: "pointer",
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
};

export default App;