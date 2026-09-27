// Acceptance pass for the 考研学习 home, the 408 chooser and a paper's knowledge outline.
//
// Same gate as `p7b-acceptance.spec.ts` / `p7c-spaces.spec.ts`: the authenticated E2E harness
// must be up, a FRESH dev server must point at it, and the run must be marked. Without that the
// file skips, because nothing here renders without a session.
//
//   1. bash scripts/start-e2e-backend.sh --json --port 8000
//   2. VITE_API_BASE_URL=<base_url> npm run dev      (fresh — never reuse a long-running server)
//   3. EXAM_HOME_E2E=1 EXAM_HOME_API_BASE=<base_url> \
//        npx playwright test tests/e2e/exam-home-redesign.spec.ts
//
// What it checks that jsdom cannot: that the home shows every subject at four widths without a
// second 考试方案 block, that the 408 card's only button is fully inside its card at every width,
// that choosing a paper lands in that paper's outline rather than on a 概览 page, that the strip
// carries every page of a paper — including the 对话 and 资料库 that are pages OF it — and that
// changing 考试方案 really changes the home.
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = process.env.EXAM_HOME_API_BASE ?? '';
const ENABLED = process.env.EXAM_HOME_E2E === '1' && API !== '';

const USERNAME = 'e2e_learner';
const PASSWORD = 'e2e-learner-pass-1';

const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
];

const PAPERS = ['数据结构', '计算机组成原理', '操作系统', '计算机网络'];

async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('账号或邮箱').fill(USERNAME);
  // `exact` matters: the password panel is announced as 「密码登录」 and Playwright's label
  // matching is substring-based, so the loose form would also resolve to the panel.
  await page.getByLabel('密码', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page.getByRole('navigation', { name: '主导航', exact: true })).toBeVisible({
    timeout: 20_000,
  });
}

async function assertNoHorizontalOverflow(page: Page, label: string) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `${label} horizontal overflow`).toBeLessThanOrEqual(1);
}

/** The one control that changes which of the four papers is open. */
const moduleSwitcher = (page: Page) => page.getByLabel('切换 408 学习科目');

/** One subject's card on the home, found by the heading that names it. */
const subjectCard = (page: Page, name: string) =>
  page.getByRole('region', { name: '我的考试科目' }).locator('li').filter({
    has: page.getByRole('heading', { name }),
  });

// Serial within this file: the last home case changes the learner's 考试方案, and the earlier
// cases read it. Running them in parallel would make those flaky for no gain.
test.describe.configure({ mode: 'serial' });

