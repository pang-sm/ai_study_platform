import { useMemo, useEffect, useState } from "react";
import {
  getRouteSource,
  getPlannedRoute,
  deriveKnowledgePointsOverview,
  calculateOverallProgress,
} from "../data/courseKnowledgePlans.js";
import "./KnowledgeLearningPage.css";

const STATUS_CONFIG = {
  mastered: { label: "已掌握", color: "#059669", bg: "#ecfdf5" },
  learning: { label: "学习中", color: "#2563eb", bg: "#eff6ff" },
  review: { label: "待复习", color: "#d97706", bg: "#fffbeb" },
  locked: { label: "未开始", color: "#94a3b8", bg: "#f8fafc" },
  weak: { label: "薄弱", color: "#dc2626", bg: "#fef2f2" },
};

function RouteNodeCard({ node, index, isLast, onClick, isExpanded }) {
  const cfg = STATUS_CONFIG[node.status] || STATUS_CONFIG.locked;
  return (
    <div className="kl-route-node-wrap">
      <div
        className={`kl-route-node${node.status === "learning" ? " kl-route-node--active" : ""}${node.status === "mastered" ? " kl-route-node--done" : ""}${isExpanded ? " kl-route-node--expanded" : ""}`}
        onClick={() => onClick && onClick(node)}
      >
        <span className="kl-route-node-seq">{index + 1}</span>
        <div className="kl-route-node-body">
          <div className="kl-route-node-title">{node.title}</div>
          <div className="kl-route-node-sub">{node.subtitle}</div>
          <div className="kl-route-node-meta">
            <span className="kl-route-node-status" style={{ color: cfg.color, background: cfg.bg }}>
              {cfg.label}
            </span>
            <span className="kl-route-node-kp-count">
              {(node.knowledgePoints || []).length} 个知识点
            </span>
          </div>
        </div>
      </div>
      {!isLast && <div className="kl-route-connector" />}
    </div>
  );
}

function KnowledgePointItem({ kp, onClick, index }) {
  const cfg = STATUS_CONFIG[kp.status] || STATUS_CONFIG.locked;
  return (
    <button
      type="button"
      className="kl-kp-item"
      onClick={() => onClick && onClick(kp)}
    >
      <span className="kl-kp-item-dot" style={{ background: cfg.color }} />
      <span className="kl-kp-item-title">{kp.title}</span>
      <span className="kl-kp-item-tag" style={{ color: cfg.color, background: cfg.bg }}>
        {cfg.label}
      </span>
    </button>
  );
}

