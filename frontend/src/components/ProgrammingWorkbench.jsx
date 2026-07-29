import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./ProgrammingWorkbench.css";
import { getExerciseDescription, getExerciseTitle } from "./programmingExerciseCopy.js";

const LANGUAGE_TABS = ["C", "C++", "Python", "Java"];
const DEFAULT_FILE = { C: "main.c", "C++": "main.cpp", Python: "main.py", Java: "Main.java" };
const PROJECT_COURSE_ID = "programming";
const UI_STORAGE_KEY = "ai_study_programming_workbench_ui_v2";

const LANGUAGE_META = {
  C: { mark: "C", description: "贴近系统底层，适合指针、结构体和多文件练习。" },
  "C++": { mark: "C++", description: "适合 STL、面向对象、算法工程和竞赛项目。" },
  Python: { mark: "Py", description: "语法轻量，适合脚本、数据处理和算法验证。" },
  Java: { mark: "Jv", description: "适合面向对象、工程结构和类协作练习。" },
};

const MONACO_BY_EXT = {
  ".c": "c",
  ".h": "c",
  ".cpp": "cpp",
  ".cc": "cpp",
  ".cxx": "cpp",
  ".hpp": "cpp",
  ".py": "python",
  ".java": "java",
  ".json": "json",
  ".xml": "xml",
  ".yaml": "yaml",
  ".yml": "yaml",
  ".toml": "ini",
  ".md": "markdown",
  ".markdown": "markdown",
  ".csv": "plaintext",
  ".sh": "shell",
  ".txt": "plaintext",
};

const SOURCE_EXTENSIONS = {
  C: [".c"],
  "C++": [".cpp", ".cc", ".cxx"],
  Python: [".py"],
  Java: [".java"],
};

