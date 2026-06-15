import { useEffect, useState } from "react";
import ExamPastPaperPractice from "./ExamPastPaperPractice.jsx";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: { label: "数据结构", shortLabel: "数据结构" },
  computer_organization: { label: "计算机组成原理", shortLabel: "计组" },
  operating_system: { label: "操作系统", shortLabel: "操作系统" },
  computer_network: { label: "计算机网络", shortLabel: "计网" },
};

const SUBJECT_RECENT_RECORDS = {
  data_structure: [
    { title: "线性表章节练习", type: "章节练习", accuracy: "80%", time: "2024-05-20 15:30" },
    { title: "栈和队列章节练习", type: "章节练习", accuracy: "72%", time: "2024-05-19 10:15" },
    { title: "树与二叉树章节练习", type: "章节练习", accuracy: "68%", time: "2024-05-18 09:00" },
    { title: "图章节练习", type: "章节练习", accuracy: "75%", time: "2024-05-17 16:45" },
    { title: "查找与排序章节练习", type: "章节练习", accuracy: "82%", time: "2024-05-16 14:20" },
  ],
  computer_organization: [
    { title: "数据的表示和运算", type: "章节练习", accuracy: "76%", time: "2024-05-20 15:30" },
    { title: "指令系统章节练习", type: "章节练习", accuracy: "70%", time: "2024-05-19 10:15" },
    { title: "CPU 的结构和功能", type: "章节练习", accuracy: "65%", time: "2024-05-18 09:00" },
    { title: "总线与I/O系统", type: "章节练习", accuracy: "78%", time: "2024-05-17 16:45" },
    { title: "计算机运算方法", type: "章节练习", accuracy: "72%", time: "2024-05-16 14:20" },
  ],
  operating_system: [
    { title: "进程管理章节练习", type: "章节练习", accuracy: "80%", time: "2024-05-20 15:30" },
    { title: "内存管理章节练习", type: "章节练习", accuracy: "75%", time: "2024-05-19 10:15" },
    { title: "文件系统章节练习", type: "章节练习", accuracy: "70%", time: "2024-05-18 09:00" },
    { title: "I/O管理章节练习", type: "章节练习", accuracy: "68%", time: "2024-05-17 16:45" },
    { title: "死锁章节练习", type: "章节练习", accuracy: "85%", time: "2024-05-16 14:20" },
  ],
  computer_network: [
    { title: "物理层章节练习", type: "章节练习", accuracy: "78%", time: "2024-05-20 15:30" },
    { title: "数据链路层章节练习", type: "章节练习", accuracy: "72%", time: "2024-05-19 10:15" },
    { title: "网络层章节练习", type: "章节练习", accuracy: "68%", time: "2024-05-18 09:00" },
    { title: "传输层章节练习", type: "章节练习", accuracy: "75%", time: "2024-05-17 16:45" },
    { title: "应用层章节练习", type: "章节练习", accuracy: "70%", time: "2024-05-16 14:20" },
  ],
};

