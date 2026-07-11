const DIRECTION_CONFIG = {
  exam_408: {
    serviceKey: "exam_11408",
    goalType: "exam_408",
    homePage: "examHome",
    onboardingPage: "onboarding",
  },
  university_course: {
    serviceKey: "course_learning",
    goalType: "university_course",
    homePage: "home",
    onboardingPage: "courseLearningOnboarding",
  },
  programming: {
    serviceKey: "programming",
    goalType: "programming",
    homePage: "programmingHome",
    onboardingPage: "programmingOnboarding",
  },
};

export async function switchLearningDirection({
  targetTrack,
  user,
  apiBase,
  setPage,
  onError,
  onPlansUpdate,
}) {
  const config = DIRECTION_CONFIG[targetTrack];
  if (!config || !setPage) return;

  let plans = user?.service_plans || {};
  try {
    const response = await fetch(`${apiBase}/me`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user?.username }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.user?.service_plans) {
      plans = data.user.service_plans;
      onPlansUpdate?.(plans);
    }
  } catch {
    // Keep the latest profile snapshot if the refresh fails.
  }

  if (plans?.[config.serviceKey]?.is_enabled) {
    setPage(config.homePage);
    return;
  }

  setPage(config.onboardingPage, {
    fromServiceSwitch: true,
    targetServiceKey: config.serviceKey,
    goalType: config.goalType,
    initialStep: 2,
    targetPage: config.homePage,
  });
  onError?.("");
}
