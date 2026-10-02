import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { DynamicPlanSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';
import { canonicalLanguage, type ProgrammingLanguageSlug } from '../programming-language';
import { ProgrammingShell } from './programming-shell';
import { useProgrammingPlan } from '../api/programming';

/**
 * 计划 — the study plan, and the adjustments proposed for it.
 *
 * The plan is read for the language in context, which is also how the backend files it: a plan
 * belongs to `programming:<language>`, so two languages' tasks cannot merge. The figures above
 * come from the endpoint as they are recorded; the surface below proposes changes and applies
 * none of them until the learner confirms.
 */
export function ProgrammingPlanPage({ language }: { language: ProgrammingLanguageSlug | undefined }) {
  const canonical = language ? canonicalLanguage(language) : undefined;
  const activeLanguage = canonical ?? '';
  const query = useProgrammingPlan(activeLanguage);

  return (
    <ProgrammingShell language={language}>
      <PageHeader
        eyebrow="计划"
        title="学习计划"
        description="调整建议需要你确认后才会生效。"
      />

      <section className="mt-8" aria-labelledby="programming-plan-record-title">
        <SectionHeading id="programming-plan-record-title" title="已记录的计划" as="h2" />
        {query.isPending ? (
          <LoadingState label="正在读取计划…" className="mt-4" />
        ) : query.isError ? (
          <StatusNote tone="warning" className="mt-4">
            计划暂时不可用；该能力可能需要升级。
          </StatusNote>
        ) : (
          <FactList className="mt-4" value={query.data} />
        )}
      </section>

      <DynamicPlanSurface
        scope={{ service_key: 'programming', course_id: '', exam_module_id: '', language: activeLanguage }}
      />
    </ProgrammingShell>
  );
}