export default function ExamPracticeCenter({
  subjectKey = "data_structure",
  subjectName = "11408 数据结构",
  user,
  courseOptions = [],
  getSubjectLabel = (v) => v,
  normalizeSubject = (v) => v,
  formatDate = (v) => v,
  setPage = () => {},
  practiceContext = null,
  onClearPracticeContext = () => {},
  coursePreference = null,
  searchNavigate = null,
  onClearSearchNavigate = () => {},
  onOpenGenerateModal = null,
  onOpenPastPaperModal = null,
}) {
  const subjectInfo = EXAM_SUBJECTS[subjectKey] || EXAM_SUBJECTS.data_structure;
  const recentRecords = SUBJECT_RECENT_RECORDS[subjectKey] || SUBJECT_RECENT_RECORDS.data_structure;

  const [practiceView, setPracticeView] = useState("dashboard");
  const [pastPaperConfig, setPastPaperConfig] = useState(null);
  const [pastPapers, setPastPapers] = useState(null);
  const [genType, setGenType] = useState("choice");
  const [genCount, setGenCount] = useState(3);

  useEffect(() => {
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => setPastPapers(data))
      .catch(() => setPastPapers({ available: false, resource_files: [] }));
  }, [subjectKey]);

  const availableYears = [];
  if (pastPapers?.resource_files) {
    for (const f of pastPapers.resource_files) {
      for (const y of f.years || []) {
        if (!availableYears.includes(y)) availableYears.push(y);
      }
    }
    availableYears.sort((a, b) => b - a);
  }

  // Render past paper practice view
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

  return (
    <div className="exam-practice-dashboard">
      <div className="practice-dashboard-header">
        <div>
          <h2>练习中心</h2>
          <p>巩固知识，提升能力</p>
        </div>
        <button type="button" className="primary-button ai-generate-btn-main" onClick={onOpenGenerateModal}>
          <span>✨</span> AI 出题
        </button>
      </div>

      <div className="practice-stats-section">
        <h3>练习数据</h3>
        <div className="practice-stats-grid">
          <div className="practice-stat-card--dashboard">
            <div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div>
            <div className="practice-stat-card-body">
              <div className="practice-stat-card-value">128</div>
              <div className="practice-stat-card-label">总练习数</div>
            </div>
          </div>
          <div className="practice-stat-card--dashboard">
            <div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div>
            <div className="practice-stat-card-body">
              <div className="practice-stat-card-value">96</div>
              <div className="practice-stat-card-label">已完成</div>
            </div>
          </div>
          <div className="practice-stat-card--dashboard">
            <div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div>
            <div className="practice-stat-card-body">
              <div className="practice-stat-card-value">75%</div>
              <div className="practice-stat-card-label">正确率</div>
            </div>
          </div>
          <div className="practice-stat-card--dashboard">
            <div className="practice-stat-card-icon practice-stat-card-icon--time">⏱</div>
            <div className="practice-stat-card-body">
              <div className="practice-stat-card-value">32h</div>
              <div className="practice-stat-card-label">累计练习时长</div>
            </div>
          </div>
        </div>
      </div>

      <div className="practice-type-section">
        <h3>练习类型</h3>
        <div className="practice-type-grid">
          <div className="practice-type-card">
            <div className="practice-type-icon">📋</div>
            <div className="practice-type-info">
              <strong>章节练习</strong>
              <p>按章节知识点进行针对性练习</p>
              <span className="practice-type-count">共 86 题</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </div>
          <div className="practice-type-card">
            <div className="practice-type-icon">❌</div>
            <div className="practice-type-info">
              <strong>错题练习</strong>
              <p>针对错题强化练习</p>
              <span className="practice-type-count">共 24 题</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </div>
          <div className="practice-type-card">
            <div className="practice-type-icon">📝</div>
            <div className="practice-type-info">
              <strong>模拟考试</strong>
              <p>模拟真实考试环境</p>
              <span className="practice-type-count">共 12 套</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </div>
          <div className="practice-type-card">
            <div className="practice-type-icon">⭐</div>
            <div className="practice-type-info">
              <strong>收藏练习</strong>
              <p>收藏的题目练习</p>
              <span className="practice-type-count">共 18 题</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </div>
          <button
            type="button"
            className="practice-type-card practice-type-card--past"
            onClick={() => {
              setPastPaperConfig({
                subjectKey,
                subjectName,
                years: availableYears,
                questionType: "all",
              });
              setPracticeView("pastPaper");
            }}
          >
            <div className="practice-type-icon">📜</div>
            <div className="practice-type-info">
              <strong>真题练习</strong>
              <p>基于历年 11408 真题进行专项训练</p>
              <span className="practice-type-count">近五年真题</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </button>
          <button
            type="button"
            className="practice-type-card practice-type-card--ai"
            onClick={onOpenGenerateModal}
          >
            <div className="practice-type-icon">🤖</div>
            <div className="practice-type-info">
              <strong>AI 出题</strong>
              <p>根据当前科目知识脉络，严格参考 11408 真题生成练习题</p>
              <span className="practice-type-count">自定义生成</span>
            </div>
            <span className="practice-type-arrow">›</span>
          </button>
        </div>
      </div>

      <div className="practice-recent-section">
        <div className="practice-recent-header">
          <h3>最近练习 · {subjectInfo.label}</h3>
          <span className="practice-recent-subject">{subjectInfo.shortLabel}专项记录</span>
        </div>
        <div className="practice-recent-list">
          {recentRecords.map((rec, idx) => (
            <div key={idx} className="practice-recent-item">
              <div>
                <strong>{rec.title}</strong>
                <span className="practice-recent-type">{rec.type}</span>
              </div>
              <div className="practice-recent-meta">
                <span>正确率 {rec.accuracy}</span>
                <span>{rec.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
