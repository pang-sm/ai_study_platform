import { useEffect, useRef, useState, useCallback } from "react";
import "./HomePage.css";
import { highlightText } from "../utils/searchHighlight.jsx";

const API_BASE = "/api";
const SEARCH_DEBOUNCE_MS = 300;
const RECENT_SEARCHES_KEY = "ai_study_recent_searches";
const MAX_RECENT = 8;

const RECOMMEND_ENTRIES = [
  { id: "workspaceMaterials", icon: "📚", label: "课程资料库" },
  { id: "taskCenter", icon: "✅", label: "任务中心" },
  { id: "practiceCenter", icon: "📝", label: "练习中心" },
  { id: "codeStudio", icon: "</>", label: "编程学习助手" },
  { id: "learningReportCenter", icon: "📄", label: "学习报告" },
  { id: "learningDataCenter", icon: "📊", label: "学习数据中心" },
];

function getRecentSearches() {
  try { return JSON.parse(localStorage.getItem(RECENT_SEARCHES_KEY) || "[]"); } catch { return []; }
}
function saveRecentSearch(q) {
  if (!q || !q.trim()) return;
  const kw = q.trim();
  let recent = getRecentSearches().filter((s) => s !== kw);
  recent.unshift(kw);
  if (recent.length > MAX_RECENT) recent = recent.slice(0, MAX_RECENT);
  try { localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent)); } catch {}
}


/* ── Time-based greeting ── */

function getGreeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 11) return { text: "早上好", emoji: "👋", subtitle: "清晨是学习的黄金时间，开始今天的计划吧！" };
  if (hour >= 11 && hour < 14) return { text: "中午好", emoji: "☀️", subtitle: "午间休息一下，然后继续前进。" };
  if (hour >= 14 && hour < 18) return { text: "下午好", emoji: "🌤", subtitle: "下午精力充沛，正是攻克难题的好时机。" };
  if (hour >= 18 && hour < 24) return { text: "晚上好", emoji: "🌙", subtitle: "晚上安静，适合深度思考和复习。" };
  return { text: "夜深了", emoji: "✨", subtitle: "已经很晚了，注意休息，明天继续加油！" };
}

/* ═══════════════════════════════════════════════════════════════════════════
   TOPBAR
   ═══════════════════════════════════════════════════════════════════════════ */

