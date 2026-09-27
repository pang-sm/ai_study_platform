import { Link } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatusNote } from '@/components/ui/status-note';
import { routePath } from '@/lib/router';
import { useExamCatalog } from '../api/catalog';
import { ApiRequestError, useExamSubjectContentStatus } from '../api/content-status';
import { normalizeApiError } from '../api/errors';
import { useExamProfile } from '../api/profile';
import { activeSubjectEntry, type ExamCatalogSubject } from '../view-models/exam-plan';
import { useMathTaxonomy } from '../api/math-taxonomy';
import { mathCapability } from '../view-models/math-domain';
import { ExamPageShell } from './exam-page-shell';
import { SubjectAvailabilityBadge } from './subject-availability-badge';

const categoryLabels: Record<string, string> = { public: '公共课', professional: '专业统考' };
const categoryLabel = (category: string) => categoryLabels[category] ?? category;

function apiState(error: unknown) {
  return error instanceof ApiRequestError ? normalizeApiError(error.status, error.detail) : normalizeApiError(undefined);
}

/**
 * The catalogue of national standardized exam subjects — a REFERENCE page, not a second home.
 *
 * It is what the exam space has to show about a subject it does not hold: the subjects that exist,
 * and which of them have content. The exam space's own subjects are on 考研学习, and the place a
 * learner changes them is 考试方案 — this page has no per-row 加入备考 control, because a row that
 * claimed to add a subject and only opened a page was a control that did not do what it said.
 */
export function SubjectsCatalogPage() {
  const catalog = useExamCatalog();
  const profile = useExamProfile();

  if (catalog.isPending || profile.isPending) {
    return (
      <ExamPageShell>
        <LoadingState label="正在读取科目目录…" />
      </ExamPageShell>
    );
  }

  if (catalog.isError || profile.isError) {
    const state = apiState(catalog.error ?? profile.error);
    return (
      <ExamPageShell>
        <PageHeader title="全部可选科目" />
        <StatusNote tone="danger" className="mt-8">
          {state.message}
        </StatusNote>
      </ExamPageShell>
    );
  }

  const selected = new Set(profile.data.selected_subjects);
  const categories = [...new Set(catalog.data.subjects.map((subject) => subject.category))];

  return (
    <ExamPageShell>
      <PageHeader
        title="全部可选科目"
        description="全国统考科目目录。目录只呈现当前真实的科目与内容状态；把你需要的科目加入考试方案，在考试方案里完成。"
        actions={
          <Button asChild variant="secondary">
            <Link to="/exam/setup">设置考试方案</Link>
          </Button>
        }
      />

      {categories.map((category) => (
        <section key={category} className="mt-10" aria-labelledby={`exam-category-${category}`}>
          <h2 id={`exam-category-${category}`} className="text-section-title font-semibold text-text-primary">
            {categoryLabel(category)}
          </h2>
          <ul className="mt-4 border-t border-border-default">
            {catalog.data.subjects
              .filter((subject) => subject.category === category)
              .map((subject) => (
                <CatalogRow key={subject.id} subject={subject} selected={selected.has(subject.id)} />
              ))}
          </ul>
        </section>
      ))}
    </ExamPageShell>
  );
}

function CatalogRow({ subject, selected }: { subject: ExamCatalogSubject; selected: boolean }) {
  const entry = activeSubjectEntry(subject.id);
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border-default py-4">
      <Link
        to="/exam/subjects/$subjectId"
        params={{ subjectId: subject.id }}
        className="min-w-0 flex-1 text-body font-medium text-text-primary hover:text-primary-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        {subject.display_name}
      </Link>
      {selected ? <span className="text-metadata text-text-secondary">已在考试方案中</span> : null}
      <SubjectAvailabilityBadge availability={subject.availability} />
      {entry ? (
        <Link to={routePath(entry)} className="text-metadata font-medium text-primary-ink hover:underline">
          进入学习
        </Link>
      ) : null}
    </li>
  );
}

/**
 * One subject's own page — a real status page, not a placeholder.
 *
 * A framework-only subject has nothing to study, so a page about it has to be worth reading
 * anyway: what state it is in, what that means for this learner's plan, and where to change it.
 * It used to be a full-page notice whose only content was that the subject was not built, which
 * reads as a page that is broken rather than a capability that is not open yet.
 *
 * Nothing on this page is a measurement. A knowledge-point total, a question total or a
 * percentage would all be numbers the product has no basis for — the honest statement is that the
 * content does not exist, and that is what it says.
 */
