---
name: zhixue-api-contract
description: 智学平台前后端 API 契约修改与同步流程。涉及 FastAPI 路由、请求/响应 schema、认证、frontend API 类型生成或接口语义调整时必须使用。
---

# ZhiXue API Contract

## Authority

> **唯一最高权威是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。**
> 本 Skill 从属于 SSOT；冲突时 SSOT wins。
> API 的处置分类（KEEP / MOVE / DEPRECATE / DELETE / NEW）以 SSOT §56.3 的冻结矩阵为准：
> `BUSINESS_HTTP_ENDPOINTS = 351`，`KEEP = 259`，`MOVE = 68`，`DEPRECATE = 24`，`DELETE = 0`，
> `NEW_API_COUNT = 10`（MVP 8 + V1 2）。处置 ≠ 已迁移；当前所有 path 仍存在。

## Purpose

用于智学AI 前后端 API 契约修改、同步与验收。

核心原则：

> FastAPI backend is the API contract source of truth（**在 API 契约这一层**）。

前端不得自行发明接口字段，不得手写与后端漂移的 DTO。

## Trigger

出现以下情况时必须使用本 Skill：

- 新增 FastAPI 路由
- 修改已有 API 路径
- 修改 HTTP method
- 修改请求参数
- 修改 request schema
- 修改 response schema
- 修改认证要求
- 修改错误码或错误响应
- 修改分页、过滤、排序参数
- 修改前端 API client
- 需要重新生成前端 API 类型
- 修改 `frontend/src/types/api.ts` 对应后端契约

以下情况通常不需要：

- 纯 UI 样式调整
- 不涉及 API 的前端组件修改
- 不影响接口契约的后端内部重构

## Contract Source of Truth

后端 FastAPI 当前实现是接口契约的事实来源。

必须优先检查：

- `backend/main.py`
- 相关 router / handler
- Pydantic schema
- authentication / authorization logic
- `docs/FRONTEND_API_CONTRACT.md`

不得仅根据前端现状猜测后端接口。

## Generated Frontend Types

`frontend/src/types/api.ts` 属于生成文件。

规则：

- 禁止手工修改以“适配”后端
- 后端契约变化后应重新生成
- 生成命令：

```bash
npm run api:generate
```

如果生成失败，应修复契约或生成流程，而不是手改生成结果。

## Before Modification

修改 API 前必须确认：

```text
当前路由路径。
HTTP method。
当前 request schema。
当前 response schema。
是否需要认证。
当前错误状态。
哪些前端页面或功能依赖该接口。
是否已有兼容性要求。
是否涉及数据库 schema。
是否真的需要修改 backend API 语义。
```

如果当前任务只是前端重构：

```text
默认不修改 backend API 语义。
```

注意：**后端本身在 STEP 7 是被授权重构的**（`main.py` = REFACTOR / EXTRACT）。
但「重构模块边界」不等于「改变 API 语义」——SSOT §56.3 的冻结矩阵中 `DELETE = 0`，
路径可以 MOVE，语义不得随意变更。改变语义仍需走本 Skill 的 BREAKING 流程。

## Backend Change Rules

API 改动必须保持：

```text
路由职责清晰
request / response schema 明确
authentication 不被意外绕过
authorization 不被弱化
错误状态可预测
旧客户端兼容性优先
```

禁止：

```text
为了方便前端临时改变已有接口语义
在返回值里随意增加未经定义的字段
将内部异常直接暴露给前端
在多个业务模块重复实现同一契约
将具体 provider/model 信息泄漏进通用业务 API
```

## Authentication

涉及认证时必须检查：

```text
Session Cookie
ai_session
登录态要求
权限范围
用户资源隔离
```

不得因为前端开发方便而关闭认证或绕过用户隔离。

## Error Contract

修改接口时必须明确：

```text
400：请求参数或业务输入错误
401：未认证
403：无权限
404：资源不存在
409：业务冲突
422：schema validation
5xx：服务端错误
```

不得依赖模糊字符串让前端猜测错误类型。

## Frontend Integration

前端调用 API 时：

```text
统一通过既有 API client
不在组件中散落 fetch 实现
不复制接口 schema
不自行定义与生成类型重复的 DTO
保持 loading / empty / error 状态完整
```

修改后应检查：

```text
request body
query params
path params
headers
credentials / cookie
response parsing
error handling
```

## Contract Documentation

新增或修改 API 后，需要同步检查：

```text
docs/FRONTEND_API_CONTRACT.md
```

若契约文档需要更新，应记录对应变化。

不得让代码与文档长期漂移。

## Verification

Shell 可用时：

后端（在 `backend/`，**必须使用项目 venv** —— 系统 `python` 是 3.11 且没有 FastAPI）：

```bash
./.venv/Scripts/python.exe -m py_compile <files>
./.venv/Scripts/python.exe -m pytest
```

前端（在 `frontend/`）：

```bash
npm run api:generate
npm run check
npm run build
```

必要时执行：

```bash
npm run test:e2e
```

## Compatibility Check

修改已有接口必须明确：

```text
BACKWARD_COMPATIBILITY = PRESERVED / BREAKING
```

若为 BREAKING：

```text
必须解释原因
必须说明受影响调用方
必须提供迁移方式
未经明确批准不得直接实施
```

## Completion Report

API 契约任务完成后输出：

```text
API_CONTRACT_REPORT

ENDPOINTS_CHANGED =
REQUEST_SCHEMA_CHANGED = YES / NO
RESPONSE_SCHEMA_CHANGED = YES / NO
AUTH_CHANGED = YES / NO
ERROR_CONTRACT_CHANGED = YES / NO
BACKWARD_COMPATIBILITY = PRESERVED / BREAKING
API_TYPES_REGENERATED = YES / NO / NOT_RUN
BACKEND_TESTS = PASSED / FAILED / NOT_RUN
FRONTEND_CHECKS = PASSED / FAILED / NOT_RUN
DOCS_UPDATED = YES / NO / NOT_REQUIRED
```

如果 Shell 当前不可用，必须明确：

```text
RUNTIME_VALIDATION_PENDING = YES
```

不得伪造测试、类型生成或 build 结果。
