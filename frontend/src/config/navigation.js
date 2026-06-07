/**
 * 统一导航配置
 * 首页快捷入口和左侧栏复用同一套配置，避免入口不一致。
 */

export const APP_PAGES = {
  // ── 核心学习 ──
  home:              { key: "home",              icon: "🏠",  label: "首页",             group: "core" },
  dashboard:         { key: "dashboard",         icon: "📋",  label: "课程工作台",       group: "core" },
  chat:              { key: "chat",              icon: "💬",  label: "AI 问答",          group: "core" },
  knowledgeLearning: { key: "knowledgeLearning", icon: "🎯",  label: "知识点学习",       group: "core" },
  taskCenter:        { key: "taskCenter",        icon: "✅",  label: "任务中心",         group: "core" },
  practiceCenter:    { key: "practiceCenter",    icon: "📝",  label: "练习中心",         group: "core" },
  codeStudio:        { key: "codeStudio",        icon: "</>", label: "编程学习助手",     group: "core" },

  // ── 学习沉淀 ──
  learningDataCenter:   { key: "learningDataCenter",   icon: "📊", label: "学习数据中心", group: "review" },
  learningReportCenter: { key: "learningReportCenter", icon: "📄", label: "学习报告",     group: "review" },
  reviewCenter:         { key: "reviewCenter",         icon: "🔄", label: "复盘中心",     group: "review" },
  learningPlanCenter:   { key: "learningPlanCenter",   icon: "📅", label: "AI 学习计划",  group: "review" },
  knowledgeBaseCenter:  { key: "knowledgeBaseCenter",  icon: "📚", label: "知识库中心",   group: "review" },

  // ── 个人与系统 ──
  profile:    { key: "profile",    icon: "👤", label: "个人资料", group: "personal" },
  profileEdit:{ key: "profileEdit",icon: "⚙️", label: "学习设置", group: "personal" },
  quotaCenter:{ key: "quotaCenter",icon: "💎", label: "我的额度", group: "personal" },
  membership: { key: "membership", icon: "👑", label: "会员中心", group: "personal" },
};

/**
 * 左侧栏导航分组
 * group 为 sidebar 分组键；adminOnly 表示仅管理员可见。
 */
export const SIDEBAR_NAV_GROUPS = [
  {
    id: "core",
    title: "核心学习",
    items: [
      APP_PAGES.home,
      APP_PAGES.dashboard,
      APP_PAGES.chat,
      APP_PAGES.knowledgeLearning,
      APP_PAGES.taskCenter,
      APP_PAGES.practiceCenter,
      APP_PAGES.codeStudio,
    ],
  },
  {
    id: "review",
    title: "学习沉淀",
    items: [
      APP_PAGES.learningDataCenter,
      APP_PAGES.learningReportCenter,
      APP_PAGES.reviewCenter,
      APP_PAGES.knowledgeBaseCenter,
    ],
  },
  {
    id: "personal",
    title: "个人与系统",
    items: [
      APP_PAGES.profile,
      APP_PAGES.profileEdit,
      APP_PAGES.quotaCenter,
      APP_PAGES.membership,
    ],
  },
];

/**
 * 首页快捷入口（核心功能卡片）
 * 注意：资料库属于课程工作台内部 Tab，不在此处作为独立一级入口。
 */
export const HOME_CORE_FEATURES = [
  {
    id: APP_PAGES.chat.key,
    icon: APP_PAGES.chat.icon,
    title: "AI 智能问答",
    desc: "随时向 AI 提问，获取知识点讲解、解题思路和学习建议",
    color: "#2563eb",
  },
  {
    id: APP_PAGES.dashboard.key,
    icon: APP_PAGES.dashboard.icon,
    title: "课程工作台",
    desc: "管理你的学习资料、聊天记录和学习进度",
    color: "#059669",
  },
  {
    id: APP_PAGES.practiceCenter.key,
    icon: APP_PAGES.practiceCenter.icon,
    title: "练习中心",
    desc: "按知识点刷题练习，AI 自动反馈，支持选择题和简答题",
    color: "#7c3aed",
  },
  {
    id: APP_PAGES.codeStudio.key,
    icon: APP_PAGES.codeStudio.icon,
    title: "编程学习助手",
    desc: "在线练习编程，AI 帮你分析代码和解答编程问题",
    color: "#db2777",
  },
  {
    id: APP_PAGES.taskCenter.key,
    icon: APP_PAGES.taskCenter.icon,
    title: "学习任务中心",
    desc: "创建和管理学习任务，让 AI 帮你生成个性化学习计划",
    color: "#ea580c",
  },
  {
    id: APP_PAGES.knowledgeLearning.key,
    icon: APP_PAGES.knowledgeLearning.icon,
    title: "知识点学习",
    desc: "按知识点体系逐步学习，支持资料路线和平台推荐路线",
    color: "#0f766e",
  },
];

/**
 * 首页学习工具入口
 */
export const HOME_LEARNING_TOOLS = [
  {
    id: APP_PAGES.learningDataCenter.key,
    icon: APP_PAGES.learningDataCenter.icon,
    title: "学习数据中心",
    desc: "全局学习统计",
  },
  {
    id: APP_PAGES.reviewCenter.key,
    icon: APP_PAGES.reviewCenter.icon,
    title: "复盘中心",
    desc: "错题与薄弱点",
  },
  {
    id: APP_PAGES.learningReportCenter.key,
    icon: APP_PAGES.learningReportCenter.icon,
    title: "学习报告",
    desc: "周报月报总结",
  },
  {
    id: APP_PAGES.quotaCenter.key,
    icon: APP_PAGES.quotaCenter.icon,
    title: "我的额度",
    desc: "用量与套餐",
  },
  {
    id: APP_PAGES.profileEdit.key,
    icon: APP_PAGES.profileEdit.icon,
    title: "学习设置",
    desc: "科目与目标管理",
  },
];

/**
 * 首页搜索下拉推荐入口
 */
export const HOME_SEARCH_RECOMMEND_ENTRIES = [
  APP_PAGES.taskCenter,
  APP_PAGES.practiceCenter,
  APP_PAGES.codeStudio,
  APP_PAGES.learningReportCenter,
  APP_PAGES.learningDataCenter,
  // 注：资料库入口已移除，用户通过课程工作台访问
];
