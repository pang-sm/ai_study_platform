import type { ReactNode } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { BackLink } from '@/components/page/back-link';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { LoadingState } from '@/components/page/loading-state';
import { Container } from '@/components/ui/container';
import { routePath } from '@/lib/router';
import { useProgrammingLanguage } from '../programming-context';
import { canonicalLanguage, normalizeLanguageSlug, programmingLanguages, type ProgrammingLanguageSlug } from '../programming-language';
import './programming-shell.css';

export type ProgrammingTab = 'practice' | 'ai' | 'records' | 'plan';

/**
 * The four tools of the programming space, in the order a learner moves through the work:
 * practise, ask, look back, plan.
 *
 * 练习中心 leads because it is where code is written, run and submitted — the space exists for
 * that, and the other three are what surrounds it. The strip is the SPACE's, not a language's:
 * which language is being practised is the page's context and travels in the search, exactly as
 * a 408 tool carries its paper in `?module=`. That is what stops the language from being a second
 * navigation — a learner changes language without leaving the tool they are using, and the strip
 * keeps its current tab.
 *
 * Five tabs became four. 记录 and 学习状态 were two summaries of one event stream and are both
 * sections of 成长记录 now; 错误与待处理 read no endpoint at all and held only an explanation of
 * the three help layers, which lives at the foot of 成长记录 rather than behind an empty door.
 */
const TAB_ORDER: readonly ProgrammingTab[] = ['practice', 'ai', 'records', 'plan'];

const TAB_LABEL: Readonly<Record<ProgrammingTab, string>> = {
  practice: '练习中心',
  ai: 'AI 编程助手',
  records: '成长记录',
  plan: '计划',
};

const TAB_ROUTE: Readonly<Record<ProgrammingTab, string>> = {
  practice: '/programming/practice',
  ai: '/programming/ai',
  records: '/programming/records',
  plan: '/programming/plan',
};

function tabSearch(language?: ProgrammingLanguageSlug): Record<string, unknown> {
  return language ? { language } : {};
}

/**
 * The strip's items carry the open language with them, so switching tools keeps the context —
 * and a learner who has declared no language yet gets links that name none, which those pages
 * answer by asking.
 */
export function programmingTabs(language?: ProgrammingLanguageSlug): readonly ContextNavItem[] {
  return TAB_ORDER.map((tab) => ({
    id: tab,
    label: TAB_LABEL[tab],
    to: TAB_ROUTE[tab],
    search: tabSearch(language),
  }));
}

/**
 * The language the page is being read in, changed without leaving the tool.
 *
 * Language and tool are two dimensions of one workspace: the language says WHICH, the strip says
 * WHAT is being done with it. It navigates rather than writing a preference, because "which
 * language is open" is a property of the page being read and there is no stored current-language
 * pointer in the API to write. A native `<select>` is used for the same reason the course and 408
 * switchers use one: keyboard and screen-reader support come with the element.
 */
function LanguageSwitcher({ language, tab }: { language: ProgrammingLanguageSlug; tab: ProgrammingTab }) {
  const navigate = useNavigate();
  return (
    <select
      aria-label="切换编程语言"
      value={language}
      onChange={(event) => {
        const next = normalizeLanguageSlug(event.target.value);
        if (!next || next === language) return;
        void navigate({ to: routePath(TAB_ROUTE[tab]), search: tabSearch(next) as never });
      }}
      className="programming-language-select"
    >
      {(Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(
        ([slug, label]) => (
          <option key={slug} value={slug}>
            {label}
          </option>
        ),
      )}
    </select>
  );
}

/**
 * Which language a tool is about — asked only when nothing has answered.
 *
 * No `?language=` and nothing declared means the question is genuinely open, and the four
 * languages are practised separately, so the page asks rather than picking one. Same shape as the
 * 408 paper chooser, so the two spaces ask their one question the same way.
 */
export function ProgrammingLanguageChooser({
  to,
  heading = '选择学习语言',
  description,
}: {
  /** The tool being opened, with the chosen language appended as its `language` search parameter. */
  to: string;
  heading?: string;
  description?: string;
}) {
  return (
    <section aria-labelledby="programming-choice-title">
      <h1 id="programming-choice-title" className="programming-choice__title">
        {heading}
      </h1>
      {description ? <p className="programming-choice__note">{description}</p> : null}
      <ul className="programming-choice-grid">
        {(Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(
          ([slug, label]) => (
            <li key={slug}>
              <Link to={routePath(to)} search={{ language: slug }} className="programming-choice">
                <span className="programming-choice__name">{label}</span>
                <ArrowRight className="programming-choice__go" aria-hidden="true" />
              </Link>
            </li>
          ),
        )}
      </ul>
    </section>
  );
}

/**
 * The frame every page inside the programming space shares.
 *
 * One line naming the language and the control that changes it, one strip of tools under them,
 * and the content. A learner whose URL names no language and who has declared none still gets the
 * strip — the tools are the space's, and each one knows how to ask for the language it needs.
 */
export function ProgrammingShell({
  language,
  active,
  children,
}: {
  /** The language this page is scoped to, when one is known. */
  language?: ProgrammingLanguageSlug;
  active: ProgrammingTab;
  children: ReactNode;
}) {
  const canonical = language ? canonicalLanguage(language) : undefined;
  return (
    <div className="programming-shell space-accent space-accent--programming">
      <Container>
        <div className="programming-head">
          <BackLink to="/programming" label="返回编程工作台" />
          <div className="programming-head__identity">
            <p className="programming-head__name">
              {canonical ? `编程学习 · ${canonical}` : '编程学习'}
            </p>
            {language ? <LanguageSwitcher language={language} tab={active} /> : null}
          </div>
        </div>
        <ContextNav
          ariaLabel="编程学习导航"
          items={programmingTabs(language)}
          activeId={active}
          className="mt-3"
        />
      </Container>
      <Container className="programming-page">{children}</Container>
    </div>
  );
}

/**
 * A tool that cannot be read until it knows which language it is about.
 *
 * The language comes from the address when the address names one and from the learner's own
 * setting otherwise, so the common case needs no parameter. When neither answers, the question is
 * genuinely open and the page asks rather than guessing — the `?language=` is not written for
 * them, because a URL that names a language the learner never chose would then look like a choice.
 *
 * `to` is the tool the chooser reopens, which is the tool when a language alone completes the
 * address and the list when it does not: an exercise id means nothing without its language, so
 * the detail and workbench pages send a language-less learner back to the bank.
 */
export function ProgrammingToolGate({
  slugFromUrl,
  to,
  active,
  description,
  children,
}: {
  slugFromUrl?: ProgrammingLanguageSlug;
  to: string;
  active: ProgrammingTab;
  description: string;
  children: (language: ProgrammingLanguageSlug) => ReactNode;
}) {
  const { language, pending } = useProgrammingLanguage(slugFromUrl);
  if (!language) {
    return (
      <ProgrammingShell active={active}>
        {pending ? (
          <LoadingState label="正在读取你的语言设置…" />
        ) : (
          <ProgrammingLanguageChooser to={to} description={description} />
        )}
      </ProgrammingShell>
    );
  }
  return <>{children(language)}</>;
}
