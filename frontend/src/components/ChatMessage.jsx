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
  message,
  currentChatSubject,
  addToLibraryState,
  setAddToLibraryState,
  subjectOptions,
  getSubjectLabel,
  getFileTypeLabel,
  getReferenceSnippet,
  addMessageToLibrary,
  openMaterialDetail,
  onAnimationComplete,
  questionText = "",
  learningRecordActionState,
  onSaveLearningRecord,
  getRecordTypeLabel,
  getRecordTypeIcon,
}) {
  const isAssistant = message.role === "assistant";
  const [displayedContent, setDisplayedContent] = useState("");
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const cardRef = useRef(null);
  const visibleContent =
    isAssistant && message.animateTyping ? displayedContent : message.content || "";

  useEffect(() => {
    if (!isAssistant || !message.animateTyping) return undefined;

    let cancelled = false;
    let timerId = 0;
    let index = 0;
    const fullText = message.content || "";
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
      } else if (message.clientId) {
        onAnimationComplete?.(message.clientId);
      }
    };

    timerId = window.setTimeout(tick, 80);

    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [isAssistant, message.animateTyping, message.clientId, message.content, onAnimationComplete]);

  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopyAnswer = async () => {
    try {
      await copyText(message.content || "");
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

  const messageKey = String(message.id || message.clientId || "");
  const savedRecordTypes = Array.isArray(message.savedRecordTypes) ? message.savedRecordTypes : [];

  const msgTime = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : message.created_at
      ? new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
      : "";

  const userInitial = message.userInitial || "?";

  return (
    <div
      ref={cardRef}
      className={`message-card ${message.role === "user" ? "user" : "assistant"}`}
    >
      {/* ── Assistant: avatar + card layout ── */}
      {isAssistant && (
        <>
          <div className="message-avatar-row">
            <div className="message-avatar message-avatar--ai">AI</div>
            <div className="message-time">{msgTime}</div>
          </div>
          <div className="message-body-card">
            <MarkdownMessage content={visibleContent} isTyping={Boolean(message.animateTyping)} />

            {/* References */}
            {Array.isArray(message.references) && message.references.length > 0 && (
              <div className="reference-section">
                <div className="reference-title">参考资料</div>
                <div className="reference-list">
                  {message.references.map((reference, referenceIndex) => (
                    <div key={`${reference.material_id}-${referenceIndex}`} className="reference-card">
                      <div className="reference-name">
                        {referenceIndex + 1}. {reference.filename}
                      </div>
                      <div className="reference-meta">
                        学科：{getSubjectLabel(reference.subject)} | 类型：
                        {getFileTypeLabel(reference.file_type)}
                      </div>
                      <div className="reference-snippet">命中片段：{getReferenceSnippet(reference)}</div>
                      <button
                        className="tiny-button"
                        onClick={() => openMaterialDetail(reference.material_id, "profile")}
                      >
                        查看资料
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!message.references || message.references.length === 0) &&
              Array.isArray(message.rag_sources) &&
              message.rag_sources.length > 0 && (
                <div className="reference-section">
                  <div className="reference-title">参考文件</div>
                  <div className="rag-sources-summary">
                    {message.rag_sources.join("、")}
                  </div>
                </div>
              )}

            {(!message.references || message.references.length === 0) &&
              (!message.rag_sources || message.rag_sources.length === 0) &&
              message.has_bound_materials && (
                <div className="reference-section reference-section--fallback">
                  <div className="reference-title">参考资料</div>
                  <div className="rag-sources-fallback">
                    本轮上传资料中没有找到足够相关的可引用片段，本次回答可能包含模型补充说明。
                  </div>
                </div>
              )}

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
                  learningRecordActionState?.loading &&
                  learningRecordActionState?.messageKey === messageKey &&
                  learningRecordActionState?.recordType === recordType;
                const isSaved = savedRecordTypes.includes(recordType);

                return (
                  <button
                    className={`message-action-text-btn ${isSaved ? "saved" : ""}`}
                    type="button"
                    disabled={isSaving || isSaved}
                    onClick={() =>
                      onSaveLearningRecord?.({
                        messageItem: message,
                        question: questionText,
                        recordType,
                      })
                    }
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
        <>
          <div className="message-avatar-row message-avatar-row--user">
            <div className="message-time">{msgTime}</div>
            <div className="message-avatar message-avatar--user">{userInitial}</div>
          </div>
          <div className="message-bubble-user">
            <div className="message-text">{visibleContent}</div>
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
        </>
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
                  addToLibraryState.messageId === message.id
                    ? addToLibraryState.subject
                    : currentChatSubject
                }
                onChange={(event) =>
                  setAddToLibraryState((prev) => ({
                    ...prev,
                    messageId: message.id,
                    subject: event.target.value,
                  }))
                }
              >
                {subjectOptions.map((item) => (
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
                    addToLibraryState.messageId === message.id
                      ? addToLibraryState.subject
                      : currentChatSubject
                  )
                }
                disabled={addToLibraryState.loading && addToLibraryState.messageId === message.id}
              >
                {addToLibraryState.loading && addToLibraryState.messageId === message.id
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
