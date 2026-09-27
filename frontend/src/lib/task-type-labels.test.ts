import { describe, expect, it } from 'vitest';
import { TASK_TYPE_LABELS } from './fact-labels';

/**
 * The label registry must describe plan task kinds that EXIST.
 *
 * The backend's vocabularies live in `backend/learning/spaces/plan_task_types.py`; this is the
 * frontend's single spelling of them. The guard matters because the previous list labelled
 * `practice` and `custom` — kinds no space's plan could complete, and which only a since-closed
 * validator could produce — so every label here would have been true of nothing.
 */
describe('TASK_TYPE_LABELS', () => {
  it('covers every kind a plan can hold', () => {
    // course learning: knowledge, review · exam prep: knowledge, chapter_practice, review
    // programming: knowledge, exercise · (`project` has no agreed product wording yet)
    for (const kind of ['knowledge', 'review', 'chapter_practice', 'exercise']) {
      expect(TASK_TYPE_LABELS[kind], `no label for ${kind}`).toBeTruthy();
    }
  });

  it('does not label a kind the product cannot produce', () => {
    expect(TASK_TYPE_LABELS).not.toHaveProperty('practice');
    expect(TASK_TYPE_LABELS).not.toHaveProperty('custom');
  });

  it('spells the exam space’s practice task as 章节练习', () => {
    expect(TASK_TYPE_LABELS.chapter_practice).toBe('章节练习');
  });
});
