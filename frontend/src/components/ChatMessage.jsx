import { useEffect, useRef, useState } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";

function copyText(text) {
  if (navigator?.clipboard?.writeText) {
    return navigator.clipboard.writeText(text);
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
  return Promise.resolve();
}

function getTypingStep(textLength) {
  if (textLength > 2400) return 28;
  if (textLength > 1400) return 18;
  if (textLength > 800) return 12;
  if (textLength > 320) return 6;
  return 3;
}

export default function ChatMessage({
  message = null,
  user = null,
  currentChatSubject = "computer_organization",
  addToLibraryState = {},
  setAddToLibraryState = () => {},
  subjectOptions = [],
  getSubjectLabel = (v) => v,
  getFileTypeLabel = (v) => v,
  getReferenceSnippet = () => "",
  addMessageToLibrary = () => {},
  openMaterialDetail = () => {},
  onAnimationComplete = () => {},
  questionText = "",
  learningRecordActionState = {},
  onSaveLearningRecord = () => {},
  getRecordTypeLabel = (v) => v,
  getRecordTypeIcon = () => "",
  onEditMessage = () => {},
  onVersionChange = () => {},
}) {
  const isAssistant = message && message.role === "assistant";
  const [displayedContent, setDisplayedContent] = useState("");
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const cardRef = useRef(null);

  // ── User-message edit / version / copy states ──
  const isUserMsg = message && message.role === "user";
  const versions = (message && Array.isArray(message.versions) && message.versions.length > 0)
    ? message.versions
    : null;
  const [userCopied, setUserCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [hovered, setHovered] = useState(false);
  const [tooltipEdit, setTooltipEdit] = useState(false);
  const [tooltipCopy, setTooltipCopy] = useState(false);
  const [localVersionIndex, setLocalVersionIndex] = useState(
    (message && message.currentVersionIndex) != null
      ? message.currentVersionIndex
      : versions
        ? versions.length - 1
        : 0
  );

  const totalVersions = versions ? versions.length : 1;
  const currentVersionContent = versions && versions[localVersionIndex]
    ? (versions[localVersionIndex].userContent || versions[localVersionIndex].content || "")
    : (message && message.content) || "";

  const visibleContent =
    isAssistant && message && message.animateTyping ? displayedContent : (message && message.content) || "";

  useEffect(() => {
    if (!isAssistant || !message || !message.animateTyping) return undefined;

    let cancelled = false;
    let timerId = 0;
    let index = 0;
    const fullText = (message && message.content) || "";
    const step = getTypingStep(fullText.length);

    const tick = () => {
      if (cancelled) return;

      index = Math.min(fullText.length, index + step);
      setDisplayedContent(fullText.slice(0, index));

      const board = cardRef.current?.closest(".messages-board") || cardRef.current?.closest(".aiqp-messages-board");
      if (board) {
        board.scrollTop = board.scrollHeight;
      }

      if (index < fullText.length) {
        timerId = window.setTimeout(tick, 18);
      } else if (message && message.clientId) {
        if (typeof onAnimationComplete === "function") onAnimationComplete(message.clientId);
      }
    };

    timerId = window.setTimeout(tick, 80);

    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [isAssistant, message && message.animateTyping, message && message.clientId, message && message.content, onAnimationComplete]);

  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  useEffect(() => {
    if (!userCopied) return undefined;
    const timer = window.setTimeout(() => setUserCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [userCopied]);

  // ── User-message helpers ──

  const handleCopyUserMessage = async () => {
    try {
      await copyText(currentVersionContent);
      setUserCopied(true);
    } catch {
      setUserCopied(false);
    }
  };

  const startEdit = () => {
    setEditContent(currentVersionContent);
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditContent("");
  };

  const submitEdit = () => {
    const trimmed = (editContent || "").trim();
    if (!trimmed) return;
    const msgKey = (message && (message.id || message.clientId)) || "";
    if (typeof onEditMessage === "function") {
      onEditMessage(msgKey, trimmed);
    }
    setIsEditing(false);
    setEditContent("");
  };

  const goToVersion = (dir) => {
    const currentIdx = localVersionIndex;
    let next = currentIdx + dir;
    if (next < 0) next = totalVersions - 1;
    if (next >= totalVersions) next = 0;
    if (next === currentIdx) return;

    setLocalVersionIndex(next);
    const msgKey = (message && (message.id || message.clientId)) || "";
    if (typeof onVersionChange === "function" && versions && versions.length > 1) {
      onVersionChange(msgKey, next);
    }
  };

  const handleCopyAnswer = async () => {
    try {
      await copyText((message && message.content) || "");
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const handleLike = () => {
    setLiked((v) => !v);
    if (disliked) setDisliked(false);
  };

  const handleDislike = () => {
    setDisliked((v) => !v);
    if (liked) setLiked(false);
  };

  const messageKey = String((message && (message.id || message.clientId)) || "");
  const savedRecordTypes = (message && Array.isArray(message.savedRecordTypes)) ? message.savedRecordTypes : [];

  const msgTime = (message && message.timestamp)
    ? new Date(message.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : (message && message.created_at)
      ? new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
      : "";

  const userDisplayName = (user && (user.nickname || user.username)) || "用户";
  const userInitial = userDisplayName.charAt(0);

  return (
    <div
      ref={cardRef}
      className={`message-card ${message && message.role === "user" ? "user" : "assistant"}`}
    >
      {/* ── Assistant: avatar + card layout ── */}
      {isAssistant && (
        <>
          <div className="message-avatar-row">
            <div className="message-avatar message-avatar--ai">AI</div>
            <div className="message-time">{msgTime}</div>
          </div>
          <div className="message-body-card">
            <MarkdownMessage content={visibleContent} isTyping={Boolean(message && message.animateTyping)} />

            {/* Action row: like / dislike / copy / add to 重点 */}
            <div className="message-action-row">
              <button
                className={`message-action-icon-btn ${liked ? "active" : ""}`}
                onClick={handleLike}
                title="点赞"
                type="button"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill={liked ? "#2563eb" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                </svg>
              </button>
              <button
                className={`message-action-icon-btn ${disliked ? "active" : ""}`}
                onClick={handleDislike}
                title="点踩"
                type="button"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill={disliked ? "#ef4444" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                </svg>
              </button>
              <span className="message-action-divider" />
              <button
                className="message-action-text-btn"
                onClick={handleCopyAnswer}
                type="button"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                {copied ? "已复制" : "复制"}
              </button>

              {/* Only "加入重点" — removed 错题本/待复习 */}
              {(() => {
                const recordType = "important";
                const isSaving =
                  learningRecordActionState &&
                  learningRecordActionState.loading &&
                  learningRecordActionState.messageKey === messageKey &&
                  learningRecordActionState.recordType === recordType;
                const isSaved = savedRecordTypes.includes(recordType);

                return (
                  <button
                    className={`message-action-text-btn ${isSaved ? "saved" : ""}`}
                    type="button"
                    disabled={isSaving || isSaved}
                    onClick={() => {
                      if (typeof onSaveLearningRecord === "function") {
                        onSaveLearningRecord({
                          messageItem: message,
                          question: questionText,
                          recordType,
                        });
                      }
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={isSaved ? "#2563eb" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                    </svg>
                    {isSaving ? "保存中..." : isSaved ? "已加入重点" : "加入重点"}
                  </button>
                );
              })()}
            </div>
          </div>
        </>
      )}

      {/* ── User message: right-aligned bubble ── */}
      {!isAssistant && (
        <div
          className="user-message-wrapper"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => {
            setHovered(false);
            setTooltipEdit(false);
            setTooltipCopy(false);
          }}
        >
          <div className="message-avatar-row message-avatar-row--user">
            <div className="message-time">{msgTime}</div>
            <div className="message-avatar message-avatar--user">
              {(user && user.avatar_url && (user.avatar_url || "").startsWith("/me/avatar/")) ? (
                <img src={`/api${user.avatar_url}?username=${encodeURIComponent(user.username || "")}`} alt="" className="msg-avatar-img" />
              ) : (
                userInitial
              )}
            </div>
          </div>

          {isEditing ? (
            <div className="message-bubble-user message-bubble-user--editing">
              <textarea
                className="user-msg-edit-input"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submitEdit();
                  }
                  if (e.key === "Escape") cancelEdit();
                }}
                autoFocus
                rows={3}
              />
              <div className="user-msg-edit-actions">
                <span className="user-msg-edit-hint">Enter 提交 · Esc 取消</span>
                <div className="user-msg-edit-btns">
                  <button className="user-msg-edit-btn user-msg-edit-btn--cancel" type="button" onClick={cancelEdit}>
                    取消
                  </button>
                  <button className="user-msg-edit-btn user-msg-edit-btn--submit" type="button" onClick={submitEdit}>
                    提交
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="message-bubble-user">
              <div className="message-text">{currentVersionContent}</div>
            </div>
          )}

          {/* Action bar below user bubble */}
          <div className="user-msg-action-bar">
            <div className="user-msg-action-left">
              {(message && message.edited) && <span className="user-msg-edited-badge">已编辑</span>}
              {versions && versions.length > 1 && (
                <div className="user-msg-version-switcher">
                  <button
                    className="user-msg-version-btn"
                    type="button"
                    onClick={() => goToVersion(-1)}
                    title="上一版本"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6" /></svg>
                  </button>
                  <span className="user-msg-version-num">{localVersionIndex + 1}/{totalVersions}</span>
                  <button
                    className="user-msg-version-btn"
                    type="button"
                    onClick={() => goToVersion(1)}
                    title="下一版本"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="9 18 15 12 9 6" /></svg>
                  </button>
                </div>
              )}
            </div>
            <div className="user-msg-action-right">
              <div className="user-msg-icon-wrap">
                <button
                  className="user-msg-icon-btn"
                  type="button"
                  onClick={startEdit}
                  onMouseEnter={() => setTooltipEdit(true)}
                  onMouseLeave={() => setTooltipEdit(false)}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                {tooltipEdit && (
                  <span className="user-msg-tooltip user-msg-tooltip--show">修改消息</span>
                )}
              </div>
              <div className="user-msg-icon-wrap">
                <button
                  className="user-msg-icon-btn"
                  type="button"
                  onClick={handleCopyUserMessage}
                  onMouseEnter={() => setTooltipCopy(true)}
                  onMouseLeave={() => setTooltipCopy(false)}
                >
                  {userCopied ? (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  )}
                </button>
                {tooltipCopy && (
                  <span className="user-msg-tooltip user-msg-tooltip--show">
                    {userCopied ? "已复制" : "复制消息"}
                  </span>
                )}
              </div>
            </div>
          </div>

          {Array.isArray(message.attachments) && message.attachments.length > 0 && (
            <div className="attachment-card">
              {message.attachments.map((attachment) => (
                <div key={attachment.material_id || attachment.original_filename} className="attachment-meta">
                  <span className="subject-pill small">{getFileTypeLabel(attachment.file_type)}</span>
                  <span>{attachment.original_filename || "未命名文件"}</span>
                  <span>{attachment.parse_status === "success" ? "已解析" : attachment.parse_status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Attachment info for assistant ── */}
      {isAssistant && message.attachment_type && (
        <div className="attachment-card">
          <div className="attachment-meta">
            <span className="subject-pill small">{getFileTypeLabel(message.attachment_type)}</span>
            <span>{message.attachment_filename || "未命名附件"}</span>
          </div>
          {message.extracted_text && (
            <div className="attachment-preview">
              {message.extracted_text.slice(0, 240)}
              {message.extracted_text.length > 240 ? "..." : ""}
            </div>
          )}

          {message.material_id ? (
            <button className="ghost-button compact" disabled>
              已加入资料库
            </button>
          ) : (
            <div className="attachment-actions">
              <select
                className="field attachment-subject-select"
                value={
                  addToLibraryState && addToLibraryState.messageId === (message && message.id)
                    ? addToLibraryState.subject
                    : currentChatSubject
                }
                onChange={(event) =>
                  setAddToLibraryState((prev) => ({
                    ...prev,
                    messageId: message && message.id,
                    subject: event.target.value,
                  }))
                }
              >
                {Array.isArray(subjectOptions) && subjectOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>
              <button
                className="tiny-button"
                onClick={() =>
                  addMessageToLibrary(
                    message,
                    addToLibraryState && addToLibraryState.messageId === (message && message.id)
                      ? addToLibraryState.subject
                      : currentChatSubject
                  )
                }
                disabled={addToLibraryState && addToLibraryState.loading && addToLibraryState.messageId === (message && message.id)}
              >
                {addToLibraryState && addToLibraryState.loading && addToLibraryState.messageId === (message && message.id)
                  ? "添加中..."
                  : "加入资料库"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
