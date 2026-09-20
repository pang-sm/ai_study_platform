# 智学平台 — 后端 API 契约盘点

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文档是 **2026-09-10 的只读快照（LEGACY CURRENT）**，从属于 SSOT；冲突时 SSOT wins。
> API 的处置分类以 SSOT §56.3 的冻结矩阵为准。
>
> **⚠️ 本文档记录的会员模型是旧体系，不是目标架构。**
> 目标会员架构（FROZEN，SSOT §4 / §5 / §67）是统一的 `Free / Standard / Advanced`
> + `Subscription → Capability Permission → Usage Budget → Model / Workflow Router`。
> **禁止**把本文档描述的「三个服务方向各自独立会员」当作未来设计延续。

> 本文档由「前端全量重构前清理」生成，用于新前端架构设计参考。
> 生成时间：2026-09-10。后端 API 未做任何修改，仅做盘点。
> 路由总数：**352**（`@app.get/post/put/delete/patch/websocket`）；
> SSOT §39 / §56.3 的分类口径为 **351 business HTTP endpoint**（+2 WebSocket +4 framework）。

## 全局约定

- **认证方式**：Session Cookie 认证（`ai_session` cookie），登录/注册后由后端 `Set-Cookie`。
- **认证依赖**：`get_current_user`（需登录）、`require_admin_user` / `require_admin_permission`（管理员）。
- **会员模型（CURRENT = 旧体系，目标见上）**：三个服务方向 `exam_11408` / `course_learning` / `programming`，各自有 `free / monthly / quarterly / full` 套餐，独立开通与续期。SSOT §41 明确此结构为 legacy，统一会员 `Unified Subscription = MISSING`（目标）。
- **公开接口**（无需登录）：`/register`、`/auth/register/send-code`、`/auth/register/verify-code`、`/login`、`/auth/email-login*`、`/health`、`/api/health`、`/settings/public`、`/shared/reports/{token}`、`/announcements/active`、`/payments/callback/{provider}`。
- **响应结构**：成功大多返回 JSON（`{"message": "...", ...}` 或领域对象）；错误返回 `{"detail": "..."}`。
- **服务前缀**：Nginx 将 `/api/*` 反向代理到后端 `127.0.0.1:8000/*`；Vite 开发代理 `/api` → 后端并去掉 `/api` 前缀。后端本身路由多数不带 `/api` 前缀。

---

## 1. Authentication（认证与会话）

| Method | Path | 用途 |
|---|---|---|
| POST | `/auth/register/send-code` | 注册第一步：向邮箱发送验证码（校验邮箱格式 + 未注册 + 60s 限频） |
| POST | `/auth/register/verify-code` | 注册第一步：校验验证码并签发邮箱验证凭证 cookie（`zhixue_register_email_proof`） |
| POST | `/register` | 注册第二步（`username` + `password` + 已验证 `email`），要求先完成邮箱验证；成功后建立会话，`email_verified=true` |
| POST | `/login` | 登录（`username` 字段可填账号或已验证邮箱 + `password`），返回 `user`/`profile` |
| POST | `/logout` | 退出登录，撤销会话并清除 cookie |
| POST | `/auth/email-login/send-code` | 发送邮箱登录验证码（仅限已绑定并验证的邮箱，未注册邮箱不自动注册） |
| POST | `/auth/email-login` | 邮箱验证码登录 |
| POST | `/admin/login` | 已废弃（返回 410，提示改用 `/login`） |

---

## 2. 用户（资料 / 学习方向 / 配置 / 会员状态）

| Method | Path | 用途 |
|---|---|---|
| POST | `/me` | 当前用户完整状态（profile + tracks + active_track_type + 三方向 service_plans/配额） |
| GET | `/me/profile` | 获取个人资料 |
| PUT | `/me/profile` | 更新个人资料（昵称/年级/专业等） |
| GET | `/me/tracks` | 用户学习方向列表 |
| POST | `/me/onboarding` | 完成引导（昵称/年级/专业/学期/方向/套餐） |
| PUT | `/me/tracks/exam_408/package` | 升级 408 方向套餐 |
| GET | `/me/guides` | 首次引导状态 |
| POST | `/me/guides/{service_key}/complete` | 标记某方向引导完成 |
| POST | `/me/avatar` | 上传头像 |
| GET | `/me/avatar/{filename}` | 获取头像文件 |
| DELETE | `/me/avatar` | 删除头像 |
| POST | `/me/email/send-code` | 发送邮箱绑定验证码 |
| PUT | `/me/email/verify` | 验证绑定邮箱 |
| POST | `/me/phone/send-code` | 发送手机绑定验证码 |
| POST | `/me/phone/verify` | 验证绑定手机 |
| POST | `/me/phone/change/send-code` | 换绑手机发送验证码 |
| POST | `/me/phone/change/verify` | 换绑手机验证 |
| PUT | `/me/password` | 修改密码 |
| GET | `/me/quota` | 当前用户配额（AI 用量/资料额度等） |
| GET | `/course-preferences` | 获取课程偏好 |
| POST | `/course-preferences` | 保存课程偏好 |
| GET | `/course-progress` | 获取课程进度 |
| PATCH | `/course-progress` | 更新课程进度 |

