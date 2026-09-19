import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useExamStudyPlan, useUpdateExamKnowledgeItem } from '@/features/exam/api/study-plan';
import { knowledgeStatusLabel, progressStatusLabel } from '@/features/exam/view-models/status-labels';
import { ExamPageShell } from './exam-page-shell';
import './cs408-knowledge-workspace.css';

type KnowledgeNode = components['schemas']['ExamStudyPlanKnowledgeNode'];
type StudyPlanChapter = components['schemas']['ExamStudyPlanChapter'];
type StudyPlanSection = components['schemas']['ExamStudyPlanSection'];
type KnowledgeStatus = components['schemas']['ExamKnowledgeItemUpdateResponse']['status'];

const statusChoices: Array<{ value: KnowledgeStatus; label: string }> = [
  { value: 'not_started', label: '未学习' }, { value: 'learning', label: '学习中' },
  { value: 'mastered', label: '已学习' }, { value: 'review_due', label: '待复习' },
];

function StatusMark({ status }: { status: KnowledgeStatus }) {
  return <span className={`knowledge-status knowledge-status--${status}`}><i aria-hidden="true" />{knowledgeStatusLabel(status)}</span>;
}

function Disclosure({ open, title, onClick, children }: { open: boolean; title: string; onClick: () => void; children: ReactNode }) {
  return <button type="button" className="knowledge-disclosure" onClick={onClick} aria-expanded={open} aria-label={`${open ? '收起' : '展开'} ${title}`}><ChevronDown aria-hidden="true" className={open ? 'is-open' : ''} />{children}</button>;
}

function Detail({ node, courseId, subjectKey, onStatusChanged }: { node: KnowledgeNode; courseId: string; subjectKey: string; onStatusChanged: (status: KnowledgeStatus) => void }) {
  const [editing, setEditing] = useState(false);
  const mutation = useUpdateExamKnowledgeItem(subjectKey);
  const isLeaf = node.is_leaf;
  const update = (status: KnowledgeStatus) => {
    mutation.mutate(
      { username: '', subject_key: subjectKey, course_id: courseId, knowledge_point_code: node.code, knowledge_point_title: node.title, status },
      { onSuccess: (response) => { onStatusChanged(response.status); setEditing(false); } },
    );
  };
  return <div className="knowledge-detail" aria-live="polite">
    <p className="knowledge-detail__eyebrow">当前知识点</p>
    <h2>{node.title}</h2>
    <dl><div><dt>知识编码</dt><dd>{node.code}</dd></div><div><dt>学习状态</dt><dd><StatusMark status={node.status} /></dd></div>
      {node.learned_at ? <div><dt>学习时间</dt><dd>{node.learned_at}</dd></div> : null}
      {node.review_due_at ? <div><dt>复习日期</dt><dd>{node.review_due_at}</dd></div> : null}
    </dl>
    {isLeaf ? <div className="knowledge-detail__action"><p>我的学习状态</p>{editing ? <div className="knowledge-status-picker" role="group" aria-label="选择学习状态">{statusChoices.map((choice) => <Button key={choice.value} size="sm" variant={choice.value === node.status ? 'primary' : 'secondary'} disabled={mutation.isPending} onClick={() => update(choice.value)}>{choice.label}</Button>)}</div> : <Button variant="secondary" onClick={() => setEditing(true)}>更新学习状态</Button>}{mutation.isError ? <p role="alert">更新失败，请稍后重试。</p> : null}</div> : <p className="knowledge-detail__hint">选择具体知识点后可更新学习状态。</p>}
  </div>;
}

function KnowledgeBranch({ node, depth, selectedCode, onSelect }: { node: KnowledgeNode; depth: number; selectedCode?: string; onSelect: (node: KnowledgeNode) => void }) {
  const [open, setOpen] = useState(false);
  const hasChildren = node.children.length > 0;
  const selected = selectedCode === node.code;
  return <li className={`knowledge-branch knowledge-branch--depth-${depth}`}>
    <div className={`knowledge-row ${selected ? 'is-selected' : ''}`}>
      {hasChildren ? <Disclosure open={open} title={node.title} onClick={() => setOpen((value) => !value)}><span>{node.title}</span></Disclosure> : <button type="button" className="knowledge-select" aria-current={selected ? 'true' : undefined} aria-label={`选择 ${node.title}`} onClick={() => onSelect(node)}>{node.title}</button>}
      <StatusMark status={node.status} />
      {hasChildren ? <button type="button" className="knowledge-row__inspect" aria-label={`查看 ${node.title}`} onClick={() => onSelect(node)}>查看</button> : null}
    </div>
    {hasChildren && open ? <ul className="knowledge-children">{node.children.map((child) => <KnowledgeBranch key={child.code} node={child} depth={depth + 1} selectedCode={selectedCode} onSelect={onSelect} />)}</ul> : null}
  </li>;
}

