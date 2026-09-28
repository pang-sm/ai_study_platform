import { useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { ChevronDown } from 'lucide-react';
import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { searchValueOut } from '@/lib/router';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { useExamPlanEntitlement } from '@/features/exam/api/cs408-study-plan';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { normalizeApiError } from '@/features/exam/api/errors';
import { useExamStudyPlan, useUpdateExamKnowledgeItem } from '@/features/exam/api/study-plan';
import { tierLabel } from '@/features/membership/view-models/membership';
import { knowledgeStatusLabel, progressStatusLabel } from '@/features/exam/view-models/status-labels';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';
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
  // The node's CODE is not shown. It is an internal identity — and on this content it is often a
  // minted path (`_leaf:1.1.1.1`) that means nothing to a learner. It is still what the state
  // update sends and what the assistant is told, so hiding it changes nothing but the reading.
  //
  // The state is ONE block: what it is, and the one control that changes it. It used to be two —
  // 学习状态 in the facts list and 我的学习状态 under it — which stated the same fact twice and
  // left the learner to work out which of the two was the real one.
  return <div className="knowledge-detail" aria-live="polite">
    <p className="knowledge-detail__eyebrow">当前知识点</p>
    <h2>{node.title}</h2>
    <div className="knowledge-detail__state">
      <div className="knowledge-detail__state-row">
        <p className="knowledge-detail__state-label">学习状态</p>
        <StatusMark status={node.status} />
        {isLeaf ? (editing ? <div className="knowledge-status-picker" role="group" aria-label="选择学习状态">{statusChoices.map((choice) => <Button key={choice.value} size="sm" variant={choice.value === node.status ? 'primary' : 'secondary'} disabled={mutation.isPending} onClick={() => update(choice.value)}>{choice.label}</Button>)}</div> : <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>更新</Button>) : null}
      </div>
      {node.learned_at || node.review_due_at ? <p className="knowledge-detail__dates">{[node.learned_at ? `学习于 ${node.learned_at}` : null, node.review_due_at ? `复习日期 ${node.review_due_at}` : null].filter(Boolean).join(' · ')}</p> : null}
      {!isLeaf ? <p className="knowledge-detail__hint">选择具体知识点后可更新学习状态。</p> : null}
      {mutation.isError ? <p role="alert">更新失败，请稍后重试。</p> : null}
    </div>
    {/* The way out of this panel into the paper's own conversation, carrying the node the learner
        is looking at. It is a link, not a chat box: the conversation is a page of the paper, and
        this states the context it will arrive with rather than opening a second one here. No
        question is asked on the learner's behalf — the composer is empty. */}
    <div className="knowledge-detail__action"><p>AI 对话</p><Button asChild variant="secondary" size="sm"><Link to="/exam/cs408/ask" search={{ module: subjectKey, knowledge_point: searchValueOut(node.code), knowledge_point_title: node.title }}>围绕此知识点问 AI</Link></Button></div>
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
  // The section carries no practice link. 章节练习 is a first-level page of the paper, and a
  // link into it on every level of the tree was a second entry point for one destination —
  // the tree said "study this" and "practise this" in the same breath, at four depths. What
  // this page owns is the structure and the state of it; the state a section is in is stated
  // beside it, and a learner who wants questions goes to the page that has them.
  return <li className="knowledge-section"><div className="knowledge-row knowledge-row--section"><Disclosure open={open} title={section.title} onClick={() => setOpen((value) => !value)}><span>{section.title}</span></Disclosure><span className="knowledge-progress-status">{progressStatusLabel(section.section_status)}</span></div>{open ? <ul className="knowledge-children">{section.children.map((node) => <KnowledgeBranch key={node.code} node={node} depth={0} selectedCode={selectedCode} onSelect={onSelect} />)}</ul> : null}</li>;
}

