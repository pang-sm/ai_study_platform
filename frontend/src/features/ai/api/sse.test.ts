import { describe, expect, it } from 'vitest';
import { createSseParser } from './sse';

describe('createSseParser', () => {
  it('reads event and data frames out of one chunk', () => {
    const parser = createSseParser();
    const frames = parser.push('event: delta\ndata: {"text":"你好"}\n\nevent: done\ndata: {"stopped":false}\n\n');
    expect(frames).toEqual([
      { event: 'delta', data: '{"text":"你好"}' },
      { event: 'done', data: '{"stopped":false}' },
    ]);
  });

  it('reassembles a frame split across chunks, even mid-line', () => {
    const parser = createSseParser();
    expect(parser.push('event: del')).toEqual([]);
    expect(parser.push('ta\ndata: {"te')).toEqual([]);
    expect(parser.push('xt":"你好"}\n\n')).toEqual([{ event: 'delta', data: '{"text":"你好"}' }]);
  });

  it('joins multiple data lines and lets comment lines pass through', () => {
    const parser = createSseParser();
    expect(parser.push(': keep-alive\nevent: message\ndata: one\ndata: two\n\n')).toEqual([
      { event: 'message', data: 'one\ntwo' },
    ]);
  });

  it('treats a \\r\\n split across chunks as a single newline', () => {
    const parser = createSseParser();
    expect(parser.push('event: delta\r')).toEqual([]);
    expect(parser.push('\ndata: {"text":"x"}\r\n\r\n')).toEqual([{ event: 'delta', data: '{"text":"x"}' }]);
  });

  it('flushes a trailing frame that never got its blank line', () => {
    const parser = createSseParser();
    expect(parser.push('event: done\ndata: {"ok":true}')).toEqual([]);
    expect(parser.flush()).toEqual({ event: 'done', data: '{"ok":true}' });
    expect(parser.flush()).toBeNull();
  });
});
