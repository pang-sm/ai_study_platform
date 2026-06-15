import { useEffect, useState, useCallback } from "react";

const API_BASE = "/api";
async function safeFetch(url, options = {}) {
  const c = new AbortController(); const t = setTimeout(() => c.abort(), options.timeout || 15000);
  try { const r = await fetch(url, { ...options, signal: c.signal }); const txt = await r.text();
    if (!r.ok) throw new Error(`接口 ${url} HTTP ${r.status}: ${txt.slice(0,200)}`);
    try { return JSON.parse(txt); } catch { throw new Error(`接口 ${url} 返回非JSON: ${txt.slice(0,200)}`); }
  } finally { clearTimeout(t); }
}

export default function ExamAIQuestionAttemptPage({ subjectKey, attemptId, user, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [closeHint, setCloseHint] = useState("");
  const [attempt, setAttempt] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { document.body.classList.add("exam-attempt-body"); return () => document.body.classList.remove("exam-attempt-body"); }, []);

  useEffect(() => {
    if (!attemptId) return; setLoading(true);
    safeFetch(`${API_BASE}/exam/11408/${subjectKey}/ai-questions/attempts/${attemptId}?username=${user?.username||""}`)
      .then(d => { setAttempt(d.attempt); setQuestions(d.questions||[]); if(d.saved_answers)setAnswers(d.saved_answers); if(d.attempt?.status==="submitted")setSubmitted(true); })
      .catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [attemptId]);

  const saveDraft = useCallback(async () => {
    if(!attemptId)return;
    try{await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/ai-questions/attempts/${attemptId}/answers`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers}),timeout:10000});}catch{}
  },[attemptId,answers]);
  useEffect(() => { if(!attemptId||submitted)return; const t=setInterval(saveDraft,10000); return ()=>clearInterval(t); },[attemptId,submitted,saveDraft]);

  const handleAnswer = (qid, val) => setAnswers(p=>({...p,[qid]:val}));
  const unanswered = questions.filter(q => { const a = answers[q.id]; return !a||!String(a).trim(); }).length;

  const handleSubmit = async () => {
    if(questions.length===0){setError("无题目");return}
    if(unanswered>0&&!window.confirm(`还有${unanswered}题未答，确定提交？`))return;
    setSubmitting(true);
    try{
      const data = await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/ai-questions/attempts/${attemptId}/submit`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:user?.username,answers}),timeout:30000});
      setResult(data); setSubmitted(true);
    }catch(e){setError(e.message)}finally{setSubmitting(false)}
  };

  if(loading)return<div className="attempt-page-loading">加载中...</div>;
  if(error&&!questions.length)return<div className="attempt-page-error">{error}</div>;

  return (<div className="attempt-page">
    <header className="attempt-page-header"><div className="attempt-page-header-left">
      <button className="ghost-button compact" onClick={()=>{window.close();setTimeout(()=>{if(!window.closed)setCloseHint("浏览器限制自动关闭，请手动关闭当前标签页。")},300);}}>← 关闭答题页</button>
      <div><h2>AI 题库练习</h2><p>{attempt?.knowledge_point_path||"综合出题"} · 第 1 次</p></div>
    </div><div className="attempt-page-header-right"><button className="ghost-button compact" onClick={saveDraft}>保存进度</button></div></header>

    {submitted&&result?(<div className="attempt-page-result"><h3>AI 题库练习结果</h3>
      <p style={{color:"#667085",marginBottom:12}}>{attempt?.knowledge_point_path||"综合出题"}</p>
      <div className="practice-stats-grid" style={{marginBottom:16}}>
        <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_questions}</div><div className="practice-stat-card-label">总题数</div></div></div>
        <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.correct_count}</div><div className="practice-stat-card-label">正确</div></div></div>
        <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">❌</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.wrong_count}</div><div className="practice-stat-card-label">错误</div></div></div>
        <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.accuracy}%</div><div className="practice-stat-card-label">正确率</div></div></div>
      </div>
      <div className="past-paper-result-actions"><button className="primary-button compact" onClick={()=>{setAnswers({});setSubmitted(false);setResult(null);}}>重新练习</button><button className="ghost-button compact" onClick={onBack}>返回 AI 题库</button></div>
      {result.results&&result.results.map((r,i)=>(<div key={r.question_id} className={`past-paper-question-card ${r.correct?"past-paper-q-correct":"past-paper-q-wrong"}`}><div className="past-paper-question-meta"><span className="past-paper-q-number">第 {i+1} 题</span><span className="past-paper-q-type">{r.question_type||"选择题"}</span><span className={`past-paper-q-result-tag ${r.correct?"past-paper-q-result-tag--correct":"past-paper-q-result-tag--wrong"}`}>{r.correct?"正确":"错误"}</span></div>{r.stem&&<div className="past-paper-q-content">{r.stem}</div>}{r.options&&Object.keys(r.options).length>0&&<div className="ai-question-options">{Object.entries(r.options).map(([k,v])=><div key={k}><strong>{k}.</strong> {v}</div>)}</div>}<div className="past-paper-q-answer-row"><span className="past-paper-q-label">你的答案：</span><span className={r.correct?"text-correct":"text-wrong"}>{r.user_answer||"未作答"}</span></div><div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{r.standard_answer}</span></div>{r.analysis&&<div className="past-paper-q-feedback"><strong>解析</strong><p>{r.analysis}</p></div>}</div>))}
    </div>):(<div className="attempt-page-body"><div className="past-paper-question-list">
      {questions.map((q,i)=>(<div key={q.id} className="past-paper-question-card"><div className="past-paper-question-meta"><span className="past-paper-q-number">第 {i+1} 题</span><span className="past-paper-q-type">选择题</span></div>{q.stem&&<div className="past-paper-q-content">{q.stem}</div>}<div className="past-paper-options">{["A","B","C","D"].map(opt=>{const t=q.options?.[opt]||"";return(<label key={opt} className={`past-paper-option ${answers[q.id]===opt?"past-paper-option--selected":""}`}><input type="radio" name={`q_${q.id}`} value={opt} checked={answers[q.id]===opt} onChange={()=>handleAnswer(q.id,opt)}/><span className="past-paper-opt-label">{opt}</span><span className="past-paper-opt-text">{t||`选项${opt}文本缺失`}</span></label>);})}</div></div>))}
    </div>{closeHint&&<div className="km-inline-message" style={{marginBottom:8}}>{closeHint}</div>}<div className="past-paper-submit-bar"><span className="past-paper-unanswered">{unanswered===0?"所有题目已作答":`还有 ${unanswered} 题未答`}</span><button className="exam-past-paper-submit-btn" disabled={submitting||questions.length===0} onClick={handleSubmit}>{submitting?"提交中...":"已答完"}</button></div></div>)}
  </div>);
}
