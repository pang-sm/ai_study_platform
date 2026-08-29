import { useEffect, useState } from "react";
import "./ProgrammingOnboarding.css";

const LANGUAGE_OPTIONS = ["C", "Python", "Java", "C++"];
const UNCERTAIN_LANGUAGE = "暂时不确定";
const LEVEL_OPTIONS = [
  { key: "beginner_zero", title: "零基础", desc: "从未系统学过编程" },
  { key: "beginner", title: "入门", desc: "学过基础语法，但独立写代码困难" },
  { key: "basic", title: "基础", desc: "能完成简单程序，函数/数组/类等已有基础" },
  { key: "advanced", title: "进阶", desc: "能独立完成中等规模题目或课程项目" },
];
const PROBLEM_OPTIONS = [
  { key: "concept_confusion", title: "概念理解不牢", desc: "基础概念理解不深，容易混淆" },
  { key: "syntax_confusion", title: "语法容易混淆", desc: "不同语言/语法点容易记混" },
  { key: "logic_to_code", title: "不会把思路转成代码", desc: "有思路但难落到代码" },
  { key: "problem_analysis", title: "题目分析困难", desc: "面对题目不清楚解题方向" },
  { key: "debugging", title: "Debug / 定位错误困难", desc: "报错或结果不对时难定位" },
  { key: "ds_algo_weak", title: "数据结构与算法薄弱", desc: "数组/链表/树图等不熟练" },
  { key: "oop_unfamiliar", title: "面向对象不熟", desc: "类/继承/多态等概念模糊" },
  { key: "no_plan", title: "缺少系统练习计划", desc: "不知道每天练什么" },
  { key: "engineering_weak", title: "代码规范 / 工程能力不足", desc: "命名、结构、调试习惯待加强" },
  { key: "no_clear_problem", title: "暂时没有明确问题", desc: "当前没有特别突出的困难" },
];

function ProgrammingIcon({ type }) {
  if (type === "bars") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 19V9M12 19V5M19 19v-8" />
      </svg>
    );
  }
  if (type === "puzzle") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 3h6v4h2a3 3 0 1 1 0 6h-2v8H9v-3a3 3 0 1 0 0-6V9H3V3h6Z" />
      </svg>
    );
  }
  if (type === "calendar") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3v4M17 3v4M4 9h16M6 5h12a2 2 0 0 1 2 2v13H4V7a2 2 0 0 1 2-2Z" />
      </svg>
    );
  }
  if (type === "brain") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 4a4 4 0 0 0-4 4v8a4 4 0 0 0 4 4M15 4a4 4 0 0 1 4 4v8a4 4 0 0 1-4 4M9 4v16M15 4v16M5 12h14" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 15c4.5-.7 8.3-4.5 9-9 2.2.5 3.5 1.8 4 4-4.5.7-8.3 4.5-9 9-2.2-.5-3.5-1.8-4-4Z" />
      <path d="M14 6l4-4M9 19l-3 3M10 11l3 3" />
    </svg>
  );
}

