import { useState } from 'react';

const mappings = [2, 0, 5, 3] as const;

export function VirtualMemoryVisual() {
  const [selectedPage, setSelectedPage] = useState(2);
  const mappedFrame = mappings[selectedPage] ?? 0;
  const sourceY = 92 + selectedPage * 38;
  const targetY = 128 + mappedFrame * 28;
  const route = `M 80 ${sourceY} H 312 V ${244 + selectedPage * 22} H 555 V ${targetY} H 742`;

  return <section className="lab-mapping" aria-labelledby="memory-visual-title">
    <h2 id="memory-visual-title" className="sr-only">虚拟内存映射交互图</h2>
    <p className="lab-mapping__instruction">选择页号，追踪一次真实的内存映射</p>
    <div className="lab-mapping__address"><p>VIRTUAL ADDRESS</p><div><strong>p = {selectedPage}</strong><span>OFFSET / 0x3F</span></div></div>
    <div className="lab-mapping__selector" aria-label="虚拟页坐标选择器">
      {mappings.map((_, page) => <button key={page} type="button" aria-label={`选择虚拟页 ${page}`} aria-pressed={selectedPage === page} onClick={() => setSelectedPage(page)}><span>0{page}</span><i aria-hidden="true" /></button>)}
    </div>
    <svg className="lab-mapping__route" viewBox="0 0 900 430" preserveAspectRatio="none" aria-hidden="true">
      <path className="lab-mapping__route-ghost" d="M 80 92 H 312 V 244 H 555 V 128 H 742" />
      <path className="lab-mapping__route-active" d={route} />
      <circle cx="80" cy={sourceY} r="8" className="lab-mapping__source" />
      <circle cx="742" cy={targetY} r="9" className="lab-mapping__target" />
    </svg>
    <div className="lab-mapping__table" aria-label="页表"><p>PAGE TABLE</p>{mappings.map((frame, page) => <div key={page} className={selectedPage === page ? 'is-selected' : ''}><span>PAGE {String(page).padStart(2, '0')}</span><b>FRAME {String(frame).padStart(2, '0')}</b></div>)}</div>
    <div className="lab-mapping__frame" aria-label={`当前物理帧 ${mappedFrame}`}><p>PHYSICAL FRAME</p><strong>{String(mappedFrame).padStart(2, '0')}</strong><span>OFFSET REMAINS<br />UNCHANGED</span></div>
    <p className="lab-mapping__state" aria-live="polite">PAGE {String(selectedPage).padStart(2, '0')} → TABLE ROW {String(selectedPage).padStart(2, '0')} → FRAME {String(mappedFrame).padStart(2, '0')}</p>
  </section>;
}
