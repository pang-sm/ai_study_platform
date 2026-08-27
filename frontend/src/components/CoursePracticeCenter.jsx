import { useEffect, useMemo, useState } from "react";
import "./CoursePracticeCenter.css";

const API_BASE = "/api";
const STATUS_OPTIONS = [
  ["all", "全部"],
  ["unanswered", "未作答"],
  ["wrong", "答错"],
  ["correct", "答对"],
];

function flattenLeaves(nodes, chapterTitle) {
  const result = [];
  (nodes || []).forEach((node) => {
    const children = node.children || [];
    const currentChapter = chapterTitle || node.title || node.name || "";
    if (children.length) result.push(...flattenLeaves(children, currentChapter));
    else result.push({ code: node.code || "", title: node.title || node.name || "未命名知识点", chapter: currentChapter });
  });
  return result;
}

function chapterLabel(chapter, index) {
  const number = chapter?.chapter_no || chapter?.chapterNo || index + 1;
  const title = chapter?.title || chapter?.name || `第 ${number} 章`;
  return `第 ${number} 章 ${String(title).replace(/^第\s*\d+\s*章\s*/u, "")}`.trim();
}

function statusLabel(status) {
  return ({ unanswered: "未作答", correct: "已答对", wrong: "已答错" })[status] || "未作答";
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

export default function CoursePracticeCenter({ user, courseId, courseName, materials = [] }) {
  const [mapData, setMapData] = useState(null);
  const [chapterCode, setChapterCode] = useState("");
  const [pointCode, setPointCode] = useState("");
  const [filterChapter, setFilterChapter] = useState("");
  const [filterPoint, setFilterPoint] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [workbook, setWorkbook] = useState([]);
  const [question, setQuestion] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [workbookLoading, setWorkbookLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const chapters = mapData?.chapters || [];
  const activeChapter = chapters.find((item) => item.code === chapterCode) || chapters[0];
  const points = useMemo(() => flattenLeaves(activeChapter?.children || [], activeChapter?.title || ""), [activeChapter]);
  const selectedPoint = points.find((item) => item.code === pointCode) || points[0];
  const allPoints = useMemo(() => chapters.flatMap((chapter) => flattenLeaves(chapter.children || [], chapter.title || "")), [chapters]);

  const loadWorkbook = async () => {
    if (!user?.username || !courseId) return;
    setWorkbookLoading(true);
    try {
      const params = new URLSearchParams({ username: user.username, course_id: courseId, status: filterStatus });
      if (filterChapter) params.set("chapter", filterChapter);
      if (filterPoint) params.set("knowledge_point_code", filterPoint);
      const response = await fetch(`${API_BASE}/course-learning/practice/workbook?${params}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "AI 题册加载失败");
      setWorkbook(Array.isArray(data.items) ? data.items : []);
    } catch (loadError) {
      setError(loadError.message || "AI 题册加载失败");
    } finally {
      setWorkbookLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user?.username || !courseId) return;
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({ course_id: courseId, username: user.username });
        const response = await fetch(`${API_BASE}/knowledge-map?${params}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "知识脉络加载失败");
        if (cancelled) return;
        const firstChapter = data.chapters?.[0];
        const firstPoint = flattenLeaves(firstChapter?.children || [], firstChapter?.title || "")[0];
        setMapData(data);
        setChapterCode(firstChapter?.code || "");
        setPointCode(firstPoint?.code || "");
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "课程练习初始化失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [courseId, user?.username]);

  useEffect(() => { loadWorkbook(); }, [courseId, user?.username]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedPoint?.code && selectedPoint.code !== pointCode) setPointCode(selectedPoint.code);
  }, [selectedPoint?.code, pointCode]);

  const clearActivePractice = () => {
    setQuestion(null);
    setAttemptId(null);
    setAnswer("");
    setResult(null);
  };

  const generate = async () => {
    if (!user?.username || !selectedPoint) return;
    setGenerating(true);
    setError("");
    clearActivePractice();
    try {
      const response = await fetch(`${API_BASE}/course-learning/practice/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: courseId,
          course_name: courseName,
          chapter: activeChapter?.title || selectedPoint.chapter,
          knowledge_point_code: selectedPoint.code,
          knowledge_point_title: selectedPoint.title,
          material_ids: materials.map((item) => item.id).filter(Boolean).slice(0, 10),
          difficulty: "基础",
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "练习题生成失败");
      setQuestion(data.question || null);
      setAttemptId(data.attempt_id || null);
      setResult({ generation_mode: data.generation_mode, fallback_reason: data.fallback_reason });
      await loadWorkbook();
    } catch (generateError) {
      setError(generateError.message || "练习题生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const startAttempt = async (item) => {
    setError("");
    try {
      const response = await fetch(`${API_BASE}/course-learning/practice/workbook/${item.id}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "无法开始本次练习");
      setQuestion(data.question || item);
      setAttemptId(data.attempt_id || null);
      setAnswer("");
      setResult(null);
    } catch (startError) {
      setError(startError.message || "无法开始本次练习");
    }
  };

  const submit = async () => {
    if (!attemptId || !answer || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/course-learning/practice/${attemptId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, answer }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "提交答案失败");
      setResult((previous) => ({ ...previous, ...data.result }));
      await loadWorkbook();
    } catch (submitError) {
      setError(submitError.message || "提交答案失败");
    } finally {
      setSubmitting(false);
    }
  };

  const changeChapter = (event) => {
    const nextCode = event.target.value;
    const next = chapters.find((item) => item.code === nextCode);
    setChapterCode(nextCode);
    setPointCode(flattenLeaves(next?.children || [], next?.title || "")[0]?.code || "");
  };

  if (loading) return <section className="course-practice-page"><div className="course-practice-card">正在加载课程知识脉络...</div></section>;

  return (
    <section className="course-practice-page">
      <header className="course-practice-hero course-practice-hero--compact">
        <div>
          <h1>章节练习 · {courseName || courseId}</h1>
        </div>
        <div className="course-practice-context"><span>当前范围</span><strong>{activeChapter?.title || "请选择章节"}</strong>{selectedPoint?.title && <em>{selectedPoint.title}</em>}</div>
      </header>

      <section className="course-practice-generate-card">
        <div className="course-practice-picker">
          <label><span>章节</span><select value={chapterCode} onChange={changeChapter}>{chapters.map((item, index) => <option key={item.code || index} value={item.code || ""}>{chapterLabel(item, index)}</option>)}</select></label>
          <label><span>知识点</span><select value={selectedPoint?.code || ""} onChange={(event) => setPointCode(event.target.value)}>{points.map((item) => <option key={item.code || item.title} value={item.code}>{item.title}</option>)}</select></label>
        </div>
        <button type="button" className="course-practice-primary" onClick={generate} disabled={generating || !selectedPoint}>{generating ? "正在生成..." : "+ AI 生成新题"}</button>
      </section>

      {error && <div className="course-practice-error" role="alert">{error}</div>}

      {question && <article className="course-practice-question">
        <div className="course-practice-question-head"><div><span className="course-practice-kicker">{question.knowledge_point_path || "当前章节"} · {question.knowledge_point_name || "当前知识点"}</span><h2>{question.stem}</h2></div><span className={result?.generation_mode === "fallback" ? "course-practice-mode is-fallback" : "course-practice-mode"}>{result?.generation_mode === "fallback" ? "备用题" : "AI 题册"}</span></div>
        <div className="course-practice-options">{Object.entries(question.options || {}).map(([key, value]) => <label key={key} className={answer === key ? "is-selected" : ""}><input type="radio" name="course-practice-answer" value={key} checked={answer === key} onChange={() => setAnswer(key)} disabled={Boolean(result?.standard_answer)} /><span className="course-practice-option-key">{key}</span><span>{value}</span></label>)}</div>
        {!result?.standard_answer && <button type="button" className="course-practice-submit" onClick={submit} disabled={!answer || submitting}>{submitting ? "判题中..." : "提交答案"}</button>}
        {result?.standard_answer && <div className={result.correct ? "course-practice-result is-correct" : "course-practice-result is-wrong"}><strong>{result.correct ? "回答正确" : "回答不正确"}</strong><span>标准答案：{result.standard_answer}</span><p>{result.analysis}</p><button type="button" className="course-practice-secondary" onClick={() => clearActivePractice()}>返回 AI 题册</button></div>}
      </article>}

      <section className="course-practice-history">
        <div className="course-practice-section-title"><div><span className="course-practice-eyebrow">AI WORKBOOK</span><h2>AI 题册</h2><p>按最近一次作答显示状态，并保留每次练习历史。</p></div><span>{workbook.length} 道题</span></div>
        <div className="course-practice-filters">
          <select value={filterChapter} onChange={(event) => setFilterChapter(event.target.value)}><option value="">全部章节</option>{chapters.map((item, index) => <option key={item.code || index} value={item.title || ""}>{chapterLabel(item, index)}</option>)}</select>
          <select value={filterPoint} onChange={(event) => setFilterPoint(event.target.value)}><option value="">全部知识点</option>{allPoints.map((item) => <option key={item.code || item.title} value={item.code}>{item.title}</option>)}</select>
          <select value={filterStatus} onChange={(event) => setFilterStatus(event.target.value)}>{STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <button type="button" className="course-practice-secondary" onClick={loadWorkbook} disabled={workbookLoading}>{workbookLoading ? "筛选中..." : "应用筛选"}</button>
        </div>
        {workbookLoading ? <p className="course-practice-muted">正在加载 AI 题册...</p> : workbook.length === 0 ? <div className="course-practice-empty"><strong>还没有匹配的 AI 题目</strong><p>选择知识点后生成第一道题，它会保存在这里。</p></div> : <div className="course-workbook-list">{workbook.map((item) => <article key={item.id} className="course-workbook-item"><div className="course-workbook-top"><span className={`course-workbook-status is-${item.workbook_status}`}>{statusLabel(item.workbook_status)}</span><time>{formatTime(item.created_at)}</time></div><h3>{item.stem}</h3><p>{item.knowledge_point_path || "当前章节"} · {item.knowledge_point_name || "当前知识点"}</p><div className="course-workbook-meta"><span>练习 {item.attempt_count || 0} 次</span>{item.latest_attempt?.status === "submitted" && <span>最近一次：{item.latest_attempt.correct ? "正确" : "错误"}</span>}</div>{item.attempts?.length > 0 && <div className="course-workbook-attempt-history">{item.attempts.slice().reverse().map((attempt, index) => <span key={attempt.id}>第 {index + 1} 次：{attempt.status === "submitted" ? (attempt.correct ? "正确" : "错误") : "未提交"}</span>)}</div>}<button type="button" className="course-practice-secondary" onClick={() => startAttempt(item)}>{item.attempt_count ? "重新练习" : "开始练习"}</button></article>)}</div>}
      </section>
    </section>
  );
}
