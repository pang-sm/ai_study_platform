import { createFileRoute, redirect } from '@tanstack/react-router';
import { Cs408SubjectChoicesPage } from '@/features/exam/components/cs408-workspace';

/**
 * `/exam/cs408` is the subject's front door: four papers, one decision.
 *
 * It answers nothing else. What used to be here — a paper's own 概览 page at
 * `/exam/cs408?module=…` — is gone, and the paper it named is opened in 知识脉络 instead. That
 * redirect is kept rather than the parameter being ignored, because this URL is the one every
 * older link and every saved 继续学习 carries: dropping the parameter would silently open the
 * four-paper question at a learner who had already answered it, and answering with a 404 or an
 * empty page would lose them entirely.
 */
export const Route = createFileRoute('/exam/cs408/')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
  }),
  beforeLoad: ({ search }) => {
    if (search.module) {
      throw redirect({ to: '/exam/cs408/knowledge', search: { module: search.module } });
    }
  },
  component: Cs408SubjectChoicesPage,
});
