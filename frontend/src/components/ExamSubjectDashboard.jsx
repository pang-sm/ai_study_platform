import { useEffect, useState, useCallback, lazy, Suspense } from "react";
import ExamChat from "./ExamChat.jsx";
import ExamStudyPlan from "./ExamStudyPlan.jsx";
import useFeatureEntitlements from "../hooks/useFeatureEntitlements.js";
import LockedFeaturePrompt, { LockedFeatureView } from "./LockedFeaturePrompt.jsx";
import FirstTimeGuideLauncher from "./FirstTimeGuideLauncher.jsx";
import { EXAM_GUIDE_STEPS } from "./firstTimeGuideFlows.js";
import UserAvatar from "./UserAvatar.jsx";
const LearningReportCenter = lazy(() => import("./LearningReportCenter.jsx"));
const ReviewCenter = lazy(() => import("./ReviewCenter.jsx"));

const SUBJECT_CONFIG = {
  data_structure: {
    title: "数据结构",
    icon: "DS",
    hero: "开始今天的数据结构学习",
    subtitle: "线性表、栈与队列、树和图，是 11408 高频得分区。",
    tags: ["线性表", "栈与队列", "树", "图"],
  },
  computer_organization: {
    title: "计算机组成原理",
    icon: "CO",
    hero: "开始今天的计算机组成原理学习",
    subtitle: "围绕数据表示、CPU、存储系统和指令系统建立硬件视角。",
    tags: ["数据表示", "CPU", "存储系统", "指令系统"],
  },
  operating_system: {
    title: "操作系统",
    icon: "OS",
    hero: "开始今天的操作系统学习",
    subtitle: "从进程、内存、文件系统到 I/O，建立系统运行的整体模型。",
    tags: ["进程管理", "内存管理", "文件系统", "I/O"],
  },
  computer_network: {
    title: "计算机网络",
    icon: "CN",
    hero: "开始今天的计算机网络学习",
    subtitle: "按网络体系结构逐层复盘，把协议、报文和计算题串起来。",
    tags: ["网络体系结构", "传输层", "网络层", "应用层"],
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

export const EXAM_SUBJECTS = SUBJECT_CONFIG;
const FEATURE_BY_PANEL = { plan: "learning_plan", review: "practice_review", report: "learning_report" };
NAV_ITEMS.splice(NAV_ITEMS.findIndex((item) => item.key === "report"), 0, { key: "review", label: "练习复盘", icon: "↻" });

export function getExamSubjectConfig(subjectKey) {
  return SUBJECT_CONFIG[subjectKey] || SUBJECT_CONFIG.data_structure;
}

export function getExamCourseId(subjectKey) {
  return `11408 ${getExamSubjectConfig(subjectKey).title}`;
}

export default function ExamSubjectDashboard({
  user, subjectKey = "data_structure", panelIntent = null,
  materialsContent = null, knowledgeContent = null,
  practiceContent = null, reportContent = null,
  planContent = null, knowledgeContext = null,
  initialMaterialToReference = null,
  onInitialMaterialReferenced = null,
  onNavigate, onBackHome, onProfile, onUpgrade,
}) {
  const panelStorageKey = `exam_subject_active_panel_${subjectKey}`;
  const normalizePanel = (panel) => (
    panel === "ai" || panel === "home" || panel === "materials" || panel === "knowledge" || panel === "practice" || panel === "review" || panel === "report" || panel === "plan" ? panel : null
  );
  const getSavedPanel = () => {
    try {
      const raw = localStorage.getItem(panelStorageKey);
      if (raw) {
        const data = JSON.parse(raw);
        return normalizePanel(data?.activePanel) || "home";
      }
    } catch { /* ignore */ }
    return "home";
  };

  const [activeSection, setActiveSection] = useState(() => normalizePanel(panelIntent?.panel) || getSavedPanel());
  const [dashData, setDashData] = useState(null);
  const [dashLoading, setDashLoading] = useState(false);
  const config = getExamSubjectConfig(subjectKey);
  const courseId = getExamCourseId(subjectKey);
  const featureEntitlements = useFeatureEntitlements("exam_11408", Boolean(user?.username));
  const [lockedFeature, setLockedFeature] = useState(null);
  const activeFeature = FEATURE_BY_PANEL[activeSection];
  const activeFeatureEntitlement = activeFeature
    ? { feature: activeFeature, current_plan: featureEntitlements.currentPlan, ...(featureEntitlements.features[activeFeature] || {}) }
    : null;
  const openMembership = () => {
    if (onUpgrade) onUpgrade();
    else onNavigate?.("membership", { subject: subjectKey, courseId, title: config.title });
  };
  const displayName = user?.nickname || user?.username || "同学";

  // Fetch dashboard summary
  const fetchDashboard = useCallback(async () => {
    const uname = user?.username;
    if (!uname) return;
    setDashLoading(true);
    try {
      const res = await fetch(
        `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/dashboard-summary?username=${encodeURIComponent(uname)}`
      );
      if (res.ok) {
        const data = await res.json();
        setDashData(data);
      }
    } catch { /* best effort */ }
    finally {
      setDashLoading(false);
    }
  }, [user?.username, subjectKey]);

  useEffect(() => {
    if (activeSection === "home") fetchDashboard();
  }, [activeSection, fetchDashboard]);

  useEffect(() => {
    if (!panelIntent?.panel) return;
    const nextPanel = normalizePanel(panelIntent.panel);
    if (nextPanel) setActiveSection(nextPanel);
  }, [panelIntent?.nonce, panelIntent?.panel]);

  useEffect(() => {
    try {
      localStorage.setItem(panelStorageKey, JSON.stringify({ activePanel: activeSection, ts: Date.now() }));
    } catch { /* ignore */ }
  }, [panelStorageKey, activeSection]);

  const navigate = (target) => {
    const feature = FEATURE_BY_PANEL[target];
    if (feature) {
      const entitlement = featureEntitlements.features[feature];
      if (featureEntitlements.loading) return;
      if (!entitlement?.allowed) {
        setLockedFeature({ feature, current_plan: featureEntitlements.currentPlan, ...(entitlement || {}) });
        return;
      }
    }
    if (target === "home") { setActiveSection("home"); return; }
    if (target === "ai") { setActiveSection("ai"); return; }
    if (target === "materials" && materialsContent) { setActiveSection("materials"); onNavigate?.(target, { subject: subjectKey, courseId, title: config.title }); return; }
    if (target === "knowledge" && knowledgeContent) { setActiveSection("knowledge"); onNavigate?.(target, { subject: subjectKey, courseId, title: config.title }); return; }
    if (target === "practice" && practiceContent) { setActiveSection("practice"); return; }
    if (target === "report" && reportContent) { setActiveSection("report"); return; }
    if (target === "plan") { setActiveSection("plan"); return; }
    onNavigate?.(target, { subject: subjectKey, courseId, title: config.title });
  };

  // Formatters
  const overview = dashData?.overview || {};
  const quota = dashData?.quota || {};
  const plans = dashData?.today_plan || [];

  const fmtStudyTime = (mins) => {
    if (!mins || mins <= 0) return "0 分钟";
    if (mins < 60) return `${mins} 分钟`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m > 0 ? `${h}.${Math.round(m / 6)} 小时` : `${h} 小时`;
  };

  const fmtQuotaPercent = (remaining, limit) => {
    if (!limit || limit <= 0) return 100;
    if (limit === null || limit === undefined) return 100;
    return Math.round(remaining / limit * 100);
  };

  const fmtQuotaValue = (remaining, limit, unit) => {
    if (limit === null || limit === undefined) return `不限`;
    const r = Number.isFinite(remaining) ? remaining : 0;
    return `${r} / ${limit} ${unit || ""}`;
  };

  const TASK_TYPE_LABELS = { knowledge: "知识点学习", chapter_practice: "章节练习", review: "阶段复习" };
  const STATUS_LABELS = { completed: "已完成", in_progress: "进行中", not_started: "未开始" };

  return (
    <div className="exam-subject-shell">
      <aside className="exam-subject-sidebar">
        <nav className="exam-subject-nav" aria-label="11408 学科工作台导航">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key} type="button"
              data-tour={`exam-nav-${item.key}`}
              className={`exam-subject-nav-item${item.key === activeSection ? " active" : ""}${FEATURE_BY_PANEL[item.key] && !featureEntitlements.loading && !featureEntitlements.features[FEATURE_BY_PANEL[item.key]]?.allowed ? " is-locked" : ""}`}
              onClick={() => navigate(item.key)}
              title={FEATURE_BY_PANEL[item.key] && !featureEntitlements.loading && !featureEntitlements.features[FEATURE_BY_PANEL[item.key]]?.allowed ? "需要升级套餐后使用" : undefined}
            >
              <span>{item.icon}</span>
              {item.label}
              {FEATURE_BY_PANEL[item.key] && !featureEntitlements.loading && !featureEntitlements.features[FEATURE_BY_PANEL[item.key]]?.allowed && <b className="exam-subject-nav-lock" aria-label="需要升级">🔒</b>}
            </button>
          ))}
        </nav>
        <button type="button" className="exam-subject-back" onClick={onBackHome}>返回主页</button>
      </aside>

      <main className={`exam-subject-main${activeSection === "ai" ? " exam-subject-main--chat" : ""}${activeSection === "materials" ? " exam-subject-main--materials" : ""}${activeSection === "knowledge" ? " exam-subject-main--knowledge" : ""}${activeSection === "practice" ? " exam-subject-main--practice" : ""}${activeSection === "report" ? " exam-subject-main--report" : ""}${activeSection === "plan" ? " exam-subject-main--plan" : ""}`}>
        {activeFeature && featureEntitlements.loading ? (
          <div className="empty-state">正在验证会员权益...</div>
        ) : activeFeature && !activeFeatureEntitlement?.allowed ? (
          <LockedFeatureView entitlement={activeFeatureEntitlement} onViewMembership={openMembership} />
        ) : activeSection === "ai" ? (
          <ExamChat user={user} subjectKey={subjectKey} subjectTitle={config.title}
            courseName={courseId} knowledgeContext={knowledgeContext}
            initialMaterialToReference={initialMaterialToReference}
            onInitialMaterialReferenced={onInitialMaterialReferenced}
            onBackDashboard={() => setActiveSection("home")}
            onOpenMaterials={() => navigate("materials")} />
        ) : activeSection === "materials" && materialsContent ? (
          materialsContent
        ) : activeSection === "knowledge" && knowledgeContent ? (
          knowledgeContent
        ) : activeSection === "practice" && practiceContent ? (
          practiceContent
        ) : activeSection === "review" ? (
          <Suspense fallback={<div className="empty-state">练习复盘加载中...</div>}>
            <ReviewCenter user={user} courseId={courseId} />
          </Suspense>
        ) : activeSection === "report" ? (
          reportContent || <Suspense fallback={<div className="empty-state">学习报告加载中...</div>}>
            <LearningReportCenter user={user} mode="exam_11408" courseId={courseId} courseName={config.title} />
          </Suspense>
        ) : activeSection === "plan" ? (
          planContent || <ExamStudyPlan user={user} subjectKey={subjectKey} onNavigate={navigate} />
        ) : (
          <>
            <header className="exam-subject-header">
              <div>
                <div className="exam-subject-title-row">
                  <span className="exam-subject-logo">{config.icon}</span>
                  <h1>{config.title}</h1>
                </div>
              </div>
              <button type="button" className="exam-subject-profile" onClick={onProfile}>
                <UserAvatar user={user} name={displayName} className="exam-subject-profile-avatar" />
                个人资料
              </button>
            </header>

            <section className="exam-subject-top-grid">
              <div className="exam-subject-card exam-subject-overview">
                <h3>课程概览</h3>
                <div className="exam-subject-overview-grid">
                  <Metric label="总章节" value={`${overview.total_chapters ?? 0} 个`} />
                  <Metric label="知识点" value={`${overview.total_knowledge_points ?? 0} 个`} />
                  <Metric label="已学习" value={`${overview.learned_percent ?? 0}%`} />
                  <Metric label="学习时长" value={fmtStudyTime(overview.study_minutes ?? 0)} />
                </div>
              </div>
            </section>

            <section className="exam-subject-content-grid">
              {/* Today's Plan */}
              <div className="exam-subject-card">
                <h3>今日学习计划</h3>
                <div className="exam-subject-plan-list">
                  {[0, 1, 2].map((slotIndex) => {
                    const task = plans[slotIndex];
                    if (task) {
                      const cs = task.computed_status || task.status || "not_started";
                      return (
                        <div key={task.id} className="exam-subject-plan-item">
                          <span>{slotIndex + 1}</span>
                          <div>
                            <strong>{task.title}</strong>
                            <p>
                              {task.knowledge_point_name || TASK_TYPE_LABELS[task.task_type] || ""}
                              {" · "}
                              <span className={`esp-task-computed-status ${cs}`} style={{fontSize:"11px"}}>
                                {STATUS_LABELS[cs] || cs}
                              </span>
                            </p>
                          </div>
                          <button type="button" onClick={() => navigate("plan")}>
                            {slotIndex === 0 ? "查看计划" : "去学习"}
                          </button>
                        </div>
                      );
                    }
                    return (
                      <div key={`empty-${slotIndex}`} className="exam-subject-plan-item exam-subject-plan-item--empty">
                        <span>{slotIndex + 1}</span>
                        <div>
                          <strong>暂无学习计划</strong>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Quota */}
              <div className="exam-subject-card">
                <h3>额度剩余</h3>
                <div className="exam-subject-quota-list">
                  <Quota label="AI 问答剩余"
                    value={fmtQuotaValue(quota.ai_chat?.remaining ?? 0, quota.ai_chat?.limit ?? 0, quota.ai_chat?.unit)}
                    percent={fmtQuotaPercent(quota.ai_chat?.remaining ?? 0, quota.ai_chat?.limit ?? 0)} />
                  <Quota label="AI 出题剩余"
                    value={fmtQuotaValue(quota.ai_question?.remaining ?? 0, quota.ai_question?.limit ?? 0, quota.ai_question?.unit)}
                    percent={fmtQuotaPercent(quota.ai_question?.remaining ?? 0, quota.ai_question?.limit ?? 0)} />
                  <Quota label="资料上传剩余"
                    value={fmtQuotaValue(quota.material_upload?.remaining ?? 0, quota.material_upload?.limit ?? 0, quota.material_upload?.unit)}
                    percent={fmtQuotaPercent(quota.material_upload?.remaining ?? 0, quota.material_upload?.limit ?? 0)} />
                </div>
              </div>
            </section>
          </>
        )}
      </main>
      <LockedFeaturePrompt entitlement={lockedFeature} onClose={() => setLockedFeature(null)} onViewMembership={openMembership} />
      <FirstTimeGuideLauncher
        serviceKey="exam_11408"
        serviceLabel="11408 备考"
        steps={EXAM_GUIDE_STEPS}
        ready={false}
        onStepChange={(index, _step, direction) => {
          if (index === 0 && direction === "previous") onBackHome?.();
        }}
      />
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
