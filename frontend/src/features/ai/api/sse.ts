/**
 * The smallest Server-Sent Events frame reader the chat stream needs.
 *
 * It is deliberately transport-only and dependency-free: it turns a sequence of text chunks
 * into `{ event, data }` frames and nothing else. It reads no JSON, knows no product field,
 * and holds no state beyond the bytes of a frame that has not yet been terminated — which is
 * why a chunk boundary landing mid-frame (mid line, mid field, even mid `\r\n`) is not a
 * special case here, only a frame that is not finished yet.
 */

export type SseFrame = { event: string; data: string };

export type SseParser = {
  /** Feed the next decoded chunk; returns every frame it completed. */
  push(chunk: string): SseFrame[];
  /** Call once the byte stream ends: a final frame may arrive without its blank-line terminator. */
  flush(): SseFrame | null;
};

export function createSseParser(): SseParser {
  let buffer = '';
  return {
    push(chunk) {
      // Normalising the WHOLE buffer (not just the new chunk) is what makes a `\r\n` split
      // across two reads arrive as one newline instead of two.
      buffer = (buffer + chunk).replace(/\r\n/g, '\n');
      const frames: SseFrame[] = [];
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = readFrame(buffer.slice(0, boundary));
        if (frame) frames.push(frame);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
      return frames;
    },
    flush() {
      const remaining = buffer;
      buffer = '';
      return readFrame(remaining);
    },
  };
}

function readFrame(raw: string): SseFrame | null {
  let event = '';
  const data: string[] = [];
  for (const line of raw.split('\n')) {
    // A blank line is the frame separator (already stripped) and a leading `:` is a comment
    // line, which is how a keep-alive ping travels without being an event.
    if (!line || line.startsWith(':')) continue;
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  }
  if (!event && data.length === 0) return null;
  return { event: event || 'message', data: data.join('\n') };
}
