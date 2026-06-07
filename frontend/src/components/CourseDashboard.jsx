import { useMemo, useState, useEffect } from "react";
import UnifiedMaterialUploader from "./UnifiedMaterialUploader.jsx";
import "./CourseDashboard.css";

const API_BASE = "/api";

function getParseStatusLabel(status) {
  const map = { success: "已入库", partial: "部分索引", parsing: "解析中", pending: "待关联", failed: "解析失败" };
  return map[status] || "待审核";
}
function getParseStatusTag(status) {
  const map = { success: "cd-status-tag--indexed", partial: "cd-status-tag--indexed", parsing: "cd-status-tag--parsing", pending: "cd-status-tag--pending", failed: "cd-status-tag--failed" };
  return map[status] || "cd-status-tag--pending";
}
function formatDate(value) {
  if (!value) return "";
  const d = new Date(value); if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}
function getSourceLabel(source) {
  const map = { manual: "手动上传", ai: "AI 生成", learning_plan: "AI 计划", system: "系统", chat_upload: "对话上传" };
  return map[source] || source || "手动上传";
}

function buildKnowledgeTree(points) {
  const list = Array.isArray(points) ? points : [];
  // Support multiple field name conventions
  const roots = list.filter(p => !p.parent_id && !p.parentId);
  const children = list.filter(p => p.parent_id || p.parentId);
  return roots.map(root => {
    const parentId = root.id;
    return {
      ...root,
      children: children.filter(c => (c.parent_id || c.parentId) === parentId),
    };
  });
}

