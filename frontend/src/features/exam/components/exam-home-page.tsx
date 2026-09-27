import { Link } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { LoadingState } from '@/components/page/loading-state';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { routePath } from '@/lib/router';
import { useRecentRecords, type LearningRecord } from '@/features/records/api/learning-records';
import { ApiRequestError } from '../api/content-status';
import { normalizeApiError } from '../api/errors';
import { useExamCatalog } from '../api/catalog';
import { useMathTaxonomy } from '../api/math-taxonomy';
import { useExamProfile } from '../api/profile';
import {
  subjectContinue,
  toExamPlan,
  type ExamContinue,
  type ExamPlan,
  type ExamPlanSubject,
} from '../view-models/exam-plan';
import { ExamPageShell } from './exam-page-shell';

/** The exam space's own record namespace (`core.learning_context.ServiceNamespace`). */
const EXAM_PREP = 'exam_prep';

/**
 * The four papers of 408 are recorded as four separate modules; this finds the last one the learner
 * actually worked in.
 *
 * Records arrive newest-first, so the first one carrying an `exam_module_id` IS "where I left off"
 * — the same fact the course space reads to name the course to continue. Nothing is inferred from
 * it beyond that: it says which paper, never which tool, so it is used to *name* the continuation
 * and not to guess a page inside the subject.
 */
function mostRecentExamModule(records: readonly LearningRecord[] | undefined): string | undefined {
  for (const record of records ?? []) {
    const moduleId = record.context?.exam_module_id;
    if (typeof moduleId === 'string' && moduleId) return moduleId;
  }
  return undefined;
}

/**
 * The exam space's home: the subjects the learner is actually sitting.
 *
 * The page is one block, 我的考试科目, and it holds every subject of the plan at once — the paper
 * that can be studied and the ones that are frameworks, side by side. That is the learner's own
 * question ("我考哪几门") answered where they asked it. It used to answer it twice: the subjects
 * as cards, then a 考试方案 summary below repeating the exam they belong to, which spent a whole
 * screen on what the catalogue had already said and pushed the studiable paper into a corner.
 *
 * The subjects that can be studied lead. Inside the block the studiable ones come first, so the
 * way in is the first thing on the page whatever the catalogue's own subject order happens to be
 * — and a framework-only subject, which has no way in, cannot push it aside.
 *
 * The space's own name is not repeated here. 考研学习 is already the highlighted item in the
 * global navigation, and a page title restating it spent the first screen on nothing.
 *
 * Every line comes from the profile, the catalogue or the study record. Where this build cannot
 * do something — a subject whose content is not written, a professional paper the learner named
 * themselves — the page says so in place, rather than offering a control that opens nothing.
 */
export function ExamHomePage() {
  const profile = useExamProfile();
  const catalog = useExamCatalog();
  const recent = useRecentRecords(8, EXAM_PREP);
  // The maths taxonomy is the backend's; a maths card says what it knows only once it has arrived.
  const math = useMathTaxonomy();

  if (profile.isPending || catalog.isPending) {
    return (
      <ExamPageShell back={false}>
        <LoadingState label="正在读取你的考试方案…" />
      </ExamPageShell>
    );
  }

  if (profile.isError || catalog.isError) {
    const state = errorState(profile.error ?? catalog.error);
    return (
      <ExamPageShell back={false}>
        <StatusNote tone="danger">{state}</StatusNote>
      </ExamPageShell>
    );
  }

  const plan = toExamPlan(catalog.data, profile.data, math.data);
  const resumeModuleKey = mostRecentExamModule(recent.data);

  // Nothing is configured yet, so there are no subjects to show and no plan to summarise: the one
  // useful thing is the way to configure it. The empty state and the button would say the same
  // sentence twice if both were drawn.
  if (!plan.configured) {
    return (
      <ExamPageShell back={false}>
        <section aria-labelledby="exam-subjects-title">
          <SectionHeading id="exam-subjects-title" title="我的考试科目" as="h1" />
          <EmptyState
            className="mt-5"
            title="还没有考试方案。"
            description="选择目标年份与备考方向，确认专业课和公共课，这套科目组合会成为你在考研学习里的全部学习范围。"
            action={
              <Button asChild>
                <Link to="/exam/setup">设置考试方案</Link>
              </Button>
            }
          />
        </section>
      </ExamPageShell>
    );
  }

  return (
    <ExamPageShell back={false}>
      <section aria-labelledby="exam-subjects-title">
        {/* One action per destination: 修改考试方案 changes the combination, and it belongs to the
            subjects it changes — which is this block, and nothing else on the page. */}
        <SectionHeading
          id="exam-subjects-title"
          title="我的考试科目"
          as="h1"
          action={
            <Link to="/exam/setup" className="exam-action">
              修改考试方案
            </Link>
          }
        />
        <div className="mt-5">
          {plan.subjects.length ? (
            <ul className="exam-subjects">
              {studiableFirst(plan.subjects).map((subject) => (
                <ExamSubjectCard
                  key={subject.id}
                  subject={subject}
                  resume={subjectContinue(subject, resumeModuleKey)}
                />
              ))}
            </ul>
          ) : (
            <EmptyState
              title="还没有选择考试科目。"
              description="在考试方案里确认专业课和公共课，它们会出现在这里。"
            />
          )}
        </div>
      </section>
    </ExamPageShell>
  );
}

