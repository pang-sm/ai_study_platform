import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";
const UNLIMITED_LIMIT = 999999;

const FEATURE_LABELS = {
  chat: "AI问答",
  code_analyze: "代码分析",
  challenge_generate: "编程题生成",
  learning_diagnosis: "学习诊断",
  knowledge_generate: "知识点生成",
  learning_plan_generate: "学习计划生成",
  material_link_recommend: "资料关联推荐",
  question_generate: "题目生成",
  question_feedback: "题目反馈",
  learning_report_generate: "学习报告生成",
  challenge_explain: "challenge_explain",
  challenge_test_gen: "challenge_test_gen",
};

const FEATURE_ICONS = {
  chat: "💬",
  code_analyze: "</>",
  challenge_generate: "⚙",
  learning_diagnosis: "☑",
  knowledge_generate: "📄",
  learning_plan_generate: "📅",
  material_link_recommend: "🔗",
  question_generate: "🧾",
  question_feedback: "💭",
  learning_report_generate: "▣",
  challenge_explain: "</>",
  challenge_test_gen: "⚗",
};

const FEATURE_ORDER = [
  "chat",
  "code_analyze",
  "challenge_generate",
  "learning_diagnosis",
  "knowledge_generate",
  "learning_plan_generate",
  "material_link_recommend",
  "question_generate",
  "question_feedback",
  "learning_report_generate",
  "challenge_explain",
  "challenge_test_gen",
];

function isUnlimited(limit) {
  return Number(limit || 0) >= UNLIMITED_LIMIT;
}

function formatLimit(limit) {
  return isUnlimited(limit) ? "∞" : Number(limit || 0);
}

function getProgressPct(used, limit) {
  if (isUnlimited(limit) || !Number(limit)) return 0;
  return Math.min(100, Math.round((Number(used || 0) / Number(limit)) * 100));
}