function TopBar({ user, avatarObj, hasCustomAvatar, apiBase, onProfileClick, onSearch }) {
  const [searchValue, setSearchValue] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef(null);
  const debounceRef = useRef(null);
  const abortRef = useRef(null);
  const inputRef = useRef(null);
  const requestIdRef = useRef(0);

  const doSearch = useCallback(async (q) => {
    const kw = (q || "").trim();
    if (!kw || !user?.username) { setSearchResults(null); setShowDropdown(false); return; }
    // Cancel previous in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const reqId = ++requestIdRef.current;

    setSearchLoading(true);
    try {
      const params = new URLSearchParams({ q: kw, username: user.username, limit: "5", include_chunks: "true" });
      const res = await fetch(`${API_BASE}/search/global?${params}`, { signal: controller.signal });
      const data = await res.json();
      // Only apply if this is still the latest request
      if (reqId !== requestIdRef.current) return;
      if (res.ok) setSearchResults(data);
      else setSearchResults(null);
      setShowDropdown(true);
    } catch (err) {
      if (err.name === "AbortError") return;
      if (reqId !== requestIdRef.current) return;
      setSearchResults(null);
    } finally {
      if (reqId === requestIdRef.current) setSearchLoading(false);
    }
  }, [user?.username]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchValue.trim()) { setSearchResults(null); setShowDropdown(false); return; }
    debounceRef.current = setTimeout(() => doSearch(searchValue), SEARCH_DEBOUNCE_MS);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchValue, doSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (searchRef.current && !searchRef.current.contains(e.target)) setShowDropdown(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const [activeIndex, setActiveIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState(() => getRecentSearches());
  const dropdownListRef = useRef(null);

  const flatResults = searchResults?.groups
    ? searchResults.groups.flatMap((group) => group.items.map((item) => ({ ...item, groupTitle: group.title })))
    : [];

  const handleKeyDown = (e) => {
    if (e.key === "Escape") { setShowDropdown(false); setActiveIndex(-1); inputRef.current?.blur(); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (flatResults.length === 0) return;
      setActiveIndex((prev) => Math.min(prev + 1, flatResults.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
      return;
    }
    if (e.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < flatResults.length) {
        e.preventDefault();
        handleResultClick(flatResults[activeIndex]);
      } else if (searchValue.trim()) {
        setShowDropdown(false);
        saveRecentSearch(searchValue.trim());
        setRecentSearches(getRecentSearches());
        if (onSearch) onSearch(searchValue.trim());
      }
    }
  };

  const handleResultClick = (item) => {
    const kw = searchValue.trim();
    if (kw) { saveRecentSearch(kw); setRecentSearches(getRecentSearches()); }
    setShowDropdown(false);
    setSearchValue("");
    setSearchResults(null);
    setActiveIndex(-1);
    if (onSearch) onSearch(null, item);
  };

  const handleInputFocus = () => {
    if (searchValue.trim() && searchResults) setShowDropdown(true);
    if (!searchValue.trim()) setShowDropdown(true);
  };

  const clearRecentSearches = () => {
    try { localStorage.removeItem(RECENT_SEARCHES_KEY); } catch {}
    setRecentSearches([]);
  };

  const totalResults = searchResults?.total || 0;
  const groups = searchResults?.groups || [];

  return (
    <header className="hp-topbar">
      <div className="hp-topbar-search" ref={searchRef} style={{ position: "relative" }}>
        <span className="hp-search-icon">🔍</span>
        <input
          ref={inputRef}
          className="hp-search-input"
          type="text"
          placeholder="搜索课程、资料、知识点、任务..."
          value={searchValue}
          onChange={(e) => { setSearchValue(e.target.value); setActiveIndex(-1); }}
          onKeyDown={handleKeyDown}
          onFocus={handleInputFocus}
        />
        {searchLoading && <span className="hp-search-spinner" />}

        {/* Dropdown: results */}
        {showDropdown && !searchLoading && groups.length > 0 && (
          <div className="hp-search-dropdown" ref={dropdownListRef}>
            {groups.map((group) => (
              <div key={group.type} className="hp-search-dropdown-group">
                <div className="hp-search-dropdown-group-title">{group.title}</div>
                {group.items.map((item, idx) => {
                  const flatIdx = flatResults.findIndex((f) => f === item);
                  const isActive = flatIdx === activeIndex;
                  return (
                    <div
                      key={`${item.type}-${item.id}-${idx}`}
                      className={`hp-search-dropdown-item${isActive ? " hp-search-dropdown-item--active" : ""}`}
                      onClick={() => handleResultClick(item)}
                      onMouseEnter={() => setActiveIndex(flatIdx)}
                    >
                      <div className="hp-search-dropdown-item-header">
                        <span className="hp-search-dropdown-item-title">
                          {highlightText(item.title, searchValue.trim())}
                        </span>
                        <span className="hp-search-dropdown-item-type">{group.title}</span>
                      </div>
                      {item.snippet && (
                        <div className="hp-search-dropdown-item-snippet">
                          {highlightText(item.snippet, searchValue.trim())}
                        </div>
                      )}
                      {item.match_reason && (
                        <div className="hp-search-dropdown-item-reason">{item.match_reason}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
            <div className="hp-search-dropdown-footer">
              <span>共 {totalResults} 条结果</span>
              <button
                className="hp-search-dropdown-viewall"
                onClick={() => {
                  setShowDropdown(false);
                  const kw = searchValue.trim();
                  if (kw) { saveRecentSearch(kw); setRecentSearches(getRecentSearches()); }
                  if (onSearch) onSearch(kw);
                }}
              >
                查看全部 →
              </button>
            </div>
          </div>
        )}

        {/* Dropdown: empty results */}
        {showDropdown && !searchLoading && searchValue.trim() && groups.length === 0 && (
          <div className="hp-search-dropdown">
            <div className="hp-search-dropdown-empty">未找到相关结果</div>
          </div>
        )}

        {/* Dropdown: recent searches + recommendations (empty input, focused) */}
        {showDropdown && !searchLoading && !searchValue.trim() && (
          <div className="hp-search-dropdown">
            {recentSearches.length > 0 && (
              <div className="hp-search-dropdown-group">
                <div className="hp-search-dropdown-group-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>最近搜索</span>
                  <button
                    className="hp-search-dropdown-clear-recent"
                    onClick={(e) => { e.stopPropagation(); clearRecentSearches(); }}
                    style={{ border: "none", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: 11 }}
                  >
                    清空
                  </button>
                </div>
                {recentSearches.map((kw, i) => (
                  <div
                    key={i}
                    className="hp-search-dropdown-item"
                    onClick={() => {
                      setSearchValue(kw);
                      setShowDropdown(false);
                      saveRecentSearch(kw);
                      setRecentSearches(getRecentSearches());
                      if (onSearch) onSearch(kw);
                    }}
                    onMouseEnter={() => setActiveIndex(i)}
                    style={activeIndex === i ? { background: "#f1f5f9" } : {}}
                  >
                    <div className="hp-search-dropdown-item-header">
                      <span className="hp-search-dropdown-item-title" style={{ color: "#475569" }}>🕐 {kw}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="hp-search-dropdown-group">
              <div className="hp-search-dropdown-group-title">推荐入口</div>
              {RECOMMEND_ENTRIES.map((entry, i) => {
                const offset = recentSearches.length;
                return (
                  <div
                    key={entry.id}
                    className="hp-search-dropdown-item"
                    onClick={() => {
                      setShowDropdown(false);
                      if (onSearch) onSearch(null, { target: { page: entry.id } });
                    }}
                    onMouseEnter={() => setActiveIndex(offset + i)}
                    style={activeIndex === offset + i ? { background: "#f1f5f9" } : {}}
                  >
                    <div className="hp-search-dropdown-item-header">
                      <span className="hp-search-dropdown-item-title" style={{ color: "#475569" }}>
                        {entry.icon} {entry.label}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
      <div className="hp-topbar-actions">
        <button className="hp-icon-btn" title="通知">
          <span className="hp-icon-bell">🔔</span>
          <span className="hp-badge">3</span>
        </button>
        <div className="hp-topbar-user hp-clickable" onClick={onProfileClick} title="个人主页">
          {hasCustomAvatar ? (
            <img
              className="hp-topbar-avatar"
              src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`}
              alt="头像"
            />
          ) : (
            <div className="hp-topbar-avatar" style={{ background: avatarObj.background }}>
              {(user?.nickname || user?.username || "?").charAt(0)}
            </div>
          )}
          <span className="hp-topbar-username">{user?.nickname || user?.username || "admin"}</span>
        </div>
      </div>
    </header>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   HERO SECTION
   ═══════════════════════════════════════════════════════════════════════════ */

function HeroSection({ user, greeting, onStartLearning, onGoPractice }) {
  return (
    <section className="hp-hero">
      <div className="hp-hero-content">
        <div className="hp-hero-text">
          <h1 className="hp-hero-greeting">
            Hi, {user?.nickname || user?.username || "同学"}，{greeting.text}
            <span style={{ marginLeft: 6 }}>{greeting.emoji}</span>
          </h1>
          <p className="hp-hero-subtitle">{greeting.subtitle}</p>
        </div>
        <div className="hp-hero-actions">
          <button className="hp-btn-primary" onClick={onStartLearning}>
            <span>🚀</span> 开始学习
          </button>
          <button className="hp-btn-secondary" onClick={onGoPractice}>
            <span>📝</span> 去练习
          </button>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SUMMARY GRID — stat cards below hero
   ═══════════════════════════════════════════════════════════════════════════ */

function SummaryGrid({ stats }) {
  const masteryPct = stats.average_mastery ?? null;
  const taskProgress = stats.total_tasks > 0
    ? Math.round((stats.completed_tasks / stats.total_tasks) * 100)
    : null;

  return (
    <div className="hp-summary-grid">
      <div className="hp-stat-card">
        <div className="hp-stat-card-top">
          <div className="hp-stat-icon-wrap">
            <span className="hp-stat-icon">📖</span>
          </div>
          {masteryPct !== null && <span className="hp-stat-trend up">已掌握</span>}
        </div>
        <div className="hp-stat-info">
          {masteryPct !== null ? (
            <div className="hp-stat-value">{masteryPct}%</div>
          ) : (
            <div className="hp-stat-empty">暂无数据</div>
          )}
          <div className="hp-stat-label">学习进度</div>
        </div>
        {masteryPct !== null && (
          <div className="hp-stat-bar">
            <div className="hp-stat-bar-fill" style={{ width: `${masteryPct}%` }} />
          </div>
        )}
      </div>

      <div className="hp-stat-card">
        <div className="hp-stat-card-top">
          <div className="hp-stat-icon-wrap">
            <span className="hp-stat-icon">🎯</span>
          </div>
          {taskProgress !== null && <span className="hp-stat-trend up">任务完成率</span>}
        </div>
        <div className="hp-stat-info">
          {taskProgress !== null ? (
            <div className="hp-stat-value">{taskProgress}%</div>
          ) : (
            <div className="hp-stat-empty">暂无数据</div>
          )}
          <div className="hp-stat-label">今日目标</div>
        </div>
        {taskProgress !== null && (
          <div className="hp-stat-bar">
            <div className="hp-stat-bar-fill" style={{ width: `${taskProgress}%` }} />
          </div>
        )}
      </div>

      <div className="hp-stat-card">
        <div className="hp-stat-card-top">
          <div className="hp-stat-icon-wrap">
            <span className="hp-stat-icon">⏱️</span>
          </div>
        </div>
        <div className="hp-stat-info">
          <div className="hp-stat-empty">暂无数据</div>
          <div className="hp-stat-label">学习时长</div>
        </div>
        <div className="hp-stat-hint">
          尚未开始记录学习时长
        </div>
      </div>

      <div className="hp-stat-card">
        <div className="hp-stat-card-top">
          <div className="hp-stat-icon-wrap">
            <span className="hp-stat-icon">💡</span>
          </div>
          {stats.total_questions > 0 && (
            <span className="hp-stat-trend up">+{stats.today_questions} 今日</span>
          )}
        </div>
        <div className="hp-stat-info">
          <div className="hp-stat-value">{stats.total_questions}</div>
          <div className="hp-stat-label">提问次数</div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   CORE FEATURES
   ═══════════════════════════════════════════════════════════════════════════ */

function CoreFeatures({ onNavigate }) {
  const features = [
    { id: "chat", icon: "💬", title: "AI 智能问答", desc: "随时向 AI 提问，获取知识点讲解、解题思路和学习建议", color: "#2563eb" },
    { id: "dashboard", icon: "📋", title: "课程工作台", desc: "管理你的学习资料、聊天记录和学习进度", color: "#059669" },
    { id: "practiceCenter", icon: "📝", title: "练习中心", desc: "按知识点刷题练习，AI 自动反馈，支持选择题和简答题", color: "#7c3aed" },
    { id: "codeStudio", icon: "</>", title: "编程学习助手", desc: "在线练习编程，AI 帮你分析代码和解答编程问题", color: "#db2777" },
    { id: "taskCenter", icon: "✅", title: "学习任务中心", desc: "创建和管理学习任务，让 AI 帮你生成个性化学习计划", color: "#ea580c" },
    { id: "knowledgeBaseCenter", icon: "📚", title: "知识库中心", desc: "管理课程资料与知识点的关联，查看资料覆盖情况", color: "#0f766e" },
  ];

  return (
    <section className="hp-core-features">
      <div className="hp-section-header">
        <div className="hp-section-header-left">
          <h2 className="hp-section-title">核心功能</h2>
          <p className="hp-section-hint">一站式学习平台，满足你的所有学习需求</p>
        </div>
      </div>
      <div className="hp-features-grid">
        {features.map((f) => (
          <button key={f.id + f.title} className="hp-feature-card" onClick={() => onNavigate(f.id)}>
            <div
              className="hp-feature-icon"
              style={{ background: `linear-gradient(135deg, ${f.color}14, ${f.color}22)`, color: f.color }}
            >
              {f.icon}
            </div>
            <div className="hp-feature-body">
              <div className="hp-feature-title">{f.title}</div>
              <div className="hp-feature-desc">{f.desc}</div>
            </div>
            <div className="hp-feature-arrow">→</div>
          </button>
        ))}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   LEARNING TOOLS
   ═══════════════════════════════════════════════════════════════════════════ */

function LearningTools({ onNavigate }) {
  const tools = [
    { id: "learningDataCenter", icon: "📊", title: "学习数据中心", desc: "全局学习统计" },
    { id: "reviewCenter", icon: "🔄", title: "复盘中心", desc: "错题与薄弱点" },
    { id: "learningPlanCenter", icon: "📅", title: "AI 学习计划", desc: "个性化学习路径" },
    { id: "learningReportCenter", icon: "📄", title: "学习报告", desc: "周报月报总结" },
    { id: "quotaCenter", icon: "💎", title: "我的额度", desc: "用量与套餐" },
    { id: "profileEdit", icon: "⚙️", title: "学习设置", desc: "科目与目标管理" },
  ];

  return (
    <section className="hp-learning-tools">
      <div className="hp-section-header">
        <div className="hp-section-header-left">
          <h2 className="hp-section-title">学习工具</h2>
        </div>
      </div>
      <div className="hp-tools-grid">
        {tools.map((t) => (
          <button key={t.id} className="hp-tool-card" onClick={() => onNavigate(t.id)}>
            <span className="hp-tool-icon">{t.icon}</span>
            <div className="hp-tool-info">
              <div className="hp-tool-title">{t.title}</div>
              <div className="hp-tool-desc">{t.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   RECOMMENDATIONS
   ═══════════════════════════════════════════════════════════════════════════ */

const MOCK_RECOMMENDATIONS = [
  { id: 1, title: "Python 基础：列表与字典进阶", type: "course", typeLabel: "课程", duration: "45 分钟", icon: "🐍" },
  { id: 2, title: "数据结构可视化：二叉树遍历", type: "exercise", typeLabel: "练习", duration: "30 分钟", icon: "🌳" },
  { id: 3, title: "算法思维：动态规划入门", type: "course", typeLabel: "课程", duration: "60 分钟", icon: "🧩" },
  { id: 4, title: "C 语言指针深度解析", type: "material", typeLabel: "资料", duration: "25 分钟", icon: "📖" },
];

function RecommendationSection({ onNavigate }) {
  const handleRecommendStart = (item) => {
    if (item.type === "exercise") {
      onNavigate("practiceCenter");
    } else if (item.type === "material") {
      onNavigate("workspaceMaterials");
    } else {
      // course or default → go to course workbench
      onNavigate("dashboard");
    }
  };

  return (
    <section className="hp-recommendations">
      <div className="hp-section-header">
        <div className="hp-section-header-left">
          <h2 className="hp-section-title">今日推荐</h2>
          <p className="hp-section-hint">根据你的学习进度，为你精选以下内容</p>
        </div>
        <button className="hp-section-more" onClick={() => onNavigate("dashboard")}>查看全部 →</button>
      </div>
      <div className="hp-recommend-grid">
        {MOCK_RECOMMENDATIONS.map((item) => (
          <div key={item.id} className="hp-recommend-card">
            <div className="hp-recommend-icon">{item.icon}</div>
            <div className="hp-recommend-info">
              <div className="hp-recommend-title">{item.title}</div>
              <div className="hp-recommend-meta">
                <span className={`hp-recommend-type ${item.type}`}>{item.typeLabel}</span>
                <span className="hp-recommend-duration">⏱ {item.duration}</span>
              </div>
            </div>
            <button className="hp-recommend-btn" onClick={() => handleRecommendStart(item)}>开始</button>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   RIGHT INSIGHT PANEL
   ═══════════════════════════════════════════════════════════════════════════ */

function RightInsightPanel({ stats, tasks, achievements }) {
  const doneCount = tasks.filter((t) => t.done).length;
  const totalTasks = tasks.length;
  const taskPct = stats.total_tasks > 0 ? Math.round((stats.completed_tasks / stats.total_tasks) * 100) : 0;

  return (
    <aside className="hp-right-panel">
      {/* Streak */}
      <div className="hp-panel-card hp-streak-card">
        <div className="hp-panel-card-header">
          <div className="hp-panel-card-icon" style={{ background: "#fff7ed" }}>🔥</div>
          <span>连续学习</span>
        </div>
        <div className="hp-streak-flame">⚡</div>
        <div className="hp-streak-body">
          {stats.study_streak !== null && stats.study_streak !== undefined ? (
            <>
              <span className="hp-streak-count">{stats.study_streak}</span>
              <span className="hp-streak-unit">天</span>
            </>
          ) : (
            <span className="hp-streak-empty">暂无记录</span>
          )}
        </div>
        {stats.study_streak !== null && stats.study_streak !== undefined ? (
          <div className="hp-streak-milestone">
            {stats.study_streak >= 7 ? "达成周冠军！" : `还差 ${7 - stats.study_streak} 天达成周目标`}
          </div>
        ) : (
          <div className="hp-streak-milestone">开始学习第一天，加油！</div>
        )}
        <div className="hp-streak-days">
          {["一", "二", "三", "四", "五", "六", "日"].map((d, i) => {
            const activeCount = stats.study_streak !== null && stats.study_streak !== undefined
              ? stats.study_streak % 7
              : 0;
            return (
              <div key={d} className={`hp-streak-dot${i < activeCount ? " active" : ""}`}>{d}</div>
            );
          })}
        </div>
      </div>

      {/* Weekly Tasks */}
      <div className="hp-panel-card">
        <div className="hp-panel-card-header hp-task-header-row">
          <div className="hp-panel-card-icon" style={{ background: "#eff6ff" }}>📋</div>
          <span>任务进度</span>
          {stats.total_tasks > 0 && (
            <span className="hp-task-progress on-track">{stats.completed_tasks}/{stats.total_tasks}</span>
          )}
        </div>
        {stats.total_tasks > 0 ? (
          <>
            <div className="hp-task-progress-bar">
              <div className="hp-task-progress-fill" style={{ width: `${taskPct}%` }} />
            </div>
            <div className="hp-task-list">
              {stats.today_completed_tasks > 0 && (
                <div className="hp-task-item done">
                  <span className="hp-task-checkbox checked">✓</span>
                  <span className="hp-task-title">今日已完成 {stats.today_completed_tasks} 个任务</span>
                </div>
              )}
              {stats.todo_tasks > 0 && (
                <div className="hp-task-item">
                  <span className="hp-task-checkbox" />
                  <span className="hp-task-title">{stats.todo_tasks} 个任务待完成</span>
                  <span className="hp-task-priority med" />
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="hp-panel-empty">
            <div className="hp-panel-empty-icon">📭</div>
            <div className="hp-panel-empty-text">暂无任务</div>
            <div className="hp-panel-empty-hint">去任务中心创建你的第一个学习任务</div>
          </div>
        )}
      </div>

      {/* Achievements */}
      <div className="hp-panel-card">
        <div className="hp-panel-card-header">
          <div className="hp-panel-card-icon" style={{ background: "#fefce8" }}>🏆</div>
          <span>学习成就</span>
        </div>
        <div className="hp-achievement-list">
          {achievements.map((a) => (
            <div key={a.id} className={`hp-achievement-item${a.unlocked ? " unlocked" : " locked"}`}>
              <div className="hp-achievement-icon">{a.icon}</div>
              <span className="hp-achievement-label">{a.label}</span>
              {a.unlocked ? (
                <span className="hp-achievement-badge">★</span>
              ) : (
                <span className="hp-achievement-locked-icon">🔒</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* AI Tips */}
      <div className="hp-panel-card hp-ai-tips-card">
        <div className="hp-panel-card-header">
          <div className="hp-panel-card-icon" style={{ background: "#dbeafe" }}>🤖</div>
          <span>AI 今日建议</span>
        </div>
        <div className="hp-ai-tips-list">
          <div className="hp-ai-tip-item">
            <div className="hp-ai-tip-avatar">AI</div>
            <span>
              {stats.average_mastery !== null
                ? `你的当前知识掌握度为 ${stats.average_mastery}%，${stats.average_mastery < 50 ? "建议从基础知识开始巩固" : stats.average_mastery < 80 ? "继续加油，还有提升空间" : "掌握度很好，可以挑战更高难度"}。`
                : "开始你的第一次学习，AI 会为你追踪学习进度。"}
            </span>
          </div>
          <div className="hp-ai-tip-item">
            <div className="hp-ai-tip-avatar">AI</div>
            <span>
              {stats.todo_tasks > 0
                ? `你还有 ${stats.todo_tasks} 个待办任务，花一点时间完成它们吧。`
                : "尝试去练习中心做几道题，巩固你的知识。"}
            </span>
          </div>
          <div className="hp-ai-tip-item">
            <div className="hp-ai-tip-avatar">AI</div>
            <span>
              {stats.total_questions > 0
                ? `你已经向 AI 提出了 ${stats.total_questions} 个问题，继续提问吧！`
                : "试试 AI 问答功能，随时解答你的学习疑问。"}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════════ */

export default function HomePage({
  user,
  page,
  setPage,
  subject,
  setSubject,
  avatarObj,
  hasCustomAvatar,
  apiBase,
  onLogout,
  isAdmin,
  onBeforeProfileEdit,
  setSearchContext,
  setSearchNavigate,
}) {
  const [stats, setStats] = useState({
    average_mastery: null,
    total_tasks: 0,
    completed_tasks: 0,
    today_completed_tasks: 0,
    todo_tasks: 0,
    total_questions: 0,
    today_questions: 0,
    total_practice_questions: 0,
    study_streak: null,
  });
  const [statsLoading, setStatsLoading] = useState(true);

  const greeting = getGreeting();

  // Build dynamic achievements based on real stats
  const achievements = [
    {
      id: 1,
      icon: "🔥",
      label: "连续学习 7 天",
      unlocked: stats.study_streak !== null && stats.study_streak >= 7,
    },
    {
      id: 2,
      icon: "💬",
      label: "提问超 50 次",
      unlocked: stats.total_questions >= 50,
    },
    {
      id: 3,
      icon: "📚",
      label: "掌握度达 80%",
      unlocked: stats.average_mastery !== null && stats.average_mastery >= 80,
    },
    {
      id: 4,
      icon: "✅",
      label: "完成 20 个任务",
      unlocked: stats.completed_tasks >= 20,
    },
    {
      id: 5,
      icon: "🎯",
      label: "首次完成练习",
      unlocked: stats.total_practice_questions > 0,
    },
  ];

  useEffect(() => {
    if (!user?.username) {
      setStatsLoading(false);
      return;
    }
    setStatsLoading(true);
    fetch(`${apiBase}/home/summary?username=${encodeURIComponent(user.username)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch summary");
        return res.json();
      })
      .then((data) => {
        setStats({
          average_mastery: data.average_mastery,
          total_tasks: data.total_tasks ?? 0,
          completed_tasks: data.completed_tasks ?? 0,
          today_completed_tasks: data.today_completed_tasks ?? 0,
          todo_tasks: data.todo_tasks ?? 0,
          total_questions: data.total_questions ?? 0,
          today_questions: data.today_questions ?? 0,
          total_practice_questions: data.total_practice_questions ?? 0,
          study_streak: data.study_streak,
        });
      })
      .catch(() => {
        // On error, keep default (null) stats
      })
      .finally(() => setStatsLoading(false));
  }, [user?.username, apiBase]);

  const handleNavigate = (targetPage) => {
    if (targetPage === "profileEdit") {
      if (onBeforeProfileEdit) onBeforeProfileEdit();
      setPage("profileEdit");
      return;
    }
    if (targetPage === "dashboard") {
      setSubject(subject);
    }
    setPage(targetPage);
  };

  const handleSearch = (query, resultItem) => {
    if (resultItem) {
      // Clicked a specific search result → navigate with context
      const t = resultItem.target || {};
      if (!t.page) return;
      // Set course context if needed
      if (t.courseId && typeof setSubject === "function") {
        setSubject(t.courseId);
      }
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
      setPage(t.page);
    } else if (query) {
      // Navigate to full search results page
      if (setSearchContext) setSearchContext({ q: query });
      setPage("searchResults");
    }
  };

  return (
    <div className="hp-content-area">
      <TopBar
        user={user}
        avatarObj={avatarObj}
        hasCustomAvatar={hasCustomAvatar}
        apiBase={apiBase}
        onProfileClick={() => setPage("profile")}
        onSearch={handleSearch}
      />
      <div className="hp-content">
        <div className="hp-content-left">
          <HeroSection
            user={user}
            greeting={greeting}
            onStartLearning={() => { setSubject(subject); setPage("dashboard"); }}
            onGoPractice={() => setPage("practiceCenter")}
          />
          <CoreFeatures onNavigate={handleNavigate} />
          <LearningTools onNavigate={handleNavigate} />
          <RecommendationSection onNavigate={handleNavigate} />
        </div>
        <RightInsightPanel stats={stats} tasks={[]} achievements={achievements} />
      </div>
      {statsLoading && (
        <div className="hp-loading-overlay">
          <div className="hp-loading-spinner" />
        </div>
      )}
    </div>
  );
}
