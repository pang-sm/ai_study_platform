import { useEffect, useRef, useState } from "react";
import FirstTimeGuideLauncher from "./FirstTimeGuideLauncher.jsx";
import { EXAM_GUIDE_STEPS } from "./firstTimeGuideFlows.js";
import UserAvatar from "./UserAvatar.jsx";

function calcDaysUntil(examTimeStr) {
  if (!examTimeStr || examTimeStr === "暂不确定") return null;
  const m = examTimeStr.match(/(\d{4}).*?(\d{1,2})/);
  if (!m) return null;
  const year = parseInt(m[1], 10);
  const month = parseInt(m[2], 10);
  const target = new Date(year, month - 1, 24);
  const now = new Date();
  const diff = Math.ceil((target - now) / (1000 * 60 * 60 * 24));
  return diff > 0 ? diff : null;
}

const SUBJECTS = [
  { key: "data_structure", name: "数据结构", icon: "📊" },
  { key: "computer_organization", name: "计算机组成原理", icon: "💻" },
  { key: "operating_system", name: "操作系统", icon: "⚙️" },
  { key: "computer_network", name: "计算机网络", icon: "🌐" },
];

const EXAM_PACKAGE_LABELS = {
  free: "免费模式",
  monthly_sprint: "月度冲刺包",
  quarterly_boost: "季度强化包",
  full_exam: "全程考包",
};
const PAID_EXAM_PLANS = new Set(["monthly_sprint", "quarterly_boost", "full_exam"]);

