import { useEffect, useState, useCallback } from "react";
import ExamStudyPlanSettingsModal from "./ExamStudyPlanSettingsModal.jsx";
import { getExamSubjectConfig, getExamCourseId } from "./ExamSubjectDashboard.jsx";

const SUBJECT_KEYS = {
  data_structure: "data_structure",
  computer_organization: "computer_organization",
  operating_system: "operating_system",
  computer_network: "computer_network",
};

function getSubjectName(subjectKey) {
  const config = getExamSubjectConfig(subjectKey);
  return config?.title || subjectKey;
}

export default function ExamStudyPlan({ user, subjectKey, onNavigate }) {
  const config = getExamSubjectConfig(subjectKey);
  const username = user?.username || "";

  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState({});
  const [savingCode, setSavingCode] = useState(null);

  const fetchPlan = useCallback(async () => {
    if (!username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan?username=${encodeURIComponent(username)}`
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setPlanData(data);
    } catch (e) {
      setError(e.message || "加载学习计划失败");
    } finally {
      setLoading(false);
    }
  }, [username, subjectKey]);

  useEffect(() => {
    fetchPlan();
  }, [fetchPlan]);

  const toggleSection = (sectionCode) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionCode]: !prev[sectionCode],
    }));
  };

  const updateKnowledgeItem = async (itemCode, itemTitle, newStatus) => {
    setSavingCode(itemCode);
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/knowledge-items/${encodeURIComponent(itemCode)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            subject_key: subjectKey,
            course_id: `${subjectKey}_11408`,
            knowledge_point_code: itemCode,
            knowledge_point_title: itemTitle,
            status: newStatus,
          }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Refresh plan data
      await fetchPlan();
    } catch (e) {
      console.error("Failed to update knowledge item:", e);
    } finally {
      setSavingCode(null);
    }
  };

  const toggleChapterPractice = async (sectionCode, sectionTitle, currentCompleted) => {
    setSavingCode(`cp:${sectionCode}`);
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/chapter-practice/${encodeURIComponent(sectionCode)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            subject_key: subjectKey,
            section_code: sectionCode,
            section_title: sectionTitle,
            completed: !currentCompleted,
          }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchPlan();
    } catch (e) {
      console.error("Failed to update chapter practice:", e);
    } finally {
      setSavingCode(null);
    }
  };

  const handleSettingsSaved = () => {
    setSettingsOpen(false);
    fetchPlan();
  };

  if (loading) {
    return (
      <div className="esp-loading">
        <div className="esp-loading-spinner" />
        <p>加载学习计划中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="esp-error">
        <p>⚠️ {error}</p>
        <button type="button" onClick={fetchPlan}>重试</button>
      </div>
    );
  }

  const stats = planData?.stats || {};
  const settings = planData?.settings || {};
  const chapters = planData?.chapters || [];

  return (
    <div className="exam-study-plan">
      {/* Header */}
      <header className="exam-subject-header">
        <div>
          <div className="exam-subject-title-row">
            <span className="exam-subject-logo">{config.icon}</span>
            <div>
              <h1>{config.title}</h1>
              <p>学习计划 / 知识点推进看板</p>
            </div>
          </div>
        </div>
      </header>

      {/* Top stats card */}
      <section className="esp-stats-card">
        <div className="esp-stats-grid">
          <div className="esp-stat-item">
            <span className="esp-stat-label">当前学习目标</span>
            <strong className="esp-stat-value">
              {settings.learning_goal || `${config.title} 系统复习`}
            </strong>
          </div>
          <div className="esp-stat-item">
            <span className="esp-stat-label">计划开始日期</span>
            <strong className="esp-stat-value">
              {settings.start_date || "未设置"}
            </strong>
          </div>
          <div className="esp-stat-item">
            <span className="esp-stat-label">每日学习时长</span>
            <strong className="esp-stat-value">
              {settings.daily_hours || "未设置"}
            </strong>
          </div>
          <div className="esp-stat-item">
            <span className="esp-stat-label">知识点任务数</span>
            <strong className="esp-stat-value">
              {stats.total_knowledge_points || 0} 个
            </strong>
          </div>
          <div className="esp-stat-item">
            <span className="esp-stat-label">完成进度</span>
            <strong className="esp-stat-value esp-stat-accent">
              {stats.overall_progress || 0}%
            </strong>
          </div>
        </div>
        <div className="esp-stats-bar-wrap">
          <div className="esp-stats-bar" style={{ width: `${stats.overall_progress || 0}%` }} />
        </div>
        <button
          type="button"
          className="esp-edit-goal-btn"
          onClick={() => setSettingsOpen(true)}
        >
          编辑目标
        </button>
      </section>

      {/* Section progress summary */}
      <section className="esp-summary-row">
        <div className="esp-summary-chip">
          <span>二级知识点</span>
          <strong>{stats.total_sections || 0}</strong>
        </div>
        <div className="esp-summary-chip done">
          <span>已完成</span>
          <strong>{stats.sections_completed || 0}</strong>
        </div>
        <div className="esp-summary-chip learning">
          <span>学习中</span>
          <strong>{stats.sections_learning || 0}</strong>
        </div>
        <div className="esp-summary-chip pending">
          <span>未开始</span>
          <strong>{stats.sections_not_started || 0}</strong>
        </div>
      </section>

      {/* Main content: Chapters (一级知识点) */}
      <section className="esp-chapters">
        {chapters.length === 0 ? (
          <div className="esp-empty">
            <p>该学科知识脉络数据尚未加载。</p>
            <button type="button" onClick={() => onNavigate?.("knowledge")}>
              前往知识脉络
            </button>
          </div>
        ) : (
          chapters.map((chapter) => (
            <ChapterCard
              key={chapter.code || chapter.title}
              chapter={chapter}
              expandedSections={expandedSections}
              onToggleSection={toggleSection}
              onUpdateKnowledgeItem={updateKnowledgeItem}
              onToggleChapterPractice={toggleChapterPractice}
              savingCode={savingCode}
              showCompleted={settings.show_completed !== false}
            />
          ))
        )}
      </section>

      {/* Settings Modal */}
      {settingsOpen && (
        <ExamStudyPlanSettingsModal
          user={user}
          subjectKey={subjectKey}
          currentSettings={settings}
          onSaved={handleSettingsSaved}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}

function ChapterCard({
  chapter,
  expandedSections,
  onToggleSection,
  onUpdateKnowledgeItem,
  onToggleChapterPractice,
  savingCode,
  showCompleted,
}) {
  const chapterCode = chapter.code || chapter.title;
  const sections = chapter.children || [];
  const isChapterDone = chapter.chapter_status === "completed";
  const chapterProgress = chapter.chapter_completion_rate || 0;

  return (
    <div className={`esp-chapter-card${isChapterDone ? " completed" : ""}`}>
      <div className="esp-chapter-header">
        <div className="esp-chapter-title-row">
          <span className="esp-chapter-code">
            {chapter.code ? `第${chapter.code}章` : ""}
          </span>
          <h3>{chapter.title}</h3>
          <span className={`esp-chapter-badge ${chapter.chapter_status}`}>
            {chapter.chapter_status === "completed"
              ? "已完成"
              : chapter.chapter_status === "learning"
              ? "学习中"
              : "未开始"}
          </span>
        </div>
        <div className="esp-chapter-meta">
          <span>
            二级知识点 {chapter.sections_completed || 0}/{chapter.section_count || 0} 完成
          </span>
          <div className="esp-chapter-bar-wrap">
            <div
              className="esp-chapter-bar"
              style={{ width: `${chapterProgress}%` }}
            />
          </div>
          <span>{chapterProgress}%</span>
        </div>
      </div>

      <div className="esp-sections">
        {sections.map((section) => {
          const sectionCode = section.code || section.title;
          const sectionStatus = section.section_status || "not_started";
          const leafStats = section.leaf_stats || {};
          const cpDone = section.chapter_practice_completed;
          const isExpanded = expandedSections[sectionCode] || false;
          const sectionProgress = section.completion_rate || 0;

          if (!showCompleted && sectionStatus === "completed") return null;

          return (
            <div
              key={sectionCode}
              className={`esp-section-card ${sectionStatus}`}
            >
              <div className="esp-section-header">
                <button
                  type="button"
                  className="esp-section-expand"
                  onClick={() => onToggleSection(sectionCode)}
                >
                  <span className={`esp-expand-arrow${isExpanded ? " open" : ""}`}>
                    ▶
                  </span>
                </button>
                <div className="esp-section-info">
                  <div className="esp-section-title-row">
                    <strong>{section.title}</strong>
                    <span className={`esp-section-status-tag ${sectionStatus}`}>
                      {sectionStatus === "completed"
                        ? "已完成"
                        : sectionStatus === "learning"
                        ? "学习中"
                        : "未开始"}
                    </span>
                  </div>
                  <div className="esp-section-meta">
                    <span>
                      小知识点 {leafStats.mastered || 0}/{leafStats.total || 0}
                    </span>
                    <span className="esp-section-cp">
                      章节练习：{cpDone ? "✅ 已完成" : "⬜ 未完成"}
                    </span>
                  </div>
                  <div className="esp-section-bar-wrap">
                    <div
                      className="esp-section-bar"
                      style={{ width: `${sectionProgress}%` }}
                    />
                  </div>
                </div>
                <div className="esp-section-actions">
                  <button
                    type="button"
                    className={`esp-cp-btn${cpDone ? " done" : ""}`}
                    disabled={savingCode === `cp:${sectionCode}`}
                    onClick={() =>
                      onToggleChapterPractice(sectionCode, section.title, cpDone)
                    }
                  >
                    {savingCode === `cp:${sectionCode}`
                      ? "保存中..."
                      : cpDone
                      ? "练习已完成 ✓"
                      : "标记练习完成"}
                  </button>
                </div>
              </div>

              {isExpanded && (
                <div className="esp-section-children">
                  {(section.children || []).map((child) => (
                    <SubSection
                      key={child.code || child.id || child.title}
                      node={child}
                      onUpdate={onUpdateKnowledgeItem}
                      savingCode={savingCode}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SubSection({ node, onUpdate, savingCode }) {
  const children = node.children || [];
  const isLeaf = children.length === 0;
  const status = node.status || "not_started";

  if (isLeaf) {
    return (
      <div className={`esp-leaf-item ${status}`}>
        <div className="esp-leaf-info">
          <span className="esp-leaf-dot" />
          <span className="esp-leaf-title">{node.title}</span>
          <span className={`esp-leaf-status ${status}`}>
            {status === "mastered"
              ? "已掌握"
              : status === "learning"
              ? "学习中"
              : "未开始"}
          </span>
        </div>
        <div className="esp-leaf-actions">
          <button
            type="button"
            className={`esp-leaf-btn${status === "not_started" ? " active" : ""}`}
            disabled={savingCode === node.code || status === "not_started"}
            onClick={() => onUpdate(node.code, node.title, "not_started")}
          >
            未开始
          </button>
          <button
            type="button"
            className={`esp-leaf-btn learning${status === "learning" ? " active" : ""}`}
            disabled={savingCode === node.code || status === "learning"}
            onClick={() => onUpdate(node.code, node.title, "learning")}
          >
            学习中
          </button>
          <button
            type="button"
            className={`esp-leaf-btn mastered${status === "mastered" ? " active" : ""}`}
            disabled={savingCode === node.code || status === "mastered"}
            onClick={() => onUpdate(node.code, node.title, "mastered")}
          >
            {savingCode === node.code ? "..." : "已掌握 ✓"}
          </button>
        </div>
      </div>
    );
  }

  // Intermediate node with children
  return (
    <div className="esp-sub-section">
      <div className="esp-sub-section-header">
        <span className="esp-sub-section-title">{node.title}</span>
        <span className={`esp-sub-section-status ${node.status || "not_started"}`}>
          {node.status === "mastered"
            ? "已掌握"
            : node.status === "learning"
            ? "学习中"
            : "未开始"}
        </span>
      </div>
      <div className="esp-sub-section-children">
        {children.map((c) => (
          <SubSection
            key={c.code || c.id || c.title}
            node={c}
            onUpdate={onUpdate}
            savingCode={savingCode}
          />
        ))}
      </div>
    </div>
  );
}
