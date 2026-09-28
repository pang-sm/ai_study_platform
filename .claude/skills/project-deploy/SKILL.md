---
name: project-deploy
description: 用于当前项目的代码修改、验证、提交、合并、推送和线上自动部署流程。当用户要求修复 bug、开发功能、提交代码、部署到服务器或更新线上版本时使用。
---

# Project Deploy Skill

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本 Skill 从属于 SSOT；冲突时 SSOT wins。
> **Git 冻结已解除（2026-09-28 现场核实）**：历史 `DIVERGED` 分叉早已 reconcile，
> `git rev-list --left-right --count origin/main...HEAD` 当前为 `0 0`，SSOT 也不再冻结 Git 操作。
> 本 Skill 的 push 流程**正常适用**。开工前仍须现场执行
> `git status --short --branch` / `git log --oneline -5` / 上面的 left-right count 核对，不要凭记忆断言。
>
> 环境注意（已只读验证）：本项目后端必须使用项目 venv
> （`backend/.venv/Scripts/python.exe`，Python 3.13）。
> 系统 `python` 是 3.11 且未安装 FastAPI，直接运行 `python -m pytest` 会失败。

## 适用场景

当用户要求你完成以下任务时，必须使用本 Skill：

- 修改当前项目代码
- 修复 bug
- 新增功能
- 前后端联调
- 提交 git commit
- 推送 main 分支
- 触发 GitHub Actions / 腾讯云自动部署
- 排查线上部署问题

## 工作原则（默认 = 改完即部署）

**默认**：除非用户明确说「只改本地不要部署」，否则一律走完整链路，**不得在本地通过就停止**。

```text
修改代码 → 运行相关测试 → 检查 git diff / git status
→ 只提交本轮明确修改的文件 → commit（中文说明）
→ push origin main → 等待 GitHub Actions 部署成功
→ 公网 URL smoke test / 功能验收 → 确认线上 SHA == 本地 HEAD → 汇报
```

1. 修改代码前，先检查项目结构和相关文件；开工前先现场检查 git 状态（branch / HEAD / staged / unstaged / untracked）。
2. 每次修改代码后，必须明确说明修改了哪些文件。
3. 优先在本地完成验证：
   - 后端 Python 项目优先运行 `python -m py_compile`
   - 前端项目优先运行 `npm run build`
   - 如果项目已有测试命令，优先运行测试
4. 验证通过后，执行：
   - `git status`
   - `git add <显式路径>`（**禁止 `git add .` / `git add -A`**，工作树里有大量未跟踪 scratch）
   - `git commit`（中文说明；**commit message 内不要出现反引号 / `$()`**，否则部署工作流会在到达服务器前失败）
   - `git push origin main`
5. 默认通过 push main 触发 GitHub Actions / 腾讯云自动部署。
6. **确认部署结果**：`gh run list --workflow=deploy.yml --limit 1` 取 run id →
   `gh run watch <id>` 或 `gh run view <id> --json conclusion`；失败则排查修复，**不得报告为完成**。
7. **确认线上 SHA**（生产无版本端点）：`gh run view <id> --log | grep "HEAD is now at"`，
   并与本地 `HEAD` 比对。另用 `curl -k https://101.32.190.42/api/health` 做存活探针。
8. **公网 smoke test**：必须在真实公网 URL 上验证功能，而不是 localhost。纯文档变更可填 `N/A`。
9. 不要优先建议直接 SSH 到云服务器手改线上代码。
10. 只有当自动部署失败或线上服务异常时，才进入服务器排查流程。

## 最终汇报格式（每轮必须给出，不得省略字段）

```text
CHANGE = PASS / FAIL
TESTS = ...
COMMIT = <sha>
DEPLOYMENT = PASS / FAIL
PRODUCTION_URL = ...
PRODUCTION_SHA = <sha>
PUBLIC_SMOKE_TEST = PASS / FAIL
ONLINE_ACCEPTANCE_READY = YES / NO
```

补充说明：修改文件、验证命令与结果、是否需要数据库迁移、遗留风险。

## 禁止事项

- 不要只修改本地代码后停止。
- 不要只创建功能分支后停止。
- 不要只跑 localhost:5173 / localhost:8000 就当作完成。
- 不要只 commit 不 push，或 push 后不确认部署结果。
- 不要部署成功却不检查公网页面，也不要在未确认线上 SHA 的情况下声称完成。
- 不要绕过 GitHub Actions 直接改线上代码，除非自动部署失败。
- 不要在未验证的情况下声称功能已修复。
- **部署失败不要把任务报告成完成**；必须排查修复，或明确报告具体阻塞原因。
