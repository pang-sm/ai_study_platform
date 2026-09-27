import { Component, useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import { useSearch } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowUp, ChevronLeft, ChevronRight, MoreHorizontal, Paperclip, Pencil, Plus, Sparkles, Square, UserRound } from 'lucide-react';
import { StatusNote } from '@/components/ui/status-note';
import { AiFeedback } from '@/components/learning/ai-feedback';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { serverMessage } from '@/lib/api/server-message';
import { cn } from '@/lib/utils';
import { useAuth } from '@/features/auth/auth-context';
import { ModelSelector } from './model-selector';
import { AssistantMarkdown } from './assistant-markdown';
import { materialStatusLabel } from '@/components/materials/material-file';
import { PersonalLibraryPicker } from './personal-library-picker';
import { streamAiChat } from '../api/ai-chat-stream';
import { uploadChatAttachment } from '../api/attachments';
import type { LibraryMaterial } from '@/features/library/api/library';
import {
  AI_SESSIONS_KEY,
  fetchAiSessionTurns,
  renameAiSession,
  useCourseMaterialsForChat,
  useScopedAiSessions,
  type AiAttachment,
  type AiScope,
  type AiTurn,
  type AiVersionInfo,
} from '../api/ai-chat';

/** The user message's action row: below the bubble, sized so the actions line up with it. */
const MESSAGE_ACTION_ROW_CLASS = 'mt-1 flex w-full items-center justify-end gap-1 pr-12';

/** One control in that row. A disabled one is a boundary — there is no version that way. */
const MESSAGE_ACTION_BUTTON_CLASS = 'inline-flex size-7 shrink-0 items-center justify-center rounded-control text-text-muted transition-opacity hover:bg-page-background hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent';

/**
 * What a turn carries and what a request needs to name: the file's identity on screen.
 *
 * Deliberately narrower than the composer's own `LibraryMaterial` — a turn restored from history
 * knows only this much about its attachments, and a re-worded question carries exactly this much
 * forward. What it is NOT is a stale copy of the file: the id names the same asset the server
 * already holds.
 */
type PendingAttachment = Pick<AiAttachment, 'materialId' | 'filename' | 'fileType' | 'parseStatus'>;

export function AiChatPage() {
  const { context: requestedContext } = useSearch({ from: '/ai' });
  const scope = scopeFromRoute(requestedContext);
  if (!scope) return <div className="mx-auto max-w-3xl px-5 py-12 text-body text-text-secondary">请从课程或科目中打开 AI 助手。</div>;
  return <ScopedAiChatWorkspace scope={scope} />;
}

