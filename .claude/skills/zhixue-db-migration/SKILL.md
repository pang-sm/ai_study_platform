---
name: zhixue-db-migration
description: 智学AI SQLite 数据库结构变更与迁移安全流程。涉及 Alembic、migrations/、alembic.ini、database.py、database_schema.py、ensure_*_schema、表/字段/索引新增或数据库迁移时必须使用。
---

# ZhiXue Database Migration

## Authority

> **唯一最高权威是根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。**
> 本 Skill 从属于 SSOT；冲突时 SSOT wins。
> 数据库原则见 SSOT §40（CURRENT Database）、§54（Clean Slate 原则）、§56.2（迁移矩阵）。

## Purpose

用于智学AI SQLite 数据库 schema 修改和迁移。

核心原则：

> additive-only

**当前数据库已清空用户数据**（SSOT §40：`users = 0`、`user_service_memberships = 0`、
`membership_orders = 0`、`ai_usage_logs = 0`），因此现在是一次 schema 清场窗口。
但 `STATIC / CONTENT / SCIENTIFIC DATA` 仍必须**强保护**。

绝对不能误删：

```text
exam_question_bank        = 9333
programming_exercises     = 1923
knowledge_points          = 32（programming_c 系统知识本体，见 SSOT §40.1）
exam_resources /
static /
backend/data/programming_catalog/
```

## Trigger

出现以下情况时必须使用本 Skill：

- 新增数据库表
- 新增字段
- 新增索引
- 修改 `alembic.ini`
- 修改 `migrations/env.py`
- 新增 / 修改 `migrations/versions/*`
- 修改 `backend/database.py`
- 修改 `backend/database_schema.py`
- 修改 `ensure_*_schema()`
- 修改 `ensure_database_schema()`
- 设计或执行数据库迁移
- 部署涉及 schema change

以下情况通常不需要：

- 普通 SELECT 查询
- 纯前端修改
- 不涉及 schema 的业务逻辑修改
- 只读取 ORM model 且不修改数据库结构

## Hard Rules

### 1. Additive-only

允许：

```sql
CREATE TABLE IF NOT EXISTS ...
ALTER TABLE ... ADD COLUMN ...
CREATE INDEX IF NOT EXISTS ...
```

原则上禁止：

```text
DROP TABLE
DROP COLUMN
TRUNCATE
```

禁止为了修改 schema：

```text
rebuild existing table
删除后重新创建已有表
批量覆盖已有用户数据
批量重写已有业务记录
清空表再重新 seed
用临时表替换真实业务表，除非用户明确批准并已有独立备份与迁移方案
```

### 2. Migration Entry Point

**正式迁移机制 = Alembic**（STEP7A 建立，SSOT §73）：

```text
alembic.ini
migrations/env.py
migrations/versions/
```

当前 HEAD 版本 = `20260915_0002`。

`backend/database.py` 的 `ensure_*_schema()` 与 `backend/database_schema.py` 的
`ensure_database_schema()` 是 **legacy 机制**，仅保留用于既有表的幂等保障。

规则：

```text
新 schema 变更            → Alembic migration
既有表的幂等保障           → 可继续使用 ensure_*_schema()
不得新增隐式的、散落在业务模块中的 schema migration
不得让两套机制同时声称自己是唯一入口
```

不得在随机业务模块中创建隐式 schema migration。

### 3. Local / Production Isolation

本地数据库：

```text
backend/app.db
```

生产数据库：

```text
/var/lib/ai_study_platform/app.db
```

两者必须严格区分。

不得因为本地验证成功就直接修改生产数据库。

生产 schema 修改必须经过既有部署流程。

## Before Modification

数据库修改之前：

```text
确认修改目标。
确认涉及哪些表、字段、索引。
检查是否已有对应字段或表。
检查已有 ensure_*_schema()。
判断是否能通过 additive migration 完成。
明确是否影响已有数据。
明确是否需要生产迁移。
不读取或输出 .env、.env.local、API Key、Secret。
```

如果无法通过 additive-only 安全完成：

```text
DB_MIGRATION_BLOCKED = YES
```

说明原因并停止实施，不得自行采用 destructive migration。

## Backup

任何实际修改数据库前必须先生成备份。

本地示例：

```text
app.db.before-<reason>.<timestamp>.db
```

生产环境必须遵循现有部署备份流程。

不得覆盖已有备份。

## Implementation

实施 schema change 时：

```text
使用幂等 SQL
新字段应考虑旧数据库兼容
新字段若需要默认值，应明确旧记录行为
新索引使用 IF NOT EXISTS
不改变无关表
不修改无关数据
不顺手重构数据库层
```

## Verification

修改后必须验证：

Static

```text
migration 是幂等的
无 DROP / TRUNCATE / destructive rewrite
只修改目标 schema
旧数据语义保持兼容
```

Runtime

Shell 可用时执行相关验证（在 `backend/`，必须使用项目 venv）：

```bash
./.venv/Scripts/python.exe -m py_compile <files>
./.venv/Scripts/python.exe -m pytest
```

数据库修改后执行：

```sql
PRAGMA integrity_check;
```

要求：

```text
ok
```

必要时验证：

```text
新表存在
新字段存在
新索引存在
旧记录数量合理
关键业务数据仍可读取
```

## Production Rule

禁止：

```text
SSH 后直接手改生产数据库
绕过部署流程执行 schema change
未备份生产数据库就迁移
未做 integrity_check 就宣布完成
```

生产数据库修改只允许通过项目既有正式部署流程完成。

## Completion Report

数据库任务完成后输出：

```text
DB_MIGRATION_REPORT

SCHEMA_CHANGE =
ADDITIVE_ONLY = YES / NO
BACKUP_CREATED = YES / NO / NOT_RUN
INTEGRITY_CHECK = OK / FAILED / NOT_RUN
TESTS = PASSED / FAILED / NOT_RUN
PRODUCTION_MIGRATION_REQUIRED = YES / NO
DESTRUCTIVE_OPERATION = NO
```

在 Shell 无法使用时必须明确：

```text
RUNTIME_VALIDATION_PENDING = YES
```

不得伪造测试、备份或 integrity check 结果。
