import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MarkdownMessage from "./MarkdownMessage.jsx";
import MaterialPickerModal from "./MaterialPickerModal.jsx";

const API_BASE = "/api";
const ALLOWED_UPLOAD_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb";

const SUBJECT_LABELS = {
  data_structure: "数据结构",
  computer_organization: "计算机组成原理",
  operating_system: "操作系统",
  computer_network: "计算机网络",
};

const SUBJECT_RECOMMENDATIONS = {
  data_structure: [
    "线性表和链表有什么区别？",
    "栈和队列的典型题型有哪些？",
    "二叉树遍历怎么理解？",
    "图的最短路径怎么做？",
    "如何分析算法的时间复杂度？",
  ],
  computer_organization: [
    "指令周期包括哪些阶段？",
    "Cache 命中率怎么计算？",
    "CPU 和主存如何交换数据？",
    "流水线冲突有哪些类型？",
    "数据表示有哪些常见考点？",
  ],
  operating_system: [
    "进程和线程有什么区别？",
    "死锁产生的条件是什么？",
    "页面置换算法怎么比较？",
    "信号量 PV 操作怎么理解？",
    "文件系统的实现原理是什么？",
  ],
  computer_network: [
    "TCP 和 UDP 有什么区别？",
    "三次握手为什么不是两次？",
    "子网划分怎么计算？",
    "HTTP 和 HTTPS 有什么区别？",
    "网络层和传输层各自负责什么？",
  ],
};

function getSubjectLabel(subjectKey, fallback = "") {
  return SUBJECT_LABELS[subjectKey] || fallback || "11408";
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getFileTypeLabel(type) {
  const normalized = String(type || "").toLowerCase();
  if (!normalized) return "未知";
  if (normalized.includes("pdf")) return "PDF";
  if (normalized.includes("doc")) return "Word";
  if (normalized.includes("ppt")) return "PPT";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(normalized)) return "图片";
  if (["txt", "md", "markdown"].includes(normalized)) return "文本";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash", "html", "css", "json", "xml", "yaml", "yml"].includes(normalized)) return "代码";
  return normalized.toUpperCase();
}

function getParseStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "success") return "已索引";
  if (normalized === "partial") return "部分索引";
  if (normalized === "pending") return "等待解析";
  if (normalized === "parsing") return "解析中";
  if (normalized === "failed") return "解析失败";
  return "未索引";
}

function getRecommendations(subjectKey) {
  return SUBJECT_RECOMMENDATIONS[subjectKey] || SUBJECT_RECOMMENDATIONS.data_structure;
}

function normalizeUploadedMaterial(data, file) {
  const id = data.material_id || data.id;
  if (!id) return null;
  return {
    id,
    material_id: id,
    original_filename: data.filename || data.original_filename || file?.name || "未命名资料",
    file_name: data.filename || data.original_filename || file?.name || "未命名资料",
    file_type: data.file_type || file?.name?.split(".").pop()?.toLowerCase() || "",
    file_size: data.file_size || file?.size || 0,
    parse_status: data.parse_status || "pending",
    parse_progress: data.parse_progress || 0,
    chunk_count: data.chunk_count || 0,
  };
}

function normalizeChatMessage(message, index = 0) {
  const role = message?.role === "user" ? "user" : "assistant";
  return {
    id: message?.id || `history-${role}-${index}`,
    clientId: message?.clientId || `history-${role}-${message?.id || index}`,
    role,
    content: message?.content || "",
    references: Array.isArray(message?.references) ? message.references : [],
    parent_message_id: message?.parent_message_id ?? null,
    root_message_id: message?.root_message_id ?? null,
    branch_id: message?.branch_id || "",
    version_index: Number(message?.version_index || 0),
    versions: Array.isArray(message?.versions) ? message.versions : undefined,
    currentVersionIndex: Number(message?.currentVersionIndex || 0),
    edited: Boolean(message?.edited),
    created_at: message?.created_at || new Date().toISOString(),
  };
}

function getBranchRootId(message) {
  return message?.root_message_id || message?.id || message?.clientId || null;
}

