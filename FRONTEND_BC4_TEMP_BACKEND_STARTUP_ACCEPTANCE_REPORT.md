# FRONTEND_BC4_TEMP_BACKEND_STARTUP_ACCEPTANCE_REPORT

> 智学AI · Frontend Blocker BC4 — Temp Database Authenticated Startup Closure
> 生成：2026-09-17 · 本轮为 **BOUNDED BACKEND CORRECTNESS FIX**（无产品语义变更）
> 结论：`F1C1_REAL_VQA_BACKEND_READY = YES`

---

## 1. Reproduction

**场景**：独立 uvicorn 进程 + 显式 TEMP `DATABASE_URL` + 库中已存在一个用户
（即 F1C1 VQA 的第二次启动：先注册用户，再重启后端）。

**第一次启动（全新空库，0 用户）** → 成功。原因：compatibility backfill 的循环体
遍历 `SELECT ... FROM users WHERE COALESCE(is_deleted,0)=0`，没有用户就没有 INSERT。

**第二次启动（同一个库，1 个用户）** → **失败**（改动前）：

```text
EXIT=1
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: user_service_memberships.status
[SQL: INSERT INTO user_service_memberships (user_id, service_key, is_enabled, plan) VALUES (?, ?, ?, ?)]
[parameters: (1, 'exam_11408', 1, 'free')]
```

也就是说：**这个 bug 只在「库里已有用户」时出现** —— 全新空库第一次启动不会暴露它，
这正是它此前没有被测试发现的原因。VQA 环境（注册 → 重启）必然命中。

```text
TEMP_STARTUP_FAILURE_REPRODUCED = YES
```

---

## 2. Full Traceback

```text
Traceback (most recent call last):
  File "...\.venv\Lib\site-packages\uvicorn\__main__.py", line 4, in <module>
    uvicorn.main()
  ...
  File "C:\Users\26477\Desktop\ai_study_platform\backend\main.py", line 354, in <module>
    init_user_profile_schema()
  File "C:\Users\26477\Desktop\ai_study_platform\backend\database.py", line 1934, in init_user_profile_schema
    ensure_user_service_memberships_schema(conn)
  File "C:\Users\26477\Desktop\ai_study_platform\backend\database.py", line 2333, in ensure_user_service_memberships_schema
    conn.execute(...)
  ...
  File "...\sqlalchemy\engine\default.py", line 952, in do_execute
    cursor.execute(statement, parameters)
sqlite3.IntegrityError: NOT NULL constraint failed: user_service_memberships.status

The above exception was the direct cause of the following exception:
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: user_service_memberships.status
[SQL: INSERT INTO user_service_memberships (user_id, service_key, is_enabled, plan) VALUES (?, ?, ?, ?)]
[parameters: (1, 'exam_11408', 1, 'free')]
```

**调用链（精确到行）**：

```text
main.py:353   Base.metadata.create_all(bind=engine)
main.py:354   init_user_profile_schema()                                   ← 触发点
database.py:1934  init_user_profile_schema → ensure_user_service_memberships_schema(conn)
database.py:2333  ensure_user_service_memberships_schema → backfill INSERT（缺 status）
```

失败的是 **第一条** INSERT（`exam_11408`），后端在 import 阶段就崩溃，uvicorn 无法完成启动。

---

## 3. Schema Ownership — USER_SERVICE_MEMBERSHIPS_SCHEMA_MATRIX

**没有 Alembic 迁移拥有这张表**（`grep -rln user_service_memberships migrations/` → 空；
`20260917_0008_baseline_exam_legacy_runtime_tables.py` 的 scope 是 Exam 运行时表）。
`database_schema.ensure_database_schema()` 也不碰它（只处理 programming_exercises /
redemption_codes / ai_usage_logs）。

真实 owner 有三个，且**它们对 `status` 的说法不一致**：

