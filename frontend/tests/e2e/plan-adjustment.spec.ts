import { expect, test, type Page } from '@playwright/test';
import { requiresHarness, signIn } from './support/session';

// PRODUCT ACCEPTANCE — the Plan Adjustment surface, in a real Chromium against a real backend.
//
// What is being accepted: a proposal must be readable (a headline, a reason built from the
// learner's own records, a counted impact), its changes must be written as labelled before/after
// pairs rather than two dates joined by an arrow, and applying it must write exactly what was
// shown. Findings live in the acceptance report; the assertions here are the durable part.
//
// The suite owns its preconditions: it creates the plan tasks it needs through the PRODUCT api
// (POST /course-learning/study-plan/tasks), so nothing here depends on seeds other specs share.
test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

// SERIAL on purpose: the plan is shared state, and this suite adds tasks as it goes.
test.describe.configure({ mode: 'serial' });

const COURSE = process.env.PA_COURSE_ID ?? '数据结构';
const PLAN_PATH = `/course/${encodeURIComponent(COURSE)}/plan`;
// Far enough from the harness's "today + 3" proposal that a reschedule is always a real change,
// and stable across a run — unlike a window measured from the wall clock.
const FAR_FUTURE = '2026-12-31';

const SURFACE = 'section[aria-label="计划调整建议"]';

let seq = 0;
const unique = (prefix: string) => `${prefix}-${Date.now()}-${(seq += 1)}`;

type Proposal = {
  plan_identity: string;
  summary: string;
  rationale: string;
  adjustment_types: string[];
  evidence: { code: string; text: string; metric: number }[];
  impact: { text: string; inserted: number; rescheduled: number };
  can_apply: boolean;
  proposed_changes: {
    op: string; task_id: number | null; type: string; field: string;
    task_title: string; before: string | null; after: string | null; task_type?: string;
  }[];
};

async function addPlanTask(page: Page, title: string, dueDate = FAR_FUTURE): Promise<void> {
  const response = await page.request.post('/api/course-learning/study-plan/tasks', {
    data: {
      username: 'e2e_learner', subject_key: COURSE, title,
      scope_type: 'all', task_type: 'knowledge', due_date: dueDate,
    },
  });
  expect(response.ok(), `plan task seed failed (${response.status()}): ${await response.text()}`)
    .toBeTruthy();
}

async function planSnapshot(page: Page): Promise<Record<string, string>> {
  const response = await page.request.get('/api/course-learning/study-plan', {
    params: { course_id: COURSE },
  });
  const body = await response.json();
  const tasks: { id: number; title: string; due_date?: string | null; status?: string }[] =
    body.tasks ?? body.plan?.tasks ?? [];
  return Object.fromEntries(
    tasks.map((task) => [`${task.id}:${task.title}`, `${task.due_date ?? ''}|${task.status ?? ''}`]),
  );
}

async function generateProposal(page: Page, goal: string): Promise<Proposal> {
  await page.getByLabel('目标（可选）').fill(goal);
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/ai/plan-adjustment')
      && r.request().method() === 'POST'),
    page.getByRole('button', { name: '生成建议' }).click(),
  ]);
  expect(response.ok(), `proposal failed: ${response.status()}`).toBeTruthy();
  await expect(page.getByRole('heading', { name: '建议调整' })).toBeVisible();
  return (await response.json()) as Proposal;
}

/** `2026 年 9 月 30 日` → `2026-09-30`, so a rendered date can be compared with the api's. */
function cnDateToIso(text: string): string {
  const match = /(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日/.exec(text);
  if (!match) throw new Error(`not a plan date: ${text}`);
  const pad = (value: string | undefined) => String(Number(value)).padStart(2, '0');
  return `${Number(match[1])}-${pad(match[2])}-${pad(match[3])}`;
}

/** The inverse: the exact form a `due_date` must be rendered in. */
function isoToCnDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) throw new Error(`not an iso date: ${iso}`);
  return `${match[1]} 年 ${Number(match[2])} 月 ${Number(match[3])} 日`;
}

/**
 * The change row for one task — the unit a learner actually reads.
 *
 * Matched on the title as TEXT INSIDE the row rather than as an exact element: the row's heading
 * line is the badge and the title together ("提前" + the task), so no element's text is exactly
 * the title. Titles are unique per run, so this cannot collide.
 */
function changeRow(page: Page, title: string) {
  return page.locator(`${SURFACE} li`).filter({ hasText: title });
}

