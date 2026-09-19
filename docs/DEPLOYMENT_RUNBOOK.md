# 部署 Runbook（ACCEL_SPRINT_S6）

> 适用对象：智学AI 生产环境（腾讯云单机 + systemd + GitHub Actions 自动部署）。
> 本文件描述**已实现**的部署序列；它不引入新工具，也不含任何密钥。
> 权威层级：`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md` > `CLAUDE.md` > 本文件。

---

## 0. 铁律（先读这一段）

```text
APPLICATION_CAN_START_BEFORE_MIGRATION = NO
```

从 `20260919_0010` 起，ORM 会 SELECT 只有迁移才能加上的列：

| 表 | 列 | 由哪个 revision 添加 |
|---|---|---|
| `learning_events` | `response_time_source`, `attempt_index` | `20260919_0010` |
| `practice_attempts` | `response_time_source`, `attempt_index` | `20260919_0010` |
| `wrong_answer_states` | `module_key` | `20260919_0009` |
| `ai_requests` | `service_namespace`, `context_json` | `20260915_0006` |
| `usage_ledger` | `service_namespace` | `20260915_0006` |

`Base.metadata.create_all` **不会**给已存在的表加列。所以：

- 跳过迁移 → 应用**拒绝启动**（不是降级运行，是启动失败）；
- 迁移完成 → 应用正常启动。

启动前的 schema 预检是 `backend/core/schema_preflight.py`，
由 `backend/main.py` 在 `create_all` **之前**调用。它只读、不改 schema、不 stamp revision。

---

## 1. 部署序列（自动流程）

`.github/workflows/deploy.yml` 的 `Deploy to Tencent Cloud` 步骤按以下顺序执行。
**顺序本身就是契约**，由 `backend/tests/test_s6_deployment_gate.py::test_the_deployment_migrates_before_it_starts_the_application` 断言保护。

| # | 步骤 | 命令 / 位置 | 失败后果 |
|---|---|---|---|
| 1 | 远端磁盘预检 | `df -h /`、`df -i /`（< 3 GiB 拒绝部署） | 中止，服务未动 |
| 2 | 同步代码 | `rsync`（排除 `backend/app.db`、`.env`、`.venv/`、`backups/`、`uploads/`） | 中止，服务未动 |
| 3 | 安装后端依赖 | `pip install -r backend/requirements.txt`（含 `alembic==1.20.0`） | 中止，服务未动 |
| 4 | 构建前端 | `npm ci && npm run build` | 中止，服务未动 |
| 5 | **停写** | `systemctl stop ai-backend`，并校验确实已停 | 中止 |
| 6 | **备份** | `cp /var/lib/ai_study_platform/app.db backend/backups/app.db.before-catalog-reform.<ts>.db`，校验非空 + `PRAGMA integrity_check` = `ok` | 中止，**不迁移** |
| 7 | **迁移** | `DATABASE_URL=… alembic -c alembic.ini upgrade head`，日志写入 `backend/backups/migration.<ts>.log` | 中止，**不启动应用**，按 §4 用第 6 步备份恢复 |
| 8 | **schema 校验** | `python scripts/deploy/check_schema.py` | 中止，**不启动应用** |
| 9 | 迁移后完整性 | `sqlite3 "$DATA_DB" 'PRAGMA integrity_check;'` = `ok` | 中止，**不启动应用** |
| 10 | 既有 seed / 题库构建 | `ensure_database_schema` + catalog seed + 11408 题库构建 | 中止 |
| 11 | **启动后端** | `systemctl restart ai-backend` | 见 §3 健康检查 |
| 12 | 健康检查 | `curl -fsS http://127.0.0.1:8000/health`（30 次 × 2s） | 部署失败，打印 `journalctl -u ai-backend` |
| 13 | 科学运行时 | `deploy/deploy-runtime-service.sh` + `:8101/health` | 部署失败 |
| 14 | HTTPS / Secure cookie | `scripts/deploy/configure_https.sh` → `AI_SESSION_COOKIE_SECURE=true` → 重启 → `https://…/api/health` | 部署失败 |