test.describe('考研学习 home', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('shows the subjects and nothing else, in the order a learner asks for them', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      await page.goto('/exam');

      // The page's own title is the block it exists for. 考研学习 is where the learner already
      // is — the global navigation says so — and repeating it spent the first screen on nothing.
      await expect(page.getByRole('heading', { level: 1, name: '我的考试科目' })).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.getByRole('heading', { name: '考研学习' })).toHaveCount(0);
      await expect(page.getByRole('navigation', { name: '考研学习导航' })).toHaveCount(0);
      await expect(page.getByRole('link', { name: '我的备考' })).toHaveCount(0);

      // The 考试方案 block is gone. What it said — the exam and its year, the direction, the
      // caveat — was a second telling of the subjects above it, and the place to change the
      // combination is the action on this block.
      await expect(page.getByRole('region', { name: '考试方案' })).toHaveCount(0);
      await expect(page.getByRole('heading', { name: '考试方案' })).toHaveCount(0);
      await expect(page.getByText('全国硕士研究生招生考试（统考）')).toHaveCount(0);
      await expect(page.getByText(/备考方向/)).toHaveCount(0);
      await expect(page.getByText('具体考试科目以目标院校当年招生专业目录为准。')).toHaveCount(0);
      await expect(
        page.getByRole('region', { name: '我的考试科目' }).getByRole('link', { name: '修改考试方案' }),
      ).toHaveAttribute('href', '/exam/setup');

      // 408 is the one subject this build can study in full, and the card says the three things
      // a learner reads it for: which line of the plan, its name, and the way in.
      const cs = subjectCard(page, '计算机学科专业基础 408');
      await expect(cs.getByText('专业课')).toBeVisible();
      const entry = cs.getByRole('link', { name: /继续学习 · .+|进入 408/ });
      await expect(entry).toHaveAttribute('href', /^\/exam\/cs408(\/knowledge\?module=.+)?$/);
      await expect(cs.getByText('完整学习功能已开放')).toHaveCount(0);
      await expect(cs.getByText('全国统考计算机学科专业基础综合（408）')).toHaveCount(0);

      // The card's own button is inside the card, with room under it: it is the point of the card
      // and must never read as pressed against the border or clipped by it.
      const card = await cs.boundingBox();
      const button = await entry.boundingBox();
      expect(card, 'the 408 card is laid out').not.toBeNull();
      expect(button, 'the 408 entry is laid out').not.toBeNull();
      if (card && button) {
        expect(button.x, 'entry inside the card').toBeGreaterThanOrEqual(card.x);
        expect(button.x + button.width, 'entry inside the card').toBeLessThanOrEqual(card.x + card.width);
        expect(button.y + button.height, 'entry fully visible').toBeLessThanOrEqual(card.y + card.height);
        expect(card.y + card.height - (button.y + button.height), 'room under the entry').toBeGreaterThan(12);
      }

      // The card is a way in, not a second index of what is behind it.
      for (const paper of PAPERS) {
        await expect(cs.getByRole('heading', { name: paper })).toHaveCount(0);
      }
      await expect(cs.getByRole('link', { name: '知识脉络' })).toHaveCount(0);
      await expect(cs.getByRole('link', { name: '真题' })).toHaveCount(0);

      await assertNoHorizontalOverflow(page, `exam home at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/home-${size.width}.png`, fullPage: true });
    }

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam');
    await expect(page.getByRole('heading', { level: 1, name: '我的考试科目' })).toBeVisible({ timeout: 20_000 });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on the exam home').toEqual([]);
  });

  test('408 opens on four papers and one sentence — the names — and nothing else', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      await page.goto('/exam/cs408');

      await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible({ timeout: 20_000 });
      // The paragraph explaining what 408 is made of is gone: the four names below it are the
      // page, and choosing one is the whole action.
      await expect(page.getByText(/由四门科目组成/)).toHaveCount(0);
      await expect(page.getByText(/先选一门/)).toHaveCount(0);

      // Four ways in, each carrying the paper it names — straight into that paper's outline.
      for (const paper of PAPERS) {
        await expect(page.getByRole('link', { name: new RegExp(`^${paper}`) })).toHaveAttribute(
          'href',
          new RegExp(`^/exam/cs408/knowledge\\?module=`),
        );
      }

      // No tool links per row, no numbering, and no tool strip before a paper has been chosen.
      for (const tool of ['AI 对话', '资料库', '知识脉络', '章节练习', '真题']) {
        await expect(page.getByRole('link', { name: tool })).toHaveCount(0);
      }
      await expect(page.locator('main').getByText('01', { exact: true })).toHaveCount(0);
      await expect(page.getByRole('navigation', { name: 'CS408 工具导航' })).toHaveCount(0);

      // And a way back that is stated, not left to the browser's history.
      await expect(page.getByRole('link', { name: '返回', exact: true })).toHaveAttribute('href', '/exam');

      await assertNoHorizontalOverflow(page, `cs408 chooser at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/cs408-${size.width}.png`, fullPage: true });
    }

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam/cs408');
    await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible({ timeout: 20_000 });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on the 408 subject chooser').toEqual([]);
  });

  test('a framework-only subject opens a status page, not a broken one', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/subjects/math_1');
    await expect(page.getByRole('heading', { level: 1, name: '数学（一）' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('当前状态')).toBeVisible();
    await expect(page.getByText('科目框架已建立')).toBeVisible();
    // Maths has a knowledge structure, so it must not borrow the sentence written for a subject
    // that has none — and it must state its unimported exam range rather than imply one.
    await expect(page.getByText(/知识体系已建立；学习内容与练习尚未开放/)).toBeVisible();
    await expect(page.getByRole('region', { name: '学习模块' })).toBeVisible();
    await expect(page.getByRole('region', { name: '考试范围' })).toBeVisible();
    await expect(page.getByRole('link', { name: '修改考试方案' })).toBeVisible();
    // No measurement of content that does not exist, and no way in to content nobody wrote.
    await expect(page.getByText(/0 个知识点|0 道题|0%|暂无记录|暂无学习记录/)).toHaveCount(0);
    await expect(page.getByRole('link', { name: /继续学习|开始学习|进入学习/ })).toHaveCount(0);

    // The status page is the whole of a framework subject's surface. There is no workspace behind
    // this link, and the URL it would be at is not one this build serves.
    await expect(page.getByRole('link', { name: /^进入 408$/ })).toHaveCount(0);

    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on the framework subject page').toEqual([]);
  });

  test('the setup flow still builds a plan, and the home reads it back as subjects', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      await page.goto('/exam/setup');
      await expect(page.getByRole('heading', { level: 1, name: '设置考试方案' })).toBeVisible({ timeout: 20_000 });
      // The year is a property of the plan and sits at the top of the page, not in a late step.
      await expect(page.getByText('目标考试', { exact: true })).toBeVisible();
      await expect(page.getByText('第 1 步，共 3 步 · 备考方向与专业课')).toBeVisible();

      // The suggested combination is offered, is disclaimed, and is not applied until asked for.
      await expect(page.getByText(/仅供参考，具体考试科目以目标院校当年招生专业目录为准。/)).toBeVisible();
      await page.getByRole('button', { name: '使用此组合' }).click();
      await page.getByRole('button', { name: '下一步' }).click();
      await page.getByRole('button', { name: '下一步' }).click();

      const confirm = page.getByRole('region', { name: '确认考试方案' });
      await expect(confirm).toBeVisible();
      for (const name of ['思想政治理论', '英语（一）', '数学（一）', '计算机学科专业基础 408']) {
        await expect(confirm.getByText(name, { exact: true })).toBeVisible();
      }
      await expect(confirm.getByText('具体考试科目以目标院校当年招生专业目录为准。')).toBeVisible();

      await assertNoHorizontalOverflow(page, `exam setup at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/setup-${size.width}.png`, fullPage: true });
    }

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam/setup');
    await expect(page.getByRole('heading', { level: 1, name: '设置考试方案' })).toBeVisible({ timeout: 20_000 });
    const setupAxe = await new AxeBuilder({ page }).analyze();
    expect(setupAxe.violations, 'axe on /exam/setup').toEqual([]);

    // Build a whole plan from nothing: a year, the professional paper, and the three public
    // courses — then read it back from the home page it lands on. 考试方案 is where the plan is
    // read back in full; the home is where the subjects are.
    await page.getByLabel('目标考试年份').fill('2027');
    await page.getByRole('button', { name: '使用此组合' }).click();
    await page.getByRole('button', { name: '下一步' }).click();
    await page.getByRole('button', { name: '下一步' }).click();
    const review = page.getByRole('region', { name: '确认考试方案' });
    await expect(review.getByText('2027 全国硕士研究生招生考试（统考）')).toBeVisible();
    await page.getByRole('button', { name: '确认考试方案' }).click();
    await expect(page).toHaveURL(/\/exam$/, { timeout: 20_000 });

    // Every subject the learner just confirmed is on the one block, in the same system: 408 with
    // its way in, the public courses as frameworks with nothing counted.
    await expect(page.getByRole('region', { name: '考试方案' })).toHaveCount(0);
    const subjects = page.getByRole('region', { name: '我的考试科目' });
    for (const name of ['计算机学科专业基础 408', '思想政治理论', '英语（一）', '数学（一）']) {
      await expect(subjects.getByRole('heading', { name })).toBeVisible();
    }
    await expect(subjects.getByRole('link', { name: /继续学习 · .+|进入 408/ })).toBeVisible();

    for (const name of ['思想政治理论', '英语（一）', '数学（一）']) {
      const card = subjectCard(page, name);
      await expect(card.getByRole('link', { name: '查看科目' })).toHaveAttribute(
        'href',
        /^\/exam\/subjects\/.+/,
      );
      // Three things and nothing else: the line of the plan it is on, its name, and the page that
      // explains it. Not its state — that is on the subject's own page — and not a study entry, a
      // count or a progress figure, none of which this subject has.
      const cardText = await card.innerText();
      expect(cardText, `${name} claims nothing`).not.toMatch(
        /继续学习|开始学习|进入学习|个知识点|道题|%|科目框架/,
      );
      expect(cardText.split('\n').map((line) => line.trim()).filter(Boolean)).toHaveLength(3);
    }

    await page.screenshot({ path: 'test-results/exam-home/home-configured.png', fullPage: true });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on the configured exam home').toEqual([]);
  });
});

