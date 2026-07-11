import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import "./ProgrammingWorkbench.css";

const LANGUAGE_TABS = ["C", "C++", "Python", "Java"];
const RUNNABLE_LANGUAGES = new Set(["C", "Python"]);

const CODE_TEMPLATES = {
  C: '#include <stdio.h>\n\nint main(void) {\n    printf("hello from c\\n");\n    return 0;\n}\n',
  "C++": '#include <iostream>\n\nint main() {\n    std::cout << "hello from cpp" << std::endl;\n    return 0;\n}\n',
  Python: 'print("hello from python")\n',
  Java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("hello from java");\n    }\n}\n',
};

const MONACO_LANGUAGE = {
  C: "c",
  "C++": "cpp",
  Python: "python",
  Java: "java",
};

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function normalizeLanguage(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (raw.includes("c++") || raw.includes("cpp")) return "C++";
  if (raw === "c" || raw.includes("c语言") || raw.includes("c language")) return "C";
  if (raw.includes("java")) return "Java";
  if (raw.includes("python") || raw === "py") return "Python";
  return "Python";
}

function formatRunResult(result) {
  if (!result) return "点击运行后，真实输出会显示在这里。";
  const lines = [];
  if (result.stdout) lines.push(result.stdout.trimEnd());
  if (result.stderr) lines.push(result.stderr.trimEnd());
  if (result.compile_error) lines.push(result.compile_error.trimEnd());
  if (result.error_message) lines.push(result.error_message);
  lines.push(`exit_code: ${result.exit_code ?? "-"}`);
  if (result.duration_ms != null) lines.push(`duration: ${result.duration_ms}ms`);
  return lines.filter(Boolean).join("\n") || "程序已运行完成，无输出。";
}

function formatTestResults(results) {
  if (!results) return "当前没有测试结果。关联 AI 编程题后可运行测试。";
  if (results.error_message) return results.error_message;
  const lines = [`通过 ${results.passed ?? 0}/${results.total ?? 0}`];
  for (const item of results.results || []) {
    lines.push(
      [
        item.passed ? "PASS" : "FAIL",
        item.description || item.name || "test case",
        item.expected_output ? `expected: ${item.expected_output}` : "",
        item.actual_output ? `actual: ${item.actual_output}` : "",
        item.stderr ? `stderr: ${item.stderr}` : "",
      ].filter(Boolean).join(" | ")
    );
  }
  return lines.join("\n");
}

