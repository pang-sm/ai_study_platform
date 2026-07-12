import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import "./ProgrammingWorkbench.css";

const LANGUAGE_TABS = ["C", "C++", "Python", "Java"];
const DEFAULT_FILE = { C: "main.c", "C++": "main.cpp", Python: "main.py", Java: "Main.java" };
const PROJECT_COURSE_ID = "programming";
const UI_STORAGE_KEY = "ai_study_programming_workbench_ui";

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
  ".md": "markdown",
  ".txt": "plaintext",
};

const SOURCE_EXTENSIONS = {
  C: [".c"],
  "C++": [".cpp", ".cc", ".cxx"],
  Python: [".py"],
  Java: [".java"],
};

const HEADER_EXTENSIONS = new Set([".h", ".hpp"]);

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
  if (!result) return "点击运行后，当前项目入口文件的真实输出会显示在这里。";
  const lines = [];
  if (result.stdout) lines.push(result.stdout.trimEnd());
  if (result.stderr) lines.push(result.stderr.trimEnd());
  if (result.compile_error) lines.push(result.compile_error.trimEnd());
  if (result.error_message) lines.push(result.error_message);
  lines.push(`exit_code: ${result.exit_code ?? "-"}`);
  if (result.duration_ms != null) lines.push(`duration: ${result.duration_ms}ms`);
  return lines.filter(Boolean).join("\n") || "程序已运行完成，无输出。";
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

