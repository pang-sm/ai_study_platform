import { useEffect, useState } from "react";

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
  const [schoolModal, setSchoolModal] = useState(false);
  const [planItems, setPlanItems] = useState(PLAN_ITEMS);
  const [schoolInput, setSchoolInput] = useState("");

  useEffect(() => {
    if (user?.onboarding_detail) {
      try {
        const d = typeof user.onboarding_detail === "string"
          ? JSON.parse(user.onboarding_detail)
          : user.onboarding_detail;
        if (d.exam_time) setDaysLeft(calcDaysUntil(d.exam_time));
        if (d.target_school) setTargetSchool(d.target_school);
      } catch { /* ignore */ }
    }
  }, [user]);

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

  const enterSubject = (subjKey) => {
    if (setSubject) setSubject(subjKey);
    if (setPage) setPage("home");
  };

  const saveTargetSchool = () => {
    setTargetSchool(schoolInput.trim());
    setSchoolModal(false);
  };

  return (
    <div className="exam-home">
      {/* ── Hero header ── */}
      <div className="eh-hero">
        <div className="eh-hero-left">
          <p className="eh-motto">🏆 保持节奏，每天进步一点点</p>
          <h1 className="eh-welcome">
            欢迎回来，开始今天的 <span className="eh-welcome-em">11408 备考</span>
          </h1>
          <p className="eh-countdown">
            📅 距离考试还有 <strong>{daysLeft}</strong> 天，继续保持稳定的复习节奏
          </p>
        </div>
        <div className="eh-hero-right">
          <div className="eh-user-card">
            <span className="eh-user-avatar">{displayName.charAt(0)}</span>
            <div>
              <strong>{displayName}</strong>
              <span className="eh-user-tag eh-user-tag--member">
                {packageLabel}
              </span>
            </div>
          </div>
          <div className="eh-target-card" onClick={() => setSchoolModal(true)}>
            <div className="eh-target-left">
              <span className="eh-target-icon">🏫</span>
            </div>
            <div className="eh-target-body">
              <div className="eh-target-head">
                <strong>目标院校</strong>
                <span className="eh-target-edit">✎</span>
              </div>
              <p>{targetSchool || "点击设置你的目标院校"}</p>
              <span className="eh-target-motto">明暗自律 · 坚定信念 · 全力以赴</span>
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
        <div className="eh-plan-illust">
          <span className="eh-plan-illust-icon">📋</span>
          <span className="eh-plan-illust-text">每日清单</span>
        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div className="eh-bottom-bar">
        <span>✨ 坚持每天学习一点点，11408 上岸近一步！ ✨</span>
      </div>

      {/* ── Target school modal ── */}
      {schoolModal && (
        <div className="eh-modal-backdrop" onClick={() => setSchoolModal(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
            <h3>设置目标院校</h3>
            <input
              className="ob-select"
              placeholder="输入目标院校，如：清华大学"
              value={schoolInput}
              onChange={(e) => setSchoolInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") saveTargetSchool(); }}
            />
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setSchoolModal(false)}>取消</button>
              <button type="button" className="ob-btn-primary" onClick={saveTargetSchool}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
