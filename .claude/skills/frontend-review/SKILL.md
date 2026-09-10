---
name: frontend-review
description: 页面开发完成后，按统一流程对 frontend 变更做 UI/UX 审核，输出 PASS/FAIL 及逐条问题清单。用于 /frontend-review。
---

# Frontend Review

在 **页面/组件开发完成之后**，对当前 frontend 变更做一次统一流程的 UI/UX 审核。

本 skill 的职责**不是**保存全部 UI 规范（权威规范在 `docs/UI_DESIGN_SPEC.md`），
而是提供一套固定的审核流程，确保每次交付前都做同样的检查。

## 触发时机

- 用户输入 `/frontend-review`
- 用户要求「检查 / 审核 / review 前端 UI」
- 前端页面完成后交付前

## 审核流程

1. 获取当前 frontend diff（`git diff` + `git status`，聚焦 `frontend/**`）。
2. 确认涉及哪些页面和组件。
3. 阅读 `docs/UI_DESIGN_SPEC.md` 中与本次变更相关的章节。
4. 逐条执行 `checklist.md` 中的检查项（重点：Design Tokens、随机值、gradient/glass/glow、Card、emoji、typography、spacing、button、primary action、loading/empty/error、responsive、accessibility）。
5. 检查是否错误修改了 backend（`backend/**`、数据库、API）。
6. 执行现有 frontend lint / typecheck / tests / build（若项目有对应脚本则真实执行，没有则明确标注「无脚本，未执行」，**不得伪造通过**）。
7. 汇总并给出结论。

## 输出格式

- 结论：`PASS` 或 `FAIL`。
- 若 `FAIL`：列出具体文件、问题、修改建议。
- 若当前任务已授权修复：修复后重新验证并给出二次结论。

## 约束

- **不要**随意大规模改动业务逻辑。
- 只对 UI/UX 一致性问题提出修改；涉及业务/接口的改动必须单独确认。
- 审核报告要忠实：脚本失败就写失败原因，跳过就写跳过。
