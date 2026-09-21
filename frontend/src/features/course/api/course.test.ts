import { describe, expect, it } from 'vitest';
import { courseScopedQuery, toCourseIdentity } from './course';

describe('course API normalization', () => {
  it('preserves an explicitly returned course identity without inferring fields', () => {
    expect(toCourseIdentity({ id: 'cs101', name: '数据结构' })).toEqual({ id: 'cs101', name: '数据结构' });
    expect(toCourseIdentity({ name: '数据结构' })).toEqual({ id: undefined, name: '数据结构' });
  });

  it('attaches the route course id to every supported course-scoped query', () => {
    expect(courseScopedQuery('cs101')).toEqual({ course_id: 'cs101' });
  });
});
