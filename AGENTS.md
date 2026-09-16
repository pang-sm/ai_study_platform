# AGENTS.md

> **本文件是入口指引（entry-point guidance），不是权威。**
> 唯一产品 / 架构 / 科学语义 / 迁移路线 SSOT 是根目录
> `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。若本文件、`CLAUDE.md`、`.claude/**`、`docs/**`
> 或历史文档与 SSOT 冲突，**SSOT wins**。
> 人类可读的工程说明见 `README.md`；Claude Code 的执行契约见 `CLAUDE.md`。

## Project

智学AI（智学平台）——高校学习者的多场景个人学习系统。

- **前端**：React 19 + Vite 8 + TypeScript（`frontend/`）
- **后端**：FastAPI 单体 + SQLAlchemy 2.0 + Pydantic v2（`backend/`）
- **数据库**：SQLite，正式迁移机制 = Alembic（`migrations/`）
- **科学运行时**：独立进程 `scientific_runtime_service/`，经 localhost HTTP 调用

## 先读什么

开任何新对话或新任务，按此顺序：

1. `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` —— 判断当前 STEP 与任务归属。
   当前权威状态块：`# 73. SSOT 状态`（`CURRENT_STEP = STEP_7`，`CURRENT_SUBSTEP = STEP_7C-P`，`NEXT_SUBSTEP = STEP_7D`）。
2. `CLAUDE.md` —— 执行契约与红线。
3. 与任务相关的次级文档（`docs/**`）与项目 Skill。

## 项目不是三个网站

三个 **Learning Space**（`course_learning` / `exam_11408` / `programming`）共享一个账户、
一套会员、一套 Usage Credits、一套 Learning Core、一套 AI Layer、一套 Data Plane 与
Scientific Runtime。

**禁止**：三个学习空间拆成三个网站；三套会员；三套 AI；三套 usage 余额。

## 当前阶段

- `STEP 1`–`STEP 6` 已冻结。
- `STEP 7`（后端实现 / 重构）进行中：`STEP7A` / `STEP7B` / `STEP7C` / `STEP7C-P` 已 FROZEN。
- 全新前端 = `NOT_STARTED`。不得恢复旧前端 UI，不得从旧 frontend 复制页面。
- 后端原则：`Preserve Capability != Preserve Architecture`。
  `main.py` = `REFACTOR / EXTRACT`（不是 DELETE，也不是 KEEP AS-IS）；禁止 big-bang rewrite。

## Development Rules

1. 动手前先说明**将要修改哪些文件与理由**。
2. 一次只做一件可验证的事；不要顺手做无关重构。
3. **不得修改** `.env`、`.env.local` 或任何 API key / secret 文件；不得读取或输出其内容。
4. Java 后端路线已取消（`JAVA_BACKEND = CANCELLED`）；不再讨论 Java 重写。
5. 纯前端任务不得顺手改 backend；但 STEP 7 的后端重构任务是**被授权且必需**的。
6. 数据库：additive-only；保护 `exam_question_bank` / `programming_exercises` /
   `knowledge_points` / `exam_resources` / `static` / `programming_catalog`；
   不得 `DROP`、rebuild 既有表或删库重建。
7. Product Backend **不得**直接 import `torch` / `transformers` / `faiss` / `zhixue_runtime`。
8. 不得把 `PLANNED` / `TARGET` 能力写成 `CURRENT` 或「已实现」。
9. 不得改写 SSOT 冻结的科学语义（`student_twin` / `learner_state` / `irt` /
   `tutor_policy` / `tutor_guard` / `evidence_reliability` / `misconception_v2` / `memory`）。
10. 发现 SSOT 自身有过期段落时，**报告**，不要自行回写。

## Git 状态（重要）

当前 `main` 与 `origin/main` **已分叉**（AHEAD 15 / BEHIND 12），工作树含大量未跟踪
Phase 2–7 代码。

在完成正式 Git reconciliation 之前：

```text
NO reset
NO clean
NO overwrite
NO rebase
NO merge
NO force push
```

不要「顺手」修这个分叉。

## 如何测试

前端（在 `frontend/`）：

```bash
npm run check
```

后端（在 `backend/`，必须用项目 venv —— 系统 `python` 是 3.11 且没有 FastAPI）：

```bash
./.venv/Scripts/python.exe -m pytest
```

## 完成任务后必须汇报

- 改了哪些文件
- 实现了什么
- 如何测试
- 有无风险（含是否需要数据库迁移）