export default function CourseDashboard({
  user, course, courseOptions, dashboard, loading, setPage,
  onCourseChange, getSubjectLabel, materials = [], goalConfig, setGoalConfig,
  onStartAsk, onOpenCodeStudio, onOpenPracticeCenter,
  formatDate: propsFormatDate, loadMaterials, loadDashboard,
}) {
  const stats = dashboard?.stats || {};
  const courseLabel = getSubjectLabel ? getSubjectLabel(course) : course;
  const fmtDate = propsFormatDate || formatDate;

  // ── Course materials ──
  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => {
      const s = getSubjectLabel ? getSubjectLabel(m.subject) : m.subject;
      return s === courseLabel;
    });
  }, [materials, courseLabel, getSubjectLabel]);

  // ── Knowledge points ──
  const [knowledgePoints, setKnowledgePoints] = useState([]);
  const [kpLoading, setKpLoading] = useState(false);
  useEffect(() => {
    if (!user?.username || !course) { setKnowledgePoints([]); return; }
    setKpLoading(true);
    fetch(`${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`)
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => setKnowledgePoints(data.knowledge_points || []))
      .catch(() => setKnowledgePoints([]))
      .finally(() => setKpLoading(false));
  }, [user?.username, course]);

  const knowledgeTree = useMemo(() => buildKnowledgeTree(knowledgePoints), [knowledgePoints]);

  // ── Collapse state: default expand first module ──
  const [expandedIds, setExpandedIds] = useState(new Set());
  useEffect(() => {
    if (knowledgeTree.length > 0 && expandedIds.size === 0) {
      setExpandedIds(new Set([knowledgeTree[0].id]));
    }
  }, [knowledgeTree]);

  const toggleModule = (id) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // ── Recent materials ──
  const recentMaterials = useMemo(() => {
    return [...courseMaterials]
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .slice(0, 6);
  }, [courseMaterials]);

  // ── Stats (all from real backend /course-dashboard) ──
  const totalKpCount = stats.knowledge_points_count ?? knowledgePoints.length;
  const materialsCount = stats.materials_count ?? courseMaterials.length;
  const reviewCount = stats.pending_review_count ?? 0;
  const unlinkedCount = stats.unlinked_material_count ?? 0;
  const pendingMatCount = stats.pending_materials_count ?? 0;
  const weeklyMins = stats.weekly_study_minutes ?? 0;
  const streakDays = stats.streak_days ?? 0;
  const progressPct = stats.progress_percent ?? 0;

  function fmtStudyMinutes(mins) {
    if (!mins || mins <= 0) return "暂无";
    if (mins < 60) return `${mins} 分钟`;
    return `${(mins / 60).toFixed(1)}h`;
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

        {/* ═══════════════════════════════════════════════
            Header
            ═══════════════════════════════════════════════ */}
        <div className="cd-header">
          <div className="cd-header-left">
            <span className="cd-header-breadcrumb">课程工作台</span>
            <h1 className="cd-header-course">{courseLabel || "选择课程"}</h1>
            <p className="cd-header-sub">编程基础课 · 初学者入门</p>
          </div>
          <div className="cd-header-right">
            <select className="cd-header-select" value={course}
              onChange={(e) => onCourseChange(e.target.value)}>
              {courseOptions.map((opt) => (
                <option key={opt} value={opt}>{getSubjectLabel ? getSubjectLabel(opt) : opt}</option>
              ))}
            </select>
            <span className="cd-header-last-study">
              上次学习：{fmtDate(stats.last_study_date) || "暂无记录"}
            </span>
            <button className="cd-header-settings" type="button"
              onClick={() => alert("课程设置功能开发中")}>
              ⚙ 课程设置
            </button>
          </div>
        </div>

        {/* ═══════════════════════════════════════════════
            Grid: Main + Right
            ═══════════════════════════════════════════════ */}
        <div className="cd-grid">

          {/* ━━━━ MAIN COLUMN ━━━━ */}
          <div className="cd-main">

            {/* ── Stats Overview ── */}
            <div className="cd-card">
              <div className="cd-card-header">
                <h3 className="cd-card-title">学习概览</h3>
              </div>
              <div className="cd-stats-grid">
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">📊</span>
                  <span className="cd-stat-val">
                    <div className="cd-progress-bar-wrap">
                      <div className="cd-progress-bar">
                        <div className="cd-progress-bar-fill" style={{ width: `${Math.min(100, progressPct)}%` }} />
                      </div>
                    </div>
                  </span>
                  <span className="cd-stat-lbl">学习进度 {progressPct}%</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">📚</span>
                  <span className="cd-stat-val">{materialsCount}</span>
                  <span className="cd-stat-lbl">上传资料</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">🧩</span>
                  <span className="cd-stat-val">{totalKpCount}</span>
                  <span className="cd-stat-lbl">知识点总数</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">🔄</span>
                  <span className="cd-stat-val">{reviewCount} / {unlinkedCount}</span>
                  <span className="cd-stat-lbl">待复习 / 待关联</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">{pendingMatCount > 0 ? "⚠️" : "✅"}</span>
                  <span className="cd-stat-val">{pendingMatCount}</span>
                  <span className="cd-stat-lbl">待审核资料</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">⏱️</span>
                  <span className="cd-stat-val">{fmtStudyMinutes(weeklyMins)}</span>
                  <span className="cd-stat-lbl">本周学习</span>
                </div>
                <div className="cd-stat-item">
                  <span className="cd-stat-icon">🔥</span>
                  <span className="cd-stat-val">{streakDays > 0 ? `${streakDays} 天` : "0 天"}</span>
                  <span className="cd-stat-lbl">连续天数</span>
                </div>
              </div>
            </div>

            {/* ── Upload Section ── */}
            <div className="cd-card">
              <div className="cd-card-header">
                <h3 className="cd-card-title">资料上传与知识入库（统一入口）</h3>
                <span className="cd-card-badge">知识库已同步同款上传入口</span>
              </div>
              <p className="cd-card-desc">
                与知识库上传功能完全一致，上传后自动进入知识库并同步课程工作台。
              </p>
              <UnifiedMaterialUploader
                courseId={course} courseName={courseLabel}
                source="course_workspace"
                onUploadSuccess={() => {
                  if (loadMaterials) loadMaterials(course);
                  if (loadDashboard) loadDashboard();
                }}
                user={user} getSubjectLabel={getSubjectLabel}
              />
            </div>

            {/* ── Knowledge Tree ── */}
            <div className="cd-card">
              <div className="cd-card-header">
                <h3 className="cd-card-title">知识体系概览</h3>
                {!kpLoading && <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>共 {knowledgeTree.length} 个模块，{totalKpCount} 个知识点</span>}
              </div>
              {kpLoading ? (
                <div className="cd-empty">知识点加载中...</div>
              ) : knowledgeTree.length === 0 ? (
                <div className="cd-empty">当前课程还没有知识体系，上传资料后可以自动解析生成。</div>
              ) : (
                <div className="cd-kp-tree">
                  {knowledgeTree.map((mod, idx) => {
                    const isOpen = expandedIds.has(mod.id);
                    const childCount = mod.children?.length || 0;
                    return (
                      <div className="cd-kp-module" key={mod.id}>
                        <button className="cd-kp-module-header" type="button"
                          onClick={() => toggleModule(mod.id)}>
                          <span className={`cd-kp-arrow${isOpen ? " cd-kp-arrow--open" : ""}`}>▶</span>
                          <span className="cd-kp-module-icon">📦</span>
                          <span className="cd-kp-module-title">
                            {idx + 1}. {mod.title}
                          </span>
                          <span className="cd-kp-module-count">{childCount} 个知识点</span>
                        </button>
                        {isOpen && childCount > 0 && (
                          <div className="cd-kp-children">
                            {mod.children.map((child, cidx) => (
                              <div className="cd-kp-child" key={child.id}
                                onClick={() => setPage("knowledgeLearning")}
                                title={child.description || ""}>
                                <span className="cd-kp-child-num">{idx + 1}.{cidx + 1}</span>
                                <span className="cd-kp-child-title">{child.title}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {isOpen && childCount === 0 && (
                          <div className="cd-kp-children">
                            <div className="cd-kp-child" style={{ color: "#94a3b8", cursor: "default" }}>
                              <span className="cd-kp-child-num">—</span>
                              <span className="cd-kp-child-title">暂无子知识点</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ── Recent Materials ── */}
            <div className="cd-card">
              <div className="cd-card-header">
                <h3 className="cd-card-title">最近上传资料</h3>
                <button className="cd-btn cd-btn--ghost cd-btn--sm" type="button"
                  onClick={() => setPage("workspaceMaterials")}>查看全部 →</button>
              </div>
              {recentMaterials.length === 0 ? (
                <div className="cd-empty">暂无资料，请上传教材、课件或笔记。</div>
              ) : (
                <div className="cd-mat-table">
                  <div className="cd-mat-thead">
                    <span>文件名称</span><span>来源</span><span>状态</span><span>上传时间</span>
                  </div>
                  {recentMaterials.map((mat) => (
                    <div className="cd-mat-row" key={mat.id}
                      onClick={() => setPage("workspaceMaterials")}>
                      <span className="cd-mat-name" title={mat.original_filename}>
                        {mat.original_filename || "未命名文件"}
                      </span>
                      <span className="cd-mat-source">{getSourceLabel(mat.source || "manual")}</span>
                      <span className={`cd-status-tag ${getParseStatusTag(mat.parse_status)}`}>
                        {getParseStatusLabel(mat.parse_status)}
                      </span>
                      <span className="cd-mat-date">{fmtDate(mat.created_at)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>

          {/* ━━━━ RIGHT COLUMN ━━━━ */}
          <div className="cd-right">

            {/* AI Suggestions */}
            <div className="cd-card cd-ai-card">
              <h3 className="cd-card-title">✨ AI 助学建议</h3>
              <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "#64748b" }}>
                基于你的学习情况为你推荐
              </p>
              <ul className="cd-ai-suggestions">
                {unlinkedCount > 0 && (
                  <li>有 {unlinkedCount} 份资料尚未关联知识点，点击处理。</li>
                )}
                {reviewCount > 0 && (
                  <li>还有 {reviewCount} 项内容待复习，打开复盘中心巩固。</li>
                )}
                {materialsCount > 0 && (
                  <li>基于资料库内容提问，AI 精准回答。</li>
                )}
                {materialsCount === 0 && totalKpCount === 0 && (
                  <li>上传教材、课件或笔记，开始构建知识体系。</li>
                )}
                {totalKpCount === 0 && materialsCount > 0 && (
                  <li>资料已就绪，自动解析后可生成知识点。</li>
                )}
              </ul>
              <button className="cd-btn cd-btn--primary cd-ai-card-btn"
                style={{ marginTop: 14, width: "100%" }} type="button"
                onClick={onStartAsk}>打开 AI 问答</button>
            </div>

            {/* Quick Actions */}
            <div className="cd-card">
              <h3 className="cd-card-title" style={{ marginBottom: 12 }}>快速操作</h3>
              <div className="cd-quick-grid">
                <button className="cd-quick-card" type="button" onClick={() => setPage("knowledgeLearning")}>
                  <span className="cd-quick-card-icon">🗺️</span>
                  <span className="cd-quick-card-label">学习路线</span>
                </button>
                <button className="cd-quick-card" type="button" onClick={() => setPage("knowledgeLearning")}>
                  <span className="cd-quick-card-icon">📖</span>
                  <span className="cd-quick-card-label">知识点学习</span>
                </button>
                <button className="cd-quick-card" type="button" onClick={() => setPage("records")}>
                  <span className="cd-quick-card-icon">📝</span>
                  <span className="cd-quick-card-label">学习记录</span>
                </button>
                <button className="cd-quick-card" type="button" onClick={() => setPage("reviewCenter")}>
                  <span className="cd-quick-card-icon">🔍</span>
                  <span className="cd-quick-card-label">待复习</span>
                </button>
                <button className="cd-quick-card" type="button" onClick={() => setPage("workspaceMaterials")}>
                  <span className="cd-quick-card-icon">📁</span>
                  <span className="cd-quick-card-label">资料管理</span>
                </button>
              </div>
            </div>

            {/* More shortcuts */}
            <div className="cd-card">
              <h3 className="cd-card-title" style={{ marginBottom: 10 }}>更多入口</h3>
              <div className="cd-link-list">
                <button className="cd-link-item" type="button" onClick={() => setPage("taskCenter")}>
                  <span className="cd-link-item-icon">📋</span> 任务中心
                </button>
                <button className="cd-link-item" type="button" onClick={() => setPage("practiceCenter")}>
                  <span className="cd-link-item-icon">✏️</span> 练习中心
                </button>
                <button className="cd-link-item" type="button" onClick={() => setPage("codeStudio")}>
                  <span className="cd-link-item-icon">💻</span> 编程助手
                </button>
                <button className="cd-link-item" type="button" onClick={() => setPage("knowledgeBaseCenter")}>
                  <span className="cd-link-item-icon">🗄️</span> 知识库中心
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
