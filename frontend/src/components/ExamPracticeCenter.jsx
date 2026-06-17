import { useEffect, useState } from "react";
import ExamPastPaperPractice from "./ExamPastPaperPractice.jsx";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: { key: "data_structure", label: "数据结构", shortLabel: "数据结构", courseId: "data_structure_11408" },
  computer_organization: { key: "computer_organization", label: "计算机组成原理", shortLabel: "计组", courseId: "computer_organization_11408" },
  operating_system: { key: "operating_system", label: "操作系统", shortLabel: "操作系统", courseId: "operating_system_11408" },
  computer_network: { key: "computer_network", label: "计算机网络", shortLabel: "计网", courseId: "computer_network_11408" },
};

const SOURCE_LABELS = {
  past_paper: "真题练习",
  chapter_practice: "章节练习",
  ai_generated: "AI 出题",
};

async function safeJsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "请求失败");
  return payload;
}

function KnowledgeTree({ nodes = [], selectedCode, onSelect }) {
  const [expanded, setExpanded] = useState(() => new Set(nodes.map((n) => n.code || n.id)));

  useEffect(() => {
    setExpanded(new Set(nodes.map((n) => n.code || n.id)));
  }, [nodes]);

  const renderNode = (node, depth = 0) => {
    const key = node.code || node.id || `${node.title}-${depth}`;
    const hasChildren = Boolean(node.children?.length);
    const isExpanded = expanded.has(key);
    const isSelected = selectedCode === key;
    return (
      <div key={key} className="exam-knowledge-node">
        <div
          className={`exam-knowledge-node-row${isSelected ? " exam-knowledge-node-row--active" : ""}`}
          style={{ paddingLeft: 12 + depth * 18 }}
          onClick={() => onSelect(node)}
        >
          {hasChildren ? (
            <button
              type="button"
              className="exam-knowledge-toggle"
              onClick={(event) => {
                event.stopPropagation();
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
              aria-label={isExpanded ? "收起" : "展开"}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="exam-knowledge-toggle-placeholder" />
          )}
          <span className="exam-knowledge-node-title">{node.code ? `${node.code} ` : ""}{node.title || node.name}</span>
        </div>
        {hasChildren && isExpanded && (
          <div className="exam-knowledge-children">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return <div className="exam-knowledge-tree">{nodes.map((node) => renderNode(node))}</div>;
}

function getKnowledgeNodeKey(node, fallback = "") {
  return String(node?.code || node?.id || node?.title || node?.name || fallback);
}

function getKnowledgeNodeTitle(node) {
  return node?.title || node?.name || node?.code || "未命名知识点";
}

function KnowledgePointSelector({ nodes = [], selectedPoint, onSelect, onClear }) {
  const [expanded, setExpanded] = useState(() => new Set(nodes.map((node, index) => getKnowledgeNodeKey(node, `root-${index}`))));

  useEffect(() => {
    setExpanded(new Set(nodes.map((node, index) => getKnowledgeNodeKey(node, `root-${index}`))));
  }, [nodes]);

  const selectedKey = selectedPoint ? getKnowledgeNodeKey(selectedPoint.node, selectedPoint.path) : "";

  const renderNode = (node, depth = 0, parentPath = []) => {
    const key = getKnowledgeNodeKey(node, `${parentPath.join("/")}-${depth}`);
    const title = getKnowledgeNodeTitle(node);
    const path = [...parentPath, title].filter(Boolean);
    const hasChildren = Boolean(node.children?.length);
    const isExpanded = expanded.has(key);
    const isSelected = selectedKey === key;

    return (
      <div key={key} className="ai-kp-tree-node">
        <div
          className={`ai-kp-tree-row${isSelected ? " ai-kp-tree-row--selected" : ""}`}
          style={{ paddingLeft: 10 + depth * 18 }}
        >
          {hasChildren ? (
            <button
              type="button"
              className="ai-kp-tree-toggle"
              onClick={() => {
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
              aria-label={isExpanded ? "收起知识点" : "展开知识点"}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="ai-kp-tree-toggle-placeholder" />
          )}
          <button
            type="button"
            className="ai-kp-tree-select"
            onClick={() => onSelect({ key, node, path: path.join(" / ") })}
          >
            <span className="ai-kp-tree-code">{node.code || ""}</span>
            <span className="ai-kp-tree-title">{title}</span>
          </button>
        </div>
        {hasChildren && isExpanded && (
          <div className="ai-kp-tree-children">
            {node.children.map((child) => renderNode(child, depth + 1, path))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="ai-kp-selector">
      <div className="ai-kp-selected-summary">
        {selectedPoint ? (
          <>
            <span>已选范围</span>
            <strong>{selectedPoint.path}</strong>
            <button type="button" onClick={onClear}>清除</button>
          </>
        ) : (
          <span>可不选，按当前科目综合出题；也可选择任意父级或子级知识点范围。</span>
        )}
      </div>
      <div className="ai-kp-tree-panel">
        {nodes.length === 0 ? (
          <div className="ai-kp-tree-empty">知识点加载中...</div>
        ) : (
          nodes.map((node, index) => renderNode(node, 0, []))
        )}
      </div>
    </div>
  );
}

function PracticeSubPageHeader({ title, subtitle, subjectInfo, onBack }) {
  return (
    <div className="exam-practice-subpage-header">
      <button type="button" className="ghost-button compact" onClick={onBack}>← 返回练习中心</button>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
        <span className="exam-practice-subject-pill">当前科目：{subjectInfo.label}</span>
      </div>
    </div>
  );
}

function formatPracticeDuration(minutes = 0) {
  const safeMinutes = Number.isFinite(Number(minutes)) ? Math.max(0, Number(minutes)) : 0;
  if (safeMinutes < 60) return `${Math.round(safeMinutes)}m`;
  const hours = safeMinutes / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)}h`;
}

function normalizeKnowledgePointId(rawId) {
  if (!rawId) return "";
  return String(rawId).replace(/^(_leaf:|leaf:|_node:|node:|_kp:|kp:)/i, "").trim();
}

// Dynamic chapter outline by subject — DO NOT hardcode data_structure as default
function getChapterOutline(subjectKey) {
  if (subjectKey === "computer_organization") {
    return [
      { id:"0", title:"总览", code:"", children:[] },
      { id:"1", title:"第1章 计算机系统概述", code:"1", children:[
        {id:"1.1", title:"1.1 计算机发展历程", code:"1.1"},
        {id:"1.2", title:"1.2 计算机系统层次结构", code:"1.2"},
        {id:"1.3", title:"1.3 计算机的性能指标", code:"1.3"},
      ]},
      { id:"2", title:"第2章 数据的表示和运算", code:"2", children:[
        {id:"2.1", title:"2.1 数制与编码", code:"2.1"},
        {id:"2.2", title:"2.2 运算方法和运算电路", code:"2.2"},
        {id:"2.3", title:"2.3 浮点数的表示与运算", code:"2.3"},
      ]},
      { id:"3", title:"第3章 存储系统", code:"3", children:[
        {id:"3.1", title:"3.1 存储器概述", code:"3.1"},
        {id:"3.2", title:"3.2 主存储器", code:"3.2"},
        {id:"3.3", title:"3.3 主存储器与CPU的连接", code:"3.3"},
        {id:"3.4", title:"3.4 外部存储器", code:"3.4"},
        {id:"3.5", title:"3.5 高速缓冲存储器", code:"3.5"},
        {id:"3.6", title:"3.6 虚拟存储器", code:"3.6"},
      ]},
      { id:"4", title:"第4章 指令系统", code:"4", children:[
        {id:"4.1", title:"4.1 指令系统", code:"4.1"},
        {id:"4.2", title:"4.2 寻址方式", code:"4.2"},
        {id:"4.3", title:"4.3 汇编程序的基本概念和表示", code:"4.3"},
        {id:"4.4", title:"4.4 CISC和RISC的基本概念", code:"4.4"},
      ]},
      { id:"5", title:"第5章 中央处理器", code:"5", children:[
        {id:"5.1", title:"5.1 CPU的功能和基本结构", code:"5.1"},
        {id:"5.2", title:"5.2 指令执行过程", code:"5.2"},
        {id:"5.3", title:"5.3 数据通路的功能和基本结构", code:"5.3"},
        {id:"5.4", title:"5.4 控制器的功能和工作原理", code:"5.4"},
        {id:"5.5", title:"5.5 异常和中断机制", code:"5.5"},
        {id:"5.6", title:"5.6 指令流水线", code:"5.6"},
        {id:"5.7", title:"5.7 多处理器的基本概念", code:"5.7"},
      ]},
      { id:"6", title:"第6章 总线", code:"6", children:[
        {id:"6.1", title:"6.1 总线概述", code:"6.1"},
        {id:"6.2", title:"6.2 总线事务和定时", code:"6.2"},
      ]},
      { id:"7", title:"第7章 输入/输出系统", code:"7", children:[
        {id:"7.1", title:"7.1 I/O系统基本概念", code:"7.1"},
        {id:"7.2", title:"7.2 I/O接口", code:"7.2"},
        {id:"7.3", title:"7.3 I/O方式", code:"7.3"},
      ]},
    ];
  }
  // OS chapter outline (operating_system)
  if (subjectKey === "operating_system") {
    return [
      { id:"0", title:"总览", code:"", children:[] },
      { id:"1", title:"第1章 计算机系统概述", code:"1", children:[
        {id:"1.1", title:"1.1 操作系统的基本概念", code:"1.1"},
        {id:"1.2", title:"1.2 操作系统发展历程", code:"1.2"},
        {id:"1.3", title:"1.3 操作系统运行环境", code:"1.3"},
        {id:"1.4", title:"1.4 操作系统结构", code:"1.4"},
        {id:"1.5", title:"1.5 操作系统引导", code:"1.5"},
        {id:"1.6", title:"1.6 虚拟机", code:"1.6"},
      ]},
      { id:"2", title:"第2章 进程与线程", code:"2", children:[
        {id:"2.1", title:"2.1 进程与线程简介", code:"2.1"},
        {id:"2.2", title:"2.2 CPU调度", code:"2.2"},
        {id:"2.3", title:"2.3 同步与互斥", code:"2.3"},
        {id:"2.4", title:"2.4 死锁", code:"2.4"},
      ]},
      { id:"3", title:"第3章 内存管理", code:"3", children:[
        {id:"3.1", title:"3.1 内存管理概述", code:"3.1"},
        {id:"3.2", title:"3.2 虚拟内存管理", code:"3.2"},
      ]},
      { id:"4", title:"第4章 文件管理", code:"4", children:[
        {id:"4.1", title:"4.1 文件系统基础", code:"4.1"},
        {id:"4.2", title:"4.2 目录与文件", code:"4.2"},
        {id:"4.3", title:"4.3 文件系统", code:"4.3"},
      ]},
      { id:"5", title:"第5章 输入/输出管理", code:"5", children:[
        {id:"5.1", title:"5.1 I/O管理概述", code:"5.1"},
        {id:"5.2", title:"5.2 设备管理与调度", code:"5.2"},
        {id:"5.3", title:"5.3 磁盘和固态硬盘", code:"5.3"},
      ]},
    ];
  }
  // CN chapter outline (computer_network)
  if (subjectKey === "computer_network") {
    return [
      { id:"0", title:"总览", code:"", children:[] },
      { id:"1", title:"第1章 计算机网络体系结构", code:"1", children:[
        {id:"1.1", title:"1.1 计算机网络概述", code:"1.1"},
        {id:"1.2", title:"1.2 计算机网络体系结构与参考模型", code:"1.2"},
      ]},
      { id:"2", title:"第2章 物理层", code:"2", children:[
        {id:"2.1", title:"2.1 通信基础", code:"2.1"},
        {id:"2.2", title:"2.2 传输介质", code:"2.2"},
        {id:"2.3", title:"2.3 物理层设备", code:"2.3"},
      ]},
      { id:"3", title:"第3章 数据链路层", code:"3", children:[
        {id:"3.1", title:"3.1 数据链路层功能", code:"3.1"},
        {id:"3.2", title:"3.2 组帧", code:"3.2"},
        {id:"3.3", title:"3.3 差错控制", code:"3.3"},
        {id:"3.4", title:"3.4 流量控制与可靠传输", code:"3.4"},
        {id:"3.5", title:"3.5 介质访问控制", code:"3.5"},
        {id:"3.6", title:"3.6 局域网", code:"3.6"},
        {id:"3.7", title:"3.7 广域网", code:"3.7"},
        {id:"3.8", title:"3.8 数据链路层设备", code:"3.8"},
      ]},
      { id:"4", title:"第4章 网络层", code:"4", children:[
        {id:"4.1", title:"4.1 网络层功能", code:"4.1"},
        {id:"4.2", title:"4.2 路由算法", code:"4.2"},
        {id:"4.3", title:"4.3 IPv4", code:"4.3"},
        {id:"4.4", title:"4.4 IPv6", code:"4.4"},
        {id:"4.5", title:"4.5 路由协议", code:"4.5"},
        {id:"4.6", title:"4.6 IP组播", code:"4.6"},
        {id:"4.7", title:"4.7 移动IP", code:"4.7"},
        {id:"4.8", title:"4.8 网络层设备", code:"4.8"},
      ]},
      { id:"5", title:"第5章 传输层", code:"5", children:[
        {id:"5.1", title:"5.1 传输层概述", code:"5.1"},
        {id:"5.2", title:"5.2 UDP", code:"5.2"},
        {id:"5.3", title:"5.3 TCP", code:"5.3"},
      ]},
      { id:"6", title:"第6章 应用层", code:"6", children:[
        {id:"6.1", title:"6.1 网络应用模型", code:"6.1"},
        {id:"6.2", title:"6.2 DNS", code:"6.2"},
        {id:"6.3", title:"6.3 FTP", code:"6.3"},
        {id:"6.4", title:"6.4 电子邮件", code:"6.4"},
        {id:"6.5", title:"6.5 万维网WWW", code:"6.5"},
      ]},
    ];
  }
  // Default: data_structure only
  return [
    { id:"0", title:"总览", code:"", children:[] },
    { id:"1", title:"第1章 绪论", code:"1", children:[
      {id:"1.1", title:"1.1 数据结构的基本概念", code:"1.1"},
      {id:"1.2", title:"1.2 算法和算法评价", code:"1.2"},
    ]},
    { id:"2", title:"第2章 线性表", code:"2", children:[
      {id:"2.1", title:"2.1 线性表的定义和基本操作", code:"2.1"},
      {id:"2.2", title:"2.2 线性表的顺序表示", code:"2.2"},
      {id:"2.3", title:"2.3 线性表的链式表示", code:"2.3"},
    ]},
    { id:"3", title:"第3章 栈、队列和数组", code:"3", children:[
      {id:"3.1", title:"3.1 栈", code:"3.1"},
      {id:"3.2", title:"3.2 队列", code:"3.2"},
      {id:"3.3", title:"3.3 栈和队列的应用", code:"3.3"},
      {id:"3.4", title:"3.4 数组和特殊矩阵", code:"3.4"},
    ]},
    { id:"4", title:"第4章 串", code:"4", children:[
      {id:"4.1", title:"4.1 串的定义和实现", code:"4.1"},
      {id:"4.2", title:"4.2 串的模式匹配", code:"4.2"},
    ]},
    { id:"5", title:"第5章 树与二叉树", code:"5", children:[
      {id:"5.1", title:"5.1 树的基本概念", code:"5.1"},
      {id:"5.2", title:"5.2 二叉树的概念", code:"5.2"},
      {id:"5.3", title:"5.3 二叉树的遍历和线索二叉树", code:"5.3"},
      {id:"5.4", title:"5.4 树、森林", code:"5.4"},
      {id:"5.5", title:"5.5 树与二叉树的应用", code:"5.5"},
    ]},
    { id:"6", title:"第6章 图", code:"6", children:[
      {id:"6.1", title:"6.1 图的基本概念", code:"6.1"},
      {id:"6.2", title:"6.2 图的遍历", code:"6.2"},
      {id:"6.3", title:"6.3 图的存储及基本操作", code:"6.3"},
      {id:"6.4", title:"6.4 图的应用", code:"6.4"},
    ]},
    { id:"7", title:"第7章 查找", code:"7", children:[
      {id:"7.1", title:"7.1 查找的基本概念", code:"7.1"},
      {id:"7.2", title:"7.2 顺序查找和折半查找", code:"7.2"},
      {id:"7.3", title:"7.3 树形查找", code:"7.3"},
      {id:"7.4", title:"7.4 散列表", code:"7.4"},
    ]},
    { id:"8", title:"第8章 排序", code:"8", children:[
      {id:"8.1", title:"8.1 排序的基本概念", code:"8.1"},
      {id:"8.2", title:"8.2 插入排序", code:"8.2"},
      {id:"8.3", title:"8.3 交换排序", code:"8.3"},
      {id:"8.4", title:"8.4 选择排序", code:"8.4"},
      {id:"8.5", title:"8.5 归并排序和基数排序", code:"8.5"},
      {id:"8.6", title:"8.6 内部排序算法比较", code:"8.6"},
      {id:"8.7", title:"8.7 外部排序", code:"8.7"},
    ]},
  ];
}

function SectionOutline({ nodes, selectedId, onSelect }) {
  const [expanded, setExpanded] = useState(() => new Set(nodes.filter(n=>n.children?.length>0).map(n=>n.id)));
  return (
    <div className="chapter-section-outline">
      {nodes.map(ch => (
        <div key={ch.id}>
          <div className={`chapter-section-chapter ${selectedId===ch.id?"chapter-section-chapter--active":""}`}
               onClick={() => onSelect(ch)}>
            <span className="chapter-section-chapter-title">{ch.title}</span>
          </div>
          {expanded.has(ch.id) && ch.children?.length > 0 && (
            <div className="chapter-section-sections">
              {ch.children.map(sec => (
                <div key={sec.id} className={`chapter-section-section ${selectedId===sec.id?"chapter-section-section--active":""}`}
                     onClick={() => onSelect(sec)}>
                  <span>{sec.title}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ChapterPracticePage({ subjectInfo, user, onBack }) {
  const [selected, setSelected] = useState(getChapterOutline(subjectInfo.key)[0]);
  const [kpQuestions, setKpQuestions] = useState(null);
  const [kpLoading, setKpLoading] = useState(false);
  const [startingPractice, setStartingPractice] = useState(false);
  const [doneIds, setDoneIds] = useState(new Set());

  // Reset selected chapter when subject changes
  useEffect(() => {
    setSelected(getChapterOutline(subjectInfo.key)[0]);
  }, [subjectInfo.key]);

  useEffect(() => {
    setKpLoading(true); setKpQuestions(null);
    const id = selected?.code || "";
    const params = new URLSearchParams();
    if (id) params.set("knowledge_point_id", id);
    params.set("include_children", "true");
    if (user?.username) params.set("username", user.username);
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/chapter-practice/questions?${params.toString()}`)
      .then(p => setKpQuestions(p)).catch(() => setKpQuestions({items:[],total:0})).finally(()=>setKpLoading(false));
    // Also load done records
    if (user?.username) {
      safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/done-records?username=${encodeURIComponent(user.username)}&practice_type=chapter`)
        .then(d => setDoneIds(new Set((d.items||[]).map(r=>r.question_bank_id).filter(Boolean))))
        .catch(() => {});
    }
  }, [selected?.code, subjectInfo.key]);

  const totalQ = kpQuestions?.total || 0;
  const selTitle = selected?.title || "总览";

  const startChapterPractice = async () => {
    if (!user?.username || !kpQuestions?.items?.length || totalQ === 0) return;
    // Open window synchronously to avoid popup blocker
    const w = window.open("", "_blank");
    setStartingPractice(true);
    try {
      const qids = kpQuestions.items.map(q => q.id);
      const data = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/chapter-practice/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          question_ids: qids,
          knowledge_point_id: selected?.code || "",
          knowledge_point_name: selected?.title || "",
          knowledge_point_path: selected?.title || "",
        }),
      });
      if (w) {
        w.location.href = `/exam/11408/${subjectInfo.key}/chapter-practice/session/${data.attempt_id}`;
      } else {
        window.open(`/exam/11408/${subjectInfo.key}/chapter-practice/session/${data.attempt_id}`, "_blank");
      }
    } catch (e) {
      if (w) w.close();
      alert("创建练习失败：" + (e.message || "未知错误"));
    } finally {
      setStartingPractice(false);
    }
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="练习看板 · 章节练习" subtitle="按章节知识点做题，提交后自动标记已练习" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-split">
        <section className="exam-practice-panel exam-practice-outline-panel" style={{maxWidth:260}}>
          <h3>章节大纲</h3>
          <SectionOutline nodes={getChapterOutline(subjectInfo.key)} selectedId={selected?.id} onSelect={setSelected} />
        </section>
        <section className="exam-practice-panel exam-practice-question-panel" style={{overflow:"auto"}}>
          <div className="exam-practice-panel-title"><h3>{selTitle}</h3></div>
          {kpLoading ? <div className="past-paper-loading">查询中...</div> :
           kpQuestions ? (totalQ > 0 ? (<>
            <div className="chapter-analytics-row" style={{marginBottom:12,padding:10,background:"#faf8ff",borderRadius:10,fontSize:"0.82rem",display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
              <div>
                <span>范围：<strong>{selTitle}</strong></span>
                <span style={{marginLeft:16}}>总题数：<strong>{totalQ}</strong></span>
              </div>
              {selected?.code ? (
                <button
                  disabled={startingPractice || totalQ === 0}
                  onClick={startChapterPractice}
                  style={{
                    fontSize: "0.82rem",
                    fontWeight: 500,
                    padding: "6px 20px",
                    height: 34,
                    borderRadius: 999,
                    border: "1.5px solid #7c3aed",
                    background: startingPractice ? "#f3f4f6" : "#f5f3ff",
                    color: startingPractice ? "#9ca3af" : "#7c3aed",
                    cursor: (startingPractice || totalQ === 0) ? "not-allowed" : "pointer",
                    transition: "all 0.15s",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                  onMouseEnter={e => { if (!startingPractice && totalQ > 0) { e.target.style.background = "#7c3aed"; e.target.style.color = "#fff"; e.target.style.boxShadow = "0 2px 8px rgba(124,58,237,0.3)"; }}}
                  onMouseLeave={e => { e.target.style.background = "#f5f3ff"; e.target.style.color = "#7c3aed"; e.target.style.boxShadow = "none"; }}
                >
                  ▶ {startingPractice ? "创建中..." : "开始练习"}
                </button>
              ) : totalQ > 0 ? (
                <span style={{fontSize:"0.78rem",color:"#9ca3af",whiteSpace:"nowrap"}}>选择二级知识点开始练习</span>
              ) : null}
            </div>
            <div className="exam-practice-list" style={{maxHeight:"calc(100vh - 280px)",overflowY:"auto"}}>
              {(kpQuestions.items||[]).map((q,i) => (
                <article key={q.id||i} className="exam-practice-question-item">
                  <div className="past-paper-question-meta">
                    <span className="past-paper-q-number">第 {i+1} 题</span>
                    <span className="past-paper-q-type">{q.question_type==="choice"?"选择题":"大题"}</span>
                    <span className="past-paper-q-year">{q.knowledge_point_name||""}</span>
                    {doneIds.has(q.id) && <span style={{fontSize:"0.7rem",background:"#d1fae5",color:"#065f46",padding:"1px 8px",borderRadius:10,fontWeight:600}}>已练习</span>}
                    {!doneIds.has(q.id) && <span style={{fontSize:"0.7rem",background:"#f3f4f6",color:"#9ca3af",padding:"1px 8px",borderRadius:10,fontWeight:500}}>未练习</span>}
                  </div>
                  <div className="past-paper-q-content">{q.stem}</div>
                  {q.options && Object.keys(q.options||{}).length>0 && (
                    <div className="ai-question-options">
                      {Object.entries(q.options).map(([k,v])=><div key={k}><strong>{k}.</strong> {v}</div>)}
                    </div>
                  )}
                </article>
              ))}
            </div>
           </>) : (
            <div className="exam-practice-empty-state"><strong>当前范围暂未录入练习题</strong></div>
           )) : null}
        </section>
      </div>
    </div>
  );
}


function parseItemOptions(item) {
  if (item.options_json) { try { return JSON.parse(item.options_json); } catch {} }
  if (item.options) {
    if (typeof item.options === 'string') {
      try { return JSON.parse(item.options); } catch { return {}; }
    }
    if (typeof item.options === 'object' && !Array.isArray(item.options)) return item.options;
    return {};
  }
  return {};
}
function AnalysisBlock({ itemKey, analysisMap }) {
  const ad = analysisMap[itemKey] || {};
  if (ad.text) return <div className="past-paper-q-feedback"><strong>AI 解析</strong><p>{ad.text}</p></div>;
  if (ad.error) return <div className="km-inline-message km-inline-message--error">{ad.error}</div>;
  return null;
}
function QuestionOptions({ item }) {
  const opts = parseItemOptions(item);
  if (Object.keys(opts).length === 0) return null;
  return <div className="ai-question-options">{Object.entries(opts).map(([k, v]) => <div key={k}><strong>{k}.</strong> {v}</div>)}</div>;
}

function WrongPracticePage({ subjectKey, subjectInfo, user, onBack }) {
  const [items, setItems] = useState([]);
  const [sourceFilters, setSourceFilters] = useState(new Set());
  const [masteredFilter, setMasteredFilter] = useState(""); // "" all, "1" mastered, "0" not
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analysisMap, setAnalysisMap] = useState({});

  const loadItems = () => {
    if (!user?.username) { setError("请先登录后查看错题练习。"); setLoading(false); return; }
    const params = new URLSearchParams({ username: user.username });
    if (sourceFilters.size > 0) params.set("source", [...sourceFilters].join(","));
    if (masteredFilter) params.set("mastered", masteredFilter);
    setLoading(true);
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions?${params.toString()}`)
      .then((payload) => { setItems(payload.items || []); setError(""); })
      .catch((err) => setError(err.message || "错题加载失败"))
      .finally(() => setLoading(false));
  };

  useEffect(loadItems, [subjectKey, user?.username, sourceFilters, masteredFilter]);

  const toggleSource = (val) => {
    setSourceFilters(prev => { const next = new Set(prev); if (next.has(val)) next.delete(val); else next.add(val); return next; });
  };

  const removeWrong = async (item) => {
    if (!window.confirm("确认移出错题本？\n\n移出后该题不会再出现在错题本中，但做题记录仍保留。")) return;
    try {
      await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions/${item.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
      loadItems();
    } catch(e) { alert("移出失败：" + (e.message||"未知错误")); }
  };

  const toggleMastered = async (item) => {
    const newVal = !item.mastered;
    try {
      const r = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions/${item.id}/mastered`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, mastered: newVal }),
      });
      if (r.success) loadItems();
    } catch(e) { alert("操作失败：" + (e.message||"未知错误")); }
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="错题练习" subtitle="系统批改后自动收集当前用户的错题" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-filter-row" style={{flexWrap:"wrap",gap:6,marginBottom:4}}>
        <span style={{fontSize:"0.78rem",color:"#6b7280",marginRight:4}}>来源：</span>
        {[["past_paper","真题错题"],["chapter","章节练习错题"],["ai_generated","AI 出题错题"]].map(([v,l])=>(
          <button key={v} className={`past-paper-chip${sourceFilters.has(v)?" past-paper-chip--active":""}`} onClick={()=>toggleSource(v)}>{l}</button>
        ))}
        <span style={{fontSize:"0.78rem",color:"#6b7280",margin:"0 4px 0 12px"}}>状态：</span>
        {[["1","已掌握"],["0","未掌握"]].map(([v,l])=>(
          <button key={v} className={`past-paper-chip${masteredFilter===v?" past-paper-chip--active":""}`} onClick={()=>setMasteredFilter(masteredFilter===v?"":v)}>{l}</button>
        ))}
        <span style={{fontSize:"0.78rem",color:"#9ca3af",marginLeft:8}}>共 {items.length} 题</span>
      </div>
      {loading ? <div className="past-paper-loading">正在加载错题...</div> : error ? (
        <div className="km-inline-message km-inline-message--error">{error}</div>
      ) : items.length === 0 ? (
        <div className="exam-practice-empty-state"><strong>暂无错题，继续练习后这里会自动收集。</strong></div>
      ) : (
        <div className="exam-practice-list">
          {items.map((item) => (
            <article key={`${item.source||"w"}-${item.id}`} className="exam-practice-question-item">
              <div className="past-paper-question-meta">
                <span className="past-paper-q-type">{item.source_label || SOURCE_LABELS[item.source] || item.source}</span>
                {item.year && <span className="past-paper-q-year">{item.year} 年 第 {item.question_number||item.number} 题</span>}
                {item.knowledge_point_name && <span className="past-paper-q-year">{item.knowledge_point_name}</span>}
                <span className="past-paper-q-number">{item.question_type}</span>
                {item.mastered && <span className="past-paper-q-result-tag past-paper-q-result-tag--correct">已掌握</span>}
              </div>
              <div className="past-paper-q-content">{item.stem||"题干暂缺"}</div>
              <QuestionOptions item={item} />
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">你的答案：</span><span className="text-wrong">{item.user_answer||"未作答"}</span></div>
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{item.standard_answer||"暂无"}</span></div>
              <AnalysisBlock itemKey={`${item.source}-${item.id}`} analysisMap={analysisMap} />
              <div className="exam-practice-action-row">
                <button className="ghost-button compact" disabled={!!(analysisMap[`${item.source}-${item.id}`]||{}).loading} onClick={async()=>{const ak=`${item.source}-${item.id}`;setAnalysisMap(p=>({...p,[ak]:{loading:true,text:"",error:""}}));try{let o={};if(item.options_json)try{o=JSON.parse(item.options_json)}catch{}else if(item.options)o=item.options;const d=await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/question-analysis`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source,question_type:item.question_type,stem:item.stem,options:o,standard_answer:item.standard_answer,user_answer:item.user_answer,context:"错题复盘"})});setAnalysisMap(p=>({...p,[ak]:{loading:false,text:d.analysis,error:""}}))}catch(e){setAnalysisMap(p=>({...p,[ak]:{loading:false,text:"",error:e.message}}))}}}>{(analysisMap[`${item.source}-${item.id}`]||{}).loading?"AI 解析中...":"AI 解析"}</button>
                <button className="ghost-button compact" onClick={()=>removeWrong(item)}>移出错题本</button>
                <button className="wrong-mastered-btn" onClick={()=>toggleMastered(item)}>{item.mastered?"取消已掌握":"标记已掌握"}</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function FavoritePracticePage({ subjectKey, subjectInfo, user, onBack }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analysisMap, setFavAnalysis] = useState({});

  const loadItems = () => {
    if (!user?.username) { setError("请先登录后查看收藏练习。"); setLoading(false); return; }
    const params = new URLSearchParams({ username: user.username });
    setLoading(true);
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/favorites?${params.toString()}`)
      .then(p => { setItems(p.items||[]); setError(""); })
      .catch(e => setError(e.message||"收藏加载失败")).finally(()=>setLoading(false));
  };
  useEffect(loadItems, [subjectKey, user?.username]);
  useEffect(() => () => setFavAnalysis({}), [subjectKey]);

  const removeFavorite = async (item) => {
    await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/favorites/${item.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    loadItems();
  };
  const requestFavAnalysis = async (item) => {
    const ak = `fav-${item.id}`;
    setFavAnalysis(p => ({...p, [ak]: {loading:true,text:"",error:""}}));
    try {
      let o = {}; if(item.options_json) try{o=JSON.parse(item.options_json)}catch{} else if(item.options) o=item.options;
      const d = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/question-analysis`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source:item.source||"favorite",question_type:item.question_type,stem:item.stem,options:o,standard_answer:item.standard_answer,user_answer:item.user_answer,context:"收藏复盘"})});
      setFavAnalysis(p => ({...p, [ak]: {loading:false, text:d.analysis, error:""}}));
    } catch(e) { setFavAnalysis(p => ({...p, [ak]: {loading:false, text:"", error:e.message}})); }
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="收藏练习" subtitle="查看并练习当前用户收藏的题目" subjectInfo={subjectInfo} onBack={onBack} />
      {loading ? <div className="past-paper-loading">正在加载收藏题...</div> : error ? (
        <div className="km-inline-message km-inline-message--error">{error}</div>
      ) : items.length === 0 ? (
        <div className="exam-practice-empty-state">
          <strong>暂无收藏题目</strong>
          <p>在真题答题页点击"☆ 收藏"后，会出现在这里。</p>
        </div>
      ) : (
        <div className="exam-practice-list">
          {items.map((item) => (
            <article key={item.id} className="exam-practice-question-item">
              <div className="past-paper-question-meta"><span className="past-paper-q-type">{SOURCE_LABELS[item.source]||item.source}</span>{item.year&&<span className="past-paper-q-year">{item.year} 年 第 {item.number} 题</span>}<span className="past-paper-q-number">{item.question_type}</span></div>
              <div className="past-paper-q-content">{item.stem||"题干暂缺"}</div>
              {(()=>{let o={};if(item.options_json)try{o=JSON.parse(item.options_json)}catch{}else if(item.options)o=item.options;return Object.keys(o).length>0?<div className="ai-question-options">{Object.entries(o).map(([k,v])=><div key={k}><strong>{k}.</strong> {v}</div>)}</div>:null})()}
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{item.standard_answer||"暂无"}</span></div>
              {(()=>{const ak=`fav-${item.id}`;const ad=analysisMap[ak]||{};return(<>{ad.text&&<div className="past-paper-q-feedback"><strong>AI 解析</strong><p>{ad.text}</p></div>}{ad.error&&<div className="km-inline-message km-inline-message--error">{ad.error}</div>}</>);})()}
              <div className="exam-practice-action-row">
                <button className="ghost-button compact" disabled={(analysisMap[`fav-${item.id}`]||{}).loading} onClick={()=>requestFavAnalysis(item)}>{(analysisMap[`fav-${item.id}`]||{}).loading?"AI 正在解析...":"AI 解析"}</button>
                <button className="fav-remove-btn" onClick={()=>removeFavorite(item)}>取消收藏</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function AIQuestionPracticePage({ subjectInfo, user, onBack }) {
  const [mapData, setMapData] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);
  const [questionType, setQuestionType] = useState("choice");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [requirement, setRequirement] = useState("");
  const [aiQuestions, setAiQuestions] = useState([]);
  const [aiGroups, setAiGroups] = useState([]);
  const [aiGroupTotal, setAiGroupTotal] = useState(0);
  const [aiLoading, setAiLoading] = useState(true);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [aiError, setAiError] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState(null);
  const [editDraft, setEditDraft] = useState({ stem: "", standard_answer: "", analysis: "" });
  const [aiManageGroupKey, setAiManageGroupKey] = useState(null);  // null = groups view, string = manage view

  useEffect(() => {
    const params = new URLSearchParams({ course_id: subjectInfo.courseId });
    if (user?.username) params.set("username", user.username);
    safeJsonFetch(`${API_BASE}/knowledge-map?${params.toString()}`)
      .then((payload) => setMapData(payload))
      .catch(() => setMapData({ chapters: [] }));
  }, [subjectInfo.courseId, user?.username]);

  const loadAiQuestions = () => {
    if (!user?.username) { setAiQuestions([]); setAiGroups([]); setAiLoading(false); return; }
    setAiLoading(true);
    const params = new URLSearchParams({ username: user.username });
    const key = subjectInfo.key || "data_structure";
    Promise.all([
      safeJsonFetch(`${API_BASE}/exam/11408/${key}/ai-questions?${params.toString()}`).catch(() => ({ items: [] })),
      safeJsonFetch(`${API_BASE}/exam/11408/${key}/ai-questions/groups?${params.toString()}`).catch(() => ({ groups: [], total_questions: 0 })),
    ]).then(([allQ, groupsQ]) => {
      setAiQuestions(allQ.items || []);
      setAiGroups(groupsQ.groups || []);
      setAiGroupTotal(groupsQ.total_questions || 0);
      setAiError("");
    }).catch((err) => setAiError(`加载 AI 题库失败：${err.message || "服务器错误"}`))
      .finally(() => setAiLoading(false));
  };

  useEffect(() => {
    loadAiQuestions();
  }, [subjectInfo.key, user?.username]);

  const parsedCount = Number(count);
  const countInvalid = !Number.isInteger(parsedCount) || parsedCount < 1 || parsedCount > 10;

  const handleGenerateAIQuestions = async () => {
    setAiError("");
    setAiMessage("");
    if (!user?.username) {
      setAiError("生成失败：请先登录。");
      return;
    }
    if (countInvalid) {
      setAiError("生成失败：题目数量必须是 1-10 的整数。");
      return;
    }
    setAiGenerating(true);
    try {
      const payload = {
        username: user.username,
        knowledge_point_id: selectedPoint?.node?.code || selectedPoint?.node?.id || "",
        knowledge_point_name: selectedPoint?.node?.title || selectedPoint?.node?.name || "",
        knowledge_point_path: selectedPoint?.path || "",
        question_type: questionType === "big" ? "大题" : "选择题",
        count: parsedCount,
        difficulty,
        requirement,
      };
      const result = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setAiQuestions((prev) => [...(result.items || []), ...prev]);
      const modeText = result.fallback_used ? "mock fallback 题" : "AI 题";
      setAiMessage(`已生成 ${result.items?.length || 0} 道${modeText}。`);
    } catch (err) {
      setAiError(`生成失败：${err.message || "服务器错误"}`);
    } finally {
      setAiGenerating(false);
    }
  };

  const startEditQuestion = (item) => {
    setEditingQuestionId(item.id);
    setEditDraft({
      stem: item.stem || "",
      standard_answer: item.standard_answer || "",
      analysis: item.analysis || "",
    });
  };

  const saveEditQuestion = async (item) => {
    if (!user?.username) {
      setAiError("保存失败：请先登录。");
      return;
    }
    try {
      const result = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, ...editDraft }),
      });
      setAiQuestions((prev) => prev.map((q) => (q.id === item.id ? result.item : q)));
      setEditingQuestionId(null);
      setAiMessage("题目已保存。");
      setAiError("");
    } catch (err) {
      setAiError(`保存失败：${err.message || "服务器错误"}`);
    }
  };

  const deleteAiQuestion = async (item) => {
    if (!user?.username) {
      setAiError("删除失败：请先登录。");
      return;
    }
    try {
      await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/${item.id}?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      setAiQuestions((prev) => prev.filter((q) => q.id !== item.id));
      setAiMessage("题目已删除。");
      setAiError("");
    } catch (err) {
      setAiError(`删除失败：${err.message || "服务器错误"}`);
    }
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="AI 出题" subtitle="根据当前科目知识点，生成贴合 11408 真题风格的练习题" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-split exam-practice-split--ai">
        <section className="exam-practice-panel">
          <h3>出题表单</h3>
          <div className="form-field">
            <span>知识点范围</span>
            <KnowledgePointSelector
              nodes={mapData?.chapters || []}
              selectedPoint={selectedPoint}
              onSelect={setSelectedPoint}
              onClear={() => setSelectedPoint(null)}
            />
          </div>
          <label className="form-field">
            <span>题型</span>
            <select className="field" value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
              <option value="choice">选择题</option>
              <option value="big">大题</option>
            </select>
          </label>
          <label className="form-field">
            <span>题目数量</span>
            <input className="field" type="number" min="1" max="10" value={count} onChange={(event) => setCount(event.target.value)} />
          </label>
          {countInvalid && <div className="km-inline-message km-inline-message--error">题目数量必须是 1-10 的整数。</div>}
          <label className="form-field">
            <span>难度</span>
            <select className="field" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
              <option value="basic">基础</option>
              <option value="medium">中等</option>
              <option value="advanced">提高</option>
            </select>
          </label>
          <label className="form-field">
            <span>生成要求</span>
            <textarea className="field" rows={4} placeholder="例如：贴近 11408 真题，考查核心概念，不要偏题" value={requirement} onChange={(event) => setRequirement(event.target.value)} />
          </label>
          {aiError && <div className="km-inline-message km-inline-message--error">{aiError}</div>}
          {aiMessage && <div className="km-inline-message">{aiMessage}</div>}
          <button type="button" className="ai-generate-submit-btn" disabled={aiGenerating || countInvalid} onClick={handleGenerateAIQuestions}>
            {aiGenerating ? "生成中..." : "生成题目"}
          </button>
        </section>
        <section className="exam-practice-panel">
          <div className="exam-practice-panel-title"><h3>AI 题库</h3></div>
          {aiLoading ? (
            <div className="past-paper-loading">正在加载 AI 题库...</div>
          ) : aiManageGroupKey ? (
            /* ── Management view for one knowledge-point group ── */
            <div className="ai-group-manage">
              <button className="ghost-button compact" onClick={() => setAiManageGroupKey(null)}>← 返回分组</button>
              <div className="ai-question-bank-list" style={{ marginTop: 8 }}>
                {aiQuestions.filter(q => {
                  const kp = (q.knowledge_point_id || "").trim();
                  if (aiManageGroupKey === "_general") return !kp;
                  return kp === aiManageGroupKey;
                }).map(item => {
                  const editing = editingQuestionId === item.id;
                  return (<article key={item.id} className="ai-question-bank-item">
                    <div className="past-paper-question-meta"><span className="past-paper-q-type">{item.question_type}</span><span className="past-paper-q-number">{item.difficulty || "中等"}</span>{item.knowledge_point_path && <span className="past-paper-q-year">{item.knowledge_point_path}</span>}{item.generation_mode && <span className="past-paper-q-year" style={{ background: item.generation_mode==="deepseek"?"#dcfce7":"#fef3c7" }}>{item.generation_mode==="deepseek"?"DeepSeek":"Mock"}</span>}</div>
                    {editing ? (<div className="ai-question-edit-form"><textarea className="field" rows={4} value={editDraft.stem} onChange={e=>setEditDraft(p=>({...p,stem:e.target.value}))}/><input className="field" value={editDraft.standard_answer} onChange={e=>setEditDraft(p=>({...p,standard_answer:e.target.value}))}/><textarea className="field" rows={3} value={editDraft.analysis} onChange={e=>setEditDraft(p=>({...p,analysis:e.target.value}))}/></div>)
                    : (<><div className="past-paper-q-content">{item.stem}</div>{item.options&&Object.keys(item.options).length>0&&<div className="ai-question-options">{Object.entries(item.options).map(([k,v])=><div key={k}><strong>{k}.</strong> {v}</div>)}</div>}<div className="past-paper-q-answer-row"><span className="past-paper-q-label">答案：</span><span>{item.standard_answer}</span></div>{item.analysis&&<div className="past-paper-q-feedback"><p>{item.analysis}</p></div>}</>)}
                    <div className="past-paper-q-answer-row" style={{marginTop:4}}><span className="past-paper-q-label">质量：</span><span>{item.quality_status||"unchecked"}</span></div>
                    {item.has_raw_response && <button className="ghost-button compact" style={{marginTop:4}} onClick={async()=>{try{const d=await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/ai-questions/${item.id}/raw-response?username=${user.username}`); alert("Prompt:\n"+(d.generation_prompt||"").slice(0,2000)+"\n\nRaw:\n"+(d.raw_ai_response||"").slice(0,2000));}catch(e){alert("查看失败")}}}>查看原始AI响应</button>}
                    <div className="exam-practice-action-row">{editing?(<><button className="primary-button compact" onClick={()=>saveEditQuestion(item)}>保存</button><button className="ghost-button compact" onClick={()=>setEditingQuestionId(null)}>取消</button></>):(<><button className="ghost-button compact" onClick={()=>startEditQuestion(item)}>编辑</button><button className="ghost-button compact" onClick={()=>deleteAiQuestion(item)}>删除</button>{item.quality_status&&<select className="field" style={{width:100}} value={item.quality_status||"unchecked"} onChange={async(e)=>{const v=e.target.value; try{const r=await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/ai-questions/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:user.username,quality_status:v})}); setAiQuestions(p=>p.map(q=>q.id===item.id?r.item:q));}catch(err){setAiError(err.message)}}}><option value="unchecked">未检查</option><option value="usable">可用</option><option value="needs_edit">需修改</option><option value="discarded">废弃</option></select>}</>)}</div>
                  </article>);
                })}
              </div>
            </div>
          ) : aiGroups.length === 0 ? (
            <div className="exam-practice-empty-state"><strong>暂无 AI 生成题目</strong><p>点击左侧"生成题目"后，AI 题会保存到当前用户的私有列表。共 {aiGroupTotal} 题。</p></div>
          ) : (
            /* ── Grouped view ── */
            <div className="ai-group-list">
              {aiGroups.map(g => (
                <div key={g.group_key} className="ai-group-card">
                  <div className="ai-group-header">
                    <strong>{g.knowledge_point_path || "综合出题"}</strong>
                    <span>{g.total} 题</span>
                  </div>
                  <div className="ai-group-stats">
                    <span>选择题 {g.choice_count}</span>
                    <span>大题 {g.big_count}</span>
                    <span style={{color:"#16a34a"}}>DeepSeek {g.deepseek_count}</span>
                    <span style={{color:"#d97706"}}>Mock {g.mock_count}</span>
                  </div>
                  <div className="ai-group-quality">
                    <span>可用 {g.quality_summary?.usable||0}</span>
                    <span>需修改 {g.quality_summary?.needs_edit||0}</span>
                    <span>未检查 {g.quality_summary?.unchecked||0}</span>
                    {g.quality_summary?.discarded>0&&<span>废弃 {g.quality_summary.discarded}</span>}
                  </div>
                  <div className="exam-practice-action-row">
                    <button className="primary-button compact" onClick={async()=>{
                      const qids=aiQuestions.filter(q=>{const kp=(q.knowledge_point_id||"").trim();return g.group_key==="_general"?!kp:kp===g.group_key;}).filter(q=>q.quality_status!=="discarded").map(q=>q.id);
                      if(qids.length===0){setAiError("该分组无可练习题目");return}
                      try{const r=await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key}/ai-questions/attempts`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:user.username,knowledge_point_id:g.knowledge_point_id,knowledge_point_path:g.knowledge_point_path,question_ids:qids})});
                      window.open(`/exam/11408/${subjectInfo.key}/ai-questions/attempt/${r.attempt_id}`,"_blank");}catch(err){setAiError(err.message)}
                    }} className="ai-group-start-btn">开始练习</button>
                    <button className="ghost-button compact" onClick={()=>setAiManageGroupKey(g.group_key)}>管理题目</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function ExamPracticeCenter({
  subjectKey = "data_structure",
  subjectName = "11408 数据结构",
  user,
}) {
  const subjectInfo = EXAM_SUBJECTS[subjectKey] || EXAM_SUBJECTS.data_structure;
  const [practiceView, setPracticeView] = useState("dashboard");
  const [pastPaperConfig, setPastPaperConfig] = useState(null);
  const [pastPapers, setPastPapers] = useState(null);
  const [practiceStats, setPracticeStats] = useState({
    total_practices: 0,
    completed_practices: 0,
    accuracy: 0,
    total_duration_minutes: 0,
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => setPastPapers(data))
      .catch(() => setPastPapers({ available: false, resource_files: [] }));
  }, [subjectKey]);

  useEffect(() => {
    if (!user?.username) {
      setPracticeStats({ total_practices: 0, completed_practices: 0, accuracy: 0, total_duration_minutes: 0 });
      setStatsLoading(false);
      setStatsError("登录后显示个人练习数据。");
      return;
    }
    setStatsLoading(true);
    setStatsError("");
    const params = new URLSearchParams({ username: user.username });
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/practice/stats?${params.toString()}`)
      .then((payload) => setPracticeStats(payload))
      .catch((err) => {
        setPracticeStats({ total_practices: 0, completed_practices: 0, accuracy: 0, total_duration_minutes: 0 });
        setStatsError(`练习数据加载失败：${err.message || "服务器错误"}`);
      })
      .finally(() => setStatsLoading(false));
  }, [subjectKey, user?.username]);

  const availableYears = [];
  if (pastPapers?.resource_files) {
    for (const f of pastPapers.resource_files) {
      for (const y of f.years || []) {
        if (!availableYears.includes(y)) availableYears.push(y);
      }
    }
    availableYears.sort((a, b) => b - a);
  }

  if (practiceView === "pastPaper" && pastPaperConfig) {
    return (
      <ExamPastPaperPractice
        subjectKey={pastPaperConfig.subjectKey}
        subjectName={pastPaperConfig.subjectName}
        years={pastPaperConfig.years}
        questionType={pastPaperConfig.questionType}
        user={user}
        onBack={() => setPracticeView("dashboard")}
      />
    );
  }

  if (practiceView === "chapter") {
    return <ChapterPracticePage subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "wrong") {
    return <WrongPracticePage subjectKey={subjectKey} subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "favorite") {
    return <FavoritePracticePage subjectKey={subjectKey} subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "ai") {
    return <AIQuestionPracticePage subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }

  const cards = [
    { key: "chapter", icon: "📋", title: "章节练习", desc: "按章节知识点进行针对性练习", count: "题目待录入" },
    { key: "wrong", icon: "❌", title: "错题练习", desc: "查看批改后自动收集的个人错题", count: "个人错题本" },
    { key: "favorite", icon: "⭐", title: "收藏练习", desc: "练习自己收藏的题目", count: "个人收藏" },
    { key: "pastPaper", icon: "📜", title: "真题练习", desc: "基于历年 11408 真题进行专项训练", count: "近五年真题", className: "practice-type-card--past" },
    { key: "ai", icon: "🤖", title: "AI 出题", desc: "按知识点生成 11408 风格练习题", count: "自定义生成", className: "practice-type-card--ai" },
  ];

  const openCard = (key) => {
    if (key === "pastPaper") {
      setPastPaperConfig({ subjectKey, subjectName, years: availableYears, questionType: "all" });
      setPracticeView("pastPaper");
      return;
    }
    setPracticeView(key);
  };

  return (
    <div className="exam-practice-dashboard">
      <div className="practice-dashboard-header">
        <div>
          <h2>练习中心</h2>
          <p>巩固知识，提升能力</p>
        </div>
      </div>

      <div className="practice-stats-section">
        <h3>练习数据</h3>
        {statsError && <div className="practice-stats-note">{statsError}</div>}
        <div className="practice-stats-grid">
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : practiceStats.total_practices || 0}</div><div className="practice-stat-card-label">总练习数</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : practiceStats.completed_practices || 0}</div><div className="practice-stat-card-label">已完成</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : `${practiceStats.accuracy || 0}%`}</div><div className="practice-stat-card-label">正确率</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">⏱</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : formatPracticeDuration(practiceStats.total_duration_minutes || 0)}</div><div className="practice-stat-card-label">累计练习时长</div></div></div>
        </div>
      </div>

      <div className="practice-type-section">
        <h3>练习类型</h3>
        <div className="practice-type-grid">
          {cards.map((card) => (
            <button key={card.key} type="button" className={`practice-type-card ${card.className || ""}`} onClick={() => openCard(card.key)}>
              <div className="practice-type-icon">{card.icon}</div>
              <div className="practice-type-info">
                <strong>{card.title}</strong>
                <p>{card.desc}</p>
                <span className="practice-type-count">{card.count}</span>
              </div>
              <span className="practice-type-arrow">›</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
