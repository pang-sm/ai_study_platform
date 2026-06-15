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
  onBack,
}) {
  const [pastPapers, setPastPapers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedYears, setSelectedYears] = useState(initialYears.length > 0 ? initialYears : []);
  const [selectedType, setSelectedType] = useState(initialType || "all");
  const [questions, setQuestions] = useState([]);

  const subjectLabel = EXAM_SUBJECTS[subjectKey] || "数据结构";

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => {
        setPastPapers(data);
        // Try to load questions if a backend endpoint exists
        const params = new URLSearchParams();
        if (selectedYears.length > 0) {
          selectedYears.forEach((y) => params.append("year", y));
        }
        if (selectedType) params.set("type", selectedType);
        return fetch(
          `${API_BASE}/api/exam/11408/${subjectKey}/past-paper-questions?${params.toString()}`
        ).then((r) => r.json());
      })
      .then((data) => {
        if (data?.questions) setQuestions(data.questions);
      })
      .catch(() => setQuestions([]))
      .finally(() => setLoading(false));
  }, [subjectKey, selectedYears, selectedType]);

  const allYears = [];
  let resourceFilenames = [];
  if (pastPapers?.resource_files) {
    for (const f of pastPapers.resource_files) {
      resourceFilenames.push(f.filename);
      for (const y of f.years || []) {
        if (!allYears.includes(y)) allYears.push(y);
      }
    }
    allYears.sort((a, b) => b - a);
  }

  const toggleYear = (year) => {
    setSelectedYears((prev) =>
      prev.includes(year) ? prev.filter((v) => v !== year) : [...prev, year]
    );
  };

  const displayYears = selectedYears.length > 0 ? selectedYears : allYears;

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
          <span className="past-paper-info-value">
            {displayYears.length > 0 ? displayYears.map((y) => `${y}年`).join("、") : "近五年真题"}
          </span>
        </div>
        <div className="past-paper-info-row">
          <span className="past-paper-info-label">题型</span>
          <span className="past-paper-info-value">
            {selectedType === "all" ? "全部" : selectedType === "choice" ? "选择题" : "大题"}
          </span>
        </div>
        {resourceFilenames.length > 0 && (
          <div className="past-paper-info-row">
            <span className="past-paper-info-label">来源文件</span>
            <span className="past-paper-info-value past-paper-info-files">
              {resourceFilenames.join("、")}
            </span>
          </div>
        )}
      </div>

      <div className="past-paper-filters">
        <div className="past-paper-filter-group">
          <span className="past-paper-filter-label">年份选择</span>
          <div className="past-paper-chip-row">
            <button
              type="button"
              className={`past-paper-chip${selectedYears.length === 0 ? " past-paper-chip--active" : ""}`}
              onClick={() => setSelectedYears([])}
            >
              全部
            </button>
            {allYears.map((y) => (
              <button
                key={y}
                type="button"
                className={`past-paper-chip${selectedYears.includes(y) ? " past-paper-chip--active" : ""}`}
                onClick={() => toggleYear(y)}
              >
                {y}
              </button>
            ))}
          </div>
        </div>

        <div className="past-paper-filter-group">
          <span className="past-paper-filter-label">题型选择</span>
          <div className="past-paper-chip-row">
            {[
              { value: "all", label: "全部" },
              { value: "choice", label: "选择题" },
              { value: "short_answer", label: "大题" },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`past-paper-chip${selectedType === opt.value ? " past-paper-chip--active" : ""}`}
                onClick={() => setSelectedType(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="past-paper-questions">
        {loading ? (
          <div className="past-paper-loading">正在加载真题资料...</div>
        ) : questions.length > 0 ? (
          <div className="past-paper-question-list">
            {questions.map((q, idx) => (
              <div key={idx} className="past-paper-question-card">
                <div className="past-paper-question-meta">
                  <span className="past-paper-q-year">{q.year} 年</span>
                  <span className="past-paper-q-number">第 {q.number} 题</span>
                  <span className="past-paper-q-type">{q.type}</span>
                </div>
                <div className="past-paper-q-content">{q.content}</div>
                {q.options && q.options.length > 0 && (
                  <div className="past-paper-q-options">
                    {q.options.map((opt, oi) => (
                      <div key={oi} className="past-paper-q-option">
                        {opt}
                      </div>
                    ))}
                  </div>
                )}
                <details className="past-paper-q-answer">
                  <summary>查看答案</summary>
                  <span className="past-paper-q-answer-text">答案：{q.answer}</span>
                </details>
              </div>
            ))}
          </div>
        ) : (
          <div className="past-paper-empty">
            <div className="past-paper-empty-icon">📋</div>
            <h3>真题文件已接入，题目解析功能正在完善</h3>
            <p>
              当前科目：<strong>{subjectLabel}</strong> 的真题文档已上传至系统。
              你可以先确认年份和题型，题目解析功能将在后续版本中正式开放，
              届时你将可以在这里直接刷真题。
            </p>
            <div className="past-paper-empty-files">
              {resourceFilenames.length > 0 ? (
                resourceFilenames.map((fn, i) => (
                  <div key={i} className="past-paper-file-item">
                    📄 {fn}
                  </div>
                ))
              ) : (
                <div className="past-paper-file-item">
                  暂无真题文件。请将真题文档放入 backend/exam_resources/11408/{subjectKey}/ 目录。
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