export default function ProgrammingOnboardingStep({
  user,
  apiBase = "/api",
  initialData,
  onBack,
  onCancel,
  onNext,
  hideBackButton = false,
}) {
  const [languages, setLanguages] = useState([]);
  const [uncertain, setUncertain] = useState(false);
  const [level, setLevel] = useState("beginner_zero");
  const [problems, setProblems] = useState(["concept_confusion"]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const applyProfile = (data) => {
    if (!data) return;
    const langs = Array.isArray(data.selected_languages) && data.selected_languages.length
      ? data.selected_languages
      : (data.main_language ? [data.main_language] : []);
    setLanguages(langs);
    setUncertain(langs.length === 0);
    setLevel(data.level || "beginner_zero");
    setProblems(Array.isArray(data.problems) && data.problems.length ? data.problems : ["concept_confusion"]);
  };

  useEffect(() => {
    if (!initialData) return;
    applyProfile(initialData);
  }, [initialData]);

  useEffect(() => {
    if (initialData || !user?.username) return;
    let alive = true;
    fetch(`${apiBase}/programming/onboarding`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (alive && data) applyProfile(data); })
      .catch(() => {});
    return () => { alive = false; };
  }, [apiBase, initialData, user?.username]);

  const toggleLanguage = (item) => {
    setUncertain(false);
    setLanguages((prev) => (
      prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
    ));
    setMessage("");
  };
  const selectUncertain = () => {
    setUncertain(true);
    setLanguages([]);
    setMessage("");
  };
  const toggleProblem = (key) => {
    setProblems((prev) => {
      if (key === "no_clear_problem") return ["no_clear_problem"];
      const next = prev.filter((x) => x !== "no_clear_problem");
      return next.includes(key) ? next.filter((x) => x !== key) : [...next, key];
    });
    setMessage("");
  };

  const handleNext = async () => {
    if (!uncertain && languages.length === 0) {
      setMessage("请选择至少一种练习语言");
      return;
    }
    if (!level) {
      setMessage("请选择当前水平");
      return;
    }
    if (!user?.username) {
      setMessage("登录状态已失效，请重新登录后再试");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch(`${apiBase}/programming/onboarding`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          main_language: languages[0] || "",
          selected_languages: uncertain ? [] : languages,
          level,
          problems,
          onboarding_completed: false,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存编程学习详情失败");
      onNext?.(data);
    } catch (error) {
      setMessage(error.message || "暂时无法保存学习详情，请稍后再试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="programming-onboarding-page">
      <section className="programming-onboarding-card" aria-label="编程学习详情">
        <div className="programming-onboarding-header">
          <span>第 2 步</span>
          <h1>学习详情</h1>
          <p>请补充你的编程学习信息，我们将为你定制更合适的学习内容与功能入口</p>
        </div>

        <div className="programming-question">
          <h2>1. 你想练习哪些编程语言？（可多选）</h2>
          <div className="programming-language-grid" role="group" aria-label="练习语言">
            {LANGUAGE_OPTIONS.map((item) => {
              const selected = !uncertain && languages.includes(item);
              return (
                <button
                  key={item}
                  type="button"
                  className={selected ? "is-selected" : ""}
                  aria-pressed={selected}
                  onClick={() => toggleLanguage(item)}
                >
                  {item}
                </button>
              );
            })}
            <button
              type="button"
              className={uncertain ? "is-selected" : ""}
              aria-pressed={uncertain}
              onClick={selectUncertain}
            >
              {UNCERTAIN_LANGUAGE}
            </button>
          </div>
        </div>

        <div className="programming-question">
          <h2>2. 当前水平？</h2>
          <div className="programming-level-grid" role="radiogroup" aria-label="当前水平">
            {LEVEL_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={level === item.key ? "is-selected" : ""}
                role="radio"
                aria-checked={level === item.key}
                onClick={() => { setLevel(item.key); setMessage(""); }}
              >
                <strong>{item.title}</strong>
                <small>{item.desc}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="programming-question">
          <h2>3. 目前代码学习遇到的问题？（可多选）</h2>
          <div className="programming-problem-grid">
            {PROBLEM_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={problems.includes(item.key) ? "is-selected" : ""}
                onClick={() => toggleProblem(item.key)}
              >
                <span className="programming-icon"><ProgrammingIcon type={item.key === "no_plan" ? "calendar" : item.key === "concept_confusion" ? "brain" : item.key === "problem_analysis" ? "puzzle" : "bars"} /></span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.desc}</small>
                </span>
              </button>
            ))}
          </div>
        </div>

        {message && <div className="programming-onboarding-error">{message}</div>}

        <div className="programming-onboarding-actions">
          {hideBackButton && <button type="button" className="programming-btn-secondary" onClick={onCancel} disabled={saving}>取消并返回</button>}
          {!hideBackButton && (
            <button type="button" className="programming-btn-secondary" onClick={onBack} disabled={saving}>上一步</button>
          )}
          <button type="button" className="programming-btn-primary" onClick={handleNext} disabled={saving}>
            {saving ? "保存中..." : "下一步"}
          </button>
        </div>
      </section>
    </div>
  );
}
