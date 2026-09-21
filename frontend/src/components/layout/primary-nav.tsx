import type { ComponentType } from 'react';
import { Link } from '@tanstack/react-router';
import {
  BookOpen,
  Code2,
  GraduationCap,
  Home,
  ListChecks,
  SlidersHorizontal,
  UserRound,
  type LucideProps,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * One product with three learning spaces and the capabilities they all share.
 *
 * The spaces and the shared tools are two different kinds of destination, so they are declared
 * as two groups rather than one flat row: a space is where a learner studies, a shared tool is
 * something they reach for while studying in any space. Every navigational surface in the
 * product — desktop sidebar, the panel on small screens, the bottom bar — reads this one
 * declaration, so a destination cannot appear on one and go missing on another.
 */
export type NavItem = {
  to: string;
  label: string;
  exact: boolean;
  icon: ComponentType<LucideProps>;
  /** Short form for the bottom bar, where five destinations share the width of a phone. */
  compactLabel?: string;
  /** The accessible name when the visible label is shortened. */
  compactAriaLabel?: string;
  /** Domain accent, used only to tell the three spaces apart — never as a theme switch. */
  accent?: 'exam' | 'course' | 'programming';
  /** Whether this destination earns one of the five bottom-bar slots. */
  inBottomBar?: boolean;
  /**
   * What kind of learning happens in a space, in the space's own words — the mode, and the
   * scope that actually exists today. Declared here so the sign-in page, the home index and the
   * navigation describe the same three spaces instead of each writing its own version.
   */
  eyebrow?: string;
  detail?: string;
};

export type NavGroup = { id: string; label?: string; items: readonly NavItem[] };

const accentClasses: Record<NonNullable<NavItem['accent']>, string> = {
  exam: 'bg-exam',
  course: 'bg-course',
  programming: 'bg-programming',
};

export const HOME_ITEM: NavItem = { to: '/', label: '首页', exact: true, icon: Home, inBottomBar: true };

export const LEARNING_SPACES: readonly NavItem[] = [
  {
    to: '/exam',
    label: '考研学习',
    exact: false,
    icon: GraduationCap,
    accent: 'exam',
    compactLabel: '考研',
    compactAriaLabel: '考研学习',
    inBottomBar: true,
    eyebrow: '目标 / 里程碑',
    detail: '11408 · 数学 · 英语 · 联考',
  },
  {
    to: '/course',
    label: '课程学习',
    exact: false,
    icon: BookOpen,
    accent: 'course',
    compactLabel: '课程',
    compactAriaLabel: '课程学习',
    inBottomBar: true,
    eyebrow: '知识 / 结构',
    detail: '数学物理 · 计算机 · 更多理工专业',
  },
  {
    to: '/programming',
    label: '编程学习',
    exact: false,
    icon: Code2,
    accent: 'programming',
    compactLabel: '编程',
    compactAriaLabel: '编程学习',
    inBottomBar: true,
    eyebrow: '代码 / 运行 / 反馈',
    detail: 'C · C++ · Java · Python',
  },
];

export const SHARED_TOOLS: readonly NavItem[] = [
  { to: '/review', label: '复习', exact: false, icon: ListChecks },
  { to: '/reports', label: '学习报告', exact: false, icon: SlidersHorizontal },
  { to: '/membership', label: '会员', exact: false, icon: UserRound },
];

export const NAV_GROUPS: readonly NavGroup[] = [
  { id: 'spaces', label: '学习空间', items: LEARNING_SPACES },
  { id: 'tools', label: '共享学习工具', items: SHARED_TOOLS },
];

/**
 * The fifth bottom-bar slot: the learner's own档案, which lives in the account menu on wide
 * screens. It is declared here rather than inside the bar so the bottom bar stays a filter over
 * the same navigation model.
 */
export const PROFILE_ITEM: NavItem = {
  to: '/profile',
  label: '我的学习档案',
  exact: false,
  icon: UserRound,
  compactLabel: '我的',
  compactAriaLabel: '我的学习档案',
};

/** Home first, then the spaces, then the profile slot — the order the bar should read in. */
export const BOTTOM_BAR: readonly NavItem[] = [
  HOME_ITEM,
  ...LEARNING_SPACES.filter((item) => item.inBottomBar),
  PROFILE_ITEM,
];

export function BottomNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav
      aria-label="主导航（底部）"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border-default bg-surface md:hidden"
    >
      <ul className="grid grid-cols-5">
        {BOTTOM_BAR.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              activeOptions={{ exact: item.exact }}
              onClick={onNavigate}
              // The bar is narrow enough that the label is shortened; the accessible name stays
              // the full destination and always contains the word that is visible.
              aria-label={item.compactAriaLabel}
              className="flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2 text-metadata text-text-secondary"
              activeProps={{
                'aria-current': 'page',
                className: cn('flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2 text-metadata font-medium text-primary-ink'),
              }}
            >
              <item.icon className="size-5" aria-hidden="true" />
              <span>{item.compactLabel ?? item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * The grouped navigation. `sidebar` is the persistent column on wide screens; `drawer` is the
 * panel the small-screen control opens. Both render the same groups, so the two cannot drift —
 * and the active destination is styled through `activeProps` so the visual state and the
 * `aria-current` attribute that assistive technology reads are produced by one declaration.
 */
export function PrimaryNav({
  variant,
  ariaLabel = '主导航',
  onNavigate,
}: {
  variant: 'sidebar' | 'drawer';
  ariaLabel?: string;
  onNavigate?: () => void;
}) {
  const sidebar = variant === 'sidebar';

  const linkClass = (item: NavItem) =>
    cn(
      'group flex items-center gap-3 rounded-control transition-colors duration-fast ease-standard',
      sidebar ? 'px-3 py-2.5' : 'px-3 py-3',
      item.accent ? 'text-body text-text-primary' : 'text-body text-text-secondary',
      'hover:bg-primary-soft hover:text-text-primary',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
    );

  const activeClass = 'bg-primary-soft font-medium text-primary-ink hover:text-primary-ink';

  return (
    <nav aria-label={ariaLabel} className={cn(sidebar ? 'px-3' : 'px-4 py-3')}>
      <ul className={sidebar ? 'space-y-1' : 'space-y-1'}>
        <li>
          <Link
            to={HOME_ITEM.to}
            activeOptions={{ exact: HOME_ITEM.exact }}
            onClick={onNavigate}
            className={linkClass(HOME_ITEM)}
            activeProps={{ 'aria-current': 'page', className: cn(linkClass(HOME_ITEM), activeClass) }}
          >
            <HOME_ITEM.icon className="size-4.5 shrink-0 text-text-muted" aria-hidden="true" />
            <span>{HOME_ITEM.label}</span>
          </Link>
        </li>
      </ul>

      {NAV_GROUPS.map((group) => (
        <div key={group.id} className={sidebar ? 'mt-6' : 'mt-5'}>
          <p className="px-3 text-metadata font-medium tracking-eyebrow text-text-muted">
            {group.label}
          </p>
          <ul className="mt-2 space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <Link
                  to={item.to}
                  activeOptions={{ exact: item.exact }}
                  onClick={onNavigate}
                  className={linkClass(item)}
                  activeProps={{ 'aria-current': 'page', className: cn(linkClass(item), activeClass) }}
                >
                  {item.accent ? (
                    <span
                      aria-hidden="true"
                      className={cn('h-4 w-1 shrink-0 rounded-pill', accentClasses[item.accent])}
                    />
                  ) : (
                    <item.icon className="size-4.5 shrink-0 text-text-muted" aria-hidden="true" />
                  )}
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
