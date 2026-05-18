import { useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import "./App.css";

function App() {
  const [course, setCourse] = useState("Python");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  const sendMessage = async () => {
    if (!message.trim()) return;

    const userMessage = {
      role: "user",
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setMessage("");

    try {
      const res = await axios.post("http://127.0.0.1:8000/chat", {
        message,
        course,
      });

      const aiMessage = {
        role: "assistant",
        content: res.data.answer,
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "后端连接失败，请检查 FastAPI 是否已经启动。",
        },
      ]);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div className="app">
      <div className="sidebar">
        <h2>AI 学习助手</h2>

        <label>选择课程</label>
        <select value={course} onChange={(e) => setCourse(e.target.value)}>
          <option value="Python">Python</option>
          <option value="Java">Java</option>
          <option value="数据结构">数据结构</option>
          <option value="计算机网络">计算机网络</option>
          <option value="操作系统">操作系统</option>
        </select>

        <button onClick={clearChat}>清空聊天</button>
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
