import type { ReactNode } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { BackLink } from '@/components/page/back-link';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { Container } from '@/components/ui/container';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { routePath } from '@/lib/router';
import './exam-shell.css';

export type Cs408TabId =
  | 'ask'
  | 'materials'
  | 'knowledge'
  | 'practice'
  | 'past-papers'
  | 'wrong'
  | 'plan'
  | 'records'
  | 'state';

/**
 * The nine pages of a 408 paper, in the order the product already reads a learning space in:
 * ask about it, see what it is made of, understand the knowledge, practise a chapter, sit a real
 * paper, deal with what went wrong, then the plan, the record and the state.
 *
 * The first two are the paper's own 对话 and 资料库, and they lead because that is where they sit
 * in 专业学习 — whose strip opens with 课程问答 and 资料 for the same reason: a learner opens a
 * space with a question, and the material is what the answer is made of. Being一级 tabs, they
 * carry the paper's scope with them like every other tab: switching the module above moves the
 * conversation and the library with it rather than leaving them behind.
 *
 * There is no 概览 tab. A paper is not a place to stand and look at a summary of itself: the
 * learner has already said which paper they are working in, and the knowledge outline is the first
 * thing they can act on. Opening a paper lands on 知识脉络 — its overview page is gone, and
 * `/exam/cs408?module=…` redirects there so no old link and no bookmark lands on nothing.
 */
const TAB_ORDER: readonly Cs408TabId[] = [
  'ask',
  'materials',
  'knowledge',
  'practice',
  'past-papers',
  'wrong',
  'plan',
  'records',
  'state',
];

const TAB_LABEL: Readonly<Record<Cs408TabId, string>> = {
  ask: 'AI 对话',
  materials: '资料库',
  knowledge: '知识脉络',
  practice: '章节练习',
  'past-papers': '真题',
  wrong: '错题',
  plan: '学习计划',
  records: '学习记录',
  state: '学习状态',
};

const TAB_ROUTE: Readonly<Record<Cs408TabId, string>> = {
  ask: '/exam/cs408/ask',
  materials: '/exam/cs408/materials',
  knowledge: '/exam/cs408/knowledge',
  practice: '/exam/cs408/practice',
  'past-papers': '/exam/cs408/past-papers',
  wrong: '/exam/cs408/wrong',
  plan: '/exam/cs408/plan',
  records: '/exam/cs408/records',
  state: '/exam/cs408/state',
};

/**
 * What a module means to each tool, which is the backend's answer and not a layout choice.
 *
 * `module` — the tool is only meaningful inside one of the four papers, so its page asks which
 * one before it says anything. `all` — the tool reports across the whole subject but can also be
 * narrowed, so 全部 is a real scope beside the four papers. `none` — the tool's own contract
 * takes no module at all (`/exam/11408/subjects/{subject_key}/study-plan` is subject-wide), so it
 * offers no switcher rather than one that would silently drop the choice.
 */
const TAB_SCOPE: Readonly<Record<Cs408TabId, 'module' | 'all' | 'none'>> = {
  ask: 'module',
  materials: 'module',
  knowledge: 'module',
  practice: 'module',
  'past-papers': 'module',
  wrong: 'all',
  records: 'all',
  state: 'all',
  plan: 'none',
};

/**
 * The search a tab carries, so moving between tools keeps the subject context instead of
 * dropping back to the first module — and so a tool's own detail parameters (the chapter, the
 * attempt, the year) are cleared rather than carried into a page they do not belong to.
 */
function tabSearch(tab: Cs408TabId, moduleKey?: string): Record<string, unknown> {
  const module = moduleKey ? { module: moduleKey } : {};
  if (tab === 'practice') return { ...module, chapter: undefined, concept: undefined, attempt: undefined };
  if (tab === 'past-papers') return { ...module, year: undefined, attempt: undefined, question: undefined };
  if (tab === 'wrong') return { ...module, status: 'all', page: 0 };
  // A knowledge point belongs to ONE paper's map, so changing the paper drops it rather than
  // carrying an id that means nothing — or something else — in the module being opened. The
  // same clearing applies to leaving the tab: a conversation about a point is entered from the
  // outline, and the strip's other tabs do not have one.
  if (tab === 'ask') return { ...module, knowledge_point: undefined, knowledge_point_title: undefined };
  return module;
}

function cs408Tabs(moduleKey?: string): readonly ContextNavItem[] {
  return TAB_ORDER.map((tab) => ({
    id: tab,
    label: TAB_LABEL[tab],
    to: TAB_ROUTE[tab],
    search: tabSearch(tab, moduleKey),
  }));
}

