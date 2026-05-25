import { useEffect, useState } from "react";

const API_BASE = "/api";

const TYPE_OPTIONS = [
  { value: "", label: "全部题型" },
  { value: "choice", label: "选择题" },
  { value: "short_answer", label: "简答题" },
  { value: "programming", label: "编程题" },
];

const DIFFICULTY_OPTIONS = [
  { value: "基础", label: "基础" },
  { value: "中等", label: "中等" },
  { value: "提高", label: "提高" },
];

const TYPE_LABELS = {
  choice: "选择题",
  short_answer: "简答题",
  programming: "编程题",
};

const SOURCE_LABELS = {
  manual: "手动创建",
  ai: "AI 生成",
  imported: "导入",
};

const RESULT_LABELS = {
  correct: "正确",
  incorrect: "错误",
  partially_correct: "部分正确",
  unknown: "未知",
};

export default function PracticeCenter({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
}) {
  const [questions, setQuestions] = useState([]);
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [courseFilter, setCourseFilter] = useState(subject || "");
  const [kpFilter, setKpFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  // Detail modal
  const [detailQuestion, setDetailQuestion] = useState(null);
  const [userAnswer, setUserAnswer] = useState("");
  const [attempts, setAttempts] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [detailActionLoading, setDetailActionLoading] = useState(false);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createType, setCreateType] = useState("choice");
  const [createTitle, setCreateTitle] = useState("");
  const [createContent, setCreateContent] = useState("");
  const [createOptions, setCreateOptions] = useState("");
  const [createAnswer, setCreateAnswer] = useState("");
  const [createExplanation, setCreateExplanation] = useState("");
  const [createCourse, setCreateCourse] = useState(subject || "");
  const [createKpId, setCreateKpId] = useState("");
  const [createDifficulty, setCreateDifficulty] = useState("基础");
  const [createSaving, setCreateSaving] = useState(false);

  // AI generate modal
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [genCourse, setGenCourse] = useState(subject || "");
  const [genCourseName, setGenCourseName] = useState("");
  const [genKpId, setGenKpId] = useState("");
  const [genType, setGenType] = useState("choice");
  const [genDifficulty, setGenDifficulty] = useState("基础");
  const [genCount, setGenCount] = useState(1);
  const [genLoading, setGenLoading] = useState(false);

  const loadKnowledgePoints = async (courseId) => {
    if (!user?.username || !courseId) {
      setKnowledgePoints([]);
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`
      );
      const data = await res.json();
      if (res.ok) {
        setKnowledgePoints(data.knowledge_points || []);
      }
    } catch (e) {
      console.error("Failed to load knowledge points:", e);
    }
  };

  const loadQuestions = async () => {
    if (!user?.username) return;
    setLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      const normalizedCourse = normalizeSubject(courseFilter, "");
      if (normalizedCourse) query.set("course_id", normalizedCourse);
      if (kpFilter) query.set("knowledge_point_id", kpFilter);
      if (typeFilter) query.set("type", typeFilter);
      const res = await fetch(`${API_BASE}/practice/questions?${query.toString()}`);
      const data = await res.json();
      if (res.ok) {
        setQuestions(data.questions || []);
      }
    } catch (e) {
      console.error("Failed to load questions:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const normalizedCourse = normalizeSubject(courseFilter, "");
    loadKnowledgePoints(normalizedCourse);
  }, [user?.username, courseFilter]);

  useEffect(() => {
    loadQuestions();
  }, [user?.username, courseFilter, kpFilter, typeFilter]);

  const openDetail = async (q) => {
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${q.id}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok) {
        setDetailQuestion(data.question);
        setUserAnswer("");
        setFeedback("");
        await loadAttempts(q.id);
      }
    } catch (e) {
      console.error("Failed to load question detail:", e);
    }
  };

  const loadAttempts = async (questionId) => {
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${questionId}/attempts?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok) {
        setAttempts(data.attempts || []);
      }
    } catch (e) {
      console.error("Failed to load attempts:", e);
    }
  };

  const submitAnswer = async () => {
    if (!userAnswer.trim()) return;
    setDetailActionLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${detailQuestion.id}/attempts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            question_id: detailQuestion.id,
            user_answer: userAnswer.trim(),
          }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        await loadAttempts(detailQuestion.id);
      }
    } catch (e) {
      console.error("Failed to submit answer:", e);
    } finally {
      setDetailActionLoading(false);
    }
  };

  const requestFeedback = async () => {
    if (!userAnswer.trim()) return;
    setFeedbackLoading(true);
    setFeedback("");
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${detailQuestion.id}/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            user_answer: userAnswer.trim(),
          }),
        }
      );
      const data = await res.json();
      if (res.ok) {
        setFeedback(data.feedback || "");
        await loadAttempts(detailQuestion.id);
      }
    } catch (e) {
      console.error("Failed to get AI feedback:", e);
    } finally {
      setFeedbackLoading(false);
    }
  };

  const createQuestion = async () => {
    if (!createTitle.trim() || !createContent.trim()) return;
    setCreateSaving(true);
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(createCourse, ""),
        knowledge_point_id: createKpId ? parseInt(createKpId) : null,
        type: createType,
        title: createTitle.trim(),
        content: createContent.trim(),
        options: createOptions.trim() || null,
        answer: createAnswer.trim() || null,
        explanation: createExplanation.trim() || null,
        difficulty: createDifficulty,
        source: "manual",
      };
      const res = await fetch(`${API_BASE}/practice/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowCreateModal(false);
        resetCreateForm();
        await loadQuestions();
      } else {
        alert(data.detail || "创建失败");
      }
    } catch (e) {
      console.error("Failed to create question:", e);
    } finally {
      setCreateSaving(false);
    }
  };

  const resetCreateForm = () => {
    setCreateType("choice");
    setCreateTitle("");
    setCreateContent("");
    setCreateOptions("");
    setCreateAnswer("");
    setCreateExplanation("");
    setCreateCourse(subject || "");
    setCreateKpId("");
    setCreateDifficulty("基础");
  };

  const generateQuestions = async () => {
    setGenLoading(true);
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(genCourse, ""),
        course_name: genCourseName || getSubjectLabel(genCourse),
        knowledge_point_id: genKpId ? parseInt(genKpId) : null,
        knowledge_point_title: genKpId
          ? (knowledgePoints.find((kp) => kp.id === parseInt(genKpId)) || {}).title || ""
          : "",
        type: genType,
        difficulty: genDifficulty,
        count: genCount,
      };
      const res = await fetch(`${API_BASE}/practice/questions/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowGenerateModal(false);
        await loadQuestions();
        alert(data.message || "生成成功");
      } else {
        alert(data.detail || "生成失败");
      }
    } catch (e) {
      console.error("Failed to generate questions:", e);
    } finally {
      setGenLoading(false);
    }
  };

  const deleteQuestion = async (q) => {
    if (!window.confirm(`确认删除题目"${q.title}"吗？`)) return;
    try {
      const res = await fetch(
        `${API_BASE}/practice/questions/${q.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        await loadQuestions();
        if (detailQuestion?.id === q.id) setDetailQuestion(null);
      }
    } catch (e) {
      console.error("Failed to delete question:", e);
    }
  };

  const getTypeClass = (type) => {
    if (type === "choice") return "q-type-choice";
    if (type === "short_answer") return "q-type-short";
    return "q-type-prog";
  };

  return (
    <section className="chat-panel chat-panel--wide practice-panel">
      <div className="panel-header panel-header--chat practice-header">
        <div>
          <div className="subject-pill panel-pill">练习中心</div>
          <h2>练习中心</h2>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="primary-button compact"
            onClick={() => {
              resetCreateForm();
              setShowCreateModal(true);
            }}
          >
            新建题目
          </button>
          <button
            className="ghost-button compact"
            onClick={() => {
              setGenCourse(courseFilter || subject || "");
              setGenCourseName("");
              setGenKpId("");
              setGenType("choice");
              setGenDifficulty("基础");
              setGenCount(1);
              setShowGenerateModal(true);
            }}
          >
            AI 生成题目
          </button>
        </div>
      </div>

      <div className="task-center-filters">
        <div className="task-filter-item">
          <label className="field-label">课程筛选</label>
          <select
            className="field"
            value={courseFilter}
            onChange={(e) => { setCourseFilter(e.target.value); setKpFilter(""); }}
          >
            <option value="">全部课程</option>
            {courseOptions.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>
        </div>
        <div className="task-filter-item">
          <label className="field-label">知识点筛选</label>
          <select
            className="field"
            value={kpFilter}
            onChange={(e) => setKpFilter(e.target.value)}
          >
            <option value="">全部知识点</option>
            {knowledgePoints.map((kp) => (
              <option key={kp.id} value={kp.id}>
                {kp.title}
              </option>
            ))}
          </select>
        </div>
        <div className="task-filter-item">
          <label className="field-label">题型筛选</label>
          <select
            className="field"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            {TYPE_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <button className="ghost-button compact" onClick={loadQuestions}>
          刷新
        </button>
      </div>

      {loading ? (
        <div className="empty-state">加载中...</div>
      ) : questions.length === 0 ? (
        <div className="empty-inline practice-empty">
          <p>当前筛选条件下没有题目。</p>
          <button
            className="primary-button compact"
            onClick={() => {
              resetCreateForm();
              setShowCreateModal(true);
            }}
          >
            创建第一道题目
          </button>
        </div>
      ) : (
        <div className="question-list">
          {questions.map((q) => (
            <div key={q.id} className="question-card">
              <div className="question-card-main">
                <div className="question-card-header">
                  <h4 className="question-card-title">{q.title}</h4>
                  <div className="question-card-badges">
                    <span className={`q-type-badge ${getTypeClass(q.type)}`}>
                      {TYPE_LABELS[q.type] || q.type}
                    </span>
                    {q.difficulty && (
                      <span className="subject-pill small">{q.difficulty}</span>
                    )}
                  </div>
                </div>
                <div className="question-card-meta">
                  {q.course_id && (
                    <span className="subject-pill small">
                      {getSubjectLabel(q.course_id)}
                    </span>
                  )}
                  {q.knowledge_point_title && (
                    <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                      {q.knowledge_point_title}
                    </span>
                  )}
                  {q.source && (
                    <span className="subject-pill small" style={{ background: "#ecfdf5", color: "#065f46" }}>
                      {SOURCE_LABELS[q.source] || q.source}
                    </span>
                  )}
                  <span className="history-meta">
                    {formatDate(q.updated_at || q.created_at)}
                  </span>
                </div>
              </div>
              <div className="question-card-actions">
                <button className="tiny-button" onClick={() => openDetail(q)}>
                  查看详情
                </button>
                <button
                  className="tiny-button"
                  onClick={() => deleteQuestion(q)}
                  style={{ color: "#dc2626" }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {detailQuestion && (
        <div className="modal-overlay" onClick={() => setDetailQuestion(null)}>
          <div className="modal-card modal-card--wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{detailQuestion.title}</h3>
              <button className="modal-close" onClick={() => setDetailQuestion(null)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <div className="question-detail-meta">
                <span className={`q-type-badge ${getTypeClass(detailQuestion.type)}`}>
                  {TYPE_LABELS[detailQuestion.type] || detailQuestion.type}
                </span>
                {detailQuestion.difficulty && (
                  <span className="subject-pill small">{detailQuestion.difficulty}</span>
                )}
                {detailQuestion.course_id && (
                  <span className="subject-pill small">
                    {getSubjectLabel(detailQuestion.course_id)}
                  </span>
                )}
                {detailQuestion.knowledge_point_title && (
                  <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                    {detailQuestion.knowledge_point_title}
                  </span>
                )}
              </div>

              <div className="question-detail-content">
                <div className="question-content-text">
                  {detailQuestion.content}
                </div>

                {detailQuestion.type === "choice" && detailQuestion.options && (
                  <div className="question-options">
                    {(detailQuestion.options || "").split("\n").filter(Boolean).map((opt, i) => (
                      <label key={i} className="question-option-label">
                        <input
                          type="radio"
                          name="choice_answer"
                          value={opt.trim().charAt(0)}
                          checked={userAnswer === opt.trim().charAt(0)}
                          onChange={(e) => setUserAnswer(e.target.value)}
                        />
                        <span>{opt.trim()}</span>
                      </label>
                    ))}
                  </div>
                )}

                {detailQuestion.type === "short_answer" && (
                  <textarea
                    className="field"
                    rows={4}
                    placeholder="请输入你的答案..."
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                  />
                )}
              </div>

              {detailQuestion.answer && (
                <div className="question-answer-section">
                  <strong>参考答案：</strong>
                  <p>{detailQuestion.answer}</p>
                </div>
              )}
              {detailQuestion.explanation && (
                <div className="question-answer-section">
                  <strong>解析：</strong>
                  <p>{detailQuestion.explanation}</p>
                </div>
              )}

              <div className="question-detail-actions">
                <button
                  className="primary-button compact"
                  disabled={detailActionLoading || !userAnswer.trim()}
                  onClick={submitAnswer}
                >
                  {detailActionLoading ? "提交中..." : "提交答案"}
                </button>
                <button
                  className="ghost-button compact"
                  disabled={feedbackLoading || !userAnswer.trim()}
                  onClick={requestFeedback}
                >
                  {feedbackLoading ? "AI 分析中..." : "AI 反馈"}
                </button>
              </div>

              {feedback && (
                <div className="ai-feedback-box">
                  <strong>AI 反馈：</strong>
                  <div
                    className="ai-feedback-content"
                    dangerouslySetInnerHTML={{ __html: feedback.replace(/\n/g, "<br>") }}
                  />
                </div>
              )}

              {attempts.length > 0 && (
                <div className="attempts-section">
                  <h4>作答历史</h4>
                  {attempts.map((a) => (
                    <div key={a.id} className="attempt-item">
                      <div className="attempt-meta">
                        <span className={`attempt-result attempt-result--${a.self_result || "unknown"}`}>
                          {RESULT_LABELS[a.self_result] || "未知"}
                        </span>
                        <span className="history-meta">
                          {formatDate(a.created_at)}
                        </span>
                      </div>
                      {a.user_answer && (
                        <div className="attempt-answer">
                          <span className="history-meta">你的答案：</span>
                          {a.user_answer}
                        </div>
                      )}
                      {a.ai_feedback && (
                        <div className="attempt-feedback">
                          <span className="history-meta">AI 反馈：</span>
                          <div
                            className="ai-feedback-content"
                            dangerouslySetInnerHTML={{ __html: a.ai_feedback.replace(/\n/g, "<br>") }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建题目</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <label className="field-label">课程</label>
              <select
                className="field"
                value={createCourse}
                onChange={(e) => setCreateCourse(e.target.value)}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <label className="field-label">知识点（可选）</label>
              <select
                className="field"
                value={createKpId}
                onChange={(e) => setCreateKpId(e.target.value)}
              >
                <option value="">不绑定知识点</option>
                {knowledgePoints.map((kp) => (
                  <option key={kp.id} value={kp.id}>
                    {kp.title}
                  </option>
                ))}
              </select>

              <label className="field-label">题型 *</label>
              <select
                className="field"
                value={createType}
                onChange={(e) => setCreateType(e.target.value)}
              >
                {TYPE_OPTIONS.filter((o) => o.value).map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="field-label">难度</label>
              <select
                className="field"
                value={createDifficulty}
                onChange={(e) => setCreateDifficulty(e.target.value)}
              >
                {DIFFICULTY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="field-label">题目标题 *</label>
              <input
                className="field"
                placeholder="例如：数组排序的时间复杂度"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
              />

              <label className="field-label">题目内容 *</label>
              <textarea
                className="field"
                rows={4}
                placeholder="输入题面内容..."
                value={createContent}
                onChange={(e) => setCreateContent(e.target.value)}
              />

              {createType === "choice" && (
                <>
                  <label className="field-label">选项（每行一个，格式：A. xxx）</label>
                  <textarea
                    className="field"
                    rows={4}
                    placeholder={"A. 选项一\nB. 选项二\nC. 选项三\nD. 选项四"}
                    value={createOptions}
                    onChange={(e) => setCreateOptions(e.target.value)}
                  />
                </>
              )}

              <label className="field-label">参考答案</label>
              <input
                className="field"
                placeholder="选择题填选项字母（A/B/C/D），简答题填参考答案"
                value={createAnswer}
                onChange={(e) => setCreateAnswer(e.target.value)}
              />

              <label className="field-label">解析（可选）</label>
              <textarea
                className="field"
                rows={3}
                placeholder="题目解析..."
                value={createExplanation}
                onChange={(e) => setCreateExplanation(e.target.value)}
              />
            </div>
            <div className="task-form-actions">
              <button
                className="ghost-button compact"
                onClick={() => setShowCreateModal(false)}
              >
                取消
              </button>
              <button
                className="primary-button compact"
                disabled={createSaving || !createTitle.trim() || !createContent.trim()}
                onClick={createQuestion}
              >
                {createSaving ? "创建中..." : "创建题目"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Generate Modal */}
      {showGenerateModal && (
        <div className="modal-overlay" onClick={() => setShowGenerateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>AI 生成题目</h3>
              <button className="modal-close" onClick={() => setShowGenerateModal(false)}>
                &times;
              </button>
            </div>
            <div className="task-modal-body">
              <label className="field-label">课程</label>
              <select
                className="field"
                value={genCourse}
                onChange={(e) => setGenCourse(e.target.value)}
              >
                <option value="">不绑定课程</option>
                {courseOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSubjectLabel(item)}
                  </option>
                ))}
              </select>

              <label className="field-label">知识点（可选）</label>
              <select
                className="field"
                value={genKpId}
                onChange={(e) => setGenKpId(e.target.value)}
              >
                <option value="">不指定知识点</option>
                {knowledgePoints.map((kp) => (
                  <option key={kp.id} value={kp.id}>
                    {kp.title}
                  </option>
                ))}
              </select>

              <label className="field-label">题型</label>
              <select
                className="field"
                value={genType}
                onChange={(e) => setGenType(e.target.value)}
              >
                <option value="choice">选择题</option>
                <option value="short_answer">简答题</option>
              </select>

              <label className="field-label">难度</label>
              <select
                className="field"
                value={genDifficulty}
                onChange={(e) => setGenDifficulty(e.target.value)}
              >
                {DIFFICULTY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="field-label">生成数量（1-5）</label>
              <input
                className="field"
                type="number"
                min={1}
                max={5}
                value={genCount}
                onChange={(e) => setGenCount(Math.min(5, Math.max(1, parseInt(e.target.value) || 1)))}
              />
            </div>
            <div className="task-form-actions">
              <button
                className="ghost-button compact"
                onClick={() => setShowGenerateModal(false)}
              >
                取消
              </button>
              <button
                className="primary-button compact"
                disabled={genLoading}
                onClick={generateQuestions}
              >
                {genLoading ? "生成中..." : "开始生成"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
