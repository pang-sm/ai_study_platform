import { ArrowDownRight } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { LearningWorlds } from './learning-worlds';
import './home-page.css';
import { VirtualMemoryVisual } from './virtual-memory-visual';

export interface HomePageProps { hasCurrentLearning?: boolean }

export function HomePage({ hasCurrentLearning = true }: HomePageProps) {
  const context = hasCurrentLearning
    ? '继续上次学习 / 操作系统 · 存储管理'
    : '知识示例 / 操作系统';
  const action = hasCurrentLearning ? '继续学习' : '开始学习';

  return (
    <div className="lab-page">
      <section className="lab-hero" aria-labelledby="open-question">
        <div className="lab-hero__rule lab-hero__rule--vertical" aria-hidden="true" />
        <div className="lab-hero__rule lab-hero__rule--horizontal" aria-hidden="true" />
        <div className="lab-hero__index" aria-label="首页学习问题">01<span>/ 04</span></div>
        <p className="lab-hero__context">{context}</p>
        <p className="lab-hero__discipline">OPERATING SYSTEMS<br />MEMORY MAPPING</p>
        <div className="lab-hero__title-wrap">
          <h1 id="open-question" className="lab-hero__title"><span>一个虚拟地址，</span><span>是怎样找到</span><span>物理内存中的</span><span>位置的？</span></h1>
          <p className="lab-hero__explanation">从页号、页表到物理帧，一步一步看懂虚拟内存映射。</p>
        </div>
        <VirtualMemoryVisual />
        <div className="lab-hero__action-area">
          <Link className="lab-hero__action" to="/exam/11408/operating-system/workspace"><span>{action}</span><ArrowDownRight aria-hidden="true" className="size-5" /></Link>
          {hasCurrentLearning && <p className="lab-hero__next">下一步：页面置换算法</p>}
        </div>
        <p className="lab-hero__coordinate">MEM / 02.05<br />VIRTUAL → PHYSICAL</p>
      </section>
      <LearningWorlds />
      <footer className="lab-footer"><p>智学平台 / 把复杂知识，一步一步学明白。</p><p>© 2026 ZHIXUE LEARNING LAB</p></footer>
    </div>
  );
}
