import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const userStorageKey = "ai_study_platform_user";
const currentPageKey = "ai_study_current_page";

async function seedUserLocalStorage(page, username, nickname, extra = {}) {
  await page.addInitScript(
    ({ userStorageKey, currentPageKey, username, nickname, extra }) => {
      window.localStorage.setItem(
        userStorageKey,
        JSON.stringify({ username, nickname, grade: "", major: "", avatar: "avatar_1", onboarding_completed: true, learning_goals: [], ...extra }),
      );
      window.localStorage.setItem(currentPageKey, extra.__page || "home");
    },
    { userStorageKey, currentPageKey, username, nickname, extra },
  );
}

test("系统公告：登录后自动弹窗，关闭后不再弹", async ({ page }) => {
  const username = `ann_u_${Date.now()}`;
  const password = "ann-test-123456";
  await page.request.post(`${API}/register`, { data: { username, password } });
  await page.request.put(`${API}/me/profile?username=${encodeURIComponent(username)}`, {
    data: { nickname: "公告测试", grade: "", major: "", avatar: "avatar_1", onboarding_completed: true },
  });

  await seedUserLocalStorage(page, username, "公告测试", { __page: "home" });
  await page.goto("/");

  // 登录后自动弹出公告 Modal（若存在有效未读公告）
  await expect(page.locator(".annm-modal")).toBeVisible();
  await expect(page.locator(".annm-title")).toBeVisible();

  // 关闭（标记已读）
  await page.locator(".annm-close").click();
  await expect(page.locator(".annm-modal")).toHaveCount(0);

  // 刷新后不再重复弹出
  await page.reload();
  await page.waitForTimeout(1200);
  await expect(page.locator(".annm-modal")).toHaveCount(0);
});

test("管理员首页：新增今日AI调用与待处理事项", async ({ page }) => {
  const login = await page.request.post(`${API}/login`, {
    data: { username: "codex_admin", password: "codex-admin-123456" },
  });
  expect(login.ok()).toBeTruthy();

  await seedUserLocalStorage(page, "codex_admin", "客服管理员", {
    __page: "adminDashboard", is_admin: true, admin_role: "super_admin", plan: "admin",
  });
  await page.goto("/");

  // 新的 KPI 卡片：今日 AI 调用
  await expect(page.getByText("今日 AI 调用")).toBeVisible();
  // 待处理事项卡片
  await expect(page.getByText("待处理事项")).toBeVisible();
  await expect(page.getByText("用户反馈未读")).toBeVisible();
  await expect(page.getByText("待处理工单")).toBeVisible();
  await expect(page.getByText("等待用户确认")).toBeVisible();
  // 趋势图
  await expect(page.getByText("AI 使用趋势")).toBeVisible();
});
