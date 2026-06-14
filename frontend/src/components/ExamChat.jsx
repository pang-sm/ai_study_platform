import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";
import MaterialPickerModal from "./MaterialPickerModal.jsx";

const API_BASE = "/api";
const ALLOWED_UPLOAD_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb";

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

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getFileTypeLabel(type) {
  const normalized = String(type || "").toLowerCase();
  if (!normalized) return "未知";
  if (normalized.includes("pdf")) return "PDF";
  if (normalized.includes("doc")) return "Word";
  if (normalized.includes("ppt")) return "PPT";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(normalized)) return "图片";
  if (["txt", "md", "markdown"].includes(normalized)) return "文本";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash", "html", "css", "json", "xml", "yaml", "yml"].includes(normalized)) return "代码";
  return normalized.toUpperCase();
}

function getParseStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "success") return "已索引";
  if (normalized === "partial") return "部分索引";
  if (normalized === "pending") return "等待解析";
  if (normalized === "parsing") return "解析中";
  if (normalized === "failed") return "解析失败";
  return "未索引";
}

function getRecommendations(subjectKey) {
  return SUBJECT_RECOMMENDATIONS[subjectKey] || SUBJECT_RECOMMENDATIONS.data_structure;
}

function normalizeUploadedMaterial(data, file) {
  const id = data.material_id || data.id;
  if (!id) return null;
  return {
    id,
    material_id: id,
    original_filename: data.filename || data.original_filename || file?.name || "未命名资料",
    file_name: data.filename || data.original_filename || file?.name || "未命名资料",
    file_type: data.file_type || file?.name?.split(".").pop()?.toLowerCase() || "",
    file_size: data.file_size || file?.size || 0,
    parse_status: data.parse_status || "pending",
    parse_progress: data.parse_progress || 0,
    chunk_count: data.chunk_count || 0,
  };
}

