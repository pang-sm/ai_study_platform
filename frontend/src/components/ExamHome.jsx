import { useEffect, useRef, useState } from "react";

function calcDaysUntil(examTimeStr) {
  if (!examTimeStr || examTimeStr === "暂不确定") return 128;
  const m = examTimeStr.match(/(\d{4}).*?(\d{1,2})/);
  if (!m) return 128;
  const year = parseInt(m[1], 10);
  const month = parseInt(m[2], 10);
  const target = new Date(year, month - 1, 24);
  const now = new Date();
  const diff = Math.ceil((target - now) / (1000 * 60 * 60 * 24));
  return diff > 0 ? diff : 128;
}

const SUBJECTS = [
  { key: "data_structure", name: "数据结构", icon: "📊", progress: 72, correctRate: 72 },
  { key: "computer_organization", name: "计算机组成原理", icon: "💻", progress: 65, correctRate: 65 },
  { key: "operating_system", name: "操作系统", icon: "⚙️", progress: 70, correctRate: 70 },
  { key: "computer_network", name: "计算机网络", icon: "🌐", progress: 58, correctRate: 58 },
];

const PLAN_ITEMS = [
  { id: 1, title: "数据结构：刷套卷专项练习", progress: "已完成10", status: "已完成", done: true },
  { id: 2, title: "操作系统：进程与线程复习", progress: "0/1", status: "待完成", done: false },
  { id: 3, title: "计组：存储系统知识点总结", progress: "0/1", status: "待完成", done: false },
  { id: 4, title: "计网：章节刷 10 题", progress: "0/10", status: "待完成", done: false },
];

export default function ExamHome({ user, setPage, subject, setSubject, apiBase, onLogout }) {
  const [daysLeft, setDaysLeft] = useState(128);
  const [targetSchool, setTargetSchool] = useState("");
  const [examStage, setExamStage] = useState("");
  const [examDaily, setExamDaily] = useState("");
  const [planItems, setPlanItems] = useState(PLAN_ITEMS);
  const [motto, setMotto] = useState("保持节奏，每天进步一点点");
  const [editingMotto, setEditingMotto] = useState(false);
  const [mottoInput, setMottoInput] = useState("");
  const mottoInputRef = useRef(null);

  // Fetch real data from tracks API on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`/api/me/tracks?username=${encodeURIComponent(user?.username || "")}`);
        const data = await res.json().catch(() => ({}));
        const tracks = data.tracks || [];
        const examTrack = tracks.find((t) => t.track_type === "exam_408");
        const detail = examTrack?.onboarding_detail || {};
        if (detail.exam_time) setDaysLeft(calcDaysUntil(detail.exam_time));
        if (detail.target_school) setTargetSchool(detail.target_school);
        if (detail.stage) setExamStage(detail.stage);
        if (detail.daily_study_time) setExamDaily(detail.daily_study_time);
        if (detail.welcome_motto) { setMotto(detail.welcome_motto); setMottoInput(detail.welcome_motto); }
      } catch { /* fallback to prop data */ }
    };
    // Also try prop data immediately
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
    // Then refresh from API for latest data
    fetchData();
  }, []);

  const displayName = user?.nickname || user?.username || "小庞同学";

  // Resolve real exam package name from tracks data
  const getPackageLabel = () => {
    try {
      // First check user.tracks from new API
      const tracks = user?.tracks;
      if (Array.isArray(tracks)) {
        const examTrack = tracks.find((t) => t.track_type === "exam_408");
        if (examTrack?.package_type) {
          const MAP = {
            free: "免费模式",
            monthly_sprint: "月度冲刺",
            quarterly_boost: "季度强化包",
            full_exam: "全程考包",
          };
          if (MAP[examTrack.package_type]) return MAP[examTrack.package_type];
        }
      }
      // Fallback: onboarding_detail
      const d = user?.onboarding_detail
        ? (typeof user.onboarding_detail === "string"
            ? JSON.parse(user.onboarding_detail)
            : user.onboarding_detail)
        : null;
      const pkg = d?.exam_package_type || "";
      const MAP = {
        free: "免费模式",
        monthly_sprint: "月度冲刺",
        quarterly_boost: "季度强化包",
        full_exam: "全程考包",
      };
      if (MAP[pkg]) return MAP[pkg];
    } catch { /* ignore */ }
    return "未选择套餐";
  };
  const packageLabel = getPackageLabel();

  const togglePlanItem = (id) => {
    setPlanItems((prev) => prev.map((p) => (p.id === id ? { ...p, done: !p.done, status: !p.done ? "已完成" : "待完成" } : p)));
  };

  const saveMotto = async () => {
    // Use ref to get latest DOM value (avoids stale closure)
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
    } catch { /* keep UI updated, API best-effort */ }
  };

  const enterSubject = (subjKey) => {
    const selected = SUBJECTS.find((item) => item.key === subjKey);
    if (setSubject && selected?.name) setSubject(`11408 ${selected.name}`);
    if (setPage) {
      setPage("examSubjectDashboard", {
        subject: subjKey,
        examCourseId: selected?.name ? `11408 ${selected.name}` : subjKey,
        forcePanel: "home",
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
            📅 距离考试还有 <strong>{daysLeft}</strong> 天，继续保持稳定的复习节奏
          </p>
          {/* Target school — read-only, displayed inline */}
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
          <div className="eh-user-card" onClick={() => setPage && setPage("examProfile")} style={{ cursor: "pointer" }}>
            <span className="eh-user-avatar">{displayName.charAt(0)}</span>
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
        <div className="eh-card eh-progress-card">
          <h3 className="eh-card-title">📈 学习进度总览</h3>
          <div className="eh-progress-list">
            {SUBJECTS.map((s) => (
              <div key={s.key} className="eh-progress-row">
                <span className="eh-progress-icon">{s.icon}</span>
                <span className="eh-progress-name">{s.name}</span>
                <div className="eh-progress-bar-wrap">
                  <div className="eh-progress-bar" style={{ width: `${s.progress}%` }} />
                </div>
                <span className="eh-progress-pct">{s.progress}%</span>
                <span className="eh-progress-rate">正确率{s.correctRate}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="eh-card eh-subjects-card">
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
        <div className="eh-card eh-plan-card">
          <h3 className="eh-card-title">📋 学习计划</h3>
          <table className="eh-plan-table">
            <thead>
              <tr>
                <th></th>
                <th>任务</th>
                <th>进度</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {planItems.map((p) => (
                <tr key={p.id} className={p.done ? "eh-plan-done" : ""}>
                  <td>
                    <button
                      type="button"
                      className={`eh-plan-check${p.done ? " checked" : ""}`}
                      onClick={() => togglePlanItem(p.id)}
                    >
                      {p.done ? "✓" : ""}
                    </button>
                  </td>
                  <td>{p.title}</td>
                  <td className="eh-plan-progress-cell">{p.progress}</td>
                  <td className={`eh-plan-status${p.done ? " done" : " pending"}`}>{p.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div className="eh-bottom-bar">
        <span>✨ 坚持每天学习一点点，11408 上岸近一步！ ✨</span>
      </div>
    </div>
  );
}
