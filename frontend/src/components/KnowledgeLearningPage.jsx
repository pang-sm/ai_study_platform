import { useMemo, useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
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
  not_started: { label: "未开始", color: "#94a3b8", bg: "#f8fafc" },
};

const ALL_STATUS_OPTIONS = [
  { value: "not_started", label: "未开始" },
  { value: "learning", label: "学习中" },
  { value: "mastered", label: "已掌握" },
];

const STATUS_MASTERY_SCORE = {
  mastered: 100,
  learning: 40,
  not_started: 0,
};

function buildRouteNodeKey({ routeType, course, routeId, stageIndex, childIndex, type }) {
  const safe = (value) =>
    String(value || "")
      .trim()
      .replace(/\s+/g, "-")
      .replace(/[:：/\\?#&]/g, "-");

  const stageNo = Number(stageIndex) + 1;
  const childNo = Number(childIndex) + 1;

  const routePart =
    routeType === "platform"
      ? `platform:${safe(course)}`
      : `material_route:${safe(course)}:${safe(routeId || "default")}`;

  if (type === "stage") {
    return `${routePart}:stage:${stageNo}`;
  }
  return `${routePart}:stage:${stageNo}:child:${childNo}`;
}

function getStatusConfig(status) {
  return STATUS_CONFIG[normalizeKnowledgeStatus(status)] || STATUS_CONFIG.not_started;
}

function normalizeKnowledgeStatus(status) {
  if (!status) return "not_started";
  const s = String(status).trim();
  // Direct 3-state values
  if (s === "not_started" || s === "未开始") return "not_started";
  if (s === "learning" || s === "学习中") return "learning";
  if (s === "mastered" || s === "已掌握") return "mastered";
  // Legacy → learning (need_review, not_understood, and variants)
  if (s === "need_review" || s === "需要复习" || s === "待复习" ||
      s === "review" || s === "reviewing" || s === "needs_review" ||
      s === "not_understood" || s === "还没理解" || s === "薄弱" ||
      s === "weak" || s === "confused" ||
      s === "in_progress" || s === "studying") return "learning";
  // Legacy → mastered
  if (s === "done" || s === "completed") return "mastered";
  // Legacy → not_started
  if (s === "later" || s === "稍后再学" || s === "postponed") return "not_started";
  // Unknown → not_started
  return "not_started";
}

function computeParentStatusFromChildren(children) {
  if (!children || children.length === 0) return "not_started";
  const statuses = children.map((c) => normalizeKnowledgeStatus(c.status || "not_started"));
  if (statuses.every((s) => s === "mastered")) return "mastered";
  if (statuses.some((s) => s === "learning" || s === "mastered")) return "learning";
  return "not_started";
}

function KnowledgeStatusControl({ value, onChange, disabled = false }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0, openUp: false });
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const normalized = normalizeKnowledgeStatus(value);
  const cfg = getStatusConfig(normalized);

  const openMenu = () => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const estimatedMenuHeight = 220;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < estimatedMenuHeight && rect.top > estimatedMenuHeight;
    setMenuPos({
      top: openUp ? rect.top - 4 : rect.bottom + 4,
      left: Math.min(rect.left, window.innerWidth - 170),
      openUp,
    });
    setMenuOpen(true);
  };

  const closeMenu = () => setMenuOpen(false);

  // Close on scroll and resize so the menu never gets detached
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [menuOpen]);

  // Click outside to close
  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  const handleSelect = (statusValue, event) => {
    event.preventDefault();
    event.stopPropagation();
    closeMenu();
    if (statusValue === normalized) return;
    onChange?.(statusValue, event);
  };

  if (disabled) {
    return (
      <span
        className="kl-status-badge kl-status-badge--saving"
        style={{ color: cfg.color, background: cfg.bg }}
      >
        {cfg.label}
        <span className="kl-status-saving-dot" />
      </span>
    );
  }

  const menu = menuOpen && createPortal(
    <div
      className="kl-status-menu kl-status-menu--portal"
      ref={menuRef}
      style={{
        position: "fixed",
        top: `${menuPos.top}px`,
        left: `${menuPos.left}px`,
        transform: menuPos.openUp ? "translateY(-100%)" : "none",
        zIndex: 9999,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {ALL_STATUS_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`kl-status-menu-item${opt.value === normalized ? " kl-status-menu-item--active" : ""}`}
          style={{
            color: (STATUS_CONFIG[opt.value] || STATUS_CONFIG.not_started).color,
          }}
          onMouseDown={(e) => handleSelect(opt.value, e)}
        >
          <span
            className="kl-status-menu-dot"
            style={{ background: (STATUS_CONFIG[opt.value] || STATUS_CONFIG.not_started).color }}
          />
          {opt.label}
          {opt.value === normalized && (
            <svg className="kl-status-menu-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </button>
      ))}
    </div>,
    document.body
  );

  return (
    <div className="kl-status-control">
      <button
        ref={buttonRef}
        type="button"
        className="kl-status-badge"
        style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.color }}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); menuOpen ? closeMenu() : openMenu(); }}
      >
        {cfg.label}
        <svg className="kl-status-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {menu}
    </div>
  );
}

