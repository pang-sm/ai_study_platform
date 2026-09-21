# ZHIXUE_FRONTEND_PRODUCT_SYSTEM_P7A_REPORT

> 范围：**P7-A（FRONTEND ENGINEERING）**
> 分工：本报告作者负责 frontend architecture / React implementation / API integration / router /
> auth state / query state / forms / responsive / tests / a11y / performance。
> 日期：2026-09-20 · 工作树：`main`（未提交，未 push，未 rebase，未 merge）
> 后端：**未修改**（见 §9 证据）

---

## 0. 结论摘要

P7-A 范围内 AUTH / HOME / PROFILE / GLOBAL SHELL / PROGRAMMING SEMANTICS 全部完成并验证。
所有数据均来自当前 OpenAPI 真实契约；未新增假入口、未伪造能力。

**`CODEX_SPEC_APPLIED = NO`** —— `ZHIXUE_P7A_INTERACTION_SPEC` 在本轮**未到达**。
因此本轮完成的是**不依赖视觉规范**的工程层（架构、状态、契约接线、语义、测试、可访问性），
界面采用 token-first 的中性实现，可被 Codex spec 直接替换 / 重排而无需重写状态层。

---

## 1. 最终 gate 值

| Gate | 值 |
| --- | --- |
| TYPECHECK | `PASS`（`tsc --noEmit`，exit 0） |
| LINT_CHANGED | `PASS` —— 先对 47 个本次改动文件跑 eslint（5 个错误，全部修复），后全量 `npm run lint` → exit 0 |
| VITEST | `PASS` —— **197 passed / 48 files**（本轮开始前为 147 passed / 40 files，新增 50 个测试 / 8 个文件） |
| BUILD | `PASS`（`vite build`，exit 0） |
| PLAYWRIGHT | `PASS` —— targeted：`smoke.spec.ts` + `p7a-auth-surfaces.spec.ts` 共 **10 passed** |
| AXE | `PASS` —— 0 violations（`/login`、`/register`，`@axe-core/playwright`） |
| CODEX_SPEC_APPLIED | `NO`（spec 未到达） |
| NO_FAKE_DATA | `YES`（见 §5 / §7） |
| NO_BACKEND_CHANGED | `YES`（见 §9） |
| USER_WORKTREE_PRESERVED | `YES`（见 §9） |

**PLAYWRIGHT 运行环境说明（重要，非代码缺陷）**：本次 e2e 证据来自**全新启动的 dev server**。
仓库中长期运行的 `127.0.0.1:5173` 在 route option（`beforeLoad` / `staticData`）变更后会保留
陈旧的 router 模块图，对同一份代码给出**不同**结果（实测：陈旧 server 下 2 个 protected-route
用例失败，全新 server 下 10/10 通过；同一用例放宽超时到 25s 仍失败，证明是模块图陈旧而非延迟）。
**结论：改完 router / route options 后必须重启 `npm run dev`。**

---

## 2. AUTH

新增 `src/features/auth/`：

| 文件 | 职责 |
| --- | --- |
| `api/auth.ts` | `fetchSession` / `useSession` / `useLogin` / `useLogout` / 注册三步 `useSendRegisterCode` `useVerifyRegisterCode` `useRegister` |
| `api/user-profile.ts` | `user_profile()` 的 Zod reader（login / register / `/me` / `/me/profile` 四路共用同一 serializer） |
| `query-keys.ts` | 单一 session key，供 API 与 cache 策略共用，避免循环依赖 |
| `session-cache.ts` | logout 的缓存淘汰策略（allow-list） |
| `return-to.ts` | `returnTo` 的进入即校验 |
| `auth-context.tsx` | `AuthProvider` / `useAuth`，唯一登录状态权威 |
| `components/` | `AuthLayout` / `LoginPage` / `RegisterPage`（RHF + Zod 4） |

`AUTH = PASS` / `AUTH_GUARD = PASS` / `SESSION_RESTORE = PASS` / `RETURN_ROUTE = PASS`

- **统一 AuthProvider**：guard 与 UI 读**同一个** `['auth','session']` query。
  `禁止各 route 自己判断登录` 已满足：只有 `__root.tsx` 的 `beforeLoad` 做判断。
