import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from './render-app';

describe('App', () => {
  it('opens on today’s work, with the three directions as the way back in', async () => {
    renderApp('/');
    // The signed-in session is what names the learner; the greeting is not a generic slogan.
    expect(await screen.findByRole('heading', { level: 1, name: /测试学习者/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '今天接下来' })).toBeInTheDocument();
    // The three directions carry their own status now, so they are a section rather than a
    // signpost line — but they are still the only way out of the page.
    expect(screen.getByRole('heading', { name: '我的学习方向' })).toBeInTheDocument();
    // ...and the event log is not on it: history lives in 学习报告.
    expect(screen.queryByRole('heading', { name: '最近学习' })).not.toBeInTheDocument();
  });

  it('renders the not-found route for unknown paths', async () => {
    renderApp('/does-not-exist');
    expect(await screen.findByText('页面不存在')).toBeInTheDocument();
  });

  it('renders the CS408 home for its exact route and mounts the knowledge child route', async () => {
    const home = renderApp('/exam/cs408');
    expect(await screen.findByRole('heading', { name: '选择学习科目' })).toBeInTheDocument();
    home.unmount();

    renderApp('/exam/cs408/knowledge?module=data_structure');
    expect(await screen.findByRole('heading', { name: '知识脉络' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '选择学习科目' })).not.toBeInTheDocument();
  });

  it('resolves the CS408 chapter practice route without inventing a chapter context', async () => {
    // No module: the tool asks which paper rather than defaulting to one, because the four parts
    // are sat and scored separately.
    renderApp('/exam/cs408/practice');
    expect(await screen.findByRole('heading', { name: '选择学习科目' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^数据结构/ })).toHaveAttribute(
      'href',
      '/exam/cs408/practice?module=data_structure',
    );
  });
});