export default function ProgrammingWorkbench({ user, apiBase = "/api", homeData, setPage, onGoHome }) {
  const initialLanguage = normalizeLanguage(
    user?.default_course_id || homeData?.onboarding?.main_language || "Python"
  );
  const [mode, setMode] = useState("lesson");
  const [language, setLanguage] = useState(initialLanguage);
  const [code, setCode] = useState(CODE_TEMPLATES[initialLanguage] || CODE_TEMPLATES.Python);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [currentChallenge, setCurrentChallenge] = useState(null);
  const [progress, setProgress] = useState(null);
  const [fontSize, setFontSize] = useState(16);
  const [theme, setTheme] = useState("light");
  const [activeResultTab, setActiveResultTab] = useState("run");
  const [runResult, setRunResult] = useState(null);
  const [testResults, setTestResults] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [messages, setMessages] = useState([]);
  const [coachQuestion, setCoachQuestion] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [saveState, setSaveState] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const editorRef = useRef(null);

  const courseId = useMemo(() => {
    return user?.default_course_id || homeData?.onboarding?.main_language || language || "Python";
  }, [homeData, language, user]);

  const loadChallenge = useCallback(async (challengeId) => {
    if (!user?.username || !challengeId) return null;
    const res = await fetch(
      `${apiBase}/code/challenges/${challengeId}?username=${encodeURIComponent(user.username)}`
    );
    const data = await safeJson(res);
    if (res.ok && data.challenge) {
      setCurrentChallenge(data.challenge);
      return data.challenge;
    }
    return null;
  }, [apiBase, user?.username]);

  const selectSession = useCallback((session) => {
    if (!session) return;
    const nextLanguage = normalizeLanguage(session.language);
    setSelectedSession(session);
    setLanguage(nextLanguage);
    setCode(session.code || CODE_TEMPLATES[nextLanguage] || CODE_TEMPLATES.Python);
    setRunResult(null);
    setTestResults(null);
    setFeedback("");
    setActiveResultTab("run");
    if (session.challenge_id) {
      loadChallenge(session.challenge_id);
    } else {
      setCurrentChallenge(null);
    }
  }, [loadChallenge]);

  const loadSessions = useCallback(async () => {
    if (!user?.username) return;
    const query = new URLSearchParams({ username: user.username, course_id: courseId });
    const res = await fetch(`${apiBase}/code/sessions?${query.toString()}`);
    const data = await safeJson(res);
    if (!res.ok) {
      setStatus(data.detail || "代码 session 读取失败");
      return;
    }
    const items = data.sessions || [];
    setSessions(items);
    if (items.length > 0) {
      selectSession(items[0]);
    } else {
      const nextLanguage = normalizeLanguage(language);
      setSelectedSession(null);
      setCurrentChallenge(null);
      setCode(CODE_TEMPLATES[nextLanguage] || CODE_TEMPLATES.Python);
    }
  }, [apiBase, courseId, language, selectSession, user?.username]);

  const loadProgress = useCallback(async () => {
    if (!user?.username) return;
    const query = new URLSearchParams({ username: user.username, course_id: courseId });
    const res = await fetch(`${apiBase}/code/progress?${query.toString()}`);
    const data = await safeJson(res);
    if (res.ok) setProgress(data);
  }, [apiBase, courseId, user?.username]);

  useEffect(() => {
    loadSessions();
    loadProgress();
  }, [loadProgress, loadSessions]);

  const ensureSessionSaved = useCallback(async () => {
    if (!user?.username) return null;
    setSaveState("保存中...");
    const payload = {
      username: user.username,
      course_id: courseId,
      title: selectedSession?.title || `${language} 编程练习`,
      language,
      code,
      challenge_id: selectedSession?.challenge_id || currentChallenge?.id || null,
    };
    const url = selectedSession?.id
      ? `${apiBase}/code/sessions/${selectedSession.id}`
      : `${apiBase}/code/sessions`;
    const res = await fetch(url, {
      method: selectedSession?.id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await safeJson(res);
    if (!res.ok) {
      setSaveState("保存失败");
      setStatus(data.detail || "session 保存失败");
      return selectedSession;
    }
    setSelectedSession(data.session);
    setSessions((prev) => {
      const rest = prev.filter((item) => item.id !== data.session.id);
      return [data.session, ...rest];
    });
    setSaveState("已保存");
    setTimeout(() => setSaveState(""), 1600);
    return data.session;
  }, [apiBase, code, courseId, currentChallenge?.id, language, selectedSession, user?.username]);

  const changeLanguage = (nextLanguage) => {
    setLanguage(nextLanguage);
    setCode(CODE_TEMPLATES[nextLanguage] || "");
    setSelectedSession(null);
    setCurrentChallenge(null);
    setRunResult(null);
    setTestResults(null);
    setFeedback("");
  };

  const runCode = async () => {
    if (!code.trim()) {
      setStatus("请先输入代码。");
      return;
    }
    setBusy("run");
    setActiveResultTab("run");
    setRunResult(null);
    try {
      const saved = await ensureSessionSaved();
      const res = await fetch(`${apiBase}/code/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          session_id: saved?.id || 0,
          language,
          code,
          stdin: "",
        }),
      });
      const data = await safeJson(res);
      setRunResult({
        stdout: data.stdout || "",
        stderr: data.stderr || "",
        exit_code: res.ok ? data.exit_code : -1,
        duration_ms: data.duration_ms || 0,
        timed_out: data.timed_out || false,
        error_message: res.ok ? data.error_message || null : data.detail || "运行请求失败",
        compile_error: data.compile_error || null,
      });
      setStatus(RUNNABLE_LANGUAGES.has(language) ? "" : "当前后端未声明支持该语言执行，结果以真实接口返回为准。");
    } catch (error) {
      setRunResult({ stdout: "", stderr: "", exit_code: -1, error_message: "无法连接后端服务。" });
    } finally {
      setBusy("");
    }
  };

  const runTests = async () => {
    setBusy("test");
    setActiveResultTab("problems");
    setTestResults(null);
    try {
      const saved = await ensureSessionSaved();
      const challengeId = saved?.challenge_id || currentChallenge?.id;
      if (!challengeId) {
        setTestResults({ total: 0, passed: 0, results: [], error_message: "当前练习没有关联编程题，无法运行题目测试。" });
        return;
      }
      const res = await fetch(`${apiBase}/code/challenges/${challengeId}/run-tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          session_id: saved?.id || 0,
          language,
          code,
        }),
      });
      const data = await safeJson(res);
      setTestResults(res.ok ? data : { total: 0, passed: 0, results: [], error_message: data.detail || "测试运行失败" });
    } catch (error) {
      setTestResults({ total: 0, passed: 0, results: [], error_message: "无法连接后端服务。" });
    } finally {
      setBusy("");
    }
  };

  const submitForAi = async () => {
    if (!code.trim()) {
      setStatus("请先输入代码。");
      return;
    }
    setBusy("feedback");
    setActiveResultTab("feedback");
    setFeedback("");
    try {
      const saved = await ensureSessionSaved();
      const challengeId = saved?.challenge_id || currentChallenge?.id;
      if (challengeId && saved?.id) {
        const res = await fetch(`${apiBase}/code/challenges/${challengeId}/submit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            session_id: saved.id,
            code,
            language,
          }),
        });
        const data = await safeJson(res);
        setFeedback(res.ok ? data.ai_feedback || "AI 判定完成。" : data.detail || "AI 判题失败。");
      } else {
        const res = await fetch(`${apiBase}/code/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            course_id: courseId,
            session_id: saved?.id || null,
            challenge_id: null,
            language,
            code,
            question: "请基于当前代码进行判题式分析，指出错误、可改进点和下一步建议。",
            last_run_result: runResult,
            last_test_results: testResults,
          }),
        });
        const data = await safeJson(res);
        setFeedback(res.ok ? data.answer || "AI 分析完成。" : data.detail || "AI 分析失败。");
      }
      loadProgress();
    } catch (error) {
      setFeedback("无法连接后端服务。");
    } finally {
      setBusy("");
    }
  };

  const generateChallenge = async () => {
    setBusy("challenge");
    setStatus("");
    try {
      const res = await fetch(`${apiBase}/code/challenges/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: courseId,
          language,
          difficulty: "基础",
          focus: "",
          count: 1,
        }),
      });
      const data = await safeJson(res);
      if (!res.ok || !data.session) {
        setStatus(data.detail || "AI 出题失败。");
        return;
      }
      setMode("practice");
      setCurrentChallenge(data.challenge || null);
      selectSession(data.session);
      setStatus("已生成编程题，并载入当前工作台。");
      loadSessions();
    } catch (error) {
      setStatus("无法连接后端服务。");
    } finally {
      setBusy("");
    }
  };

  const askCoach = async (question = coachQuestion) => {
    const text = question.trim();
    if (!text) return;
    setBusy("coach");
    setCoachQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const saved = await ensureSessionSaved();
      const res = await fetch(`${apiBase}/code/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: courseId,
          session_id: saved?.id || null,
          challenge_id: currentChallenge?.id || saved?.challenge_id || null,
          language,
          code,
          question: text,
          last_run_result: runResult,
          last_test_results: testResults,
        }),
      });
      const data = await safeJson(res);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.ok ? data.answer || "AI 教练已回复。" : data.detail || "AI 教练暂时无法回复。" },
      ]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", content: "无法连接后端服务。" }]);
    } finally {
      setBusy("");
    }
  };

  const resultText = activeResultTab === "run"
    ? formatRunResult(runResult)
    : activeResultTab === "problems"
      ? formatTestResults(testResults)
      : feedback || "点击 AI 判题后，真实反馈会显示在这里。";

  return (
    <section className={`pw-shell${isFullscreen ? " pw-shell--fullscreen" : ""}`}>
      <div className="pw-center">
        <div className="pw-mode-tabs">
          <button className={mode === "lesson" ? "is-active" : ""} onClick={() => setMode("lesson")} type="button">微课</button>
          <button className={mode === "practice" ? "is-active" : ""} onClick={() => setMode("practice")} type="button">练习</button>
          <button className="pw-save-btn" onClick={ensureSessionSaved} type="button">{saveState || "保存"}</button>
          <button className="pw-save-btn" onClick={generateChallenge} type="button" disabled={busy === "challenge"}>
            {busy === "challenge" ? "出题中" : "AI 出题"}
          </button>
        </div>

        <div className="pw-language-tabs">
          {LANGUAGE_TABS.map((item) => (
            <button key={item} className={language === item ? "is-active" : ""} onClick={() => changeLanguage(item)} type="button">
              {item}
            </button>
          ))}
        </div>

        {currentChallenge && (
          <div className="pw-challenge">
            <strong>{currentChallenge.title}</strong>
            <span>{currentChallenge.difficulty || "练习"} · {currentChallenge.knowledge_point || language}</span>
            <p>{currentChallenge.description || currentChallenge.requirements || "请在编辑器中完成这道编程题。"}</p>
          </div>
        )}

        <div className="pw-editor-card">
          <Editor
            height="100%"
            language={MONACO_LANGUAGE[language] || "plaintext"}
            value={code}
            theme={theme === "dark" ? "vs-dark" : "light"}
            onChange={(value) => setCode(value || "")}
            onMount={(editor) => { editorRef.current = editor; }}
            options={{
              fontSize,
              minimap: { enabled: false },
              lineNumbers: "on",
              roundedSelection: true,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: language === "Python" ? 4 : 2,
              wordWrap: "on",
            }}
          />
          <div className="pw-editor-controls">
            <span>字体</span>
            <button type="button" onClick={() => setFontSize((size) => Math.max(12, size - 1))}>−</button>
            <strong>{fontSize}px</strong>
            <button type="button" onClick={() => setFontSize((size) => Math.min(24, size + 1))}>＋</button>
            <button type="button" className={theme === "light" ? "is-active" : ""} onClick={() => setTheme("light")}>浅色</button>
            <button type="button" className={theme === "dark" ? "is-active" : ""} onClick={() => setTheme("dark")}>深色</button>
            <button type="button" onClick={() => setIsFullscreen((value) => !value)}>全屏</button>
          </div>
        </div>

        <div className="pw-actions">
          <button type="button" onClick={runCode} disabled={busy === "run"}>{busy === "run" ? "运行中" : "运行"}</button>
          <button type="button" onClick={runTests} disabled={busy === "test"}>{busy === "test" ? "测试中" : "测试"}</button>
          <button type="button" onClick={submitForAi} disabled={busy === "feedback"}>{busy === "feedback" ? "分析中" : "AI 判题"}</button>
        </div>

        <div className="pw-results">
          <div className="pw-result-tabs">
            <button type="button" className={activeResultTab === "run" ? "is-active" : ""} onClick={() => setActiveResultTab("run")}>运行输出</button>
            <button type="button" className={activeResultTab === "problems" ? "is-active" : ""} onClick={() => setActiveResultTab("problems")}>问题</button>
            <button type="button" className={activeResultTab === "feedback" ? "is-active" : ""} onClick={() => setActiveResultTab("feedback")}>AI 判定反馈</button>
          </div>
          <pre>{resultText}</pre>
        </div>

        <div className="pw-bottom-row">
          <button type="button" onClick={onGoHome}>返回首页</button>
          <span>{status}</span>
          {progress && <em>提交 {progress.total_attempts || 0} · 已掌握 {progress.mastered_attempts || 0}</em>}
        </div>
      </div>

      <aside className="pw-coach">
        <div className="pw-coach-head">
          <strong>AI 教练</strong>
          <button type="button" aria-label="收起 AI 教练">»</button>
        </div>
        <div className="pw-coach-body">
          <div className="pw-bot" aria-hidden="true">
            <span>•</span><span>•</span>
          </div>
          <h2>你好！我是你的 AI 教练</h2>
          <p>我可以结合当前语言、代码、运行输出和测试结果，帮你分析思路、检查错误并给出改进建议。</p>
          <div className="pw-quick-list">
            {[
              "帮我理解这道题的思路",
              "帮我分析当前代码",
              "解释一下这个算法",
              "帮我检查代码错误",
            ].map((item) => (
              <button key={item} type="button" onClick={() => askCoach(item)}>
                <span>{item}</span><b>›</b>
              </button>
            ))}
          </div>
          <div className="pw-chat-log">
            {messages.slice(-4).map((message, index) => (
              <div key={`${message.role}-${index}`} className={`pw-chat-msg pw-chat-msg--${message.role}`}>
                {message.content}
              </div>
            ))}
          </div>
        </div>
        <form className="pw-chat-input" onSubmit={(event) => { event.preventDefault(); askCoach(); }}>
          <input
            value={coachQuestion}
            onChange={(event) => setCoachQuestion(event.target.value)}
            placeholder="向 AI 教练提问..."
          />
          <button type="submit" disabled={busy === "coach"}>➤</button>
        </form>
        <small>AI 生成内容仅供参考，请结合自身思考</small>
      </aside>
    </section>
  );
}
