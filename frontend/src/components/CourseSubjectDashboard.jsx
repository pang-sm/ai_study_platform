import { useEffect, useState, lazy, Suspense } from "react";
import ExamChat from "./ExamChat.jsx";
import ExamStudyPlan from "./ExamStudyPlan.jsx";
import KnowledgeLearningPage from "./KnowledgeLearningPage.jsx";
const LearningReportCenter = lazy(() => import("./LearningReportCenter.jsx"));
import "./CourseSubjectDashboard.css";

const COURSE_TRACK = "course_learning";

const NAV_ITEMS = [
  { key: "overview", label: "首页", icon: "◆" },
  { key: "chat", label: "AI 问答", icon: "☵" },
  { key: "materials", label: "资料库", icon: "▣" },
  { key: "knowledge", label: "知识脉络", icon: "⌘" },
  { key: "plan", label: "学习计划", icon: "▤" },
  { key: "report", label: "学习报告", icon: "▧" },
];

const EXAM_CRAM_NAV_ITEMS = NAV_ITEMS.filter((item) => item.key !== "report");

const MATERIAL_CARDS = [
  { key: "slides", label: "课件讲义", tone: "purple", match: ["ppt", "课件", "讲义", "slides"] },
  { key: "exercises", label: "习题集", tone: "blue", match: ["习题", "作业", "exercise", "homework"] },
  { key: "references", label: "参考资料", tone: "green", match: ["教材", "参考", "book", "paper"] },
  { key: "examples", label: "代码示例", tone: "orange", match: ["代码", "示例", "code", "demo"] },
];

const CRAM_TASKS = [
  { title: "复习 TCP/IP 分层模型", time: "35 分钟", priority: "高优先级", status: "待完成" },
  { title: "背诵 TCP 三次握手与四次挥手", time: "45 分钟", priority: "必背", status: "进行中" },
  { title: "练习子网划分计算题", time: "50 分钟", priority: "计算题", status: "待完成" },
  { title: "整理拥塞控制与流量控制区别", time: "30 分钟", priority: "简答题", status: "待复盘" },
];

const CRAM_QUESTION_TYPES = [
  { title: "概念简答", examples: ["OSI 与 TCP/IP 模型对比", "交换机与路由器区别", "HTTP 与 HTTPS"] },
  { title: "计算题", examples: ["子网划分", "传输时延与传播时延", "CRC 校验"] },
  { title: "协议流程题", examples: ["TCP 三次握手", "ARP 解析流程", "DNS 查询流程"] },
  { title: "综合应用题", examples: ["网络故障定位", "拥塞控制策略选择", "应用层协议对比"] },
];

const DEFAULT_CRAM_EXAM_INFO = {
  examDate: "6月25日",
  reviewScope: "第1-6章",
  dailyReview: "2小时",
  readiness: "中等",
  daysLeft: "5 天",
  target: "稳过",
};

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

function formatHours(minutes) {
  const mins = numberValue(minutes);
  if (mins <= 0) return "0 小时";
  return `${(mins / 60).toFixed(1)} 小时`;
}

function buildCourseId(courseName, course) {
  return String(course || courseName || "course").trim().replace(/\s+/g, "_");
}

function resolveCourseName(course, getSubjectLabel) {
  if (course && typeof course === "object") {
    return course.courseName || course.courseTitle || course.name || course.title || course.subject || course.courseId || "璇剧▼瀛︿範";
  }
  return getSubjectLabel?.(course) || course || "璇剧▼瀛︿範";
}

function resolveCourseId(course, courseName) {
  if (course && typeof course === "object") {
    return course.courseId || course.id || course.subject || courseName;
  }
  return course || courseName;
}

function getCourseInitials(courseName) {
  const known = {
    计算机网络: "CN",
    数据结构: "DS",
    "Python 程序设计": "PY",
    操作系统: "OS",
    数据库系统: "DB",
    计算机组成原理: "CO",
  };
  return known[courseName] || String(courseName || "CL").trim().slice(0, 2).toUpperCase();
}

