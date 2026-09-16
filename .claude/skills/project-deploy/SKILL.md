---
name: project-deploy
description: 用于当前项目的代码修改、验证、提交、合并、推送和线上自动部署流程。当用户要求修复 bug、开发功能、提交代码、部署到服务器或更新线上版本时使用。
---

# Project Deploy Skill

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本 Skill 从属于 SSOT；冲突时 SSOT wins。
> 若 SSOT 冻结了 Git 操作（当前 Git 状态 = DIVERGED），则本 Skill 的 push 流程**暂停适用**，
> 以 SSOT §68.1 与 `CLAUDE.md` 的 Git 工作流程为准。
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

## 工作原则

1. 修改代码前，先检查项目结构和相关文件。
2. 每次修改代码后，必须明确说明修改了哪些文件。
3. 优先在本地完成验证：
   - 后端 Python 项目优先运行 `python -m py_compile`
   - 前端项目优先运行 `npm run build`
   - 如果项目已有测试命令，优先运行测试
4. 验证通过后，执行：
   - `git status`
   - `git add`
   - `git commit`
   - `git push origin main`
5. 默认通过 push main 触发 GitHub Actions / 腾讯云自动部署。
6. 不要优先建议直接 SSH 到云服务器手改线上代码。
7. 只有当自动部署失败或线上服务异常时，才进入服务器排查流程。
8. 最终汇报必须包含：
   - 修改文件
   - 验证命令和结果
   - commit hash
   - 是否已 push 到 main
   - 是否触发自动部署
   - 后续需要用户手动验证的页面或接口

## 禁止事项

- 不要只修改本地代码后停止。
- 不要只创建功能分支后停止。
- 不要绕过 GitHub Actions 直接改线上代码，除非自动部署失败。
- 不要在未验证的情况下声称功能已修复。
