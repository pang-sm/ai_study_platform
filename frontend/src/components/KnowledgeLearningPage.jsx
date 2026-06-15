import { useEffect, useMemo, useState } from "react";
import "./KnowledgeLearningPage.css";

const API_BASE = "/api";
const COURSE_ID = "data_structure_11408";

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

function countDescendants(node) {
  return (node?.children || []).reduce((sum, child) => sum + 1 + countDescendants(child), 0);
}

function flattenNodes(nodes, chapterTitle = "") {
  const result = [];
  const walk = (items, parent = null, depth = 1) => {
    (items || []).forEach((item) => {
      const enriched = { ...item, parent, depth, chapterTitle };
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

function TreeNode({ node, onSelect, selectedId, depth = 1 }) {
  const selected = selectedId === node.id;
  return (
    <div className="km-tree-node">
      <button
        type="button"
        className={`km-node-pill${selected ? " km-node-pill--selected" : ""}`}
        style={{ marginLeft: `${Math.min(depth - 1, 4) * 18}px` }}
        onClick={() => onSelect(node)}
      >
        <span className="km-node-code">{node.code || "条目"}</span>
        <span className="km-node-title">{nodeLabel(node)}</span>
        {node.optional && <span className="km-node-optional">选学</span>}
      </button>
      {(node.children || []).map((child) => (
        <TreeNode
          key={child.id}
          node={child}
          onSelect={onSelect}
          selectedId={selectedId}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

function GraphBranch({ node, onSelect, selectedId, depth = 1 }) {
  const selected = selectedId === node.id;
  return (
    <div className={`km-graph-branch km-graph-branch--depth-${Math.min(depth, 3)}`}>
      <button
        type="button"
        className={`km-graph-node${selected ? " km-graph-node--selected" : ""}`}
        onClick={() => onSelect(node)}
      >
        <span>{nodeLabel(node)}</span>
        {(node.children || []).length > 0 && <small>{node.children.length} 个子项</small>}
      </button>
      {(node.children || []).length > 0 && (
        <div className="km-graph-children">
          {node.children.map((child) => (
            <GraphBranch
              key={child.id}
              node={child}
              onSelect={onSelect}
              selectedId={selectedId}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function KnowledgeLearningPage({
  user,
  setPage,
  onNavigateToAI,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeChapterCode, setActiveChapterCode] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [viewMode, setViewMode] = useState("graph");

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
    () => flattenNodes(activeChapter?.children || [], activeChapter?.title || ""),
    [activeChapter]
  );

  const handleChapterClick = (chapter) => {
    setActiveChapterCode(chapter.code);
    setSelectedNode(chapter);
  };

  const handleSearch = () => {
    setQuery(searchInput);
  };

  const selectNode = (node) => {
    setSelectedNode(node);
  };

  const selectedChapterName = activeChapter ? `第${activeChapter.chapter_no}章 ${activeChapter.title}` : "";
  const detailNode = selectedNode || activeChapter;
  const detailStatus = normalizeStatus(detailNode?.status);

  const openMaterials = () => {
    if (!detailNode) return;
    setPage?.("workspaceMaterials", {
      courseId: "11408 数据结构",
      materialKeyword: nodeLabel(detailNode),
    });
  };

  const openPractice = () => {
    if (!detailNode) return;
    setPage?.("practiceCenter", {
      courseId: "11408 数据结构",
      courseName: "11408 数据结构",
      knowledgePointTitle: nodeLabel(detailNode),
      knowledgePointText: nodeLabel(detailNode),
    });
  };

  const openAI = () => {
    if (!detailNode) return;
    onNavigateToAI?.({
      type: "knowledge_point",
      courseId: "11408 数据结构",
      courseName: "11408 数据结构",
      knowledgePointId: detailNode.id,
      knowledgePointTitle: nodeLabel(detailNode),
      knowledgePointStatus: detailNode.status || "not_started",
      nodeKey: detailNode.id,
      title: nodeLabel(detailNode),
      aiPromptContext: `当前学习知识点：${nodeLabel(detailNode)}，所属章节：${selectedChapterName}。`,
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
          <p>当前课程：{data?.course_name || "11408 数据结构"}</p>
        </div>
        <button type="button" className="km-import-button">导入知识点</button>
      </section>

      <section className="km-stats-row">
        <StatCard icon="▣" value={data?.stats?.total} label="知识点总数" />
        <StatCard icon="✓" value={data?.stats?.mastered} label="已掌握" />
        <StatCard icon="◴" value={data?.stats?.learning} label="学习中" />
        <StatCard icon="▤" value={data?.stats?.not_started} label="待学习" />
      </section>

      <section className="km-filter-card">
        <div className="km-search-row">
          <div className="km-search-box">
            <span>⌕</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSearch();
              }}
              placeholder="在当前科目中搜索知识点、章节或关系..."
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
                onClick={() => setStatusFilter(option.value)}
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
            <option value="chapter">按章节</option>
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
              <strong>第{chapter.chapter_no}章 {chapter.title}</strong>
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
          ) : viewMode === "tree" ? (
            <div className="km-tree-view">
              {filteredChildren.map((node) => (
                <TreeNode key={node.id} node={node} onSelect={selectNode} selectedId={detailNode?.id} />
              ))}
            </div>
          ) : viewMode === "chapter" ? (
            <div className="km-chapter-view">
              {filteredChildren.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  className={`km-section-card${detailNode?.id === node.id ? " km-section-card--selected" : ""}`}
                  onClick={() => selectNode(node)}
                >
                  <span>{node.code || "小节"}</span>
                  <strong>{nodeLabel(node)}</strong>
                  <small>{countDescendants(node)} 个下级知识点</small>
                </button>
              ))}
            </div>
          ) : (
            <div className="km-graph-view">
              <button
                type="button"
                className={`km-center-node${detailNode?.id === activeChapter?.id ? " km-center-node--selected" : ""}`}
                onClick={() => selectNode(activeChapter)}
              >
                <strong>第{activeChapter?.chapter_no}章</strong>
                <span>{activeChapter?.title}</span>
              </button>
              <div className="km-graph-grid">
                {filteredChildren.map((node) => (
                  <GraphBranch key={node.id} node={node} onSelect={selectNode} selectedId={detailNode?.id} />
                ))}
              </div>
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
            <button type="button" onClick={openMaterials}>查看讲义</button>
            <button type="button" onClick={openPractice}>做练习</button>
            <button type="button" onClick={openAI}>AI问答</button>
          </div>
        </aside>
      </section>
    </div>
  );
}
