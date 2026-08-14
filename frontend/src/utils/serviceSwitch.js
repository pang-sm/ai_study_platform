const DIRECTION_CONFIG = {
  exam_408: {
    serviceKey: "exam_11408",
    goalType: "exam_408",
    homePage: "examHome",
    onboardingPage: "onboarding",
    onboardingCompletionField: "exam_408_onboarding_completed",
  },
  university_course: {
    serviceKey: "course_learning",
    goalType: "university_course",
    homePage: "home",
    onboardingPage: "courseLearningOnboarding",
    onboardingCompletionField: "course_learning_onboarding_completed",
  },
  programming: {
    serviceKey: "programming",
    goalType: "programming",
    homePage: "programmingHome",
    onboardingPage: "programmingOnboarding",
    onboardingCompletionField: "programming_onboarding_completed",
  },
};

export async function switchLearningDirection({
  targetTrack,
  user,
  apiBase,
  setPage,
  onError,
  onPlansUpdate,
  returnPage,
}) {
  const config = DIRECTION_CONFIG[targetTrack];
  if (!config || !setPage) return;

  let plans = user?.service_plans || {};
  let tracks = user?.tracks || [];
  try {
    const response = await fetch(`${apiBase}/me`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user?.username }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.user?.service_plans) {
      plans = data.user.service_plans;
      tracks = data.user.tracks || tracks;
      onPlansUpdate?.(plans);
    }
  } catch {
    // Keep the latest profile snapshot if the refresh fails.
  }

  const targetTrackRecord = tracks.find((track) => track.track_type === targetTrack);
  const onboardingDetail = targetTrackRecord?.onboarding_detail || {};
  const targetTrackReady = Boolean(targetTrackRecord)
    && onboardingDetail[config.onboardingCompletionField] === true;

  if (plans?.[config.serviceKey]?.is_enabled && targetTrackReady) {
    setPage(config.homePage);
    return;
  }

  setPage(config.onboardingPage, {
    fromServiceSwitch: true,
    targetServiceKey: config.serviceKey,
    goalType: config.goalType,
    initialStep: 2,
    targetPage: config.homePage,
    returnPage,
  });
  onError?.("");
}
