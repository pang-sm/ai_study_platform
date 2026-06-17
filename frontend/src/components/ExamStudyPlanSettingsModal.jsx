import { useState } from "react";
import { getExamSubjectConfig } from "./ExamSubjectDashboard.jsx";

export default function ExamStudyPlanSettingsModal({
  user,
  subjectKey,
  currentSettings,
  onSaved,
  onClose,
}) {
  const config = getExamSubjectConfig(subjectKey);
  const username = user?.username || "";

  const [learningGoal, setLearningGoal] = useState(
    currentSettings?.learning_goal || `${config.title} 系统复习`
  );
  const [startDate, setStartDate] = useState(
    currentSettings?.start_date || ""
  );
  const [dailyHours, setDailyHours] = useState(
    currentSettings?.daily_hours || "2小时"
  );
  const [weeklyDays, setWeeklyDays] = useState(
    currentSettings?.weekly_days || 5
  );
  const [reviewStrategy, setReviewStrategy] = useState(
    currentSettings?.review_strategy || "sequential"
  );
  const [showCompleted, setShowCompleted] = useState(
    currentSettings?.show_completed !== false
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!learningGoal.trim()) {
      setError("请输入学习目标");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/settings`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            subject_key: subjectKey,
            learning_goal: learningGoal.trim(),
            start_date: startDate,
            daily_hours: dailyHours,
            weekly_days: weeklyDays,
            review_strategy: reviewStrategy,
            show_completed: showCompleted,
          }),
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.success) {
        onSaved?.();
      }
    } catch (e) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const REVIEW_STRATEGIES = [
    { value: "sequential", label: "顺序推进", desc: "按知识体系顺序逐章学习" },
    { value: "priority", label: "重点优先", desc: "优先攻克高频考点和重点章节" },
    { value: "weakness", label: "薄弱点优先", desc: "优先复习掌握度低的知识点" },
  ];

  return (
    <div className="esp-modal-overlay" onClick={onClose}>
      <div className="esp-modal" onClick={(e) => e.stopPropagation()}>
        <div className="esp-modal-header">
          <h2>✏️ 编辑学习目标 — {config.title}</h2>
          <button type="button" className="esp-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="esp-modal-body">
          {error && <div className="esp-modal-error">{error}</div>}

          <div className="esp-form-group">
            <label>当前学习目标</label>
            <input
              type="text"
              value={learningGoal}
              onChange={(e) => setLearningGoal(e.target.value)}
              placeholder={`例如：第1章 ${config.tags?.[0] || ""} 的系统复习`}
            />
          </div>

          <div className="esp-form-row">
            <div className="esp-form-group">
              <label>计划开始日期</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="esp-form-group">
              <label>每日学习时长</label>
              <select
                value={dailyHours}
                onChange={(e) => setDailyHours(e.target.value)}
              >
                <option value="30分钟">30分钟</option>
                <option value="1小时">1小时</option>
                <option value="1.5小时">1.5小时</option>
                <option value="2小时">2小时</option>
                <option value="3小时">3小时</option>
                <option value="4小时">4小时</option>
                <option value="5小时+">5小时+</option>
              </select>
            </div>
          </div>

          <div className="esp-form-row">
            <div className="esp-form-group">
              <label>每周学习天数</label>
              <select
                value={weeklyDays}
                onChange={(e) => setWeeklyDays(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                  <option key={d} value={d}>
                    {d} 天
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="esp-form-group">
            <label>复习策略</label>
            <div className="esp-strategy-list">
              {REVIEW_STRATEGIES.map((s) => (
                <label
                  key={s.value}
                  className={`esp-strategy-option${reviewStrategy === s.value ? " selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="review_strategy"
                    value={s.value}
                    checked={reviewStrategy === s.value}
                    onChange={() => setReviewStrategy(s.value)}
                  />
                  <div>
                    <strong>{s.label}</strong>
                    <p>{s.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="esp-form-group">
            <label className="esp-checkbox-label">
              <input
                type="checkbox"
                checked={showCompleted}
                onChange={(e) => setShowCompleted(e.target.checked)}
              />
              <span>显示已完成知识点</span>
            </label>
          </div>
        </div>

        <div className="esp-modal-footer">
          <button
            type="button"
            className="esp-modal-cancel"
            onClick={onClose}
            disabled={saving}
          >
            取消
          </button>
          <button
            type="button"
            className="esp-modal-save"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
