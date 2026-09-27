import { useEffect, useRef, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { searchValueOut } from '@/lib/router';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useChapterPracticeAttempt, useChapterPracticeOutline, useChapterPracticeQuestions, useCreateChapterPracticeAttempt, useSaveChapterPracticeAnswers, useSubmitChapterPractice, type ChapterPracticeAttempt } from '@/features/exam/api/chapter-practice';
import { useQuestionExplain } from '@/features/exam/api/question-explain';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';
import { PracticeQuestionNavigator } from './practice-question-navigator';
import { AiFeedback } from '@/components/learning/ai-feedback';
import './cs408-practice-workspace.css';

type Question = ChapterPracticeAttempt['questions'][number];
type SubmitResult = NonNullable<ChapterPracticeAttempt['results']>[number];
type PracticeViewMode = 'questions' | 'summary';
/** One question's AI explanation, plus the follow-ups asked about it — all keyed by the turn. */
type ExplainState = { analysis?: string; error?: string; requestId?: string; followUps?: Array<{ question: string; answer: string }> };
const emptyQuestions: Question[] = [];

function chapterLabel(chapter: { chapter_no: number; chapter_title: string } | undefined, hasAttempt = false, conceptCode?: string) {
  // A concept-scoped practice states the concept it is scoped to. The code IS the identity
  // the attempt and its learning event carry, so showing it is showing the real scope —
  // not a mastery claim and not a model output.
  if (chapter) return `第 ${chapter.chapter_no} 章 · ${chapter.chapter_title}${conceptCode ? ` · 知识点 ${conceptCode}` : ''}`;
  // An attempt is a complete entry point on its own: a `?attempt=` deep link opens an
  // existing session without its chapter ever being addressed, and telling that learner to
  // "choose a chapter first" would be describing a state they are not in.
  if (hasAttempt) return '本次练习记录';
  return conceptCode ? `知识点 ${conceptCode}` : '选择章节后开始练习';
}

function QuestionBody({ question, answer, questionIndex, questionTotal, onChange, submitted }: { question: Question; answer: string; questionIndex: number; questionTotal: number; onChange: (answer: string) => void; submitted: boolean }) {
  if (question.question_type === 'big') {
    return <div className="practice-question practice-question--big"><QuestionIdentity index={questionIndex} total={questionTotal} chapter={question.chapter_name} /><p className="practice-question__type">简答题 · 自行复盘</p><h2>{question.stem}</h2><label className="practice-question__textarea-label" htmlFor={`answer-${question.id}`}>你的作答</label><textarea id={`answer-${question.id}`} value={answer} disabled={submitted} onChange={(event) => onChange(event.target.value)} placeholder="写下你的思路与答案" rows={9} /><p className="practice-question__hint">本题提交后可自行对照参考答案。</p></div>;
  }
  // The stem is a paragraph, NOT a <legend>. A full-width legend is laid into the fieldset's
  // own top border, so the 2px rule ran straight through the question text: the sentence the
  // learner is answering read as struck through. The fieldset keeps the group semantics, and
  // both it and the option group take their name from the stem through aria-labelledby.
  const stemId = `practice-stem-${question.id}`;
  return <fieldset className="practice-question" disabled={submitted} aria-labelledby={stemId}><QuestionIdentity index={questionIndex} total={questionTotal} chapter={question.chapter_name} /><p className="practice-question__type">选择题</p><p id={stemId} className="practice-question__stem">{question.stem}</p><div className="practice-question__options" role="radiogroup" aria-labelledby={stemId}>{Object.entries(question.options).map(([key, value]) => <label key={key} className={answer === key ? 'is-selected' : undefined}><input type="radio" name={`question-${question.id}`} value={key} checked={answer === key} onChange={() => onChange(key)} /><span><b>{key}</b>{value}</span></label>)}</div></fieldset>;
}

function sessionFacts(results: SubmitResult[]) { const answered = results.filter((r) => r.user_answer !== ''); const choices = answered.filter((r) => r.question_type === 'choice'); const correct = choices.filter((r) => r.correct === true); const incorrect = choices.filter((r) => r.correct === false); const selfReview = answered.filter((r) => r.question_type === 'big' && r.judge === 'self_review'); return { answered: answered.length, unanswered: results.length - answered.length, correct: correct.length, incorrect: incorrect.length, selfReview: selfReview.length, retryIds: incorrect.map((r) => r.question_id), denominator: choices.length }; }