- **未登录访问受保护路由** → `/login?returnTo=<原路径+query>`。
- **登录成功** → 回到 `returnTo`，否则 Home。
- **已有有效 session 访问 `/login`** → 不再显示登录表单，直接放行到目标。
- **logout** → 调真实 `POST /logout`，清除 user-private cache，回到 `/login`。

### returnTo 的安全处理
`returnTo` 来自地址栏，属攻击者可控输入。只接受同源绝对路径；`https://` 绝对 URL、
协议相对 `//host`、反斜杠变体、控制字符一律拒绝并回退 Home；指向 `/login` / `/register`
的目标被过滤，避免登录后弹回登录页。单测 11 例覆盖（含 `javascript:`、换行注入）。

### logout 缓存淘汰（只清 user-private）
allow-list 保留三个**无用户态**的公共读：`exam/catalog`、`exam/subject-content-status/*`、
`exam/scientific-capabilities`；其余一律移除；session 条目本身由 login/logout 显式写入，
避免淘汰竞态。单测 3 例覆盖。

### 两个在实现中被发现的真实缺陷（已修）
1. **`fetchSession` 把「无法解析的响应」当成「未登录」**。原实现 `safeParse` 失败即 `return null`，
   意味着**任何返回 200 的非 JSON 响应（captive portal、代理拦截页、后端回归）都会把每个用户静默登出**，
   并把已登录用户送到登录页而不给任何解释。现改为**只有 401/403 才是 `null`，其余（网络失败、
   非预期状态码、无法解析的 body）一律抛错**。
2. **guard 让 public 路由也阻塞在网络探测上**。原实现在判 public 之前 `await` 探测，
   实测当 API 不可达时 `/login` **约 5–7 秒白屏**（e2e 计量：t≈500ms 空 → t≈8000ms 才出现表单）。
   现改为 public 路径**同步读缓存立即渲染**、探测在后台继续，`LoginPage` 在探测证实已有 session 时
   主动跳转（满足「已有 session 不重复显示 Login」且不再阻塞首屏）。修复后 `/login` 在 500ms 内渲染。
   同时补 `pendingComponent`（此前受保护深链首屏是空白）与 `ErrorState` 的重试动作。

---

## 3. HOME

`HOME = PASS` / `DAILY_AGENDA = PASS` / `FIRST_USER_STATE = PASS`

顺序为 **服务端策略顺序，前端零重排**：`GET /learning/agenda` 返回什么顺序就渲染什么顺序，
`priority_reason` / `resolved_by` / `deep_link` / `facts` 全部原样呈现；优先级语义没有在前端重实现。

### 修掉的真实缺陷
`daily-agenda.tsx` 的 `reasonLabels` 本地映射 **6 个 key 中 4 个是后端根本不存在的**：

| 本地（错） | 后端真实 reason code |
| --- | --- |
| `recent_wrong` | `repeated_wrong` |
| `plan_due` | `overdue_plan_task` / `current_plan_task` |
| `coverage_gap` | `unseen_coverage` |
| `unseen_topic` | （不存在） |

后果：7 个真实 reason code 里有 4 个在界面上**直接显示机器码**。
同一处还读取 `explain.reasons`，而后端 `explain_agenda` 返回的是 **`priority_rules`** ——
即「依据」一行在生产中**从未渲染过**。

修复方式不是「把 map 抄对」，而是**不再重复后端已有的清单**：改读 `/learning/agenda/explain`
的 `priority_rules[reason]`（后端自己写的中文规则），缺失时显示 `服务端给出的原因码：<code>`。
另修 `namespaceLabels` 把 `exam_11408` 当 key —— 实际发出的 canonical namespace 是 `exam_prep`
（`exam_11408` 只是**输入侧** legacy alias），同样导致原始串外泄。

### 其余 Home 内容（全部真实契约）
- **待复习**：`GET /review/summary` → `total` / `has_stored_due_dates`。
- **最近学习**：`GET /learning-records`（STEP 7F canonical 事件流，服务端默认排除 audit-only 事件）。
  事件类型中文标签只覆盖 taxonomy 中 21 个 `ACTIVE` + `USER_FACING` 家族，
  **未映射的码原样显示**（测试断言了这一点），不猜。