export default function QuotaCenter({ user, setPage }) {
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchQuota = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/me/quota?username=${encodeURIComponent(user.username)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "加载额度信息失败");
      }
      const data = await res.json();
      setQuota(data);
    } catch (e) {
      setError(e.message || "加载额度信息失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuota();
  }, [user.username]);

  const featureRows = useMemo(() => {
    const featureLimits = quota?.feature_limits || {};
    const returnedFeatures = Array.isArray(quota?.all_features) ? quota.all_features : [];
    const ordered = [
      ...FEATURE_ORDER,
      ...returnedFeatures.filter((feature) => !FEATURE_ORDER.includes(feature)),
      ...Object.keys(featureLimits).filter((feature) => !FEATURE_ORDER.includes(feature) && !returnedFeatures.includes(feature)),
    ];

    return ordered.map((feature) => {
      const info = featureLimits[feature] || {};
      const used = Number(info.used || 0);
      const limit = Number(info.limit || 0);
      return {
        feature,
        label: FEATURE_LABELS[feature] || feature,
        icon: FEATURE_ICONS[feature] || "✨",
        used,
        limit,
        pct: getProgressPct(used, limit),
      };
    });
  }, [quota]);

  if (loading) {
    return <div className="quota-center quota-center--state">额度信息加载中...</div>;
  }

  if (error) {
    return (
      <div className="quota-center quota-center--state">
        <p>{error}</p>
        <button className="primary-button" onClick={fetchQuota}>重试</button>
      </div>
    );
  }

  if (!quota) return null;

  const { plan = {}, upload_limits = {} } = quota;
  const uploadCount = upload_limits?.material_upload_count || {};
  const uploadUsed = Number(uploadCount.used || 0);
  const uploadLimit = Number(uploadCount.limit || 0);
  const singleFileSize = Number(upload_limits?.single_file_size_mb || 0);
  const totalAiCalls = featureRows.reduce((sum, item) => sum + item.used, 0);
  const isPlanUnlimited = plan.plan === "admin" || featureRows.some((item) => isUnlimited(item.limit));
  const remainingQuota = isPlanUnlimited
    ? "∞"
    : featureRows.reduce((sum, item) => sum + Math.max(0, Number(item.limit || 0) - Number(item.used || 0)), 0);
  const uploadPct = getProgressPct(uploadUsed, uploadLimit);

  return (
    <div className="quota-center">
      <header className="quota-hero">
        <div>
          <div className="quota-title-row">
            <span className="quota-title-mark" />
            <h1>我的额度</h1>
            <span className="quota-title-gem">💎</span>
          </div>
          <p>查看今日 AI 功能调用情况与上传额度</p>
        </div>
        <div className="quota-refresh-note">
          <span>ⓘ</span>
          额度将在每日自动刷新，上传资料不影响历史学习记录。
        </div>
      </header>

      <section className="quota-overview-grid">
        <article className="quota-overview-card">
          <div className="quota-overview-icon quota-overview-icon--purple">💬</div>
          <div>
            <span className="quota-overview-label">今日总调用</span>
            <strong>{totalAiCalls} <small>次</small></strong>
            <p>较昨日 0 · 0%</p>
          </div>
        </article>
        <article className="quota-overview-card">
          <div className="quota-overview-icon quota-overview-icon--blue">◔</div>
          <div>
            <span className="quota-overview-label">剩余额度</span>
            <strong>{remainingQuota} <small>次</small></strong>
            <p>{isPlanUnlimited ? "无限额度，放心使用" : "今日剩余 AI 调用额度"}</p>
          </div>
        </article>
        <article className="quota-overview-card">
          <div className="quota-overview-icon quota-overview-icon--green">☁</div>
          <div>
            <span className="quota-overview-label">资料上传量</span>
            <strong>{uploadUsed} <small>个</small></strong>
            <p>单文件上限 {singleFileSize || 0} MB</p>
          </div>
        </article>
      </section>

      <section className="quota-section quota-feature-section">
        <div className="quota-section-heading">
          <span className="quota-section-icon">✦</span>
          <h2>AI 功能使用额度（今日）</h2>
        </div>
        <div className="quota-feature-grid">
          {featureRows.map((item) => (
            <article key={item.feature} className="quota-feature-item">
              <span className="quota-feature-icon">{item.icon}</span>
              <div className="quota-feature-main">
                <div className="quota-feature-top">
                  <span>{item.label}</span>
                  <strong>{item.used} / {formatLimit(item.limit)}</strong>
                </div>
                <div className="quota-bar-track">
                  <div
                    className={`quota-bar-fill ${item.pct >= 100 ? "quota-bar-full" : item.pct >= 70 ? "quota-bar-warn" : ""}`}
                    style={{ width: `${item.pct}%` }}
                  />
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="quota-section quota-upload-section">
        <div className="quota-section-heading">
          <span className="quota-section-icon">☁</span>
          <h2>上传额度</h2>
        </div>
        <div className="quota-upload-panel">
          <div className="quota-upload-metric">
            <span className="quota-upload-icon">📁</span>
            <div className="quota-upload-body">
              <span>资料数量</span>
              <strong>{uploadUsed} / {formatLimit(uploadLimit)}</strong>
              <div className="quota-bar-track">
                <div className="quota-bar-fill" style={{ width: `${uploadPct}%` }} />
              </div>
            </div>
          </div>
          <div className="quota-upload-divider" />
          <div className="quota-upload-metric quota-upload-metric--compact">
            <span className="quota-upload-icon">📄</span>
            <div>
              <span>单文件大小上限</span>
              <strong>{singleFileSize || 0} <small>MB</small></strong>
            </div>
          </div>
          <aside className="quota-upload-tip">
            <span>💡</span>
            支持上传 PDF、Word、PPT、图片等多种格式，更好地辅助你的学习。
          </aside>
        </div>
      </section>

      <div className="quota-actions">
        <button className="ghost-button quota-secondary-action" type="button" onClick={() => setPage?.("membership")}>查看套餐</button>
        <button className="primary-button quota-primary-action" type="button" onClick={fetchQuota}>刷新额度</button>
      </div>
    </div>
  );
}