| column | type | nullable | Python default | server_default | owner |
| --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | NOT NULL | — | （AUTOINCREMENT，仅 ensure 的 CREATE TABLE） | model `models.py:1176` |
| `user_id` | INTEGER | NOT NULL | — | — | model `models.py:1177` |
| `service_key` | VARCHAR(50) | NOT NULL | — | — | model `models.py:1178` |
| `is_enabled` | BOOLEAN | NOT NULL | `False` | `0`（仅 ensure 的 CREATE TABLE） | model `models.py:1179` |
| `plan` | VARCHAR(30) | NULL | `"free"` | `'free'`（仅 ensure 的 CREATE TABLE） | model `models.py:1180` |
| **`status`** | **VARCHAR(20)** | **NOT NULL** | **`"active"`** | **无（create_all 路径）** / `'active'`（ALTER 路径） | model `models.py:1181` + `database.py:2207` |
| `activated_at` | DATETIME | NULL | — | — | `database.py:2208` |
| `expires_at` | DATETIME | NULL | — | — | `database.py:2209` |
| `created_at` / `updated_at` | DATETIME | NULL | `utc_now` | — | model `models.py:1184-1185` |

### 3.1 `status` 为什么存在两种物理形态（实测 DDL）

`ensure_user_service_memberships_schema` 的写法是**先建表、再补列**：

```python
CREATE TABLE IF NOT EXISTS user_service_memberships (        # ← 不含 status
    ... is_enabled ... plan ... created_at ... updated_at ...
)
ensure_columns(conn, "user_service_memberships", {
    "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",       # ← 想补一个带 DEFAULT 的列
    "activated_at": "DATETIME", "expires_at": "DATETIME",
})
```

两条真实启动路径给出**不同的物理列**：

| 起点 | `status` 的 DDL | 有无 DB DEFAULT |
| --- | --- | --- |
| **A. 全新 TEMP 库** —— `create_all` 先建表，`CREATE TABLE IF NOT EXISTS` 变成 no-op，`ensure_columns` 见列已存在也 no-op | `status VARCHAR(20) NOT NULL` | **无**（`PRAGMA table_info` 的 `dflt_value = None`，已实测） |
| **B. 已部署的 `backend/app.db`** —— `ensure_columns` 真的执行了 `ALTER TABLE ADD COLUMN` | `status VARCHAR(20) NOT NULL DEFAULT 'active'` | **有**（已只读实测） |

```text
REAL app.db  DDL:
  ... created_at DATETIME, updated_at DATETIME,
      status VARCHAR(20) NOT NULL DEFAULT 'active', activated_at DATETIME, ...
  → 列是 ALTER 出来的，带 DEFAULT

FRESH temp DB DDL:
  ... "plan" VARCHAR(30), status VARCHAR(20) NOT NULL, activated_at DATETIME, ...
  → 列是 create_all 出来的，无 DEFAULT
```

模型上的 `default="active"` 是 **Python 侧默认**，只对 ORM INSERT 生效，
不会写进 `create_all` 生成的 DDL —— 这正是两条路径分叉的根源。

---

## 4. Insert Ownership

`user_service_memberships` 的写入口只有两类：

| # | 位置 | 方式 | 是否写 `status` | 是否受损 |
| --- | --- | --- | --- | --- |
| 1 | `database.py:2343`（本 helper 的 compatibility backfill） | **原生 SQL INSERT** | 改动前：**否** | **是（本次 blocker）** |
| 2 | `main.py:6527` / `6660` / `7297` | SQLAlchemy ORM `db.add(...)` | 否，但 ORM 会套用 Python 端 `default="active"` | 否 |
| 3 | `main.py:30801`（admin 会员授予） | ORM，显式 `status=requested_status` | 是 | 否 |

```text
全部原生 SQL INSERT INTO user_service_memberships：
  改动前 —— 仅 database.py:2335 一处，缺 status      ← 唯一受损点
  改动后 —— 仅 database.py:2343 一处，含 status
```

**确认：只有一处 compatibility insert 有此问题**，不存在第二处同类原生 INSERT。
三个老 ORM 创建点（6527/6660/7297）虽然源码里也没写 `status`，但 SQLAlchemy 在 flush 时
会填入 Python 端默认值，**永远不会**触发 NOT NULL —— 所以它们不是同一个 bug，
本轮不动它们（§8 禁止顺手扩大改动）。

**触发条件**：`ensure_user_service_memberships_schema` 的 backfill 循环，
对每个 `is_deleted = 0` 的用户 × 3 个 service_key，在**该 user+service 还没有行**时插入。
所以：新用户首次注册后的第一次重启必然命中。

