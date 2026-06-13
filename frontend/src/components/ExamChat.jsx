import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";

const API_BASE = "/api";

const SUBJECT_RECOMMENDATIONS = {
  data_structure: [
    "线性表和链表有什么区别？",
    "栈和队列的典型题型有哪些？",
    "二叉树遍历怎么理解？",
    "图的最短路径怎么做？",
    "如何分析算法的时间复杂度？",
  ],
  computer_organization: [
    "指令周期包括哪些阶段？",
    "Cache 命中率怎么计算？",
    "CPU 和主存如何交换数据？",
    "流水线冲突有哪些类型？",
    "数据表示有哪些常见考点？",
  ],
  operating_system: [
    "进程和线程有什么区别？",
    "死锁产生的条件是什么？",
    "页面置换算法怎么比较？",
    "信号量 PV 操作怎么理解？",
    "文件系统的实现原理是什么？",
  ],
  computer_network: [
    "TCP 和 UDP 有什么区别？",
    "三次握手为什么不是两次？",
    "子网划分怎么计算？",
    "HTTP 和 HTTPS 有什么区别？",
    "网络层和传输层各自负责什么？",
  ],
};

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRecommendations(subjectKey) {
  return SUBJECT_RECOMMENDATIONS[subjectKey] || SUBJECT_RECOMMENDATIONS.data_structure;
}

