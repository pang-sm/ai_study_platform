import { useEffect, useState, useMemo, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/atom-one-dark.css";
import "katex/dist/katex.min.css";

function copyText(text) {
  if (navigator?.clipboard?.writeText) {
    return navigator.clipboard.writeText(text);
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
  return Promise.resolve();
}

function getNodeText(node) {
  if (!node) return "";
  if (node.type === "text") return node.value || "";
  if (!Array.isArray(node.children)) return "";
  return node.children.map(getNodeText).join("");
}

function extractTextFromReactNode(value) {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(extractTextFromReactNode).join("");
  if (isValidElement(value)) return extractTextFromReactNode(value.props.children);
  return "";
}

function normalizeMathDelimiters(text) {
  if (!text || typeof text !== "string") return text;

  const codeBlockPattern = /```[\s\S]*?```/g;
  const codeBlocks = [];
  const segments = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockPattern.exec(text)) !== null) {
    segments.push(text.slice(lastIndex, match.index));
    codeBlocks.push(match[0]);
    lastIndex = match.index + match[0].length;
  }
  segments.push(text.slice(lastIndex));

  const processed = segments.map((seg) => {
    let result = seg;
    // \( ... \) → $ ... $
    result = result.replace(/\\\(/g, "$");
    result = result.replace(/\\\)/g, "$");
    // \[ ... \] → $$ ... $$
    result = result.replace(/\\\[/g, "$$");
    result = result.replace(/\\\]/g, "$$");
    return result;
  });

  let output = "";
  for (let i = 0; i < processed.length; i++) {
    output += processed[i];
    if (i < codeBlocks.length) {
      output += codeBlocks[i];
    }
  }
  return output;
}

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false);
  const copySource = useMemo(() => extractTextFromReactNode(children), [children]);
  const languageMatch = /language-([\w-]+)/.exec(className || "");
  const language = languageMatch?.[1] || "Text";

  useEffect(() => {
    if (!copied) return undefined;

    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await copyText(copySource);
      setCopied(true);
    } catch (error) {
      console.error("复制代码失败：", error);
      setCopied(false);
    }
  };

  return (
    <div className="code-block-card">
      <div className="code-block-toolbar">
        <span className="code-block-language">{language}</span>
        <button className="code-copy-button" type="button" onClick={handleCopy}>
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className="code-block-pre">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

export default function MarkdownMessage({ content, isTyping = false }) {
  const safeContent = useMemo(() => normalizeMathDelimiters(content || ""), [content]);

  return (
    <div className="message-text message-text--markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          code({ inline, className, children }) {
            if (inline) {
              return <code className="inline-code">{children}</code>;
            }

            return <CodeBlock className={className}>{children}</CodeBlock>;
          },
          p({ node, children }) {
            const rawText = getNodeText(node).trim();
            const highlightMatch = rawText.match(
              /^(最终答案|核心结论|关键命令|结论|建议|验证方式)[：:]\s*(.+)$/
            );

            if (highlightMatch) {
              return (
                <div className="markdown-callout">
                  <div className="markdown-callout-label">{highlightMatch[1]}</div>
                  <div className="markdown-callout-body">{highlightMatch[2]}</div>
                </div>
              );
            }

            return <p>{children}</p>;
          },
          table({ children }) {
            return <div className="table-wrapper"><table>{children}</table></div>;
          },
          img({ src, alt }) {
            return <img src={src} alt={alt || ""} className="markdown-image" loading="lazy" />;
          },
          hr() {
            return <hr className="markdown-divider" />;
          },
        }}
      >
        {safeContent}
      </ReactMarkdown>

      {isTyping && <span className="typing-cursor" aria-hidden="true" />}
    </div>
  );
}
