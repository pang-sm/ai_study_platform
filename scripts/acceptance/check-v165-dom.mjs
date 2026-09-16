import { chromium } from "playwright";
const WEB = "http://127.0.0.1:5173";
const USER = `mobile_v165_chk_${Date.now()}`;
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
await api.post("http://127.0.0.1:8000/register", { data: { username: USER, password: "x12345" } });
const page = await ctx.newPage();
await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded" });
await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V165", onboarding_completed: true })), USER);

async function dump(label, route, wait=2200) {
  await page.goto(`${WEB}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(wait);
  const info = await page.evaluate(() => {
    const txt = document.body.innerText;
    const headerStrong = document.querySelector(".exam-topbar-v15 > strong, .v16-practice-header > strong, .v16-select-header > strong")?.textContent || "";
    const hasIntro = txt.includes("展开知识图谱") || txt.includes("选择练习方式") || txt.includes("选择练习范围");
    const statusBadges = document.querySelectorAll(".v16-status-badge").length;
    const leafDots = document.querySelectorAll(".v16-tree-dot").length;
    const treeCards = document.querySelectorAll(".v16-tree-node").length;
    const navItems = [...document.querySelectorAll(".exam-bottom-nav-v15 button, .exam-bottom-nav-v14 button")].map(b => b.textContent.trim());
    const firstLine = txt.split("\n").filter(Boolean).slice(0, 6);
    return { headerStrong, hasIntro, statusBadges, leafDots, treeCards, navItems, firstLine };
  });
  console.log(`\n=== ${label} (${route}) ===`);
  console.log(JSON.stringify(info, null, 2));
}

await dump("knowledge", `/m/exam11408/computer_organization/chapters`);
await dump("practice-home", `/m/exam11408/computer_organization/practice`);
await dump("subject-select", `/m/exam11408`);
await dump("chapter", `/m/exam11408/computer_organization/practice?type=chapter`);
await browser.close();