function buildConversationView(rawMessages) {
  const normalized = (Array.isArray(rawMessages) ? rawMessages : []).map(normalizeChatMessage);
  const usersByRoot = new Map();
  const assistantsByParent = new Map();
  const rawIndexById = new Map();

  normalized.forEach((message, index) => {
    rawIndexById.set(String(message.id), index);
    if (message.role === "user") {
      const rootId = getBranchRootId(message);
      if (!rootId) return;
      const key = String(rootId);
      usersByRoot.set(key, [...(usersByRoot.get(key) || []), message]);
    } else if (message.parent_message_id) {
      const key = String(message.parent_message_id);
      assistantsByParent.set(key, [...(assistantsByParent.get(key) || []), message]);
    }
  });

  const branchGroups = new Map();
  usersByRoot.forEach((users, rootKey) => {
    const hasBranch = users.length > 1 || users.some((message) => message.root_message_id || message.version_index > 0);
    if (!hasBranch) return;
    const versions = [...users].sort((a, b) => {
      const versionDiff = Number(a.version_index || 0) - Number(b.version_index || 0);
      if (versionDiff !== 0) return versionDiff;
      return (rawIndexById.get(String(a.id)) || 0) - (rawIndexById.get(String(b.id)) || 0);
    });
    const activeIndex = Math.max(0, versions.length - 1);
    const activeVersion = versions[activeIndex];
    const rootIndex = Math.min(...versions.map((message) => rawIndexById.get(String(message.id)) ?? Number.MAX_SAFE_INTEGER));
    branchGroups.set(rootKey, {
      versions,
      activeIndex,
      activeBranchId: activeVersion?.branch_id || "",
      rootIndex,
      userIds: new Set(versions.map((message) => String(message.id))),
    });
  });

  if (branchGroups.size === 0) return normalized;

  const branchUserIds = new Set();
  branchGroups.forEach((group) => group.userIds.forEach((id) => branchUserIds.add(id)));

  const isAllowedInActivePath = (message, index) => {
    for (const group of branchGroups.values()) {
      if (index <= group.rootIndex) continue;
      const branchId = message.branch_id || "";
      if (branchId && branchId !== group.activeBranchId) return false;
      if (!branchId && group.activeBranchId) return false;
    }
    return true;
  };

  const renderedRoots = new Set();
  const renderedBranchAssistantParents = new Set();
  const result = [];

  normalized.forEach((message, index) => {
    if (message.role === "user") {
      const rootKey = String(getBranchRootId(message));
      const group = branchGroups.get(rootKey);
      if (group) {
        if (renderedRoots.has(rootKey)) return;
        renderedRoots.add(rootKey);
        const activeMessage = group.versions[group.activeIndex];
        const versions = group.versions.map((versionMessage) => {
          const assistants = (assistantsByParent.get(String(versionMessage.id)) || [])
            .map((assistant) => ({ ...assistant, animateTyping: false }));
          renderedBranchAssistantParents.add(String(versionMessage.id));
          return {
            message_id: versionMessage.id,
            clientId: versionMessage.clientId,
            userContent: versionMessage.content || "",
            assistantMessages: assistants,
            branch_id: versionMessage.branch_id || "",
            root_message_id: versionMessage.root_message_id || versionMessage.id,
            parent_message_id: versionMessage.parent_message_id ?? null,
            version_index: Number(versionMessage.version_index || 0),
            createdAt: versionMessage.created_at,
          };
        });
        result.push({
          ...activeMessage,
          versions,
          currentVersionIndex: group.activeIndex,
          edited: versions.length > 1,
        });
        result.push(...(versions[group.activeIndex]?.assistantMessages || []));
        return;
      }
    }

    if (message.role === "assistant" && renderedBranchAssistantParents.has(String(message.parent_message_id))) return;
    if (message.role === "user" && branchUserIds.has(String(message.id))) return;
    if (!isAllowedInActivePath(message, index)) return;
    result.push(message);
  });

  return result;
}