- **会员/用量轻量状态**：`GET /subscription` + `/subscription/plans` + `/usage/summary`。
- **first-user / empty**：`needs_onboarding === true` 时给出两个**真实有效**的去处
  （`/profile` → `PUT /me/profile`；`/exam/setup` → `PUT /exam/prep/profile`）；
  agenda 空、记录空各有各自的诚实空状态，不用占位内容填充。
- **未使用**：`GET /home/summary` —— 它返回 `average_mastery` / `streak`，
  是 legacy `UserKnowledgeProgress.mastery_score` 的聚合，**不是**已产品化的 scientific 输出，
  也不在 `/exam/prep/scientific/capabilities` 中；用了就是伪造掌握度 KPI。

---

## 4. GLOBAL SHELL

`GLOBAL_SHELL = PASS` / `RESPONSIVE_NAV = PASS`

**一个产品 + 三个 Learning Space**，不是三套壳。桌面导航与移动面板共用
`PRIMARY_NAV` 单一列表（`primary-nav.tsx`），二者不可能漂移。

修掉的真实缺陷（原 `app-shell.tsx`）：
- 「搜索学习内容」按钮 —— **后端无搜索能力，按钮点了没有任何行为**。已删除。
- 账户按钮显示**硬编码的「同」字**，与登录者无关。已替换为读真实 session 的账户菜单
  （显示昵称/账号、`学习档案`、`会员与用量`、`退出登录`）。
- 移动端汉堡按钮**不打开任何东西** —— 手机上完全没有导航。已替换为真实的 disclosure 面板
  （`aria-expanded` / 路由跳转后自动关闭 / Escape 关闭），面板与桌面共用同一份链接列表。
- 导航含 `复习` / `学习报告` / `会员`（共享学习能力），与三个空间同层呈现。

账号菜单与移动面板均为 disclosure 模式（非 `role="menu"`），两个 landmark 使用**不同 aria-label**
以便读屏区分。

---

## 5. PROFILE

`PROFILE = PASS` / `LEARNING_SETTINGS = PASS` / `MEMBERSHIP_USAGE = PASS` / `ACCOUNT_SECURITY = PASS`

分区：个人信息 / 学习设置 / 会员 / 用量 / 学习数据 / 账号与安全 / 法务 / 退出登录。

### 学习设置只暴露**后端真正读取**的字段
逐一 grep 全后端确认消费方后：

| 字段 | 后端消费方 | 是否可编辑 |
| --- | --- | --- |
| `learning_direction` | `main.py:1904`（legacy 408 轨道判定） | ✅ |
| `focus_courses` | `main.py:1255`（课程解析 fallback） | ✅ |
| `default_course_id` | `main.py:1260/1910`（课程解析、408 判定） | ✅（随 focus_courses 规则呈现） |
| `school` `learning_stage` `ai_answer_style` `answer_detail_level` `material_reference_preference` `daily_study_minutes` | **无任何读取方**（仅 `user_profile` 回显 + admin 报表） | ❌ **不呈现** |

后六个字段虽然可写、可回显，但**没有任何行为读取它们**。把它们做成「AI 回答风格 / 学习阶段」
设置就是承诺一个不存在的效果。测试显式断言这些 label 不在页面上。
每科真实生效的计划设置（每日时长 / 每周天数 / 复习策略）由 `/exam/cs408/plan` 拥有，
Profile **链接过去**而不是复制一套。

### 会员 / 用量
`GET /subscription` → `tier` + `policy_version`；`GET /subscription/plans` → 档位标签与额度；
`GET /usage/summary` → `daily` / `weekly` 各 4 个账本字段。
额度为 `null` 时显示**「无上限」**而不是 `0`（后端用它表示「该周期无上限」，是真实缺失而非零）——
测试断言了 4 个字段全部为 null 的周期渲染出 4 个「无上限」。
`plans[tier].capabilities` 是内部 capability id（形如 `tutor.chat`），契约里没有中文名映射，
**不展示**（自造中文名即伪造）。

### 账号与安全
- **修改密码**：`PUT /me/password`，校验与后端逐条对齐（全部非空、新密码 **≥ 8 位**
  —— 注意与注册的 6 位不同、两次一致、不得与旧密码相同）。
