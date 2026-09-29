import { useRef, useState } from 'react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useCreatePastPaperAttempt, usePastPaperAttempt, usePastPaperIndex, usePastPaperQuestions, useSavePastPaperAnswers, useSubmitPastPaper } from '@/features/exam/api/past-paper';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { questionNeedsFigure } from '../view-models/question-figure';
import { optionLabel } from '../view-models/option-label';
import { useQuestionExplain } from '@/features/exam/api/question-explain';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { AiFeedback } from '@/components/learning/ai-feedback';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';
import './cs408-past-paper-workspace.css';

type Question = components['schemas']['PastPaperQuestion'];
type Result = components['schemas']['PastPaperQuestionResult'];
type ViewMode = 'paper' | 'summary';
const noQuestions: Question[] = [];
const noResults: Result[] = [];
const questionKey = (question: Pick<Question, 'question_number'>) => String(question.question_number);
function PaperQuestion({ question, answer, submitted, onChange, result, moduleKey }: { question: Question; answer: string; submitted: boolean; onChange: (answer: string) => void; result?: Result; moduleKey: string }) {
  const id = `past-paper-${question.question_number}`;
  // The stem is a paragraph, NOT a <legend>: a full-width legend is laid into the fieldset's own
  // top border, so the 2px rule ran through the question text. Same fix as chapter practice.
  const stemId = `past-paper-stem-${question.question_number}`;
  const figureRequired = questionNeedsFigure(question.stem);
  return <><fieldset className="past-paper-question" disabled={submitted} aria-labelledby={stemId}>
    {/* The score is the PAPER's, not a fixed 10: a 15-point 组成原理 question has to say so
        before the learner answers it. `full_score` comes from the canonical per-question table. */}
    <div className="past-paper-question__identity"><strong>第 {question.question_number} 题</strong><span>{question.question_type === 'choice' ? '选择题' : '综合应用题'} · 满分 {question.full_score} 分 · {question.year} 年真题</span></div>
    <p id={stemId} className="past-paper-question__stem">{question.stem}</p>
    {/* The paper's own figure is drawn ONLY when the question is about one. Most questions are
        stored twice — as text and as the scan they were read from — and the scan restates what
        is already on screen, so it is not drawn. A question that says 「如下图」 or 「如下表所示」
        depends on its figure and keeps it. Nothing is OCR'd, rewritten or invented either way. */}
    {figureRequired ? question.resources.map((resource, index) => <img key={resource.url} className="past-paper-question__figure" src={resolveApiResourceUrl(resource.url)} alt={`第 ${question.question_number} 题图示 ${index + 1}`} onError={(event) => { event.currentTarget.hidden = true; }} />) : null}
    {question.question_type === 'choice' ? <div className="past-paper-question__options" role="radiogroup" aria-labelledby={stemId}>{Object.entries(question.options).map(([option, label]) => <label key={option} className={answer === option ? 'is-selected' : undefined}><input type="radio" name={id} value={option} checked={answer === option} onChange={() => onChange(option)} /><b>{option}</b><span>{optionLabel(option, label)}</span></label>)}</div> : <><label htmlFor={id}>你的作答</label><textarea id={id} value={answer} onChange={(event) => onChange(event.target.value)} placeholder="写下你的思路与答案" rows={9} /></>}
  </fieldset>{result ? <><ResultPanel result={result} /><PaperAiExplain question={question} result={result} moduleKey={moduleKey} /></> : null}</>;
}

