import { cs408Modules, useCs408DashboardSummaries } from '@/features/exam/api/dashboard-summary';
import { toCs408ModuleStatus } from '@/features/exam/view-models/dashboard-summary';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';

/** Where each paper's own state is read from, in the order the catalogue lists them. */
function summaryIndex(moduleKey: string) {
  return cs408Modules.findIndex((entry) => entry.key === moduleKey);
}

/**
 * `/exam/cs408` — the subject's front door, and the one decision it asks for.
 *
 * It is four ways in and nothing else: the names, and the little of their state that is real. It
 * used to be a five-part index — a heading, a summary line, then four numbered rows each carrying a
 * progress figure, a chapter and knowledge-point count, today's tasks and three tool links — which
 * asked the learner to read a status board before letting them choose anything, and duplicated the
 * navigation that lives inside every one of those tools.
 *
 * Each paper leads into 知识脉络, which is where a paper starts now that the 概览 tab is gone: the
 * learner has just said which of the four they are working in, and the outline of it is the first
 * thing they can act on. There is no page here that describes a paper instead of teaching it, and
 * `?module=` on this route redirects into the outline so no older link lands on one.
 */
export function Cs408SubjectChoicesPage() {
  const summaries = useCs408DashboardSummaries();
  return (
    <ExamPageShell cs408Tab="knowledge" atSubjectHome>
      <Cs408SubjectChooser
        to="/exam/cs408/knowledge"
        // A paper whose summary has not arrived says nothing rather than something provisional:
        // the status is a real reading of the learner's work, not a placeholder to fill.
        statusOf={(key) => {
          const result = summaries[summaryIndex(key)];
          return result?.data ? toCs408ModuleStatus(result.data) : undefined;
        }}
      />
    </ExamPageShell>
  );
}