---

## 5. Working Reference — canonical status value

不猜字段名。以下独立证据都指向同一组值：

| 证据 | 内容 |
| --- | --- |
| `models.py:1181` | `status = Column(String(20), nullable=False, default="active")` |
| `database.py:2207` | `ensure_columns` 的 spec：`"VARCHAR(20) NOT NULL DEFAULT 'active'"` |
| `database.py:2233`（**同一函数内**） | `UPDATE ... SET status = CASE WHEN COALESCE(is_enabled,0)=1 THEN 'active' ELSE 'inactive' END WHERE status IS NULL OR TRIM(status)=''` |
| `main.py:28311` / `main.py:30691` | 没有 membership 行时序列化出的默认值是 `"inactive"` |
| `payments/service.py:114` | 退款降级路径写 `membership.status = "inactive"` |
| `membership.py:452` / `membership.py:574` / `membership.py:76` | resolver 一律判定 `status == "active"` 才算生效 |
| `main.py:30762` | admin API 接受的输入域：`{"active", "disabled", "expired"}` |

**结论**：`user_service_memberships.status` 的 canonical 值域是
`active` / `inactive`（外加 admin 输入的 `disabled` / `expired`），
判定语义是 **只有 `"active"` 生效**。

对 compatibility 行来说，`is_enabled` 与 `status` 必须一致 ——
这正是同一函数第 2233 行已经写明的规则。

```text
STATUS_SEMANTICS_VERIFIED = YES
CANONICAL_STATUS_VALUE = "active"（is_enabled=1）/ "inactive"（is_enabled=0）
```

---

## 6. Root Cause — Verdict

**根因属于 §6 的候选 B**（model/migration 约定 status required，
但 ensure helper 的 compat insert 错误假设了一个并不总是存在的 DB DEFAULT），
并且只在「全新库」这条路径上暴露（因此也带一点候选 C 的形状）。

```text
ROOT CAUSE:
ensure_user_service_memberships_schema() 的原生 compatibility INSERT
只写 (user_id, service_key, is_enabled, plan)，
而 status 列在「全新库」这条启动路径上 **没有 DB 级 DEFAULT**：

  Base.metadata.create_all() 先用 model 建出 status VARCHAR(20) NOT NULL
  （model 的 default="active" 是 Python 端默认，不进 DDL），
  随后 CREATE TABLE IF NOT EXISTS 变成 no-op、
  ensure_columns 见列已存在也 no-op，
  于是 helper 自己期望的 "DEFAULT 'active'" 从未落到这份 schema 上。

该 INSERT 既没有 DB DEFAULT 可依赖，也不是 ORM INSERT（拿不到 Python 端默认），
因此 NOT NULL 直接失败，进程在 import 阶段退出。

helper 内部逻辑本身是自洽的（它甚至就在几行之前定义了 is_enabled -> status 的规则），
缺的只是把这条规则同样应用到它自己的 INSERT 上。
```

**为什么线上库不暴露**：已部署的 `app.db` 的 `status` 是 `ALTER TABLE ADD COLUMN ...
NOT NULL DEFAULT 'active'` 建出来的，**有** DB DEFAULT，所以同一个 INSERT 在那里能成功。
只有 `create_all` 先建表的全新库会缺这个 DEFAULT。

**明确排除的其它解释**：

* 不是 migration / model 与 ensure helper 的列集不一致 —— 列集是齐的，差的是 DEFAULT；
* 不是 helper 没被调用 —— 它在 traceback 里；
* 不是业务数据问题 —— 用最小合法 user 行即可复现。

---

## 7. Failing Test Before Fix

新增 `backend/tests/test_membership_startup_compat.py`。

它在**独立的 temp SQLite 文件**上复刻生产启动顺序
（`Base.metadata.create_all()` → 插入 user → `init_user_profile_schema()`），
不是只测 helper 函数：

```python
def _fresh_engine(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}", ...)
    Base.metadata.create_all(bind=engine)      # ← main.py:353
    return engine

def _run_startup(engine, monkeypatch):
    monkeypatch.setattr(database, "engine", engine)
    database.init_user_profile_schema()        # ← main.py:354
```

**修复前运行结果（稳定失败）**：

