import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FactList } from './fact-list';

/**
 * A timestamp reaches the reader in their own locale.
 *
 * `/review` was showing `到期时间 2026-09-21T00:00:00+00:00` — the transport's spelling of a date,
 * in front of a learner asking when something is due. The fix lives here rather than on that one
 * page because every surface renders its facts through this component.
 */
describe('FactList value rendering', () => {
  it('formats an ISO datetime instead of printing it raw', () => {
    render(<FactList value={{ due_at: '2026-09-21T00:00:00+00:00' }} />);
    expect(screen.queryByText(/2026-09-21T00:00:00\+00:00/)).not.toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it('leaves a date-only value alone, so a negative-offset reader cannot see the day before', () => {
    render(<FactList value={{ due_date: '2026-09-21' }} />);
    expect(screen.getByText('2026-09-21')).toBeInTheDocument();
  });

  it('still renders a coded value through its label and a missing one as an em dash', () => {
    render(<FactList value={{ parse_status: 'parsed', due_at: null }} />);
    expect(screen.getByText('已解析')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
