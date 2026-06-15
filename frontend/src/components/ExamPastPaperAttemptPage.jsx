import { useEffect, useState, useCallback } from "react";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: "数据结构",
  computer_organization: "计算机组成原理",
  operating_system: "操作系统",
  computer_network: "计算机网络",
};

export default function ExamPastPaperAttemptPage({ subjectKey, attemptId, onNavigateBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const subjectLabel = EXAM_SUBJECTS[subjectKey] || subjectKey;

  useEffect(() => {
    if (!subjectKey || !attemptId) return;
    setLoading(true);
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}`)
      .then(r => r.json())
      .then(d => {
        if (d.attempt) { setAttempt(d.attempt); setQuestions(d.questions || []); }
        if (d.saved_answers) setAnswers(d.saved_answers);
        if (d.attempt?.status === "submitted") { setSubmitted(true); }
      })
      .catch(e => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [subjectKey, attemptId]);

  const saveDraft = useCallback(async () => {
    if (!attemptId) return;
    await fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
  }, [attemptId, answers, subjectKey]);

  useEffect(() => {
    if (!attemptId || submitted) return;
    const t = setInterval(saveDraft, 10000);
    return () => clearInterval(t);
  }, [attemptId, submitted, saveDraft]);

  const handleAnswer = (qid, val) => {
    setAnswers(prev => ({ ...prev, [qid]: val }));
  };

  const unansweredCount = questions.filter(q => {
    const a = answers[q.id];
    return !a || !String(a).trim();
  }).length;

  const handleSubmit = async () => {
    if (questions.length === 0) { setError("无题目可提交"); return; }
    if (unansweredCount > 0 && !window.confirm(`还有 ${unansweredCount} 题未答，确定提交？`)) return;
    setSubmitting(true);
    try {
      const payload = {
        answers: questions.map(q => ({
          question_id: q.id,
          user_answer: String(answers[q.id] || "").trim(),
        })),
      };
      const res = await fetch(
        `${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}/submit`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "提交失败");
      setResult(data);
      setSubmitted(true);
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  if (loading) return <div className="attempt-page-loading">加载中...</div>;
  if (error && !questions.length) return <div className="attempt-page-error">{error}</div>;

  return (
    <div className="attempt-page">
      <header className="attempt-page-header">
        <div className="attempt-page-header-left">
          <button type="button" className="ghost-button compact" onClick={onNavigateBack}>
            ← 返回练习中心
          </button>
          <div>
            <h2>11408 真题练习</h2>
            <p>{subjectLabel} · {attempt?.year || "?"} 年 · 第 {attempt?.attempt_no || "?"} 次</p>
          </div>
        </div>
        <div className="attempt-page-header-right">
          <button type="button" className="ghost-button compact" onClick={saveDraft}>保存进度</button>
        </div>
      </header>

      {submitted && result ? (
        <div className="attempt-page-result">
          <h3>练习结果</h3>
          <div className="practice-stats-grid" style={{ marginBottom: 16 }}>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_questions}</div><div className="practice-stat-card-label">总题数</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.choice_correct}/{result.choice_total}</div><div className="practice-stat-card-label">选择题正确</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_score}/{result.max_score}</div><div className="practice-stat-card-label">总分</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">❌</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.wrong_questions?.length || 0}</div><div className="practice-stat-card-label">错题数</div></div></div>
          </div>
          {result.results && result.results.map(r => {
            const q = questions.find(q => q.id === r.question_id);
            const isCorrect = r.type === "选择题" ? r.correct : null;
            return (
              <div key={r.question_id} className={`past-paper-question-card ${isCorrect === true ? "past-paper-q-correct" : isCorrect === false ? "past-paper-q-wrong" : ""}`}>
                <div className="past-paper-question-meta">
                  <span className="past-paper-q-year">{attempt?.year} 年</span>
                  <span className="past-paper-q-number">第 {r.number} 题</span>
                  <span className="past-paper-q-type">{r.type}</span>
                  {isCorrect !== null && <span className={`past-paper-q-result-tag ${isCorrect ? "past-paper-q-result-tag--correct" : "past-paper-q-result-tag--wrong"}`}>{isCorrect ? "正确" : "错误"}</span>}
                </div>
                {q?.content && <div className="past-paper-q-content">{q.content}</div>}
                <div className="past-paper-q-answer-row"><span className="past-paper-q-label">你的答案：</span><span className={isCorrect ? "text-correct" : "text-wrong"}>{r.user_answer || "未作答"}</span></div>
                <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{r.standard_answer}</span></div>
                {r.type === "大题" && r.feedback && <div className="past-paper-q-feedback"><strong>评分：{r.score}/{r.full_score} 分</strong><p>{r.feedback}</p></div>}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="attempt-page-body">
          {questions.length === 0 ? (
            <div className="past-paper-empty">当前年份无题目数据</div>
          ) : (
            <div className="past-paper-question-list">
              {questions.map(q => (
                <div key={q.id} className="past-paper-question-card">
                  <div className="past-paper-question-meta">
                    <span className="past-paper-q-year">{q.year} 年</span>
                    <span className="past-paper-q-number">第 {q.number} 题</span>
                    <span className="past-paper-q-type">{q.type}</span>
                  </div>
                  {q.content && q.content !== `第 ${q.number} 题` && <div className="past-paper-q-content">{q.content}</div>}
                  {q.image_urls?.length > 0 && (
                    <div className="past-paper-q-images">
                      {q.image_urls.map((url, i) => (
                        <img key={i} src={url} alt={`第${q.number}题`} className="past-paper-q-img" />
                      ))}
                    </div>
                  )}
                  {q.type === "选择题" ? (
                    <div className="past-paper-options">
                      {["A", "B", "C", "D"].map(opt => (
                        <label key={opt} className={`past-paper-option ${answers[q.id] === opt ? "past-paper-option--selected" : ""}`}>
                          <input type="radio" name={`q_${q.id}`} value={opt} checked={answers[q.id] === opt} onChange={() => handleAnswer(q.id, opt)} />
                          <span>{opt}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <div className="past-paper-big-answer">
                      {q.image_urls?.length > 0 && <p style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: 8 }}>请根据上方题目图片作答</p>}
                      <textarea className="field" rows={5} placeholder="请输入你的答案..." value={answers[q.id] || ""} onChange={e => handleAnswer(q.id, e.target.value)} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {questions.length > 0 && (
            <div className="past-paper-submit-bar">
              <span>{unansweredCount === 0 ? "所有题目已作答" : `还有 ${unansweredCount} 题未答`}</span>
              <button type="button" className="primary-button" disabled={submitting || questions.length === 0} onClick={handleSubmit}>
                {submitting ? "提交中..." : "已答完"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
