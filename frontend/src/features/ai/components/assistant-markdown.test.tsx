import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AssistantMarkdown } from './assistant-markdown';

describe('AssistantMarkdown', () => {
  it('renders GFM, math and code instead of exposing markdown source', () => {
    render(<AssistantMarkdown content={'# 标题\n\n这是 **粗体** 和 `inline`。\n\n- 第一项\n\n$O(n)$\n\n```java\nint n = 1;\n```'} />);
    expect(screen.getByRole('heading', { name: '标题' })).toBeInTheDocument();
    expect(screen.getByText('粗体').tagName).toBe('STRONG');
    expect(screen.getByText('第一项').closest('li')).toBeTruthy();
    expect(document.querySelector('.katex')).toBeTruthy();
    expect(screen.getByText('int n = 1;').closest('pre')).toBeTruthy();
  });

  it('copies only a fenced code body and exposes its language', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<AssistantMarkdown content={'```java\nint n = 1;\n```'} />);
    expect(screen.getByText('java')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '复制' }));
    expect(writeText).toHaveBeenCalledWith('int n = 1;');
  });

  it('copies with a mark rather than the word, and confirms with a tick', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<AssistantMarkdown content={'```java\nint n = 1;\n```'} />);

    const control = screen.getByRole('button', { name: '复制' });
    // The word never appears: the icon says it, and the tooltip is where it is named.
    expect(control.textContent).toBe('');
    expect(control.querySelector('svg')).toBeTruthy();
    expect(screen.queryByText('复制')).not.toBeInTheDocument();

    fireEvent.click(control);
    await waitFor(() => expect(screen.getByRole('button', { name: '已复制' })).toBeInTheDocument());
    expect(screen.queryByText('已复制')).not.toBeInTheDocument();
  });
});