function Section({ section, selectedCode, onSelect }: { section: StudyPlanSection; selectedCode?: string; onSelect: (node: KnowledgeNode) => void }) {
  const [open, setOpen] = useState(false);
  return <li className="knowledge-section"><div className="knowledge-row knowledge-row--section"><Disclosure open={open} title={section.title} onClick={() => setOpen((value) => !value)}><span>{section.title}</span></Disclosure><span className="knowledge-progress-status">{progressStatusLabel(section.section_status)}</span></div>{open ? <ul className="knowledge-children">{section.children.map((node) => <KnowledgeBranch key={node.code} node={node} depth={0} selectedCode={selectedCode} onSelect={onSelect} />)}</ul> : null}</li>;
}

function Chapter({ chapter, selectedCode, onSelect, initiallyOpen }: { chapter: StudyPlanChapter; selectedCode?: string; onSelect: (node: KnowledgeNode) => void; initiallyOpen: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  const currentModule = new URLSearchParams(window.location.search).get('module') ?? 'data_structure';
  return <li className="knowledge-chapter" id={`chapter-${chapter.code}`}><div className="knowledge-chapter__heading"><span>{String(chapter.chapter_no).padStart(2, '0')}</span><Disclosure open={open} title={chapter.title} onClick={() => setOpen((value) => !value)}><strong>{chapter.title}</strong></Disclosure><a className="knowledge-chapter__practice" href={`/exam/cs408/practice?module=${currentModule}&chapter=${chapter.code}`}>章节练习</a><span className="knowledge-progress-status">{progressStatusLabel(chapter.chapter_status)}</span></div>{open ? <ul className="knowledge-sections">{chapter.children.map((section) => <Section key={section.code} section={section} selectedCode={selectedCode} onSelect={onSelect} />)}</ul> : null}</li>;
}

export function Cs408KnowledgeWorkspace({ moduleKey }: { moduleKey: string }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey) ?? cs408Modules[0];
  const query = useExamStudyPlan(module.key);
  const [selected, setSelected] = useState<KnowledgeNode>();
  return <ExamPageShell activeItem="cs408"><section className="cs408-knowledge" aria-labelledby="knowledge-title"><header className="cs408-knowledge__header"><p>CS408 / 知识脉络</p><h1 id="knowledge-title">{module.name}知识脉络</h1><div className="cs408-knowledge__modules" aria-label="CS408 模块">{cs408Modules.map((entry) => <a key={entry.key} href={`/exam/cs408/knowledge?module=${entry.key}`} aria-current={entry.key === module.key ? 'page' : undefined}>{entry.name}</a>)}</div></header>{query.isPending ? <div className="cs408-knowledge__loading"><Skeleton className="h-11 w-48" /><Skeleton className="h-72 w-full" /></div> : null}{query.isError || !query.data ? <section className="cs408-knowledge__error"><h2>知识脉络暂时无法加载</h2><p>请检查网络后重试。</p><Button variant="secondary" onClick={() => void query.refetch()}>重试</Button></section> : null}{query.data ? <div className="cs408-knowledge__grid"><section className="knowledge-outline" aria-label={`${module.name}知识目录`}><p className="knowledge-outline__summary">已学习 {query.data.stats.mastered} / {query.data.stats.total_knowledge_points} 个知识点</p><ol>{query.data.chapters.map((chapter, index) => <Chapter key={chapter.code} chapter={chapter} selectedCode={selected?.code} onSelect={setSelected} initiallyOpen={index === 0} />)}</ol></section>{selected ? <Detail node={selected} courseId={query.data.course_id} subjectKey={module.key} onStatusChanged={(status) => setSelected((current) => current ? { ...current, status } : current)} /> : <div className="knowledge-detail knowledge-detail--empty"><p>选择一个知识点</p><h2>从目录开始</h2><span>展开章节，查看具体知识点与当前学习状态。</span></div>}</div> : null}</section></ExamPageShell>;
}
