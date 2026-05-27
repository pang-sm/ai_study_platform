import { useState } from "react";
import "./HomePage.css";

/* ── Mock data ── */

const MOCK_STATS = {
  coursesCompleted: 12,
  totalCourses: 20,
  studyHours: 48.5,
  questionsAsked: 156,
  streakDays: 7,
  todayGoalMinutes: 90,
  todayCompletedMinutes: 45,
};

const MOCK_WEEKLY_TASKS = [
  { id: 1, title: "完成 Python 函数章节练习", done: true, priority: "high" },
  { id: 2, title: "复习数据结构 - 链表部分", done: true, priority: "high" },
  { id: 3, title: "阅读《算法导论》第3章", done: false, priority: "med" },
  { id: 4, title: "完成 AI 推荐练习题组", done: false, priority: "med" },
  { id: 5, title: "整理本周错题笔记", done: false, priority: "low" },
];

const MOCK_ACHIEVEMENTS = [
  { id: 1, icon: "🔥", label: "连续学习 7 天", unlocked: true },
  { id: 2, icon: "💬", label: "提问超 100 次", unlocked: true },
  { id: 3, icon: "📚", label: "完成 10 门课程", unlocked: true },
  { id: 4, icon: "⭐", label: "代码练习 50 次", unlocked: false },
  { id: 5, icon: "🏅", label: "周榜前十名", unlocked: false },
];

const MOCK_AI_TIPS = [
  "复习一下「函数」相关的错题，能帮你巩固薄弱环节。",
  "建议花 15 分钟做一道算法题，保持编程手感。",
  "你的数据结构掌握度已达 72%，继续加油！",
];

const MOCK_RECOMMENDATIONS = [
  { id: 1, title: "Python 基础：列表与字典进阶", type: "course", typeLabel: "课程", duration: "45 分钟", icon: "🐍" },
  { id: 2, title: "数据结构可视化：二叉树遍历", type: "exercise", typeLabel: "练习", duration: "30 分钟", icon: "🌳" },
  { id: 3, title: "算法思维：动态规划入门", type: "course", typeLabel: "课程", duration: "60 分钟", icon: "🧩" },
  { id: 4, title: "C 语言指针深度解析", type: "material", typeLabel: "资料", duration: "25 分钟", icon: "📖" },
];

/* ═══════════════════════════════════════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════════════════════════════════════ */

