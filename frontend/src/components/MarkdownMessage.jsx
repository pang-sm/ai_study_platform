import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

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

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false);
  const rawCode = String(children || "").replace(/\n$/, "");
  const languageMatch = /language-([\w-]+)/.exec(className || "");
  const language = languageMatch?.[1] || "代码";

  useEffect(() => {
    if (!copied) return undefined;

    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await copyText(rawCode);
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
        <code className={className}>{rawCode}</code>
      </pre>
    </div>
  );
}

export default function MarkdownMessage({ content, isTyping = false }) {
  return (
    <div className="message-text message-text--markdown">
      <ReactMarkdown
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
        }}
      >
        {content || ""}
      </ReactMarkdown>

      {isTyping && <span className="typing-cursor" aria-hidden="true" />}
    </div>
  );
}
