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

function TreeNode({ node, activeFileId, collapsedFolders, onToggleFolder, onOpenFile, onRenameFile, onDeleteFile, depth = 0 }) {
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
  const [runResult, setRunResult] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [messages, setMessages] = useState([]);
  const [coachQuestion, setCoachQuestion] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [saveState, setSaveState] = useState("已保存");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);
  const saveTimerRef = useRef(null);
  const shellRef = useRef(null);
  const editorRef = useRef(null);
  const activeFile = files.find((file) => file.id === activeFileId) || files[0] || null;
  const language = selectedLanguage || project?.language || onboardingLanguage || "Python";

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

  const editEntryFile = async () => {
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

  const runProject = async () => {
    if (!project?.id) return;
    await manualSave();
    setBusy("run");
    setOutputCollapsed(false);
    setActiveResultTab("run");
    setRunResult(null);
    try {
      const res = await fetch(`${apiBase}/code/projects/${project.id}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, stdin: "" }),
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
          <button type="button" className="pw-back-btn" onClick={onGoHome}>返回首页</button>
          <div className="pw-title-block">
            <span>{language} 工作区</span>
            <strong>{project?.name || `还没有 ${language} 项目`}</strong>
            <small>{project ? `入口：${project.entry_file}` : "选择或新建项目后开始编码"}</small>
          </div>
          <div className="pw-top-actions">
            <button type="button" onClick={() => createProject(language, true)}>新建项目</button>
            <button type="button" onClick={renameProject} disabled={!project}>重命名</button>
            <button type="button" onClick={editEntryFile} disabled={!project}>入口文件</button>
            <button type="button" onClick={manualSave} disabled={!activeFile}>{saveState || "保存"}</button>
            <button type="button" data-action="switch-language" onClick={switchLanguage}>切换语言</button>
            <button type="button" data-action="fullscreen" onClick={toggleFullscreen}>{isFullscreen || fullscreenFallback ? "退出全屏" : "全屏"}</button>
          </div>
        </div>

        <div className="pw-workbench-body">
          {!explorerCollapsed && (
            <aside className="pw-explorer">
              <div className="pw-explorer-head">
                <button type="button" onClick={() => setExplorerCollapsed(true)} title="折叠项目树">‹</button>
                <strong>项目文件</strong>
              </div>
              <div className="pw-project-switcher">
                <span>{language} 项目</span>
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
                <>
                  <div className="pw-explorer-project">
                    <strong title={project.name}>{project.name}</strong>
                    <span>{language} · {files.length} 文件</span>
                  </div>
                  <div className="pw-explorer-actions">
                    <button type="button" onClick={createFile}>新建文件</button>
                    <button type="button" onClick={createFolder}>新建文件夹</button>
                  </div>
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
                    />
                  </div>
                </>
              ) : (
                <div className="pw-empty-project">
                  <strong>还没有 {language} 项目</strong>
                  <p>新建项目后会自动生成 {DEFAULT_FILE[language]}。</p>
                  <button type="button" onClick={() => createProject(language, true)}>新建 {language} 项目</button>
                </div>
              )}
            </aside>
          )}

          {explorerCollapsed && (
            <button type="button" className="pw-rail pw-rail--left" onClick={() => setExplorerCollapsed(false)} title="展开项目树">›</button>
          )}

          <div className="pw-editor-area">
            <div className="pw-file-tabs">
              {tabFiles.map((file) => (
                <button key={file.id} type="button" className={file.id === activeFileId ? "is-active" : ""} onClick={() => setActiveFileId(file.id)} title={file.relative_path}>
                  <span>{dirtyFiles.has(file.id) ? "●" : ""}</span>
                  {file.filename}
                  <b onClick={(event) => { event.stopPropagation(); closeTab(file.id); }}>×</b>
                </button>
              ))}
            </div>
            <div className="pw-editor-card">
              {activeFile ? (
                <Editor
                  height="100%"
                  path={`project://${project?.id}/${activeFile.relative_path}`}
                  language={getMonacoLanguage(activeFile)}
                  value={activeFile.content || ""}
                  theme={theme === "dark" ? "vs-dark" : "light"}
                  onMount={(editor) => { editorRef.current = editor; relayoutEditor(); }}
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
                  <strong>{language} 工作区</strong>
                  <p>从左侧打开项目，或新建一个 {language} 项目。</p>
                </div>
              )}
              <div className="pw-editor-controls">
                <span>字体</span>
                <button type="button" onClick={() => setFontSize((size) => Math.max(12, size - 1))}>−</button>
                <strong>{fontSize}px</strong>
                <button type="button" onClick={() => setFontSize((size) => Math.min(24, size + 1))}>＋</button>
                <button type="button" className={theme === "light" ? "is-active" : ""} onClick={() => setTheme("light")}>浅色</button>
                <button type="button" className={theme === "dark" ? "is-active" : ""} onClick={() => setTheme("dark")}>深色</button>
              </div>
            </div>
          </div>

          {!coachCollapsed && (
            <aside className="pw-coach">
              <div className="pw-coach-head">
                <strong>AI 教练</strong>
                <button type="button" aria-label="收起 AI 教练" onClick={() => setCoachCollapsed(true)}>›</button>
              </div>
              <div className="pw-coach-body">
                <div className="pw-bot" aria-hidden="true"><span /><span /></div>
                <h2>你好，我是你的 AI 教练</h2>
                <p>我会结合项目语言、入口文件、当前文件、文件树、运行输出和相关文件内容给出建议。</p>
                <div className="pw-quick-list">
                  {["帮我理解这个项目结构", "帮我分析当前代码", "解释这次运行错误", "帮我检查跨文件引用"].map((item) => (
                    <button key={item} type="button" onClick={() => analyzeProject(item)}>
                      <span>{item}</span><b>→</b>
                    </button>
                  ))}
                </div>
                <div className="pw-chat-log">
                  {messages.slice(-6).map((message, index) => (
                    <div key={`${message.role}-${index}`} className={`pw-chat-msg pw-chat-msg--${message.role}`}>
                      {message.content}
                    </div>
                  ))}
                </div>
              </div>
              <form className="pw-chat-input" onSubmit={(event) => { event.preventDefault(); analyzeProject(coachQuestion.trim()); }}>
                <input value={coachQuestion} onChange={(event) => setCoachQuestion(event.target.value)} placeholder="向 AI 教练提问..." />
                <button type="submit" disabled={busy === "coach"}>→</button>
              </form>
              <small>AI 生成内容仅供参考，请结合自身思考。</small>
            </aside>
          )}

          {coachCollapsed && (
            <button type="button" className="pw-rail pw-rail--right" onClick={() => setCoachCollapsed(false)} title="展开 AI 教练">‹</button>
          )}
        </div>

        <div className="pw-actions">
          <button type="button" data-action="run-project" onClick={runProject} disabled={!project || busy === "run"}>{busy === "run" ? "运行中" : "运行"}</button>
          <button type="button" onClick={() => { setOutputCollapsed(false); setActiveResultTab("problems"); }}>测试</button>
          <button type="button" onClick={() => analyzeProject()} disabled={!activeFile || busy === "feedback"}>{busy === "feedback" ? "分析中" : "AI 判题"}</button>
          <button type="button" className="pw-output-toggle" data-action="toggle-output" onClick={() => setOutputCollapsed(!outputCollapsed)}>
            {outputCollapsed ? "展开输出" : "收起输出"}
          </button>
          <span>{status}</span>
          <em>{activeFile?.relative_path || "未选择文件"}</em>
        </div>

        {!outputCollapsed && (
          <div className="pw-results">
            <div className="pw-result-tabs">
              <button type="button" className={activeResultTab === "run" ? "is-active" : ""} onClick={() => setActiveResultTab("run")}>运行输出</button>
              <button type="button" className={activeResultTab === "problems" ? "is-active" : ""} onClick={() => setActiveResultTab("problems")}>问题</button>
              <button type="button" className={activeResultTab === "feedback" ? "is-active" : ""} onClick={() => setActiveResultTab("feedback")}>AI 判定反馈</button>
            </div>
            <pre>{resultText}</pre>
          </div>
        )}
      </div>
    </section>
  );
}