- **邮箱**：`POST /me/email/send-code` + `PUT /me/email/verify`。已绑定则**只读展示**
  （`EMAIL_ALREADY_BOUND`：「绑定后不可更换」），不提供后端会拒绝的更换入口。
- **手机号**：绑定与更换是**两条不同后端路由**（`bind` 对已绑定账号返回 409 `PHONE_ALREADY_BOUND`，
  `change` 才是替换），前端按当前状态选路由，不靠猜。提示「中国大陆手机号」与后端 `PHONE_RE` 一致。

### 法务
后端与前端**均不存在**用户协议 / 隐私政策 endpoint 或内容。该分区**明说未发布且不提供入口**，
而不是链到一个编造的页面。测试断言该区域内没有任何链接。

### 修复的真实缺陷
表单用 `profile.data ?? auth.user` 作为 `defaultValues`，而 RHF 的默认值**只在 mount 时读取一次**：
session 里的部分 profile 先到、完整 profile 后到时，字段会**停在过期值**。
现改为**等 `GET /me/profile` 到达后才挂载可编辑分区**（此前显示骨架），身份头部仍即时可见。

---

## 6. PROGRAMMING SEMANTICS

`PROGRAMMING_DIAGNOSE = PASS` / `AI_DEBUG = PASS` / `DEBUG_AGENT = PASS`

### 修复前（真实语义错误）
`src/features/programming/api/programming.ts` 的 `useCodeCoach`：

```
kind === 'debug'   → POST /code/diagnose   （编译器静态检查，无模型、无额度、无 request_id）
kind === 'explain' → POST /code/analyze    （真实 AI）
```

而 UI（`programming-pages.tsx`）把 `kind:'debug'` 的按钮标为 **「AI Debug」**、
把失败测试快捷入口标为 **「用 AI Debug 诊断失败测试」**，并写着
「AI Debug 是单次诊断」。即：**一个编译器的结论被当作 AI 呈现给学习者**。
`ErrorsPage` 同样声称错误复盘来自「AI Debug 返回」。

另有一处**潜在 400**：`AI Debug` 按钮传 `question: ''`，而 `/code/analyze` 对空问题返回
`400 请输入要分析的问题` —— 所以简单地把 `debug` 指到 `/code/analyze` 会直接坏掉。

### 修复后：三种能力显式分离

| UI 名称 | endpoint | 语义 |
| --- | --- | --- |
| **代码诊断（静态语法检查）** | `POST /code/diagnose` | 确定性：`gcc -fsyntax-only` / `py_compile`。不调模型、不消耗额度、无 `request_id`。行/列来自编译器本身。 |
| **AI Debug（AI 代码分析）** | `POST /code/analyze` | 真实 AI 能力 `programming.explain`，消耗额度，返回真实 `request_id` 可评价。 |
| **Debug Agent** | `POST /programming/agent/debug` | 有边界的多步工作流（诊断 → 修补 → 跑题目的测试 → 复查），每步单独结算。 |

- `useCodeCoach` 被**删除**，替换为 `useCodeDiagnose` / `useCodeAnalysis` —— 两个独立命名的
  hook，`kind` 判别式不存在了，语义无法再被混淆。
- AI Debug **要求真实问题**：按钮在问题为空时禁用，并说明「AI 需要知道你在问什么」。
  失败测试快捷入口把**本次运行的真实 stderr** 组进问题（`测试未通过。stderr：…`），
  不是通用 prompt。
- 代码诊断结果按编译器的 `line:column` / `message` / `source` 结构化渲染，**不再 dump JSON**；
  诊断失败时明说「不影响运行、测试与提交」（实证：编译器不可用不阻断学习闭环）。
- AI 分析结果渲染 `answer`，并只在存在真实 `request_id` 时挂 `AiFeedback`。
- 顺带修掉 `ProgrammingHomePage` 里**硬编码的「进入 Python 练习」**单一语言入口，
  改为列出四个真实存在的语言路由。

测试（7 例）：`代码诊断` 渲染编译器诊断且**即使 payload 携带 `request_id` 也不渲染评价组件**；
`AI Debug` 空问题禁用、填写后调用真实 AI 端点并评价真实 request_id；
失败测试快捷入口进入 **AI 端点**（断言 language 与 question 组成）；
Debug Agent 断言 POST 目标是 `/programming/agent/debug` 且**明确不是** `/code/diagnose` /
`/code/analyze`，并渲染完整 trace、前后测试测量与 credits。

