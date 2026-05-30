import { useMemo, useEffect, useState } from "react";
import KnowledgeRoadmap from "./KnowledgeRoadmap.jsx";
import {
  getRouteSource,
  getPlannedRoute,
  deriveKnowledgePointsOverview,
  calculateOverallProgress,
} from "../data/courseKnowledgePlans.js";
import "./CourseDashboard.css";

function DonutProgress({ pct, size = 72, strokeWidth = 6 }) {
  const r = (size - strokeWidth) / 2;
  const c = Math.PI * r * 2;
  const offset = c - (Math.min(Math.max(pct, 0), 100) / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="co-donut">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#2563eb"
        strokeWidth={strokeWidth} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        fill="#0f172a" fontSize={size * 0.26} fontWeight="700">
        {pct}%
      </text>
    </svg>
  );
}

const STATUS_CONFIG = {
  mastered: { label: "已掌握", color: "#059669", bg: "#ecfdf5" },
  learning: { label: "学习中", color: "#2563eb", bg: "#eff6ff" },
  review: { label: "待复习", color: "#d97706", bg: "#fffbeb" },
  locked: { label: "未开始", color: "#94a3b8", bg: "#f8fafc" },
};

function RouteNodeCard({ node, index, isLast, onClick }) {
  const cfg = STATUS_CONFIG[node.status] || STATUS_CONFIG.locked;
  return (
    <div className="co-route-node-wrap">
      <div
        className={`co-route-node${node.status === "learning" ? " co-route-node--active" : ""}${node.status === "mastered" ? " co-route-node--done" : ""}`}
        onClick={() => onClick && onClick(node)}
      >
        <span className="co-route-node-seq">{index + 1}</span>
        <div className="co-route-node-body">
          <div className="co-route-node-title">{node.title}</div>
          <div className="co-route-node-sub">{node.subtitle}</div>
          <span className="co-route-node-status" style={{ color: cfg.color, background: cfg.bg }}>
            {cfg.label}
          </span>
        </div>
      </div>
      {!isLast && <div className="co-route-connector" />}
    </div>
  );
}

