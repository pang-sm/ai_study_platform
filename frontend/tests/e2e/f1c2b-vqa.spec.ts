import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const screenshots = path.join(process.env.TEMP ?? '.', 'zhixue-f1c2b-vqa', 'screenshots');
const questions = [
  { id: 11, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 1, question_type: 'choice', stem: '线性表的逻辑顺序由什么决定？', options: { A: '存储地址', B: '元素之间的前后关系' }, difficulty: null, quality_status: null, created_at: null, practiced: false },
  { id: 24, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 2, question_type: 'big', stem: '说明顺序表插入操作的主要步骤。', options: {}, difficulty: null, quality_status: null, created_at: null, practiced: false },
];

async function mockPractice(page: Page) {
  await page.route('**/exam/11408/data_structure/chapter-practice/**', async (route) => {
    const url = new URL(route.request().url());
    const json = url.pathname.endsWith('/outline') ? { subject_key: 'data_structure', knowledge_points: {}, total: 2, chapters: [{ chapter_code: '1', chapter_no: 1, chapter_title: '线性表', question_count: 2 }] }
      : url.pathname.endsWith('/questions') ? { items: questions, total: 2 }
        : url.pathname.endsWith('/answers') ? { success: true }
          : url.pathname.endsWith('/submit') ? { total_questions: 2, choice_total: 1, big_count: 1, correct_count: 1, wrong_count: 0, accuracy: 1, mistake_saved_count: 0, results: [{ question_id: 11, correct: true, standard_answer: 'B', user_answer: 'B', stem: questions[0]!.stem, options: questions[0]!.options, analysis: '提交后可见', question_type: 'choice' }, { question_id: 24, correct: null, judge: 'self_review', standard_answer: '略', user_answer: '', stem: questions[1]!.stem, options: {}, analysis: '提交后可见', question_type: 'big', hint: '' }] }
            : url.pathname.endsWith('/attempts') ? { attempt_id: 91, status: 'in_progress', total_questions: 2 }
              : { attempt: { id: 91, status: 'in_progress', total_questions: 2, knowledge_point_path: null, started_at: null }, questions, saved_answers: {} };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(json) });
  });
}

test.beforeAll(() => fs.mkdirSync(screenshots, { recursive: true }));

test('F1C2B chapter practice VQA', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await mockPractice(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408/practice');
  await expect(page.getByRole('heading', { name: '选择学习模块' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-module-select.png') });
  await page.getByRole('link', { name: /数据结构/ }).click();
  await expect(page.getByRole('heading', { name: '数据结构' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-chapter-select.png') });
  await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
  await expect(page.getByRole('group', { name: questions[0]!.stem })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-choice-unanswered.png') });
  await page.getByRole('radio', { name: /元素之间的前后关系/ }).check();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-choice-selected.png') });
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await page.getByRole('button', { name: '提交本章答案' }).click();
  const desktopContinue = page.getByRole('button', { name: '继续作答' });
  await expect(desktopContinue).toBeFocused();
  expect((await desktopContinue.boundingBox())?.y).toBeLessThan(900);
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-unanswered-confirm.png'), fullPage: true });
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
  await page.getByRole('button', { name: '仍然提交' }).click();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
  await expect(page.getByRole('button', { name: '下一题' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '上一题' })).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: '题目导航' })).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-session-summary.png') });
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByRole('navigation', { name: '题目导航' })).toBeVisible();
  await expect(page.getByText('回答正确')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-choice-submitted.png') });
  await page.getByRole('button', { name: '第 2 题' }).click();
  await expect(page.getByRole('textbox', { name: '你的作答' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-practice-big.png') });
  expect(errors).toEqual([]);
});

test('F1C2B mobile chapter practice VQA', async ({ page }) => {
  await mockPractice(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/exam/cs408/practice');
  await expect(page.getByRole('heading', { name: '选择学习模块' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-practice-module-select.png') });
  await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
  await page.getByRole('radio', { name: /元素之间的前后关系/ }).check();
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await page.screenshot({ path: path.join(screenshots, 'mobile-practice-choice.png') });
  await page.getByRole('button', { name: '提交本章答案' }).click();
  const mobileContinue = page.getByRole('button', { name: '继续作答' });
  await expect(mobileContinue).toBeFocused();
  expect((await mobileContinue.boundingBox())?.y).toBeLessThan(844);
  await page.screenshot({ path: path.join(screenshots, 'mobile-practice-unanswered-confirm.png'), fullPage: true });
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
  await page.getByRole('button', { name: '仍然提交' }).click();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-practice-session-summary.png') });
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('回答正确')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-practice-submitted.png') });
});

test('F1C2B practice has no scoped Axe violations', async ({ page }) => {
  await mockPractice(page);
  await page.goto('/exam/cs408/practice?module=data_structure&chapter=1');
  await expect(page.getByRole('group', { name: questions[0]!.stem })).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
});