function ResultPanel({ result }: { result: Result }) {
  const analysis = result.analysis?.trim();
  if (result.judge === 'self_review') return <section className="past-paper-result past-paper-result--review"><h2>自行复盘</h2><p><span>你的作答</span>{result.user_answer || '未作答'}</p><p><span>参考答案</span>{result.standard_answer}</p>{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
  if (result.judge === 'ai_graded') return <section className="past-paper-result past-paper-result--review"><h2>评分结果</h2>{result.score !== null && result.full_score !== null ? <p><span>得分</span>{result.score} / {result.full_score}</p> : null}<p><span>你的作答</span>{result.user_answer || '未作答'}</p><p><span>参考答案</span>{result.standard_answer}</p>{result.feedback ? <p><span>反馈</span>{result.feedback}</p> : null}{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
  return <section className={`past-paper-result ${result.correct ? 'past-paper-result--correct' : 'past-paper-result--wrong'}`}><h2>{result.correct ? '回答正确' : '回答错误'}</h2><p><span>你的答案</span>{result.user_answer || '未作答'}</p><p><span>正确答案</span>{result.standard_answer}</p>{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
}

/**
 * The AI explanation for one past-paper question, asked for rather than shown by default.
 *
 * 题目解析 is the paper's own text and it costs nothing; this is a model call against the
 * learner's own AI 额度, and a learner who does not want it is never charged for it. It is
 * answer-blind on purpose: the question is sent as the prompt material, so the analysis is of
 * the QUESTION and not a re-verdict on whether the learner got it right.
 *
 * The follow-ups continue in the product's one conversation surface, scoped to this exam subject.
 */
function PaperAiExplain({ question, result, moduleKey }: { question: Question; result: Result; moduleKey: string }) {
  const explain = useQuestionExplain();
  const [analysis, setAnalysis] = useState<string>();
  const [requestId, setRequestId] = useState<string>();
  const [error, setError] = useState<string>();

  const run = () => {
    setError(undefined);
    explain.mutate(
      { moduleKey, input: { stem: question.stem, options: question.options ?? {}, standard_answer: result.standard_answer, user_answer: result.user_answer, question_type: question.question_type } },
      {
        onSuccess: (data) => { setAnalysis(data.analysis); setRequestId(data.request_id); },
        onError: (value) => {
          if (value instanceof ApiRequestError && value.status >= 500) setError('AI 讲解暂时不可用。');
          else if (value instanceof ApiRequestError && value.status === 403) setError('当前无法使用 AI 讲解。');
          else if (value instanceof ApiRequestError && value.status === 429) setError('AI 讲解额度暂不可用。');
          else setError('AI 讲解暂时不可用。');
        },
      },
    );
  };

  return <section className="past-paper-question__ai" aria-labelledby={`past-paper-ai-${question.question_number}`}>
    <h3 id={`past-paper-ai-${question.question_number}`}>AI 讲解</h3>
    {analysis ? <p>{analysis}</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {!analysis ? <Button variant="secondary" disabled={explain.isPending} onClick={run}>{explain.isPending ? '正在生成讲解' : error ? '重新生成讲解' : 'AI 讲解这道题'}</Button> : null}
    {explain.isPending ? <p role="status" aria-live="polite">正在生成讲解</p> : null}
    {requestId ? <AiFeedback requestId={requestId} workflowId="exam_past_paper_ai_explain" /> : null}
    {analysis ? <div className="past-paper-question__followups">
      <p>继续追问</p>
      <ul>
        <li><a href={`/ai?context=exam:${moduleKey}`}>换一种方法讲</a></li>
        <li><a href={`/ai?context=exam:${moduleKey}`}>这道题考的是哪个知识点</a></li>
        <li><a href={`/ai?context=exam:${moduleKey}`}>给我一道类似的题</a></li>
      </ul>
    </div> : null}
  </section>;
}

function QuestionButtons({ questions, current, displayed, onSelect }: { questions: Question[]; current: number; displayed: Record<string, string>; onSelect: (position: number) => void }) {
  // The paper's OWN question number is the label, never the position: a 408 paper runs 1–11 then
  // 41–42, and a learner looking for 题 41 must be able to find the button that says 41.
  return <>{questions.map((question, position) => <button key={question.question_number} type="button" aria-current={position === current ? 'step' : undefined} className={displayed[questionKey(question)] ? 'is-answered' : undefined} onClick={() => onSelect(position)}>{String(question.question_number).padStart(2, '0')}</button>)}</>;
}

/**
 * The question strip, on a phone.
 *
 * The desktop strip is a permanent left column; at 390px there is no room for one, and a wide
 * bar of 42 numbers would either overflow the page or squeeze the question it is meant to
 * serve. So the phone gets the two things it actually needs and nothing else: which question is
 * open, and a way to reach any other one. Both live in one native disclosure that opens in the
 * flow of the page — it pushes the question down instead of covering it — and closes itself once
 * a question is chosen, so the learner lands on the question rather than on the picker.
 */
function QuestionNavDrawer({ questions, current, displayed, onSelect }: { questions: Question[]; current: number; displayed: Record<string, string>; onSelect: (position: number) => void }) {
  const drawer = useRef<HTMLDetailsElement>(null);
  return <details className="past-paper__nav-drawer" ref={drawer}>
    <summary><span className="past-paper__nav-drawer-position">第 {current + 1} / {questions.length} 题</span><span className="past-paper__nav-drawer-label">题号</span></summary>
    <nav className="past-paper__nav-drawer-list" aria-label="跳转到题目"><QuestionButtons questions={questions} current={current} displayed={displayed} onSelect={(position) => { onSelect(position); if (drawer.current) drawer.current.open = false; }} /></nav>
  </details>;
}

function facts(results: Result[]) { const answered = results.filter((result) => result.user_answer.trim()).length; const correct = results.filter((result) => result.correct === true).length; const incorrect = results.filter((result) => result.correct === false).length; const selfReview = results.filter((result) => result.judge === 'self_review').length; const aiGraded = results.filter((result) => result.judge === 'ai_graded').length; return { answered, correct, incorrect, selfReview, aiGraded, unanswered: results.length - answered }; }

export function Cs408PastPaperWorkspace({ moduleKey, year, attemptId: initialAttemptId, questionNumber, onAttemptChange }: { moduleKey?: string; year?: number; attemptId?: number; questionNumber?: number; onAttemptChange?: (attemptId: number) => void }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  const index = usePastPaperIndex(module?.key ?? '');
  const paper = usePastPaperQuestions(module?.key ?? '', year);
  const [localAttemptId, setLocalAttemptId] = useState<number>();
  const attemptId = initialAttemptId ?? localAttemptId;
  const attempt = usePastPaperAttempt(module?.key ?? '', attemptId);
  const create = useCreatePastPaperAttempt(); const save = useSavePastPaperAnswers(); const submit = useSubmitPastPaper();
  const [answers, setAnswers] = useState<Record<string, string>>({}); const [localResults, setLocalResults] = useState<Result[]>([]); const [selected, setSelected] = useState<number>(); const [view, setView] = useState<ViewMode>();
  const questions = attemptId !== undefined ? attempt.data?.questions ?? noQuestions : paper.data?.questions ?? noQuestions;
  // A `?question=` deep link opens the paper AT that question. It is matched on the
  // question's own public identity, never on its position, so the link stays correct if the
  // paper's question list ever changes order. A question number the paper does not contain
  // is left alone rather than clamped: landing on question 1 silently would look like the
  // link worked.
  //
  // Derived during render, not synced in an effect: an effect would cascade a second render
  // and would fight the learner the moment they navigate away from the linked question.
  const deepLinkIndex = questionNumber === undefined ? -1 : questions.findIndex((question) => question.question_number === questionNumber);
  const current = selected ?? (deepLinkIndex >= 0 ? deepLinkIndex : 0);
  const submitted = attempt.data?.attempt.status === 'submitted' || localResults.length > 0;
  const results = submitted ? (attempt.data?.results ?? localResults) : noResults;
  const byQuestion = new Map(results.map((result) => [result.question_number, result]));
  const persisted = attempt.data?.saved_answers ?? {}; const displayed = submitted ? Object.fromEntries(results.map((result) => [String(result.question_number), result.user_answer])) : { ...persisted, ...answers };
  const activeView = view ?? (submitted ? 'summary' : 'paper'); const currentQuestion = questions[current]; const summary = facts(results);
  const update = (question: Question, answer: string) => setAnswers((old) => ({ ...old, [questionKey(question)]: answer }));
  const start = () => { if (module && year) create.mutate({ moduleKey: module.key, year }, { onSuccess: (created) => { setLocalAttemptId(created.attempt_id); onAttemptChange?.(created.attempt_id); } }); };
  const saveDraft = () => { if (module && attemptId !== undefined) save.mutate({ moduleKey: module.key, attemptId, answers: displayed }); };
  const submitPaper = () => { if (module && attemptId !== undefined) submit.mutate({ moduleKey: module.key, attemptId, answers: displayed }, { onSuccess: (response) => { setLocalResults(response.results); setView('summary'); } }); };
  if (!module) {
    return <ExamPageShell cs408Tab="past-papers"><Cs408SubjectChooser to="/exam/cs408/past-papers" description="真题按四门课分别归档。先选一门，再进入它的真实年份试卷。" /></ExamPageShell>;
  }

  // The 真题 tab above already says which tool this is, so the body does not repeat it as a
  // title. What the body owes the learner is the one thing the tab cannot say: WHICH paper is
  // open. That is the year, and it is a line of context above the desk — not a headline.
  return <ExamPageShell cs408Tab="past-papers" moduleKey={module.key}><section className="past-paper" aria-labelledby="past-paper-title"><h1 id="past-paper-title" className="sr-only">真题</h1>{year ? <p className="past-paper__paper">{year} 年全国硕士研究生招生考试</p> : attemptId !== undefined ? <p className="past-paper__paper">本次答卷记录</p> : null}
    {index.isPending ? <div className="past-paper__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-24 w-full" /></div> : null}
    {module && index.isError ? <section className="past-paper__state"><h2>真题档案暂时无法加载</h2><Button variant="secondary" onClick={() => void index.refetch()}>重试</Button></section> : null}
    {module && !year && index.data ? <YearIndex moduleKey={module.key} papers={index.data.papers} /> : null}
    {module && year && paper.isPending ? <div className="past-paper__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && year && (paper.isError || !paper.data) ? <section className="past-paper__state"><h2>该年份试卷暂时无法加载</h2><Button variant="secondary" onClick={() => void paper.refetch()}>重试</Button></section> : null}
    {/* An attempt alone is a complete entry point: the attempt carries its own year, so the
        desk renders from it without the paper index being addressed first. */}
    {module && !year && attemptId !== undefined && attempt.isPending ? <div className="past-paper__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && !year && attemptId !== undefined && attempt.isError ? <section className="past-paper__state"><h2>本次答卷暂时无法加载</h2><Button variant="secondary" onClick={() => void attempt.refetch()}>重试</Button></section> : null}
    {module && year && paper.data && questions.length === 0 ? <section className="past-paper__state"><h2>该年份暂无可用真题</h2><a href={`/exam/cs408/past-papers?module=${module.key}`}>返回真题索引</a></section> : null}
    {module && currentQuestion ? <div className="past-paper__desk">{activeView === 'paper' ? <><nav className="past-paper__navigator" aria-label="试卷题目导航"><QuestionButtons questions={questions} current={current} displayed={displayed} onSelect={setSelected} /></nav><QuestionNavDrawer questions={questions} current={current} displayed={displayed} onSelect={setSelected} /></> : null}<div className="past-paper__main">{activeView === 'summary' ? <section className="past-paper-summary"><h2>本次答卷</h2><p>已作答 {summary.answered} · 未作答 {summary.unanswered}</p><p>客观题答对 {summary.correct} · 客观题答错 {summary.incorrect} · 自行复盘 {summary.selfReview}{summary.aiGraded ? ` · 已评分 ${summary.aiGraded}` : ''}</p><Button variant="secondary" onClick={() => setView('paper')}>查看答题纸</Button></section> : <><PaperQuestion moduleKey={module.key} question={currentQuestion} answer={displayed[questionKey(currentQuestion)] ?? ''} submitted={submitted} onChange={(answer) => update(currentQuestion, answer)} result={byQuestion.get(currentQuestion.question_number)} /><div className="past-paper__actions"><div><Button variant="ghost" disabled={current === 0} onClick={() => setSelected(current - 1)}>上一题</Button><Button variant="ghost" disabled={current === questions.length - 1} onClick={() => setSelected(current + 1)}>下一题</Button></div><div>{submitted ? <Button variant="secondary" onClick={() => setView('summary')}>本次答卷</Button> : attemptId === undefined ? <Button disabled={create.isPending} onClick={start}>开始作答</Button> : <><Button variant="secondary" disabled={save.isPending} onClick={saveDraft}>保存答案</Button><Button disabled={submit.isPending} onClick={submitPaper}>提交答卷</Button></>}</div></div></>}</div></div> : null}
    {create.isError || save.isError || submit.isError ? <p className="past-paper__error" role="alert">操作未完成，请稍后重试。</p> : null}
  </section></ExamPageShell>;
}

function YearIndex({ moduleKey, papers }: { moduleKey: string; papers: components['schemas']['PastPaperSummary'][] }) { return <section className="past-paper-index" aria-label="选择年份"><h2>选择年份</h2>{papers.length === 0 ? <p>当前暂无可用真题</p> : papers.map((paper) => <a key={paper.year} href={`/exam/cs408/past-papers?module=${moduleKey}&year=${paper.year}`}><span>{paper.year}</span><strong>全国硕士研究生招生考试 · CS408</strong><small>{paper.question_count} 道真题</small><i aria-hidden="true">→</i></a>)}</section>; }
