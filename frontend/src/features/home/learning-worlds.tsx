import { ArrowUpRight } from 'lucide-react';

const worlds = [
  { id: '01', title: '考研学习', english: 'TARGET / MILESTONE', description: '面向目标考试建立系统备考路径', summary: '11408 · 数学 · 英语 · 联考', action: '进入考研', motif: 'target' },
  { id: '02', title: '课程学习', english: 'KNOWLEDGE / STRUCTURE', description: '覆盖理工科基础与专业核心课程', summary: '数学物理 · 计算机 · 更多理工专业', action: '进入课程', motif: 'structure' },
  { id: '03', title: '编程学习', english: 'CODE / RUN / FEEDBACK', description: '从知识理解走向真实代码实践', summary: 'C · C++ · Java · Python', action: '开始编程', motif: 'runtime' },
] as const;

function Motif({ type }: { type: (typeof worlds)[number]['motif'] }) {
  if (type === 'target') return <svg viewBox="0 0 120 80" aria-hidden="true"><circle cx="31" cy="48" r="18" /><circle cx="31" cy="48" r="6" fill="currentColor" /><path d="M31 48 93 15M83 15h10v10" /></svg>;
  if (type === 'structure') return <svg viewBox="0 0 120 80" aria-hidden="true"><path d="M60 62V39M60 39 24 17M60 39 96 17" /><circle cx="60" cy="62" r="7" /><circle cx="60" cy="39" r="5" /><circle cx="24" cy="17" r="5" /><circle cx="96" cy="17" r="5" /></svg>;
  return <svg viewBox="0 0 120 80" aria-hidden="true"><path d="M16 19h47v42H16zM27 32h24M27 41h14M76 40h23M89 28l12 12-12 12" /><circle cx="105" cy="40" r="4" fill="currentColor" /></svg>;
}

export function LearningWorlds() {
  return <section id="learning-worlds" className="lab-index" aria-labelledby="worlds-title">
    <div className="lab-index__heading"><p>LEARNING INDEX / 03 PATHS</p><h2 id="worlds-title">选择你的学习方向</h2><span aria-hidden="true">↓</span></div>
    <div className="lab-index__rows">{worlds.map((world) => <a href="/#learning-worlds" className={`lab-index__row lab-index__row--${world.motif}`} key={world.id}>
      <span className="lab-index__number">{world.id}</span><div className="lab-index__identity"><p>{world.english}</p><h3>{world.title}</h3></div><Motif type={world.motif} />
      <div className="lab-index__description"><p>{world.description}</p><small>{world.summary}</small></div><span className="lab-index__action">{world.action}<ArrowUpRight className="size-4" aria-hidden="true" /></span>
    </a>)}</div>
  </section>;
}
