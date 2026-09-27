import { ScopedAiChatWorkspace } from '@/features/ai/components/ai-chat-page';
import { cs408Modules } from '../api/dashboard-summary';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';

/**
 * A 408 paper's assistant, inside the paper's own workspace.
 *
 * The conversation stays on this page rather than sending the learner to the product-wide
 * assistant: the subject they are working in is the page they are on, and leaving it to ask
 * about it is the navigation this page exists to remove. What is embedded is the ONE chat
 * workspace the course and programming spaces embed too — same composer, same history, same
 * attachment picker, same streaming — with the exam scope handed to it.
 *
 * The scope is the paper, and — when the learner arrived from a knowledge point on the outline —
 * that point as well. It is an identity the turn carries, not a question asked on their behalf:
 * the composer is empty, and the line above it says which point they are asking from so they can
 * tell this apart from a conversation about the whole paper. Switching the paper above drops the
 * point, because a node of 数据结构 means nothing inside 操作系统.
 */
export function Cs408AskWorkspace({
  moduleKey,
  knowledgePoint,
  knowledgePointTitle,
}: {
  moduleKey?: string;
  /** The canonical knowledge point this conversation is about, when it came from the outline. */
  knowledgePoint?: string;
  /** The point's title as the page that linked here wrote it — display only. */
  knowledgePointTitle?: string;
}) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  if (!module) {
    return (
      <ExamPageShell cs408Tab="ask">
        <Cs408SubjectChooser
          to="/exam/cs408/ask"
          description="对话按四门课分别建立。先选一门，再问它的内容。"
        />
      </ExamPageShell>
    );
  }

  return (
    <ExamPageShell cs408Tab="ask" moduleKey={module.key}>
      {/* The tabs above already say which page this is; the heading is what a screen reader
          announces on arrival, and the chat's own history list names the paper again. */}
      <h1 className="sr-only">
        AI 对话 · {module.name}
        {knowledgePoint ? ` · ${knowledgePointTitle ?? knowledgePoint}` : ''}
      </h1>
      <ScopedAiChatWorkspace
        scope={{ kind: 'exam', moduleKey: module.key, label: module.name, knowledgePoint, knowledgePointTitle }}
        embedded
        contextNote={
          knowledgePoint
            ? `当前围绕：${knowledgePointTitle ?? knowledgePoint}`
            : undefined
        }
      />
    </ExamPageShell>
  );
}
