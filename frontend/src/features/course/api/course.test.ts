import { describe, expect, it } from 'vitest';
import { courseKeys, courseScopedQuery, toCourseIdentity } from './course';

describe('course API normalization', () => {
  it('preserves an explicitly returned course identity without inferring fields', () => {
    expect(toCourseIdentity({ id: 'cs101', name: '数据结构' })).toEqual({ id: 'cs101', name: '数据结构' });
    expect(toCourseIdentity({ name: '数据结构' })).toEqual({ id: undefined, name: '数据结构' });
  });

  it('attaches the route course id to every supported course-scoped query', () => {
    expect(courseScopedQuery('cs101')).toEqual({ course_id: 'cs101' });
  });
});

describe('practice query keys', () => {
  // React Query invalidates by PREFIX. The practice page reads its set under a key that changes
  // shape with the URL — bare "current" at the entry, the attempt id once a set is open — so the
  // key a practice mutation invalidates has to be a prefix of BOTH. It was not: answering a
  // question left the page showing the question just answered, and the next answer went to the
  // same question again. This asserts the relationship, not the strings.
  const isPrefix = (prefix: readonly unknown[], key: readonly unknown[]) =>
    prefix.length <= key.length && prefix.every((part, index) => part === key[index]);

  it('every session view a page can open is covered by the practice key', () => {
    const courseId = '数据结构';
    expect(isPrefix(courseKeys.practice(courseId), courseKeys.session(courseId))).toBe(true);
    expect(isPrefix(courseKeys.practice(courseId), courseKeys.session(courseId, 42))).toBe(true);
    expect(isPrefix(courseKeys.session(courseId), courseKeys.session(courseId, 42))).toBe(false);
  });
});
