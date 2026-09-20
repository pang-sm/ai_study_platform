import { useEffect, useRef, useState } from 'react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useChapterPracticeAttempt, useChapterPracticeOutline, useChapterPracticeQuestions, useCreateChapterPracticeAttempt, useSaveChapterPracticeAnswers, useSubmitChapterPractice, type ChapterPracticeAttempt } from '@/features/exam/api/chapter-practice';
import { useQuestionExplain } from '@/features/exam/api/question-explain';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { ExamPageShell } from './exam-page-shell';
import './cs408-practice-workspace.css';

type Question = ChapterPracticeAttempt['questions'][number];
type SubmitResult = NonNullable<ChapterPracticeAttempt['results']>[number];
type PracticeViewMode = 'questions' | 'summary';
const emptyQuestions: Question[] = [];

function chapterLabel(chapter?: { chapter_no: number; chapter_title: string }, hasAttempt = false) {
  if (chapter) return `第 ${chapter.chapter_no} 章 · ${chapter.chapter_title}`;
  // An attempt is a complete entry point on its own: a `?attempt=` deep link opens an
  // existing session without its chapter ever being addressed, and telling that learner to
  // "choose a chapter first" would be describing a state they are not in.
  return hasAttempt ? '本次练习记录' : '选择章节后开始练习';
}

function QuestionBody({ question, answer, questionIndex, questionTotal, onChange, submitted }: { question: Question; answer: string; questionIndex: number; questionTotal: number; onChange: (answer: string) => void; submitted: boolean }) {
  if (question.question_type === 'big') {
    return <div className="practice-question practice-question--big"><QuestionIdentity index={questionIndex} total={questionTotal} chapter={question.chapter_name} /><p className="practice-question__type">简答题 · 自行复盘</p><h2>{question.stem}</h2><label className="practice-question__textarea-label" htmlFor={`answer-${question.id}`}>你的作答</label><textarea id={`answer-${question.id}`} value={answer} disabled={submitted} onChange={(event) => onChange(event.target.value)} placeholder="写下你的思路与答案" rows={9} /><p className="practice-question__hint">本题提交后可自行对照参考答案。</p></div>;
  }
  return <fieldset className="practice-question" disabled={submitted}><QuestionIdentity index={questionIndex} total={questionTotal} chapter={question.chapter_name} /><p className="practice-question__type">选择题 · {question.chapter_name}</p><legend>{question.stem}</legend><div className="practice-question__options">{Object.entries(question.options).map(([key, value]) => <label key={key} className={answer === key ? 'is-selected' : undefined}><input type="radio" name={`question-${question.id}`} value={key} checked={answer === key} onChange={() => onChange(key)} /><span><b>{key}</b>{value}</span></label>)}</div></fieldset>;
}

function sessionFacts(results: SubmitResult[]) { const answered = results.filter((r) => r.user_answer !== ''); const choices = answered.filter((r) => r.question_type === 'choice'); const correct = choices.filter((r) => r.correct === true); const incorrect = choices.filter((r) => r.correct === false); const selfReview = answered.filter((r) => r.question_type === 'big' && r.judge === 'self_review'); return { answered: answered.length, unanswered: results.length - answered.length, correct: correct.length, incorrect: incorrect.length, selfReview: selfReview.length, retryIds: incorrect.map((r) => r.question_id), denominator: choices.length }; }

function QuestionIdentity({ index, total, chapter }: { index: number; total: number; chapter: string }) {
  return <div className="practice-question__identity"><strong>{String(index).padStart(2, '0')}</strong><span>第 {index} / {total} 题</span><small>{chapter}</small></div>;
}

function ResultMark({ result, onExplain, explainState }: { result?: SubmitResult; onExplain: () => void; explainState: { loading: boolean; analysis?: string; error?: string } }) {
  if (!result) return null;
  const staticAnalysis = result.analysis.trim();
  if (result.question_type === 'big') {
    return <section className="practice-result practice-result--review" aria-labelledby="self-review-title">
      <h2 id="self-review-title">自行复盘</h2>
      <div className="practice-result__answer"><span>你的作答</span><p>{result.user_answer || '未作答'}</p></div>
      <div className="practice-result__answer"><span>参考答案</span><p>{result.standard_answer}</p></div>
      {staticAnalysis ? <StaticAnalysis analysis={staticAnalysis} /> : null}
      <ExplainBlock onExplain={onExplain} state={explainState} />
    </section>;
  }
  const unanswered = result.correct === null || result.user_answer === '';
  const verdict = unanswered ? '未作答' : result.correct ? '回答正确' : '回答错误';
  return <section className={`practice-result ${unanswered ? 'practice-result--review' : result.correct ? 'practice-result--correct' : 'practice-result--wrong'}`} aria-labelledby="grading-title">
    <span>判定</span><strong id="grading-title">{verdict}</strong>
    <small>你的答案：{result.user_answer || '未作答'}</small><small>正确答案：{result.standard_answer}</small>
    {staticAnalysis ? <StaticAnalysis analysis={staticAnalysis} /> : null}
    <ExplainBlock onExplain={onExplain} state={explainState} />
  </section>;
}

