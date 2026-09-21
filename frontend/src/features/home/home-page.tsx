import { Link } from '@tanstack/react-router';
import { useAuth } from '@/features/auth/auth-context';
import { useReviewSummary } from '@/features/advanced/api/workflows';
import { AgendaFocus, DailyAgenda } from './daily-agenda';
import { FirstRunSurface } from './first-run';
import { LearningSpaces } from './learning-worlds';
import { LearningStatus } from './learning-status';
import { RecentLearning } from './recent-learning';
import { useSpaceContext } from './space-context';

/**
 * The review queue as a count and a way in. The two figures are the server's own; `null` due
 * dates are reported as not stored rather than as a zero.
 */
function ReviewQueue() {
  const summary = useReviewSummary();

  return (
    <section aria-labelledby="review-title" className="border-t border-border-default pt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id="review-title" className="text-card-title font-semibold text-text-primary">
          待复习
        </h2>
        {summary.isSuccess ? (
          <Link
            to="/review"
            className="text-body text-primary-ink hover:text-primary-hover"
          >
            进入统一复习
          </Link>
        ) : null}
      </div>

      {summary.isPending ? (
        <p role="status" className="mt-4 text-body text-text-secondary">
          正在读取复习安排…
        </p>
      ) : summary.isError ? (
        <p role="alert" className="mt-4 text-body text-danger-ink">
          复习安排暂时无法加载。
        </p>
      ) : (
        <>
          <p className="mt-4 text-body text-text-primary">待处理：{summary.data.total}</p>
          <p className="mt-1 text-metadata text-text-secondary">
            已存复习日期：{summary.data.has_stored_due_dates ? '有' : '无'}
          </p>
        </>
      )}
    </section>
  );
}

export function HomePage() {
  const auth = useAuth();
  const displayName = auth.user?.nickname || auth.user?.username;
  const space = useSpaceContext();
  // Until the three spaces have answered, the page promotes nothing: guessing here would either
  // show a start prompt to a learner who is already set up, or float an agenda item that belongs
  // in the list below.
  //
  // The two states below are mutually exclusive, and that is the point: once any space holds a
  // context the first-run surface is gone for good, so an empty agenda can only ever be reported
  // as an empty agenda — never as "set yourself up", which the learner has already done.
  const dailyLearning = space.settled && space.anyConfigured;
  const needsFirstSetup = space.settled && !space.anyConfigured;

  return (
    <div className="pb-12">
      <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
        <header>
          <p className="text-metadata font-medium tracking-eyebrow text-text-muted">
            个人学习首页
          </p>
          {/* `wrap-anywhere` because the greeting opens with the learner's own name: a long
              unbroken one (no spaces, no hyphen) has no wrap opportunity and would push the
              heading — and the page — wider than the viewport on a phone. */}
          <h1 className="mt-2 text-page-title font-semibold text-text-primary wrap-anywhere">
            {displayName ? `${displayName}，今天从这里继续` : '今天从这里继续'}
          </h1>
          <p className="mt-3 max-w-prose text-body text-text-secondary">
            先看服务端给出的下一步，再看最近发生了什么；学习空间是之后的探索层。
          </p>
        </header>

        <div className="mt-10 space-y-12">
          {needsFirstSetup ? <FirstRunSurface spaces={space.spaces} /> : null}
          {dailyLearning ? <AgendaFocus /> : null}

          <DailyAgenda skipFirstItem={dailyLearning} />

          <ReviewQueue />

          <RecentLearning />

          <LearningSpaces />

          <LearningStatus />
        </div>
      </div>

      <footer className="mt-4 border-t border-border-default">
        <div className="mx-auto flex w-full max-w-content flex-wrap justify-between gap-3 px-5 py-6 text-metadata text-text-secondary sm:px-8 lg:px-12">
          <p>智学平台 / 把复杂知识，一步一步学明白。</p>
          <p>© 2026 ZHIXUE LEARNING LAB</p>
        </div>
      </footer>
    </div>
  );
}