---

## 3. 考研（11408 真题 / 题库 / 章节练习 / 知识点 / 学习计划）

### 3.1 408 院校与目标
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam-408/schools` | 院校搜索列表 |
| PUT | `/exam-408/target-school` | 设置目标院校 |
| PUT | `/exam-408/motto` | 设置座右铭 |
| PUT | `/exam-408/exam-info` | 设置考试信息 |

### 3.2 学习计划（11408）
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam/11408/study-plan/summary` | 学习计划汇总 |
| GET | `/exam/11408/study-plan/tasks/summary` | 计划任务汇总 |
| GET | `/exam/11408/subjects/{subject_key}/dashboard-summary` | 科目仪表盘汇总 |
| GET | `/exam/11408/subjects/{subject_key}/study-plan` | 科目学习计划 |
| POST | `/exam/11408/subjects/{subject_key}/study-plan/tasks` | 创建计划任务 |
| PATCH | `/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}` | 更新任务 |
| DELETE | `/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}` | 删除任务 |
| PATCH | `/exam/11408/subjects/{subject_key}/study-plan/settings` | 计划设置 |
| PATCH | `/exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{node_code:path}` | 章节练习节点进度 |
| PATCH | `/exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code:path}` | 知识点条目进度 |

> `subject_key` 取值：`data_structure`（数据结构）、`computer_organization`（计算机组成原理）、`operating_system`（操作系统）、`computer_network`（计算机网络）。

### 3.3 章节练习
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam/11408/{subject_key}/chapter-practice/outline` | 章节练习大纲 |
| GET | `/exam/11408/{subject_key}/chapter-practice/questions` | 章节练习题目 |
| POST | `/exam/11408/{subject_key}/chapter-practice/attempts` | 开始章节练习 |
| POST | `/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/answers` | 提交单题答案 |
| POST | `/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit` | 交卷 |
| GET | `/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}` | 练习详情 |
| GET | `/exam/11408/{subject_key}/chapter/analytics` | 章节分析 |

### 3.4 真题
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam/11408/{subject_key}/past-papers` | 历年真题列表 |
| GET | `/exam/11408/{subject_key}/past-paper-questions` | 真题题目 |
| POST | `/exam/11408/{subject_key}/past-paper-attempts` | 开始真题作答 |
| POST | `/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers` | 提交单题答案 |
| POST | `/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit` | 交卷 |
| GET | `/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}` | 真题作答详情 |
| GET | `/exam/11408/past-paper-images/{subject_key}/{year}/{filename:path}` | 真题图片资源 |

