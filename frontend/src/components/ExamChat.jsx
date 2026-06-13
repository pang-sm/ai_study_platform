import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";

const API_BASE = "/api";

const SUBJECT_RECOMMENDATIONS = {
  data_structure: [
    "线性表和链表有什么区别？", "栈和队列的典型题型有哪些？",
    "二叉树遍历怎么理解？", "图的最短路径怎么做？",
    "如何分析算法的时间复杂度？",
  ],
  computer_organization: [
    "指令周期包括哪些阶段？", "Cache 命中率怎么计算？",
    "CPU 和主存如何交换数据？", "流水线冲突有哪些类型？",
    "数据表示都有哪些常见考点？",
  ],
  operating_system: [
    "进程和线程有什么区别？", "死锁产生的条件是什么？",
    "页面置换算法怎么比较？", "信号量 PV 操作怎么理解？",
    "文件系统的实现原理是什么？",
  ],
  computer_network: [
    "TCP 和 UDP 有什么区别？", "三次握手为什么不是两次？",
    "子网划分怎么计算？", "HTTP 和 HTTPS 有什么区别？",
    "网络层和传输层各自负责什么？",
  ],
};

function formatTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function shuffle(arr, count) {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, count);
}

export default function ExamChat({ user, subjectKey, subjectTitle, courseName, onBackDashboard, onNavigatePackage }) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedMaterials, setSelectedMaterials] = useState([]);
  const messagesEndRef = useRef(null);

  // Recommendations per subject
  const recommendations = useMemo(() => {
    const pool = SUBJECT_RECOMMENDATIONS[subjectKey] || SUBJECT_RECOMMENDATIONS.data_structure;
    return shuffle(pool, 4);
  }, [subjectKey]);

  // Load history on mount and after session changes
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/history?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      setHistorySessions(data.sessions || []);
    } catch { /* ignore */ }
  }, [user.username]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Auto-scroll
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // New conversation
  const startNewConversation = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setError("");
  };

  // Load a history session
  const loadSession = async (sid) => {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sid}?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setCurrentSessionId(sid);
        setMessages((data.messages || []).map((m) => ({
          id: m.id, role: m.role, content: m.content || "",
          references: m.references || [], created_at: m.created_at,
        })));
      }
    } catch { setError("加载历史失败"); }
    setHistoryOpen(false);
  };

  // Delete session
  const deleteSession = async (sid) => {
    try {
      await fetch(`${API_BASE}/chat/sessions/${sid}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
      if (currentSessionId === sid) startNewConversation();
      loadHistory();
    } catch { /* ignore */ }
  };

  // Send message
  const sendMessage = async (text) => {
    const msg = (text || inputText).trim();
    if (!msg || loading) return;
    setInputText("");
    setError("");

    const userMsg = { id: Date.now(), role: "user", content: msg, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const body = {
        username: user.username,
        message: msg,
        session_id: currentSessionId,
        subject: subjectTitle,
        course: courseName,
        material_ids: selectedMaterials.map((m) => m.id),
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
        id: data.assistant_message_id || Date.now() + 1,
        role: "assistant",
        content: data.answer || "",
        references: data.references || [],
        created_at: new Date().toISOString(),
      }]);

      if (!currentSessionId) loadHistory();
    } catch (err) {
      setError(err.message || "发送失败");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  // Persist active panel for refresh recovery
  const PANEL_KEY = `exam_subject_active_panel_${subjectKey}`;
  useEffect(() => {
    try { localStorage.setItem(PANEL_KEY, JSON.stringify({ activePanel: "ai", ts: Date.now() })); } catch { /* ignore */ }
  }, [PANEL_KEY]);

  return (
    <div className="examchat-shell">
      {/* ── Header ── */}
      <div className="examchat-header">
        <div>
          <h2 className="examchat-title">AI 问答 · {subjectTitle}</h2>
          <p className="examchat-subtitle" style={{ fontSize: 13, color: "#7c3aed" }}>当前上下文：{courseName}</p>
        </div>
        <div className="examchat-header-actions">
          <button type="button" className="eh-motto-edit" style={{ padding: "6px 14px", fontSize: 13, fontWeight: 700, border: "1.5px solid #c4b5fd", borderRadius: 10, background: "#fff", color: "#7c3aed", cursor: "pointer" }} onClick={startNewConversation}>+ 新对话</button>
          <button type="button" className="eh-motto-edit" style={{ padding: "6px 14px", fontSize: 13, fontWeight: 700, border: "1.5px solid #c4b5fd", borderRadius: 10, background: "#fff", color: "#7c3aed", cursor: "pointer" }} onClick={() => { loadHistory(); setHistoryOpen(true); }}>📋 历史对话</button>
          <button type="button" className="eh-motto-edit" style={{ padding: "6px 14px", fontSize: 13, fontWeight: 700, border: "1.5px solid #c4b5fd", borderRadius: 10, background: "#fff", color: "#7c3aed", cursor: "pointer" }} onClick={onBackDashboard}>← 返回首页</button>
        </div>
      </div>

      {/* ── Error ── */}
      {error && <div className="ob-error" style={{ margin: "0 0 12px" }}>{error}</div>}

      {/* ── Body: messages + sidebar ── */}
      <div className="examchat-body">
        <div className="examchat-messages">
          {messages.length === 0 && !loading ? (
            <div className="examchat-empty">
              <span className="examchat-empty-icon">💬</span>
              <strong>开始 AI 问答</strong>
              <p>输入你的问题，AI 将围绕 {subjectTitle} 课程内容为你解答。</p>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={`examchat-msg${m.role === "user" ? " examchat-msg--user" : ""}`}>
                <div className="examchat-msg-content">
                  {m.role === "assistant" ? (
                    <MarkdownMessage content={m.content} />
                  ) : (
                    <p>{m.content}</p>
                  )}
                  {m.references && m.references.length > 0 && (
                    <div className="examchat-refs">
                      <strong>📎 参考资料：</strong>
                      {m.references.map((r, i) => (
                        <span key={i} className="examchat-ref">{r.source_filename || `资料 ${i + 1}`}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && <div className="examchat-msg"><div className="examchat-msg-content"><p style={{ color: "#94a3b8" }}>AI 正在思考...</p></div></div>}
          <div ref={messagesEndRef} />
        </div>

        {/* ── Sidebar: references + recommendations ── */}
        <div className="examchat-sidebar">
          <div className="examchat-side-card">
            <h4>本轮引用资料</h4>
            {selectedMaterials.length === 0 ? (
              <p className="examchat-side-hint">尚未引用资料，点击下方按钮从资料库中选择</p>
            ) : (
              <ul className="examchat-ref-list">
                {selectedMaterials.map((m) => (
                  <li key={m.id}>
                    <span>{m.original_filename || m.file_name}</span>
                    <button type="button" onClick={() => setSelectedMaterials((p) => p.filter((x) => x.id !== m.id))}>✕</button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="examchat-side-card">
            <h4>推荐提问</h4>
            {recommendations.map((q, i) => (
              <button key={i} type="button" className="examchat-rec-btn" onClick={() => sendMessage(q)}>{q}</button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Input area ── */}
      <div className="examchat-input-area">
        <textarea
          className="examchat-input"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`向 AI 提问 ${subjectTitle} 相关问题...`}
          rows={2}
          disabled={loading}
        />
        <button type="button" className="ob-btn-primary" style={{ width: 120, height: 48, flexShrink: 0 }} onClick={() => sendMessage()} disabled={loading || !inputText.trim()}>
          {loading ? "思考中..." : "发送"}
        </button>
      </div>

      {/* ── History Modal ── */}
      {historyOpen && (
        <div className="eh-modal-backdrop" onClick={() => setHistoryOpen(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()} style={{ width: "min(520px, 90vw)", maxHeight: "70vh", overflow: "auto" }}>
            <div className="eh-modal-head"><h3>历史对话</h3><button type="button" className="eh-modal-close" onClick={() => setHistoryOpen(false)}>×</button></div>
            {historySessions.length === 0 ? (
              <p style={{ color: "#94a3b8", textAlign: "center", padding: 20 }}>暂无历史对话记录</p>
            ) : (
              <div>
                {historySessions.map((s) => (
                  <div key={s.id} className="ep-sec-item" style={{ marginBottom: 8, cursor: "pointer" }} onClick={() => loadSession(s.id)}>
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: 14 }}>{s.title}</strong>
                      <p style={{ fontSize: 12, color: "#94a3b8", margin: "2px 0" }}>{s.subject || ""} · {formatTime(s.created_at)}</p>
                    </div>
                    <button type="button" className="ep-outline-btn" style={{ fontSize: 12, padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}>删除</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