export default function ExamChat({
  user,
  subjectKey,
  subjectTitle,
  courseName,
  mode = "exam_11408",       // "exam_11408" | "course_learning"
  courseId = "",             // used in course_learning mode
  contextDisplay = "",       // custom subtitle, e.g. "课程学习 / 互联网计算"
  knowledgeContext = null,
  initialMaterialToReference = null,
  onInitialMaterialReferenced = null,
  examCramMode = false,
}) {
  const isCourseMode = mode === "course_learning";
  const subjectLabel = isCourseMode
    ? (courseName || subjectTitle || "课程学习")
    : getSubjectLabel(subjectKey, subjectTitle);
  const displayCourseName = isCourseMode ? courseName : (courseName || `11408 ${subjectLabel}`);
  const subtitleText = isCourseMode
    ? (contextDisplay || `课程学习 / ${courseName || "当前课程"}`)
    : (contextDisplay || `当前上下文：${courseName || `11408 ${subjectLabel}`}`);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedMaterials, setSelectedMaterials] = useState([]);
  const [libraryMaterials, setLibraryMaterials] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [librarySearchQuery, setLibrarySearchQuery] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [toolMenuOpen, setToolMenuOpen] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editingText, setEditingText] = useState("");
  const messagesContainerRef = useRef(null);
  const lastUserMessageRef = useRef(null);
  const currentSessionIdRef = useRef(null);
  const currentBranchIdRef = useRef("");
  const uploadInputRef = useRef(null);
  const toolMenuRef = useRef(null);
  const userInteractedRef = useRef(false);
  const shouldScrollToLatestUserRef = useRef(false);

  const recommendations = useMemo(() => {
    if (examCramMode) {
      return ["三次握手速记", "子网划分怎么做", "TCP/UDP 区别", "高频简答题"];
    }
    if (isCourseMode) {
      return [
        `《${courseName}》的核心知识点有哪些？`,
        `如何高效学习${courseName}？`,
        `${courseName}的课程重点是什么？`,
        `请帮我梳理${courseName}的知识体系`,
        `${courseName}常见的习题类型有哪些？`,
      ];
    }
    return getRecommendations(subjectKey).slice(0, 5);
  }, [examCramMode, isCourseMode, courseName, subjectKey]);
  const lastUserMessageId = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "user") return messages[index].id;
    }
    return null;
  }, [messages]);

  const buildScopeParams = useCallback((includeUser = true) => {
    const query = new URLSearchParams();
    if (includeUser && user?.username) query.set("username", user.username);
    if (isCourseMode) {
      // course_learning mode: use courseName as subject/course, no exam_subject
      if (courseName) {
        query.set("subject", courseName);
        query.set("course", courseName);
      }
    } else {
      if (subjectKey) {
        query.set("subject_key", subjectKey);
        query.set("exam_subject", subjectKey);
      }
      if (subjectLabel) query.set("subject", subjectLabel);
      if (courseName) query.set("course", courseName);
    }
    return query;
  }, [isCourseMode, courseName, subjectKey, subjectLabel, user?.username]);

  const buildChatPayload = useCallback((message, extra = {}) => {
    const base = {
      username: user.username,
      message,
      subject: subjectLabel,
      course: displayCourseName,
    };
    if (isCourseMode) {
      // course_learning mode: no exam_subject or subject_key
      Object.assign(base, {
        knowledge_context: knowledgeContext || undefined,
        ...extra,
      });
    } else {
      Object.assign(base, {
        subject_key: subjectKey,
        exam_subject: subjectKey,
        knowledge_context: knowledgeContext || undefined,
        ...extra,
      });
    }
    return base;
  }, [isCourseMode, displayCourseName, knowledgeContext, subjectKey, subjectLabel, user?.username]);

  const canReferenceMaterial = useCallback((material) => {
    const status = String(material?.parse_status || "").toLowerCase();
    return (status === "success" || status === "partial") && Number(material?.chunk_count || 0) > 0;
  }, []);

  const getUnreferenceableReason = useCallback((material) => {
    const status = String(material?.parse_status || "").toLowerCase();
    if (status === "pending" || status === "parsing") return "资料正在解析，完成后可引用";
    if (status === "failed") return "资料解析失败，不能用于问答";
    if ((status === "success" || status === "partial") && Number(material?.chunk_count || 0) <= 0) return "尚未生成知识片段";
    return "暂不可引用";
  }, []);

  const loadHistory = useCallback(async () => {
    if (!user?.username) return;
    try {
      const res = await fetch(`${API_BASE}/chat/history?${buildScopeParams().toString()}`);
      const data = await res.json().catch(() => ({}));
      setHistorySessions(Array.isArray(data.sessions) ? data.sessions : []);
    } catch {
      setHistorySessions([]);
    }
  }, [buildScopeParams, user?.username]);

  const loadMaterials = useCallback(async () => {
    if (!user?.username) return [];
    setLibraryLoading(true);
    try {
      const query = new URLSearchParams({ username: user.username });
      // Resolve subject for material filtering — try all available identifiers
      const resolvedSubject = courseName || courseId || displayCourseName
        || (typeof courseName === 'string' ? courseName : '')
        || (typeof courseId === 'string' ? courseId : '')
        || (isCourseMode ? subjectLabel : "");
      if (resolvedSubject) query.set("subject", resolvedSubject);
      const res = await fetch(`${API_BASE}/materials?${query.toString()}`);
      const data = await res.json().catch(() => ({}));
      const materials = res.ok && Array.isArray(data.materials) ? data.materials : [];
      setLibraryMaterials(materials);
      return materials;
    } catch {
      setLibraryMaterials([]);
      return [];
    } finally {
      setLibraryLoading(false);
    }
  }, [courseName, courseId, displayCourseName, isCourseMode, subjectLabel, user?.username]);

  const updateCurrentSessionId = useCallback((sessionId) => {
    const nextSessionId = sessionId === null || sessionId === undefined || sessionId === "" ? null : Number(sessionId);
    const safeSessionId = Number.isNaN(nextSessionId) ? sessionId : nextSessionId;
    currentSessionIdRef.current = safeSessionId;
    setCurrentSessionId(safeSessionId);
  }, []);

  const scrollMessagesToTop = useCallback(() => {
    window.requestAnimationFrame(() => {
      const container = messagesContainerRef.current;
      if (container) container.scrollTop = 0;
    });
  }, []);

  const scrollToLatestUser = useCallback(() => {
    window.requestAnimationFrame(() => {
      const container = messagesContainerRef.current;
      const target = lastUserMessageRef.current;
      if (!container || !target) return;
      const top = target.offsetTop - container.offsetTop - 12;
      container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    });
  }, []);

  const loadSession = useCallback(async (sessionId, options = {}) => {
    if (!user?.username || !sessionId) return;
    const preserveCurrentMessages = Boolean(options.preserveCurrentMessages);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}?${buildScopeParams().toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "加载历史对话失败");
      if (preserveCurrentMessages && userInteractedRef.current) return;
      if (!preserveCurrentMessages) userInteractedRef.current = true;
      updateCurrentSessionId(sessionId);
      const nextMessages = buildConversationView(data.messages);
      const lastUser = [...nextMessages].reverse().find((message) => message.role === "user");
      currentBranchIdRef.current = lastUser?.branch_id || "";
      shouldScrollToLatestUserRef.current = false;
      setMessages(nextMessages);
      scrollMessagesToTop();
    } catch (err) {
      setError(err.message || "加载历史对话失败");
    }
  }, [buildScopeParams, scrollMessagesToTop, updateCurrentSessionId, user?.username]);

  useEffect(() => {
    userInteractedRef.current = false;
    currentSessionIdRef.current = null;
    currentBranchIdRef.current = "";
    shouldScrollToLatestUserRef.current = false;
    setCurrentSessionId(null);
    setMessages([]);
    setInputText("");
    setSelectedMaterials([]);
    setEditingMessageId(null);
    setEditingText("");
    setError("");
    setNotice("");
    loadHistory();
    scrollMessagesToTop();
  }, [loadHistory, scrollMessagesToTop, subjectKey]);

  useEffect(() => {
    const material = initialMaterialToReference?.material;
    if (!material?.id) return;
    setSelectedMaterials((prev) => {
      if (prev.some((item) => item.id === material.id)) return prev;
      return [...prev, material];
    });
    setNotice("已将资料加入本轮引用");
    onInitialMaterialReferenced?.();
  }, [initialMaterialToReference?.nonce, initialMaterialToReference?.material, onInitialMaterialReferenced]);

  useEffect(() => {
    const title = knowledgeContext?.knowledgePointTitle || knowledgeContext?.knowledge_point_title || knowledgeContext?.title || "";
    if (!title) return;
    setInputText((prev) => prev || `请围绕「${title}」帮我梳理考研重点。`);
  }, [knowledgeContext?.knowledgePointTitle, knowledgeContext?.knowledge_point_title, knowledgeContext?.title]);

  useEffect(() => {
    if (!shouldScrollToLatestUserRef.current) return;
    scrollToLatestUser();
  }, [messages, loading, scrollToLatestUser]);

  useEffect(() => {
    if (!toolMenuOpen) return undefined;
    const handlePointerDown = (event) => {
      if (!toolMenuRef.current?.contains(event.target)) setToolMenuOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [toolMenuOpen]);

  const openMaterialPicker = async () => {
    setToolMenuOpen(false);
    setPickerOpen(true);
    setLibrarySearchQuery("");
    await loadMaterials();
  };

  const openUploadPicker = () => {
    setToolMenuOpen(false);
    uploadInputRef.current?.click();
  };

  const startNewConversation = () => {
    userInteractedRef.current = true;
    updateCurrentSessionId(null);
    currentBranchIdRef.current = "";
    shouldScrollToLatestUserRef.current = false;
    setMessages([]);
    setInputText("");
    setEditingMessageId(null);
    setEditingText("");
    setError("");
    setNotice("");
    scrollMessagesToTop();
  };

  const deleteSession = async (sessionId, event) => {
    event.stopPropagation();
    if (!user?.username) return;
    try {
      const query = buildScopeParams();
      await fetch(`${API_BASE}/chat/sessions/${sessionId}?${query.toString()}`, { method: "DELETE" });
      if (currentSessionIdRef.current === sessionId || Number(currentSessionIdRef.current) === Number(sessionId)) startNewConversation();
      loadHistory();
    } catch {
      setError("暂时无法删除该对话");
    }
  };

  const renameSession = async (session, event) => {
    event.stopPropagation();
    if (!user?.username) return;
    const inputTitle = window.prompt("请输入新的对话标题", session.title || "");
    if (inputTitle === null) return;
    const title = inputTitle.trim();
    if (!title) return;
    try {
      const query = buildScopeParams();
      const res = await fetch(`${API_BASE}/conversations/${session.id}?${query.toString()}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "重命名失败");
      setHistorySessions((prev) => prev.map((item) => (item.id === session.id ? { ...item, title: data.title || title } : item)));
    } catch (err) {
      setError(err.message || "暂时无法重命名该对话");
    }
  };

  const toggleMaterialSelection = (material) => {
    if (!canReferenceMaterial(material)) return;
    setSelectedMaterials((prev) => {
      const exists = prev.some((item) => item.id === material.id);
      if (exists) return prev.filter((item) => item.id !== material.id);
      return [...prev, material];
    });
  };

  const removeSelectedMaterial = (materialId) => {
    setSelectedMaterials((prev) => prev.filter((item) => item.id !== materialId));
  };

  const handleUploadFiles = async (files) => {
    const fileList = Array.from(files || []);
    if (fileList.length === 0 || !user?.username) return;
    setUploading(true);
    setError("");
    setNotice("");
    try {
      const uploadedMaterials = [];
      for (const file of fileList) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("username", user.username);
        formData.append("subject", courseName || subjectLabel);
        formData.append("save_to_materials", "true");
        const res = await fetch(`${API_BASE}/materials/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${user.username}` },
          body: formData,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `上传失败：${file.name}`);
        const material = normalizeUploadedMaterial(data, file);
        if (material) uploadedMaterials.push(material);
      }
      const latestMaterials = await loadMaterials();
      const byId = new Map(latestMaterials.map((material) => [material.id, material]));
      const readyUploads = uploadedMaterials.map((material) => byId.get(material.id) || material).filter(canReferenceMaterial);
      if (readyUploads.length > 0) {
        setSelectedMaterials((prev) => {
          const existing = new Set(prev.map((item) => item.id));
          return [...prev, ...readyUploads.filter((item) => !existing.has(item.id))];
        });
        setNotice("资料已上传并加入本轮引用");
      } else {
        setNotice("资料已上传，解析完成后可在资料选择中引用");
      }
    } catch (err) {
      setError(err.message || "资料上传失败");
    } finally {
      setUploading(false);
    }
  };

  const getMessageKey = (message) => String(message?.clientId ?? message?.id ?? "");

  const collectFollowingAssistants = (items, startIndex) => {
    const assistants = [];
    for (let index = startIndex + 1; index < items.length && items[index]?.role === "assistant"; index += 1) {
      assistants.push({ ...items[index], animateTyping: false });
    }
    return assistants;
  };

  const beginEditMessage = (message) => {
    setEditingMessageId(getMessageKey(message));
    setEditingText(message?.content || "");
  };

  const cancelEditMessage = () => {
    setEditingMessageId(null);
    setEditingText("");
  };

  const switchMessageVersion = (messageKey, nextVersionIndex) => {
    setMessages((prev) => {
      const userIndex = prev.findIndex((item) => getMessageKey(item) === String(messageKey));
      if (userIndex === -1 || prev[userIndex]?.role !== "user") return prev;
      const userMessage = prev[userIndex];
      const versions = Array.isArray(userMessage.versions) ? [...userMessage.versions] : [];
      if (versions.length <= 1 || nextVersionIndex < 0 || nextVersionIndex >= versions.length) return prev;

      const currentVersionIndex = Number(userMessage.currentVersionIndex || 0);
      const currentAssistants = collectFollowingAssistants(prev, userIndex);
      if (versions[currentVersionIndex]) {
        versions[currentVersionIndex] = {
          ...versions[currentVersionIndex],
          assistantMessages: currentAssistants,
        };
      }

      const nextVersion = versions[nextVersionIndex];
      currentBranchIdRef.current = nextVersion.branch_id || "";
      shouldScrollToLatestUserRef.current = true;
      const restoredAssistants = (Array.isArray(nextVersion.assistantMessages) ? nextVersion.assistantMessages : [])
        .map((assistant) => ({ ...assistant, animateTyping: false }));

      return [
        ...prev.slice(0, userIndex),
        {
          ...userMessage,
          id: nextVersion.message_id || userMessage.id,
          clientId: nextVersion.clientId || userMessage.clientId,
          content: nextVersion.userContent || nextVersion.content || userMessage.content,
          branch_id: nextVersion.branch_id || "",
          root_message_id: nextVersion.root_message_id ?? userMessage.root_message_id ?? null,
          parent_message_id: nextVersion.parent_message_id ?? userMessage.parent_message_id ?? null,
          version_index: nextVersion.version_index ?? nextVersionIndex,
          versions,
          currentVersionIndex: nextVersionIndex,
          edited: versions.length > 1,
        },
        ...restoredAssistants,
      ];
    });
  };

  const submitEditedMessage = async (messageKey) => {
    const nextContent = editingText.trim();
    if (!nextContent || loading || !user?.username) return;

    const sourceIndex = messages.findIndex((item) => getMessageKey(item) === String(messageKey));
    if (sourceIndex === -1 || messages[sourceIndex]?.role !== "user") return;
    const sourceMessage = messages[sourceIndex];
    const oldVersions = Array.isArray(sourceMessage.versions) && sourceMessage.versions.length > 0
      ? [...sourceMessage.versions]
      : [{
          message_id: sourceMessage.id,
          clientId: sourceMessage.clientId,
          userContent: sourceMessage.content || "",
          assistantMessages: collectFollowingAssistants(messages, sourceIndex),
          branch_id: sourceMessage.branch_id || "",
          root_message_id: sourceMessage.root_message_id ?? sourceMessage.id ?? null,
          parent_message_id: sourceMessage.parent_message_id ?? null,
          version_index: sourceMessage.version_index || 0,
          createdAt: sourceMessage.created_at || new Date().toISOString(),
        }];
    const currentVersionIndex = Number(sourceMessage.currentVersionIndex || 0);
    if (oldVersions[currentVersionIndex]) {
      oldVersions[currentVersionIndex] = {
        ...oldVersions[currentVersionIndex],
        assistantMessages: collectFollowingAssistants(messages, sourceIndex),
      };
    }
    const nextVersions = [
      ...oldVersions,
      {
        message_id: null,
        userContent: nextContent,
        assistantMessages: [],
        branch_id: "",
        root_message_id: sourceMessage.root_message_id ?? sourceMessage.id ?? null,
        parent_message_id: sourceMessage.id ?? null,
        version_index: oldVersions.length,
        createdAt: new Date().toISOString(),
      },
    ];

    shouldScrollToLatestUserRef.current = true;
    setMessages((prev) => [
      ...prev.slice(0, sourceIndex),
      {
        ...sourceMessage,
        content: nextContent,
        versions: nextVersions,
        currentVersionIndex: nextVersions.length - 1,
        edited: true,
      },
    ]);

    if (!sourceMessage || sourceIndex === -1) return;

    setEditingMessageId(null);
    setEditingText("");
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildChatPayload(nextContent, {
          session_id: currentSessionIdRef.current,
          edit_source_message_id: Number(sourceMessage.id) || null,
          material_ids: selectedMaterials.filter(canReferenceMaterial).map((material) => material.id),
        })),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "AI 回复失败");

      if (data.session?.id || data.session_id) updateCurrentSessionId(data.session?.id ?? data.session_id);
      const branchId = data.branch_id || `local-${Date.now()}`;
      currentBranchIdRef.current = branchId;
      const assistantMessage = {
        id: data.assistant_message_id || `local-assistant-${Date.now()}`,
        clientId: `local-assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer || "",
        references: data.references || [],
        branch_id: branchId,
        root_message_id: data.root_message_id ?? Number(sourceMessage.id) ?? null,
        parent_message_id: data.user_message_id ?? null,
        version_index: Number(data.version_index || nextVersions.length - 1),
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => {
        const index = prev.findIndex((item) => getMessageKey(item) === String(messageKey));
        if (index === -1) return [...prev, assistantMessage];
        const userMessage = prev[index];
        const versions = Array.isArray(userMessage.versions) ? [...userMessage.versions] : nextVersions;
        const currentVersionIndex = Number(userMessage.currentVersionIndex ?? versions.length - 1);
        if (versions[currentVersionIndex]) {
          versions[currentVersionIndex] = {
            ...versions[currentVersionIndex],
            message_id: data.user_message_id || versions[currentVersionIndex].message_id,
            branch_id: branchId,
            root_message_id: data.root_message_id ?? versions[currentVersionIndex].root_message_id ?? Number(sourceMessage.id) ?? null,
            parent_message_id: Number(sourceMessage.id) || versions[currentVersionIndex].parent_message_id || null,
            version_index: assistantMessage.version_index,
            assistantMessages: [assistantMessage],
          };
        }
        return [
          ...prev.slice(0, index),
          {
            ...userMessage,
            id: data.user_message_id || userMessage.id,
            branch_id: branchId,
            root_message_id: data.root_message_id ?? userMessage.root_message_id ?? Number(sourceMessage.id) ?? null,
            parent_message_id: Number(sourceMessage.id) || userMessage.parent_message_id || null,
            version_index: assistantMessage.version_index,
            versions,
            currentVersionIndex,
            edited: true,
          },
          assistantMessage,
        ];
      });
      loadHistory();
    } catch (err) {
      setError(err.message || "编辑问题失败");
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (text) => {
    const msg = (text || inputText).trim();
    if (!msg || loading || !user?.username) return;
    userInteractedRef.current = true;
    shouldScrollToLatestUserRef.current = true;
    const activeSessionId = currentSessionIdRef.current;

    setInputText("");
    setError("");
    const userMessage = {
      id: `local-user-${Date.now()}`,
      clientId: `local-user-${Date.now()}`,
      role: "user",
      content: msg,
      branch_id: currentBranchIdRef.current || "",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildChatPayload(msg, {
          session_id: activeSessionId,
          branch_id: currentBranchIdRef.current || "",
          material_ids: selectedMaterials.filter(canReferenceMaterial).map((material) => material.id),
        })),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 429) throw new Error("今日 AI 问答额度已用完，请明天再试或升级套餐");
        throw new Error(data.detail || "AI 服务调用失败");
      }

      const nextSessionId = data.session?.id ?? data.session_id ?? activeSessionId;
      if (nextSessionId) updateCurrentSessionId(nextSessionId);
      currentBranchIdRef.current = data.branch_id || currentBranchIdRef.current || "";

      const assistantMessage = {
        id: data.assistant_message_id || `local-assistant-${Date.now()}`,
        clientId: `local-assistant-${Date.now()}`,
        role: "assistant",
        content: data.answer || "",
        references: data.references || [],
        branch_id: data.branch_id || currentBranchIdRef.current || "",
        root_message_id: data.root_message_id ?? null,
        parent_message_id: data.user_message_id ?? null,
        version_index: Number(data.version_index || 0),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [
        ...prev.map((item) => (
          item.clientId === userMessage.clientId
            ? {
                ...item,
                id: data.user_message_id || item.id,
                branch_id: data.branch_id || item.branch_id || "",
                root_message_id: data.root_message_id ?? item.root_message_id ?? null,
                version_index: Number(data.version_index || item.version_index || 0),
              }
            : item
        )),
        assistantMessage,
      ]);
      loadHistory();
    } catch (err) {
      setError(err.message || "发送失败");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="examchat-shell">
      <aside className="examchat-history-panel">
        <button type="button" className="examchat-new-btn" onClick={startNewConversation}>
          + 新对话
        </button>
        <div className="examchat-history-head">
          <strong>历史对话</strong>
          <button type="button" onClick={loadHistory}>刷新</button>
        </div>
        <div className="examchat-history-list">
          {historySessions.length === 0 ? (
            <div className="examchat-history-empty">暂无历史对话</div>
          ) : (
            historySessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`examchat-history-item${currentSessionId === session.id ? " active" : ""}`}
                onClick={() => loadSession(session.id)}
              >
                <span>{session.title || "未命名对话"}</span>
                <small>{isCourseMode ? (session.subject || subjectLabel) : getSubjectLabel(session.exam_subject, subjectLabel)} · {formatTime(session.created_at)}</small>
                <i>
                  <b onClick={(event) => renameSession(session, event)}>重命名</b>
                  <b onClick={(event) => deleteSession(session.id, event)}>删除</b>
                </i>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="examchat-main-panel">
        <header className="examchat-header">
          <div>
            <h2 className="examchat-title">{examCramMode ? subjectLabel : `AI 问答 · ${subjectLabel}`}</h2>
            <p className="examchat-subtitle">{subtitleText}</p>
          </div>
        </header>

        {error && (
          <div className="examchat-error">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>关闭</button>
          </div>
        )}
        {notice && !error && (
          <div className="examchat-notice">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice("")}>知道了</button>
          </div>
        )}

        <div className="examchat-messages" ref={messagesContainerRef}>
          {messages.length === 0 && !loading ? (
            <div className="examchat-empty" />
          ) : (
            messages.map((message) => (
              <div
                key={`${message.role}-${message.id}-${message.clientId || ""}`}
                ref={message.id === lastUserMessageId ? lastUserMessageRef : null}
                className={`examchat-msg${message.role === "user" ? " examchat-msg--user" : ""}`}
              >
                <div className="examchat-msg-content">
                  {message.role === "assistant" ? (
                    <MarkdownMessage content={message.content} />
                  ) : editingMessageId === getMessageKey(message) ? (
                    <div className="examchat-edit-box">
                      <textarea
                        value={editingText}
                        onChange={(event) => setEditingText(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            submitEditedMessage(getMessageKey(message));
                          }
                          if (event.key === "Escape") cancelEditMessage();
                        }}
                        rows={3}
                        autoFocus
                      />
                      <div className="examchat-edit-actions">
                        <span>Enter 提交 · Esc 取消</span>
                        <button type="button" onClick={cancelEditMessage}>取消</button>
                        <button type="button" onClick={() => submitEditedMessage(getMessageKey(message))} disabled={!editingText.trim() || loading}>
                          提交
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p>{message.content}</p>
                  )}
                  {message.role === "user" && editingMessageId !== getMessageKey(message) && (
                    <div className="examchat-msg-tools">
                      {Array.isArray(message.versions) && message.versions.length > 1 && (
                        <div className="examchat-branch-switch">
                          <button
                            type="button"
                            onClick={() => {
                              const total = message.versions.length;
                              const current = Number(message.currentVersionIndex || 0);
                              switchMessageVersion(getMessageKey(message), (current - 1 + total) % total);
                            }}
                          >
                            上一分支
                          </button>
                          <span>分支 {Number(message.currentVersionIndex || 0) + 1} / {message.versions.length}</span>
                          <button
                            type="button"
                            onClick={() => {
                              const total = message.versions.length;
                              const current = Number(message.currentVersionIndex || 0);
                              switchMessageVersion(getMessageKey(message), (current + 1) % total);
                            }}
                          >
                            下一分支
                          </button>
                        </div>
                      )}
                      <button type="button" onClick={() => beginEditMessage(message)} disabled={loading}>
                        编辑问题
                      </button>
                    </div>
                  )}
                  {Array.isArray(message.references) && message.references.length > 0 && (
                    <div className="examchat-refs">
                      <strong>参考资料</strong>
                      {message.references.map((reference, index) => {
                        const title = reference.source_filename || reference.filename || `资料 ${index + 1}`;
                        const summary = reference.chunk_summary || reference.summary || reference.snippet || "";
                        const text = reference.chunk_text || reference.text || "";
                        return (
                          <details key={`${reference.material_id || index}-${index}`} className="examchat-ref-detail">
                            <summary>{title}</summary>
                            {summary && <p>{summary}</p>}
                            {text && <pre>{text}</pre>}
                          </details>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="examchat-msg">
              <div className="examchat-msg-content">
                <p className="examchat-thinking">AI 正在思考...</p>
              </div>
            </div>
          )}
        </div>

        <div className="examchat-input-area">
          {selectedMaterials.length > 0 && (
            <div className="examchat-selected-bar">
              {selectedMaterials.map((material) => (
                <button key={material.id} type="button" onClick={() => removeSelectedMaterial(material.id)}>
                  {material.original_filename || material.file_name || "资料"} ×
                </button>
              ))}
            </div>
          )}
          <div className="examchat-input-row">
            <div className="examchat-plus-wrap" ref={toolMenuRef}>
              <button
                type="button"
                className={`examchat-plus-btn${toolMenuOpen ? " active" : ""}`}
                onClick={() => setToolMenuOpen((open) => !open)}
                aria-label="添加资料"
                aria-expanded={toolMenuOpen}
              >
                +
              </button>
              {toolMenuOpen && (
                <div className="examchat-plus-menu">
                  <button type="button" onClick={openMaterialPicker}>
                    <span aria-hidden="true">引</span>
                    引用资料
                  </button>
                  <button type="button" onClick={openUploadPicker} disabled={uploading}>
                    <span aria-hidden="true">↑</span>
                    {uploading ? "上传中..." : "上传资料"}
                  </button>
                </div>
              )}
            </div>
            <textarea
              className="examchat-input"
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={examCramMode
                ? "输入你的问题，例如：TCP 三次握手为什么不是两次？"
                : `向 AI 提问${isCourseMode ? `《${courseName}》` : " " + subjectLabel}相关问题...`}
              rows={2}
              disabled={loading}
            />
            <button
              type="button"
              className="examchat-send-btn"
              onClick={() => sendMessage()}
              disabled={loading || !inputText.trim()}
            >
              <span className="examchat-send-icon">➤</span>
              <span>{loading ? "发送中" : "发送"}</span>
            </button>
          </div>
          <input
            ref={uploadInputRef}
            type="file"
            multiple
            accept={ALLOWED_UPLOAD_EXTENSIONS}
            onChange={(event) => {
              handleUploadFiles(event.target.files);
              event.target.value = "";
            }}
            style={{ display: "none" }}
          />
        </div>
      </section>

      <aside className="examchat-sidebar">
        <div className="examchat-side-card">
          <div className="examchat-side-title">
            <h4>本轮引用资料</h4>
          </div>
          {selectedMaterials.length === 0 ? (
            <div className="examchat-side-empty">
              <p>尚未引用资料。</p>
            </div>
          ) : (
            <ul className="examchat-ref-list">
              {selectedMaterials.map((material) => (
                <li key={material.id}>
                  <span title={material.original_filename || material.file_name}>
                    {material.original_filename || material.file_name}
                  </span>
                  <button type="button" onClick={() => removeSelectedMaterial(material.id)}>
                    移除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="examchat-side-card">
          <h4>{examCramMode ? "冲刺问答建议" : "推荐提问"}</h4>
          {examCramMode && (
            <div className="examchat-cram-tips">
              <span>5 天内最值得问</span>
              <span>高频考点</span>
              <span>可追问方向</span>
            </div>
          )}
          {recommendations.map((question) => (
            <button key={question} type="button" className="examchat-rec-btn" onClick={() => setInputText(question)}>
              {question}
            </button>
          ))}
        </div>

        {examCramMode && (
          <div className="examchat-side-card">
            <h4>AI 速记模式</h4>
            <button type="button" className="examchat-rec-btn" onClick={() => setInputText("请生成本课程考前速记卡，优先覆盖高频简答和计算题。")}>
              生成考前速记
            </button>
            <button type="button" className="examchat-rec-btn" onClick={() => setInputText("请总结本页对话中的考试重点和可复盘清单。")}>
              总结本页重点
            </button>
          </div>
        )}
      </aside>

      <MaterialPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        subjectLabel={courseName || subjectLabel}
        materials={libraryMaterials}
        loading={libraryLoading}
        searchQuery={librarySearchQuery}
        onSearchChange={setLibrarySearchQuery}
        selectedMaterials={selectedMaterials}
        onToggleMaterial={toggleMaterialSelection}
        canReferenceMaterial={canReferenceMaterial}
        getUnreferenceableReason={getUnreferenceableReason}
        getFileTypeLabel={getFileTypeLabel}
        formatFileSize={formatFileSize}
        getParseStatusLabel={getParseStatusLabel}
      />
    </div>
  );
}