### 3.5 题库 / 错题 / 收藏 / 统计
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam/11408/{subject_key}/question-bank/questions` | 题库题目列表 |
| POST | `/exam/11408/{subject_key}/question-bank/questions` | 新增题目 |
| GET | `/exam/11408/{subject_key}/question-bank/stats` | 题库统计 |
| GET | `/exam/11408/{subject_key}/wrong-questions` | 错题列表 |
| POST | `/exam/11408/{subject_key}/question-analysis` | 题目 AI 解析 |
| PATCH | `/exam/11408/{subject_key}/wrong-questions/{wrong_id}/mastered` | 标记错题已掌握 |
| DELETE | `/exam/11408/{subject_key}/wrong-questions/{wrong_id}` | 删除错题 |
| GET | `/exam/11408/{subject_key}/favorites` | 收藏题目列表 |
| POST | `/exam/11408/{subject_key}/favorites` | 收藏题目 |
| DELETE | `/exam/11408/{subject_key}/favorites/{favorite_id}` | 取消收藏 |
| GET | `/exam/11408/{subject_key}/done-records` | 完成记录 |
| GET | `/exam/11408/{subject_key}/practice/stats` | 练习统计 |

### 3.6 考研 AI 问答
| Method | Path | 用途 |
|---|---|---|
| GET | `/exam/11408/{subject_key}/ai-questions` | AI 题目列表 |
| POST | `/exam/11408/{subject_key}/ai-questions/generate` | 生成 AI 题目 |
| GET | `/exam/11408/{subject_key}/ai-questions/groups` | AI 题目分组 |
| POST | `/exam/11408/{subject_key}/ai-questions/attempts` | 开始 AI 题目作答 |
| POST | `/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}/answers` | 提交答案 |
| POST | `/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}/submit` | 交卷 |
| GET | `/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}` | 作答详情 |
| GET | `/exam/11408/{subject_key}/ai-questions/{question_id}/raw-response` | AI 原始响应 |
| PATCH | `/exam/11408/{subject_key}/ai-questions/{question_id}` | 更新 AI 题目 |
| DELETE | `/exam/11408/{subject_key}/ai-questions/{question_id}` | 删除 AI 题目 |

---

## 4. 课程学习（课程 / 资料 / 知识脉络 / 学习记录）

### 4.1 课程与引导
| Method | Path | 用途 |
|---|---|---|
| GET | `/course-learning/courses` | 课程列表 |
| GET | `/course-learning/entitlements` | 课程权益 |
| GET | `/course-learning/packages` | 套餐 |
| GET | `/course-learning/status` | 状态 |
| GET | `/course-learning/onboarding` | 获取引导状态 |
| POST | `/course-learning/onboarding` | 完成引导 |
| POST | `/course-learning/register` | 注册课程学习方向 |
| GET | `/course-learning/exam-scope` | 获取考试范围 |
| PUT | `/course-learning/exam-scope` | 设置考试范围 |
| GET | `/course-learning/exam-scope/knowledge-points` | 考试范围知识点 |
| GET | `/course-learning/exam-settings` | 考试设置 |
| POST | `/course-learning/exam-settings` | 保存考试设置 |
| PATCH | `/course-learning/courses/{course_id}/settings` | 课程设置 |

### 4.2 学习计划
| Method | Path | 用途 |
|---|---|---|
| GET | `/course-learning/study-plan` | 学习计划 |
| POST | `/course-learning/study-plan/tasks` | 创建计划任务 |
| PATCH | `/course-learning/study-plan/tasks/{task_id}` | 更新任务 |
| DELETE | `/course-learning/study-plan/tasks/{task_id}` | 删除任务 |
| GET | `/course-learning/today-plan` | 今日计划 |
| PATCH | `/course-learning/today-plan/order` | 今日计划排序 |

### 4.3 练习
| Method | Path | 用途 |
|---|---|---|
| GET | `/course-learning/practice/workbook` | 练习本 |
| GET | `/course-learning/practice/workbook/{question_id}` | 练习详情 |
| POST | `/course-learning/practice/generate` | 生成练习 |
| POST | `/course-learning/practice/workbook/{question_id}/attempts` | 开始练习 |
| POST | `/course-learning/practice/{attempt_id}/submit` | 提交练习 |
| GET | `/course-learning/practice/history` | 练习历史 |

### 4.4 资料库
| Method | Path | 用途 |
|---|---|---|
| GET | `/materials` | 资料列表 |
| GET | `/materials/search` | 资料搜索 |
| POST | `/materials/upload` | 上传资料（multipart，触发解析） |
| GET | `/materials/{material_id}` | 资料详情 |
| GET | `/materials/{material_id}/download` | 下载原文件 |
| GET | `/materials/{material_id}/preview` | 网页内预览 |
| GET | `/materials/{material_id}/status` | 解析状态 |
| POST | `/materials/{material_id}/reparse` | 重新解析 |
| DELETE | `/materials/{material_id}` | 删除资料 |
| POST | `/materials/reindex` | 重建检索索引 |
| POST | `/materials/add-from-message` | 从 AI 消息沉淀为资料 |
| POST | `/materials/analyze-knowledge-preview` | 资料知识点分析预览 |
| POST | `/materials/confirm-knowledge-tree` | 确认知识点树 |
| GET | `/materials/{material_id}/knowledge-links` | 知识点关联列表 |
| POST | `/materials/{material_id}/knowledge-links` | 添加知识点关联 |
| POST | `/materials/{material_id}/knowledge-links/apply` | 应用关联 |
| POST | `/materials/{material_id}/knowledge-links/recommend` | 推荐关联 |
| DELETE | `/materials/{material_id}/knowledge-links/{link_id}` | 删除关联 |

### 4.5 知识脉络 / 图谱
| Method | Path | 用途 |
|---|---|---|
| GET | `/knowledge-map` | 知识图谱 |
| GET | `/knowledge-map/review-settings` | 复习设置 |
| PATCH | `/knowledge-map/progress` | 图谱进度 |
| PATCH | `/knowledge-map/review-settings` | 更新复习设置 |
| GET | `/knowledge-base/dashboard` | 知识库仪表盘 |
| GET | `/knowledge-points` | 知识点列表 |
| POST | `/knowledge-points` | 创建知识点 |
| POST | `/knowledge-points/generate-preview` | 生成知识点预览 |
| POST | `/knowledge-points/import-generated` | 导入生成的知识点 |
| PUT | `/knowledge-points/{point_id}` | 更新知识点 |
| DELETE | `/knowledge-points/{point_id}` | 删除知识点 |
| GET | `/knowledge-points/{point_id}/progress-events` | 知识点进度事件 |
| PUT | `/knowledge-points/{point_id}/progress` | 更新知识点进度 |
| POST | `/knowledge-path/generate-from-materials` | 从资料生成学习路径 |

### 4.6 学习记录 / 报告 / 计划
| Method | Path | 用途 |
|---|---|---|
| GET | `/learning/dashboard` | 学习仪表盘 |
| GET | `/learning/tasks` | 学习任务列表 |
| POST | `/learning/tasks` | 创建学习任务 |
| POST | `/learning/tasks/from-diagnosis` | 从诊断生成任务 |
| POST | `/learning/tasks/reorder` | 任务排序 |
| PUT | `/learning/tasks/reorder` | 任务排序（PUT） |
| PUT | `/learning/tasks/{task_id}` | 更新任务 |
| DELETE | `/learning/tasks/{task_id}` | 删除任务 |
| GET | `/learning/tasks/summary` | 任务汇总 |
| POST | `/learning/plans/generate-preview` | 生成学习计划预览 |
| POST | `/learning/plans/generate-preview-advanced` | 高级计划预览 |
| POST | `/learning/plans/import-tasks` | 导入计划任务 |
| GET | `/learning/report` | 学习报告（概览） |
| GET | `/learning/reports` | 报告列表 |
| POST | `/learning/reports/generate-preview` | 生成报告预览 |
| POST | `/learning/reports/save` | 保存报告 |
| GET | `/learning/reports/{report_id}` | 报告详情 |
| DELETE | `/learning/reports/{report_id}` | 删除报告 |
| GET | `/learning/reports/{report_id}/export/markdown` | 导出 Markdown |
| GET | `/learning/reports/{report_id}/export/text` | 导出文本 |
| POST | `/learning/reports/{report_id}/share` | 分享报告 |
| GET | `/learning/reports/{report_id}/share` | 分享状态 |
| DELETE | `/learning/reports/{report_id}/share` | 取消分享 |
| GET | `/learning/practice/stats` | 练习统计 |
| GET | `/learning-records` | 学习记录列表 |
| POST | `/learning-records` | 创建学习记录 |
| GET | `/learning-records/stats` | 学习记录统计 |
| PATCH | `/learning-records/{record_id}` | 更新记录 |
| DELETE | `/learning-records/{record_id}` | 删除记录 |
| POST | `/learning-records/{record_id}/reviewed` | 标记已复习 |
| POST | `/learning-report/ai-generate` | AI 生成学习报告 |
| GET | `/course-dashboard` | 课程仪表盘 |
| GET | `/review/center` | 复习中心 |
| POST | `/review/tasks/create` | 创建复习任务 |

### 4.7 通用练习中心（`/practice`）
| Method | Path | 用途 |
|---|---|---|
| GET | `/practice/summary` | 练习汇总 |
| GET | `/practice/papers` | 试卷列表 |
| GET | `/practice/papers/{paper_id}` | 试卷详情 |
| DELETE | `/practice/papers/{paper_id}` | 删除试卷 |
| GET | `/practice/questions` | 练习题列表 |
| GET | `/practice/questions/{question_id}` | 题目详情 |
| POST | `/practice/questions` | 创建题目 |
| PUT | `/practice/questions/{question_id}` | 更新题目 |
| DELETE | `/practice/questions/{question_id}` | 删除题目 |
| POST | `/practice/questions/generate` | AI 生成题目 |
| POST | `/practice/questions/batch-create-from-ai` | AI 批量创建题目 |
| POST | `/practice/questions/{question_id}/ai-explain` | AI 讲解题目 |
| POST | `/practice/questions/{question_id}/attempts` | 提交作答 |
| GET | `/practice/questions/{question_id}/attempts` | 作答记录 |
| POST | `/practice/questions/{question_id}/feedback` | 作答反馈 |
| POST | `/practice/submit-result` | 提交练习结果 |
| POST | `/practice/generate-task-preview` | 生成任务预览 |
| POST | `/practice/import-paper/parse` | 解析导入试卷 |
| POST | `/practice/import-paper/jobs` | 创建导入任务 |
| POST | `/practice/import-paper/confirm` | 确认导入 |
| GET | `/practice/import-paper/jobs/{job_id}` | 导入任务状态 |

---

## 5. 编程学习（编程档案 / 题目 / 代码提交 / AI 反馈）

### 5.1 编程方向
| Method | Path | 用途 |
|---|---|---|
| GET | `/programming/onboarding` | 获取编程引导状态 |
| POST | `/programming/onboarding` | 完成编程引导 |
| GET | `/programming/packages` | 套餐 |
| GET | `/programming/entitlements` | 权益 |
| GET | `/programming/home` | 编程主页 |
| GET | `/programming/file-library` | 文件库 |
| GET | `/programming/exercises` | 编程题目列表 |
| GET | `/programming/exercises/{exercise_id}` | 题目详情 |
| POST | `/programming/exercises/{exercise_id}/start` | 开始练习 |
| POST | `/programming/exercises/{exercise_id}/run` | 运行代码 |
| POST | `/programming/exercises/{exercise_id}/samples/run` | 运行示例用例 |
| POST | `/programming/exercises/{exercise_id}/test` | 运行测试 |
| POST | `/programming/exercises/{exercise_id}/submit` | 提交代码 |
| WEBSOCKET | `/programming/exercises/{exercise_id}/interactive` | 交互式运行 |

### 5.2 代码工作台 / AI 教练（`/code`）
| Method | Path | 用途 |
|---|---|---|
| GET | `/code/progress` | 编程学习进度 |
| GET | `/code/challenges/{challenge_id}` | 挑战详情 |
| POST | `/code/challenges/generate` | AI 出题 |
| POST | `/code/challenges/{challenge_id}/generate-tests` | 生成测试 |
| POST | `/code/challenges/{challenge_id}/run-tests` | 运行测试 |
| POST | `/code/challenges/{challenge_id}/submit` | 提交挑战 |
| POST | `/code/challenges/{challenge_id}/explain-failure` | 解释失败原因 |
| POST | `/code/execute` | 执行代码 |
| POST | `/code/analyze` | AI 分析代码 |
| POST | `/code/diagnose` | AI 诊断 |
| POST | `/code/learning-diagnosis` | 学习诊断 |
| GET | `/code/attempts` | 提交尝试记录 |
| GET | `/code/attempts/{attempt_id}` | 尝试详情 |
| PUT | `/code/attempts/{attempt_id}/mastered` | 标记掌握 |
| GET | `/code/sessions` | 代码会话列表 |
| POST | `/code/sessions` | 创建会话 |
| GET | `/code/sessions/{session_id}` | 会话详情 |
| PUT | `/code/sessions/{session_id}` | 更新会话 |
| DELETE | `/code/sessions/{session_id}` | 删除会话 |
| GET | `/code/sessions/{session_id}/messages` | 会话消息 |
| DELETE | `/code/sessions/{session_id}/messages` | 清空消息 |
| GET | `/code/projects` | 项目列表 |
| POST | `/code/projects` | 创建项目 |
| GET | `/code/projects/{project_id}` | 项目详情 |
| PUT | `/code/projects/{project_id}` | 更新项目 |
| DELETE | `/code/projects/{project_id}` | 删除项目 |
| POST | `/code/projects/{project_id}/execute` | 执行项目 |
| POST | `/code/projects/{project_id}/files` | 创建项目文件 |
| PUT | `/code/projects/{project_id}/files/{file_id}` | 更新项目文件 |
| DELETE | `/code/projects/{project_id}/files/{file_id}` | 删除项目文件 |
| GET | `/code/ai-coach/saved-chats` | AI 教练已存对话 |
| POST | `/code/ai-coach/saved-chats` | 保存对话 |
| DELETE | `/code/ai-coach/saved-chats/{saved_id}` | 删除对话 |
| WEBSOCKET | `/code/interactive-run` | 交互式运行（WebSocket） |

---

## 6. AI 能力（问答 / RAG / OCR / 文件解析 / 出题 / 用量）

### 6.1 通用 AI 问答
| Method | Path | 用途 |
|---|---|---|
| POST | `/chat` | 通用 AI 问答 |
| GET | `/chat/history` | 问答历史 |
| GET | `/chat/sessions/{session_id}` | 会话详情 |
| DELETE | `/chat/sessions/{session_id}` | 删除会话 |
| POST | `/chat/upload` | 上传文件进行 RAG 问答 |
| PUT | `/conversations/{conversation_id}` | 更新对话 |

### 6.2 各业务域 AI 能力（出题/解析/诊断/生成）
> 已在对应模块列出，这里集中索引：
- 考研 AI 出题：`POST /exam/11408/{subject_key}/ai-questions/generate`、`POST /exam/11408/{subject_key}/question-analysis`
- 通用出题：`POST /practice/questions/generate`、`POST /practice/questions/batch-create-from-ai`、`POST /practice/questions/{question_id}/ai-explain`
- 编程 AI：`POST /code/challenges/generate`、`POST /code/analyze`、`POST /code/diagnose`、`POST /code/learning-diagnosis`
- 资料解析/知识：`POST /materials/upload`（触发 OCR/解析）、`POST /materials/analyze-knowledge-preview`、`POST /materials/{material_id}/reparse`、`POST /materials/reindex`
- 知识点生成：`POST /knowledge-points/generate-preview`、`POST /knowledge-path/generate-from-materials`
- 计划/报告生成：`POST /learning/plans/generate-preview`、`POST /learning/plans/generate-preview-advanced`、`POST /learning/reports/generate-preview`、`POST /learning-report/ai-generate`

### 6.3 用量 / 配额 / 模型
| Method | Path | 用途 |
|---|---|---|
| GET | `/me/quota` | 当前用户 AI/资料配额 |
| GET | `/debug/qwen-status` | Qwen OCR/模型服务状态（调试） |

> 模型调用：DeepSeek（对话/生成）+ DashScope/Qwen（OCR，`qwen-vl-ocr`）。RAG 检索与 OCR 为后端内部能力，通过 `/chat/upload`、`/materials/upload` 等接口触发，无独立前端路由。

---

## 7. 商业系统（会员 / 套餐 / 订单 / 支付 / 兑换）

| Method | Path | 用途 |
|---|---|---|
| GET | `/membership/plans` | 套餐列表 |
| GET | `/membership/catalog` | 会员目录 |
| GET | `/membership/summary` | 会员汇总 |
| GET | `/membership/entitlements` | 会员权益 |
| GET | `/membership/orders` | 我的订单 |
| POST | `/membership/orders` | 创建订单 |
| GET | `/membership/orders/{order_id}` | 订单详情 |
| POST | `/membership/orders/{order_id}/pay` | 发起支付 |
| POST | `/membership/orders/{order_id}/cancel` | 取消订单 |
| POST | `/membership/orders/{order_id}/refund` | 退款 |
| GET | `/membership/recommendation` | 套餐推荐 |
| POST | `/membership/recommendation/manual` | 手动触发推荐 |
| GET | `/membership/reminders` | 到期提醒 |
| POST | `/membership/redeem` | 兑换码兑换 |
| POST | `/membership/redeem/preview` | 兑换码预览 |
| POST | `/payments/callback/{provider_name}` | 支付服务商回调（webhook） |

> 支付 provider 位于 `backend/payments/`（base / mock / registry / service）。当前为 mock provider，`/payments/callback` 仅对 mock 返回 404。订单/退款/兑换统一写 ledger。

---

## 8. 管理后台（`/admin/*`，全部需管理员权限）

### 8.1 总览 / 统计
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/dashboard` | 仪表盘 |
| GET | `/admin/dashboard-v1` | 仪表盘 v1 |
| GET | `/admin/statistics` | 统计 |
| GET | `/admin/usage-summary` | 用量汇总 |
| GET | `/admin/usage-trend` | 用量趋势 |
| GET | `/admin/operations-dashboard` | 运维仪表盘 |
| GET | `/admin/system-health` | 系统健康 |
| GET | `/admin/me/permissions` | 当前管理员权限 |

### 8.2 用户管理
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/users` | 用户列表 |
| POST | `/admin/users/batch` | 批量操作 |
| GET | `/admin/users/{target_username}/detail` | 用户详情 |
| PUT | `/admin/users/{target_username}/status` | 启用/禁用 |
| PUT | `/admin/users/{target_username}/admin-role` | 设置管理员角色 |
| POST | `/admin/users/{target_username}/plan` | 设置用户套餐 |
| POST | `/admin/users/{user_id}/ban` | 封禁用户 |
| POST | `/admin/users/{user_id}/unban` | 解封用户 |
| DELETE | `/admin/users/{user_id}` | 删除用户 |
| GET | `/admin/admins` | 管理员列表 |
| POST | `/admin/admins` | 新增管理员 |
| PUT | `/admin/admins/{user_id}/status` | 管理员状态 |

### 8.3 会员 / 订单 / 兑换码
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/memberships` | 会员列表 |
| GET | `/admin/memberships/catalog` | 会员目录 |
| PATCH | `/admin/users/{user_id}/memberships` | 修改会员 |
| GET | `/admin/orders` | 订单列表 |
| GET | `/admin/orders/{order_id}` | 订单详情 |
| POST | `/admin/orders/{order_id}/cancel` | 取消订单 |
| POST | `/admin/orders/{order_id}/refund` | 退款 |
| GET | `/admin/membership/redemption-codes` | 兑换码列表 |
| POST | `/admin/membership/redemption-codes` | 生成兑换码 |
| GET | `/admin/membership/redemption-codes/{code_id}` | 兑换码详情 |
| POST | `/admin/membership/redemption-codes/{code_id}/revoke` | 撤销兑换码 |

### 8.4 内容 / 题库 / 资料 / 课程
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/materials` | 资料列表 |
| POST | `/admin/materials/{material_id}/reindex` | 重建资料索引 |
| GET | `/admin/material-issues` | 资料解析问题 |
| GET | `/admin/courses` | 课程列表 |
| GET | `/admin/courses-summary` | 课程汇总 |
| GET | `/admin/practice` | 练习管理 |
| GET | `/admin/tasks` | 任务管理 |

### 8.5 配额 / 配置 / 公告
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/quota` | 配额列表 |
| GET | `/admin/quota/{user_id}` | 用户配额 |
| PUT | `/admin/quota/{user_id}/override` | 覆盖配额 |
| DELETE | `/admin/quota/{user_id}/override` | 删除配额覆盖 |
| GET | `/admin/model-config` | 模型配置 |
| PUT | `/admin/model-config` | 更新模型配置 |
| GET | `/admin/settings` | 系统设置 |
| PUT | `/admin/settings` | 更新系统设置 |
| GET | `/admin/announcements` | 公告列表 |
| POST | `/admin/announcements` | 创建公告 |
| PUT | `/admin/announcements/{a_id}` | 更新公告 |
| PATCH | `/admin/announcements/{a_id}` | 部分更新公告 |
| PUT | `/admin/announcements/{a_id}/status` | 公告状态 |
| POST | `/admin/announcements/{a_id}/withdraw` | 撤回公告 |
| DELETE | `/admin/announcements/{a_id}` | 删除公告 |

### 8.6 日志 / 审计 / 备份 / 工单
| Method | Path | 用途 |
|---|---|---|
| GET | `/admin/ai-logs` | AI 调用日志 |
| GET | `/admin/ai-logs/export` | 导出 AI 日志 |
| GET | `/admin/audit-logs` | 审计日志 |
| GET | `/admin/audit-logs/export` | 导出审计日志 |
| GET | `/admin/logs` | 日志列表 |
| GET | `/admin/backups` | 备份列表 |
| POST | `/admin/backups` | 创建备份 |
| DELETE | `/admin/backups/{filename}` | 删除备份 |
| GET | `/admin/backups/{filename}/download` | 下载备份 |
| GET | `/admin/support/tickets` | 工单列表 |
| GET | `/admin/support/tickets/{ticket_id}` | 工单详情 |
| PATCH | `/admin/support/tickets/{ticket_id}/status` | 工单状态 |
| POST | `/admin/support/tickets/{ticket_id}/messages` | 工单回复 |
| POST | `/admin/support/tickets/{ticket_id}/read` | 标记已读 |
| GET | `/admin/support/unread-count` | 未读工单数 |
| GET | `/admin/report-shares` | 报告分享管理 |
| PUT | `/admin/report-shares/{share_id}/status` | 分享状态 |

---

## 9. 其他（公共 / 用户侧支持 / 分享）

| Method | Path | 用途 |
|---|---|---|
| GET | `/` | 根路径（后端健康/占位） |
| GET | `/health` | 健康检查 |
| GET | `/api/health` | 健康检查（带前缀） |
| GET | `/home/summary` | 首页汇总 |
| GET | `/search/global` | 全局搜索 |
| GET | `/settings/public` | 公开设置 |
| GET | `/announcements/active` | 生效公告 |
| GET | `/announcements/unread` | 未读公告 |
| POST | `/announcements/{a_id}/read` | 标记公告已读 |
| GET | `/support/tickets` | 我的工单 |
| POST | `/support/tickets` | 创建工单 |
| GET | `/support/tickets/{ticket_id}` | 工单详情 |
| POST | `/support/tickets/{ticket_id}/messages` | 工单回复 |
| POST | `/support/tickets/{ticket_id}/confirm-resolution` | 确认解决 |
| POST | `/support/tickets/{ticket_id}/read` | 标记已读 |
| GET | `/support/unread-count` | 未读工单数 |
| GET | `/shared/reports/{share_token}` | 公开分享报告（免登录） |

---

## 附注：快照之后新增的路由（DELTA，不是快照的一部分）

上面正文是 **2026-09-10 的只读盘点**。下表只登记该日期之后新增的路由，**不回写快照正文**——
快照的价值在于它记录了那一天的真实状态，改写它等于伪造历史。

| Method | Path | 认证 | 说明 |
|---|---|---|---|
| GET | `/exam/prep/scientific/student-twin` | 需登录 | 学习状态实验视图（PREVIEW，用户可见） |
| GET | `/exam/prep/scientific/learner-state` | 需登录 | learner_state 能力门报告（SHADOW_NOT_USER_VISIBLE，不产出数值） |
| GET | `/exam/prep/scientific/evidence-reliability` | 需登录 | evidence_reliability 能力门报告（SHADOW_NOT_USER_VISIBLE，不产出数值） |
| GET | `/exam/prep/scientific/capabilities` | 需登录 | 13 个科学组件的产品面就绪度汇总 |
| GET | `/exam/prep/scientific/kt-dataset-audit` | 需登录 | CS408-native KT 数据集契约健康度（不含任何数据行） |
| GET | `/science/status` | **仅管理员** | 科学能力与模型执行证明（ACCEL_PRODUCT_S8 PART 10/11）。非学习者页面：普通用户 403、未登录 401；不含任何逐用户字段、不含文件系统路径/原始 prompt/密钥。`?probe_runtime=true` 才探测运行时，默认 `reachable=null`（= 未探测，与 `false` 不同） |
| POST | `/practice/sessions`、`/practice/sessions/{id}/attempts` 等 | 需登录 | 统一 Practice Core（STEP 7D）；`attempts` 的 payload 自 S5 起接受 `telemetry` 对象 |
| — | `/v1/inference/*` | — | Scientific Runtime Service，**不是** Product Backend 路由，前端不可达 |

### S8：`/exam/prep/scientific/capabilities` 的响应形状变化（ADDITIVE）

ACCEL_PRODUCT_S8 为该响应新增字段，**全部为新增，无字段被删除或改义**：

- `components[]` 新增 `runtime_available` / `scientifically_compatible` /
  `product_input_ready`（S5 就已在这三个维度上判断，但响应模型没有声明它们，
  因而被 FastAPI **静默丢弃**——HTTP body 里一直看不到。S8 补上声明）与
  `category` / `category_reason`（冻结的四分类：
  `USER_VISIBLE` / `SHADOW_COLLECTING_DATA` / `RESEARCH_ONLY` /
  `RETIRED_FROM_PRODUCT_ROADMAP`）。
- 顶层新增 `category_meaning`（四分类语义；刻意**不**放进 `terminology`，以免
  把那个 `str -> str` 的扁平映射撑成嵌套结构）。
- 顶层新增 `product_native_capabilities[]`（产品自建能力，**不属于** SSOT §36 的
  13 个科学组件，因此单独成块，避免被误读为第 14 个组件）。
- `totals` 新增 `by_category`。
- `components` 仍然是 **13 项**，未增未减。

`POST /practice/sessions/{id}/attempts` 的 `telemetry` 为可选对象，字段
`duration_ms` / `duration_source` / `hint_count` / `hint_source` / `attempt_index`。
`duration_source = UNAVAILABLE` 时不得携带 `duration_ms`（400）；`hint_source` 非
`COUNTED` 时不得携带 `hint_count`（400）。响应新增 `response_time_source` /
`attempt_index` 两个可空字段。旧的 `response_time_ms` 仍照常接受。

---

### S9：章节练习的**规范概念身份**（ADDITIVE + 一个语义收紧）

ACCEL_PRODUCT_S9 让「从规范知识叶子进入章节练习」这条路径把**已知的**规范
`knowledge_point_id` 带进 attempt / learning event / 数据集导出。概念**从不推断**：
不从标题、不从路径文本、不从数组下标、不从题干。

**读取路径（ADDITIVE）** — `GET /exam/11408/{subject_key}/chapter-practice/questions`
新增查询参数 `concept_code`：

- 它只接受该模块的**规范叶子 code**（知识地图 seed 发布的那一个字符串）。
  不是规范叶子的 id → **422**（不是「返回空列表」：空列表是「本知识点没有题」，
  与「这不是一个知识点」是两回事）。
- 它与既有的 `knowledge_point_id`（legacy 练习子分组过滤）**是两个不同的参数**，
  后者语义未变。
- 是规范叶子但没有题 → 200 且 `total = 0`（诚实，例如 `computer_network` 第 4 章
  撞位叶子）。

**写入路径（语义收紧，**不是**新增字段）** —
`POST /exam/11408/{subject_key}/chapter-practice/attempts` 的 `knowledge_point_id`
从「任意字符串照单全收」改为**校验后接受**。非空时必须同时满足：

1. 该模块发布了知识地图 seed；
2. 该值是该模块的规范叶子 code；
3. 所选题目全部属于该模块；
4. 所选题目全部携带该概念（与读取路径**同一个**判定函数）。

任一条不成立 → **422**，`detail` 为
`{code, message, concept_code, subject_key, ...}`；`code ∈
{CONCEPT_NOT_CANONICAL_LEAF_OF_MODULE, CONCEPT_QUESTION_MODULE_MISMATCH,
CONCEPT_QUESTION_SET_MISMATCH}`。**该值从不被改写、不被就近匹配**。

留空/NULL 仍然合法，且是直接入口、真题、legacy attempt 的诚实编码 —— 这三种情况
本来就没有已知的规范概念。

**兼容性说明（会破坏旧调用方的地方）**：此前客户端可以对**任意**题目集合声明
**任意** `knowledge_point_id`，服务端原样落库并带进 learning event。该行为现在会
422。真实前端此前从不发送该字段，所以这条收紧影响的是「本来就会往事件里写一个
伪造概念」的调用。`BC5A` 契约测试中那一条（整章题目 + 概念 1.1）已按新契约更新，
原意图（响应形状具体）不变。

**运行时响应形状变化（一处）** — `GET /usage/summary` 的 `periods.<daily|weekly>`
现在**恒定**返回四个键 `budget` / `reserved` / `settled` / `remaining`：
无额度上限的档位此前只返回 `budget` 与 `remaining`，导致同一个端点按值返回两种
不同形状的对象。变化是**纯新增**（原先缺失的两个键现在为 `null`），
不删除、不改义任何已有键。

**新增响应模型（绑定既有运行时形状，未改任何响应体）** —
`GET /subscription`、`GET /subscription/plans`、`GET /usage/summary`、
`POST /membership/redeem`、`POST /membership/redeem/preview`
此前返回裸 `dict`，OpenAPI 里是 `{}`，前端拿不到任何类型。S9 为它们声明了
响应模型，字段逐一取自真实运行时 payload，**响应体不变**，只是现在被契约固定。

**`GET /science/status` 新增 `data_collection`（ADDITIVE）** — 采集就绪度的事实量：
`users_with_events` / `users_with_eligible_interactions` / `eligible_interactions` /
`concept_level_interactions` / `module_level_interactions` /
`non_canonical_concept_ids` / `events_scanned` / `collection_start_version`，
以及 `uncollected_fields`（`response_time_ms = NOT_COLLECTED`、
`hint_count = NOT_AVAILABLE`，`coverage` 为 `null`）。无任何逐用户标识。
未传入 db 会话时 `measured = false` 且**不出现**计数键 —— 没数过与数到 0 不同。

---

## 附注：清理期后端耦合点说明

- 后端 `main.py` 不托管任何前端 SPA：无 `app.mount("/", StaticFiles)`、无返回 `index.html` 的 `FileResponse`。所有 `FileResponse` 均为业务资源（头像 / 资料下载 / 资料预览 / 真题图片 / 管理备份下载）。
- CORS 仅允许 `http://localhost:5173` 与 `http://127.0.0.1:5173`（开发服务器），与新前端无关，无需改动。
- 后端无前端跳转 URL（`success_url` / `cancel_url` / `return_url` / `window.location`）耦合；支付回调为后端 webhook 端点。
- 唯一残留的前端数据文件依赖：`backend/scripts/audit_programming_exercises.py` 与 `backend/scripts/localize_all_exercism.py` 读取 `frontend/src/components/programmingExerciseCopy.js`（编程题中文文案映射），该文件在本次清理中被保留。