/**
 * The subjects with a study surface first, in the order the plan already has them.
 *
 * This is the same rule the cards are drawn by — a subject's own maturity decides its treatment —
 * and it is why 408 leads without the page naming 408: on the day a second professional paper has
 * content, it takes the leading place by the same rule, and no template has to be edited.
 */
function studiableFirst(subjects: ExamPlan['subjects']): ExamPlan['subjects'] {
  return [
    ...subjects.filter((subject) => subject.maturity === 'open'),
    ...subjects.filter((subject) => subject.maturity !== 'open'),
  ];
}

function errorState(error: unknown): string {
  return error instanceof ApiRequestError
    ? normalizeApiError(error.status, error.detail).message
    : '考研学习暂时无法加载，请稍后重试。';
}

/**
 * One subject of the plan.
 *
 * The card says which line of the plan the subject sits on, what it is called, and one action:
 * the way in when this build can open the subject, and the page that explains it when it cannot.
 * That difference follows from the subject's own maturity, never from its name — a subject with a
 * study surface carries the accent and the primary action; one without carries the secondary
 * action and nothing else.
 *
 * It used to say more, and every line of it was a repetition or a claim: a 完整学习功能已开放 badge
 * on the card whose button already said 进入 408, the catalogue's own description of the paper
 * under its name, a sentence explaining the framework under each framework-only subject, and then
 * that framework's own state line. None of it is what a learner opens this page to read. They open
 * it to see which subjects they are sitting and to get back into the one they are studying — so
 * the card is the subject and the way in, and everything else is on the subject's own page, one
 * click away.
 */
function ExamSubjectCard({ subject, resume }: { subject: ExamPlanSubject; resume: ExamContinue | null }) {
  const fallbackHref = subject.maturity === 'custom' || subject.maturity === 'unknown'
    ? '/exam/setup'
    : `/exam/subjects/${subject.id}`;
  const fallbackLabel = subject.maturity === 'custom' || subject.maturity === 'unknown'
    ? '在考试方案中管理'
    : '查看科目';

  return (
    <li className={resume ? 'exam-subject exam-subject--open' : 'exam-subject'}>
      <span className="exam-subject__slot">{subject.slotLabel}</span>
      <h2 className="exam-subject__name">{subject.name}</h2>

      <div className="exam-subject__action">
        {resume ? (
          // The label comes from `subjectContinue`: "继续学习 · 操作系统" only when a study fact
          // named that paper, "进入 408" otherwise. Neither is hardcoded here.
          <Button asChild size="sm">
            <Link to={routePath(resume.href)} search={resume.search}>
              {resume.label}
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        ) : (
          <Button asChild size="sm" variant="secondary">
            <Link to={routePath(fallbackHref)}>{fallbackLabel}</Link>
          </Button>
        )}
      </div>
    </li>
  );
}
