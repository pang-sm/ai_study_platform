import { createFileRoute } from '@tanstack/react-router';
import { AiChatPage } from '@/features/ai/components/ai-chat-page';

/**
 * `context` lets a learning space open the assistant ALREADY scoped to itself — a programming
 * exercise's 问 AI should not land a learner on 通用学习 and make them find their own language
 * again. The value is a `kind:value` pair matching the page's own scope vocabulary, and an
 * unparseable value is ignored rather than erroring: this is a convenience parameter, not a
 * contract, and a stale link must still open the assistant.
 */
export const Route = createFileRoute('/ai')({
  validateSearch: (search: Record<string, unknown>): { context?: string } =>
    typeof search.context === 'string' && search.context ? { context: search.context } : {},
  component: AiChatPage,
});
