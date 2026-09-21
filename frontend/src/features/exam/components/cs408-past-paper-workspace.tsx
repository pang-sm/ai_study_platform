import { useState } from 'react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useCreatePastPaperAttempt, usePastPaperAttempt, usePastPaperIndex, usePastPaperQuestions, useSavePastPaperAnswers, useSubmitPastPaper } from '@/features/exam/api/past-paper';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { ExamPageShell } from './exam-page-shell';
import './cs408-past-paper-workspace.css';

type Question = components['schemas']['PastPaperQuestion'];
type Result = components['schemas']['PastPaperQuestionResult'];
type ViewMode = 'paper' | 'summary';
const noQuestions: Question[] = [];
const noResults: Result[] = [];
const questionKey = (question: Pick<Question, 'question_number'>) => String(question.question_number);

function PaperQuestion({ question, answer, submitted, onChange, result }: { question: Question; answer: string; submitted: boolean; onChange: (answer: string) => void; result?: Result }) {
  const id = `past-paper-${question.question_number}`;
  return <><fieldset className="past-paper-question" disabled={submitted}>
    <div className="past-paper-question__identity"><strong>第 {question.question_number} 题</strong><span>{question.question_type === 'choice' ? '选择题' : '简答题'} · {question.year} 年真题</span></div>
    <legend>{question.stem}</legend>
    {question.resources.map((resource, index) => <img key={resource.url} className="past-paper-question__figure" src={resolveApiResourceUrl(resource.url)} alt={`第 ${question.question_number} 题图示 ${index + 1}`} onError={(event) => { event.currentTarget.hidden = true; }} />)}
    {question.question_type === 'choice' ? <div className="past-paper-question__options">{Object.entries(question.options).map(([option, label]) => <label key={option} className={answer === option ? 'is-selected' : undefined}><input type="radio" name={id} value={option} checked={answer === option} onChange={() => onChange(option)} /><b>{option}</b><span>{label}</span></label>)}</div> : <><label htmlFor={id}>你的作答</label><textarea id={id} value={answer} onChange={(event) => onChange(event.target.value)} placeholder="写下你的思路与答案" rows={9} /></>}
  </fieldset>{result ? <ResultPanel result={result} /> : null}</>;
}