**没有任何一步可以调换顺序。** 特别是 7 与 11：迁移必须在应用启动之前完成。

---

## 2. 手动执行（同一条序列）

在服务器上，`REPO_ROOT=~/ai_study_platform`、`DATA_DB=/var/lib/ai_study_platform/app.db`。

### 2.1 备份（不可跳过）

```bash
sudo systemctl stop ai-backend
mkdir -p "$REPO_ROOT/backend/backups"
cp "$DATA_DB" "$REPO_ROOT/backend/backups/app.db.before-migration.$(date +%Y%m%d_%H%M%S).db"
test -s "$REPO_ROOT/backend/backups/app.db.before-migration."*.db
sqlite3 "$DATA_DB" 'PRAGMA integrity_check;'   # 必须输出 ok
```

### 2.2 迁移

```bash
cd "$REPO_ROOT"
DATABASE_URL="sqlite:////var/lib/ai_study_platform/app.db" \
  backend/.venv/bin/python -m alembic -c alembic.ini upgrade head
```

### 2.3 schema 校验（迁移之后、启动之前）

```bash
DATABASE_URL="sqlite:////var/lib/ai_study_platform/app.db" \
  backend/.venv/bin/python scripts/deploy/check_schema.py
```

期望：退出码 `0`，且输出包含 `"state": "AT_HEAD"`。

### 2.4 启动

```bash
sudo systemctl start ai-backend
```

---

## 3. 验证

### 3.1 进程健康

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8101/health          # 科学运行时
journalctl -u ai-backend -n 80 --no-pager      # 启动失败时唯一有用的证据
```

### 3.2 已认证冒烟（最低限度）

用真实账号走一遍，确认迁移没有破坏读路径：

1. `POST /login` → 200，且响应带 `ai_session` cookie；
2. `GET /exam/prep/catalog` → 200；
3. `GET /exam/prep/profile` → 200；
4. `GET /exam/11408/subjects/operating_system/dashboard-summary` → 200；
5. `GET /exam/11408/subjects/operating_system/study-plan` → 200（需 `learning_plan` 权益；无权益时为 403，这是权益门，不是 schema 故障）；
6. `GET /exam/prep/records` → 200；
7. `GET /exam/prep/scientific/student-twin` → 200（`PREVIEW`）。

**注意**：`GET /exam/prep/scientific/evidence-reliability` 即使返回 200，也**不得**向用户展示其数值 —— 该组件处于 `SHADOW_NOT_USER_VISIBLE`。

### 3.3 新事实是否开始累积

做**一次真实答题**，然后确认三处：

- `learning_events` 新增一行，且 `correct` 是真正的布尔值；
- 该行的 `attempt_index` 已写入（live 路径的第 1 次答题为 `1`）；
- `GET /exam/prep/records` 能看到它，`GET /exam/prep/scientific/student-twin` 的
  `input_summary.event_count` 增加。

---

## 4. 失败与回滚决策点

```text
DECISION POINT — 部署脚本在迁移失败时退出，应用保持 STOPPED。
```

### 4.1 迁移失败（步骤 7）

应用**没有**启动。此时数据库可能处于部分应用状态 —— Alembic 的 SQLite DDL 是非事务性的
（日志中的 `Will assume non-transactional DDL`），所以「回滚事务」并不存在。

恢复动作是把第 6 步的备份**整文件替换**回去：

```bash
sudo systemctl stop ai-backend
cp "$REPO_ROOT/backend/backups/app.db.before-migration.<ts>.db" "$DATA_DB"
sqlite3 "$DATA_DB" 'PRAGMA integrity_check;'   # 必须 ok
DATABASE_URL="sqlite:////var/lib/ai_study_platform/app.db" \
  backend/.venv/bin/python scripts/deploy/check_schema.py   # 期望退出码 1（回到迁移前）