const HEADER_EXTENSIONS = new Set([".h", ".hpp"]);
const CODE_RESOURCE_EXTENSIONS = new Set([".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".py", ".java", ".js", ".ts", ".sh"]);
const TEXT_RESOURCE_EXTENSIONS = new Set([".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml"]);
const MARKDOWN_EXTENSIONS = new Set([".md", ".markdown"]);
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]);
const PDF_EXTENSIONS = new Set([".pdf"]);
const OFFICE_EXTENSIONS = new Set([".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]);
const ARCHIVE_EXTENSIONS = new Set([".zip", ".rar", ".tar", ".gz", ".tgz", ".7z"]);
const IDE_TEXT_RESOURCE_EXTENSIONS = new Set([...CODE_RESOURCE_EXTENSIONS, ...TEXT_RESOURCE_EXTENSIONS, ...MARKDOWN_EXTENSIONS]);
const LANGUAGE_RESOURCE_EXTENSIONS = {
  C: new Set([".c", ".h"]),
  "C++": new Set([".cpp", ".hpp", ".cc", ".cxx", ".h"]),
  Python: new Set([".py"]),
  Java: new Set([".java"]),
};
const COMMON_DEV_TEXT_EXTENSIONS = new Set([".md", ".markdown", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml", ".txt", ".sh", ".js", ".ts"]);

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function getExt(path = "") {
  const match = String(path).toLowerCase().match(/\.[a-z0-9]+$/);
  return match?.[0] || "";
}

function getMonacoLanguage(file) {
  return MONACO_BY_EXT[getExt(file?.relative_path)] || "plaintext";
}

function getDisplayFilename(item = {}) {
  return item.relative_path?.split("/").pop()
    || item.filename
    || item.original_filename
    || item.file_name
    || "resource";
}

function getMaterialPath(material = {}) {
  return material.relative_path || material.original_filename || material.file_name || `material-${material.id}`;
}

function getResourceKind(item = {}) {
  const ext = getExt(getMaterialPath(item));
  const fileType = String(item.file_type || item.mime_type || "").toLowerCase();
  if (MARKDOWN_EXTENSIONS.has(ext) || fileType.includes("markdown")) return "markdown";
  if (PDF_EXTENSIONS.has(ext) || fileType === "pdf" || fileType.includes("pdf")) return "pdf";
  if (IMAGE_EXTENSIONS.has(ext) || fileType === "image" || fileType.startsWith("image/")) return "image";
  if (CODE_RESOURCE_EXTENSIONS.has(ext) || fileType === "code") return "code";
  if (TEXT_RESOURCE_EXTENSIONS.has(ext) || fileType === "text" || fileType === "txt") return "text";
  if (OFFICE_EXTENSIONS.has(ext)) return "office";
  if (ARCHIVE_EXTENSIONS.has(ext)) return "archive";
  return "binary";
}

function isIdeTextResource(item = {}) {
  const ext = getExt(getMaterialPath(item));
  return IDE_TEXT_RESOURCE_EXTENSIONS.has(ext);
}

function isResourceForLanguage(item = {}, language = "") {
  const ext = getExt(getMaterialPath(item));
  if (!isIdeTextResource(item)) return false;
  if (COMMON_DEV_TEXT_EXTENSIONS.has(ext)) return true;
  return LANGUAGE_RESOURCE_EXTENSIONS[language]?.has(ext) || false;
}

function getProblemText(result) {
  return [result?.compile_error, result?.stderr, result?.error_message].filter(Boolean).join("\n");
}

function parseCompilerDiagnostics(result, activeProject) {
  const text = getProblemText(result);
  if (!text.trim()) return [];
  const lines = text.split(/\r?\n/);
  const items = [];
  const pushItem = (item) => {
    const message = String(item.message || "").trim();
    if (!message) return;
    items.push({
      severity: item.severity || (/warning/i.test(message) ? "warning" : "error"),
      file: item.file || activeProject?.entry_file || "",
      line: item.line || null,
      column: item.column || null,
      message,
      source: "compiler",
    });
  };

  for (const line of lines) {
    const gcc = /^(.*?):(\d+):(\d+):\s+(fatal error|error|warning):\s+(.*)$/i.exec(line);
    if (gcc) {
      pushItem({ file: gcc[1], line: Number(gcc[2]), column: Number(gcc[3]), severity: gcc[4].toLowerCase().includes("warning") ? "warning" : "error", message: gcc[5] });
      continue;
    }
    const javac = /^(.*?\.java):(\d+):\s+(error|warning):\s+(.*)$/i.exec(line);
    if (javac) {
      pushItem({ file: javac[1], line: Number(javac[2]), severity: javac[3].toLowerCase(), message: javac[4] });
      continue;
    }
    const pythonFile = /^\s*File\s+"([^"]+)",\s+line\s+(\d+)/.exec(line);
    if (pythonFile) {
      pushItem({ file: pythonFile[1], line: Number(pythonFile[2]), severity: "error", message: lines[lines.indexOf(line) + 1] || "Python syntax error" });
      continue;
    }
    if (/\b(error|warning)\b/i.test(line)) {
      pushItem({ message: line });
    }
  }
  if (!items.length && result?.exit_code && result.exit_code !== 0) {
    pushItem({ message: text.split(/\r?\n/).find(Boolean) || "运行或编译失败" });
  }
  return items;
}

function markerToProblem(marker, file) {
  return {
    severity: marker.severity === 8 ? "error" : "warning",
    file: file?.relative_path || "",
    line: marker.startLineNumber || null,
    column: marker.startColumn || null,
    message: marker.message || "Monaco diagnostic",
    source: "monaco",
  };
}

function getMaterialPreviewUrl(apiBase, material, username) {
  if (!material?.id || !username) return "";
  const raw = material.preview_url || `/materials/${material.id}/preview`;
  const joiner = raw.includes("?") ? "&" : "?";
  return `${apiBase}${raw}${joiner}username=${encodeURIComponent(username)}`;
}

function getMaterialDownloadUrl(apiBase, material, username) {
  if (!material?.id || !username) return "";
  const raw = material.download_url || `/materials/${material.id}/download`;
  const joiner = raw.includes("?") ? "&" : "?";
  return `${apiBase}${raw}${joiner}username=${encodeURIComponent(username)}`;
}

function getFileIcon(path = "") {
  const ext = getExt(path);
  if (ext === ".py") return "Py";
  if (ext === ".java") return "J";
  if (ext === ".c") return "C";
  if ([".cpp", ".cc", ".cxx"].includes(ext)) return "C++";
  if ([".h", ".hpp"].includes(ext)) return "H";
  if (ext === ".json") return "{}";
  if (ext === ".md") return "Md";
  if (ext === ".txt") return "Txt";
  return ext.replace(".", "").slice(0, 3) || "File";
}

function getResourceIcon(item = {}) {
  const kind = getResourceKind(item);
  if (kind === "markdown") return "Md";
  if (kind === "pdf") return "PDF";
  if (kind === "image") return "Img";
  if (kind === "office") return "Doc";
  if (kind === "archive") return "Zip";
  if (kind === "code" || kind === "text") return getFileIcon(getMaterialPath(item));
  return "Bin";
}

function getRuntimeLabel(language) {
  if (language === "Python") return "Python 3.x";
  if (language === "Java") return "Java";
  if (language === "C++") return "C++";
  if (language === "C") return "C";
  return language || "";
}

function normalizeLanguage(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (raw.includes("c++") || raw.includes("cpp")) return "C++";
  if (raw === "c" || raw.includes("c语言")) return "C";
  if (raw.includes("java")) return "Java";
  if (raw.includes("python") || raw.includes("py")) return "Python";
  return "";
}

function formatRunResult(result) {
  if (!result) return "点击运行后，当前练习的真实程序输出会显示在这里。";
  const output = result.actual_output ?? result.stdout;
  return output?.trimEnd() || (result.exit_code === 0 ? "程序已运行完成，无输出。" : "程序运行失败，请展开运行详情查看错误信息。");
}

function formatRunDetails(result) {
  if (!result) return "";
  const lines = [`exit_code: ${result.exit_code ?? "-"}`];
  if (result.duration_ms != null) lines.push(`duration: ${result.duration_ms}ms`);
  const technicalDetails = result.technical_details || result.stderr || result.compile_error || result.error_message;
  if (technicalDetails) lines.push(`原始测试日志\n${String(technicalDetails).trimEnd()}`);
  return lines.join("\n");
}

function caseStatusLabel(status) {
  return {
    passed: "通过",
    failed: "未通过",
    compile_failed: "编译失败",
    runtime_failed: "运行失败",
    timeout: "运行超时",
    skipped: "已跳过",
  }[status] || "未通过";
}

function caseDisplayReason(item) {
  if (item?.reason) return item.reason;
  if (item?.status === "compile_failed") return "代码编译失败";
  if (item?.status === "runtime_failed") return "代码运行时发生异常";
  if (item?.status === "timeout") return "程序运行超过 5 秒，可能存在死循环";
  return item?.status === "passed" ? "" : "返回结果与期望值不一致";
}

function caseExpectedValue(item) {
  return item?.expected ?? item?.expected_output;
}

function caseActualValue(item) {
  if (item?.actual !== undefined && item?.actual !== null) return item.actual;
  if (item?.actual_output !== undefined && item?.actual_output !== null) return item.actual_output;
  return "未返回结果";
}

function normalizeResultCase(item, index = 0) {
  return {
    id: item?.id || `case-${index + 1}`,
    name: item?.name || `测试样例 ${index + 1}`,
    status: item?.status || (item?.passed ? "passed" : "failed"),
    reason: caseDisplayReason(item),
    input_display: item?.input_display ?? item?.input,
    expected: caseExpectedValue(item),
    actual: caseActualValue(item),
    location: item?.location,
    duration_ms: item?.duration_ms ?? 0,
  };
}

function ExerciseResultModal({ result, mode, filter, onFilterChange, onClose, onRerun, busy }) {
  const cases = (result?.cases || []).map(normalizeResultCase);
  const failedCount = Math.max(0, Number(result?.total_count || cases.length) - Number(result?.passed_count || 0));
  const orderedCases = [...cases]
    .sort((a, b) => (a.status === "passed" ? 1 : 0) - (b.status === "passed" ? 1 : 0))
    .filter((item) => filter === "all" || (filter === "failed" ? item.status !== "passed" : item.status === "passed"));
  const durationSeconds = (Number(result?.duration_ms || 0) / 1000).toFixed(1);
  const title = mode === "submit" ? "提交结果" : "全部测试结果";

  return (
    <div className="pw-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="pw-result-modal" role="dialog" aria-modal="true" aria-labelledby="pw-result-modal-title">
        <header className="pw-result-modal-head">
          <div>
            <span className="pw-modal-eyebrow">{mode === "submit" ? "完整官方测试集" : "公开测试样例"}</span>
            <h2 id="pw-result-modal-title">{title}</h2>
          </div>
          <button type="button" className="pw-modal-close" onClick={onClose} aria-label="关闭">×</button>
        </header>
        <div className="pw-result-modal-summary">
          <strong>通过 {result?.passed_count ?? 0}/{result?.total_count ?? cases.length}</strong>
          <span>未通过 {failedCount}</span>
          <span>耗时 {durationSeconds}s</span>
        </div>
        <div className="pw-result-modal-toolbar">
          <div className="pw-result-filter" role="group" aria-label="测试结果筛选">
            {[['all', '全部'], ['failed', '仅失败'], ['passed', '仅通过']].map(([value, label]) => (
              <button key={value} type="button" className={filter === value ? "is-active" : ""} onClick={() => onFilterChange(value)}>{label}</button>
            ))}
          </div>
          <button type="button" className="pw-modal-rerun" onClick={onRerun} disabled={Boolean(busy)}>
            {busy ? "运行中…" : "重新运行全部测试"}
          </button>
        </div>
        <div className="pw-result-modal-list">
          {orderedCases.length ? orderedCases.map((item) => {
            const failed = item.status !== "passed";
            return (
              <details key={item.id} className={`pw-modal-case pw-modal-case--${item.status}`} open={failed}>
                <summary>
                  <strong>{item.name}</strong>
                  <span>{caseStatusLabel(item.status)}</span>
                </summary>
                <div className="pw-modal-case-body">
                  {item.input_display && <span>输入或参数：{item.input_display}</span>}
                  {item.expected !== undefined && <span>期望：{String(item.expected)}</span>}
                  {item.actual !== undefined && <span>实际：{String(item.actual)}</span>}
                  {failed && item.reason && <span>原因：{item.reason}</span>}
                  {item.location && <span>位置：{item.location}</span>}
                  <span>执行时间：{item.duration_ms ?? 0}ms</span>
                </div>
              </details>
            );
          }) : <div className="pw-modal-empty">当前筛选没有测试样例。</div>}
        </div>
        {result?.technical_details && (
          <details className="pw-technical-details pw-modal-technical">
            <summary>技术详情</summary>
            <pre>{result.technical_details}</pre>
          </details>
        )}
      </section>
    </div>
  );
}

function readUiPreference(key, fallback) {
  try {
    const saved = JSON.parse(localStorage.getItem(UI_STORAGE_KEY) || "{}");
    return typeof saved[key] === "boolean" ? saved[key] : fallback;
  } catch {
    return fallback;
  }
}

function writeUiPreference(key, value) {
  try {
    const saved = JSON.parse(localStorage.getItem(UI_STORAGE_KEY) || "{}");
    localStorage.setItem(UI_STORAGE_KEY, JSON.stringify({ ...saved, [key]: value }));
  } catch {
    // localStorage is a pure UI preference here; ignore failures.
  }
}

function buildTree(files) {
  const root = { name: "", path: "", folders: new Map(), files: [] };
  for (const file of files) {
    const parts = String(file.relative_path || file.filename || "").split("/").filter(Boolean);
    let node = root;
    parts.slice(0, -1).forEach((part, index) => {
      const path = parts.slice(0, index + 1).join("/");
      if (!node.folders.has(part)) node.folders.set(part, { name: part, path, folders: new Map(), files: [] });
      node = node.folders.get(part);
    });
    node.files.push(file);
  }
  return root;
}

function joinPath(parentPath, name) {
  const parent = String(parentPath || "").replace(/\/+$/, "");
  const child = String(name || "").replace(/^\/+/, "");
  return parent ? `${parent}/${child}` : child;
}

function isSourceFileForLanguage(path, language) {
  const ext = getExt(path);
  return (SOURCE_EXTENSIONS[language] || []).includes(ext);
}

function detectJavaMainClass(file) {
  if (!file || getExt(file.relative_path) !== ".java") return "";
  const content = file.content || "";
  if (!/public\s+static\s+void\s+main\s*\(\s*String\s*\[\]\s+\w+\s*\)|static\s+void\s+main\s*\(/.test(content)) return "";
  const packageName = content.match(/^\s*package\s+([A-Za-z_][\w.]*)\s*;/m)?.[1] || "";
  const className = content.match(/\b(?:public\s+)?(?:class|record|enum)\s+([A-Za-z_]\w*)\b/)?.[1]
    || String(file.filename || file.relative_path || "").replace(/\.java$/i, "");
  return packageName ? `${packageName}.${className}` : className;
}

function clampMenuPosition(x, y) {
  const width = 210;
  const height = 280;
  return {
    x: Math.max(8, Math.min(x, window.innerWidth - width - 8)),
    y: Math.max(8, Math.min(y, window.innerHeight - height - 8)),
  };
}

function TreeNode({
  node,
  activeFileId,
  collapsedFolders,
  onToggleFolder,
  onOpenFile,
  onRenameFile,
  onDeleteFile,
  onContextMenu,
  depth = 0,
}) {
  const folders = [...node.folders.values()].sort((a, b) => a.name.localeCompare(b.name));
  const files = [...node.files].sort((a, b) => a.relative_path.localeCompare(b.relative_path));
  return (
    <>
      {folders.map((folder) => {
        const collapsed = collapsedFolders.has(folder.path);
        return (
          <div key={folder.path}>
            <button
              type="button"
              className="pw-tree-folder"
              style={{ paddingLeft: 10 + depth * 14 }}
              onClick={() => onToggleFolder(folder.path)}
              onContextMenu={(event) => onContextMenu(event, { type: "folder", path: folder.path, name: folder.name })}
            >
              <span>{collapsed ? "▸" : "▾"}</span>
              <strong>{folder.name}</strong>
            </button>
            {!collapsed && (
              <TreeNode
                node={folder}
                activeFileId={activeFileId}
                collapsedFolders={collapsedFolders}
                onToggleFolder={onToggleFolder}
                onOpenFile={onOpenFile}
                onRenameFile={onRenameFile}
                onDeleteFile={onDeleteFile}
                onContextMenu={onContextMenu}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
      {files.map((file) => (
        <div
          key={file.id}
          className={`pw-tree-file${activeFileId === file.id ? " is-active" : ""}`}
          style={{ paddingLeft: 24 + depth * 14 }}
          onContextMenu={(event) => onContextMenu(event, { type: "file", file })}
        >
          <button type="button" onClick={() => onOpenFile(file.id)} title={file.relative_path}>
            <span>{getExt(file.relative_path).replace(".", "") || "txt"}</span>
            <strong>{file.filename}</strong>
          </button>
          <button type="button" onClick={() => onRenameFile(file)} title="重命名">✎</button>
          <button type="button" onClick={() => onDeleteFile(file)} title="删除">×</button>
        </div>
      ))}
    </>
  );
}

function LibraryResourceTree({
  materials,
  activeResourceKey,
  onOpen,
  onContextMenu,
}) {
  return (
    <>
      {materials.map((item) => {
        const resourceKey = `library-${item.id}`;
        const name = getDisplayFilename(item);
        return (
          <div
            key={resourceKey}
            className={`pw-tree-file pw-tree-file--library${activeResourceKey === resourceKey ? " is-active" : ""}`}
            style={{ paddingLeft: 12 }}
            onContextMenu={(event) => onContextMenu(event, { type: "library-file", material: item })}
          >
            <button type="button" onClick={() => onOpen(item)} title={name}>
              <span>{getResourceIcon(item)}</span>
              <strong>{name}</strong>
            </button>
          </div>
        );
      })}
    </>
  );
}

function MarkdownResourceView({ value, mode, onModeChange }) {
  return (
    <div className={`pw-markdown-view pw-markdown-view--${mode}`}>
      <div className="pw-resource-modebar">
        {["edit", "preview", "split"].map((item) => (
          <button key={item} type="button" className={mode === item ? "is-active" : ""} onClick={() => onModeChange(item)}>
            {item === "edit" ? "Edit" : item === "preview" ? "Preview" : "Split"}
          </button>
        ))}
      </div>
      <div className="pw-markdown-body">
        {(mode === "edit" || mode === "split") && (
          <div className="pw-markdown-source">
            <Editor
              height="100%"
              language="markdown"
              value={value || ""}
              theme="light"
              options={{
                readOnly: true,
                minimap: { enabled: false },
                lineNumbers: "on",
                wordWrap: "on",
                scrollBeyondLastLine: false,
                automaticLayout: true,
              }}
            />
          </div>
        )}
        {(mode === "preview" || mode === "split") && (
          <div className="pw-markdown-preview">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {value || "_Empty markdown resource._"}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProgrammingWorkbench({
  user,
  apiBase = "/api",
  homeData,
  initialProjectId = null,
  initialExerciseId = null,
  initialLanguageSelection = "",
  onProjectChanged,
  onOpenQuestions,
  onGoHome,
}) {
  const onboardingLanguage = normalizeLanguage(homeData?.onboarding?.main_language || user?.default_course_id || "");
  const [projects, setProjects] = useState([]);
  const [libraryMaterials, setLibraryMaterials] = useState([]);
  const [projectFileCache, setProjectFileCache] = useState({});
  const [expandedProjectIds, setExpandedProjectIds] = useState(() => new Set());
  const [selectedLanguage, setSelectedLanguage] = useState(() => normalizeLanguage(initialLanguageSelection) || onboardingLanguage || "Python");
  const [project, setProject] = useState(null);
  const [files, setFiles] = useState([]);
  const [activeFileId, setActiveFileId] = useState(null);
  const [openTabs, setOpenTabs] = useState([]);
  const [dirtyFiles, setDirtyFiles] = useState(() => new Set());
  const [collapsedFolders, setCollapsedFolders] = useState(() => new Set());
  const [explorerCollapsed, setExplorerCollapsedState] = useState(() => readUiPreference("explorerCollapsed", false));
  const [coachCollapsed, setCoachCollapsedState] = useState(() => readUiPreference("coachCollapsed", true));
  const [outputCollapsed, setOutputCollapsedState] = useState(() => readUiPreference("outputCollapsed", true));
  const [fontSize, setFontSize] = useState(16);
  const [theme, setTheme] = useState("light");
  const [activeResultTab, setActiveResultTab] = useState("run");
  const [bottomHeight, setBottomHeight] = useState(250);
  const [cursorPosition, setCursorPosition] = useState({ lineNumber: 1, column: 1 });
  const [focusMode, setFocusMode] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runDetailsOpen, setRunDetailsOpen] = useState(false);
  const [compileDiagnostics, setCompileDiagnostics] = useState([]);
  const [monacoDiagnostics, setMonacoDiagnostics] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [messages, setMessages] = useState([]);
  const [coachSuggestionsVisible, setCoachSuggestionsVisible] = useState(true);
  const [coachQuestion, setCoachQuestion] = useState("");
  const [status, setStatus] = useState("");
  const [exercise, setExercise] = useState(null);
  const [exerciseResult, setExerciseResult] = useState(null);
  const [selectedSampleIndex, setSelectedSampleIndex] = useState(null);
  const [sampleResult, setSampleResult] = useState(null);
  const [testModal, setTestModal] = useState(null);
  const [testModalFilter, setTestModalFilter] = useState("all");
  const [fileListOpen, setFileListOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [saveState, setSaveState] = useState("已保存");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);
  const [runConfigOpen, setRunConfigOpen] = useState(false);
  const [runMode, setRunMode] = useState("project");
  const [resourceContents, setResourceContents] = useState({});
  const [markdownMode, setMarkdownMode] = useState("split");
  const [draftEntryFile, setDraftEntryFile] = useState("");
  const [draftMainClass, setDraftMainClass] = useState("");
  const [contextMenu, setContextMenu] = useState(null);
  const saveTimerRef = useRef(null);
  const workspaceRequestRef = useRef(0);
  const shellRef = useRef(null);
  const editorRef = useRef(null);
  const focusLayoutRef = useRef(null);
  const activeResource = String(activeFileId || "").startsWith("library-")
    ? libraryMaterials.find((item) => `library-${item.id}` === activeFileId)
    : null;
  const language = selectedLanguage || project?.language || onboardingLanguage || "Python";
  const exerciseIdentity = `${user?.id || user?.username || "anonymous"}:${language}:${initialExerciseId || project?.programming_exercise_id || "none"}`;
  const editableFiles = useMemo(() => {
    const manifestPaths = exercise?.manifest?.editable_files;
    if (Array.isArray(manifestPaths) && manifestPaths.length) {
      const allowed = new Set(manifestPaths.map((path) => String(path).replace(/\\/g, "/")));
      return files.filter((file) => allowed.has(String(file.relative_path || "").replace(/\\/g, "/")));
    }
    return files.filter((file) => !/^(test|tests|test-framework)\//i.test(String(file.relative_path || "")));
  }, [exercise?.manifest?.editable_files, files]);
  const activeFile = activeResource ? null : (editableFiles.find((file) => file.id === activeFileId) || editableFiles[0] || null);
  const sourceFiles = useMemo(
    () => editableFiles.filter((file) => isSourceFileForLanguage(file.relative_path, language)),
    [editableFiles, language],
  );
  const javaMainClasses = useMemo(
    () => files.map(detectJavaMainClass).filter(Boolean),
    [files],
  );
  const uniqueJavaMainClasses = useMemo(() => [...new Set(javaMainClasses)], [javaMainClasses]);
  const activeJavaMainClass = useMemo(() => detectJavaMainClass(activeFile), [activeFile]);
  const runTargetLabel = useMemo(() => {
    if (!project) return "入口：未选择练习";
    if (exercise?.manifest?.editable_files?.length) return `文件：${exercise.manifest.editable_files[0]}`;
    if (language === "Java") return `入口：${project.main_class || uniqueJavaMainClasses[0] || "Main"}`;
    return `入口：${project.entry_file || activeFile?.relative_path || DEFAULT_FILE[language]}`;
  }, [activeFile?.relative_path, exercise, language, project, uniqueJavaMainClasses]);
  const relayoutEditor = useCallback(() => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => editorRef.current?.layout?.());
    });
  }, []);

  const setExplorerCollapsed = (value) => {
    setExplorerCollapsedState(value);
    writeUiPreference("explorerCollapsed", value);
    relayoutEditor();
  };

  const setCoachCollapsed = (value) => {
    setCoachCollapsedState(value);
    writeUiPreference("coachCollapsed", value);
    relayoutEditor();
  };

  const setOutputCollapsed = (value) => {
    setOutputCollapsedState(value);
    writeUiPreference("outputCollapsed", value);
    relayoutEditor();
  };

  const filteredProjects = useMemo(
    () => projects.filter((item) => normalizeLanguage(item.language) === language),
    [language, projects],
  );
  const visibleLibraryMaterials = useMemo(
    () => libraryMaterials
      .filter((item) => isResourceForLanguage(item, language))
      .sort((a, b) => getDisplayFilename(a).localeCompare(getDisplayFilename(b), "zh-CN")),
    [language, libraryMaterials],
  );
  const activeDiagnostics = compileDiagnostics.length
    ? compileDiagnostics
    : monacoDiagnostics.filter((marker) => marker.severity === 8 || marker.severity === 4).map((marker) => markerToProblem(marker, activeFile));
  const diagnosticSummary = activeDiagnostics.reduce((acc, item) => {
    if (item.severity === "warning") acc.warnings += 1;
    else acc.errors += 1;
    return acc;
  }, { errors: 0, warnings: 0 });

  const loadProject = useCallback(async (projectId, requestId = workspaceRequestRef.current) => {
    if (!user?.username || !projectId) return null;
    const res = await fetch(`${apiBase}/code/projects/${projectId}?username=${encodeURIComponent(user.username)}`);
    const data = await safeJson(res);
    if (requestId !== workspaceRequestRef.current) return null;
    if (!res.ok || !data.project) {
      setStatus(data.detail || "项目读取失败");
      return null;
    }
    const nextProject = data.project;
    setSelectedLanguage(normalizeLanguage(nextProject.language));
    setProject(nextProject);
    setFiles(nextProject.files || []);
    setProjectFileCache((prev) => ({ ...prev, [nextProject.id]: nextProject.files || [] }));
    setExpandedProjectIds((prev) => new Set(prev).add(nextProject.id));
    const firstFile = nextProject.files?.find((file) => file.relative_path === nextProject.entry_file) || nextProject.files?.[0];
    setActiveFileId(firstFile?.id || null);
    setOpenTabs((nextProject.files || []).map((file) => file.id));
    setDirtyFiles(new Set());
    setSaveState("已保存");
    setCompileDiagnostics([]);
    setMonacoDiagnostics([]);
    relayoutEditor();
    return nextProject;
  }, [apiBase, relayoutEditor, user?.username]);

  const ensureProjectFiles = useCallback(async (projectId) => {
    if (!user?.username || !projectId) return [];
    if (projectFileCache[projectId]) return projectFileCache[projectId];
    const res = await fetch(`${apiBase}/code/projects/${projectId}?username=${encodeURIComponent(user.username)}`);
    const data = await safeJson(res);
    if (!res.ok || !data.project) {
      setStatus(data.detail || "项目文件读取失败");
      return [];
    }
    const nextFiles = data.project.files || [];
    setProjectFileCache((prev) => ({ ...prev, [projectId]: nextFiles }));
    return nextFiles;
  }, [apiBase, projectFileCache, user?.username]);

  const toggleProjectExpanded = useCallback(async (item) => {
    if (!item?.id) return;
    const isExpanded = expandedProjectIds.has(item.id);
    if (isExpanded) {
      setExpandedProjectIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
      return;
    }
    setExpandedProjectIds((prev) => new Set(prev).add(item.id));
    await ensureProjectFiles(item.id);
  }, [ensureProjectFiles, expandedProjectIds]);

  const activateProject = useCallback(async (item) => {
    if (!item?.id) return;
    await loadProject(item.id);
  }, [loadProject]);

  const openProjectFile = useCallback(async (projectId, fileId) => {
    if (project?.id !== projectId) await loadProject(projectId);
    setActiveFileId(fileId);
    setOpenTabs((prev) => (prev.includes(fileId) ? prev : [...prev, fileId]));
  }, [loadProject, project?.id]);

  const loadProjects = useCallback(async () => {
    const requestId = workspaceRequestRef.current;
    if (!user?.username || !initialProjectId) {
      setProjects([]);
      return;
    }
    const res = await fetch(`${apiBase}/code/projects/${initialProjectId}?username=${encodeURIComponent(user.username)}`);
    const data = await safeJson(res);
    if (requestId !== workspaceRequestRef.current) return;
    if (!res.ok) {
      setStatus(data.detail || "练习工作区读取失败");
      return;
    }
    setProjects([]);
    if (data.project) await loadProject(data.project.id, requestId);
  }, [apiBase, initialProjectId, loadProject, user?.username]);

  useEffect(() => {
    const requestId = ++workspaceRequestRef.current;
    window.clearTimeout(saveTimerRef.current);
    setProject(null);
    setFiles([]);
    setOpenTabs([]);
    setActiveFileId(null);
    setDirtyFiles(new Set());
    setCollapsedFolders(new Set());
    setRunResult(null);
    setRunDetailsOpen(false);
    setCompileDiagnostics([]);
    setMonacoDiagnostics([]);
    setFeedback("");
    setExerciseResult(null);
    setSelectedSampleIndex(null);
    setSampleResult(null);
    setTestModal(null);
    setTestModalFilter("all");
    setFileListOpen(false);
    setMessages([]);
    setCoachQuestion("");
    setCoachSuggestionsVisible(true);
    setResourceContents({});
    setContextMenu(null);
    setRunConfigOpen(false);
    setStatus("");
    setSaveState("已保存");
    const nextLanguage = normalizeLanguage(initialLanguageSelection);
    if (nextLanguage) setSelectedLanguage(nextLanguage);
    relayoutEditor();
    return () => {
      if (requestId === workspaceRequestRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [initialExerciseId, initialLanguageSelection, relayoutEditor]);

  useEffect(() => () => {
    const model = editorRef.current?.getModel?.();
    model?.dispose?.();
    editorRef.current = null;
  }, [exerciseIdentity, activeFile?.id]);

  useEffect(() => { loadProjects(); }, [loadProjects]);

  useEffect(() => {
    const exerciseId = initialExerciseId || project?.programming_exercise_id;
    if (!exerciseId) {
      setExercise(null);
      setExerciseResult(null);
      return undefined;
    }
    let cancelled = false;
    fetch(`${apiBase}/programming/exercises/${exerciseId}`)
      .then(safeJson)
      .then((data) => { if (!cancelled) setExercise(data.exercise || null); })
      .catch(() => { if (!cancelled) setExercise(null); });
    return () => { cancelled = true; };
  }, [apiBase, initialExerciseId, project?.programming_exercise_id]);

  const refreshWorkspace = useCallback(async () => {
    await loadProjects();
    setContextMenu(null);
  }, [loadProjects]);

  useEffect(() => {
    const onFullscreenChange = () => {
      const active = document.fullscreenElement === shellRef.current;
      setIsFullscreen(active);
      if (active) setFullscreenFallback(false);
      relayoutEditor();
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, [relayoutEditor]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key !== "Escape") return;
      if (fullscreenFallback) {
        setFullscreenFallback(false);
        setIsFullscreen(false);
        relayoutEditor();
        return;
      }
      if (document.fullscreenElement === shellRef.current) {
        document.exitFullscreen?.();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [fullscreenFallback, relayoutEditor]);

  useEffect(() => {
    const node = shellRef.current;
    if (!node || !window.ResizeObserver) return undefined;
    const observer = new ResizeObserver(() => relayoutEditor());
    observer.observe(node);
    return () => observer.disconnect();
  }, [relayoutEditor]);

  useEffect(() => {
    relayoutEditor();
  }, [coachCollapsed, explorerCollapsed, outputCollapsed, isFullscreen, fullscreenFallback, selectedLanguage, relayoutEditor]);

  useEffect(() => {
    setDraftEntryFile(project?.entry_file || activeFile?.relative_path || DEFAULT_FILE[language] || "");
    setDraftMainClass(project?.main_class || uniqueJavaMainClasses[0] || "");
  }, [activeFile?.relative_path, language, project?.entry_file, project?.main_class, uniqueJavaMainClasses]);

  useEffect(() => {
    const closeMenu = (event) => {
      const target = event.target;
      if (target?.closest?.("[data-action='top-more'], .pw-context-menu")) return;
      setContextMenu(null);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setContextMenu(null);
        setRunConfigOpen(false);
      }
    };
    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  const createProject = useCallback(async (preferredLanguage = language, askName = true) => {
    if (!user?.username) return;
    const lockedLanguage = normalizeLanguage(preferredLanguage) || language;
    const defaultName = `${lockedLanguage} 项目`;
    let name = defaultName;
    if (askName) {
      try {
        name = window.prompt("项目名称", defaultName);
      } catch {
        name = defaultName;
      }
    }
    if (name === null) return;
    const res = await fetch(`${apiBase}/code/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: user.username,
        course_id: PROJECT_COURSE_ID,
        name: name.trim() || `${lockedLanguage} 项目`,
        language: lockedLanguage,
      }),
    });
    const data = await safeJson(res);
    if (!res.ok || !data.project) {
      setStatus(data.detail || "项目创建失败");
      return;
    }
    setSelectedLanguage(lockedLanguage);
    setProjects((prev) => [data.project, ...prev.filter((item) => item.id !== data.project.id)]);
    setProject(data.project);
    setFiles(data.project.files || []);
    const firstFile = data.project.files?.[0];
    setActiveFileId(firstFile?.id || null);
    setOpenTabs(firstFile ? [firstFile.id] : []);
    onProjectChanged?.();
    relayoutEditor();
  }, [apiBase, language, onProjectChanged, relayoutEditor, user?.username]);

  const updateProjectFile = useCallback(async (fileId, patch, quiet = false) => {
    if (!project?.id || !user?.username) return null;
    if (!quiet) setSaveState("保存中...");
    const res = await fetch(`${apiBase}/code/projects/${project.id}/files/${fileId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username, ...patch }),
    });
    const data = await safeJson(res);
    if (!res.ok || !data.file) {
      setSaveState("保存失败");
      setStatus(data.detail || "文件保存失败");
      return null;
    }
    setFiles((prev) => prev.map((file) => (file.id === fileId ? data.file : file)));
    setDirtyFiles((prev) => {
      const next = new Set(prev);
      next.delete(fileId);
      return next;
    });
    setSaveState("已保存");
    onProjectChanged?.();
    return data.file;
  }, [apiBase, onProjectChanged, project?.id, user?.username]);

  const scheduleAutosave = useCallback((fileId, content) => {
    window.clearTimeout(saveTimerRef.current);
    setSaveState("未保存");
    saveTimerRef.current = window.setTimeout(() => {
      updateProjectFile(fileId, { content }, true);
    }, 700);
  }, [updateProjectFile]);

  useEffect(() => () => window.clearTimeout(saveTimerRef.current), []);

  const openFile = (fileId) => {
    setActiveFileId(fileId);
    setOpenTabs((prev) => (prev.includes(fileId) ? prev : [...prev, fileId]));
  };

  const openLibraryResource = async (material) => {
    if (!material?.id || !user?.username) return;
    const key = `library-${material.id}`;
    setActiveFileId(key);
    setOpenTabs((prev) => (prev.includes(key) ? prev : [...prev, key]));
    if (resourceContents[key]?.loaded) return;
    const kind = getResourceKind(material);
    setResourceContents((prev) => ({ ...prev, [key]: { loading: true, loaded: false } }));
    try {
      const detailRes = await fetch(`${apiBase}/materials/${material.id}?username=${encodeURIComponent(user.username)}`);
      const detailData = await safeJson(detailRes);
      const detail = detailData.material || material;
      let content = detail.extracted_text || "";
      if (["code", "text", "markdown"].includes(kind)) {
        const previewUrl = getMaterialPreviewUrl(apiBase, material, user.username);
        const previewRes = await fetch(previewUrl);
        if (previewRes.ok) content = await previewRes.text();
      }
      setResourceContents((prev) => ({
        ...prev,
        [key]: {
          loading: false,
          loaded: true,
          material: detail,
          content,
          previewUrl: getMaterialPreviewUrl(apiBase, material, user.username),
          downloadUrl: getMaterialDownloadUrl(apiBase, material, user.username),
        },
      }));
    } catch {
      setResourceContents((prev) => ({
        ...prev,
        [key]: {
          loading: false,
          loaded: true,
          material,
          content: "",
          error: "Resource preview failed",
          previewUrl: getMaterialPreviewUrl(apiBase, material, user.username),
          downloadUrl: getMaterialDownloadUrl(apiBase, material, user.username),
        },
      }));
    }
  };

  const closeTab = (fileId) => {
    setOpenTabs((prev) => {
      const next = prev.filter((id) => id !== fileId);
      if (activeFileId === fileId) setActiveFileId(next[next.length - 1] || files[0]?.id || null);
      return next;
    });
  };

  const createFileWithPath = async (path) => {
    if (!project?.id || !user?.username) return;
    const res = await fetch(`${apiBase}/code/projects/${project.id}/files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username, relative_path: path.trim(), content: "" }),
    });
    const data = await safeJson(res);
    if (!res.ok || !data.file) {
      setStatus(data.detail || "文件创建失败");
      return;
    }
    setFiles((prev) => [...prev, data.file].sort((a, b) => a.relative_path.localeCompare(b.relative_path)));
    openFile(data.file.id);
    onProjectChanged?.();
    return data.file;
  };

  const addLibraryResourceToProject = async (material) => {
    if (!project?.id || !material?.id || !user?.username) return;
    const kind = getResourceKind(material);
    if (!["code", "text", "markdown"].includes(kind)) {
      setStatus("Only text-like resources can be added to the current project.");
      setContextMenu(null);
      return;
    }
    const filename = getDisplayFilename(material);
    const targetPath = window.prompt("Add to project as", filename);
    if (!targetPath) return;
    let content = resourceContents[`library-${material.id}`]?.content || "";
    try {
      const previewRes = await fetch(getMaterialPreviewUrl(apiBase, material, user.username));
      if (previewRes.ok) content = await previewRes.text();
    } catch {
      // Keep the already loaded extracted text fallback when preview fetch fails.
    }
    const res = await fetch(`${apiBase}/code/projects/${project.id}/files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username, relative_path: targetPath.trim(), content }),
    });
    const data = await safeJson(res);
    if (!res.ok || !data.file) {
      setStatus(data.detail || "Add to project failed");
      return;
    }
    setFiles((prev) => [...prev, data.file].sort((a, b) => a.relative_path.localeCompare(b.relative_path)));
    openFile(data.file.id);
    setStatus("Resource copied into current project.");
    setContextMenu(null);
    onProjectChanged?.();
  };

  const downloadLibraryResource = (material) => {
    const url = getMaterialDownloadUrl(apiBase, material, user?.username);
    if (url) window.open(url, "_blank", "noopener,noreferrer");
    setContextMenu(null);
  };

  const deleteLibraryResource = async (material) => {
    if (!material?.id || !user?.username) return;
    if (!window.confirm(`Delete ${getDisplayFilename(material)} from programming library?`)) return;
    const res = await fetch(`${apiBase}/materials/${material.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    const data = await safeJson(res);
    if (!res.ok) {
      setStatus(data.detail || "Delete library resource failed");
      return;
    }
    setLibraryMaterials((prev) => prev.filter((item) => item.id !== material.id));
    closeTab(`library-${material.id}`);
    setContextMenu(null);
    setStatus("Library resource deleted.");
    onProjectChanged?.();
  };

  const createFile = async () => {
    const path = window.prompt("文件路径，例如 src/main.py 或 calculator.h", DEFAULT_FILE[language] || "main.py");
    if (!path) return;
    await createFileWithPath(path);
  };

  const createFolder = async () => {
    const folder = window.prompt("文件夹名称，例如 src 或 models");
    if (!folder) return;
    const filename = window.prompt("新文件名", language === "Java" ? "Main.java" : "index.txt");
    if (!filename) return;
    await createFileWithPath(`${folder.replace(/\/+$/, "")}/${filename}`);
  };

  const renameFile = async (file) => {
    const nextPath = window.prompt("新的文件路径", file.relative_path);
    if (!nextPath || nextPath === file.relative_path) return;
    const updated = await updateProjectFile(file.id, { relative_path: nextPath });
    if (updated) {
      setOpenTabs((prev) => (prev.includes(file.id) ? prev : [...prev, file.id]));
      setStatus("文件已重命名");
    }
  };

  const deleteFile = async (file) => {
    if (!window.confirm(`确认删除 ${file.relative_path} 吗？`)) return;
    const res = await fetch(`${apiBase}/code/projects/${project.id}/files/${file.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    const data = await safeJson(res);
    if (!res.ok) {
      setStatus(data.detail || "文件删除失败");
      return;
    }
    setFiles((prev) => prev.filter((item) => item.id !== file.id));
    closeTab(file.id);
    if (project.entry_file === file.relative_path) {
      const nextEntry = files.find((item) => item.id !== file.id && isSourceFileForLanguage(item.relative_path, language))?.relative_path || "";
      await updateProjectMeta({ entry_file: nextEntry });
    }
    if (language === "Java" && project.main_class && detectJavaMainClass(file) === project.main_class) {
      await updateProjectMeta({ main_class: "" });
      setStatus("当前 Java 主类已删除，请重新选择运行配置。");
    }
    onProjectChanged?.();
  };

  const manualSave = async () => {
    window.clearTimeout(saveTimerRef.current);
    if (!activeFile) return;
    await updateProjectFile(activeFile.id, { content: activeFile.content || "" });
  };

  const renameProject = async () => {
    if (!project) return;
    const name = window.prompt("项目名称", project.name);
    if (!name || name.trim() === project.name) return;
    await updateProjectMeta({ name: name.trim() });
  };

  const deleteProject = async () => {
    if (!project?.id || !user?.username) return;
    if (!window.confirm(`Confirm delete project ${project.name}?`)) return;
    const res = await fetch(`${apiBase}/code/projects/${project.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    const data = await safeJson(res);
    if (!res.ok) {
      setStatus(data.detail || "Project delete failed");
      return;
    }
    setProjects((prev) => prev.filter((item) => item.id !== project.id));
    setProject(null);
    setFiles([]);
    setOpenTabs([]);
    setActiveFileId(null);
    setStatus("Project deleted");
    onProjectChanged?.();
  };

  const editEntryFile = async () => {
    setRunConfigOpen(true);
    return;
    if (!project) return;
    const entryFile = window.prompt("入口文件", project.entry_file);
    if (!entryFile || entryFile === project.entry_file) return;
    await updateProjectMeta({ entry_file: entryFile });
  };

  const updateProjectMeta = async (patch) => {
    if (!project?.id || !user?.username) return;
    const res = await fetch(`${apiBase}/code/projects/${project.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username, ...patch }),
    });
    const data = await safeJson(res);
    if (res.ok && data.project) {
      setProject(data.project);
      if (data.project.files) setFiles(data.project.files);
      setProjects((prev) => prev.map((item) => (item.id === data.project.id ? { ...item, ...data.project } : item)));
      onProjectChanged?.();
    } else {
      setStatus(data.detail || "项目设置保存失败");
    }
  };

  const saveRunConfig = async () => {
    if (!project) return;
    const patch = {
      entry_file: draftEntryFile || project.entry_file || activeFile?.relative_path || DEFAULT_FILE[language],
    };
    if (language === "Java") patch.main_class = draftMainClass || uniqueJavaMainClasses[0] || "";
    await updateProjectMeta(patch);
    setRunConfigOpen(false);
    setStatus("运行配置已保存");
  };

  const changeRunTarget = async (value) => {
    if (!project) return;
    if (language === "Java") {
      setDraftMainClass(value);
      await updateProjectMeta({ main_class: value });
      return;
    }
    setDraftEntryFile(value);
    await updateProjectMeta({ entry_file: value });
  };

  const openTopMenu = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({ type: "top", ...clampMenuPosition(event.clientX, event.clientY) });
  };

  const selectResultTab = (tab) => {
    if (activeResultTab === tab && !outputCollapsed) {
      setOutputCollapsed(true);
      return;
    }
    setActiveResultTab(tab);
    setOutputCollapsed(false);
  };

  const openFeedback = () => {
    analyzeProject();
  };

  const openCoach = () => {
    setCoachCollapsed(false);
  };

  const openRunConfig = () => {
    setRunConfigOpen(true);
    setContextMenu(null);
  };

  const adjustFontSize = (delta) => {
    setFontSize((size) => Math.max(12, Math.min(24, size + delta)));
    setContextMenu(null);
  };

  const switchTheme = (nextTheme) => {
    setTheme(nextTheme);
    setContextMenu(null);
  };

  const startBottomResize = (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = bottomHeight;
    const onMove = (moveEvent) => {
      const nextHeight = Math.max(150, Math.min(320, startHeight + startY - moveEvent.clientY));
      setBottomHeight(nextHeight);
      relayoutEditor();
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const toggleFocusMode = () => {
    const next = !focusMode;
    setFocusMode(next);
    if (next) {
      focusLayoutRef.current = { explorerCollapsed, coachCollapsed, outputCollapsed };
      setExplorerCollapsed(true);
      setCoachCollapsed(true);
      setOutputCollapsed(true);
    } else {
      const previous = focusLayoutRef.current;
      setExplorerCollapsed(previous?.explorerCollapsed ?? false);
      setCoachCollapsed(previous?.coachCollapsed ?? false);
      setOutputCollapsed(previous?.outputCollapsed ?? false);
      focusLayoutRef.current = null;
    }
    relayoutEditor();
    setContextMenu(null);
  };

  const collapseAllFolders = () => {
    const paths = [];
    const collect = (node) => {
      [...node.folders.values()].forEach((folder) => {
        paths.push(folder.path);
        collect(folder);
      });
    };
    collect(tree);
    setCollapsedFolders(new Set(paths));
    setContextMenu(null);
  };

  const openContextMenu = (event, target) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({ ...target, ...clampMenuPosition(event.clientX, event.clientY) });
  };

  const createFileInFolder = async (folderPath = "") => {
    const name = window.prompt("新建文件名", language === "Java" ? "Student.java" : DEFAULT_FILE[language] || "main.py");
    if (!name) return;
    await createFileWithPath(joinPath(folderPath, name));
    setContextMenu(null);
  };

  const createFolderInFolder = async (folderPath = "") => {
    const name = window.prompt("新建文件夹名", "models");
    if (!name) return;
    await createFileWithPath(joinPath(joinPath(folderPath, name), ".keep"));
    setContextMenu(null);
  };

  const renameFolder = async (folderPath) => {
    const nextName = window.prompt("新的文件夹路径", folderPath);
    if (!nextName || nextName === folderPath) return;
    const prefix = `${folderPath.replace(/\/+$/, "")}/`;
    const nextPrefix = `${nextName.replace(/\/+$/, "")}/`;
    const folderFiles = files.filter((file) => file.relative_path.startsWith(prefix));
    for (const file of folderFiles) {
      await updateProjectFile(file.id, { relative_path: file.relative_path.replace(prefix, nextPrefix) });
    }
    setStatus("文件夹已重命名");
    setContextMenu(null);
  };

  const deleteFolder = async (folderPath) => {
    const prefix = `${folderPath.replace(/\/+$/, "")}/`;
    const folderFiles = files.filter((file) => file.relative_path.startsWith(prefix));
    if (!folderFiles.length) return;
    if (!window.confirm(`确认删除文件夹 ${folderPath} 及其中 ${folderFiles.length} 个文件吗？`)) return;
    for (const file of folderFiles) {
      await fetch(`${apiBase}/code/projects/${project.id}/files/${file.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    }
    setFiles((prev) => prev.filter((file) => !file.relative_path.startsWith(prefix)));
    setOpenTabs((prev) => prev.filter((id) => !folderFiles.some((file) => file.id === id)));
    if (project.entry_file?.startsWith(prefix)) await updateProjectMeta({ entry_file: "" });
    if (language === "Java" && folderFiles.some((file) => detectJavaMainClass(file) === project.main_class)) {
      await updateProjectMeta({ main_class: "" });
    }
    setStatus("文件夹已删除");
    setContextMenu(null);
    onProjectChanged?.();
  };

  const setFileAsRunTarget = async (file) => {
    const patch = { entry_file: file.relative_path };
    const javaMain = detectJavaMainClass(file);
    if (language === "Java" && javaMain) patch.main_class = javaMain;
    await updateProjectMeta(patch);
    setDraftEntryFile(file.relative_path);
    if (javaMain) setDraftMainClass(javaMain);
    setStatus(language === "Java" ? "Java 主类已设置" : "入口文件已设置");
    setContextMenu(null);
  };

  const runFile = async (file) => {
    if (!file) return;
    const javaMain = detectJavaMainClass(file);
    if (language === "Java" && !javaMain) {
      setStatus("该 Java 文件没有 main 方法，不能作为运行目标。");
      setContextMenu(null);
      return;
    }
    await setFileAsRunTarget(file);
    await runProject({ entryFile: file.relative_path, mainClass: javaMain || project.main_class });
  };

  const openProblem = async (item) => {
    if (!item?.file) return;
    const normalizedFile = String(item.file).replace(/\\/g, "/").replace(/^\.?\//, "");
    const matched = files.find((file) => file.relative_path === normalizedFile || file.relative_path.endsWith(`/${normalizedFile}`) || normalizedFile.endsWith(file.relative_path));
    if (!matched) return;
    openFile(matched.id);
    window.requestAnimationFrame(() => {
      if (item.line && editorRef.current?.revealLineInCenter) {
        editorRef.current.revealLineInCenter(Number(item.line));
        editorRef.current.setPosition?.({ lineNumber: Number(item.line), column: Number(item.column || 1) });
        editorRef.current.focus?.();
      }
    });
  };

  const openProblems = () => {
    setActiveResultTab("run");
    setOutputCollapsed(false);
    setRunDetailsOpen(true);
  };

  const runProject = async (override = {}) => {
    if (!project?.id) return;
    if (exercise) {
      if (selectedSampleIndex !== null && !override.forceAllTests) {
        await runExerciseSample(selectedSampleIndex);
      } else {
        await runExerciseCheck(false);
      }
      return;
    }
    if (language === "Java" && uniqueJavaMainClasses.length > 1 && !project.main_class && !override.mainClass) {
      setRunConfigOpen(true);
      setStatus("检测到多个 Java main class，请先选择运行主类。");
      return;
    }
    if (language === "Java" && runMode === "current-file" && activeFile && !activeJavaMainClass && !override.mainClass) {
      setStatus("当前 Java 文件没有 main 方法，不能直接运行。");
      return;
    }
    await manualSave();
    setBusy("run");
    setOutputCollapsed(false);
    setActiveResultTab("run");
    setRunResult(null);
    setRunDetailsOpen(false);
    setCompileDiagnostics([]);
    try {
      const res = await fetch(`${apiBase}/code/projects/${project.id}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          stdin: "",
          run_mode: "project",
          entry_file: project.entry_file,
          main_class: project.main_class || uniqueJavaMainClasses[0] || "",
          source_files: sourceFiles.map((file) => file.relative_path),
        }),
      });
      const data = await safeJson(res);
      const nextResult = res.ok ? data : { exit_code: -1, error_message: data.detail || "运行失败" };
      setRunResult(nextResult);
      setRunDetailsOpen(nextResult.exit_code !== 0 || Boolean(nextResult.stderr || nextResult.compile_error || nextResult.error_message));
      setCompileDiagnostics(parseCompilerDiagnostics(nextResult, project));
    } catch {
      const nextResult = { exit_code: -1, error_message: "无法连接后端服务。" };
      setRunResult(nextResult);
      setRunDetailsOpen(true);
      setCompileDiagnostics(parseCompilerDiagnostics(nextResult, project));
    } finally {
      setBusy("");
    }
  };

  const runExerciseSample = async (sampleIndex) => {
    if (!exercise?.id || !project?.id) return;
    setSelectedSampleIndex(sampleIndex);
    setSampleResult(null);
    setBusy("sample");
    setOutputCollapsed(false);
    setActiveResultTab("run");
    try {
      await manualSave();
      const res = await fetch(`${apiBase}/programming/exercises/${exercise.id}/samples/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, project_id: project.id, sample_index: sampleIndex }),
      });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "测试样例运行失败");
      setSampleResult(data);
      setRunResult({ ...(data.result || {}), actual_output: data.actual_output, expected_output: data.expected_output, duration_ms: data.duration_ms, test_name: data.test_name, timeout: data.timeout, technical_details: data.technical_details || data.result?.technical_details });
      setRunDetailsOpen(false);
      setCompileDiagnostics(parseCompilerDiagnostics(data.result || data, project));
      setStatus(data.passed ? "测试样例通过" : "测试样例未通过");
    } catch (err) {
      setStatus(err.message || "测试样例运行失败");
    } finally {
      setBusy("");
    }
  };

  const runExerciseCheck = async (submission) => {
    if (!exercise?.id || !project?.id) return;
    setBusy(submission ? "submit" : "test");
    setSampleResult(null);
    setOutputCollapsed(true);
    setActiveResultTab("tests");
    try {
      await manualSave();
      const res = await fetch(`${apiBase}/programming/exercises/${exercise.id}/${submission ? "submit" : "test"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, project_id: project.id }),
      });
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "题目校验失败");
      setExerciseResult(data);
      setRunResult(data.result || null);
      setRunDetailsOpen(false);
      setFeedback(`通过 ${data.passed_count}/${data.total_count}\n${data.ai_explanation || ""}`);
      setTestModal({ mode: submission ? "submit" : "test" });
      setTestModalFilter("all");
      setStatus(data.passed ? "题目校验通过" : "题目校验未通过");
    } catch (err) {
      setStatus(err.message || "题目校验失败");
    } finally {
      setBusy("");
    }
  };

  const analyzeProject = async (question) => {
    const text = question || "请基于当前项目上下文进行判题式分析，指出错误、可改进点和下一步建议。";
    if (!activeFile && !activeResource) return;
    setBusy(question ? "coach" : "feedback");
    setOutputCollapsed(false);
    setActiveResultTab(question ? activeResultTab : "feedback");
    if (question) {
      setCoachSuggestionsVisible(false);
      setMessages((prev) => [...prev, { role: "user", content: question }]);
    }
    try {
      await manualSave();
       const treeText = editableFiles.map((file) => `- ${file.relative_path}`).join("\n");
       const recentTests = exerciseResult ? {
         total: exerciseResult.total_count || 0,
         passed: exerciseResult.passed_count || 0,
         results: (exerciseResult.cases || []).map(normalizeResultCase),
       } : null;
       const diagnostics = {
         status: activeDiagnostics.length ? "has_diagnostics" : "clean",
         errors: activeDiagnostics.filter((item) => item.severity !== "warning"),
         warnings: activeDiagnostics.filter((item) => item.severity === "warning"),
       };
      if (activeResource) {
        const resourceText = activeResourceContent.content || activeResource.summary || "";
        const resourceContext = `Resource: ${getDisplayFilename(activeResource)}\nType: ${getResourceKind(activeResource)}\nReadonly StudyMaterial from programming library.\n\n--- Resource text ---\n${resourceText || "No extracted text is available for this resource."}`;
        const res = await fetch(`${apiBase}/code/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
             body: JSON.stringify({
               username: user.username,
               course_id: PROJECT_COURSE_ID,
               session_id: null,
               challenge_id: null,
               exercise_id: exercise?.id || null,
               language,
               code: resourceContext,
               question: text,
               last_run_result: runResult,
               last_test_results: recentTests,
               diagnostics,
               chat_history: messages,
             }),
        });
        const data = await safeJson(res);
        const answer = res.ok ? data.answer || "AI analysis complete." : data.detail || "AI analysis failed.";
        if (question) setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
        else setFeedback(answer);
        return;
      }
       const related = editableFiles
        .filter((file) => file.id !== activeFile.id)
        .slice(0, 5)
        .map((file) => `\n\n--- ${file.relative_path} ---\n${String(file.content || "").slice(0, 1800)}`)
        .join("");
      const codeContext = `当前练习：${getExerciseTitle(exercise)}\n语言：${exercise?.language || language}\n题目说明：${getExerciseDescription(exercise)}\n当前文件：${activeFile.relative_path}\n当前练习文件：\n${treeText}\n\n--- 当前文件内容 ---\n${activeFile.content || ""}${related}`;
      const res = await fetch(`${apiBase}/code/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
         body: JSON.stringify({
           username: user.username,
           course_id: PROJECT_COURSE_ID,
           session_id: null,
           challenge_id: null,
           exercise_id: exercise?.id || null,
           language: project.language,
           code: codeContext,
           question: text,
           last_run_result: runResult,
           last_test_results: recentTests,
           diagnostics,
           chat_history: messages,
         }),
      });
      const data = await safeJson(res);
      const answer = res.ok ? data.answer || "AI 分析完成。" : data.detail || "AI 分析失败。";
      if (question) setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
      else setFeedback(answer);
    } catch {
      if (question) setMessages((prev) => [...prev, { role: "assistant", content: "无法连接后端服务。" }]);
      else setFeedback("无法连接后端服务。");
    } finally {
      setBusy("");
      setCoachQuestion("");
    }
  };

  const resetCoach = () => {
    setMessages([]);
    setCoachQuestion("");
    setCoachSuggestionsVisible(true);
  };

  const toggleFullscreen = async () => {
    const node = shellRef.current;
    if (!node) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen?.();
      setFullscreenFallback(false);
      setIsFullscreen(false);
      return;
    }
    if (node.requestFullscreen) {
      try {
        await node.requestFullscreen();
        return;
      } catch {
        // Fall through to viewport fallback.
      }
    }
    setFullscreenFallback(true);
    setIsFullscreen(true);
    relayoutEditor();
  };

  const changeLanguageInIde = (nextLanguage) => {
    const normalized = normalizeLanguage(nextLanguage);
    if (!normalized || normalized === language) return;
    setSelectedLanguage(normalized);
    setProject(null);
    setFiles([]);
    setOpenTabs([]);
    setActiveFileId(null);
    setRunResult(null);
    setCompileDiagnostics([]);
    setMonacoDiagnostics([]);
    setFeedback("");
    setStatus("");
    setOutputCollapsed(true);
    relayoutEditor();
  };

  const resultText = activeResultTab === "run"
    ? formatRunResult(runResult)
    : activeResultTab === "tests"
      ? (exerciseResult ? `${exerciseResult.summary || `通过 ${exerciseResult.passed_count}/${exerciseResult.total_count}`}\n${exerciseResult.failed_categories?.length ? `失败类别：${exerciseResult.failed_categories.join("、")}` : "全部测试通过"}` : "点击“运行全部公开测试”或“提交”查看测试结果。")
      : activeResultTab === "problems"
        ? ""
        : feedback || "点击 AI 判题后，当前练习上下文反馈会显示在这里。";

  const tree = useMemo(() => buildTree(files), [files]);
  const projectTabs = openTabs
    .filter((id) => !String(id).startsWith("library-"))
    .map((id) => editableFiles.find((file) => file.id === id))
    .filter(Boolean);
  const resourceTabs = openTabs
    .filter((id) => String(id).startsWith("library-"))
    .map((id) => {
      const material = libraryMaterials.find((item) => `library-${item.id}` === id);
      return material ? { key: id, material } : null;
    })
    .filter(Boolean);
  const activeResourceContent = activeResource ? resourceContents[`library-${activeResource.id}`] || {} : {};
  const shellClassName = [
    "pw-shell",
    "pw-shell--workspace",
    explorerCollapsed ? "pw-shell--explorer-collapsed" : "",
    coachCollapsed ? "pw-shell--coach-collapsed" : "",
    outputCollapsed ? "pw-shell--output-collapsed" : "",
    focusMode ? "pw-shell--focus-mode" : "",
    isFullscreen || fullscreenFallback ? "pw-shell--fullscreen" : "",
    fullscreenFallback ? "pw-shell--fullscreen-fallback" : "",
  ].filter(Boolean).join(" ");

  return (
    <section className={shellClassName} ref={shellRef} data-workspace-language={selectedLanguage || ""}>
      <div className="pw-center">
        <div className="pw-topbar">
          <div className="pw-toolbar-left">
            <div className="pw-language-segment" aria-label="Programming language">
            {explorerCollapsed && (
              <button
                type="button"
                className="pw-tree-restore"
                onClick={() => setExplorerCollapsed(false)}
                title="显示题目"
                aria-label="显示题目"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h7l2 3h9v9H3V7Z" /></svg>
              </button>
            )}
              <span className="pw-current-language">{language}</span>
            </div>
          </div>
          <div className="pw-toolbar-center">
            <div className="pw-run-cluster">
              <span className="pw-run-target" title={activeFile?.relative_path || runTargetLabel}>{project ? (activeFile?.relative_path || runTargetLabel) : "入口：未选择练习"}</span>
              <button type="button" className="run-btn pw-icon-button pw-run-button" data-action="top-run" onClick={runProject} disabled={!project || busy === "run" || busy === "sample"} title={selectedSampleIndex === null ? "运行全部公开测试" : "运行当前样例"}>
                {busy === "run" ? "..." : "▶ 运行"}
              </button>
              {exercise && (
                <>
                  <button type="button" className="pw-top-exercise-action" onClick={() => runExerciseCheck(false)} disabled={!project || busy === "test" || busy === "submit"} title="运行全部公开测试">运行全部测试</button>
                  <button type="button" className="pw-top-exercise-action pw-top-exercise-action--primary" onClick={() => runExerciseCheck(true)} disabled={!project || busy === "test" || busy === "submit"} title="提交并运行完整官方测试">提交</button>
                  <div className="pw-file-list-wrap">
                    <button type="button" className="pw-top-exercise-action pw-file-list-trigger" onClick={() => setFileListOpen((open) => !open)} disabled={!editableFiles.length} aria-expanded={fileListOpen}>
                      文件列表
                    </button>
                    {fileListOpen && (
                      <div className="pw-file-list-popover" role="menu">
                        <strong>当前练习文件</strong>
                        {editableFiles.map((file) => (
                          <button key={file.id} type="button" className={file.id === activeFileId ? "is-active" : ""} onClick={() => { setActiveFileId(file.id); setOpenTabs((tabs) => tabs.includes(file.id) ? tabs : [...tabs, file.id]); setFileListOpen(false); }} title={file.relative_path}>
                            <span>{getFileIcon(file.relative_path)}</span>
                            <b>{file.relative_path}</b>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="pw-toolbar-right">
            <div className="pw-top-actions">
            <button type="button" className="pw-diagnostic-chip pw-diagnostic-chip--error" onClick={openProblems} title="打开问题查看错误">
              <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.5" /></svg>
              <span>{diagnosticSummary.errors}</span>
            </button>
            <button type="button" className="pw-diagnostic-chip pw-diagnostic-chip--warning" onClick={openProblems} title="打开问题查看警告">
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2 14 13H2L8 2Z" /></svg>
              <span>{diagnosticSummary.warnings}</span>
            </button>
            <span className="pw-save-chip">{saveState}</span>
            <button type="button" data-action="fullscreen" onClick={toggleFullscreen}>{isFullscreen || fullscreenFallback ? "退出全屏" : "全屏"}</button>
            <button type="button" className="pw-icon-button pw-more-button" data-action="top-more" onClick={openTopMenu} title="更多">...</button>
            </div>
          </div>
        </div>

        <div className="pw-workbench-body">
          {!explorerCollapsed && (
            <aside className="pw-explorer pw-exercise-sidebar">
              <div className="pw-exercise-sidebar-head">
                <span className="pw-tool-title">题目</span>
                <button type="button" onClick={() => setExplorerCollapsed(true)} title="折叠题目">‹</button>
              </div>
              {exercise ? (
                <div className="pw-exercise-sidebar-body">
                  <div className="pw-exercise-sidebar-meta">
                    <span>{exercise.language}</span>
                    <strong>{exercise.difficulty}</strong>
                  </div>
                  <h1>{getExerciseTitle(exercise)}</h1>
                  <div className="pw-exercise-sidebar-tags">
                    {(exercise.tags || []).map((tag) => <span key={tag}>{tag}</span>)}
                  </div>
                  <div className="pw-exercise-sidebar-copy">{getExerciseDescription(exercise)}</div>
                  <section className="pw-exercise-sidebar-section">
                    <h2>测试样例</h2>
                    {(exercise.public_samples || []).length ? (
                      (exercise.public_samples || []).slice(0, 8).map((sample, index) => (
                        <button
                          type="button"
                          className={`pw-exercise-example${selectedSampleIndex === index ? " is-selected" : ""}`}
                          key={`${sample.test_path}-${sample.selector}-${index}`}
                          onClick={() => runExerciseSample(index)}
                        >
                          <span>{sample.name || `样例 ${index + 1}`}</span>
                          <code>输入：{sample.input_display || "无参数"}</code>
                          <code>期望：{String(sample.expected ?? "")}</code>
                          {selectedSampleIndex === index && sampleResult && <em>{sampleResult.passed ? "通过" : "未通过"}</em>}
                        </button>
                      ))
                    ) : <p className="pw-exercise-example-empty">官方没有提供可公开展示的测试样例。</p>}
                  </section>
                </div>
              ) : (
                <div className="pw-exercise-sidebar-empty">
                  <strong>选择一道练习开始</strong>
                  <p>这里会显示中文题目、知识点、示例和约束。代码会自动保存，刷新后可继续。</p>
                  <button type="button" onClick={onOpenQuestions}>从题库选题</button>
                </div>
              )}
            </aside>
          )}

          <div className="pw-editor-area">
            <div className="pw-file-tabs">
              {projectTabs.map((file) => (
                <button key={file.id} type="button" className={`pw-file-tab${file.id === activeFileId ? " is-active" : ""}`} onClick={() => setActiveFileId(file.id)} title={file.relative_path}>
                  <span className={"pw-tab-icon pw-tab-icon--" + (getExt(file.relative_path).replace(".", "") || "txt")}>{getFileIcon(file.relative_path)}</span>
                  <span className={dirtyFiles.has(file.id) ? "pw-dirty-dot is-dirty" : "pw-dirty-dot"} />
                  <strong>{file.filename || getDisplayFilename(file)}</strong>
                  <b onClick={(event) => { event.stopPropagation(); closeTab(file.id); }}>×</b>
                </button>
              ))}
            </div>
            <div className="pw-editor-card">
              {activeFile ? (
                <Editor
                  height="100%"
                  key={`${exerciseIdentity}-${activeFile.id}`}
                  path={`exercise://${exerciseIdentity}/${activeFile.relative_path}`}
                  language={getMonacoLanguage(activeFile)}
                  value={activeFile.content || ""}
                  theme={theme === "dark" ? "vs-dark" : "light"}
                  onMount={(editor) => {
                    editorRef.current = editor;
                    setCursorPosition(editor.getPosition?.() || { lineNumber: 1, column: 1 });
                    editor.onDidChangeCursorPosition?.((event) => setCursorPosition(event.position));
                    relayoutEditor();
                  }}
                  onChange={(value) => {
                    const nextContent = value || "";
                    setFiles((prev) => prev.map((file) => (file.id === activeFile.id ? { ...file, content: nextContent } : file)));
                    setDirtyFiles((prev) => new Set(prev).add(activeFile.id));
                    setCompileDiagnostics([]);
                    scheduleAutosave(activeFile.id, nextContent);
                  }}
                  onValidate={(markers) => setMonacoDiagnostics(markers || [])}
                  options={{
                    fontSize,
                    minimap: { enabled: false },
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: getMonacoLanguage(activeFile) === "python" ? 4 : 2,
                    wordWrap: "on",
                  }}
                />
              ) : (
                <div className="pw-editor-empty">
                  <strong>从题库选择练习后开始编码</strong>
                  <button type="button" onClick={onOpenQuestions}>打开题库</button>
                </div>
              )}
            </div>
          </div>

          {!coachCollapsed && (
            <aside className="pw-coach">
              <div className="pw-coach-head">
                <span className="pw-tool-title">AI 教练</span>
                <div className="pw-coach-actions">
                  <button type="button" onClick={resetCoach} title="重置 AI 教练">↻</button>
                  <button type="button" onClick={() => setCoachCollapsed(true)} title="收起 AI 教练">×</button>
                </div>
              </div>
              <div className="pw-coach-body">
                <h2>你好！我是你的 AI 助手</h2>
                <p>我可以结合当前练习、代码和运行结果帮助你分析问题。</p>
                {exercise && (
                  <div className="pw-coach-context" aria-label="当前题目上下文">
                    <strong>当前题目</strong>
                    <b>{getExerciseTitle(exercise)}</b>
                    <span>{exercise.language} · {editableFiles.length} 个可编辑文件</span>
                    <span>当前文件：{activeFile?.relative_path || "未打开"}</span>
                    <span>最近结果：{exerciseResult?.summary || (sampleResult ? (sampleResult.passed ? "单样例通过" : "单样例未通过") : "暂无")}</span>
                  </div>
                )}
                <strong className="pw-coach-section-title">学习工具</strong>
                <div className="pw-coach-action-grid">
                  {[
                    ["题目分析", "分析当前题目的目标、解题思路和边界条件"],
                    ["代码诊断", "诊断当前文件和当前题目的全部可编辑文件"],
                    ["失败分析", "结合最近一次测试或提交结果定位失败原因"],
                    ["一级提示", "只给思路提示，不直接给出完整答案"],
                    ["复杂度分析", "分析时间复杂度、空间复杂度和改进点"],
                  ].map(([label, question]) => (
                    <button key={label} type="button" onClick={() => analyzeProject(question)} disabled={busy === "coach"}>
                      <span>{label}</span><small>{question}</small>
                    </button>
                  ))}
                </div>
                <div className="pw-coach-recommendations">
                  <strong>相关练习</strong>
                  <span>当前练习推荐数据暂未提供</span>
                </div>
                {coachSuggestionsVisible && (
                  <>
                    <strong className="pw-coach-section-title">建议操作</strong>
                    <div className="pw-quick-list">
                      {["解释这段代码的作用", "分析代码的时间复杂度", "优化这段代码", "生成单元测试", "查找潜在问题"].map((item) => (
                        <button key={item} type="button" onClick={() => analyzeProject(item)}>
                          <span>{item}</span><b>›</b>
                        </button>
                      ))}
                    </div>
                  </>
                )}
                <div className="pw-chat-log">
                  {messages.slice(-6).map((message, index) => (
                    <div key={message.role + "-" + index} className={"pw-chat-msg pw-chat-msg--" + message.role}>
                      {message.content}
                    </div>
                  ))}
                </div>
              </div>
              <form className="pw-chat-input" onSubmit={(event) => { event.preventDefault(); analyzeProject(coachQuestion.trim()); }}>
                <input value={coachQuestion} onChange={(event) => setCoachQuestion(event.target.value)} placeholder="向 AI 提问..." />
                <button type="submit" disabled={busy === "coach"}>▷</button>
              </form>
              <small>AI 生成的内容仅供参考，请结合自身思考。</small>
            </aside>
          )}
        </div>

        <div className="pw-bottom-toolwindow" style={{ height: outputCollapsed ? 32 : bottomHeight }}>
          {!outputCollapsed && <div className="pw-bottom-resizer" onMouseDown={startBottomResize} />}
          <div className="pw-result-tabs">
            <button type="button" className={activeResultTab === "run" && !outputCollapsed ? "is-active" : ""} onClick={() => selectResultTab("run")}>
              <span>▷</span> 运行结果
            </button>
            <button type="button" className={activeResultTab === "tests" && !outputCollapsed ? "is-active" : ""} onClick={() => selectResultTab("tests")}>
              <span>✓</span> 测试结果
            </button>
            <div className="pw-bottom-tools">
              <button type="button" data-action="toggle-output" onClick={() => setOutputCollapsed(!outputCollapsed)} title={outputCollapsed ? "展开" : "收起"}>{outputCollapsed ? "^" : "×"}</button>
            </div>
          </div>
          {!outputCollapsed && (
            <div className="pw-results">
              {activeResultTab === "tests" ? (
                <div className="pw-test-result-summary">
                  {exerciseResult ? (
                    (() => {
                      const cases = (exerciseResult.cases || []).map(normalizeResultCase);
                      const failedCases = cases.filter((item) => !["passed", "skipped"].includes(item.status));
                      const passedCases = cases.filter((item) => ["passed", "skipped"].includes(item.status));
                      return (
                        <>
                          <div className="pw-test-summary-head">
                            <strong>{exerciseResult.summary || `通过 ${exerciseResult.passed_count}/${exerciseResult.total_count}`}</strong>
                            <span>{exerciseResult.failed_categories?.length ? `失败类别：${exerciseResult.failed_categories.join("、")}` : "全部测试通过"}</span>
                            <span>执行时间：{exerciseResult.duration_ms ?? 0}ms</span>
                          </div>
                          {failedCases.length > 0 && (
                            <div className="pw-test-case-list">
                              {failedCases.map((item) => (
                                <article className={`pw-test-case-card pw-test-case-card--${item.status}`} key={item.id}>
                                  <strong>测试样例：{item.name}</strong>
                                  <span>结果：{caseStatusLabel(item.status)}</span>
                                  <span>原因：{item.reason}</span>
                                  {item.expected !== undefined && <span>期望：{String(item.expected)}</span>}
                                  {item.actual !== undefined && <span>实际：{String(item.actual)}</span>}
                                  {item.location && <span>位置：{item.location}</span>}
                                  <span>执行时间：{item.duration_ms}ms</span>
                                </article>
                              ))}
                            </div>
                          )}
                          {passedCases.length > 0 && (
                            <details className="pw-passed-cases">
                              <summary>查看已通过的 {passedCases.length} 个样例</summary>
                              <div className="pw-test-case-list">
                                {passedCases.map((item) => (
                                  <article className="pw-test-case-card pw-test-case-card--passed" key={item.id}>
                                    <strong>测试样例：{item.name}</strong>
                                    <span>结果：通过</span>
                                    {item.expected !== undefined && <span>期望：{String(item.expected)}</span>}
                                    {item.actual !== "未返回结果" && <span>实际：{String(item.actual)}</span>}
                                    <span>执行时间：{item.duration_ms}ms</span>
                                  </article>
                                ))}
                              </div>
                            </details>
                          )}
                          {exerciseResult.ai_explanation && <p>{exerciseResult.ai_explanation}</p>}
                          {exerciseResult.technical_details && (
                            <details className="pw-technical-details">
                              <summary>技术详情</summary>
                              <pre>{exerciseResult.technical_details}</pre>
                            </details>
                          )}
                        </>
                      );
                    })()
                  ) : <span>点击顶部“运行全部测试”或“提交”查看真实测试结果。</span>}
                </div>
              ) : activeResultTab === "problems" ? (
                <div className="pw-problems-list">
                  <div className="pw-problems-summary">
                    <span className="pw-problems-error">{diagnosticSummary.errors} 个错误</span>
                    <span className="pw-problems-warning">{diagnosticSummary.warnings} 个警告</span>
                  </div>
                  {activeDiagnostics.length ? activeDiagnostics.map((item, index) => (
                    <button
                      key={`${item.source}-${item.file}-${item.line}-${index}`}
                      type="button"
                      className={`pw-problem-row pw-problem-row--${item.severity}`}
                      onClick={() => openProblem(item)}
                    >
                      <span>{item.severity}</span>
                      <strong>{item.file || "当前练习"}</strong>
                      <em>{item.line ? `${item.line}${item.column ? `:${item.column}` : ""}` : "-"}</em>
                      <b>{item.message}</b>
                    </button>
                  )) : (
                    <div className="pw-problems-empty">当前练习没有真实诊断问题。</div>
                  )}
                </div>
              ) : activeResultTab === "run" ? (
                <div className="pw-run-result">
                  {sampleResult && (
                    (() => {
                      const item = normalizeResultCase(sampleResult.cases?.[0] || {
                        id: sampleResult.sample?.id,
                        name: sampleResult.test_name || sampleResult.sample?.name,
                        status: sampleResult.status || (sampleResult.passed ? "passed" : "failed"),
                        reason: sampleResult.status === "compile_failed" ? "代码编译失败" : sampleResult.status === "timeout" ? "程序运行超过 5 秒，可能存在死循环" : undefined,
                        expected: sampleResult.expected_output ?? sampleResult.sample?.expected,
                        actual: sampleResult.actual_output,
                        duration_ms: sampleResult.duration_ms ?? sampleResult.result?.duration_ms,
                      });
                      return (
                        <div className={`pw-sample-result pw-sample-result--${item.status}`}>
                          <strong>测试样例：{item.name}</strong>
                          <span>结果：{caseStatusLabel(item.status)}</span>
                          {item.status !== "passed" && <span>原因：{item.reason}</span>}
                          {item.expected !== undefined && <span>期望：{String(item.expected)}</span>}
                          {item.actual !== undefined && <span>实际：{String(item.actual)}</span>}
                          {item.location && <span>位置：{item.location}</span>}
                          <span>执行时间：{item.duration_ms}ms</span>
                          {(sampleResult.technical_details || sampleResult.result?.technical_details) && (
                            <details className="pw-technical-details">
                              <summary>技术详情</summary>
                              <pre>{sampleResult.technical_details || sampleResult.result?.technical_details}</pre>
                            </details>
                          )}
                        </div>
                      );
                    })()
                  )}
                  {!sampleResult && <pre>{resultText}</pre>}
                  {runResult && (
                    <>
                      <button type="button" className="pw-run-details-toggle" onClick={() => setRunDetailsOpen((open) => !open)} aria-expanded={runDetailsOpen}>
                        [{runDetailsOpen ? "收起" : "展开"}运行详情]
                      </button>
                      {runDetailsOpen && <pre className="pw-run-details">{formatRunDetails(runResult)}</pre>}
                    </>
                  )}
                </div>
              ) : (
                <pre>{resultText}</pre>
              )}
            </div>
          )}
        </div>

        <div className="pw-statusbar">
          <div>
            <span>{getRuntimeLabel(language)}</span>
            <span className={runResult?.exit_code === 0 ? "is-ok" : runResult ? "is-error" : ""}>{runResult?.exit_code === 0 ? "✓ 运行成功" : runResult ? "运行失败" : status || saveState}</span>
          </div>
          <div>
            <span>Ln {cursorPosition.lineNumber || 1}, Col {cursorPosition.column || 1}</span>
            <span>UTF-8</span>
            <span>LF</span>
            <span>{activeResource ? getResourceKind(activeResource) : getMonacoLanguage(activeFile) || language}</span>
          </div>
        </div>
      </div>

      {testModal && exerciseResult && (
        <ExerciseResultModal
          result={exerciseResult}
          mode={testModal.mode}
          filter={testModalFilter}
          onFilterChange={setTestModalFilter}
          onClose={() => setTestModal(null)}
          onRerun={() => runExerciseCheck(testModal.mode === "submit")}
          busy={busy === "test" || busy === "submit"}
        />
      )}

      {contextMenu && (
        <div
          className="pw-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
        >
          {contextMenu.type === "top" && (
            <>
              <button type="button" onClick={refreshWorkspace}>刷新练习</button>
              <button type="button" onClick={() => adjustFontSize(-1)}>缩小字体</button>
              <button type="button" onClick={() => adjustFontSize(1)}>放大字体</button>
              <button type="button" onClick={() => switchTheme("light")}>浅色模式</button>
              <button type="button" onClick={() => switchTheme("dark")}>深色模式</button>
              <button type="button" onClick={toggleFocusMode}>{focusMode ? "退出专注编辑" : "专注编辑"}</button>
              <button type="button" onClick={openCoach}>打开 AI 教练</button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
