import { useState } from "react";
import goalExamIllustration from "../assets/onboarding/goal-exam-illustration.png";
import goalCourseIllustration from "../assets/onboarding/goal-course-illustration.png";
import goalCodeIllustration from "../assets/onboarding/goal-code-illustration.png";

const GOAL_OPTIONS = [
  {
    key: "exam_408",
    letter: "A",
    title: "考研 11408 备考",
    audience: "适合目标明确的考研用户",
    detail: "围绕数据结构、计算机组成原理、操作系统、计算机网络，制定备考计划、刷题、错题复盘和知识点诊断。",
    illustration: goalExamIllustration,
  },
  {
    key: "university_course",
    letter: "B",
    title: "大学课程学习",
    audience: "适合普通大学生",
    detail: "上传课程 PPT、教材、作业、往年卷，让 AI 围绕当前课程辅助学习、答疑、复习和生成练习。",
    illustration: goalCourseIllustration,
  },
  {
    key: "programming",
    letter: "C",
    title: "编程能力提升",
    audience: "适合想练 C / Python / Java / 算法 / 实验的用户",
    detail: "通过代码运行、AI 纠错、编程练习和错题诊断，提升代码能力。",
    illustration: goalCodeIllustration,
  },
];

const EXAM_TIMES = ["2026 年 12 月", "2027 年 12 月", "暂不确定"];
const EXAM_STAGES = ["基础阶段", "强化阶段", "冲刺阶段"];
const EXAM_WEAK = ["数据结构", "计算机组成原理", "操作系统", "计算机网络", "暂时不清楚"];
const EXAM_DAILY = ["4 小时以内", "4 - 6 小时", "6 - 8 小时", "8 小时以上"];
const EXAM_MATERIALS = ["王道资料", "课程 PPT", "真题", "笔记", "暂时没有"];

const COURSE_MAJORS = [
  "软件工程", "计算机科学与技术", "人工智能", "数据科学与大数据技术",
  "网络工程", "信息安全", "其他",
];
const COURSE_GRADES = ["大一", "大二", "大三", "大四", "研究生", "其他"];
const COURSE_OPTIONS = [
  "数据结构", "操作系统", "计算机网络", "计算机组成原理",
  "C 语言", "Python", "Java", "离散数学",
  "数据库系统", "算法设计与分析", "编译原理", "软件工程",
];
const COURSE_MATERIALS = ["PPT", "教材", "作业", "往年卷", "笔记", "暂时没有"];

const CODE_LANGS = ["C", "Python", "Java", "C++", "暂时不确定"];
const CODE_LEVELS = ["零基础", "学过语法"];
const CODE_PROBLEMS = ["概念不熟", "题目思路不足", "缺少系统练习计划"];

function toggleFromList(list, item) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

const EXAM_PACKAGES = [
  {
    key: "free",
    title: "免费模式",
    subtitle: "基础体验",
    price: "0",
    period: "",
    icon: "🎓",
    features: [
      { text: "基础备考体验", avail: true },
      { text: "AI问答次数：50次/每天", avail: true },
      { text: "AI出题次数：5次/每天", avail: true },
      { text: "资料上传限制：100MB", avail: true },
      { text: "学习计划", avail: false },
      { text: "错题复盘", avail: false },
      { text: "学习报告", avail: false },
    ],
    btnLabel: "免费体验",
    recommended: false,
  },
  {
    key: "monthly_sprint",
    title: "月度冲刺",
    subtitle: "短期提升",
    price: "29",
    period: "/ 月",
    icon: "🚀",
    features: [
      { text: "进阶备考体验", avail: true },
      { text: "AI问答次数：300次/每天", avail: true },
      { text: "AI出题次数：30次/每天", avail: true },
      { text: "资料上传限制：500MB", avail: true },
      { text: "学习计划", avail: true },
      { text: "错题复盘", avail: true },
      { text: "学习报告", avail: true },
    ],
    btnLabel: "去支付",
    recommended: false,
  },
  {
    key: "quarterly_boost",
    title: "季度强化包",
    subtitle: "学习更稳",
    price: "79",
    period: "/ 季度",
    icon: "⭐",
    features: [
      { text: "进阶备考体验", avail: true },
      { text: "AI问答次数：300次/每天", avail: true },
      { text: "AI出题次数：30次/每天", avail: true },
      { text: "资料上传限制：500MB", avail: true },
      { text: "学习计划", avail: true },
      { text: "错题复盘", avail: true },
      { text: "学习报告", avail: true },
    ],
    btnLabel: "去支付",
    recommended: true,
  },
  {
    key: "full_exam",
    title: "全程考包",
    subtitle: "长期备考",
    price: "149",
    period: "/ 年",
    icon: "🏆",
    features: [
      { text: "长期备考体验", avail: true },
      { text: "AI问答次数：1000次/每天", avail: true },
      { text: "AI出题次数：100次/每天", avail: true },
      { text: "资料上传限制：2GB", avail: true },
      { text: "学习计划", avail: true },
      { text: "错题复盘", avail: true },
      { text: "学习报告", avail: true },
    ],
    btnLabel: "去支付",
    recommended: false,
  },
];

