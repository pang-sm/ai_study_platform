import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const screenshots = path.join(process.env.TEMP ?? '.', 'zhixue-f1c2c-vqa', 'screenshots');
const questions = [
  { id: 11, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 1, question_type: 'choice', stem: '线性表的逻辑顺序由什么决定？', options: { A: '存储地址', B: '元素之间的前后关系' }, difficulty: null, quality_status: null, created_at: null, practiced: false },
  { id: 24, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 2, question_type: 'big', stem: '说明顺序表插入操作的主要步骤。', options: {}, difficulty: null, quality_status: null, created_at: null, practiced: false },
];

function results(correct: boolean) {
  return [
    { question_id: 11, correct, standard_answer: 'B', user_answer: correct ? 'B' : 'A', stem: questions[0]!.stem, options: questions[0]!.options, analysis: '线性表的逻辑顺序取决于元素之间的前后关系。', question_type: 'choice' },
    { question_id: 24, correct: null, judge: 'self_review', standard_answer: '略', user_answer: '先移动元素，再插入新元素。', stem: questions[1]!.stem, options: {}, analysis: '', question_type: 'big', hint: '' },
  ];
}

async function mockPractice(page: Page, correct = true) {
  let isSubmitted = false;
  await page.route('**/exam/11408/data_structure/question-analysis', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis: '这道题的关键在于区分逻辑顺序与物理存储位置。', generated_at: null, model: 'not-rendered', request_id: 'not-rendered' }) }));
  await page.route('**/exam/11408/data_structure/chapter-practice/**', async (route) => {
    const url = new URL(route.request().url());
    const json = url.pathname.endsWith('/outline') ? { subject_key: 'data_structure', knowledge_points: {}, total: 2, chapters: [{ chapter_code: '1', chapter_no: 1, chapter_title: '线性表', question_count: 2 }] }
      : url.pathname.endsWith('/questions') ? { items: questions, total: 2 }
        : url.pathname.endsWith('/answers') ? { success: true }
          : url.pathname.endsWith('/submit') ? (isSubmitted = true, { total_questions: 2, choice_total: 1, big_count: 1, correct_count: correct ? 1 : 0, wrong_count: correct ? 0 : 1, accuracy: correct ? 1 : 0, mistake_saved_count: 0, results: results(correct) })
            : url.pathname.endsWith('/attempts') ? { attempt_id: 91, status: 'in_progress', total_questions: 2 }
              : { attempt: { id: 91, status: isSubmitted ? 'submitted' : 'in_progress', total_questions: 2, knowledge_point_path: null, started_at: null }, questions, saved_answers: { '11': correct ? 'B' : 'A', '24': '先移动元素，再插入新元素。' }, ...(isSubmitted ? { results: results(correct) } : {}) };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(json) });
  });
}

async function submit(page: Page, correct = true) {
  await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
  await page.getByRole('radio', { name: correct ? /元素之间的前后关系/ : /存储地址/ }).check();
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await page.getByRole('button', { name: '提交本章答案' }).click();
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText(correct ? '回答正确' : '回答错误')).toBeVisible();
}

test.beforeAll(() => fs.mkdirSync(screenshots, { recursive: true }));

test('F1C2C feedback and AI VQA', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await mockPractice(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await submit(page);
  await page.screenshot({ path: path.join(screenshots, 'desktop-choice-correct-feedback.png') });
  await page.getByRole('button', { name: 'AI 讲解' }).click();
  await expect(page.getByText('这道题的关键在于区分逻辑顺序与物理存储位置。')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-choice-ai-explain.png') });
  await page.getByRole('button', { name: '第 2 题' }).click();
  await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-big-self-review.png') });
  await page.getByRole('button', { name: 'AI 讲解' }).click();
  await expect(page.getByText('这道题的关键在于区分逻辑顺序与物理存储位置。')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-big-ai-explain.png') });
  expect(errors).toEqual([]);
});

test('F1C2C incorrect feedback and submitted reload VQA', async ({ page }) => {
  await mockPractice(page, false);
  await page.setViewportSize({ width: 1440, height: 900 });
  await submit(page, false);
  await expect(page.getByText('正确答案：B')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-choice-incorrect-feedback.png') });
  await page.reload();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('回答错误')).toBeVisible();
  await expect(page.getByText('你的答案：A')).toBeVisible();
});

test('F1C2C mobile feedback and AI have no scoped Axe violations', async ({ page }) => {
  await mockPractice(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await submit(page);
  await page.screenshot({ path: path.join(screenshots, 'mobile-choice-feedback.png') });
  await page.getByRole('button', { name: 'AI 讲解' }).click();
  await expect(page.getByText('这道题的关键在于区分逻辑顺序与物理存储位置。')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-ai-explain.png') });
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
});