```text
FAILED test_fresh_temp_db_startup_does_not_raise
FAILED test_compat_rows_are_inserted_with_a_canonical_non_null_status
FAILED test_status_not_null_is_preserved
FAILED test_repeated_startup_is_idempotent
FAILED test_existing_membership_row_is_not_overwritten
FAILED test_deleted_users_are_not_backfilled
FAILED test_legacy_course_service_key_is_still_canonicalized
7 failed, 2 passed
```

失败原因统一是 `NOT NULL constraint failed: user_service_memberships.status`。
2 个通过的是**前置条件断言**（证明全新 schema 确实没有 DB DEFAULT），
它们本就应当通过，也是本次复现的立足点。

**修复后**：`9 passed`。

```text
FAILING_TEST_BEFORE_FIX = PASS
```

覆盖面（对应 §7 的 5 条要求）：

| 要求 | 测试 |
| --- | --- |
| fresh TEMP database → schema ready → startup → no IntegrityError | `test_fresh_temp_db_startup_does_not_raise` |
| 1. no existing membership row | 同上（`_memberships` 初始为空） |
| 2. compatibility row is inserted | `test_compat_rows_are_inserted_with_a_canonical_non_null_status` |
| 3. inserted status 合法且非 NULL | 同上 + `test_status_not_null_is_preserved` |
| 4. existing compatible row 不被错误覆盖 | `test_existing_membership_row_is_not_overwritten` |
| 5. repeated startup idempotent | `test_repeated_startup_is_idempotent` |
| 记录前置条件（无 DB DEFAULT、NOT NULL 必须在） | `test_fresh_schema_has_no_db_default_for_status` |
| 已部署形态（有 DB DEFAULT）仍然工作 | `test_deployed_shape_with_a_real_db_default_still_backfills` |
| 相邻兼容规则（`course` → `course_learning`）未回退 | `test_legacy_course_service_key_is_still_canonicalized` |
| 已删除用户不补行 | `test_deleted_users_are_not_backfilled` |

---

## 8. Minimal Fix

`backend/database.py`，`ensure_user_service_memberships_schema()` 的 compatibility INSERT
（唯一改动点）：

```diff
             is_enabled = 1 if sk == "exam_11408" else 0
             plan = legacy_plan if sk == "exam_11408" else "free"
+            # `status` has to be written explicitly. On a database built by
+            # `Base.metadata.create_all` the column comes from the model, whose
+            # `default="active"` is Python-side only, so the DDL carries no
+            # DEFAULT — and `ensure_columns` above cannot add one because the
+            # column already exists. Omitting it there violates NOT NULL.
+            # The value follows the same is_enabled -> status rule this helper
+            # already applies to existing rows.
+            status = "active" if is_enabled else "inactive"
             conn.execute(
                 text(
-                    "INSERT INTO user_service_memberships (user_id, service_key, is_enabled, plan) "
-                    "VALUES (:uid, :sk, :enabled, :plan)"
+                    "INSERT INTO user_service_memberships (user_id, service_key, is_enabled, plan, status) "
+                    "VALUES (:uid, :sk, :enabled, :plan, :status)"
                 ),
-                {"uid": uid, "sk": sk, "enabled": is_enabled, "plan": plan},
+                {"uid": uid, "sk": sk, "enabled": is_enabled, "plan": plan, "status": status},
             )
```

**净改动**：+1 赋值，+1 列，+1 绑定参数，+8 行注释。无其它任何变更。

**明确没有做的事**（§8 全项）：

| 禁止项 | 状态 |
| --- | --- |
| 把 status 改成 nullable 绕过 | 未做 —— NOT NULL 保留（有测试断言） |
| 删除 NOT NULL | 未做 |
| `INSERT OR IGNORE` 吞错 | 未做 |
| catch IntegrityError 后继续启动 | 未做 |
| 跳过 membership compatibility initialization | 未做 —— backfill 仍在跑 |
| 给所有表加宽松 server default | 未做 —— 没有改任何 schema |
| 重建会员体系 / 改统一 Subscription 架构 | 未做 |
| 恢复 legacy per-service membership 为产品真相 | 未做 |

