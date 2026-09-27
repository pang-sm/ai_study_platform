import { describe, expect, it } from 'vitest';
import {
  contextLabel,
  decisionBadges,
  decisionSentence,
  listRowDetail,
  localDeepLink,
  scopeLine,
  type AgendaItem,
} from './agenda-narrative';

function item(overrides: Partial<AgendaItem> = {}): AgendaItem {
  return {
    action_type: 'review',
    service_namespace: 'exam_prep',
    domain_context: {},
    source_type: 'wrong_answer',
    source_id: '1',
    title: '错题 · 数据结构',
    summary: '',
    priority_reason: 'repeated_wrong',
    deep_link: '/exam/cs408/wrong',
    due_at: null,
    facts: {},
    status: 'open',
    ...overrides,
  };
}

describe('decisionSentence', () => {
  it('states a repeated wrong answer as the count the backend recorded', () => {
    expect(decisionSentence(item({ facts: { wrong_count: 5 } })))
      .toBe('这道内容已经做错 5 次，建议优先完成订正。');
  });

  it('reads an adaptive candidate’s wrong state from the fact that carries it', () => {
    expect(decisionSentence(item({
      priority_reason: 'adaptive_recommendation',
      facts: { active_wrong_count: 3 },
    }))).toBe('这道内容已经做错 3 次，建议优先完成订正。');
  });

  it('treats a marked programming exercise as its own shape, not a wrong answer', () => {
    expect(decisionSentence(item({
      service_namespace: 'programming',
      source_type: 'programming_exercise',
      priority_reason: 'needs_work',
      facts: { personal_status: 'needs_work', passed_count: 3, total_count: 5 },
    }))).toBe('这个练习被标记为需要加强，建议重新做一遍。');
  });

  it('states a failed submission with the case counts the backend recorded', () => {
    expect(decisionSentence(item({
      service_namespace: 'programming',
      source_type: 'programming_exercise',
      priority_reason: 'needs_work',
      facts: { passed_count: 3, total_count: 5 },
    }))).toBe('最近一次提交没有通过（3/5 个用例通过），建议先修好。');
  });

  it('states a stored review date that has arrived', () => {
    expect(decisionSentence(item({ priority_reason: 'due_review' })))
      .toBe('这个知识点的复习时间已经到了，建议先复习。');
  });

  it('states an overdue plan task with its own date', () => {
    expect(decisionSentence(item({
      action_type: 'plan_task',
      source_type: 'plan_task',
      priority_reason: 'overdue_plan_task',
      facts: { overdue: true, due_date: '2026-09-20' },
    }))).toBe('这项计划任务已经过了截止日期（2026-09-20），建议先处理。');
  });

  it('falls back to the server’s own summary, and to nothing when there is none', () => {
    expect(decisionSentence(item({ priority_reason: 'brand_new_reason', summary: '后端的说明' })))
      .toBe('后端的说明');
    expect(decisionSentence(item({ priority_reason: 'brand_new_reason', summary: '' }))).toBeNull();
  });
});

describe('decisionBadges', () => {
  it('counts a repeated wrong answer and its correction state', () => {
    expect(decisionBadges(item({ facts: { wrong_count: 5 }, status: 'needs_attention' })))
      .toEqual(['错 5 次', '未订正']);
  });

  it('calls a marked programming exercise what it is', () => {
    expect(decisionBadges(item({
      source_type: 'programming_exercise',
      status: 'needs_attention',
    }))).toEqual(['需要加强']);
  });

  it('says nothing where the product has no word', () => {
    expect(decisionBadges(item({ status: 'open' }))).toEqual([]);
  });
});

describe('contextLabel / scopeLine', () => {
  it('maps an exam module key to its own name rather than printing the key', () => {
    const value = item({ domain_context: { exam_module_id: 'data_structure' } });
    expect(contextLabel(value)).toBe('数据结构');
    expect(scopeLine(value)).toBe('考研学习 · 数据结构');
  });

  it('shows a programming language as itself', () => {
    expect(contextLabel(item({ service_namespace: 'programming', domain_context: { language: 'C' } })))
      .toBe('C');
  });

  it('resolves a course id through the catalog and prints nothing when it cannot', () => {
    const value = item({ service_namespace: 'course_learning', domain_context: { course_id: 'os_11408' } });
    expect(contextLabel(value)).toBeNull();
    expect(contextLabel(value, new Map([['os_11408', '操作系统']]))).toBe('操作系统');
  });

  it('drops an unknown module key instead of showing it', () => {
    expect(contextLabel(item({ domain_context: { exam_module_id: 'not_a_module' } }))).toBeNull();
  });
});

describe('listRowDetail', () => {
  it('joins the direction detail to the server’s own summary', () => {
    expect(listRowDetail(item({
      service_namespace: 'programming',
      source_type: 'programming_exercise',
      domain_context: { language: 'C' },
      summary: '标记为需要加强',
    }))).toBe('C · 标记为需要加强');
  });

  it('returns nothing rather than an empty separator when neither part exists', () => {
    expect(listRowDetail(item({ summary: '' }))).toBeNull();
  });
});

describe('localDeepLink', () => {
  it('follows a path this product serves', () => {
    expect(localDeepLink('/exam/cs408/wrong?module=data_structure'))
      .toBe('/exam/cs408/wrong?module=data_structure');
  });

  it('refuses a destination that would leave the platform', () => {
    expect(localDeepLink('https://example.com/x')).toBeNull();
    expect(localDeepLink('//example.com/x')).toBeNull();
  });
});