sudo systemctl start ai-backend
```

### 4.2 schema 校验失败（步骤 8）或完整性失败（步骤 9）

与 4.1 相同：备份替换 → 完整性 → 重启旧代码。**不要**手工 `ALTER TABLE` 去「补上」缺的列 ——
那会让 `alembic_version` 与真实 schema 脱节，预检从此失效。

### 4.3 应用启动后健康检查失败（步骤 12）

应用已启动但不可用。**先看日志**，再决定：

```bash
sudo systemctl status ai-backend --no-pager -l
sudo journalctl -u ai-backend -n 120 --no-pager
```

- 日志是 `SCHEMA PREFLIGHT FAILED` → 走 4.1；
- 日志是别的异常 → 那是应用缺陷，不是迁移问题：回滚**应用代码**（重新部署上一个 commit），
  **不要**回滚数据库。迁移是 additive-only，旧代码在新 schema 上仍然可读。

### 4.3b 关于 WAL 的备份陷阱（必须知道）

生产库运行在 **WAL 模式**，且 `app.db-wal` 可能持有尚未 checkpoint 的已提交事务
（2026-09-19 实测：主文件 81→76 张表，5 张表只存在于 WAL 中）。

- 部署脚本的备份发生在 `systemctl stop ai-backend` **之后**，进程正常关闭会触发
  checkpoint，因此该备份是完整的 —— **顺序不能改**：停止 → 备份 → 迁移。
- 但在服务**运行中**手工 `cp app.db` 得到的备份**会丢失 WAL 中的最新事务**。
  需要热备份时必须用一致性快照：

```bash
sqlite3 "file:/var/lib/ai_study_platform/app.db?mode=ro" \
  "VACUUM INTO '/tmp/app-snapshot.db'"
```

- 核对方法：比较两边的表数与行数，而不是只看文件大小。

### 4.4 不要做什么

- **不要**依赖 `alembic downgrade`。本项目的 `20260919_0009` / `20260919_0010` 的
  `downgrade()` 直接 `raise NotImplementedError`：删掉 telemetry 列会销毁「这个时长是怎么测出来的」
  的唯一记录，删掉 `module_key` 会销毁错题归档的模块归属。
  **Alembic downgrade 在这里不是无损的，本项目也不声称它无损。**
- **不要**在没有备份的情况下迁移。
- **不要**把本地 `backend/app.db` 与生产库混为一谈。

---

## 5. 证据留存

每次部署之后应能回答「当时是哪个 revision、日志在哪」：

| 证据 | 位置 |
|---|---|
| 迁移前备份 | `backend/backups/app.db.before-catalog-reform.<ts>.db` |
| 迁移日志 | `backend/backups/migration.<ts>.log`（含 `Running upgrade … -> …`） |
| 迁移后 revision | `sqlite3 "$DATA_DB" 'SELECT * FROM alembic_version;'` |
| 部署记录 | GitHub Actions run（标题 = 中文 commit message） |

保留策略：每个受管目录只保留最新的 3 个自动备份，里程碑备份不受影响。

---

## 6. 部署前本地验证（发布者自查）

在提交/推送之前，本地必须先通过：

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_s6_deployment_gate.py tests/test_s6_data_flywheel.py -q
```

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q
```

其中 `test_s6_deployment_gate.py` 会在**真实 `backend/app.db` 的逐字节副本**上跑完整序列
（备份 → 迁移 → 校验 → 应用启动 → CS408 全表面 → StudentTwin），并断言真实文件
sha256 / size / mtime 未变。真实库在本流程中始终只读。

---

## 7. 已知边界

- 生产库与本地 `backend/app.db` 是同一个祖先（首次部署时拷贝），但**不是同一个文件**。
  本 runbook 的迁移序列在本地副本上已被逐字节验证；生产库的实际状态应在迁移前用
  §2.3 的 `check_schema.py` 读一次并存档。
- `DATA_PLANE_WRITE_ENABLED` 是**分路径**生效的，不是全局开关：
  - `data_plane/emitter.py`（`course_learning` 的 `course_practice` 事件）**受它门控**，
    部署默认 `false`，所以课程练习的事件在未显式打开时不会写入；
  - `learning/practice/events.py`（`exam_prep` / `programming` 的 `question_answered` /
    `code_submitted` 事件）**不受它门控**，CS408 的事实流照常写入。
  因此 CS408 的数据飞轮**不依赖**该变量；课程侧依赖。这不是迁移问题，是部署配置。