function QuestionIdentity({ index, total, chapter }: { index: number; total: number; chapter: string }) {
  return (
    <div className="practice-question__identity">
      <p>
        <span>第 {index} / {total} 题</span>
        {chapter ? <span className="practice-question__chapter">{chapter}</span> : null}
      </p>
    </div>
  );
}

function ResultMark({ result, onExplain, onFollowUp, explainState }: { result?: SubmitResult; onExplain: () => void; onFollowUp: (question: string) => void; explainState: React.ComponentProps<typeof ExplainBlock>['state'] }) {
  if (!result) return null;
  const staticAnalysis = result.analysis.trim();
  if (result.question_type === 'big') {
    return <section className="practice-result practice-result--review" aria-labelledby="self-review-title">
      <h2 id="self-review-title">自行复盘</h2>
      <div className="practice-result__answer"><span>你的作答</span><p>{result.user_answer || '未作答'}</p></div>
      <div className="practice-result__answer"><span>参考答案</span><p>{result.standard_answer}</p></div>
      {staticAnalysis ? <StaticAnalysis analysis={staticAnalysis} /> : null}
      <ExplainBlock onExplain={onExplain} onFollowUp={onFollowUp} state={explainState} />
    </section>;
  }
  const unanswered = result.correct === null || result.user_answer === '';
  const verdict = unanswered ? '未作答' : result.correct ? '回答正确' : '回答错误';
  return <section className={`practice-result ${unanswered ? 'practice-result--review' : result.correct ? 'practice-result--correct' : 'practice-result--wrong'}`} aria-labelledby="grading-title">
    <span>判定</span><strong id="grading-title">{verdict}</strong>
    <small>你的答案：{result.user_answer || '未作答'}</small><small>正确答案：{result.standard_answer}</small>
    {staticAnalysis ? <StaticAnalysis analysis={staticAnalysis} /> : null}
    <ExplainBlock onExplain={onExplain} onFollowUp={onFollowUp} state={explainState} />
  </section>;
}

function StaticAnalysis({ analysis }: { analysis: string }) {
  return <section className="practice-result__analysis" aria-labelledby="static-analysis-title"><h2 id="static-analysis-title">题目解析</h2><p>{analysis}</p></section>;
}

/**
 * The AI explanation of THIS question, and the follow-ups that stay about it.
 *
 * It is deliberately NOT the default reading of a submitted answer: 题目解析 is the product's own
 * text and it is free and instant, while this is a model call that consumes the learner's AI
 * 额度 and takes seconds. A learner who wants it presses the button; one who does not is never
 * charged for it. It exists only after submission — before that, nobody here has an answer to
 * give away.
 *
 * Everything the model is told about comes from the question the learner is on: the stem, the
 * options, the answer they gave, the reference answer, the product's own 解析, and the knowledge
 * point the question examines. A follow-up is sent the same way, with the learner's own question
 * added, which is why 为什么 B 不对 needs no re-typing of the question.
 *
 * The follow-ups stay HERE. They used to open the product-wide assistant, which took the learner
 * off the question and promised only "a conversation about this subject" — the assistant had
 * never read the question at all.
 */