/**
 * A paper of 408, in a real browser.
 *
 * The unit suite covers the strip's own state machine; what only a browser can show is that
 * choosing a paper lands in its outline, that the control a learner actually touches — the native
 * select — moves between the four papers without dropping the tool they are using, and that the
 * outline carries the paper's own tools rather than a generic assistant.
 */
test.describe('408 paper navigation', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('进入 408 → 计算机组成原理 lands in that paper’s own knowledge outline', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam');

    // The entry names the subject and opens its front door — or, when a record named the paper,
    // opens that paper directly. Which of the two happens depends on what this learner has
    // actually done, so both are followed rather than assumed: this is a shared harness account,
    // and a test that only passes on a fresh one is a test that lies on the second run.
    await page.getByRole('region', { name: '我的考试科目' })
      .getByRole('link', { name: /继续学习 · .+|进入 408/ })
      .click();
    if (/\/exam\/cs408$/.test(page.url())) {
      await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible({ timeout: 20_000 });
      await page.getByRole('link', { name: /^计算机组成原理/ }).click();
    } else {
      // A paper resumed. Changing paper is the switcher's job, and it keeps the tool open.
      await moduleSwitcher(page).selectOption('computer_organization');
    }
    await expect(page).toHaveURL(/\/exam\/cs408\/knowledge\?module=computer_organization$/);

    // The paper is named, the switcher is on it, and 知识脉络 is the current tool — there is no
    // 概览 for this page to land on.
    await expect(page.getByText('408 · 计算机组成原理')).toBeVisible({ timeout: 20_000 });
    await expect(moduleSwitcher(page)).toHaveValue('computer_organization');
    await expect(page.getByRole('link', { name: '知识脉络' })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('link', { name: '概览' })).toHaveCount(0);
    await expect(page.getByRole('region', { name: '计算机组成原理知识目录' })).toBeVisible({ timeout: 20_000 });

    // No second title bar. The tab strip above already says 知识脉络 by marking that tab, so the
    // page draws no heading of its own: the one in the document is for screen readers and takes
    // no space on screen.
    const title = await page.getByRole('heading', { level: 1, name: '知识脉络' }).boundingBox();
    expect(title, 'the page draws no visible 知识脉络 title').not.toBeNull();
    expect(title?.width ?? 99, 'the heading is not drawn').toBeLessThanOrEqual(1);

    // And no tools of its own: 对话 and 资料库 are pages of the paper, ranked with this one in
    // the strip above. A tool that also lived in this body was a second navigation for one
    // destination, and it made the outline answer for the whole space.
    await expect(page.getByText(/问 AI/)).toHaveCount(0);
    await expect(page.getByText('暂未开放')).toHaveCount(0);
    await expect(page.getByRole('region', { name: '本科目工作区' })).toHaveCount(0);

    await assertNoHorizontalOverflow(page, 'knowledge outline at 1440px');
    await page.screenshot({ path: 'test-results/exam-home/knowledge-computer_organization.png', fullPage: true });
  });

  test('every page of a paper holds up at 1024 and 390, with the strip still scrolling', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      // The outline, which says the page arrived — its heading is deliberately not drawn.
      await page.goto('/exam/cs408/knowledge?module=computer_organization');
      await expect(page.getByRole('region', { name: '计算机组成原理知识目录' })).toBeVisible({ timeout: 20_000 });
      await expect(moduleSwitcher(page)).toBeVisible();
      await assertNoHorizontalOverflow(page, `knowledge outline at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/knowledge-${size.width}.png`, fullPage: true });

      // The two first-level pages added to the strip. Neither is behind a narrow-screen rule:
      // both are reachable at every width, which is the whole point of them being tabs.
      await page.goto('/exam/cs408/ask?module=computer_organization');
      await expect(page.getByPlaceholder('问关于计算机组成原理的问题…')).toBeVisible({ timeout: 20_000 });
      await expect(moduleSwitcher(page)).toBeVisible();
      await assertNoHorizontalOverflow(page, `ask at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/ask-${size.width}.png`, fullPage: true });

      await page.goto('/exam/cs408/materials?module=computer_organization');
      await expect(page.getByRole('region', { name: '资料库 · 计算机组成原理' })).toBeVisible({ timeout: 20_000 });
      await expect(page.getByLabel('选择要上传的文件')).toBeAttached();
      await assertNoHorizontalOverflow(page, `materials at ${size.width}px`);
      await page.screenshot({ path: `test-results/exam-home/materials-${size.width}.png`, fullPage: true });
    }

    for (const [path, anchor] of [
      ['/exam/cs408/knowledge?module=computer_organization', ['region', '计算机组成原理知识目录']],
      ['/exam/cs408/ask?module=computer_organization', ['placeholder', '问关于计算机组成原理的问题…']],
      ['/exam/cs408/materials?module=computer_organization', ['region', '资料库 · 计算机组成原理']],
    ] as const) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(path);
      const [kind, name] = anchor;
      await expect(
        kind === 'region' ? page.getByRole('region', { name }) : page.getByPlaceholder(name),
      ).toBeVisible({ timeout: 20_000 });
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `axe on ${path}`).toEqual([]);
    }
  });

  test('the paper assistant is the paper own conversation, scoped by the module above it', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/ask?module=computer_organization');
    await expect(page.getByPlaceholder('问关于计算机组成原理的问题…')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('link', { name: 'AI 对话' })).toHaveAttribute('aria-current', 'page');
    // It is a page OF the paper, not a jump to the product-wide assistant.
    await expect(page).toHaveURL(/\/exam\/cs408\/ask\?module=computer_organization$/);

    // The paper is what the scope changes: the same conversation follows the module above it.
    await moduleSwitcher(page).selectOption('operating_system');
    await expect(page).toHaveURL(/\/exam\/cs408\/ask\?module=operating_system$/);
    await expect(page.getByPlaceholder('问关于操作系统的问题…')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('link', { name: 'AI 对话' })).toHaveAttribute('aria-current', 'page');
  });

  test('the paper own library takes a real upload and lists it, per subject', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/materials?module=operating_system');
    const library = page.getByRole('region', { name: '资料库 · 操作系统' });
    await expect(library).toBeVisible({ timeout: 20_000 });
    // Wait for the LIST, not just the page: the region is on screen while its query is still in
    // flight, and counting rows then would count the loading state's zero.
    await expect(library.getByText('名称').or(library.getByText('还没有资料'))).toBeVisible({ timeout: 20_000 });

    // Whatever this subject already holds, this is the only file about to be added to it.
    const before = await library.getByRole('listitem').count();
    // The name AND the bytes are unique per run: the pipeline deduplicates by content hash
    // within a domain, so a second run of identical bytes would be refused as a duplicate —
    // which is the product working, not the test passing.
    const stamp = `${Date.now()}`;
    const name = `os-notes-${stamp}.txt`;
    await page.getByLabel('选择要上传的文件').setInputFiles({
      name,
      mimeType: 'text/plain',
      buffer: Buffer.from(`进程调度与虚拟内存：操作系统复习要点 ${stamp}。`),
    });

    await expect(library.getByText(name)).toBeVisible({ timeout: 30_000 });
    expect(await library.getByRole('listitem').count(), 'one real file was added').toBe(before + 1);
    // The row is a real material: it can be deleted through the one library delete.
    await expect(library.getByRole('button', { name: /删除/ }).first()).toBeVisible();

    // The scope is the subject: the file is not in another paper's library.
    await page.goto('/exam/cs408/materials?module=computer_network');
    await expect(page.getByRole('region', { name: '资料库 · 计算机网络' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(name)).toHaveCount(0);
  });

  test('an old ?module= link lands in the outline rather than on nothing', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408?module=operating_system');
    await expect(page).toHaveURL(/\/exam\/cs408\/knowledge\?module=operating_system$/);
    await expect(page.getByRole('heading', { level: 1, name: '知识脉络' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('408 · 操作系统')).toBeVisible();
  });

  test('the switcher keeps 知识脉络 while changing paper', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam/cs408/knowledge?module=data_structure');
    await expect(page.getByRole('heading', { level: 1, name: '知识脉络' })).toBeVisible({ timeout: 20_000 });

    await moduleSwitcher(page).selectOption('operating_system');

    await expect(page).toHaveURL(/\/exam\/cs408\/knowledge\?module=operating_system$/);
    await expect(page.getByText('408 · 操作系统')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1, name: '知识脉络' })).toBeVisible();
    await expect(page.getByRole('link', { name: '知识脉络' })).toHaveAttribute('aria-current', 'page');
    // The paper really changed: the outline on screen is the other paper's, named by the region
    // that holds it rather than by any text that happens to repeat the module name.
    await expect(page.getByRole('region', { name: '操作系统知识目录' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('region', { name: '数据结构知识目录' })).toHaveCount(0);
  });

  test('the switcher keeps 章节练习 and drops the old chapter', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
    await expect(page.getByRole('heading', { level: 1, name: '章节练习' })).toBeVisible({ timeout: 20_000 });

    await moduleSwitcher(page).selectOption('operating_system');

    // The chapter belonged to the paper that was open; it is not carried onto another one.
    await expect(page).toHaveURL(/\/exam\/cs408\/practice\?module=operating_system$/);
    await expect(page.getByRole('heading', { level: 1, name: '章节练习' })).toBeVisible();
  });

  test('the switcher keeps 真题 and drops the old paper year', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/exam/cs408/past-papers?module=data_structure&year=2022');
    await expect(page.getByRole('heading', { level: 1, name: '真题' })).toBeVisible({ timeout: 20_000 });

    await moduleSwitcher(page).selectOption('operating_system');

    // The year belonged to the paper that was open; the tool and the module are what survive.
    await expect(page).toHaveURL(/\/exam\/cs408\/past-papers\?module=operating_system$/);
    await expect(page.getByRole('link', { name: '真题', exact: true })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByText(/2022 年全国硕士研究生招生考试/)).toHaveCount(0);
  });

  test('every 408 page can still be reached, and states its own way back', async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // Opened by direct URL — the case where a history-based back button has nowhere to go. Every
    // tool inside a paper returns to the subject's front door; the front door itself returns to
    // 考研学习, because that is what is above it. Each row also names the page it lands on, so the
    // loop proves the route really renders rather than merely answering.
    for (const [path, label, href, heading] of [
      ['/exam/cs408/ask?module=data_structure', '返回 408', '/exam/cs408', 'AI 对话 · 数据结构'],
      ['/exam/cs408/materials?module=data_structure', '返回 408', '/exam/cs408', '资料库 · 数据结构'],
      ['/exam/cs408/knowledge?module=data_structure', '返回 408', '/exam/cs408', '知识脉络'],
      ['/exam/cs408/practice?module=operating_system', '返回 408', '/exam/cs408', '章节练习'],
      ['/exam/cs408/past-papers?module=data_structure', '返回 408', '/exam/cs408', '真题'],
      ['/exam/cs408/wrong?module=data_structure', '返回 408', '/exam/cs408', '错题'],
      ['/exam/cs408/records?module=data_structure', '返回 408', '/exam/cs408', '学习记录'],
      ['/exam/cs408/state?module=data_structure', '返回 408', '/exam/cs408', '学习状态'],
      ['/exam/cs408/plan', '返回 408', '/exam/cs408', '学习计划'],
      ['/exam/cs408', '返回', '/exam', '选择学习科目'],
    ] as const) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1, name: heading }), `${path} renders`).toBeVisible({
        timeout: 20_000,
      });
      const back = page.getByRole('link', { name: label, exact: true });
      await expect(back, `${path} states its way out`).toBeVisible({ timeout: 20_000 });
      await expect(back, `${path} returns to ${href}`).toHaveAttribute('href', href);
    }

    // And it really goes there: one click, one stable destination.
    await page.goto('/exam/cs408/knowledge?module=data_structure');
    await page.getByRole('link', { name: '返回 408', exact: true }).click();
    await expect(page).toHaveURL(/\/exam\/cs408$/);
    await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible({ timeout: 20_000 });
  });

  test('every 408 page lays out and passes axe at both ends of the range', async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    for (const [path, heading] of [
      ['/exam/cs408/ask?module=data_structure', 'AI 对话 · 数据结构'],
      ['/exam/cs408/materials?module=data_structure', '资料库 · 数据结构'],
      ['/exam/cs408/knowledge?module=data_structure', '知识脉络'],
      ['/exam/cs408/practice?module=operating_system', '章节练习'],
      ['/exam/cs408/past-papers?module=data_structure', '真题'],
      ['/exam/cs408/wrong?module=data_structure', '错题'],
      ['/exam/cs408/records?module=data_structure', '学习记录'],
      ['/exam/cs408/state?module=data_structure', '学习状态'],
      ['/exam/cs408/plan', '学习计划'],
      ['/exam/cs408', '选择学习科目'],
    ] as const) {
      for (const size of WIDTHS) {
        await page.setViewportSize(size);
        await page.goto(path);
        await expect(page.getByRole('heading', { level: 1, name: heading }), `${path} renders`).toBeVisible({
          timeout: 20_000,
        });
        await assertNoHorizontalOverflow(page, `${path} at ${size.width}px`);
      }

      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible({ timeout: 20_000 });
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `axe on ${path}`).toEqual([]);
    }
  });
});

