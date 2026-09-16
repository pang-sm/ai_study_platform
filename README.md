# 智学AI（ai_study_platform）

> 这是一个进行中的产品重构项目。**开始任何工作前，先读
> [`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`](./ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md)**，
> 它是本项目唯一的产品 / 架构 / 科学语义 / 迁移路线事实来源。
> `CLAUDE.md`（AI 执行契约）、`AGENTS.md`（入口指引）、`docs/**` 全部从属于它。

## 智学AI 是什么

一个统一账户、统一会员、统一 AI 与学习智能底座之上的**多场景个人学习系统**。

三个 **Learning Space**：

```text
course_learning   课程学习
exam_11408        计算机考研 11408
programming       编程学习
```

它们**共享**账户、会员、Usage Credits、资料、知识、练习、错题、复习、计划、学习记录、
AI Layer、Data Plane 与 Scientific Runtime。

**不是**三个网站，**不是**三套会员，**不是**三套 AI。

## 当前阶段

- `STEP 1`–`STEP 6` 已冻结。
- 当前 **`STEP 7`：后端实现 / 重构**（`CURRENT_SUBSTEP = STEP_7C-P`，`NEXT_SUBSTEP = STEP_7D`）。
- 全新前端 = **NOT_STARTED**。`frontend/` 目前只有 Clean-Slate 骨架与首页。
- 详细状态见 SSOT `# 73. SSOT 状态`。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19 + Vite 8 + TypeScript + TanStack Router/Query + Tailwind CSS 4 + Radix |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2（`backend/`） |
| 数据库 | SQLite，迁移走 **Alembic**（`migrations/`） |
| 科学运行时 | 独立进程 `scientific_runtime_service/`，经 localhost HTTP 调用 |

Product Backend **不允许**直接 import `torch` / `transformers` / `faiss` / `zhixue_runtime`。

## 本地启动

前端（`frontend/`，Node ≥ 24）：

```bash
npm run dev
```

访问 `http://127.0.0.1:5173`。

后端（在 `backend/` 下，**必须使用项目 venv** —— 系统 `python` 是 3.11 且没有 FastAPI）：

```bash
./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Linux / macOS 用 `./.venv/bin/python`。

## 验证

前端（`frontend/`）：

```bash
npm run check
```

后端（`backend/`）：

```bash
./.venv/Scripts/python.exe -m pytest
```

## Git 状态（重要）

当前 `main` 与 `origin/main` **已分叉**，工作树含大量未跟踪的 Phase 2–7 代码。
在完成正式 Git reconciliation 之前，**禁止** `reset` / `clean` / `overwrite` / `rebase` /
`merge` / `force push`。详见 `CLAUDE.md` 的 Git 工作流程一节。

## 部署注意事项

如果线上通过 Nginx 代理前端和后端，文件上传功能需要允许 10MB 请求体。
请在对应的 `server` 或 `http` 配置中设置：

```nginx
client_max_body_size 10M;
```

修改 Nginx 配置后需要检查并重载配置，例如：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 图片 OCR 部署要求

图片上传问答使用 Python 依赖 `pillow` 和 `pytesseract`，并依赖服务器系统中的 Tesseract OCR。

Ubuntu 服务器需要安装：

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
```

安装后可用以下命令验证：

```bash
tesseract --version
tesseract --list-langs
```

## 作者

逄森淼