**为什么不用「给列补 DB DEFAULT」**：SQLite 无法对已存在的列 `ALTER ... ADD DEFAULT`，
唯一办法是 rebuild 表 —— 那是 §8 与数据库安全原则共同禁止的破坏性操作。
补写 `status` 是唯一既最小又不破坏 schema 的修法。

**状态值选择**：没有新造 magic string —— `'active'` / `'inactive'` 是本函数
第 2233 行已经写下的同一规则，也与 `models.py` 的默认值、`payments/service.py`
的降级路径、resolver 的判定完全一致。

```text
MINIMAL_FIX = PASS
STATUS_NOT_NULL_PRESERVED = YES
```

---

## 9. Idempotency

**测试层**：`test_repeated_startup_is_idempotent` —— 连续跑 3 次
`init_user_profile_schema()`，行集合完全不变。

**真实进程层**：对同一个 TEMP 库连续启动 uvicorn **三次**：

```text
第 1 次（空库、0 用户）  → startup complete
第 2 次（1 个用户）      → startup complete（改动前此处崩溃）
第 3 次（同样 1 个用户）  → startup complete

memberships after 2nd startup:
  (1, 'course_learning', 0, 'free',           'inactive')
  (1, 'exam_11408',      1, 'monthly_sprint', 'active')
  (1, 'programming',     0, 'free',           'inactive')

memberships after 3rd startup == after 2nd startup   → IDEMPOTENT = True
```

不重复插行、不改写已存在行的 status（`test_existing_membership_row_is_not_overwritten`
用一个 `status='expired'` 的真实 grant 证明）、不报错。

```text
STARTUP_IDEMPOTENT = PASS
```

---

## 10. Fresh uvicorn startup

```text
方式：独立 uvicorn 进程
      DATABASE_URL=sqlite:///<temp>/vqa.db
      UPLOAD_ROOT=<temp>/uploads
      STUDENT_TWIN_MODE=internal
      ./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8942
```

```text
INFO:     Started server process [n]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8942

tracebacks in log = 0
GET /health      → 200
GET /openapi.json → 200
```

不是 `import main` —— 是真的独立进程 + 真实端口。

```text
INDEPENDENT_UVICORN_TEMP_DB = PASS
```

---

## 11. Authenticated Request Proof

在修复后的 TEMP 后端上建立真实登录会话（`ai_session` cookie），并访问两个受保护端点：

```text
POST /login {"username":"bc4_qa","password":"secret123"}
  → 200，Set-Cookie: ai_session=...
  → body.user.plan = "monthly_sprint"

GET /exam/prep/profile                       （需登录）
  → 200
    {"configured":false,"exam_type":"postgraduate","selected_track":null,
     "selected_subjects":[],"target_exam_year":null,"subjects":[]}

GET /exam/11408/subjects/data_structure/study-plan   （需登录 + learning_plan 授权）
  → 200
    {"course_id":"data_structure_11408","course_name":"11408 数据结构",
     "subject_key":"data_structure","subject_name":"数据结构",
     "settings":{...},"stats":{"total_knowledge_points":196,...}, ...}
```

注意：study-plan 返回 **200 而不是 403**，说明 compatibility backfill 补出的
`exam_11408 / is_enabled=1 / plan=monthly_sprint / status=active` 行真的被
entitlement resolver 认作有效 —— 修复不只是「不崩溃」，会员语义也正确。

```text
AUTHENTICATED_TEMP_BACKEND = PASS
F1C1_STUDY_PLAN_TEMP_REQUEST = PASS
```

---

## 12. Real DB Safety

```text
REAL backend/app.db
  mtime           = 2026-09-16 21:24:23（改动前后均未变；本轮为 09-17）
  SHA256 改动前   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  SHA256 改动后   = 1c1b2d8538d7a3c52a79a64dec904c69c6ec964b86decbc6508d0d2a438fe522
  integrity_check = ok
  表总数           = 72
  exam_question_bank = 9333 · programming_exercises = 1923 · knowledge_points = 32
  user_service_memberships 行数 = 0
  alembic_version table = 不存在

REAL_APP_DB_MUTATED = NO
```

真实库只被**只读**打开（`sqlite3.connect("file:backend/app.db?mode=ro", uri=True)`）
做过 DDL / 计数 / 完整性审计。没有对它执行任何 migration、`create_all` 或写操作。