/**
 * The three things this round changed, in a real browser.
 *
 * 资料库's single call to action, the knowledge point's own way into the assistant — with the
 * point actually carried — and 章节练习 reading the paper's real chapter bank. The last of those
 * only a browser can show: the numbers on the page have to come from the same data the questions
 * do, and only the live bank can prove that.
 */
test.describe('408 workspace refinements', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('资料库 offers ONE upload action, whether or not it holds files', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    // 计算机组成原理 holds no files: the empty state is the call to action, and there is no
    // second one above it.
    await page.goto('/exam/cs408/materials?module=computer_organization');
    const empty = page.getByRole('region', { name: '资料库 · 计算机组成原理' });
    await expect(empty.getByText('还没有资料')).toBeVisible({ timeout: 20_000 });
    await expect(empty.getByRole('button', { name: '上传资料' })).toHaveCount(1);

    // Another paper holds files (the library test below uploads one), so the toolbar carries the
    // action instead — still exactly one.
    await page.goto('/exam/cs408/materials?module=operating_system');
    const filled = page.getByRole('region', { name: '资料库 · 操作系统' });
    await expect(filled).toBeVisible({ timeout: 20_000 });
    await expect(filled.getByRole('button', { name: '上传资料' })).toHaveCount(1);
  });

  test('a knowledge point carries itself into the paper assistant', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/knowledge?module=data_structure');
    await expect(page.getByRole('region', { name: '数据结构知识目录' })).toBeVisible({ timeout: 20_000 });

    // The tree is structure and state only: practice is a page of the paper, not a link on every
    // chapter, section and knowledge point. Inside the outline there is now no link at all —
    // every row is a disclosure or a node selector — while the strip above still carries the one
    // 章节练习 tab, which is where questions are.
    const outline = page.getByRole('region', { name: '数据结构知识目录' });
    await expect(outline.getByRole('link')).toHaveCount(0);
    await expect(outline.getByText('知识点练习')).toHaveCount(0);
    await expect(outline.getByText('章节练习')).toHaveCount(0);
    await expect(page.getByRole('link', { name: '章节练习', exact: true })).toHaveCount(1);

    // Walk down the first branch until a leaf is reachable — the tree's depth is the module's,
    // not this test's to assume — then select it.
    for (let depth = 0; depth < 5; depth += 1) {
      if (await outline.getByRole('button', { name: /^选择 / }).count()) break;
      const next = outline.getByRole('button', { name: /^展开 / }).first();
      if (!(await next.count())) break;
      await next.click();
    }
    const leaf = outline.getByRole('button', { name: /^选择 / }).first();
    await leaf.click();
    await expect(page.getByText('当前知识点')).toBeVisible();

    const ask = page.getByRole('link', { name: '围绕此知识点问 AI' });
    await expect(ask).toBeVisible();
    const entryHref = (await ask.getAttribute('href')) ?? '';
    // The URL carries the paper, the node's own code and the title the page is showing. The code
    // is whatever this module publishes for the node — canonical numbering where the seed has it,
    // an internal path where it does not — so it is asserted as an identity, not as a shape.
    const entry = new URL(entryHref, 'http://localhost');
    expect(entry.pathname).toBe('/exam/cs408/ask');
    expect(entry.searchParams.get('module')).toBe('data_structure');
    expect(entry.searchParams.get('knowledge_point')).toBeTruthy();
    expect(entry.searchParams.get('knowledge_point_title')).toBeTruthy();

    await ask.click();

    // It lands INSIDE the paper's own workspace as a first-level page — not on the product-wide
    // assistant — and the point is stated where the learner types.
    await expect(page).toHaveURL(/\/exam\/cs408\/ask\?module=data_structure&knowledge_point=/);
    await expect(page.getByRole('link', { name: 'AI 对话' })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByText(/^当前围绕：/)).toBeVisible({ timeout: 20_000 });
    const composer = page.getByPlaceholder(/问关于数据结构的问题/);
    await expect(composer).toBeVisible();
    // Nothing was asked on the learner's behalf: the composer is empty and waiting.
    await expect(composer).toHaveValue('');

    // The paper's own point does not survive a change of paper.
    await moduleSwitcher(page).selectOption('operating_system');
    await expect(page).toHaveURL(/\/exam\/cs408\/ask\?module=operating_system$/);
    await expect(page.getByText(/^当前围绕：/)).toHaveCount(0);
    await expect(page.getByPlaceholder(/问关于操作系统的问题/)).toBeVisible();

    await page.screenshot({ path: 'test-results/exam-home/ask-knowledge-point.png', fullPage: true });
  });

  test('章节练习 is the paper real chapter bank, and nothing else', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/practice?module=data_structure');
    const chooser = page.getByRole('region', { name: '章节练习选择' });
    await expect(chooser.getByRole('heading', { name: '选择章节' })).toBeVisible({ timeout: 20_000 });

    // Wait for the PAPER's chapters, not just the page: the region is on screen while its query
    // is still in flight, and counting rows then would count the loading state's zero.
    await expect(
      chooser.getByText(/共 \d+ 道章节练习题/).or(chooser.getByText('这门科目还没有章节练习题。')),
    ).toBeVisible({ timeout: 20_000 });

    // Real chapters, each with a real question count and one way in.
    const rows = chooser.getByRole('listitem');
    const rowCount = await rows.count();
    expect(rowCount, 'the paper has chapter questions in the bank').toBeGreaterThan(0);
    const firstRow = rows.first();
    await expect(firstRow.getByRole('link')).toHaveAttribute(
      'href',
      /^\/exam\/cs408\/practice\?module=data_structure&chapter=/,
    );
    await expect(firstRow).toContainText(/\d+ 道题/);
    await expect(firstRow).toContainText('开始练习');
    // Every number on the page counts questions — no percentage, no target, no fabricated 0%.
    for (let index = 0; index < rowCount; index += 1) {
      await expect(rows.nth(index)).not.toContainText('%');
      await expect(rows.nth(index)).not.toContainText(/正确率|已做|完成度/);
    }
    await expect(chooser).toContainText(/共 \d+ 道章节练习题/);

    // Doing the questions is the page: neither auxiliary surface is on the chooser.
    await expect(page.getByText(/深度思考/)).toHaveCount(0);
    await expect(page.getByRole('region', { name: '推荐练习' })).toHaveCount(0);

    await assertNoHorizontalOverflow(page, 'chapter chooser at 1440px');
    await page.screenshot({ path: 'test-results/exam-home/practice-chooser.png', fullPage: true });

    // Opening a chapter is the existing question flow, and it stays in 章节练习.
    await firstRow.getByRole('link').click();
    await expect(page).toHaveURL(/\/exam\/cs408\/practice\?module=data_structure&chapter=\d+/);
    await expect(page.getByRole('heading', { level: 1, name: '章节练习' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('button', { name: '开始本章练习' })).toBeVisible({ timeout: 20_000 });
    // Nothing else came with it: the desk is the question, and the AI about the question appears
    // with the answer to it.
    await expect(page.getByText(/深度思考|强推理/)).toHaveCount(0);
    await expect(page.getByRole('region', { name: '推荐练习' })).toHaveCount(0);

    // Changing the paper stays in 章节练习, and loads that paper's own chapters.
    await moduleSwitcher(page).selectOption('operating_system');
    await expect(page).toHaveURL(/\/exam\/cs408\/practice\?module=operating_system$/);
    const osChooser = page.getByRole('region', { name: '章节练习选择' });
    await expect(osChooser).toBeVisible({ timeout: 20_000 });
    await expect(osChooser.getByRole('listitem').first()).toContainText(/\d+ 道题/);
    await assertNoHorizontalOverflow(page, 'chapter chooser at 1440px (operating_system)');
  });
});

