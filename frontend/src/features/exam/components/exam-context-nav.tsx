import { Link } from '@tanstack/react-router';
import { cn } from '@/lib/utils';

export type ExamContextItem = 'overview' | 'setup' | 'subjects' | 'cs408';

const items: ReadonlyArray<{ id: ExamContextItem; label: string; to: '/exam' | '/exam/setup' | '/exam/subjects' | '/exam/cs408' }> = [
  { id: 'overview', label: '我的备考', to: '/exam' },
  { id: 'subjects', label: '科目', to: '/exam/subjects' },
  { id: 'cs408', label: 'CS408', to: '/exam/cs408' },
];

export function ExamContextNav({ activeItem }: { activeItem: ExamContextItem }) {
  return (
    <nav className="border-b border-lab-grid/45" aria-label="考研学习导航">
      <div className="mx-auto flex max-w-content gap-1 overflow-x-auto px-5 sm:px-8 lg:px-12">
        {items.map((item) => {
          const active = item.id === activeItem || (activeItem === 'setup' && item.id === 'overview');
          return (
            <Link
              key={item.id}
              to={item.to}
              activeOptions={{ exact: true }}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'inline-flex min-h-11 shrink-0 items-center border-b-2 px-4 text-body transition-colors duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset',
                active ? 'border-lab-accent text-lab-ink font-semibold' : 'border-transparent text-text-secondary hover:text-lab-ink',
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
