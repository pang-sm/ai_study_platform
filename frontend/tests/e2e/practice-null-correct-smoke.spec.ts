import { expect, test } from '@playwright/test';

const api = 'http://127.0.0.1:8957';

test('a submitted blank choice remains unanswered after refresh without a wrong record', async ({ page }) => {
  const login = await page.request.post(`${api}/login`, { data: { username: 'practice_null_smoke', password: 'smoke-pass-123' } });
  expect(login.status()).toBe(200);
  const questionsResponse = await page.request.get(`${api}/exam/11408/data_structure/chapter-practice/questions?chapter_code=1`);
  const questions = await questionsResponse.json() as { items: Array<{ id: number; question_type: string }> };
  const choice = questions.items.find((question) => question.question_type === 'choice');
  expect(choice).toBeTruthy();
  const before = await (await page.request.get(`${api}/exam/11408/data_structure/wrong-questions`)).json();
  const created = await page.request.post(`${api}/exam/11408/data_structure/chapter-practice/attempts`, { data: { question_ids: [choice!.id] } });
  const { attempt_id: attemptId } = await created.json() as { attempt_id: number };
  const submitted = await page.request.post(`${api}/exam/11408/data_structure/chapter-practice/attempts/${attemptId}/submit`, { data: { answers: {} } });
  const body = await submitted.json() as { results: Array<{ correct: boolean | null; user_answer: string }> };
  expect(body.results[0]).toMatchObject({ correct: null, user_answer: '' });
  const after = await (await page.request.get(`${api}/exam/11408/data_structure/wrong-questions`)).json();
  expect(after).toEqual(before);

  await page.goto(`/exam/cs408/practice?module=data_structure&chapter=1&attempt=${attemptId}`);
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('未作答', { exact: true })).toBeVisible();
  await expect(page.getByText('回答错误')).toHaveCount(0);
  await page.reload();
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('未作答', { exact: true })).toBeVisible();
  await expect(page.getByText('回答错误')).toHaveCount(0);
});
