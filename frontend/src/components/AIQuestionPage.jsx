import { useState, useRef } from "react";
import ChatMessage from "./ChatMessage.jsx";
import "./AIQuestionPage.css";

const RECOMMENDATION_POOLS = [
  "请帮我总结${subject}的核心知识点",
  "${subject}有哪些常见的考点和难点？",
  "请举例说明${subject}中的一个重要概念",
  "帮我整理${subject}的知识框架和脉络",
  "在学习${subject}时需要注意哪些问题？",
  "${subject}的学习路径应该如何规划？",
  "可以给我出一道${subject}的练习题吗？",
  "请对比${subject}中容易混淆的概念",
  "${subject}在实际中有哪些应用场景？",
  "帮我分析${subject}的知识结构图",
];

function shufflePool(pool, count) {
  const shuffled = [...pool];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, count);
}

export default function AIQuestionPage({
  user,
  apiBase,
  subject,
  setSubject,
  setPage,
  COURSE_OPTIONS,
  AVATARS,
  getSubjectLabel,
  activeSessionId,
  setActiveSessionSubject,

  currentChatSubject,
  messages,
  loading,
  tip,
  message,
  setMessage,
  sendMessage,
  canSendMessage,

  selectedFiles,
  selectedLibraryMaterials,
  removeSelectedFile,
  removeSelectedLibraryMaterial,
  handleFileChange,
  formatFileSize,
  getSelectedFileStatusText,
  selectedFilesBlockReason,

  showPlusMenu,
  setShowPlusMenu,
  plusMenuRef,
  openLibraryReferenceModal,
  fileInputRef,

  addToLibraryState,
  setAddToLibraryState,
  getFileTypeLabel,
  getReferenceSnippet,
  addMessageToLibrary,
  openMaterialDetail,
  finishAssistantTyping,
  getQuestionForAssistantMessage,
  learningRecordActionState,
  saveLearningRecord,
  getRecordTypeLabel,
  getRecordTypeIcon,
}) {
  const [suggestionBatch, setSuggestionBatch] = useState(() => {
    const subjectLabel = getSubjectLabel(currentChatSubject);
    return shufflePool(RECOMMENDATION_POOLS, 5).map((t) =>
      t.replace("${subject}", subjectLabel)
    );
  });

  const refreshSuggestions = () => {
    const subjectLabel = getSubjectLabel(currentChatSubject);
    setSuggestionBatch(
      shufflePool(RECOMMENDATION_POOLS, 5).map((t) =>
        t.replace("${subject}", subjectLabel)
      )
    );
  };

  const avatarObj = AVATARS.find((a) => a.id === (user?.avatar || "")) || AVATARS[0];
  const hasCustomAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

  const referencedFiles = selectedFiles.filter((f) => !f.uploading);
  const hasReferences =
    referencedFiles.length > 0 || selectedLibraryMaterials.length > 0;

  return (
    <div className="aiqp-shell">
      {/* ═══════════════════════════════════════════════════════════════════
          A. TOP BAR — site-level only, no course workspace tabs
          ═══════════════════════════════════════════════════════════════════ */}
      <header className="aiqp-topbar">
        <div className="aiqp-topbar-left">
          <select
            className="aiqp-subject-select"
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              if (!activeSessionId) {
                setActiveSessionSubject(e.target.value);
              }
            }}
          >
            {COURSE_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>
        </div>

        <div className="aiqp-topbar-search">
          <span className="aiqp-search-icon">🔍</span>
          <input
            className="aiqp-search-input"
            type="text"
            placeholder="搜索课程、资料、知识点..."
          />
        </div>

        <div className="aiqp-topbar-actions">
          <button className="aiqp-icon-btn" title="通知">
            <span className="aiqp-icon-bell">🔔</span>
            <span className="aiqp-badge">3</span>
          </button>

          <div
            className="aiqp-topbar-user aiqp-clickable"
            onClick={() => setPage("profile")}
            title="个人主页"
          >
            {hasCustomAvatar ? (
              <img
                className="aiqp-topbar-avatar"
                src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`}
                alt="头像"
              />
            ) : (
              <div
                className="aiqp-topbar-avatar"
                style={{ background: avatarObj.background }}
              >
                {(user?.nickname || user?.username || "?").charAt(0)}
              </div>
            )}
            <span className="aiqp-topbar-username">
              {user?.nickname || user?.username || "admin"}
            </span>
          </div>
        </div>
      </header>

      {/* ═══════════════════════════════════════════════════════════════════
          B. TITLE AREA
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="aiqp-title-area">
        <div className="aiqp-title-inner">
          <div className="aiqp-title-icon">🤖</div>
          <div className="aiqp-title-text">
            <h1 className="aiqp-title-heading">AI 智能问答</h1>
            <p className="aiqp-title-sub">
              基于课程资料与历史记录进行高相关问答
            </p>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          C. MAIN CONTENT — two-column layout
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="aiqp-main">
        <div className="aiqp-layout">
          {/* ── Left: chat panel ── */}
          <section className="aiqp-chat">
            <div className="aiqp-chat-subject-bar">
              <span className="aiqp-chat-subject-label">当前对话</span>
              <span className="aiqp-chat-subject-value">
                学科：{getSubjectLabel(currentChatSubject)}
              </span>
            </div>

            <div className="aiqp-messages-board">
              {messages.length === 0 && (
                <div className="aiqp-empty-state">
                  <div className="aiqp-empty-icon">💬</div>
                  <p className="aiqp-empty-title">开始你的 AI 问答之旅</p>
                  <p className="aiqp-empty-hint">
                    在下方输入你的问题，或点击 + 上传资料后基于资料提问。
                  </p>
                </div>
              )}

              {messages.map((msg, index) => (
                <ChatMessage
                  key={msg.id || msg.clientId || index}
                  message={msg}
                  currentChatSubject={currentChatSubject}
                  addToLibraryState={addToLibraryState}
                  setAddToLibraryState={setAddToLibraryState}
                  subjectOptions={COURSE_OPTIONS}
                  getSubjectLabel={getSubjectLabel}
                  getFileTypeLabel={getFileTypeLabel}
                  getReferenceSnippet={getReferenceSnippet}
                  addMessageToLibrary={addMessageToLibrary}
                  openMaterialDetail={openMaterialDetail}
                  onAnimationComplete={finishAssistantTyping}
                  questionText={getQuestionForAssistantMessage(index)}
                  learningRecordActionState={learningRecordActionState}
                  onSaveLearningRecord={saveLearningRecord}
                  getRecordTypeLabel={getRecordTypeLabel}
                  getRecordTypeIcon={getRecordTypeIcon}
                />
              ))}

              {loading && (
                <div className="aiqp-thinking-card">
                  <div className="aiqp-thinking-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                  <span className="aiqp-thinking-text">AI 正在思考...</span>
                </div>
              )}
            </div>

            <div className="aiqp-composer">
              {selectedFiles.length > 0 && (
                <div className="aiqp-attachments-row">
                  {selectedFiles.map((item) => (
                    <div
                      key={item.localId}
                      className={`aiqp-attachment-card ${item.parse_status === "failed" ? "aiqp-attachment-card--failed" : ""}`}
                    >
                      <div className="aiqp-attachment-card-header">
                        <span className="aiqp-attachment-card-type">
                          {getFileTypeLabel(item.file_type || item.type)}
                        </span>
                        <button
                          className="aiqp-attachment-card-remove"
                          onClick={() => removeSelectedFile(item.localId)}
                          type="button"
                          title="从本次提问移除"
                        >
                          ×
                        </button>
                      </div>
                      <div
                        className="aiqp-attachment-card-name"
                        title={item.original_filename}
                      >
                        {item.original_filename}
                      </div>
                      <div className="aiqp-attachment-card-meta">
                        <span>{formatFileSize(item.file_size)}</span>
                        <span
                          className={`aiqp-attachment-card-status aiqp-attachment-card-status--${item.parse_status}`}
                        >
                          {getSelectedFileStatusText(item)}
                          {Number(item.parse_progress || 0) > 0 &&
                          item.parse_status === "parsing"
                            ? ` ${Math.round(Number(item.parse_progress || 0))}%`
                            : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {selectedFilesBlockReason && (
                <div className="aiqp-composer-hint">
                  {selectedFilesBlockReason}
                </div>
              )}

              {selectedLibraryMaterials.length > 0 && (
                <div className="aiqp-library-bar">
                  <div className="aiqp-library-bar-title">
                    已引用资料库资料
                  </div>
                  <div className="aiqp-library-bar-list">
                    {selectedLibraryMaterials.map((material) => (
                      <div key={material.id} className="aiqp-library-chip">
                        <span className="aiqp-library-chip-name">
                          {material.original_filename}
                        </span>
                        <span className="aiqp-library-chip-type">
                          {getFileTypeLabel(material.file_type)}
                        </span>
                        <span className="aiqp-library-chip-source">
                          来自资料库
                        </span>
                        <button
                          className="aiqp-library-chip-remove"
                          title="从本次提问中移除"
                          onClick={() =>
                            removeSelectedLibraryMaterial(material.id)
                          }
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="aiqp-composer-row">
                <div className="aiqp-plus-menu-wrapper" ref={plusMenuRef}>
                  <button
                    className="aiqp-attach-button"
                    type="button"
                    onClick={() => setShowPlusMenu((v) => !v)}
                    disabled={loading}
                    title="添加资料"
                  >
                    +
                  </button>
                  {showPlusMenu && (
                    <div className="aiqp-plus-menu">
                      <button
                        className="aiqp-plus-menu-item"
                        type="button"
                        onClick={() => {
                          setShowPlusMenu(false);
                          fileInputRef.current?.click();
                        }}
                      >
                        上传新文件
                      </button>
                      <button
                        className="aiqp-plus-menu-item"
                        type="button"
                        onClick={() => {
                          setShowPlusMenu(false);
                          openLibraryReferenceModal();
                        }}
                      >
                        引用资料库文件
                      </button>
                    </div>
                  )}
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
                  onChange={handleFileChange}
                  className="aiqp-hidden-file-input"
                />

                <input
                  className="aiqp-composer-input"
                  placeholder={
                    selectedFiles.length > 0
                      ? "请输入你想基于这些资料提问的问题"
                      : "请输入你的问题，支持上传图片或文件..."
                  }
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                />

                <button
                  className="aiqp-send-button"
                  onClick={sendMessage}
                  disabled={!canSendMessage}
                >
                  {loading ? "发送中..." : "发送"}
                </button>

                <label className="aiqp-add-material-btn" title="添加资料">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
                    onChange={handleFileChange}
                    className="aiqp-hidden-file-input"
                  />
                  添加资料
                </label>
              </div>

              {tip && <p className="aiqp-tip-text">{tip}</p>}
            </div>
          </section>

          {/* ── Right: info sidebar ── */}
          <aside className="aiqp-sidebar">
            <div className="aiqp-sidebar-card">
              <div className="aiqp-sidebar-card-header">
                <h4 className="aiqp-sidebar-card-title">本轮已引用资料</h4>
              </div>
              {hasReferences ? (
                <div className="aiqp-ref-list">
                  {referencedFiles.map((item) => (
                    <div key={item.localId} className="aiqp-ref-item">
                      <span className="aiqp-ref-icon">📄</span>
                      <div className="aiqp-ref-info">
                        <span className="aiqp-ref-name">
                          {item.original_filename}
                        </span>
                        <span className="aiqp-ref-desc">
                          {formatFileSize(item.file_size)} ·{" "}
                          {getFileTypeLabel(item.file_type || item.type)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {selectedLibraryMaterials.map((item) => (
                    <div key={item.id} className="aiqp-ref-item">
                      <span className="aiqp-ref-icon">📚</span>
                      <div className="aiqp-ref-info">
                        <span className="aiqp-ref-name">
                          {item.original_filename}
                        </span>
                        <span className="aiqp-ref-desc">
                          {formatFileSize(item.file_size)} ·{" "}
                          {getFileTypeLabel(item.file_type)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="aiqp-ref-empty">
                  尚未引用资料，点击输入框左侧 + 上传或引用资料库文件
                </p>
              )}
              <button
                className="aiqp-ref-all-link"
                onClick={() => {
                  setPage("workspaceMaterials");
                }}
              >
                全部资料库 →
              </button>
            </div>

            <div className="aiqp-sidebar-card">
              <div className="aiqp-sidebar-card-header">
                <h4 className="aiqp-sidebar-card-title">推荐提问</h4>
                <button
                  className="aiqp-refresh-btn"
                  onClick={refreshSuggestions}
                  title="换一批"
                >
                  换一批
                </button>
              </div>
              <div className="aiqp-suggestions">
                {suggestionBatch.map((q, i) => (
                  <button
                    key={i}
                    className="aiqp-suggestion-item"
                    onClick={() => {
                      setMessage(q);
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