/**
 * Open the collapsed tail of a proposal.
 *
 * A proposal longer than the four the page shows at once hides the rest behind 查看调整详情 —
 * correct product behaviour, and it means a test that wants to read a particular change must ask
 * for the full diff first rather than assuming every change is on screen.
 */
async function showAllChanges(page: Page): Promise<void> {
  const more = page.getByRole('button', { name: /查看调整详情（还有 \d+ 项）/ });
  if (await more.count()) {
    await more.click();
    await expect(page.getByRole('button', { name: '收起调整详情' })).toBeVisible();
  }
}

test('a generated proposal says why, what and what it costs — with no api field on the page', async ({ page }) => {
  await signIn(page);
  await addPlanTask(page, unique('进程调度复习'));
  await page.goto(PLAN_PATH);

  const goal = unique('目标');
  const proposal = await generateProposal(page, goal);

  // WHY — a reason built from stored numbers, and the evidence that carries them
  await expect(page.getByRole('heading', { name: '为什么建议这样调整' })).toBeVisible();
  await expect(page.getByText(proposal.rationale, { exact: true })).toBeVisible();
  expect(proposal.evidence.length).toBeGreaterThan(0);
  for (const item of proposal.evidence) {
    expect(item.metric, 'evidence must quote a stored number, never zero').toBeGreaterThan(0);
    await expect(page.getByText(item.text, { exact: true })).toBeVisible();
  }

  // WHAT — headline, the changes section, and the impact it was NOT asked to forecast
  await expect(page.getByText(proposal.summary, { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '具体变更' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '调整后影响' })).toBeVisible();
  await expect(page.getByText(proposal.impact.text, { exact: true })).toBeVisible();

  // The proposal is unapplied until the learner says otherwise
  await expect(page.getByText('这份建议还没有应用到你的计划。')).toBeVisible();
  await expect(page.getByRole('button', { name: '应用调整' })).toBeEnabled();

  // No machine field, and none of the things the product must never claim
  const surface = page.locator(SURFACE);
  for (const leak of ['update_task', 'create_task', 'task_id', 'plan_identity', 'RESCHEDULE',
                      'INSERT', '掌握', '预计', '分钟', '提升', '移除', '删除', '重新排序',
                      '调整顺序', 'REMOVE', 'REORDER', '→']) {
    await expect(surface, `leaked ${leak}`).not.toContainText(leak);
  }
});

test('a reschedule reads as 原计划 / 调整后, and an insert names its own task type', async ({ page }) => {
  await signIn(page);
  await addPlanTask(page, unique('进程调度复习'));
  await page.goto(PLAN_PATH);

  const proposal = await generateProposal(page, unique('目标'));
  await showAllChanges(page);

  // The expectation comes from the proposal the SERVER produced, not from a value written here:
  // the page must render that change's own `before` under 原计划 and its `after` under 调整后.
  const reschedule = proposal.proposed_changes.find((change) => change.type === 'RESCHEDULE');
  expect(reschedule, 'the fixture reschedules the plan it is handed').toBeTruthy();
  const row = changeRow(page, reschedule!.task_title);
  await expect(row).toBeVisible();
  await expect(row).toContainText(reschedule!.after! < reschedule!.before! ? '提前' : '推迟');
  await expect(row.locator('div', { hasText: '原计划：' }))
    .toContainText(isoToCnDate(reschedule!.before!));
  await expect(row.locator('div', { hasText: '调整后：' }))
    .toContainText(isoToCnDate(reschedule!.after!));

  // INSERT: named, dated, and typed — a practice task reads 练习 and never 知识学习
  const insert = proposal.proposed_changes.find((change) => change.type === 'INSERT');
  expect(insert, 'a goal produces an insert').toBeTruthy();
  expect(insert!.task_type).toBe('practice');
  const insertRow = changeRow(page, insert!.task_title);
  await expect(insertRow).toContainText('新增');
  await expect(insertRow).toContainText('练习');
  await expect(insertRow).not.toContainText('知识学习');
  await expect(insertRow).toContainText('计划日期：');
});