function Chapter({ chapter, selectedCode, onSelect, initiallyOpen }: { chapter: StudyPlanChapter; selectedCode?: string; onSelect: (node: KnowledgeNode) => void; initiallyOpen: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  return <li className="knowledge-chapter" id={`chapter-${chapter.code}`}><div className="knowledge-chapter__heading"><span>{String(chapter.chapter_no).padStart(2, '0')}</span><Disclosure open={open} title={chapter.title} onClick={() => setOpen((value) => !value)}><strong>{chapter.title}</strong></Disclosure><span className="knowledge-progress-status">{progressStatusLabel(chapter.chapter_status)}</span></div>{open ? <ul className="knowledge-sections">{chapter.children.map((section) => <Section key={section.code} section={section} selectedCode={selectedCode} onSelect={onSelect} />)}</ul> : null}</li>;
}

export function Cs408KnowledgeWorkspace({ moduleKey }: { moduleKey?: string }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  if (!module) {
    return (
      <ExamPageShell cs408Tab="knowledge">
        <Cs408SubjectChooser
          to="/exam/cs408/knowledge"
          description="知识脉络按四门课分别组织。先选一门，再进入它的知识目录。"
        />
      </ExamPageShell>
    );
  }
  return <Cs408KnowledgeModule module={module} />;
}

/**
 * The page's one LOCKED state, and the only honest answer to a refused outline.
 *
 * 知识脉络 is gated by the same `learning_plan` entitlement 学习计划 is, so it is refused the
 * same way — and it used to be refused the WRONG way: a 403 was reported as 「请检查网络后重试」
 * with a 重试 button that could never succeed, because retrying does not change a tier. It names
 * the exact tier the learner has to reach and links to the page that owns that decision, which is
 * the same shape 学习计划 uses because it is literally the same entitlement.
 */
function LockedKnowledge({ requiredTier }: { requiredTier?: string }) {
  return <section className="cs408-knowledge__state">
    <h2>当前档位暂未开放知识脉络</h2>
    <p>{requiredTier ? <>知识脉络需要 {tierLabel(requiredTier)} 及以上档位，当前账号尚未开通。</> : <>该功能将在符合当前会员权益时开放。</>}</p>
    <Link to="/membership">查看会员档位与权益</Link>
  </section>;
}

function Cs408KnowledgeModule({ module }: { module: (typeof cs408Modules)[number] }) {
  const entitlement = useExamPlanEntitlement();
  // `features` is a MAPPING whose key set depends on the direction, so it is only safe to index
  // after a presence check — the generated type says so, and `data?.features[...]` would still
  // throw on a payload that carries `data` but no `features`.
  const planFeature = entitlement.data?.features?.['learning_plan'];
  const allowed = planFeature?.allowed === true;
  // The outline is only asked for once the gate is known OPEN. Calling it unconditionally on a
  // free account means a guaranteed 403 whose only visible effect was a fake network error.
  const query = useExamStudyPlan(module.key, allowed);
  const [selected, setSelected] = useState<KnowledgeNode>();
  // Which paper this is open in is stated once, by the shell above — the page used to repeat the
  // four papers as a second switcher beside its own title, next to the one the shell already
  // draws.
  //
  // The title is not drawn either. The tab strip above says 知识脉络, and it says it as the tab
  // that is open, so a heading repeating it was a second statement of the same fact — one that
  // also split the page into a title bar plus a body. The heading stays in the document, unseen,
  // because a page still has to be a document: this is what a screen reader announces on arrival
  // and what the outline below is labelled by.
  //
  // The page's tools are not here either. 对话 and 资料库 are first-level pages of the paper, in
  // the strip above, because that is what they are in 专业学习 — a global entry bolted into one
  // tool's body is a second navigation, and it made this page answer for the whole space. What is
  // left is what this page is: the outline, and the knowledge point that is open in it.
  const errorState = query.error instanceof ApiRequestError ? normalizeApiError(query.error.status, query.error.detail) : normalizeApiError(undefined);
  if (!entitlement.isPending && !entitlement.isError && !allowed) {
    return <ExamPageShell cs408Tab="knowledge" moduleKey={module.key}><section className="cs408-knowledge" aria-labelledby="knowledge-title"><h1 id="knowledge-title" className="sr-only">知识脉络</h1><LockedKnowledge requiredTier={planFeature?.required_tier} /></section></ExamPageShell>;
  }
  return <ExamPageShell cs408Tab="knowledge" moduleKey={module.key}><section className="cs408-knowledge" aria-labelledby="knowledge-title"><h1 id="knowledge-title" className="sr-only">知识脉络</h1>{query.isPending ? <div className="cs408-knowledge__loading"><Skeleton className="h-11 w-48" /><Skeleton className="h-72 w-full" /></div> : null}{query.isError || !query.data ? <section className="cs408-knowledge__error">{errorState.kind === 'capability_required' ? <><h2>当前档位暂未开放知识脉络</h2><Link to="/membership">查看会员档位与权益</Link></> : <><h2>{errorState.message}</h2><Button variant="secondary" onClick={() => void query.refetch()}>重试</Button></>}</section> : null}{query.data ? <div className="cs408-knowledge__grid"><section className="knowledge-outline" aria-label={`${module.name}知识目录`}><p className="knowledge-outline__summary">已学习 {query.data.stats.mastered} / {query.data.stats.total_knowledge_points} 个知识点</p><ol>{query.data.chapters.map((chapter, index) => <Chapter key={chapter.code} chapter={chapter} selectedCode={selected?.code} onSelect={setSelected} initiallyOpen={index === 0} />)}</ol></section>{selected ? <Detail node={selected} courseId={query.data.course_id} subjectKey={module.key} onStatusChanged={(status) => setSelected((current) => current ? { ...current, status } : current)} /> : <div className="knowledge-detail knowledge-detail--empty"><p>选择一个知识点</p><h2>从目录开始</h2><span>展开章节，查看具体知识点与当前学习状态。</span></div>}</div> : null}</section></ExamPageShell>;
}
