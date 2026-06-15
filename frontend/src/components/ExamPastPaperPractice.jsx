import { useEffect, useState } from "react";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: "数据结构",
  computer_organization: "计算机组成原理",
  operating_system: "操作系统",
  computer_network: "计算机网络",
};

export default function ExamPastPaperPractice({
  subjectKey = "data_structure",
  subjectName = "11408 数据结构",
  years: initialYears = [],
  questionType: initialType = "all",
  user,
  onBack,
}) {
  const [loading, setLoading] = useState(true);
  const [pastPapers, setPastPapers] = useState(null);
  const [selectedYear, setSelectedYear] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const subjectLabel = EXAM_SUBJECTS[subjectKey] || "数据结构";

  useEffect(() => {
    fetch(`${API_BASE}/api/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => {
        setPastPapers(data);
        if (data.years && data.years.length > 0) {
          setSelectedYear(data.years[0]);
        }
      })
      .catch(() => setPastPapers({ available: false, years: [] }))
      .finally(() => setLoading(false));
  }, [subjectKey]);

  useEffect(() => {
    if (!selectedYear) return;
    setLoading(true);
    setQuestions([]);
    setAnswers({});
    setSubmitted(false);
    setResult(null);
    setError("");
    fetch(`${API_BASE}/api/exam/11408/${subjectKey}/past-paper-questions?year=${selectedYear}`)
      .then((r) => r.json())
      .then((data) => {
        setQuestions(data.questions || []);
      })
      .catch(() => setError("题目加载失败"))
      .finally(() => setLoading(false));
  }, [subjectKey, selectedYear]);

  const yearsList = pastPapers?.years || [];

  const handleAnswer = (qid, value) => {
    setAnswers((prev) => ({ ...prev, [qid]: value }));
  };

  const allAnswered = questions.length > 0 && questions.every((q) => {
    const a = answers[q.id];
    return a !== undefined && a !== null && String(a).trim() !== "";
  });

  const handleSubmit = async () => {
    if (!allAnswered) {
      if (!window.confirm(`还有 ${questions.filter((q) => !answers[q.id] || !String(answers[q.id]).trim()).length} 道题未作答，确定提交吗？`)) {
        return;
      }
    }
    if (!user?.username) {
      setError("请先登录");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        username: user.username,
        year: selectedYear,
        answers: questions.map((q) => ({
          question_id: q.id,
          user_answer: String(answers[q.id] || "").trim(),
        })),
      };
      const res = await fetch(`${API_BASE}/api/exam/11408/${subjectKey}/past-paper-submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "提交失败");
      setResult(data);
      setSubmitted(true);
    } catch (e) {
      setError(e.message || "提交失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const resetPractice = () => {
    setAnswers({});
    setSubmitted(false);
    setResult(null);
  };

  const choiceCount = questions.filter((q) => q.type === "选择题").length;
  const bigCount = questions.filter((q) => q.type === "大题").length;

  return (
    <div className="exam-past-paper-practice">
      <div className="past-paper-header">
        <button type="button" className="ghost-button compact" onClick={onBack}>
          ← 返回练习中心
        </button>
        <div>
          <h2>真题练习</h2>
          <p>基于历年 11408 真题进行专项训练</p>
        </div>
      </div>

      <div className="past-paper-info-card">
        <div className="past-paper-info-row">
          <span className="past-paper-info-label">当前科目</span>
          <span className="past-paper-info-value">{subjectLabel}</span>
        </div>
        <div className="past-paper-info-row">
          <span className="past-paper-info-label">真题范围</span>
          <span className="past-paper-info-value">近五年真题</span>
        </div>
        {pastPapers?.resource_files?.[0] && (
          <div className="past-paper-info-row">
            <span className="past-paper-info-label">来源文件</span>
            <span className="past-paper-info-value past-paper-info-files">
              {pastPapers.resource_files[0].filename}
            </span>
          </div>
        )}
      </div>

      <div className="past-paper-filters">
        <div className="past-paper-filter-group">
          <span className="past-paper-filter-label">年份选择</span>
          <div className="past-paper-chip-row">
            {yearsList.map((y) => (
              <button
                key={y}
                type="button"
                className={`past-paper-chip${selectedYear === y ? " past-paper-chip--active" : ""}`}
                onClick={() => setSelectedYear(y)}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="km-inline-message km-inline-message--error" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {(() => {
        if (loading) return <div className="past-paper-loading">正在加载 {selectedYear} 年真题...</div>;
        if (submitted && result) return (
        <div className="past-paper-result">
          <div className="past-paper-result-header">
            <h3>{selectedYear} 年真题练习结果</h3>
          </div>
          <div className="practice-stats-grid" style={{ marginBottom: 16 }}>
            <div className="practice-stat-card--dashboard">
              <div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div>
              <div className="practice-stat-card-body">
                <div className="practice-stat-card-value">{result.total_questions}</div>
                <div className="practice-stat-card-label">总题数</div>
              </div>
            </div>
            <div className="practice-stat-card--dashboard">
              <div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div>
              <div className="practice-stat-card-body">
                <div className="practice-stat-card-value">{result.choice_correct}/{result.choice_total}</div>
                <div className="practice-stat-card-label">选择题正确</div>
              </div>
            </div>
            <div className="practice-stat-card--dashboard">
              <div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div>
              <div className="practice-stat-card-body">
                <div className="practice-stat-card-value">
                  {result.total_score}/{result.max_score}
                </div>
                <div className="practice-stat-card-label">总分</div>
              </div>
            </div>
            <div className="practice-stat-card--dashboard">
              <div className="practice-stat-card-icon practice-stat-card-icon--time">❌</div>
              <div className="practice-stat-card-body">
                <div className="practice-stat-card-value">{result.wrong_questions?.length || 0}</div>
                <div className="practice-stat-card-label">错题数</div>
              </div>
            </div>
          </div>

          <div className="past-paper-result-actions">
            <button type="button" className="primary-button compact" onClick={resetPractice}>
              重新练习
            </button>
            <button type="button" className="ghost-button compact" onClick={onBack}>
              返回练习中心
            </button>
          </div>

          {result.results && (
            <div className="past-paper-question-list" style={{ marginTop: 16 }}>
              {result.results.map((r) => {
                const q = questions.find((q) => q.id === r.question_id);
                const isCorrect = r.correct === true;
                const isBig = r.type === "大题";
                return (
                  <div key={r.question_id} className={`past-paper-question-card ${isCorrect ? "past-paper-q-correct" : "past-paper-q-wrong"}`}>
                    <div className="past-paper-question-meta">
                      <span className="past-paper-q-year">{selectedYear} 年</span>
                      <span className="past-paper-q-number">第 {r.number} 题</span>
                      <span className="past-paper-q-type">{r.type}</span>
                      {!isBig && (
                        <span className={`past-paper-q-result-tag ${isCorrect ? "past-paper-q-result-tag--correct" : "past-paper-q-result-tag--wrong"}`}>
                          {isCorrect ? "正确" : "错误"}
                        </span>
                      )}
                    </div>
                    {q?.content && (
                      <div className="past-paper-q-content">{q.content}</div>
                    )}
                    <div className="past-paper-q-answer-row">
                      <span className="past-paper-q-label">你的答案：</span>
                      <span className={isCorrect ? "text-correct" : "text-wrong"}>{r.user_answer || "未作答"}</span>
                    </div>
                    <div className="past-paper-q-answer-row">
                      <span className="past-paper-q-label">标准答案：</span>
                      <span>{r.standard_answer}</span>
                    </div>
                    {isBig && r.feedback && (
                      <div className="past-paper-q-feedback">
                        <strong>评分：{r.score}/{r.full_score} 分</strong>
                        <p>{r.feedback}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
      if (questions.length === 0) return (
        <div className="past-paper-empty">
          <div className="past-paper-empty-icon">📋</div>
          <h3>{selectedYear} 年真题</h3>
          <p>
            当前科目：<strong>{subjectLabel}</strong>，共有 {choiceCount} 道选择题、{bigCount} 道大题。
            真题题目为图片格式，目前显示题目图片。后续版本将接入 OCR 自动识别题目文本。
          </p>
          <div className="past-paper-question-list">
            {questions.map((q) => (
              <div key={q.id} className="past-paper-question-card">
                <div className="past-paper-question-meta">
                  <span className="past-paper-q-year">{q.year} 年</span>
                  <span className="past-paper-q-number">第 {q.number} 题</span>
                  <span className="past-paper-q-type">{q.type}</span>
                </div>
                <div className="past-paper-q-content">{q.content}</div>
                {q.type === "选择题" ? (
                  <div className="past-paper-options">
                    {["A", "B", "C", "D"].map((opt) => (
                      <label key={opt} className={`past-paper-option ${answers[q.id] === opt ? "past-paper-option--selected" : ""}`}>
                        <input
                          type="radio"
                          name={`q_${q.id}`}
                          value={opt}
                          checked={answers[q.id] === opt}
                          onChange={() => handleAnswer(q.id, opt)}
                        />
                        <span>{opt}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="past-paper-big-answer">
                    <textarea
                      className="field"
                      rows={4}
                      placeholder="请输入你的答案..."
                      value={answers[q.id] || ""}
                      onChange={(e) => handleAnswer(q.id, e.target.value)}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="past-paper-submit-bar">
            <span>
              {allAnswered ? "所有题目已作答" : `还有 ${questions.filter((q) => !answers[q.id] || !String(answers[q.id]).trim()).length} 题未答`}
            </span>
            <button
              type="button"
              className="primary-button"
              disabled={submitting || questions.length === 0}
              onClick={handleSubmit}
            >
              {submitting ? "提交中..." : "已答完"}
            </button>
          </div>
        </div>
      );
      return null;
      })()}
    </div>
  );
}