test('a long proposal is shortened, and the rest opens behind 查看调整详情', async ({ page }) => {
  await signIn(page);
  // Four more open tasks guarantee more changes than the page shows at once.
  for (let index = 0; index < 4; index += 1) await addPlanTask(page, unique('附加任务'));
  await page.goto(PLAN_PATH);

  const proposal = await generateProposal(page, unique('目标'));
  expect(proposal.proposed_changes.length).toBeGreaterThan(4);

  const more = page.getByRole('button', { name: /查看调整详情（还有 \d+ 项）/ });
  await expect(more).toBeVisible();
  await expect(more).toHaveAttribute('aria-expanded', 'false');

  const shown = (await page.locator(`${SURFACE} li`).count());
  await more.click();
  await expect(page.getByRole('button', { name: '收起调整详情' }))
    .toHaveAttribute('aria-expanded', 'true');
  expect(await page.locator(`${SURFACE} li`).count()).toBeGreaterThan(shown);

  await page.getByRole('button', { name: '收起调整详情' }).click();
  expect(await page.locator(`${SURFACE} li`).count()).toBe(shown);
});

test('the thumbs on a proposal offer the plan vocabulary and record the target', async ({ page }) => {
  await signIn(page);
  await addPlanTask(page, unique('反馈任务'));
  await page.goto(PLAN_PATH);
  await generateProposal(page, unique('目标'));

  await page.getByRole('button', { name: '需要改进' }).click();
  const popover = page.getByRole('dialog', { name: '负反馈' });
  await expect(popover).toBeVisible();

  // Ten reasons make this panel taller than the room the control used to leave for it, and a
  // reason laid out above the top of the window is visible to the accessibility tree while being
  // impossible to click. The whole panel, and every reason in it, must be inside the viewport.
  const viewport = page.viewportSize()!;
  const panel = (await popover.boundingBox())!;
  expect(panel.y, 'popover starts above the viewport').toBeGreaterThanOrEqual(0);
  expect(panel.y + panel.height, 'popover runs past the bottom').toBeLessThanOrEqual(viewport.height);

  for (const label of ['调整幅度太大', '调整幅度太小', '时间安排不合理', '学习任务太多',
                       '学习任务太少', '科目或知识点优先级不合理', '没有考虑我的目标或截止时间',
                       '调整原因不充分', '建议太笼统，无法执行', '其他']) {
    await expect(popover.getByRole('checkbox', { name: label }), `missing ${label}`).toBeVisible();
  }
  for (const label of ['回答不正确', '没有回答我的问题', '解释不清楚', '太啰嗦',
                       '引用或依据有问题']) {
    await expect(popover.getByRole('checkbox', { name: label }), `leaked ${label}`).toHaveCount(0);
  }

  await popover.getByRole('checkbox', { name: '调整幅度太大' }).check();
  const [request] = await Promise.all([
    page.waitForRequest((r) => r.url().endsWith('/ai/feedback') && r.method() === 'POST'),
    popover.getByRole('button', { name: '提交' }).click(),
  ]);
  expect(request.postDataJSON()).toMatchObject({
    rating: 'down', target_type: 'plan_adjustment', reasons: ['adjustment_too_large'],
  });
  await expect(page.getByRole('status').filter({ hasText: '感谢反馈' })).toBeVisible();
});

test('applying writes exactly the previewed change, once, and cannot be repeated', async ({ page }) => {
  await signIn(page);
  await addPlanTask(page, unique('精确任务'));
  await page.goto(PLAN_PATH);

  const proposal = await generateProposal(page, unique('目标'));
  await showAllChanges(page);
  const reschedule = proposal.proposed_changes.find((change) => change.type === 'RESCHEDULE');
  const insert = proposal.proposed_changes.find((change) => change.type === 'INSERT');
  expect(reschedule).toBeTruthy();
  expect(insert).toBeTruthy();

  // what the page actually SHOWS as the new date for that row
  const previewedAfter = cnDateToIso(
    await changeRow(page, reschedule!.task_title).locator('div', { hasText: '调整后：' }).innerText());
  expect(previewedAfter).toBe(reschedule!.after);

  await page.getByRole('button', { name: '应用调整' }).click();

  await expect(page.getByText(/已应用到学习计划/)).toBeVisible();
  await expect(page.getByText('这份建议还没有应用到你的计划。')).toHaveCount(0);
  // the proposal is gone, so it has no apply affordance left to press again
  await expect(page.getByRole('button', { name: '应用调整' })).toHaveCount(0);
  await page.screenshot({ path: 'test-results/plan-adjustment/05-applied-state.png' });

  // the REAL plan now holds the previewed value, and the insert exists exactly once
  const response = await page.request.get('/api/course-learning/study-plan', {
    params: { course_id: COURSE },
  });
  const tasks: { id: number; title: string; due_date?: string | null }[] =
    (await response.json()).tasks ?? [];
  const moved = tasks.find((task) => task.id === reschedule!.task_id);
  expect(moved?.due_date, 'the plan must hold the date the preview promised').toBe(previewedAfter);
  expect(tasks.filter((task) => task.title === insert!.task_title)).toHaveLength(1);

  // the backend still refuses a replay of the same proposal (UI aside)
  const replayed = await page.request.post('/api/ai/plan-adjustment/apply', {
    data: {
      service_key: 'course_learning', course_id: COURSE,
      plan_identity: proposal.plan_identity,
      proposed_changes: proposal.proposed_changes,
    },
  });
  expect(replayed.status()).toBe(409);
});

