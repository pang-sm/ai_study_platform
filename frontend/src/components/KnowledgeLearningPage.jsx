import { useEffect, useMemo, useState } from "react";
import "./KnowledgeLearningPage.css";

const API_BASE = "/api";
const COURSE_ID = "data_structure_11408";
const COURSE_NAME = "11408 数据结构";

const STATUS_CONFIG = {
  mastered: { label: "已掌握", shortLabel: "已掌握", color: "#16a34a", bg: "#dcfce7" },
  learning: { label: "学习中", shortLabel: "学习中", color: "#7c3aed", bg: "#ede9fe" },
  not_started: { label: "未学习", shortLabel: "未学习", color: "#64748b", bg: "#f1f5f9" },
};

const STATUS_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "mastered", label: "已掌握" },
  { value: "learning", label: "学习中" },
  { value: "not_started", label: "未学习" },
];

const VIEW_OPTIONS = [
  { value: "graph", label: "关系图" },
  { value: "tree", label: "树状图" },
  { value: "chapter", label: "章节视图" },
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

function countDescendants(node) {
  return (node?.children || []).reduce((sum, child) => sum + 1 + countDescendants(child), 0);
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

function filterTree(nodes, keyword, status) {
  const normalizedKeyword = keyword.trim().toLowerCase();
  return (nodes || [])
    .map((node) => {
      const children = filterTree(node.children || [], keyword, status);
      const text = [node.title, node.code].filter(Boolean).join(" ").toLowerCase();
      const keywordMatch = !normalizedKeyword || text.includes(normalizedKeyword);
      const statusMatch = status === "all" || normalizeStatus(node.status) === status;
      if ((keywordMatch && statusMatch) || children.length > 0) {
        return { ...node, children };
      }
      return null;
    })
    .filter(Boolean);
}

function collectExpandableIds(nodes, maxDepth = 1, depth = 1, result = new Set()) {
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
  if (!query) return null;
  return (chapters || []).find((chapter) => filterTree(chapter.children || [], query, status).length > 0) || null;
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

function KnowledgeTreeNode({
  node,
  depth = 1,
  selectedId,
  expandedIds,
  keyword,
  onSelect,
  onToggle,
}) {
  const children = node.children || [];
  const hasChildren = children.length > 0;
  const expanded = hasChildren && expandedIds.has(node.id);
  const selected = selectedId === node.id;

  return (
    <div className={`km-tree-node km-tree-node--depth-${Math.min(depth, 4)}`}>
      <button
        type="button"
        className={`km-node-pill${selected ? " km-node-pill--selected" : ""}${hasChildren ? " km-node-pill--parent" : ""}`}
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
        <span className="km-node-code">
          <HighlightedText text={node.code || "条目"} keyword={keyword} />
        </span>
        <span className="km-node-title">
          <HighlightedText text={nodeLabel(node)} keyword={keyword} />
        </span>
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
  const [activeChapterCode, setActiveChapterCode] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [viewMode, setViewMode] = useState("tree");
  const [expandedIds, setExpandedIds] = useState(() => new Set());

  useEffect(() => {
    let alive = true;
    const loadMap = async () => {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams({ course_id: COURSE_ID });
        if (user?.username) params.set("username", user.username);
        const res = await fetch(`${API_BASE}/knowledge-map?${params.toString()}`);
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.detail || "知识脉络加载失败");
        if (!alive) return;
        setData(payload);
        const firstChapter = payload.chapters?.[0] || null;
        setActiveChapterCode(firstChapter?.code || "");
        setSelectedNode(firstChapter || null);
        setExpandedIds(collectExpandableIds(firstChapter?.children || [], 1));
      } catch (err) {
        if (alive) setError(err.message || "知识脉络加载失败");
      } finally {
        if (alive) setLoading(false);
      }
    };
    loadMap();
    return () => {
      alive = false;
    };
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

  useEffect(() => {
    if (!query.trim()) return;
    setExpandedIds(collectAllExpandableIds(filteredChildren));
  }, [filteredChildren, query]);

  const handleChapterClick = (chapter) => {
    setActiveChapterCode(chapter.code);
    setSelectedNode(chapter);
    setExpandedIds(collectExpandableIds(chapter.children || [], 1));
  };

  const handleSearch = () => {
    const nextQuery = searchInput.trim();
    setQuery(nextQuery);
    if (!nextQuery) {
      setExpandedIds(collectExpandableIds(activeChapter?.children || [], 1));
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
    if (query.trim()) {
      const matchingChapter = findFirstMatchingChapter(chapters, query, nextStatus);
      if (matchingChapter) {
        setActiveChapterCode(matchingChapter.code);
        setSelectedNode(matchingChapter);
        setExpandedIds(collectAllExpandableIds(filterTree(matchingChapter.children || [], query, nextStatus)));
      }
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

  const selectedChapterName = chapterLabel(activeChapter);
  const detailNode = selectedNode || activeChapter;
  const detailStatus = normalizeStatus(detailNode?.status);

  const openAI = () => {
    if (!detailNode) return;
    onNavigateToAI?.({
      type: "knowledge_point",
      course_id: COURSE_ID,
      courseId: COURSE_NAME,
      course_name: COURSE_NAME,
      courseName: COURSE_NAME,
      chapter: selectedChapterName,
      knowledge_point_code: detailNode.code || "",
      knowledge_point_title: nodeLabel(detailNode),
      knowledgePointId: detailNode.id,
      knowledgePointTitle: nodeLabel(detailNode),
      knowledgePointStatus: detailNode.status || "not_started",
      nodeKey: detailNode.id,
      title: nodeLabel(detailNode),
      aiPromptContext: `当前学习知识点：${nodeLabel(detailNode)}；编号：${detailNode.code || "无"}；所属章节：${selectedChapterName}。`,
    });
  };

  if (loading) {
    return (
      <div className="km-page">
        <div className="km-loading-card">正在加载知识脉络...</div>
      </div>
    );
  }

  if (error) {
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
        <StatCard icon="◎" value={data?.stats?.total} label="知识点总数" />
        <StatCard icon="✓" value={data?.stats?.mastered} label="已掌握" />
        <StatCard icon="◐" value={data?.stats?.learning} label="学习中" />
        <StatCard icon="○" value={data?.stats?.not_started} label="待学习" />
      </section>

      <section className="km-filter-card">
        <div className="km-search-row">
          <div className="km-search-box">
            <span>⌕</span>
            <input
              value={searchInput}
              onChange={(event) => {
                const nextValue = event.target.value;
                setSearchInput(nextValue);
                if (!nextValue.trim()) {
                  setQuery("");
                  setExpandedIds(collectExpandableIds(activeChapter?.children || [], 1));
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

        <div className="km-filter-line">
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
        </div>

        <div className="km-filter-line">
          <span className="km-filter-label">视图</span>
          <div className="km-chip-group">
            {VIEW_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`km-chip${viewMode === option.value ? " km-chip--active" : ""}`}
                onClick={() => setViewMode(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="km-filter-line">
          <span className="km-filter-label">排序</span>
          <select className="km-sort-select" value="chapter" disabled>
            <option value="chapter">按章节顺序</option>
          </select>
        </div>
      </section>

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

          {viewMode === "graph" ? (
            <div className="km-graph-placeholder">
              关系图视图后续开放
            </div>
          ) : filteredChildren.length === 0 ? (
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
              <dd>{nodeLabel(detailNode)}</dd>
            </div>
            <div>
              <dt>编号</dt>
              <dd>{detailNode?.code || "无编号"}</dd>
            </div>
            <div>
              <dt>所属章节</dt>
              <dd>{selectedChapterName || "未选择章节"}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{STATUS_CONFIG[detailStatus].shortLabel}</dd>
            </div>
            <div>
              <dt>子知识点数量</dt>
              <dd>{(detailNode?.children || []).length}</dd>
            </div>
          </dl>
          <div className="km-actions">
            <button type="button" onClick={openAI}>AI问答</button>
          </div>
        </aside>
      </section>
    </div>
  );
}
