import { useEffect, useState } from "react";
import ExamChat from "./ExamChat.jsx";

const SUBJECT_CONFIG = {
  data_structure: {
    title: "数据结构",
    icon: "DS",
    hero: "开始今天的数据结构学习",
    subtitle: "线性表、栈与队列、树和图，是 11408 高频得分区。",
    tags: ["线性表", "栈与队列", "树", "图"],
    overview: { chapters: 12, knowledge: 86, learned: 24, hours: 18.6 },
    plan: ["线性表的基本概念", "顺序表的实现", "单链表的操作"],
    materials: [32, 68, 24, 15],
  },
  computer_organization: {
    title: "计算机组成原理",
    icon: "CO",
    hero: "开始今天的计算机组成原理学习",
    subtitle: "围绕数据表示、CPU、存储系统和指令系统建立硬件视角。",
    tags: ["数据表示", "CPU", "存储系统", "指令系统"],
    overview: { chapters: 14, knowledge: 92, learned: 18, hours: 15.2 },
    plan: ["定点数与浮点数表示", "CPU 数据通路梳理", "Cache 映射方式复盘"],
    materials: [24, 52, 19, 12],
  },
  operating_system: {
    title: "操作系统",
    icon: "OS",
    hero: "开始今天的操作系统学习",
    subtitle: "从进程、内存、文件系统到 I/O，建立系统运行的整体模型。",
    tags: ["进程管理", "内存管理", "文件系统", "I/O"],
    overview: { chapters: 11, knowledge: 78, learned: 21, hours: 16.4 },
    plan: ["进程与线程状态转换", "PV 操作同步互斥", "页面置换算法训练"],
    materials: [28, 61, 22, 10],
  },
  computer_network: {
    title: "计算机网络",
    icon: "CN",
    hero: "开始今天的计算机网络学习",
    subtitle: "按网络体系结构逐层复盘，把协议、报文和计算题串起来。",
    tags: ["网络体系结构", "传输层", "网络层", "应用层"],
    overview: { chapters: 10, knowledge: 74, learned: 16, hours: 12.8 },
    plan: ["OSI/TCP-IP 体系结构", "TCP 可靠传输机制", "IP 地址与子网划分"],
    materials: [20, 45, 18, 9],
  },
};

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "首" },
  { key: "ai", label: "AI 问答", icon: "问" },
  { key: "materials", label: "资料库", icon: "资" },
  { key: "knowledge", label: "知识脉络", icon: "知" },
  { key: "plan", label: "学习计划", icon: "计" },
  { key: "practice", label: "练习中心", icon: "练" },
  { key: "report", label: "学习报告", icon: "报" },
];

const MATERIAL_LABELS = ["课件讲义", "习题集", "参考资料", "代码示例"];

export const EXAM_SUBJECTS = SUBJECT_CONFIG;

export function getExamSubjectConfig(subjectKey) {
  return SUBJECT_CONFIG[subjectKey] || SUBJECT_CONFIG.data_structure;
}

export function getExamCourseId(subjectKey) {
  return `11408 ${getExamSubjectConfig(subjectKey).title}`;
}

