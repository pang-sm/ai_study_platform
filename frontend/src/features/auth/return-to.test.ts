import { describe, expect, it } from 'vitest';
import { resolvePostAuthDestination, sanitizeReturnTo } from './return-to';

describe('sanitizeReturnTo', () => {
  it('keeps a same-origin path with its query string', () => {
    expect(sanitizeReturnTo('/exam/cs408/practice?module=data_structure')).toBe(
      '/exam/cs408/practice?module=data_structure',
    );
  });

  it.each([
    ['https://evil.example/steal', 'absolute URL'],
    ['//evil.example', 'protocol-relative URL'],
    ['/\\evil.example', 'backslash variant of a protocol-relative URL'],
    ['exam/cs408', 'relative path that is not rooted'],
    ['/exam\ncs408', 'embedded newline'],
    ['javascript:alert(1)', 'script URL'],
  ])('rejects %s (%s)', (value) => {
    expect(sanitizeReturnTo(value)).toBeNull();
  });

  it('rejects values that are not strings at all', () => {
    expect(sanitizeReturnTo(undefined)).toBeNull();
    expect(sanitizeReturnTo(['/exam', '/course'])).toBeNull();
    expect(sanitizeReturnTo({ toString: () => '/exam' })).toBeNull();
  });
});

describe('resolvePostAuthDestination', () => {
  it('falls back to Home when nothing usable was supplied', () => {
    expect(resolvePostAuthDestination(undefined)).toBe('/');
    expect(resolvePostAuthDestination('//evil.example')).toBe('/');
  });

  it('never returns the visitor to another sign-in screen', () => {
    expect(resolvePostAuthDestination('/login')).toBe('/');
    expect(resolvePostAuthDestination('/register?step=2')).toBe('/');
  });

  it('returns the requested destination when it is a real in-app path', () => {
    expect(resolvePostAuthDestination('/programming/python/exercises')).toBe(
      '/programming/python/exercises',
    );
  });
});