export default function KnowledgeLearningPage({
  user,
  course,
  courseOptions,
  getSubjectLabel,
  setPage,
  onNavigateToAI,
  materials = [],
  loadMaterials = () => {},
}) {
  const courseLabel = getSubjectLabel(course);
  const routeSource = useMemo(() => getRouteSource(course, courseLabel), [course, courseLabel]);
  const hasPlannedRoute = routeSource !== "materials";

  // Course-scoped materials
  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => getSubjectLabel(m.subject) === courseLabel);
  }, [materials, courseLabel, getSubjectLabel]);

  // Route source toggle
  const [activeRouteSource, setActiveRouteSource] = useState(() => "materials");

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

  // Platform route nodes
  const platformRouteNodes = useMemo(() => {
    if (!hasPlannedRoute) return [];
    return getPlannedRoute(course);
  }, [hasPlannedRoute, course]);

  // Material route nodes from API knowledge points
  const [apiKnowledgePoints, setApiKnowledgePoints] = useState([]);

  useEffect(() => {
    if (!user?.username || !course) {
      setApiKnowledgePoints([]);
      return;
    }
    setApiKnowledgePoints([]);
    let cancelled = false;
    fetch(`/api/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled && data.knowledge_points) setApiKnowledgePoints(data.knowledge_points);
      })
      .catch(() => {})
      .finally(() => {});
    return () => { cancelled = true; };
  }, [user?.username, course]);

  const materialRouteNodes = useMemo(() => {
    if (apiKnowledgePoints.length > 0) {
      const nodes = [];
      const rootPoints = apiKnowledgePoints.filter((p) => !p.parent_id);
      rootPoints.forEach((root) => {
        const children = apiKnowledgePoints.filter((p) => p.parent_id === root.id);
        const allPoints = [root, ...children];
        const mastered = allPoints.filter((p) => p.status === "mastered").length;
        nodes.push({
          id: `kp-${root.id}`,
          title: root.title,
          subtitle: root.description || "",
          knowledgePoints: children.map((c) => ({
            id: `kp-${c.id}`,
            title: c.title,
            status: c.status || "locked",
            importance: "medium",
          })),
          sourceType: "materials",
          status: nodes.length <= 1 ? "learning" : "locked",
          progress: allPoints.length > 0 ? mastered / allPoints.length : 0,
        });
      });
      if (nodes.length > 0) return nodes;
    }
    return [];
  }, [apiKnowledgePoints]);

  // Convert platform route nodes' knowledge strings to object format
  const normalizedPlatformNodes = useMemo(() => {
    return platformRouteNodes.map((node) => ({
      ...node,
      knowledgePoints: (node.knowledgePoints || []).map((kp, i) => ({
        id: `${node.id}-${i}`,
        title: typeof kp === "string" ? kp : kp.title || kp,
        status: node.status === "mastered" ? "mastered" : node.status === "learning" ? "learning" : "locked",
        importance: i < 3 ? "high" : "medium",
      })),
    }));
  }, [platformRouteNodes]);

  const routeNodes = activeRouteSource === "platform" ? normalizedPlatformNodes : materialRouteNodes;

  const overallProgress = useMemo(() => {
    if (routeNodes.length > 0) return calculateOverallProgress(routeNodes);
    return { percent: 0, masteredPoints: 0, totalPoints: 0, reviewCount: 0 };
  }, [routeNodes]);

  const knowledgeOverview = useMemo(() => {
    if (routeNodes.length > 0) return deriveKnowledgePointsOverview(routeNodes);
    return [];
  }, [routeNodes]);

  // Expanded node
  const [expandedNodeId, setExpandedNodeId] = useState(null);

  // Selected knowledge point (for sidebar detail)
  const [selectedKp, setSelectedKp] = useState(null);

  const handleNodeClick = (node) => {
    setExpandedNodeId((prev) => (prev === node.id ? null : node.id));
    setSelectedKp(null);
  };

  const handleKpClick = (kp) => {
    setSelectedKp(kp);
  };

  const handleStartAIWithKp = () => {
    if (!selectedKp) return;
    const parentNode = routeNodes.find((n) =>
      (n.knowledgePoints || []).some((kp) => kp.id === selectedKp.id)
    );
    if (onNavigateToAI) {
      onNavigateToAI({
        type: "knowledge_point",
        courseId: course,
        courseName: courseLabel,
        routeSource: activeRouteSource,
        nodeId: parentNode?.id || "",
        nodeTitle: parentNode?.title || "",
        knowledgePointId: selectedKp.id,
        knowledgePointTitle: selectedKp.title,
        materialIds: parentNode?.materialIds || [],
        aiPromptContext: `当前学习知识点：${selectedKp.title}，课程：${courseLabel}。`,
      });
    }
  };

  const expandedNode = routeNodes.find((n) => n.id === expandedNodeId);

  return (
    <div className="kl-page">
      {/* ── Page Title ── */}
      <div className="kl-page-title-area">
        <div className="kl-page-title-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <div>
          <h1 className="kl-page-title">知识点学习</h1>
          <p className="kl-page-subtitle">根据学习目标，结合课程资料或平台路线推进学习</p>
        </div>
      </div>

      <div className="kl-layout">
        {/* ── Left main column ── */}
        <div className="kl-main">
          {/* ── Route source toggle ── */}
          <div className="kl-control-bar">
            <div className="kl-route-tabs">
              <button
                className={`kl-route-tab${activeRouteSource === "materials" ? " kl-route-tab--active" : ""}`}
                type="button"
                onClick={() => setActiveRouteSource("materials")}
              >
                我的资料路线
              </button>
              {hasPlannedRoute && (
                <button
                  className={`kl-route-tab${activeRouteSource === "platform" ? " kl-route-tab--active" : ""}`}
                  type="button"
                  onClick={() => setActiveRouteSource("platform")}
                >
                  平台推荐路线
                </button>
              )}
            </div>
            <div className="kl-progress-summary">
              <span className="kl-progress-pct">{overallProgress.percent}%</span>
              <span className="kl-progress-detail">
                {overallProgress.masteredPoints}/{overallProgress.totalPoints} 已掌握
              </span>
            </div>
          </div>

          {/* ── Route nodes ── */}
          {routeNodes.length > 0 ? (
            <div className="kl-route-section">
              <div className="kl-route-track">
                {routeNodes.map((node, i) => (
                  <RouteNodeCard
                    key={node.id}
                    node={node}
                    index={i}
                    isLast={i === routeNodes.length - 1}
                    onClick={handleNodeClick}
                    isExpanded={expandedNodeId === node.id}
                  />
                ))}
              </div>

              {/* ── Expanded node detail ── */}
              {expandedNode && (
                <div className="kl-node-detail">
                  <div className="kl-node-detail-header">
                    <h3 className="kl-node-detail-title">{expandedNode.title}</h3>
                    <span className="kl-node-detail-subtitle">{expandedNode.subtitle}</span>
                  </div>
                  <div className="kl-node-detail-body">
                    <p className="kl-node-detail-desc">{expandedNode.description || ""}</p>
                    <div className="kl-kp-list">
                      {(expandedNode.knowledgePoints || []).map((kp) => (
                        <KnowledgePointItem
                          key={kp.id}
                          kp={kp}
                          index={0}
                          onClick={handleKpClick}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div className="kl-route-footer">
                <span className="kl-route-source-label">
                  {activeRouteSource === "platform" ? "平台预设学习路线" : "基于已上传资料生成"}
                </span>
                {activeRouteSource === "materials" && (
                  <div className="kl-route-actions">
                    <button className="kl-btn kl-btn--primary" type="button" onClick={() => setPage("workspaceMaterials")}>
                      上传资料生成路线
                    </button>
                    {materialRouteNodes.length > 0 && (
                      <button className="kl-btn kl-btn--ghost" type="button" onClick={() => loadMaterials(course)}>
                        重新分析资料
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="kl-empty">
              <div className="kl-empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="18" x2="12" y2="12" />
                  <line x1="9" y1="15" x2="15" y2="15" />
                </svg>
              </div>
              {activeRouteSource === "materials" ? (
                <>
                  <p className="kl-empty-title">当前课程还没有上传资料</p>
                  <p className="kl-empty-hint">
                    你可以上传教材、课件或笔记，让 AI 按你的资料生成个性化学习路线。
                  </p>
                  <div className="kl-empty-actions">
                    <button className="kl-btn kl-btn--primary" type="button" onClick={() => setPage("workspaceMaterials")}>
                      上传资料生成路线
                    </button>
                    {hasPlannedRoute && (
                      <button className="kl-btn kl-btn--ghost" type="button" onClick={() => setActiveRouteSource("platform")}>
                        使用平台推荐路线
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <p className="kl-empty-title">暂无可用的平台推荐路线</p>
                  <p className="kl-empty-hint">请切换到「我的资料路线」上传资料后生成个性化路线。</p>
                  <button className="kl-btn kl-btn--primary" type="button" onClick={() => setActiveRouteSource("materials")}>
                    切换至资料路线
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* ── Right sidebar ── */}
        <aside className="kl-sidebar">
          {/* Selected knowledge point detail */}
          {selectedKp ? (
            <div className="kl-card kl-side-card">
              <div className="kl-side-card-header">
                <h3 className="kl-side-card-title">当前选中知识点</h3>
              </div>
              <div className="kl-kp-detail">
                <p className="kl-kp-detail-name">{selectedKp.title}</p>
                <span className="kl-kp-detail-status" style={{
                  color: (STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.locked).color,
                  background: (STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.locked).bg,
                }}>
                  {(STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.locked).label}
                </span>
                <div className="kl-kp-actions">
                  <button className="kl-btn kl-btn--primary" type="button" onClick={handleStartAIWithKp}>
                    进入 AI 问答学习
                  </button>
                </div>
                <div className="kl-kp-suggestions">
                  <p className="kl-kp-suggestions-label">推荐问题</p>
                  <button className="kl-suggestion-btn" type="button" onClick={handleStartAIWithKp}>
                    给我这个知识点的定义
                  </button>
                  <button className="kl-suggestion-btn" type="button" onClick={handleStartAIWithKp}>
                    用一个简单例子解释
                  </button>
                  <button className="kl-suggestion-btn" type="button" onClick={handleStartAIWithKp}>
                    这个知识点考试怎么考
                  </button>
                  <button className="kl-suggestion-btn" type="button" onClick={handleStartAIWithKp}>
                    给我 3 道练习题
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="kl-card kl-side-card">
              <div className="kl-side-card-header">
                <h3 className="kl-side-card-title">知识点详情</h3>
              </div>
              <div className="kl-side-empty">
                <p>点击路线节点展开知识点</p>
                <p className="kl-side-empty-hint">再点击知识点查看详情和学习建议</p>
              </div>
            </div>
          )}

          {/* Knowledge points overview */}
          <div className="kl-card kl-side-card">
            <div className="kl-side-card-header">
              <h3 className="kl-side-card-title">学习阶段概览</h3>
            </div>
            {knowledgeOverview.length === 0 ? (
              <div className="kl-side-empty">
                <p>暂无知识点数据</p>
                <p className="kl-side-empty-hint">选择路线后生成</p>
              </div>
            ) : (
              <div className="kl-kp-stages">
                {knowledgeOverview.map((stage) => {
                  const cfg = STATUS_CONFIG[stage.status] || STATUS_CONFIG.locked;
                  return (
                    <div key={stage.stageId} className="kl-kp-stage">
                      <div className="kl-kp-stage-header">
                        <span className="kl-kp-stage-dot" style={{ background: cfg.color }} />
                        <span className="kl-kp-stage-title">{stage.stageTitle}</span>
                        <span className="kl-kp-stage-tag" style={{ color: cfg.color, background: cfg.bg }}>
                          {cfg.label}
                        </span>
                      </div>
                      <div className="kl-kp-stage-count">{stage.pointCount} 个知识点</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* AI suggestion */}
          <div className="kl-card kl-side-card kl-ai-card">
            <div className="kl-side-card-header">
              <h3 className="kl-side-card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" style={{ marginRight: 6 }}>
                  <path d="M12 2a10 10 0 1 0 10 10h-10v-10z" />
                </svg>
                AI 建议
              </h3>
            </div>
            <p className="kl-ai-suggestion">
              {activeRouteSource === "materials"
                ? courseMaterials.length === 0
                  ? "还没有上传课程资料。上传教材、课件或笔记后，AI 将自动生成学习路线与知识点结构。"
                  : "根据已上传资料生成的学习路线，保持当前节奏持续学习。"
                : "这是平台预设学习路线，建议从基础开始逐步推进到高级内容。"}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
