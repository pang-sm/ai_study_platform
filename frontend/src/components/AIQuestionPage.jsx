import { useState, useRef, useEffect, useCallback } from "react";
import ChatMessage from "./ChatMessage.jsx";
import MarkdownMessage from "./MarkdownMessage.jsx";
import GlobalSearchBox from "./GlobalSearchBox.jsx";
import "./AIQuestionPage.css";

const RECOMMENDATION_POOL = [
  "指令周期各阶段的功能是什么？",
  "流水线执行与非流水线执行的区别？",
  "什么是 CPI？如何影响 CPU 性能？",
  "存储器层次结构是怎样的？",
  "总线的分类和作用是什么？",
  "请帮我总结${subject}的核心知识点",
  "${subject}有哪些常见的考点和难点？",
  "请举例说明${subject}中的一个重要概念",
];

const KNOWLEDGE_STATUS_OPTIONS = [
  { status: "not_started", label: "未开始", color: "#94a3b8", bg: "#f8fafc", score: 0 },
  { status: "learning", label: "学习中", color: "#2563eb", bg: "#eff6ff", score: 40 },
  { status: "mastered", label: "已掌握", color: "#059669", bg: "#ecfdf5", score: 100 },
];

const KNOWLEDGE_STATUS_LABELS = {
  mastered: "已掌握",
  learning: "学习中",
  not_started: "未开始",
};

function normalizeKnowledgeStatus(status) {
  if (!status) return "not_started";
  const s = String(status).trim();
  // Direct 3-state values
  if (s === "not_started" || s === "未开始") return "not_started";
  if (s === "learning" || s === "学习中") return "learning";
  if (s === "mastered" || s === "已掌握") return "mastered";
  // Legacy → learning
  if (s === "need_review" || s === "需要复习" || s === "待复习" ||
      s === "review" || s === "reviewing" || s === "needs_review" ||
      s === "not_understood" || s === "还没理解" || s === "薄弱" ||
      s === "weak" || s === "confused" ||
      s === "in_progress" || s === "studying") return "learning";
  // Legacy → mastered
  if (s === "done" || s === "completed") return "mastered";
  // Legacy → not_started
  if (s === "later" || s === "稍后再学" || s === "postponed") return "not_started";
  return "not_started";
}

function shufflePool(pool, count) {
  const shuffled = [...pool];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, count);
}