Git：`HEAD = ebad5282`（未变）；无 commit / push / reset / clean / restore / stash /
merge / rebase / pull / worktree。

---

## 13. Tests

```text
BC4 专项（test_membership_startup_compat.py，独立运行）      = 9 passed / 0 failed
membership / auth / startup 回归组（14 个文件，含上面 9 条） = 118 passed / 0 failed
  （BC4 + admin_memberships + feature_entitlements + membership_orders
    + membership_redemption_codes + payment_lifecycle + auth + auth_v2
    + profile_identity + subscription_api + subscription_usage
    + admin_quota_override + knowledge_map_progress + learning_reports）

FULL_BACKEND_TESTS（backend/ pytest 全量）                  = 1012 passed / 0 failed
  本轮 baseline（BC3）= 1003；本轮新增 9  →  1012
```

---

## 14. F1C1 readiness

```text
current backend + fresh TEMP DB + authenticated session
  → GET /exam/11408/subjects/data_structure/study-plan  → 200，合法 JSON payload
```

BC3 已把该端点的 200 契约 typed（`ExamStudyPlanResponse`），BC4 让真实的
独立后端能够在这个契约上跑起来。二者合起来才让 F1C1 的真实 VQA 可用。

```text
F1C1_REAL_VQA_BACKEND_READY = YES
```

**本轮未写任何前端代码**（§16）。未做截图。

---

## 15. Changed Files

| file | 变更 | 理由 |
| --- | --- | --- |
| `backend/database.py` | compatibility INSERT 补写 `status`（+1 赋值 / +1 列 / +1 绑定 / +8 行注释） | 唯一根因点；无 schema 变更 |
| `backend/tests/test_membership_startup_compat.py` | **新建**（9 tests） | 复现 + 防回归 |

**未改**：`models.py`、任何 migration、`database_schema.py`、`main.py`、任何别的
`ensure_*` helper、任何 endpoint、任何会员业务逻辑、任何前端文件、`backend/app.db`。

---

## 16. Final Gates

```text
ROOT_CAUSE_VERIFIED                = YES
TEMP_STARTUP_FAILURE_REPRODUCED    = YES
FAILING_TEST_BEFORE_FIX            = PASS
STATUS_SEMANTICS_VERIFIED          = YES
MINIMAL_FIX                        = PASS
STATUS_NOT_NULL_PRESERVED          = YES
STARTUP_IDEMPOTENT                 = PASS
INDEPENDENT_UVICORN_TEMP_DB        = PASS
AUTHENTICATED_TEMP_BACKEND         = PASS
F1C1_STUDY_PLAN_TEMP_REQUEST       = PASS

BACKEND_PRODUCT_SEMANTICS_CHANGED  = NO
DB_SCHEMA_CHANGED                  = NO
MIGRATION_ADDED                    = NO
REAL_APP_DB_MUTATED                = NO

FULL_BACKEND_TESTS                 = PASS（1012 passed / 0 failed）
F1C1_REAL_VQA_BACKEND_READY        = YES
```

---

## 17. 观察（不属本轮，未处理）

按 §13 要求，以下既有工程债本轮**一律未动**：

① 本机遗留的旧后端进程（BC1 起已记录，服务的是改动前代码）。
   本轮启动的 TEMP 进程用完即停，端口 8931–8943 已释放。

② `npm run api:generate` 依赖手工启动的 8000 端口后端，CI 不可复现。

③ `backend/file`（0 字节游离文件）。

④ `create_all` + `ensure_*` 双轨制的全局架构债 —— 本轮只修了它实际咬到人的那一处。
   更一般地说，**任何「原生 SQL INSERT + model 的 Python 端默认」组合在有
   `create_all` 的全新库上都是不安全的**；本轮没有做全仓扫描（§13）。

⑤ `frontend/src/types/api.ts` 中其余 372 处 `unknown`（BC3 已记录）。

⑥ 已部署 `app.db` 与全新库在 `status` 列上物理 DDL 不同（一个有 DB DEFAULT、
   一个没有）。修复后行为一致，但这个**历史分叉本身**仍在；若要彻底消除，
   需要单独立项统一 schema 生成路径（属结构性重构，非本 blocker）。