function Sidebar({ user, page, onNavigate, onLogout, isAdmin }) {
  const mainNav = [
    { id: "home", icon: "🏠", label: "首页" },
    { id: "dashboard", icon: "💬", label: "AI 问答" },
  ];

  const studyNav = [
    { id: "dashboard", icon: "📋", label: "课程工作台" },
    { id: "practiceCenter", icon: "📝", label: "练习中心" },
    { id: "codeStudio", icon: "</>", label: "编程助手" },
    { id: "taskCenter", icon: "✅", label: "学习任务" },
  ];

  const resourceNav = [
    { id: "knowledgeBaseCenter", icon: "📚", label: "资料库" },
    { id: "learningReportCenter", icon: "📄", label: "学习报告" },
    ...(isAdmin ? [{ id: "adminCenter", icon: "🛡️", label: "管理后台" }] : []),
  ];

  return (
    <aside className="hp-sidebar">
      {/* Logo */}
      <div className="hp-sidebar-header">
        <div className="hp-logo">
          <div className="hp-logo-icon">🧠</div>
          <span className="hp-logo-text">AI 学习助手</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="hp-sidebar-nav">
        {mainNav.map((item) => (
          <button
            key={item.id + item.label}
            className={`hp-nav-item${page === item.id && item.label === "首页" ? " active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="hp-nav-icon">{item.icon}</span>
            <span className="hp-nav-label">{item.label}</span>
          </button>
        ))}

        <div className="hp-nav-section-label">学习</div>
        {studyNav.map((item) => (
          <button
            key={item.id + item.label}
            className="hp-nav-item"
            onClick={() => onNavigate(item.id)}
          >
            <span className="hp-nav-icon">{item.icon}</span>
            <span className="hp-nav-label">{item.label}</span>
          </button>
        ))}

        <div className="hp-nav-section-label">资源</div>
        {resourceNav.map((item) => (
          <button
            key={item.id + item.label}
            className="hp-nav-item"
            onClick={() => onNavigate(item.id)}
          >
            <span className="hp-nav-icon">{item.icon}</span>
            <span className="hp-nav-label">{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="hp-sidebar-footer">
        {/* Premium upgrade card */}
        <div className="hp-premium-card">
          <div className="hp-premium-top">
            <span className="hp-premium-icon">👑</span>
            <span className="hp-premium-title">升级会员</span>
          </div>
          <div className="hp-premium-desc">解锁无限 AI 问答和更多高级功能</div>
          <button className="hp-premium-btn">立即升级</button>
        </div>

        {/* User row */}
        <div className="hp-sidebar-user-row">
          <div className="hp-sidebar-avatar">
            {(user?.nickname || user?.username || "A").charAt(0)}
          </div>
          <div className="hp-sidebar-user-info">
            <div className="hp-sidebar-user-name">
              {user?.nickname || user?.username || "admin"}
            </div>
            <div className="hp-sidebar-user-role">
              {user?.grade || "学习者"}
            </div>
          </div>
        </div>

        <div className="hp-sidebar-divider" />

        <button className="hp-logout-btn" onClick={onLogout}>
          退出登录
        </button>
      </div>
    </aside>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   TOPBAR
   ═══════════════════════════════════════════════════════════════════════════ */

function TopBar({ user, avatarObj, hasCustomAvatar, apiBase, onAvatarClick }) {
  return (
    <header className="hp-topbar">
      <div className="hp-topbar-search">
        <span className="hp-search-icon">🔍</span>
        <input
          className="hp-search-input"
          type="text"
          placeholder="搜索课程、资料、知识点..."
        />
      </div>
      <div className="hp-topbar-actions">
        <button className="hp-icon-btn" title="通知">
          <span className="hp-icon-bell">🔔</span>
          <span className="hp-badge">3</span>
        </button>
        <div
          className="hp-topbar-user"
          onClick={onAvatarClick}
          title="点击更换头像"
        >
          {hasCustomAvatar ? (
            <img
              className="hp-topbar-avatar"
              src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`}
              alt="头像"
            />
          ) : (
            <div
              className="hp-topbar-avatar"
              style={{ background: avatarObj.background }}
            >
              {(user?.nickname || user?.username || "?").charAt(0)}
            </div>
          )}
          <span className="hp-topbar-username">
            {user?.nickname || user?.username || "admin"}
          </span>
        </div>
      </div>
    </header>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   HERO SECTION
   ═══════════════════════════════════════════════════════════════════════════ */

function HeroSection({ user, stats, onStartLearning, onAiChat }) {
  const progressPct = stats.totalCourses > 0
    ? Math.round((stats.coursesCompleted / stats.totalCourses) * 100)
    : 0;
  const todayPct = stats.todayGoalMinutes > 0
    ? Math.round((stats.todayCompletedMinutes / stats.todayGoalMinutes) * 100)
    : 0;

  return (
    <section className="hp-hero">
      <div className="hp-hero-grid-lines" />
      <div className="hp-hero-top">
        <div className="hp-hero-text">
          <h1 className="hp-hero-greeting">
            {user?.nickname || user?.username || "同学"}，早上好
            <span style={{ marginLeft: 6 }}>👋</span>
          </h1>
          <p className="hp-hero-subtitle">
            新的一天，继续你的学习之旅。今天的目标是掌握一个新知识点！
          </p>
        </div>

        {/* Illustration area */}
        <div className="hp-hero-illustration">
          {/* Code card */}
          <div className="hp-illust-card">
            <div className="hp-illust-card-header">
              <div className="hp-illust-card-dot" style={{ background: "#ef4444" }} />
              <div className="hp-illust-card-dot" style={{ background: "#f59e0b" }} />
              <div className="hp-illust-card-dot" style={{ background: "#22c55e" }} />
            </div>
            <div className="hp-illust-card-lines">
              <div className="hp-illust-card-line" style={{ width: "80%" }} />
              <div className="hp-illust-card-line" style={{ width: "55%", marginLeft: 8 }} />
              <div className="hp-illust-card-line" style={{ width: "68%" }} />
              <div className="hp-illust-card-line" style={{ width: "42%", marginLeft: 8 }} />
            </div>
          </div>

          {/* Tags */}
          <div className="hp-illust-tags">
            <span className="hp-illust-tag" style={{ background: "rgba(255,255,255,0.18)", color: "#fff" }}>
              {"</> C++"}
            </span>
            <span className="hp-illust-tag" style={{ background: "rgba(255,255,255,0.18)", color: "#fff" }}>
              {"</> Python"}
            </span>
            <span className="hp-illust-tag" style={{ background: "rgba(255,255,255,0.18)", color: "#fff" }}>
              {"</> C"}
            </span>
          </div>

          {/* Book */}
          <div className="hp-illust-book">📘</div>
        </div>

        <div className="hp-hero-actions">
          <button className="hp-btn-primary" onClick={onStartLearning}>
            <span>🚀</span> 开始学习
          </button>
          <button className="hp-btn-secondary" onClick={onAiChat}>
            <span>🤖</span> AI 问答
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="hp-hero-stats">
        <div className="hp-stat-card">
          <div className="hp-stat-card-top">
            <div className="hp-stat-icon-wrap">
              <span className="hp-stat-icon">📖</span>
            </div>
            <span className="hp-stat-trend up">+8%</span>
          </div>
          <div className="hp-stat-info">
            <div className="hp-stat-value">{progressPct}%</div>
            <div className="hp-stat-label">学习进度</div>
          </div>
          <div className="hp-stat-bar">
            <div className="hp-stat-bar-fill" style={{ width: `${progressPct}%` }} />
          </div>
        </div>

        <div className="hp-stat-card">
          <div className="hp-stat-card-top">
            <div className="hp-stat-icon-wrap">
              <span className="hp-stat-icon">🎯</span>
            </div>
            <span className="hp-stat-trend up">+5%</span>
          </div>
          <div className="hp-stat-info">
            <div className="hp-stat-value">{todayPct}%</div>
            <div className="hp-stat-label">今日目标</div>
          </div>
          <div className="hp-stat-bar">
            <div className="hp-stat-bar-fill" style={{ width: `${todayPct}%` }} />
          </div>
        </div>

        <div className="hp-stat-card">
          <div className="hp-stat-card-top">
            <div className="hp-stat-icon-wrap">
              <span className="hp-stat-icon">⏱️</span>
            </div>
            <span className="hp-stat-trend up">+12h</span>
          </div>
          <div className="hp-stat-info">
            <div className="hp-stat-value">{stats.studyHours}h</div>
            <div className="hp-stat-label">学习时长</div>
          </div>
        </div>

        <div className="hp-stat-card">
          <div className="hp-stat-card-top">
            <div className="hp-stat-icon-wrap">
              <span className="hp-stat-icon">💡</span>
            </div>
            <span className="hp-stat-trend up">+23</span>
          </div>
          <div className="hp-stat-info">
            <div className="hp-stat-value">{stats.questionsAsked}</div>
            <div className="hp-stat-label">提问次数</div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   CORE FEATURES
   ═══════════════════════════════════════════════════════════════════════════ */

function CoreFeatures({ onNavigate }) {
  const features = [
    { id: "dashboard", icon: "💬", title: "AI 智能问答", desc: "随时向 AI 提问，获取知识点讲解、解题思路和学习建议", color: "#2563eb" },
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
          <button
            key={f.id + f.title}
            className="hp-feature-card"
            onClick={() => onNavigate(f.id)}
          >
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
          <button
            key={t.id}
            className="hp-tool-card"
            onClick={() => onNavigate(t.id)}
          >
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

function RecommendationSection() {
  return (
    <section className="hp-recommendations">
      <div className="hp-section-header">
        <div className="hp-section-header-left">
          <h2 className="hp-section-title">今日推荐</h2>
          <p className="hp-section-hint">根据你的学习进度，为你精选以下内容</p>
        </div>
        <button className="hp-section-more">查看全部 →</button>
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
            <button className="hp-recommend-btn">开始</button>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   RIGHT INSIGHT PANEL
   ═══════════════════════════════════════════════════════════════════════════ */

function RightInsightPanel({ stats, tasks, achievements, aiTips }) {
  const doneCount = tasks.filter((t) => t.done).length;
  const totalTasks = tasks.length;
  const taskPct = Math.round((doneCount / totalTasks) * 100);
  const taskOnTrack = taskPct >= 30;

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
          <span className="hp-streak-count">{stats.streakDays}</span>
          <span className="hp-streak-unit">天</span>
        </div>
        <div className="hp-streak-milestone">
          {stats.streakDays >= 7 ? "达成周冠军！" : `还差 ${7 - stats.streakDays} 天达成周目标`}
        </div>
        <div className="hp-streak-days">
          {["一", "二", "三", "四", "五", "六", "日"].map((d, i) => (
            <div
              key={d}
              className={`hp-streak-dot${i < stats.streakDays % 7 || (i === 0 && stats.streakDays % 7 === 0 && stats.streakDays > 0) ? " active" : ""}`}
            >
              {d}
            </div>
          ))}
        </div>
      </div>

      {/* Weekly Tasks */}
      <div className="hp-panel-card">
        <div className="hp-panel-card-header hp-task-header-row">
          <div className="hp-panel-card-icon" style={{ background: "#eff6ff" }}>📋</div>
          <span>本周任务</span>
          <span className={`hp-task-progress ${taskOnTrack ? "on-track" : "behind"}`}>
            {doneCount}/{totalTasks}
          </span>
        </div>
        <div className="hp-task-progress-bar">
          <div className="hp-task-progress-fill" style={{ width: `${taskPct}%` }} />
        </div>
        <div className="hp-task-list">
          {tasks.map((task) => (
            <label key={task.id} className={`hp-task-item${task.done ? " done" : ""}`}>
              <span className={`hp-task-checkbox${task.done ? " checked" : ""}`}>
                {task.done ? "✓" : ""}
              </span>
              <span className="hp-task-title">{task.title}</span>
              <span className={`hp-task-priority ${task.priority}`} />
            </label>
          ))}
        </div>
      </div>

      {/* Achievements */}
      <div className="hp-panel-card">
        <div className="hp-panel-card-header">
          <div className="hp-panel-card-icon" style={{ background: "#fefce8" }}>🏆</div>
          <span>学习成就</span>
        </div>
        <div className="hp-achievement-list">
          {achievements.map((a) => (
            <div
              key={a.id}
              className={`hp-achievement-item${a.unlocked ? " unlocked" : " locked"}`}
            >
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
          {aiTips.map((tip, i) => (
            <div key={i} className="hp-ai-tip-item">
              <div className="hp-ai-tip-avatar">AI</div>
              <span>{tip}</span>
            </div>
          ))}
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
  onAvatarClick,
  onLogout,
  isAdmin,
  onBeforeProfileEdit,
}) {
  const [stats] = useState(MOCK_STATS);
  const [tasks] = useState(MOCK_WEEKLY_TASKS);
  const [achievements] = useState(MOCK_ACHIEVEMENTS);
  const [aiTips] = useState(MOCK_AI_TIPS);

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

  return (
    <div className="hp-shell">
      <Sidebar
        user={user}
        page={page}
        onNavigate={handleNavigate}
        onLogout={onLogout}
        isAdmin={isAdmin}
      />
      <div className="hp-main">
        <TopBar
          user={user}
          avatarObj={avatarObj}
          hasCustomAvatar={hasCustomAvatar}
          apiBase={apiBase}
          onAvatarClick={onAvatarClick}
        />
        <div className="hp-content">
          <div className="hp-content-left">
            <HeroSection
              user={user}
              stats={stats}
              onStartLearning={() => { setSubject(subject); setPage("dashboard"); }}
              onAiChat={() => { setSubject(subject); setPage("dashboard"); }}
            />
            <CoreFeatures onNavigate={handleNavigate} />
            <LearningTools onNavigate={handleNavigate} />
            <RecommendationSection />
          </div>
          <RightInsightPanel
            stats={stats}
            tasks={tasks}
            achievements={achievements}
            aiTips={aiTips}
          />
        </div>
      </div>
    </div>
  );
}
