import { ScopedAiChatWorkspace } from '@/features/ai/components/ai-chat-page';
import { canonicalLanguage, type ProgrammingLanguageSlug } from '../programming-language';
import { ProgrammingLanguageChooser, ProgrammingShell } from './programming-shell';

/**
 * AI 编程助手 — the space's assistant, inside the space.
 *
 * The conversation stays on this page rather than sending the learner to the product-wide
 * assistant: the language they are working in is the page they are on, and leaving it to ask
 * about it is the navigation this page exists to remove. What is embedded is the ONE chat
 * workspace every space embeds — same composer, same history, same attachment picker, same
 * streaming — with the programming scope handed to it.
 *
 * The scope carries the language by its CANONICAL name, which is what
 * `/ai?context=programming:Python` already sends. The scope is a conversation's identity, so
 * spelling it two ways would file one learner's questions under two different conversations.
 */
export function ProgrammingAiPage({ language }: { language: ProgrammingLanguageSlug | undefined }) {
  if (!language) {
    return (
      <ProgrammingShell active="ai">
        <ProgrammingLanguageChooser
          to="/programming/ai"
          heading="选择学习语言"
          description="对话按语言分别建立。先选一门，再问它的内容。"
        />
      </ProgrammingShell>
    );
  }

  const canonical = canonicalLanguage(language)!;
  return (
    <ProgrammingShell language={language} active="ai">
      {/* The strip above already says which page this is; the heading is what a screen reader
          announces on arrival, and the chat's own history list names the language again. */}
      <h1 className="sr-only">AI 编程助手 · {canonical}</h1>
      <ScopedAiChatWorkspace
        scope={{ kind: 'programming', language: canonical, label: canonical }}
        embedded
      />
    </ProgrammingShell>
  );
}