/** The one full chat workspace, embedded by learning spaces with their canonical scope. */
export function ScopedAiChatWorkspace({
  scope,
  embedded = false,
  contextNote,
}: {
  scope: ScopedAiScope;
  embedded?: boolean;
  /**
   * What this conversation is about beyond its scope, stated where the learner is typing.
   *
   * A learner who entered from one knowledge point has to be able to see, without asking, that
   * the assistant knows which one — otherwise they cannot tell this apart from a conversation
   * about the whole paper. It is a line, not a banner: it sits directly above the composer, and
   * it is absent for every scope that has nothing extra to say.
   */
  contextNote?: ReactNode;
}) {
  const [turns, setTurns] = useState<AiTurn[]>([]);
  const [draft, setDraft] = useState('');
  const [deep, setDeep] = useState(false);
  const [sessionId, setSessionId] = useState<number | undefined>();
  const [modelId, setModelId] = useState('auto');
  const [streaming, setStreaming] = useState(false);
  const [attachments, setAttachments] = useState<LibraryMaterial[]>([]);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const nextId = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const localFileRef = useRef<HTMLInputElement>(null);
  /** One run's identity: bumped whenever a run starts OR is abandoned, so a lagging callback
      from a run the learner already left can never write into the current one. */
  const runToken = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const activeAnswer = useRef<string | null>(null);
  // The answer text seen so far, mirroring the turn: the error path needs it synchronously (the
  // turns state is stale inside the callback) to tell an interrupted answer from an empty one.
  const partialText = useRef('');
  /** Guards a session restore against a second one finishing after it. */
  const loadToken = useRef(0);
  /** Whether new content should pull the transcript along (false once the learner scrolls up). */
  const followingRef = useRef(true);
  const scrollFrame = useRef<number | null>(null);

  const courseMaterials = useCourseMaterialsForChat(scope.kind === 'course' ? scope.courseId : undefined);
  const auth = useAuth();
  /** The learner turn currently being re-worded, if any. */
  const [editing, setEditing] = useState<{ turnId: string; text: string } | null>(null);
  const busy = streaming;
  const materialIds = courseMaterials.data?.map((material) => material.id) ?? [];
  const standardCapability = scope.kind === 'course' ? 'material.qa' : 'tutor.chat';
  const modelCapability = deep ? 'tutor.strong_reasoning' : standardCapability;
  const scopeIdentity = scopeIdentityOf(scope);
  const clearPendingAttachments = () => setAttachments([]);
  const addAttachments = (items: LibraryMaterial[]) => setAttachments((current) => {
    const ids = new Set(current.map((item) => item.materialId));
    return [...current, ...items.filter((item) => !ids.has(item.materialId))];
  });
  const removeAttachment = (materialId: number) => setAttachments((current) => current.filter((item) => item.materialId !== materialId));
  const onLocalFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []); event.target.value = '';
    addAttachments(await Promise.all(files.map(uploadChatAttachment)));
  };

  // A remount for another course, or an in-place scope change, must both kill the running run:
  // its answer belongs to a question asked under a different scope.
  useEffect(() => {
    return () => {
      runToken.current += 1;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, [scopeIdentity]);

  // If the SAME instance is handed a new scope (not remounted), start it clean rather than
  // leave a half-answer from the old scope on screen.
  const previousScope = useRef(scopeIdentity);
  useEffect(() => {
    if (previousScope.current === scopeIdentity) return;
    previousScope.current = scopeIdentity;
    setTurns([]);
    setSessionId(undefined);
    setDraft('');
    setStreaming(false);
    clearPendingAttachments();
  }, [scopeIdentity]);

  // Follow the answer only while the learner is at the bottom, and at most once per animation
  // frame: a token arriving mid-frame is batched into the same scroll instead of one per token.
  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !followingRef.current) return;
    if (scrollFrame.current !== null) return;
    scrollFrame.current = window.requestAnimationFrame(() => {
      scrollFrame.current = null;
      node.scrollTop = node.scrollHeight;
    });
    return () => {
      if (scrollFrame.current !== null) {
        window.cancelAnimationFrame(scrollFrame.current);
        scrollFrame.current = null;
      }
    };
  }, [turns]);

  const handleScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    followingRef.current = distanceFromBottom <= 80;
  };

  const newId = () => `turn-${(nextId.current += 1)}`;
  const settle = (id: string, patch: Partial<AiTurn>) =>
    setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn)));

  /** Abandon the running run (if any): its later events find the token stale and are dropped.
      A partial answer is kept as a normal done answer; an empty one leaves no bubble behind. */
  const stopRun = () => {
    const answerId = activeAnswer.current;
    if (answerId) {
      setTurns((current) => {
        const turn = current.find((item) => item.id === answerId);
        if (!turn) return current;
        if (!turn.text.trim()) return current.filter((item) => item.id !== answerId);
        return current.map((item) => (item.id === answerId ? { ...item, state: 'done' as const } : item));
      });
    }
    abortRef.current?.abort();
    abortRef.current = null;
    activeAnswer.current = null;
    runToken.current += 1;
    setStreaming(false);
  };

  /** The last message of the view on screen: what the next turn continues from. */
  const viewContinuationId = () => [...turns].reverse().find((turn) => turn.messageId !== undefined)?.messageId;

  /**
   * `editSourceMessageId` is set by exactly one caller: re-asking a question that is already in
   * this conversation, in new words. The server then records the new wording as a VERSION of that
   * question — same session, original kept — instead of as a brand-new turn.
   *
   * Everything else is asked from the view the learner is on: the turn names the last message of
   * that view, so asking a question while looking at an older version continues THAT version.
   */
  const ask = (question: string, options: { pending?: PendingAttachment[]; editSourceMessageId?: number } = {}) => {
    const pending = options.pending ?? attachments;
    stopRun();
    const run = (runToken.current += 1);
    const controller = new AbortController();
    abortRef.current = controller;
    const answerId = newId();
    const learnerId = newId();
    activeAnswer.current = answerId;
    partialText.current = '';

    setTurns((current) => [
      ...current,
      { id: learnerId, role: 'learner', text: question, attachments: pending, state: 'done' },
      { id: answerId, role: 'assistant', text: '', state: 'pending' },
    ]);
    setDraft('');
    followingRef.current = true;
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setStreaming(true);

    const isCurrent = () => runToken.current === run;
    const finish = () => {
      if (!isCurrent()) return;
      abortRef.current = null;
      activeAnswer.current = null;
      setStreaming(false);
    };

    void streamAiChat(
      {
        message: question,
        sessionId,
        editSourceMessageId: options.editSourceMessageId,
        continueFromMessageId: options.editSourceMessageId === undefined ? viewContinuationId() : undefined,
        scope,
        thinkingMode: deep ? 'deep' : 'standard',
        materialIds,
        attachmentIds: pending.map((item) => item.materialId),
        modelId: modelId === 'auto' ? '' : modelId,
      },
      {
        onStart: (payload) => {
          if (!isCurrent()) return;
          if (payload.sessionId !== null) setSessionId(payload.sessionId);
          settle(answerId, { requestId: payload.requestId });
          // The stored id of the question just asked, so it can be edited without a reload.
          if (payload.userMessageId !== null) settle(learnerId, { messageId: payload.userMessageId });
          clearPendingAttachments();
        },
        onDelta: (text) => {
          if (!isCurrent()) return;
          partialText.current += text;
          setTurns((current) => current.map((turn) => (turn.id === answerId ? { ...turn, text: turn.text + text } : turn)));
        },
        onDone: (payload) => {
          if (!isCurrent()) return;
          finish();
          if (payload.sessionId !== null) setSessionId(payload.sessionId);
          settle(answerId, {
            citations: payload.references,
            requestId: payload.requestId,
            resolvedModel: payload.resolvedModel,
            finishReason: payload.finishReason,
            stopped: payload.stopped,
            deep,
            state: 'done',
          });
        },
        onError: (error) => {
          if (!isCurrent()) return;
          finish();
          // A PROVIDER THAT BROKE MID-ANSWER: the text the learner already read is all there will
          // be, and it is a finished answer for this turn — it keeps its text, its actions and its
          // rating rather than becoming an error card. Only a turn with nothing to show is a
          // failure. (The partial is already persisted server-side, so a reload agrees.)
          if (partialText.current.trim()) {
            settle(answerId, { finishReason: 'interrupted', stopped: false, deep, state: 'done' });
            return;
          }
          settle(answerId, { ...failure(error), state: 'failed' });
        },
      },
      controller.signal,
    ).finally(finish);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const question = draft.trim();
    if (question && !busy) ask(question);
  };

  const openSession = async (id: number) => {
    stopRun();
    const load = (loadToken.current += 1);
    setSessionId(id);
    const restored = await fetchAiSessionTurns(id, scope);
    if (loadToken.current !== load) return;
    setTurns(restored.map((turn) => ({ ...turn })));
    clearPendingAttachments();
  };

  /**
   * Look at another version of a question.
   *
   * This is READING, not editing: the other version and everything that continued from it are
   * already in the database, so switching asks the server for that branch and shows it. Nothing is
   * written, no provider is reached, and the conversation is the same conversation it was — the
   * history list does not move.
   */
  const switchVersion = async (messageId: number) => {
    if (sessionId === undefined) return;
    stopRun();
    const load = (loadToken.current += 1);
    const restored = await fetchAiSessionTurns(sessionId, scope, messageId);
    if (loadToken.current !== load) return;
    setEditing(null);
    setTurns(restored.map((turn) => ({ ...turn })));
  };

  const startNew = () => {
    stopRun();
    loadToken.current += 1;
    setTurns([]);
    setSessionId(undefined);
    setDraft('');
    clearPendingAttachments();
  };

  /**
   * Ask a question that is already in this conversation again, in new words.
   *
   * It stays THIS conversation. The server records the new wording as a version of the question
   * being re-worded — the original and everything answered from it stay in the database — and the
   * view moves onto the new version: what is dropped from the screen is everything from the
   * re-worded question onwards, because those turns answered a question the learner has replaced.
   *
   * The question's own attachments come with it, minus the ones that have since been deleted:
   * they remain part of the history they were part of, but they are no longer files anyone can
   * ask about.
   */
  const submitEdit = () => {
    const editingTurn = turns.find((turn) => turn.id === editing?.turnId);
    const text = editing?.text.trim() ?? '';
    if (!editingTurn || editingTurn.messageId === undefined || sessionId === undefined || !text) return;
    const carried = (editingTurn.attachments ?? []).filter((item) => item.parseStatus !== 'deleted');

    setEditing(null);
    // The turns after the re-worded question belong to the version being replaced. They are still
    // stored — this only stops showing them.
    setTurns((current) => current.slice(0, current.findIndex((turn) => turn.id === editingTurn.id)));
    ask(text, { pending: carried, editSourceMessageId: editingTurn.messageId });
  };

  return (
    <div className={cn('w-full', embedded ? '' : 'mx-auto max-w-[1440px] px-5 py-6 sm:px-8 lg:px-12')}>
      <div className={cn('overflow-hidden rounded-2xl border border-border-default bg-surface shadow-sm lg:grid lg:grid-cols-[17rem_minmax(0,1fr)]', embedded ? 'min-h-[calc(100vh-17rem)]' : 'min-h-[calc(100vh-8.5rem)]')}>
        <aside aria-label="历史对话" className="border-b border-border-default bg-page-background p-4 lg:border-b-0 lg:border-r">
          <p className="px-2 text-body font-semibold text-text-primary">{scope.label}</p>
          <HistoryList scope={scope} activeSessionId={sessionId} onOpen={openSession} onNew={startNew} />
        </aside>

        <div className="flex min-h-0 min-w-0 flex-col">
          {embedded ? null : <header className="flex min-h-16 items-center border-b border-border-default px-5">
            <h1 className="text-heading font-semibold text-text-primary">{scope.label} AI 助手</h1>
          </header>}
          <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-y-auto px-5 py-6 sm:px-8">
          {turns.length ? (
            <ol role="log" aria-label="对话记录" className="mx-auto max-w-4xl space-y-6 pb-6">
              {turns.map((turn) =>
                turn.role === 'learner' ? (
                  <LearnerTurn
                    key={turn.id}
                    turn={turn}
                    avatarUrl={auth.user?.avatar_url ?? auth.user?.avatar}
                    version={turn.version}
                    // Editing needs a stored question to re-word, and one run at a time.
                    onStartEdit={turn.messageId !== undefined && !streaming ? () => setEditing({ turnId: turn.id, text: turn.text }) : undefined}
                    editing={editing?.turnId === turn.id ? editing : undefined}
                    onEditText={(text) => setEditing((current) => (current ? { ...current, text } : current))}
                    onCancelEdit={() => setEditing(null)}
                    onSubmitEdit={submitEdit}
                    onSwitchVersion={(messageId) => void switchVersion(messageId)}
                  />
                ) : (
                  <li key={turn.id}>
                    <AnswerTurn turn={turn} />
                    {turn.state === 'failed' ? (
                      <StatusNote tone="danger" className="mt-3">
                        {turn.text}
                        <button type="button" className="ml-3 underline" onClick={() => ask(turn.text)}>
                          再试一次
                        </button>
                      </StatusNote>
                    ) : null}
                  </li>
                ),
              )}
            </ol>
          ) : (
            <Opening />
          )}
          </div>

          <form
            onSubmit={submit}
            className="border-t border-border-default bg-surface px-5 py-4 sm:px-8"
          >
            {contextNote ? (
              <p className="mb-2 text-metadata text-text-secondary">{contextNote}</p>
            ) : null}
            <label htmlFor="ai-question" className="sr-only">
              你的问题
            </label>
            <div className="rounded-2xl border border-border-default bg-page-background p-2 shadow-sm focus-within:ring-2 focus-within:ring-primary">
              {attachments.length ? <div aria-label="待发送附件" className="flex flex-wrap gap-2 px-2 pt-2">{attachments.map((item) => <AttachmentChip key={item.materialId} item={item} onRemove={() => removeAttachment(item.materialId)} />)}</div> : null}
              <textarea
                id="ai-question"
                ref={textareaRef}
                value={draft}
                onChange={(event) => { setDraft(event.target.value); event.currentTarget.style.height = 'auto'; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 200)}px`; }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    const question = draft.trim();
                    if (question && !busy) ask(question);
                  }
                }}
                rows={1}
                className="block max-h-52 min-h-12 w-full resize-none bg-transparent px-3 py-2 text-body text-text-primary outline-none"
                placeholder={`问关于${scope.label}的问题…`}
              />
              <div className="flex items-center justify-between gap-2 px-1 pb-1">
                <div className="relative flex items-center gap-1"><input ref={localFileRef} onChange={(event) => void onLocalFiles(event)} className="hidden" type="file" multiple /><button type="button" aria-label="添加附件" aria-expanded={attachmentMenuOpen} onClick={() => setAttachmentMenuOpen((value) => !value)} className="inline-flex size-8 items-center justify-center rounded-lg text-text-secondary hover:bg-surface"><Paperclip className="size-4" /></button>{attachmentMenuOpen ? <div role="menu" className="absolute bottom-10 left-0 z-20 w-44 rounded-lg border border-border-default bg-surface p-1 shadow-sm"><button role="menuitem" type="button" onClick={() => { setAttachmentMenuOpen(false); localFileRef.current?.click(); }} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-page-background">上传本地文件</button><button role="menuitem" type="button" onClick={() => { setAttachmentMenuOpen(false); setLibraryOpen(true); }} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-page-background">从资料库添加</button></div> : null}<ModelSelector capability={modelCapability} value={modelId} onChange={setModelId} /><button type="button" aria-pressed={deep} onClick={() => { setDeep((value) => !value); setModelId('auto'); }} className={cn('inline-flex h-8 items-center gap-1 rounded-lg px-2 text-sm', deep ? 'bg-primary text-white' : 'text-text-secondary hover:bg-surface')}><Sparkles className="size-3.5" />深度思考</button></div>
                {busy ? (
                  <button type="button" aria-label="停止生成" onClick={stopRun} className="inline-flex size-8 items-center justify-center rounded-lg bg-primary text-white hover:bg-primary-hover"><Square className="size-4" /></button>
                ) : (
                  <button type="submit" aria-label="发送" disabled={!draft.trim()} className="inline-flex size-8 items-center justify-center rounded-lg bg-primary text-white hover:bg-primary-hover disabled:opacity-40"><ArrowUp className="size-4" /></button>
                )}
              </div>
            </div>

          </form>
          {libraryOpen ? (
            <PersonalLibraryPicker
              initialSelected={attachments.map((item) => item.materialId)}
              onCancel={() => setLibraryOpen(false)}
              onAdd={(items) => { addAttachments(items); setLibraryOpen(false); }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

export type ScopedAiScope = Exclude<AiScope, { kind: 'general' }>;

/**
 * The scope's stable identity, used only to notice a change.
 *
 * It carries the knowledge point for the exam scope, which the API layer's `scopeKey` does not:
 * a conversation ABOUT one knowledge point and a conversation about the paper at large are
 * different conversations even though the server files them in the same place, so stepping from
 * one to the other starts clean rather than appending to an answer about something else.
 */
function scopeIdentityOf(scope: ScopedAiScope): string {
  switch (scope.kind) {
    case 'exam': return `exam:${scope.moduleKey}:${scope.knowledgePoint ?? ''}`;
    case 'course': return `course:${scope.courseId}`;
    case 'programming': return `programming:${scope.language}`;
  }
}

function scopeFromRoute(value?: string): ScopedAiScope | null {
  if (!value) return null;
  const [kind, id] = value.split(':', 2);
  if (!id) return null;
  if (kind === 'exam') return { kind: 'exam', moduleKey: id, label: examLabel(id) };
  if (kind === 'course') return { kind: 'course', courseId: id, label: id };
  if (kind === 'programming') return { kind: 'programming', language: id, label: id };
  return null;
}

function examLabel(key: string): string {
  return ({ data_structure: '数据结构', operating_system: '操作系统', computer_network: '计算机网络', computer_organization: '计算机组成原理' } as Record<string, string>)[key] ?? key;
}

function HistoryList({
  scope,
  activeSessionId,
  onOpen,
  onNew,
}: {
  scope: AiScope;
  activeSessionId?: number;
  onOpen: (id: number) => void;
  onNew: () => void;
}) {
  const sessions = useScopedAiSessions(scope);
  const queryClient = useQueryClient();
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const [renaming, setRenaming] = useState<{ id: number; text: string; saving: boolean } | null>(null);
  const [renameError, setRenameError] = useState('');

  const saveRename = async () => {
    if (!renaming || renaming.saving) return;
    const title = renaming.text.trim();
    // An empty name is not a name: the old one stands rather than the row losing its label.
    if (!title) { setRenaming(null); setRenameError(''); return; }
    setRenaming({ ...renaming, saving: true });
    try {
      await renameAiSession(renaming.id, title, scope);
      setRenaming(null);
      setRenameError('');
      void queryClient.invalidateQueries({ queryKey: AI_SESSIONS_KEY });
    } catch (error) {
      setRenaming({ ...renaming, saving: false });
      setRenameError(error instanceof ApiRequestError ? serverMessage(error.detail) ?? '重命名没有成功，请稍后重试。' : '重命名没有成功，请稍后重试。');
    }
  };

  return (
    <section className="mt-6" aria-labelledby="ai-history-title">
      <div className="flex items-center justify-between px-2">
        <h2 id="ai-history-title" className="text-metadata font-medium text-text-secondary">历史对话</h2>
        <button type="button" onClick={onNew} className="inline-flex size-8 items-center justify-center rounded-control text-text-secondary hover:bg-primary-soft hover:text-primary" aria-label="新建对话"><Plus className="size-4" /></button>
      </div>
      {sessions.isPending ? (
        <p className="mt-4 px-2 text-metadata text-text-muted">正在加载…</p>
      ) : (sessions.data?.length ?? 0) === 0 ? (
        <p className="mt-4 px-2 text-metadata text-text-muted">还没有对话</p>
      ) : (
        <div className="mt-4 space-y-4">
          {groupSessions(sessions.data ?? []).map(([label, rows]) => (
            <section key={label} aria-label={label}>
              <p className="px-2 text-metadata text-text-muted">{label}</p>
              <ul className="mt-1 space-y-1">
                {rows.map((session) => (
                  <li key={session.id} className="group relative">
                    {renaming?.id === session.id ? (
                      <RenameForm
                        text={renaming.text}
                        saving={renaming.saving}
                        onText={(text) => setRenaming({ ...renaming, text })}
                        onCancel={() => { setRenaming(null); setRenameError(''); }}
                        onSave={() => void saveRename()}
                      />
                    ) : (
                      <div className="flex items-center gap-1">
                        <button type="button" aria-current={session.id === activeSessionId ? 'true' : undefined} onClick={() => void onOpen(session.id)} className={cn('min-w-0 flex-1 rounded-control px-2 py-2 text-left text-body transition-colors hover:bg-primary-soft', session.id === activeSessionId ? 'bg-primary-soft font-medium text-primary-ink' : 'text-text-secondary')}>
                          <span className="block truncate">{session.title}</span>
                          <span className="mt-0.5 block text-metadata text-text-muted">{formatHistoryTime(session.createdAt)}</span>
                        </button>
                        {/* Not a row of permanent buttons: the menu appears for the row being
                            pointed at (or tabbed into), and holds the actions that change a
                            conversation rather than open one. */}
                        <button
                          type="button"
                          aria-label={`${session.title} 的更多操作`}
                          aria-haspopup="menu"
                          aria-expanded={menuFor === session.id}
                          onClick={() => setMenuFor((current) => (current === session.id ? null : session.id))}
                          className="inline-flex size-7 shrink-0 items-center justify-center rounded-control text-text-muted opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 hover:bg-page-background hover:text-text-primary"
                        >
                          <MoreHorizontal className="size-4" />
                        </button>
                        {menuFor === session.id ? (
                          <div role="menu" className="absolute right-1 top-full z-20 w-32 rounded-lg border border-border-default bg-surface p-1 shadow-sm">
                            <button
                              role="menuitem"
                              type="button"
                              onClick={() => { setMenuFor(null); setRenameError(''); setRenaming({ id: session.id, text: session.title, saving: false }); }}
                              className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-page-background"
                            >
                              重命名
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {renameError ? <p role="alert" className="px-2 text-metadata text-danger-ink">{renameError}</p> : null}
        </div>
      )}
    </section>
  );
}

/** A conversation's name, edited in place. Enter saves, Escape abandons, leaving it keeps it. */
function RenameForm({
  text,
  saving,
  onText,
  onCancel,
  onSave,
}: {
  text: string;
  saving: boolean;
  onText: (text: string) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  const focusRef = useFocusOnMount<HTMLInputElement>();
  return (
    <form onSubmit={(event) => { event.preventDefault(); onSave(); }} className="px-1 py-0.5">
      <input
        ref={focusRef}
        value={text}
        disabled={saving}
        maxLength={100}
        aria-label="对话名称"
        onChange={(event) => onText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') { event.preventDefault(); onCancel(); }
        }}
        // Leaving the field keeps what was typed, which is what a title field does everywhere
        // else in this product.
        onBlur={onSave}
        className="w-full rounded-control border border-border-default bg-surface px-2 py-1.5 text-body text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary"
      />
    </form>
  );
}

/* ---------------------------------------------------------------- transcript */

/**
 * Focus a field as it appears, without `autoFocus`.
 *
 * The a11y rules refuse `autoFocus`, and rightly: it moves focus without the learner asking. A
 * field that only exists because they just asked for it is the other case — focusing it follows
 * them into it — so the focus happens here, once, on the mount that their own action caused.
 */
function useFocusOnMount<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return ref;
}

/**
 * The question, opened for re-wording. A field over the message rather than a modal, because it
 * is that message being changed and the rest of the conversation is still the context for it.
 */
function EditQuestionForm({
  turnId,
  text,
  onText,
  onCancel,
  onSubmit,
}: {
  turnId: string;
  text: string;
  onText?: (text: string) => void;
  onCancel?: () => void;
  onSubmit?: () => void;
}) {
  const focusRef = useFocusOnMount<HTMLTextAreaElement>();
  return (
    <div className="w-full max-w-[85%] rounded-2xl rounded-tr-sm border border-border-default bg-surface p-3 shadow-sm">
      <label className="sr-only" htmlFor={`edit-${turnId}`}>修改这条提问</label>
      <textarea
        id={`edit-${turnId}`}
        ref={focusRef}
        value={text}
        onChange={(event) => onText?.(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') { event.preventDefault(); onCancel?.(); return; }
          // Enter alone inserts a newline: a question is often more than one line, and committing
          // on Enter would send half of one.
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); onSubmit?.(); }
        }}
        rows={3}
        className="block w-full resize-y rounded-control border border-border-default bg-page-background px-3 py-2 text-body text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-primary"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-metadata text-text-muted">发送后会从这条提问重新回答，原对话保留。</p>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" onClick={onCancel} className="inline-flex h-9 items-center rounded-control px-3 text-body text-text-secondary hover:bg-page-background">
            取消
          </button>
          <button type="button" onClick={onSubmit} disabled={!text.trim()} className="inline-flex h-9 items-center rounded-control bg-primary px-4 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50">
            发送
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * What the learner asked, and — on hover — the way to ask it differently.
 *
 * The pencil is not a second message box: it opens the question in place. Sending it does not
 * amend that question either — the original and everything answered from it are kept — it adds a
 * version of it, in the same conversation, and the view moves onto that version.
 *
 * It appears only where it can work: on a learner turn (an answer is not a question, so there is
 * nothing to re-ask), and only once the server has told us which stored question this is.
 */
function LearnerTurn({
  turn,
  avatarUrl,
  version,
  onStartEdit,
  onSwitchVersion,
  editing,
  onEditText,
  onCancelEdit,
  onSubmitEdit,
}: {
  turn: AiTurn;
  avatarUrl?: string | null;
  /** Present only when this question has other versions to step between. */
  version?: AiVersionInfo;
  onStartEdit?: () => void;
  onSwitchVersion?: (messageId: number) => void;
  editing?: { turnId: string; text: string };
  onEditText?: (text: string) => void;
  onCancelEdit?: () => void;
  onSubmitEdit?: () => void;
}) {
  if (editing) {
    return (
      <li className="flex justify-end gap-3">
        <EditQuestionForm
          turnId={turn.id}
          text={editing.text}
          onText={onEditText}
          onCancel={onCancelEdit}
          onSubmit={onSubmitEdit}
        />
        <UserAvatar src={avatarUrl} />
      </li>
    );
  }

  return (
    <li className="group flex flex-col">
      <div className="flex w-full min-w-0 items-center justify-end gap-3">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-white shadow-sm">
          <p className="whitespace-pre-wrap text-body">{turn.text}</p>
          {turn.attachments?.length ? <div className="mt-2 flex flex-wrap gap-1">{turn.attachments.map((item) => <span key={item.materialId} className="rounded bg-white/15 px-2 py-1 text-xs">{item.filename}</span>)}</div> : null}
        </div>
        <UserAvatar src={avatarUrl} />
      </div>
      {/* The message's own action row, BELOW the bubble and right-aligned to its edge: the
          `pr-12` clears the avatar column (36px) plus the gap (12px), so the action lines up with
          the bubble rather than with the transcript.
          The whole row appears together when the message is pointed at or tabbed into — these are
          things to do to a question, not things to read — and `pointer-events` follows the opacity
          so a hidden control is not a target. Keyboard focus still reaches it, and
          `group-focus-within` reveals it when it does. */}
      {onStartEdit ? (
        <div
          className={cn(
            MESSAGE_ACTION_ROW_CLASS,
            'opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto group-focus-within:opacity-100 group-focus-within:pointer-events-auto',
          )}
        >
          {version ? (
            <>
              <button
                type="button"
                disabled={!version.hasPrevious}
                onClick={() => { if (version.previousMessageId !== undefined) onSwitchVersion?.(version.previousMessageId); }}
                title="上一个版本"
                aria-label={`上一个版本，当前第 ${version.index} 个，共 ${version.total} 个`}
                className={MESSAGE_ACTION_BUTTON_CLASS}
              >
                <ChevronLeft className="size-4" />
              </button>
              {/* The counter is decoration: the two buttons already say which version this is. */}
              <span aria-hidden="true" className="shrink-0 text-metadata tabular-nums text-text-muted">
                {version.index} / {version.total}
              </span>
              <button
                type="button"
                disabled={!version.hasNext}
                onClick={() => { if (version.nextMessageId !== undefined) onSwitchVersion?.(version.nextMessageId); }}
                title="下一个版本"
                aria-label={`下一个版本，当前第 ${version.index} 个，共 ${version.total} 个`}
                className={MESSAGE_ACTION_BUTTON_CLASS}
              >
                <ChevronRight className="size-4" />
              </button>
            </>
          ) : null}
          <button
            type="button"
            onClick={onStartEdit}
            title="编辑"
            aria-label={`编辑提问：${turn.text.slice(0, 20)}`}
            className={MESSAGE_ACTION_BUTTON_CLASS}
          >
            <Pencil className="size-4" />
          </button>
        </div>
      ) : null}
    </li>
  );
}

function AttachmentChip({ item, onRemove }: { item: LibraryMaterial; onRemove: () => void }) {
  return <span className="inline-flex items-center gap-1 rounded-lg border border-border-default bg-surface px-2 py-1 text-xs text-text-secondary"><span>{item.filename}</span><span>{materialStatusLabel(item.parseStatus)}</span><button type="button" aria-label={`移除 ${item.filename}`} onClick={onRemove} className="ml-1 text-text-muted hover:text-text-primary">×</button></span>;
}

function AnswerTurn({ turn }: { turn: AiTurn }) {
  const hasText = Boolean(turn.text.trim());
  // The action row belongs to a finished answer that actually says something. A streaming
  // answer, and an empty one, have nothing to copy or rate.
  const showActions = turn.state === 'done' && Boolean(turn.requestId) && hasText;

  return (
    <div className="flex gap-3" data-resolved-model={turn.resolvedModel ?? undefined}>
      <AssistantAvatar />
      <div data-answer-card className="min-w-0 max-w-[min(90%,48rem)] rounded-card border border-border-default bg-surface px-5 py-4 text-text-primary">
        {/* Only ever stated for an answer produced on this page: the server stores the answer and
            its citations but not which capability produced it, so a restored turn says nothing
            rather than claiming a mode it cannot prove. */}
        <div className="mb-3 flex items-center gap-2 text-metadata text-text-secondary">
          {turn.resolvedModel ? <span>{turn.resolvedModel}</span> : null}
          {turn.deep === true ? <span>· 深度思考</span> : null}
        </div>
      {hasText ? (
        <div className="ai-markdown text-body text-text-primary">
          {/* The answer grows in place, re-rendered from the accumulated text on every delta.
              Incomplete markdown mid-stream must never blank the conversation, so a throw here
              falls back to the raw text for that render and retries on the next one. */}
          <MarkdownBoundary text={turn.text}>
            <AssistantMarkdown content={turn.text} />
          </MarkdownBoundary>
        </div>
      ) : turn.state === 'pending' ? (
        <ThinkingIndicator />
      ) : null}

      {turn.citations?.length ? (
        <details className="mt-4 border-t border-lab-grid pt-3">
          <summary className="text-body text-text-secondary">引用资料（{turn.citations.length}）</summary>
          <ul className="mt-3 space-y-3">
            {turn.citations.map((citation, index) => (
              <li key={`${citation.filename}-${index}`}>
                <p className="text-body font-medium text-text-primary">{citation.filename}</p>
                {citation.snippet ? (
                  <p className="mt-1 text-metadata text-text-secondary">{citation.snippet}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {showActions ? (
        <AiFeedback requestId={turn.requestId} workflowId="ai_chat" answerText={turn.text} />
      ) : null}
      </div>
    </div>
  );
}

/**
 * What the learner sees before the first token: the brand mark beside a light skeleton, not a
 * banner. It is a `status` region so the wait is announced without demanding attention.
 */
function ThinkingIndicator() {
  return (
    <span role="status" aria-label="正在作答" className="inline-flex flex-col gap-1.5 py-1">
      <span aria-hidden="true" className="h-3 w-40 animate-pulse rounded-full bg-neutral-soft" />
      <span aria-hidden="true" className="h-3 w-24 animate-pulse rounded-full bg-neutral-soft" />
    </span>
  );
}

/**
 * Keeps a render of half-arrived markdown from taking the page down. It re-renders the children
 * whenever the text changes, so a throw becomes one plain-text frame rather than a stuck
 * fallback; the parser itself is never bypassed or reimplemented here.
 */
class MarkdownBoundary extends Component<{ text: string; children: ReactNode }, { failed: boolean; text: string }> {
  state: { failed: boolean; text: string } = { failed: false, text: '' };

  static getDerivedStateFromError(): Partial<{ failed: boolean; text: string }> {
    return { failed: true };
  }

  static getDerivedStateFromProps(props: { text: string }, state: { failed: boolean; text: string }) {
    return props.text === state.text ? null : { failed: false, text: props.text };
  }

  render(): ReactNode {
    if (this.state.failed) {
      return <p className="whitespace-pre-wrap text-body text-text-primary">{this.props.text}</p>;
    }
    return this.props.children;
  }
}

function Opening() {
  return (
    <div className="flex h-full min-h-72 items-center justify-center text-body text-text-muted">
      开始新的对话
    </div>
  );
}

function AssistantAvatar() {
  return <img src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png" alt="智学 AI" className="size-9 shrink-0 rounded-full bg-primary p-1.5" />;
}

function UserAvatar({ src }: { src?: string | null }) {
  if (src) return <img src={src} alt="你的头像" className="size-9 shrink-0 rounded-full object-cover" />;
  return <span aria-label="你的头像" className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary"><UserRound className="size-5" /></span>;
}

function formatHistoryTime(value: string) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function groupSessions(sessions: { id: number; title: string; createdAt: string }[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const groups = new Map<string, typeof sessions>();
  for (const session of sessions) {
    const date = new Date(session.createdAt);
    const day = Number.isNaN(date.getTime()) ? -1 : new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    const label = day === today ? '今天' : day === today - 86_400_000 ? '昨天' : '更早';
    groups.set(label, [...(groups.get(label) ?? []), session]);
  }
  return [...groups.entries()];
}

/**
 * A refused turn, in the words the server used, or a sentence about what to do next.
 *
 * A 5xx is the one case where the server's own text is NOT shown. Its detail for a technical
 * failure is whatever the failing layer raised — for an AI outage that is the provider SDK's
 * message, naming the variable it wanted and the vendor behind the answer. The backend no longer
 * puts that in the body, and this refuses to render it even if some other handler does: a
 * learner reading an environment variable name has been shown the product's plumbing, not an
 * answer, and cannot act on it either way.
 */
function failure(error: unknown): { text: string } {
  if (error instanceof ApiRequestError) {
    if (error.status >= 500) return { text: 'AI 服务暂时不可用，稍后重试通常就好了。' };
    const message = serverMessage(error.detail);
    if (message) return { text: message };
    if (error.status === 403) return { text: '这个功能需要更高的会员档位。' };
    if (error.status === 429) return { text: '本次额度已经用完，稍后再试或查看会员档位。' };
  }
  return { text: '这次提问没有得到回答，再试一次通常就好了。' };
}