---

## 7. NO_FAKE_DATA 逐项

| 检查 | 结果 |
| --- | --- |
| 忘记密码 / 找回密码 | **未创建**（契约不存在） |
| 假分数 / 假掌握度 / 假学习等级 / 假 KPI | **无**。`/home/summary` 的 `average_mastery`·`streak` 刻意未使用 |
| 假知识点 / 假章节 / 假真题 / 假进度 | **无** |
| 假搜索入口 | 已删除（原 shell 的搜索按钮无后端能力） |
| 无消费者的设置项 | **未呈现**（6 个 write-only 字段） |
| 法务文档 | 明示不存在，不链假页面 |
| 硬编码科目 / 语言清单 | 前端唯一硬编码清单是 `PRIMARY_NAV`（产品自身导航）；语言列表来自**前端自己的路由词汇** `programmingLanguages`，不是对后端可用性的断言 |
| provider / 模型名 / 价格 | **未暴露** |
| 旧三服务会员 | **未恢复**；会员面使用统一 `/subscription` + `/usage/summary` |

---

## 8. BACKEND_CONTRACT_BLOCKERS

1. **法务文档不存在** —— 无 `/legal` / `/terms` / `/privacy` endpoint，也无对应前端内容。
   Profile 的法务分区只能陈述事实。
2. **无密码找回契约** —— 未创建假流程（按本轮指令）。
3. **6 个 write-only 偏好字段**（`school` `learning_stage` `ai_answer_style` `answer_detail_level`
   `material_reference_preference` `daily_study_minutes`）：可写、可回显，**全后端无读取方**。
   展示为设置即等于承诺不存在的行为。
4. **邮箱 bind-once** —— `PUT /me/email/verify` 对已绑定账号返回 `EMAIL_ALREADY_BOUND`，
   无换绑能力。
5. **邮件 / 短信服务可能未配置** —— 注册依赖邮件验证码（未配置时 `503 邮件服务暂未配置`），
   手机绑定依赖短信（未配置时 `503 SMS_SERVICE_NOT_CONFIGURED`）。
   在未配置的部署上这两个流程**无法完成**；UI 显示服务端原文，不假装成功。
6. **`/subscription/plans` 的 capabilities 无中文名映射** —— 契约内不存在，故不展示。
7. **12 个依赖后端的 e2e spec 相对 auth guard 已过期**（见下）。

### 需要后续处置（本轮**未修改**，因为无法在此环境验证）
`tests/e2e/` 中面向受保护页面的用例是在**「未登录也能打开受保护页面」的旧行为**下写的：
`course-workspace`、`daily-agenda`、`f1c2b`、`f1c2c-real`、`f1c2c`、`f1c2d-r2-real-smoke`、
`f1c2d-real`、`f1c2d-supplement-real`、`f1c3-real`、`f1c4-real`、`f1c5-real`、`f1c6-state-real`、
`p3b-learning-intelligence`、`practice-null-correct-smoke`、`programming-workspace`、
`shared-learning-surfaces`（`exam-vqa` / `f1c1-vqa` 已被 `test.skip` 门控）。
它们本来就需要后端；现在额外需要一个**已登录的 harness**。
已确认存在可用的现成基础设施：`backend/scripts/e2e_serve.py`、`e2e_seed.py`、`e2e_harness.py`
与 `scripts/start-e2e-backend.sh`。**这些 spec 应迁移到该 harness，属 P7-A 之后的独立工作**。

---

## 9. 安全与工作树证据

- **NO_BACKEND_CHANGED = YES**：`find backend -newermt "2026-09-20 22:00" -name "*.py"` → **空**。
  本会话只**读取** backend 文件（endpoint / schema / 消费方审计），未写入任何 backend 文件。
- **未执行**：`reset` / `clean` / `restore` / `stash` / `checkout --` / `rebase` / `merge` / `pull` /
  `push` / `commit` / `deploy`。
