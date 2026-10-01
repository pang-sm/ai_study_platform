import { useMemo, useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { StatusNote } from '@/components/ui/status-note';
import { PageHeader } from '@/components/page/page-header';
import { LoadingState } from '@/components/page/loading-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { useAdaptivePractice } from '@/components/learning/p4-api';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { serverMessage } from '@/lib/api/server-message';
import {
  useAnswerCoursePractice,
  useCourseKnowledgeStructure,
  useCoursePracticeHistory,
  useCoursePracticeSession,
  useGenerateCoursePractice,
  type PracticeQuestion,
  type PracticeSession,
} from '@/features/course/api/course';
import { CoursePageShell } from './course-page-shell';

/* ------------------------------------------------------------------ vocabulary */

const SCOPE_OPTIONS = [
  { value: 'knowledge_point', label: '当前知识点' },
  { value: 'chapter', label: '当前章节' },
  { value: 'course', label: '整门课程' },
] as const;

const GOAL_OPTIONS = [
  { value: 'consolidate', label: '巩固理解' },
  { value: 'gap_fill', label: '查漏补缺' },
  { value: 'exam_train', label: '考试训练' },
] as const;

const COUNT_OPTIONS = [3, 5, 10] as const;

const DIFFICULTY_OPTIONS = [
  { value: 'adaptive', label: '自适应' },
  { value: 'basic', label: '基础' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '较难' },
] as const;

const QUESTION_TYPE_LABELS: Record<string, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  short_answer: '简答题',
};

function questionTypeLabel(value: string | undefined): string {
  return QUESTION_TYPE_LABELS[value ?? ''] ?? '题目';
}

/** The set's questions, always an array — the read may omit the field when it is empty. */
function questionsOf(session: PracticeSession): PracticeQuestion[] {
  return session.questions ?? [];
}

/**
 * What the learner is practising, read back from the questions themselves.
 *
 * Derived rather than stored: the server attributes every question to a knowledge point, so the
 * set's own scope is a fact of its contents. A set whose questions share one point says that
 * point; one spanning a chapter says the chapter; one spanning the course says so.
 */
function scopeLabelOf(questions: PracticeQuestion[]): string {
  if (!questions.length) return '';
  const points = new Set(questions.map((question) => question.knowledge_point_title).filter(Boolean));
  if (points.size === 1) return [...points][0]!;
  const chapters = new Set(questions.map((question) => question.chapter).filter(Boolean));
  if (chapters.size === 1) return [...chapters][0]!;
  return '整门课程';
}

/* ------------------------------------------------------------------ the question */

type AnswerKind = 'radio' | 'checkbox' | 'text';

function answerKind(questionType: string | undefined): AnswerKind {
  if (questionType === 'multiple_choice') return 'checkbox';
  if (questionType === 'short_answer') return 'text';
  return 'radio';
}

/**
 * ONE question, in the input its own type calls for.
 *
 * A single choice is a set of radios, a multiple choice a set of checkboxes, a true/false a
 * pair of radios, and only a short answer is a textarea — the answer control is a property of
 * the question, never a guess made from its text.
 */
