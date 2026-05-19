import { useState, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import "./App.css";
import "./style.css";

// 登录/注册组件
function Login({ onLogin }) {
  const [mode, setMode] = useState("login");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [grade, setGrade] = useState("");
  const [major, setMajor] = useState("");

  const majorOptions = [
  "软件工程",
  "计算机科学与技术",
  "人工智能",
  "数据科学与大数据技术",
  "网络工程",
  "信息安全",
  "电子信息工程",
  "自动化",
  "其他"
];

  const [tip, setTip] = useState("");

  const API_BASE_URL = "/api";

  const handleLogin = async () => {
  try {
    setTip("");

    const res = await axios.post(`${API_BASE_URL}/login`, {
      username,
      password,
    });

    setTip("登录成功");
    onLogin(res.data.user);
  } catch (error) {
    console.error("登录失败：", error);

    setTip(
      error.response?.data?.detail ||
        error.message ||
        "登录失败，请检查后端是否启动"
    );
  }
};

  const handleRegister = async () => {
    try {
      setTip("");

      const res = await axios.post(`${API_BASE_URL}/register`, {
  username,
  password,
  grade,
  major,
});

      setTip(res.data.message || "注册成功，请登录");

      setMode("login");
      setPassword("");
    } catch (error) {
      console.error("注册失败：", error);

      setTip(
        error.response?.data?.detail ||
          error.message ||
          "注册失败，请检查后端是否启动"
      );
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>AI 学习助手</h1>

        <div className="login-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setTip("");
            }}
          >
            登录
          </button>

          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setTip("");
            }}
          >
            注册
          </button>
        </div>

        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="请输入账号"
        />

        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="请输入密码"
          type="password"
        />

        {mode === "register" && (
          <>
            <input
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              placeholder="请输入年级，例如：大一"
            />

            <select
  value={major}
  onChange={(e) => setMajor(e.target.value)}
>
  <option value="">请选择专业</option>
  {majorOptions.map((item) => (
    <option key={item} value={item}>
      {item}
    </option>
  ))}
</select>

          
          </>
        )}

        {mode === "login" ? (
          <button onClick={handleLogin}>登录</button>
        ) : (
          <button onClick={handleRegister}>注册</button>
        )}

        {tip && <p className="login-tip">{tip}</p>}
      </div>
    </div>
  );
}

// 主 App
function App() {
  const [user, setUser] = useState(null);
  const [course, setCourse] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  

  // 发送消息函数
  const sendMessage = async () => {
  if (!message.trim()) return;

  if (!course) {
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "请先在左侧选择一门课程，然后再开始提问。",
      },
    ]);
    return;
  }

  const userMessage = {
    role: "user",
    content: message,
  };

  setMessages((prev) => [...prev, userMessage]);
  setMessage("");

  try {
    const res = await axios.post("/api/chat", {
  message,
  course,
  grade: user.grade,
  major: user.major,
});

    const aiMessage = {
      role: "assistant",
      content: res.data.answer,
    };

    setMessages((prev) => [...prev, aiMessage]);
  } catch (error) {
    console.error("请求失败详情：", error);

    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content:
          "请求失败：" +
          (error.response?.data?.detail ||
            error.message ||
            "未知错误"),
      },
    ]);
  }
};

  const clearChat = () => {
    setMessages([]);
  };

  // 如果 user 为空，显示登录页面
  if (!user) {
  return (
    <Login
      onLogin={(loginUser) => {
        setUser(loginUser);
      }}
    />
  );
}

  // AI 学习助手页面
  return (
    <div className="app">
      <div className="sidebar">
  <h2>AI 学习助手</h2>

  <p>用户：{user.username} ({user.grade}, {user.major})</p>
  <p>当前课程：{course || "未选择"}</p>

  <label>选择课程</label>
  <select value={course} onChange={(e) => setCourse(e.target.value)}>
    <option value="">请选择课程</option>
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

  <button onClick={clearChat} style={{ marginTop: "10px" }}>
    清空聊天
  </button>
</div>

      <div className="chat">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          ))}
        </div>

        <div className="input-area">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={`请输入你的 ${course} 学习问题...`}
          />
          <button onClick={sendMessage}>发送</button>
        </div>
      </div>
    </div>
  );
}

export default App;