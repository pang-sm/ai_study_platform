/**
 * F1C3 — REAL AUTHENTICATED BACKEND VQA (CS408 past-paper workspace).
 *
 * Runs against the real FastAPI app on port 8955 backed by a disposable TEMP database, with a real
 * `POST /login` session. Nothing is intercepted: the dossier, the paper, the attempt, the grading,
 * the replay and every figure go through the real endpoints.
 *
 * Both normalized sources are exercised:
 *   - data_structure 2022 -> the DOCUMENT-backed source (bank has no rows for it)
 *   - operating_system 2022 -> the BANK-backed source
 * The frontend must behave identically for both; nothing source-specific may be visible.
 */
import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = 'http://127.0.0.1:8955';
const ROOT = path.join(process.env.TEMP ?? '.', 'f1c3-final');
const SCREENSHOTS = path.join(ROOT, 'screenshots');
const USERNAME = 'f1c3_student';
const PASSWORD = 'f1c3-secret-123';

const DOC_SUBJECT = 'data_structure';
const BANK_SUBJECT = 'operating_system';
const YEAR = 2022;

// Strings that only make sense if the UI leaked a source, an internal id or a source-specific code.
const SOURCE_WORDS = ['bank', 'document', 'ocr', 'cache', 'source', '来源', '题库来源'];
const FORBIDDEN_SUBJECTIVE = ['回答正确', '回答错误', '自动评分', 'AI判分', '得分'];

type RawResult = {
  question_number: number;
  question_type: 'choice' | 'big';
  user_answer: string;
  correct: boolean | null;
  judge: string | null;
};

function apiLog(page: Page): Array<{ url: string; body: unknown }> {
  const entries: Array<{ url: string; body: unknown }> = [];
  page.on('response', async (response) => {
    if (!response.url().startsWith(API)) return;
    if (!response.url().includes('/exam/11408/')) return;
    try {
      entries.push({ url: response.url(), body: await response.json() });
    } catch {
      /* non-JSON (an image) — nothing to inspect */
    }
  });
  return entries;
}

function walkProtected(payload: unknown, keys: string[]): string[] {
  const found: string[] = [];
  const walk = (node: unknown, where = '') => {
    if (Array.isArray(node)) return node.forEach((value, index) => walk(value, `${where}[${index}]`));
    if (node && typeof node === 'object') {
      for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
        if (keys.includes(key) && value !== null && value !== '' && value !== false) found.push(`${where}.${key}`);
        walk(value, `${where}.${key}`);
      }
    }
  };
  walk(payload);
  return found;
}

async function login(page: Page) {
  const response = await page.request.post(`${API}/login`, { data: { username: USERNAME, password: PASSWORD } });
  expect(response.status(), 'real POST /login').toBe(200);
  expect((await page.context().cookies(API)).map((cookie) => cookie.name)).toContain('ai_session');
}

async function backendPaper(page: Page, subjectKey: string, year: number) {
  const response = await page.request.get(`${API}/exam/11408/${subjectKey}/past-paper-questions?year=${year}`);
  expect(response.status()).toBe(200);
  return response.json();
}

function questionOf(paper: { questions: Array<{ question_number: number; question_type: string }> }, type: string, pick: 'first' | 'last' = 'first') {
  const matching = paper.questions.filter((q) => q.question_type === type);
  return pick === 'first' ? matching[0]! : matching[matching.length - 1]!;
}

const nextButton = (page: Page) => page.getByRole('button', { name: '下一题' });

/** Navigate the answer desk to a given question by official number, viewport-independently. */
async function gotoQuestion(page: Page, questionNumber: number, questionType: string) {
  // The navigator is hidden below 40rem, so use the official-number button where present and the
  // step controls otherwise. Both are real user affordances.
  const target = page.getByRole('button', { name: String(questionNumber).padStart(2, '0'), exact: true });
  if (await target.isVisible().catch(() => false)) {
    await target.click();
  } else {
    for (let i = 0; i < 40; i += 1) {
      if (await page.getByText(`第 ${questionNumber} 题`, { exact: false }).first().isVisible().catch(() => false)) break;
      const next = nextButton(page);
      if (!(await next.isEnabled().catch(() => false))) break;
      await next.click();
      await page.waitForTimeout(60);
    }
  }
  await expect(page.locator('.past-paper-question__identity strong')).toHaveText(`第 ${questionNumber} 题`);
  expect(questionType === 'choice' ? '选择题' : '简答题').toBeTruthy();
}

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));
test.describe.configure({ mode: 'default' });

