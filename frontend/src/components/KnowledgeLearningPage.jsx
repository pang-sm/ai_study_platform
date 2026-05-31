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

function RouteNodeCard({ node, index, isLast, onClick, isExpanded, onKnowledgePointClick }) {
  const cfg = STATUS_CONFIG[node.status] || STATUS_CONFIG.locked;
  return (
    <div className="kl-route-node-wrap">
      <div className="kl-route-node-stack">
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
        {isExpanded && (
          <div className="kl-node-inline-detail">
            {node.description && <p className="kl-node-inline-desc">{node.description}</p>}
            <div className="kl-kp-list">
              {(node.knowledgePoints || []).map((kp, kpIndex) => (
                <KnowledgePointItem
                  key={kp.id}
                  kp={kp}
                  index={kpIndex}
                  onClick={onKnowledgePointClick}
                />
              ))}
            </div>
          </div>
        )}
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

function isMaterialUsableForPath(material) {
  const status = String(material?.parse_status || "").toLowerCase();
  return ["success", "partial", "indexed"].includes(status) && Number(material?.chunk_count || 0) > 0;
}

function formatDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("zh-CN");
}

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function getParseStatusLabel(status) {
  if (status === "success" || status === "indexed") return "已索引";
  if (status === "partial") return "部分索引";
  if (status === "parsing") return "解析中";
  if (status === "pending") return "等待解析";
  if (status === "failed") return "解析失败";
  return "未索引";
}

function MaterialPathModal({
  open,
  materials,
  loading,
  generating,
  selectedIds,
  searchQuery,
  error,
  onSearchChange,
  onToggle,
  onSelectAll,
  onClear,
  onCancel,
  onGenerate,
}) {
  if (!open) return null;
  const filtered = searchQuery.trim()
    ? materials.filter((m) => String(m.original_filename || "").toLowerCase().includes(searchQuery.trim().toLowerCase()))
    : materials;
  const usableMaterials = filtered.filter(isMaterialUsableForPath);
  const usableSelectedCount = selectedIds.filter((id) => materials.some((m) => m.id === id && isMaterialUsableForPath(m))).length;

  return (
    <div className="kl-modal-overlay">
      <div className="kl-material-modal" role="dialog" aria-modal="true">
        <div className="kl-modal-header">
          <div>
            <h2 className="kl-modal-title">选择资料生成学习路线</h2>
            <p className="kl-modal-subtitle">请选择当前科目下已上传的资料，AI 将根据资料中的知识片段生成学习路线。</p>
          </div>
          <button className="kl-modal-close" type="button" onClick={onCancel} disabled={generating}>×</button>
        </div>

        <div className="kl-modal-toolbar">
          <input
            className="kl-modal-search"
            value={searchQuery}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="搜索资料文件名"
            disabled={generating}
          />
          <div className="kl-modal-tools">
            <button type="button" className="kl-link-btn" onClick={() => onSelectAll(usableMaterials)} disabled={generating || usableMaterials.length === 0}>全选可用</button>
            <button type="button" className="kl-link-btn" onClick={onClear} disabled={generating || selectedIds.length === 0}>清空选择</button>
          </div>
        </div>

        <div className="kl-material-list">
          {loading ? (
            <div className="kl-modal-empty">正在加载资料...</div>
          ) : materials.length === 0 ? (
            <div className="kl-modal-empty">当前科目暂无资料，请先去资料库上传并索引。</div>
          ) : usableMaterials.length === 0 && filtered.length > 0 ? (
            <div className="kl-modal-empty">当前资料还没有知识片段，请先在资料库点击 AI 索引。</div>
          ) : filtered.length === 0 ? (
            <div className="kl-modal-empty">没有匹配的资料。</div>
          ) : (
            filtered.map((material) => {
              const usable = isMaterialUsableForPath(material);
              const selected = selectedIds.includes(material.id);
              return (
                <label key={material.id} className={`kl-material-row${selected ? " kl-material-row--selected" : ""}${!usable ? " kl-material-row--disabled" : ""}`}>
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={!usable || generating}
                    onChange={() => onToggle(material)}
                  />
                  <div className="kl-material-row-main">
                    <div className="kl-material-name">{material.original_filename}</div>
                    <div className="kl-material-meta">
                      <span>{String(material.file_type || "").toUpperCase() || "文件"}</span>
                      <span>{formatFileSize(material.file_size)}</span>
                      <span>{formatDate(material.created_at)}</span>
                      <span>{getParseStatusLabel(material.parse_status)}</span>
                      <span>{Number(material.chunk_count || 0)} 个知识片段</span>
                    </div>
                    {!usable && (
                      <div className="kl-material-disabled-reason">暂无知识片段，请先前往资料库点击 AI 索引</div>
                    )}
                  </div>
                </label>
              );
            })
          )}
        </div>

        {error && <div className="kl-modal-error">{error}</div>}
        {generating && <div className="kl-modal-generating">AI 正在分析资料并生成路线...</div>}

        <div className="kl-modal-footer">
          <span className="kl-modal-count">已选择 {usableSelectedCount} 个可用资料</span>
          <div className="kl-modal-actions">
            <button className="kl-btn kl-btn--ghost" type="button" onClick={onCancel} disabled={generating}>取消</button>
            <button className="kl-btn kl-btn--ghost" type="button" onClick={onClear} disabled={generating || selectedIds.length === 0}>重新选择</button>
            <button className="kl-btn kl-btn--primary" type="button" onClick={onGenerate} disabled={generating || usableSelectedCount === 0}>
              {generating ? "生成中..." : "生成学习路线"}
            </button>
          </div>
        </div>
      </div>
    </div>
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
  materialsLoading = false,
  loadMaterials = () => {},
  goalConfig = null,
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
  const [materialPathModalOpen, setMaterialPathModalOpen] = useState(false);
  const [materialPathSearch, setMaterialPathSearch] = useState("");
  const [selectedPathMaterialIds, setSelectedPathMaterialIds] = useState([]);
  const [pathGenerating, setPathGenerating] = useState(false);
  const [pathError, setPathError] = useState("");
  const [pathNotice, setPathNotice] = useState("");
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);

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

  const fetchKnowledgePoints = async () => {
    if (!user?.username || !course) {
      setApiKnowledgePoints([]);
      return;
    }
    setKnowledgeLoading(true);
    try {
      const res = await fetch(`/api/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "加载知识点失败");
      setApiKnowledgePoints(data.knowledge_points || []);
    } catch {
      setApiKnowledgePoints([]);
    } finally {
      setKnowledgeLoading(false);
    }
  };

  useEffect(() => {
    fetchKnowledgePoints();
  }, [user?.username, course]);

  useEffect(() => {
    if (user?.username && course) loadMaterials(course);
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
      const config = goalConfig || {};
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
        goal: config.goal || "systematic",
        difficulty: config.difficulty || "standard",
        depth: config.depth || "standard",
        dailyTime: config.dailyTime || 30,
        examMode: config.goal === "exam",
        examDays: config.examDays || "",
        examCustomDate: config.examCustomDate || "",
        examPaperUploaded: config.examPaperUploaded || false,
        aiPromptContext: `当前学习知识点：${selectedKp.title}，课程：${courseLabel}。`,
      });
    }
  };

  const openMaterialPathModal = () => {
    setPathError("");
    setPathNotice("");
    setMaterialPathSearch("");
    setSelectedPathMaterialIds([]);
    setMaterialPathModalOpen(true);
    loadMaterials(course);
  };

  const togglePathMaterial = (material) => {
    if (!isMaterialUsableForPath(material)) return;
    setSelectedPathMaterialIds((prev) =>
      prev.includes(material.id) ? prev.filter((id) => id !== material.id) : [...prev, material.id]
    );
  };

  const selectAllPathMaterials = (items) => {
    setSelectedPathMaterialIds(items.filter(isMaterialUsableForPath).map((item) => item.id));
  };

  const generateMaterialPath = async () => {
    const usableIds = selectedPathMaterialIds.filter((id) =>
      courseMaterials.some((material) => material.id === id && isMaterialUsableForPath(material))
    );
    if (usableIds.length === 0) {
      setPathError("请至少选择 1 个已生成知识片段的资料。");
      return;
    }
    setPathGenerating(true);
    setPathError("");
    try {
      const res = await fetch("/api/knowledge-path/generate-from-materials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          subject: course,
          material_ids: usableIds,
          overwrite: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "生成学习路线失败");
      await fetchKnowledgePoints();
      setActiveRouteSource("materials");
      setMaterialPathModalOpen(false);
      setSelectedPathMaterialIds([]);
      setPathNotice("已根据所选资料生成学习路线");
    } catch (error) {
      setPathError(error.message || "生成学习路线失败，请稍后重试。");
    } finally {
      setPathGenerating(false);
    }
  };

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
          {pathNotice && <div className="kl-route-notice">{pathNotice}</div>}
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
                    onKnowledgePointClick={handleKpClick}
                  />
                ))}
              </div>

              <div className="kl-route-footer">
                <span className="kl-route-source-label">
                  {activeRouteSource === "platform" ? "平台预设学习路线" : "基于已上传资料生成"}
                </span>
                {activeRouteSource === "materials" && (
                  <div className="kl-route-actions">
                    <button className="kl-btn kl-btn--primary" type="button" onClick={openMaterialPathModal}>
                      {materialRouteNodes.length > 0 ? "重新选择资料生成路线" : "选择已上传资料来生成路线"}
                    </button>
                    {materialRouteNodes.length > 0 && (
                      <button className="kl-btn kl-btn--ghost" type="button" onClick={() => loadMaterials(course)}>
                        刷新资料
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
                  <p className="kl-empty-title">当前课程还没有基于资料生成的学习路线</p>
                  <p className="kl-empty-hint">
                    你可以选择资料库中已上传并完成索引的资料，AI 会根据资料内容生成适合当前课程的学习路线。
                  </p>
                  <div className="kl-empty-actions">
                    <button className="kl-btn kl-btn--primary" type="button" onClick={openMaterialPathModal}>
                      选择已上传资料来生成路线
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
      <MaterialPathModal
        open={materialPathModalOpen}
        materials={courseMaterials}
        loading={materialsLoading}
        generating={pathGenerating}
        selectedIds={selectedPathMaterialIds}
        searchQuery={materialPathSearch}
        error={pathError}
        onSearchChange={setMaterialPathSearch}
        onToggle={togglePathMaterial}
        onSelectAll={selectAllPathMaterials}
        onClear={() => setSelectedPathMaterialIds([])}
        onCancel={() => !pathGenerating && setMaterialPathModalOpen(false)}
        onGenerate={generateMaterialPath}
      />
    </div>
  );
}
