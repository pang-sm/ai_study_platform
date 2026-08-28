import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const userStorageKey = "ai_study_platform_user";
const currentPageKey = "ai_study_current_page";

async function seedUserLocalStorage(page, username, nickname, extra = {}) {
  await page.addInitScript(
    ({ userStorageKey, currentPageKey, username, nickname, extra }) => {
      window.localStorage.setItem(
        userStorageKey,
        JSON.stringify({
          username,
          nickname,
          grade: "",
          major: "",
          avatar: "avatar_1",
          onboarding_completed: true,
          learning_goals: [],
          ...extra,
        }),
      );
      window.localStorage.setItem(currentPageKey, extra.__page || "home");
    },
    { userStorageKey, currentPageKey, username, nickname, extra },
  );
}

test("用户端：打开客服 Modal、提交工单并看到客服记录", async ({ page }) => {
  const username = `support_u_${Date.now()}`;
  const password = "support-test-123456";

  const reg = await page.request.post(`${API}/register`, { data: { username, password } });
  expect(reg.ok()).toBeTruthy();
  await page.request.put(`${API}/me/profile?username=${encodeURIComponent(username)}`, {
    data: { nickname: "客服测试用户", grade: "", major: "", avatar: "avatar_1", onboarding_completed: true },
  });

  await seedUserLocalStorage(page, username, "客服测试用户", { __page: "examProfile" });
  await page.goto("/");

  // 11408 个人主页底部出现可点击的客服入口
  await expect(page.getByText("如有疑问，请联系")).toBeVisible();
  await page.getByRole("button", { name: "客服支持" }).click();

  // Modal 打开
  await expect(page.locator(".csm-title")).toHaveText("客服支持");
  await expect(page.getByText("遇到问题？提交反馈后，管理员会在这里回复你。")).toBeVisible();

  // 进入「发起新问题」表单
  await page.getByRole("button", { name: "发起新问题" }).click();

  // 填写问题描述并提交
  await page.locator(".csm-textarea").first().fill("Python 资料库上传后消失，刷新也没有");
  await page.getByRole("button", { name: "提交工单" }).click();

  // 提交后进入聊天详情，能看到自己的首条消息
  await expect(page.locator(".csm-msg-bubble").first()).toContainText("Python 资料库上传后消失");

  // 返回我的问题列表，能看到这条客服记录
  await page.getByRole("button", { name: "← 我的问题" }).click();
  await expect(page.locator(".csm-ticket").first()).toBeVisible();

  // 关闭后仍停留当前页面（Modal 关闭，个人主页仍在）
  await page.locator(".csm-close").click();
  await expect(page.getByText("如有疑问，请联系")).toBeVisible();
});

test("管理员：用户反馈页面渲染并可查看工单", async ({ page }) => {
  const login = await page.request.post(`${API}/login`, {
    data: { username: "codex_admin", password: "codex-admin-123456" },
  });
  expect(login.ok()).toBeTruthy();

  // 管理员自己也创建一条工单，保证列表有数据可看
  await page.request.post(`${API}/support/tickets`, {
    data: {
      service_key: "programming",
      category: "functional_bug",
      title: "管理员自建测试工单",
      description: "用于管理员反馈页验收",
      source_url: "/programming/python_programming/materials",
      source_page: "编程学习 / Python / 资料库",
    },
  });

  await seedUserLocalStorage(page, "codex_admin", "客服管理员", {
    __page: "adminDashboard",
    is_admin: true,
    admin_role: "super_admin",
    plan: "admin",
  });
  await page.goto("/");

  // 进入「用户反馈」一级分栏
  await page.getByRole("button", { name: /用户反馈/ }).click();

  // 页面渲染：筛选标签 + 工单列表
  await expect(page.getByRole("button", { name: "全部" })).toBeVisible();
  await expect(page.getByRole("button", { name: "待处理" })).toBeVisible();
  await expect(page.getByRole("button", { name: "处理中" })).toBeVisible();
  await expect(page.getByRole("button", { name: "等待确认" })).toBeVisible();
  await expect(page.getByRole("button", { name: "已解决" })).toBeVisible();
  await expect(page.getByRole("button", { name: "未解决" })).toBeVisible();

  // 列表中能看到工单标题
  await expect(page.locator(".asc-item").first()).toBeVisible();

  // 打开工单，出现信息卡与聊天区域
  await page.locator(".asc-item").first().click();
  await expect(page.locator(".asc-info-card")).toBeVisible();
  await expect(page.getByText("当前状态")).toBeVisible();
  await expect(page.getByRole("button", { name: /标记为等待用户确认/ })).toBeVisible();
});