export default function ExamSubjectDashboard({
  user,
  subjectKey = "data_structure",
  panelIntent = null,
  materialsContent = null,
  knowledgeContent = null,
  practiceContent = null,
  reportContent = null,
  knowledgeContext = null,
  initialMaterialToReference = null,
  onInitialMaterialReferenced = null,
  onNavigate,
  onBackHome,
  onProfile,
}) {
  const panelStorageKey = `exam_subject_active_panel_${subjectKey}`;
  const normalizePanel = (panel) => (
    panel === "ai" || panel === "home" || panel === "materials" || panel === "knowledge" || panel === "practice" || panel === "report" ? panel : null
  );
  const getSavedPanel = () => {
    try {
      const raw = localStorage.getItem(panelStorageKey);
      if (raw) {
        const data = JSON.parse(raw);
        return normalizePanel(data?.activePanel) || "home";
      }
    } catch {
      // Ignore corrupt local UI state.
    }
    return "home";
  };

  const [activeSection, setActiveSection] = useState(() => normalizePanel(panelIntent?.panel) || getSavedPanel());
  const config = getExamSubjectConfig(subjectKey);
  const courseId = getExamCourseId(subjectKey);
  const displayName = user?.nickname || user?.username || "同学";

  useEffect(() => {
    if (!panelIntent?.panel) return;
    const nextPanel = normalizePanel(panelIntent.panel);
    if (nextPanel) setActiveSection(nextPanel);
  }, [panelIntent?.nonce, panelIntent?.panel]);

  useEffect(() => {
    try {
      localStorage.setItem(panelStorageKey, JSON.stringify({ activePanel: activeSection, ts: Date.now() }));
    } catch {
      // Ignore private-mode storage failures.
    }
  }, [panelStorageKey, activeSection]);

  const navigate = (target) => {
    if (target === "home") {
      setActiveSection("home");
      return;
    }
    if (target === "ai") {
      setActiveSection("ai");
      return;
    }
    if (target === "materials" && materialsContent) {
      setActiveSection("materials");
      onNavigate?.(target, { subject: subjectKey, courseId, title: config.title });
      return;
    }
    if (target === "knowledge" && knowledgeContent) {
      setActiveSection("knowledge");
      onNavigate?.(target, { subject: subjectKey, courseId, title: config.title });
      return;
    }
    if (target === "practice" && practiceContent) {
      setActiveSection("practice");
      return;
    }
    if (target === "report" && reportContent) {
      setActiveSection("report");
      return;
    }
    onNavigate?.(target, { subject: subjectKey, courseId, title: config.title });
  };

  return (
    <div className="exam-subject-shell">
      <aside className="exam-subject-sidebar">
        <nav className="exam-subject-nav" aria-label="11408 学科工作台导航">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`exam-subject-nav-item${item.key === activeSection ? " active" : ""}`}
              onClick={() => navigate(item.key)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <button type="button" className="exam-subject-back" onClick={onBackHome}>
          返回主页
        </button>
      </aside>

      <main className={`exam-subject-main${activeSection === "ai" ? " exam-subject-main--chat" : ""}${activeSection === "materials" ? " exam-subject-main--materials" : ""}${activeSection === "knowledge" ? " exam-subject-main--knowledge" : ""}${activeSection === "practice" ? " exam-subject-main--practice" : ""}${activeSection === "report" ? " exam-subject-main--report" : ""}`}>
        {activeSection === "ai" ? (
          <ExamChat
            user={user}
            subjectKey={subjectKey}
            subjectTitle={config.title}
            courseName={courseId}
            knowledgeContext={knowledgeContext}
            initialMaterialToReference={initialMaterialToReference}
            onInitialMaterialReferenced={onInitialMaterialReferenced}
            onBackDashboard={() => setActiveSection("home")}
            onOpenMaterials={() => navigate("materials")}
          />
        ) : activeSection === "materials" && materialsContent ? (
          materialsContent
        ) : activeSection === "knowledge" && knowledgeContent ? (
          knowledgeContent
        ) : activeSection === "practice" && practiceContent ? (
          practiceContent
        ) : activeSection === "report" && reportContent ? (
          reportContent
        ) : (
          <>
            <header className="exam-subject-header">
              <div>
                <div className="exam-subject-title-row">
                  <span className="exam-subject-logo">{config.icon}</span>
                  <div>
                    <h1>{config.title}</h1>
                    <p>课程学习 / 当前科目</p>
                  </div>
                </div>
              </div>
              <button type="button" className="exam-subject-profile" onClick={onProfile}>
                <span>{displayName.charAt(0)}</span>
                个人资料
              </button>
            </header>

            <section className="exam-subject-top-grid">
              <div className="exam-subject-hero">
                <div>
                  <h2>{config.hero}</h2>
                  <p>{config.subtitle}</p>
                  <div className="exam-subject-tags">
                    {config.tags.map((tag) => <span key={tag}>{tag}</span>)}
                  </div>
                </div>
                <div className="exam-subject-hero-art" aria-hidden="true">
                  <span>{config.icon}</span>
                </div>
              </div>

              <div className="exam-subject-card exam-subject-overview">
                <h3>课程概览</h3>
                <div className="exam-subject-overview-grid">
                  <Metric label="总章节" value={`${config.overview.chapters} 个`} />
                  <Metric label="知识点" value={`${config.overview.knowledge} 个`} />
                  <Metric label="已学习" value={`${config.overview.learned}%`} />
                  <Metric label="学习时长" value={`${config.overview.hours} 小时`} />
                </div>
              </div>
            </section>

            <section className="exam-subject-content-grid">
              <div className="exam-subject-card">
                <h3>今日学习计划</h3>
                <div className="exam-subject-plan-list">
                  {config.plan.map((item, index) => (
                    <div key={item} className="exam-subject-plan-item">
                      <span>{index + 1}</span>
                      <div>
                        <strong>{item}</strong>
                        <p>第 {Math.max(1, index + 1)} 章 · {config.title}</p>
                      </div>
                      <button type="button" onClick={() => navigate("plan")}>
                        {index === 0 ? "继续学习" : "去学习"}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="exam-subject-card">
                <h3>资料库概览</h3>
                <div className="exam-subject-material-grid">
                  {MATERIAL_LABELS.map((label, index) => (
                    <button key={label} type="button" onClick={() => navigate("materials")}>
                      <span>{label}</span>
                      <strong>{config.materials[index]} 份</strong>
                    </button>
                  ))}
                </div>
              </div>

              <div className="exam-subject-card exam-subject-knowledge-card">
                <h3>知识脉络</h3>
                <div className="exam-subject-knowledge-map">
                  <strong>{config.title}</strong>
                  {config.tags.map((tag) => <span key={tag}>{tag}</span>)}
                </div>
              </div>

              <div className="exam-subject-card">
                <h3>额度剩余</h3>
                <div className="exam-subject-quota-list">
                  <Quota label="AI 问答剩余" value="42 / 50" percent={84} />
                  <Quota label="AI 出题剩余" value="8 / 10" percent={80} />
                  <Quota label="资料上传剩余" value="6 / 10" percent={60} />
                </div>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
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
