import { useMemo, useState } from "react";
import "./CourseSubjectDashboard.css";

const COURSE_TRACK = "course_learning";

const NAV_ITEMS = [
  { key: "overview", label: "首页", icon: "◆" },
  { key: "chat", label: "AI 问答", icon: "☵" },
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
    离散数学: "DM",
    软件工程: "SE",
    高等数学: "MA",
    线性代数: "LA",
    数据库系统: "DB",
    人工智能导论: "AI",
    互联网计算: "IC",
    计算机图形学: "CG",
  };
  return known[courseName] || String(courseName || "课程").slice(0, 2).toUpperCase();
}

function formatHours(minutes) {
  const mins = numberValue(minutes);
  if (mins <= 0) return "0 小时";
  return `${(mins / 60).toFixed(1)} 小时`;
}

function buildCourseId(courseName, course) {
  return String(course || courseName || "course").trim().replace(/\s+/g, "_");
}

function SectionHeader({ eyebrow, title, desc, courseName }) {
  return (
    <div className="csd-section-header">
      <span>{eyebrow}</span>
      <h2>{title}</h2>
      <p>{desc || `当前课程：${courseName}，数据隔离于课程学习体系。`}</p>
    </div>
  );
}

function EmptyState({ title, desc }) {
  return (
    <div className="csd-empty-state">
      <strong>{title}</strong>
      <p>{desc}</p>
    </div>
  );
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
}) {
  const [activeSection, setActiveSection] = useState("overview");
  const [chatDraft, setChatDraft] = useState("");
  const stats = dashboard?.stats || {};
  const courseName = getSubjectLabel?.(course) || course || "课程学习";
  const courseId = buildCourseId(courseName, course);
  const courseMaterials = useMemo(
    () => getCourseMaterials(materials, courseName, course, getSubjectLabel),
    [materials, courseName, course, getSubjectLabel],
  );
  const learnedPercent = Math.max(0, Math.min(100, numberValue(stats.progress_percent, 0)));
  const knowledgeCount = numberValue(stats.knowledge_points_count, 0);
  const chapterCount = numberValue(stats.chapter_count || stats.modules_count, 12);
  const studyMinutes = numberValue(stats.weekly_study_minutes || stats.total_study_minutes, 0);
  const aiRemaining = numberValue(user?.ai_quota_remaining ?? user?.quota_remaining, 42);
  const questionRemaining = numberValue(user?.question_quota_remaining ?? user?.exercise_quota_remaining, 8);
  const uploadRemaining = numberValue(user?.upload_quota_remaining ?? user?.material_upload_remaining, 6);
  const preference = coursePreference || dashboard?.preference || {};
  const focusTag = preference.learning_goal || "平日学习";
  const activeLabel = NAV_ITEMS.find((item) => item.key === activeSection)?.label || "首页";

  const planItems = [
    { index: 1, title: `${courseName}课程导学`, desc: "梳理课程要求与本周重点", status: "已完成", done: true },
    { index: 2, title: `${courseName}重点小节学习`, desc: "围绕当前课程资料推进", status: "继续学习", done: false },
    { index: 3, title: `${courseName}练习与复盘`, desc: "整理课堂练习、作业与错题", status: "去学习", done: false },
  ];

  const knowledgeNodes = ["课程概念", "课堂资料", "作业练习", "复盘报告"].map((item) => ({
    label: item,
    active: item === "课程概念",
  }));

  const context = { track: COURSE_TRACK, courseId, courseName };

  const renderOverview = () => (
    <>
      <section className="csd-top-grid">
        <div className="csd-card csd-hero-card">
          <div>
            <h2>开始今天的{courseName}学习</h2>
            <p>坚持学习，稳步提升，攻克每一个课程知识点！</p>
            <div className="csd-hero-actions">
              <button className="is-primary" type="button">课程导学</button>
              <button type="button">课堂资料</button>
              <button type="button">作业复盘</button>
              <button type="button">阶段测验</button>
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

      <section className="csd-middle-grid">
        {renderPlanCard()}
        {renderMaterialSummaryCard()}
      </section>

      <section className="csd-bottom-grid">
        {renderKnowledgeCard()}
        {renderQuotaCard()}
      </section>
    </>
  );

  const renderPlanCard = () => (
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
  );

  const renderMaterialSummaryCard = () => (
    <div className="csd-card csd-material-card">
      <h3><span>▣</span> 资料库概览</h3>
      <div className="csd-material-grid">
        {MATERIAL_CARDS.map((item) => (
          <button className={`csd-material-item csd-material-item--${item.tone}`} type="button" key={item.key} onClick={() => setActiveSection("materials")}>
            <span>■</span>
            <strong>{item.label}</strong>
            <em>{countMaterialType(courseMaterials, item)} 份</em>
          </button>
        ))}
      </div>
    </div>
  );

  const renderKnowledgeCard = () => (
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
  );

  const renderQuotaCard = () => (
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
  );

  const renderChatSection = () => (
    <section className="csd-section">
      <SectionHeader
        eyebrow="Course AI"
        title={`${courseName} · AI 问答`}
        desc={`提问将携带 track=${COURSE_TRACK}、courseId=${courseId}、courseName=${courseName} 的课程学习上下文。`}
        courseName={courseName}
      />
      <div className="csd-card csd-chat-card">
        <div className="csd-context-strip">
          <span>track: {context.track}</span>
          <span>courseId: {context.courseId}</span>
          <span>courseName: {context.courseName}</span>
        </div>
        <div className="csd-chat-window">
          <p className="csd-chat-bubble">你好，我会围绕《{courseName}》的课程资料、课堂笔记和学习目标回答问题，并保持在当前课程上下文中。</p>
        </div>
        <div className="csd-chat-input">
          <textarea value={chatDraft} onChange={(event) => setChatDraft(event.target.value)} placeholder={`向 ${courseName} 的课程 AI 提问...`} />
          <button type="button" disabled={!chatDraft.trim()}>发送</button>
        </div>
      </div>
    </section>
  );

  const renderMaterialsSection = () => (
    <section className="csd-section">
      <SectionHeader eyebrow="Course Library" title={`${courseName} · 资料库`} courseName={courseName} />
      <div className="csd-card csd-library-card">
        <div className="csd-context-strip">
          <span>资料作用域：{COURSE_TRACK}</span>
          <span>当前课程：{courseName}</span>
        </div>
        {courseMaterials.length > 0 ? (
          <div className="csd-material-list">
            {courseMaterials.slice(0, 8).map((item) => (
              <div className="csd-material-row" key={item.id || item.original_filename}>
                <strong>{item.original_filename || item.file_name || "未命名资料"}</strong>
                <span>{item.file_type || "course_material"}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title={`${courseName} 暂无课程资料`} desc="上传入口预留给课程学习资料库，当前只展示本课程范围内的资料内容。" />
        )}
      </div>
    </section>
  );

  const renderKnowledgeSection = () => (
    <section className="csd-section">
      <SectionHeader eyebrow="Course Knowledge" title={`${courseName} · 知识脉络`} courseName={courseName} />
      <div className="csd-knowledge-section-grid">
        {renderKnowledgeCard()}
        <div className="csd-card csd-section-side-card">
          <h3>课程知识体系状态</h3>
          <p>当前知识点数量：{knowledgeCount} 个</p>
          <EmptyState title="等待课程资料生成知识脉络" desc={`这里预留 ${courseName} 的课程知识点、章节和资料关联，并停留在课程学习工作台内。`} />
        </div>
      </div>
    </section>
  );

  const renderPlanSection = () => (
    <section className="csd-section">
      <SectionHeader eyebrow="Course Plan" title={`${courseName} · 学习计划`} courseName={courseName} />
      <div className="csd-section-single">{renderPlanCard()}</div>
    </section>
  );

  const renderPracticeSection = () => (
    <section className="csd-section">
      <SectionHeader eyebrow="Course Practice" title={`${courseName} · 练习中心`} courseName={courseName} />
      <div className="csd-practice-grid">
        {["课堂练习", "作业复盘", "AI 出题", "错题整理"].map((item) => (
          <div className="csd-card csd-practice-card" key={item}>
            <span>✎</span>
            <strong>{item}</strong>
            <p>{courseName} 专属练习入口，等待课程题库接入。</p>
          </div>
        ))}
      </div>
    </section>
  );

  const renderReportSection = () => (
    <section className="csd-section">
      <SectionHeader eyebrow="Course Report" title={`${courseName} · 学习报告`} courseName={courseName} />
      <div className="csd-report-grid">
        <div className="csd-card csd-report-card"><strong>{learnedPercent}%</strong><span>课程进度</span></div>
        <div className="csd-card csd-report-card"><strong>{formatHours(studyMinutes)}</strong><span>学习时长</span></div>
        <div className="csd-card csd-report-card"><strong>{courseMaterials.length}</strong><span>课程资料</span></div>
      </div>
      <div className="csd-card csd-report-note">
        <h3>报告数据范围</h3>
        <p>当前报告按 courseId={courseId}、track={COURSE_TRACK} 统计。暂无真实报告接口时显示课程维度 fallback，后续可直接接入课程学习报告接口。</p>
      </div>
    </section>
  );

  const renderActiveContent = () => {
    if (activeSection === "chat") return renderChatSection();
    if (activeSection === "materials") return renderMaterialsSection();
    if (activeSection === "knowledge") return renderKnowledgeSection();
    if (activeSection === "plan") return renderPlanSection();
    if (activeSection === "practice") return renderPracticeSection();
    if (activeSection === "report") return renderReportSection();
    return renderOverview();
  };

  return (
    <div className="csd-page">
      <aside className="csd-sidebar" aria-label="课程工作台导航">
        <nav className="csd-nav" aria-label="课程学习功能">
          {NAV_ITEMS.map((item) => (
            <button
              className={`csd-nav-item${activeSection === item.key ? " is-active" : ""}`}
              type="button"
              key={item.key}
              onClick={() => setActiveSection(item.key)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="csd-sidebar-footer">
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
        </div>
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
          <div className="csd-header-right">
            <span className="csd-active-pill">{activeLabel}</span>
            <button className="csd-profile" type="button" aria-label="个人资料">
              <span>{(user?.nickname || user?.username || "同学").charAt(0).toUpperCase()}</span>
              个人资料⌄
            </button>
          </div>
        </header>

        {loading ? (
          <section className="csd-card csd-loading">课程工作台加载中...</section>
        ) : renderActiveContent()}
      </main>
    </div>
  );
}
