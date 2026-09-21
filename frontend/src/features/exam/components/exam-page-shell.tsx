import type { ReactNode } from 'react';
import { Breadcrumb } from '@/components/page/breadcrumb';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { Container } from '@/components/ui/container';
import { ExamContextNav, type ExamContextItem } from '@/features/exam/components/exam-context-nav';
import './exam-product-pages.css';

export type Cs408TabId =
  | 'overview'
  | 'knowledge'
  | 'practice'
  | 'past-papers'
  | 'wrong'
  | 'plan'
  | 'records'
  | 'state';

/**
 * CS408's own tools, in exam order: understand the knowledge, practise a chapter, sit a real
 * paper, deal with what went wrong, then the plan, the record and the state.
 *
 * The tabs carry the module a learner is already in, so moving between tools keeps the subject
 * context instead of silently dropping back to the first module. Only the routes that declare a
 * `module` search parameter receive one.
 */
function cs408Tabs(moduleKey?: string): readonly ContextNavItem[] {
  const module = moduleKey ? { module: moduleKey } : {};
  return [
    { id: 'overview', label: '概览', to: '/exam/cs408' },
    { id: 'knowledge', label: '知识脉络', to: '/exam/cs408/knowledge', search: module },
    {
      id: 'practice',
      label: '章节练习',
      to: '/exam/cs408/practice',
      search: { ...module, chapter: undefined, concept: undefined, attempt: undefined },
    },
    {
      id: 'past-papers',
      label: '真题',
      to: '/exam/cs408/past-papers',
      search: { ...module, year: undefined, attempt: undefined, question: undefined },
    },
    {
      id: 'wrong',
      label: '错题',
      to: '/exam/cs408/wrong',
      search: { ...module, status: 'all', page: 0 },
    },
    { id: 'plan', label: '学习计划', to: '/exam/cs408/plan' },
    { id: 'records', label: '学习记录', to: '/exam/cs408/records', search: module },
    { id: 'state', label: '学习状态', to: '/exam/cs408/state', search: module },
  ];
}

/**
 * The frame every exam page shares.
 *
 * Two navigations, two jobs: `ExamContextNav` is where the exam space sits inside the product
 * (我的备考 / 科目 / CS408), and the CS408 tab strip is where a learner moves between the tools
 * of one exam subject. Pages pass the tab they are, so the strip is identical everywhere and the
 * current one is always marked — previously it existed only on the overview page.
 */
export function ExamPageShell({
  activeItem,
  cs408Tab,
  moduleKey,
  children,
}: {
  activeItem: ExamContextItem;
  cs408Tab?: Cs408TabId;
  /** The subject module this page is scoped to, when it has one. */
  moduleKey?: string;
  children: ReactNode;
}) {
  const tabs = activeItem === 'cs408' ? cs408Tabs(moduleKey) : [];
  const tabLabel = tabs.find((tab) => tab.id === cs408Tab)?.label;

  return (
    <div className="exam-shell">
      <div className="exam-shell__masthead">
        <Container className="exam-shell__masthead-inner">
          <p>考研学习</p>
          <small>全国统考 · 学习空间</small>
        </Container>
      </div>
      <ExamContextNav activeItem={activeItem} />
      {tabs.length ? (
        <Container>
          <Breadcrumb
            className="pt-5"
            items={[
              { label: '考研学习', to: '/exam' },
              { label: 'CS408', to: cs408Tab === 'overview' ? undefined : '/exam/cs408' },
              ...(tabLabel ? [{ label: tabLabel }] : []),
            ]}
          />
          <ContextNav
            ariaLabel="CS408 工具导航"
            items={tabs}
            activeId={cs408Tab}
            className="mt-4"
          />
        </Container>
      ) : null}
      <Container className="exam-page">{children}</Container>
    </div>
  );
}
