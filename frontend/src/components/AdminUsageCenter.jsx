import { useEffect, useState } from "react";

const API_BASE = "/api";

const FEATURE_LABELS = {
  chat:"AI 问答", code_analyze:"代码分析", challenge_generate:"编程题生成",
  learning_diagnosis:"学习诊断", knowledge_generate:"知识点生成",
  learning_plan_generate:"学习计划生成", material_link_recommend:"资料关联推荐",
  question_generate:"题目生成", question_feedback:"题目反馈",
  course_report:"课程报告生成", challenge_explain:"挑战题解答", challenge_test_gen:"测试用例生成",
  code_execute:"代码执行", paper_import:"试卷导入",
};

const PLAN_NAMES = { free:"免费版", pro:"专业版", admin:"管理员" };
const STAT_COLORS = ["#eff6ff","#f0fdf4","#fef3c7","#ede9fe"];
const STAT_ICONS = ["🤖","👤","⭐","🔑"];

export default function AdminUsageCenter({ user }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [planForm, setPlanForm] = useState({ username:"", plan:"free" });
  const [planMsg, setPlanMsg] = useState("");

  const fetchSummary = async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/usage-summary?admin_username=${encodeURIComponent(user.username)}`);
      if(!res.ok){ const b=await res.json().catch(()=>({})); throw new Error(b.detail||"加载失败"); }
      setSummary(await res.json());
    }catch(e){ setError(e.message||"加载失败"); }
    finally{ setLoading(false); }
  };

  useEffect(()=>{ fetchSummary(); },[user.username]);

  const handlePlanUpdate = async () => {
    setPlanMsg(""); const target=planForm.username.trim();
    if(!target){ setPlanMsg("请输入目标用户名"); return; }
    try {
      const res=await fetch(`${API_BASE}/admin/users/${encodeURIComponent(target)}/plan`,{
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ admin_username:user.username, plan:planForm.plan }),
      });
      const data=await res.json();
      if(!res.ok) throw new Error(data.detail||"修改失败");
      setPlanMsg(`已为 ${data.username} 设置套餐：${PLAN_NAMES[data.plan]||data.plan}`);
      fetchSummary();
    }catch(e){ setPlanMsg(e.message||"修改失败"); }
  };

  if(loading) return <div className="empty-state">加载中...</div>;
  if(error) return <div className="empty-state"><p>{error}</p><button className="primary-button" onClick={fetchSummary}>重试</button></div>;
  if(!summary) return null;

  const stats = [
    { label:"今日 AI 调用", value:summary.today_total, color:"#eff6ff", icon:"🤖" },
    { label:"免费用户", value:summary.plan_counts?.free||0, color:"#f0fdf4", icon:"👤" },
    { label:"专业版用户", value:summary.plan_counts?.pro||0, color:"#fef3c7", icon:"⭐" },
    { label:"管理员", value:summary.plan_counts?.admin||0, color:"#ede9fe", icon:"🔑" },
  ];

  return (
    <div className="admin-usage-center">
      {/* Header */}
      <div className="auc-header">
        <div className="auc-header-left">
          <h1>管理后台</h1>
          <p>查看今日平台调用、用户套餐分布与最近使用记录</p>
        </div>
        <div className="auc-header-right">
          <button className="primary-button" onClick={fetchSummary}>刷新数据</button>
        </div>
      </div>

      {/* Stats */}
      <div className="auc-stats">
        {stats.map((s,i) => (
          <div className="auc-stat" key={i}>
            <div className="auc-stat-icon" style={{ background:s.color }}>{s.icon}</div>
            <div><div className="auc-stat-val">{s.value}</div><div className="auc-stat-lbl">{s.label}</div></div>
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="auc-grid">
        {/* Feature Usage */}
        <div className="auc-card">
          <h3 className="auc-card-title">📊 今日功能用量</h3>
          {Object.keys(summary.feature_stats||{}).length===0 ? (
            <div className="auc-empty">今日暂无 AI 调用记录</div>
          ) : (
            <div className="auc-feature-list">
              {Object.entries(summary.feature_stats||{}).map(([f,c]) => (
                <div className="auc-feature-row" key={f}>
                  <span className="auc-feature-name">{FEATURE_LABELS[f]||f}</span>
                  <span className={`auc-feature-badge ${c>0?"auc-feature-badge--active":"auc-feature-badge--zero"}`}>{c}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Plan */}
        <div className="auc-card">
          <h3 className="auc-card-title">⚙️ 修改用户套餐</h3>
          <p style={{margin:"0 0 12px",fontSize:"0.84rem",color:"#64748b"}}>输入用户名并选择目标套餐，确认后会更新该用户的额度策略。</p>
          <div className="auc-plan-form">
            <div className="auc-plan-row">
              <input className="field" placeholder="目标用户名" value={planForm.username} onChange={e=>setPlanForm(p=>({...p,username:e.target.value}))} />
              <select className="field" value={planForm.plan} onChange={e=>setPlanForm(p=>({...p,plan:e.target.value}))}>
                <option value="free">免费版</option><option value="pro">专业版</option><option value="admin">管理员</option>
              </select>
            </div>
            <button className="primary-button" onClick={handlePlanUpdate} style={{width:"100%"}}>确认修改</button>
          </div>
          {planMsg && <p className="auc-plan-msg" style={{color:planMsg.includes("失败")?"#dc2626":"#16a34a"}}>{planMsg}</p>}
        </div>
      </div>

      {/* Table */}
      <div className="auc-card">
        <h3 className="auc-card-title">📋 最近使用记录</h3>
        <div className="auc-table-wrap">
          <table className="auc-table">
            <thead><tr><th>用户</th><th>功能</th><th>模型</th><th>估算 Tokens</th><th>状态</th><th>时间</th></tr></thead>
            <tbody>
              {(summary.recent_logs||[]).map((log,i)=>(
                <tr key={i}>
                  <td style={{fontWeight:600}}>{log.username}</td>
                  <td>{FEATURE_LABELS[log.feature]||log.feature}</td>
                  <td>{log.model?<span className="auc-model-tag">{log.model}</span>:"-"}</td>
                  <td style={{fontVariantNumeric:"tabular-nums"}}>{log.estimated_tokens||0}</td>
                  <td>{log.status==="success"?<span className="auc-status-success">成功</span>:<span className="auc-status-other">{log.status||"-"}</span>}</td>
                  <td style={{fontSize:"0.8rem",color:"#94a3b8"}}>{log.created_at?new Date(log.created_at).toLocaleString("zh-CN"):"-"}</td>
                </tr>
              ))}
              {(summary.recent_logs||[]).length===0&&(<tr><td colSpan={6} style={{textAlign:"center",color:"#94a3b8",padding:20}}>暂无记录</td></tr>)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