function QuestionBody({
  question,
  draft,
  submitted,
  onChange,
}: {
  question: PracticeQuestion;
  draft: string;
  submitted: boolean;
  onChange: (value: string) => void;
}) {
  const kind = answerKind(question.question_type);
  const options = Object.entries(question.options ?? {});
  const stemId = `practice-stem-${question.id}`;

  if (kind === 'text') {
    return (
      <fieldset disabled={submitted} className="mt-6">
        <p id={stemId} className="text-card-title font-medium text-text-primary">{question.stem}</p>
        <label htmlFor={`practice-answer-${question.id}`} className="mt-4 block text-body text-text-secondary">
          你的作答
        </label>
        <textarea
          id={`practice-answer-${question.id}`}
          value={draft}
          disabled={submitted}
          onChange={(event) => onChange(event.target.value)}
          rows={6}
          aria-labelledby={stemId}
          className="mt-2 w-full rounded-card border border-border-default bg-surface p-4 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          placeholder="写下你的答案"
        />
      </fieldset>
    );
  }

  const selected = kind === 'checkbox' ? new Set(draft.split('')) : new Set([draft]);
  return (
    <fieldset disabled={submitted} className="mt-6">
      <p id={stemId} className="text-card-title font-medium text-text-primary">{question.stem}</p>
      <div role={kind === 'checkbox' ? 'group' : 'radiogroup'} aria-labelledby={stemId} className="mt-4 space-y-2">
        {options.map(([key, text]) => {
          const isSelected = selected.has(key);
          return (
            <label
              key={key}
              className={`flex cursor-pointer items-start gap-3 rounded-control border p-3 text-body transition-colors ${
                isSelected ? 'border-primary bg-primary-soft text-text-primary' : 'border-border-default bg-surface text-text-primary hover:bg-primary-soft/40'
              }`}
            >
              <input
                type={kind}
                name={`practice-${question.id}`}
                value={key}
                checked={isSelected}
                disabled={submitted}
                onChange={() => {
                  if (kind === 'checkbox') {
                    const next = new Set(selected);
                    if (next.has(key)) next.delete(key);
                    else next.add(key);
                    onChange([...next].sort().join(''));
                  } else {
                    onChange(key);
                  }
                }}
                className="mt-1"
              />
              <span className="min-w-0">
                <span className="font-medium">{key}.</span> {text}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** The verdict for the question the learner just answered — or already answered. */
function Verdict({ question }: { question: PracticeQuestion }) {
  const result = question.result;
  if (!result) return null;
  const selfReview = result.correct === null || result.correct === undefined;
  const heading = selfReview ? '请自行对照参考答案' : result.correct ? '回答正确' : '回答错误';
  return (
    <section
      aria-live="polite"
      className={`mt-6 border-l-2 pl-4 ${selfReview ? 'border-border-default' : result.correct ? 'border-success' : 'border-danger'}`}
    >
      <p className={`flex items-center gap-2 text-body font-medium ${selfReview ? 'text-text-primary' : result.correct ? 'text-success-ink' : 'text-danger-ink'}`}>
        {selfReview ? null : result.correct ? <Check className="size-4" aria-hidden="true" /> : <X className="size-4" aria-hidden="true" />}
        {heading}
      </p>
      <dl className="mt-3 space-y-2 text-body">
        <div>
          <dt className="text-metadata text-text-muted">你的答案</dt>
          <dd className="text-text-primary">{result.user_answer || '未作答'}</dd>
        </div>
        <div>
          <dt className="text-metadata text-text-muted">正确答案</dt>
          <dd className="text-text-primary">{result.standard_answer}</dd>
        </div>
        {result.analysis ? (
          <div>
            <dt className="text-metadata text-text-muted">解析</dt>
            <dd className="max-w-prose text-text-secondary">{result.analysis}</dd>
          </div>
        ) : null}
        {result.knowledge_point_title ? (
          <div>
            <dt className="text-metadata text-text-muted">相关知识点</dt>
            <dd className="text-text-primary">{result.knowledge_point_title}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}

/** 1 2 3 4 5 — how far the set has got, without repeating a single word of the questions. */
function QuestionNavigator({
  session,
  current,
  onSelect,
}: {
  session: PracticeSession;
  current: number;
  onSelect: (index: number) => void;
}) {
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="本组题目">
      {questionsOf(session).map((question, index) => {
        const state = question.result
          ? question.result.correct === null || question.result.correct === undefined ? 'self' : question.result.correct ? 'correct' : 'wrong'
          : 'unanswered';
        const tone = state === 'correct' ? 'border-success bg-success-soft text-success-ink'
          : state === 'wrong' ? 'border-danger bg-danger-soft text-danger-ink'
          : state === 'self' ? 'border-border-default bg-surface text-text-primary'
          : 'border-border-default bg-surface text-text-muted';
        return (
          <li key={question.id}>
            <button
              type="button"
              onClick={() => onSelect(index)}
              aria-current={index === current ? 'step' : undefined}
              aria-label={`第 ${index + 1} 题${
                state === 'correct' ? '，已答对' : state === 'wrong' ? '，已答错'
                : state === 'self' ? '，已作答' : '，未作答'}`}
              className={`size-9 rounded-control border text-body font-medium ${tone} ${
                index === current ? 'ring-2 ring-primary ring-offset-2' : ''
              }`}
            >
              {index + 1}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ the set */

function FinishSummary({ session }: { session: PracticeSession }) {
  const questions = questionsOf(session);
  const graded = questions.filter((question) => question.result && question.result.correct !== null && question.result.correct !== undefined);
  const correct = graded.filter((question) => question.result?.correct).length;
  const toReview = questions
    .filter((question) => question.result && question.result.correct === false)
    .map((question) => question.knowledge_point_title)
    .filter((title): title is string => Boolean(title));
  const uniqueToReview = [...new Set(toReview)];

  return (
    <section aria-labelledby="practice-finished" className="border-l-2 border-success pl-4">
      <h2 id="practice-finished" className="text-card-title font-medium text-text-primary">本次练习完成</h2>
      <p className="mt-2 text-body text-text-secondary">
        {session.total ?? questions.length} 题 · 正确 {correct} · 错误 {graded.length - correct}
      </p>
      {uniqueToReview.length ? (
        <div className="mt-4">
          <p className="text-metadata text-text-muted">需要复习</p>
          <ul className="mt-1 space-y-1 text-body text-text-primary">
            {uniqueToReview.map((title) => <li key={title}>{title}</li>)}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/**
 * The set the learner is on: one question at a time, its verdict after they answer, and the way
 * to the next one.
 *
 * The whole set comes from ONE server read, so the progress, the navigator and the verdicts can
 * never disagree with each other — there is no second copy of "which question am I on".
 */
function PracticePlayer({
  courseId,
  session,
  readOnly,
  onClosed,
  onFinishAnother,
}: {
  courseId: string;
  session: PracticeSession;
  readOnly: boolean;
  onClosed?: (attemptId: number) => void;
  onFinishAnother?: () => void;
}) {
  const questions = questionsOf(session);
  const [index, setIndex] = useState(() =>
    Math.max(0, questions.findIndex((question) => !question.answered)));
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const answer = useAnswerCoursePractice(courseId);

  const question = questions[index];
  if (!question) return null;
  const draft = drafts[question.id] ?? '';
  const submitted = Boolean(question.result);
  const answeredAll = questions.every((item) => item.answered);

  const nextIndex = () => {
    for (let step = 1; step <= questions.length; step += 1) {
      const candidate = (index + step) % questions.length;
      if (!questions[candidate]!.answered) return candidate;
    }
    return index;
  };

  const callError = answer.isError
    ? answer.error instanceof ApiRequestError ? serverMessage(answer.error.detail) : null
    : null;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <p className="text-body text-text-secondary">
          正在练习：<span className="text-text-primary">{scopeLabelOf(questions)}</span>
        </p>
        <p className="text-metadata text-text-muted">{index + 1} / {session.total ?? questions.length}</p>
      </div>

      <div className="mt-4">
        <QuestionNavigator session={session} current={index} onSelect={setIndex} />
      </div>

      <p className="mt-6 text-metadata text-text-muted">
        {questionTypeLabel(question.question_type)}
        {question.difficulty ? ` · ${question.difficulty}` : ''}
        {question.chapter ? ` · ${question.chapter}` : ''}
      </p>
      <QuestionBody
        question={question}
        draft={draft}
        submitted={submitted}
        onChange={(value) => setDrafts((current) => ({ ...current, [question.id]: value }))}
      />

      {submitted ? <Verdict question={question} /> : null}

      {callError ? <StatusNote tone="danger" className="mt-4">{callError}</StatusNote> : null}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {!submitted && !readOnly ? (
          <Button
            disabled={!draft.trim() || answer.isPending}
            onClick={() => answer.mutate(
              { attemptId: session.attempt_id, questionId: question.id, answer: draft },
              {
                // The LAST answer closes the set, and a closed set is no longer "the open one" —
                // so the page names it in the URL. Without this the learner's own summary would
                // be replaced by the entry screen the moment they finished.
                onSuccess: (response) => {
                  if (response.session?.status === 'submitted') {
                    onClosed?.(response.session.attempt_id ?? session.attempt_id);
                  }
                },
              })}
          >
            {answer.isPending ? '正在提交…' : '提交答案'}
          </Button>
        ) : null}
        {submitted && !answeredAll ? <Button onClick={() => setIndex(nextIndex())}>下一题</Button> : null}
        {answeredAll && onFinishAnother ? <Button onClick={onFinishAnother}>再练一组</Button> : null}
        {answeredAll ? (
          <Button asChild variant="secondary">
            <Link to="/course/$courseId/wrong" params={{ courseId }}>查看错题</Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ generation */

function Choice<T extends string>({
  legend,
  options,
  value,
  onChange,
  disabled,
}: {
  legend: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="mt-5">
      <legend className="text-metadata font-medium tracking-eyebrow text-text-muted">{legend}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`h-9 rounded-control border px-3 text-body ${
              value === option.value
                ? 'border-primary bg-primary-soft font-medium text-text-primary'
                : 'border-border-default bg-surface text-text-secondary hover:bg-primary-soft/40'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function GeneratePanel({
  courseId,
  chapters,
  pointId,
  chapterId,
  onGenerated,
}: {
  courseId: string;
  chapters: { id: number | null; title: string; points: { id: number; title: string }[] }[];
  pointId?: number;
  chapterId?: number;
  onGenerated: (attemptId: number) => void;
}) {
  const navigate = useNavigate();
  const structure = chapters;
  const point = structure.flatMap((chapter) => chapter.points).find((item) => item.id === pointId);
  const [scope, setScope] = useState<'knowledge_point' | 'chapter' | 'course'>(
    point ? 'knowledge_point' : chapterId ? 'chapter' : 'course');
  const [goal, setGoal] = useState<'consolidate' | 'gap_fill' | 'exam_train'>('consolidate');
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState<'adaptive' | 'basic' | 'medium' | 'hard'>('adaptive');
  const [scopePoint, setScopePoint] = useState<number | undefined>(point?.id);
  const [scopeChapter, setScopeChapter] = useState<number | undefined>(chapterId);
  const generate = useGenerateCoursePractice(courseId);

  const missingStructure = structure.length === 0;
  const error = generate.isError
    ? generate.error instanceof ApiRequestError ? serverMessage(generate.error.detail) : null
    : null;

  if (missingStructure) {
    return (
      <EmptyState
        title="这门课程还没有知识结构。"
        description="练习按你的知识结构出题，先建立知识结构再开始。"
        action={
          <Button asChild variant="secondary">
            <Link to="/course/$courseId/knowledge" params={{ courseId }}>去建立知识结构</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div>
      {point ? (
        <p className="text-body text-text-secondary">
          当前知识点：<span className="text-text-primary">{point.title}</span>
        </p>
      ) : null}

      <Choice legend="练习范围" options={SCOPE_OPTIONS} value={scope} onChange={setScope} />

      {scope === 'knowledge_point' ? (
        <label className="mt-3 block">
          <span className="text-body text-text-secondary">知识点</span>
          <select
            value={scopePoint ?? ''}
            onChange={(event) => setScopePoint(Number(event.target.value))}
            className="mt-2 h-10 w-full max-w-md rounded-control border border-border-default bg-surface px-3 text-body text-text-primary"
          >
            <option value="" disabled>请选择知识点</option>
            {structure.map((chapter) => (
              <optgroup key={chapter.title} label={chapter.title}>
                {chapter.points.map((item) => (
                  <option key={item.id} value={item.id}>{item.title}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      ) : null}

      {scope === 'chapter' ? (
        <label className="mt-3 block">
          <span className="text-body text-text-secondary">章节</span>
          <select
            value={scopeChapter ?? ''}
            onChange={(event) => setScopeChapter(Number(event.target.value))}
            className="mt-2 h-10 w-full max-w-md rounded-control border border-border-default bg-surface px-3 text-body text-text-primary"
          >
            <option value="" disabled>请选择章节</option>
            {structure.map((chapter) => chapter.id ? (
              <option key={chapter.id} value={chapter.id}>{chapter.title}</option>
            ) : null)}
          </select>
        </label>
      ) : null}

      <Choice legend="练习目标" options={GOAL_OPTIONS} value={goal} onChange={setGoal} />
      <Choice
        legend="题量"
        options={COUNT_OPTIONS.map((value) => ({ value: String(value), label: `${value} 题` }))}
        value={String(count)}
        onChange={(value) => setCount(Number(value))}
      />
      <Choice legend="难度" options={DIFFICULTY_OPTIONS} value={difficulty} onChange={setDifficulty} />

      {error ? <StatusNote tone="danger" className="mt-4">{error}</StatusNote> : null}

      <Button
        className="mt-6"
        disabled={generate.isPending
          || (scope === 'knowledge_point' && !scopePoint)
          || (scope === 'chapter' && !scopeChapter)}
        onClick={() => generate.mutate({
          scope, goal, count, difficulty,
          knowledge_point_id: scope === 'knowledge_point' ? scopePoint ?? null : null,
          chapter_id: scope === 'chapter' ? scopeChapter ?? null : null,
        }, {
          onSuccess: (response) => {
            // The URL carries the set, so a reload (or a shared link) reopens this same one.
            void navigate({
              to: '/course/$courseId/practice',
              params: { courseId },
              search: { session: response.attempt_id },
            });
            onGenerated(response.attempt_id);
          },
        })}
      >
        {generate.isPending ? '正在生成…' : '生成练习'}
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ page */

/**
 * 练习 — one scoped set, played one question at a time.
 *
 * The page has three states and shows exactly one of them: the set in front of the learner, the
 * entry that creates one, or a finished set they opened from history. Recommendations and
 * history are secondary and sit BELOW the task, never above it.
 */
export function CoursePracticePage({
  courseId,
  pointId,
  chapterId,
  sessionId,
}: {
  courseId: string;
  pointId?: number;
  chapterId?: number;
  sessionId?: number;
}) {
  const navigate = useNavigate();
  const structure = useCourseKnowledgeStructure(courseId);
  const sessionQuery = useCoursePracticeSession(courseId, sessionId);
  const [panelOpen, setPanelOpen] = useState(Boolean(pointId || chapterId));

  const session = sessionQuery.data?.session ?? null;
  const openSet = session && session.status !== 'submitted' ? session : null;
  const finishedSet = session && session.status === 'submitted' ? session : null;

  const chapters = useMemo(() => (structure.data?.chapters ?? []).map((chapter) => ({
    id: chapter.id ?? null,
    title: chapter.title,
    points: chapter.points.map((point) => ({ id: point.id, title: point.title })),
  })), [structure.data]);

  const showEntry = !openSet;

  return (
    <CoursePageShell courseId={courseId} active="practice">
      {/* ONE entry control, and it is the same one at both moments: the empty state offers
          「AI 生成练习」 and the open panel offers 「收起设置」. Two buttons saying the same thing
          on one screen is how a page starts looking like a menu. */}
      <PageHeader
        title="练习"
        actions={showEntry && panelOpen ? (
          <Button variant="secondary" onClick={() => setPanelOpen(false)}>收起设置</Button>
        ) : null}
      />

      {sessionQuery.isError ? (
        <StatusNote tone="danger" className="mt-6">练习暂时无法加载。</StatusNote>
      ) : null}

      {sessionQuery.isPending && sessionId !== undefined ? (
        <LoadingState label="正在读取这次练习…" className="mt-8" />
      ) : null}

      {finishedSet ? (
        <div className="mt-8 space-y-8">
          <FinishSummary session={finishedSet} />
          <PracticePlayer
            courseId={courseId}
            session={finishedSet}
            readOnly
            onFinishAnother={() => void navigate({
              to: '/course/$courseId/practice', params: { courseId }, search: {},
            })}
          />
        </div>
      ) : null}

      {openSet ? (
        <div className="mt-8">
          <PracticePlayer
            courseId={courseId}
            session={openSet}
            readOnly={false}
            onClosed={(attemptId) => void navigate({
              to: '/course/$courseId/practice',
              params: { courseId },
              search: { session: attemptId },
            })}
          />
        </div>
      ) : null}

      {showEntry && panelOpen ? (
        <section className="mt-8" aria-labelledby="practice-generate-title">
          <SectionHeading id="practice-generate-title" title="生成一组练习" />
          <div className="mt-4">
            {structure.isPending ? (
              <LoadingState label="正在读取知识结构…" />
            ) : structure.isError ? (
              <StatusNote tone="warning">知识结构暂时无法加载。</StatusNote>
            ) : (
              <GeneratePanel
                courseId={courseId}
                chapters={chapters}
                pointId={pointId}
                chapterId={chapterId}
                onGenerated={() => setPanelOpen(false)}
              />
            )}
          </div>
        </section>
      ) : null}

      {showEntry && !panelOpen ? (
        <div className="mt-8">
          <Button onClick={() => setPanelOpen(true)}>AI 生成练习</Button>
        </div>
      ) : null}

      {showEntry ? <RecommendedPractice courseId={courseId} chapters={chapters} /> : null}

      <PracticeHistory courseId={courseId} />
    </CoursePageShell>
  );
}

/**
 * Practice the learner has a REASON to do, taken from the product's own ranking.
 *
 * Each row names the rule that selected it and the knowledge point it belongs to, and starts a
 * short set on exactly that point. A recommendation whose point is no longer in the active
 * structure is dropped rather than guessed at — and when nothing resolves, the whole block is
 * absent instead of explaining its own emptiness.
 */
function RecommendedPractice({
  courseId,
  chapters,
}: {
  courseId: string;
  chapters: { id: number | null; title: string; points: { id: number; title: string }[] }[];
}) {
  const query = useAdaptivePractice({ serviceKey: 'course_learning', courseId });
  const generate = useGenerateCoursePractice(courseId);

  const rows = useMemo(() => {
    const byTitle = new Map(chapters.flatMap((chapter) => chapter.points.map((point) => [point.title, point] as const)));
    const seen = new Set<string>();
    const out: { title: string; pointId: number; reason: string }[] = [];
    for (const candidate of query.data?.candidates ?? []) {
      const title = candidate.knowledge_point_name?.trim();
      if (!title || seen.has(title)) continue;
      const point = byTitle.get(title);
      if (!point) continue;
      seen.add(title);
      out.push({ title, pointId: point.id, reason: query.data?.reasons?.[candidate.reason] ?? '' });
      if (out.length >= 3) break;
    }
    return out;
  }, [query.data, chapters]);

  if (query.isPending || query.isError || !rows.length) return null;
  return (
    <section className="mt-10" aria-labelledby="practice-recommended-title">
      <SectionHeading id="practice-recommended-title" title="推荐练习" />
      <ol className="mt-4 space-y-4">
        {rows.map((row) => (
          <li key={row.title} className="border-l-2 border-border-default pl-4">
            <p className="text-body font-medium text-text-primary">{row.title}</p>
            {row.reason ? <p className="mt-1 max-w-prose text-body text-text-secondary">{row.reason}</p> : null}
            <p className="mt-1 text-metadata text-text-muted">3 题 · 自适应</p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              disabled={generate.isPending}
              onClick={() => generate.mutate({ scope: 'knowledge_point', knowledge_point_id: row.pointId, count: 3, difficulty: 'adaptive', goal: 'gap_fill' })}
            >
              开始
            </Button>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Finished sets, newest first. A set is one row; opening it shows the questions. */
function PracticeHistory({ courseId }: { courseId: string }) {
  const query = useCoursePracticeHistory(courseId);
  const items = query.data?.items ?? [];
  if (query.isPending || query.isError || !items.length) return null;

  return (
    <section className="mt-10" aria-labelledby="practice-history-title">
      <SectionHeading id="practice-history-title" title="练习历史" />
      <ol className="mt-4 border-t border-border-default">
        {items.map((item) => (
          <li key={item.session_id} className="border-b border-border-default">
            <Link
              to="/course/$courseId/practice"
              params={{ courseId }}
              search={{ session: item.session_id }}
              className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-3 text-body hover:bg-primary-soft/40"
            >
              <span className="text-text-primary">
                {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' }) : ''}
                {' · '}
                {[item.chapter, item.knowledge_point_title].filter(Boolean).join(' · ')}
              </span>
              <span className="text-text-secondary">{item.total} 题 · {item.correct_count} 正确</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