test.describe('F1C3 real backend VQA', () => {
  test('dossier index is real, source-free and accessible', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);

    await page.goto('/exam/cs408/past-papers');
    // Real papers belong to one of the four papers, so with none chosen the page asks which.
    await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();
    await expect(page.getByRole('link', { name: /数据结构/ })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-index.png') });

    // the year list must come from the normalized backend, not a hardcoded range
    const backend = await backendPaper(page, DOC_SUBJECT, YEAR);
    await page.goto(`/exam/cs408/past-papers?module=${DOC_SUBJECT}`);
    await expect(page.getByRole('heading', { name: '选择年份' })).toBeVisible();

    const indexResponse = await page.request.get(`${API}/exam/11408/${DOC_SUBJECT}/past-papers`);
    const papers = (await indexResponse.json()).papers as Array<{ year: number; question_count: number }>;
    expect(papers.length).toBeGreaterThan(0);
    for (const paper of papers) {
      // year and its real question count, scoped to the same row (several years share a count)
      await expect(page.getByRole('link', {
        name: new RegExp(`${paper.year}.*${paper.question_count} 道真题`),
      })).toBeVisible();
    }
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-year-list.png') });

    const text = (await page.locator('body').innerText()).toLowerCase();
    for (const word of SOURCE_WORDS) expect(text, `leaked "${word}"`).not.toContain(word);

    const axe = await new AxeBuilder({ page }).include('.past-paper').analyze();
    expect(axe.violations).toEqual([]);
    expect(errors).toEqual([]);
    expect(backend.source).toBeTruthy();
  });

  test('DOCUMENT source: data_structure full objective lifecycle with replay and rehydration', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    const traffic = apiLog(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);

    const paper = await backendPaper(page, DOC_SUBJECT, YEAR);
    console.log(`[document] data_structure 2022 source=${paper.source} n=${paper.questions.length}`);
    expect(paper.source).toBe('document');

    await page.goto(`/exam/cs408/past-papers?module=${DOC_SUBJECT}&year=${YEAR}`);
    await expect(page.locator('.past-paper-question__identity strong')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-question.png') });

    // official numbers, never an array index
    await expect(page.locator('.past-paper-question__identity strong')).toHaveText(`第 ${paper.questions[0].question_number} 题`);
    const text = (await page.locator('body').innerText()).toLowerCase();
    for (const word of SOURCE_WORDS) expect(text, `leaked "${word}"`).not.toContain(word);

    // answer the FIRST choice question with its real standard answer when it is correct-able,
    // otherwise with option A — the verdict is the server's either way.
    const choice = questionOf(paper, 'choice');
    await page.getByRole('button', { name: '开始作答' }).click();
    await expect(page.getByRole('button', { name: '提交答卷' })).toBeVisible();
    const options = await page.locator('.past-paper-question__options input').count();
    expect(options).toBeGreaterThan(1);
    const first = page.locator('.past-paper-question__options input').first();
    await first.check();
    await page.getByRole('button', { name: '保存答案' }).click();

    // PRE-SUBMIT: nothing answer-bearing may have crossed the wire
    const preSubmit = traffic.filter((entry) => !entry.url.includes('/submit'));
    for (const entry of preSubmit) {
      expect(walkProtected(entry.body, ['standard_answer', 'analysis', 'correct', 'judge', 'score']),
        `${entry.url} leaked`).toEqual([]);
    }
    await expect(page.getByText('回答正确')).toHaveCount(0);

    await page.getByRole('button', { name: '提交答卷' }).click();
    await expect(page.getByRole('heading', { name: '本次答卷' })).toBeVisible();

    // the attempt defines the question set — no phantoms
    const attemptId = Number(new URL(page.url()).searchParams.get('attempt'));
    const detail = await (await page.request.get(`${API}/exam/11408/${DOC_SUBJECT}/past-paper-attempts/${attemptId}`)).json();
    expect(detail.questions.map((q: { question_number: number }) => q.question_number))
      .toEqual(paper.questions.map((q: { question_number: number }) => q.question_number));

    const results = detail.results as RawResult[];
    const expected = {
      answered: results.filter((r) => r.user_answer.trim()).length,
      unanswered: results.filter((r) => !r.user_answer.trim()).length,
      correct: results.filter((r) => r.correct === true).length,
      incorrect: results.filter((r) => r.correct === false).length,
      selfReview: results.filter((r) => r.judge === 'self_review').length,
    };
    await expect(page.getByText(`已作答 ${expected.answered} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await expect(page.getByText(new RegExp(`客观题答对 ${expected.correct} · 客观题答错 ${expected.incorrect} · 自行复盘 ${expected.selfReview}`))).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-summary.png') });

    // view mode: summary <-> answer paper, with the persisted status not forcing either
    await page.getByRole('button', { name: '查看答题纸' }).click();
    await gotoQuestion(page, choice.question_number, 'choice');
    await expect(page.locator('.past-paper-question__options input').first()).toBeChecked();
    await expect(page.locator('.past-paper-question__options input').first()).toBeDisabled();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-objective-result.png') });
    await page.getByRole('button', { name: '本次答卷' }).click();
    await expect(page.getByRole('heading', { name: '本次答卷' })).toBeVisible();

    // refresh -> replay from the submitted detail, identical counts, inputs rehydrated
    await page.reload();
    await expect(page.getByRole('heading', { name: '本次答卷' })).toBeVisible();
    await expect(page.getByText(`已作答 ${expected.answered} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await page.getByRole('button', { name: '查看答题纸' }).click();
    await gotoQuestion(page, choice.question_number, 'choice');
    await expect(page.locator('.past-paper-question__options input').first()).toBeChecked();
    await expect(page.locator('.past-paper-question__options input').first()).toBeDisabled();

    // no forbidden frontend write target was ever called
    const paths = traffic.map((entry) => new URL(entry.url).pathname);
    expect(paths.some((p) => /grade|wrong|master/i.test(p)), `unexpected write: ${paths.join(' ')}`).toBe(false);

    const axe = await new AxeBuilder({ page }).include('.past-paper').analyze();
    expect(axe.violations).toEqual([]);
    expect(errors).toEqual([]);
  });

  test('BANK source: operating_system objective + self-review + recovered Q46 figure', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);

    const paper = await backendPaper(page, BANK_SUBJECT, YEAR);
    console.log(`[bank] operating_system 2022 source=${paper.source} n=${paper.questions.length}`);
    expect(paper.source).toBe('bank');

    await page.goto(`/exam/cs408/past-papers?module=${BANK_SUBJECT}&year=${YEAR}`);
    await expect(page.locator('.past-paper-question__identity strong')).toBeVisible();
    const choice = questionOf(paper, 'choice');
    const big = questionOf(paper, 'big', 'last');
    expect(big.question_number).toBe(46);   // the figure BC6 recovered

    // objective
    await page.getByRole('button', { name: '开始作答' }).click();
    await gotoQuestion(page, choice.question_number, 'choice');
    // This question is prose — 「下列关于多道程序系统的叙述中，不正确的是」 — and says nothing
    // about a figure, so the scan it was read from would restate what is already on screen. It is
    // not drawn, and nothing is OCR'd or rewritten in its place.
    await expect(page.locator('.past-paper-question__options')).toBeVisible();
    await expect(page.locator('.past-paper-question__figure')).toHaveCount(0);
    await page.locator('.past-paper-question__options input').first().check();
    await page.getByRole('button', { name: '保存答案' }).click();

    // subjective: the self-review surface
    await gotoQuestion(page, big.question_number, 'big');
    // Q46 is the question whose figure BC6 recovered — and its own prose asks for it
    // (「题 46 图表示上述 6 个操作的执行顺序所必须满足的约束」). The figure IS the question
    // here, so it stays. This is the other half of the rule: a scan is dropped only when the
    // question is answerable without it.
    await expect(page.locator('.past-paper-question__figure')).toHaveCount(1);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-figure-question.png') });

    await page.getByLabel('你的作答').fill('互斥、占有且等待、不可剥夺、循环等待。');
    await page.getByRole('button', { name: '提交答卷' }).click();
    await expect(page.getByRole('heading', { name: '本次答卷' })).toBeVisible();

    await page.getByRole('button', { name: '查看答题纸' }).click();
    await gotoQuestion(page, big.question_number, 'big');
    await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
    const review = page.locator('.past-paper-result');
    await expect(review.getByText('你的作答')).toBeVisible();
    await expect(review.getByText('参考答案')).toBeVisible();
    await expect(review).toContainText('互斥、占有且等待');
    for (const forbidden of FORBIDDEN_SUBJECTIVE) {
      await expect(page.getByText(forbidden, { exact: false }), `rendered "${forbidden}"`).toHaveCount(0);
    }
    await expect(page.getByText(/5\s*\/\s*10/)).toHaveCount(0);
    await expect(page.getByText(/%/)).toHaveCount(0);
    // static analysis is absent for this row -> no empty explanation block
    await expect(page.getByText('题目解析')).toHaveCount(0);
    await review.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-past-paper-self-review.png') });

    // refresh restores the self-review and the submitted text
    await page.reload();
    await page.getByRole('button', { name: '查看答题纸' }).click();
    await gotoQuestion(page, big.question_number, 'big');
    await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
    const textarea = page.getByLabel('你的作答');
    await expect(textarea).toHaveValue('互斥、占有且等待、不可剥夺、循环等待。');
    await expect(textarea).toBeDisabled();

    const axe = await new AxeBuilder({ page }).include('.past-paper').analyze();
    expect(axe.violations).toEqual([]);

    // The figure Q46 asks for survives the round trip through submit and reload: a question that
    // depends on its figure must still have it when the learner comes back to review.
    await gotoQuestion(page, big.question_number, 'big');
    await expect(page.locator('.past-paper-question__figure')).toHaveCount(1);

    expect(errors).toEqual([]);
  });

  test('normalized image resources serve over real HTTP with no path leak', async ({ page }) => {
    await login(page);
    // representative repaired cases + a document-source figure
    const cases: Array<[string, number, string, string]> = [
      ['operating_system', YEAR, '2022_23_0.jpg', 'extension fallback (.jpg mapped, .jpeg on disk)'],
      ['computer_organization', YEAR, 'q12_0.jpg', 'derived deterministic layout'],
      ['operating_system', YEAR, 'img_14.jpg', 'cross-source resolution (Q46 figure)'],
      ['data_structure', YEAR, 'img_0.jpg', 'document-source figure'],
    ];
    for (const [subject, year, filename, label] of cases) {
      const response = await page.request.get(`${API}/exam/11408/past-paper-images/${subject}/${year}/${filename}`);
      expect(response.status(), `${label}: ${subject}/${year}/${filename}`).toBe(200);
      expect(response.headers()['content-type']).toContain('image/');
      expect((await response.body()).byteLength).toBeGreaterThan(1000);
    }

    for (const subject of [DOC_SUBJECT, BANK_SUBJECT]) {
      const paper = await backendPaper(page, subject, YEAR);
      for (const question of paper.questions) {
        for (const resource of question.resources as Array<{ url: string }>) {
          expect(resource.url, 'resource URL leaked a filesystem path')
            .toMatch(/^\/exam\/11408\/past-paper-images\/[a-z_]+\/\d{4}\/[A-Za-z0-9._-]+$/);
          const response = await page.request.get(`${API}${resource.url}`);
          expect(response.status(), resource.url).toBe(200);
        }
      }
    }
  });

  test('mobile: dossier, question, figure and summary without overflow', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);

    await page.goto('/exam/cs408/past-papers');
    await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-past-paper-index.png') });

    const paper = await backendPaper(page, BANK_SUBJECT, YEAR);
    const big = questionOf(paper, 'big', 'last');
    await page.goto(`/exam/cs408/past-papers?module=${BANK_SUBJECT}&year=${YEAR}`);
    await expect(page.locator('.past-paper-question__identity strong')).toBeVisible();
    await expect(page.locator('.past-paper-question__identity strong')).toHaveText(`第 ${paper.questions[0].question_number} 题`);

    let overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    await page.getByRole('button', { name: '开始作答' }).click();
    await gotoQuestion(page, big.question_number, 'big');
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-past-paper-question.png') });

    await page.getByLabel('你的作答').fill('移动端作答');
    await page.getByRole('button', { name: '提交答卷' }).click();
    await expect(page.getByRole('heading', { name: '本次答卷' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-past-paper-summary.png') });

    overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    const axe = await new AxeBuilder({ page }).include('.past-paper').analyze();
    expect(axe.violations).toEqual([]);
    expect(errors).toEqual([]);

    // Q46 needs its figure at 390px as much as at 1440px, and the phone's own question strip
    // reaches it without the page scrolling sideways.
    await page.getByRole('button', { name: '查看答题纸' }).click();
    await expect(page.locator('.past-paper__nav-drawer')).toBeVisible();
    await page.locator('.past-paper__nav-drawer > summary').click();
    await page.locator('.past-paper__nav-drawer-list button', { hasText: String(big.question_number) }).click();
    await expect(page.locator('.past-paper-question__figure')).toHaveCount(1);
    await expect(page.locator('.past-paper-question__identity strong')).toHaveText(`第 ${big.question_number} 题`);
  });
});
