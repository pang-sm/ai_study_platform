import { useEffect, useMemo, useState } from "react";
import UnifiedMaterialUploader from "./UnifiedMaterialUploader.jsx";
import "./CourseDashboard.css";

const API_BASE = "/api";

const MASTERY_OPTIONS = ["课堂跟上", "考试通过", "系统掌握", "项目实践", "深入理解"];
const GOAL_OPTIONS = ["期末复习", "查漏补缺", "项目实践", "考研基础", "兴趣拓展"];

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function getParseStatusLabel(status) {
  const map = { success: "已入库", partial: "部分索引", parsing: "解析中", pending: "待关联", failed: "解析失败" };
  return map[status] || "待审核";
}

function getParseStatusTag(status) {
  const map = { success: "cd-status-tag--indexed", partial: "cd-status-tag--indexed", parsing: "cd-status-tag--parsing", pending: "cd-status-tag--pending", failed: "cd-status-tag--failed" };
  return map[status] || "cd-status-tag--pending";
}

function getSourceLabel(source) {
  const map = { manual: "手动上传", ai: "AI 生成", learning_plan: "AI 计划", system: "系统", chat_upload: "对话上传" };
  return map[source] || source || "手动上传";
}

function buildKnowledgeTree(points) {
  const list = Array.isArray(points) ? points : [];
  const roots = list.filter((p) => !p.parent_id && !p.parentId);
  const children = list.filter((p) => p.parent_id || p.parentId);
  return roots.map((root) => ({
    ...root,
    children: children.filter((c) => (c.parent_id || c.parentId) === root.id),
  }));
}

