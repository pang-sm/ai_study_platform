import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const evidenceDir = path.join(process.env.LOCALAPPDATA ?? process.cwd(), 'ZhixueAI', 'review-e2e', 'evidence');

test('course wrong entry starts the scoped real attempt and navigates to its practice session', async ({ page }) => {
  const calls: Array<{ method: string; path: string }> = [];
  await page.route((requestUrl) => {
    const pathname = new URL(requestUrl).pathname;
    return pathname.endsWith('/me') || pathname.endsWith('/course-dashboard') || pathname.includes('/course-learning/');
  }, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = decodeURIComponent(url.pathname);
    calls.push({ method: request.method(), path: pathname });
    if (pathname === '/me' && request.method() === 'POST') {
      return route.fulfill({ json: { user: { id: 101, username: 'redo-e2e', plan: 'free' } } });
    }
    if (pathname === '/course-learning/courses' && request.method() === 'GET') {
      return route.fulfill({ json: { courses: [{ course_id: '数据结构', course_name: '数据结构' }] } });
    }
    if (pathname === '/course-dashboard') {
      return route.fulfill({ json: { course_name: '数据结构' } });
    }
    if (pathname === '/course-learning/courses/数据结构/wrong-answers') {
      return route.fulfill({ json: { total: 1, limit: 50, offset: 0, items: [
        { wrong_record_id: 22, status: 'active', service_namespace: 'course_learning',
          course_id: '数据结构', source_kind: 'ai_generated', source_label: '课程练习',
          stem: '栈的特点是什么？', user_answer: '先进先出', reference_answer: '后进先出',
          question_id: 314, knowledge_point_id: 'kp:7', knowledge_point_name: '栈' },
      ] } });
    }
    if (pathname === '/course-learning/courses/数据结构/practice/questions/314/attempts' && request.method() === 'POST') {
      return route.fulfill({ json: { course_id: '数据结构', success: true, attempt_id: 91,
        question: { id: 314, question_type: 'single_choice', stem: '栈的特点是什么？', options: { A: '先进先出', B: '后进先出' } } } });
    }
    if (pathname === '/course-learning/courses/数据结构/practice/session') {
      return route.fulfill({ json: { course_id: '数据结构', session: {
        attempt_id: 91, course_id: '数据结构', status: 'in_progress', total: 1,
        answered: 0, correct_count: 0, questions: [{ id: 314,
          question_type: 'single_choice', stem: '栈的特点是什么？',
          options: { A: '先进先出', B: '后进先出' }, difficulty: '中等', chapter: '栈',
          knowledge_point_id: 'kp:7', knowledge_point_title: '栈', answered: false, result: null,
        }],
      } } });
    }
    return route.fulfill({ status: 404, json: { detail: 'E2E route not configured' } });
  });

  await page.goto('/course/数据结构/wrong');
  await expect(page.getByRole('heading', { name: '待复习条目' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '栈的特点是什么？' })).toBeVisible();
  await mkdir(evidenceDir, { recursive: true });
  await page.screenshot({ path: path.join(evidenceDir, 'course-redo-before.png'), fullPage: true });

  await page.getByRole('button', { name: '重做此题' }).click();
  await expect.poll(() => decodeURIComponent(page.url())).toMatch(/\/course\/数据结构\/practice\?session=91$/);
  await expect(page.getByText('栈的特点是什么？', { exact: true })).toBeVisible();
  await expect(page.getByRole('radio', { name: /后进先出/ })).toBeVisible();
  await expect(page.getByRole('button', { name: '提交答案' })).toBeDisabled();
  expect(calls).toContainEqual({
    method: 'POST', path: '/course-learning/courses/数据结构/practice/questions/314/attempts',
  });
  await page.screenshot({ path: path.join(evidenceDir, 'course-redo-after.png'), fullPage: true });
});
