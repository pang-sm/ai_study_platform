import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from './render-app';

describe('App', () => {
  it('renders the index route with the agenda first and learning spaces second', async () => {
    renderApp('/');
    // The signed-in session is what names the learner; the greeting is not a generic slogan.
    expect(await screen.findByRole('heading', { level: 1, name: /测试学习者/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '今天接下来学什么' })).toBeInTheDocument();
    // Learning spaces remain a secondary exploration section.
    expect(screen.getByRole('heading', { name: '选择你的学习方向' })).toBeInTheDocument();
  });

  it('renders the not-found route for unknown paths', async () => {
    renderApp('/does-not-exist');
    expect(await screen.findByText('页面不存在')).toBeInTheDocument();
  });

  it('renders the CS408 home for its exact route and mounts the knowledge child route', async () => {
    const home = renderApp('/exam/cs408');
    expect(await screen.findByRole('heading', { name: '学习工作区' })).toBeInTheDocument();
    home.unmount();

    renderApp('/exam/cs408/knowledge?module=data_structure');
    expect(await screen.findByRole('heading', { name: '数据结构知识脉络' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '学习工作区' })).not.toBeInTheDocument();
  });

  it('resolves the CS408 chapter practice route without inventing a chapter context', async () => {
    renderApp('/exam/cs408/practice');
    expect(await screen.findByRole('heading', { name: '选择学习模块' })).toBeInTheDocument();
    expect(screen.getByText('选择学习模块')).toBeInTheDocument();
  });
});
