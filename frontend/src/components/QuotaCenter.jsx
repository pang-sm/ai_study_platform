import { useEffect, useState } from "react";
import { getSubjectLabel } from "../courseOptions.js";

const API_BASE = "/api";

const FEATURE_LABELS = {
  chat: "AI 问答",
  code_analyze: "代码分析",
  challenge_generate: "编程题生成",
  learning_diagnosis: "学习诊断",
  knowledge_generate: "知识点生成",
  learning_plan_generate: "学习计划生成",
  material_link_recommend: "资料关联推荐",
  question_generate: "题目生成",
  question_feedback: "题目反馈",
  learning_report_generate: "学习报告生成",
};

const PLAN_NAMES = {
  free: "免费版",
  pro: "专业版",
  admin: "管理员",
};

export default function QuotaCenter({ user }) {
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

  if (loading) {
    return <div className="empty-state">加载中...</div>;
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="primary-button" onClick={fetchQuota}>重试</button>
      </div>
    );
  }

  if (!quota) return null;

  const { plan, feature_limits, upload_limits, all_features } = quota;

  return (
    <div className="quota-center">
      <section className="quota-plan-section">
        <div className="quota-plan-card">
          <div className="quota-plan-badge">{PLAN_NAMES[plan.plan] || plan.plan}</div>
          {plan.plan_expires_at && (
            <div className="quota-plan-expire">
              到期时间：{new Date(plan.plan_expires_at).toLocaleDateString("zh-CN")}
            </div>
          )}
        </div>
        {plan.plan === "free" && (
          <p className="quota-upgrade-hint">升级到专业版以获得更多 AI 使用次数和更大的上传额度。</p>
        )}
      </section>

      <section className="quota-section">
        <h3>AI 功能使用额度（今日）</h3>
        <div className="quota-grid">
          {(all_features || []).map((feature) => {
            const info = feature_limits?.[feature] || { used: 0, limit: 0, remaining: 0 };
            const pct = info.limit > 0 ? Math.min(100, Math.round((info.used / info.limit) * 100)) : 0;
            return (
              <div key={feature} className="quota-item">
                <div className="quota-item-header">
                  <span className="quota-item-label">{FEATURE_LABELS[feature] || feature}</span>
                  <span className="quota-item-count">
                    {info.used} / {info.limit >= 999999 ? "∞" : info.limit}
                  </span>
                </div>
                <div className="quota-bar-track">
                  <div
                    className={`quota-bar-fill ${pct >= 100 ? "quota-bar-full" : pct >= 70 ? "quota-bar-warn" : ""}`}
                    style={{ width: `${info.limit >= 999999 ? 0 : pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="quota-section">
        <h3>上传额度</h3>
        <div className="quota-grid">
          <div className="quota-item">
            <div className="quota-item-header">
              <span className="quota-item-label">资料数量</span>
              <span className="quota-item-count">
                {upload_limits?.material_upload_count?.used || 0} /{" "}
                {upload_limits?.material_upload_count?.limit >= 999999
                  ? "∞"
                  : upload_limits?.material_upload_count?.limit || 0}
              </span>
            </div>
            <div className="quota-bar-track">
              <div
                className="quota-bar-fill"
                style={{
                  width: `${upload_limits?.material_upload_count?.limit >= 999999
                    ? 0
                    : Math.min(100, Math.round(
                        ((upload_limits?.material_upload_count?.used || 0) /
                          (upload_limits?.material_upload_count?.limit || 1)) *
                          100
                      ))
                    }%`,
                }}
              />
            </div>
          </div>
          <div className="quota-item">
            <div className="quota-item-header">
              <span className="quota-item-label">单文件大小上限</span>
              <span className="quota-item-count">{upload_limits?.single_file_size_mb || 0} MB</span>
            </div>
          </div>
        </div>
      </section>

      <div className="quota-refresh">
        <button className="ghost-button" onClick={fetchQuota}>刷新</button>
      </div>
    </div>
  );
}
