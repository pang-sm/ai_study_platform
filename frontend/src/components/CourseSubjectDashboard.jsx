import { useMemo, useState } from "react";
import "./CourseSubjectDashboard.css";

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "◆" },
  { key: "ai", label: "AI 问答", icon: "☵" },
  { key: "materials", label: "资料库", icon: "▣" },
  { key: "knowledge", label: "知识脉络", icon: "⌘" },
  { key: "plan", label: "学习计划", icon: "▤" },
  { key: "practice", label: "练习中心", icon: "✎" },
  { key: "report", label: "学习报告", icon: "▧" },
];

const MATERIAL_CARDS = [
  { key: "slides", label: "课件讲义", tone: "purple", match: ["ppt", "课件", "讲义", "slides"] },
  { key: "exercises", label: "习题集", tone: "blue", match: ["习题", "作业", "exercise", "homework"] },
  { key: "references", label: "参考资料", tone: "green", match: ["教材", "参考", "book", "paper"] },
  { key: "examples", label: "代码示例", tone: "orange", match: ["代码", "示例", "code", "demo"] },
];

function numberValue(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function getCourseMaterials(materials, courseName, subject, getSubjectLabel) {
  const targetNames = new Set([courseName, subject, getSubjectLabel?.(subject)].filter(Boolean));
  return (Array.isArray(materials) ? materials : []).filter((item) => {
    const itemName = getSubjectLabel?.(item.subject) || item.subject;
    return targetNames.has(item.subject) || targetNames.has(itemName);
  });
}

function countMaterialType(materials, type) {
  return materials.filter((item) => {
    const text = `${item.file_type || ""} ${item.file_name || ""} ${item.original_filename || ""} ${item.summary || ""}`.toLowerCase();
    return type.match.some((keyword) => text.includes(keyword.toLowerCase()));
  }).length;
}

function getInitials(courseName) {
  const known = {
    数据结构: "DS",
    离散数学: "DM",
    操作系统: "OS",
    计算机网络: "CN",
    计算机组成原理: "CO",
    软件工程: "SE",
    高等数学: "MA",
    线性代数: "LA",
    数据库系统: "DB",
    人工智能导论: "AI",
  };
  return known[courseName] || String(courseName || "课程").slice(0, 2).toUpperCase();
}

function formatHours(minutes) {
  const mins = numberValue(minutes);
  if (mins <= 0) return "0 小时";
  return `${(mins / 60).toFixed(1)} 小时`;
}

export default function CourseSubjectDashboard({
  user,
  course,
  dashboard,
  coursePreference,
  loading,
  setPage,
  getSubjectLabel,
  materials = [],
  onStartAsk,
}) {
  const [activePanel, setActivePanel] = useState("home");
  const stats = dashboard?.stats || {};
  const courseName = getSubjectLabel?.(course) || course || "课程学习";
  const courseMaterials = useMemo(
    () => getCourseMaterials(materials, courseName, course, getSubjectLabel),
    [materials, courseName, course, getSubjectLabel],
  );
  const learnedPercent = Math.max(0, Math.min(100, numberValue(stats.progress_percent, 24)));
  const knowledgeCount = numberValue(stats.knowledge_points_count, 86);
  const chapterCount = numberValue(stats.chapter_count || stats.modules_count, 12);
  const studyMinutes = numberValue(stats.weekly_study_minutes || stats.total_study_minutes, 1116);
  const aiRemaining = numberValue(user?.ai_quota_remaining ?? user?.quota_remaining, 42);
  const questionRemaining = numberValue(user?.question_quota_remaining ?? user?.exercise_quota_remaining, 8);
  const uploadRemaining = numberValue(user?.upload_quota_remaining ?? user?.material_upload_remaining, 6);
  const preference = coursePreference || dashboard?.preference || {};
  const focusTag = preference.learning_goal || "平日学习";

  const planItems = [
    { index: 1, title: `${courseName}核心概念复习`, desc: "第 1 章 · 基础概念", status: "已完成", done: true },
    { index: 2, title: `${courseName}重点小节学习`, desc: "第 2 章 · 课程重点", status: "继续学习", done: false },
    { index: 3, title: `${courseName}练习题整理`, desc: "第 2 章 · 巩固练习", status: "去学习", done: false },
  ];

  const knowledgeNodes = ["概念", "方法", "应用", "练习"].map((item) => ({
    label: item,
    active: item === "概念",
  }));

  const handleNav = (key) => {
    setActivePanel(key);
    if (key === "ai") onStartAsk?.();
  };

  return (
    <div className="csd-page">
      <aside className="csd-sidebar" aria-label="课程工作台导航">
        <nav className="csd-nav">
          {NAV_ITEMS.map((item) => (
            <button
              className={`csd-nav-item${activePanel === item.key ? " is-active" : ""}`}
              type="button"
              key={item.key}
              onClick={() => handleNav(item.key)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="csd-member-card">
          <strong>会员 <span>♛</span></strong>
          <p>解锁专属权益，畅享课程学习特权</p>
          <ul>
            <li>专属学习资源</li>
            <li>AI 问答优先使用</li>
            <li>学习数据深度分析</li>
            <li>更多高级功能</li>
          </ul>
          <button type="button" onClick={() => setPage?.("membership")}>了解会员权益 →</button>
        </div>

        <button className="csd-back-home" type="button" onClick={() => setPage?.("home")}>
          ↩ 返回主页
        </button>
      </aside>

      <main className="csd-main">
        <header className="csd-header">
          <div className="csd-title-block">
            <span className="csd-course-mark">{getInitials(courseName)}</span>
            <div>
              <h1>{courseName}</h1>
              <p>课程学习 / 当前科目</p>
            </div>
          </div>
          <button className="csd-profile" type="button" aria-label="个人资料">
            <span>{(user?.nickname || user?.username || "同学").charAt(0).toUpperCase()}</span>
            个人资料⌄
          </button>
        </header>

        {loading ? (
          <section className="csd-card csd-loading">课程工作台加载中...</section>
        ) : (
          <>
            <section className="csd-top-grid">
              <div className="csd-card csd-hero-card">
                <div>
                  <h2>开始今天的{courseName}学习</h2>
                  <p>坚持学习，稳步提升，攻克每一个知识点！</p>
                  <div className="csd-hero-actions">
                    <button className="is-primary" type="button">线性表</button>
                    <button type="button">栈与队列</button>
                    <button type="button">树</button>
                    <button type="button">图</button>
                  </div>
                </div>
                <div className="csd-hero-art" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>

              <div className="csd-card csd-overview-card">
                <h3>课程概览</h3>
                <div className="csd-overview-grid">
                  <div><span>总章节</span><strong>{chapterCount}<small> 个</small></strong></div>
                  <div><span>知识点</span><strong>{knowledgeCount}<small> 个</small></strong></div>
                  <div><span>已学习</span><strong>{learnedPercent}<small>%</small></strong><em style={{ width: `${learnedPercent}%` }} /></div>
                  <div><span>学习时长</span><strong>{formatHours(studyMinutes)}</strong></div>
                </div>
              </div>
            </section>

            {activePanel !== "home" && (
              <section className="csd-panel-hint">
                当前模块：<strong>{NAV_ITEMS.find((item) => item.key === activePanel)?.label}</strong>
                <span>已保持在新版课程工作台框架内，后续可接入真实模块内容。</span>
              </section>
            )}

            <section className="csd-middle-grid">
              <div className="csd-card csd-plan-card">
                <h3><span>▤</span> 今日学习计划</h3>
                <div className="csd-plan-list">
                  {planItems.map((item) => (
                    <div className="csd-plan-item" key={item.title}>
                      <span className={item.done ? "is-done" : ""}>{item.done ? "✓" : item.index}</span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.desc}</p>
                      </div>
                      <button type="button" className={item.done ? "is-complete" : ""}>{item.status}</button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="csd-card csd-material-card">
                <h3><span>▣</span> 资料库概览</h3>
                <div className="csd-material-grid">
                  {MATERIAL_CARDS.map((item) => (
                    <button className={`csd-material-item csd-material-item--${item.tone}`} type="button" key={item.key}>
                      <span>■</span>
                      <strong>{item.label}</strong>
                      <em>{countMaterialType(courseMaterials, item)} 份</em>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            <section className="csd-bottom-grid">
              <div className="csd-card csd-knowledge-card">
                <h3><span>⌘</span> 知识脉络</h3>
                <div className="csd-orbit">
                  <strong>{courseName}</strong>
                  {knowledgeNodes.map((node, index) => (
                    <span className={`csd-node csd-node--${index}${node.active ? " is-active" : ""}`} key={node.label}>
                      {node.label}
                    </span>
                  ))}
                </div>
              </div>

              <div className="csd-card csd-quota-card">
                <h3><span>▧</span> 额度剩余</h3>
                {[
                  ["AI 问答剩余", aiRemaining, 50],
                  ["AI 出题剩余", questionRemaining, 10],
                  ["资料上传剩余", uploadRemaining, 10],
                ].map(([label, value, total]) => (
                  <div className="csd-quota-row" key={label}>
                    <span>{label}</span>
                    <strong>{value} / {total}</strong>
                    <em><i style={{ width: `${Math.max(4, Math.min(100, (Number(value) / Number(total)) * 100))}%` }} /></em>
                  </div>
                ))}
                <div className="csd-course-task-tag">当前目标：{focusTag}</div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