function ExplainBlock({ onExplain, onFollowUp, state }: {
  onExplain: () => void;
  onFollowUp: (question: string) => void;
  state: { loading: boolean; followingUp: boolean; analysis?: string; error?: string; requestId?: string; followUps?: ReadonlyArray<{ question: string; answer: string }> };
}) {
  const [draft, setDraft] = useState('');
  const ask = () => {
    const question = draft.trim();
    if (!question || state.followingUp) return;
    setDraft('');
    onFollowUp(question);
  };
  return <section className="practice-result__ai" aria-labelledby="ai-explain-title"><h2 id="ai-explain-title">AI 讲解</h2>
    {state.analysis ? <p>{state.analysis}</p> : null}
    {state.error ? <p role="alert">{state.error}</p> : null}
    {!state.analysis ? <Button variant="secondary" disabled={state.loading} onClick={onExplain}>{state.loading ? '正在生成讲解' : state.error ? '重新生成讲解' : 'AI 讲解这道题'}</Button> : null}
    {state.loading ? <p className="practice-result__ai-status" role="status" aria-live="polite">正在生成讲解</p> : null}
    {state.requestId ? <AiFeedback requestId={state.requestId} workflowId="exam_practice_ai_explain" /> : null}
    {state.followUps?.length ? <ul className="practice-result__followups-list">
      {state.followUps.map((turn, index) => (
        <li key={`${index}-${turn.question}`}>
          <p className="practice-result__followups-question">{turn.question}</p>
          <p>{turn.answer}</p>
        </li>
      ))}
    </ul> : null}
    {state.analysis ? <div className="practice-result__followups">
      <label className="practice-result__followups-title" htmlFor="practice-follow-up">继续追问这道题</label>
      <div className="practice-result__followups-row">
        <input
          id="practice-follow-up"
          type="text"
          value={draft}
          disabled={state.followingUp}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); ask(); } }}
          placeholder="例如：为什么 B 不对？"
          className="practice-result__followups-input"
        />
        <Button variant="secondary" size="sm" disabled={!draft.trim() || state.followingUp} onClick={ask}>
          {state.followingUp ? '正在作答' : '追问'}
        </Button>
      </div>
    </div> : null}
  </section>;
}

function createErrorMessage(error: unknown) {
  // A 422 here means the server refused the canonical concept the learner entered from —
  // the question set no longer carries it, or the id is not a canonical leaf of this
  // module. Saying so is honest; the generic "try again" would invite a retry loop that
  // cannot succeed.
  if (error instanceof ApiRequestError && error.status === 422) return '本知识点的练习内容已变化，请返回知识脉络重新进入。';
  return '操作未完成，请稍后重试。';
}

function explainErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.status === 401) return '需要重新登录';
    if (error.status === 403) return '当前无法使用 AI 讲解';
    if (error.status === 429) return 'AI 讲解额度暂不可用';
    if (error.status === 502) return 'AI 讲解暂时不可用';
  }
  return 'AI 讲解暂时不可用';
}

