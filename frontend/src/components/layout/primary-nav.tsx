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
 * The product's destinations, declared once.
 *
 * There are no groups and no permanent column any more: every destination is a peer in one bar
 * across the top of the page, which is what let the two group headings ("学习空间" / "共享学习
 * 工具") and the sentence explaining that the spaces share an account disappear. A learner reads
 * seven names and picks one; the product's internal structure is not something they have to be
 * taught before they can navigate.
 *
 * Every navigational surface reads this one declaration, so a destination cannot appear in the
 * header and go missing in the panel a phone opens.
 */
export type NavItem = {
  to: string;
  label: string;
  exact: boolean;
  icon: ComponentType<LucideProps>;
  /** Domain accent, used only to tell the three spaces apart — never as a theme switch. */
  accent?: 'exam' | 'course' | 'programming';
  /**
   * What kind of learning happens in a space, in the space's own words — the mode, and the
   * scope that actually exists today. Used by the home page's index, not by the header.
   */
  eyebrow?: string;
  detail?: string;
};

export const HOME_ITEM: NavItem = { to: '/', label: '首页', exact: true, icon: Home };

/**
 * The assistant, as its own destination rather than a button inside a page.
 *
 * It sits directly after 首页 because it is the one thing here a learner can use without first
 * deciding which space they are in: the question comes first and the space is chosen inside the
 * conversation. Under a space's own pages it would have read as that space's feature.
 */
/** The three spaces. Also the source of the home page's index of where to go next. */
export const LEARNING_SPACES: readonly NavItem[] = [
  {
    to: '/exam',
    label: '考研学习',
    exact: false,
    icon: GraduationCap,
    accent: 'exam',
    eyebrow: '目标 / 里程碑',
    detail: '11408 · 数学 · 英语 · 政治',
  },
  {
    to: '/course',
    label: '专业学习',
    exact: false,
    icon: BookOpen,
    accent: 'course',
    eyebrow: '课程 / 结构',
    detail: '按专业与课程组织资料、练习与错题',
  },
  {
    to: '/programming',
    label: '编程学习',
    exact: false,
    icon: Code2,
    accent: 'programming',
    eyebrow: '代码 / 运行 / 反馈',
    detail: 'C · C++ · Java · Python',
  },
];

/** The capabilities every space shares. */
export const SHARED_DESTINATIONS: readonly NavItem[] = [
  { to: '/review', label: '复习', exact: false, icon: ListChecks },
  { to: '/reports', label: '学习报告', exact: false, icon: SlidersHorizontal },
  { to: '/membership', label: '会员', exact: false, icon: UserRound },
];

/** The header's destinations, in the order they read. The account control follows them. */
export const TOP_NAV: readonly NavItem[] = [
  HOME_ITEM,
  ...LEARNING_SPACES,
  ...SHARED_DESTINATIONS,
];

export const accentClasses: Record<NonNullable<NavItem['accent']>, string> = {
  exam: 'bg-exam',
  course: 'bg-course',
  programming: 'bg-programming',
};

/**
 * The one navigation surface, drawn twice: a row inside the header on a wide screen, and the
 * panel the header's control opens below that width.
 *
 * Both render the same items, so the two layouts cannot drift — and the active destination is
 * styled through `activeProps`, which is what keeps the visual state and the `aria-current`
 * attribute assistive technology reads produced by a single declaration.
 */
export function PrimaryNav({
  variant,
  ariaLabel = '主导航',
  onNavigate,
}: {
  variant: 'header' | 'drawer';
  ariaLabel?: string;
  onNavigate?: () => void;
}) {
  const header = variant === 'header';

  const linkClass = cn(
    'inline-flex items-center rounded-control transition-colors duration-fast ease-standard',
    header ? 'h-10 gap-1.5 px-2.5 text-body' : 'min-h-12 gap-3 px-3 py-3 text-body',
    'text-lab-paper/70 hover:bg-white/10 hover:text-lab-paper',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent',
  );

  const activeClass = 'bg-white/12 font-medium text-lab-paper hover:bg-white/12 hover:text-lab-paper';

  return (
    <nav aria-label={ariaLabel} className={header ? undefined : 'px-4 py-3'}>
      <ul className={header ? 'flex items-center gap-0.5' : 'space-y-1'}>
        {TOP_NAV.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              activeOptions={{ exact: item.exact }}
              onClick={onNavigate}
              className={linkClass}
              activeProps={{ 'aria-current': 'page', className: cn(linkClass, activeClass) }}
            >
              {!header && item.accent ? (
                <span
                  aria-hidden="true"
                  className={cn('h-4 w-1 shrink-0 rounded-pill', accentClasses[item.accent])}
                />
              ) : null}
              {!header ? (
                <item.icon className="size-4.5 shrink-0 text-lab-paper/60" aria-hidden="true" />
              ) : null}
              <span>{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
