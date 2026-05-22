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
}) {
  const isAssistant = message.role === "assistant";
  const [displayedContent, setDisplayedContent] = useState("");
  const [copied, setCopied] = useState(false);
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

      const board = cardRef.current?.closest(".messages-board");
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
    } catch (error) {
      console.error("复制回答失败：", error);
      setCopied(false);
    }
  };

  return (
    <div
      ref={cardRef}
      className={message.role === "user" ? "message-card user" : "message-card assistant"}
    >
      <div className="message-meta-row">
        <div className="message-role">{message.role === "user" ? "我" : "AI"}</div>
        {isAssistant && (
          <button className="message-copy-button" type="button" onClick={handleCopyAnswer}>
            {copied ? "已复制" : "复制回答"}
          </button>
        )}
      </div>

      {isAssistant ? (
        <MarkdownMessage content={visibleContent} isTyping={Boolean(message.animateTyping)} />
      ) : (
        <div className="message-text">{visibleContent}</div>
      )}

      {message.attachment_type && (
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

      {isAssistant && Array.isArray(message.references) && message.references.length > 0 && (
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
    </div>
  );
}