/**
 * This round: the knowledge detail without internal ids, the chapter chooser without a second
 * title, and the question's own AI inside the practice flow.
 */
test.describe('408 workspace tightening', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('the knowledge point panel shows one state block and no internal id', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/knowledge?module=data_structure');
    const outline = page.getByRole('region', { name: '数据结构知识目录' });
    await expect(outline).toBeVisible({ timeout: 20_000 });

    for (let depth = 0; depth < 5; depth += 1) {
      if (await outline.getByRole('button', { name: /^选择 / }).count()) break;
      const next = outline.getByRole('button', { name: /^展开 / }).first();
      if (!(await next.count())) break;
      await next.click();
    }
    await outline.getByRole('button', { name: /^选择 / }).first().click();

    const panel = page.locator('.knowledge-detail');
    await expect(panel).toBeVisible({ timeout: 20_000 });
    // ONE state block: the label, the value and the one control that changes it.
    await expect(panel.getByText('学习状态', { exact: true })).toBeVisible();
    await expect(panel.getByRole('button', { name: '更新' })).toBeVisible();
    await expect(panel.getByText('我的学习状态')).toHaveCount(0);
    // The internal identity is nowhere on the page — not as a label, not as a value.
    await expect(panel.getByText('知识编码')).toHaveCount(0);
    const text = await panel.innerText();
    expect(text).not.toMatch(/_leaf:|knowledge_point_id|knowledge_point_code/);
    // And the one AI action is still the way into the paper's conversation.
    await expect(panel.getByRole('link', { name: '围绕此知识点问 AI' })).toBeVisible();
    await expect(page.getByText(/深度思考|强推理/)).toHaveCount(0);

    await page.screenshot({ path: 'test-results/exam-home/knowledge-panel.png', fullPage: true });
  });

  test('章节练习 opens on the chapters, with no second title and no AI panels', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/practice?module=data_structure');
    const chooser = page.getByRole('region', { name: '章节练习选择' });
    await expect(chooser.getByText(/共 \d+ 道章节练习题/)).toBeVisible({ timeout: 20_000 });

    // The tab above says 章节练习; the page does not say it again as its biggest element.
    const title = await page.getByRole('heading', { level: 1, name: '章节练习' }).boundingBox();
    expect(title, 'the page draws no visible 章节练习 title').not.toBeNull();
    expect(title?.width ?? 99, 'the heading is not drawn').toBeLessThanOrEqual(1);
    expect(await chooser.getByRole('listitem').count()).toBeGreaterThan(0);

    // Neither auxiliary surface is part of the chooser, nor of the desk behind it.
    await expect(page.getByText(/深度思考/)).toHaveCount(0);
    await expect(page.getByRole('region', { name: '推荐练习' })).toHaveCount(0);
    await expect(page.getByText(/为什么推荐这一题/)).toHaveCount(0);
  });

  test('a submitted question carries its own AI, asked about that question, in place', async ({ page }) => {
    test.setTimeout(240_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto('/exam/cs408/practice?module=data_structure');
    await page.getByRole('region', { name: '章节练习选择' }).getByRole('link').first().click();
    await expect(page).toHaveURL(/\/exam\/cs408\/practice\?module=data_structure&chapter=\d+/);
    await expect(page.getByRole('button', { name: '开始本章练习' })).toBeVisible({ timeout: 20_000 });

    // Before answering, the page offers no verdict and no AI answer.
    await expect(page.getByRole('button', { name: 'AI 讲解这道题' })).toHaveCount(0);
    await expect(page.getByText('题目解析')).toHaveCount(0);

    await page.getByRole('button', { name: '开始本章练习' }).click();
    // Answer one real question (the first option, whichever question the bank gives) and submit.
    await page.getByRole('radio').first().check();
    await page.getByRole('button', { name: '提交本章答案' }).click();
    const confirm = page.getByRole('alertdialog');
    if (await confirm.count()) await confirm.getByRole('button', { name: '仍然提交' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible({ timeout: 20_000 });
    await page.getByRole('button', { name: '查看本次题目' }).click();

    // What a submitted answer gives is the verdict and the reference answer. (This bank's chapter
    // rows carry NO analysis text — all 4,205 of them — so 题目解析 renders only where there is
    // one, and the AI explanation is what actually explains the question.)
    await expect(page.getByText('判定')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/正确答案：/)).toBeVisible();
    // The AI explanation is a thing the learner asks for, about this question.
    const explain = page.getByRole('button', { name: 'AI 讲解这道题' });
    await expect(explain).toBeVisible();

    const sent: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/question-analysis')) sent.push(request.postData() ?? '');
    });
    await explain.click();
    await expect(page.getByRole('heading', { name: 'AI 讲解' })).toBeVisible({ timeout: 20_000 });
    await expect.poll(() => sent.length, { timeout: 20_000 }).toBeGreaterThan(0);

    // What went to the model is THIS question: its stem, both answers and its own 解析.
    const payload = JSON.parse(sent[0] ?? '{}');
    expect(payload.stem, 'the question itself').toBeTruthy();
    expect(payload, 'asked about this question, not the paper').toHaveProperty('standard_answer');
    expect(payload).toHaveProperty('user_answer');
    // Nothing is asked on the learner's behalf unless they type it.
    expect(payload.follow_up ?? '').toBe('');

    await page.screenshot({ path: 'test-results/exam-home/practice-question-ai.png', fullPage: true });

    // The submitted state is a page like any other: it lays out and it passes axe.
    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      await assertNoHorizontalOverflow(page, `submitted question at ${size.width}px`);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on a submitted question').toEqual([]);
  });
});