export default function ProgrammingWorkbench({
  user,
  apiBase = "/api",
  homeData,
  initialProjectId = null,
  initialLanguageSelection = "",
  onProjectChanged,
  onGoHome,
}) {
  const onboardingLanguage = normalizeLanguage(homeData?.onboarding?.main_language || user?.default_course_id || "");
  const [projects, setProjects] = useState([]);
  const [selectedLanguage, setSelectedLanguage] = useState(() => normalizeLanguage(initialLanguageSelection));
  const [project, setProject] = useState(null);
  const [files, setFiles] = useState([]);
  const [activeFileId, setActiveFileId] = useState(null);
  const [openTabs, setOpenTabs] = useState([]);
  const [dirtyFiles, setDirtyFiles] = useState(() => new Set());
  const [collapsedFolders, setCollapsedFolders] = useState(() => new Set());
  const [explorerCollapsed, setExplorerCollapsedState] = useState(() => readUiPreference("explorerCollapsed", false));
  const [coachCollapsed, setCoachCollapsedState] = useState(() => readUiPreference("coachCollapsed", false));
  const [outputCollapsed, setOutputCollapsedState] = useState(() => readUiPreference("outputCollapsed", false));
  const [fontSize, setFontSize] = useState(16);
  const [theme, setTheme] = useState("light");
  const [activeResultTab, setActiveResultTab] = useState("run");
  const [bottomHeight, setBottomHeight] = useState(210);
  const [cursorPosition, setCursorPosition] = useState({ lineNumber: 1, column: 1 });
  const [focusMode, setFocusMode] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [messages, setMessages] = useState([]);
  const [coachQuestion, setCoachQuestion] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [saveState, setSaveState] = useState("已保存");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);
  const [runConfigOpen, setRunConfigOpen] = useState(false);
  const [runMode, setRunMode] = useState("project");
  const [draftEntryFile, setDraftEntryFile] = useState("");
  const [draftMainClass, setDraftMainClass] = useState("");
  const [contextMenu, setContextMenu] = useState(null);
  const saveTimerRef = useRef(null);
  const shellRef = useRef(null);
  const editorRef = useRef(null);
  const activeFile = files.find((file) => file.id === activeFileId) || files[0] || null;
  const language = selectedLanguage || project?.language || onboardingLanguage || "Python";
  const sourceFiles = useMemo(
    () => files.filter((file) => isSourceFileForLanguage(file.relative_path, language)),
    [files, language],
  );
  const javaMainClasses = useMemo(
    () => files.map(detectJavaMainClass).filter(Boolean),
    [files],
  );
  const uniqueJavaMainClasses = useMemo(() => [...new Set(javaMainClasses)], [javaMainClasses]);
  const activeJavaMainClass = useMemo(() => detectJavaMainClass(activeFile), [activeFile]);
  const runTargetLabel = useMemo(() => {
    if (!project) return "运行：未选择项目";
    if (language === "Java") return `运行：${project.main_class || uniqueJavaMainClasses[0] || "请选择主类"}`;
    return `运行：${project.entry_file || activeFile?.relative_path || DEFAULT_FILE[language]}`;
  }, [activeFile?.relative_path, language, project, uniqueJavaMainClasses]);
  const runScopeLabel = useMemo(() => {
    if (!project) return "";
    if (language === "C") return `范围：项目内 ${sourceFiles.length} 个 .c 源文件`;
    if (language === "C++") return `范围：项目内 ${sourceFiles.length} 个 C++ 源文件`;
    if (language === "Java") return `范围：全部 ${sourceFiles.length} 个 Java 源文件`;
    return runMode === "current-file" ? "范围：当前文件" : "范围：项目根目录";
  }, [language, project, runMode, sourceFiles.length]);

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

  const languageCounts = useMemo(() => {
    const counts = Object.fromEntries(LANGUAGE_TABS.map((item) => [item, 0]));
    projects.forEach((item) => {
      const key = normalizeLanguage(item.language);
      if (key) counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }, [projects]);

  const loadProject = useCallback(async (projectId) => {
    if (!user?.username || !projectId) return null;
    const res = await fetch(`${apiBase}/code/projects/${projectId}?username=${encodeURIComponent(user.username)}`);
    const data = await safeJson(res);
    if (!res.ok || !data.project) {
      setStatus(data.detail || "项目读取失败");
      return null;
    }
    const nextProject = data.project;
    setSelectedLanguage(normalizeLanguage(nextProject.language));
    setProject(nextProject);
    setFiles(nextProject.files || []);
    const firstFile = nextProject.files?.find((file) => file.relative_path === nextProject.entry_file) || nextProject.files?.[0];
    setActiveFileId(firstFile?.id || null);
    setOpenTabs(firstFile ? [firstFile.id] : []);
    setDirtyFiles(new Set());
    setSaveState("已保存");
    relayoutEditor();
    return nextProject;
  }, [apiBase, relayoutEditor, user?.username]);

  const loadProjects = useCallback(async () => {
    if (!user?.username) return;
    const query = new URLSearchParams({ username: user.username, course_id: PROJECT_COURSE_ID });
    const res = await fetch(`${apiBase}/code/projects?${query.toString()}`);
    const data = await safeJson(res);
    if (!res.ok) {
      setStatus(data.detail || "项目列表读取失败");
      return;
    }
    const items = data.projects || [];
    setProjects(items);
    if (initialProjectId) {
      const matched = items.find((item) => item.id === Number(initialProjectId));
      if (matched) {
        setSelectedLanguage(normalizeLanguage(matched.language));
        await loadProject(matched.id);
      }
      return;
    }
    const nextLanguage = normalizeLanguage(initialLanguageSelection);
    if (nextLanguage) setSelectedLanguage(nextLanguage);
  }, [apiBase, initialLanguageSelection, initialProjectId, loadProject, user?.username]);

  useEffect(() => { loadProjects(); }, [loadProjects]);

  useEffect(() => {
    if (!selectedLanguage || initialProjectId) return;
    const sameLanguageProjects = projects.filter((item) => normalizeLanguage(item.language) === selectedLanguage);
    if (sameLanguageProjects.length === 0) {
      setProject(null);
      setFiles([]);
      setOpenTabs([]);
      setActiveFileId(null);
      return;
    }
    if (!project || normalizeLanguage(project.language) !== selectedLanguage) {
      loadProject(sameLanguageProjects[0].id);
    }
  }, [initialProjectId, loadProject, project, projects, selectedLanguage]);

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
    const closeMenu = () => setContextMenu(null);
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
    const name = askName ? window.prompt("项目名称", `${lockedLanguage} 项目`) : `${lockedLanguage} 项目`;
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
      setExplorerCollapsed(true);
      setCoachCollapsed(true);
      setOutputCollapsed(true);
    } else {
      setExplorerCollapsed(false);
      setCoachCollapsed(false);
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

  const runProject = async (override = {}) => {
    if (!project?.id) return;
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
    try {
      const res = await fetch(`${apiBase}/code/projects/${project.id}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          stdin: "",
          run_mode: runMode,
          entry_file: override.entryFile || (runMode === "current-file" ? activeFile?.relative_path : project.entry_file),
          main_class: override.mainClass || project.main_class || uniqueJavaMainClasses[0] || "",
          source_files: sourceFiles.map((file) => file.relative_path),
        }),
      });
      const data = await safeJson(res);
      setRunResult(res.ok ? data : { exit_code: -1, error_message: data.detail || "运行失败" });
    } catch {
      setRunResult({ exit_code: -1, error_message: "无法连接后端服务。" });
    } finally {
      setBusy("");
    }
  };

  const analyzeProject = async (question) => {
    const text = question || "请基于当前项目上下文进行判题式分析，指出错误、可改进点和下一步建议。";
    if (!activeFile) return;
    setBusy(question ? "coach" : "feedback");
    setOutputCollapsed(false);
    setActiveResultTab(question ? activeResultTab : "feedback");
    if (question) setMessages((prev) => [...prev, { role: "user", content: question }]);
    try {
      await manualSave();
      const treeText = files.map((file) => `- ${file.relative_path}${file.relative_path === project.entry_file ? " (entry)" : ""}`).join("\n");
      const related = files
        .filter((file) => file.id !== activeFile.id)
        .slice(0, 5)
        .map((file) => `\n\n--- ${file.relative_path} ---\n${String(file.content || "").slice(0, 1800)}`)
        .join("");
      const codeContext = `项目：${project.name}\n语言：${project.language}\n入口文件：${project.entry_file}\n当前文件：${activeFile.relative_path}\n文件树：\n${treeText}\n\n--- 当前文件内容 ---\n${activeFile.content || ""}${related}`;
      const res = await fetch(`${apiBase}/code/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: PROJECT_COURSE_ID,
          session_id: null,
          challenge_id: null,
          language: project.language,
          code: codeContext,
          question: text,
          last_run_result: runResult,
          last_test_results: null,
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

  const switchLanguage = () => {
    setSelectedLanguage("");
    setProject(null);
    setFiles([]);
    setOpenTabs([]);
    setActiveFileId(null);
    setStatus("");
  };

  const resultText = activeResultTab === "run"
    ? formatRunResult(runResult)
    : activeResultTab === "problems"
      ? "当前普通项目暂无测试配置。关联 AI 编程题后可运行 challenge tests。"
      : feedback || "点击 AI 判题后，项目上下文反馈会显示在这里。";

  const tree = useMemo(() => buildTree(files), [files]);
  const tabFiles = openTabs.map((id) => files.find((file) => file.id === id)).filter(Boolean);
  const shellClassName = [
    "pw-shell",
    selectedLanguage ? "pw-shell--workspace" : "pw-shell--chooser",
    explorerCollapsed ? "pw-shell--explorer-collapsed" : "",
    coachCollapsed ? "pw-shell--coach-collapsed" : "",
    outputCollapsed ? "pw-shell--output-collapsed" : "",
    focusMode ? "pw-shell--focus-mode" : "",
    isFullscreen || fullscreenFallback ? "pw-shell--fullscreen" : "",
    fullscreenFallback ? "pw-shell--fullscreen-fallback" : "",
  ].filter(Boolean).join(" ");

  if (!selectedLanguage) {
    return (
      <section className={shellClassName} ref={shellRef}>
        <div className="pw-language-picker">
          <div className="pw-language-picker-head">
            <button type="button" onClick={onGoHome}>返回首页</button>
            <div>
              <h2>选择编程语言工作区</h2>
              <p>先选择 C / C++ / Python / Java，再进入对应 IDE 工作区管理项目。</p>
            </div>
          </div>
          <div className="pw-language-grid">
            {LANGUAGE_TABS.map((item) => (
              <button key={item} type="button" className="pw-language-card" data-language={item} onClick={() => setSelectedLanguage(item)}>
                <span>{LANGUAGE_META[item].mark}</span>
                <strong>{item}</strong>
                <small>{LANGUAGE_META[item].description}</small>
                <b>{languageCounts[item] || 0} 个项目</b>
              </button>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className={shellClassName} ref={shellRef} data-workspace-language={selectedLanguage || ""}>
      <div className="pw-center">
        <div className="pw-topbar">
          <div className="pw-brand-mark" aria-hidden="true">◇</div>
          <div className="pw-title-block">
            <strong title={project?.name || ""}>{project?.name || ("No " + language + " Project")}</strong>
          </div>
          <div className="pw-run-cluster">
            <label className="pw-run-combo" title="Run Configuration">
              <span className={"pw-lang-badge pw-lang-badge--" + language.toLowerCase().replace(/[^a-z0-9]+/g, "-")}>{LANGUAGE_META[language]?.mark || language}</span>
              <select
                className="pw-run-select"
                value={language === "Java" ? (project?.main_class || uniqueJavaMainClasses[0] || "") : (project?.entry_file || draftEntryFile || "")}
                onChange={(event) => changeRunTarget(event.target.value)}
                disabled={!project}
                title="Run Configuration"
              >
                {language === "Java" ? (
                  <>
                    <option value="">Select main class</option>
                    {project?.main_class && !uniqueJavaMainClasses.includes(project.main_class) && (
                      <option value={project.main_class}>{project.main_class}</option>
                    )}
                    {uniqueJavaMainClasses.map((mainClass) => (
                      <option key={mainClass} value={mainClass}>{mainClass}</option>
                    ))}
                  </>
                ) : (
                  sourceFiles.map((file) => (
                    <option key={file.id} value={file.relative_path}>{file.relative_path}</option>
                  ))
                )}
              </select>
            </label>
            <button type="button" className="pw-icon-button pw-run-button" data-action="top-run" onClick={runProject} disabled={!project || busy === "run"} title="Run">
              {busy === "run" ? "..." : "▷"}
            </button>
            <button type="button" className="pw-icon-button" data-action="top-more" onClick={openTopMenu} title="More">...</button>
          </div>
          <div className="pw-top-actions">
            <span className="pw-save-chip">{saveState}</span>
            <button type="button" data-action="switch-language" onClick={switchLanguage}>切换语言</button>
            <button type="button" data-action="fullscreen" onClick={toggleFullscreen}>{isFullscreen || fullscreenFallback ? "退出全屏" : "全屏"}</button>
          </div>
        </div>

        <div className="pw-workbench-body">
          <nav className="pw-tool-rail pw-tool-rail--left" aria-label="Tool windows">
            <button type="button" className={explorerCollapsed ? "" : "is-active"} onClick={() => setExplorerCollapsed(!explorerCollapsed)} title="Project">
              <span className="pw-rail-icon">□</span>
              <span>Project</span>
            </button>
            <button type="button" onClick={() => selectResultTab("run")} title="Run">
              <span className="pw-rail-icon">▷</span>
            </button>
            <button type="button" onClick={() => selectResultTab("feedback")} title="AI Feedback">
              <span className="pw-rail-icon">AI</span>
            </button>
          </nav>

          {!explorerCollapsed && (
            <aside className="pw-explorer">
              <div className="pw-explorer-head">
                <span className="pw-tool-title">Project</span>
                <div className="pw-project-tools">
                  <button type="button" onClick={(event) => openContextMenu(event, { type: "project-new", path: "" })} title="New">+</button>
                  <button type="button" onClick={(event) => openContextMenu(event, { type: "project-actions", path: "" })} disabled={!project} title="Project actions">...</button>
                </div>
              </div>
              <div className="pw-project-switcher">
                {filteredProjects.length === 0 ? (
                  <em>暂无项目</em>
                ) : (
                  filteredProjects.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={project?.id === item.id ? "is-active" : ""}
                      onClick={() => loadProject(item.id)}
                    >
                      {item.name}
                    </button>
                  ))
                )}
              </div>
              {project ? (
                <div className="pw-tree-shell">
                  <button className="pw-tree-root" type="button" onContextMenu={(event) => openContextMenu(event, { type: "root", path: "" })}>
                    <span>v</span>
                    <i aria-hidden="true" />
                    <strong title={project.name}>{project.name}</strong>
                  </button>
                  <div className="pw-tree">
                    <TreeNode
                      node={tree}
                      activeFileId={activeFileId}
                      collapsedFolders={collapsedFolders}
                      onToggleFolder={(path) => setCollapsedFolders((prev) => {
                        const next = new Set(prev);
                        if (next.has(path)) next.delete(path);
                        else next.add(path);
                        return next;
                      })}
                      onOpenFile={openFile}
                      onRenameFile={renameFile}
                      onDeleteFile={deleteFile}
                      onContextMenu={openContextMenu}
                    />
                  </div>
                </div>
              ) : (
                <div className="pw-project-empty-line">暂无项目</div>
              )}
            </aside>
          )}

          <div className="pw-editor-area">
            <div className="pw-file-tabs">
              {tabFiles.map((file) => (
                <button key={file.id} type="button" className={file.id === activeFileId ? "is-active" : ""} onClick={() => setActiveFileId(file.id)} title={file.relative_path}>
                  <span className={"pw-tab-icon pw-tab-icon--" + (getExt(file.relative_path).replace(".", "") || "txt")}>{getFileIcon(file.relative_path)}</span>
                  <span className={dirtyFiles.has(file.id) ? "pw-dirty-dot is-dirty" : "pw-dirty-dot"} />
                  <strong>{file.filename}</strong>
                  <b onClick={(event) => { event.stopPropagation(); closeTab(file.id); }}>×</b>
                </button>
              ))}
              {project && <button type="button" className="pw-tab-add" onClick={createFile}>+</button>}
            </div>
            <div className="pw-editor-card">
              {activeFile ? (
                <Editor
                  height="100%"
                  path={"project://" + project?.id + "/" + activeFile.relative_path}
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
                    scheduleAutosave(activeFile.id, nextContent);
                  }}
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
                  <strong>还没有 {language} 项目</strong>
                  <button type="button" onClick={() => createProject(language, true)}>新建 {language} 项目</button>
                </div>
              )}
            </div>
          </div>

          {!coachCollapsed && (
            <aside className="pw-coach">
              <div className="pw-coach-head">
                <span className="pw-tool-title">AI Coach</span>
                <div className="pw-project-tools">
                  <button type="button" onClick={() => setCoachCollapsed(true)} title="Collapse AI">×</button>
                </div>
              </div>
              <div className="pw-coach-body">
                <h2>你好！我是你的 AI 助手</h2>
                <p>我可以结合当前项目、当前文件、运行结果和相关文件帮助你分析代码。</p>
                <strong className="pw-coach-section-title">建议操作</strong>
                <div className="pw-quick-list">
                  {["解释这段代码的作用", "分析代码的时间复杂度", "优化这段代码", "生成单元测试", "查找潜在问题"].map((item) => (
                    <button key={item} type="button" onClick={() => analyzeProject(item)}>
                      <span>{item}</span><b>›</b>
                    </button>
                  ))}
                </div>
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

          <nav className="pw-tool-rail pw-tool-rail--right" aria-label="Right tool windows">
            <button type="button" className={coachCollapsed ? "" : "is-active"} onClick={() => setCoachCollapsed(!coachCollapsed)} title="AI Coach">
              <span className="pw-rail-icon">◇</span>
              <span>AI Coach</span>
            </button>
          </nav>
        </div>

        <div className="pw-bottom-toolwindow" style={{ height: outputCollapsed ? 34 : bottomHeight }}>
          {!outputCollapsed && <div className="pw-bottom-resizer" onMouseDown={startBottomResize} />}
          <div className="pw-result-tabs">
            <button type="button" className={activeResultTab === "run" && !outputCollapsed ? "is-active" : ""} onClick={() => selectResultTab("run")}>
              <span>▷</span> Run
            </button>
            <button type="button" className={activeResultTab === "problems" && !outputCollapsed ? "is-active" : ""} onClick={() => selectResultTab("problems")}>
              <span>!</span> Problems
            </button>
            <button type="button" className={activeResultTab === "feedback" && !outputCollapsed ? "is-active" : ""} onClick={() => selectResultTab("feedback")}>
              <span>AI</span> AI Feedback
            </button>
            <div className="pw-bottom-tools">
              <button type="button" onClick={() => setRunConfigOpen(true)} title="Edit run configuration">...</button>
              <button type="button" data-action="toggle-output" onClick={() => setOutputCollapsed(!outputCollapsed)} title={outputCollapsed ? "Expand" : "Collapse"}>{outputCollapsed ? "^" : "×"}</button>
            </div>
          </div>
          {!outputCollapsed && (
            <div className="pw-results">
              <pre>{resultText}</pre>
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
            <span>{getMonacoLanguage(activeFile) || language}</span>
          </div>
        </div>
      </div>

      {runConfigOpen && (
        <div className="pw-run-popover" role="dialog" aria-label="运行配置" onClick={(event) => event.stopPropagation()}>
          <div className="pw-run-popover-head">
            <strong>运行配置</strong>
            <button type="button" onClick={() => setRunConfigOpen(false)}>×</button>
          </div>
          <label>
            <span>运行模式</span>
            <select value={runMode} onChange={(event) => setRunMode(event.target.value)}>
              <option value="project">当前项目</option>
              <option value="current-file">当前文件</option>
              <option value="entry">指定入口</option>
            </select>
          </label>
          {language !== "Java" && (
            <label>
              <span>入口文件</span>
              <select value={draftEntryFile} onChange={(event) => setDraftEntryFile(event.target.value)}>
                {sourceFiles.map((file) => (
                  <option key={file.id} value={file.relative_path}>{file.relative_path}</option>
                ))}
              </select>
            </label>
          )}
          {language === "Java" && (
            <label>
              <span>运行主类</span>
              <select value={draftMainClass} onChange={(event) => setDraftMainClass(event.target.value)}>
                <option value="">请选择 Java main class</option>
                {project?.main_class && !uniqueJavaMainClasses.includes(project.main_class) && (
                  <option value={project.main_class}>{project.main_class}</option>
                )}
                {uniqueJavaMainClasses.map((mainClass) => (
                  <option key={mainClass} value={mainClass}>{mainClass}</option>
                ))}
              </select>
            </label>
          )}
          <p>{runScopeLabel}</p>
          <div className="pw-run-source-list">
            {sourceFiles.map((file) => (
              <span key={file.id}>{file.relative_path}</span>
            ))}
          </div>
          <div className="pw-run-popover-actions">
            <button type="button" onClick={() => setRunConfigOpen(false)}>取消</button>
            <button type="button" onClick={saveRunConfig}>保存配置</button>
          </div>
        </div>
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
              <button type="button" onClick={() => { selectResultTab("problems"); setContextMenu(null); }}>Problems</button>
              <button type="button" onClick={() => { analyzeProject(); setContextMenu(null); }} disabled={!activeFile}>AI Feedback</button>
              <button type="button" onClick={() => { createProject(language, true); setContextMenu(null); }}>New Project</button>
              <button type="button" onClick={() => { setRunConfigOpen(true); setContextMenu(null); }} disabled={!project}>Edit Run Configuration</button>
              <button type="button" onClick={() => setFontSize((size) => Math.max(12, size - 1))}>Font Size -</button>
              <button type="button" onClick={() => setFontSize((size) => Math.min(24, size + 1))}>Font Size +</button>
              <button type="button" onClick={() => { setTheme("light"); setContextMenu(null); }}>Light Mode</button>
              <button type="button" onClick={() => { setTheme("dark"); setContextMenu(null); }}>Dark Mode</button>
              <button type="button" onClick={toggleFocusMode}>{focusMode ? "Exit Focus Editing" : "Focus Editing"}</button>
            </>
          )}
          {contextMenu.type === "project-new" && (
            <>
              <button type="button" onClick={() => createFileInFolder(contextMenu.path)}>新建文件</button>
              <button type="button" onClick={() => createFolderInFolder(contextMenu.path)}>新建文件夹</button>
              <button type="button" onClick={() => { createProject(language, true); setContextMenu(null); }}>新建项目</button>
            </>
          )}
          {contextMenu.type !== "file" && contextMenu.type !== "top" && contextMenu.type !== "project-actions" && contextMenu.type !== "project-new" && (
            <>
              <button type="button" onClick={() => createFileInFolder(contextMenu.path)}>新建文件</button>
              <button type="button" onClick={() => createFolderInFolder(contextMenu.path)}>新建文件夹</button>
            </>
          )}
          {contextMenu.type === "folder" && (
            <>
              <button type="button" onClick={() => renameFolder(contextMenu.path)}>重命名</button>
              <button type="button" onClick={() => deleteFolder(contextMenu.path)}>删除</button>
            </>
          )}
          {contextMenu.type === "root" && (
            <>
              <button type="button" onClick={() => { renameProject(); setContextMenu(null); }} disabled={!project}>Rename Project</button>
              <button type="button" onClick={() => { deleteProject(); setContextMenu(null); }} disabled={!project}>Delete Project</button>
            </>
          )}
          {contextMenu.type === "project-actions" && (
            <>
              <button type="button" onClick={() => { renameProject(); setContextMenu(null); }} disabled={!project}>重命名项目</button>
              <button type="button" onClick={() => { deleteProject(); setContextMenu(null); }} disabled={!project}>删除项目</button>
              <button type="button" onClick={collapseAllFolders}>折叠全部</button>
            </>
          )}
          {contextMenu.type === "file" && (
            <>
              <button type="button" onClick={() => { openFile(contextMenu.file.id); setContextMenu(null); }}>打开</button>
              <button type="button" onClick={() => { renameFile(contextMenu.file); setContextMenu(null); }}>重命名</button>
              <button type="button" onClick={() => { deleteFile(contextMenu.file); setContextMenu(null); }}>删除</button>
              {isSourceFileForLanguage(contextMenu.file.relative_path, language) && (
                <button type="button" onClick={() => setFileAsRunTarget(contextMenu.file)}>
                  {language === "Java" ? "设为运行主类" : "设为入口文件"}
                </button>
              )}
              {isSourceFileForLanguage(contextMenu.file.relative_path, language) && !HEADER_EXTENSIONS.has(getExt(contextMenu.file.relative_path)) && (
                <button type="button" onClick={() => runFile(contextMenu.file)}>运行此文件</button>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