- **USER_WORKTREE_PRESERVED = YES**：会话开始前已存在的全部 backend `M`、根目录未跟踪 sprint 报告与
  `.s*tmp/` scratch 目录**原样保留**；本会话未删除任何非自建文件。
  （唯一一次 `rm -rf` 尝试为清理 playwright 结果目录，**被本机策略拒绝**，随后改用 Playwright 自身覆盖。）
- 自建临时脚手架（`.tmp-patch-programming.py`、诊断 spec `zz-diag.spec.ts`、
  临时 `playwright.p7a.config.ts`）已全部删除，不在工作树留下残留。
- `frontend/dist`、`frontend/test-results`、`frontend/playwright-report` 均在 `.gitignore` 中。
- **无 API 契约变更** → **未重跑 `api:generate`**（已核验所需 endpoint 全部已在
  `src/types/api.ts` 中：`/login` `/register` `/logout` `/me` `/me/profile` `/me/password`
  `/subscription` `/subscription/plans` `/usage/summary` `/learning/agenda` `/learning-records`
  `/code/diagnose` `/code/analyze` `/programming/agent/debug` `/exam/prep/scientific/capabilities`）。
  若后续需要重跑：必须使用 **TEMP DATABASE_URL**，**禁止** `backend/app.db`。

---

## 10. 需用户裁决的声明冲突（未自行改写）

`CLAUDE.md` 与 `.claude/rules/frontend-ui.md` 声明：

> `frontend/` 目前只有 Clean-Slate 骨架与首页（`routes/`、`features/home/`）。
> 全新前端 = **NOT_STARTED**。

**工作树事实与此不符**：`frontend/src/` 现有 **173 个源文件**，包含 `routes/course/**`、
`routes/exam/**`、`routes/programming/**`、`membership`、`review`、`reports` 与
`features/{advanced,course,exam,home,learning-intelligence,membership,programming,review}`，
`types/api.ts` 为 27,775 行的已生成契约。

按 SSOT 治理规则（次级文件冲突时 SSOT wins；stale CURRENT/NEXT 段应**报告**而非自行回写），
此处**只报告**：上述两处声明是 stale claim，需你决定是修正文件还是重新定义「全新前端」的边界。
本轮工作**未**依赖该声明，也**未**恢复任何旧前端 UI 或从旧 frontend 复制页面——
所有新增代码均为本轮新写。

---

## 11. 改动的文件清单

**新增（frontend/src）**
`features/auth/api/auth.ts`、`features/auth/api/user-profile.ts`、`features/auth/query-keys.ts`、
`features/auth/session-cache.ts`、`features/auth/return-to.ts`、`features/auth/auth-context.tsx`、
`features/auth/components/{auth-layout,login-page,register-page}.tsx`、
`features/profile/api/profile.ts`、
`features/profile/components/{profile-page,profile-settings,profile-membership,profile-security}.tsx`、
`features/records/api/learning-records.ts`、`features/records/event-labels.ts`、
`features/home/{learning-status,recent-learning}.tsx`、
`components/layout/{account-menu,primary-nav}.tsx`、`components/ui/text-field.tsx`、
`lib/api/server-message.ts`、`routes/{login,register,profile}.tsx`、`test/render-app.tsx`

**新增（测试）**
`features/auth/{return-to,session-cache}.test.ts`、`features/auth/auth-guard.test.tsx`、
`features/auth/components/auth-pages.test.tsx`、`features/profile/components/profile-page.test.tsx`、
`features/home/home-page.test.tsx`、`components/layout/app-shell.test.tsx`、
`components/learning/debug-agent.test.tsx`、`tests/e2e/p7a-auth-surfaces.spec.ts`

**修改**
`routes/__root.tsx`（route guard / staticData bare layout / pendingComponent）、`router.tsx`（queryClient context）、
`main.tsx`（AuthProvider）、`components/layout/app-shell.tsx`、
`components/layout/error-state.tsx`（重试）、
`features/home/{home-page,daily-agenda,daily-agenda.test}.tsx`、
`features/programming/api/programming.ts`、`features/programming/components/programming-pages.tsx` +
其测试、`features/exam/components/{exam-foundation,exam-product-pages.render}.test.tsx`（router context）、
`test/app.test.tsx`、`tests/e2e/smoke.spec.ts`

**删除**：`features/auth/components/auth-field.tsx`（上移为 `components/ui/text-field.tsx`）
