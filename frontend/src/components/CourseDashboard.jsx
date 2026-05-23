export default function CourseDashboard({
  course,
  courseOptions,
  dashboard,
  loading,
  savingPointKey,
  onCourseChange,
  onProgressChange,
  onOpenMaterial,
  onOpenChat,
  onStartAsk,
  onUploadMaterial,
  onViewMaterials,
  onViewLearningRecords,
  onNewCourseChat,
  getSubjectLabel,
  getFileTypeLabel,
  formatDate,
}) {
  const stats = dashboard?.stats || {};
  const progress = Array.isArray(dashboard?.progress) ? dashboard.progress : [];
  const recentMaterials = Array.isArray(dashboard?.recent_materials) ? dashboard.recent_materials : [];
  const recentChats = Array.isArray(dashboard?.recent_chats) ? dashboard.recent_chats : [];
  const statusOptions = Array.isArray(dashboard?.progress_status_options)
    ? dashboard.progress_status_options
    : ["未开始", "学习中", "已掌握", "薄弱", "待复习"];

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
        <div className="dashboard-layout">
          <section className="dashboard-card dashboard-overview">
            <div className="panel-title-row">
              <h3>当前课程概览</h3>
              <span className="subject-pill">{getSubjectLabel(course)}</span>
            </div>
            <div className="dashboard-stats-grid">
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">当前课程</div>
                <div className="dashboard-stat-value dashboard-stat-value--text">
                  {getSubjectLabel(course)}
                </div>
              </div>
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">学习进度</div>
                <div className="dashboard-stat-value">{stats.progress_percent ?? 0}%</div>
              </div>
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">资料数量</div>
                <div className="dashboard-stat-value">{stats.materials_count ?? 0}</div>
              </div>
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">历史对话数量</div>
                <div className="dashboard-stat-value">{stats.chat_count ?? 0}</div>
              </div>
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">待复习数量</div>
                <div className="dashboard-stat-value">{stats.pending_review_count ?? 0}</div>
              </div>
              <div className="dashboard-stat-card">
                <div className="dashboard-stat-label">最近学习时间</div>
                <div className="dashboard-stat-value dashboard-stat-value--text">
                  {dashboard?.recent_learning_at
                    ? formatDate(dashboard.recent_learning_at)
                    : "暂无"}
                </div>
              </div>
            </div>
          </section>

          <section className="dashboard-card dashboard-suggestion-card">
            <div className="panel-title-row">
              <h3>今日学习建议</h3>
            </div>
            <p className="dashboard-suggestion-text">
              今日建议：
              {dashboard?.suggestion || "建议先从一个基础问题开始提问。"}
            </p>
          </section>

          <section className="dashboard-card dashboard-actions-card">
            <div className="panel-title-row">
              <h3>快捷操作</h3>
            </div>
            <div className="dashboard-action-grid">
              <button className="ghost-button compact" onClick={onStartAsk}>
                开始提问
              </button>
              <button className="ghost-button compact" onClick={onUploadMaterial}>
                上传资料
              </button>
              <button className="ghost-button compact" onClick={onViewMaterials}>
                查看资料库
              </button>
              <button className="ghost-button compact" onClick={onViewLearningRecords}>
                查看学习记录
              </button>
              <button className="primary-button compact" onClick={onNewCourseChat}>
                新建本课程对话
              </button>
            </div>
          </section>

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

          <section className="dashboard-card dashboard-materials-card">
            <div className="panel-title-row">
              <h3>当前课程资料</h3>
              <button className="tiny-button" onClick={onViewMaterials}>
                查看全部
              </button>
            </div>
            <div className="dashboard-mini-stats">
              <span>资料总数：{stats.materials_count ?? 0}</span>
              <span>PDF：{stats.pdf_count ?? 0}</span>
              <span>图片：{stats.image_count ?? 0}</span>
            </div>
            {recentMaterials.length === 0 ? (
              <div className="empty-inline">当前课程还没有资料，建议先上传课程资料。</div>
            ) : (
              <div className="material-list">
                {recentMaterials.map((material) => (
                  <div key={material.id} className="material-item material-item--profile">
                    <div className="material-item-head">
                      <div className="material-title">{material.original_filename}</div>
                      <span className="subject-pill small">
                        {getFileTypeLabel(material.file_type)}
                      </span>
                    </div>
                    <div className="history-meta">{formatDate(material.created_at)}</div>
                    <div className="material-actions">
                      <button
                        className="tiny-button"
                        onClick={() => onOpenMaterial(material.id)}
                      >
                        查看资料
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="dashboard-card dashboard-chats-card">
            <div className="panel-title-row">
              <h3>当前课程最近对话</h3>
            </div>
            {recentChats.length === 0 ? (
              <div className="empty-inline">当前课程还没有历史对话，建议先从基础问题开始。</div>
            ) : (
              <div className="history-list">
                {recentChats.map((chat) => (
                  <div key={chat.id} className="history-item dashboard-chat-item">
                    <div className="history-subject">{getSubjectLabel(chat.subject || chat.course)}</div>
                    <div className="history-title">{chat.title}</div>
                    <div className="history-meta">{formatDate(chat.created_at)}</div>
                    <div className="history-actions">
                      <button className="tiny-button" onClick={() => onOpenChat(chat)}>
                        点击打开
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
