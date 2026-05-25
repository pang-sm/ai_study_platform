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
      const data = await res.json();
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
      const data = await res.json();
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
    if (session.id) {
      loadMessages(session.id);
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
    };
    setSelectedSession(newS);
    setTitle(newS.title);
    setLanguage(newS.language);
    setCode(newS.code);
    setAiMessages([]);
    setAiQuestion("");
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
      const data = await res.json();
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
      const data = await res.json();
      if (res.ok) {
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.answer },
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
                <div className="code-session-item-title">{s.title}</div>
                <div className="code-session-item-meta">
                  <span className="subject-pill small">{s.language}</span>
                  <span>{formatDate(s.updated_at)}</span>
                </div>
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
            className="primary-button compact"
            onClick={saveSession}
            disabled={saving || !title.trim()}
          >
            {saving ? "保存中..." : hasUnsaved ? "保存 *" : "保存"}
          </button>
        </div>

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
      </main>

      {/* Right Panel — AI Assistant */}
      <aside className="code-studio-assistant">
        <div className="code-studio-assistant-header">
          <h3>AI 代码助手</h3>
        </div>

        <div className="code-studio-assistant-chat">
          {aiMessagesLoading ? (
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
    </section>
  );
}