function RouteNodeCard({ node, index, isLast, onClick, isExpanded, onKnowledgePointClick, onStatusChange, statusSavingId }) {
  const cfg = getStatusConfig(node.status);
  const children = node.knowledgePoints || [];
  const masteredChildren = children.filter((c) => normalizeKnowledgeStatus(c.status) === "mastered").length;
  const totalChildren = children.length;
  const progressPct = totalChildren > 0 ? Math.round((masteredChildren / totalChildren) * 100) : (node.status === "mastered" ? 100 : 0);
  const parentDisabled = statusSavingId != null && (statusSavingId === node.nodeKey || statusSavingId === node.backendId || statusSavingId === node.id);

  return (
    <div className={`kl-rnc-card${isExpanded ? " kl-rnc-card--expanded" : ""}${node.status === "mastered" ? " kl-rnc-card--mastered" : ""}${node.status === "learning" ? " kl-rnc-card--active" : ""}`}>
      <div className="kl-rnc-main" onClick={() => onClick && onClick(node)}>
        <div className="kl-rnc-left">
          <span className={`kl-rnc-seq${node.status === "mastered" ? " kl-rnc-seq--done" : ""}${node.status === "learning" ? " kl-rnc-seq--active" : ""}`}>
            {node.status === "mastered" ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              index + 1
            )}
          </span>
        </div>
        <div className="kl-rnc-body">
          <div className="kl-rnc-title-row">
            <h3 className="kl-rnc-title">{node.title}</h3>
            <KnowledgeStatusControl
              value={node.status}
              disabled={parentDisabled}
              onChange={(nextStatus, event) => onStatusChange?.(node, nextStatus, event)}
            />
          </div>
          {node.subtitle && <p className="kl-rnc-sub">{node.subtitle}</p>}
          <div className="kl-rnc-meta">
            <div className="kl-rnc-progress-track">
              <div
                className="kl-rnc-progress-fill"
                style={{
                  width: `${progressPct}%`,
                  background: cfg.color,
                }}
              />
            </div>
            <span className="kl-rnc-progress-text">
              {masteredChildren}/{totalChildren} 个知识点已掌握
            </span>
            <span className="kl-rnc-expand-hint">
              {isExpanded ? "点击收起" : "点击展开知识点"}
            </span>
          </div>
        </div>
        <svg
          className={`kl-rnc-chevron${isExpanded ? " kl-rnc-chevron--open" : ""}`}
          width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {isExpanded && totalChildren > 0 && (
        <div className="kl-rnc-children">
          <div className="kl-rnc-children-list">
            {children.map((kp, kpIndex) => (
              <KnowledgePointItem
                key={kp.id}
                kp={kp}
                index={kpIndex}
                onClick={onKnowledgePointClick}
                onStatusChange={onStatusChange}
                statusSavingId={statusSavingId}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KnowledgePointItem({ kp, onClick, index, onStatusChange, statusSavingId }) {
  const cfg = getStatusConfig(kp.status);
  const childDisabled = statusSavingId != null && (statusSavingId === kp.nodeKey || statusSavingId === kp.backendId || statusSavingId === kp.id);
  const normalizedStatus = normalizeKnowledgeStatus(kp.status);

  return (
    <div
      className={`kl-kp-card${normalizedStatus === "mastered" ? " kl-kp-card--mastered" : ""}${normalizedStatus === "learning" ? " kl-kp-card--learning" : ""}`}
      onClick={() => onClick && onClick(kp)}
    >
      <div className="kl-kp-card-top">
        <span className="kl-kp-card-index">{index + 1}</span>
        <span className="kl-kp-card-title">{kp.title}</span>
      </div>
      <div className="kl-kp-card-bottom">
        <KnowledgeStatusControl
          value={kp.status}
          disabled={childDisabled}
          onChange={(nextStatus, event) => onStatusChange?.(kp, nextStatus, event)}
        />
        <span className="kl-kp-card-dot" style={{ background: cfg.color }} />
      </div>
    </div>
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

  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => getSubjectLabel(m.subject) === courseLabel);
  }, [materials, courseLabel, getSubjectLabel]);

  const [activeRouteSource, setActiveRouteSource] = useState(() => "materials");
  const [materialPathModalOpen, setMaterialPathModalOpen] = useState(false);
  const [materialPathSearch, setMaterialPathSearch] = useState("");
  const [selectedPathMaterialIds, setSelectedPathMaterialIds] = useState([]);
  const [pathGenerating, setPathGenerating] = useState(false);
  const [pathError, setPathError] = useState("");
  const [pathNotice, setPathNotice] = useState("");
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [statusSavingId, setStatusSavingId] = useState(null);
  const [statusError, setStatusError] = useState("");

  useEffect(() => {
    if (courseMaterials.length > 0) {
      setActiveRouteSource("materials");
    } else if (hasPlannedRoute) {
      setActiveRouteSource("platform");
    } else {
      setActiveRouteSource("materials");
    }
  }, [course]);

  const platformRouteNodes = useMemo(() => {
    if (!hasPlannedRoute) return [];
    return getPlannedRoute(course);
  }, [hasPlannedRoute, course]);

  const [apiKnowledgePoints, setApiKnowledgePoints] = useState([]);
  const [localStatusByNodeKey, setLocalStatusByNodeKey] = useState({});

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
    setLocalStatusByNodeKey({});
  }, [user?.username, course]);

  useEffect(() => {
    if (user?.username && course) loadMaterials(course);
  }, [user?.username, course]);

  const backendPointByNodeKey = useMemo(() => {
    const map = new Map();
    apiKnowledgePoints.forEach((point) => {
      if (point.node_key) map.set(point.node_key, point);
    });
    return map;
  }, [apiKnowledgePoints]);

  const pointIdByNodeKey = useMemo(() => {
    const map = new Map();
    apiKnowledgePoints.forEach((point) => {
      if (point.node_key) map.set(point.node_key, point.id);
    });
    return map;
  }, [apiKnowledgePoints]);

  const getStatusByNodeKey = (nodeKey) => {
    const backendPoint = backendPointByNodeKey.get(nodeKey);
    return normalizeKnowledgeStatus(
      localStatusByNodeKey[nodeKey] ||
      backendPoint?.progress?.status ||
      backendPoint?.status ||
      "not_started"
    );
  };

  const materialRouteNodes = useMemo(() => {
    if (apiKnowledgePoints.length > 0) {
      const nodes = [];
      const rootPoints = apiKnowledgePoints.filter((p) => !p.parent_id);
      rootPoints.forEach((root, stageIndex) => {
        const rootNodeKey = root.node_key || buildRouteNodeKey({
          routeType: "material",
          course,
          routeId: "default",
          stageIndex,
          type: "stage",
        });
        const children = apiKnowledgePoints.filter((p) => p.parent_id === root.id);
        const childList = children.map((c, childIndex) => {
          const childNodeKey = c.node_key || buildRouteNodeKey({
            routeType: "material",
            course,
            routeId: "default",
            stageIndex,
            childIndex,
            title: c.title,
            parentTitle: root.title,
            type: "child",
          });
          const resolvedStatus = getStatusByNodeKey(childNodeKey);
          return {
            id: `kp-${c.id}`,
            backendId: c.id,
            pointId: c.id,
            title: c.title,
            status: resolvedStatus,
            importance: "medium",
            parentBackendId: root.id,
            nodeKey: childNodeKey,
            parentNodeKey: rootNodeKey,
            type: "child",
            stageIndex,
            childIndex,
          };
        });
        const mastered = childList.filter((c) => c.status === "mastered").length;
        const rootOwnStatus = getStatusByNodeKey(rootNodeKey);
        const computedStatus = rootOwnStatus !== "not_started" ? rootOwnStatus : computeParentStatusFromChildren(childList);
        nodes.push({
          id: `kp-${root.id}`,
          backendId: root.id,
          pointId: root.id,
          title: root.title,
          subtitle: root.description || "",
          knowledgePoints: childList,
          sourceType: "materials",
          status: computedStatus,
          progress: childList.length > 0 ? mastered / childList.length : 0,
          nodeKey: rootNodeKey,
          type: "stage",
          stageIndex,
        });
      });
      if (nodes.length > 0) return nodes;
    }
    return [];
  }, [apiKnowledgePoints, course, localStatusByNodeKey, backendPointByNodeKey]);

  const normalizedPlatformNodes = useMemo(() => {
    return platformRouteNodes.map((node, stageIndex) => {
      // Stage nodeKey — deterministic, never uses title lookup
      const stageNodeKey = buildRouteNodeKey({
        routeType: "platform",
        course,
        stageIndex,
        title: node.title,
        type: "stage",
      });
      const stageApiPoint = backendPointByNodeKey.get(stageNodeKey);
      const parentBackendId = pointIdByNodeKey.get(stageNodeKey) || stageApiPoint?.id || null;

      const childPoints = (node.knowledgePoints || []).map((kp, childIndex) => {
        const kpTitle = typeof kp === "string" ? kp : kp.title || kp;

        // Child nodeKey — deterministic, includes parent path
        const childNodeKey = buildRouteNodeKey({
          routeType: "platform",
          course,
          stageIndex,
          childIndex,
          title: kpTitle,
          parentTitle: node.title,
          type: "child",
        });

        // ONLY lookup by nodeKey — no title fallback
        const apiChild = backendPointByNodeKey.get(childNodeKey);
        const resolvedStatus = getStatusByNodeKey(childNodeKey);

        console.debug("[node-key:render-match]", {
          title: kpTitle,
          nodeKey: childNodeKey,
          matchedPointId: apiChild?.id || null,
          matchedNodeKey: apiChild?.node_key || null,
          status: resolvedStatus,
        });

        return {
          id: `${node.id}-${childIndex}`,
          backendId: pointIdByNodeKey.get(childNodeKey) || apiChild?.id || null,
          pointId: pointIdByNodeKey.get(childNodeKey) || apiChild?.id || null,
          parentBackendId,
          parentTitle: node.title,
          parentSubtitle: node.subtitle || "",
          title: kpTitle,
          status: resolvedStatus,
          importance: childIndex < 3 ? "high" : "medium",
          nodeKey: childNodeKey,
          parentNodeKey: stageNodeKey,
          type: "child",
          stageIndex,
          childIndex,
        };
      });

      const computedStatus = getStatusByNodeKey(stageNodeKey) !== "not_started"
        ? getStatusByNodeKey(stageNodeKey)
        : computeParentStatusFromChildren(childPoints);

      console.debug("[node-key:render-match]", {
        title: node.title,
        nodeKey: stageNodeKey,
        type: "stage",
        matchedPointId: stageApiPoint?.id || null,
        matchedNodeKey: stageApiPoint?.node_key || null,
        status: computedStatus,
      });

      return {
        ...node,
        backendId: parentBackendId,
        pointId: parentBackendId,
        status: computedStatus,
        knowledgePoints: childPoints,
        nodeKey: stageNodeKey,
        type: "stage",
        stageIndex,
      };
    });
  }, [platformRouteNodes, course, backendPointByNodeKey, pointIdByNodeKey, localStatusByNodeKey]);

  const routeNodes = activeRouteSource === "platform" ? normalizedPlatformNodes : materialRouteNodes;

  const overallProgress = useMemo(() => {
    if (routeNodes.length > 0) return calculateOverallProgress(routeNodes);
    return { percent: 0, masteredPoints: 0, totalPoints: 0, reviewCount: 0 };
  }, [routeNodes]);

  const knowledgeOverview = useMemo(() => {
    if (routeNodes.length > 0) return deriveKnowledgePointsOverview(routeNodes);
    return [];
  }, [routeNodes]);

  const [expandedNodeId, setExpandedNodeId] = useState(null);
  const [selectedKp, setSelectedKp] = useState(null);

  const handleNodeClick = (node) => {
    setExpandedNodeId((prev) => (prev === node.id ? null : node.id));
    setSelectedKp(null);
  };

  const handleKpClick = (kp) => {
    setSelectedKp(kp);
  };

  const applyLocalKnowledgeStatus = (knowledgePointId, status, nodeKey = "") => {
    const normalizedStatus = normalizeKnowledgeStatus(status);
    if (nodeKey) {
      setLocalStatusByNodeKey((prev) => ({
        ...prev,
        [nodeKey]: normalizedStatus,
      }));
    }
    setApiKnowledgePoints((prev) =>
      prev.map((point) =>
        point.id === knowledgePointId
          ? {
              ...point,
              status: normalizedStatus,
              mastery_score: STATUS_MASTERY_SCORE[status] ?? point.mastery_score ?? 0,
            }
          : point
      )
    );
    setSelectedKp((prev) =>
      prev?.backendId === knowledgePointId
        ? { ...prev, status: normalizedStatus, mastery_score: STATUS_MASTERY_SCORE[status] ?? prev.mastery_score ?? 0 }
        : prev
    );
  };

  const createKnowledgePointRecord = async (item) => {
    let parentId = item.parentBackendId || (item.parentNodeKey ? pointIdByNodeKey.get(item.parentNodeKey) : null) || null;

    if (!parentId && item.parentNodeKey) {
      const existingParent = backendPointByNodeKey.get(item.parentNodeKey);
      if (existingParent) {
        parentId = existingParent.id;
      } else if (item.parentTitle) {
        const parentPayload = {
          username: user.username,
          course_id: course,
          parent_id: null,
          title: item.parentTitle,
          description: item.parentSubtitle || "",
          level: 0,
          node_key: item.parentNodeKey,
          parent_node_key: null,
        };
        console.debug("[node-key:create-payload]", { type: "parent", nodeKey: item.parentNodeKey, payload: parentPayload });
        const parentRes = await fetch("/api/knowledge-points", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parentPayload),
        });
        const parentData = await parentRes.json();
        if (parentRes.ok && parentData.knowledge_point) {
          parentId = parentData.knowledge_point.id;
          setApiKnowledgePoints((prev) =>
            prev.some((p) => p.id === parentId) ? prev : [...prev, parentData.knowledge_point]
          );
        }
      }
    }

    const payload = {
      username: user.username,
      course_id: course,
      parent_id: parentId,
      title: item.title,
      description: item.subtitle || "",
      level: parentId ? 1 : 0,
      node_key: item.nodeKey || null,
      parent_node_key: item.parentNodeKey || null,
    };
    console.debug("[node-key:create-payload]", { type: item.type || "point", nodeKey: item.nodeKey, payload });

    const res = await fetch("/api/knowledge-points", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "创建知识点失败");
    const point = data.knowledge_point;
    setApiKnowledgePoints((prev) => (point && !prev.some((p) => p.id === point.id) ? [...prev, point] : prev));
    return point;
  };

  const saveKnowledgeStatusByTarget = async (target, status) => {
    const pointId = target.pointId || target.backendId || pointIdByNodeKey.get(target.nodeKey) || (await createKnowledgePointRecord(target))?.id;
    if (!pointId) throw new Error("无法识别当前知识点，状态保存失败");

    const requestBody = {
      username: user.username,
      status,
      mastery_score: STATUS_MASTERY_SCORE[status] ?? 0,
    };
    console.debug("[node-key:update-request]", { pointId, nodeKey: target.nodeKey, body: requestBody });

    const res = await fetch(`/api/knowledge-points/${pointId}/progress`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await res.json().catch(() => ({}));
    console.debug("[node-key:update-response]", {
      pointId,
      nodeKey: target.nodeKey,
      requestStatus: status,
      responseNodeKey: data.progress?.node_key,
      responseStatus: data.progress?.status,
      finalDisplay: normalizeKnowledgeStatus(data.progress?.status || status),
    });

    if (!res.ok) throw new Error(data.detail || "状态保存失败");
    const finalStatus = normalizeKnowledgeStatus(data.progress?.status || status);
    applyLocalKnowledgeStatus(pointId, finalStatus, target.nodeKey);
    return { pointId, status: finalStatus, data };
  };

  const handleUpdateKnowledgeStatus = async (item, status, event) => {
    event?.preventDefault?.();
    event?.stopPropagation?.();
    if (!user?.username || !item?.nodeKey) return;

    const target = {
      nodeKey: item.nodeKey,
      parentNodeKey: item.parentNodeKey || "",
      type: item.type || (item.parentNodeKey ? "child" : "stage"),
      title: item.title,
      stageIndex: item.stageIndex,
      childIndex: item.childIndex,
      pointId: item.pointId || item.backendId || pointIdByNodeKey.get(item.nodeKey) || null,
      backendId: item.backendId || null,
      parentBackendId: item.parentBackendId || null,
      parentTitle: item.parentTitle,
      parentSubtitle: item.parentSubtitle,
      subtitle: item.subtitle,
    };
    console.debug("[node-key:update]", {
      target,
      nextStatus: status,
    });

    const normalizedNewStatus = normalizeKnowledgeStatus(status);
    const isParent = target.type === "stage";
    const parentNode = routeNodes.find((node) => node.nodeKey === target.nodeKey);
    const parentForChild = !isParent
      ? routeNodes.find((node) => (node.knowledgePoints || []).some((kp) => kp.nodeKey === target.nodeKey))
      : null;

    setStatusError("");
    setStatusSavingId(target.nodeKey);
    setLocalStatusByNodeKey((prev) => ({
      ...prev,
      [target.nodeKey]: normalizedNewStatus,
    }));
    setSelectedKp((prev) =>
      prev?.nodeKey === target.nodeKey ? { ...prev, status: normalizedNewStatus } : prev
    );

    let cascadeChildren = [];
    if (isParent) {
      cascadeChildren = (parentNode?.knowledgePoints || []).filter((child) => {
        if (normalizedNewStatus === "learning") {
          return getStatusByNodeKey(child.nodeKey) === "not_started";
        }
        return true;
      });
      if (cascadeChildren.length > 0) {
        setLocalStatusByNodeKey((prev) => {
          const next = { ...prev, [target.nodeKey]: normalizedNewStatus };
          cascadeChildren.forEach((child) => {
            next[child.nodeKey] = normalizedNewStatus;
          });
          return next;
        });
      }
    }

    try {
      const saved = await saveKnowledgeStatusByTarget(target, normalizedNewStatus);
      setSelectedKp((prev) =>
        prev?.nodeKey === target.nodeKey
          ? { ...prev, backendId: saved.pointId, pointId: saved.pointId, status: saved.status }
          : prev
      );

      if (isParent && cascadeChildren.length > 0) {
        await Promise.all(cascadeChildren.map((child) =>
          saveKnowledgeStatusByTarget(
            {
              ...child,
              pointId: child.pointId || child.backendId || pointIdByNodeKey.get(child.nodeKey) || null,
              parentBackendId: saved.pointId,
            },
            normalizedNewStatus
          ).catch((error) => {
            console.debug("[node-key:cascade-error]", { nodeKey: child.nodeKey, error: error.message });
            return null;
          })
        ));
      }

      if (!isParent && parentForChild?.nodeKey) {
        const siblings = parentForChild.knowledgePoints || [];
        const mergedChildren = siblings.map((child) => ({
          ...child,
          status: child.nodeKey === target.nodeKey ? normalizedNewStatus : getStatusByNodeKey(child.nodeKey),
        }));
        const parentStatus = computeParentStatusFromChildren(mergedChildren);
        setLocalStatusByNodeKey((prev) => ({
          ...prev,
          [parentForChild.nodeKey]: parentStatus,
        }));
        await saveKnowledgeStatusByTarget(
          {
            ...parentForChild,
            pointId: parentForChild.pointId || parentForChild.backendId || pointIdByNodeKey.get(parentForChild.nodeKey) || null,
          },
          parentStatus
        ).catch((error) => {
          console.debug("[node-key:parent-sync-error]", { nodeKey: parentForChild.nodeKey, error: error.message });
        });
      }
    } catch (error) {
      setStatusError(error.message || "状态保存失败，请稍后重试");
    } finally {
      setStatusSavingId(null);
    }
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
        knowledgePointBackendId: selectedKp.backendId,
        knowledgePointTitle: selectedKp.title,
        knowledgePointStatus: selectedKp.status || "not_started",
        knowledgePointNodeKey: selectedKp.nodeKey || "",
        knowledgePointParentNodeKey: selectedKp.parentNodeKey || "",
        knowledgePointType: selectedKp.type || "child",
        knowledgePointStageIndex: selectedKp.stageIndex,
        knowledgePointChildIndex: selectedKp.childIndex,
        nodeKey: selectedKp.nodeKey || "",
        parentNodeKey: selectedKp.parentNodeKey || "",
        pointId: selectedKp.pointId || selectedKp.backendId || null,
        title: selectedKp.title,
        nodeType: selectedKp.type || "child",
        course,
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
          {statusError && <div className="kl-route-error">{statusError}</div>}
          {knowledgeLoading ? (
            <div className="kl-loading">
              <div className="kl-loading-spinner" />
              <p className="kl-loading-text">正在加载知识点...</p>
            </div>
          ) : routeNodes.length > 0 ? (
            <div className="kl-route-section">
              <div className="kl-route-list">
                {routeNodes.map((node, i) => (
                  <RouteNodeCard
                    key={node.id}
                    node={node}
                    index={i}
                    isLast={i === routeNodes.length - 1}
                    onClick={handleNodeClick}
                    isExpanded={expandedNodeId === node.id}
                    onKnowledgePointClick={handleKpClick}
                    onStatusChange={handleUpdateKnowledgeStatus}
                    statusSavingId={statusSavingId}
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
          {selectedKp ? (
            <div className="kl-card kl-side-card">
              <div className="kl-side-card-header">
                <h3 className="kl-side-card-title">当前选中知识点</h3>
              </div>
              <div className="kl-kp-detail">
                <p className="kl-kp-detail-name">{selectedKp.title}</p>
                <span className="kl-kp-detail-status" style={{
                  color: (STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.not_started).color,
                  background: (STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.not_started).bg,
                }}>
                  {(STATUS_CONFIG[selectedKp.status] || STATUS_CONFIG.not_started).label}
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
                  const cfg = STATUS_CONFIG[stage.status] || STATUS_CONFIG.not_started;
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
