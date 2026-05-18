import { useState, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import "./App.css";

// 登录/注册组件
function Login({ onLogin }) {
  const [name, setName] = useState("");
  const [year, setYear] = useState("大一");
  const [major, setMajor] = useState("软件工程");
  const [habit, setHabit] = useState("每天学习1-2小时");

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin({ name, year, major, habit });
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial", maxWidth: "400px", margin: "50px auto", background: "#f4f6fb", borderRadius: "12px" }}>
      <h2 style={{ textAlign: "center", marginBottom: "30px" }}>欢迎使用 AI 学习助手</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "16px" }}>
          <label>姓名:</label>
          <input style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc" }} value={name} onChange={e => setName(e.target.value)} required/>
        </div>
        <div style={{ marginBottom: "16px" }}>
          <label>年级:</label>
          <select style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc" }} value={year} onChange={e => setYear(e.target.value)}>
            <option>大一</option>
            <option>大二</option>
            <option>大三</option>
            <option>大四</option>
          </select>
        </div>
        <div style={{ marginBottom: "16px" }}>
  <label>专业类别:</label>
  <select
    style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc" }}
    value={major}
    onChange={e => setMajor(e.target.value)}
  >
    <option value="泛计算机类">泛计算机类（计算机、软件、AI、大数据等）</option>
    <option value="电子信息 & 电气类">电子信息 & 电气类（电子、通信、电气、自动化等）</option>
    <option value="其他理工科类">其他理工科类（数理、化工、土木、机械、农林、医学等）</option>
    <option value="文科类">文科类</option>
  </select>
</div>
        <div style={{ marginBottom: "16px" }}>
          <label>学习习惯:</label>
          <input style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc" }} value={habit} onChange={e => setHabit(e.target.value)}/>
        </div>
        <button type="submit" style={{ width: "100%", padding: "12px", background: "#2563eb", color: "white", border: "none", borderRadius: "8px", cursor: "pointer" }}>进入学习助手</button>
      </form>
    </div>
  );
}

// 主 App
function App() {
  const [user, setUser] = useState(null); // 用户信息
  const [course, setCourse] = useState("Python");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  // 如果 user 为空，显示登录页面
  if (!user) {
    return <Login onLogin={setUser} />;
  }

  // 发送消息函数
  const sendMessage = async () => {
    if (!message.trim()) return;

    const userMessage = {
      role: "user",
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setMessage("");

    try {
      const res = await axios.post("/chat", {
        message,
        course,
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

  // AI 学习助手页面
  return (
    <div className="app">
      <div className="sidebar">
        <h2>AI 学习助手</h2>
        <p>用户：{user.name} ({user.year}, {user.major})</p>
        <p>学习习惯：{user.habit}</p>

        <label>选择课程</label>
        <select value={course} onChange={(e) => setCourse(e.target.value)}>
          <option value="Python">Python</option>
          <option value="Java">Java</option>
          <option value="数据结构">数据结构</option>
          <option value="计算机网络">计算机网络</option>
          <option value="操作系统">操作系统</option>
        </select>

        <button onClick={clearChat} style={{ marginTop: "10px" }}>清空聊天</button>
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