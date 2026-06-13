import { useEffect, useMemo, useRef, useState } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";

const API_BASE = "/api";

function formatTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatFileSize(size) {
  const n = Number(size || 0);
  if (n <= 0) return "未知大小";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function getErrorMessage(status, detail) {
  if (status === 429) return "今日 AI 问答额度已用完，请明天再试或升级套餐";
  if (status === 401) return "登录状态已失效，请重新登录";
  if (status >= 500) return "AI 服务暂时不可用，请稍后再试";
  return detail || "网络异常，请检查连接后重试";
}

function normalizeMessages(items) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    id: item.id || `${item.role}-${Math.random()}`,
    role: item.role,
    content: item.content || "",
    references: item.references || [],
    created_at: item.created_at,
  }));
}

export default function ExamChat({ user, subjectKey, subjectTitle, courseName, onBackDashboard, onNavigatePackage }) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [histories, setHistories] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedMaterials, setSelectedMaterials] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [materialPickerOpen, setMaterialPickerOpen] = useState(false);
  const [materialSearch, setMaterialSearch] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const endRef = useRef(null);

  const selectedMaterialIds = useMemo(() => selectedMaterials.map((item) => item.id), [selectedMaterials]);
  const visibleMaterials = useMemo(() => {
    const q = materialSearch.trim().toLowerCase();
    if (!q) return materials;
    return materials.filter((item) => (item.original_filename || item.file_name || "").toLowerCase().includes(q));
  }, [materials, materialSearch]);

  const relatedHistories = useMemo(() => {
    const title = subjectTitle || "";
    return [...histories].sort((a, b) => {
      const aHit = String(a.subject || a.course || "").includes(title) ? 0 : 1;
      const bHit = String(b.subject || b.course || "").includes(title) ? 0 : 1;
      return aHit - bHit;
    });
  }, [histories, subjectTitle]);

  const requestJson = async (url, options = {}) => {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(getErrorMessage(res.status, data.detail));
      err.status = res.status;
      throw err;
    }
    return data;
  };

  const loadHistories = async () => {
    if (!user?.username) return;
    setHistoryLoading(true);
    try {
      const data = await requestJson(`${API_BASE}/chat/history?username=${encodeURIComponent(user.username)}`);
      setHistories(data.sessions || []);
    } catch (err) {
      setError(err.message || "历史对话加载失败");
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadMaterials = async () => {
    if (!user?.username) return;
    setMaterialsLoading(true);
    try {
      const data = await requestJson(`${API_BASE}/materials?username=${encodeURIComponent(user.username)}&subject=${encodeURIComponent(subjectTitle)}`);
      setMaterials(data.materials || []);
    } catch {
      setMaterials([]);
    } finally {
      setMaterialsLoading(false);
    }
  };

  useEffect(() => {
    setCurrentSessionId(null);
    setMessages([]);
    setInputText("");
    setError("");
    setSelectedMaterials([]);
    loadHistories();
    loadMaterials();
  }, [user?.username, subjectKey, courseName]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  const startNewConversation = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setInputText("");
    setError("");
    setSelectedMaterials([]);
  };

  const openSession = async (session) => {
    setError("");
    try {
      const data = await requestJson(`${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(user.username)}`);
      setCurrentSessionId(data.session?.id || session.id);
      setMessages(normalizeMessages(data.messages || []));
      setSelectedMaterials([]);
    } catch (err) {
      setError(err.message || "历史消息加载失败");
    }
  };

  const deleteSession = async (session, event) => {
    event?.stopPropagation();
    if (!window.confirm("确认删除这条对话吗？删除后不可恢复。")) return;
    setDeletingSessionId(session.id);
    setError("");
    try {
      await requestJson(`${API_BASE}/chat/sessions/${session.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
      if (currentSessionId === session.id) startNewConversation();
      await loadHistories();
    } catch (err) {
      setError(err.message || "删除对话失败");
    } finally {
      setDeletingSessionId(null);
    }
  };

  const renameSession = async (session, event) => {
    event?.stopPropagation();
    const nextTitle = window.prompt("请输入新的对话标题", session.title || "");
    if (nextTitle === null) return;
    const title = nextTitle.trim();
    if (!title) return;
    setRenamingSessionId(session.id);
    setError("");
    try {
      await requestJson(`${API_BASE}/conversations/${session.id}?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      await loadHistories();
    } catch (err) {
      setError(err.message || "重命名失败");
    } finally {
      setRenamingSessionId(null);
    }
  };

  const toggleMaterial = (material) => {
    setSelectedMaterials((prev) => (
      prev.some((item) => item.id === material.id)
        ? prev.filter((item) => item.id !== material.id)
        : [...prev, material]
    ));
  };

  const sendMessage = async () => {
    const text = inputText.trim();
    if (!text || loading) return;
    const optimisticUserMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: text,
      references: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMessage]);
    setInputText("");
    setError("");
    setLoading(true);

    try {
      const data = await requestJson(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          message: text,
          session_id: currentSessionId || null,
          subject: subjectTitle,
          course: courseName,
          hidden_instruction: `你正在辅导用户进行 11408 考研中的【${subjectTitle}】科目学习，请围绕该科目回答。`,
          material_ids: selectedMaterialIds,
        }),
      });

      if (data.session?.id && !currentSessionId) setCurrentSessionId(data.session.id);
      setMessages((prev) => [
        ...prev,
        {
          id: data.assistant_message_id || `assistant-${Date.now()}`,
          role: "assistant",
          content: data.answer || "",
          references: data.references || [],
          created_at: new Date().toISOString(),
        },
      ]);
      setSelectedMaterials([]);
      await loadHistories();
    } catch (err) {
      setInputText(text);
      setError(err.message || "网络异常，请检查连接后重试");
    } finally {
      setLoading(false);
    }
  };

  const handleInputKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="exam-chat-page">
      <aside className="exam-chat-history">
        <button type="button" className="exam-chat-new" onClick={startNewConversation}>+ 新建对话</button>
        <div className="exam-chat-history-head">
          <strong>历史对话</strong>
          {historyLoading && <span>加载中...</span>}
        </div>
        <div className="exam-chat-session-list">
          {relatedHistories.length === 0 ? (
            <p className="exam-chat-empty">暂无历史对话</p>
          ) : relatedHistories.map((session) => (
            <button
              type="button"
              key={session.id}
              className={`exam-chat-session${currentSessionId === session.id ? " active" : ""}`}
              onClick={() => openSession(session)}
            >
              <span>{session.title || "未命名对话"}</span>
              <small>{session.subject || session.course || "全局对话"} · {formatTime(session.created_at)}</small>
              <i>
                <b onClick={(event) => renameSession(session, event)}>{renamingSessionId === session.id ? "..." : "重命名"}</b>
                <b onClick={(event) => deleteSession(session, event)}>{deletingSessionId === session.id ? "..." : "删除"}</b>
              </i>
            </button>
          ))}
        </div>
      </aside>

      <section className="exam-chat-main">
        <header className="exam-chat-header">
          <div>
            <button type="button" onClick={onBackDashboard}>← 返回学科首页</button>
            <h2>AI 问答 · {subjectTitle}</h2>
            <p>当前上下文：{courseName}</p>
          </div>
        </header>

        {error && (
          <div className="exam-chat-error">
            <span>{error}</span>
            {error.includes("额度") && <button type="button" onClick={onNavigatePackage}>查看套餐</button>}
          </div>
        )}

        <div className="exam-chat-messages">
          {messages.length === 0 ? (
            <div className="exam-chat-welcome">
              <strong>开始提问 {subjectTitle}</strong>
              <p>可以问概念、题型、易错点，也可以引用资料后让 AI 按资料回答。</p>
            </div>
          ) : messages.map((message) => (
            <article key={message.id} className={`exam-chat-message exam-chat-message--${message.role}`}>
              <div className="exam-chat-bubble">
                {message.role === "assistant" ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
                {message.role === "assistant" && Array.isArray(message.references) && message.references.length > 0 && (
                  <ReferenceList references={message.references} />
                )}
              </div>
            </article>
          ))}
          {loading && (
            <article className="exam-chat-message exam-chat-message--assistant">
              <div className="exam-chat-bubble exam-chat-thinking">正在思考...</div>
            </article>
          )}
          <div ref={endRef} />
        </div>

        <footer className="exam-chat-input-area">
          {selectedMaterials.length > 0 && (
            <div className="exam-chat-selected-materials">
              <span>已引用：</span>
              {selectedMaterials.map((item) => (
                <button key={item.id} type="button" onClick={() => toggleMaterial(item)}>
                  {item.original_filename || item.file_name} ×
                </button>
              ))}
            </div>
          )}
          <div className="exam-chat-input-tools">
            <button type="button" onClick={() => setMaterialPickerOpen(true)}>引用资料</button>
            <span>Enter 发送，Shift + Enter 换行</span>
          </div>
          <div className="exam-chat-input-row">
            <textarea
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={`向 11408 ${subjectTitle} 提问...`}
              rows={3}
            />
            <button type="button" disabled={loading || !inputText.trim()} onClick={sendMessage}>
              {loading ? "发送中" : "发送"}
            </button>
          </div>
        </footer>
      </section>

      {materialPickerOpen && (
        <div className="exam-chat-material-mask" role="presentation">
          <div className="exam-chat-material-panel" role="dialog" aria-modal="true" aria-label="选择引用资料">
            <div className="exam-chat-material-head">
              <div>
                <h3>引用资料</h3>
                <p>选择 {courseName} 资料，发送时会携带 material_ids。</p>
              </div>
              <button type="button" onClick={() => setMaterialPickerOpen(false)}>×</button>
            </div>
            <input
              className="exam-chat-material-search"
              value={materialSearch}
              onChange={(event) => setMaterialSearch(event.target.value)}
              placeholder="搜索资料名称"
            />
            <div className="exam-chat-material-list">
              {materialsLoading ? (
                <p className="exam-chat-empty">资料加载中...</p>
              ) : visibleMaterials.length === 0 ? (
                <p className="exam-chat-empty">当前科目暂无可引用资料</p>
              ) : visibleMaterials.map((material) => {
                const selected = selectedMaterialIds.includes(material.id);
                const disabled = (material.parse_status || "success") !== "success" || Number(material.chunk_count || 0) <= 0;
                return (
                  <button
                    key={material.id}
                    type="button"
                    className={`exam-chat-material-item${selected ? " selected" : ""}`}
                    disabled={disabled}
                    onClick={() => toggleMaterial(material)}
                  >
                    <strong>{material.original_filename || material.file_name}</strong>
                    <span>{material.file_type || "文件"} · {formatFileSize(material.file_size)} · {disabled ? "解析未完成" : `${material.chunk_count || 0} 个片段`}</span>
                  </button>
                );
              })}
            </div>
            <div className="exam-chat-material-actions">
              <span>已选择 {selectedMaterials.length} 份</span>
              <button type="button" onClick={() => setSelectedMaterials([])}>清空</button>
              <button type="button" className="primary" onClick={() => setMaterialPickerOpen(false)}>完成</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReferenceList({ references }) {
  return (
    <div className="exam-chat-references">
      <strong>参考资料</strong>
      {references.map((ref, index) => (
        <details key={`${ref.material_id || index}-${ref.filename || index}`}>
          <summary>{ref.filename || "资料片段"}</summary>
          <p>{ref.snippet || ref.chunk_text || ref.chunk_summary || "暂无片段摘要"}</p>
        </details>
      ))}
    </div>
  );
}
