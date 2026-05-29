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
  const stripped = (codeText || "").trim();
  if (!stripped) return false;

  // Multi-line content never fits in inline text flow
  if (stripped.includes("\n")) return false;

  // Bracket-only / symbol-only content (e.g. `{}`, `[]`, `()`) — not real code
  const bracketOnlyRe = /^[\{\}\[\]\(\)<>'"`,.:;!?@#$%^&*_+\-=\\\/|~`\s]{0,10}$/;
  if (bracketOnlyRe.test(stripped)) return true;

  // Single-line content ≤90 chars → always inline chip
  // A single line is never "big" enough to warrant a full code-block card
  if (stripped.length <= 90) return true;

  return false;
}

function shouldRenderAsCompactCode(language, codeText) {
  const stripped = (codeText || "").trim();
  if (!stripped) return false;

  const lines = stripped.split("\n");
  // Only multi-line content reaches compact tier; single-line is inline above
  const langLower = (language || "").trim().toLowerCase();
  const hasExplicitLang = PRESERVED_LANGUAGES.has(langLower);

  // 2–3 lines, no explicit programming language → compact snippet
  if (lines.length >= 2 && lines.length <= 3 && !hasExplicitLang && stripped.length <= 200) {
    return true;
  }

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

// Block-type heuristic — tells us whether a fenced block is real code,
// a table/process demonstration, command output, plain text, or math.
const CODE_LANGUAGE_SET = new Set([
  "java", "python", "py", "c", "cpp", "c++", "bash", "sh", "zsh", "shell",
  "javascript", "js", "typescript", "ts", "tsx", "jsx", "html", "css",
  "json", "yaml", "yml", "xml", "sql", "go", "rust", "rs", "php", "ruby", "rb",
  "powershell", "ps1", "dockerfile", "swift", "kotlin", "scala",
  "r", "lua", "dart", "perl", "groovy", "toml", "ini", "conf", "makefile",
  "diff", "patch",
]);

const TABLE_HEADER_RE = /[一-鿿]+\s*[|｜\/]\s*[一-鿿]+/;
const TABLE_ROW_RE = /^[|｜].*[|｜].*[|｜]/m;
const OUTPUT_PATTERN_RE = /(true|false|success|error|fail|运行|输出|结果)/i;

function getBlockType(lang, rawText) {
  const text = (rawText || "").trim();
  if (!text) return { type: "code", label: "代码", copyLabel: "复制代码" };

  const langLower = (lang || "").trim().toLowerCase();

  // Explicit programming language → real code
  if (langLower && CODE_LANGUAGE_SET.has(langLower)) {
    if (text.includes("\n") || text.length > 120) {
      return { type: "code", label: getLanguageLabel(langLower), copyLabel: "复制代码" };
    }
  }

  // Table detection: pipe-delimited rows or table-style headers
  const lines = text.split("\n").filter(Boolean);
  if (lines.length >= 2) {
    const pipeCount = lines.filter((l) => (l.match(/\|/g) || []).length >= 2).length;
    if (pipeCount >= 2 && pipeCount >= Math.min(lines.length, 3)) {
      return { type: "table", label: "表格内容", copyLabel: "复制内容" };
    }
    // Chinese table header patterns like "字符 | 栈内容 | 操作"
    if (TABLE_HEADER_RE.test(lines[0]) && lines.length >= 2) {
      return { type: "table", label: "执行过程", copyLabel: "复制内容" };
    }
    if (String(lines[0]).includes("|") && lines.length >= 2 && TEXT_TABLE_KEYWORDS.some((kw) => text.includes(kw))) {
      return { type: "table", label: "执行过程", copyLabel: "复制内容" };
    }
  }

  // Output patterns: repeated true/false lines, "运行结果" indicators
  if (lines.length >= 2 && lines.every((l) => /^(true|false)$/i.test(l.trim()))) {
    return { type: "output", label: "输出结果", copyLabel: "复制内容" };
  }
  if (OUTPUT_PATTERN_RE.test(lines[0]) && lines.length <= 4) {
    return { type: "output", label: "输出结果", copyLabel: "复制内容" };
  }

  // LaTeX / math
  if (langLower === "latex" || langLower === "tex" || text.startsWith("\\") || /\$[^$]+\$/.test(text) || /\\begin\{/.test(text)) {
    return { type: "math", label: "公式说明", copyLabel: "复制内容" };
  }

  // Generic text
  if (!langLower || langLower === "text" || langLower === "plain" || langLower === "txt" || langLower === "markdown" || langLower === "md") {
    return { type: "text", label: "示例内容", copyLabel: "复制内容" };
  }

  // Has code structure → real code
  if (CODE_STRUCTURE_RE.test(text)) {
    return { type: "code", label: getLanguageLabel(langLower), copyLabel: "复制代码" };
  }

  return { type: "text", label: "示例内容", copyLabel: "复制内容" };
}

const TEXT_TABLE_KEYWORDS = ["栈", "字符", "操作", "步骤", "过程", "演示", "输出", "结果"];

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false);
  const copySource = useMemo(() => extractTextFromReactNode(children), [children]);
  const languageMatch = /language-([\w-]+)/.exec(className || "");
  const language = languageMatch?.[1] || "";
  const blockType = useMemo(
    () => getBlockType(language, copySource),
    [language, copySource],
  );
  const blockLabel = blockType.label;
  const copyLabel = blockType.copyLabel;

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
      console.error("复制失败：", error);
      setCopied(false);
    }
  };

  return (
    <div className="code-block-card">
      <div className="code-block-toolbar">
        <span className="code-block-language">{blockLabel}</span>
        <button className="code-copy-button" type="button" onClick={handleCopy}>
          {copied ? "已复制" : copyLabel}
        </button>
      </div>
      <pre className="code-block-pre">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

function CompactCodeBlock({ className, children }) {
  const copySource = useMemo(() => extractTextFromReactNode(children), [children]);

  return (
    <div className="compact-code-snippet">
      <pre className="compact-code-pre">
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

            // Tier 1 — inline chip
            if (shouldRenderAsInlineCode(language, rawText)) {
              return <code className="inline-code inline-code--block">{rawText}</code>;
            }

            // Tier 2 — compact snippet (no toolbar, subtle styling)
            if (shouldRenderAsCompactCode(language, rawText)) {
              return <CompactCodeBlock className={className}>{children}</CompactCodeBlock>;
            }

            // Tier 3 — full code block with toolbar & highlight
            return <CodeBlock className={className}>{children}</CodeBlock>;
          },
          pre({ children }) {
            if (isValidElement(children)) {
              if (children.props?.className?.includes("inline-code--block")) {
                return <div className="inline-code-standalone">{children}</div>;
              }
              // Compact / full blocks supply their own layout — don't double-wrap
              if (children.type === CodeBlock || children.type === CompactCodeBlock) {
                return children;
              }
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