export function Cs408PracticeWorkspace({ moduleKey, chapterCode, conceptCode, attemptId: initialAttemptId, onAttemptChange }: { moduleKey?: string; chapterCode?: string; conceptCode?: string; attemptId?: number; onAttemptChange?: (attemptId: number) => void }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  const outline = useChapterPracticeOutline(module?.key ?? '');
  const questionsQuery = useChapterPracticeQuestions(module?.key ?? '', chapterCode ?? '', conceptCode);
  const create = useCreateChapterPracticeAttempt();
  const save = useSaveChapterPracticeAnswers();
  const submit = useSubmitChapterPractice();
  const [localAttemptId, setLocalAttemptId] = useState<number>();
  const [createdAttemptQuestionIds, setCreatedAttemptQuestionIds] = useState<number[]>();
  const attemptId = initialAttemptId ?? localAttemptId;
  const attempt = useChapterPracticeAttempt(module?.key ?? '', attemptId);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [resultByQuestionId, setResultByQuestionId] = useState<Record<number, SubmitResult>>({});
  const [explanations, setExplanations] = useState<Record<string, ExplainState>>({});
  const [explainingKey, setExplainingKey] = useState<string>();
  const [followingUpKey, setFollowingUpKey] = useState<string>();
  const [viewMode, setViewMode] = useState<PracticeViewMode>(); const [confirmSubmit, setConfirmSubmit] = useState(false);
  const confirmationRef = useRef<HTMLElement>(null);
  const continuePracticeRef = useRef<HTMLButtonElement>(null);
  const submitControlRef = useRef<HTMLButtonElement>(null);
  const explain = useQuestionExplain();
  const selectedChapter = outline.data?.chapters.find((entry) => entry.chapter_code === chapterCode);
  const chapterQuestions = questionsQuery.data?.items ?? emptyQuestions;
  // Attempt detail owns both the active membership and the order of an answer desk. Chapter
  // questions are only the source for beginning a new chapter attempt.
  const activeAttemptQuestionIds = attempt.data?.questions.map((question) => question.id) ?? [];
  const activeAttemptQuestionIdSet = new Set(activeAttemptQuestionIds);
  const createdAttemptQuestionIdSet = new Set(createdAttemptQuestionIds);
  const questions = attemptId === undefined
    ? chapterQuestions
    : attempt.data
      ? attempt.data.questions.filter((question) => activeAttemptQuestionIdSet.has(question.id))
      : createdAttemptQuestionIds
        ? chapterQuestions.filter((question) => createdAttemptQuestionIdSet.has(question.id))
        : emptyQuestions;
  const currentQuestion = questions[currentIndex];
  const isSubmittedAttempt = attempt.data?.attempt.status === 'submitted';
  const replayedResults = isSubmittedAttempt ? attempt.data?.results ?? [] : [];
  const authoritativeResults = replayedResults.length > 0 ? replayedResults : Object.values(resultByQuestionId);
  const authoritativeResultByQuestionId = Object.fromEntries(authoritativeResults.map((result) => [result.question_id, result]));
  const savedAnswers = attempt.data ? Object.fromEntries(attempt.data.questions.flatMap((question) => {
    const saved = attempt.data!.saved_answers[String(question.id)];
    return saved === undefined ? [] : [[String(question.id), saved]];
  })) : {};
  const reconciledAnswers = { ...savedAnswers, ...answers };
  const submitted = isSubmittedAttempt || authoritativeResults.length > 0;
  const displayedAnswers = submitted ? Object.fromEntries(authoritativeResults.map((result) => [String(result.question_id), result.user_answer])) : reconciledAnswers;
  const facts = sessionFacts(authoritativeResults);
  const chapterQuestionIds = chapterQuestions.map((question) => question.id);
  const defaultViewMode: PracticeViewMode = isSubmittedAttempt ? 'summary' : 'questions';
  const activeViewMode = viewMode ?? defaultViewMode;
  useEffect(() => {
    if (!confirmSubmit) return;
    const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    confirmationRef.current?.scrollIntoView?.({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
    continuePracticeRef.current?.focus();
  }, [confirmSubmit]);
  const updateAnswer = (questionId: number, answer: string) => setAnswers((current) => ({ ...current, [String(questionId)]: answer }));
  const start = () => create.mutate({ moduleKey: module!.key, questionIds: chapterQuestionIds, knowledgePointId: conceptCode }, { onSuccess: (response) => { setCreatedAttemptQuestionIds(chapterQuestionIds); setViewMode('questions'); setLocalAttemptId(response.attempt_id); onAttemptChange?.(response.attempt_id); } });
  const saveCurrent = () => { if (attemptId !== undefined) save.mutate({ moduleKey: module!.key, attemptId, answers: reconciledAnswers }); };
  const submitAll = () => { if (attemptId !== undefined) submit.mutate({ moduleKey: module!.key, attemptId, answers: reconciledAnswers }, { onSuccess: (response) => { setResultByQuestionId(Object.fromEntries(response.results.map((result) => [result.question_id, result]))); setViewMode('summary'); } }); };
  const requestSubmit = () => { const unanswered = questions.filter((question) => !(reconciledAnswers[String(question.id)] ?? '').trim()).length; if (unanswered) setConfirmSubmit(true); else submitAll(); };
  const dismissConfirmation = () => { submitControlRef.current?.focus(); setConfirmSubmit(false); };
  // A retry stays inside the concept the learner entered from: every id it can pass is drawn
  // from the concept-filtered question list, so the re-attempt carries the same canonical
  // concept and the write boundary validates it against that same set.
  const retry = (ids: number[]) => create.mutate({ moduleKey: module!.key, questionIds: ids, knowledgePointId: conceptCode }, { onSuccess: (response) => { setResultByQuestionId({}); setAnswers({}); setCreatedAttemptQuestionIds(ids); setCurrentIndex(0); setViewMode('questions'); setLocalAttemptId(response.attempt_id); onAttemptChange?.(response.attempt_id); } });
  const explainKey = currentQuestion && attemptId !== undefined ? `${attemptId}:${currentQuestion.id}` : undefined;
  /**
   * What the model is told about, for ONE question: the question itself, the answer the learner
   * gave, the reference answer, the product's own 解析, and the knowledge point the question
   * examines. All of it comes from the question the learner is looking at — the code is never sent
   * (`_leaf:1.1.1.1` means nothing to a model), only the point's name, when there is one.
   */
  const questionMaterial = (question: NonNullable<typeof currentQuestion>, result: SubmitResult) => ({
    stem: result.stem, options: result.options, standard_answer: result.standard_answer,
    user_answer: result.user_answer, question_type: result.question_type,
    analysis: result.analysis,
    knowledge_point: question.knowledge_point_name ?? undefined,
  });
  const explainCurrent = () => {
    if (!currentQuestion || !module || attemptId === undefined) return;
    const result = authoritativeResultByQuestionId[currentQuestion.id];
    if (!result) return;
    const key = `${attemptId}:${currentQuestion.id}`;
    setExplainingKey(key);
    setExplanations((current) => ({ ...current, [key]: {} }));
    explain.mutate({ moduleKey: module.key, input: questionMaterial(currentQuestion, result) }, {
      onSuccess: (response) => setExplanations((current) => ({ ...current, [key]: { analysis: response.analysis, requestId: response.request_id } })),
      onError: (error) => setExplanations((current) => ({ ...current, [key]: { error: explainErrorMessage(error) } })),
      onSettled: () => setExplainingKey((current) => current === key ? undefined : current),
    });
  };
  /** One follow-up about the SAME question, answered from the same material. */
  const followUpCurrent = (question: string) => {
    if (!currentQuestion || !module || attemptId === undefined || !question.trim()) return;
    const result = authoritativeResultByQuestionId[currentQuestion.id];
    const existing = explanations[`${attemptId}:${currentQuestion.id}`];
    if (!result || !existing?.analysis) return;
    const key = `${attemptId}:${currentQuestion.id}`;
    setFollowingUpKey(key);
    explain.mutate({ moduleKey: module.key, input: { ...questionMaterial(currentQuestion, result), follow_up: question.trim() } }, {
      onSuccess: (response) => setExplanations((current) => {
        const state = current[key] ?? {};
        return { ...current, [key]: { ...state, followUps: [...(state.followUps ?? []), { question: question.trim(), answer: response.analysis }] } };
      }),
      onError: (error) => setExplanations((current) => {
        const state = current[key] ?? {};
        return { ...current, [key]: { ...state, followUps: [...(state.followUps ?? []), { question: question.trim(), answer: explainErrorMessage(error) }] } };
      }),
      onSettled: () => setFollowingUpKey((current) => current === key ? undefined : current),
    });
  };

  if (!module) {
    return <ExamPageShell cs408Tab="practice"><Cs408SubjectChooser to="/exam/cs408/practice" description="章节练习按四门课分别组织。先选一门，再进入它的章节目录。" /></ExamPageShell>;
  }

  // A chapter (or an attempt) is open. The chapter-selection screen is then the whole page: the
  // two things below the desk — the deep-reasoning panel and the recommendation strip — are
  // about a chapter that has been chosen, and on the chooser they were a second, larger entry
  // point than the chapter list itself. Doing the questions is the task; these are help.
  const chapterOpen = Boolean(chapterCode) || attemptId !== undefined;
  return <ExamPageShell cs408Tab="practice" moduleKey={module.key}><section className="cs408-practice" aria-labelledby="practice-title"><header className="cs408-practice__header"><h1 id="practice-title" className="sr-only">章节练习</h1>{chapterOpen ? <span>{chapterLabel(selectedChapter, attemptId !== undefined, conceptCode)}</span> : null}</header>
    {!chapterCode && attemptId === undefined ? <PracticeSelector moduleKey={module.key} outline={outline.data} loading={outline.isPending} /> : null}
    {/* An attempt the learner opened by URL, while it loads or when it cannot be read. Both used
        to render nothing at all — a deep link to an attempt that is gone (or that is not theirs:
        the API answers 404 for both, deliberately) left a page whose entire body was an empty
        line, with no way back. It says what it is and offers the chapter again. */}
    {module && attemptId !== undefined && attempt.isPending ? <div className="cs408-practice__loading"><Skeleton className="h-9 w-40" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && attemptId !== undefined && attempt.isError ? <section className="cs408-practice__state" aria-labelledby="practice-attempt-unavailable"><h2 id="practice-attempt-unavailable">练习记录不可用</h2><p>这次练习记录不存在或已过期。</p><Button asChild variant="secondary"><Link to="/exam/cs408/practice" search={{ module: module.key, chapter: searchValueOut(chapterCode), concept: undefined, attempt: undefined }}>返回本章练习</Link></Button></section> : null}
    {module && chapterCode && attemptId === undefined && questionsQuery.isPending ? <div className="cs408-practice__loading"><Skeleton className="h-9 w-40" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && chapterCode && attemptId === undefined && (questionsQuery.isError || !questionsQuery.data) ? <section className="cs408-practice__state"><h2>章节练习暂时无法加载</h2><Button variant="secondary" onClick={() => void questionsQuery.refetch()}>重试</Button></section> : null}
    {module && chapterCode && attemptId === undefined && questionsQuery.data && questions.length === 0 ? <section className="cs408-practice__state"><h2>{conceptCode ? '本知识点暂无可用练习题' : '本章节暂无可用练习题'}</h2><a href={`/exam/cs408/practice?module=${module.key}${conceptCode ? `&chapter=${chapterCode}` : ''}`}>{conceptCode ? '返回本章练习' : '返回章节选择'}</a></section> : null}
    {currentQuestion ? <div className="cs408-practice__desk">{activeViewMode === 'questions' ? <PracticeQuestionNavigator total={questions.length} currentIndex={currentIndex} isAnswered={(index) => Boolean(displayedAnswers[String(questions[index]?.id)])} onSelect={(index) => { setViewMode('questions'); setCurrentIndex(index); }} /> : null}<div className="practice-main">{activeViewMode === 'summary' ? <section className="practice-summary"><h2>本次练习完成</h2><div className="practice-summary__facts"><p>共 {authoritativeResults.length} 题</p><p>已作答 {facts.answered} · 答对 {facts.correct} · 答错 {facts.incorrect} · 自行复盘 {facts.selfReview} · 未作答 {facts.unanswered}</p><p>{facts.denominator ? `自动判分题正确率 ${Math.round(facts.correct / facts.denominator * 100)}%` : '本次没有自动判分题'}</p></div><div className="practice-summary__actions"><Button variant="secondary" onClick={() => setViewMode('questions')}>查看本次题目</Button>{facts.retryIds.length ? <Button onClick={() => retry(facts.retryIds)}>重练本次错题</Button> : null}<Button variant="secondary" onClick={() => retry(chapterQuestionIds)}>{conceptCode ? '再做一遍本知识点' : '再做一遍本章'}</Button>{facts.incorrect > 0 ? <a href={`/exam/cs408/wrong?module=${module?.key}&status=active`}>去错题本订正</a> : null}<a href={conceptCode && chapterCode ? `/exam/cs408/practice?module=${module?.key}&chapter=${chapterCode}` : `/exam/cs408/practice?module=${module?.key}`}>返回章节</a></div></section> : <><QuestionBody question={currentQuestion} questionIndex={currentIndex + 1} questionTotal={questions.length} answer={displayedAnswers[String(currentQuestion.id)] ?? ''} submitted={submitted} onChange={(answer) => updateAnswer(currentQuestion.id, answer)} /><ResultMark result={authoritativeResultByQuestionId[currentQuestion.id]} onExplain={explainCurrent} onFollowUp={followUpCurrent} explainState={{ loading: explainingKey === explainKey, followingUp: followingUpKey === explainKey, ...explanations[explainKey ?? ''] }} /></>}{activeViewMode === 'questions' ? <div className="practice-main__actions"><div>{currentIndex > 0 ? <Button variant="ghost" onClick={() => setCurrentIndex((index) => index - 1)}>上一题</Button> : null}{currentIndex < questions.length - 1 ? <Button variant="ghost" onClick={() => setCurrentIndex((index) => index + 1)}>下一题</Button> : null}</div><div>{submitted ? <Button variant="secondary" onClick={() => setViewMode('summary')}>本次练习总结</Button> : null}{attemptId === undefined ? <Button disabled={create.isPending} onClick={start}>开始本章练习</Button> : submitted ? null : <><Button variant="secondary" disabled={save.isPending} onClick={saveCurrent}>保存答案</Button><Button ref={submitControlRef} disabled={submit.isPending} onClick={requestSubmit}>提交本章答案</Button></>}</div></div> : null}{confirmSubmit ? <section ref={confirmationRef} className="practice-confirm" role="alertdialog" aria-label="未完成提交确认"><h2>还有 {questions.filter((question) => !(reconciledAnswers[String(question.id)] ?? '').trim()).length} 题未作答</h2><p>仍然提交本次练习吗？</p><div><Button ref={continuePracticeRef} variant="secondary" onClick={dismissConfirmation}>继续作答</Button><Button onClick={() => { setConfirmSubmit(false); submitAll(); }}>仍然提交</Button></div></section> : null}{create.isError ? <p className="practice-error" role="alert">{createErrorMessage(create.error)}</p> : null}{save.isError || submit.isError ? <p className="practice-error" role="alert">操作未完成，请稍后重试。</p> : null}</div></div> : null}

  </section></ExamPageShell>;
}

/**
 * The paper's chapters, and the way into one of them.
 *
 * This is what 章节练习 is for, so it is the whole of the page when no chapter is open: the real
 * chapter list, each chapter's real question count, and one action. Every number comes from the
 * question bank through the outline endpoint — there is no target, no percentage and no
 * "recommended" chapter, because the product has measured none of those and a learner cannot act
 * on a number nobody took.
 *
 * The four papers are NOT listed here. Which paper is open is stated once, in the header above,
 * and this page only chooses the chapter.
 */
function PracticeSelector({ moduleKey, outline, loading }: { moduleKey: string; outline?: components['schemas']['ExamChapterPracticeOutlineResponse']; loading: boolean }) {
  return <section className="practice-selector" aria-label="章节练习选择">
    <h2>选择章节</h2>
    {loading ? <Skeleton className="h-32 w-full" /> : null}
    {outline && outline.chapters.length === 0 ? <p className="practice-selector__empty">这门科目还没有章节练习题。</p> : null}
    {outline ? <ol>{outline.chapters.map((chapter) => <li key={chapter.chapter_code}>
      <a href={`/exam/cs408/practice?module=${moduleKey}&chapter=${chapter.chapter_code}`}>
        <span className="practice-selector__no">{String(chapter.chapter_no).padStart(2, '0')}</span>
        <strong>{chapterTitle(chapter.chapter_title, chapter.chapter_no)}</strong>
        <small>{chapter.question_count} 道题</small>
        <span className="practice-selector__go">开始练习</span>
      </a>
    </li>)}</ol> : null}
    {outline && outline.chapters.length ? <p className="practice-selector__total">共 {chapterTotal(outline)} 道章节练习题</p> : null}
  </section>;
}

/**
 * How many chapter questions the paper has, counted the way the chapters are.
 *
 * NOT `outline.total`: the server's total counts a question once per knowledge point it is
 * tagged with, so a question filed under two points is counted twice there. The chapter counts
 * are one per question, so the sum of them is the number a learner would get by adding up the
 * page — and the page must not disagree with itself.
 */
function chapterTotal(outline: components['schemas']['ExamChapterPracticeOutlineResponse']): number {
  return outline.chapters.reduce((sum, chapter) => sum + chapter.question_count, 0);
}

/**
 * The chapter's title without the seed's own numbering.
 *
 * Some modules' seeds title a chapter 「第1章 计算机系统概述」 and others just 「线性表」. The
 * row already states the number in its own column, so the prefix is dropped when it is THIS
 * chapter's own number — never a title that merely begins with something that looks like one,
 * and never so much that nothing is left.
 */
function chapterTitle(title: string, chapterNo: number): string {
  const stripped = title.replace(new RegExp(`^第\\s*${chapterNo}\\s*[章节]\\s*`), '').trim();
  return stripped || title;
}
