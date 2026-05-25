import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";

const API_BASE = "/api";

const LANGUAGES = ["Python", "C", "Java"];

function getMonacoLanguage(language) {
  const map = { Python: "python", Java: "java", C: "c", "C++": "cpp" };
  return map[language] || "plaintext";
}

const CODE_TEMPLATES = {
  Python: 'def main():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    main()',
  C: '#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}',
  Java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}',
};

const STATUS_LABELS = {
  probable_pass: "大概率通过",
  partial: "可能部分通过",
  failed: "大概率不通过",
  unknown: "无法判定",
};

const STATUS_CLASSES = {
  probable_pass: "feedback-status--pass",
  partial: "feedback-status--partial",
  failed: "feedback-status--fail",
  unknown: "feedback-status--unknown",
};

function safeJson(res) {
  return res.json().catch(() => ({}));
}

export default function CodeStudio({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
}) {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [codeCourseId, setCodeCourseId] = useState(() => normalizeSubject(subject));
  const [title, setTitle] = useState("未命名练习");
  const [language, setLanguage] = useState("Python");
  const [code, setCode] = useState(CODE_TEMPLATES["Python"]);
  const [saving, setSaving] = useState(false);
  const [tip, setTip] = useState("");

  const [aiQuestion, setAiQuestion] = useState("");
  const [aiMessages, setAiMessages] = useState([]);
  const [aiMessagesLoading, setAiMessagesLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const aiEndRef = useRef(null);

  const [showChallengeModal, setShowChallengeModal] = useState(false);
  const [challengeDifficulty, setChallengeDifficulty] = useState("基础");
  const [challengeFocus, setChallengeFocus] = useState("");
  const [challengeGenerating, setChallengeGenerating] = useState(false);
  const [currentChallenge, setCurrentChallenge] = useState(null);

  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [diagnosisReport, setDiagnosisReport] = useState(null);
  const [targetedChallengeLoading, setTargetedChallengeLoading] = useState(false);
  const [taskGenerationLoading, setTaskGenerationLoading] = useState(false);

  // Feedback / Submit panel
  const [showFeedbackPanel, setShowFeedbackPanel] = useState(false);
  const [feedbackContent, setFeedbackContent] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [codeTruncated, setCodeTruncated] = useState(false);

  // Reference solution & starter code
  const [showReference, setShowReference] = useState(false);
  const [starterConfirmOpen, setStarterConfirmOpen] = useState(false);

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const hasUnsaved =
    selectedSession &&
    (selectedSession.title !== title ||
      selectedSession.language !== language ||
      selectedSession.code !== code);

  useEffect(() => {
    setCodeCourseId(normalizeSubject(subject));
  }, [subject, normalizeSubject]);

  useEffect(() => {
    if (aiEndRef.current) {
      aiEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [aiMessages]);

  const loadSessions = async () => {
    if (!user?.username) return;
    setSessionsLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      const course = normalizeSubject(codeCourseId);
      if (course) query.set("course_id", course);
      const res = await fetch(`${API_BASE}/code/sessions?${query.toString()}`);
      const data = await safeJson(res);
      if (res.ok) {
        setSessions(data.sessions || []);
        if (!selectedSession && data.sessions?.length > 0) {
          selectSession(data.sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to load code sessions:", error);
    } finally {
      setSessionsLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [user?.username, codeCourseId]);

  const loadMessages = async (sessionId) => {
    if (!user?.username || !sessionId) return;
    setAiMessagesLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/sessions/${sessionId}/messages?username=${encodeURIComponent(user.username)}`
      );
      const data = await safeJson(res);
      if (res.ok) {
        setAiMessages(data.messages || []);
      }
    } catch (error) {
      console.error("Failed to load code AI messages:", error);
    } finally {
      setAiMessagesLoading(false);
    }
  };

  const selectSession = (session) => {
    setSelectedSession(session);
    setTitle(session.title);
    setLanguage(session.language);
    setCode(session.code);
    setAiMessages([]);
    setAiQuestion("");
    setCurrentChallenge(null);
    setShowFeedbackPanel(false);
    setFeedbackContent("");
    setFeedbackStatus(null);
    setCodeTruncated(false);
    setShowReference(false);
    if (session.id) {
      loadMessages(session.id);
      if (session.challenge_id) {
        loadChallenge(session.challenge_id);
      }
    }
  };

  const newSession = () => {
    const newS = {
      id: null,
      title: "未命名练习",
      language: "Python",
      code: CODE_TEMPLATES["Python"],
      course_id: normalizeSubject(codeCourseId),
      username: user?.username || "",
      session_type: "normal",
    };
    setSelectedSession(newS);
    setTitle(newS.title);
    setLanguage(newS.language);
    setCode(newS.code);
    setAiMessages([]);
    setAiQuestion("");
    setCurrentChallenge(null);
    setShowFeedbackPanel(false);
    setFeedbackContent("");
    setFeedbackStatus(null);
    setCodeTruncated(false);
    setShowReference(false);
  };

  const loadChallenge = async (challengeId) => {
    if (!user?.username || !challengeId) return;
    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${challengeId}?username=${encodeURIComponent(user.username)}`
      );
      const data = await safeJson(res);
      if (res.ok && data.challenge) {
        setCurrentChallenge(data.challenge);
        setShowReference(false);
      }
    } catch (error) {
      console.error("Failed to load challenge:", error);
    }
  };

  const generateChallenge = async () => {
    if (!user?.username) return;
    setChallengeGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/code/challenges/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language,
          difficulty: challengeDifficulty,
          focus: challengeFocus,
        }),
      });
      const data = await safeJson(res);
      if (res.ok && data.session) {
        setShowChallengeModal(false);
        setChallengeFocus("");
        await loadSessions();
        selectSession(data.session);
        if (data.challenge) {
          setCurrentChallenge(data.challenge);
        }
        setTip("AI 题目已生成");
        setTimeout(() => setTip(""), 2000);
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || "AI 出题失败，请重试");
      }
    } catch (error) {
      console.error("Failed to generate challenge:", error);
      setTip("AI 出题失败，请稍后重试");
    } finally {
      setChallengeGenerating(false);
    }
  };

  const saveSession = async () => {
    if (!user?.username) return;
    setSaving(true);
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(codeCourseId),
        title,
        language,
        code,
      };
      let res;
      if (selectedSession?.id) {
        res = await fetch(`${API_BASE}/code/sessions/${selectedSession.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        res = await fetch(`${API_BASE}/code/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      const data = await safeJson(res);
      if (res.ok && data.session) {
        setSelectedSession(data.session);
        setTitle(data.session.title);
        setLanguage(data.session.language);
        setCode(data.session.code);
        setTip("保存成功");
        setTimeout(() => setTip(""), 2000);
        loadSessions();
      } else {
        setTip(data.detail || "保存失败");
      }
    } catch (error) {
      console.error("Failed to save code session:", error);
      setTip("保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    if (!selectedSession?.id && (!code || code === CODE_TEMPLATES[language])) {
      setCode(CODE_TEMPLATES[newLang]);
    }
  };

  const analyzeCode = async () => {
    if (!code.trim()) {
      setTip("请先输入代码再进行分析。");
      return;
    }
    if (!aiQuestion.trim()) {
      setTip("请输入要分析的问题。");
      return;
    }
    setAiLoading(true);
    setCodeTruncated(false);
    const userMsg = { role: "user", content: aiQuestion };
    setAiMessages((prev) => [...prev, userMsg]);
    const question = aiQuestion;
    setAiQuestion("");

    try {
      const res = await fetch(`${API_BASE}/code/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          session_id: selectedSession?.id || null,
          language,
          code,
          question,
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        if (data.code_truncated) {
          setCodeTruncated(true);
        }
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.answer },
        ]);
      } else if (res.status === 429) {
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: "今日 AI 使用次数已达上限，请明天再试或升级套餐。" },
        ]);
      } else {
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.detail || "AI 分析失败，请稍后重试。" },
        ]);
      }
    } catch (error) {
      console.error("Failed to analyze code:", error);
      setAiMessages((prev) => [
        ...prev,
        { role: "assistant", content: "无法连接后端服务。" },
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!user?.username || !selectedSession?.challenge_id) return;
    if (!code.trim()) {
      setTip("请先编写代码再提交判定。");
      return;
    }
    setSubmitting(true);
    setShowFeedbackPanel(true);
    setFeedbackContent("");
    setFeedbackStatus(null);

    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${selectedSession.challenge_id}/submit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            session_id: selectedSession.id,
            code,
            language,
          }),
        }
      );
      const data = await safeJson(res);
      if (res.ok) {
        setFeedbackContent(data.ai_feedback || "");
        setFeedbackStatus(data.status || "unknown");
        if (selectedSession?.id) {
          loadMessages(selectedSession.id);
        }
      } else if (res.status === 429) {
        setFeedbackContent(
          "## 额度不足\n\n今日 AI 使用次数已达上限，请明天再试或升级套餐。"
        );
        setFeedbackStatus("unknown");
      } else {
        setFeedbackContent(
          `## 提交失败\n\n${data.detail || "请稍后重试"}`
        );
        setFeedbackStatus("unknown");
      }
    } catch (error) {
      console.error("Failed to submit answer:", error);
      setFeedbackContent("## 提交失败\n\n无法连接后端服务。");
      setFeedbackStatus("unknown");
    } finally {
      setSubmitting(false);
    }
  };

  const deleteSession = async (sessionId) => {
    if (!user?.username || !sessionId) return;
    setDeleting(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await safeJson(res);
      if (res.ok) {
        if (selectedSession?.id === sessionId) {
          setSelectedSession(null);
          setTitle("未命名练习");
          setLanguage("Python");
          setCode(CODE_TEMPLATES["Python"]);
          setAiMessages([]);
          setCurrentChallenge(null);
          setShowFeedbackPanel(false);
          setFeedbackContent("");
          setFeedbackStatus(null);
          setShowReference(false);
        }
        await loadSessions();
        setTip("练习已删除");
        setTimeout(() => setTip(""), 2000);
      } else {
        setTip(data.detail || "删除失败");
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
      setTip("删除失败，请稍后重试");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const useStarterCode = () => {
    if (!currentChallenge?.starter_code) {
      setTip("该题目没有起始代码");
      setTimeout(() => setTip(""), 2000);
      return;
    }
    const isDefault =
      !code ||
      Object.values(CODE_TEMPLATES).includes(code);
    if (!isDefault) {
      setStarterConfirmOpen(true);
      return;
    }
    setCode(currentChallenge.starter_code);
    setTip("已应用起始代码");
    setTimeout(() => setTip(""), 2000);
  };

  const confirmStarterCode = () => {
    if (currentChallenge?.starter_code) {
      setCode(currentChallenge.starter_code);
      setTip("已应用起始代码");
      setTimeout(() => setTip(""), 2000);
    }
    setStarterConfirmOpen(false);
  };

  const fetchDiagnosis = async () => {
    if (!user?.username) return;
    setDiagnosisLoading(true);
    setDiagnosisReport(null);
    try {
      const res = await fetch(`${API_BASE}/code/learning-diagnosis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language: "",
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setDiagnosisReport(data);
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || "诊断生成失败");
      }
    } catch (error) {
      console.error("Failed to fetch diagnosis:", error);
      setTip("诊断生成失败，请稍后重试");
    } finally {
      setDiagnosisLoading(false);
    }
  };

  const generateTargetedChallenge = async () => {
    if (!user?.username || !diagnosisReport?.summary) return;
    setTargetedChallengeLoading(true);
    try {
      const diagnosisText = diagnosisReport.summary.slice(0, 2000);
      const res = await fetch(`${API_BASE}/code/challenges/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language,
          difficulty: "基础",
          focus: "",
          diagnosis_summary: diagnosisText,
          source: "diagnosis",
        }),
      });
      const data = await safeJson(res);
      if (res.ok && data.session) {
        setDiagnosisReport(null);
        await loadSessions();
        selectSession(data.session);
        if (data.challenge) {
          setCurrentChallenge(data.challenge);
        }
        setTip("已生成针对性练习");
        setTimeout(() => setTip(""), 2000);
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || "针对性出题失败，请重试");
      }
    } catch (error) {
      console.error("Failed to generate targeted challenge:", error);
      setTip("针对性出题失败，请稍后重试");
    } finally {
      setTargetedChallengeLoading(false);
    }
  };

  const generateTasksFromDiagnosis = async () => {
    if (!user?.username || !diagnosisReport?.summary) return;
    setTaskGenerationLoading(true);
    try {
      const diagnosisText = diagnosisReport.summary.slice(0, 2000);
      const res = await fetch(`${API_BASE}/learning/tasks/from-diagnosis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          course_name: getSubjectLabel(codeCourseId) || codeCourseId,
          diagnosis_summary: diagnosisText,
          language,
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setTip(data.message || `已生成 ${data.tasks?.length || 0} 个学习任务`);
        setTimeout(() => setTip(""), 3000);
      } else {
        setTip(data.detail || "生成学习任务失败");
      }
    } catch (error) {
      console.error("Failed to generate tasks from diagnosis:", error);
      setTip("生成学习任务失败，请稍后重试");
    } finally {
      setTaskGenerationLoading(false);
    }
  };

  return (
    <section className="code-studio-shell">
      {/* Left Panel — Session List */}
      <aside className="code-studio-sidebar">
        <div className="code-studio-sidebar-header">
          <h3>代码练习</h3>
          <div className="code-studio-course-picker">
            <select
              className="field"
              value={codeCourseId}
              onChange={(e) => {
                setCodeCourseId(e.target.value);
                setSelectedSession(null);
              }}
            >
              {courseOptions.map((item) => (
                <option key={item} value={item}>
                  {getSubjectLabel(item)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button className="primary-button compact code-studio-new-btn" onClick={newSession}>
          新建练习
        </button>

        <div className="code-studio-session-list">
          {sessionsLoading ? (
            <div className="empty-inline">加载中...</div>
          ) : sessions.length === 0 ? (
            <div className="empty-inline">暂无代码练习</div>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`code-session-item ${selectedSession?.id === s.id ? "code-session-item--active" : ""}`}
                onClick={() => selectSession(s)}
              >
                <div className="code-session-item-title">
                  {s.title}
                  {s.session_type === "challenge" && (
                    <span className={`code-session-type-badge ${s.challenge_source === "diagnosis" ? "code-session-type-badge--diagnosis" : ""}`}>
                      {s.challenge_source === "diagnosis" ? "诊断推荐" : "AI题"}
                    </span>
                  )}
                </div>
                <div className="code-session-item-meta">
                  <span className="subject-pill small">{s.language}</span>
                  <span>{formatDate(s.updated_at)}</span>
                </div>
                <button
                  className="code-session-delete-btn"
                  title="删除该练习"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(s);
                  }}
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Center Panel — Code Editor */}
      <main className="code-studio-editor">
        <div className="code-studio-editor-header">
          <input
            className="field code-studio-title-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="练习标题"
          />
          <div className="code-studio-lang-selector">
            {LANGUAGES.map((lang) => (
              <button
                key={lang}
                className={`ghost-button compact ${language === lang ? "code-lang-btn--active" : ""}`}
                onClick={() => handleLanguageChange(lang)}
              >
                {lang}
              </button>
            ))}
          </div>
          <button
            className="ghost-button compact code-challenge-btn"
            onClick={() => {
              setChallengeDifficulty("基础");
              setChallengeFocus("");
              setShowChallengeModal(true);
            }}
            title="AI 出题"
          >
            AI 出题
          </button>
          {selectedSession?.challenge_id && (
            <button
              className="primary-button compact code-submit-btn"
              onClick={submitAnswer}
              disabled={submitting || !code.trim()}
            >
              {submitting ? "判定中..." : "提交答案"}
            </button>
          )}
          <button
            className="primary-button compact"
            onClick={saveSession}
            disabled={saving || !title.trim()}
          >
            {saving ? "保存中..." : hasUnsaved ? "保存 *" : "保存"}
          </button>
        </div>

        {codeTruncated && (
          <div className="code-truncated-warning">
            代码较长，本次仅分析了前 12000 个字符
          </div>
        )}

        {currentChallenge && (
          <div className="code-challenge-card">
            <div className="code-challenge-card-header">
              <span className="subject-pill small">{currentChallenge.difficulty || "基础"}</span>
              {currentChallenge.knowledge_point && (
                <span className="subject-pill small">{currentChallenge.knowledge_point}</span>
              )}
              {currentChallenge.source === "diagnosis" && (
                <span className="subject-pill small" style={{ background: "#ecfdf5", color: "#065f46" }}>
                  来源：诊断推荐
                </span>
              )}
              {currentChallenge.target_weak_point && (
                <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                  薄弱点：{currentChallenge.target_weak_point}
                </span>
              )}
            </div>
            <h4 className="code-challenge-card-title">{currentChallenge.title}</h4>
            {currentChallenge.description && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">题目描述</div>
                <p>{currentChallenge.description}</p>
              </div>
            )}
            {currentChallenge.requirements && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">要求</div>
                <p>{currentChallenge.requirements}</p>
              </div>
            )}
            {currentChallenge.input_format && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">输入格式</div>
                <p>{currentChallenge.input_format}</p>
              </div>
            )}
            {currentChallenge.output_format && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">输出格式</div>
                <p>{currentChallenge.output_format}</p>
              </div>
            )}
            {currentChallenge.examples && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">示例</div>
                <pre className="code-challenge-card-examples">{currentChallenge.examples}</pre>
              </div>
            )}

            <div className="code-challenge-card-actions">
              {currentChallenge.starter_code && (
                <button className="ghost-button compact" onClick={useStarterCode}>
                  使用起始代码
                </button>
              )}
              <button
                className="ghost-button compact"
                onClick={() => setShowReference(!showReference)}
              >
                {showReference ? "隐藏参考解法" : "查看参考解法"}
              </button>
            </div>

            {showReference && (
              <div className="code-reference-solution">
                <div className="code-reference-solution-label">参考解法</div>
                {currentChallenge.reference_solution ? (
                  <pre className="code-challenge-card-examples">{currentChallenge.reference_solution}</pre>
                ) : (
                  <p className="empty-inline" style={{ padding: "8px 0" }}>暂无参考解法</p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="code-studio-monaco-wrapper">
          <Editor
            language={getMonacoLanguage(language)}
            value={code}
            onChange={(value) => setCode(value || "")}
            theme="vs-dark"
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              automaticLayout: true,
              scrollBeyondLastLine: false,
              wordWrap: "on",
            }}
            loading={
              <div className="code-studio-monaco-loading">
                代码编辑器加载中...
              </div>
            }
          />
        </div>

        {!selectedSession && (
          <div className="code-studio-empty-overlay">
            <p>点击左侧「新建练习」开始编程学习</p>
          </div>
        )}

        {/* Feedback / Submit Panel */}
        {showFeedbackPanel && (
          <div className="code-feedback-panel">
            <div className="code-feedback-panel-header">
              <h4>AI 判定反馈</h4>
              <div className="code-feedback-panel-header-right">
                {feedbackStatus && (
                  <span className={`feedback-status-badge ${STATUS_CLASSES[feedbackStatus] || ""}`}>
                    {STATUS_LABELS[feedbackStatus] || feedbackStatus}
                  </span>
                )}
                <button
                  className="code-feedback-panel-close"
                  onClick={() => setShowFeedbackPanel(false)}
                >
                  &times;
                </button>
              </div>
            </div>
            <div className="code-feedback-panel-body">
              {submitting ? (
                <div className="empty-inline" style={{ padding: "16px" }}>
                  AI 正在判定你的代码...
                </div>
              ) : feedbackContent ? (
                <div className="code-assistant-msg-content">{feedbackContent}</div>
              ) : (
                <div className="empty-inline" style={{ padding: "16px" }}>
                  暂无反馈内容
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Right Panel — AI Assistant */}
      <aside className="code-studio-assistant">
        <div className="code-studio-assistant-header">
          <h3>AI 代码助手</h3>
          <button
            className="ghost-button compact code-diagnosis-btn"
            onClick={fetchDiagnosis}
            disabled={diagnosisLoading}
          >
            {diagnosisLoading ? "分析中..." : "生成学习诊断"}
          </button>
        </div>

        <div className="code-studio-assistant-chat">
          {diagnosisReport ? (
            <div className="code-diagnosis-report">
              {diagnosisReport.data_insufficient ? (
                <div className="empty-inline" style={{ padding: "16px" }}>
                  {diagnosisReport.summary.split("\n").map((line, i) => (
                    <p key={i} style={{ margin: "4px 0" }}>{line || " "}</p>
                  ))}
                </div>
              ) : (
                <div className="code-assistant-msg code-assistant-msg--assistant">
                  <div className="code-assistant-msg-role">编程学习诊断报告</div>
                  <div className="code-assistant-msg-content">{diagnosisReport.summary}</div>
                  <div className="code-diagnosis-meta">
                    分析依据：{diagnosisReport.used_sessions_count} 条练习、{diagnosisReport.used_messages_count} 条分析记录、{diagnosisReport.used_challenges_count} 道出题
                  </div>
                  {!diagnosisReport.data_insufficient && (
                    <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        className="primary-button compact"
                        onClick={generateTargetedChallenge}
                        disabled={targetedChallengeLoading}
                      >
                        {targetedChallengeLoading ? "AI 正在根据薄弱点生成练习..." : "根据薄弱点生成练习"}
                      </button>
                      <button
                        className="primary-button compact"
                        onClick={generateTasksFromDiagnosis}
                        disabled={taskGenerationLoading}
                        style={{ background: "#0f766e" }}
                      >
                        {taskGenerationLoading ? "AI 正在根据诊断报告生成学习任务..." : "生成学习任务"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : diagnosisLoading ? (
            <div className="empty-inline" style={{ padding: "24px 16px" }}>
              AI 正在分析你的编程学习情况...
            </div>
          ) : aiMessagesLoading ? (
            <div className="empty-inline" style={{ padding: "24px 16px" }}>
              加载历史记录中...
            </div>
          ) : aiMessages.length === 0 ? (
            <div className="empty-inline" style={{ padding: "24px 16px" }}>
              {selectedSession?.id ? (
                <>
                  <p>还没有 AI 分析记录</p>
                  <p className="muted-text">可以让 AI 帮你检查代码。</p>
                </>
              ) : (
                <>
                  <p>保存练习后，AI 分析记录会自动保留</p>
                  <p className="muted-text">
                    例如：检查代码问题、解释这段代码、给我学习建议。
                  </p>
                </>
              )}
            </div>
          ) : (
            aiMessages.map((msg, i) => (
              <div key={i} className={`code-assistant-msg code-assistant-msg--${msg.role}`}>
                <div className="code-assistant-msg-role">
                  {msg.role === "user" ? "你" : "AI 助手"}
                </div>
                <div className="code-assistant-msg-content">{msg.content}</div>
              </div>
            ))
          )}
          {aiLoading && <div className="empty-inline">AI 分析中...</div>}
          <div ref={aiEndRef} />
        </div>

        <div className="code-studio-assistant-input">
          <input
            className="field"
            placeholder="例如：帮我检查代码问题"
            value={aiQuestion}
            onChange={(e) => setAiQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                analyzeCode();
              }
            }}
          />
          <button
            className="primary-button compact"
            onClick={analyzeCode}
            disabled={aiLoading || !aiQuestion.trim()}
          >
            {aiLoading ? "分析中..." : "发送"}
          </button>
        </div>
      </aside>

      {tip && (
        <div className="code-studio-tip">
          {tip}
        </div>
      )}

      {/* Challenge Generation Modal */}
      {showChallengeModal && (
        <div className="modal-overlay" onClick={() => setShowChallengeModal(false)}>
          <div
            className="modal-card code-challenge-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>AI 出题</h3>
              <button className="modal-close" onClick={() => setShowChallengeModal(false)}>
                &times;
              </button>
            </div>

            <label className="field-label">编程语言</label>
            <div className="code-studio-lang-selector" style={{ marginBottom: 12 }}>
              {LANGUAGES.map((lang) => (
                <button
                  key={lang}
                  className={`ghost-button compact ${language === lang ? "code-lang-btn--active" : ""}`}
                  onClick={() => setLanguage(lang)}
                >
                  {lang}
                </button>
              ))}
            </div>

            <label className="field-label">难度</label>
            <select
              className="field"
              value={challengeDifficulty}
              onChange={(e) => setChallengeDifficulty(e.target.value)}
              style={{ marginBottom: 12 }}
            >
              <option value="基础">基础</option>
              <option value="中等">中等</option>
              <option value="提高">提高</option>
            </select>

            <label className="field-label">想练的知识点（可选）</label>
            <input
              className="field"
              placeholder="例如：数组、循环、递归、排序、面向对象"
              value={challengeFocus}
              onChange={(e) => setChallengeFocus(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  generateChallenge();
                }
              }}
            />

            <div className="modal-actions" style={{ marginTop: 16 }}>
              <button
                className="ghost-button"
                onClick={() => setShowChallengeModal(false)}
              >
                取消
              </button>
              <button
                className="primary-button"
                onClick={generateChallenge}
                disabled={challengeGenerating}
              >
                {challengeGenerating ? "AI 正在生成题目..." : "生成题目"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="modal-card code-delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>删除练习</h3>
              <button className="modal-close" onClick={() => setDeleteTarget(null)}>
                &times;
              </button>
            </div>
            <p style={{ margin: "0 0 16px", color: "#334155", fontSize: "0.9rem" }}>
              确定要删除练习「{deleteTarget.title}」吗？该练习的 AI 分析记录也会被删除。此操作不可撤销。
            </p>
            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setDeleteTarget(null)}>
                取消
              </button>
              <button
                className="danger-button"
                onClick={() => deleteSession(deleteTarget.id)}
                disabled={deleting}
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Starter Code Confirm Modal */}
      {starterConfirmOpen && (
        <div className="modal-overlay" onClick={() => setStarterConfirmOpen(false)}>
          <div className="modal-card code-delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>应用起始代码</h3>
              <button className="modal-close" onClick={() => setStarterConfirmOpen(false)}>
                &times;
              </button>
            </div>
            <p style={{ margin: "0 0 16px", color: "#334155", fontSize: "0.9rem" }}>
              当前编辑器中有未保存的代码。应用起始代码将覆盖当前内容，是否继续？
            </p>
            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setStarterConfirmOpen(false)}>
                取消
              </button>
              <button className="primary-button" onClick={confirmStarterCode}>
                确认覆盖
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
