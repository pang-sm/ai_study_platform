import { useEffect, useMemo, useState } from "react";
import "./KnowledgeLearningPage.css";

const API_BASE = "/api";
const COURSE_ID = "data_structure_11408";
const COURSE_NAME = "11408 数据结构";

const STATUS_CONFIG = {
  not_started: { label: "未学习", shortLabel: "未学习", color: "#64748b", bg: "#f1f5f9" },
  learning: { label: "学习中", shortLabel: "学习中", color: "#7c3aed", bg: "#ede9fe" },
  mastered: { label: "已学习", shortLabel: "已学习", color: "#16a34a", bg: "#dcfce7" },
  review_due: { label: "待复习", shortLabel: "待复习", color: "#dc2626", bg: "#fee2e2" },
};

const STATUS_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "not_started", label: "未学习" },
  { value: "learning", label: "学习中" },
  { value: "mastered", label: "已学习" },
  { value: "review_due", label: "待复习" },
];

const MANUAL_STATUS_OPTIONS = [
  { value: "not_started", label: "未学习" },
  { value: "learning", label: "学习中" },
  { value: "mastered", label: "已学习" },
];

function normalizeStatus(status) {
  return STATUS_CONFIG[status] ? status : "not_started";
}

function nodeLabel(node) {
  return node?.title || "未命名知识点";
}

function chapterLabel(chapter) {
  if (!chapter) return "";
  return `第${chapter.chapter_no}章 ${chapter.title}`;
}

function isInternalCode(code) {
  return !code || String(code).startsWith("_leaf:");
}

function getDisplayCode(node) {
  const code = node?.code;
  if (!code || String(code).startsWith("_leaf:")) return "";
  return code;
}

function normalizeTitle(title) {
  if (!title) return "未命名知识点";
  return String(title).replace(/^(\d+)[．、]\s*/, "$1. ").trim();
}

function isLeaf(node) {
  // Backend sets is_leaf; fallback: check children length
  if (typeof node?.is_leaf === "boolean") return node.is_leaf;
  return !(node?.children || []).length;
}

function flattenNodes(nodes, chapter = null) {
  const result = [];
  const walk = (items, parent = null, depth = 1) => {
    (items || []).forEach((item) => {
      const enriched = { ...item, parent, depth, chapter };
      result.push(enriched);
      walk(item.children || [], enriched, depth + 1);
    });
  };
  walk(nodes);
  return result;
}

function updateNodeInTree(nodes, code, patch) {
  return (nodes || []).map((node) => {
    const next = node.code === code ? { ...node, ...patch } : { ...node };
    next.children = updateNodeInTree(next.children || [], code, patch);
    return next;
  });
}

function recalcStats(chapters) {
  const stats = { total: 0, mastered: 0, learning: 0, review_due: 0, not_started: 0 };
  const walk = (nodes) => {
    (nodes || []).forEach((node) => {
      if ((node.children || []).length > 0) {
        walk(node.children);
      } else {
        stats.total += 1;
        const status = normalizeStatus(node.status);
        stats[status] = (stats[status] || 0) + 1;
      }
    });
  };
  (chapters || []).forEach((ch) => walk(ch.children || []));
  return stats;
}

function filterTree(nodes, keyword, status) {
  const normalizedKeyword = keyword.trim().toLowerCase();
  return (nodes || [])
    .map((node) => {
      const children = filterTree(node.children || [], keyword, status);
      const text = [node.title, node.code].filter(Boolean).join(" ").toLowerCase();
      const keywordMatch = !normalizedKeyword || text.includes(normalizedKeyword);
      const nodeStatus = normalizeStatus(node.status);
      const statusMatch = status === "all" || nodeStatus === status;
      if ((keywordMatch && statusMatch) || children.length > 0) {
        return { ...node, children };
      }
      return null;
    })
    .filter(Boolean);
}

function collectExpandableIds(nodes, maxDepth = 2, depth = 1, result = new Set()) {
  (nodes || []).forEach((node) => {
    if ((node.children || []).length > 0 && depth <= maxDepth) {
      result.add(node.id);
    }
    collectExpandableIds(node.children || [], maxDepth, depth + 1, result);
  });
  return result;
}

function collectAllExpandableIds(nodes, result = new Set()) {
  (nodes || []).forEach((node) => {
    if ((node.children || []).length > 0) {
      result.add(node.id);
      collectAllExpandableIds(node.children || [], result);
    }
  });
  return result;
}

