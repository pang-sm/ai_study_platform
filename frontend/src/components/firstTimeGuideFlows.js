export const COURSE_GUIDE_STEPS = [
  { selector: '[data-tour="course-courses"]', title: "从课程开始", description: "选择已加入的课程后，会进入该课程的真实学习工作台。" },
  { selector: '[data-tour="course-nav-knowledge"]', title: "知识脉络", description: "从这里进入当前课程的知识脉络，按章节和知识点安排学习。" },
  { selector: '[data-tour="course-nav-practice"]', title: "章节练习", description: "在这里进入当前课程的真实练习入口。" },
  { selector: '[data-tour="course-nav-materials"]', title: "资料库", description: "课程资料按课程保存，可在这里管理和使用。" },
  { selector: '[data-tour="course-nav-chat"]', title: "AI 问答", description: "可基于当前课程、知识点和资料向 AI 提问。" },
  { selector: '[data-tour="course-nav-lock-learning_plan"]', title: "会员专属能力", description: "带锁标识的学习计划仍受当前套餐限制；本引导不会解锁或发起购买。" },
];

export const EXAM_GUIDE_STEPS = [
  { selector: '[data-tour="exam-subjects"]', title: "四科入口", description: "从四个科目中进入真实的 11408 学科工作台。" },
  { selector: '[data-tour="exam-nav-knowledge"]', title: "知识脉络", description: "按当前科目的章节和知识点组织备考内容。" },
  { selector: '[data-tour="exam-nav-practice"]', title: "章节练习与真题", description: "从真实练习中心进入章节练习和历年真题。" },
  { selector: '[data-tour="exam-nav-materials"]', title: "资料库", description: "在当前科目的资料库中查看和管理学习资料。" },
  { selector: '[data-tour="exam-nav-ai"]', title: "AI 问答", description: "围绕当前科目、资料和知识点继续提问。" },
];
