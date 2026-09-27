import { expect, test } from '@playwright/test';
import { HARNESS, requiresHarness } from './support/session';

// Migrated off a hardcoded `127.0.0.1:8957`: that port was never part of any documented contract,
// so the spec could only ever run on the one machine that happened to have a backend on it. It
// now uses the SAME isolated harness as every other authenticated spec — the dev server points at
// that harness, so the session cookie this spec obtains is the one the page then uses.
test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

const api = HARNESS.apiBase;

test('a submitted blank choice remains unanswered after refresh without a wrong record', async ({ page }) => {
  const login = await page.request.post(`${api}/login`, { data: { username: HARNESS.username, password: HARNESS.password } });
  expect(login.status()).toBe(200);
  // Discovered, not hardcoded: which chapter carries questions is DATA, and pinning it to
  // `chapter_code=1` made this spec depend on one fixture's shape rather than on the behaviour it
  // is about. It now asks the outline which chapter actually has questions.
  const outlineResponse = await page.request.get(`${api}/exam/11408/data_structure/chapter-practice/outline`);
  expect(outlineResponse.status()).toBe(200);
  const outline = await outlineResponse.json() as { chapters: Array<{ chapter_code: string; question_count: number }> };
  const chapter = outline.chapters.find((item) => item.question_count > 0);
  // BLOCKER, stated so it cannot be mistaken for a product defect: the isolated acceptance
  // harness seeds NO exam question bank (`exam_question_bank` is a preservation-critical asset and
  // is deliberately not copied into it), so every module's outline is empty. This spec is
  // migrated to the canonical session and the canonical harness; it cannot complete until that
  // harness carries at least one objective question, which is a harness change, not a UI one.
  expect(
    chapter,
    'the acceptance harness has no exam question bank: every chapter-practice outline is empty. '
      + 'Seed one objective question into the harness to run this spec.',
  ).toBeTruthy();

  const questionsResponse = await page.request.get(`${api}/exam/11408/data_structure/chapter-practice/questions?chapter_code=${chapter!.chapter_code}`);
  const questions = await questionsResponse.json() as { items: Array<{ id: number; question_type: string }> };
  const choice = questions.items.find((question) => question.question_type === 'choice');
  expect(choice, 'the chosen chapter must hold at least one objective question').toBeTruthy();
  const before = await (await page.request.get(`${api}/exam/11408/data_structure/wrong-questions`)).json();
  const created = await page.request.post(`${api}/exam/11408/data_structure/chapter-practice/attempts`, { data: { question_ids: [choice!.id] } });
  const { attempt_id: attemptId } = await created.json() as { attempt_id: number };
  const submitted = await page.request.post(`${api}/exam/11408/data_structure/chapter-practice/attempts/${attemptId}/submit`, { data: { answers: {} } });
  const body = await submitted.json() as { results: Array<{ correct: boolean | null; user_answer: string }> };
  expect(body.results[0]).toMatchObject({ correct: null, user_answer: '' });
  const after = await (await page.request.get(`${api}/exam/11408/data_structure/wrong-questions`)).json();
  expect(after).toEqual(before);

  await page.goto(`/exam/cs408/practice?module=data_structure&chapter=${chapter!.chapter_code}&attempt=${attemptId}`);
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('未作答', { exact: true })).toBeVisible();
  await expect(page.getByText('回答错误')).toHaveCount(0);
  await page.reload();
  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByText('未作答', { exact: true })).toBeVisible();
  await expect(page.getByText('回答错误')).toHaveCount(0);
});
