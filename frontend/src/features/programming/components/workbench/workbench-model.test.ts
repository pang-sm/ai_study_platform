import { describe, expect, it } from 'vitest';
import type { ExerciseWorkspace } from '../../api/programming';
import {
  chapterOf,
  coachTestPayload,
  entryFileOf,
  exerciseStatus,
  exerciseTitle,
  groupByChapter,
  publicSampleIds,
  resumeExerciseId,
} from './workbench-model';

describe('the bank as the rail reads it', () => {
  it('reads the product status the endpoint published, and treats an unknown one as 未完成', () => {
    expect(exerciseStatus({ personal_progress: { personal_status: 'passed' } })).toBe('passed');
    expect(exerciseStatus({ personal_progress: { personal_status: 'needs_work' } })).toBe('needs_work');
    expect(exerciseStatus({ personal_progress: { personal_status: 'needs_improvement' } })).toBe('needs_work');
    expect(exerciseStatus({ personal_progress: { personal_status: 'not_started' } })).toBe('not_started');
    // An exercise nobody has opened carries no progress row at all, and neither does an unknown
    // status — both are 未完成, never a status this build guessed at.
    expect(exerciseStatus({})).toBe('not_started');
    expect(exerciseStatus({ personal_progress: { personal_status: 'something_new' } })).toBe('not_started');
  });

  it('falls back through the exercise own names before giving up on a title', () => {
    expect(exerciseTitle({ title: '两数之和' }, '练习 1')).toBe('两数之和');
    expect(exerciseTitle({ name: '回文数' }, '练习 1')).toBe('回文数');
    // An exercise with no title is unnamed: its id is not a name.
    expect(exerciseTitle({ id: 7 }, '练习 1')).toBe('练习 1');
    expect(exerciseTitle({ title: '   ' }, '练习 1')).toBe('练习 1');
  });

  it('groups by the catalogue own chapter, then by the first knowledge point, then 其他题目', () => {
    expect(chapterOf({ curriculum_module: '控制流与函数' })).toBe('控制流与函数');
    expect(chapterOf({ knowledge_points: [{ code: '1.2', title: '循环结构' }] })).toBe('循环结构');
    expect(chapterOf({ knowledge_points: [] })).toBe('其他题目');
  });

  it('keeps the bank\'s own order inside a chapter and the chapter where its first exercise is', () => {
    const groups = groupByChapter([
      { id: 1, curriculum_module: '输入解析与类型' },
      { id: 2, curriculum_module: '控制流与函数' },
      { id: 3, curriculum_module: '输入解析与类型' },
    ]);
    expect(groups.map((group) => group.title)).toEqual(['输入解析与类型', '控制流与函数']);
    expect(groups[0]?.items.map((item) => item.id)).toEqual([1, 3]);
    expect(groups[1]?.items.map((item) => item.id)).toEqual([2]);
  });

  it('resumes the most recently touched unfinished exercise, then the most recent, then the first', () => {
    const untouched = [{ id: 1 }, { id: 2 }];
    expect(resumeExerciseId(untouched)).toBe(1);

    const bank = [
      { id: 1, personal_progress: { personal_status: 'passed', last_submit_at: '2026-09-01T10:00:00Z' } },
      { id: 2, personal_progress: { personal_status: 'needs_work', last_run_at: '2026-09-02T10:00:00Z' } },
      { id: 3, personal_progress: { personal_status: 'not_started', last_test_at: '2026-09-03T10:00:00Z' } },
    ];
    expect(resumeExerciseId(bank)).toBe(3);

    // With nothing unfinished, the most recently touched is still the best place to return to.
    const allPassed = [
      { id: 1, personal_progress: { personal_status: 'passed', last_submit_at: '2026-09-01T10:00:00Z' } },
      { id: 2, personal_progress: { personal_status: 'passed', last_submit_at: '2026-09-05T10:00:00Z' } },
    ];
    expect(resumeExerciseId(allPassed)).toBe(2);
  });
});

describe('the题面 and the project', () => {
  it('collects the visible sample ids, which `test` must be told to run', () => {
    expect(publicSampleIds({ exercise: { public_samples: [{ id: 1 }, { id: 'a' }, { name: 'no id' }] } }))
      .toEqual(['1', 'a']);
    expect(publicSampleIds({})).toEqual([]);
  });

  it('edits the project\'s entry file and knows what the starter shipped it as', () => {
    const workspace: ExerciseWorkspace = {
      project: {
        id: 55,
        entry_file: 'main.py',
        language: 'Python',
        files: [
          { id: 91, relative_path: 'helper.py', filename: 'helper.py', content: '# helper' },
          { id: 92, relative_path: 'main.py', filename: 'main.py', content: 'print(1)' },
        ],
      },
      starterFiles: [{ path: 'main.py', content: '# 在这里编写代码\n' }],
      resumed: true,
    };
    const entry = entryFileOf(workspace);
    expect(entry?.file.id).toBe(92);
    expect(entry?.starter).toBe('# 在这里编写代码\n');
  });

  it('has nothing to reset to when the exercise ships no starter for that file', () => {
    const workspace: ExerciseWorkspace = {
      project: { id: 1, entry_file: 'main.py', language: 'Python', files: [{ id: 1, relative_path: 'main.py', filename: 'main.py', content: '' }] },
      starterFiles: [],
      resumed: false,
    };
    expect(entryFileOf(workspace)?.starter).toBeUndefined();
  });
});

describe('what the coach is told about the last test', () => {
  it('translates the judge\'s counts into the shape the answer endpoint reads', () => {
    const payload = coachTestPayload({ passed_count: 1, total_count: 3, cases: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] });
    expect(payload).toEqual({ total: 3, passed: 1, results: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] });
  });

  it('has nothing to say before a test has run', () => {
    expect(coachTestPayload(undefined)).toBeUndefined();
  });
});