export default function CourseDashboard({
  user,
  course,
  courseOptions,
  dashboard,
  loading,
  savingPointKey,
  setPage,
  onCourseChange,
  onProgressChange,
  onStartAsk,
  onOpenCodeStudio,
  onOpenPracticeCenter,
  getSubjectLabel,
  formatDate,
  materials = [],
  loadMaterials = () => {},
}) {
  const stats = dashboard?.stats || {};
  const progress = Array.isArray(dashboard?.progress) ? dashboard.progress : [];
  const statusOptions = Array.isArray(dashboard?.progress_status_options)
    ? dashboard.progress_status_options
    : ["未开始", "学习中", "已掌握", "薄弱", "待复习"];

  const courseLabel = getSubjectLabel(course);
  const routeSource = useMemo(() => getRouteSource(course, courseLabel), [course, courseLabel]);
  const hasPlannedRoute = routeSource === "planned";

  // Course-scoped materials filter
  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => getSubjectLabel(m.subject) === courseLabel);
  }, [materials, courseLabel, getSubjectLabel]);

  // Route source toggle: "materials" | "platform"
  const [activeRouteSource, setActiveRouteSource] = useState(() => {
    return "materials"; // initial default, may be adjusted
  });

  // Reset route source when course changes
  useEffect(() => {
    if (courseMaterials.length > 0) {
      setActiveRouteSource("materials");
    } else if (hasPlannedRoute) {
      setActiveRouteSource("platform");
    } else {
      setActiveRouteSource("materials");
    }
  }, [course]);

  // Build progress/status map from API data (course dashboard progress list)
  const progressMap = useMemo(() => {
    const m = {};
    progress.forEach((p) => { m[p.knowledge_point] = p.status; });
    return m;
  }, [progress]);

  // Platform route nodes (always available for C courses from planned route)
  const platformRouteNodes = useMemo(() => {
    if (!hasPlannedRoute) return [];
    return getPlannedRoute(progressMap, progressMap);
  }, [hasPlannedRoute, progressMap]);

  // Material route nodes — derived from API knowledge points for current course
  const [apiKnowledgePoints, setApiKnowledgePoints] = useState([]);
  const [kpLoading, setKpLoading] = useState(false);

  useEffect(() => {
    if (!user?.username || !course) {
      setApiKnowledgePoints([]);
      return;
    }
    setApiKnowledgePoints([]);
    setKpLoading(true);
    let cancelled = false;
    fetch(`/api/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled && data.knowledge_points) setApiKnowledgePoints(data.knowledge_points);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setKpLoading(false); });
    return () => { cancelled = true; };
  }, [user?.username, course]);

  const materialRouteNodes = useMemo(() => {
    if (apiKnowledgePoints.length > 0) {
      const nodes = [];
      const rootPoints = apiKnowledgePoints.filter((p) => !p.parent_id);
      rootPoints.forEach((root, idx) => {
        const children = apiKnowledgePoints.filter((p) => p.parent_id === root.id);
        const allPoints = [root, ...children];
        const mastered = allPoints.filter((p) => p.status === "mastered").length;
        nodes.push({
          id: `kp-${root.id}`,
          title: root.title,
          subtitle: root.description || "",
          knowledgePoints: children.map((c) => c.title),
          sourceType: "materials",
          status: nodes.length <= 1 ? "learning" : "locked",
          progress: allPoints.length > 0 ? mastered / allPoints.length : 0,
        });
      });
      if (nodes.length > 0) return nodes;
    }
    return [];
  }, [apiKnowledgePoints]);

  // Active route nodes based on selected route source
  const routeNodes = activeRouteSource === "platform" ? platformRouteNodes : materialRouteNodes;

  const overallProgress = useMemo(() => {
    if (routeNodes.length > 0) return calculateOverallProgress(routeNodes);
    const pct = stats.progress_percent ?? 0;
    return { percent: pct, masteredPoints: 0, totalPoints: progress.length, reviewCount: stats.pending_review_count ?? 0 };
  }, [routeNodes, stats, progress]);

  const knowledgeOverview = useMemo(() => {
    if (routeNodes.length > 0) return deriveKnowledgePointsOverview(routeNodes);
    return [];
  }, [routeNodes]);

  // AI suggestion — dynamic based on route source and material availability
  const aiSuggestion = useMemo(() => {
    if (activeRouteSource === "materials") {
      if (courseMaterials.length === 0) return "还没有上传课程资料。建议上传PDF、图片或文档后，AI将自动生成学习路线与知识点结构。";
      if (materialRouteNodes.length === 0) return "已上传资料，AI正在分析中。分析完成后将自动生成学习路线与知识点结构。";
      if (overallProgress.reviewCount > 1) return `当前有 ${overallProgress.reviewCount} 个阶段需要复习，建议优先巩固薄弱知识点。`;
      if (materialRouteNodes.some((n) => n.status === "learning")) return "继续完成当前学习中的阶段，按路线逐步推进可以更高效地掌握知识体系。";
      return "根据已上传资料生成的学习路线，保持当前节奏持续学习。";
    }
    // Platform route
    if (overallProgress.reviewCount > 1) return `当前有 ${overallProgress.reviewCount} 个阶段需要复习，建议优先巩固薄弱知识点。`;
    if (platformRouteNodes.some((n) => n.status === "learning")) return "继续完成当前学习中的阶段，按路线逐步推进可以更高效地掌握知识体系。";
    return "这是平台预设学习路线，建议从基础开始逐步推进到高级内容。";
  }, [activeRouteSource, courseMaterials.length, materialRouteNodes, platformRouteNodes, overallProgress.reviewCount]);

  // Top 5 recent materials for sidebar (strictly filtered by current course)
  const recentMaterials = useMemo(() => {
    return courseMaterials.slice(0, 5);
  }, [courseMaterials]);

  const [selectedMaterialId, setSelectedMaterialId] = useState(null);
  const [selectedMaterialDetail, setSelectedMaterialDetail] = useState(null);

  const openMaterialDetail = async (material) => {
    setSelectedMaterialId(material.id);
    setSelectedMaterialDetail(null);
    try {
      const res = await fetch(`/api/materials/${material.id}?username=${encodeURIComponent(user?.username || "")}`);
      const data = await res.json();
      if (res.ok) setSelectedMaterialDetail(data);
    } catch { /* ignore */ }
  };

  const handleNodeClick = (node) => {
    // Could expand to show knowledge points, for now just highlight
  };

  if (loading) {
    return (
      <div className="co-loading">
        <div className="co-loading-spinner" />
        <p>课程概览加载中...</p>
      </div>
    );
  }

  return (
    <div className="co-page">
      {/* ── Page Title ── */}
      <div className="co-page-title-area">
        <div className="co-page-title-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
        </div>
        <div>
          <h1 className="co-page-title">课程概览</h1>
          <p className="co-page-subtitle">基于课程资料自动生成学习路线与知识点结构</p>
        </div>
      </div>

      {/* ── Two-column layout ── */}
      <div className="co-layout">
        {/* ── Left main column ── */}
        <div className="co-main">
          {/* ── Progress card ── */}
          <div className="co-card co-progress-card">
            <div className="co-progress-top">
              <div className="co-progress-donut-col">
                <DonutProgress pct={overallProgress.percent} />
                <span className="co-progress-label">整体进度</span>
              </div>
              <div className="co-progress-right">
                <p className="co-progress-encourage">
                  继续保持！按学习路线推进，可更高效掌握知识体系。
                </p>
                <div className="co-progress-bar-wrap">
                  <div className="co-progress-bar">
                    <div className="co-progress-bar-fill" style={{ width: `${overallProgress.percent}%` }} />
                  </div>
                  <span className="co-progress-bar-pct">{overallProgress.percent}%</span>
                </div>
              </div>
            </div>
            <div className="co-progress-stats">
              <div className="co-progress-stat">
                <span className="co-progress-stat-val">{stats.materials_count ?? courseMaterials.length}</span>
                <span className="co-progress-stat-lbl">已上传资料</span>
              </div>
              <div className="co-progress-stat">
                <span className="co-progress-stat-val">{overallProgress.masteredPoints || overallProgress.totalPoints}</span>
                <span className="co-progress-stat-lbl">已掌握知识点</span>
              </div>
              <div className="co-progress-stat">
                <span className="co-progress-stat-val">{overallProgress.reviewCount}</span>
                <span className="co-progress-stat-lbl">待复习</span>
              </div>
            </div>
          </div>

          {/* ── Learning roadmap card ── */}
          <div className="co-card co-roadmap-card">
            <div className="co-roadmap-header">
              <div>
                <h2 className="co-roadmap-title">学习路线</h2>
                {/* Route source toggle tabs */}
                <div className="co-route-tabs">
                  <button
                    className={`co-route-tab${activeRouteSource === "materials" ? " co-route-tab--active" : ""}`}
                    type="button"
                    onClick={() => setActiveRouteSource("materials")}
                  >
                    我的资料路线
                  </button>
                  {hasPlannedRoute && (
                    <button
                      className={`co-route-tab${activeRouteSource === "platform" ? " co-route-tab--active" : ""}`}
                      type="button"
                      onClick={() => setActiveRouteSource("platform")}
                    >
                      平台推荐路线
                    </button>
                  )}
                </div>
                <p className="co-roadmap-subtitle">
                  {activeRouteSource === "platform"
                    ? "基于C语言课程预设学习路线，从基础语法到高级编程逐步推进"
                    : materialRouteNodes.length > 0
                      ? "根据上传资料自动生成学习路线，并同步绘制知识点路线"
                      : "上传课程资料后，AI将自动生成学习路线与知识点结构"}
                </p>
              </div>
            </div>

            {routeNodes.length > 0 ? (
              <>
                <div className="co-route-track">
                  {routeNodes.map((node, i) => (
                    <RouteNodeCard
                      key={node.id}
                      node={node}
                      index={i}
                      isLast={i === routeNodes.length - 1}
                      onClick={handleNodeClick}
                    />
                  ))}
                </div>
                <div className="co-roadmap-footer">
                  <span className="co-roadmap-source-label">
                    {activeRouteSource === "platform" ? "平台预设学习路线" : "基于已上传资料生成"}
                  </span>
                  {activeRouteSource === "materials" && recentMaterials.length > 0 && (
                    <div className="co-roadmap-materials">
                      {recentMaterials.slice(0, 4).map((m) => (
                        <span key={m.id} className="co-roadmap-chip">{m.original_filename}</span>
                      ))}
                    </div>
                  )}
                  <div className="co-roadmap-actions">
                    {activeRouteSource === "materials" ? (
                      <>
                        <button className="co-btn co-btn--primary" type="button" onClick={() => setPage("workspaceMaterials")}>
                          上传资料生成路线
                        </button>
                        {materialRouteNodes.length > 0 && (
                          <button className="co-btn co-btn--ghost" type="button" onClick={() => loadMaterials(course)}>
                            重新分析资料
                          </button>
                        )}
                      </>
                    ) : (
                      courseMaterials.length === 0 && (
                        <button className="co-btn co-btn--ghost" type="button" onClick={() => { setActiveRouteSource("materials"); setPage("workspaceMaterials"); }}>
                          上传资料自定义路线
                        </button>
                      )
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="co-roadmap-empty">
                <div className="co-roadmap-empty-icon">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="12" y1="18" x2="12" y2="12" />
                    <line x1="9" y1="15" x2="15" y2="15" />
                  </svg>
                </div>
                {activeRouteSource === "materials" ? (
                  <>
                    <p className="co-roadmap-empty-title">还没有可用于生成路线的资料</p>
                    <p className="co-roadmap-empty-hint">上传PDF、图片或文档后，AI将自动生成学习路线与知识点结构。</p>
                    <button className="co-btn co-btn--primary" type="button" onClick={() => setPage("workspaceMaterials")}>
                      上传资料生成路线
                    </button>
                  </>
                ) : (
                  <>
                    <p className="co-roadmap-empty-title">暂无可用的平台推荐路线</p>
                    <p className="co-roadmap-empty-hint">请切换到「我的资料路线」上传资料后生成。</p>
                    <button className="co-btn co-btn--primary" type="button" onClick={() => setActiveRouteSource("materials")}>
                      切换至资料路线
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* ── Knowledge roadmap (from API, collapsed in accordion) ── */}
          <KnowledgeRoadmap user={user} course={course} getSubjectLabel={getSubjectLabel} />
        </div>

        {/* ── Right sidebar ── */}
        <aside className="co-sidebar">
          {/* Uploaded materials */}
          <div className="co-card co-side-card">
            <div className="co-side-card-header">
              <h3 className="co-side-card-title">已上传资料</h3>
              <button className="co-side-card-action" type="button" onClick={() => setPage("workspaceMaterials")}>
                查看全部
              </button>
            </div>
            {recentMaterials.length === 0 ? (
              <div className="co-side-empty">
                <p>暂无资料</p>
                <p className="co-side-empty-hint">上传资料后展示在这里</p>
              </div>
            ) : (
              <div className="co-material-list">
                {recentMaterials.map((m) => (
                  <button
                    key={m.id}
                    className={`co-material-item${selectedMaterialId === m.id ? " co-material-item--open" : ""}`}
                    type="button"
                    onClick={() => openMaterialDetail(m)}
                  >
                    <div className="co-material-item-name">{m.original_filename}</div>
                    <div className="co-material-item-meta">
                      {Number(m.chunk_count || 0) > 0 && <span>{m.chunk_count} 个知识片段</span>}
                    </div>
                    {selectedMaterialId === m.id && selectedMaterialDetail && (
                      <div className="co-material-detail">
                        {selectedMaterialDetail.summary && (
                          <p>{selectedMaterialDetail.summary.slice(0, 200)}</p>
                        )}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Knowledge points overview */}
          <div className="co-card co-side-card">
            <div className="co-side-card-header">
              <h3 className="co-side-card-title">知识点概览</h3>
            </div>
            {knowledgeOverview.length === 0 ? (
              <div className="co-side-empty">
                <p>暂无知识点数据</p>
                <p className="co-side-empty-hint">上传资料或使用预设路线后生成</p>
              </div>
            ) : (
              <div className="co-kp-list">
                {knowledgeOverview.map((stage) => {
                  const cfg = STATUS_CONFIG[stage.status] || STATUS_CONFIG.locked;
                  return (
                    <div key={stage.stageId} className="co-kp-stage">
                      <div className="co-kp-stage-header">
                        <span className="co-kp-stage-dot" style={{ background: cfg.color }} />
                        <span className="co-kp-stage-title">{stage.stageTitle}</span>
                        <span className="co-kp-stage-tag" style={{ color: cfg.color, background: cfg.bg }}>
                          {cfg.label}
                        </span>
                      </div>
                      <div className="co-kp-stage-count">{stage.pointCount} 个知识点</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* AI suggestion */}
          <div className="co-card co-side-card co-ai-card">
            <div className="co-side-card-header">
              <h3 className="co-side-card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" style={{ marginRight: 6 }}>
                  <path d="M12 2a10 10 0 1 0 10 10h-10v-10z" />
                </svg>
                AI 建议
              </h3>
            </div>
            <p className="co-ai-suggestion">{aiSuggestion}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