function Metric({ label, value }) {
  return (
    <div className="exam-subject-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Quota({ label, value, percent }) {
  return (
    <div className="exam-subject-quota">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <i><b style={{ width: `${percent}%` }} /></i>
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
  // Content props — if provided, render them; otherwise render fallback overview placeholders
  materialsContent = null,
  knowledgeContent = null,
  reportContent = null,
  planContent = null,
  knowledgeContext = null,
  initialMaterialToReference = null,
  onInitialMaterialReferenced = null,
  panelIntent = null,
  learningGoal = "",
}) {
  const initialCourseName = resolveCourseName(course, getSubjectLabel);
  const initialCourseId = resolveCourseId(course, initialCourseName);
  const panelStorageKey = `course_subject_active_panel_${buildCourseId(initialCourseName, initialCourseId)}`;

  const isExamCramMode = learningGoal === "考试突击" ||
    course?.learningGoal === "考试突击" ||
    course?.learning_goal === "考试突击" ||
    coursePreference?.learning_goal === "考试突击";
  const navItems = isExamCramMode ? EXAM_CRAM_NAV_ITEMS : NAV_ITEMS;
  const allowedPanels = isExamCramMode
    ? ["overview", "chat", "materials", "knowledge", "plan"]
    : ["overview", "chat", "materials", "knowledge", "plan", "report"];

  const normalizePanel = (panel) =>
    allowedPanels.includes(panel)
      ? panel
      : null;

  const getSavedPanel = () => {
    try {
      const raw = localStorage.getItem(panelStorageKey);
      if (raw) {
        const data = JSON.parse(raw);
        return normalizePanel(data?.activePanel) || "overview";
      }
    } catch { /* ignore */ }
    return "overview";
  };

  const [activeSection, setActiveSection] = useState(() =>
    normalizePanel(panelIntent?.panel) || getSavedPanel()
  );
  const [entitlements, setEntitlements] = useState(null);
  const stats = dashboard?.stats || {};
  const courseName = initialCourseName;
  const courseId = buildCourseId(courseName, initialCourseId);

  // Persist active section
  useEffect(() => {
    try {
      localStorage.setItem(panelStorageKey, JSON.stringify({ activePanel: activeSection, ts: Date.now() }));
    } catch { /* ignore */ }
  }, [panelStorageKey, activeSection]);

  // Handle panel intent navigation
  useEffect(() => {
    if (!panelIntent?.panel) return;
    const nextPanel = normalizePanel(panelIntent.panel);
    if (nextPanel) setActiveSection(nextPanel);
  }, [panelIntent?.nonce, panelIntent?.panel]);

  useEffect(() => {
    if (!user?.username) return;
    let alive = true;
    fetch(`/api/course-learning/entitlements?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (alive) setEntitlements(data); })
      .catch(() => { if (alive) setEntitlements(null); });
    return () => { alive = false; };
  }, [user?.username]);

  const learnedPercent = Math.max(0, Math.min(100, numberValue(stats.progress_percent, 0)));
  const knowledgeCount = numberValue(stats.knowledge_points_count, 0);
  const chapterCount = numberValue(stats.chapter_count || stats.modules_count, 12);
  const studyMinutes = numberValue(stats.weekly_study_minutes || stats.total_study_minutes, 0);
  const aiLimit = numberValue(entitlements?.feature_limits?.chat?.limit, 0);
  const aiRemaining = numberValue(entitlements?.feature_limits?.chat?.remaining, 0);
  const questionLimit = numberValue(entitlements?.feature_limits?.question_generate?.limit, 0);
  const questionRemaining = numberValue(entitlements?.feature_limits?.question_generate?.remaining, 0);
  const uploadLimitMb = numberValue(entitlements?.upload_limits?.single_file_size_mb || entitlements?.permissions?.material_upload_limit_mb, 0);
  const uploadLimitText = uploadLimitMb ? (uploadLimitMb >= 1024 ? `${uploadLimitMb / 1024} GB` : `${uploadLimitMb} MB`) : "未获取";
  const preference = coursePreference || dashboard?.preference || {};
  const focusTag = learningGoal || preference.learning_goal || "平日学习";
  const activeLabel = navItems.find((item) => item.key === activeSection)?.label || "首页";
  const courseContextDisplay = `课程学习 / ${courseName}`;
  const examInfo = { ...DEFAULT_CRAM_EXAM_INFO, ...(dashboard?.exam_info || dashboard?.examInfo || {}) };

  // Check course_learning membership plan — hide ad if full
  const coursePlan = entitlements?.plan || user?.service_plans?.["course_learning"]?.plan || "free";
  const isCourseFullPlan = coursePlan === "full";

  // Materials for overview
  const courseMaterialsArr = (() => {
    const targetNames = new Set([courseName, initialCourseId, getSubjectLabel?.(initialCourseId)].filter(Boolean));
    return (Array.isArray(materials) ? materials : []).filter((item) => {
      const itemName = getSubjectLabel?.(item.subject) || item.subject;
      return targetNames.has(item.subject) || targetNames.has(itemName);
    });
  })();

  const planItems = [];

  useEffect(() => {
    if (!allowedPanels.includes(activeSection)) setActiveSection("overview");
  }, [activeSection, allowedPanels]);

  const renderExamCramHeader = (subtitle = "考试突击 · 课程冲刺工作台") => (
    <header className="csd-cram-header">
      <div className="csd-cram-title-block">
        <span className="csd-cram-logo">{getCourseInitials(courseName)}</span>
        <div>
          <h1>{courseName}</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="csd-cram-badges">
        <span>距离考试 {examInfo.daysLeft || "5 天"}</span>
        <span>目标：{examInfo.target || "稳过"}</span>
      </div>
    </header>
  );

  const renderExamCramOverview = () => (
    <div className="csd-cram-page">
      {renderExamCramHeader()}

      <section className="csd-cram-grid csd-cram-grid--top">
        <div className="csd-cram-card">
          <div className="csd-cram-card-head">
            <span>Exam Info</span>
            <h2>考试信息</h2>
          </div>
          <div className="csd-cram-info-grid">
            <div><span>考试日期</span><strong>{examInfo.examDate}</strong></div>
            <div><span>复习范围</span><strong>{examInfo.reviewScope}</strong></div>
            <div><span>每日复习</span><strong>{examInfo.dailyReview}</strong></div>
            <div><span>当前准备度</span><strong>{examInfo.readiness}</strong></div>
          </div>
        </div>

        <div className="csd-cram-card csd-cram-self-test">
          <div className="csd-cram-card-head">
            <span>Quick Check</span>
            <h2>考前自测入口</h2>
          </div>
          <button type="button">生成 10 分钟自测</button>
          <button type="button">AI 预测重点</button>
        </div>
      </section>

      <section className="csd-cram-card">
        <div className="csd-cram-card-head">
          <span>Sprint Tasks</span>
          <h2>考前冲刺清单</h2>
        </div>
        <div className="csd-cram-task-list">
          {CRAM_TASKS.map((task) => (
            <label className="csd-cram-task" key={task.title}>
              <input type="checkbox" />
              <span>
                <strong>{task.title}</strong>
                <em>{task.time} · {task.priority}</em>
              </span>
              <b>{task.status}</b>
            </label>
          ))}
        </div>
      </section>

      <section className="csd-cram-card">
        <div className="csd-cram-card-head">
          <span>High Frequency</span>
          <h2>高频题型</h2>
        </div>
        <div className="csd-cram-type-grid">
          {CRAM_QUESTION_TYPES.map((type) => (
            <article className="csd-cram-type-card" key={type.title}>
              <strong>{type.title}</strong>
              {type.examples.map((example) => <span key={example}>{example}</span>)}
            </article>
          ))}
        </div>
      </section>
    </div>
  );

  const renderOverview = () => (
    <>
      <section className="csd-top-grid">
        <div className="csd-card csd-hero-card">
          <div>
            <h2>开始今天的{courseName}学习</h2>
            <p>坚持学习，稳步提升，攻克每一个课程知识点！</p>
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
        {/* Today's Plan */}
        <div className="csd-card csd-plan-card">
          <h3><span>▤</span> 今日学习计划</h3>
          <div className="csd-plan-list">
            {planItems.length === 0 && (
              <div className="csd-empty-state">
                <strong>暂无今日学习计划</strong>
                <p>当前课程还没有生成学习任务，可在学习计划页查看课程任务空状态。</p>
              </div>
            )}
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

        {/* Material Summary */}
        <div className="csd-card csd-material-card">
          <h3><span>▣</span> 资料库概览</h3>
          <div className="csd-material-grid">
            {MATERIAL_CARDS.map((item) => (
              <div className={`csd-material-item csd-material-item--${item.tone}`} key={item.key}>
                <span>■</span>
                <strong>{item.label}</strong>
                <em>{countMaterialType(courseMaterialsArr, item)} 份</em>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="csd-bottom-grid">
        {/* Knowledge Preview */}
        <div className="csd-card csd-knowledge-card">
          <h3><span>⌘</span> 知识脉络</h3>
          <div className="csd-orbit">
            <strong>{courseName}</strong>
            {["课程概念", "课堂资料", "阶段复盘", "学习报告"].map((label, index) => (
              <span className={`csd-node csd-node--${index}${index === 0 ? " is-active" : ""}`} key={label}>
                {label}
              </span>
            ))}
          </div>
        </div>

        {/* Quota */}
        <div className="csd-card csd-quota-card">
          <h3><span>▧</span> 额度剩余</h3>
          {[
            ["AI 问答剩余", aiRemaining, aiLimit],
            ["AI 出题剩余", questionRemaining, questionLimit],
            ["资料上传上限", uploadLimitText, ""],
          ].map(([label, value, total]) => (
            <div className="csd-quota-row" key={label}>
              <span>{label}</span>
              <strong>{total ? `${value} / ${total}` : value}</strong>
              {total ? <em><i style={{ width: `${Math.max(4, Math.min(100, (Number(value) / Number(total || 1)) * 100))}%` }} /></em> : null}
            </div>
          ))}
          <div className="csd-course-task-tag">当前目标：{focusTag}</div>
        </div>
      </section>
    </>
  );

  const renderActiveContent = () => {
    // AI Chat — use mature ExamChat component with course_learning context
    if (activeSection === "chat") {
      return (
        <ExamChat
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          contextDisplay={isExamCramMode ? "考试突击 · AI 复习问答" : courseContextDisplay}
          knowledgeContext={knowledgeContext}
          initialMaterialToReference={initialMaterialToReference}
          onInitialMaterialReferenced={onInitialMaterialReferenced}
        />
      );
    }

    // Materials — use content prop if available, otherwise fallback
    if (activeSection === "materials") {
      if (materialsContent) return materialsContent;
      // Fallback: show minimal materials preview
      return (
        <section className="csd-section">
          <div className="csd-section-header">
            <span>Course Library</span>
            <h2>{courseName} · 资料库</h2>
            <p>当前课程：{courseContextDisplay}</p>
          </div>
          <div className="csd-card csd-library-card" style={{ padding: 26 }}>
            {courseMaterialsArr.length > 0 ? (
              <div className="csd-material-list">
                {courseMaterialsArr.slice(0, 8).map((item) => (
                  <div className="csd-material-row" key={item.id || item.original_filename}>
                    <strong>{item.original_filename || item.file_name || "未命名资料"}</strong>
                    <span>{item.file_type || "course_material"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="csd-empty-state">
                <strong>{courseName} 暂无课程资料</strong>
                <p>上传课程资料后，可用于 AI 问答引用和学习。</p>
              </div>
            )}
          </div>
        </section>
      );
    }

    // Knowledge — use content prop if available, else use KnowledgeLearningPage with course_learning mode
    if (activeSection === "knowledge") {
      if (knowledgeContent) return knowledgeContent;
      return (
        <KnowledgeLearningPage
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          onNavigateToAI={(ctx) => {
            // Navigate to AI chat within CourseSubjectDashboard
            setActiveSection("chat");
          }}
        />
      );
    }

    // Study Plan — use content prop if available, else use ExamStudyPlan with course_learning mode
    if (activeSection === "plan") {
      if (planContent) return planContent;
      return (
        <ExamStudyPlan
          user={user}
          mode="course_learning"
          examCramMode={isExamCramMode}
          courseId={courseId}
          courseName={courseName}
          onNavigate={(target) => {
            // Navigate within CourseSubjectDashboard
            if (target === "knowledge") setActiveSection("knowledge");
          }}
        />
      );
    }

    // Learning Report — use content prop if available, else use LearningReportCenter with course context
    if (activeSection === "report") {
      if (reportContent) return reportContent;
      return (
        <Suspense fallback={<div className="csd-loading">学习报告加载中...</div>}>
          <LearningReportCenter
            user={user}
            mode="course_learning"
            courseName={courseName}
          />
        </Suspense>
      );
    }

    if (isExamCramMode) return renderExamCramOverview();
    return renderOverview();
  };

  return (
    <div className="csd-page">
      <aside className="csd-sidebar" aria-label="课程工作台导航">
        <nav className="csd-nav" aria-label="课程学习功能">
          {navItems.map((item) => (
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
          {!isExamCramMode && !isCourseFullPlan && (
            <div className="csd-member-card">
              <strong>会员 <span>♛</span></strong>
              <p>解锁专属权益，畅享课程学习特权</p>
              <ul>
                <li>专属学习资源</li>
                <li>AI 问答优先使用</li>
                <li>学习数据深度分析</li>
                <li>更多高级功能</li>
              </ul>
              <button type="button" onClick={() => setPage?.("coursePlan")}>了解会员权益 →</button>
            </div>
          )}

          <button className="csd-back-home" type="button" onClick={() => setPage?.("home")}>
            ↩ 返回主页
          </button>
        </div>
      </aside>

      <main className={`csd-main${isExamCramMode ? " csd-main--cram" : ""}${activeSection === "chat" ? " csd-main--chat" : ""}${activeSection === "materials" ? " csd-main--materials" : ""}${activeSection === "knowledge" ? " csd-main--knowledge" : ""}${activeSection === "plan" ? " csd-main--plan" : ""}${activeSection === "report" ? " csd-main--report" : ""}`}>
        {loading ? (
          <section className="csd-card csd-loading">课程工作台加载中...</section>
        ) : (
          renderActiveContent()
        )}
      </main>
    </div>
  );
}
