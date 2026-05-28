import { useEffect, useState, useMemo, isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
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

// ── Inline-code downgrade for short text/plain fenced code blocks ──

const PRESERVED_LANGUAGES = new Set([
  "java", "python", "py", "c", "cpp", "c++", "bash", "sh", "zsh", "shell",
  "javascript", "js", "typescript", "ts", "tsx", "jsx", "html", "css",
  "json", "yaml", "yml", "xml", "sql", "latex", "tex", "dockerfile",
  "go", "rust", "rs", "php", "ruby", "rb", "powershell", "ps1",
  "markdown", "md", "diff", "patch", "toml", "ini", "conf", "makefile",
  "swift", "kotlin", "scala", "r", "lua", "dart", "perl", "groovy",
]);

const COLLAPSIBLE_LANGUAGES = new Set([
  "", "text", "txt", "plain", "none", "nohighlight", "plaintext",
]);

const CODE_STRUCTURE_RE =
  /[;{}]|\bimport\s|\bclass\s|\bpublic\s|\bprivate\s|\bprotected\s|\bfunction\s|\bconst\s|\blet\s|\bvar\s|\bdef\s|\breturn\s|\bthrow\s|\bcatch\s|\btry\s|\bif\s*\(|\bfor\s*\(|\bwhile\s*\(|\bswitch\s*\(|\bnpm\s|\bgit\s|\bsudo\s|\bpip\s|\bapt\s|\bsystemctl|\bdocker\s|\bcd\s|\bls\s|\bmkdir\s|\brm\s|\bcp\s|\bmv\s|&&|\|\||#include|\bexport\s|\brequire\s|\bpackage\s|\bprint\s*\(|\becho\s|=>|\bnew\s+\w+\s*\(/i;

function shouldRenderAsInlineCode(language, codeText) {
  const lang = (language || "").trim().toLowerCase();
  if (PRESERVED_LANGUAGES.has(lang)) return false;
  if (!COLLAPSIBLE_LANGUAGES.has(lang)) return false;

  const stripped = (codeText || "").trim();
  if (!stripped) return false;
  if (stripped.includes("\n")) return false;
  if (stripped.length > 60) return false;

  // Very short bracket-only / symbol-only content is not real code
  const bracketOnlyRe = /^[\{\}\[\]\(\)<>'"`,.:;!?@#$%^&*_+\-=\\\/|~`\s]{0,8}$/;
  if (bracketOnlyRe.test(stripped)) return true;

  // Plain natural-language-looking text (no code syntax) should be inline
  const looksLikeCode = CODE_STRUCTURE_RE.test(stripped);
  if (!looksLikeCode) return true;

  return false;
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

function getLanguageLabel(lang) {
  const map = {
    "": "代码", text: "文本", plain: "文本", txt: "文本",
    c: "C 代码示例", cpp: "C++ 代码示例", "c++": "C++ 代码示例",
    java: "Java 代码示例", python: "Python 代码示例", py: "Python 代码示例",
    javascript: "JavaScript 代码示例", js: "JavaScript 代码示例",
    typescript: "TypeScript 代码示例", ts: "TypeScript 代码示例",
    jsx: "JSX 代码示例", tsx: "TSX 代码示例",
    html: "HTML 代码示例", css: "CSS 代码示例",
    bash: "Bash 代码示例", sh: "Shell 代码示例", zsh: "Zsh 代码示例", shell: "Shell 代码示例",
    json: "JSON 代码示例", yaml: "YAML 代码示例", yml: "YAML 代码示例",
    xml: "XML 代码示例", sql: "SQL 代码示例",
    go: "Go 代码示例", rust: "Rust 代码示例", rs: "Rust 代码示例",
    php: "PHP 代码示例", ruby: "Ruby 代码示例", rb: "Ruby 代码示例",
    dart: "Dart 代码示例", kotlin: "Kotlin 代码示例", swift: "Swift 代码示例",
    scala: "Scala 代码示例", r: "R 代码示例", lua: "Lua 代码示例",
    dockerfile: "Dockerfile 代码示例",
    markdown: "Markdown 代码示例", md: "Markdown 代码示例",
    diff: "Diff 代码示例", patch: "Patch 代码示例",
    powershell: "PowerShell 代码示例", ps1: "PowerShell 代码示例",
    makefile: "Makefile 代码示例",
    toml: "TOML 代码示例", ini: "INI 代码示例", conf: "配置文件示例",
  };
  return map[lang.toLowerCase()] || `${lang} 代码示例`;
}

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false);
  const copySource = useMemo(() => extractTextFromReactNode(children), [children]);
  const languageMatch = /language-([\w-]+)/.exec(className || "");
  const language = languageMatch?.[1] || "";
  const languageLabel = getLanguageLabel(language);

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
        <span className="code-block-language">{languageLabel}</span>
        <button className="code-copy-button" type="button" onClick={handleCopy}>
          {copied ? "已复制" : "复制代码"}
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

            const langMatch = /language-([\w-]+)/.exec(className || "");
            const language = langMatch?.[1] || "";
            const rawText = extractTextFromReactNode(children);

            if (shouldRenderAsInlineCode(language, rawText)) {
              return <code className="inline-code inline-code--block">{rawText}</code>;
            }

            return <CodeBlock className={className}>{children}</CodeBlock>;
          },
          pre({ children }) {
            if (isValidElement(children) && children.props?.className?.includes("inline-code--block")) {
              return <div className="inline-code-standalone">{children}</div>;
            }
            return <pre>{children}</pre>;
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
