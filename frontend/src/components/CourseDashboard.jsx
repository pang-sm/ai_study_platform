import KnowledgeRoadmap from "./KnowledgeRoadmap.jsx";

export default function CourseDashboard({
  user,
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
  onOpenCodeStudio,
  onOpenTaskCenter,
  onOpenPracticeCenter,
  getSubjectLabel,
  getFileTypeLabel,
  formatDate,
}) {
  const stats = dashboard?.stats || {};
  const codeProgress = dashboard?.code_progress || {};
  const progress = Array.isArray(dashboard?.progress) ? dashboard.progress : [];
  const recentMaterials = Array.isArray(dashboard?.recent_materials) ? dashboard.recent_materials : [];
  const recentChats = Array.isArray(dashboard?.recent_chats) ? dashboard.recent_chats : [];
  const taskSummary = dashboard?.task_summary || {};
  const recentTasks = Array.isArray(taskSummary.recent_tasks) ? taskSummary.recent_tasks : [];
  const practiceSummary = dashboard?.practice_summary || {};
  const recentAttempts = Array.isArray(practiceSummary.recent_attempts) ? practiceSummary.recent_attempts : [];
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

          <section className="dashboard-card dashboard-task-card">
            <div className="panel-title-row">
              <h3>学习任务</h3>
            </div>
            {(taskSummary.total ?? 0) > 0 ? (
              <>
                <div className="dashboard-mini-stats">
                  <span>任务总数：{taskSummary.total ?? 0}</span>
                  <span>待完成：{taskSummary.todo_count ?? 0}</span>
                  <span>进行中：{taskSummary.doing_count ?? 0}</span>
                  <span>已完成：{taskSummary.done_count ?? 0}</span>
                </div>
                {recentTasks.length > 0 && (
                  <div className="task-mini-list">
                    {recentTasks.slice(0, 3).map((task) => (
                      <div key={task.id} className="task-mini-item">
                        <span className="task-mini-title">{task.title}</span>
                        <span className={`task-mini-status task-mini-status--${task.status}`}>
                          {task.status === "todo" ? "未开始" : task.status === "doing" ? "进行中" : "已完成"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <button
                  className="primary-button compact"
                  onClick={onOpenTaskCenter}
                  style={{ marginTop: 12 }}
                >
                  进入任务中心
                </button>
              </>
            ) : (
              <div className="empty-inline">
                <p>当前课程还没有学习任务。</p>
                <button
                  className="primary-button compact"
                  onClick={onOpenTaskCenter}
                  style={{ marginTop: 8 }}
                >
                  进入任务中心
                </button>
              </div>
            )}
          </section>

          <section className="dashboard-card dashboard-code-card">
            <div className="panel-title-row">
              <h3>编程练习统计</h3>
            </div>
            {(codeProgress.total ?? 0) > 0 ? (
              <>
                <div className="dashboard-code-stats">
                  <div className="dashboard-code-stat">
                    <div className="dashboard-code-stat-value">{codeProgress.total ?? 0}</div>
                    <div className="dashboard-code-stat-label">总练习数</div>
                  </div>
                  <div className="dashboard-code-stat">
                    <div className="dashboard-code-stat-value">{codeProgress.language_counts?.["Python"] ?? 0}</div>
                    <div className="dashboard-code-stat-label">Python</div>
                  </div>
                  <div className="dashboard-code-stat">
                    <div className="dashboard-code-stat-value">{codeProgress.language_counts?.["Java"] ?? 0}</div>
                    <div className="dashboard-code-stat-label">Java</div>
                  </div>
                  <div className="dashboard-code-stat">
                    <div className="dashboard-code-stat-value">
                      {(codeProgress.language_counts?.["C"] ?? 0) + (codeProgress.language_counts?.["C++"] ?? 0)}
                    </div>
                    <div className="dashboard-code-stat-label">C/C++</div>
                  </div>
                </div>
                {(codeProgress.challenge_count ?? 0) > 0 && (
                  <>
                    <div className="dashboard-code-recent">
                      <span className="history-meta">
                        AI 出题练习：{codeProgress.challenge_count} 道
                        {codeProgress.recent_challenge_title ? `（最近：${codeProgress.recent_challenge_title}）` : ""}
                      </span>
                    </div>
                    {(codeProgress.diagnosis_challenge_count ?? 0) > 0 && (
                      <div className="dashboard-code-recent">
                        <span className="history-meta" style={{ color: "#0f766e" }}>
                          诊断推荐题：{codeProgress.diagnosis_challenge_count} 道
                        </span>
                      </div>
                    )}
                  </>
                )}
                {codeProgress.recent_title && (
                  <div className="dashboard-code-recent">
                    <span className="history-meta">
                      最近练习：{codeProgress.recent_title}
                      {codeProgress.recent_language ? `（${codeProgress.recent_language}）` : ""}
                    </span>
                    {codeProgress.recent_updated_at && (
                      <span className="history-meta">{formatDate(codeProgress.recent_updated_at)}</span>
                    )}
                  </div>
                )}
                <button
                  className="primary-button compact"
                  onClick={onOpenCodeStudio}
                  style={{ marginTop: 12 }}
                >
                  进入编程学习助手
                </button>
              </>
            ) : (
              <div className="empty-inline">
                <p>当前课程还没有编程练习，可以前往编程学习助手开始练习。</p>
                <button
                  className="primary-button compact"
                  onClick={onOpenCodeStudio}
                  style={{ marginTop: 8 }}
                >
                  进入编程学习助手
                </button>
              </div>
            )}
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

          <KnowledgeRoadmap
            user={user}
            course={course}
            getSubjectLabel={getSubjectLabel}
          />

          <section className="dashboard-card dashboard-practice-card">
            <div className="panel-title-row">
              <h3>练习统计</h3>
              <button className="tiny-button" onClick={onOpenPracticeCenter}>
                进入练习中心
              </button>
            </div>
            {(practiceSummary.total_questions ?? 0) > 0 ? (
              <>
                <div className="dashboard-mini-stats">
                  <span>题目总数：{practiceSummary.total_questions ?? 0}</span>
                  <span>作答次数：{practiceSummary.total_attempts ?? 0}</span>
                  <span>正确数：{practiceSummary.correct_count ?? 0}</span>
                  <span>选择题：{practiceSummary.choice_count ?? 0}</span>
                  <span>简答题：{practiceSummary.short_answer_count ?? 0}</span>
                </div>
                {recentAttempts.length > 0 && (
                  <div className="task-mini-list">
                    {recentAttempts.slice(0, 3).map((a) => (
                      <div key={a.id} className="task-mini-item">
                        <span className="task-mini-title">
                          {a.question_title || `题目 #${a.question_id}`}
                        </span>
                        <span className={`task-mini-status ${
                          a.self_result === "correct" ? "task-mini-status--done"
                            : a.self_result === "incorrect" ? "task-mini-status--todo"
                            : "task-mini-status--doing"
                        }`}>
                          {a.self_result === "correct" ? "正确"
                            : a.self_result === "incorrect" ? "错误"
                            : a.self_result === "partially_correct" ? "部分正确"
                            : "未知"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="empty-inline">
                <p>当前课程还没有练习记录。</p>
                <button
                  className="primary-button compact"
                  onClick={onOpenPracticeCenter}
                  style={{ marginTop: 8 }}
                >
                  进入练习中心
                </button>
              </div>
            )}
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
