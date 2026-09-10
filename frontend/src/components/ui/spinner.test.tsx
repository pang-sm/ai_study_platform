import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Spinner } from './spinner';

describe('Spinner', () => {
  it('exposes a status role with an accessible name', () => {
    render(<Spinner label="正在加载" />);
    expect(screen.getByRole('status', { name: '正在加载' })).toBeInTheDocument();
  });
});
