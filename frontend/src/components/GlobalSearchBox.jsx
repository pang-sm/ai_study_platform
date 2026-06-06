import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { highlightText } from "../utils/searchHighlight.jsx";
import "./GlobalSearchBox.css";

const API_BASE = "/api";
const SEARCH_DEBOUNCE_MS = 300;
const RECENT_SEARCHES_KEY = "ai_study_recent_searches";
const MAX_RECENT = 8;

const RECOMMEND_ENTRIES = [
  { id: "workspaceMaterials", icon: "资料", label: "课程资料库" },
  { id: "taskCenter", icon: "任务", label: "任务中心" },
  { id: "practiceCenter", icon: "练习", label: "练习中心" },
  { id: "codeStudio", icon: "</>", label: "编程学习助手" },
  { id: "learningReportCenter", icon: "报告", label: "学习报告" },
  { id: "learningDataCenter", icon: "数据", label: "学习数据中心" },
];

function getRecentSearches() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function saveRecentSearch(q) {
  const kw = (q || "").trim();
  if (!kw) return;
  const next = [kw, ...getRecentSearches().filter((item) => item !== kw)].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next));
  } catch {
    // ignore storage failures
  }
}

export default function GlobalSearchBox({
  user,
  onSearch,
  placeholder = "搜索课程、资料、知识点、任务...",
  className = "",
}) {
  const [searchValue, setSearchValue] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState(() => getRecentSearches());
  const searchRef = useRef(null);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);
  const abortRef = useRef(null);
  const requestIdRef = useRef(0);

  const doSearch = useCallback(async (q) => {
    const kw = (q || "").trim();
    if (!kw || !user?.username) {
      setSearchResults(null);
      setShowDropdown(false);
      return;
    }
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const reqId = ++requestIdRef.current;
    setSearchLoading(true);
    try {
      const params = new URLSearchParams({
        q: kw,
        username: user.username,
        limit: "5",
        include_chunks: "true",
      });
      const res = await fetch(`${API_BASE}/search/global?${params}`, { signal: controller.signal });
      const data = await res.json();
      if (reqId !== requestIdRef.current) return;
      setSearchResults(res.ok ? data : null);
      setShowDropdown(true);
    } catch (err) {
      if (err.name !== "AbortError" && reqId === requestIdRef.current) {
        setSearchResults(null);
      }
    } finally {
      if (reqId === requestIdRef.current) setSearchLoading(false);
    }
  }, [user?.username]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchValue.trim()) {
      setSearchResults(null);
      return;
    }
    debounceRef.current = setTimeout(() => doSearch(searchValue), SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchValue, doSearch]);

  useEffect(() => {
    const handler = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowDropdown(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const groups = searchResults?.groups || [];
  const flatResults = useMemo(
    () => groups.flatMap((group) => group.items.map((item) => ({ ...item, groupTitle: group.title }))),
    [groups],
  );
  const emptyMenuItems = useMemo(
    () => [
      ...recentSearches.map((kw) => ({ kind: "recent", label: kw, query: kw })),
      ...RECOMMEND_ENTRIES.map((entry) => ({ kind: "recommend", ...entry })),
    ],
    [recentSearches],
  );
  const activeItems = searchValue.trim() ? flatResults : emptyMenuItems;

  const refreshRecentSearches = () => setRecentSearches(getRecentSearches());

  const openResult = (item) => {
    const kw = searchValue.trim();
    if (kw) saveRecentSearch(kw);
    refreshRecentSearches();
    setShowDropdown(false);
    setSearchValue("");
    setSearchResults(null);
    setActiveIndex(-1);
    onSearch?.(null, item);
  };

  const openQuery = (kw) => {
    const query = (kw || "").trim();
    if (!query) return;
    saveRecentSearch(query);
    refreshRecentSearches();
    setShowDropdown(false);
    setSearchValue("");
    setActiveIndex(-1);
    onSearch?.(query);
  };

  const handleEmptyItem = (item) => {
    if (item.kind === "recent") {
      openQuery(item.query);
      return;
    }
    setShowDropdown(false);
    setActiveIndex(-1);
    onSearch?.(null, { target: { page: item.id } });
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setShowDropdown(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setShowDropdown(true);
      if (activeItems.length === 0) return;
      setActiveIndex((prev) => (prev < activeItems.length - 1 ? prev + 1 : 0));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setShowDropdown(true);
      if (activeItems.length === 0) return;
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : activeItems.length - 1));
      return;
    }
    if (event.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < activeItems.length) {
        event.preventDefault();
        if (searchValue.trim()) openResult(activeItems[activeIndex]);
        else handleEmptyItem(activeItems[activeIndex]);
        return;
      }
      if (searchValue.trim()) {
        event.preventDefault();
        openQuery(searchValue);
      }
    }
  };

  const clearRecentSearches = (event) => {
    event.stopPropagation();
    try {
      localStorage.removeItem(RECENT_SEARCHES_KEY);
    } catch {
      // ignore storage failures
    }
    setRecentSearches([]);
    setActiveIndex(-1);
  };

  const totalResults = searchResults?.total || 0;

  return (
    <div className={`global-search ${className}`} ref={searchRef}>
      <span className="global-search-icon" aria-hidden="true">🔍</span>
      <input
        ref={inputRef}
        className="global-search-input"
        type="text"
        placeholder={placeholder}
        value={searchValue}
        onChange={(event) => {
          setSearchValue(event.target.value);
          setActiveIndex(-1);
          setShowDropdown(true);
        }}
        onFocus={() => {
          refreshRecentSearches();
          setShowDropdown(true);
        }}
        onKeyDown={handleKeyDown}
      />
      {searchLoading && <span className="global-search-spinner" />}

      {showDropdown && !searchLoading && searchValue.trim() && groups.length > 0 && (
        <div className="global-search-dropdown">
          {groups.map((group) => (
            <div key={group.type} className="global-search-group">
              <div className="global-search-group-title">{group.title}</div>
              {group.items.map((item, idx) => {
                const flatIdx = flatResults.findIndex((flat) => flat.type === item.type && flat.id === item.id);
                const isActive = flatIdx === activeIndex;
                return (
                  <button
                    key={`${item.type}-${item.id}-${idx}`}
                    className={`global-search-item${isActive ? " global-search-item--active" : ""}`}
                    type="button"
                    onClick={() => openResult(item)}
                    onMouseEnter={() => setActiveIndex(flatIdx)}
                  >
                    <span className="global-search-item-head">
                      <span className="global-search-item-title">{highlightText(item.title, searchValue.trim())}</span>
                      <span className="global-search-item-type">{group.title}</span>
                    </span>
                    {item.snippet && (
                      <span className="global-search-item-snippet">{highlightText(item.snippet, searchValue.trim())}</span>
                    )}
                    {item.match_reason && <span className="global-search-item-reason">{item.match_reason}</span>}
                  </button>
                );
              })}
            </div>
          ))}
          <div className="global-search-footer">
            <span>共 {totalResults} 条结果</span>
            <button className="global-search-viewall" type="button" onClick={() => openQuery(searchValue)}>
              查看全部
            </button>
          </div>
        </div>
      )}

      {showDropdown && !searchLoading && searchValue.trim() && searchResults && groups.length === 0 && (
        <div className="global-search-dropdown">
          <div className="global-search-empty">未找到相关结果</div>
        </div>
      )}

      {showDropdown && !searchLoading && !searchValue.trim() && (
        <div className="global-search-dropdown">
          {recentSearches.length > 0 && (
            <div className="global-search-group">
              <div className="global-search-group-title global-search-group-title--split">
                <span>最近搜索</span>
                <button className="global-search-clear" type="button" onClick={clearRecentSearches}>清空</button>
              </div>
              {recentSearches.map((kw, index) => (
                <button
                  key={kw}
                  className={`global-search-item${activeIndex === index ? " global-search-item--active" : ""}`}
                  type="button"
                  onClick={() => openQuery(kw)}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  <span className="global-search-item-title">最近：{kw}</span>
                </button>
              ))}
            </div>
          )}
          <div className="global-search-group">
            <div className="global-search-group-title">推荐入口</div>
            {RECOMMEND_ENTRIES.map((entry, index) => {
              const active = recentSearches.length + index === activeIndex;
              return (
                <button
                  key={entry.id}
                  className={`global-search-item${active ? " global-search-item--active" : ""}`}
                  type="button"
                  onClick={() => handleEmptyItem({ kind: "recommend", ...entry })}
                  onMouseEnter={() => setActiveIndex(recentSearches.length + index)}
                >
                  <span className="global-search-item-title">
                    <span className="global-search-entry-icon">{entry.icon}</span>
                    {entry.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