export default function ExamHome({ user, setPage, subject, setSubject, apiBase, onLogout, guideReplayToken = 0 }) {
  const [daysLeft, setDaysLeft] = useState(null);
  const [targetSchool, setTargetSchool] = useState("");
  const [examStage, setExamStage] = useState("");
  const [examDaily, setExamDaily] = useState("");
  const [motto, setMotto] = useState("保持节奏，每天进步一点点");
  const [editingMotto, setEditingMotto] = useState(false);
  const [mottoInput, setMottoInput] = useState("");
  const [examPackageLabel, setExamPackageLabel] = useState("");
  const mottoInputRef = useRef(null);
  const [studyPlanSummary, setStudyPlanSummary] = useState(null);
  const [taskSummary, setTaskSummary] = useState(null);
  const [planRestricted, setPlanRestricted] = useState(false);

  // Resolve the effective 11408 plan from the service-direction membership —
  // the single source of truth — falling back to the track package_type.
  const effectivePlan = user?.service_plans?.exam_11408?.plan || "";
  const hasLearningPlan = PAID_EXAM_PLANS.has(effectivePlan);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`/api/me/tracks?username=${encodeURIComponent(user?.username || "")}`);
        const data = await res.json().catch(() => ({}));
        const tracks = data.tracks || [];
        const examTrack = tracks.find((t) => t.track_type === "exam_408");
        const detail = examTrack?.onboarding_detail || {};
        if (examTrack?.package_display_name) setExamPackageLabel(examTrack.package_display_name);
        if (detail.exam_time) setDaysLeft(calcDaysUntil(detail.exam_time));
        if (detail.target_school) setTargetSchool(detail.target_school);
        if (detail.stage) setExamStage(detail.stage);
        if (detail.daily_study_time) setExamDaily(detail.daily_study_time);
        if (detail.welcome_motto) { setMotto(detail.welcome_motto); setMottoInput(detail.welcome_motto); }
        return Boolean(examTrack?.permissions?.learning_plan);
      } catch {
        return false;
      }
    };

    const propDetail = (() => {
      try {
        const examTrack = (user?.tracks || []).find((t) => t.track_type === "exam_408");
        if (examTrack?.onboarding_detail) return examTrack.onboarding_detail;
        const d = user?.onboarding_detail;
        if (!d) return null;
        return typeof d === "string" ? JSON.parse(d) : d;
      } catch { return null; }
    })();
    if (propDetail) {
      if (propDetail.exam_time) setDaysLeft(calcDaysUntil(propDetail.exam_time));
      if (propDetail.target_school) setTargetSchool(propDetail.target_school);
      if (propDetail.stage) setExamStage(propDetail.stage);
      if (propDetail.daily_study_time) setExamDaily(propDetail.daily_study_time);
    }

    const fetchPlanSummary = async () => {
      try {
        const username = user?.username || "";
        if (!username) return;
        const res = await fetch(`/api/exam/11408/study-plan/summary?username=${encodeURIComponent(username)}`);
        const data = await res.json().catch(() => null);
        if (data?.subjects) setStudyPlanSummary(data);
      } catch { /* ignore */ }
    };
    const fetchTaskSummary = async () => {
      try {
        const username = user?.username || "";
        if (!username) return;
        const res = await fetch(`/api/exam/11408/study-plan/tasks/summary?username=${encodeURIComponent(username)}`);
        if (res.status === 403) { setPlanRestricted(true); return; }
        const data = await res.json().catch(() => null);
        if (data) setTaskSummary(data);
      } catch { /* ignore */ }
    };

    const loadHomeData = async () => {
      const planOk = effectivePlan ? hasLearningPlan : await fetchData();
      if (!planOk) { setPlanRestricted(true); return; }
      setPlanRestricted(false);
      await Promise.all([fetchPlanSummary(), fetchTaskSummary()]);
    };
    loadHomeData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.username, effectivePlan]);

  const displayName = user?.nickname || user?.username || "小庞同学";

  const getPackageLabel = () => {
    if (effectivePlan) return EXAM_PACKAGE_LABELS[effectivePlan] || effectivePlan;
    try {
      const tracks = user?.tracks;
      if (Array.isArray(tracks)) {
        const examTrack = tracks.find((t) => t.track_type === "exam_408");
        if (examTrack?.package_type) {
          if (EXAM_PACKAGE_LABELS[examTrack.package_type]) return EXAM_PACKAGE_LABELS[examTrack.package_type];
        }
      }
      const d = user?.onboarding_detail
        ? (typeof user.onboarding_detail === "string" ? JSON.parse(user.onboarding_detail) : user.onboarding_detail)
        : null;
      const pkg = d?.exam_package_type || "";
      if (EXAM_PACKAGE_LABELS[pkg]) return EXAM_PACKAGE_LABELS[pkg];
    } catch { /* ignore */ }
    return "";
  };
  const packageLabel = getPackageLabel() || examPackageLabel || "未选择套餐";

  const saveMotto = async () => {
    const raw = mottoInputRef.current?.value ?? mottoInput;
    const newMotto = (raw || "").trim() || "保持节奏，每天进步一点点";
    setMotto(newMotto);
    setMottoInput(newMotto);
    setEditingMotto(false);
    try {
      await fetch("/api/exam-408/motto", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user?.username, motto: newMotto }),
      });
    } catch { /* keep UI updated */ }
  };

  const enterSubject = (subjKey, panel = "home") => {
    const selected = SUBJECTS.find((item) => item.key === subjKey);
    if (setPage) {
      setPage("examSubjectDashboard", {
        examMode: true,
        examSubjectKey: subjKey,
        examCourseId: selected?.name ? `11408 ${selected.name}` : subjKey,
        forcePanel: panel,
      });
    }
  };

  return (
    <div className="exam-home">
      {/* ── Hero header ── */}
      <div className="eh-hero">
        <div className="eh-hero-left">
          <div className="eh-motto-wrap">
            {editingMotto ? (
              <form className="eh-motto-form" onSubmit={(e) => e.preventDefault()}>
                <input
                  ref={mottoInputRef}
                  className="eh-motto-input"
                  value={mottoInput}
                  onChange={(e) => setMottoInput(e.target.value)}
                  autoFocus
                  onKeyDown={async (e) => {
                    if (e.key === "Enter") { e.preventDefault(); await saveMotto(); }
                    if (e.key === "Escape") { setMottoInput(motto); setEditingMotto(false); }
                  }}
                  onBlur={() => saveMotto()}
                />
              </form>
            ) : (
              <p className="eh-motto" onClick={() => { setMottoInput(motto); setEditingMotto(true); }}>
                🏆 {motto}
                <button type="button" className="eh-motto-edit" title="编辑" onClick={(e) => { e.stopPropagation(); setMottoInput(motto); setEditingMotto(true); }}>✎</button>
              </p>
            )}
          </div>
          <h1 className="eh-welcome">
            欢迎回来，开始今天的 <span className="eh-welcome-em">11408 备考</span>
          </h1>
          <p className="eh-countdown">
            📅 距离考试还有 <strong>{daysLeft === null ? "暂无数据" : daysLeft}</strong>{daysLeft === null ? "" : " 天"}，继续保持稳定的复习节奏
          </p>
          <div className="eh-target-info">
            <span className="eh-target-info-item">
              🏫 目标院校：<strong>{targetSchool || "未设置"}</strong>
            </span>
            {examStage && <span className="eh-target-info-item">📌 当前阶段：{examStage}</span>}
            {examDaily && <span className="eh-target-info-item">⏱ 每天学习：{examDaily}</span>}
            <span className="eh-target-info-hint" onClick={() => setPage && setPage("examProfile")}>如需修改，前往个人中心</span>
          </div>
        </div>
        <div className="eh-hero-right">
          <div className="eh-user-card" data-tour="exam-profile" onClick={() => setPage && setPage("examProfile")} style={{ cursor: "pointer" }}>
            <UserAvatar user={user} name={displayName} className="eh-user-avatar" imgClassName="eh-user-avatar--img" />
            <div>
              <strong>{displayName}</strong>
              <span className="eh-user-tag eh-user-tag--member">
                {packageLabel}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Middle row: Progress + Subjects ── */}
      <div className="eh-middle">
        <div className="eh-card eh-progress-card" data-tour="exam-progress">
          <h3 className="eh-card-title">📈 学习进度总览</h3>
          <div className="eh-progress-list">
            {SUBJECTS.map((s) => {
              const realProgress = studyPlanSummary?.subjects?.find(
                (sp) => sp.subject_key === s.key
              );
              const leafTotal = realProgress?.total_knowledge_points ?? 0;
              const leafMastered = realProgress?.mastered_knowledge_points ?? 0;
              const pct = leafTotal > 0 ? Math.round((leafMastered / leafTotal) * 100) : null;
              return (
                <div key={s.key} className="eh-progress-row">
                  <span className="eh-progress-icon">{s.icon}</span>
                  <span className="eh-progress-name">{s.name}</span>
                  <div className="eh-progress-bar-wrap">
                    <div className="eh-progress-bar" style={{ width: `${pct ?? 0}%` }} />
                  </div>
                  <span className="eh-progress-pct">{pct === null ? "暂无数据" : `${pct}%`}</span>
                  <span className="eh-progress-rate">
                    {pct === null ? "暂无数据" : `${leafMastered}/${leafTotal} 知识点`}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="eh-card eh-subjects-card" data-tour="exam-subjects">
          <h3 className="eh-card-title">📚 科目入口</h3>
          <div className="eh-subjects-grid">
            {SUBJECTS.map((s) => (
              <div key={s.key} className="eh-subject-tile" onClick={() => enterSubject(s.key)}>
                <span className="eh-subject-tile-icon">{s.icon}</span>
                <span className="eh-subject-tile-name">{s.name}</span>
                <span className="eh-subject-tile-enter">进入学习 →</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom row: Study Plan ── */}
      <div className="eh-bottom">
        <div className="eh-card eh-plan-card" data-tour="exam-tasks">
          <h3 className="eh-card-title">📋 学习计划</h3>
          {planRestricted ? (
            <div className="eh-plan-empty">
              <p>当前套餐暂未包含学习计划。</p>
              <button
                type="button"
                className="eh-plan-upgrade-btn"
                onClick={() => setPage && setPage("membership", { serviceKey: "exam_11408", profilePage: "examProfile", returnPage: "examHome" })}
              >
                升级套餐
              </button>
            </div>
          ) : taskSummary?.tasks && taskSummary.tasks.length > 0 ? (
            <div className="eh-task-cards">
              {taskSummary.tasks.map((task) => {
                const subj = SUBJECTS.find((s) => s.key === task.subject_key);
                const cs = task.computed_status || task.status || "not_started";
                const STATUS_LABELS = { completed: "已完成", in_progress: "进行中", not_started: "未开始" };
                return (
                  <div
                    key={task.id}
                    className={`eh-task-card ${cs}`}
                    onClick={() => enterSubject(task.subject_key, "plan")}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="eh-task-card-header">
                      <span className="eh-task-subject-tag">
                        {subj?.icon || "📚"} {subj?.name || task.subject_key}
                      </span>
                      <span className={`eh-task-status-tag ${cs}`}>
                        {STATUS_LABELS[cs] || cs}
                      </span>
                    </div>
                    <strong className="eh-task-card-title">{task.title}</strong>
                    <div className="eh-task-card-meta">
                      <span>
                        {task.scope_type === "all" ? "📚 全部范围" : `📖 ${task.knowledge_point_name || task.secondary_knowledge || ""}`}
                      </span>
                    </div>
                    {task.due_date && (
                      <span className="eh-task-card-due">📅 截止：{task.due_date}</span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="eh-plan-empty">
              <p>暂无学习计划，请进入具体学科的学习计划中设置。</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div className="eh-bottom-bar" data-tour="exam-footer">
        <span>✨ 坚持每天学习一点点，11408 上岸近一步！ ✨</span>
      </div>
      <FirstTimeGuideLauncher serviceKey="exam_11408" serviceLabel="11408 备考" steps={EXAM_GUIDE_STEPS} apiBase={apiBase} ready={Boolean(user?.username)} replayToken={guideReplayToken} onStepChange={(index, _step, direction) => {
        if (index === 1 && direction === "next") enterSubject(SUBJECTS[0].key);
      }} />
    </div>
  );
}
