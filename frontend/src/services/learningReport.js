const API_BASE = "/api";

function toPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${Math.round(n)}%`;
}

function formatMinutes(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours <= 0) return `${mins} 分钟`;
  if (mins === 0) return `${hours} h`;
  return `${hours} h ${mins} m`;
}

function getKnowledgeName(item, index) {
  if (!item || typeof item !== "object") return `知识点 ${index + 1}`;
  return item.knowledge_point_name || item.knowledgePointName || item.title || item.name || `知识点 ${index + 1}`;
}

function adaptDashboardReport(data, { start, end }) {
  const overview = data?.overview || {};
  const weakPoints = Array.isArray(data?.weak_points) ? data.weak_points : [];
  const recommendations = Array.isArray(data?.recommendations) ? data.recommendations : [];
  const trend = Array.isArray(data?.trend) ? data.trend : [];

  const strengths = [];
  if (Number(overview.completed_tasks || 0) > 0) strengths.push(`已完成 ${overview.completed_tasks} 个学习任务`);
  if (Number(overview.practice_accuracy || 0) >= 70) strengths.push(`练习正确率达到 ${toPercent(overview.practice_accuracy)}`);
  if (Number(overview.active_days_this_week || 0) > 0) strengths.push(`本阶段保持 ${overview.active_days_this_week} 天学习记录`);

  const weaknesses = weakPoints.slice(0, 5).map(getKnowledgeName);
  const suggestions = recommendations.length > 0
    ? recommendations.slice(0, 5).map((item) => (typeof item === "string" ? item : item.title || item.content || item.text || "安排一次专项复习"))
    : weaknesses.slice(0, 3).map((item) => `优先复习「${item}」并完成对应练习`);

  return {
    start,
    end,
    summary: {
      overall_summary:
        "当前后端暂未提供新版 AI 报告接口，系统已基于学习数据中心记录生成临时分析。建议结合学习时长、练习正确率和薄弱知识点安排下一阶段复习。",
      strengths: strengths.length > 0 ? strengths : ["已有学习记录可用于后续趋势分析"],
      weaknesses: weaknesses.length > 0 ? weaknesses : ["当前范围内暂无明确薄弱知识点"],
      suggestions: suggestions.length > 0 ? suggestions : ["继续完成学习任务，并保持错题复盘节奏"],
    },
    metrics: {
      study_time: formatMinutes(overview.total_study_minutes),
      knowledge_points: String(overview.completed_tasks ?? overview.knowledge_points ?? "--"),
      accuracy: toPercent(overview.practice_accuracy),
      study_days: `${overview.active_days_this_week ?? overview.study_days ?? "--"} 天`,
    },
    trend,
    errors: weakPoints.map((item, index) => ({
      knowledge_point: getKnowledgeName(item, index),
      count: item.error_count || item.wrong_count || item.practice_count || 0,
      mastery: item.mastery ?? item.progress ?? item.mastery_rate,
    })),
  };
}

export async function generateAIReport({ rangeType, startDate, endDate, username, mode, courseName } = {}) {
  const body = {
    username,
    range_type: rangeType || "7d",
    start_date: startDate || null,
    end_date: endDate || null,
  };
  if (mode === "course_learning" && courseName) {
    body.mode = "course_learning";
    body.course_name = courseName;
  }
  const res = await fetch(`${API_BASE}/learning-report/ai-generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok) return data;
  throw new Error(data.detail || "AI报告生成失败，请稍后重试。");
}

export async function fetchLearningReport({ start, end, username } = {}) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (username) params.set("username", username);

  const res = await fetch(`${API_BASE}/learning/report?${params.toString()}`);
  const data = await res.json().catch(() => ({}));

  if (res.ok) {
    return data;
  }

  if (username) {
    const dashboardParams = new URLSearchParams({ username });
    const dashboardRes = await fetch(`${API_BASE}/learning/dashboard?${dashboardParams.toString()}`);
    const dashboardData = await dashboardRes.json().catch(() => ({}));
    if (dashboardRes.ok) {
      return adaptDashboardReport(dashboardData, { start, end });
    }
  }

  throw new Error(data.detail || "学习报告加载失败，请稍后重试。");
}
