import { expect, test } from "@playwright/test";

const userStorageKey = "ai_study_platform_user";
const currentPageKey = "ai_study_current_page";

async function prepareUser(request) {
  const username = `codex_ldc_${Date.now()}`;
  const password = "codex-test-123456";

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

  const taskRes = await request.post("http://127.0.0.1:8000/learning/tasks", {
    data: {
      username,
      course_id: "c_programming",
      title: "自动验证任务",
      description: "用于学习数据中心联动测试",
      task_type: "review",
      status: "done",
      source: "manual",
      priority: "medium",
    },
  });
  expect(taskRes.ok()).toBeTruthy();

  return username;
}

test("学习数据中心使用真实数据并支持页面联动", async ({ page, request }) => {
  const username = await prepareUser(request);
  const consoleErrors = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    consoleErrors.push(error.message);
  });

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
      window.localStorage.setItem("ai_study_sidebar_collapsed", "false");
    },
    { userStorageKey, currentPageKey, username },
  );

  await page.goto("/");
  await expect(page.getByText("AI 学习助手")).toBeVisible();

  const sidebar = page.locator(".sb-sidebar");
  await page.locator(".sb-nav").getByRole("button", { name: /学习数据中心/ }).click();

  await expect(page.getByRole("heading", { name: "学习数据中心", level: 1 })).toBeVisible();
  await expect(page.getByText("查看你的学习表现、进度趋势与薄弱点分析")).toBeVisible();
  await expect(page.locator(".sb-nav-item.active", { hasText: "学习数据中心" })).toBeVisible();

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
    "未设置目标，使用展示参考线",
  ];
  for (const text of expectedTexts) {
    await expect(page.getByText(text).first()).toBeVisible();
  }

  await expect(page.getByText("学习数据加载失败")).toHaveCount(0);
  await expect(page.getByText("请稍后重试")).toHaveCount(0);
  await expect(page.getByText("未命名知识点")).toHaveCount(0);
  await expect(page.getByText(/^测试$/)).toHaveCount(0);
  await expect(page.getByText("看起来真实")).toHaveCount(0);
  await expect(
    page.locator(".app-shell > .workspace-topbar .subject-pill.panel-pill", {
      hasText: "学习数据中心",
    }),
  ).toHaveCount(0);

  const navBoxes = await page.locator(".sb-nav-item").evaluateAll((items) =>
    items.map((item) => {
      const rect = item.getBoundingClientRect();
      const label = item.querySelector(".sb-nav-label")?.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, height: rect.height, width: rect.width, labelWidth: label?.width || 0 };
    }),
  );
  for (let i = 0; i < navBoxes.length; i += 1) {
    expect(navBoxes[i].height).toBeGreaterThanOrEqual(36);
    expect(navBoxes[i].width).toBeGreaterThan(120);
    expect(navBoxes[i].labelWidth).toBeGreaterThan(20);
    if (i > 0) {
      expect(navBoxes[i].top).toBeGreaterThanOrEqual(navBoxes[i - 1].bottom - 1);
    }
  }
  const sidebarBox = await sidebar.boundingBox();
  expect(sidebarBox.width).toBeGreaterThanOrEqual(230);

  await page.locator(".ldc-kpi-grid").getByRole("button", { name: /^完成任务数/ }).click();
  await expect(page.locator(".sb-nav-item.active", { hasText: "任务中心" })).toBeVisible();
  await page.locator(".sb-nav").getByRole("button", { name: /学习数据中心/ }).click();

  await page.locator(".ldc-kpi-grid").getByRole("button", { name: /^练习正确率/ }).click();
  await expect(page.locator(".sb-nav-item.active", { hasText: "练习中心" })).toBeVisible();
  await page.locator(".sb-nav").getByRole("button", { name: /学习数据中心/ }).click();

  await page.screenshot({
    path: "test-results/learning-data-center-linked.png",
    fullPage: true,
  });

  await page.getByRole("button", { name: "去学习设置" }).click();
  await expect(page.getByRole("heading", { name: "编辑学习信息" })).toBeVisible();

  const reactErrors = consoleErrors.filter((text) => /react|exception|failed/i.test(text));
  expect(reactErrors).toEqual([]);
});
