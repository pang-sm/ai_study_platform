import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { COURSE_OPTIONS, getSubjectLabel } from "../courseOptions.js";

const API_BASE = "/api";

const SOURCE_LABELS = { manual: "手动", ai: "AI 推荐" };

export default function KnowledgeBaseCenter({ user, getSubjectLabel }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(null);

  // Bind modal
  const [bindModalMaterial, setBindModalMaterial] = useState(null);
  const [bindKps, setBindKps] = useState([]);
  const [bindLoading, setBindLoading] = useState(false);
  const [bindKpList, setBindKpList] = useState([]);
  const [selectedKpIds, setSelectedKpIds] = useState(new Set());

  // Recommend modal
  const [recModalMaterial, setRecModalMaterial] = useState(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recResults, setRecResults] = useState([]);
  const [recApplyLoading, setRecApplyLoading] = useState(false);

  const fetchDashboard = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-base/dashboard?username=${encodeURIComponent(user.username)}`
      );
      if (res.ok) {
        setData(await res.json());
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "知识库数据加载失败，请稍后重试。");
      }
    } catch (e) {
      setError("知识库数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [user?.username]);

  // ── Bind Modal ──
  const openBindModal = async (material) => {
    setBindModalMaterial(material);
    setSelectedKpIds(new Set());
    setBindLoading(true);
    try {
      const courseId = material.course_id || "";
      const query = `username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(courseId)}`;
      const res = await fetch(`${API_BASE}/knowledge-points?${query}`);
      if (res.ok) {
        const json = await res.json();
        setBindKpList(json.knowledge_points || []);
      } else {
        setBindKpList([]);
      }
    } catch {
      setBindKpList([]);
    } finally {
      setBindLoading(false);
    }
  };

  const closeBindModal = () => {
    setBindModalMaterial(null);
    setBindKpList([]);
    setSelectedKpIds(new Set());
  };

  const toggleKp = (kpId) => {
    setSelectedKpIds((prev) => {
      const next = new Set(prev);
      if (next.has(kpId)) next.delete(kpId);
      else next.add(kpId);
      return next;
    });
  };

  const confirmBind = async () => {
    if (!bindModalMaterial || selectedKpIds.size === 0) return;
    setBindLoading(true);
    const courseId = bindModalMaterial.course_id || "";
    let success = 0;
    for (const kpId of selectedKpIds) {
      try {
        const res = await fetch(
          `${API_BASE}/materials/${bindModalMaterial.id}/knowledge-links`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: user.username,
              course_id: courseId,
              knowledge_point_id: kpId,
            }),
          }
        );
        if (res.ok) success++;
      } catch {}
    }
    closeBindModal();
    if (success > 0) fetchDashboard();
  };

  // ── Recommend Modal ──
  const openRecModal = async (material) => {
    setRecModalMaterial(material);
    setRecResults([]);
    setRecLoading(true);
    try {
      const courseId = material.course_id || "";
      const res = await fetch(
        `${API_BASE}/materials/${material.id}/knowledge-links/recommend`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            course_id: courseId,
          }),
        }
      );
      if (res.ok) {
        const json = await res.json();
        setRecResults(json.recommendations || []);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "AI 推荐失败");
      }
    } catch {
      alert("AI 推荐失败，请稍后重试。");
    } finally {
      setRecLoading(false);
    }
  };

  const closeRecModal = () => {
    setRecModalMaterial(null);
    setRecResults([]);
  };

  const applyRec = async () => {
    if (!recModalMaterial || recResults.length === 0) return;
    setRecApplyLoading(true);
    try {
      const courseId = recModalMaterial.course_id || "";
      const res = await fetch(
        `${API_BASE}/materials/${recModalMaterial.id}/knowledge-links/apply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            course_id: courseId,
            links: recResults.map((r) => ({
              knowledge_point_id: r.knowledge_point_id,
              confidence: r.confidence,
              reason: r.reason,
            })),
          }),
        }
      );
      if (res.ok) {
        closeRecModal();
        fetchDashboard();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "应用失败");
      }
    } catch {
      alert("应用失败，请稍后重试。");
    } finally {
      setRecApplyLoading(false);
    }
  };

  // ── Delete link ──
  const deleteLink = async (materialId, linkId) => {
    if (!window.confirm("确认删除这个绑定关系吗？")) return;
    setActionLoading(linkId);
    try {
      const res = await fetch(
        `${API_BASE}/materials/${materialId}/knowledge-links/${linkId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      if (res.ok) fetchDashboard();
    } catch {}
    finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="empty-state">知识库数据加载中...</div>;
  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="ghost-button compact" onClick={fetchDashboard} style={{ marginTop: 12 }}>
          重试
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-state">
        <p>当前知识库还没有数据，可以先上传课程资料或生成知识点路线图。</p>
      </div>
    );
  }

  const ov = data.overview || {};
  const isEmpty = ov.material_count === 0 && ov.knowledge_point_count === 0;
  if (isEmpty) {
    return (
      <div className="empty-state">
        <p>当前知识库还没有数据，可以先上传课程资料或生成知识点路线图。</p>
        <button className="ghost-button compact" onClick={fetchDashboard} style={{ marginTop: 12 }}>
          刷新
        </button>
      </div>
    );
  }

  return (
    <div className="datacenter-shell">
      {/* ── Header ── */}
      <div className="datacenter-header">
        <div>
          <h2 style={{ margin: 0 }}>知识库中心</h2>
          <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: 14 }}>
            管理课程资料与知识点的关联，查看资料覆盖情况
          </p>
        </div>
        <button className="ghost-button compact" onClick={fetchDashboard}>
          刷新数据
        </button>
      </div>

      {/* ── Overview ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>知识库总览</h3>
        <div className="learning-stats-grid">
          <div className="learning-stat-card">
            <div className="learning-stat-label">资料总数</div>
            <div className="learning-stat-value">{ov.material_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">已关联资料</div>
            <div className="learning-stat-value">{ov.linked_material_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">未关联资料</div>
            <div className="learning-stat-value">{ov.unlinked_material_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">知识点总数</div>
            <div className="learning-stat-value">{ov.knowledge_point_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">已覆盖知识点</div>
            <div className="learning-stat-value">{ov.covered_knowledge_point_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">未覆盖知识点</div>
            <div className="learning-stat-value">{ov.uncovered_knowledge_point_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">覆盖率</div>
            <div className="learning-stat-value">{ov.coverage_rate}%</div>
          </div>
        </div>
      </section>

      {/* ── Course Summaries ── */}
      {data.course_summaries?.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>课程知识库概览</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: 12,
            }}
          >
            {data.course_summaries.map((cs, idx) => (
              <div
                key={idx}
                style={{
                  padding: 14,
                  borderRadius: 10,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 14 }}>
                  {getSubjectLabel ? getSubjectLabel(cs.course_id) : cs.course_name}
                </div>
                <div style={{ color: "#4b5563", lineHeight: 1.8 }}>
                  资料：{cs.material_count}（已关联 {cs.linked_material_count}）
                </div>
                <div style={{ color: "#4b5563", lineHeight: 1.8 }}>
                  知识点：{cs.knowledge_point_count}（已覆盖 {cs.covered_knowledge_point_count}）
                </div>
                <div style={{ fontWeight: 600, color: cs.coverage_rate > 0 ? "#059669" : "#9ca3af", marginTop: 4 }}>
                  覆盖率 {cs.coverage_rate}%
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Unlinked Materials ── */}
      {data.unlinked_materials?.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>未关联资料</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.unlinked_materials.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "#fffbeb",
                  border: "1px solid #fde68a",
                  fontSize: 14,
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{m.title}</span>
                  <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 13 }}>
                    {getSubjectLabel ? getSubjectLabel(m.course_id) : m.course_name}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="tiny-button"
                    onClick={() => openBindModal(m)}
                    style={{ color: "#0f766e" }}
                  >
                    绑定知识点
                  </button>
                  <button
                    className="tiny-button"
                    onClick={() => openRecModal(m)}
                    style={{ color: "#7c3aed" }}
                  >
                    AI 推荐关联
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Uncovered Points ── */}
      {data.uncovered_points?.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>覆盖不足知识点</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.uncovered_points.map((kp) => (
              <div
                key={kp.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  fontSize: 14,
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{kp.title}</span>
                  <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 13 }}>
                    {getSubjectLabel ? getSubjectLabel(kp.course_id) : kp.course_name}
                  </span>
                </div>
                <span style={{ fontSize: 13, color: "#9ca3af" }}>暂无关联资料</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Recent Links ── */}
      {data.recent_links?.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>最近关联记录</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {data.recent_links.map((r, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px solid #f1f5f9",
                  fontSize: 14,
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span>{r.material_title || `资料 #${r.material_id}`}</span>
                  <span style={{ color: "#9ca3af" }}>→</span>
                  <span style={{ fontWeight: 600 }}>
                    {r.knowledge_point_title || `知识点 #${r.knowledge_point_id}`}
                  </span>
                  <span
                    style={{
                      padding: "1px 6px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: r.source === "ai" ? "#ede9fe" : "#e0e7ff",
                      color: r.source === "ai" ? "#6b21a8" : "#3730a3",
                    }}
                  >
                    {SOURCE_LABELS[r.source] || r.source}
                  </span>
                  {r.confidence != null && r.source === "ai" && (
                    <span style={{ fontSize: 12, color: "#6b7280" }}>{r.confidence}%</span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "#9ca3af" }}>
                  {r.created_at && <span>{new Date(r.created_at + "Z").toLocaleString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Bind Modal ── */}
      {bindModalMaterial &&
        createPortal(
          <div
            className="modal-overlay"
            onClick={closeBindModal}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: "#fff",
                borderRadius: 16,
                padding: 24,
                maxWidth: 500,
                width: "90%",
                maxHeight: "70vh",
                overflow: "auto",
                boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
              }}
            >
              <h3 style={{ margin: "0 0 4px" }}>
                绑定知识点 — {bindModalMaterial.title}
              </h3>
              <p style={{ color: "#6b7280", fontSize: 13, margin: "0 0 16px" }}>
                {getSubjectLabel ? getSubjectLabel(bindModalMaterial.course_id) : bindModalMaterial.course_name}
              </p>
              {bindLoading && <p style={{ color: "#6b7280" }}>加载知识点...</p>}
              {!bindLoading && bindKpList.length === 0 && (
                <p style={{ color: "#9ca3af" }}>
                  当前课程还没有知识点，请先生成知识点路线图。
                </p>
              )}
              {bindKpList.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
                  {bindKpList.map((kp) => (
                    <label
                      key={kp.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 12px",
                        borderRadius: 8,
                        background: selectedKpIds.has(kp.id) ? "#f0fdf4" : "#f8fafc",
                        border: selectedKpIds.has(kp.id) ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
                        cursor: "pointer",
                        fontSize: 14,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedKpIds.has(kp.id)}
                        onChange={() => toggleKp(kp.id)}
                      />
                      <span>{kp.title}</span>
                    </label>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="ghost-button compact" onClick={closeBindModal}>
                  取消
                </button>
                <button
                  className="onboarding-primary-btn"
                  onClick={confirmBind}
                  disabled={selectedKpIds.size === 0 || bindLoading}
                >
                  确认绑定 ({selectedKpIds.size})
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* ── Recommend Modal ── */}
      {recModalMaterial &&
        createPortal(
          <div
            className="modal-overlay"
            onClick={closeRecModal}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: "#fff",
                borderRadius: 16,
                padding: 24,
                maxWidth: 550,
                width: "90%",
                maxHeight: "70vh",
                overflow: "auto",
                boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
              }}
            >
              <h3 style={{ margin: "0 0 4px" }}>
                AI 推荐关联 — {recModalMaterial.title}
              </h3>
              <p style={{ color: "#6b7280", fontSize: 13, margin: "0 0 16px" }}>
                {getSubjectLabel ? getSubjectLabel(recModalMaterial.course_id) : recModalMaterial.course_name}
              </p>
              {recLoading && <p style={{ color: "#6b7280" }}>AI 正在分析资料内容...</p>}
              {!recLoading && recResults.length === 0 && (
                <p style={{ color: "#9ca3af" }}>AI 没有找到合适的知识点关联。</p>
              )}
              {recResults.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
                  {recResults.map((r, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: "10px 14px",
                        borderRadius: 10,
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        fontSize: 14,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <span style={{ fontWeight: 600 }}>{r.knowledge_point_title}</span>
                        <span
                          style={{
                            padding: "1px 6px",
                            borderRadius: 4,
                            fontSize: 12,
                            background: r.confidence >= 70 ? "#f0fdf4" : r.confidence >= 40 ? "#fffbeb" : "#fef2f2",
                            color: r.confidence >= 70 ? "#059669" : r.confidence >= 40 ? "#d97706" : "#dc2626",
                          }}
                        >
                          匹配度 {r.confidence}%
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: 13, color: "#4b5563" }}>{r.reason}</p>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="ghost-button compact" onClick={closeRecModal}>
                  取消
                </button>
                <button
                  className="onboarding-primary-btn"
                  onClick={applyRec}
                  disabled={recResults.length === 0 || recApplyLoading}
                  style={{ background: "#7c3aed" }}
                >
                  {recApplyLoading ? "应用中..." : "应用推荐"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
