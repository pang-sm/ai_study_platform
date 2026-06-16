import { useEffect, useState, useCallback } from "react";

const API_BASE = "/api";
async function safeFetch(url, options = {}) {
  const c = new AbortController(); const t = setTimeout(() => c.abort(), options.timeout || 15000);
  try { const r = await fetch(url, { ...options, signal: c.signal }); const txt = await r.text();
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${txt.slice(0,200)}`);
    try { return JSON.parse(txt); } catch { throw new Error(`Non-JSON: ${txt.slice(0,200)}`); }
  } finally { clearTimeout(t); }
}

export default function ExamChapterPracticeSession({ subjectKey, attemptId, user, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [closeHint, setCloseHint] = useState("");
  const [attempt, setAttempt] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(0);

  useEffect(() => { document.body.classList.add("exam-attempt-body"); return () => document.body.classList.remove("exam-attempt-body"); }, []);

  useEffect(() => {
    if (!attemptId) return; setLoading(true);
    safeFetch(`${API_BASE}/exam/11408/${subjectKey}/chapter-practice/attempts/${attemptId}?username=${user?.username||""}`)
      .then(d => { setAttempt(d.attempt); setQuestions(d.questions||[]); if(d.saved_answers)setAnswers(d.saved_answers); if(d.attempt?.status==="submitted"){setSubmitted(true); loadResult();} })
      .catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [attemptId]);

  const loadResult = async () => {
    try {
      const d = await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/chapter-practice/attempts/${attemptId}?username=${user?.username||""}`);
      if (d.attempt?.status === "submitted") {
        // Re-submit to get results (the GET endpoint doesn't return results)
        const r = await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/chapter-practice/attempts/${attemptId}/submit`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:user?.username,answers:d.saved_answers||answers})});
        setResult(r); setSubmitted(true);
      }
    } catch {}
  };

  // Auto-save every 10 seconds
  const saveDraft = useCallback(async () => {
    if(!attemptId||submitted)return;
    try{await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/chapter-practice/attempts/${attemptId}/answers`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answers}),timeout:10000});}catch{}
  },[attemptId,answers,submitted]);
  useEffect(() => { if(!attemptId||submitted)return; const t=setInterval(saveDraft,10000); return ()=>clearInterval(t); },[attemptId,submitted,saveDraft]);

  const handleAnswer = (qid, val) => setAnswers(p=>({...p,[qid]:val}));
  const unanswered = questions.filter(q => { const a = answers[q.id]; return !a||!String(a).trim(); }).length;

  const handleSubmit = async () => {
    if(questions.length===0){setError("无题目");return}
    if(unanswered>0&&!window.confirm(`还有 ${unanswered} 题未答，确定提交？`))return;
    setSubmitting(true);
    try{
      const data = await safeFetch(`${API_BASE}/exam/11408/${subjectKey}/chapter-practice/attempts/${attemptId}/submit`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:user?.username,answers}),timeout:30000});
      setResult(data); setSubmitted(true);
    }catch(e){setError(e.message)}finally{setSubmitting(false)}
  };

  const goTo = (idx) => { if (idx >= 0 && idx < questions.length) setCurrentIdx(idx); };
  const q = questions[currentIdx];

  if(loading)return<div className="attempt-page"><div className="attempt-page-loading">加载中...</div></div>;
  if(error&&!questions.length)return<div className="attempt-page"><div className="attempt-page-error">{error}</div></div>;

  // Result view
  if(submitted&&result){
    const choiceResults = (result.results||[]).filter(r=>r.question_type!=="big");
    const bigResults = (result.results||[]).filter(r=>r.question_type==="big");
    const cCorrect = choiceResults.filter(r=>r.correct).length;
    const cTotal = choiceResults.length;
    return (<div className="attempt-page">
      <header className="attempt-page-header">
        <div className="attempt-page-header-left">
          <button className="ghost-button compact" onClick={()=>{window.close();setTimeout(()=>{if(!window.closed)setCloseHint("请手动关闭当前标签页。")},300);}}>← 关闭</button>
          <div><h2>章节专项练习 · 结果</h2><p>{attempt?.knowledge_point_path||""} · {result.total_questions} 题</p></div>
        </div>
      </header>
      <div className="attempt-page-body">
        <div className="attempt-page-result">
          <div className="practice-stats-grid" style={{marginBottom:16}}>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.total_questions}</div><div className="practice-stat-card-label">总题数</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.correct_count}</div><div className="practice-stat-card-label">正确</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">❌</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.wrong_count}</div><div className="practice-stat-card-label">错误</div></div></div>
            <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.accuracy}%</div><div className="practice-stat-card-label">正确率</div></div></div>
            {result.big_count>0&&<div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon">📝</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{result.big_count}</div><div className="practice-stat-card-label">大题(自评)</div></div></div>}
          </div>
          {result.mistake_saved_count > 0 ? (
            <div style={{marginBottom:12,padding:"8px 14px",background:"#fef3c7",borderRadius:8,fontSize:"0.85rem",color:"#92400e"}}>
              📋 已将 <strong>{result.mistake_saved_count}</strong> 道错题收入错题本
            </div>
          ) : (
            <div style={{marginBottom:12,padding:"8px 14px",background:"#f0fdf4",borderRadius:8,fontSize:"0.85rem",color:"#166534"}}>
              ✅ 本次没有新增错题
            </div>
          )}
          <div style={{marginBottom:12,padding:"8px 14px",background:"#ede9fe",borderRadius:8,fontSize:"0.82rem",color:"#5b21b6"}}>
            ✅ 已完成练习，题目已标记为"已做过"
          </div>
          {closeHint&&<div className="km-inline-message" style={{marginBottom:8}}>{closeHint}</div>}
          <div className="past-paper-result-actions" style={{marginBottom:16}}>
            <button className="ghost-button compact" onClick={onBack}>返回章节练习</button>
          </div>
          <div className="past-paper-question-list">
            {(result.results||[]).map((r,i)=>(
              <div key={r.question_id} className={`past-paper-question-card ${r.judge==="self_review"?"past-paper-q-self-review":(r.correct?"past-paper-q-correct":"past-paper-q-wrong")}`}>
                <div className="past-paper-question-meta">
                  <span className="past-paper-q-number">第 {i+1} 题</span>
                  <span className="past-paper-q-type">{r.question_type==="big"?"大题":(r.question_type||"选择题")}</span>
                  {r.judge==="self_review"
                    ? <span className="past-paper-q-result-tag" style={{background:"#fef3c7",color:"#92400e"}}>自行对照</span>
                    : <span className={`past-paper-q-result-tag ${r.correct?"past-paper-q-result-tag--correct":"past-paper-q-result-tag--wrong"}`}>{r.correct?"正确":"错误"}</span>
                  }
                </div>
                {r.stem&&<div className="past-paper-q-content">{r.stem}</div>}
                {r.options&&Object.keys(r.options).length>0&&<div className="ai-question-options">{Object.entries(r.options).map(([k,v])=><div key={k}><strong>{k}.</strong> {v}</div>)}</div>}
                <div className="past-paper-q-answer-row"><span className="past-paper-q-label">你的答案：</span><span className={r.correct?"text-correct":(r.judge==="self_review"?"":"text-wrong")}>{r.user_answer||"未作答"}</span></div>
                <div className="past-paper-q-answer-row"><span className="past-paper-q-label">{r.judge==="self_review"?"参考答案：":"标准答案："}</span><span>{r.standard_answer}</span></div>
                {r.judge==="self_review"&&<div className="past-paper-q-feedback" style={{background:"#fffbeb",borderLeft:"3px solid #f59e0b"}}><strong>💡 提示</strong><p>此题为综合题/大题，请自行对照参考答案判断对错。</p></div>}
                {r.analysis&&<div className="past-paper-q-feedback"><strong>解析</strong><p>{r.analysis}</p></div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>);
  }

  // Practice view
  return (<div className="attempt-page">
    <header className="attempt-page-header">
      <div className="attempt-page-header-left">
        <button className="ghost-button compact" onClick={()=>{window.close();setTimeout(()=>{if(!window.closed)setCloseHint("请手动关闭当前标签页。")},300);}}>← 关闭</button>
        <div><h2>章节专项练习</h2><p>{attempt?.knowledge_point_path||""} · {questions.length} 题</p></div>
      </div>
      <div className="attempt-page-header-right">
        <span style={{fontSize:"0.85rem",color:"#667085",marginRight:12}}>第 {currentIdx+1} / {questions.length} 题</span>
        <button className="ghost-button compact" onClick={saveDraft}>保存进度</button>
      </div>
    </header>

    <div className="attempt-page-body">
      {q ? (<>
        <div className="past-paper-question-card" style={{marginBottom:16}}>
          <div className="past-paper-question-meta">
            <span className="past-paper-q-number">第 {currentIdx+1} 题</span>
            <span className="past-paper-q-type">{q.question_type==="big"?"大题":"选择题"}</span>
            {q.knowledge_point_name&&<span className="past-paper-q-year">{q.knowledge_point_name}</span>}
          </div>
          {q.stem&&<div className="past-paper-q-content">{q.stem}</div>}
          {q.question_type==="big" ? (
            <div style={{marginTop:12}}>
              <textarea className="field" rows={4} style={{width:"100%",fontSize:"0.95rem"}}
                placeholder="请输入你的答案..."
                value={answers[q.id]||""}
                onChange={e=>handleAnswer(q.id,e.target.value)} />
            </div>
          ) : (
            <div className="past-paper-options">
              {["A","B","C","D"].map(opt=>{
                const t=q.options?.[opt]||"";
                return(<label key={opt} className={`past-paper-option ${answers[q.id]===opt?"past-paper-option--selected":""}`}>
                  <input type="radio" name={`q_${q.id}`} value={opt} checked={answers[q.id]===opt} onChange={()=>handleAnswer(q.id,opt)}/>
                  <span className="past-paper-opt-label">{opt}</span>
                  <span className="past-paper-opt-text">{t||`选项${opt}文本缺失`}</span>
                </label>);
              })}
            </div>
          )}
        </div>

        <div className="past-paper-nav-row" style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
          <button className="ghost-button" disabled={currentIdx===0} onClick={()=>goTo(currentIdx-1)}>← 上一题</button>
          <div style={{display:"flex",gap:4,flexWrap:"wrap",maxWidth:"60%",overflow:"hidden"}}>
            {questions.map((_,i)=>(
              <button key={i} onClick={()=>goTo(i)}
                style={{width:28,height:28,borderRadius:6,border:"1px solid #d0d5dd",background:i===currentIdx?"#7c3aed":(answers[questions[i]?.id]?"#ede9fe":"#fff"),color:i===currentIdx?"#fff":"#374151",fontSize:"0.75rem",cursor:"pointer",flexShrink:0}}
              >{i+1}</button>
            ))}
          </div>
          <button className="ghost-button" disabled={currentIdx===questions.length-1} onClick={()=>goTo(currentIdx+1)}>下一题 →</button>
        </div>
      </>) : null}

      {closeHint&&<div className="km-inline-message" style={{marginBottom:8}}>{closeHint}</div>}
      <div className="past-paper-submit-bar">
        <span className="past-paper-unanswered">{unanswered===0?"所有题目已作答":`还有 ${unanswered} 题未答`}</span>
        <button className="exam-past-paper-submit-btn" disabled={submitting||questions.length===0} onClick={handleSubmit}>{submitting?"提交中...":"提交练习"}</button>
      </div>
    </div>
  </div>);
}