export default function Onboarding({ user, onComplete, API_BASE }) {
  const [step, setStep] = useState(1);
  const [goalType, setGoalType] = useState("university_course");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // ── Exam 408 form ──
  const [examTime, setExamTime] = useState("暂不确定");
  const [examStage, setExamStage] = useState("");
  const [examWeak, setExamWeak] = useState("");
  const [examDaily, setExamDaily] = useState("");
  const [examMaterials, setExamMaterials] = useState([]);

  // ── University course form ──
  const [courseMajor, setCourseMajor] = useState("");
  const [courseGrade, setCourseGrade] = useState("");
  const [courseCourses, setCourseCourses] = useState([]);
  const [courseMaterials, setCourseMaterials] = useState([]);

  // ── Programming form ──
  const [codeLang, setCodeLang] = useState("");
  const [codeLevel, setCodeLevel] = useState("");
  const [codeProblems, setCodeProblems] = useState([]);

  // ── Exam package step ──
  const [selectedPackage, setSelectedPackage] = useState("quarterly_boost");

  const handleNext = () => {
    if (!goalType) {
      setError("请选择一个学习目标");
      return;
    }
    setError("");
    if (goalType === "exam_408") { setStep(2); } else { setStep(2); }
  };

  const handleStep2Next = () => {
    setError("");
    if (goalType === "exam_408") {
      if (!examStage) { setError("请选择当前备考阶段"); return; }
      setStep(3);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    setError("");
    if (step === 3) { setStep(2); } else { setStep(1); }
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError("");

    let detail = {};
    let nickname = user?.nickname || user?.username || "";

    if (goalType === "exam_408") {
      if (!examStage) { setError("请选择当前备考阶段"); setSaving(false); return; }
      detail = { exam_time: examTime, stage: examStage, weak_subject: examWeak, daily_study_time: examDaily, materials: examMaterials, exam_package_type: selectedPackage };
    } else if (goalType === "university_course") {
      if (!courseMajor) { setError("请选择专业"); setSaving(false); return; }
      if (!courseGrade) { setError("请选择年级"); setSaving(false); return; }
      detail = { major: courseMajor, grade: courseGrade, courses: courseCourses, materials: courseMaterials };
    } else if (goalType === "programming") {
      if (!codeLang) { setError("请选择主要想练的语言"); setSaving(false); return; }
      if (!codeLevel) { setError("请选择当前水平"); setSaving(false); return; }
      detail = { main_language: codeLang, level: codeLevel, problems: codeProblems };
    }

    try {
      const res = await fetch(`${API_BASE}/me/onboarding?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname,
          grade: goalType === "university_course" ? courseGrade : "",
          major: goalType === "university_course" ? courseMajor : "",
          learning_direction: goalType,
          learning_goal_type: goalType,
          onboarding_detail: detail,
          exam_package_type: goalType === "exam_408" ? selectedPackage : undefined,
          preferred_subjects:
            goalType === "university_course" ? courseCourses
            : goalType === "exam_408" ? examMaterials.filter((m) => m !== "暂时没有")
            : [],
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存失败");
      onComplete(data.profile || data.user, goalType);
    } catch (err) {
      setError(err.message || "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const resetGoal = () => { setGoalType(null); setStep(1); setError(""); };

  // ══════════════════════════════════════════════════════
  // STEP 2: Exam 408 detail
  // ══════════════════════════════════════════════════════
  const renderExamDetail = () => (
    <>
      <div className="ob-step2-head">
        <p className="ob-subtitle">第 2 步</p>
        <h1 className="ob-title">备考详情</h1>
        <p className="ob-desc">请补充一些基础信息，我们将为你生成更适合的考内学习入口</p>
      </div>

      <div className="ob-field">
        <label className="ob-label">考试时间</label>
        <select className="ob-select" value={examTime} onChange={(e) => setExamTime(e.target.value)}>
          {EXAM_TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="ob-field">
        <label className="ob-label">当前备考阶段？</label>
        <div className="ob-chips">
          {EXAM_STAGES.map((s) => (
            <button key={s} type="button" className={`ob-chip${examStage === s ? " active" : ""}`} onClick={() => setExamStage(s)}>{s}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">四科里面你最薄弱的是？</label>
        <div className="ob-chips">
          {EXAM_WEAK.map((w) => (
            <button key={w} type="button" className={`ob-chip${examWeak === w ? " active" : ""}`} onClick={() => setExamWeak(w)}>{w}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">每天大概能学多久？</label>
        <div className="ob-chips">
          {EXAM_DAILY.map((d) => (
            <button key={d} type="button" className={`ob-chip${examDaily === d ? " active" : ""}`} onClick={() => setExamDaily(d)}>{d}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">是否已有资料？（多选）</label>
        <div className="ob-chips">
          {EXAM_MATERIALS.map((m) => (
            <button key={m} type="button" className={`ob-chip${examMaterials.includes(m) ? " active" : ""}`} onClick={() => {
              if (m === "暂时没有") {
                setExamMaterials(examMaterials.includes("暂时没有") ? [] : ["暂时没有"]);
              } else {
                setExamMaterials(toggleFromList(examMaterials.filter((x) => x !== "暂时没有"), m));
              }
            }}>{m}</button>
          ))}
        </div>
      </div>
    </>
  );

  // ══════════════════════════════════════════════════════
  // STEP 2: University course detail
  // ══════════════════════════════════════════════════════
  const renderCourseDetail = () => (
    <>
      <h1 className="ob-title">学习详情</h1>
      <p className="ob-subtitle">第 2 步</p>
      <p className="ob-desc">请补充你的课程学习信息，我们将为你定制更适合的学习内容与功能入口</p>

      <div className="ob-row">
        <div className="ob-field ob-field--half">
          <label className="ob-label">你的专业</label>
          <select className="ob-select" value={courseMajor} onChange={(e) => setCourseMajor(e.target.value)}>
            <option value="">选择专业</option>
            {COURSE_MAJORS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="ob-field ob-field--half">
          <label className="ob-label">你的年级</label>
          <select className="ob-select" value={courseGrade} onChange={(e) => setCourseGrade(e.target.value)}>
            <option value="">选择年级</option>
            {COURSE_GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">想学习哪些课程？（多选）</label>
        <div className="ob-chips">
          {COURSE_OPTIONS.map((c) => (
            <button key={c} type="button" className={`ob-chip${courseCourses.includes(c) ? " active" : ""}`} onClick={() => setCourseCourses(toggleFromList(courseCourses, c))}>{c}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">是否已有课程资料？（多选）</label>
        <div className="ob-chips">
          {COURSE_MATERIALS.map((m) => (
            <button key={m} type="button" className={`ob-chip${courseMaterials.includes(m) ? " active" : ""}`} onClick={() => setCourseMaterials(toggleFromList(courseMaterials, m))}>{m}</button>
          ))}
        </div>
      </div>
    </>
  );

  // ══════════════════════════════════════════════════════
  // STEP 2: Programming detail
  // ══════════════════════════════════════════════════════
  const renderCodeDetail = () => (
    <>
      <h1 className="ob-title">学习详情</h1>
      <p className="ob-subtitle">第 2 步</p>
      <p className="ob-desc">请补充你的编程学习信息，我们将为你定制更适合的学习内容与功能入口</p>

      <div className="ob-field">
        <label className="ob-label">你主要想练哪门语言？</label>
        <div className="ob-chips">
          {CODE_LANGS.map((l) => (
            <button key={l} type="button" className={`ob-chip${codeLang === l ? " active" : ""}`} onClick={() => setCodeLang(l)}>{l}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">当前水平？</label>
        <div className="ob-chips">
          {CODE_LEVELS.map((l) => (
            <button key={l} type="button" className={`ob-chip${codeLevel === l ? " active" : ""}`} onClick={() => setCodeLevel(l)}>{l}</button>
          ))}
        </div>
      </div>

      <div className="ob-field">
        <label className="ob-label">目前代码学习遇到的问题？（多选）</label>
        <div className="ob-chips">
          {CODE_PROBLEMS.map((p) => (
            <button key={p} type="button" className={`ob-chip${codeProblems.includes(p) ? " active" : ""}`} onClick={() => setCodeProblems(toggleFromList(codeProblems, p))}>{p}</button>
          ))}
        </div>
      </div>
    </>
  );

  // ══════════════════════════════════════════════════════
  // STEP 3: Exam package selection
  // ══════════════════════════════════════════════════════
  const renderExamPackages = () => (
    <>
      <div className="ob-step2-head">
        <p className="ob-subtitle">第 3 步</p>
        <h1 className="ob-title">选择你的备考套餐</h1>
        <p className="ob-desc">根据你的学习方向，为你推荐适合 11408 备考的使用方案</p>
      </div>

      <div className="ob-packages">
        {EXAM_PACKAGES.map((pkg) => (
          <div
            key={pkg.key}
            className={`ob-package-card${selectedPackage === pkg.key ? " active" : ""}${pkg.recommended ? " recommended" : ""}`}
            onClick={() => setSelectedPackage(pkg.key)}
          >
            {pkg.recommended && <span className="ob-package-badge">推荐</span>}
            <div className="ob-package-icon">{pkg.icon}</div>
            <h3 className="ob-package-title">{pkg.title}</h3>
            <p className="ob-package-subtitle">{pkg.subtitle}</p>
            <div className="ob-package-price">
              <span className="ob-package-currency">￥</span>
              <span className="ob-package-amount">{pkg.price}</span>
              {pkg.period && <span className="ob-package-period">{pkg.period}</span>}
            </div>
            <ul className="ob-package-features">
              {pkg.features.map((f, i) => (
                <li key={i} className={f.avail ? "ob-package-feature" : "ob-package-feature ob-package-feature--unavail"}>
                  <span className="ob-package-check">{f.avail ? "✓" : "✕"}</span>
                  {f.text}
                </li>
              ))}
            </ul>
            <button
              type="button"
              className={selectedPackage === pkg.key ? "ob-btn-primary" : "ob-btn-secondary"}
              onClick={(e) => { e.stopPropagation(); setSelectedPackage(pkg.key); handleSubmit(); }}
            >
              {pkg.btnLabel}
            </button>
          </div>
        ))}
      </div>
    </>
  );

  const renderStep2 = () => {
    if (goalType === "exam_408") return renderExamDetail();
    if (goalType === "university_course") return renderCourseDetail();
    if (goalType === "programming") return renderCodeDetail();
    return null;
  };

  return (
    <div className="onboarding-v2-page">
      <div className="onboarding-v2-card">
        {step === 1 ? (
          <div className="ob-step1">
            <div className="ob-step1-head">
              <span className="ob-subtitle">第 1 步</span>
              <h1 className="ob-title">你的学习目标</h1>
              <p className="ob-desc">请选择最符合当前阶段的学习方向，我们将为你定制学习内容与功能入口</p>
            </div>

            {error && <div className="ob-error">{error}</div>}

            <div className="ob-goals-row">
              {GOAL_OPTIONS.map((g) => (
                <button
                  key={g.key}
                  type="button"
                  className={`ob-goal-card-v2${goalType === g.key ? " active" : ""}`}
                  onClick={() => { setGoalType(g.key); setError(""); }}
                >
                  <span className="ob-goal-letter-v2">{g.letter}</span>
                  <strong className="ob-goal-title-v2">{g.title}</strong>
                  <span className="ob-goal-audience-v2">{g.audience}</span>
                  <div className="ob-goal-illust">
                    <img src={g.illustration} alt={g.title} className="ob-goal-illust-img" />
                  </div>
                  <span className="ob-goal-detail-v2">{g.detail}</span>
                </button>
              ))}
            </div>

            <div className="ob-actions">
              <button className="ob-btn-primary" onClick={handleNext}>
                下一步
              </button>
            </div>
          </div>
        ) : step === 2 ? (
          <>
            {renderStep2()}

            {error && <div className="ob-error">{error}</div>}

            <div className="ob-actions ob-actions--dual">
              <button type="button" className="ob-btn-secondary" onClick={handleBack}>上一步</button>
              <button type="button" className="ob-btn-primary" onClick={handleStep2Next} disabled={saving && goalType !== "exam_408"}>
                {goalType === "exam_408" ? "下一步" : (saving ? "保存中..." : "保存并进入")}
              </button>
            </div>
          </>
        ) : (
          <>
            {renderExamPackages()}

            {error && <div className="ob-error">{error}</div>}

            <div className="ob-actions">
              <button type="button" className="ob-btn-secondary" onClick={handleBack}>上一步</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
