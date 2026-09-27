import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RESEND_COOLDOWN_SECONDS, useResendCooldown } from './use-resend-cooldown';

describe('useResendCooldown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('counts the backend’s window down and stops at zero', () => {
    const { result } = renderHook(() => useResendCooldown());
    // Nothing sent yet: there is no window to count down.
    expect(result.current.remaining).toBe(0);

    act(() => result.current.start());
    expect(result.current.remaining).toBe(RESEND_COOLDOWN_SECONDS);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.remaining).toBe(RESEND_COOLDOWN_SECONDS - 1);

    act(() => {
      vi.advanceTimersByTime((RESEND_COOLDOWN_SECONDS - 1) * 1000);
    });
    expect(result.current.remaining).toBe(0);

    // Past zero nothing keeps ticking — and nothing starts a new window on its own.
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.remaining).toBe(0);
  });

  it('reports the real time left rather than the ticks it happened to receive', () => {
    const { result } = renderHook(() => useResendCooldown());
    act(() => result.current.start());

    // A backgrounded tab misses its intervals: 45 seconds pass with no tick at all, then one
    // fires. The answer comes from the deadline — 14 seconds left — not from the missed ticks.
    act(() => {
      vi.setSystemTime(Date.now() + 45_000);
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.remaining).toBe(14);

    act(() => result.current.start());
    expect(result.current.remaining).toBe(RESEND_COOLDOWN_SECONDS);
  });
});
