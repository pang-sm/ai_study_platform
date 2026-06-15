import { useEffect, useState, useCallback } from "react";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: "数据结构",
  computer_organization: "计算机组成原理",
  operating_system: "操作系统",
  computer_network: "计算机网络",
};

const STORAGE_KEY = "exam_past_paper_state";

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch { return null; }
}
function saveState(state) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {}
}

export default function ExamPastPaperPractice({
  subjectKey = "data_structure",
  subjectName = "11408 数据结构",
  user,
  onBack,
}) {
  const saved = loadState();
  const [pastPapers, setPastPapers] = useState(null);
  const [selectedYear, setSelectedYear] = useState(saved?.year || null);
  const [questions, setQuestions] = useState([]);
  const [attemptId, setAttemptId] = useState(saved?.attemptId || null);
  const [answers, setAnswers] = useState(saved?.answers || {});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(!!saved?.submitted);
  const [result, setResult] = useState(saved?.result || null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const subjectLabel = EXAM_SUBJECTS[subjectKey] || "数据结构";

  useEffect(() => {
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-papers`)
      .then(r => r.json()).then(d => { setPastPapers(d); setLoading(false); })
      .catch(() => setPastPapers({ available: false, years: [] }));
  }, [subjectKey]);

  // Restore attempt if we have one
  useEffect(() => {
    if (!attemptId || !selectedYear) return;
    setLoading(true);
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}`)
      .then(r => r.json()).then(d => {
        setQuestions(d.questions || []);
        if (d.saved_answers) setAnswers(d.saved_answers);
        setLoading(false);
      }).catch(() => setLoading(false));
  }, [attemptId]);

  // Persist state
  useEffect(() => {
    saveState({ year: selectedYear, attemptId, answers, submitted, result });
  }, [selectedYear, attemptId, answers, submitted, result]);

  const yearsList = (pastPapers?.years && pastPapers.years.length > 0) ? pastPapers.years : [2022, 2023, 2024, 2025, 2026];

  const selectYear = async (year) => {
    setSelectedYear(year);
    setQuestions([]);
    setAttemptId(null);
    setAnswers({});
    setSubmitted(false);
    setResult(null);
    setError("");
  };

  const startPractice = async () => {
    if (!user?.username || !selectedYear) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, year: selectedYear }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "创建练习失败");
      setAttemptId(data.attempt_id);
      // Load questions for this year
      const qRes = await fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-questions?year=${selectedYear}`);
      const qData = await qRes.json();
      setQuestions(qData.questions || []);
      setAnswers({});
      setSubmitted(false);
      setResult(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const saveDraft = async () => {
    if (!attemptId) return;
    await fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
  };

  const handleAnswer = (qid, val) => {
    setAnswers(prev => ({ ...prev, [qid]: val }));
  };

  // Auto-save draft every 10 seconds
  useEffect(() => {
    if (!attemptId) return;
    const timer = setInterval(saveDraft, 10000);
    return () => clearInterval(timer);
  }, [attemptId, answers]);

  const allAnswered = questions.length > 0 && questions.every(q => {
    const a = answers[q.id];
    return a !== undefined && a !== null && String(a).trim() !== "";
  });
  const unansweredCount = questions.filter(q => !answers[q.id] || !String(answers[q.id]).trim()).length;

  const handleSubmit = async () => {
    if (questions.length === 0) {
      setError("当前年份未解析到题目，请检查真题文档解析结果");
      return;
    }
    if (!allAnswered && !window.confirm(`还有 ${unansweredCount} 题未作答，确定提交吗？`)) return;
    if (!user?.username) { setError("请先登录"); return; }
    setSubmitting(true);
    try {
      const payload = {
        username: user.username,
        answers: questions.map(q => ({
          question_id: q.id,
          user_answer: String(answers[q.id] || "").trim(),
        })),
      };
      const res = await fetch(`${API_BASE}/exam/11408/${subjectKey}/past-paper-attempts/${attemptId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "提交失败");
      setResult(data);
      setSubmitted(true);
    } catch (e) { setError(e.message); }
    finally { setSubmitting(false); }
  };

  const resetPractice = () => {
    setAttemptId(null);
    setAnswers({});
    setSubmitted(false);
    setResult(null);
  };

  if (loading && !questions.length) {
    return <div className="past-paper-loading">正在加载真题数据...</div>;
  }

  return (
    <div className="exam-past-paper-practice">
      <div className="past-paper-header">
        <button type="button" className="ghost-button compact" onClick={onBack}>← 返回练习中心</button>
        <div><h2>真题练习</h2><p>基于历年 11408 真题进行专项训练</p></div>
      </div>

      <div className="past-paper-info-card">
        <div className="past-paper-info-row"><span className="past-paper-info-label">当前科目</span><span className="past-paper-info-value">{subjectLabel}</span></div>
        <div className="past-paper-info-row"><span className="past-paper-info-label">真题范围</span><span className="past-paper-info-value">近五年真题</span></div>
        {attemptId && <div className="past-paper-info-row"><span className="past-paper-info-label">练习编号</span><span className="past-paper-info-value">第 {saved?.attemptNo || "?"} 次</span></div>}
      </div>

      <div className="past-paper-filters">
        <div className="past-paper-filter-group">
          <span className="past-paper-filter-label">年份选择</span>
          <div className="past-paper-chip-row">
            {yearsList.map(y => (
              <button key={y} type="button" className={`past-paper-chip${selectedYear === y ? " past-paper-chip--active" : ""}`} onClick={() => selectYear(y)}>{y}</button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="km-inline-message km-inline-message--error" style={{ marginBottom: 12 }}>{error}</div>}

      {submitted && result ? (
        <div className="past-paper-result">
          <h3>{selectedYear} 年真题 · 第 {saved?.attemptNo || "?"} 次练习结果</h3>
          <div className="practice-stats-grid" style={{ marginBottom: 16 }}>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_questions}</div><div className="practice-stat-card-label">总题数</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.choice_correct}/{result.choice_total}</div><div className="practice-stat-card-label">选择题正确</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_score}/{result.max_score}</div><div className="practice-stat-card-label">总分</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">❌</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.wrong_questions?.length || 0}</div><div className="practice-stat-card-label">错题数</div></div></div>
          </div>
          <div className="past-paper-result-actions">
            <button type="button" className="primary-button compact" onClick={resetPractice}>重新练习</button>
            <button type="button" className="ghost-button compact" onClick={onBack}>返回练习中心</button>
          </div>
          {result.results && (
            <div className="past-paper-question-list" style={{ marginTop: 16 }}>
              {result.results.map(r => {
                const q = questions.find(q => q.id === r.question_id);
                const isCorrect = r.type === "选择题" ? r.correct : null;
                return (
                  <div key={r.question_id} className={`past-paper-question-card ${isCorrect === true ? "past-paper-q-correct" : isCorrect === false ? "past-paper-q-wrong" : ""}`}>
                    <div className="past-paper-question-meta">
                      <span className="past-paper-q-year">{selectedYear} 年</span><span className="past-paper-q-number">第 {r.number} 题</span><span className="past-paper-q-type">{r.type}</span>
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
          )}
        </div>
      ) : selectedYear && attemptId ? (
        questions.length === 0 ? (
          <div className="past-paper-empty">
            <div className="past-paper-empty-icon">⚠️</div>
            <h3>{selectedYear} 年真题 — 未解析到题目</h3>
            <p>当前年份未解析到题目。请检查 docx 文件是否存在于 backend/exam_resources/11408/{subjectKey}/ 目录，或查看后端解析日志。</p>
          </div>
        ) : (
          <div className="past-paper-practice-body">
            <div className="past-paper-question-list">
              {questions.map(q => (
                <div key={q.id} className="past-paper-question-card">
                  <div className="past-paper-question-meta">
                    <span className="past-paper-q-year">{q.year} 年</span>
                    <span className="past-paper-q-number">第 {q.number} 题</span>
                    <span className="past-paper-q-type">{q.type}</span>
                  </div>
                  {q.content && q.content !== `第 ${q.number} 题` && <div className="past-paper-q-content">{q.content}</div>}
                  {q.image_urls && q.image_urls.length > 0 && (
                    <div className="past-paper-q-images">
                      {q.image_urls.map((url, i) => (
                        <img key={i} src={url} alt={`第${q.number}题 图片${i+1}`} className="past-paper-q-img" style={{ maxWidth: "100%", borderRadius: 8, marginBottom: 8 }} />
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
                      {q.image_urls && q.image_urls.length > 0 && <p style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: 8 }}>请根据上方题目图片作答</p>}
                      <textarea className="field" rows={5} placeholder="请输入你的答案..." value={answers[q.id] || ""} onChange={e => handleAnswer(q.id, e.target.value)} />
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="past-paper-submit-bar">
              <span>{allAnswered ? "所有题目已作答" : `还有 ${unansweredCount} 题未答`}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="ghost-button compact" onClick={saveDraft}>保存草稿</button>
                <button type="button" className="primary-button" disabled={submitting || questions.length === 0} onClick={handleSubmit}>{submitting ? "提交中..." : "已答完"}</button>
              </div>
            </div>
          </div>
        )
      ) : (
        <div className="past-paper-empty">
          <div className="past-paper-empty-icon">📋</div>
          <h3>{selectedYear ? `${selectedYear} 年真题` : "选择年份开始练习"}</h3>
          <p>选择上方年份后，点击下方按钮开始该年真题练习。每次练习会创建独立记录，可多次作答。</p>
          {selectedYear && (
            <button type="button" className="primary-button" onClick={startPractice} disabled={loading}>
              {loading ? "加载中..." : `开始 ${selectedYear} 年练习`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
