import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import MarkdownMessage from "./MarkdownMessage.jsx";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";

const API_BASE = "/api";

function getWsBase() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

function getTerminalWsUrl() {
  const base = getWsBase();
  // Try the direct path first (works with Nginx location block for /code/interactive-run)
  return `${base}/code/interactive-run`;
}

const LANGUAGES = ["Python", "C"];

function getMonacoLanguage(language) {
  const map = { Python: "python", C: "c", "C++": "cpp" };
  return map[language] || "plaintext";
}

const CODE_TEMPLATES = {
  Python: 'def main():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    main()',
  C: '#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}',
};

const STATUS_LABELS = {
  probable_pass: "大概率通过",
  partial: "可能部分通过",
  failed: "大概率不通过",
  unknown: "无法判定",
};

const STATUS_CLASSES = {
  probable_pass: "feedback-status--pass",
  partial: "feedback-status--partial",
  failed: "feedback-status--fail",
  unknown: "feedback-status--unknown",
};

/** Unified AI challenge detection — handles historical and current data formats */
function isAIChallenge(session) {
  if (!session) return false;
  // Has associated challenge_id: was generated through AI 出题 or diagnosis
  if (session.challenge_id) return true;
  // Backend field: session_type explicitly set
  if (session.session_type === "challenge") return true;
  // Backend returns challenge_source per session
  if (session.challenge_source && session.challenge_source !== "manual") return true;
  // Challenge was loaded separately (currentChallenge state)
  return false;
}

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function fetchWithTimeout(url, options = {}, timeout = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

// ── Autocompletion data ──────────────────────────────

const PYTHON_KEYWORDS = [
  "def", "class", "if", "elif", "else", "for", "while", "try", "except",
  "finally", "import", "from", "return", "break", "continue", "pass",
  "with", "lambda", "global", "nonlocal", "and", "or", "not", "in", "is",
  "True", "False", "None", "as", "assert", "async", "await", "del",
  "raise", "yield",
];

const PYTHON_BUILTINS = [
  "print", "input", "len", "range", "int", "str", "float", "list", "dict",
  "set", "tuple", "enumerate", "zip", "map", "filter", "sum", "max", "min",
  "abs", "type", "isinstance", "open", "sorted", "reversed", "round",
  "bool", "chr", "ord", "hex", "oct", "bin", "id", "dir", "help",
  "any", "all", "next", "iter", "slice", "super", "object", "hasattr",
  "getattr", "setattr", "delattr", "callable", "format", "pow", "divmod",
];

const PYTHON_SNIPPETS = [
  {
    label: "if __name__ == \"__main__\"",
    insertText: 'if __name__ == "__main__":\n    ${1:main()}',
    detail: "主入口",
  },
  {
    label: "def",
    insertText: "def ${1:name}(${2:args}):\n    ${3:pass}",
    detail: "函数定义",
  },
  {
    label: "class",
    insertText: "class ${1:ClassName}(${2:object}):\n    ${3:pass}",
    detail: "类定义",
  },
  {
    label: "for",
    insertText: "for ${1:i} in ${2:range}:\n    ${3:pass}",
    detail: "for 循环",
  },
  {
    label: "while",
    insertText: "while ${1:condition}:\n    ${2:pass}",
    detail: "while 循环",
  },
  {
    label: "if",
    insertText: "if ${1:condition}:\n    ${2:pass}",
    detail: "if 语句",
  },
  {
    label: "if/else",
    insertText: "if ${1:condition}:\n    ${2:pass}\nelse:\n    ${3:pass}",
    detail: "if-else 语句",
  },
  {
    label: "try/except",
    insertText: "try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}",
    detail: "异常处理",
  },
  {
    label: "try/except/finally",
    insertText: "try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}\nfinally:\n    ${5:pass}",
    detail: "try-except-finally",
  },
  {
    label: "list comprehension",
    insertText: "[${1:expr} for ${2:x} in ${3:iterable}]",
    detail: "列表推导式",
  },
];

const C_KEYWORDS = [
  "int", "char", "float", "double", "void", "if", "else", "for", "while",
  "do", "switch", "case", "break", "continue", "return", "struct",
  "typedef", "const", "static", "sizeof", "enum", "long", "short",
  "unsigned", "signed", "auto", "extern", "register", "volatile",
  "default", "goto", "union",
];

const C_FUNCTIONS = [
  "printf", "scanf", "getchar", "putchar", "strlen", "strcpy", "strcmp",
  "strcat", "malloc", "free", "memset", "memcpy", "memmove", "fopen",
  "fclose", "fgets", "fprintf", "sprintf", "qsort", "atoi", "atof",
  "abs", "rand", "srand", "time", "clock", "exit", "system",
  "gets", "puts", "fread", "fwrite", "fscanf", "sscanf", "perror",
  "tolower", "toupper", "isalpha", "isdigit", "isalnum", "isspace",
];

const C_SNIPPETS = [
  {
    label: "int main",
    insertText: "int main() {\n    ${1}\n    return 0;\n}",
    detail: "main 函数",
  },
  {
    label: "#include <stdio.h>",
    insertText: "#include <stdio.h>",
    detail: "标准 I/O 头文件",
  },
  {
    label: "#include <stdlib.h>",
    insertText: "#include <stdlib.h>",
    detail: "标准库头文件",
  },
  {
    label: "for",
    insertText: "for (int ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n    ${3}\n}",
    detail: "for 循环",
  },
  {
    label: "while",
    insertText: "while (${1:condition}) {\n    ${2}\n}",
    detail: "while 循环",
  },
  {
    label: "if",
    insertText: "if (${1:condition}) {\n    ${2}\n}",
    detail: "if 语句",
  },
  {
    label: "if/else",
    insertText: "if (${1:condition}) {\n    ${2}\n} else {\n    ${3}\n}",
    detail: "if-else 语句",
  },
  {
    label: "struct",
    insertText: "struct ${1:Name} {\n    ${2:int field};\n};",
    detail: "结构体定义",
  },
  {
    label: "malloc",
    insertText: "${1:int *}${2:p} = (${1:int *})malloc(${3:n} * sizeof(${1:int}));\nif (${2:p} == NULL) {\n    ${4:perror(\"malloc\"); return 1;}\n}",
    detail: "malloc 安全分配",
  },
  {
    label: "switch",
    insertText: "switch (${1:expr}) {\n    case ${2:0}:\n        ${3:break;}\n    default:\n        break;\n}",
    detail: "switch 语句",
  },
  {
    label: "do/while",
    insertText: "do {\n    ${1}\n} while (${2:condition});",
    detail: "do-while 循环",
  },
];

function makeCompletionItem(label, kind, detail, insertText, range) {
  return {
    label,
    kind,
    detail,
    insertText: insertText || label,
    range,
    sortText: `0${label}`,
  };
}

function makeSnippetItem(label, detail, insertText, kind, range) {
  return {
    label,
    kind,
    detail,
    insertText,
    insertTextRules: 4, // monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet
    range,
    sortText: `1${label}`,
  };
}

function registerAutocomplete(monaco) {
  // ── Python ──
  monaco.languages.registerCompletionItemProvider("python", {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const suggestions = [];

      PYTHON_KEYWORDS.forEach((kw) => {
        suggestions.push(makeCompletionItem(kw, monaco.languages.CompletionItemKind.Keyword, "关键词", kw, range));
      });
      PYTHON_BUILTINS.forEach((fn) => {
        suggestions.push(makeCompletionItem(fn, monaco.languages.CompletionItemKind.Function, "内置函数", fn, range));
      });
      PYTHON_SNIPPETS.forEach((snip) => {
        suggestions.push(makeSnippetItem(snip.label, snip.detail, snip.insertText, monaco.languages.CompletionItemKind.Snippet, range));
      });

      return { suggestions };
    },
    triggerCharacters: [".", " "],
  });

  // ── C ──
  monaco.languages.registerCompletionItemProvider("c", {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const suggestions = [];

      C_KEYWORDS.forEach((kw) => {
        suggestions.push(makeCompletionItem(kw, monaco.languages.CompletionItemKind.Keyword, "关键词", kw, range));
      });
      C_FUNCTIONS.forEach((fn) => {
        suggestions.push(makeCompletionItem(fn, monaco.languages.CompletionItemKind.Function, "库函数", fn, range));
      });
      C_SNIPPETS.forEach((snip) => {
        suggestions.push(makeSnippetItem(snip.label, snip.detail, snip.insertText, monaco.languages.CompletionItemKind.Snippet, range));
      });

      return { suggestions };
    },
    triggerCharacters: ["#", ".", " "],
  });
}