/**
 * The two edge cases this round fixed: a deep link to an attempt that cannot be read, and the
 * search param the router was quoting back.
 */
test.describe('408 practice deep links', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('an attempt that cannot be read says so, and offers the chapter again', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    // The stale deep link, opened by URL — the case with no history to go back to.
    await page.goto('/exam/cs408/practice?module=data_structure&chapter=1&attempt=999999999');
    await expect(page.getByRole('heading', { name: '练习记录不可用' })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('这次练习记录不存在或已过期。')).toBeVisible();
    // NOT a blank body: the page states what happened and where to go.
    await expect(page.getByRole('button', { name: '开始本章练习' })).toHaveCount(0);

    const back = page.getByRole('link', { name: '返回本章练习' });
    await expect(back).toHaveAttribute('href', '/exam/cs408/practice?module=data_structure&chapter=1');
    await back.click();
    await expect(page).toHaveURL('/exam/cs408/practice?module=data_structure&chapter=1');
    await expect(page.getByRole('button', { name: '开始本章练习' })).toBeVisible({ timeout: 20_000 });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/exam/cs408/practice?module=data_structure&chapter=1&attempt=999999999');
    await expect(page.getByRole('heading', { name: '练习记录不可用' })).toBeVisible({ timeout: 20_000 });
    await assertNoHorizontalOverflow(page, 'attempt recovery at 390px');
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, 'axe on the attempt recovery state').toEqual([]);
  });

  test('the chapter the learner opened stays the chapter in the URL', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    // Opened directly: the router must not rewrite `1` into a quoted string on the way through.
    await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
    await expect(page.getByRole('button', { name: '开始本章练习' })).toBeVisible({ timeout: 20_000 });
    expect(page.url(), 'the URL the learner typed').toBe(
      'http://127.0.0.1:5173/exam/cs408/practice?module=data_structure&chapter=1',
    );
    expect(page.url()).not.toContain('%22');
    expect(page.url()).not.toContain('"');

    // A reload keeps it — the same value, the same page.
    await page.reload();
    await expect(page.getByRole('button', { name: '开始本章练习' })).toBeVisible({ timeout: 20_000 });
    expect(page.url()).toBe('http://127.0.0.1:5173/exam/cs408/practice?module=data_structure&chapter=1');

    // Arriving by clicking a chapter produces the same clean URL.
    await page.goto('/exam/cs408/practice?module=data_structure');
    await page.getByRole('region', { name: '章节练习选择' }).getByRole('link').first().click();
    await expect(page).toHaveURL(/\/exam\/cs408\/practice\?module=data_structure&chapter=\d+$/);
    expect(page.url()).not.toContain('%22');

    // And changing the paper clears it rather than carrying it, as it always did.
    await moduleSwitcher(page).selectOption('operating_system');
    await expect(page).toHaveURL('/exam/cs408/practice?module=operating_system');
  });

  test('a knowledge point keeps its own id clean in the assistant URL', async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    // The numeric-looking code is the case that used to arrive quoted.
    await page.goto('/exam/cs408/ask?module=data_structure&knowledge_point=1.1&knowledge_point_title=%E7%BA%BF%E6%80%A7%E8%A1%A8');
    await expect(page.getByText(/^当前围绕：/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('当前围绕：线性表')).toBeVisible();
    expect(page.url(), 'the knowledge point survives the round trip').toContain('knowledge_point=1.1');
    expect(page.url()).not.toContain('%22');
  });
});