export default function CourseDashboard({
  user,
  course,
  courseOptions,
  dashboard,
  coursePreference,
  onPreferenceChange,
  loading,
  setPage,
  onCourseChange,
  getSubjectLabel,
  materials = [],
  onStartAsk,
  formatDate: propsFormatDate,
  loadMaterials,
  loadDashboard,
}) {
  const stats = dashboard?.stats || {};
  const preference = coursePreference || dashboard?.preference || null;
  const courseLabel = getSubjectLabel ? getSubjectLabel(course) : course;
  const fmtDate = propsFormatDate || formatDate;
  const hasStartedCourse = Boolean(preference?.is_started && preference?.mastery_level && preference?.learning_goal);

  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [kpLoading, setKpLoading] = useState(false);
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [selectedMasteryLevel, setSelectedMasteryLevel] = useState("");
  const [selectedLearningGoal, setSelectedLearningGoal] = useState("");
  const [preferenceSaving, setPreferenceSaving] = useState(false);
  const [preferenceError, setPreferenceError] = useState("");
  const [editingPreference, setEditingPreference] = useState(false);

  useEffect(() => {
    setSelectedMasteryLevel(preference?.mastery_level || "系统掌握");
    setSelectedLearningGoal(preference?.learning_goal || "期末复习");
    setPreferenceError("");
    setEditingPreference(false);
  }, [course, preference?.mastery_level, preference?.learning_goal]);

  useEffect(() => {
    if (!user?.username || !course) {
      setKnowledgePoints([]);
      return;
    }
    setKpLoading(true);
    fetch(`${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((data) => setKnowledgePoints(data.knowledge_points || []))
      .catch(() => setKnowledgePoints([]))
      .finally(() => setKpLoading(false));
  }, [user?.username, course]);

  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    return list.filter((m) => {
      const s = getSubjectLabel ? getSubjectLabel(m.subject) : m.subject;
      return s === courseLabel;
    });
  }, [materials, courseLabel, getSubjectLabel]);

  const knowledgeTree = useMemo(() => buildKnowledgeTree(knowledgePoints), [knowledgePoints]);

  useEffect(() => {
    if (knowledgeTree.length > 0 && expandedIds.size === 0) {
      setExpandedIds(new Set([knowledgeTree[0].id]));
    }
  }, [knowledgeTree, expandedIds.size]);

  const recentMaterials = useMemo(() => (
    [...courseMaterials].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)).slice(0, 6)
  ), [courseMaterials]);

  const totalKpCount = stats.knowledge_points_count ?? knowledgePoints.length;
  const materialsCount = stats.materials_count ?? courseMaterials.length;
  const reviewCount = hasStartedCourse ? (stats.pending_review_count ?? 0) : 0;
  const unlinkedCount = hasStartedCourse ? (stats.unlinked_material_count ?? 0) : 0;
  const pendingMatCount = hasStartedCourse ? (stats.pending_materials_count ?? 0) : 0;
  const weeklyMins = hasStartedCourse ? (stats.weekly_study_minutes ?? 0) : 0;
  const streakDays = hasStartedCourse ? (stats.streak_days ?? 0) : 0;
  const progressPct = hasStartedCourse ? (stats.progress_percent ?? 0) : 0;

  function fmtStudyMinutes(mins) {
    if (!mins || mins <= 0) return "0 分钟";
    if (mins < 60) return `${mins} 分钟`;
    return `${(mins / 60).toFixed(1)}h`;
  }

  function toggleModule(id) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function saveCoursePreference() {
    const masteryLevel = selectedMasteryLevel || "";
    const learningGoal = selectedLearningGoal || "";
    if (!masteryLevel || !learningGoal) {
      setPreferenceError("请选择掌握程度和学习目标。");
      return;
    }

    setPreferenceSaving(true);
    setPreferenceError("");
    try {
      const res = await fetch(`${API_BASE}/course-preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: course,
          mastery_level: masteryLevel,
          learning_goal: learningGoal,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "保存失败");
      onPreferenceChange?.(data.preference);
      setEditingPreference(false);
      await loadDashboard?.();
    } catch (error) {
      setPreferenceError(error.message || "保存失败，请稍后重试。");
    } finally {
      setPreferenceSaving(false);
    }
  }

  function renderHeader() {
    return (
      <div className="cd-header">
        <div className="cd-header-left">
          <span className="cd-header-breadcrumb">课程工作台</span>
          <h1 className="cd-header-course">{courseLabel || "选择课程"}</h1>
          <div className="cd-header-meta-row">
            <p className="cd-header-sub">编程基础课 · 初学者入门</p>
            {hasStartedCourse && (
              <>
                <span className="cd-pref-tag cd-pref-tag--mastery">掌握程度：{preference.mastery_level}</span>
                <span className="cd-pref-tag cd-pref-tag--goal">学习目标：{preference.learning_goal}</span>
                <button className="cd-adjust-link" type="button" onClick={() => setEditingPreference(true)}>
                  可随时调整
                </button>
              </>
            )}
          </div>
        </div>
        <div className="cd-header-right">
          <select className="cd-header-select" value={course} onChange={(e) => onCourseChange(e.target.value)}>
            {courseOptions.map((opt) => (
              <option key={opt} value={opt}>{getSubjectLabel ? getSubjectLabel(opt) : opt}</option>
            ))}
          </select>
          <span className="cd-header-last-study">
            上次学习：{hasStartedCourse ? (fmtDate(stats.last_study_date) || "暂无记录") : "尚未开始"}
          </span>
          <button className="cd-header-settings" type="button" onClick={() => setEditingPreference(true)}>
            ⚙ 课程设置
          </button>
        </div>
      </div>
    );
  }

  function renderPreferenceSelector(compact = false) {
    return (
      <div className={compact ? "cd-pref-editor cd-pref-editor--compact" : "cd-pref-editor"}>
        <div className="cd-pref-section">
          <div className="cd-pref-section-title"><span>1</span>想掌握到什么程度 <b>*</b></div>
          <div className="cd-pill-grid cd-pill-grid--mastery">
            {MASTERY_OPTIONS.map((item) => (
              <button
                key={item}
                type="button"
                className={`cd-option-pill${selectedMasteryLevel === item ? " is-selected" : ""}`}
                onClick={() => setSelectedMasteryLevel(item)}
              >
                <span className="cd-option-dot" />
                {item}
              </button>
            ))}
          </div>
        </div>
        <div className="cd-pref-section">
          <div className="cd-pref-section-title"><span>2</span>学习这门科目的目标 <b>*</b></div>
          <div className="cd-goal-grid">
            {GOAL_OPTIONS.map((item) => (
              <button
                key={item}
                type="button"
                className={`cd-goal-card${selectedLearningGoal === item ? " is-selected" : ""}`}
                onClick={() => setSelectedLearningGoal(item)}
              >
                <span className="cd-goal-icon">{item === "期末复习" ? "🎓" : item === "查漏补缺" ? "🔍" : item === "项目实践" ? "💻" : item === "考研基础" ? "📘" : "☆"}</span>
                <strong>{item}</strong>
                <small>{item === "期末复习" ? "夯实知识，考出好成绩" : item === "查漏补缺" ? "发现弱点，精准提升" : item === "项目实践" ? "学以致用，解决问题" : item === "考研基础" ? "打好基础，备战考研" : "拓展视野，探索更多"}</small>
              </button>
            ))}
          </div>
        </div>
        <div className="cd-pref-note">这些设定会作为本课程的长期背景，被 AI 问答、AI 出题、知识点推荐、学习建议等功能持续使用。</div>
        {preferenceError && <div className="cd-pref-error">{preferenceError}</div>}
        <div className="cd-pref-actions">
          <button className="cd-btn cd-btn--primary cd-btn--lg" type="button" onClick={saveCoursePreference} disabled={preferenceSaving}>
            {preferenceSaving ? "保存中..." : compact ? "保存调整" : "保存并开始学习"}
          </button>
          <button className="cd-btn cd-btn--secondary cd-btn--lg" type="button" onClick={() => compact ? setEditingPreference(false) : null}>
            稍后再说
          </button>
        </div>
      </div>
    );
  }

  function renderStatsOverview() {
    return (
      <div className={`cd-card${!hasStartedCourse ? " cd-card--muted" : ""}`}>
        <div className="cd-card-header"><h3 className="cd-card-title">学习概览</h3></div>
        <div className="cd-stats-grid">
          <div className="cd-stat-item"><span className="cd-stat-val">{progressPct}%</span><span className="cd-stat-lbl">学习进度</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{materialsCount}</span><span className="cd-stat-lbl">上传资料</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{totalKpCount}</span><span className="cd-stat-lbl">知识点总数</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{reviewCount} / {unlinkedCount}</span><span className="cd-stat-lbl">待复习 / 待关联</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{pendingMatCount}</span><span className="cd-stat-lbl">待审核资料</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{fmtStudyMinutes(weeklyMins)}</span><span className="cd-stat-lbl">本周学习</span></div>
          <div className="cd-stat-item"><span className="cd-stat-val">{streakDays} 天</span><span className="cd-stat-lbl">连续天数</span></div>
        </div>
      </div>
    );
  }

  function renderUploadSection() {
    return (
      <div className={`cd-card${!hasStartedCourse ? " cd-card--muted" : ""}`}>
        <div className="cd-card-header">
          <h3 className="cd-card-title">资料上传与知识入库（统一入口）</h3>
          {hasStartedCourse && <span className="cd-card-badge">知识库已同步</span>}
        </div>
        <p className="cd-card-desc">与知识库上传功能完全一致，上传后自动进入知识库并同步课程工作台。</p>
        {hasStartedCourse ? (
          <UnifiedMaterialUploader
            courseId={course}
            courseName={courseLabel}
            source="course_workspace"
            onUploadSuccess={() => {
              loadMaterials?.(course);
              loadDashboard?.();
            }}
            user={user}
            getSubjectLabel={getSubjectLabel}
          />
        ) : (
          <div className="cd-empty cd-empty--initial">完成学习设定后即可上传资料并生成课程知识体系。</div>
        )}
      </div>
    );
  }

  function renderKnowledgeTree() {
    return (
      <div className={`cd-card${!hasStartedCourse ? " cd-card--muted" : ""}`}>
        <div className="cd-card-header">
          <h3 className="cd-card-title">知识体系概览</h3>
          {!kpLoading && <span className="cd-card-subtle">共 {knowledgeTree.length} 个模块，{totalKpCount} 个知识点</span>}
        </div>
        {kpLoading ? (
          <div className="cd-empty">知识点加载中...</div>
        ) : knowledgeTree.length === 0 ? (
          <div className="cd-empty">当前课程还没有知识点数据。</div>
        ) : (
          <div className="cd-kp-tree">
            {knowledgeTree.map((mod, idx) => {
              const isOpen = expandedIds.has(mod.id);
              const childCount = mod.children?.length || 0;
              return (
                <div className="cd-kp-module" key={mod.id}>
                  <button className="cd-kp-module-header" type="button" onClick={() => toggleModule(mod.id)}>
                    <span className={`cd-kp-arrow${isOpen ? " cd-kp-arrow--open" : ""}`}>▶</span>
                    <span className="cd-kp-module-title">{idx + 1}. {mod.title}</span>
                    <span className="cd-kp-module-count">{childCount} 个知识点</span>
                  </button>
                  {isOpen && childCount > 0 && (
                    <div className="cd-kp-children">
                      {mod.children.map((child, cidx) => (
                        <button className="cd-kp-child" key={child.id} type="button" onClick={() => setPage("knowledgeLearning")}>
                          <span className="cd-kp-child-num">{idx + 1}.{cidx + 1}</span>
                          <span className="cd-kp-child-title">{child.title}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  function renderRecentMaterials() {
    if (!hasStartedCourse) return null;
    return (
      <div className="cd-card">
        <div className="cd-card-header">
          <h3 className="cd-card-title">最近上传资料</h3>
          <button className="cd-btn cd-btn--ghost cd-btn--sm" type="button" onClick={() => setPage("workspaceMaterials")}>查看全部 →</button>
        </div>
        {recentMaterials.length === 0 ? (
          <div className="cd-empty">暂无资料，请上传教材、课件或笔记。</div>
        ) : (
          <div className="cd-mat-table">
            <div className="cd-mat-thead"><span>文件名称</span><span>来源</span><span>状态</span><span>上传时间</span></div>
            {recentMaterials.map((mat) => (
              <button className="cd-mat-row" type="button" key={mat.id} onClick={() => setPage("workspaceMaterials")}>
                <span className="cd-mat-name" title={mat.original_filename}>{mat.original_filename || "未命名文件"}</span>
                <span className="cd-mat-source">{getSourceLabel(mat.source || "manual")}</span>
                <span className={`cd-status-tag ${getParseStatusTag(mat.parse_status)}`}>{getParseStatusLabel(mat.parse_status)}</span>
                <span className="cd-mat-date">{fmtDate(mat.created_at)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderInitialState() {
    return (
      <div className="cd-grid">
        <div className="cd-main">
          <div className="cd-start-card">
            <div className="cd-start-left">
              <div className="cd-start-illustration">✓</div>
              <h2>开始这门科目的学习</h2>
              <p>你还没有开始学习这门科目。请先设置学习背景，这些设置将严格影响 AI 问答、AI 出题、学习建议与学习路线。</p>
            </div>
            {renderPreferenceSelector(false)}
          </div>
          {renderStatsOverview()}
          {renderUploadSection()}
          {renderKnowledgeTree()}
        </div>
        <div className="cd-right">
          <div className="cd-card cd-ai-card">
            <h3 className="cd-card-title">✨ AI 助学建议</h3>
            <p className="cd-side-desc">完成学习设定后，AI 将基于你的掌握程度与学习目标，为你提供更精准、更有针对性的帮助。</p>
            <ul className="cd-ai-suggestions">
              <li>AI 问答会根据你的掌握程度调整讲解深度</li>
              <li>AI 出题会根据你的学习目标调整题目方向</li>
              <li>学习建议会优先服务你的当前目标</li>
            </ul>
            <button className="cd-btn cd-btn--primary cd-ai-card-btn" type="button" onClick={saveCoursePreference}>先完成学习设定</button>
          </div>
          <div className="cd-card">
            <h3 className="cd-card-title">🎁 开始后可用</h3>
            <div className="cd-available-list">
              <span>个性化 AI 问答</span>
              <span>目标导向出题</span>
              <span>动态学习路线</span>
              <span>课程数据追踪</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  function renderPreferenceCard() {
    return (
      <div className="cd-card">
        <h3 className="cd-card-title">当前学习设定</h3>
        {editingPreference ? (
          renderPreferenceSelector(true)
        ) : (
          <>
            <div className="cd-current-pref-box">
              <div><span>掌握程度：</span><b>{preference.mastery_level}</b></div>
              <div><span>学习目标：</span><b>{preference.learning_goal}</b></div>
            </div>
            <button className="cd-btn cd-btn--secondary cd-pref-adjust-btn" type="button" onClick={() => setEditingPreference(true)}>调整设定</button>
            <p className="cd-side-desc">这些设定会影响 AI 问答、AI 出题、学习建议与路线推荐。</p>
          </>
        )}
      </div>
    );
  }

  function renderActiveState() {
    return (
      <div className="cd-grid">
        <div className="cd-main">
          {renderStatsOverview()}
          {renderUploadSection()}
          <div className="cd-two-col">
            {renderKnowledgeTree()}
            {renderRecentMaterials()}
          </div>
        </div>
        <div className="cd-right">
          <div className="cd-card cd-ai-card">
            <h3 className="cd-card-title">✨ AI 助学建议</h3>
            <p className="cd-side-desc">你当前以“{preference.mastery_level}”为掌握程度、以“{preference.learning_goal}”为学习目标，AI 会优先提供结构化讲解、重点考点总结和针对性练习。</p>
            <ul className="cd-ai-suggestions">
              <li>优先复习未关联知识点</li>
              <li>适合生成{preference.learning_goal}习题</li>
              <li>建议先学习基础模块</li>
            </ul>
            <button className="cd-btn cd-btn--primary cd-ai-card-btn" type="button" onClick={onStartAsk}>打开 AI 问答</button>
          </div>
          <div className="cd-card">
            <h3 className="cd-card-title">快速操作</h3>
            <div className="cd-quick-grid">
              <button className="cd-quick-card" type="button" onClick={() => setPage("knowledgeLearning")}><span>🗺️</span><b>学习路线</b></button>
              <button className="cd-quick-card" type="button" onClick={() => setPage("knowledgeLearning")}><span>📖</span><b>知识点学习</b></button>
              <button className="cd-quick-card" type="button" onClick={() => setPage("records")}><span>📝</span><b>学习记录</b></button>
              <button className="cd-quick-card" type="button" onClick={() => setPage("reviewCenter")}><span>🔍</span><b>待复习</b></button>
              <button className="cd-quick-card" type="button" onClick={() => setPage("workspaceMaterials")}><span>📁</span><b>资料管理</b></button>
            </div>
          </div>
          {renderPreferenceCard()}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="cd-page"><div className="cd-page-inner">
        <div className="cd-loading"><div className="cd-loading-spinner" /><p>课程工作台加载中...</p></div>
      </div></div>
    );
  }

  return (
    <div className="cd-page">
      <div className="cd-page-inner">
        {renderHeader()}
        {hasStartedCourse ? renderActiveState() : renderInitialState()}
      </div>
    </div>
  );
}