export default function ExamChat({
  user,
  subjectKey,
  subjectTitle,
  courseName,
  onBackDashboard,
}) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedMaterials, setSelectedMaterials] = useState([]);
  const [libraryMaterials, setLibraryMaterials] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [librarySearchQuery, setLibrarySearchQuery] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [toolMenuOpen, setToolMenuOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const currentSessionIdRef = useRef(null);
  const uploadInputRef = useRef(null);
  const toolMenuRef = useRef(null);

  const recommendations = useMemo(() => getRecommendations(subjectKey).slice(0, 5), [subjectKey]);
  const sessionStorageKey = `exam_chat_session_${subjectKey}`;

  const canReferenceMaterial = useCallback((material) => {
    const status = String(material?.parse_status || "").toLowerCase();
    return (status === "success" || status === "partial") && Number(material?.chunk_count || 0) > 0;
  }, []);

  const getUnreferenceableReason = useCallback((material) => {
    const status = String(material?.parse_status || "").toLowerCase();
    if (status === "pending" || status === "parsing") return "资料正在解析，完成后可引用";
    if (status === "failed") return "资料解析失败，不能用于问答";
    if ((status === "success" || status === "partial") && Number(material?.chunk_count || 0) <= 0) {
      return "尚未生成知识片段";
    }
    return "暂不可引用";
  }, []);

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

  const loadMaterials = useCallback(async () => {
    if (!user?.username) return [];
    setLibraryLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      if (courseName) query.set("subject", courseName);
      const res = await fetch(`${API_BASE}/materials?${query.toString()}`);
      const data = await res.json().catch(() => ({}));
      const materials = res.ok && Array.isArray(data.materials) ? data.materials : [];
      setLibraryMaterials(materials);
      return materials;
    } catch {
      setLibraryMaterials([]);
      return [];
    } finally {
      setLibraryLoading(false);
    }
  }, [courseName, user?.username]);

  const updateCurrentSessionId = useCallback((sessionId) => {
    const nextSessionId = sessionId === null || sessionId === undefined || sessionId === ""
      ? null
      : Number(sessionId);
    const safeSessionId = Number.isNaN(nextSessionId) ? sessionId : nextSessionId;
    currentSessionIdRef.current = safeSessionId;
    setCurrentSessionId(safeSessionId);
    if (safeSessionId) {
      try { localStorage.setItem(sessionStorageKey, String(safeSessionId)); } catch { /* ignore */ }
    }
  }, [sessionStorageKey]);

  const loadSession = useCallback(async (sessionId) => {
    if (!user?.username || !sessionId) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "加载历史对话失败");
      updateCurrentSessionId(sessionId);
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
  }, [updateCurrentSessionId, user?.username]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    const savedSessionId = (() => {
      try { return localStorage.getItem(sessionStorageKey); } catch { return null; }
    })();
    if (savedSessionId) loadSession(savedSessionId);
  }, [loadSession, sessionStorageKey]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    if (!toolMenuOpen) return;
    const handlePointerDown = (event) => {
      if (!toolMenuRef.current?.contains(event.target)) {
        setToolMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [toolMenuOpen]);

  const openMaterialPicker = async () => {
    setToolMenuOpen(false);
    setPickerOpen(true);
    setLibrarySearchQuery("");
    await loadMaterials();
  };

  const openUploadPicker = () => {
    setToolMenuOpen(false);
    uploadInputRef.current?.click();
  };

  const startNewConversation = () => {
    updateCurrentSessionId(null);
    try { localStorage.removeItem(sessionStorageKey); } catch { /* ignore */ }
    setMessages([]);
    setInputText("");
    setError("");
    setNotice("");
  };

  const deleteSession = async (sessionId, event) => {
    event.stopPropagation();
    if (!user?.username) return;
    try {
      await fetch(`${API_BASE}/chat/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      if (currentSessionIdRef.current === sessionId || Number(currentSessionIdRef.current) === Number(sessionId)) {
        startNewConversation();
      }
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

  const toggleMaterialSelection = (material) => {
    if (!canReferenceMaterial(material)) return;
    setSelectedMaterials((prev) => {
      const exists = prev.some((item) => item.id === material.id);
      if (exists) return prev.filter((item) => item.id !== material.id);
      return [...prev, material];
    });
  };

  const removeSelectedMaterial = (materialId) => {
    setSelectedMaterials((prev) => prev.filter((item) => item.id !== materialId));
  };

  const handleUploadFiles = async (files) => {
    const fileList = Array.from(files || []);
    if (fileList.length === 0 || !user?.username) return;
    setUploading(true);
    setError("");
    setNotice("");
    try {
      const uploadedMaterials = [];
      for (const file of fileList) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("username", user.username);
        formData.append("subject", courseName || subjectTitle);
        formData.append("save_to_materials", "true");
        const res = await fetch(`${API_BASE}/materials/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${user.username}` },
          body: formData,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `上传失败：${file.name}`);
        const material = normalizeUploadedMaterial(data, file);
        if (material) uploadedMaterials.push(material);
      }
      const latestMaterials = await loadMaterials();
      const byId = new Map(latestMaterials.map((material) => [material.id, material]));
      const readyUploads = uploadedMaterials
        .map((material) => byId.get(material.id) || material)
        .filter(canReferenceMaterial);
      if (readyUploads.length > 0) {
        setSelectedMaterials((prev) => {
          const existing = new Set(prev.map((item) => item.id));
          return [...prev, ...readyUploads.filter((item) => !existing.has(item.id))];
        });
        setNotice("资料已上传并加入本轮引用");
      } else {
        setNotice("资料已上传，解析完成后可在资料选择中引用");
      }
    } catch (err) {
      setError(err.message || "资料上传失败");
    } finally {
      setUploading(false);
    }
  };

  const sendMessage = async (text) => {
    const msg = (text || inputText).trim();
    if (!msg || loading || !user?.username) return;
    const activeSessionId = currentSessionIdRef.current;

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
        session_id: activeSessionId,
        subject: subjectTitle,
        course: courseName,
        material_ids: selectedMaterials.filter(canReferenceMaterial).map((material) => material.id),
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

      const nextSessionId = data.session?.id ?? data.session_id ?? activeSessionId;
      if (nextSessionId) {
        updateCurrentSessionId(nextSessionId);
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
        </header>

        {error && (
          <div className="examchat-error">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>关闭</button>
          </div>
        )}
        {notice && !error && (
          <div className="examchat-notice">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice("")}>知道了</button>
          </div>
        )}

        <div className="examchat-messages">
          {messages.length === 0 && !loading ? (
            <div className="examchat-empty" />
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
                      <strong>参考资料</strong>
                      {message.references.map((reference, index) => {
                        const title = reference.source_filename || reference.filename || `资料 ${index + 1}`;
                        const summary = reference.chunk_summary || reference.summary || reference.snippet || "";
                        const text = reference.chunk_text || reference.text || "";
                        return (
                          <details key={`${reference.material_id || index}-${index}`} className="examchat-ref-detail">
                            <summary>{title}</summary>
                            {summary && <p>{summary}</p>}
                            {text && <pre>{text}</pre>}
                          </details>
                        );
                      })}
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
          {selectedMaterials.length > 0 && (
            <div className="examchat-selected-bar">
              {selectedMaterials.map((material) => (
                <button key={material.id} type="button" onClick={() => removeSelectedMaterial(material.id)}>
                  {material.original_filename || material.file_name || "资料"} ×
                </button>
              ))}
            </div>
          )}
          <div className="examchat-input-row">
            <div className="examchat-plus-wrap" ref={toolMenuRef}>
              <button
                type="button"
                className={`examchat-plus-btn${toolMenuOpen ? " active" : ""}`}
                onClick={() => setToolMenuOpen((open) => !open)}
                aria-label="添加资料"
                aria-expanded={toolMenuOpen}
              >
                +
              </button>
              {toolMenuOpen && (
                <div className="examchat-plus-menu">
                  <button type="button" onClick={openMaterialPicker}>
                    <span aria-hidden="true">▣</span>
                    引用资料
                  </button>
                  <button type="button" onClick={openUploadPicker} disabled={uploading}>
                    <span aria-hidden="true">⇧</span>
                    {uploading ? "上传中..." : "上传资料"}
                  </button>
                </div>
              )}
            </div>
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
              <span className="examchat-send-icon">➤</span>
              <span>{loading ? "发送中" : "发送"}</span>
            </button>
          </div>
          <input
            ref={uploadInputRef}
            type="file"
            multiple
            accept={ALLOWED_UPLOAD_EXTENSIONS}
            onChange={(event) => {
              handleUploadFiles(event.target.files);
              event.target.value = "";
            }}
            style={{ display: "none" }}
          />
        </div>
      </section>

      <aside className="examchat-sidebar">
        <div className="examchat-side-card">
          <div className="examchat-side-title">
            <h4>本轮引用资料</h4>
          </div>
          {selectedMaterials.length === 0 ? (
            <div className="examchat-side-empty">
              <p>尚未引用资料。</p>
            </div>
          ) : (
            <ul className="examchat-ref-list">
              {selectedMaterials.map((material) => (
                <li key={material.id}>
                  <span title={material.original_filename || material.file_name}>
                    {material.original_filename || material.file_name}
                  </span>
                  <button type="button" onClick={() => removeSelectedMaterial(material.id)}>
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
            <button key={question} type="button" className="examchat-rec-btn" onClick={() => setInputText(question)}>
              {question}
            </button>
          ))}
        </div>
      </aside>

      <MaterialPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        subjectLabel={courseName || subjectTitle}
        materials={libraryMaterials}
        loading={libraryLoading}
        searchQuery={librarySearchQuery}
        onSearchChange={setLibrarySearchQuery}
        selectedMaterials={selectedMaterials}
        onToggleMaterial={toggleMaterialSelection}
        canReferenceMaterial={canReferenceMaterial}
        getUnreferenceableReason={getUnreferenceableReason}
        getFileTypeLabel={getFileTypeLabel}
        formatFileSize={formatFileSize}
        getParseStatusLabel={getParseStatusLabel}
      />
    </div>
  );
}