function StaticAnalysis({ analysis }: { analysis: string }) {
  return <section className="practice-result__analysis" aria-labelledby="static-analysis-title"><h2 id="static-analysis-title">题目解析</h2><p>{analysis}</p></section>;
}

function ExplainBlock({ onExplain, state }: { onExplain: () => void; state: { loading: boolean; analysis?: string; error?: string } }) {
  return <section className="practice-result__ai" aria-labelledby="ai-explain-title"><h2 id="ai-explain-title">AI 讲解</h2>
    {state.analysis ? <p>{state.analysis}</p> : null}
    {state.error ? <p role="alert">{state.error}</p> : null}
    {!state.analysis ? <Button variant="secondary" disabled={state.loading} onClick={onExplain}>{state.loading ? '正在生成讲解' : state.error ? '重新生成讲解' : 'AI 讲解'}</Button> : null}
    {state.loading ? <p className="practice-result__ai-status" role="status" aria-live="polite">正在生成讲解</p> : null}
  </section>;
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

export function Cs408PracticeWorkspace({ moduleKey, chapterCode, attemptId: initialAttemptId, onAttemptChange }: { moduleKey?: string; chapterCode?: string; attemptId?: number; onAttemptChange?: (attemptId: number) => void }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  const outline = useChapterPracticeOutline(module?.key ?? '');
  const questionsQuery = useChapterPracticeQuestions(module?.key ?? '', chapterCode ?? '');
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
  const [explanations, setExplanations] = useState<Record<string, { analysis?: string; error?: string }>>({});
  const [explainingKey, setExplainingKey] = useState<string>();
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
  const start = () => create.mutate({ moduleKey: module!.key, questionIds: chapterQuestionIds }, { onSuccess: (response) => { setCreatedAttemptQuestionIds(chapterQuestionIds); setViewMode('questions'); setLocalAttemptId(response.attempt_id); onAttemptChange?.(response.attempt_id); } });
  const saveCurrent = () => { if (attemptId !== undefined) save.mutate({ moduleKey: module!.key, attemptId, answers: reconciledAnswers }); };
  const submitAll = () => { if (attemptId !== undefined) submit.mutate({ moduleKey: module!.key, attemptId, answers: reconciledAnswers }, { onSuccess: (response) => { setResultByQuestionId(Object.fromEntries(response.results.map((result) => [result.question_id, result]))); setViewMode('summary'); } }); };
  const requestSubmit = () => { const unanswered = questions.filter((question) => !(reconciledAnswers[String(question.id)] ?? '').trim()).length; if (unanswered) setConfirmSubmit(true); else submitAll(); };
  const dismissConfirmation = () => { submitControlRef.current?.focus(); setConfirmSubmit(false); };
  const retry = (ids: number[]) => create.mutate({ moduleKey: module!.key, questionIds: ids }, { onSuccess: (response) => { setResultByQuestionId({}); setAnswers({}); setCreatedAttemptQuestionIds(ids); setCurrentIndex(0); setViewMode('questions'); setLocalAttemptId(response.attempt_id); onAttemptChange?.(response.attempt_id); } });
  const explainKey = currentQuestion && attemptId !== undefined ? `${attemptId}:${currentQuestion.id}` : undefined;
  const explainCurrent = () => {
    if (!currentQuestion || !module || attemptId === undefined) return;
    const result = authoritativeResultByQuestionId[currentQuestion.id];
    if (!result) return;
    const key = `${attemptId}:${currentQuestion.id}`;
    setExplainingKey(key);
    setExplanations((current) => ({ ...current, [key]: {} }));
    explain.mutate({ moduleKey: module.key, input: { stem: result.stem, options: result.options, standard_answer: result.standard_answer, user_answer: result.user_answer, question_type: result.question_type } }, {
      onSuccess: (response) => setExplanations((current) => ({ ...current, [key]: { analysis: response.analysis } })),
      onError: (error) => setExplanations((current) => ({ ...current, [key]: { error: explainErrorMessage(error) } })),
      onSettled: () => setExplainingKey((current) => current === key ? undefined : current),
    });
  };

  return <ExamPageShell activeItem="cs408"><section className="cs408-practice" aria-labelledby="practice-title"><header className="cs408-practice__header"><p>CS408 / 章节练习</p><h1 id="practice-title">{module ? module.name : '选择学习模块'}</h1><span>{chapterLabel(selectedChapter, attemptId !== undefined)}</span></header>
    {(!module || !chapterCode) && attemptId === undefined ? <PracticeSelector moduleKey={module?.key} outline={outline.data} loading={outline.isPending} /> : null}
    {module && chapterCode && attemptId === undefined && questionsQuery.isPending ? <div className="cs408-practice__loading"><Skeleton className="h-9 w-40" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && chapterCode && attemptId === undefined && (questionsQuery.isError || !questionsQuery.data) ? <section className="cs408-practice__state"><h2>章节练习暂时无法加载</h2><Button variant="secondary" onClick={() => void questionsQuery.refetch()}>重试</Button></section> : null}
    {module && chapterCode && attemptId === undefined && questionsQuery.data && questions.length === 0 ? <section className="cs408-practice__state"><h2>本章节暂无可用练习题</h2><a href={`/exam/cs408/practice?module=${module.key}`}>返回章节选择</a></section> : null}
    {currentQuestion ? <div className="cs408-practice__desk">{activeViewMode === 'questions' ? <nav className="practice-navigator" aria-label="题目导航"><p>本次 {questions.length} 题</p><div>{questions.map((question, index) => <button key={question.id} type="button" aria-current={index === currentIndex ? 'step' : undefined} aria-label={`第 ${index + 1} 题`} className={displayedAnswers[String(question.id)] ? 'is-answered' : undefined} onClick={() => { setViewMode('questions'); setCurrentIndex(index); }}>{String(index + 1).padStart(2, '0')}</button>)}</div></nav> : null}<div className="practice-main">{activeViewMode === 'summary' ? <section className="practice-summary"><h2>本次练习完成</h2><div className="practice-summary__facts"><p>共 {authoritativeResults.length} 题</p><p>已作答 {facts.answered} · 答对 {facts.correct} · 答错 {facts.incorrect} · 自行复盘 {facts.selfReview} · 未作答 {facts.unanswered}</p><p>{facts.denominator ? `自动判分题正确率 ${Math.round(facts.correct / facts.denominator * 100)}%` : '本次没有自动判分题'}</p></div><div className="practice-summary__actions"><Button variant="secondary" onClick={() => setViewMode('questions')}>查看本次题目</Button>{facts.retryIds.length ? <Button onClick={() => retry(facts.retryIds)}>重练本次错题</Button> : null}<Button variant="secondary" onClick={() => retry(chapterQuestionIds)}>再做一遍本章</Button>{facts.incorrect > 0 ? <a href={`/exam/cs408/wrong?module=${module?.key}&status=active`}>去错题本订正</a> : null}<a href={`/exam/cs408/practice?module=${module?.key}`}>返回章节</a></div></section> : <><QuestionBody question={currentQuestion} questionIndex={currentIndex + 1} questionTotal={questions.length} answer={displayedAnswers[String(currentQuestion.id)] ?? ''} submitted={submitted} onChange={(answer) => updateAnswer(currentQuestion.id, answer)} /><ResultMark result={authoritativeResultByQuestionId[currentQuestion.id]} onExplain={explainCurrent} explainState={{ loading: explainingKey === explainKey, ...explanations[explainKey ?? ''] }} /></>}{activeViewMode === 'questions' ? <div className="practice-main__actions"><div>{currentIndex > 0 ? <Button variant="ghost" onClick={() => setCurrentIndex((index) => index - 1)}>上一题</Button> : null}{currentIndex < questions.length - 1 ? <Button variant="ghost" onClick={() => setCurrentIndex((index) => index + 1)}>下一题</Button> : null}</div><div>{submitted ? <Button variant="secondary" onClick={() => setViewMode('summary')}>本次练习总结</Button> : null}{attemptId === undefined ? <Button disabled={create.isPending} onClick={start}>开始本章练习</Button> : submitted ? null : <><Button variant="secondary" disabled={save.isPending} onClick={saveCurrent}>保存答案</Button><Button ref={submitControlRef} disabled={submit.isPending} onClick={requestSubmit}>提交本章答案</Button></>}</div></div> : null}{confirmSubmit ? <section ref={confirmationRef} className="practice-confirm" role="alertdialog" aria-label="未完成提交确认"><h2>还有 {questions.filter((question) => !(reconciledAnswers[String(question.id)] ?? '').trim()).length} 题未作答</h2><p>仍然提交本次练习吗？</p><div><Button ref={continuePracticeRef} variant="secondary" onClick={dismissConfirmation}>继续作答</Button><Button onClick={() => { setConfirmSubmit(false); submitAll(); }}>仍然提交</Button></div></section> : null}{create.isError || save.isError || submit.isError ? <p className="practice-error" role="alert">操作未完成，请稍后重试。</p> : null}</div></div> : null}
  </section></ExamPageShell>;
}

function PracticeSelector({ moduleKey, outline, loading }: { moduleKey?: string; outline?: components['schemas']['ExamChapterPracticeOutlineResponse']; loading: boolean }) {
  return <section className="practice-selector" aria-label="章节练习选择"><h2>{moduleKey ? '章节目录' : '模块目录'}</h2>{!moduleKey ? <div className="practice-selector__modules">{cs408Modules.map((entry, index) => <a key={entry.key} href={`/exam/cs408/practice?module=${entry.key}`}><span>{String(index + 1).padStart(2, '0')}</span><strong>{entry.name}</strong><i aria-hidden="true">→</i></a>)}</div> : null}{moduleKey && loading ? <Skeleton className="h-32 w-full" /> : null}{moduleKey && outline ? <ol>{outline.chapters.map((chapter) => <li key={chapter.chapter_code}><a href={`/exam/cs408/practice?module=${moduleKey}&chapter=${chapter.chapter_code}`}><span>第 {chapter.chapter_no} 章</span><strong>{chapter.chapter_title}</strong><small>{chapter.question_count} 道题</small></a></li>)}</ol> : null}</section>;
}
