import { useEffect, useMemo, useState } from "react";
import "./CoursePracticeCenter.css";

const API_BASE = "/api";

function flattenLeaves(nodes, chapterTitle) {
  const result = [];
  (nodes || []).forEach((node) => {
    const children = node.children || [];
    const currentChapter = chapterTitle || node.title || node.name || "";
    if (children.length > 0) {
      result.push(...flattenLeaves(children, currentChapter));
    } else {
      result.push({
        code: node.code || "",
        title: node.title || node.name || "未命名知识点",
        description: node.description || "",
        chapter: currentChapter,
      });
    }
  });
  return result;
}
function chapterLabel(chapter, index) {
  const number = chapter?.chapter_no || chapter?.chapterNo || index + 1;
  const title = chapter?.title || chapter?.name || ("第 " + number + " 章");
  return ("第 " + number + " 章 " + String(title).replace(/^第\\s*\\d+\\s*章\\s*/u, "")).trim();
}

function modeLabel(mode) {
  if (mode === "ai") return "AI 生成";
  if (mode === "fallback") return "备用题（模型暂不可用）";
  return "生成失败";
}

export default function CoursePracticeCenter({ user, courseId, courseName, materials = [] }) {
  const [mapData, setMapData] = useState(null);
  const [chapterCode, setChapterCode] = useState("");
  const [pointCode, setPointCode] = useState("");
  const [question, setQuestion] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadHistory = async () => {
    if (!user?.username || !courseId) return;
    const params = new URLSearchParams({ username: user.username, course_id: courseId });
    const res = await fetch(API_BASE + "/course-learning/practice/history?" + params.toString());
    const data = await res.json().catch(() => ({}));
    if (res.ok) setHistory(Array.isArray(data.items) ? data.items : []);
  };

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user?.username || !courseId) return;
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({ course_id: courseId, username: user.username });
        const res = await fetch(API_BASE + "/knowledge-map?" + params.toString());
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "知识脉络加载失败");
        if (cancelled) return;
        setMapData(data);
        const firstChapter = data.chapters?.[0];
        setChapterCode(firstChapter?.code || "");
        const firstPoint = flattenLeaves(firstChapter?.children || [], firstChapter?.title || "")[0];
        setPointCode(firstPoint?.code || "");
        await loadHistory();
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "课程练习初始化失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [courseId, user?.username]);

  const chapters = mapData?.chapters || [];
  const activeChapter = chapters.find((item) => item.code === chapterCode) || chapters[0];
  const points = useMemo(
    () => flattenLeaves(activeChapter?.children || [], activeChapter?.title || ""),
    [activeChapter],
  );
  const selectedPoint = points.find((item) => item.code === pointCode) || points[0];

  useEffect(() => {
    if (selectedPoint?.code && selectedPoint.code !== pointCode) setPointCode(selectedPoint.code);
  }, [selectedPoint?.code, pointCode]);

  const handleChapterChange = (event) => {
    const nextCode = event.target.value;
    const nextChapter = chapters.find((item) => item.code === nextCode);
    const firstPoint = flattenLeaves(nextChapter?.children || [], nextChapter?.title || "")[0];
    setChapterCode(nextCode);
    setPointCode(firstPoint?.code || "");
    setQuestion(null);
    setResult(null);
    setAttemptId(null);
    setAnswer("");
  };

  const generate = async () => {
    if (!user?.username || !selectedPoint) return;
    setGenerating(true);
    setError("");
    setQuestion(null);
    setResult(null);
    setAttemptId(null);
    setAnswer("");
    try {
      const res = await fetch(API_BASE + "/course-learning/practice/generate", {
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
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "练习题生成失败");
      setQuestion(data.question || null);
      setAttemptId(data.attempt_id || null);
      setResult({ generation_mode: data.generation_mode, fallback_reason: data.fallback_reason });
    } catch (generateError) {
      setError(generateError.message || "练习题生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const submit = async () => {
    if (!attemptId || !answer || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(API_BASE + "/course-learning/practice/" + attemptId + "/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, answer }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "提交答案失败");
      setResult((previous) => ({ ...previous, ...data.result }));
      await loadHistory();
    } catch (submitError) {
      setError(submitError.message || "提交答案失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <section className="course-practice-page"><div className="course-practice-card">正在加载课程知识脉络...</div></section>;
  }

  return (
    <section className="course-practice-page">
      <div className="course-practice-hero">
        <div>
          <span className="course-practice-eyebrow">COURSE PRACTICE</span>
          <h1>{courseName || courseId} · 章节练习</h1>
          <p>题目只依据当前课程、章节、知识点和你选择的资料生成，不使用 11408 题库。</p>
        </div>
        <div className="course-practice-context">
          <span>当前知识点</span>
          <strong>{selectedPoint?.title || "暂无可练习知识点"}</strong>
        </div>
      </div>

      <div className="course-practice-toolbar">
        <label>
          <span>章节</span>
          <select value={chapterCode} onChange={handleChapterChange}>
            {chapters.map((chapter, index) => (
              <option key={chapter.code || index} value={chapter.code || ""}>{chapterLabel(chapter, index)}</option>
            ))}
          </select>
        </label>
        <label>
          <span>知识点</span>
          <select value={selectedPoint?.code || ""} onChange={(event) => { setPointCode(event.target.value); setQuestion(null); setResult(null); }}>
            {points.map((point) => <option key={point.code || point.title} value={point.code}>{point.title}</option>)}
          </select>
        </label>
        <button type="button" className="course-practice-primary" onClick={generate} disabled={generating || !selectedPoint}>
          {generating ? "正在生成..." : "生成一道练习"}
        </button>
      </div>

      {error && <div className="course-practice-error" role="alert">{error}</div>}

      {question ? (
        <article className="course-practice-question">
          <div className="course-practice-question-head">
            <div>
              <span className="course-practice-kicker">{activeChapter?.title || selectedPoint?.chapter || "当前章节"}</span>
              <h2>{question.stem}</h2>
            </div>
            <span className={result?.generation_mode === "fallback" ? "course-practice-mode is-fallback" : "course-practice-mode"}>
              {modeLabel(result?.generation_mode)}
            </span>
          </div>
          <div className="course-practice-options">
            {Object.entries(question.options || {}).map(([key, value]) => (
              <label key={key} className={answer === key ? "is-selected" : ""}>
                <input type="radio" name="course-practice-answer" value={key} checked={answer === key} onChange={() => setAnswer(key)} disabled={Boolean(result?.standard_answer)} />
                <span className="course-practice-option-key">{key}</span>
                <span>{value}</span>
              </label>
            ))}
          </div>
          {!result?.standard_answer && (
            <button type="button" className="course-practice-submit" onClick={submit} disabled={!answer || submitting}>
              {submitting ? "判题中..." : "提交答案"}
            </button>
          )}
          {result?.standard_answer && (
            <div className={result.correct ? "course-practice-result is-correct" : "course-practice-result is-wrong"}>
              <strong>{result.correct ? "回答正确" : "回答不正确"}</strong>
              <span>标准答案：{result.standard_answer}</span>
              <p>{result.analysis}</p>
              {result.generation_mode === "fallback" && <small>本题为备用题：AI 模型不可用时生成，仅用于保持练习流程可用。</small>}
            </div>
          )}
        </article>
      ) : (
        <div className="course-practice-empty">
          <strong>选择知识点后生成练习</strong>
          <p>{chapters.length ? "建议从当前章节的第一个知识点开始。" : "当前课程还没有可用知识脉络，请先上传资料并生成知识点。"}</p>
        </div>
      )}

      <section className="course-practice-history">
        <div className="course-practice-section-title"><h2>练习记录</h2><span>仅显示当前课程</span></div>
        {history.length === 0 ? (
          <p className="course-practice-muted">暂无练习记录</p>
        ) : (
          <div className="course-practice-history-list">
            {history.map((item) => (
              <div key={item.id} className="course-practice-history-row">
                <span>{item.knowledge_point_name || "当前知识点"}</span>
                <span>{item.status === "submitted" ? (item.correct_count ? "答对 · " : "待复盘 · ") + (item.accuracy ?? 0) + "%" : "未提交"}</span>
                <time>{item.created_at || ""}</time>
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
