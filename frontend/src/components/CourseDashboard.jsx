import KnowledgeRoadmap from "./KnowledgeRoadmap.jsx";

export default function CourseDashboard({
  user,
  course,
  courseOptions,
  dashboard,
  loading,
  savingPointKey,
  setPage,
  onCourseChange,
  onProgressChange,
  onStartAsk,
  onOpenCodeStudio,
  onOpenPracticeCenter,
  getSubjectLabel,
  formatDate,
}) {
  const stats = dashboard?.stats || {};
  const progress = Array.isArray(dashboard?.progress) ? dashboard.progress : [];
  const statusOptions = Array.isArray(dashboard?.progress_status_options)
    ? dashboard.progress_status_options
    : ["未开始", "学习中", "已掌握", "薄弱", "待复习"];

  const progressPct = stats.progress_percent ?? 0;

  return (
    <section className="chat-panel chat-panel--wide dashboard-panel">
      <div className="panel-header panel-header--chat dashboard-header">
        <div>
          <div className="subject-pill panel-pill">课程学习工作台</div>
          <h2>课程学习工作台</h2>
        </div>
        <div className="dashboard-course-picker">
          <label className="field-label">当前课程</label>
          <select
            className="field"
            value={course}
            onChange={(event) => onCourseChange(event.target.value)}
          >
            {courseOptions.map((item) => (
              <option key={item} value={item}>
                {getSubjectLabel(item)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="empty-state">课程工作台加载中...</div>
      ) : (
        <div className="doh-layout">
          {/* ── Block 1: Course overview card ── */}
          <section className="doh-overview-card">
            <div className="doh-overview-header">
              <h3>{getSubjectLabel(course)}</h3>
              <span className="subject-pill">当前课程</span>
            </div>

            <div className="doh-progress-section">
              <div className="doh-progress-header">
                <span className="doh-progress-label">学习进度</span>
                <span className="doh-progress-pct">{progressPct}%</span>
              </div>
              <div className="doh-progress-bar">
                <div
                  className="doh-progress-fill"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>

            <div className="doh-mini-stats">
              <div className="doh-mini-stat">
                <span className="doh-mini-stat-value">{stats.materials_count ?? 0}</span>
                <span className="doh-mini-stat-label">资料</span>
              </div>
              <div className="doh-mini-stat">
                <span className="doh-mini-stat-value">{stats.chat_count ?? 0}</span>
                <span className="doh-mini-stat-label">对话</span>
              </div>
              <div className="doh-mini-stat">
                <span className="doh-mini-stat-value">{stats.pending_review_count ?? 0}</span>
                <span className="doh-mini-stat-label">待复习</span>
              </div>
              <div className="doh-mini-stat doh-mini-stat--wide">
                <span className="doh-mini-stat-value doh-mini-stat-value--text">
                  {dashboard?.recent_learning_at
                    ? formatDate(dashboard.recent_learning_at)
                    : "暂无"}
                </span>
                <span className="doh-mini-stat-label">最近学习</span>
              </div>
            </div>
          </section>

          {/* ── Block 2: Course feature navigation cards ── */}
          <section className="doh-nav-section">
            <h3 className="doh-nav-section-title">课程功能</h3>
            <div className="doh-nav-grid">
              <button className="doh-nav-card" onClick={onStartAsk}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #eff6ff, #dbeafe)", color: "#2563eb" }}>
                  💬
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">AI 问答</div>
                  <div className="doh-nav-desc">基于课程资料智能提问</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>

              <button className="doh-nav-card" onClick={() => setPage("workspaceMaterials")}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #f0fdf4, #dcfce7)", color: "#059669" }}>
                  📚
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">资料库</div>
                  <div className="doh-nav-desc">管理课程 PDF、图片与文档</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>

              <button className="doh-nav-card" onClick={() => setPage("records")}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #fef3c7, #fde68a)", color: "#d97706" }}>
                  📝
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">学习记录</div>
                  <div className="doh-nav-desc">查看本课程学习轨迹</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>

              <button className="doh-nav-card" onClick={() => setPage("history")}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #f5f3ff, #ede9fe)", color: "#7c3aed" }}>
                  📋
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">历史对话</div>
                  <div className="doh-nav-desc">回顾课程问答记录</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>

              <button className="doh-nav-card" onClick={onOpenPracticeCenter}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #fef2f2, #fecaca)", color: "#dc2626" }}>
                  🎯
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">练习中心</div>
                  <div className="doh-nav-desc">做题练习与薄弱点巩固</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>

              <button className="doh-nav-card" onClick={onOpenCodeStudio}>
                <div className="doh-nav-icon" style={{ background: "linear-gradient(135deg, #ecfdf5, #d1fae5)", color: "#0f766e" }}>
                  💻
                </div>
                <div className="doh-nav-body">
                  <div className="doh-nav-title">编程助手</div>
                  <div className="doh-nav-desc">在线编程练习与 AI 辅导</div>
                </div>
                <div className="doh-nav-arrow">→</div>
              </button>
            </div>
          </section>

          {/* ── Knowledge roadmap ── */}
          <KnowledgeRoadmap
            user={user}
            course={course}
            getSubjectLabel={getSubjectLabel}
          />

          {/* ── Learning progress list ── */}
          {progress.length > 0 && (
            <section className="dashboard-card dashboard-progress-card">
              <div className="panel-title-row">
                <h3>课程学习路线</h3>
                <span className="history-meta">共 {progress.length} 个知识点</span>
              </div>
              <div className="dashboard-progress-list">
                {progress.map((item, index) => {
                  const pointKey = `${course}-${item.knowledge_point}`;
                  const saving = savingPointKey === pointKey;
                  return (
                    <div key={item.knowledge_point} className="dashboard-progress-item">
                      <div className="dashboard-progress-main">
                        <div className="dashboard-progress-index">{index + 1}</div>
                        <div>
                          <div className="dashboard-progress-point">{item.knowledge_point}</div>
                          <div className="history-meta">当前状态：{item.status}</div>
                        </div>
                      </div>
                      <select
                        className="field dashboard-progress-select"
                        value={item.status}
                        onChange={(event) =>
                          onProgressChange(item.knowledge_point, event.target.value)
                        }
                        disabled={saving}
                      >
                        {statusOptions.map((status) => (
                          <option key={status} value={status}>
                            {saving && status === item.status ? `保存中：${status}` : status}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      )}
    </section>
  );
}