export default function ExamChat({
  user,
  subjectKey,
  subjectTitle,
  courseName,
  onBackDashboard,
  onOpenMaterials,
}) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedMaterials, setSelectedMaterials] = useState([]);
  const messagesEndRef = useRef(null);

  const recommendations = useMemo(() => getRecommendations(subjectKey).slice(0, 5), [subjectKey]);

  const loadHistory = useCallback(async () => {
    if (!user?.username) return;
    try {
      const res = await fetch(`${API_BASE}/chat/history?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      setHistorySessions(Array.isArray(data.sessions) ? data.sessions : []);
    } catch {
      setHistorySessions([]);
    }
  }, [user?.username]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const startNewConversation = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setInputText("");
    setError("");
  };

  const loadSession = async (sessionId) => {
    if (!user?.username) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "加载历史对话失败");
      setCurrentSessionId(sessionId);
      setMessages((data.messages || []).map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content || "",
        references: message.references || [],
        created_at: message.created_at,
      })));
    } catch (err) {
      setError(err.message || "加载历史对话失败");
    }
  };

  const deleteSession = async (sessionId, event) => {
    event.stopPropagation();
    if (!user?.username) return;
    try {
      await fetch(`${API_BASE}/chat/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      if (currentSessionId === sessionId) startNewConversation();
      loadHistory();
    } catch {
      setError("暂时无法删除该对话");
    }
  };

  const renameSession = async (session, event) => {
    event.stopPropagation();
    if (!user?.username) return;
    const inputTitle = window.prompt("请输入新的对话标题", session.title || "");
    if (inputTitle === null) return;
    const title = inputTitle.trim();
    if (!title) return;
    try {
      const res = await fetch(`${API_BASE}/conversations/${session.id}?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "重命名失败");
      setHistorySessions((prev) => prev.map((item) => (
        item.id === session.id ? { ...item, title: data.title || title } : item
      )));
    } catch (err) {
      setError(err.message || "暂时无法重命名该对话");
    }
  };

  const sendMessage = async (text) => {
    const msg = (text || inputText).trim();
    if (!msg || loading || !user?.username) return;

    setInputText("");
    setError("");
    const userMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: msg,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const body = {
        username: user.username,
        message: msg,
        session_id: currentSessionId,
        subject: subjectTitle,
        course: courseName,
        material_ids: selectedMaterials.map((material) => material.id),
      };

      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 429) throw new Error("今日 AI 问答额度已用完，请明天再试或升级套餐");
        throw new Error(data.detail || "AI 服务调用失败");
      }

      if (!currentSessionId && data.session?.id) {
        setCurrentSessionId(data.session.id);
      }

      setMessages((prev) => [...prev, {
        id: data.assistant_message_id || `assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer || "",
        references: data.references || [],
        created_at: new Date().toISOString(),
      }]);
      loadHistory();
    } catch (err) {
      setError(err.message || "发送失败");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="examchat-shell">
      <aside className="examchat-history-panel">
        <button type="button" className="examchat-new-btn" onClick={startNewConversation}>
          + 新对话
        </button>
        <div className="examchat-history-head">
          <strong>历史对话</strong>
          <button type="button" onClick={loadHistory}>刷新</button>
        </div>
        <div className="examchat-history-list">
          {historySessions.length === 0 ? (
            <div className="examchat-history-empty">暂无历史对话</div>
          ) : (
            historySessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`examchat-history-item${currentSessionId === session.id ? " active" : ""}`}
                onClick={() => loadSession(session.id)}
              >
                <span>{session.title || "未命名对话"}</span>
                <small>{session.subject || subjectTitle} · {formatTime(session.created_at)}</small>
                <i>
                  <b onClick={(event) => renameSession(session, event)}>重命名</b>
                  <b onClick={(event) => deleteSession(session.id, event)}>删除</b>
                </i>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="examchat-main-panel">
        <header className="examchat-header">
          <div>
            <h2 className="examchat-title">AI 问答 · {subjectTitle}</h2>
            <p className="examchat-subtitle">当前上下文：{courseName}</p>
          </div>
          <button type="button" className="examchat-back-btn" onClick={onBackDashboard}>返回首页</button>
        </header>

        {error && (
          <div className="examchat-error">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>关闭</button>
          </div>
        )}

        <div className="examchat-messages">
          {messages.length === 0 && !loading ? (
            <div className="examchat-empty">
              <span className="examchat-empty-icon">💬</span>
              <strong>开始 AI 问答</strong>
              <p>围绕 {subjectTitle} 提问，AI 会结合当前科目和引用资料给出讲解。</p>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className={`examchat-msg${message.role === "user" ? " examchat-msg--user" : ""}`}>
                <div className="examchat-msg-content">
                  {message.role === "assistant" ? (
                    <MarkdownMessage content={message.content} />
                  ) : (
                    <p>{message.content}</p>
                  )}
                  {Array.isArray(message.references) && message.references.length > 0 && (
                    <div className="examchat-refs">
                      <strong>参考资料：</strong>
                      {message.references.map((reference, index) => (
                        <span key={`${reference.material_id || index}-${index}`} className="examchat-ref">
                          {reference.source_filename || reference.filename || `资料 ${index + 1}`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="examchat-msg">
              <div className="examchat-msg-content">
                <p className="examchat-thinking">AI 正在思考...</p>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="examchat-input-area">
          <textarea
            className="examchat-input"
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`向 AI 提问 ${subjectTitle} 相关问题...`}
            rows={2}
            disabled={loading}
          />
          <button
            type="button"
            className="examchat-send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !inputText.trim()}
          >
            {loading ? "思考中..." : "发送"}
          </button>
        </div>
      </section>

      <aside className="examchat-sidebar">
        <div className="examchat-side-card">
          <div className="examchat-side-title">
            <h4>本轮引用资料</h4>
            <button type="button" onClick={onOpenMaterials}>全部资料库</button>
          </div>
          {selectedMaterials.length === 0 ? (
            <div className="examchat-side-empty">
              <p>尚未引用资料。</p>
              <button type="button" onClick={onOpenMaterials}>去资料库选择</button>
            </div>
          ) : (
            <ul className="examchat-ref-list">
              {selectedMaterials.map((material) => (
                <li key={material.id}>
                  <span>{material.original_filename || material.file_name}</span>
                  <button
                    type="button"
                    onClick={() => setSelectedMaterials((prev) => prev.filter((item) => item.id !== material.id))}
                  >
                    移除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="examchat-side-card">
          <h4>推荐提问</h4>
          {recommendations.map((question) => (
            <button key={question} type="button" className="examchat-rec-btn" onClick={() => sendMessage(question)}>
              {question}
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}
