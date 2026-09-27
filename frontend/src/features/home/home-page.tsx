import { useAuth } from '@/features/auth/auth-context';
import { FirstRunSurface } from './first-run';
import { LearningSpaces } from './learning-spaces';
import { NextUp } from './next-up';
import { useSpaceContext } from './space-context';
import { TodaysDecision } from './todays-decision';

/** The greeting is the clock's, not the product's — no claim is made about the learner. */
export function greetingFor(hour: number): string {
  if (hour < 5) return '夜深了';
  if (hour < 11) return '早上好';
  if (hour < 13) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

/**
 * The personal learning home.
 *
 * Three questions, in the order a learner asks them: what to do now, what else is on today, and
 * how the three directions stand. The page used to answer four — it also carried the eight most
 * recent learning events, which is a log, and a second index of the three spaces, which is the
 * header drawn again. Both pushed today's work down the screen, and neither helped anyone decide
 * anything; the log now lives in 学习报告, where a learner goes when they want history.
 */
export function HomePage() {
  const auth = useAuth();
  const displayName = auth.user?.nickname || auth.user?.username;
  const space = useSpaceContext();

  // Until the three directions have answered, the page promotes nothing: guessing here would
  // either show a start prompt to a learner who is already set up, or float an agenda item that
  // belongs in the list below. The two states are mutually exclusive — once any direction holds
  // a context, the start prompt is gone for good, so an empty agenda can only ever be reported
  // as an empty agenda, never as "set yourself up", which the learner has already done.
  const needsFirstSetup = space.settled && !space.anyConfigured;

  return (
    <div className="pb-12">
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <header>
          {/* `wrap-anywhere` because the greeting opens with the learner's own name: a long
              unbroken one (no spaces, no hyphen) has no wrap opportunity and would push the
              heading — and the page — wider than the viewport on a phone. */}
          <h1 className="text-page-title font-semibold text-text-primary wrap-anywhere">
            {displayName
              ? `${greetingFor(new Date().getHours())}，${displayName}`
              : greetingFor(new Date().getHours())}
          </h1>
        </header>

        {needsFirstSetup ? (
          <div className="mt-8">
            <FirstRunSurface spaces={space.spaces} />
          </div>
        ) : (
          <>
            <TodaysDecision courseNames={space.courseNames} />
            <NextUp courseNames={space.courseNames} />
          </>
        )}

        <LearningSpaces spaces={space.spaces} />
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