/**
 * The part of 408 being studied, changed without leaving the tool being used.
 *
 * Module and tool are two dimensions of one workspace: the module says WHICH of the four papers,
 * the tab says WHAT is being done with it. So switching here keeps the tool — from
 * `/exam/cs408/knowledge?module=data_structure` to `/exam/cs408/knowledge?module=operating_system`
 * — which is the whole point of having it on the page: without it a learner had to go back to the
 * subject list, choose the paper, and find their way into the tool again.
 *
 * It navigates rather than writing a preference, because "which part is open" is a property of
 * the page being read and there is no stored current-module in the API to write.
 */
function ModuleSwitcher({ tab, moduleKey }: { tab: Cs408TabId; moduleKey?: string }) {
  const navigate = useNavigate();
  const withAll = TAB_SCOPE[tab] === 'all';
  return (
    <select
      aria-label="切换 408 学习科目"
      value={moduleKey ?? ''}
      onChange={(event) => {
        const next = event.target.value || undefined;
        void navigate({ to: routePath(TAB_ROUTE[tab]), search: tabSearch(tab, next) as never });
      }}
      className="cs408-module-select"
    >
      {withAll ? <option value="">全部 408</option> : null}
      {cs408Modules.map((module) => (
        <option key={module.key} value={module.key}>
          {module.name}
        </option>
      ))}
    </select>
  );
}

/**
 * The frame every exam page shares: the canvas, and — inside 408 — the one strip that says which
 * paper is open and which of its tools is being used.
 *
 * The exam space is one page (考研学习) with subjects on it, so it has no space-level tab bar and
 * no page-level title: the space is already named in the global navigation, and repeating it as
 * the biggest thing on the page spent the first screen saying what the learner's own click had
 * just said. A page inside a subject carries a back link to the page above it instead of a
 * breadcrumb trail, so the only three things above the content are: where you came from, which
 * paper you are in, and which tool you are using.
 *
 * `cs408Tab` is what puts a page inside 408. Its absence — the exam home, 考试方案, a subject's
 * own status page — gets the bare canvas and a link back to 考研学习. `atSubjectHome` is the one
 * page that has the 408 chrome but is not a tool inside a paper: the chooser, whose way out is
 * 考研学习 rather than the chooser it already is. It is stated rather than inferred from the tab,
 * because since the 概览 tab was removed the chooser and a module-less tool page are drawn the
 * same way and only differ in where their back link points.
 */
export function ExamPageShell({
  cs408Tab,
  moduleKey,
  atSubjectHome = false,
  back = true,
  children,
}: {
  /** The 408 tool this page is, when it is one. Its presence is what draws the 408 chrome. */
  cs408Tab?: Cs408TabId;
  /** The 408 paper this page is scoped to, when it has one. */
  moduleKey?: string;
  /** Whether this IS 408's own front door, whose way out is 考研学习. */
  atSubjectHome?: boolean;
  /** Whether this page has somewhere above it. False on the space's own home. */
  back?: boolean;
  children: ReactNode;
}) {
  if (!cs408Tab) {
    return (
      <div className="exam-shell space-accent space-accent--exam">
        <Container className="exam-page">
          {back ? <BackLink to="/exam" className="mb-4" /> : null}
          {children}
        </Container>
      </div>
    );
  }

  const scope = TAB_SCOPE[cs408Tab];
  // A tool that is only meaningful inside one paper has nothing to offer without one, so its strip
  // waits for a paper to be chosen; the subject-wide tools are readable as they stand.
  const workspace = scope !== 'module' || moduleKey !== undefined;
  const tabItems = workspace ? cs408Tabs(moduleKey) : [];
  const moduleName = cs408Modules.find((entry) => entry.key === moduleKey)?.name;

  return (
    <div className="exam-shell space-accent space-accent--exam">
      <Container>
        <div className="cs408-head">
          <BackLink to={atSubjectHome ? '/exam' : '/exam/cs408'} label={atSubjectHome ? '返回' : '返回 408'} />
          <div className="cs408-head__identity">
            <p className="cs408-head__name">
              {moduleName ? `408 · ${moduleName}` : '408 计算机学科专业基础'}
            </p>
            {workspace && scope !== 'none' ? <ModuleSwitcher tab={cs408Tab} moduleKey={moduleKey} /> : null}
          </div>
        </div>
        {tabItems.length ? (
          <ContextNav ariaLabel="CS408 工具导航" items={tabItems} activeId={cs408Tab} className="mt-3" />
        ) : null}
      </Container>
      <Container className="exam-page">{children}</Container>
    </div>
  );
}
