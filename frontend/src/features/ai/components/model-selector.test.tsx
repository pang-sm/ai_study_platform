import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const useModelOptions = vi.hoisted(() => vi.fn());

vi.mock('../api/ai-chat', () => ({ useModelOptions }));

import { ModelSelector } from './model-selector';

describe('ModelSelector', () => {
  it('shows the Router recommendation on Auto and lists only selectable models', () => {
    useModelOptions.mockReturnValue({ data: {
      recommended: { id: 'deepseek-flash', label: 'DeepSeek V4' },
      options: [
      { id: 'qwen3.8-flash', label: 'qwen3.8-flash', provider: 'qwen', thinking: false },
      { id: 'deepseek-flash', label: 'deepseek-flash', provider: 'deepseek', thinking: false },
    ] } });

    render(<ModelSelector capability="material.qa" value="auto" onChange={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: '选择回答使用的模型' }));

    expect(screen.getByRole('menuitem', { name: '自动（推荐：DeepSeek V4）' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'qwen3.8-flash' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'deepseek-flash' })).toBeInTheDocument();
    expect(screen.queryByText('qwen', { selector: 'p' })).not.toBeInTheDocument();
    expect(screen.queryByText('deepseek', { selector: 'p' })).not.toBeInTheDocument();
  });
});
