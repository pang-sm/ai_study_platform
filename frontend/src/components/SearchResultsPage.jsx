import { useCallback, useEffect, useState } from "react";
import "./SearchResultsPage.css";
import { highlightText } from "../utils/searchHighlight.jsx";

const API_BASE = "/api";

const FILTER_CATEGORIES = [
  { key: "all", label: "全部" },
  { key: "course", label: "课程" },
  { key: "material", label: "资料" },
  { key: "chunk", label: "资料内容" },
  { key: "knowledge_point", label: "知识点" },
  { key: "task", label: "学习任务" },
  { key: "question", label: "练习题" },
  { key: "chat", label: "历史对话" },
];

const TYPE_LABELS = {
  course: "课程", material: "资料", chunk: "资料内容",
  knowledge_point: "知识点", task: "学习任务", question: "练习题", chat: "历史对话",
};

const TYPE_COLORS = {
  course: { bg: "#dbeafe", text: "#1e40af" },
  material: { bg: "#dcfce7", text: "#166534" },
  chunk: { bg: "#fef3c7", text: "#92400e" },
  knowledge_point: { bg: "#ede9fe", text: "#5b21b6" },
  task: { bg: "#fce7f3", text: "#9d174d" },
  question: { bg: "#e0f2fe", text: "#0369a1" },
  chat: { bg: "#f1f5f9", text: "#475569" },
};

export default function SearchResultsPage({ user, setPage, searchContext, onClearSearchContext, setSearchNavigate }) {
  const initialQuery = searchContext?.q || (typeof window !== "undefined" && window.__searchQuery) || "";
  const [query, setQuery] = useState(initialQuery);
  const [inputValue, setInputValue] = useState(initialQuery);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const doSearch = useCallback(async (q) => {
    const kw = (q || "").trim();
    if (!kw || !user?.username) {
      setResults(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        q: kw,
        username: user.username,
        limit: "20",
        include_chunks: "true",
      });
      const res = await fetch(`${API_BASE}/search/global?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "搜索失败");
      setResults(data);
    } catch (e) {
      setError(e.message || "搜索失败");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [user?.username]);

  useEffect(() => {
    if (initialQuery) {
      doSearch(initialQuery);
    }
  }, [initialQuery, doSearch]);

  const handleInputSubmit = () => {
    const kw = inputValue.trim();
    if (kw) {
      setQuery(kw);
      doSearch(kw);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleInputSubmit();
    if (e.key === "Escape") setInputValue("");
  };

  const handleResultClick = (item) => {
    const t = item.target || {};
    if (!t.page) return;

    // Store navigation context for the target page
    if (setSearchNavigate) {
      setSearchNavigate({
        fromSearch: true,
        page: t.page,
        courseId: t.courseId || "",
        materialId: t.materialId,
        knowledgePointId: t.knowledgePointId,
        taskId: t.taskId,
        questionId: t.questionId,
        conversationId: t.conversationId,
        tab: t.tab,
      });
    }

    onClearSearchContext();
    setPage(t.page);
  };

  const filteredGroups = results?.groups
    ? (activeFilter === "all"
        ? results.groups
        : results.groups.filter((g) => g.type === activeFilter))
    : [];

  const totalResults = filteredGroups.reduce((sum, g) => sum + g.items.length, 0);

  return (
    <div className="srp-shell">
      {/* Search Header */}
      <div className="srp-header">
        <div className="srp-search-bar">
          <span className="srp-search-icon">🔍</span>
          <input
            className="srp-search-input"
            type="text"
            placeholder="搜索课程、资料、知识点、任务、练习题..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          {inputValue && (
            <button className="srp-search-clear" onClick={() => { setInputValue(""); setQuery(""); setResults(null); }}>
              ×
            </button>
          )}
          <button className="srp-search-btn" onClick={handleInputSubmit} disabled={loading}>
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>
        {query && results && !loading && (
          <p className="srp-result-summary">
            搜索 "{results.query}"，共 {results.total} 条结果
            {results.search_time_ms != null && ` · ${results.search_time_ms}ms`}
          </p>
        )}
      </div>

      {/* Filter Tabs */}
      {results && results.groups && results.groups.length > 0 && (
        <div className="srp-filters">
          {FILTER_CATEGORIES.map((cat) => {
            const count = cat.key === "all"
              ? results.groups.reduce((s, g) => s + g.items.length, 0)
              : (results.groups.find((g) => g.type === cat.key)?.items.length || 0);
            return (
              <button
                key={cat.key}
                className={`srp-filter-chip${activeFilter === cat.key ? " active" : ""}`}
                onClick={() => setActiveFilter(cat.key)}
              >
                {cat.label} {count > 0 && <span className="srp-filter-chip-count">{count}</span>}
              </button>
            );
          })}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="srp-empty">搜索中...</div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="srp-empty">
          <p>{error}</p>
          <button className="ghost-button compact" onClick={() => doSearch(query)} style={{ marginTop: 12 }}>
            重试
          </button>
        </div>
      )}

      {/* No query */}
      {!query && !loading && (
        <div className="srp-empty">
          <div className="srp-empty-icon">🔍</div>
          <h3>输入关键词开始搜索</h3>
          <p>支持搜索课程、资料、知识点、任务、练习题和历史对话</p>
        </div>
      )}

      {/* Results */}
      {query && results && !loading && !error && totalResults === 0 && (
        <div className="srp-empty">
          <div className="srp-empty-icon">📭</div>
          <h3>未找到相关结果</h3>
          <p>试试其他关键词，或检查是否有对应内容</p>
        </div>
      )}

      {query && results && !loading && !error && totalResults > 0 && (
        <div className="srp-results">
          {filteredGroups.map((group) => (
            <section key={group.type} className="srp-group">
              <h3 className="srp-group-title">{group.title}</h3>
              <div className="srp-group-items">
                {group.items.map((item, idx) => {
                  const colors = TYPE_COLORS[item.type] || TYPE_COLORS.chat;
                  return (
                    <div
                      key={`${item.type}-${item.id}-${idx}`}
                      className="srp-result-item"
                      onClick={() => handleResultClick(item)}
                    >
                      <div className="srp-result-item-header">
                        <span className="srp-result-item-title">
                          {highlightText(item.title, query)}
                        </span>
                        <span
                          className="srp-result-item-type"
                          style={{ background: colors.bg, color: colors.text }}
                        >
                          {TYPE_LABELS[item.type] || item.type}
                        </span>
                      </div>
                      <div className="srp-result-item-subtitle">{item.subtitle}</div>
                      {item.snippet && (
                        <div className="srp-result-item-snippet">
                          {highlightText(item.snippet, query)}
                        </div>
                      )}
                      {item.match_reason && (
                        <div className="srp-result-item-reason">{item.match_reason}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