export function SubjectDetailPage({ subjectId }: { subjectId: string }) {
  const catalog = useExamCatalog();
  const profile = useExamProfile();
  const status = useExamSubjectContentStatus(subjectId);
  const mathTaxonomy = useMathTaxonomy();

  if (catalog.isPending || profile.isPending || status.isPending) {
    return (
      <ExamPageShell>
        <LoadingState label="正在读取科目状态…" />
      </ExamPageShell>
    );
  }

  if (catalog.isError || profile.isError) {
    const state = apiState(catalog.error ?? profile.error);
    return (
      <ExamPageShell>
        <PageHeader title="科目" />
        <StatusNote tone="danger" className="mt-8">
          {state.message}
        </StatusNote>
      </ExamPageShell>
    );
  }

  const subject = catalog.data.subjects.find((item) => item.id === subjectId);
  if (!subject) {
    return (
      <ExamPageShell>
        <PageHeader title="科目" />
        <StatusNote tone="danger" className="mt-8">
          这个科目不在全国统考科目目录中。
        </StatusNote>
      </ExamPageShell>
    );
  }

  const selected = profile.data.selected_subjects.includes(subject.id);
  const entry = activeSubjectEntry(subject.id);
  const year = profile.data.target_exam_year;
  // The shared maths model, when this subject is one of the three maths papers. It is read from
  // the same provider the home card uses, over the same backend taxonomy, so the two can never
  // describe maths differently — and no surface branches on which paper it is holding.
  const math = mathCapability(subject, mathTaxonomy.data);

  // The availability gate is the backend's own answer to "can this be studied?", so it decides
  // the state rather than the catalogue's flag being re-interpreted here.
  const notOpen = status.isError && apiState(status.error).kind === 'content_unavailable';
  if (status.isError && !notOpen) {
    const state = apiState(status.error);
    return (
      <ExamPageShell>
        <PageHeader title={subject.display_name} />
        <StatusNote tone="danger" className="mt-8">
          {state.message}
        </StatusNote>
      </ExamPageShell>
    );
  }

  return (
    <ExamPageShell>
      <PageHeader title={subject.display_name} />

      <div className="exam-status">
        <div className="exam-status__state">
          <p className="exam-status__state-label">当前状态</p>
          <Badge tone={notOpen ? 'warning' : 'success'}>
            {notOpen ? '科目框架已建立' : '完整学习功能已开放'}
          </Badge>
        </div>

        {notOpen ? (
          <>
            <p className="exam-status__body">
              {selected
                ? `已纳入你的${year ? ` ${year} ` : ''}考研方案。`
                : '还没有加入你的考试方案。'}
            </p>
            <p className="exam-status__body exam-status__body--muted">
              {math
                ? '这门科目已进入全国统考科目目录，知识体系已建立；学习内容与练习尚未开放。开放后你会在考研首页的同一张科目卡上直接进入，不需要再配置一次。'
                : '这门科目已进入全国统考科目目录，但完整知识体系、练习与学习工具尚未开放。开放后你会在考研首页的同一张科目卡上直接进入，不需要再配置一次。'}
            </p>

            {math ? (
              <>
                {/* What the maths exam is made of. The domains are the canonical three, shared by
                    every maths paper — this is not a per-paper list, which is precisely why the
                    same three appear under 数学（一）,（二）and（三）. */}
                <section className="exam-status__section" aria-labelledby="math-domains-title">
                  <h2 className="exam-status__section-title" id="math-domains-title">
                    学习模块
                  </h2>
                  <ul className="exam-status__plan">
                    {math.domains.map((domain) => (
                      <li key={domain.key}>
                        {domain.name}
                        <span>
                          · {domain.knowledgeMapStatus === 'available' ? '知识体系已建立' : '尚未建立学习数据'}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {/* Why three different papers show the same three modules. Without this the page
                      reads as though the choice of paper made no difference, which is not what the
                      product means: the papers differ in RANGE, and the range is not yet imported. */}
                  <p className="exam-status__body exam-status__body--muted">
                    数学（一）、数学（二）、数学（三）共享同一套数学知识框架；具体考试范围在正式考试大纲导入后配置。
                  </p>
                </section>

                {/* Which of those domains this paper examines is national syllabus data. Nothing
                    in this repository states it, so the page says so rather than guessing — and it
                    will keep saying so until the syllabus is imported. The sentence is the
                    backend's own, so the frontend cannot soften or sharpen it. */}
                <section className="exam-status__section" aria-labelledby="math-scope-title">
                  <h2 className="exam-status__section-title" id="math-scope-title">
                    考试范围
                  </h2>
                  <p className="exam-status__body exam-status__body--muted">{math.coverage.note}</p>
                </section>
              </>
            ) : null}
          </>
        ) : (
          <>
            <p className="exam-status__body">{subject.description || '这门科目已开放学习内容。'}</p>
            {status.data?.modules.length ? (
              <p className="exam-status__body exam-status__body--muted">
                由 {status.data.modules.length} 部分组成：{status.data.modules.map((module) => module.display_name).join(' · ')}。
              </p>
            ) : (
              <p className="exam-status__body exam-status__body--muted">
                这门科目的内容已开放，但当前版本还没有它的学习页面。
              </p>
            )}
          </>
        )}

        <section className="exam-status__section" aria-labelledby="subject-plan-title">
          <h2 className="exam-status__section-title" id="subject-plan-title">
            考试方案
          </h2>
          <ul className="exam-status__plan">
            <li>
              {subject.display_name}
              {selected ? <span>· 已在考试方案中</span> : <span>· 未加入考试方案</span>}
            </li>
            <li>
              {year ? `${year} 全国硕士研究生招生考试（统考）` : '全国硕士研究生招生考试（统考）'}
              <span>· 目标考试</span>
            </li>
          </ul>
        </section>

        <div className="exam-status__actions">
          <div className="flex flex-wrap gap-3">
            {entry ? (
              <Button asChild>
                <Link to={routePath(entry)}>
                  进入学习
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
            ) : null}
            <Button asChild variant={entry ? 'secondary' : 'primary'}>
              <Link to="/exam/setup">修改考试方案</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/exam/subjects">返回科目目录</Link>
            </Button>
          </div>
        </div>
      </div>
    </ExamPageShell>
  );
}
