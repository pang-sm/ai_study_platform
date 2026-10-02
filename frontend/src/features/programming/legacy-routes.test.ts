import { describe, expect, it } from 'vitest';
import { legacyProgrammingTarget } from './legacy-routes';

describe('legacy programming addresses', () => {
  it('sends the bare language and its exercise list to the workspace', () => {
    expect(legacyProgrammingTarget('python')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python' },
    });
    expect(legacyProgrammingTarget('python/exercises')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python' },
    });
  });

  // The backend builds these links itself — `backend/learning/agenda.py` and
  // `backend/learning/review.py` — and it spells the language CANONICALLY, so both spellings have
  // to resolve to the same slug or a learner's own next-action link would land on nothing.
  it('accepts the canonical spelling the backend uses in its deep links', () => {
    expect(legacyProgrammingTarget('Python/exercises/8801')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python', exercise: 8801 },
    });
    expect(legacyProgrammingTarget('C++/plan')).toEqual({
      to: '/programming/plan',
      search: { language: 'cpp' },
    });
  });

  it('opens the exercise the old workbench address named, in the workspace', () => {
    expect(legacyProgrammingTarget('java/projects/12')).toEqual({
      to: '/programming/workbench',
      search: { language: 'java', exercise: 12 },
    });
  });

  // 练习中心, 成长记录 and the AI 编程助手 are regions of the workspace now, so their old addresses
  // open it rather than a page that no longer exists.
  it('folds the retired tool pages into the workspace', () => {
    for (const tool of ['practice', 'records', 'state', 'errors', 'ai']) {
      expect(legacyProgrammingTarget(`c/${tool}`)).toEqual({
        to: '/programming/workbench',
        search: { language: 'c' },
      });
    }
  });

  // The tool-first shape is the SECOND older form — `/programming/records?language=python` — where
  // the language was in the search and the tool in the path.
  it('maps the tool-first shape, keeping the language the address carried', () => {
    expect(legacyProgrammingTarget('practice', 'python')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python' },
    });
    expect(legacyProgrammingTarget('practice/7', 'python')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python', exercise: 7 },
    });
    expect(legacyProgrammingTarget('records', 'cpp')).toEqual({
      to: '/programming/workbench',
      search: { language: 'cpp' },
    });
    expect(legacyProgrammingTarget('plan', 'java')).toEqual({
      to: '/programming/plan',
      search: { language: 'java' },
    });
  });

  it('does not invent a destination for an address it cannot place', () => {
    expect(legacyProgrammingTarget('javascript')).toBeUndefined();
    expect(legacyProgrammingTarget('python/exercises/not-an-id')).toBeUndefined();
    expect(legacyProgrammingTarget('python/anything/else')).toBeUndefined();
  });

  // `projects` was the Workbench's own name before it was named for what it opens. Without an id
  // it claimed nothing in particular, and the workspace for that language is where it belongs.
  it('opens the workspace for a bare old workbench address', () => {
    expect(legacyProgrammingTarget('python/projects')).toEqual({
      to: '/programming/workbench',
      search: { language: 'python' },
    });
  });

  // The space's own front door is not a legacy address: `/programming` reaches the index route,
  // and an empty splat only ever appears when something asked for `/programming/` itself.
  it('treats an empty address as the workspace', () => {
    expect(legacyProgrammingTarget('')).toEqual({ to: '/programming/workbench', search: {} });
  });
});
