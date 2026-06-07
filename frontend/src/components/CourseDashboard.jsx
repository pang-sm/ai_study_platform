import { useMemo, useState, useEffect } from "react";
import UnifiedMaterialUploader from "./UnifiedMaterialUploader.jsx";
import "./CourseDashboard.css";

const API_BASE = "/api";

const PAGE_LABELS = {
  dashboard: "课程工作台",
  knowledgeLearning: "知识点学习",
  workspaceMaterials: "资料管理",
  chat: "AI 问答",
  records: "学习记录",
  reviewCenter: "复盘中心",
  taskCenter: "任务中心",
  practiceCenter: "练习中心",
  codeStudio: "编程助手",
  knowledgeBaseCenter: "知识库中心",
};

function getParseStatusLabel(status) {
  const map = {
    success: "已入库", partial: "部分索引", parsing: "解析中",
    pending: "待关联", failed: "解析失败",
  };
  return map[status] || "待审核";
}

function getParseStatusClass(status) {
  const map = { success: "cd-status-indexed", partial: "cd-status-indexed", parsing: "cd-status-parsing", pending: "cd-status-pending", failed: "cd-status-failed" };
  return map[status] || "cd-status-pending";
}

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function getSourceLabel(source) {
  const map = { manual: "手动上传", ai: "AI 生成", learning_plan: "AI 计划", system: "系统", chat_upload: "对话上传" };
  return map[source] || source || "手动上传";
}

