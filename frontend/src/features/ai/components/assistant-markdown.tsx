import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

export function AssistantMarkdown({ content }: { content: string }) {
  return <ReactMarkdown
    remarkPlugins={[remarkGfm, remarkMath]}
    rehypePlugins={[rehypeKatex]}
    components={{
      code({ className, children, ...props }) {
        const language = /language-([\w-]+)/.exec(className ?? '')?.[1];
        const block = String(children).includes('\n');
        if (!block) return <code className="rounded bg-primary-soft px-1 py-0.5 font-mono text-[0.9em]" {...props}>{children}</code>;
        return <CodeBlock language={language} text={String(children).replace(/\n$/, '')} />;
      },
      a: ({ children, ...props }) => <a className="underline" target="_blank" rel="noreferrer" {...props}>{children}</a>,
      // Headings are styled here rather than left to the browser, whose defaults the CSS reset
      // removes — an answer with sections in it would otherwise read as one flat paragraph, on
      // the chat and on 学习 alike. The sizes are the product's own scale, not new ones.
      h1: ({ children }) => <h2 className="mt-6 mb-2 text-card-title font-semibold text-text-primary first:mt-0">{children}</h2>,
      h2: ({ children }) => <h3 className="mt-6 mb-2 text-card-title font-semibold text-text-primary first:mt-0">{children}</h3>,
      h3: ({ children }) => <h4 className="mt-5 mb-1.5 text-body font-semibold text-text-primary first:mt-0">{children}</h4>,
      h4: ({ children }) => <h5 className="mt-5 mb-1.5 text-body font-semibold text-text-primary first:mt-0">{children}</h5>,
      ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>,
      ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-5">{children}</ol>,
      p: ({ children }) => <p className="my-3 first:mt-0 last:mb-0">{children}</p>,
      hr: () => <hr className="my-6 border-border-default" />,
      table: ({ children }) => <div className="my-4 overflow-x-auto"><table className="w-full border-collapse border border-border-default text-left text-sm">{children}</table></div>,
      th: ({ children }) => <th className="border border-border-default bg-page-background px-3 py-2 font-medium text-text-primary">{children}</th>,
      td: ({ children }) => <td className="border border-border-default px-3 py-2 align-top">{children}</td>,
      blockquote: ({ children }) => <blockquote className="my-4 border-l-2 border-primary bg-primary-soft px-4 py-3 text-text-secondary">{children}</blockquote>,
      pre: ({ children }) => <>{children}</>,
    }}
  >{content}</ReactMarkdown>;
}

/**
 * One fenced block, with the copy control the answer card also uses.
 *
 * The control is an ICON, not the word 复制: the same Copy mark means the same thing on both
 * surfaces, where a word here and an icon there read as two different actions. What it does is
 * said by the tooltip, and the tick it briefly becomes is the confirmation — a second word
 * ("已复制") would be the same mistake in reverse.
 */
function CodeBlock({ language, text }: { language?: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard?.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };
  return <div className="my-4 overflow-hidden rounded-xl border border-border-default bg-slate-950 text-slate-100">
    <div className="flex items-center justify-between border-b border-white/10 px-3 py-2 text-xs text-slate-300"><span>{language ?? '代码'}</span><button type="button" onClick={() => void copy()} title={copied ? '已复制' : '复制'} aria-label={copied ? '已复制' : '复制'} className="inline-flex size-7 items-center justify-center rounded text-slate-300 hover:bg-white/10 hover:text-white">{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</button></div>
    <pre className="overflow-x-auto p-4 text-sm leading-6"><code>{text}</code></pre>
  </div>;
}