export default function CodeStudio({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  normalizeSubject,
  formatDate,
}) {
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [codeCourseId, setCodeCourseId] = useState(() => normalizeSubject(subject));
  const [title, setTitle] = useState("未命名练习");
  const [language, setLanguage] = useState("Python");
  const [code, setCode] = useState(CODE_TEMPLATES["Python"]);
  const [saving, setSaving] = useState(false);
  const [tip, setTip] = useState("");

  const [aiQuestion, setAiQuestion] = useState("");
  const [aiMessages, setAiMessages] = useState([]);
  const [aiMessagesLoading, setAiMessagesLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [savedMessageIds, setSavedMessageIds] = useState(new Set());
  const aiEndRef = useRef(null);

  const [showChallengeModal, setShowChallengeModal] = useState(false);
  const [challengeDifficulty, setChallengeDifficulty] = useState("基础");
  const [challengeFocus, setChallengeFocus] = useState("");
  const [challengeGenerating, setChallengeGenerating] = useState(false);
  const [currentChallenge, setCurrentChallenge] = useState(null);

  // ── Problem loading stability ──
  const [problemLoading, setProblemLoading] = useState(false);
  const [problemError, setProblemError] = useState("");
  const challengeCacheRef = useRef(new Map()); // challenge_id -> challenge data

  // ── AI Coach saved chats ──
  const [savedChats, setSavedChats] = useState([]);
  const [savedChatsLoading, setSavedChatsLoading] = useState(false);
  const [savedChatsCollapsed, setSavedChatsCollapsed] = useState(false);
  const [savingMsgIndex, setSavingMsgIndex] = useState(null);  // message index being saved
  const [savedMsgIds, setSavedMsgIds] = useState(new Set());   // backend ids of saved records
  const [deletingSavedId, setDeletingSavedId] = useState(null);

  // AI 出题 enhanced fields
  const [challengeCount, setChallengeCount] = useState(1);
  const [challengeGenError, setChallengeGenError] = useState("");
  const [challengeExtraReq, setChallengeExtraReq] = useState("");
  const [genKnowledgePoints, setGenKnowledgePoints] = useState([]);
  const [genMaterials, setGenMaterials] = useState([]);
  const [selectedGenKpIds, setSelectedGenKpIds] = useState([]);
  const [selectedGenMaterialIds, setSelectedGenMaterialIds] = useState([]);
  const [genDataLoading, setGenDataLoading] = useState(false);
  const [genDataError, setGenDataError] = useState("");

  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [diagnosisReport, setDiagnosisReport] = useState(null);
  const [targetedChallengeLoading, setTargetedChallengeLoading] = useState(false);
  const [taskGenerationLoading, setTaskGenerationLoading] = useState(false);

  // Feedback / Submit panel
  const [outputPanelTab, setOutputPanelTab] = useState("feedback"); // "run" | "feedback"
  const [showFeedbackPanel, setShowFeedbackPanel] = useState(false);
  const [feedbackContent, setFeedbackContent] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [codeTruncated, setCodeTruncated] = useState(false);

  // Code execution
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [stdin, setStdin] = useState("");

  // Test runner
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState(null);

  // Test failure explanation
  const [testExplanations, setTestExplanations] = useState({});
  const [explainingTestCase, setExplainingTestCase] = useState({});

  // Attempt history
  const [showAttemptHistory, setShowAttemptHistory] = useState(false);
  const [attempts, setAttempts] = useState([]);
  const [attemptsLoading, setAttemptsLoading] = useState(false);
  const [attemptFilter, setAttemptFilter] = useState("all");
  const [selectedAttempt, setSelectedAttempt] = useState(null);
  const [attemptDetailLoading, setAttemptDetailLoading] = useState(false);
  const [togglingMastered, setTogglingMastered] = useState({});

  // Code progress stats
  const [codeProgress, setCodeProgress] = useState(null);

  // Collapse passed test cases
  const [collapsePassed, setCollapsePassed] = useState(true);

  // Sidebar collapse
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [assistantCollapsed, setAssistantCollapsed] = useState(false);

  // ── Code diagnostics ──
  const [diagnosticStatus, setDiagnosticStatus] = useState("idle"); // idle | checking | ok | warning | error | unsupported
  const [diagnostics, setDiagnostics] = useState([]);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticSummary, setDiagnosticSummary] = useState({ errors: 0, warnings: 0 });
  const [diagnosticErrors, setDiagnosticErrors] = useState(0);
  const [diagnosticWarnings, setDiagnosticWarnings] = useState(0);
  const diagnoseTimerRef = useRef(null);
  const lastDiagnosedCodeRef = useRef("");
  const lastDiagnosedLanguageRef = useRef("");
  const monacoRef = useRef(null);
  const diagnosticDecorationsRef = useRef([]);

  // ── Interactive terminal ──
  const terminalRef = useRef(null);
  const terminalContainerRef = useRef(null);
  const fitAddonRef = useRef(null);
  const wsRef = useRef(null);
  const [terminalRunning, setTerminalRunning] = useState(false);
  const [terminalExitCode, setTerminalExitCode] = useState(null);
  const terminalOutputRef = useRef({ stdout: "", stderr: "", compile_error: "", exit_code: null, timed_out: false });

  // Generate test cases for old challenges
  const [generatingTests, setGeneratingTests] = useState(false);

  // Reference solution & starter code
  const [isReferenceModalOpen, setIsReferenceModalOpen] = useState(false);
  const [starterConfirmOpen, setStarterConfirmOpen] = useState(false);
  const [pendingApplyCode, setPendingApplyCode] = useState(null); // tracks which code to apply on confirm
  const [problemTab, setProblemTab] = useState("io");
  const [editorCursor, setEditorCursor] = useState({ line: 1, column: 1 });
  const [copyRefFeedback, setCopyRefFeedback] = useState(false);

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // ── Layout: resizable panes ──────────────────────────
  const LAYOUT_KEY = "codestudio.layout.v2";
  const LAYOUT_DEFAULTS = { leftWidth: 260, rightWidth: 320, problemWidth: 420, outputHeight: 220 };
  const LAYOUT_MIN = { leftWidth: 56, rightWidth: 56, problemWidth: 340, outputHeight: 80 };
  const [layout, setLayout] = useState(() => {
    try {
      const raw = localStorage.getItem(LAYOUT_KEY);
      if (raw) {
        const loaded = { ...LAYOUT_DEFAULTS, ...JSON.parse(raw) };
        // Enforce minimum widths — prevent 0-width from broken localStorage
        for (const key of Object.keys(LAYOUT_MIN)) {
          if (typeof loaded[key] === "number" && loaded[key] < LAYOUT_MIN[key]) {
            loaded[key] = LAYOUT_MIN[key];
          }
        }
        return loaded;
      }
    } catch {}
    return LAYOUT_DEFAULTS;
  });
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  const [resizing, setResizing] = useState(null);
  const resizeRef = useRef({});
  const editorRef = useRef(null);

  // persist layout
  useEffect(() => {
    const t = setTimeout(() => {
      try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch {}
    }, 300);
    return () => clearTimeout(t);
  }, [layout]);

  // ESC key to close modals
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") {
        if (isReferenceModalOpen) setIsReferenceModalOpen(false);
      }
    };
    if (isReferenceModalOpen) {
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }
  }, [isReferenceModalOpen]);

  // drag-resize listeners
  useEffect(() => {
    if (!resizing) return;
    const onMove = (e) => {
      const { type, startX, startY, startLayout } = resizeRef.current;
      setLayout((prev) => {
        const next = { ...prev };
        if (type === "left") next.leftWidth = Math.min(360, Math.max(56, startLayout.leftWidth + (e.clientX - startX)));
        if (type === "right") next.rightWidth = Math.min(420, Math.max(56, startLayout.rightWidth - (e.clientX - startX)));
        if (type === "problem") next.problemWidth = Math.min(560, Math.max(340, startLayout.problemWidth + (e.clientX - startX)));
        if (type === "output") next.outputHeight = Math.min(window.innerHeight * 0.45, Math.max(48, startLayout.outputHeight - (e.clientY - startY)));
        return next;
      });
      if (editorRef.current) editorRef.current.layout();
    };
    const onUp = () => {
      setResizing(null);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [resizing]);

  const startResize = (e, type) => {
    e.preventDefault();
    setResizing(type);
    resizeRef.current = { type, startX: e.clientX, startY: e.clientY, startLayout: { ...layoutRef.current } };
    document.body.style.cursor = type === "output" ? "row-resize" : "col-resize";
    document.body.style.userSelect = "none";
  };

  // focus mode
  const [focusMode, setFocusMode] = useState(false);
  const preFocusLayout = useRef(null);
  const enterFocus = () => { preFocusLayout.current = { ...layoutRef.current }; setProblemCollapsed(true); setFocusMode(true); setProblemError(""); };
  const exitFocus = () => {
    if (preFocusLayout.current) setLayout(preFocusLayout.current);
    setProblemCollapsed(false);
    setFocusMode(false);
  };

  // problem-card & output-panel collapse
  const [problemCollapsed, setProblemCollapsed] = useState(false);
  const [outputCollapsed, setOutputCollapsed] = useState(false);

  const hasUnsaved =
    selectedSession &&
    (selectedSession.title !== title ||
      selectedSession.language !== language ||
      selectedSession.code !== code);

  useEffect(() => {
    setCodeCourseId(normalizeSubject(subject));
  }, [subject, normalizeSubject]);

  // ── Code Diagnostics ── (declared BEFORE useEffects that reference it)
  const clearDiagnostics = useCallback(() => {
    setDiagnostics([]);
    setDiagnosticSummary({ errors: 0, warnings: 0 });
    setDiagnosticErrors(0);
    setDiagnosticWarnings(0);
    const monaco = monacoRef.current;
    const editor = editorRef.current;
    const model = editor?.getModel?.();
    if (monaco && model) {
      monaco.editor.setModelMarkers(model, "codestudio", []);
      diagnosticDecorationsRef.current = editor.deltaDecorations(
        diagnosticDecorationsRef.current,
        []
      );
    }
  }, []);

  const applyDiagnosticsToEditor = useCallback((items) => {
    const monaco = monacoRef.current;
    const editor = editorRef.current;
    const model = editor?.getModel?.();
    if (!monaco || !editor || !model) return;

    const markers = items.map((item) => {
      const severity = item.severity === "warning"
        ? monaco.MarkerSeverity.Warning
        : monaco.MarkerSeverity.Error;
      return {
        severity,
        message: item.message || "Diagnostic issue",
        source: item.source || "diagnostics",
        startLineNumber: Math.max(1, item.line || 1),
        startColumn: Math.max(1, item.column || 1),
        endLineNumber: Math.max(1, item.endLine || item.line || 1),
        endColumn: Math.max(2, item.endColumn || (item.column || 1) + 1),
      };
    });

    const decorations = items.map((item) => ({
      range: new monaco.Range(
        Math.max(1, item.line || 1),
        1,
        Math.max(1, item.line || 1),
        1
      ),
      options: {
        isWholeLine: true,
        glyphMarginClassName:
          item.severity === "warning"
            ? "code-diagnostic-glyph code-diagnostic-glyph--warning"
            : "code-diagnostic-glyph code-diagnostic-glyph--error",
        overviewRuler: {
          color: item.severity === "warning" ? "#facc15" : "#ef4444",
          position: monaco.editor.OverviewRulerLane.Right,
        },
        minimap: {
          color: item.severity === "warning" ? "#facc15" : "#ef4444",
          position: monaco.editor.MinimapPosition.Inline,
        },
      },
    }));

    monaco.editor.setModelMarkers(model, "codestudio", markers);
    diagnosticDecorationsRef.current = editor.deltaDecorations(
      diagnosticDecorationsRef.current,
      decorations
    );
  }, []);

  const diagnoseCode = useCallback(async (currentCode, currentLanguage, options = {}) => {
    if (!currentCode || !currentCode.trim()) {
      setDiagnosticStatus("idle");
      setDiagnosticsLoading(false);
      clearDiagnostics();
      lastDiagnosedCodeRef.current = "";
      lastDiagnosedLanguageRef.current = "";
      return { status: "idle", errors: [], warnings: [] };
    }
    if (
      !options.force &&
      currentCode === lastDiagnosedCodeRef.current &&
      currentLanguage === lastDiagnosedLanguageRef.current
    ) {
      setDiagnosticsLoading(false);
      return {
        status: diagnosticStatus,
        errors: diagnostics.filter((item) => item.severity === "error"),
        warnings: diagnostics.filter((item) => item.severity === "warning"),
      };
    }
    lastDiagnosedCodeRef.current = currentCode;
    lastDiagnosedLanguageRef.current = currentLanguage;

    setDiagnosticStatus("checking");
    setDiagnosticsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/code/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: currentLanguage, code: currentCode }),
      });
      const data = await safeJson(res);
      if (data.status === "unsupported") {
        setDiagnosticStatus("unsupported");
        clearDiagnostics();
      } else {
        const errorItems = (data.errors || []).map((item) => ({ ...item, severity: "error" }));
        const warningItems = (data.warnings || []).map((item) => ({ ...item, severity: "warning" }));
        const nextDiagnostics = [...errorItems, ...warningItems].sort((a, b) => {
          if ((a.line || 1) !== (b.line || 1)) return (a.line || 1) - (b.line || 1);
          return (a.column || 1) - (b.column || 1);
        });
        const errCount = errorItems.length;
        const warnCount = warningItems.length;
        setDiagnostics(nextDiagnostics);
        setDiagnosticSummary({ errors: errCount, warnings: warnCount });
        setDiagnosticErrors(errCount);
        setDiagnosticWarnings(warnCount);
        if (errCount > 0) setDiagnosticStatus("error");
        else if (warnCount > 0) setDiagnosticStatus("warning");
        else setDiagnosticStatus("ok");
        applyDiagnosticsToEditor(nextDiagnostics);
        if (nextDiagnostics.length > 0 && !focusMode) {
          setShowFeedbackPanel(true);
          setOutputPanelTab("problems");
        }
      }
      return data;
    } catch {
      setDiagnosticStatus("idle");
      return { status: "idle", errors: [], warnings: [] };
    } finally {
      setDiagnosticsLoading(false);
    }
  }, [applyDiagnosticsToEditor, clearDiagnostics, diagnosticStatus, diagnostics, focusMode]);

  // Clear stale gen-modal data when course changes
  useEffect(() => {
    setGenKnowledgePoints([]);
    setGenMaterials([]);
    setSelectedGenKpIds([]);
    setSelectedGenMaterialIds([]);
    setGenDataError("");
  }, [codeCourseId]);

  // Debounced code diagnostics
  useEffect(() => {
    if (diagnoseTimerRef.current) clearTimeout(diagnoseTimerRef.current);
    if (!code || !code.trim()) {
      setDiagnosticStatus("idle");
      clearDiagnostics();
      return undefined;
    }
    diagnoseTimerRef.current = setTimeout(() => {
      diagnoseCode(code, language);
    }, 800);
    return () => {
      if (diagnoseTimerRef.current) clearTimeout(diagnoseTimerRef.current);
    };
  }, [code, language, diagnoseCode, clearDiagnostics]);

  // Clear diagnostics when switching languages
  useEffect(() => {
    lastDiagnosedCodeRef.current = "";
    lastDiagnosedLanguageRef.current = "";
    setDiagnosticStatus("idle");
    clearDiagnostics();
  }, [language, clearDiagnostics]);

  useEffect(() => {
    if (aiEndRef.current) {
      aiEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [aiMessages]);

  const loadSessions = async () => {
    if (!user?.username) return;
    setSessionsLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      const course = normalizeSubject(codeCourseId);
      if (course) query.set("course_id", course);
      const res = await fetch(`${API_BASE}/code/sessions?${query.toString()}`);
      const data = await safeJson(res);
      if (res.ok) {
        setSessions(data.sessions || []);
        if (!selectedSession && data.sessions?.length > 0) {
          selectSession(data.sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to load code sessions:", error);
    } finally {
      setSessionsLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [user?.username, codeCourseId]);

  const loadMessages = async (sessionId) => {
    if (!user?.username || !sessionId) return;
    setAiMessagesLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/sessions/${sessionId}/messages?username=${encodeURIComponent(user.username)}`
      );
      const data = await safeJson(res);
      if (res.ok) {
        setAiMessages(data.messages || []);
      }
    } catch (error) {
      console.error("Failed to load code AI messages:", error);
    } finally {
      setAiMessagesLoading(false);
    }
  };

  const selectSession = (session) => {
    setSelectedSession(session);
    setTitle(session.title);
    setLanguage(session.language);
    setCode(session.code);
    setAiMessages([]);
    setAiQuestion("");
    setShowFeedbackPanel(false);
    setFeedbackContent("");
    setFeedbackStatus(null);
    setCodeTruncated(false);
    setRunResult(null);
    setTestResults(null);
    setTestExplanations({});
    setExplainingTestCase({});
    setOutputPanelTab("feedback");
    setProblemCollapsed(false);
    setProblemTab("io");
    setProblemError("");
    setSavedChats([]);
    setSavedMsgIds(new Set());

    if (session.id) {
      loadMessages(session.id);
      if (session.challenge_id) {
        // stale-while-revalidate: show cached or session-derived data first
        const cached = challengeCacheRef.current.get(session.challenge_id);
        if (cached) {
          setCurrentChallenge(cached);
        } else {
          // Build fallback challenge from session data so the panel shows immediately
          setCurrentChallenge({
            id: session.challenge_id,
            title: session.title || "未命名题目",
            difficulty: "",
            description: "",
            requirements: "",
            input_format: "",
            output_format: "",
            examples: "",
            hints: "",
            starter_code: "",
            test_cases: "[]",
            _fallback: true,
          });
        }
        setProblemLoading(true);
        loadChallenge(session.challenge_id);
        loadSavedChats(session.challenge_id);
      } else {
        // Clear challenge when switching to a non-challenge session
        setCurrentChallenge(null);
        setProblemLoading(false);
        setSavedChats([]);
        setSavedMsgIds(new Set());
      }
    }
  };

  const newSession = () => {
    const newS = {
      id: null,
      title: "未命名练习",
      language: "Python",
      code: CODE_TEMPLATES["Python"],
      course_id: normalizeSubject(codeCourseId),
      username: user?.username || "",
      session_type: "normal",
    };
    setSelectedSession(newS);
    setTitle(newS.title);
    setLanguage(newS.language);
    setCode(newS.code);
    setAiMessages([]);
    setAiQuestion("");
    setCurrentChallenge(null);
    setProblemLoading(false);
    setProblemError("");
    setSavedChats([]);
    setSavedMsgIds(new Set());
    setShowFeedbackPanel(false);
    setFeedbackContent("");
    setFeedbackStatus(null);
    setCodeTruncated(false);
    setRunResult(null);
    setTestResults(null);
    setTestExplanations({});
    setExplainingTestCase({});
    setOutputPanelTab("feedback");
    setProblemCollapsed(false);
    setProblemTab("io");
  };

  const loadChallenge = async (challengeId) => {
    if (!user?.username || !challengeId) {
      setProblemLoading(false);
      return;
    }
    // Keep existing challenge data visible while loading
    setProblemError("");
    try {
      const res = await fetchWithTimeout(
        `${API_BASE}/code/challenges/${challengeId}?username=${encodeURIComponent(user.username)}`,
        {},
        10000
      );
      const data = await safeJson(res);
      if (res.ok && data.challenge) {
        console.debug("[loadChallenge] loaded challenge", challengeId, data.challenge.title);
        setCurrentChallenge(data.challenge);
        // Update cache
        challengeCacheRef.current.set(challengeId, data.challenge);
        setProblemTab("io");
      } else {
        const statusCode = res.status;
        console.warn("[loadChallenge] failed to load challenge", challengeId, statusCode, data);
        // Keep existing content, show error only if we have nothing to show
        if (!challengeCacheRef.current.has(challengeId)) {
          setProblemError(`题目详情加载失败 (${statusCode || "网络错误"})。已保留本地已有内容。请点击重新加载。`);
        }
      }
    } catch (error) {
      console.error("[loadChallenge] error loading challenge:", challengeId, error?.message || error);
      if (!challengeCacheRef.current.has(challengeId)) {
        const msg = error?.name === "AbortError"
          ? "题目详情加载超时。已保留本地已有内容。请点击重新加载。"
          : "题目详情加载失败，已保留本地已有内容。请点击重新加载。";
        setProblemError(msg);
      }
    } finally {
      setProblemLoading(false);
    }
  };

  // ── Interactive Terminal ──

  // HTTP fallback when WebSocket is unavailable
  const runTerminalHttpFallback = useCallback(async (term, reason) => {
    term.writeln(`\x1b[33m交互终端不可用: ${reason}\x1b[0m`);
    term.writeln("\x1b[33m已回退到普通运行模式（/code/execute）。\x1b[0m");
    try {
      const res = await fetch(`${API_BASE}/code/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user?.username || "anonymous",
          session_id: selectedSession?.id || 0,
          language,
          code,
          stdin,
        }),
      });
      const data = await safeJson(res);
      const result = {
        stdout: data.stdout || "",
        stderr: data.stderr || "",
        exit_code: res.ok ? data.exit_code : -1,
        duration_ms: data.duration_ms || 0,
        timed_out: data.timed_out || false,
        error_message: res.ok ? data.error_message || null : data.detail || "运行请求失败",
        compile_error: data.compile_error || null,
        compiled: data.compiled,
        stdout_truncated: data.stdout_truncated || false,
        stderr_truncated: data.stderr_truncated || false,
      };
      setRunResult(result);
      terminalOutputRef.current = {
        stdout: result.stdout,
        stderr: result.stderr,
        compile_error: result.compile_error || "",
        exit_code: result.exit_code,
        timed_out: result.timed_out,
      };
      term.writeln(`\x1b[90m═══ 普通运行模式（非交互） ═══\x1b[0m`);
      if (result.error_message) term.writeln(`\x1b[31m${result.error_message}\x1b[0m`);
      if (result.compile_error) term.writeln(`\x1b[31m${result.compile_error}\x1b[0m`);
      if (result.stdout) term.write(result.stdout);
      if (result.stderr) term.write(`\x1b[31m${result.stderr}\x1b[0m`);
      if (!result.stdout && !result.stderr && !result.compile_error && !result.error_message) {
        term.writeln("(无输出)");
      }
      setTerminalExitCode(result.exit_code);
      term.writeln(`\n\x1b[90m进程结束，exit_code: ${result.exit_code}${result.timed_out ? " (超时)" : ""}\x1b[0m`);
    } catch (error) {
      console.error("[Terminal] HTTP fallback failed:", error);
      setTerminalExitCode(-1);
      term.writeln("\x1b[31m运行失败：无法连接到后端 /code/execute。\x1b[0m");
      term.writeln("\x1b[90m进程结束，exit_code: -1\x1b[0m");
    } finally {
      setTerminalRunning(false);
    }
  }, [code, language, selectedSession?.id, stdin, user?.username]);

  const launchInteractiveTerminal = useCallback(async () => {
    if (!code.trim() || terminalRunning) return;

    // Dispose old terminal
    if (terminalRef.current) {
      terminalRef.current.dispose();
      terminalRef.current = null;
    }
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }

    terminalOutputRef.current = { stdout: "", stderr: "", compile_error: "", exit_code: null, timed_out: false };
    setTerminalExitCode(null);
    setTerminalRunning(true);
    setShowFeedbackPanel(true);
    setOutputPanelTab("terminal");

    // Create terminal after DOM update
    setTimeout(() => {
      const container = terminalContainerRef.current;
      if (!container) return;

      const term = new Terminal({
        fontSize: 13,
        fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
        theme: { background: "#1e1e1e", foreground: "#d4d4d4", cursor: "#ffffff" },
        cursorBlink: true,
        cols: 80,
        rows: 24,
      });
      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(container);
      fitAddon.fit();
      fitAddonRef.current = fitAddon;
      terminalRef.current = term;

      term.writeln(`\x1b[1;36m═══ 交互终端 ── ${language.toUpperCase()} ═══\x1b[0m`);

      // Connect WebSocket with fallback
      const primaryWsUrl = getTerminalWsUrl();
      const alternateWsUrl = `${getWsBase()}/api/code/interactive-run`;
      let wsAttempt = 0;
      let switchingWs = false;

      function connectWs(url, label) {
        wsAttempt++;
        if (wsAttempt === 1) {
          console.info("[Terminal] Connecting WebSocket (primary):", url);
        } else {
          console.info("[Terminal] Connecting WebSocket (alternate):", url);
          term.writeln(`\x1b[33m试用备用端点: ${url}\x1b[0m`);
        }
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          console.info("[Terminal] WebSocket connected:", url);
          if (switchingWs) term.writeln("\x1b[90m已连接\x1b[0m");
          ws.send(JSON.stringify({ language, code, username: user?.username || "anonymous", session_id: selectedSession?.id || null }));
        };

        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data);
            if (msg.type === "stdout") {
              term.write(msg.data);
              terminalOutputRef.current.stdout += msg.data;
            } else if (msg.type === "stderr") {
              term.write(`\x1b[31m${msg.data}\x1b[0m`);
              terminalOutputRef.current.stderr += msg.data;
            } else if (msg.type === "compile_error") {
              term.writeln(`\x1b[31m${msg.message}\x1b[0m`);
              terminalOutputRef.current.compile_error = msg.message;
            } else if (msg.type === "status") {
              term.writeln(`\x1b[90m${msg.message}\x1b[0m`);
            } else if (msg.type === "error") {
              term.writeln(`\x1b[31m✗ ${msg.message}\x1b[0m`);
            } else if (msg.type === "exit") {
              terminalOutputRef.current.exit_code = msg.exit_code;
              terminalOutputRef.current.timed_out = msg.timed_out || false;
              if (msg.stdout) terminalOutputRef.current.stdout = msg.stdout;
              if (msg.stderr) terminalOutputRef.current.stderr = msg.stderr;
              setTerminalExitCode(msg.exit_code);
              setTerminalRunning(false);
              term.writeln(`\n\x1b[90m═══ 进程退出，exit_code: ${msg.exit_code}${msg.timed_out ? " (超时)" : ""} ═══\x1b[0m`);
            }
          } catch {}
        };

        ws.onerror = (event) => {
          console.error("[Terminal] WebSocket error:", url, event);
          if (wsAttempt < 2) {
            switchingWs = true;
            connectWs(alternateWsUrl, "alternate");
          } else {
            term.writeln(`\x1b[31mWebSocket 连接失败：${url}\x1b[0m`);
            term.writeln("\x1b[33m交互终端不可用，正在回退到普通运行模式...\x1b[0m");
            runTerminalHttpFallback(term, "WebSocket 连接失败");
          }
        };

        ws.onclose = () => {
          if (!switchingWs && wsAttempt < 2) setTerminalRunning(false);
        };
      }

      connectWs(primaryWsUrl, "primary");

      term.onData((data) => {
        const activeWs = wsRef.current;
        if (activeWs && activeWs.readyState === WebSocket.OPEN) {
          const stdinData = data.replace(/\r/g, "\n");
          activeWs.send(JSON.stringify({ type: "stdin", data: stdinData }));
          if (data === "\r") {
            term.write("\r\n");
          } else if (data === "\u007f") {
            term.write("\b \b");
          } else {
            term.write(data);
          }
        }
      });
    }, 100);
  }, [code, language, user?.username, terminalRunning, runTerminalHttpFallback, selectedSession?.id]);

  const stopInteractiveTerminal = useCallback(() => {
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }
    if (terminalRef.current) {
      terminalRef.current.writeln(`\n\x1b[33m═══ 用户终止运行 ═══\x1b[0m`);
      setTerminalRunning(false);
      setTerminalExitCode(-1);
    }
  }, []);

  const clearInteractiveTerminal = useCallback(() => {
    if (terminalRef.current) {
      terminalRef.current.clear();
    }
    terminalOutputRef.current = { stdout: "", stderr: "", compile_error: "", exit_code: null, timed_out: false };
    setTerminalExitCode(null);
  }, []);

  const openChallengeModal = async () => {
    setChallengeDifficulty("基础");
    setChallengeFocus("");
    setChallengeCount(1);
    setChallengeGenError("");
    setChallengeExtraReq("");
    setSelectedGenKpIds([]);
    setSelectedGenMaterialIds([]);
    // Clear stale data before showing modal — prevents cross-course data leak
    setGenKnowledgePoints([]);
    setGenMaterials([]);
    setGenDataError("");
    setShowChallengeModal(true);

    // Load knowledge points & materials for current course
    const normalizedCourse = normalizeSubject(codeCourseId, "");
    if (!user?.username) {
      setGenDataError("请先登录后再生成题目。");
      return;
    }
    if (!normalizedCourse) {
      setGenDataError("请先选择课程后再生成题目。");
      return;
    }
    setGenDataLoading(true);
    try {
      const [kpRes, matRes] = await Promise.all([
        fetch(`${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(normalizedCourse)}`),
        fetch(`${API_BASE}/materials?username=${encodeURIComponent(user.username)}&subject=${encodeURIComponent(normalizedCourse)}`),
      ]);
      const [kpData, matData] = await Promise.all([safeJson(kpRes), safeJson(matRes)]);
      const loadErrors = [];
      if (kpRes.ok) {
        setGenKnowledgePoints(kpData.knowledge_points || []);
      } else {
        loadErrors.push(kpData.detail || "知识点数据加载失败，请稍后重试。");
      }
      if (matRes.ok) {
        setGenMaterials(matData.materials || []);
      } else {
        loadErrors.push(matData.detail || "课程资料加载失败，请稍后重试。");
      }
      if (loadErrors.length > 0) {
        setGenDataError(loadErrors.join("；"));
      }
    } catch (error) {
      console.error("Failed to load gen-modal data:", error);
      setGenDataError("当前课程知识点或资料加载失败。请检查网络后重试。");
    } finally {
      setGenDataLoading(false);
    }
  };

  const generateChallenge = async () => {
    if (!user?.username) return;
    setChallengeGenerating(true);
    setChallengeGenError("");
    try {
      const res = await fetch(`${API_BASE}/code/challenges/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language,
          difficulty: challengeDifficulty,
          focus: challengeFocus,
          count: challengeCount,
          knowledge_point_ids: selectedGenKpIds.length > 0 ? selectedGenKpIds : undefined,
          knowledge_text: challengeFocus,
          material_ids: selectedGenMaterialIds.length > 0 ? selectedGenMaterialIds : undefined,
          extra_requirement: challengeExtraReq || undefined,
        }),
      });
      const data = await safeJson(res);
      if (res.ok && data.sessions && data.sessions.length > 0) {
        setShowChallengeModal(false);
        setChallengeFocus("");
        setChallengeExtraReq("");
        // Set challenge and session BEFORE loadSessions to avoid flash of "自由练习"
        const firstSession = data.sessions[0];
        const firstChallenge = data.challenges?.[0];
        if (firstChallenge) {
          setCurrentChallenge(firstChallenge);
          challengeCacheRef.current.set(firstChallenge.id, firstChallenge);
          loadSavedChats(firstChallenge.id);
        }
        setSelectedSession(firstSession);
        setTitle(firstSession.title);
        setLanguage(firstSession.language);
        setCode(firstSession.code || "");
        setProblemCollapsed(false);
        setProblemTab("io");
        setProblemLoading(false);
        setProblemError("");
        // Refresh sidebar list
        await loadSessions();
        const generatedCount = data.sessions.length;
        setTip(`AI 已生成 ${generatedCount} 道题目`);
        setTimeout(() => setTip(""), 3000);
      } else if (res.status === 429) {
        setChallengeGenError("今日 AI 使用次数已达上限，请明天再试或升级套餐");
      } else {
        setChallengeGenError(data.detail || "AI 出题失败，请重试");
      }
    } catch (error) {
      console.error("Failed to generate challenge:", error);
      setChallengeGenError("AI 出题失败，请检查网络连接后重试");
    } finally {
      setChallengeGenerating(false);
    }
  };

  const saveSession = async () => {
    if (!user?.username) return;
    setSaving(true);
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(codeCourseId),
        title,
        language,
        code,
      };
      let res;
      if (selectedSession?.id) {
        res = await fetch(`${API_BASE}/code/sessions/${selectedSession.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        res = await fetch(`${API_BASE}/code/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      const data = await safeJson(res);
      if (res.ok && data.session) {
        setSelectedSession(data.session);
        setTitle(data.session.title);
        setLanguage(data.session.language);
        setCode(data.session.code);
        setTip("保存成功");
        setTimeout(() => setTip(""), 2000);
        loadSessions();
      } else {
        setTip(data.detail || "保存失败");
      }
    } catch (error) {
      console.error("Failed to save code session:", error);
      setTip("保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    if (!selectedSession?.id && (!code || code === CODE_TEMPLATES[language])) {
      setCode(CODE_TEMPLATES[newLang]);
    }
  };

  const runCode = async () => {
    if (!code.trim()) {
      setTip("请先输入代码再运行。");
      return;
    }
    await diagnoseCode(code, language, { force: true });
    setRunning(true);
    setRunResult(null);
    setShowFeedbackPanel(true);
    setOutputPanelTab("run");

    try {
      const res = await fetch(`${API_BASE}/code/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          session_id: selectedSession?.id || 0,
          language,
          code,
          stdin,
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setRunResult({
          stdout: data.stdout || "",
          stderr: data.stderr || "",
          exit_code: data.exit_code,
          duration_ms: data.duration_ms || 0,
          timed_out: data.timed_out || false,
          error_message: data.error_message || null,
          compile_error: data.compile_error || null,
          compiled: data.compiled,
          stdout_truncated: data.stdout_truncated || false,
          stderr_truncated: data.stderr_truncated || false,
        });
      } else if (res.status === 429) {
        setRunResult({
          stdout: "",
          stderr: "",
          exit_code: -1,
          duration_ms: 0,
          timed_out: false,
          error_message: "运行过于频繁，请稍后再试。",
        });
      } else if (res.status === 503) {
        setRunResult({
          stdout: "",
          stderr: "",
          exit_code: -1,
          duration_ms: 0,
          timed_out: false,
          error_message: "当前代码运行任务较多，请稍后重试。",
        });
      } else {
        setRunResult({
          stdout: "",
          stderr: "",
          exit_code: -1,
          duration_ms: 0,
          timed_out: false,
          error_message: data.detail || "运行请求失败",
        });
      }
    } catch (error) {
      console.error("Failed to run code:", error);
      setRunResult({
        stdout: "",
        stderr: "",
        exit_code: -1,
        duration_ms: 0,
        timed_out: false,
        error_message: "无法连接后端服务。",
      });
    } finally {
      setRunning(false);
    }
  };

  const runTests = async () => {
    if (!user?.username || !selectedSession?.challenge_id) return;
    if (!code.trim()) {
      setTip("请先编写代码再运行测试。");
      return;
    }
    if (language !== "Python" && language !== "C") {
      setTip("当前测试运行暂支持 Python 和 C");
      return;
    }
    await diagnoseCode(code, language, { force: true });
    setTesting(true);
    setTestResults(null);
    setTestExplanations({});
    setExplainingTestCase({});
    setShowFeedbackPanel(true);
    setOutputPanelTab("run");

    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${selectedSession.challenge_id}/run-tests`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            session_id: selectedSession.id,
            language,
            code,
          }),
        }
      );
      const data = await safeJson(res);
      if (res.ok) {
        setTestResults(data);
      } else if (res.status === 429) {
        setTestResults({
          total: 0,
          passed: 0,
          results: [],
          error_message: "运行测试过于频繁，每分钟最多运行 5 次，请稍后再试。",
        });
      } else if (res.status === 503) {
        setTestResults({
          total: 0,
          passed: 0,
          results: [],
          error_message: "当前代码运行任务较多，请稍后重试。",
        });
      } else {
        setTestResults({
          total: 0,
          passed: 0,
          results: [],
          error_message: data.detail || "运行测试失败",
        });
      }
    } catch (error) {
      console.error("Failed to run tests:", error);
      setTestResults({
        total: 0,
        passed: 0,
        results: [],
        error_message: "无法连接后端服务。",
      });
    } finally {
      setTesting(false);
    }
  };

  const explainFailure = async (tcIndex) => {
    if (!user?.username || !selectedSession?.challenge_id || !testResults) return;

    const tc = testResults.results[tcIndex];
    if (!tc) return;

    setExplainingTestCase((prev) => ({ ...prev, [tcIndex]: true }));

    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${selectedSession.challenge_id}/explain-failure`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            session_id: selectedSession.id,
            language,
            code,
            test_case: {
              input: tc.input || "",
              expected_output: tc.expected_output || "",
              description: tc.description || "",
            },
            actual_output: tc.actual_output || "",
            stderr: tc.stderr || "",
            exit_code: tc.exit_code ?? 0,
            timed_out: tc.timed_out || false,
          }),
        }
      );
      const data = await safeJson(res);

      if (res.ok) {
        setTestExplanations((prev) => ({ ...prev, [tcIndex]: data.explanation || "" }));
      } else if (res.status === 429) {
        setTestExplanations((prev) => ({
          ...prev,
          [tcIndex]: "今日 AI 使用次数已达上限，请明天再试或升级套餐。",
        }));
      } else {
        setTestExplanations((prev) => ({
          ...prev,
          [tcIndex]: data.detail || "AI 解释失败，请稍后重试。",
        }));
      }
    } catch (error) {
      console.error("Failed to explain failure:", error);
      setTestExplanations((prev) => ({
        ...prev,
        [tcIndex]: "无法连接后端服务。",
      }));
    } finally {
      setExplainingTestCase((prev) => ({ ...prev, [tcIndex]: false }));
    }
  };

  const generateTests = async () => {
    if (!user?.username || !selectedSession?.challenge_id) return;
    if (language !== "Python" && language !== "C") {
      setTip("当前测试用例生成暂支持 Python 和 C");
      return;
    }
    setGeneratingTests(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${selectedSession.challenge_id}/generate-tests`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            language,
          }),
        }
      );
      const data = await safeJson(res);
      if (res.ok && data.success) {
        if (data.test_cases && data.test_cases !== "[]") {
          setTip(data.message || "测试用例已生成");
          setTimeout(() => setTip(""), 2000);
          // Refresh challenge to get updated test_cases
          loadChallenge(selectedSession.challenge_id);
        } else {
          setTip(data.message || "生成测试用例失败，请重试");
          setTimeout(() => setTip(""), 4000);
        }
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || data.message || "生成测试用例失败，请重试");
      }
    } catch (error) {
      console.error("Failed to generate tests:", error);
      setTip("生成测试用例失败，请稍后重试");
    } finally {
      setGeneratingTests(false);
    }
  };

  const retryChallenge = async () => {
    if (!user?.username || !selectedAttempt?.challenge_id) return;
    try {
      const body = {
        username: user.username,
        course_id: normalizeSubject(codeCourseId),
        title: `复做：${selectedAttempt.challenge_title || "未命名题目"}`,
        language: selectedAttempt.language || "Python",
        code: selectedAttempt.code || CODE_TEMPLATES[selectedAttempt.language || "Python"],
        challenge_id: selectedAttempt.challenge_id,
      };
      const res = await fetch(`${API_BASE}/code/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await safeJson(res);
      if (res.ok && data.session) {
        // Close attempt history and switch to the new session
        setShowAttemptHistory(false);
        setSelectedAttempt(null);
        setShowFeedbackPanel(false);
        setRunResult(null);
        setTestResults(null);
        setTestExplanations({});
        setExplainingTestCase({});
        setOutputPanelTab("feedback");
        await loadSessions();
        selectSession(data.session);  // selectSession handles loadChallenge + loadSavedChats
        setTip("已创建复做练习");
        setTimeout(() => setTip(""), 2000);
      } else {
        setTip(data.detail || "创建复做练习失败");
      }
    } catch (error) {
      console.error("Failed to retry challenge:", error);
      setTip("创建复做练习失败，请稍后重试");
    }
  };

  const loadAttempts = async () => {
    if (!user?.username) return;
    setAttemptsLoading(true);
    try {
      const params = new URLSearchParams({ username: user.username, limit: "30" });
      if (attemptFilter !== "all" && attemptFilter !== "mastered" && attemptFilter !== "unmastered") {
        params.set("status", attemptFilter);
      }
      if (normalizeSubject(codeCourseId)) params.set("course_id", normalizeSubject(codeCourseId));
      const res = await fetch(`${API_BASE}/code/attempts?${params.toString()}`);
      const data = await safeJson(res);
      if (res.ok) {
        let list = data.attempts || [];
        if (attemptFilter === "mastered") list = list.filter((a) => a.mastered === 1);
        if (attemptFilter === "unmastered") list = list.filter((a) => a.mastered !== 1);
        setAttempts(list);
      }
    } catch (error) {
      console.error("Failed to load attempts:", error);
    } finally {
      setAttemptsLoading(false);
    }
  };

  const loadAttemptDetail = async (attemptId) => {
    if (!user?.username || !attemptId) return;
    setAttemptDetailLoading(true);
    setSelectedAttempt(null);
    try {
      const res = await fetch(
        `${API_BASE}/code/attempts/${attemptId}?username=${encodeURIComponent(user.username)}`
      );
      const data = await safeJson(res);
      if (res.ok) {
        setSelectedAttempt(data.attempt);
      }
    } catch (error) {
      console.error("Failed to load attempt detail:", error);
    } finally {
      setAttemptDetailLoading(false);
    }
  };

  const toggleMastered = async (attemptId, currentMastered) => {
    if (!user?.username || !attemptId) return;
    setTogglingMastered((prev) => ({ ...prev, [attemptId]: true }));
    const newMastered = currentMastered ? 0 : 1;
    try {
      const res = await fetch(`${API_BASE}/code/attempts/${attemptId}/mastered`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, mastered: newMastered }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setAttempts((prev) =>
          prev.map((a) =>
            a.id === attemptId ? { ...a, mastered: data.mastered } : a
          )
        );
        if (selectedAttempt?.id === attemptId) {
          setSelectedAttempt((prev) => prev ? { ...prev, mastered: data.mastered, mastered_at: data.mastered_at } : prev);
        }
      }
    } catch (error) {
      console.error("Failed to toggle mastered:", error);
    } finally {
      setTogglingMastered((prev) => ({ ...prev, [attemptId]: false }));
      loadCodeProgress();
    }
  };

  const loadCodeProgress = async () => {
    if (!user?.username) return;
    try {
      const params = new URLSearchParams({ username: user.username });
      const course = normalizeSubject(codeCourseId);
      if (course) params.set("course_id", course);
      const res = await fetch(`${API_BASE}/code/progress?${params.toString()}`);
      const data = await safeJson(res);
      if (res.ok) {
        setCodeProgress(data);
      }
    } catch (error) {
      console.error("Failed to load code progress:", error);
    }
  };

  useEffect(() => {
    if (showAttemptHistory) {
      loadAttempts();
    }
  }, [showAttemptHistory, attemptFilter]);

  useEffect(() => {
    if (user?.username) {
      loadCodeProgress();
    }
  }, [user?.username, codeCourseId]);

  const analyzeCode = async () => {
    if (!code.trim()) {
      setTip("请先输入代码再进行分析。");
      return;
    }
    if (!aiQuestion.trim()) {
      setTip("请输入要分析的问题。");
      return;
    }
    setAiLoading(true);
    setCodeTruncated(false);
    const userMsg = { role: "user", content: aiQuestion };
    setAiMessages((prev) => [...prev, userMsg]);
    const question = aiQuestion;
    setAiQuestion("");

    try {
      const latestDiagnostics = await diagnoseCode(code, language, { force: true });
      const res = await fetch(`${API_BASE}/code/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          session_id: selectedSession?.id || null,
          challenge_id: currentChallenge?.id || selectedSession?.challenge_id || null,
          language,
          code,
          question,
          last_run_result: runResult,
          last_test_results: testResults,
          diagnostics: {
            status: latestDiagnostics?.status || diagnosticStatus,
            errors: latestDiagnostics?.errors || diagnostics.filter((item) => item.severity === "error"),
            warnings: latestDiagnostics?.warnings || diagnostics.filter((item) => item.severity === "warning"),
          },
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        if (data.code_truncated) {
          setCodeTruncated(true);
        }
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.answer },
        ]);
      } else if (res.status === 429) {
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: "今日 AI 使用次数已达上限，请明天再试或升级套餐。" },
        ]);
      } else {
        setAiMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.detail || "AI 分析失败，请稍后重试。" },
        ]);
      }
    } catch (error) {
      console.error("Failed to analyze code:", error);
      setAiMessages((prev) => [
        ...prev,
        { role: "assistant", content: "无法连接后端服务。" },
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!user?.username || !selectedSession?.challenge_id) return;
    if (!code.trim()) {
      setTip("请先编写代码再提交判定。");
      return;
    }
    setSubmitting(true);
    setShowFeedbackPanel(true);
    setOutputPanelTab("feedback");
    setFeedbackContent("");
    setFeedbackStatus(null);

    try {
      const res = await fetch(
        `${API_BASE}/code/challenges/${selectedSession.challenge_id}/submit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: user.username,
            session_id: selectedSession.id,
            code,
            language,
          }),
        }
      );
      const data = await safeJson(res);
      if (res.ok) {
        setFeedbackContent(data.ai_feedback || "");
        setFeedbackStatus(data.status || "unknown");
        if (selectedSession?.id) {
          loadMessages(selectedSession.id);
        }
        loadCodeProgress();
      } else if (res.status === 429) {
        setFeedbackContent(
          "## 额度不足\n\n今日 AI 使用次数已达上限，请明天再试或升级套餐。"
        );
        setFeedbackStatus("unknown");
      } else {
        setFeedbackContent(
          `## 提交失败\n\n${data.detail || "请稍后重试"}`
        );
        setFeedbackStatus("unknown");
      }
    } catch (error) {
      console.error("Failed to submit answer:", error);
      setFeedbackContent("## 提交失败\n\n无法连接后端服务。");
      setFeedbackStatus("unknown");
    } finally {
      setSubmitting(false);
    }
  };

  // ── AI Coach saved chats ──
  const loadSavedChats = async (challengeId) => {
    if (!user?.username || !challengeId) return;
    setSavedChatsLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/ai-coach/saved-chats?username=${encodeURIComponent(user.username)}&challenge_id=${challengeId}`
      );
      const data = await safeJson(res);
      if (res.ok && data.items) {
        setSavedChats(data.items);
        setSavedMsgIds(new Set(data.items.map((item) => item.id)));
      }
    } catch (error) {
      console.error("Failed to load saved chats:", error);
    } finally {
      setSavedChatsLoading(false);
    }
  };

  const saveChat = async (msgIndex) => {
    const msg = aiMessages[msgIndex];
    if (!msg || msg.role !== "assistant" || !user?.username) return;
    if (!currentChallenge?.id) {
      setTip("当前题目未加载完成，暂不能保存记录");
      setTimeout(() => setTip(""), 3000);
      return;
    }
    setSavingMsgIndex(msgIndex);
    try {
      // Find the preceding user message
      const userMsg = msgIndex > 0 && aiMessages[msgIndex - 1]?.role === "user"
        ? aiMessages[msgIndex - 1].content : "";
      const res = await fetch(`${API_BASE}/code/ai-coach/saved-chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          challenge_id: currentChallenge.id,
          session_id: selectedSession?.id || null,
          language,
          user_message: userMsg,
          assistant_message: msg.content,
          code_snapshot: code,
        }),
      });
      const data = await safeJson(res);
      if (res.ok && data.saved_chat) {
        setSavedChats((prev) => [...prev, data.saved_chat]);
        setSavedMsgIds((prev) => new Set([...prev, data.saved_chat.id]));
        setTip("已保存");
        setTimeout(() => setTip(""), 1500);
      } else {
        setTip(data.detail || "保存失败");
        setTimeout(() => setTip(""), 3000);
      }
    } catch (error) {
      console.error("Failed to save chat:", error);
      setTip("保存失败，请稍后重试");
      setTimeout(() => setTip(""), 3000);
    } finally {
      setSavingMsgIndex(null);
    }
  };

  const deleteSavedChat = async (savedId) => {
    if (!user?.username || !savedId) return;
    setDeletingSavedId(savedId);
    try {
      const res = await fetch(
        `${API_BASE}/code/ai-coach/saved-chats/${savedId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await safeJson(res);
      if (res.ok) {
        setSavedChats((prev) => prev.filter((sc) => sc.id !== savedId));
        setSavedMsgIds((prev) => {
          const next = new Set(prev);
          next.delete(savedId);
          return next;
        });
        setTip("已取消保存");
        setTimeout(() => setTip(""), 1500);
      } else {
        setTip(data.detail || "删除失败");
        setTimeout(() => setTip(""), 3000);
      }
    } catch (error) {
      console.error("Failed to delete saved chat:", error);
      setTip("删除失败，请稍后重试");
      setTimeout(() => setTip(""), 3000);
    } finally {
      setDeletingSavedId(null);
    }
  };

  const deleteSession = async (sessionId) => {
    if (!user?.username || !sessionId) return;
    setDeleting(true);
    try {
      const res = await fetch(
        `${API_BASE}/code/sessions/${sessionId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await safeJson(res);
      if (res.ok) {
        if (selectedSession?.id === sessionId) {
          setSelectedSession(null);
          setTitle("未命名练习");
          setLanguage("Python");
          setCode(CODE_TEMPLATES["Python"]);
          setAiMessages([]);
          setCurrentChallenge(null);
          setProblemLoading(false);
          setProblemError("");
          setSavedChats([]);
          setSavedMsgIds(new Set());
          setShowFeedbackPanel(false);
          setFeedbackContent("");
          setFeedbackStatus(null);
          setRunResult(null);
          setTestResults(null);
          setTestExplanations({});
          setExplainingTestCase({});
        }
        await loadSessions();
        setTip("练习已删除");
        setTimeout(() => setTip(""), 2000);
      } else {
        setTip(data.detail || "删除失败");
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
      setTip("删除失败，请稍后重试");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyRefFeedback(true);
      setTimeout(() => setCopyRefFeedback(false), 2000);
    } catch {
      // fallback for older browsers
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); setCopyRefFeedback(true); setTimeout(() => setCopyRefFeedback(false), 2000); } catch {}
      document.body.removeChild(ta);
    }
  };

  const useStarterCode = () => {
    const targetCode = currentChallenge?.starter_code;
    if (!targetCode) {
      setTip("该题目没有起始代码");
      setTimeout(() => setTip(""), 2000);
      return;
    }
    // If editor is empty or contains only default templates, apply directly
    const trimmed = (code || "").trim();
    const isDefault =
      !trimmed ||
      Object.values(CODE_TEMPLATES).map((t) => t.trim()).includes(trimmed) ||
      trimmed === targetCode.trim();
    if (!isDefault) {
      setPendingApplyCode(targetCode);
      setStarterConfirmOpen(true);
      return;
    }
    setCode(targetCode);
    setTip("已应用起始代码");
    setTimeout(() => setTip(""), 2000);
  };

  const confirmStarterCode = () => {
    const targetCode = pendingApplyCode || currentChallenge?.starter_code;
    if (targetCode) {
      setCode(targetCode);
      setTip("已应用起始代码");
      setTimeout(() => setTip(""), 2000);
    }
    setStarterConfirmOpen(false);
    setPendingApplyCode(null);
  };

  const fetchDiagnosis = async () => {
    if (!user?.username) return;
    setDiagnosisLoading(true);
    setDiagnosisReport(null);
    try {
      const res = await fetch(`${API_BASE}/code/learning-diagnosis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language: "",
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setDiagnosisReport(data);
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || "诊断生成失败");
      }
    } catch (error) {
      console.error("Failed to fetch diagnosis:", error);
      setTip("诊断生成失败，请稍后重试");
    } finally {
      setDiagnosisLoading(false);
    }
  };

  const generateTargetedChallenge = async () => {
    if (!user?.username || !diagnosisReport?.summary) return;
    setTargetedChallengeLoading(true);
    try {
      const diagnosisText = diagnosisReport.summary.slice(0, 2000);
      const res = await fetch(`${API_BASE}/code/challenges/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          language,
          difficulty: "基础",
          focus: "",
          diagnosis_summary: diagnosisText,
          source: "diagnosis",
        }),
      });
      const data = await safeJson(res);
      if (res.ok && data.session) {
        setDiagnosisReport(null);
        await loadSessions();
        if (data.challenge) {
          setCurrentChallenge(data.challenge);
          challengeCacheRef.current.set(data.challenge.id, data.challenge);
          loadSavedChats(data.challenge.id);
          setProblemLoading(false);
          setProblemError("");
        }
        selectSession(data.session);
        setTip("已生成针对性练习");
        setTimeout(() => setTip(""), 2000);
      } else if (res.status === 429) {
        setTip("今日 AI 使用次数已达上限，请明天再试或升级套餐");
        setTimeout(() => setTip(""), 4000);
      } else {
        setTip(data.detail || "针对性出题失败，请重试");
      }
    } catch (error) {
      console.error("Failed to generate targeted challenge:", error);
      setTip("针对性出题失败，请稍后重试");
    } finally {
      setTargetedChallengeLoading(false);
    }
  };

  const generateTasksFromDiagnosis = async () => {
    if (!user?.username || !diagnosisReport?.summary) return;
    setTaskGenerationLoading(true);
    try {
      const diagnosisText = diagnosisReport.summary.slice(0, 2000);
      const res = await fetch(`${API_BASE}/learning/tasks/from-diagnosis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: normalizeSubject(codeCourseId),
          course_name: getSubjectLabel(codeCourseId) || codeCourseId,
          diagnosis_summary: diagnosisText,
          language,
        }),
      });
      const data = await safeJson(res);
      if (res.ok) {
        setTip(data.message || `已生成 ${data.tasks?.length || 0} 个学习任务`);
        setTimeout(() => setTip(""), 3000);
      } else {
        setTip(data.detail || "生成学习任务失败");
      }
    } catch (error) {
      console.error("Failed to generate tasks from diagnosis:", error);
      setTip("生成学习任务失败，请稍后重试");
    } finally {
      setTaskGenerationLoading(false);
    }
  };

  const canRun = true; // Only Python and C remain, both are runnable
  const currentFileName = language === "C" ? "main.c" : "main.py";
  const codeLineCount = Math.max(1, String(code || "").split("\n").length);
  const warningCount = diagnosticSummary.warnings;
  const errorCount = diagnosticSummary.errors;

  const openProblemsPanel = () => {
    setShowFeedbackPanel(true);
    setOutputPanelTab("problems");
  };

  const jumpToDiagnostic = (item) => {
    const editor = editorRef.current;
    if (!editor) return;
    const lineNumber = Math.max(1, item.line || 1);
    const column = Math.max(1, item.column || 1);
    editor.revealPositionInCenter({ lineNumber, column });
    editor.setPosition({ lineNumber, column });
    editor.focus();
  };

  return (
    <section
      className={`code-studio-shell${focusMode ? " code-studio-shell--focus" : ""}${resizing ? " code-studio-shell--resizing" : ""}`}
      style={{ display: "flex", flexDirection: "row", height: "100%", overflow: "hidden" }}
    >
      {/* Left Panel — Session List */}
      {!focusMode && (
        <>
          <aside
            className={`code-studio-sidebar ${sidebarCollapsed ? "code-studio-sidebar--collapsed" : ""}`}
            style={{ width: sidebarCollapsed ? 44 : layout.leftWidth, minWidth: sidebarCollapsed ? 44 : 56, flexShrink: 0 }}
          >
        {sidebarCollapsed ? (
          <div className="code-sidebar-collapsed-bar">
            <button
              className="code-sidebar-toggle-btn"
              onClick={() => setSidebarCollapsed(false)}
              title="展开侧边栏"
            >
              &rang;&rang;
            </button>
          </div>
        ) : (
          <>
        <div className="code-studio-sidebar-header">
          <div className="code-sidebar-header-row">
            <h3>代码练习</h3>
            <button
              className="code-sidebar-toggle-btn"
              onClick={() => setSidebarCollapsed(true)}
              title="折叠侧边栏"
            >
              &lang;&lang;
            </button>
          </div>
          <div className="code-studio-course-picker">
            <select
              className="field"
              value={codeCourseId}
              onChange={(e) => {
                setCodeCourseId(e.target.value);
                setSelectedSession(null);
              }}
            >
              {courseOptions.map((item) => (
                <option key={item} value={item}>
                  {getSubjectLabel(item)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="code-studio-sidebar-actions">
          <button className="primary-button compact" onClick={newSession}>
            新建练习
          </button>
          <button
            className={`ghost-button compact ${showAttemptHistory ? "code-history-btn--active" : ""}`}
            onClick={() => { setShowAttemptHistory(!showAttemptHistory); setSelectedAttempt(null); }}
          >
            提交历史
          </button>
        </div>

        {showAttemptHistory ? (
          <div className="code-attempt-history-panel">
            {/* Filters */}
            <div className="code-attempt-filters">
              {[
                { value: "all", label: "全部" },
                { value: "failed", label: "不通过" },
                { value: "partial", label: "部分通过" },
                { value: "probable_pass", label: "通过" },
                { value: "mastered", label: "已掌握" },
                { value: "unmastered", label: "未掌握" },
              ].map((f) => (
                <button
                  key={f.value}
                  className={`code-attempt-filter-btn ${attemptFilter === f.value ? "code-attempt-filter-btn--active" : ""}`}
                  onClick={() => setAttemptFilter(f.value)}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Attempt list */}
            <div className="code-attempt-list">
              {attemptsLoading ? (
                <div className="empty-inline">加载中...</div>
              ) : attempts.length === 0 ? (
                <div className="empty-inline" style={{ padding: "24px 0" }}>
                  {attemptFilter !== "all"
                    ? "该筛选条件下暂无提交记录"
                    : "暂无提交记录，完成练习并提交判定后即可在此查看"}
                </div>
              ) : (
                attempts.map((a) => (
                  <div key={a.id}>
                    <div
                      className={`code-attempt-item ${selectedAttempt?.id === a.id ? "code-attempt-item--active" : ""}`}
                      onClick={() => {
                        if (selectedAttempt?.id === a.id) {
                          setSelectedAttempt(null);
                        } else {
                          loadAttemptDetail(a.id);
                        }
                      }}
                    >
                      <div className="code-attempt-item-header">
                        <span
                          className={`code-attempt-status-badge ${
                            a.status === "probable_pass"
                              ? "code-attempt-status--pass"
                              : a.status === "partial"
                              ? "code-attempt-status--partial"
                              : a.status === "failed"
                              ? "code-attempt-status--fail"
                              : "code-attempt-status--unknown"
                          }`}
                        >
                          {STATUS_LABELS[a.status] || a.status || "未知"}
                        </span>
                        {a.mastered === 1 && (
                          <span className="code-attempt-mastered-badge">已掌握</span>
                        )}
                      </div>
                      <div className="code-attempt-item-title">
                        {a.challenge_title || `提交 #${a.id}`}
                      </div>
                      <div className="code-attempt-item-meta">
                        {a.language && <span className="subject-pill small">{a.language}</span>}
                        {a.difficulty && <span className="subject-pill small">{a.difficulty}</span>}
                        {a.knowledge_point && (
                          <span className="subject-pill small">{a.knowledge_point}</span>
                        )}
                        <span className="code-attempt-date">{a.created_at ? formatDate(a.created_at) : ""}</span>
                      </div>
                      {a.ai_feedback_summary && (
                        <div className="code-attempt-item-summary">{a.ai_feedback_summary}</div>
                      )}
                    </div>

                    {/* Expanded detail */}
                    {selectedAttempt?.id === a.id && (
                      <div className="code-attempt-detail">
                        {attemptDetailLoading ? (
                          <div className="empty-inline" style={{ padding: "12px" }}>加载详情中...</div>
                        ) : selectedAttempt ? (
                          <>
                            {/* Challenge info */}
                            {selectedAttempt.challenge_description && (
                              <div className="code-attempt-detail-section">
                                <div className="code-attempt-detail-label">题目描述</div>
                                <p style={{ whiteSpace: "pre-wrap", fontSize: "0.82rem" }}>
                                  {selectedAttempt.challenge_description}
                                </p>
                              </div>
                            )}

                            {/* Submitted code */}
                            <div className="code-attempt-detail-section">
                              <div className="code-attempt-detail-label">提交代码</div>
                              <pre className="code-run-pre" style={{ maxHeight: 160, fontSize: "0.72rem" }}>
                                {selectedAttempt.code || "(无)"}
                              </pre>
                            </div>

                            {/* AI feedback */}
                            <div className="code-attempt-detail-section">
                              <div className="code-attempt-detail-label">AI 判定反馈</div>
                              <div className="code-attempt-detail-feedback">
                                {selectedAttempt.ai_feedback || "(无反馈)"}
                              </div>
                            </div>

                            {/* Reference solution */}
                            {selectedAttempt.challenge_reference_solution && (
                              <div className="code-attempt-detail-section">
                                <div className="code-attempt-detail-label">参考解法</div>
                                <pre className="code-run-pre" style={{ maxHeight: 160, fontSize: "0.72rem" }}>
                                  {selectedAttempt.challenge_reference_solution}
                                </pre>
                              </div>
                            )}

                            {/* Mastered toggle & Retry */}
                            <div className="code-attempt-detail-actions">
                              <button
                                className={`ghost-button compact ${selectedAttempt.mastered ? "code-mastered-btn--active" : ""}`}
                                onClick={() => toggleMastered(selectedAttempt.id, selectedAttempt.mastered)}
                                disabled={togglingMastered[selectedAttempt.id]}
                              >
                                {togglingMastered[selectedAttempt.id]
                                  ? "处理中..."
                                  : selectedAttempt.mastered
                                  ? "取消已掌握"
                                  : "标记已掌握"}
                              </button>
                              {selectedAttempt.challenge_id && (
                                <button
                                  className="primary-button compact"
                                  onClick={retryChallenge}
                                  style={{ marginLeft: 8 }}
                                >
                                  重新练习这道题
                                </button>
                              )}
                            </div>
                          </>
                        ) : null}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
          <div className="code-studio-session-list">
            {sessionsLoading ? (
              <div className="empty-inline">加载中...</div>
            ) : sessions.length === 0 ? (
              <div className="empty-inline">暂无代码练习</div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={`code-session-item ${selectedSession?.id === s.id ? "code-session-item--active" : ""}`}
                  onClick={() => selectSession(s)}
                  title={s.title}
                >
                  <div className="code-session-item-title">
                    {s.title}
                  </div>
                  <div className="code-session-item-meta">
                    <span className="subject-pill small code-session-lang-pill">{s.language}</span>
                    {isAIChallenge(s) && (
                      <span className={`code-session-type-badge ${s.challenge_source === "diagnosis" ? "code-session-type-badge--diagnosis" : ""}`}>
                        {s.challenge_source === "diagnosis" ? "诊断推荐" : "AI题"}
                      </span>
                    )}
                    <span className="code-session-time">{formatDate(s.updated_at)}</span>
                  </div>
                  <button
                    className="code-session-delete-btn"
                    title="删除该练习"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(s);
                    }}
                  >
                    &times;
                  </button>
                </div>
              ))
            )}
          </div>
        )}
          </>
        )}
      </aside>
          {!sidebarCollapsed && (
            <div
              className={`code-resize-handle code-resize-handle--h${resizing === "left" ? " code-resize-handle--active" : ""}`}
              onMouseDown={(e) => startResize(e, "left")}
            />
          )}
        </>
      )}

      {/* Center Panel — Code Editor */}
      <main className="code-studio-editor" style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
        {/* Status Bar */}
        <div className="code-status-bar">
          <div className="code-status-bar-left">
            <span className="code-status-title" title={title}>
              {title}
            </span>
            <span className="code-status-tag code-status-tag--lang">
              {language}
            </span>
            {selectedSession?.challenge_id ? (
              <span className={`code-status-tag ${selectedSession?.challenge_source === "diagnosis" ? "code-status-tag--diagnosis" : "code-status-tag--challenge"}`}>
                {selectedSession?.challenge_source === "diagnosis" ? "诊断推荐" : "AI 题目"}
              </span>
            ) : (
              <span className="code-status-tag code-status-tag--free">自由练习</span>
            )}
            {selectedSession?.session_type === "challenge" && !selectedSession?.challenge_id && (
              <span className="code-status-tag code-status-tag--redo">复做题目</span>
            )}
            {codeCourseId && (
              <span className="code-status-tag code-status-tag--course">{getSubjectLabel(codeCourseId)}</span>
            )}
          </div>
          <div className="code-status-bar-right">
            <button
              className={`code-focus-btn ${problemCollapsed ? "code-focus-btn--warn" : ""}`}
              onClick={() => setProblemCollapsed((v) => !v)}
              title={problemCollapsed ? "查看题目" : "隐藏题目"}
            >
              {problemCollapsed ? "查看题目" : "隐藏题目"}
            </button>
            <button
              className={`code-focus-btn ${focusMode ? "code-focus-btn--active" : ""}`}
              onClick={focusMode ? exitFocus : enterFocus}
              title={focusMode ? "退出专注模式" : "专注模式：收起侧边栏和面板，专注编辑"}
            >
              {focusMode ? "退出专注" : "专注模式"}
            </button>
          </div>
        </div>

        {/* Editor Toolbar: Language + Actions */}
        <div className="code-studio-editor-header">
          <div className="code-editor-toolbar-row">
            {/* Current language indicator */}
            <div className="code-editor-lang-group">
              <span className="code-lang-btn code-lang-btn--active" style={{ cursor: "default" }}>
                {language}
              </span>
            </div>

            {/* Action buttons */}
            <div className="code-editor-actions">
              {/* Run group */}
              <div className="code-editor-btn-group">
                <button
                  className={`code-action-btn code-action-btn--run ${terminalRunning ? "code-action-btn--active" : ""}`}
                  onClick={launchInteractiveTerminal}
                  disabled={!code.trim()}
                  title={diagnosticStatus === "error" ? "代码存在编译错误，建议先修复" : "交互式运行代码（支持 scanf/input）"}
                >
                  {terminalRunning ? "⏳ 运行中..." : "▶ 运行"}
                </button>
                <button
                  className={`code-action-btn code-action-btn--test ${!canRun ? "code-action-btn--disabled" : ""}`}
                  onClick={runTests}
                  disabled={testing || !canRun || !code.trim()}
                  title={!selectedSession?.challenge_id ? "请先 AI 出题或选择一道题目" : "运行测试用例"}
                >
                  {testing ? "⏳ 测试中..." : "✔ 测试"}
                </button>
              </div>

              {/* AI group */}
              <div className="code-editor-btn-group">
                <button
                  className="code-action-btn code-action-btn--submit"
                  onClick={submitAnswer}
                  disabled={submitting || !code.trim()}
                  title={!selectedSession?.challenge_id ? "请先 AI 出题或选择一道题目" : "提交答案由 AI 判定"}
                >
                  {submitting ? "⏳ 判定中..." : "AI 判定"}
                </button>
                <button
                  className="code-action-btn code-action-btn--challenge"
                  onClick={openChallengeModal}
                  title="AI 出题"
                >
                  出题
                </button>
              </div>

              {/* Save */}
              <button
                className="code-action-btn code-action-btn--save"
                onClick={saveSession}
                disabled={saving || !title.trim()}
              >
                {saving ? "⏳..." : hasUnsaved ? "保存 *" : "保存"}
              </button>
            </div>
          </div>
        </div>

        {codeTruncated && (
          <div className="code-truncated-warning">
            代码较长，本次仅分析了前 12000 个字符
          </div>
        )}

        {/* ── Horizontal split: Problem Panel (left) | Editor + Output (right) ── */}
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "row" }}>
          {/* ── Problem Panel ── */}
          {!problemCollapsed && currentChallenge && (
            <>
              <div
                className="code-challenge-card"
                style={{ width: Math.max(layout.problemWidth, 280), minWidth: 280, flexShrink: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}
              >
            {/* Panel body — scrollable content */}
            <div className="code-challenge-card-body">
            <div className="code-challenge-card-header">
              <span className="subject-pill small">{currentChallenge.difficulty || "基础"}</span>
              {currentChallenge.knowledge_point && (
                <span className="subject-pill small">{currentChallenge.knowledge_point}</span>
              )}
              {currentChallenge.source === "diagnosis" && (
                <span className="subject-pill small" style={{ background: "#ecfdf5", color: "#065f46" }}>
                  诊断推荐
                </span>
              )}
              {currentChallenge.target_weak_point && (
                <span className="subject-pill small" style={{ background: "#fef3c7", color: "#92400e" }}>
                  薄弱点：{currentChallenge.target_weak_point}
                </span>
              )}
            </div>
            <h4 className="code-challenge-card-title">{currentChallenge.title}</h4>
            {problemLoading && (
              <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginBottom: 4 }}>
                (后台同步最新题目数据...)
              </div>
            )}
            {(() => {
              try {
                const tc = JSON.parse(typeof currentChallenge.test_cases === "string" ? currentChallenge.test_cases : JSON.stringify(currentChallenge.test_cases || "[]"));
                const count = Array.isArray(tc) ? tc.length : 0;
                return count > 0 ? <div className="code-challenge-card-test-count">{count} 组测试用例</div> : null;
              } catch { return null; }
            })()}

            {/* Description — always visible above tabs */}
            <div className="code-challenge-card-section">
              <div className="code-challenge-card-label">题目描述</div>
              <p>{currentChallenge.description || "暂无题目描述。如果这是旧题，可重新生成。"}</p>
            </div>
            {currentChallenge.requirements && (
              <div className="code-challenge-card-section">
                <div className="code-challenge-card-label">要求</div>
                <p>{currentChallenge.requirements}</p>
              </div>
            )}

            {/* Detail tabs: I/O format, examples, hints */}
            <div className="code-problem-tabs">
              {[
                { value: "io", label: "输入输出格式" },
                { value: "examples", label: "样例" },
                { value: "hints", label: "提示" },
              ].map((tab) => (
                <button
                  key={tab.value}
                  className={`code-problem-tab ${problemTab === tab.value ? "code-problem-tab--active" : ""}`}
                  onClick={() => setProblemTab(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="code-problem-tab-panel">
              {problemTab === "io" && (
                <>
                  <div className="code-challenge-card-section">
                    <div className="code-challenge-card-label">输入格式</div>
                    <p>{currentChallenge.input_format || "暂无输入格式说明"}</p>
                  </div>
                  <div className="code-challenge-card-section">
                    <div className="code-challenge-card-label">输出格式</div>
                    <p>{currentChallenge.output_format || "暂无输出格式说明"}</p>
                  </div>
                </>
              )}
              {problemTab === "examples" && (
                <div className="code-challenge-card-section">
                  <div className="code-challenge-card-label">样例</div>
                  <pre className="code-challenge-card-examples">{currentChallenge.examples || "暂无样例"}</pre>
                </div>
              )}
              {problemTab === "hints" && (
                <>
                  {currentChallenge.target_weak_point && (
                    <div className="code-challenge-card-section">
                      <div className="code-challenge-card-label">薄弱点提示</div>
                      <p>{currentChallenge.target_weak_point}</p>
                    </div>
                  )}
                  <div className="code-challenge-card-section">
                    <div className="code-challenge-card-label">练习建议</div>
                    <p>先保证输入输出格式正确，再用样例验证边界情况；提交 AI 判定前建议运行测试用例。</p>
                  </div>
                </>
              )}
            </div>

            {/* No test cases notice */}
            {(() => {
              try {
                const tc = currentChallenge.test_cases ? JSON.parse(
                  typeof currentChallenge.test_cases === "string"
                    ? currentChallenge.test_cases
                    : JSON.stringify(currentChallenge.test_cases)
                ) : [];
                return !Array.isArray(tc) || tc.length === 0;
              } catch { return true; }
            })() && (
              <div className="code-no-tests-notice">
                <span>当前题目暂无测试用例</span>
                <button
                  className="ghost-button compact code-test-gen-btn"
                  onClick={generateTests}
                  disabled={generatingTests || (language !== "Python" && language !== "C")}
                  title={(language !== "Python" && language !== "C") ? "当前仅支持 Python 和 C 题目" : "AI 为本题补全测试用例"}
                >
                  {generatingTests ? "AI 生成中..." : "AI 补全测试用例"}
                </button>
              </div>
            )}
            </div>

            {/* Fixed footer — buttons */}
            <div className="code-challenge-card-footer">
              {currentChallenge.starter_code && (
                <button className="ghost-button compact" onClick={useStarterCode}>
                  使用起始代码
                </button>
              )}
              <button
                className="ghost-button compact"
                onClick={() => {
                  const prompt = `请根据当前题目（${currentChallenge.title}）给我讲解解题思路，不要直接给完整答案。可以给关键伪代码或步骤说明。`;
                  setAiQuestion(prompt);
                  if (assistantCollapsed) setAssistantCollapsed(false);
                }}
              >
                问 AI 教练要思路
              </button>
            </div>
              </div>
              <div
                className={`code-resize-handle code-resize-handle--h${resizing === "problem" ? " code-resize-handle--active" : ""}`}
                onMouseDown={(e) => startResize(e, "problem")}
              />
            </>
          )}

          {/* ── Problem loading/fallback (only when not collapsed) ── */}
          {!problemCollapsed && !currentChallenge && selectedSession && (
            <div
              className="code-challenge-card"
              style={{ width: Math.max(layout.problemWidth, 280), minWidth: 280, flexShrink: 0, overflow: "auto" }}
            >
              {selectedSession.challenge_id ? (
                problemError ? (
                  <div className="code-problem-error">
                    <div className="code-problem-error-text">{problemError}</div>
                    <button
                      className="code-problem-retry-btn"
                      onClick={() => {
                        setProblemError("");
                        setProblemLoading(true);
                        loadChallenge(selectedSession.challenge_id);
                      }}
                    >
                      重新加载
                    </button>
                  </div>
                ) : problemLoading ? (
                  <div className="code-problem-loading">
                    <div className="code-problem-loading-spinner" />
                    <p>正在从服务器获取题目内容...</p>
                  </div>
                ) : (
                  <div className="code-problem-error">
                    <div className="code-problem-error-text">题目详情加载异常，请刷新重试。</div>
                    <button
                      className="code-problem-retry-btn"
                      onClick={() => {
                        setProblemError("");
                        setProblemLoading(true);
                        loadChallenge(selectedSession.challenge_id);
                      }}
                    >
                      重新加载
                    </button>
                  </div>
                )
              ) : (
                <>
                  <div className="code-challenge-card-header">
                    <span className="subject-pill small">自由练习</span>
                  </div>
                  <h4 className="code-challenge-card-title">{selectedSession.title}</h4>
                  <div className="code-challenge-card-section" style={{ marginTop: 16 }}>
                    <div className="code-challenge-card-label">当前为自由练习模式</div>
                    <p>该练习没有关联编程题目。你可以自由编写代码，或点击下方按钮让 AI 为你生成一道编程题。</p>
                  </div>
                  <div className="code-challenge-card-actions" style={{ marginTop: 12 }}>
                    <button className="primary-button compact" onClick={openChallengeModal}>
                      AI 出题
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Right: Editor + Output ── */}
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
            <div className="code-studio-monaco-wrapper" style={{ minHeight: focusMode ? 0 : 300 }}>
              <div className="code-editor-filebar">
                <div className="code-editor-filetab code-editor-filetab--active">
                  {currentFileName}
                </div>
                <button
                  type="button"
                  className="code-editor-diagnostics"
                  onClick={openProblemsPanel}
                  title="Open Problems"
                >
                  <span className="code-editor-diagnostic code-editor-diagnostic--error">● {errorCount}</span>
                  <span className="code-editor-diagnostic code-editor-diagnostic--warning">▲ {warningCount}</span>
                </button>
              </div>
              <div className="code-editor-monaco-surface">
              <Editor
                language={getMonacoLanguage(language)}
                value={code}
                onChange={(value) => setCode(value || "")}
                theme="vs-dark"
                beforeMount={(monaco) => {
                  registerAutocomplete(monaco);
                  monacoRef.current = monaco;
                }}
                onMount={(editor) => {
                  editorRef.current = editor;
                  const position = editor.getPosition();
                  if (position) setEditorCursor({ line: position.lineNumber, column: position.column });
                  editor.onDidChangeCursorPosition((event) => {
                    setEditorCursor({ line: event.position.lineNumber, column: event.position.column });
                  });
                  applyDiagnosticsToEditor(diagnostics);
                }}
                options={{
                  fontSize: 14,
                  minimap: { enabled: false },
                  glyphMargin: true,
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  quickSuggestions: true,
                  suggestOnTriggerCharacters: true,
                  acceptSuggestionOnEnter: "on",
                  tabCompletion: "on",
                  wordBasedSuggestions: "currentDocument",
                  snippetSuggestions: "inline",
                  parameterHints: { enabled: true },
                }}
                loading={
                  <div className="code-studio-monaco-loading">
                    代码编辑器加载中...
                  </div>
                }
              />
              </div>
              <div className="code-editor-statusbar">
                <span>行 {editorCursor.line}，列 {editorCursor.column}</span>
                <span>{codeLineCount} 行</span>
                <span>空格: 4</span>
                <span>UTF-8</span>
                <span>LF</span>
                <span>{language}</span>
                <span className="code-editor-status-run">
                  <span className={`code-status-run-dot ${language === "Java" ? "code-status-run-dot--warn" : "code-status-run-dot--ok"}`} />
                  环境：{language === "Java" ? "AI 分析" : `${language} 可运行`}
                </span>
                {diagnosticStatus !== "unsupported" && diagnosticStatus !== "idle" && (
                  <span className="code-editor-status-diag">
                    {diagnosticStatus === "checking" ? (
                      <><span className="code-diag-dot code-diag-dot--checking" />代码：检查中</>
                    ) : diagnosticStatus === "ok" ? (
                      <><span className="code-diag-dot code-diag-dot--ok" />代码：编译通过</>
                    ) : diagnosticStatus === "warning" ? (
                      <><span className="code-diag-dot code-diag-dot--warn" />代码：{diagnosticWarnings} 个警告</>
                    ) : diagnosticStatus === "error" ? (
                      <><span className="code-diag-dot code-diag-dot--err" />代码：{diagnosticErrors} 个错误</>
                    ) : null}
                  </span>
                )}
              </div>
            </div>

            {!selectedSession && (
              <div className="code-studio-empty-overlay">
                <p>点击左侧「新建练习」开始编程学习</p>
              </div>
            )}

            {/* Output Panel with Tabs */}
            {showFeedbackPanel && !focusMode && (
              <>
                {!outputCollapsed && (
                  <div
                    className={`code-resize-handle code-resize-handle--v${resizing === "output" ? " code-resize-handle--active" : ""}`}
                    onMouseDown={(e) => startResize(e, "output")}
                  />
                )}
              <div className="code-feedback-panel" style={{ height: outputCollapsed ? "auto" : layout.outputHeight, flexShrink: 0 }}>
            <div className="code-feedback-panel-header">
              <div className="code-output-tabs">
                <button
                  className={`code-output-tab ${outputPanelTab === "terminal" ? "code-output-tab--active" : ""}`}
                  onClick={() => setOutputPanelTab("terminal")}
                >
                  运行终端
                </button>
                <button
                  className={`code-output-tab ${outputPanelTab === "run" ? "code-output-tab--active" : ""}`}
                  onClick={() => setOutputPanelTab("run")}
                >
                  运行输出
                </button>
                <button
                  className={`code-output-tab ${outputPanelTab === "problems" ? "code-output-tab--active" : ""}`}
                  onClick={() => setOutputPanelTab("problems")}
                >
                  Problems
                  {(errorCount + warningCount) > 0 && (
                    <span className="code-output-tab-badge">{errorCount + warningCount}</span>
                  )}
                </button>
                <button
                  className={`code-output-tab ${outputPanelTab === "feedback" ? "code-output-tab--active" : ""}`}
                  onClick={() => setOutputPanelTab("feedback")}
                >
                  AI 判定反馈
                </button>
              </div>
              <div className="code-feedback-panel-header-right">
                {outputPanelTab === "feedback" && feedbackStatus && (
                  <span className={`feedback-status-badge ${STATUS_CLASSES[feedbackStatus] || ""}`}>
                    {STATUS_LABELS[feedbackStatus] || feedbackStatus}
                  </span>
                )}
                {outputPanelTab === "terminal" && (
                  <>
                    {terminalRunning ? (
                      <button className="code-action-btn code-action-btn--stop compact" onClick={stopInteractiveTerminal} title="停止运行">
                        ⏹ 停止
                      </button>
                    ) : (
                      <>
                        <button
                          className="code-action-btn code-action-btn--run compact"
                          onClick={launchInteractiveTerminal}
                          disabled={!code.trim()}
                          title="Run again"
                        >
                          Rerun
                        </button>
                      <button className="code-action-btn code-action-btn--clear compact" onClick={clearInteractiveTerminal} title="清空终端">
                        清空
                      </button>
                      </>
                    )}
                    {terminalExitCode !== null && (
                      <span className="code-terminal-exit-code">exit_code: {terminalExitCode}</span>
                    )}
                  </>
                )}
                <button className="code-collapse-btn code-collapse-btn--panel" onClick={() => setOutputCollapsed(!outputCollapsed)} title={outputCollapsed ? "展开面板" : "收起面板"}>
                  {outputCollapsed ? "▲" : "▼"}
                </button>
                <button
                  className="code-feedback-panel-close"
                  onClick={() => { setShowFeedbackPanel(false); setRunResult(null); setTestResults(null); setTestExplanations({}); setExplainingTestCase({}); }}
                >
                  &times;
                </button>
              </div>
            </div>
            {!outputCollapsed && (
            <>
            <div className="code-feedback-panel-body">
              {/* Interactive Terminal Tab */}
              {outputPanelTab === "terminal" && (
                <div className="code-terminal-container" ref={terminalContainerRef} style={{ width: "100%", height: "100%", minHeight: 200 }} />
              )}

              {/* Problems Tab */}
              {outputPanelTab === "problems" && (
                <div className="code-problems-panel">
                  <div className="code-problems-toolbar">
                    <div className="code-problems-summary">
                      <span className="code-problems-summary-item code-problems-summary-item--error">● {errorCount} Errors</span>
                      <span className="code-problems-summary-item code-problems-summary-item--warning">▲ {warningCount} Warnings</span>
                      {diagnosticsLoading && <span className="code-problems-checking">Checking...</span>}
                    </div>
                    <button
                      type="button"
                      className="code-action-btn code-action-btn--clear compact"
                      onClick={() => diagnoseCode(code, language, { force: true })}
                      disabled={!code.trim() || diagnosticsLoading}
                    >
                      Refresh
                    </button>
                  </div>
                  {diagnostics.length > 0 ? (
                    <div className="code-problems-list">
                      {diagnostics.map((item, index) => (
                        <button
                          type="button"
                          key={`${item.severity}-${item.line}-${item.column}-${index}`}
                          className={`code-problem-row code-problem-row--${item.severity}`}
                          onClick={() => jumpToDiagnostic(item)}
                        >
                          <span className="code-problem-row-icon">
                            {item.severity === "warning" ? "▲" : "●"}
                          </span>
                          <span className="code-problem-row-message">{item.message}</span>
                          <span className="code-problem-row-meta">
                            {currentFileName}:{item.line || 1}:{item.column || 1}
                            {item.source ? ` · ${item.source}` : ""}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="code-problems-empty">
                      {diagnosticsLoading ? "Checking diagnostics..." : "No problems found"}
                    </div>
                  )}
                </div>
              )}

              {/* Run Output Tab */}
              {outputPanelTab === "run" && (
                <div className="code-run-output">
                  {running ? (
                    <div className="empty-inline" style={{ padding: "12px 0" }}>
                      代码执行中...
                    </div>
                  ) : testing ? (
                    <div className="empty-inline" style={{ padding: "12px 0" }}>
                      测试运行中...
                    </div>
                  ) : testResults ? (
                    <div className="code-test-results">
                      {/* Error message */}
                      {testResults.error_message && (
                        <div className="code-run-error-message">
                          {testResults.error_message}
                        </div>
                      )}

                      {/* Test Summary */}
                      {testResults.total > 0 ? (
                        <>
                          <div
                            className={`code-test-summary ${
                              testResults.passed === testResults.total
                                ? "code-test-summary--all-pass"
                                : testResults.passed > 0
                                ? "code-test-summary--partial"
                                : "code-test-summary--all-fail"
                            }`}
                          >
                            <span className="code-test-summary-text">
                              测试结果：通过 {testResults.passed}/{testResults.total}
                              {testResults.passed < testResults.total && (
                                <span className="code-test-summary-fail-hint">
                                  ，{testResults.total - testResults.passed} 个未通过
                                </span>
                              )}
                            </span>
                            {testResults.passed > 0 && testResults.passed < testResults.total && (
                              <button
                                className="ghost-button compact code-test-collapse-btn"
                                onClick={() => setCollapsePassed(!collapsePassed)}
                              >
                                {collapsePassed ? "展开已通过" : "折叠已通过"}
                              </button>
                            )}
                          </div>

                          {/* Per-test-case results */}
                          {testResults.results.map((tc, idx) => {
                            const isCollapsed = collapsePassed && tc.passed;
                            return (
                            <div
                              key={idx}
                              className={`code-test-case ${tc.passed ? "code-test-case--pass" : "code-test-case--fail"} ${isCollapsed ? "code-test-case--collapsed" : ""}`}
                            >
                              <div className="code-test-case-header">
                                <span className="code-test-case-index">测试用例 #{idx + 1}</span>
                                <span
                                  className={`code-test-case-badge ${
                                    tc.passed
                                      ? "code-test-case-badge--pass"
                                      : "code-test-case-badge--fail"
                                  }`}
                                >
                                  {tc.passed ? "通过" : "未通过"}
                                </span>
                                {tc.timed_out && (
                                  <span className="code-test-case-badge code-test-case-badge--timeout">
                                    超时
                                  </span>
                                )}
                              </div>
                              {tc.description && (
                                <div className="code-test-case-desc">{tc.description}</div>
                              )}
                              <div className="code-test-case-details">
                                <div className="code-test-case-detail">
                                  <span className="code-test-case-label">Input</span>
                                  <pre className="code-run-pre" style={{ maxHeight: 80 }}>
                                    {tc.input || "(空)"}
                                  </pre>
                                </div>
                                <div className="code-test-case-detail">
                                  <span className="code-test-case-label">期望输出</span>
                                  <pre className="code-run-pre" style={{ maxHeight: 80 }}>
                                    {tc.expected_output || "(空)"}
                                  </pre>
                                </div>
                                <div className="code-test-case-detail">
                                  <span className="code-test-case-label">实际输出</span>
                                  <pre
                                    className={`code-run-pre ${!tc.passed ? "code-run-pre--err" : ""}`}
                                    style={{ maxHeight: 80 }}
                                  >
                                    {tc.actual_output || "(空)"}
                                  </pre>
                                </div>
                                {tc.stderr && (
                                  <div className="code-test-case-detail">
                                    <span className="code-test-case-label code-run-section-label--err">
                                      stderr
                                    </span>
                                    <pre
                                      className="code-run-pre code-run-pre--err"
                                      style={{ maxHeight: 80 }}
                                    >
                                      {tc.stderr}
                                    </pre>
                                  </div>
                                )}
                              </div>

                              {/* Diff summary for failed test cases */}
                              {!tc.passed && tc.diff_summary && (
                                <div className="code-test-diff-summary">
                                  <span className="code-test-diff-label">差异提示：</span>
                                  {tc.diff_summary}
                                </div>
                              )}

                              {/* Compile error */}
                              {tc.compile_error && (
                                <div className="code-compile-error">
                                  <span className="code-compile-error-label">编译错误</span>
                                  <pre className="code-run-pre code-run-pre--err" style={{ maxHeight: 120 }}>
                                    {tc.compile_error}
                                  </pre>
                                </div>
                              )}

                              {/* Truncation warning */}
                              {(tc.stdout_truncated || tc.stderr_truncated) && (
                                <div className="code-run-truncated-warning">
                                  输出较长，已截断显示前 {8000} 字符
                                </div>
                              )}

                              {/* AI Explain button for failed test cases */}
                              {!tc.passed && (
                                <div className="code-test-explain-area">
                                  {explainingTestCase[idx] ? (
                                    <div className="code-test-explain-loading">
                                      AI 正在分析失败原因...
                                    </div>
                                  ) : !testExplanations[idx] ? (
                                    <button
                                      className="ghost-button compact code-test-explain-btn"
                                      onClick={() => explainFailure(idx)}
                                    >
                                      AI 解释失败原因
                                    </button>
                                  ) : null}

                                  {testExplanations[idx] && (
                                    <div className="code-test-explain-content">
                                      {testExplanations[idx]}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                          })}
                        </>
                      ) : testResults.total === 0 && !testResults.error_message ? (
                        <div className="code-no-tests-notice" style={{ margin: "8px 0" }}>
                          <span>当前题目暂无测试用例</span>
                          <button
                            className="ghost-button compact code-test-gen-btn"
                            onClick={generateTests}
                            disabled={generatingTests || (language !== "Python" && language !== "C")}
                          >
                            {generatingTests ? "AI 生成中..." : "AI 补全测试用例"}
                          </button>
                        </div>
                      ) : (
                        <div className="empty-inline" style={{ padding: "16px" }}>
                          {testResults.error_message || "当前题目暂无测试用例，可使用 AI 判定功能分析答案"}
                        </div>
                      )}
                    </div>
                  ) : runResult ? (
                    <>
                      {runResult.error_message && (
                        <div className="code-run-error-message">
                          {runResult.error_message}
                        </div>
                      )}

                      {runResult.timed_out && (
                        <div className="code-run-timeout-warning">
                          执行超时（超过 3 秒），进程已被终止。
                        </div>
                      )}

                      {runResult.compile_error && (
                        <div className="code-compile-error" style={{ marginBottom: 8 }}>
                          <span className="code-compile-error-label">编译错误</span>
                          <pre className="code-run-pre code-run-pre--err" style={{ maxHeight: 160 }}>
                            {runResult.compile_error}
                          </pre>
                        </div>
                      )}

                      <div className="code-run-meta">
                        <span>exit_code: {runResult.exit_code}</span>
                        <span>耗时: {runResult.duration_ms} ms</span>
                        {runResult.timed_out && <span className="code-run-timeout-tag">超时</span>}
                      </div>

                      {(runResult.stdout_truncated || runResult.stderr_truncated) && (
                        <div className="code-run-truncated-warning">
                          输出较长，已截断显示前 {8000} 字符
                        </div>
                      )}

                      {runResult.stdout !== undefined && runResult.stdout !== null && (
                        <div className="code-run-section">
                          <div className="code-run-section-label">stdout</div>
                          <pre className="code-run-pre">
                            {runResult.stdout || "(无输出)"}
                          </pre>
                        </div>
                      )}

                      {runResult.stderr && (
                        <div className="code-run-section">
                          <div className="code-run-section-label code-run-section-label--err">stderr</div>
                          <pre className="code-run-pre code-run-pre--err">
                            {runResult.stderr}
                          </pre>
                        </div>
                      )}

                      {/* Stdin input for next run */}
                      <div className="code-run-stdin">
                        <label className="code-run-section-label">stdin（下次运行使用）</label>
                        <textarea
                          className="field code-run-stdin-textarea"
                          rows={3}
                          placeholder="输入数据（可选）"
                          value={stdin}
                          onChange={(e) => setStdin(e.target.value)}
                        />
                      </div>
                    </>
                  ) : (
                    <div className="empty-inline" style={{ padding: "16px" }}>
                      点击「运行代码」或「运行测试」查看执行结果
                    </div>
                  )}
                </div>
              )}

              {/* AI Feedback Tab */}
              {outputPanelTab === "feedback" && (
                <>
                  {submitting ? (
                    <div className="empty-inline" style={{ padding: "16px" }}>
                      AI 正在判定你的代码...
                    </div>
                  ) : feedbackContent ? (
                    <div className="code-assistant-msg-content">{feedbackContent}</div>
                  ) : (
                    <div className="empty-inline" style={{ padding: "16px" }}>
                      点击「提交答案」获取 AI 判定反馈
                    </div>
                  )}
                </>
              )}
            </div>
            </>
            )}
          </div>
          </>
        )}
          </div>{/* end right: editor + output */}
        </div>{/* end horizontal split */}
      </main>

      {/* Right Panel — AI Coach */}
      {!focusMode && (
        <>
          {!assistantCollapsed && (
            <div
              className={`code-resize-handle code-resize-handle--h${resizing === "right" ? " code-resize-handle--active" : ""}`}
              onMouseDown={(e) => startResize(e, "right")}
            />
          )}
      <aside
        className={`code-studio-assistant ${assistantCollapsed ? "code-studio-assistant--collapsed" : ""}`}
        style={{ width: assistantCollapsed ? 44 : layout.rightWidth, minWidth: assistantCollapsed ? 44 : 56, flexShrink: 0 }}
      >
        {assistantCollapsed ? (
          <div className="code-assistant-collapsed-bar">
            <button
              className="code-sidebar-toggle-btn"
              onClick={() => setAssistantCollapsed(false)}
              title="展开 AI 教练"
            >
              &lang;&lang;
            </button>
          </div>
        ) : (
          <>
        <div className="code-studio-assistant-header">
          <div className="code-sidebar-header-row">
            <h3>AI 教练</h3>
            <button
              className="code-sidebar-toggle-btn"
              onClick={() => setAssistantCollapsed(true)}
              title="折叠 AI 教练"
            >
              &rang;&rang;
            </button>
          </div>
        </div>

        {/* Code progress stats card */}
        {(() => {
          const total = codeProgress?.total_attempts || 0;
          const mastered = codeProgress?.mastered_attempts || 0;
          const unmastered = codeProgress?.unmastered_attempts || 0;
          const masteryPct = total > 0 ? Math.round((mastered / total) * 100) : 0;
          return total > 0 ? (
          <div className="code-progress-mini-card">
            <div className="code-progress-mini-title">编程进度概览</div>
            <div className="code-progress-mini-stats">
              <div className="code-progress-mini-stat">
                <span className="code-progress-mini-num">{total}</span>
                <span className="code-progress-mini-label">总提交</span>
              </div>
              <div className="code-progress-mini-stat">
                <span className="code-progress-mini-num code-progress-mini-num--warn">{unmastered}</span>
                <span className="code-progress-mini-label">未掌握</span>
              </div>
              <div className="code-progress-mini-stat">
                <span className="code-progress-mini-num code-progress-mini-num--ok">{mastered}</span>
                <span className="code-progress-mini-label">已掌握</span>
              </div>
            </div>
            {/* Mastery progress bar */}
            <div className="code-mastery-bar-wrap">
              <div className="code-mastery-bar">
                <div
                  className="code-mastery-bar-fill"
                  style={{ width: `${masteryPct}%` }}
                />
              </div>
              <span className="code-mastery-bar-label">掌握度 {masteryPct}%</span>
            </div>
            {codeProgress.weak_points_from_attempts?.length > 0 && (
              <div className="code-progress-mini-weak">
                <span className="code-progress-mini-weak-title">高频薄弱点：</span>
                {codeProgress.weak_points_from_attempts.slice(0, 3).map((wp, i) => (
                  <span key={i} className="code-progress-mini-weak-tag">
                    {wp.knowledge_point} ({wp.unmastered_count})
                  </span>
                ))}
              </div>
            )}
          </div>
          ) : null;
        })()}

        <div className="code-studio-assistant-chat">
          {diagnosisReport ? (
            <div className="code-diagnosis-report">
              {diagnosisReport.data_insufficient ? (
                <div className="empty-inline" style={{ padding: "16px" }}>
                  {diagnosisReport.summary.split("\n").map((line, i) => (
                    <p key={i} style={{ margin: "4px 0" }}>{line || " "}</p>
                  ))}
                </div>
              ) : (
                <div className="code-assistant-msg code-assistant-msg--assistant">
                  <div className="code-assistant-msg-role">编程学习诊断报告</div>
                  <div className="code-assistant-msg-content">{diagnosisReport.summary}</div>
                  <div className="code-diagnosis-meta">
                    分析依据：{diagnosisReport.used_sessions_count} 条练习、{diagnosisReport.used_messages_count} 条分析记录、{diagnosisReport.used_challenges_count} 道出题
                  </div>
                  {!diagnosisReport.data_insufficient && (
                    <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        className="primary-button compact"
                        onClick={generateTargetedChallenge}
                        disabled={targetedChallengeLoading}
                      >
                        {targetedChallengeLoading ? "AI 正在根据薄弱点生成练习..." : "根据薄弱点生成练习"}
                      </button>
                      <button
                        className="primary-button compact"
                        onClick={generateTasksFromDiagnosis}
                        disabled={taskGenerationLoading}
                        style={{ background: "#0f766e" }}
                      >
                        {taskGenerationLoading ? "AI 正在根据诊断报告生成学习任务..." : "生成学习任务"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : diagnosisLoading ? (
            <div className="empty-inline" style={{ padding: "24px 16px" }}>
              AI 正在分析你的编程学习情况...
            </div>
          ) : (
            <>
              {/* Saved Chats Section */}
              {currentChallenge?.id && (
                <div className="code-saved-chats-section">
                  <div className="code-saved-chats-header">
                    <span className="code-saved-chats-title">
                      已保存的 AI 记录 ({savedChats.length})
                    </span>
                    {savedChats.length > 0 && (
                      <button
                        className="code-saved-chats-toggle"
                        onClick={() => setSavedChatsCollapsed(!savedChatsCollapsed)}
                      >
                        {savedChatsCollapsed ? "展开" : "折叠"}
                      </button>
                    )}
                  </div>
                  {savedChatsLoading ? (
                    <div style={{ fontSize: "0.72rem", color: "#94a3b8", padding: "4px 0" }}>加载中...</div>
                  ) : !savedChatsCollapsed && savedChats.length > 0 ? (
                    savedChats.map((sc) => (
                      <div key={sc.id} className="code-saved-chat-item">
                        <div className="code-saved-chat-item-q">Q: {sc.user_message || "(无问题文本)"}</div>
                        <div className="code-saved-chat-item-a">
                          <MarkdownMessage content={sc.assistant_message} />
                        </div>
                        <div className="code-saved-chat-item-time">
                          {sc.created_at ? new Date(sc.created_at).toLocaleString("zh-CN") : ""}
                        </div>
                        <button
                          className="code-saved-chat-item-delete"
                          onClick={() => deleteSavedChat(sc.id)}
                          disabled={deletingSavedId === sc.id}
                        >
                          {deletingSavedId === sc.id ? "删除中..." : "取消保存"}
                        </button>
                      </div>
                    ))
                  ) : !savedChatsCollapsed && savedChats.length === 0 && currentChallenge?.id ? (
                    <div style={{ fontSize: "0.7rem", color: "#cbd5e1", padding: "4px 0" }}>
                      暂无已保存记录，点击 AI 回复下方的「保存」按钮即可保存
                    </div>
                  ) : null}
                </div>
              )}

              {/* Chat Messages */}
              {aiMessagesLoading ? (
                <div className="empty-inline" style={{ padding: "24px 16px" }}>
                  加载历史记录中...
                </div>
              ) : aiMessages.length === 0 ? (
            <div className="code-assistant-empty">
              <p className="code-assistant-empty-title">AI 教练</p>
              <p className="muted-text">基于当前题目和代码回答你的问题</p>
              <div className="code-assistant-suggestions">
                <p className="code-assistant-suggestions-title">你可以问：</p>
                {[
                  "帮我分析这段代码的问题",
                  "解释这个编译错误",
                  "为什么这个测试用例没过",
                  "帮我优化时间复杂度",
                  "给我讲解这道题的思路",
                  "给我一份参考答案代码",
                ].map((s, i) => (
                  <button
                    key={i}
                    className="code-suggestion-chip"
                    onClick={() => { setAiQuestion(s); }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            aiMessages.map((msg, i) => (
              <div key={i} className={`code-assistant-msg code-assistant-msg--${msg.role}`}>
                <div className="code-assistant-msg-role">
                  {msg.role === "user" ? "你" : "AI 教练"}
                </div>
                {msg.role === "assistant" ? (
                  <div className="code-assistant-msg-bubble-ai">
                    <MarkdownMessage content={msg.content} />
                  </div>
                ) : (
                  <div className="code-assistant-msg-bubble-user">{msg.content}</div>
                )}
                {msg.role === "assistant" && (
                  <div className="code-assistant-msg-actions">
                    <button
                      className="code-msg-action-btn"
                      onClick={() => {
                        navigator.clipboard?.writeText(msg.content).catch(() => {});
                      }}
                    >
                      复制
                    </button>
                    {msg._savedId && savedMsgIds.has(msg._savedId) ? (
                      <button
                        className="code-msg-action-btn code-msg-action-btn--saved"
                        onClick={() => {
                          if (msg._savedId) deleteSavedChat(msg._savedId);
                        }}
                        disabled={deletingSavedId === msg._savedId}
                      >
                        已保存
                      </button>
                    ) : savingMsgIndex === i ? (
                      <button className="code-msg-action-btn" disabled>保存中...</button>
                    ) : (
                      <button
                        className="code-msg-action-btn"
                        onClick={() => saveChat(i)}
                        disabled={!currentChallenge?.id}
                        title={currentChallenge?.id ? "保存此回答" : "题目未加载完成"}
                      >
                        保存
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
          {aiLoading && (
            <div className="code-assistant-loading">
              <span>AI 正在结合题目和代码分析</span>
              <div className="code-assistant-loading-dots">
                <span /><span /><span />
              </div>
            </div>
          )}
          <div ref={aiEndRef} />
          </>
        )}
        </div>

        <div className="code-studio-assistant-input">
          <textarea
            className="field"
            placeholder="例如：帮我检查代码问题（Enter 发送，Shift+Enter 换行）"
            value={aiQuestion}
            onChange={(e) => setAiQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                analyzeCode();
              }
            }}
            rows={2}
            style={{ resize: "none" }}
          />
          <button
            className="primary-button compact"
            onClick={analyzeCode}
            disabled={aiLoading || !aiQuestion.trim()}
            style={{ alignSelf: "flex-end" }}
          >
            {aiLoading ? "分析中..." : "发送"}
          </button>
        </div>
          </>
        )}
      </aside>
        </>
      )}

      {tip && (
        <div className="code-studio-tip">
          {tip}
        </div>
      )}

      {/* ── AI 出题 Modal ── */}
      {showChallengeModal && (
        <div className="modal-overlay" onClick={() => { if (!challengeGenerating) setShowChallengeModal(false); }}>
          <div
            className="modal-card code-challenge-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3>AI 出题</h3>
                <p className="code-challenge-modal-subtitle">
                  当前课程：<strong>{getSubjectLabel(codeCourseId) || "未选择"}</strong>，编程语言：<strong>{language}</strong>
                </p>
              </div>
              <button className="modal-close" onClick={() => setShowChallengeModal(false)} disabled={challengeGenerating}>
                &times;
              </button>
            </div>

            <div className="code-challenge-modal-body">
              {/* ── Language ── */}
              <label className="field-label">编程语言</label>
              <div className="code-challenge-lang-row">
                {LANGUAGES.map((lang) => (
                  <button
                    key={lang}
                    className={`code-challenge-lang-btn ${language === lang ? "code-challenge-lang-btn--active" : ""}`}
                    onClick={() => setLanguage(lang)}
                  >
                    {lang}
                  </button>
                ))}
              </div>

              <div className="code-challenge-grid">
                {/* ── Difficulty ── */}
                <div>
                  <label className="field-label">难度</label>
                  <div className="code-challenge-diff-row">
                    {["基础", "中等", "提高"].map((d) => (
                      <button
                        key={d}
                        className={`code-challenge-diff-btn ${challengeDifficulty === d ? "code-challenge-diff-btn--active" : ""}`}
                        onClick={() => setChallengeDifficulty(d)}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                {/* ── Count ── */}
                <div>
                  <label className="field-label">生成数量</label>
                  <div className="code-challenge-count-row">
                    <input
                      className="field code-challenge-count-input"
                      type="number"
                      min={1}
                      max={10}
                      value={challengeCount}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v)) setChallengeCount(Math.min(10, Math.max(1, v)));
                      }}
                    />
                    <span className="code-challenge-count-hint">1 ~ 10 道</span>
                  </div>
                </div>
              </div>

              {/* ── Knowledge Points ── */}
              <label className="field-label">绑定知识点</label>
              {genDataError ? (
                <p className="code-challenge-empty-hint" style={{ color: "#dc2626" }}>{genDataError}</p>
              ) : genDataLoading ? (
                <p className="code-challenge-empty-hint">正在加载当前课程知识点...</p>
              ) : genKnowledgePoints.length > 0 ? (
                <>
                  <div className="code-challenge-kp-tags">
                    {genKnowledgePoints.slice(0, 20).map((kp) => {
                      const sel = selectedGenKpIds.includes(kp.id);
                      return (
                        <button
                          key={kp.id}
                          className={`code-challenge-kp-tag ${sel ? "code-challenge-kp-tag--active" : ""}`}
                          onClick={() => {
                            setSelectedGenKpIds((prev) =>
                              sel ? prev.filter((id) => id !== kp.id) : [...prev, kp.id]
                            );
                          }}
                          title={kp.title}
                        >
                          {sel && <span className="code-challenge-kp-check">&#10003;</span>}
                          {kp.title}
                        </button>
                      );
                    })}
                  </div>
                  {selectedGenKpIds.length > 0 && (
                    <div className="code-challenge-kp-selected-count">
                      已选择 {selectedGenKpIds.length} 个知识点
                    </div>
                  )}
                </>
              ) : (
                <p className="code-challenge-empty-hint">
                  {codeCourseId
                    ? "当前课程暂无知识点路线，可直接输入补充知识点"
                    : "请先选择课程查看知识点"}
                </p>
              )}
              <input
                className="field"
                placeholder="补充知识点，例如：循环队列、数组模拟、指针操作"
                value={challengeFocus}
                onChange={(e) => setChallengeFocus(e.target.value)}
                style={{ marginTop: 8 }}
              />

              {/* ── Reference Materials ── */}
              <label className="field-label">引用课程资料（可选）</label>
              {genDataLoading ? (
                <p className="code-challenge-empty-hint">正在加载当前课程资料...</p>
              ) : genMaterials.length > 0 ? (
                <div className="code-challenge-material-list">
                  {genMaterials.slice(0, 15).map((m) => {
                    const sel = selectedGenMaterialIds.includes(m.id);
                    return (
                      <label
                        key={m.id}
                        className={`code-challenge-material-item ${sel ? "code-challenge-material-item--active" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={sel}
                          onChange={() => {
                            setSelectedGenMaterialIds((prev) =>
                              sel ? prev.filter((id) => id !== m.id) : [...prev, m.id]
                            );
                          }}
                        />
                        <span className="code-challenge-material-name" title={m.original_filename}>
                          {m.original_filename}
                        </span>
                        <span className="code-challenge-material-type">{m.file_type}</span>
                      </label>
                    );
                  })}
                </div>
              ) : genDataError && genMaterials.length === 0 ? (
                <p className="code-challenge-empty-hint" style={{ color: "#dc2626" }}>{genDataError}</p>
              ) : (
                <p className="code-challenge-empty-hint">
                  当前课程暂无资料，可先到资料库上传，也可以不引用资料直接生成
                </p>
              )}
              {selectedGenMaterialIds.length > 0 && (
                <div className="code-challenge-material-count">
                  已选择 {selectedGenMaterialIds.length} 份资料
                </div>
              )}

              {/* ── Extra Requirements ── */}
              <label className="field-label">额外要求（可选）</label>
              <textarea
                className="field code-challenge-extra-req"
                placeholder="例如：希望考查循环队列，不要用链表，给 3 组测试用例"
                value={challengeExtraReq}
                onChange={(e) => setChallengeExtraReq(e.target.value)}
                rows={3}
              />

              {/* ── Error ── */}
              {challengeGenError && (
                <div className="practice-import-error" style={{ marginTop: 8 }}>
                  {challengeGenError}
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button
                className="ghost-button"
                onClick={() => setShowChallengeModal(false)}
                disabled={challengeGenerating}
              >
                取消
              </button>
              <button
                className="code-challenge-generate-btn"
                onClick={generateChallenge}
                disabled={challengeGenerating}
              >
                {challengeGenerating ? "⏳ 生成中..." : "生成题目"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="modal-card code-delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>删除练习</h3>
              <button className="modal-close" onClick={() => setDeleteTarget(null)}>
                &times;
              </button>
            </div>
            <p style={{ margin: "0 0 16px", color: "#334155", fontSize: "0.9rem" }}>
              确定要删除练习「{deleteTarget.title}」吗？该练习的 AI 分析记录也会被删除。此操作不可撤销。
            </p>
            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setDeleteTarget(null)}>
                取消
              </button>
              <button
                className="danger-button"
                onClick={() => deleteSession(deleteTarget.id)}
                disabled={deleting}
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Reference Solution Modal ── */}
      {isReferenceModalOpen && currentChallenge?.reference_solution && (
        <div
          className="modal-overlay"
          onClick={() => setIsReferenceModalOpen(false)}
        >
          <div
            className="modal-card code-reference-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="code-ref-modal-title-row">
                <h3>参考解法</h3>
                <span className="code-ref-lang-pill">
                  {language}
                </span>
              </div>
              <button className="modal-close" onClick={() => setIsReferenceModalOpen(false)}>
                &times;
              </button>
            </div>
            <div className="code-reference-modal-body">
              {/* File tab indicator */}
              <div className="code-ref-file-tab">
                <span className="code-ref-file-tab-label">
                  {language === "C" ? "main.c" : "main.py"}
                </span>
              </div>
              <pre className="code-reference-modal-code">{currentChallenge.reference_solution}</pre>
            </div>
            <div className="modal-actions code-ref-modal-actions">
              <button
                className={`code-ref-copy-btn${copyRefFeedback ? " code-ref-copy-btn--done" : ""}`}
                onClick={() => copyToClipboard(currentChallenge.reference_solution)}
                disabled={copyRefFeedback}
              >
                {copyRefFeedback ? "✓ 已复制" : "复制代码"}
              </button>
              <div className="code-ref-modal-spacer" />
              <button
                className="ghost-button compact"
                onClick={() => setIsReferenceModalOpen(false)}
              >
                关闭
              </button>
              <button
                className="code-ref-apply-btn"
                onClick={() => {
                  const refSol = currentChallenge.reference_solution;
                  const trimmed = (code || "").trim();
                  const isDefault =
                    !trimmed ||
                    Object.values(CODE_TEMPLATES).map((t) => t.trim()).includes(trimmed) ||
                    trimmed === refSol.trim();
                  if (!isDefault) {
                    setPendingApplyCode(refSol);
                    setIsReferenceModalOpen(false);
                    setStarterConfirmOpen(true);
                  } else {
                    setCode(refSol);
                    setTip("已应用参考解法");
                    setTimeout(() => setTip(""), 2000);
                    setIsReferenceModalOpen(false);
                  }
                }}
              >
                应用到编辑器
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Starter Code Confirm Modal ── */}
      {starterConfirmOpen && (
        <div className="modal-overlay" onClick={() => {}}>
          <div
            className="modal-card code-starter-confirm-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="code-starter-confirm-title-row">
                <span className="code-starter-warn-icon" aria-hidden="true">
                  <span className="code-starter-warn-inner">!</span>
                </span>
                <h3>确认覆盖当前代码？</h3>
              </div>
              <button className="modal-close" onClick={() => setStarterConfirmOpen(false)}>
                &times;
              </button>
            </div>
            <div className="code-starter-confirm-body">
              <p>
                当前编辑器中已有代码修改。继续应用后，<strong>当前代码将被覆盖且无法撤销</strong>。
              </p>
              <p className="code-starter-confirm-hint">
                建议先复制当前代码（Ctrl+C）再执行覆盖
              </p>
            </div>
            <div className="modal-actions code-starter-confirm-actions">
              <button
                className="code-starter-cancel-btn"
                onClick={() => setStarterConfirmOpen(false)}
              >
                继续编辑
              </button>
              <button
                className="code-starter-confirm-btn"
                onClick={confirmStarterCode}
              >
                确认覆盖并应用
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