function findFirstMatchingChapter(chapters, keyword, status) {
  const query = keyword.trim();
  if (!query && status === "all") return null;
  return (chapters || []).find((chapter) => filterTree(chapter.children || [], query, status).length > 0) || null;
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[normalizeStatus(status)];
  return (
    <span className="km-status-badge" style={{ color: cfg.color, background: cfg.bg }}>
      {cfg.label}
    </span>
  );
}

function StatCard({ icon, value, label }) {
  return (
    <div className="km-stat-card">
      <div className="km-stat-icon">{icon}</div>
      <div>
        <div className="km-stat-value">{Number(value || 0).toLocaleString("zh-CN")}</div>
        <div className="km-stat-label">{label}</div>
      </div>
    </div>
  );
}

function HighlightedText({ text, keyword }) {
  const value = String(text || "");
  const query = keyword.trim();
  if (!query) return value;
  const index = value.toLowerCase().indexOf(query.toLowerCase());
  if (index < 0) return value;
  return (
    <>
      {value.slice(0, index)}
      <mark className="km-highlight">{value.slice(index, index + query.length)}</mark>
      {value.slice(index + query.length)}
    </>
  );
}

function KnowledgeTreeNode({ node, depth = 1, selectedId, expandedIds, keyword, onSelect, onToggle }) {
  const children = node.children || [];
  const hasChildren = children.length > 0;
  const expanded = hasChildren && expandedIds.has(node.id);
  const selected = selectedId === node.id;
  const leaf = isLeaf(node);

  return (
    <div className={`km-tree-node km-tree-node--depth-${Math.min(depth, 4)}`}>
      <button
        type="button"
        className={`km-node-pill${selected ? " km-node-pill--selected" : ""}${hasChildren ? " km-node-pill--parent" : ""}${leaf ? " km-node-pill--leaf" : ""}`}
        style={{ "--km-depth": Math.min(depth - 1, 5) }}
        onClick={() => onSelect(node)}
      >
        {hasChildren ? (
          <span
            role="button"
            tabIndex={0}
            className="km-node-toggle"
            aria-label={expanded ? "收起" : "展开"}
            onClick={(event) => {
              event.stopPropagation();
              onToggle(node.id);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                onToggle(node.id);
              }
            }}
          >
            {expanded ? "▼" : "▶"}
          </span>
        ) : (
          <span className="km-node-toggle km-node-toggle--leaf" aria-hidden="true" />
        )}
        {getDisplayCode(node) ? (
          <span className="km-node-code">
            <HighlightedText text={getDisplayCode(node)} keyword={keyword} />
          </span>
        ) : null}
        <span className="km-node-title">
          <HighlightedText text={normalizeTitle(nodeLabel(node))} keyword={keyword} />
        </span>
        <StatusBadge status={node.status} />
        {!leaf && hasChildren && <span className="km-node-summary-tag">汇总</span>}
        {node.optional && <span className="km-node-optional">选学</span>}
      </button>
      {expanded && children.length > 0 && (
        <div className="km-tree-children">
          {children.map((child) => (
            <KnowledgeTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              expandedIds={expandedIds}
              keyword={keyword}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeLearningPage({ user, onNavigateToAI }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeChapterCode, setActiveChapterCode] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const [savingStatus, setSavingStatus] = useState("");
  const [reviewIntervalDays, setReviewIntervalDays] = useState(7);
  const [reviewInput, setReviewInput] = useState("7");
  const [reviewSaving, setReviewSaving] = useState(false);

  const loadMap = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ course_id: COURSE_ID });
      if (user?.username) params.set("username", user.username);
      const res = await fetch(`${API_BASE}/knowledge-map?${params.toString()}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || "知识脉络加载失败");
      setData(payload);
      const firstChapter = payload.chapters?.[0] || null;
      setActiveChapterCode((prev) => prev || firstChapter?.code || "");
      setSelectedNode((prev) => prev || firstChapter || null);
      setReviewIntervalDays(payload.review_interval_days || 7);
      setReviewInput(String(payload.review_interval_days || 7));
      setExpandedIds((prev) => (prev.size > 0 ? prev : collectExpandableIds(firstChapter?.children || [], 2)));
    } catch (err) {
      setError(err.message || "知识脉络加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let alive = true;
    const run = async () => {
      if (!alive) return;
      await loadMap();
    };
    run();
    return () => {
      alive = false;
    };
  }, [user?.username]);

  useEffect(() => {
    const loadSettings = async () => {
      if (!user?.username) return;
      try {
        const params = new URLSearchParams({ course_id: COURSE_ID, username: user.username });
        const res = await fetch(`${API_BASE}/knowledge-map/review-settings?${params.toString()}`);
        const payload = await res.json().catch(() => ({}));
        if (res.ok) {
          setReviewIntervalDays(payload.review_interval_days || 7);
          setReviewInput(String(payload.review_interval_days || 7));
        }
      } catch {
        // Keep the default interval.
      }
    };
    loadSettings();
  }, [user?.username]);

  const chapters = data?.chapters || [];
  const activeChapter = chapters.find((chapter) => chapter.code === activeChapterCode) || chapters[0] || null;
  const filteredChildren = useMemo(
    () => filterTree(activeChapter?.children || [], query, statusFilter),
    [activeChapter, query, statusFilter]
  );
  const flatActiveNodes = useMemo(
    () => flattenNodes(activeChapter?.children || [], activeChapter),
    [activeChapter]
  );
  // Use backend stats (leaf-only) when available; fall back to local recalculation
  const stats = data?.stats && data.stats.total > 0 ? data.stats : recalcStats(chapters);

  useEffect(() => {
    if (query.trim() || statusFilter !== "all") {
      setExpandedIds(collectAllExpandableIds(filteredChildren));
    }
  }, [filteredChildren, query, statusFilter]);

  const handleChapterClick = (chapter) => {
    setActiveChapterCode(chapter.code);
    setSelectedNode(chapter);
    setExpandedIds(collectExpandableIds(chapter.children || [], 2));
  };

  const handleSearch = () => {
    const nextQuery = searchInput.trim();
    setQuery(nextQuery);
    if (!nextQuery && statusFilter === "all") {
      setExpandedIds(collectExpandableIds(activeChapter?.children || [], 2));
      return;
    }
    const matchingChapter = findFirstMatchingChapter(chapters, nextQuery, statusFilter);
    if (matchingChapter && matchingChapter.code !== activeChapterCode) {
      setActiveChapterCode(matchingChapter.code);
      setSelectedNode(matchingChapter);
      setExpandedIds(collectAllExpandableIds(filterTree(matchingChapter.children || [], nextQuery, statusFilter)));
    }
  };

  const handleStatusFilter = (nextStatus) => {
    setStatusFilter(nextStatus);
    const matchingChapter = findFirstMatchingChapter(chapters, query, nextStatus);
    if (matchingChapter && matchingChapter.code !== activeChapterCode) {
      setActiveChapterCode(matchingChapter.code);
      setSelectedNode(matchingChapter);
      setExpandedIds(collectAllExpandableIds(filterTree(matchingChapter.children || [], query, nextStatus)));
    }
  };

  const selectNode = (node) => {
    setSelectedNode(node);
  };

  const toggleNode = (nodeId) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  };

  const applyNodePatch = (code, patch) => {
    setData((prev) => {
      if (!prev) return prev;
      const chaptersNext = updateNodeInTree(prev.chapters || [], code, patch);
      return { ...prev, chapters: chaptersNext, stats: recalcStats(chaptersNext) };
    });
    setSelectedNode((prev) => (prev?.code === code ? { ...prev, ...patch } : prev));
  };

  const selectedChapterName = chapterLabel(activeChapter);
  const detailNode = selectedNode || activeChapter;
  const detailIsLeaf = isLeaf(detailNode);
  const detailStatus = normalizeStatus(detailNode?.status);
  const statusCounts = detailNode?.status_counts || {};

  const saveStatus = async (nextStatus) => {
    if (!detailNode?.code || !user?.username) return;
    if (!detailIsLeaf) {
      setError("Only leaf knowledge points can be manually updated");
      return;
    }
    setSavingStatus(nextStatus);
    setError("");
    setNotice("");
    try {
      const res = await fetch(`${API_BASE}/knowledge-map/progress`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: COURSE_ID,
          knowledge_point_code: detailNode.code,
          knowledge_point_title: nodeLabel(detailNode),
          status: nextStatus,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || "状态保存失败");
      const patch = {
        status: payload.node?.status || nextStatus,
        stored_status: payload.node?.stored_status || nextStatus,
        learned_at: payload.node?.learned_at || null,
        review_due_at: payload.node?.review_due_at || null,
        review_interval_days: payload.node?.review_interval_days || reviewIntervalDays,
        progress: payload.progress || {},
      };
      applyNodePatch(detailNode.code, patch);
      setNotice("状态已保存");
    } catch (err) {
      setError(err.message || "状态保存失败");
    } finally {
      setSavingStatus("");
    }
  };

  const saveReviewSettings = async () => {
    const value = Number(reviewInput);
    setError("");
    setNotice("");
    if (!Number.isInteger(value) || value < 1 || value > 365) {
      setError("复习间隔必须是 1 到 365 之间的整数");
      return;
    }
    if (!user?.username) return;
    setReviewSaving(true);
    try {
      const res = await fetch(`${API_BASE}/knowledge-map/review-settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: COURSE_ID,
          review_interval_days: value,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || "复习间隔保存失败");
      setReviewIntervalDays(payload.review_interval_days || value);
      setReviewInput(String(payload.review_interval_days || value));
      setNotice("复习间隔已保存");
    } catch (err) {
      setError(err.message || "复习间隔保存失败");
    } finally {
      setReviewSaving(false);
    }
  };

  const openAI = () => {
    if (!detailNode) return;
    onNavigateToAI?.({
      type: "knowledge_point",
      course_id: COURSE_ID,
      courseId: COURSE_NAME,
      course_name: COURSE_NAME,
      courseName: COURSE_NAME,
      exam: "11408",
      subject: "数据结构",
      subject_key: "data_structure",
      source_page: "knowledge_map",
      chapter: selectedChapterName,
      chapterTitle: selectedChapterName,
      knowledge_point_code: detailNode.code || "",
      knowledgePointCode: detailNode.code || "",
      knowledge_point_title: nodeLabel(detailNode),
      knowledgePointTitle: nodeLabel(detailNode),
      is_leaf: detailIsLeaf,
      knowledgePointStatus: detailNode.status || "not_started",
      nodeKey: detailNode.id,
      title: nodeLabel(detailNode),
      aiPromptContext: `当前围绕知识点「${getDisplayCode(detailNode) || ""} ${normalizeTitle(nodeLabel(detailNode))}」进行提问；所属章节：${selectedChapterName}。`,
    });
  };

  if (loading) {
    return (
      <div className="km-page">
        <div className="km-loading-card">正在加载知识脉络...</div>
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="km-page">
        <div className="km-error-card">{error}</div>
      </div>
    );
  }

  return (
    <div className="km-page">
      <section className="km-hero-card">
        <div>
          <h1>知识脉络 · 数据结构</h1>
          <p>当前课程：{data?.course_name || COURSE_NAME}</p>
        </div>
      </section>

      <section className="km-stats-row">
        <StatCard icon="◎" value={stats.total} label="知识点总数" />
        <StatCard icon="✓" value={stats.mastered} label="已学习" />
        <StatCard icon="◐" value={stats.learning} label="学习中" />
        <StatCard icon="!" value={stats.review_due} label="待复习" />
      </section>

      <section className="km-filter-card">
        <div className="km-filter-row">
          <div className="km-search-box">
            <span>⌕</span>
            <input
              value={searchInput}
              onChange={(event) => {
                const nextValue = event.target.value;
                setSearchInput(nextValue);
                if (!nextValue.trim()) {
                  setQuery("");
                  if (statusFilter === "all") setExpandedIds(collectExpandableIds(activeChapter?.children || [], 2));
                }
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSearch();
              }}
              placeholder="在当前课程中搜索知识点、章节或编号..."
            />
          </div>
          <button type="button" className="km-primary-button" onClick={handleSearch}>搜索</button>
        </div>

        <div className="km-filter-row km-filter-row--inline">
          <span className="km-filter-label">掌握状态</span>
          <div className="km-chip-group">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`km-chip${statusFilter === option.value ? " km-chip--active" : ""}`}
                onClick={() => handleStatusFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <span className="km-filter-sep" />

          <span className="km-filter-label">复习规则</span>
          <div className="km-review-setting">
            <span>已学习后</span>
            <input
              type="number"
              min="1"
              max="365"
              value={reviewInput}
              onChange={(event) => setReviewInput(event.target.value)}
              className="km-review-input"
            />
            <span>天转为待复习</span>
            <button type="button" className="km-secondary-button" onClick={saveReviewSettings} disabled={reviewSaving}>
              {reviewSaving ? "保存中..." : "保存"}
            </button>
          </div>

        </div>
      </section>

      {(error || notice) && (
        <div className={`km-inline-message${error ? " km-inline-message--error" : ""}`}>
          {error || notice}
        </div>
      )}

      <section className="km-map-card">
        <aside className="km-chapter-list">
          <h2>章节目录</h2>
          {chapters.map((chapter) => (
            <button
              key={chapter.code}
              type="button"
              className={`km-chapter-item${activeChapter?.code === chapter.code ? " km-chapter-item--active" : ""}`}
              onClick={() => handleChapterClick(chapter)}
            >
              <span>{chapter.chapter_no}</span>
              <strong>{chapterLabel(chapter)}</strong>
            </button>
          ))}
        </aside>

        <div className="km-visual-area">
          <div className="km-visual-header">
            <div>
              <h2>{selectedChapterName}</h2>
              <p>{flatActiveNodes.length} 个知识节点</p>
            </div>
            <StatusBadge status={activeChapter?.status} />
          </div>

          {filteredChildren.length === 0 ? (
            <div className="km-empty-state">没有匹配的知识点，请调整搜索或筛选条件。</div>
          ) : (
            <div className="km-tree-view">
              {filteredChildren.map((node) => (
                <KnowledgeTreeNode
                  key={node.id}
                  node={node}
                  selectedId={detailNode?.id}
                  expandedIds={expandedIds}
                  keyword={query}
                  onSelect={selectNode}
                  onToggle={toggleNode}
                />
              ))}
            </div>
          )}
        </div>

        <aside className="km-detail-panel">
          <div className="km-detail-header">
            <h2>知识点详情</h2>
            <StatusBadge status={detailStatus} />
          </div>
          <dl className="km-detail-list">
            <div>
              <dt>名称</dt>
              <dd>{normalizeTitle(nodeLabel(detailNode))}</dd>
            </div>
            <div>
              <dt>编号</dt>
              <dd>{getDisplayCode(detailNode) || "无编号"}</dd>
            </div>
            <div>
              <dt>所属章节</dt>
              <dd>{selectedChapterName || "未选择章节"}</dd>
            </div>
            <div>
              <dt>当前状态</dt>
              <dd>{STATUS_CONFIG[detailStatus].shortLabel}</dd>
            </div>
            {!detailIsLeaf && (
              <div>
                <dt>下级知识点</dt>
                <dd>{statusCounts ? Object.values(statusCounts).reduce((a, b) => a + b, 0) : 0} 个</dd>
              </div>
            )}
          </dl>

          {!detailIsLeaf && statusCounts && (
            <div className="km-status-counts">
              <h3>下级状态统计</h3>
              <div className="km-counts-grid">
                <div className="km-count-item"><span className="km-count-num">{statusCounts.not_started || 0}</span><span className="km-count-label">未学习</span></div>
                <div className="km-count-item"><span className="km-count-num">{statusCounts.learning || 0}</span><span className="km-count-label">学习中</span></div>
                <div className="km-count-item"><span className="km-count-num">{statusCounts.mastered || 0}</span><span className="km-count-label">已学习</span></div>
                <div className="km-count-item"><span className="km-count-num">{statusCounts.review_due || 0}</span><span className="km-count-label">待复习</span></div>
              </div>
            </div>
          )}

          {detailIsLeaf ? (
            <div className="km-status-manager">
              <h3>状态管理</h3>
              <div className="km-status-actions">
                {MANUAL_STATUS_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`km-status-button${detailStatus === option.value ? " km-status-button--active" : ""}`}
                    onClick={() => saveStatus(option.value)}
                    disabled={savingStatus !== "" || !detailNode?.code}
                  >
                    {savingStatus === option.value ? "保存中..." : option.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="km-status-manager km-status-manager--disabled">
              <h3>状态管理</h3>
              <p className="km-parent-hint">该节点状态由下级知识点自动汇总，不能手动设置。</p>
            </div>
          )}

          <div className="km-review-hint">
            <h3>复习提示</h3>
            {detailIsLeaf && detailStatus === "review_due" ? (
              <p>该知识点已到复习时间，复习完成后请点击"已学习"开启下一轮复习。</p>
            ) : detailIsLeaf && detailStatus === "mastered" ? (
              <p>{detailNode?.review_due_at ? `下次复习时间：${formatDateTime(detailNode.review_due_at)}` : `已学习后 ${reviewIntervalDays} 天进入待复习。`}</p>
            ) : detailIsLeaf ? (
              <p>设置为"已学习"后，系统会根据复习间隔自动生成下次复习时间。</p>
            ) : (
              <p>父级节点的复习状态由下级叶子知识点自动决定。</p>
            )}
          </div>

          <div className="km-actions">
            <button type="button" onClick={openAI}>AI问答</button>
          </div>
        </aside>
      </section>
    </div>
  );
}