export default function CourseDashboard({
  user,
  course,
  courseOptions,
  dashboard,
  loading,
  setPage,
  onCourseChange,
  getSubjectLabel,
  materials = [],
  goalConfig,
  setGoalConfig,
  onStartAsk,
  onOpenCodeStudio,
  onOpenPracticeCenter,
  formatDate: propsFormatDate,
  loadMaterials,
  searchNavigate,
  onClearSearchNavigate,
}) {
  const stats = dashboard?.stats || {};
  const courseLabel = getSubjectLabel ? getSubjectLabel(course) : course;
  const fmtDate = propsFormatDate || formatDate;

  // Course-scoped materials
  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => {
      const matSubject = getSubjectLabel ? getSubjectLabel(m.subject) : m.subject;
      return matSubject === courseLabel;
    });
  }, [materials, courseLabel, getSubjectLabel]);

  // Knowledge points for this course
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

  // Knowledge tree — group by parent_id
  const knowledgeTree = useMemo(() => {
    const points = Array.isArray(knowledgePoints) ? knowledgePoints : [];
    const roots = points.filter(p => !p.parent_id);
    const children = points.filter(p => p.parent_id);
    return roots.map(root => ({
      ...root,
      children: children.filter(c => c.parent_id === root.id),
    }));
  }, [knowledgePoints]);

  // Count total knowledge points (modules + children)
  const totalKpCount = knowledgePoints.length;
  const moduleCount = knowledgeTree.length;

  // Recent materials (last 6)
  const recentMaterials = useMemo(() => {
    return [...courseMaterials]
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .slice(0, 6);
  }, [courseMaterials]);

  // Stats calculations
  const pendingCount = courseMaterials.filter(m => !m.parse_status || m.parse_status === "pending" || m.parse_status === "unknown").length;
  const reviewCount = stats.pending_review_count ?? 0;
  const weeklyHours = stats.weekly_study_minutes ? Math.round(stats.weekly_study_minutes / 60) : null;
  const streakDays = stats.streak_days ?? 0;

  if (loading) {
    return (
      <div className="co-loading">
        <div className="co-loading-spinner" />
        <p>课程工作台加载中...</p>
      </div>
    );
  }

  return (
    <div className="cd-page">
      {/* ── Header bar ── */}
      <div className="cd-header-bar">
        <div className="cd-header-left">
          <div>
            <span className="cd-breadcrumb">← 课程工作台</span>
            <h1 className="cd-header-course">{courseLabel || "选择课程"}</h1>
            <p className="cd-header-course-sub">编程基础课 · 初学者入门</p>
          </div>
        </div>
        <div className="cd-header-right">
          <select
            className="field cd-header-course-select"
            value={course}
            onChange={(e) => onCourseChange(e.target.value)}
          >
            {courseOptions.map((opt) => (
              <option key={opt} value={opt}>{getSubjectLabel ? getSubjectLabel(opt) : opt}</option>
            ))}
          </select>
          <span className="cd-header-last-study">上次学习：{fmtDate(stats.last_study_date) || "暂无记录"}</span>
          <button className="cu-btn cu-btn--ghost cu-btn--sm" type="button" onClick={() => setGoalConfig && setGoalConfig({})}>
            课程设置
          </button>
        </div>
      </div>

      <div className="cd-layout">
        {/* ── Main area ── */}
        <div className="cd-main">
          {/* Learning overview stats */}
          <div className="cd-stats-grid">
            <div className="cd-stat-card">
              <span className="cd-stat-icon">📊</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{stats.progress_percent ?? 0}%</span>
                <span className="cd-stat-label">学习进度</span>
              </div>
            </div>
            <div className="cd-stat-card">
              <span className="cd-stat-icon">📚</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{courseMaterials.length}</span>
                <span className="cd-stat-label">上传资料</span>
              </div>
            </div>
            <div className="cd-stat-card">
              <span className="cd-stat-icon">🧩</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{totalKpCount}</span>
                <span className="cd-stat-label">知识点总数</span>
              </div>
            </div>
            <div className="cd-stat-card">
              <span className="cd-stat-icon">🔄</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{reviewCount || pendingCount}</span>
                <span className="cd-stat-label">待复习 / 待关联</span>
              </div>
            </div>
            <div className="cd-stat-card">
              <span className="cd-stat-icon">⏱️</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{weeklyHours != null ? `${weeklyHours}h` : "—"}</span>
                <span className="cd-stat-label">本周学习时长</span>
              </div>
            </div>
            <div className="cd-stat-card">
              <span className="cd-stat-icon">🔥</span>
              <div className="cd-stat-body">
                <span className="cd-stat-value">{streakDays || "—"}</span>
                <span className="cd-stat-label">连续学习天数</span>
              </div>
            </div>
          </div>

          {/* ── Unified Upload Section ── */}
          <div className="cd-section">
            <div className="cd-section-header">
              <h3 className="cd-section-title">资料上传与知识入库（统一入口）</h3>
              <span className="cd-section-badge">知识库已同步同款上传入口</span>
            </div>
            <p className="cd-section-desc">
              与知识库上传功能完全一致，上传后自动进入知识库并同步课程工作台。
            </p>
            <UnifiedMaterialUploader
              courseId={course}
              courseName={courseLabel}
              source="course_workspace"
              onUploadSuccess={(count) => { if (loadMaterials) loadMaterials(course); }}
              user={user}
              getSubjectLabel={getSubjectLabel}
            />
          </div>

          {/* ── Quick Actions ── */}
          <div className="cd-section">
            <h3 className="cd-section-title" style={{ marginBottom: 14 }}>快速操作</h3>
            <div className="cd-quick-actions">
              <button className="cd-quick-action" type="button" onClick={() => setPage("knowledgeLearning")}>
                <span className="cd-quick-action-icon">🗺️</span> 学习路线
              </button>
              <button className="cd-quick-action" type="button" onClick={onStartAsk}>
                <span className="cd-quick-action-icon">💬</span> AI 问答
              </button>
              <button className="cd-quick-action" type="button" onClick={() => setPage("knowledgeLearning")}>
                <span className="cd-quick-action-icon">📖</span> 知识点学习
              </button>
              <button className="cd-quick-action" type="button" onClick={() => setPage("records")}>
                <span className="cd-quick-action-icon">📝</span> 学习记录
              </button>
              <button className="cd-quick-action" type="button" onClick={() => setPage("reviewCenter")}>
                <span className="cd-quick-action-icon">🔍</span> 待复习
              </button>
              <button className="cd-quick-action" type="button" onClick={() => setPage("workspaceMaterials")}>
                <span className="cd-quick-action-icon">📁</span> 资料管理
              </button>
            </div>
          </div>

          {/* ── Knowledge Overview ── */}
          <div className="cd-section">
            <h3 className="cd-section-title" style={{ marginBottom: 14 }}>知识体系概览</h3>
            {kpLoading ? (
              <p style={{ color: "#94a3b8", fontSize: "0.84rem" }}>知识点加载中...</p>
            ) : knowledgeTree.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "0.84rem" }}>
                当前课程还没有知识体系，上传资料后可以自动解析生成知识点。
              </p>
            ) : (
              <div className="cd-knowledge-tree">
                {knowledgeTree.map((mod) => (
                  <div className="cd-kp-module" key={mod.id}>
                    <div className="cd-kp-module-header">
                      <span>📦</span> {mod.title}
                      <span className="cd-kp-module-count">{mod.children?.length || 0} 个知识点</span>
                    </div>
                    {mod.children?.length > 0 && (
                      <div className="cd-kp-children">
                        {mod.children.map((child) => (
                          <div className="cd-kp-child" key={child.id}
                            onClick={() => setPage("knowledgeLearning")}
                            title={child.description || child.title}
                          >
                            <span className="cd-kp-child-dot" />
                            {child.title}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Recent Materials ── */}
          <div className="cd-section">
            <div className="cd-section-header">
              <h3 className="cd-section-title">最近上传资料</h3>
              <button className="cu-btn cu-btn--ghost cu-btn--sm" type="button"
                onClick={() => setPage("workspaceMaterials")}>
                查看全部 →
              </button>
            </div>
            {recentMaterials.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "0.84rem" }}>暂无资料，请上传教材、课件或笔记。</p>
            ) : (
              <div className="cd-materials-table">
                <div className="cd-materials-table-header">
                  <span>文件名称</span><span>来源</span><span>状态</span><span>上传时间</span>
                </div>
                {recentMaterials.map((mat) => (
                  <div className="cd-materials-row" key={mat.id}
                    onClick={() => {
                      setPage("workspaceMaterials");
                      // Could pass material ID to highlight
                    }}
                  >
                    <span className="cd-materials-name" title={mat.original_filename}>
                      {mat.original_filename || "未命名文件"}
                    </span>
                    <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                      {getSourceLabel(mat.source || "manual")}
                    </span>
                    <span className={`cd-status-badge ${getParseStatusClass(mat.parse_status)}`}>
                      {getParseStatusLabel(mat.parse_status)}
                    </span>
                    <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{fmtDate(mat.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Bottom CTA ── */}
          <div className="cd-bottom-cta">
            <button className="cu-btn cu-btn--primary cu-btn--lg" type="button"
              onClick={() => setPage("knowledgeLearning")}>
              进入知识点学习
            </button>
            <button className="cu-btn cu-btn--primary cu-btn--lg" type="button"
              onClick={onStartAsk}>
              打开 AI 问答
            </button>
            <button className="cu-btn cu-btn--secondary cu-btn--lg" type="button"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
              上传资料
            </button>
          </div>
        </div>

        {/* ── Right Sidebar ── */}
        <aside className="cd-sidebar">
          {/* AI Suggestions */}
          <div className="cd-section cd-ai-card">
            <h4>💡 AI 学习建议</h4>
            <ul className="cd-ai-suggestions">
              {pendingCount > 0 && (
                <li>有 {pendingCount} 份资料尚未关联知识点，建议处理。</li>
              )}
              {reviewCount > 0 && (
                <li>还有 {reviewCount} 项内容待复习，打开复盘中心巩固。</li>
              )}
              {courseMaterials.length > 0 && (
                <li>可以打开 AI 问答，基于资料库中的内容提问。</li>
              )}
              {totalKpCount === 0 && (
                <li>上传课程资料后，AI 会自动提取知识点结构。</li>
              )}
              {courseMaterials.length === 0 && totalKpCount === 0 && (
                <li>上传教材、课件或笔记，开始构建知识体系。</li>
              )}
            </ul>
            <button className="cu-btn cu-btn--primary" type="button" onClick={onStartAsk}
              style={{ marginTop: 10, width: "100%" }}>
              打开 AI 问答
            </button>
          </div>

          {/* Quick Links */}
          <div className="cd-section">
            <h4 style={{ margin: "0 0 10px", fontSize: "0.92rem", fontWeight: 700, color: "#0f172a" }}>快捷入口</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <button className="cu-btn cu-btn--ghost" type="button" onClick={() => setPage("taskCenter")}
                style={{ justifyContent: "flex-start" }}>📋 任务中心</button>
              <button className="cu-btn cu-btn--ghost" type="button" onClick={() => setPage("practiceCenter")}
                style={{ justifyContent: "flex-start" }}>✏️ 练习中心</button>
              <button className="cu-btn cu-btn--ghost" type="button" onClick={() => setPage("codeStudio")}
                style={{ justifyContent: "flex-start" }}>💻 编程助手</button>
              <button className="cu-btn cu-btn--ghost" type="button" onClick={() => setPage("knowledgeBaseCenter")}
                style={{ justifyContent: "flex-start" }}>🗄️ 知识库中心</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