export default function AIQuestionPage({
  user = null,
  apiBase = "/api",
  subject = "computer_organization",
  setSubject = () => {},
  setPage = () => {},
  COURSE_OPTIONS = [],
  AVATARS = [],
  getSubjectLabel = (v) => v,
  activeSessionId = null,
  setActiveSessionSubject = () => {},

  currentChatSubject = "computer_organization",
  messages = [],
  loading = false,
  tip = "",
  message = "",
  setMessage = () => {},
  sendMessage = () => {},
  canSendMessage = false,

  selectedFiles = [],
  selectedLibraryMaterials = [],
  removeSelectedFile = () => {},
  removeSelectedLibraryMaterial = () => {},
  handleFileChange = () => {},
  formatFileSize = (v) => v,
  getSelectedFileStatusText = () => "",
  selectedFilesBlockReason = "",

  showPlusMenu = false,
  setShowPlusMenu = () => {},
  plusMenuRef = null,
  openLibraryReferenceModal = () => {},
  fileInputRef = null,

  addToLibraryState = {},
  setAddToLibraryState = () => {},
  getFileTypeLabel = (v) => v,
  getReferenceSnippet = () => "",
  addMessageToLibrary = () => {},
  openMaterialDetail = () => {},
  finishAssistantTyping = () => {},
  getQuestionForAssistantMessage = () => "",
  learningRecordActionState = {},
  saveLearningRecord = () => {},
  getRecordTypeLabel = (v) => v,
  getRecordTypeIcon = () => "",

  startNewConversation = () => {},
  chatSessions = [],
  openChatSession = () => {},
  loadChatSessions = () => {},
  onEditMessage = () => {},
  onVersionChange = () => {},
  pendingAIContext = null,
  setPendingAIContext = () => {},
  setSearchContext = null,
  setSearchNavigate = null,
}) {
  const [suggestionBatch, setSuggestionBatch] = useState(() =>
    shufflePool(RECOMMENDATION_POOL, 5)
  );
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historyFilterSubject, setHistoryFilterSubject] = useState("all");
  const [historySearchQuery, setHistorySearchQuery] = useState("");
  const [selectedHistorySession, setSelectedHistorySession] = useState(null);
  const [previewMessages, setPreviewMessages] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [kpStatusSaving, setKpStatusSaving] = useState(false);
  const [kpStatusError, setKpStatusError] = useState("");
  const [isKpContextExpanded, setIsKpContextExpanded] = useState(false);

  useEffect(() => {
    setIsKpContextExpanded(false);
  }, [pendingAIContext?.pointId, pendingAIContext?.knowledgePointTitle]);

  const refreshSuggestions = () => {
    const subjectLabel = getSubjectLabel(currentChatSubject);
    setSuggestionBatch(
      shufflePool(RECOMMENDATION_POOL, 5).map((t) =>
        t.replace("${subject}", subjectLabel)
      )
    );
  };

  const avatarObj = Array.isArray(AVATARS)
    ? (AVATARS.find((a) => a.id === (user?.avatar || "")) || AVATARS[0])
    : { background: "#2563eb" };
  const hasCustomAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

  function handleGlobalSearch(query, resultItem) {
    if (resultItem) {
      const t = resultItem.target || {};
      if (!t.page) return;
      if (t.courseId && typeof setSubject === "function") {
        setSubject(t.courseId);
      }
      if (setSearchNavigate) {
        setSearchNavigate({
          fromSearch: true,
          page: t.page,
          courseId: t.courseId || "",
          materialId: t.materialId,
          knowledgePointId: t.knowledgePointId,
          taskId: t.taskId,
          questionId: t.questionId,
          conversationId: t.conversationId,
          tab: t.tab,
        });
      }
      setPage(t.page);
      return;
    }
    if (query) {
      if (setSearchContext) setSearchContext({ q: query });
      setPage("searchResults");
    }
  }

  const referencedFiles = Array.isArray(selectedFiles) ? selectedFiles.filter((f) => !f.uploading) : [];

  function cleanDisplayText(text) {
    if (!text) return "";
    let s = String(text);
    // Strip HTML tags
    s = s.replace(/<[^>]*>/g, "");
    // Strip LaTeX math delimiters ($, $$, \(, \), \[, \])
    s = s.replace(/\$\$/g, "").replace(/\$/g, "").replace(/\\[\(\[]/g, "").replace(/\\[\)\]]/g, "");
    // Strip Markdown link syntax [...](url)
    s = s.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
    // Strip Markdown emphasis markers
    s = s.replace(/[*_~`]{1,3}/g, "");
    // Collapse whitespace
    s = s.replace(/\s+/g, " ").trim();
    return s;
  }

  const dedupeMaterials = (items) => {
    const map = new Map();
    (items || []).forEach((item) => {
      const key = item.material_id || item.filename || item.file_name || item.title || item.source || item.path || item.original_filename;
      if (!key) return;
      if (!map.has(key)) {
        map.set(key, { ...item, _pages: [] });
      }
      const existed = map.get(key);
      if (item.page) existed._pages.push(item.page);
      if (item.page_range) existed._pages.push(item.page_range);
    });
    return Array.from(map.values());
  };

  const aiReferences = dedupeMaterials(
    Array.isArray(messages)
      ? messages.filter((m) => m && m.role === "assistant").flatMap((m) => m.references || [])
      : []
  );

  const hasReferences =
    referencedFiles.length > 0 ||
    (Array.isArray(selectedLibraryMaterials) && selectedLibraryMaterials.length > 0) ||
    aiReferences.length > 0;
  const refCount =
    referencedFiles.length +
    (Array.isArray(selectedLibraryMaterials) ? selectedLibraryMaterials.length : 0) +
    aiReferences.length;

  const openHistoryModal = useCallback(() => {
    setShowHistoryModal(true);
    setSelectedHistorySession(null);
    setPreviewMessages([]);
    setHistorySearchQuery("");
    if (chatSessions.length === 0) {
      loadChatSessions?.();
    }
  }, [chatSessions.length, loadChatSessions]);

  const closeHistoryModal = () => {
    setShowHistoryModal(false);
    setSelectedHistorySession(null);
    setPreviewMessages([]);
  };

  const handleSelectHistorySession = async (session) => {
    setSelectedHistorySession(session);
    setPreviewLoading(true);
    try {
      const res = await fetch(
        `${apiBase}/chat/sessions/${session.id}?username=${encodeURIComponent(user?.username || "")}`
      );
      const data = await res.json();
      if (res.ok) {
        setPreviewMessages((data.messages || []).slice(0, 4));
      } else {
        setPreviewMessages([]);
      }
    } catch {
      setPreviewMessages([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleContinueChat = () => {
    if (selectedHistorySession) {
      openChatSession?.(selectedHistorySession);
      closeHistoryModal();
    }
  };

  const filteredSessions = (chatSessions || []).filter((s) => {
    if (historyFilterSubject !== "all") {
      const sessionSubject =
        s.subject || s.course || "";
      if (
        sessionSubject !== historyFilterSubject &&
        sessionSubject !== getSubjectLabel(historyFilterSubject)
      )
        return false;
    }
    if (historySearchQuery.trim()) {
      const q = historySearchQuery.trim().toLowerCase();
      const title = (s.title || "").toLowerCase();
      return title.includes(q);
    }
    return true;
  });

  return (
    <div className="aiqp-shell">
      {/* ═══════════════════════════════════════════════════════════════════
          A. TOP BAR
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
            {Array.isArray(COURSE_OPTIONS) && COURSE_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>
        </div>

        <div className="aiqp-topbar-search aiqp-topbar-search--global">
          <GlobalSearchBox
            user={user}
            onSearch={handleGlobalSearch}
            placeholder="搜索课程、资料、知识点..."
          />
        </div>

        <div className="aiqp-topbar-actions">
          <button className="aiqp-icon-btn" title="通知">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            <span className="aiqp-badge">3</span>
          </button>

          <div
            className="aiqp-topbar-user"
            onClick={() => setPage("profile")}
            title="个人主页"
          >
            {hasCustomAvatar && user ? (
              <img
                className="aiqp-topbar-avatar"
                src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user.username || "")}`}
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
              {user?.nickname || user?.username || "孙源"}
            </span>
          </div>
        </div>
      </header>

      {/* ═══════════════════════════════════════════════════════════════════
          B. TITLE AREA — with 新对话 / 历史对话 buttons
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="aiqp-title-area">
        <div className="aiqp-title-inner">
          <div className="aiqp-title-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="14" rx="3" />
              <path d="M7 13l2 2 4-4" />
              <circle cx="12" cy="18" r="1.5" fill="#2563eb" stroke="none" />
              <circle cx="16.5" cy="18" r="1.5" fill="#93c5fd" stroke="none" />
              <circle cx="7.5" cy="18" r="1.5" fill="#93c5fd" stroke="none" />
            </svg>
          </div>
          <div className="aiqp-title-text">
            <h1 className="aiqp-title-heading">AI 智能问答</h1>
            <p className="aiqp-title-sub">
              基于课程资料与历史记录进行高相关问答
            </p>
          </div>
          <div className="aiqp-title-actions">
            <button
              className="aiqp-title-btn aiqp-title-btn--new"
              onClick={startNewConversation}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              新对话
            </button>
            <button
              className="aiqp-title-btn aiqp-title-btn--history"
              onClick={openHistoryModal}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              历史对话
            </button>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          KP CONTEXT CARD — shown when navigating from knowledge learning
          ═══════════════════════════════════════════════════════════════════ */}
      {pendingAIContext && pendingAIContext.type === "knowledge_point" && (() => {
        const ctx = pendingAIContext;
        const goalLabel = ({ overview: "大概了解", systematic: "系统学习", project: "项目实践", exam: "期中/期末速成" })[ctx.goal] || "系统学习";
        const diffLabel = ({ intro: "入门", standard: "标准", advanced: "提高", challenge: "挑战" })[ctx.difficulty] || "标准";
        const depthLabel = ({ brief: "粗略", standard: "标准", detailed: "详细" })[ctx.depth] || "标准";
        const dailyTimeLabel = ctx.dailyTime ? `${ctx.dailyTime} 分钟` : "30 分钟";
        const examDaysLabel = ({ "3": "3 天内", "7": "1 周内", "14": "2 周内", "30": "1 个月内" })[ctx.examDays] || "";
        const routeLabel = ctx.routeSource === "platform" ? "平台推荐路线" : "我的资料路线";

        // Dynamic recommended questions based on goal
        const questionsByGoal = {
          overview: [
            "这个知识点是什么？",
            "用一句话解释它的作用",
            "给我一个生活类比",
            "我需要掌握到什么程度？",
          ],
          systematic: [
            "给我完整讲解这个知识点",
            "用例子说明",
            "有哪些易错点？",
            "给我 3 道基础练习题",
          ],
          project: [
            "这个知识点在项目中怎么用？",
            "给我一个实际代码案例",
            "常见 bug 有哪些？",
            "帮我设计一个小练习项目",
          ],
          exam: [
            "这个知识点考试怎么考？",
            "给我高频题型",
            "给我速记版总结",
            "给我 3 道可能考试题",
            "哪些细节最容易丢分？",
          ],
        };
        const questions = questionsByGoal[ctx.goal] || questionsByGoal.systematic;
        const knowledgePointTitle = ctx.knowledgePointTitle || ctx.title || "当前知识点";
        const knowledgePointDescription = ctx.knowledgePointDescription || ctx.description || "";

        // sendMessage(overrideText) bypasses async setState, sends exact text immediately
        const handleSendWithContext = (questionText) => {
          sendMessage(questionText);
        };
        const currentStatus = normalizeKnowledgeStatus(ctx.knowledgePointStatus || ctx.status);
        const currentStatusLabel = KNOWLEDGE_STATUS_LABELS[currentStatus] || "未开始";
        const handleUpdateKnowledgeStatus = async (nextStatus, event) => {
          event?.preventDefault?.();
          event?.stopPropagation?.();
          let knowledgePointId = ctx.pointId || ctx.knowledgePointBackendId || null;
          if (knowledgePointId) {
            knowledgePointId = Number(String(knowledgePointId).replace(/^kp-/, ""));
          }
          const nodeKey = ctx.nodeKey || ctx.knowledgePointNodeKey || "";
          const parentNodeKey = ctx.parentNodeKey || ctx.knowledgePointParentNodeKey || "";
          const pointType = ctx.nodeType || ctx.knowledgePointType || (parentNodeKey ? "child" : "stage");
          const title = ctx.title || ctx.knowledgePointTitle;
          const courseId = ctx.course || ctx.courseId || subject;
          if (!user?.username) {
            setKpStatusError("无法识别当前知识点，状态保存失败。");
            return;
          }
          const oldContext = ctx;
          const option = KNOWLEDGE_STATUS_OPTIONS.find((item) => item.status === nextStatus);
          setKpStatusError("");
          setKpStatusSaving(true);
          setPendingAIContext((prev) =>
            prev
              ? {
                  ...prev,
                  knowledgePointStatus: nextStatus,
                  status: nextStatus,
                }
              : prev
          );
          try {
            if (!knowledgePointId) {
              let parentId = null;
              if (pointType === "child" && parentNodeKey) {
                const parentBody = {
                  username: user.username,
                  course_id: courseId,
                  title: ctx.nodeTitle || title,
                  description: "",
                  parent_id: null,
                  level: 0,
                  node_key: parentNodeKey,
                  parent_node_key: null,
                };
                console.debug("[node-key:ai-create-payload]", { type: "parent", nodeKey: parentNodeKey, createBody: parentBody });
                const parentRes = await fetch(`${apiBase}/knowledge-points`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(parentBody),
                });
                const parentData = await parentRes.json();
                if (!parentRes.ok) throw new Error(parentData.detail || "创建父知识点失败");
                parentId = parentData.knowledge_point?.id || null;
              }
              const createBody = {
                username: user.username,
                course_id: courseId,
                title,
                description: "",
                parent_id: parentId,
                level: pointType === "child" ? 1 : 0,
                node_key: nodeKey || null,
                parent_node_key: parentNodeKey || null,
              };
              console.debug("[node-key:ai-create-payload]", { type: pointType, nodeKey, parentNodeKey, createBody });
              const createRes = await fetch(`${apiBase}/knowledge-points`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(createBody),
              });
              const createData = await createRes.json();
              if (!createRes.ok) throw new Error(createData.detail || "创建知识点失败");
              knowledgePointId = createData.knowledge_point?.id;
              if (!knowledgePointId) throw new Error("无法识别当前知识点，状态保存失败。");
              setPendingAIContext((prev) =>
                prev
                  ? {
                      ...prev,
                      knowledgePointBackendId: knowledgePointId,
                      pointId: knowledgePointId,
                    }
                  : prev
              );
            }
            const updateBody = {
              username: user.username,
              status: nextStatus,
              mastery_score: option?.score ?? 0,
            };
            console.debug("[node-key:ai-update-request]", { pointId: knowledgePointId, nodeKey, body: updateBody });
            const res = await fetch(`${apiBase}/knowledge-points/${knowledgePointId}/progress`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(updateBody),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || "状态保存失败");
            const savedStatus = normalizeKnowledgeStatus(data.progress?.status || nextStatus);
            console.debug("[node-key:ai-update-response]", { pointId: knowledgePointId, nodeKey, requestStatus: nextStatus, savedStatus });
            setPendingAIContext((prev) =>
              prev
                ? {
                    ...prev,
                    knowledgePointStatus: savedStatus,
                    status: savedStatus,
                  }
                : prev
            );
          } catch (error) {
            setPendingAIContext(oldContext);
            setKpStatusError(error.message || "状态保存失败，请稍后重试。");
          } finally {
            setKpStatusSaving(false);
          }
        };

        return (
        <div className={`aiqp-kp-context${isKpContextExpanded ? " aiqp-kp-context--expanded" : " aiqp-kp-context--collapsed"}`}>
          <div className="aiqp-kp-context-header">
            <div className="aiqp-kp-context-left">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
              <span className="aiqp-kp-context-label">当前学习知识点</span>
            </div>
            <div className="aiqp-kp-context-header-actions">
              <button
                className="aiqp-kp-context-toggle"
                type="button"
                onClick={() => setIsKpContextExpanded((v) => !v)}
                aria-expanded={isKpContextExpanded}
              >
                {isKpContextExpanded ? "收起详情" : "展开详情"}
                <svg
                  className="aiqp-kp-context-toggle-icon"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              <button
                className="aiqp-kp-context-close"
                type="button"
                onClick={() => setPendingAIContext(null)}
                title="关闭"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>
          <div className="aiqp-kp-context-body">
            <div className="aiqp-kp-context-info">
              <div className="aiqp-kp-context-summary">
                <div className="aiqp-kp-context-summary-main">
                  <span className="aiqp-kp-context-summary-label">知识点</span>
                  <div className="aiqp-kp-context-title">
                    <MarkdownMessage content={knowledgePointTitle} />
                  </div>
                </div>
                <div className="aiqp-kp-context-summary-meta">
                  <span className="aiqp-kp-context-course">课程：{ctx.courseName || getSubjectLabel(ctx.course || ctx.courseId || subject)}</span>
                  <span className="aiqp-kp-status-current">当前：{currentStatusLabel}</span>
                </div>
              </div>
              {isKpContextExpanded && (
                <div className="aiqp-kp-context-details">
                  <div className="aiqp-kp-context-detail-row">
                    <span className="aiqp-kp-context-detail-label">阶段：</span>
                    <div className="aiqp-kp-context-detail-content">
                      <MarkdownMessage content={ctx.nodeTitle || knowledgePointTitle} />
                    </div>
                  </div>
                  <p className="aiqp-kp-context-source">路线来源：{routeLabel}</p>
                  {knowledgePointDescription && (
                    <div className="aiqp-kp-context-description">
                      <span className="aiqp-kp-context-detail-label">知识点说明：</span>
                      <MarkdownMessage content={knowledgePointDescription} />
                    </div>
                  )}
                  <div className="aiqp-kp-context-goal">
                    <span className="aiqp-kp-context-goal-label">学习目标：</span>
                    <span className="aiqp-kp-context-goal-badge">{goalLabel}</span>
                    <span className="aiqp-kp-context-goal-badge">{diffLabel}</span>
                    <span className="aiqp-kp-context-goal-badge">{depthLabel}</span>
                    <span className="aiqp-kp-context-goal-badge">{dailyTimeLabel}</span>
                  </div>
                  {ctx.examMode && (
                    <p className="aiqp-kp-context-exam">
                      考试速成 · 距离考试：{examDaysLabel || ctx.examCustomDate || "未设置"}
                    </p>
                  )}
                </div>
              )}
            </div>
            {isKpContextExpanded && (
              <div className="aiqp-kp-context-suggestions">
                <p className="aiqp-kp-suggest-label">推荐问题（{goalLabel}）</p>
                {questions.map((q) => (
                  <button
                    key={q}
                    className="aiqp-kp-suggest-btn"
                    type="button"
                    onClick={() => handleSendWithContext(q)}
                  >
                    <MarkdownMessage content={q} />
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* Knowledge point status marking */}
          <div className="aiqp-kp-context-status">
            <span className="aiqp-kp-status-label">这个知识点学得怎么样？</span>
            <div className="aiqp-kp-status-btns">
              {KNOWLEDGE_STATUS_OPTIONS.map((btn) => {
                const active = currentStatus === btn.status;
                return (
                  <button
                    key={btn.status}
                    className={`aiqp-kp-status-btn${active ? " aiqp-kp-status-btn--active" : ""}`}
                    type="button"
                    disabled={kpStatusSaving}
                    style={{
                      borderColor: btn.color,
                      color: active ? "#fff" : btn.color,
                      background: active ? btn.color : btn.bg,
                    }}
                    onClick={(event) => handleUpdateKnowledgeStatus(btn.status, event)}
                  >
                    {btn.label}
                  </button>
                );
              })}
            </div>
            {kpStatusError && <span className="aiqp-kp-status-error">{kpStatusError}</span>}
          </div>
        </div>
        );
      })()}

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
              {(!Array.isArray(messages) || messages.length === 0) && (
                <div className="aiqp-empty-state">
                  <div className="aiqp-empty-robot">
                    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                      <rect x="12" y="16" width="40" height="32" rx="8" fill="#eef4ff" stroke="#bfdbfe" strokeWidth="2" />
                      <circle cx="28" cy="30" r="4" fill="#93c5fd" />
                      <circle cx="36" cy="30" r="4" fill="#93c5fd" />
                      <path d="M26 38h12" stroke="#93c5fd" strokeWidth="2" strokeLinecap="round" />
                      <rect x="27" y="8" width="10" height="8" rx="3" fill="#eef4ff" stroke="#bfdbfe" strokeWidth="1.5" />
                      <circle cx="22" cy="22" r="3" fill="#dbeafe" />
                      <circle cx="42" cy="22" r="3" fill="#dbeafe" />
                    </svg>
                  </div>
                  <p className="aiqp-empty-title">开始你的 AI 问答之旅</p>
                  <p className="aiqp-empty-hint">
                    在下方输入你的问题，或点击 + 上传资料后基于资料提问。
                  </p>
                </div>
              )}

              {Array.isArray(messages) && messages.map((msg, index) => (
                <ChatMessage
                  key={msg.id || msg.clientId || index}
                  message={msg}
                  user={user}
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
                  onEditMessage={onEditMessage}
                  onVersionChange={onVersionChange}
                />
              ))}

              {loading && (
                <div className="aiqp-thinking-card">
                  <div className="aiqp-thinking-dots">
                    <span /><span /><span />
                  </div>
                  <span className="aiqp-thinking-text">AI 正在思考...</span>
                </div>
              )}
            </div>

            <div className="aiqp-composer">
              {Array.isArray(selectedFiles) && selectedFiles.length > 0 && (
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
                          &times;
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

              {Array.isArray(selectedLibraryMaterials) && selectedLibraryMaterials.length > 0 && (
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
                    className="aiqp-attach-btn"
                    type="button"
                    onClick={() => setShowPlusMenu((v) => !v)}
                    disabled={loading}
                    title="添加资料"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <path d="M12 5v14M5 12h14" />
                    </svg>
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
                        <span className="aiqp-plus-menu-icon">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><path d="M12 3v12"/></svg>
                        </span>
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
                        <span className="aiqp-plus-menu-icon">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                        </span>
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
                  placeholder="请输入你的问题，支持上传图片或文件..."
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
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>

              <p className="aiqp-disclaimer">
                内容由 AI 生成，请结合课程资料与个人判断使用
              </p>

              {tip && <p className="aiqp-tip-text">{tip}</p>}
            </div>
          </section>

          {/* ── Right: info sidebar ── */}
          <aside className="aiqp-sidebar">
            <div className="aiqp-sidebar-card">
              <div className="aiqp-sidebar-card-header">
                <h4 className="aiqp-sidebar-card-title">本轮已引用资料</h4>
                {hasReferences && (
                  <span className="aiqp-ref-count-badge">{refCount}</span>
                )}
              </div>
              {hasReferences ? (
                <div className="aiqp-ref-list">
                  {Array.isArray(referencedFiles) && referencedFiles.map((item) => (
                    <div key={item.localId} className="aiqp-ref-item">
                      <span className="aiqp-ref-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                          <path d="M9 15h6" /><path d="M9 11h3" />
                        </svg>
                      </span>
                      <div className="aiqp-ref-info">
                        <span className="aiqp-ref-name">{item.original_filename}</span>
                        <span className="aiqp-ref-desc">
                          {formatFileSize(item.file_size)} · {getFileTypeLabel(item.file_type || item.type)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {Array.isArray(selectedLibraryMaterials) && selectedLibraryMaterials.map((item) => (
                    <div key={item.id} className="aiqp-ref-item">
                      <span className="aiqp-ref-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round">
                          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                        </svg>
                      </span>
                      <div className="aiqp-ref-info">
                        <span className="aiqp-ref-name">{item.original_filename}</span>
                        <span className="aiqp-ref-desc">
                          {formatFileSize(item.file_size)} · {getFileTypeLabel(item.file_type)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {aiReferences.map((ref, idx) => {
                    const pageInfo = ref._pages && ref._pages.length > 0
                      ? ` · P${ref._pages.filter(Boolean).join(", P")}`
                      : "";
                    const displayName = cleanDisplayText(ref.filename || ref.original_filename) || "参考资料";
                    const subjectLabel = ref.subject ? getSubjectLabel(cleanDisplayText(ref.subject)) : "";
                    const fileTypeLabel = ref.file_type ? getFileTypeLabel(cleanDisplayText(ref.file_type)) : "";
                    return (
                      <div key={ref.material_id || ref.filename || idx} className="aiqp-ref-item">
                        <span className="aiqp-ref-icon">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.5" strokeLinecap="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <path d="M16 13H8" /><path d="M10 17H8" />
                          </svg>
                        </span>
                        <div className="aiqp-ref-info">
                          <span className="aiqp-ref-name">{displayName}</span>
                          <span className="aiqp-ref-desc">
                            {subjectLabel ? `${subjectLabel} · ` : ""}
                            {fileTypeLabel}
                            {pageInfo}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="aiqp-ref-empty">
                  尚未引用资料，点击输入框左侧 + 上传或引用资料库文件
                </p>
              )}
              <button
                className="aiqp-ref-all-link"
                onClick={() => setPage("workspaceMaterials")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                全部资料库
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
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
                  换一批
                </button>
              </div>
              <div className="aiqp-suggestions">
                {suggestionBatch.map((q, i) => (
                  <button
                    key={i}
                    className="aiqp-suggestion-item"
                    onClick={() => setMessage(q)}
                  >
                    <MarkdownMessage content={q} />
                  </button>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          D. HISTORY MODAL
          ═══════════════════════════════════════════════════════════════════ */}
      {showHistoryModal && (
        <div className="aiqp-modal-overlay" onClick={closeHistoryModal}>
          <div
            className="aiqp-history-modal"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="aiqp-history-modal-header">
              <h2 className="aiqp-history-modal-title">历史对话</h2>
              <button
                className="aiqp-modal-close"
                onClick={closeHistoryModal}
                title="关闭"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal body: left-right columns */}
            <div className="aiqp-history-modal-body">
              {/* Left panel */}
              <div className="aiqp-history-left">
                <div className="aiqp-history-filters">
                  <select
                    className="aiqp-history-subject-filter"
                    value={historyFilterSubject}
                    onChange={(e) => setHistoryFilterSubject(e.target.value)}
                  >
                    <option value="all">全部学科</option>
                    {Array.isArray(COURSE_OPTIONS) && COURSE_OPTIONS.map((item) => (
                      <option key={item} value={item}>
                        {getSubjectLabel(item)}
                      </option>
                    ))}
                  </select>
                  <div className="aiqp-history-search">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                    <input
                      className="aiqp-history-search-input"
                      type="text"
                      placeholder="搜索历史对话内容..."
                      value={historySearchQuery}
                      onChange={(e) => setHistorySearchQuery(e.target.value)}
                    />
                  </div>
                </div>

                <div className="aiqp-history-list">
                  {filteredSessions.length === 0 ? (
                    <div className="aiqp-history-empty">
                      <p>暂无历史对话记录</p>
                    </div>
                  ) : (
                    filteredSessions.map((session) => (
                      <button
                        key={session.id}
                        className={`aiqp-history-item ${selectedHistorySession?.id === session.id ? "aiqp-history-item--active" : ""}`}
                        onClick={() => handleSelectHistorySession(session)}
                      >
                        <div className="aiqp-history-item-title">
                          {session.title || "未命名对话"}
                        </div>
                        <div className="aiqp-history-item-subject">
                          {(session.subject || session.course)
                            ? getSubjectLabel(session.subject || session.course)
                            : ""}
                        </div>
                        <div className="aiqp-history-item-time">
                          {session.created_at
                            ? new Date(session.created_at).toLocaleString("zh-CN", {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>

              {/* Right panel: preview */}
              <div className="aiqp-history-right">
                {!selectedHistorySession ? (
                  <div className="aiqp-history-right-empty">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    <p>选择左侧对话查看预览</p>
                  </div>
                ) : previewLoading ? (
                  <div className="aiqp-history-right-loading">加载中...</div>
                ) : (
                  <>
                    <div className="aiqp-history-preview-title">
                      {selectedHistorySession.title || "未命名对话"}
                    </div>
                    <div className="aiqp-history-preview-msgs">
                      {previewMessages.length === 0 ? (
                        <p className="aiqp-history-right-empty-text">
                          暂无消息
                        </p>
                      ) : (
                        previewMessages.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`aiqp-history-preview-msg ${msg.role === "user" ? "aiqp-history-preview-msg--user" : "aiqp-history-preview-msg--ai"}`}
                          >
                            <div className="aiqp-history-preview-role">
                              {msg.role === "user" ? "用户" : "AI"}
                            </div>
                            <div className="aiqp-history-preview-content">
                              {(msg.content || "").slice(0, 200)}
                              {(msg.content || "").length > 200 ? "..." : ""}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="aiqp-history-preview-footer">
                      <button
                        className="aiqp-continue-chat-btn"
                        onClick={handleContinueChat}
                      >
                        继续该对话
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