function ResultPanel({ result }: { result: Result }) {
  const analysis = result.analysis?.trim();
  if (result.judge === 'self_review') return <section className="past-paper-result past-paper-result--review"><h2>自行复盘</h2><p><span>你的作答</span>{result.user_answer || '未作答'}</p><p><span>参考答案</span>{result.standard_answer}</p>{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
  if (result.judge === 'ai_graded') return <section className="past-paper-result past-paper-result--review"><h2>评分结果</h2>{result.score !== null && result.full_score !== null ? <p><span>得分</span>{result.score} / {result.full_score}</p> : null}<p><span>你的作答</span>{result.user_answer || '未作答'}</p><p><span>参考答案</span>{result.standard_answer}</p>{result.feedback ? <p><span>反馈</span>{result.feedback}</p> : null}{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
  return <section className={`past-paper-result ${result.correct ? 'past-paper-result--correct' : 'past-paper-result--wrong'}`}><h2>{result.correct ? '回答正确' : '回答错误'}</h2><p><span>你的答案</span>{result.user_answer || '未作答'}</p><p><span>正确答案</span>{result.standard_answer}</p>{analysis ? <p><span>题目解析</span>{analysis}</p> : null}</section>;
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
  return <ExamPageShell activeItem="cs408" cs408Tab="past-papers" moduleKey={module?.key}><section className="past-paper" aria-labelledby="past-paper-title"><header className="past-paper__header"><p>CS408 / 历年试卷档案</p><h1 id="past-paper-title">{module?.name ?? '选择真题科目'}</h1><span>{year ? `${year} 年全国硕士研究生招生考试` : attemptId !== undefined ? '本次答卷记录' : '选择模块与真实年份试卷'}</span></header>
    {!module ? <ModuleIndex /> : null}
    {module && index.isPending ? <div className="past-paper__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-24 w-full" /></div> : null}
    {module && index.isError ? <section className="past-paper__state"><h2>真题档案暂时无法加载</h2><Button variant="secondary" onClick={() => void index.refetch()}>重试</Button></section> : null}
    {module && !year && index.data ? <YearIndex moduleKey={module.key} papers={index.data.papers} /> : null}
    {module && year && paper.isPending ? <div className="past-paper__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && year && (paper.isError || !paper.data) ? <section className="past-paper__state"><h2>该年份试卷暂时无法加载</h2><Button variant="secondary" onClick={() => void paper.refetch()}>重试</Button></section> : null}
    {/* An attempt alone is a complete entry point: the attempt carries its own year, so the
        desk renders from it without the paper index being addressed first. */}
    {module && !year && attemptId !== undefined && attempt.isPending ? <div className="past-paper__loading"><Skeleton className="h-10 w-48" /><Skeleton className="h-80 w-full" /></div> : null}
    {module && !year && attemptId !== undefined && attempt.isError ? <section className="past-paper__state"><h2>本次答卷暂时无法加载</h2><Button variant="secondary" onClick={() => void attempt.refetch()}>重试</Button></section> : null}
    {module && year && paper.data && questions.length === 0 ? <section className="past-paper__state"><h2>该年份暂无可用真题</h2><a href={`/exam/cs408/past-papers?module=${module.key}`}>返回真题索引</a></section> : null}
    {module && currentQuestion ? <div className="past-paper__desk">{activeView === 'paper' ? <nav className="past-paper__navigator" aria-label="试卷题目导航">{questions.map((question, position) => <button key={question.question_number} type="button" aria-current={position === current ? 'step' : undefined} className={displayed[questionKey(question)] ? 'is-answered' : undefined} onClick={() => setSelected(position)}>{String(question.question_number).padStart(2, '0')}</button>)}</nav> : null}<div className="past-paper__main">{activeView === 'summary' ? <section className="past-paper-summary"><h2>本次答卷</h2><p>已作答 {summary.answered} · 未作答 {summary.unanswered}</p><p>客观题答对 {summary.correct} · 客观题答错 {summary.incorrect} · 自行复盘 {summary.selfReview}{summary.aiGraded ? ` · 已评分 ${summary.aiGraded}` : ''}</p><Button variant="secondary" onClick={() => setView('paper')}>查看答题纸</Button></section> : <><PaperQuestion question={currentQuestion} answer={displayed[questionKey(currentQuestion)] ?? ''} submitted={submitted} onChange={(answer) => update(currentQuestion, answer)} result={byQuestion.get(currentQuestion.question_number)} /><div className="past-paper__actions"><div><Button variant="ghost" disabled={current === 0} onClick={() => setSelected(current - 1)}>上一题</Button><Button variant="ghost" disabled={current === questions.length - 1} onClick={() => setSelected(current + 1)}>下一题</Button></div><div>{submitted ? <Button variant="secondary" onClick={() => setView('summary')}>本次答卷</Button> : attemptId === undefined ? <Button disabled={create.isPending} onClick={start}>开始作答</Button> : <><Button variant="secondary" disabled={save.isPending} onClick={saveDraft}>保存答案</Button><Button disabled={submit.isPending} onClick={submitPaper}>提交答卷</Button></>}</div></div></>}</div></div> : null}
    {create.isError || save.isError || submit.isError ? <p className="past-paper__error" role="alert">操作未完成，请稍后重试。</p> : null}
  </section></ExamPageShell>;
}

function ModuleIndex() { return <section className="past-paper-index" aria-label="真题科目"><h2>选择科目</h2>{cs408Modules.map((item) => <a key={item.key} href={`/exam/cs408/past-papers?module=${item.key}`}><span>{item.number}</span><strong>{item.name}</strong><i aria-hidden="true">→</i></a>)}</section>; }
function YearIndex({ moduleKey, papers }: { moduleKey: string; papers: components['schemas']['PastPaperSummary'][] }) { return <section className="past-paper-index" aria-label="真实年份试卷"><h2>真实年份试卷</h2>{papers.length === 0 ? <p>当前暂无可用真题</p> : papers.map((paper) => <a key={paper.year} href={`/exam/cs408/past-papers?module=${moduleKey}&year=${paper.year}`}><span>{paper.year}</span><strong>全国硕士研究生招生考试 · CS408</strong><small>{paper.question_count} 道真题</small><i aria-hidden="true">→</i></a>)}</section>; }
