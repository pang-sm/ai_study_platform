import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BankExercise } from '../../api/programming';
import {
  STATUS_LABEL,
  exerciseIdOf,
  exerciseStatus,
  exerciseTitle,
  difficultyOf,
  groupByChapter,
  type ExerciseStatus,
} from './workbench-model';

type StatusFilter = 'all' | ExerciseStatus;

const FILTERS: ReadonlyArray<{ id: StatusFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'not_started', label: '未完成' },
  { id: 'needs_work', label: '做错过' },
  { id: 'passed', label: '已完成' },
];

/**
 * 题目导航 — the language's bank as the workspace's own index.
 *
 * Grouped by the chapter the catalogue files each exercise under, because that is the axis a
 * learner actually navigates by ("先做控制流"), and marked with the product status the backend
 * recorded for them: 未完成 / 做错过 / 已完成. Selecting a题 swaps the centre column in place; the
 * rail never navigates away from the workspace.
 *
 * Filtering is local. The whole bank is already in hand, so a keystroke costs nothing, and the
 * counts shown on each filter are the real counts the bank returned — not this page's own slice.
 */
export type RecommendedExercise = { id: number; label: string; reason: string; note?: string };

export function ExerciseNav({
  items,
  total,
  statusCounts,
  currentId,
  onSelect,
  isPending,
  isError,
  recommended = [],
  collapsed = false,
  onToggleCollapsed,
}: {
  items: readonly BankExercise[];
  total: number;
  statusCounts: Record<string, number>;
  currentId: number | undefined;
  onSelect: (id: number) => void;
  isPending: boolean;
  isError: boolean;
  /**
   * Practice the backend picked for this learner, with the rule that picked it. Optional and
   * non-blocking: the rail is the bank and works without it, so a failed recommendation read
   * leaves no mark at all rather than an error in the middle of the题目 map.
   */
  recommended?: readonly RecommendedExercise[];
  /** The learner's own width choice for the rail, remembered on the device. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}) {
  const [keyword, setKeyword] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('all');

  const visible = useMemo(() => {
    const needle = keyword.trim().toLowerCase();
    return items.filter((item) => {
      if (filter !== 'all' && exerciseStatus(item) !== filter) return false;
      if (!needle) return true;
      return exerciseTitle(item, '').toLowerCase().includes(needle);
    });
  }, [items, keyword, filter]);

  const groups = useMemo(() => groupByChapter(visible), [visible]);

  // Recommendations answer "下一步做什么" — they are shown as the rail's own top group while the
  // learner is browsing the bank, and stepped aside the moment they filter or search, when they
  // have said what they are looking for.
  const showRecommended = recommended.length > 0 && !keyword.trim() && filter === 'all';

  /** How many of the bank a filter holds. `needs_improvement` is the backend's name for 做错过. */
  const countFor = (id: StatusFilter): number => {
    if (id === 'all') return total;
    if (id === 'needs_work') return statusCounts.needs_improvement ?? statusCounts.needs_work ?? 0;
    if (id === 'not_started') return statusCounts.not_started ?? 0;
    return statusCounts.passed ?? 0;
  };

  // Collapsed is a narrow rail that keeps only the way back open: the bank itself is hidden, so
  // the column holds no content that could overflow a 44px strip.
  if (collapsed) {
    return (
      <div className="wb-nav__rail">
        <button
          type="button"
          className="wb-nav__collapse"
          aria-label="展开题目栏"
          aria-expanded={false}
          title="展开题目栏"
          onClick={onToggleCollapsed}
        >
          <ChevronRight className="size-4" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="wb-nav__head">
        <p className="wb-nav__title">题目</p>
        <span className="wb-nav__count">共 {total} 道</span>
        <button
          type="button"
          className="wb-nav__collapse"
          aria-label="收起题目栏"
          aria-expanded
          title="收起题目栏"
          onClick={onToggleCollapsed}
        >
          <ChevronLeft className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="wb-nav__search">
        <label htmlFor="wb-nav-search" className="sr-only">
          搜索题目
        </label>
        <input
          id="wb-nav-search"
          type="search"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜索题目"
          className="h-9 w-full rounded-control border border-border-default bg-surface px-2.5 text-metadata text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
        />
      </div>

      <div className="wb-nav__filters" role="group" aria-label="按状态筛选题目">
        {FILTERS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            aria-pressed={filter === entry.id}
            onClick={() => setFilter(entry.id)}
            className={cn(
              'inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-[0.72rem] font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
              filter === entry.id
                ? 'border-primary bg-primary-soft text-primary-ink'
                : 'border-border-default bg-surface text-text-secondary hover:bg-primary-soft',
            )}
          >
            {entry.label}
            <span className="text-text-muted">{countFor(entry.id)}</span>
          </button>
        ))}
      </div>

      {showRecommended ? (
        <div className="wb-nav__group">
          <p className="wb-nav__group-title">
            <span>推荐练习</span>
          </p>
          <ul className="wb-nav__list">
            {recommended.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  aria-current={entry.id === currentId}
                  onClick={() => onSelect(entry.id)}
                  className="wb-nav__item"
                >
                  <span className="wb-nav__item-title">
                    {entry.label}
                    <span className="wb-nav__item-meta">{entry.note ? `${entry.reason} · ${entry.note}` : entry.reason}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isPending ? (
        <p className="wb-nav__empty" role="status">
          正在读取题目…
        </p>
      ) : isError ? (
        <p className="wb-nav__empty">题目列表暂时无法加载。</p>
      ) : groups.length ? (
        groups.map((group) => (
          <div key={group.key} className="wb-nav__group">
            <p className="wb-nav__group-title">
              <span>{group.title}</span>
              <span>{group.items.length}</span>
            </p>
            <ul className="wb-nav__list">
              {group.items.map((item, index) => {
                const id = exerciseIdOf(item);
                const status = exerciseStatus(item);
                const difficulty = difficultyOf(item);
                const title = exerciseTitle(item, `练习 ${index + 1}`);
                return (
                  <li key={id ?? `${group.key}-${index}`}>
                    <button
                      type="button"
                      aria-current={id !== undefined && id === currentId}
                      onClick={() => id !== undefined && onSelect(id)}
                      className="wb-nav__item"
                    >
                      <span className="wb-nav__item-title">
                        {title}
                        <span className="wb-nav__item-meta">
                          {difficulty ? `${difficulty} · ` : ''}
                          {STATUS_LABEL[status]}
                        </span>
                      </span>
                      <span className={cn('wb-nav__mark', `wb-nav__mark--${status}`)}>
                        {STATUS_LABEL[status]}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))
      ) : (
        <p className="wb-nav__empty">没有匹配的题目。</p>
      )}
    </div>
  );
}