test('保留当前计划 closes the proposal and writes nothing', async ({ page }) => {
  await signIn(page);
  const title = unique('保留任务');
  await addPlanTask(page, title);
  await page.goto(PLAN_PATH);

  await generateProposal(page, unique('目标'));
  const before = await planSnapshot(page);

  const applyCalls: string[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/ai/plan-adjustment/apply')) applyCalls.push(request.url());
  });
  await page.getByRole('button', { name: '保留当前计划' }).click();

  await expect(page.getByRole('heading', { name: '建议调整' })).toHaveCount(0);
  expect(applyCalls).toEqual([]);
  expect(await planSnapshot(page)).toEqual(before);
});

test('a partly-applied proposal is reported as partial, not as success', async ({ page }) => {
  await signIn(page);
  await addPlanTask(page, unique('部分应用任务'));
  await page.goto(PLAN_PATH);
  await generateProposal(page, unique('目标'));

  // A hostile client appends a change for a task that is not in this plan. The backend genuinely
  // drops it and answers partially — nothing about the response is simulated here.
  await page.route('**/ai/plan-adjustment/apply', async (route) => {
    const payload = route.request().postDataJSON();
    payload.proposed_changes = [
      ...payload.proposed_changes,
      { op: 'update_task', task_id: 999999, due_date: '2026-12-30' },
    ];
    await route.continue({ postData: JSON.stringify(payload) });
  });

  await page.getByRole('button', { name: '应用调整' }).click();
  await expect(page.getByText(/项已生效，另有 \d+ 项未能应用/)).toBeVisible();
});

test('desktop and narrow layouts keep the diff readable and reachable', async ({ page }) => {
  await signIn(page);
  for (let index = 0; index < 4; index += 1) await addPlanTask(page, unique('布局任务'));
  await page.goto(PLAN_PATH);
  await generateProposal(page, unique('目标'));

  const artifacts = 'test-results/plan-adjustment';
  const surface = page.locator(SURFACE);

  // Desktop
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(surface).toBeVisible();
  await expect(page.getByRole('button', { name: '应用调整' })).toBeVisible();
  await expect(page.getByRole('button', { name: '保留当前计划' })).toBeVisible();
  await page.screenshot({ path: `${artifacts}/01-proposal-desktop.png`, fullPage: true });

  // The extra changes are reachable, not clipped away
  const more = page.getByRole('button', { name: /查看调整详情（还有 \d+ 项）/ });
  if (await more.isVisible()) {
    await more.click();
    await page.screenshot({ path: `${artifacts}/02-details-expanded-desktop.png`, fullPage: true });
    await page.getByRole('button', { name: '收起调整详情' }).click();
  }

  // The feedback popover must fit inside the viewport, not hang off its edge
  await page.getByRole('button', { name: '需要改进' }).click();
  const popover = page.getByRole('dialog', { name: '负反馈' });
  await expect(popover).toBeVisible();
  const box = await popover.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(1440);
  await page.screenshot({ path: `${artifacts}/03-feedback-popover-desktop.png` });
  await page.keyboard.press('Escape');

  // Narrow — with the full diff open, so a hidden row cannot pass the check by not existing
  await showAllChanges(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(surface).toBeVisible();
  const label = page.locator('div', { hasText: '原计划：' }).first();
  await expect(label).toBeVisible();
  // the labelled pair does not collapse into one unreadable line
  const labelBox = await label.boundingBox();
  expect(labelBox!.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: `${artifacts}/04-proposal-narrow.png`, fullPage: true });

  for (const button of ['应用调整', '保留当前计划']) {
    const target = page.getByRole('button', { name: button });
    await expect(target).toBeVisible();
    const box2 = await target.boundingBox();
    expect(box2!.x, `${button} overflows the narrow viewport`).toBeGreaterThanOrEqual(0);
    expect(box2!.x + box2!.width).toBeLessThanOrEqual(390);
  }

  // no horizontal overflow of the page itself
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
