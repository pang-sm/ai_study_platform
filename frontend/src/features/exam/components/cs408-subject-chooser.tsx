import { Link } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { routePath } from '@/lib/router';

/**
 * Which of the four papers of 408 is being studied — asked, not assumed.
 *
 * 408 is four subjects examined as one paper (数据结构 / 计算机组成原理 / 操作系统 / 计算机网络),
 * and everything inside it belongs to one of them, so the choice is a real one a learner makes
 * before any tool can say anything. It is one page with one job: four ways in. It used to be a
 * long index in which each paper also carried 知识脉络 / 章节练习 / 真题 / 问 AI, which is four
 * navigation strips for one decision, and it numbered the papers 01–04 as though the order were
 * something to remember.
 *
 * The same four choices are asked wherever a tool is opened without one — `/exam/cs408/knowledge`
 * with no module — because every tool but the subject-wide ones needs a paper before it can be
 * read. The alternative was defaulting to 数据结构, which would be the product answering a
 * question it was never asked, on an exam where the four parts are sat and scored separately.
 */
export function Cs408SubjectChooser({
  /** The route to open, with the chosen paper appended as its `module` search parameter. */
  to,
  heading = '选择学习科目',
  description,
  /** The paper's real state, when the page holding this chooser has read it. Never a guess. */
  statusOf,
}: {
  to: string;
  heading?: string;
  description?: string;
  statusOf?: (moduleKey: string) => string | undefined;
}) {
  return (
    <section aria-labelledby="cs408-choice-title">
      <h1 id="cs408-choice-title" className="cs408-choice__title">
        {heading}
      </h1>
      {description ? <p className="cs408-choice__note">{description}</p> : null}
      <ul className="cs408-choice-grid">
        {cs408Modules.map((module) => {
          const status = statusOf?.(module.key);
          return (
            <li key={module.key}>
              <Link to={routePath(to)} search={{ module: module.key }} className="cs408-choice">
                <span className="cs408-choice__name">{module.name}</span>
                {status ? <span className="cs408-choice__status">{status}</span> : null}
                <ArrowRight className="cs408-choice__go" aria-hidden="true" />
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
