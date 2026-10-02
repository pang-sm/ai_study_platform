import { describe, expect, it } from 'vitest';
import { legacyProgrammingTarget } from './legacy-routes';

describe('legacy programming addresses', () => {
  it('sends the bare language and its exercise list to 练习中心', () => {
    expect(legacyProgrammingTarget('python')).toEqual({
      to: '/programming/practice',
      search: { language: 'python' },
    });
    expect(legacyProgrammingTarget('python/exercises')).toEqual({
      to: '/programming/practice',
      search: { language: 'python' },
    });
  });

  // The backend builds these links itself — `backend/learning/agenda.py` and
  // `backend/learning/review.py` — and it spells the language CANONICALLY, so both spellings have
  // to resolve to the same slug or a learner's own next-action link would land on nothing.
  it('accepts the canonical spelling the backend uses in its deep links', () => {
    expect(legacyProgrammingTarget('Python/exercises/8801')).toEqual({
      to: '/programming/practice/$exerciseId',
      params: { exerciseId: '8801' },
      search: { language: 'python' },
    });
    expect(legacyProgrammingTarget('C++/plan')).toEqual({
      to: '/programming/plan',
      search: { language: 'cpp' },
    });
  });

  it('maps the workbench address it used to have', () => {
    expect(legacyProgrammingTarget('java/projects/12')).toEqual({
      to: '/programming/workbench/$exerciseId',
      params: { exerciseId: '12' },
      search: { language: 'java' },
    });
  });

  // `errors` and `state` were their own tabs and are now sections of one page: the review material
  // and the recorded facts, read together.
  it('folds the retired tabs into 成长记录', () => {
    for (const tab of ['records', 'state', 'errors']) {
      expect(legacyProgrammingTarget(`c/${tab}`)).toEqual({
        to: '/programming/records',
        search: { language: 'c' },
      });
    }
  });

  it('does not invent a destination for an address it cannot place', () => {
    expect(legacyProgrammingTarget('javascript')).toBeUndefined();
    expect(legacyProgrammingTarget('')).toBeUndefined();
    expect(legacyProgrammingTarget('python/exercises/not-an-id')).toBeUndefined();
    expect(legacyProgrammingTarget('python/projects/')).toBeUndefined();
    expect(legacyProgrammingTarget('python/anything/else')).toBeUndefined();
  });
});
