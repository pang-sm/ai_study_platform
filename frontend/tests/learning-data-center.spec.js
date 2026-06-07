import { expect, test } from "@playwright/test";

const userStorageKey = "ai_study_platform_user";
const currentPageKey = "ai_study_current_page";

test("学习数据中心页面模块完整且无顶部重复胶囊条", async ({ page, request }) => {
  const username = `codex_ldc_${Date.now()}`;
  const password = "codex-test-123456";
  const consoleErrors = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    consoleErrors.push(error.message);
  });

  const registerRes = await request.post("http://127.0.0.1:8000/register", {
    data: { username, password },
  });
  expect(registerRes.ok()).toBeTruthy();

  const profileRes = await request.put(
    `http://127.0.0.1:8000/me/profile?username=${encodeURIComponent(username)}`,
    {
      data: {
        nickname: "自动验证用户",
        grade: "",
        major: "",
        avatar: "avatar_1",
        onboarding_completed: true,
      },
    },
  );
  expect(profileRes.ok()).toBeTruthy();

  await page.addInitScript(
    ({ userStorageKey, currentPageKey, username }) => {
      window.localStorage.setItem(
        userStorageKey,
        JSON.stringify({
          username,
          nickname: "自动验证用户",
          grade: "",
          major: "",
          avatar: "avatar_1",
          onboarding_completed: true,
          learning_goals: [],
        }),
      );
      window.localStorage.setItem(currentPageKey, "home");
    },
    { userStorageKey, currentPageKey, username },
  );

  await page.goto("/");
  await expect(page.getByText("AI 学习助手")).toBeVisible();

  await page.locator(".sb-nav").getByRole("button", { name: /学习数据中心/ }).click();

  await expect(page.getByRole("heading", { name: "学习数据中心", level: 1 })).toBeVisible();
  await expect(page.getByText("查看你的学习表现、进度趋势与薄弱点分析")).toBeVisible();

  const expectedTexts = [
    "总学习时长",
    "本周学习天数",
    "完成任务数",
    "练习正确率",
    "AI 提问次数",
    "连续学习天数",
    "学习趋势",
    "学科掌握度",
    "薄弱知识点",
    "学习热力图",
    "最近学习记录",
    "本周目标达成",
    "AI 学习建议",
  ];
  for (const text of expectedTexts) {
    await expect(page.getByText(text).first()).toBeVisible();
  }

  await expect(page.getByText("学习数据加载失败")).toHaveCount(0);
  await expect(page.getByText("请稍后重试")).toHaveCount(0);
  await expect(
    page.locator(".app-shell > .workspace-topbar .subject-pill.panel-pill", {
      hasText: "学习数据中心",
    }),
  ).toHaveCount(0);
  await expect(page.locator(".sb-nav-item.active", { hasText: "学习数据中心" })).toBeVisible();

  await page.screenshot({
    path: "test-results/learning-data-center.png",
    fullPage: true,
  });

  const reactErrors = consoleErrors.filter((text) => /react|error|exception|failed/i.test(text));
  expect(reactErrors).toEqual([]);
});
