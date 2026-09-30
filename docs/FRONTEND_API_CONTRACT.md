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
| GET | `/exam/11408/subjects/{subject_key}/materials` | 科目资料库（该科目的真实上传资料，按 `<module>_11408` scope） |
| POST | `/exam/11408/subjects/{subject_key}/materials` | 上传一份资料到该科目资料库（复用统一 materials 管道） |
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
| POST | `/knowledge-path/generate-from-materials` | 从资料生成知识结构**草稿**（语义已变更，见附录 `KNOWLEDGE_STRUCTURE_VERSIONS`） |

`/knowledge-points` 现在只返回该用户 **ACTIVE 版本** 的知识点：草稿版本与已被替换的旧版本都不出现在
这个读接口里（没有版本时按「无版本的 legacy 点」处理）。见附录 `KNOWLEDGE_STRUCTURE_VERSIONS`。

### 4.5.1 用户级知识结构（course_learning，NEW）

学习者自己的、按课程划分、可版本化的知识结构。归属为 **USER + COURSE**：同一门课的两个学习者可以有
两份完全不同的结构，互不影响。所有端点都要求登录，并以 `{course_id}` 路径段 + 会话身份决定归属
（调用者没有该课程时为 404）。

| Method | Path | 用途 |
|---|---|---|
| GET | `/course-learning/courses/{course_id}/knowledge-structure` | 当前结构：active 版本、草稿版本（若有）与要展示的树 |
| POST | `/course-learning/courses/{course_id}/knowledge-structure/generate` | 生成**草稿**：`selected_materials`（自己选的文件）或 `ai_generated`（无需资料） |
| POST | `/course-learning/courses/{course_id}/knowledge-structure/{structure_id}/confirm` | 让这份草稿生效；旧版本标记为 superseded（不删除），可对应的学习进度前移 |
| DELETE | `/course-learning/courses/{course_id}/knowledge-structure/{structure_id}` | 丢弃草稿（仅草稿；active / superseded 返回 409） |
| POST | `/course-learning/courses/{course_id}/knowledge-structure/{structure_id}/points` | 在草稿的某个章节下新增知识点 |
| PATCH | `/course-learning/courses/{course_id}/knowledge-structure/{structure_id}/points/{point_id}` | 改草稿中知识点名称（`title`）或调整章节归属（`chapter_id`） |
| DELETE | `/course-learning/courses/{course_id}/knowledge-structure/{structure_id}/points/{point_id}` | 删除草稿中的知识点（非空章节返回 400） |

关键语义：

- **生成不生效**：`generate` 只写 draft。active 版本与其知识点、`user_knowledge_progress`、错题关联、
  复习安排都不受影响。只有 `confirm` 才切换 active。
- **来源可追溯**：`source_mode` = `selected_materials` \| `ai_generated`，`source_file_ids` 记录实际
  选中的资料 id；每个知识点还带 `origin` = `source_extracted`（模型指明了来源文件且该文件确实被选中）
  \| `ai_inferred`（模型自己补充的）。内部枚举不直接展示给学生。
- **进度安全**：`confirm` 时按标题把可对应知识点的学习进度前移；无法对应的旧知识点进度**保留在原版本**，
  不删除、不清零。`carry_over` 在确认前给出「有多少已学过的知识点能对上」。
- **错误码**：400（未选资料 / 目标章节不存在等输入问题）、404（课程或草稿不存在）、409（对已生效版本做
  编辑或删除、重复确认）。

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
| POST | `/code/challenges/{challenge_id}/submit` | 提交挑战（AI 判定 → 统一 AI 链路，返回真实 `request_id`；空代码 / 语言不符为确定性判定，`request_id` 为 `null`） |
| POST | `/code/challenges/{challenge_id}/explain-failure` | 解释失败原因 |
| POST | `/code/execute` | 执行代码 |
| POST | `/code/analyze` | AI 分析代码（统一 AI 链路，返回真实 `request_id`） |
| POST | `/code/diagnose` | 代码诊断（静态语法检查，**非 AI**：gcc / py_compile，无 `request_id`、不消耗 AI credits） |
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
| POST | `/chat` | 通用 AI 问答（course / exam / programming 三个分支共用统一 AI 链路，返回真实 `request_id`） |
| GET | `/chat/history` | 问答历史 |
| GET | `/chat/sessions/{session_id}` | 会话详情 |
| DELETE | `/chat/sessions/{session_id}` | 删除会话 |
| POST | `/chat/upload` | 上传文件进行 RAG 问答 |
| PUT | `/conversations/{conversation_id}` | 更新对话 |

`POST /chat` 新增两个**可选**字段（408 知识脉络 → AI 对话使用，默认 `""`，不影响既有调用方）：

- `knowledge_point_id`：本轮提问所围绕的知识点**身份**（该模块知识图发布的 code）。它进入
  `LearningContext.knowledge_point_id` 与 `ai_requests.context_json`，**不**选择能力 / 模型 / 预算。
- `knowledge_point_title`：该知识点的**名称**（页面上学习者看到的那一行）。仅用于告知模型，
  不落库、不参与任何判定 —— code 是身份，title 是给模型读的，两者不可互相替代。

### 6.2 各业务域 AI 能力（出题/解析/诊断/生成）
> 已在对应模块列出，这里集中索引：
- 考研 AI 出题：`POST /exam/11408/{subject_key}/ai-questions/generate`、`POST /exam/11408/{subject_key}/question-analysis`
- 通用出题：`POST /practice/questions/generate`、`POST /practice/questions/batch-create-from-ai`、`POST /practice/questions/{question_id}/ai-explain`
- 编程 AI：`POST /code/challenges/generate`、`POST /code/analyze`、`POST /code/learning-diagnosis`
- 编程**确定性**能力（无模型、无 request_id、不消耗 AI credits）：`POST /code/diagnose`（静态语法检查）、`POST /code/execute`、`POST /code/challenges/{challenge_id}/run-tests`
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
| PUT | `/admin/users/{target_username}/data-origin` | 设置/清除账号数据来源标记（仅超管；只能设为不进入训练集的取值，留空清除） |
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
| GET | `/exam/prep/scientific/student-twin` | 需登录 | 学习状态页的可选增强层（PREVIEW，用户可见）；unavailable / zero-event 时页面不受影响 |
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

### THREE_DOMAIN_PRODUCTIZATION_P1：三方向最小契约补齐

第一轮「三方向完整产品化」补的是**最小契约**，不重写任何既有能力。后端既有
`/course-learning/*`、`/programming/*`、`/code/*`、`/exam/prep/*` 路由全部不动。

**新增路由**（全部需登录，全部只读，除计划任务外均无写操作）：

| Method | Path | 说明 |
|---|---|---|
| GET | `/course-learning/courses/{course_id}/records` | 该课程的学习记录页（游标分页）。SQL 层同时按 `service_key=course_learning` 与事件自身 `course_id` 过滤，**在分页之前**，因此 exam_prep / programming 事件与其它课程的事件都不可能出现在这一页 |
| GET | `/course-learning/courses/{course_id}/records/summary` | 同一作用域的确定性计数（`course_id` 新增进响应体） |
| GET | `/course-learning/courses/{course_id}/wrong-answers` | 该课程的错题/待复习读取契约（`status` 过滤 active/resolved） |
| GET | `/course-learning/courses/{course_id}/wrong-answers/{wrong_record_id}` | 单条错题 + 真实作答历史（`attempt_history`）+ 已有错因分析（`error_analysis`） |
| GET | `/course-learning/courses/{course_id}/state` | 该课程的**确定性状态投影**，只读、不写、不预测 |
| GET | `/programming/records` | 编程学习记录页，SQL 层固定 `service_key=programming` |
| GET | `/programming/records/summary` | 同一作用域的计数 |
| GET | `/programming/state` | 编程的确定性状态投影，只读、不写、不预测 |
| GET | `/programming/plan` | 编程学习计划。**由统一会员档位门控**（`learning_plan`） |
| POST | `/programming/plan/tasks` | 新增计划任务（同一门控） |
| PATCH | `/programming/plan/tasks/{task_id}` | 更新计划任务（同一门控） |
| DELETE | `/programming/plan/tasks/{task_id}` | 删除计划任务（同一门控） |

语义要点（前端可依赖）：

- **课程隔离以 `course_id` 为身份而非查询参数**。`/course-learning/courses/{course_id}/...`
  的路径形态让隔离边界写在路由里；调用者没有的课程返回 **404**（不是空列表）。
- **`/course-learning/courses/{course_id}/state` 与 `/programming/state` 不产生任何预测字段。**
  没有掌握概率、没有就绪度评分、没有薄弱项排序、没有模型输出。课程侧**不接 Student Twin**。
  课程状态里的 `course.declared_level` 是学习者**自己填的**入门水平（存
  `course_learning_preferences.mastery_level`），在线上改名以免被读成实测能力。
- **编程记录带 `context.programming_language` / `context.exercise_id` / `context.project_id`。**
  `learning_events` 没有对应列，也没有为此加列：这些值走事件的 snapshot 上下文
  （见 `learning.records.native_concept.PROGRAMMING_CONTEXT_KEYS`）。
- **`RecordContext` / `RecordSummary` 新增字段（ADDITIVE）** — `programming_language` /
  `exercise_id` / `project_id`，以及 `code_run` / `code_tested` 的 `passed_count` /
  `total_count` / `exit_code` / `timed_out`。无字段被删除或改义。
- **`RecordsSummaryResponse` 新增 `course_id`（ADDITIVE）**。
- **`summary.practice_attempts` 与 `summary.programming_submissions` 是互斥计数**：
  前者只数客观题作答（`question_answered` / `course_practice`），编程提交由后者计数。
  因此一个纯编程作用域的 `practice_attempts` 合法地为 0。
- **编程学习计划复用统一会员门控**：`FEATURE_CAPABILITY["learning_plan"] → planning.generate`，
  Free 拒绝并返回标准 `FEATURE_REQUIRES_UPGRADE` 403，Standard / Advanced 允许。
  `SERVICE_FEATURES` 新增 `"programming": ("learning_plan",)`（**方向拥有哪些功能**，不是第二套会员）。
- **编程侧新增三个 canonical 事件**：`exercise_started`（每人每题去重）/
  `code_run` / `code_tested`（真实执行事实，**不携带 `correct`**）。提交与判定仍由既有
  `code_submitted` 唯一拥有，不重复发事件。

---

### THREE_DOMAIN_PRODUCTIZATION_P1_1：Course Learning 后端收口

补齐 course 工作区剩余的真实后端阻塞项：**资料上传**、**练习闭环**、**今日计划**。
全部新增路由都在 `/course-learning/courses/{course_id}/...` 之下，全部需登录。

**新增路由**：

| Method | Path | 说明 |
|---|---|---|
| GET | `/course-learning/courses/{course_id}/materials` | 该课程的资料库列表（只读） |
| POST | `/course-learning/courses/{course_id}/materials` | **上传一个文件到该课程**（multipart，仅 `file`） |
| GET | `/course-learning/courses/{course_id}/practice/workbook` | 该课程的 AI 题册（含每题自己的作答历史与 `workbook_status`） |
| GET | `/course-learning/courses/{course_id}/practice/history` | 该课程的练习历史 |
| POST | `/course-learning/courses/{course_id}/practice/questions/{question_id}/attempts` | 对**本课程**某题开启一次新作答（「下一题」/重做） |
| POST | `/course-learning/courses/{course_id}/practice/generate` | 为本课程生成一道新题并开启作答 |
| POST | `/course-learning/courses/{course_id}/practice/{attempt_id}/submit` | 提交本课程某次作答（判分 + 知识状态 + 学习记录 + 数据面事件 + practice 镜像） |
| GET | `/course-learning/courses/{course_id}/today-plan` | 本课程今日任务（只读） |

语义要点（前端可依赖）：

- **身份不由客户端提供。** 上传接口的请求体**只有文件**：没有 `username`、没有
  `subject_key`、没有 `course_id`。提交接口的请求体**只有 `answer`**，`extra="forbid"`，
  多传 `course_id` / `username` 直接 **422**。用户来自会话 cookie，课程来自路径。
- **课程身份 = `course_learning_preferences.course_id`**，也就是 `/course-learning/courses`
  返回的 `course_id`。课程作用域路径**只认这个精确字符串**，其它拼写为 404。
  课程与它其它已存拼写（如 `data_structure` ↔ `数据结构`）的对应关系只由
  `subjects.py` 的字典决定，**不做子串 / 前缀 / 模糊匹配**。
- **资料落库使用课程自身的身份**：`course_id = subject_key = subject =` 该课程 canonical key。
  **不再为课程伪造一个 subject_key**；同一课程的两个已存拼写在资料域判定里被认成同一门课
  （重复检测、存储配额、领域标签一致）。
- **上传复用既有 `/materials/upload` 管线**（配额 → 重复检测 → 存盘 → 解析 → 后台任务），
  没有第二套材料系统；`course_id` / `subject_key` / `subject` 由服务端从路径解析后注入。
- **跨课程作答被拒**：`/courses/A/practice/{attempt}/submit` 会先校验该 attempt 属于 A
  （其存储的课程身份必须是 A 的精确身份形态之一），否则 **404**，且**在判分之前**返回——
  被拒的提交不会改动任何数据。`/courses/A/practice/questions/{qid}/attempts` 同理。
- **提交写入的 canonical 事实带课程**：`practice_attempts.question_ref_json.context.course_id`
  与 `learning_events.course_id` 都是该课程（此前 live emitter 把 `course_id` 留空，
  导致真实提交在课程自己的时间线里不可见）。
- **今日计划可归属**：计划任务走共享的 `course_learning:<course>` key；通用
  `learning_tasks` 仅当其存储的 `course_id` **正好是**本课程身份形态之一时才出现，
  否则**不返回**（不做标题匹配、不猜、不回退到「当前课程」）。`today-plan` 为只读，
  不写偏好、不写排序。
- **答题前不下发答案**：题册 / 历史 / 开始作答三个响应都不含 `standard_answer` 与
  `analysis`；参考答案只在 submit 的 `result` 里返回。
- **生成受统一会员门控**：Free 对本路径返回标准 `FEATURE_REQUIRES_UPGRADE` 403
  （不做本地伪造题目降级）；Standard / Advanced 允许，`generation_mode` 会如实说明
  题目来自模型还是确定性本地兜底。
- **资料库读接口推荐用课程作用域这一个**：`/course-learning/courses/{course_id}/materials`
  按**同一门课的全部已存拼写**取资料，因此旧路径（英文 key）上传的资料也在里面。
  旧的 `GET /materials?course_id=...&subject_key=...` 仍然可用（新增：canonical 拼写不再 400），
  但它**只匹配请求里写的那一个拼写**，看不到该课程另一种拼写的资料。

### THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6：运营 / 管理契约 + 高级工作流开关

P6 **不新增任何学习功能**：它把既有高级能力变成可运营、可审计、可随时关闭的系统。
冻结清单见根目录 `THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P6_API_CONTRACT_FREEZE.md`
（21 条，含逐条 fingerprint；由 `backend/scripts/freeze_advanced_api_contract.py` 从
FastAPI 路由表直接生成，可重跑比对漂移）。

**新增路由**（全部 `require_admin_user` + 既有权限，不加新权限）：

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/admin/ai-operations/summary` | `ai_logs.view` | AI 运营总览（聚合）：请求数、成功/失败/拒绝/待结算、延迟、预估与实际 credits、capability / model / provider / tier / space 分布、fallback 数与原因码分布、反馈 up/down 与原因、degraded availability |
| GET | `/admin/workflow-operations/summary` | `ai_logs.view` | 五个高级工作流逐项聚合：调用、成功/失败、延迟、credits、**归一化**失败类别；调试智能体另报 iterations / executions |
| GET | `/admin/workflow-operations/agent-runs/{run_id}` | `ai_logs.view` | 单次调试智能体运行的**无代码**轨迹（来自既有 `learning_events` + 每步 `ai_requests` 行） |
| GET | `/admin/feature-flags` | `feature_flags.manage` | 七个高级工作流开关的当前模式 |
| PUT | `/admin/feature-flags` | `feature_flags.manage` | 设置模式（`OFF` / `INTERNAL` / `TIER` / `ALL`），**下一次请求即生效**，写入审计日志 |

**行为变化（既有高级路由）**：以下入口在功能开关关闭时**先于任何工作**返回
`403 {"detail": {"code": "feature_disabled" | "feature_internal_only", "feature", "mode"}}`：

| 开关 | 关闭后拒绝的入口 |
|---|---|
| `deep_study` | `POST /ai/deep-study` |
| `programming_agent` | `POST /programming/agent/debug` |
| `learning_report` | `POST /ai/learning-report` |
| `wrong_analysis` | `POST /wrong-answers/{state_id}/analysis` |
| `dynamic_planning` | `POST /ai/plan-adjustment`、`POST /ai/plan-adjustment/apply` |
| `adaptive_practice` | `GET /adaptive/practice` |
| `intelligent_review` | `GET /review`、`GET /review/summary`、`POST /review/schedule`、`POST /review/{item_id}/complete` |

语义要点（前端可依赖）：

- **默认是 `TIER`，未设置开关时行为与 P6 之前完全一致**（`system_settings` 中
  `feature_flag.<name>` 无行 ⇒ 一律按订阅政策判定）。
- **`INTERNAL`**：仅管理员账号可达（管理员可无付费档位演练）。
- **`ALL`**：为**该一个能力**放行 entitlement 判定（按"最低已允许档位"评估模型选择），
  **不改变**用量预算、结算与 `ai_requests.tier` 记录的真实档位；放行会记入该次调用的
  `ai_called` 审计事实（`entitlement_grant`）。
- **`OFF` 优先于一切**：即使管理员也拒绝。
- 响应 `403` 的 `detail` 是**对象**（不是字符串），前端按 `detail.code` 分支。
- 运营读接口**只返回聚合**：不含 prompt、回复正文、用户 id、用户名、request_id、
  错误正文与文件路径。

---

## 附注：清理期后端耦合点说明

- 后端 `main.py` 不托管任何前端 SPA：无 `app.mount("/", StaticFiles)`、无返回 `index.html` 的 `FileResponse`。所有 `FileResponse` 均为业务资源（头像 / 资料下载 / 资料预览 / 真题图片 / 管理备份下载）。
- CORS 仅允许 `http://localhost:5173` 与 `http://127.0.0.1:5173`（开发服务器），与新前端无关，无需改动。
- 后端无前端跳转 URL（`success_url` / `cancel_url` / `return_url` / `window.location`）耦合；支付回调为后端 webhook 端点。
- 唯一残留的前端数据文件依赖：`backend/scripts/audit_programming_exercises.py` 与 `backend/scripts/localize_all_exercism.py` 读取 `frontend/src/components/programmingExerciseCopy.js`（编程题中文文案映射），该文件在本次清理中被保留。

## ZHIXUE_PRODUCT_IA_AND_LEARNING_SURFACES_V2：会员档位价格进入契约（ADDITIVE）

**`GET /subscription/plans` 新增两个档位字段** —— `price_cents`（`int | null`）与
`duration_days`（`int | null`），来源是 `usage/service.py` 的 `UNIFIED_PLAN_PRICING`
（即 `create_pending_order` 计价所用的同一个常量）。

- **纯新增**：不删除、不改名、不改义任何已有字段；`label` / `daily_budget` /
  `weekly_budget` / `capabilities` 完全不变。
- **为什么加**：会员页要展示价格，而此前唯一的价格来源是后端常量本身。前端若自行
  写死 ¥29 / ¥149，页面就可能与订单实际收取的金额不一致 —— 这是「展示价 ≠ 结算价」
  这一类缺陷的根源。把价格放进契约后，页面显示的数字只能是订单会收的数字。
- **`null` 的含义**：`free` 档不可下单，因此没有价格。`null` 是**缺席**，不是 0；
  前端渲染为「免费」，不渲染为「¥0.00」。
- **未改动**：价格数值本身未变（standard 2900 / advanced 14900 分，30 天），
  daily / weekly 额度未变，`UNIFIED_PLAN_PRICING` 未变。成本与定价分析见根目录
  `ZHIXUE_MEMBERSHIP_COST_AUDIT.md`（该文件只给建议，未改任何预算或价格）。

**learner UI 变更（无契约影响）** —— 兑换码入口从会员页移除：该机制由管理员生成、
管理员交付，对学习者不构成可完成的路径。后端 `/subscription/redeem*` 与
`/admin/membership/redemption-codes` 端点**保留不动**。会员页新增 `/membership/payment`
路由，真实调用 `POST /subscription/orders` 与 `POST /subscription/orders/{id}/pay`；
支付未开通时如实呈现服务端 403，**不模拟支付成功**。

## ZHIXUE_V2_FINAL_FIX：自命题专业课 + 课程推荐来源（ADDITIVE）

**`GET/PUT /exam/prep/profile` 新增 `custom_subjects`（新增字段，非新增 subject）**

一个学习者**自己命名**的专业课（自命题专业课）。它是一个**独立数组**，不是 `subjects` 里的一员：

- **不进入全国统考目录。** `exam_prep.catalog` 是冻结配置（14 个科目），把自命题课加进去等于宣称第 15 个
  全国科目存在且背后有内容 —— 而它既不属于统考，也没有题库。
- **形状**：`custom_subjects: [{id: "custom_<sha1前10>", name: "<用户输入>"}]`，`id` 由**名称派生**
  （同一名称重复保存保持同一身份，深链不会因再次保存而失效），并且带 `custom_` 前缀，永远不会与目录 id 相撞。
- **写入**：`PUT` 接受 `custom_subjects: string[]`（**名称**，不是 id —— id 由服务端拥有，客户端不能指定，
  否则一个学习者就能寻址另一个人的科目）。空数组表示清空；名称去空白、去重、上限 20 条、每条 60 字。
- **不伪造内容**：没有题库、没有知识点树、没有 availability。前端对它只显示诚实空态
  「暂未内置题库，可添加资料建立自己的学习内容。」，且**不提供**「进入学习」入口。
- **存储**：`exam_prep_profiles.custom_subjects_json`（ADDITIVE 列，默认 `[]`，无回填）。
  Alembic `20260921_0014`。revision 的 `revision` / `down_revision` 采用**带注解**写法，
  与既有迁移一致 —— 迁移链的 AST 读取器只认注解赋值。

**`GET /subscription/plans` 的价格字段**（`price_cents` / `duration_days`）见上一节，本轮未再变动。

**`GET/PUT /course-learning/onboarding` 新增 `recommended_courses: string[]`（ADDITIVE）**

学习者从**智学AI推荐学习框架**里确认采纳的课程名子集。**来源必须在采纳时记录**：
推荐随专业、年级与目录变化，事后重算无法还原当时的选择，而学习者自己输入的课程从来就不是推荐。
读取时与现存 `selected_courses` **取交集**，因此被移除的课程不会留着「推荐」标记。
前端据此在 `/course` 的分 band 列表上标注哪些来自推荐框架，其余**不标注**。

---

## TASK_TYPE_CONTRACT_CLOSURE：计划任务的 `task_type` 收敛为每个学习空间唯一一套

`ExamStudyPlanTask` 是三个学习空间共用的一张表，但**各空间能拥有的任务种类不同**，因为「完成」
的判定是空间独有的。唯一权威定义：`backend/learning/spaces/plan_task_types.py`。

| 空间 | `task_type` 允许值 |
|---|---|
| `course_learning` | `knowledge` / `review` |
| `exam_prep`（11408 等） | `knowledge` / `chapter_practice` / `review` |
| `programming` | `knowledge` / `exercise` / `project` / `review` |

**三个创建入口 + 计划调整，全部校验同一套词表**：
`POST /course-learning/study-plan/tasks`、`POST /exam/11408/subjects/{k}/study-plan/tasks`、
`POST /programming/plan/tasks`，以及 `POST /ai/plan-adjustment/apply` 的 `create_task`。
不再存在第二份 hardcoded 名单。

**`practice` / `custom` 不再是合法任务类型。** 计划列表的状态由
`main._compute_task_completion` 推导，它只实现了 `knowledge` / `chapter_practice` / `review`
三个分支；其他值会永远停在「等待开始」，学习者无法完成。这两个值此前只有计划调整能写入，
现已关闭：`dropped_changes.reason = "task_type_not_supported_in_space"`。
`chapter_practice` 在课程空间仍保留**具名**拒绝（「课程学习不使用章节练习任务」），因为它是
另一个空间真实存在的类型，具名比笼统拒绝更有说明力。

`POST /ai/plan-adjustment` 的模型提示词会按目标空间给出允许值（
`prompts.plan_adjustment_system_prompt`），因此模型不会提出一个注定被拒的种类。

## PLAN_ADJUSTMENT_PRACTICALITY：计划调整变更为可审阅、可执行的调整

### `POST /ai/plan-adjustment` 的响应由「一段模型文案 + 裸字段」改为结构化建议

新增字段（原 `reason` **移除** —— 模型不再产出解释性文字）：

| 字段 | 含义 |
|---|---|
| `summary` | 一句话摘要，**由服务端从 changes 派生**（例如「把「进程调度复习」提前 5 天」） |
| `rationale` | 调整理由，**只由真实记录构成**；无可用记录时明说没有，不编造 |
| `adjustment_types` | 本次建议的语义类型集合（见下） |
| `evidence[]` | `{code, text, metric}`，每条都对应一个真实存储值，`metric` 为 0 的项**不出现** |
| `impact` | `{inserted, rescheduled, moved_earlier, moved_later, replaced, task_count_before/after, overdue_before/after, text}`，全部为**计数**，没有时长 / 掌握度 / 预测 |
| `can_apply` | 没有合法变更时为 `false`，前端不得提供「应用调整」 |

`proposed_changes[]` 的每一项同时携带**要执行的 mutation** 与**要展示的 diff**：

```
{op, task_id, due_date | title,        <- apply 会执行的字段
 type, field, task_title, before, after, direction}   <- 服务端派生
```

`type ∈ {RESCHEDULE, INSERT, REPLACE}`。`before` **由服务端从计划中读取**，客户端无法提供或篡改；
因此「展示的变更」与「应用的变更」是同一个对象，不可能分叉。

### 支持的调整语义（`semantic type ≠ database op`）

| 语义 | 底层 mutation |
|---|---|
| `RESCHEDULE` | `update_task(due_date)`（`direction` 给提前 / 推迟） |
| `INSERT` | `create_task(title, task_type, due_date)` |
| `REPLACE` | `update_task(title)` |
| `REDUCE_LOAD` | 整体判定：存在被推迟的任务 |
| `INCREASE_LOAD` | 整体判定：存在新增或被提前的任务 |

**NOT_SUPPORTED**：`REMOVE`（无 soft-delete，本轮不删任务）、`REORDER`（`ExamStudyPlanTask`
没有 `sort_order`）。两者在**服务端**被拒绝并记入 `dropped_changes.reason =
"adjustment_type_not_supported"`；前端不展示它们，也不依赖前端隐藏。

**不再可写**：`status`。标记任务完成是对**学习者已完成什么**的断言，规划模型无权作出；写进去
就是把伪造的进度写进真实计划。`update_task` 只接受 `due_date` / `title`。

**学习时长不在契约内**：`ExamStudyPlanTask` 没有 duration 字段，因此任何「预计 X 分钟」
都不可计算，也不产生。

### `POST /ai/feedback` 新增 `target_type`（ADDITIVE，默认 `answer`）

`target_type ∈ {answer, plan_adjustment}` 决定用**哪一套**封闭原因表校验：

- `answer`：原有 FROZEN 词表，**值、名称、行为完全不变**（不传 `target_type` 即为该档）。
- `plan_adjustment`：独立的计划调整词表（`adjustment_too_large` / `adjustment_too_small` /
  `unreasonable_timing` / `too_much_work` / `too_little_work` / `wrong_priority` /
  `ignored_goal_or_deadline` / `insufficient_reason` / `too_vague_to_execute` / `other`）。

跨场景原因被**服务端**拒绝（`invalid_reason`）；`target_type=plan_adjustment` 只能针对
`capability = planning.adjust` 的请求，否则 `target_capability_mismatch` —— 声明目标不能改变
被评价请求的实际能力。未知原因仍是 schema 级 422（封闭词表行为不变）。
存储无需迁移：`target_type` 进入既有 audit payload，`reason_taxonomy` 按目标选取
（answer 档与历史值逐字相同）。

## PLAN_TASK_DATED_AND_SUGGESTION_COPY：计划任务必须有日期，建议文案不再重复与计数

### `POST` / `PATCH /exam/11408/subjects/{subject_key}/study-plan/tasks` 现在要求 `due_date`

`due_date` 在 schema 里仍是可选字段（OpenAPI 未变，`api.ts` 无需重生成），但**运行时**要求
它是合法的 `YYYY-MM-DD`：

- 缺失或空串 → `400 due_date must be a YYYY-MM-DD date`
- 格式不合法 → 同上

理由：计划是日程。没有日期的任务永远不会到期、不会逾期、也不会进入「今天要做」，
只会永久留在列表里（前端此前显示为「计划日期：未设定」）。
校验在**身份校验之后**执行，未授权调用仍得到 401/403 而不是 400。

### `POST /ai/plan-adjustment` 的新增任务：日期由学习者补齐，但绝不以无日期写入

模型通常没有依据选择具体日期。**建议不被丢弃**：`proposed_changes` 里该条保留，
`due_date` 为 `null`、并带 `needs_due_date: true`，`can_apply` 仍为 `true`。
客户端必须让学习者选一个日期，并把选定的 `due_date` 随 `proposed_changes` 一起回传。

若 `POST /ai/plan-adjustment/apply` 收到仍无 `due_date` 的新增任务，该条被丢掉并记
`dropped_changes.reason = "missing_due_date"`；全部被丢掉时返回
`400 empty_proposal`。也就是说：**无日期的正式任务在任何路径上都不会被创建**，
但学习者始终看得见这条建议并知道要补什么。

（早先的实现直接在 propose 阶段丢掉这类建议，结果模型给出的建议几乎全是新增任务、
整份建议因此变空、路由返回 `empty_proposal`，AI 建议功能实际不可用。）

### `POST /ai/plan-adjustment` 的「没有可调整内容」是 200，不是 400

**触发原因（2026-09-29 生产实测）**：真实模型对「空计划」与「计划本来就正常」这两种状态
一律回答 `{"changes":[]}`。这既不是解析失败，也不是 provider 故障，而是模型对问题的回答。
旧实现把它当成错误，`propose` 抛 `empty_proposal` → HTTP **400**；前端只能把无法识别的 400
渲染成「请求暂时不可用，请稍后重试。」——一个计划本来就正常的用户被告知服务坏了，
公网验收账号（`event_count = 0`）点「生成建议」必然踩中。

新增响应字段：

| 字段 | 含义 |
|---|---|
| `outcome` | `proposed`（有可应用变更）/ `no_learning_record` / `no_change_suggested` / `suggestion_not_applicable` |
| `message` | **学习者可见的一句话**；`outcome = proposed` 时为空串 |

`outcome` 的判定全部由服务端依据**已经交给模型的那份上下文**得出，不额外查询。
判据是**计划、复习清单、练习事实**这三样——建议本身就是从这三样推出来的（`_evidence` 读的也是它们），
因此「没有可依据的记录」不可能与建议本身的口径打架。
**`recent_events` 不算**：它是给模型看的上下文，却不是「学习过」的证据，里面会积累
`plan_adjustment_proposed` 这类记账事件——把它算进来的结果是，一个什么都没学的空计划用户
得到的是「你有计划，计划无需调整」这句写给已有计划的人的话。

| `outcome` | 条件 | `message` |
|---|---|---|
| `no_learning_record` | 计划 / 复习 / 练习**全为空** | 还没有足够学习记录。你可以先添加一个学习任务。 |
| `no_change_suggested` | 有记录，但模型**没有提出任何会改变计划的变更**（包括「返回空 changes」与「把某一项改写成它现在已有的值」） | 当前计划没有需要调整的地方。 |
| `suggestion_not_applicable` | 模型提了变更，但全部是**系统无法采用的**（未知 op、不支持的类型、不属于本计划的 task_id、非法日期、空间不支持的 task_type ……） | 这次的建议里没有可以应用的内容，计划保持不变。 |

`no_change_suggested` 与 `suggestion_not_applicable` 的区别是「模型什么都没要求」与
「模型要求了系统做不到的事」。把某一项改写成它当前已有的值属于前者——它不是一次失败的
建议，只是模型没有可说的，所以学习者读到的是同一句「没有需要调整的地方」。

配套语义：

- 这三条路径的 `proposed_changes` 为 `[]`、`can_apply` 为 `false`（apply 的
  `proposed_changes` 有 `min_length=1`，因此不可能被应用）；`plan_identity` 照常返回。
- `plan_adjustment_proposed` **不再为 0 变更的建议写学习记录**（`plan_adjustment_proposed`
  是用户可见记录类型，「提出了 0 条变更」是没有信息量的一行）。
- **真正**的失败仍然是失败：解析不出 JSON 仍是 `400 unusable_proposal`；provider 不可达 /
  无可用模型仍是 502，额度不足仍是 429，权限不足仍是 403。前端必须按状态码区分
  「请求被拒绝」与「服务不可用」，只有后者才提示「服务暂时不可用，请稍后重试。」

### `POST /ai/plan-initial` — 「创建第一份计划」不是「调整计划」

**触发原因。** 空计划页面以前只提供「生成建议」（即 plan-adjustment），而 plan-adjustment 的语义是
「改我现有的计划」。空计划用户因此收到的是一个关于**不存在的计划**的回答。两者是不同的问题，
现在有两个 capability、两个提示词、两条路由；**底下的机制全部共用**
（context builder / task 词汇 / 日期规则 / entitlement / provider / settlement）。

| | `POST /ai/plan-initial` | `POST /ai/plan-adjustment` |
|---|---|---|
| capability | `planning.generate` | `planning.adjust` |
| 问题 | 「我还没有计划，给我一份」 | 「改我现有的计划」 |
| 返回 | **草稿** `tasks[]` | **差异** `proposed_changes[]` |
| 落库 | **不落库** | propose 不落库；apply 落库 |
| 结果如何生效 | 学习者经**各空间自己的 task 接口**逐条写入 | `POST /ai/plan-adjustment/apply` |
| 零学习记录 | **必须可用**（空账号正是需要第一份计划的账号） | 可用，但更可能是「没有足够记录」 |

`tasks[]` 的每一项：`{title, task_type, due_date | null, needs_due_date}`。
`due_date` 为 `null` 的项**保留**并由学习者补日期（与 plan-adjustment 的新增任务同一条规则）：
前端在任一任务缺日期时必须禁用「保存为我的计划」，不得丢弃该任务、不得自动猜日期、不得 400。

`outcome`：`proposed`（有草稿）/ `no_tasks`（模型没给出可用任务，`message` 给出一句话）。
模型返回非 JSON 时仍是 `400 unusable_proposal`；provider 不可达 502、额度 429、权限 403。

**模型看到的是真实章节结构。** context 里多两样：`syllabus`（该科目**自己的章节标题**，取自
knowledge map 与章节练习用的同一份 canonical seed）与 `today`。所以任务是按学生真正在学的科目排出来的，
不是模型对科目的想象；`syllabus` 为空时提示词也明说为空，模型退回学生自己写的目标，而不是编一份章节表。

### 提示词禁止「重复当前已有的值」

**这是建议质量问题，不是故障。** 生产实测（2026-09-29/30，`deepseek-flash`，计划内 1 条
逾期任务，5 次真实调用）：2 次给出可应用的调整，3 次把某一项的 `due_date` 或 `title`
「改写」成它现在已有的值——服务端按 `no_supported_field` 丢掉，学习者因此得到
「没有可调整的内容」。模型看不出「这不是一次调整」。

`prompts.PLAN_ADJUSTMENT_INSTRUCTION` 因此新增：

> 只有当新值与当前计划中该项的值不同、并且构成一次实际调整时，才输出这条 change。
> 重复当前计划已有的值不算调整。
> 如果没有有意义的调整，请返回 `{"changes":[]}`。不要为了必须给出建议而重复已有内容。

可比较的前提是**模型看得见现值**：`build_plan_context` 的 `plan.tasks[]` 每一项都带有它当前的
`title` / `task_type` / `status` / `due_date`，提示词显式指向这一点。

**服务端校验一条都没有放松**：`_clean_changes` 仍然逐条对照计划本身判断「是否真的变了」，
`before` 仍然从计划读出而非由调用方提供。提示词只是让模型少提无效变更，
**不是**把判断权交给模型。

### 建议文案的产品化（响应字段语义微调，字段名不变）

- `rationale`：从「依据你当前的记录：<全部证据>」改为**一句话**，取排序第一的证据文本。
  证据列表本身仍在 `evidence` 里返回，因此不再出现同一句话在页面上说两遍。
- `impact.text`：不再输出「计划任务总数由 N 项变为 M 项」。这个计数只反映当前面板里有多少任务，
  学习者看得到列表，计数帮不上判断。逾期数量仍保留，表述改为「调整后还有 N 项任务已逾期。」
  `impact` 的数值字段（`inserted` / `rescheduled` / `moved_earlier` / `moved_later` /
  `replaced` / `task_count_before` / `task_count_after` / `overdue_before` / `overdue_after`）
  全部保留不变。

## SCORE_CANONICAL：真题每题满分改为卷面真实分值（行为变化）

### `PastPaperQuestion.full_score` / `PastPaperQuestionResult.full_score` 不再固定 2 / 10

此前全站硬编码：选择题 2 分、综合应用题 10 分。真实卷面并非如此
（2022 计算机组成原理 Q43 是 15 分，操作系统两题是 7 / 8 分，计算机网络 Q47 是 9 分或 8 分）。

唯一权威 = `backend/exam_resources/11408/question_scores.json`，读取入口 =
`backend/exam_paper_scores.py`（`choice_full_score()` / `big_full_score()` / `full_score()`）。
每一道题的分值都逐题读自该题原卷截图题头；选择题的每题 2 分由 2022 年官方考试大纲交叉确认
（满分 150 = 单选 80（40 小题，每小题 2 分）+ 综合 70），卷面自证为：2022–2026 每一年
「四科选择题 80 分 + 四科大题之和 70 分」= 150 分。

所有产出或消费分值的位置都改为读该表：两个投影（bank / document）、
两条评分路径（bank 判定式评分、document 的关键词回退评分）、
AI 阅卷的评分上限（`grade_big_answer(..., max_score=...)`，prompt 与区间校验同步）。
`PastPaperAttempt.max_score` 因此不再少 5 分。

**选择题 2 分、综合应用题按卷面分值**；`question_score_audit.json` 记录 235 题逐题结论。

### `PastPaperAnswerGrade` 之外的既有一处缺陷同时修复

`replay_results` 用 `bool(raw.get("correct"))` 投影判定，把「未作答」的三态 `null`
压成了 `false` —— 提交响应把未作答的选择题报成答错（错题本与计分用的是内部三态，未受影响）。
现在 `null` 原样透出。

---

## KNOWLEDGE_STRUCTURE_VERSIONS：知识结构改为「用户级 + 可版本化」（行为变化）

### 归属：`USER + COURSE`（一直如此，本次只是补上"版本"）

知识结构本来就不是全局共享内容。`knowledge_points` 一直带 `username`，主索引是
`(username, course_id, node_key)`，生成路径也只读写调用者自己的行——用户 A 给「数据结构」生成知识点
不会影响用户 B。这次新增的不是作用域，而是**版本**。

### `/course-learning/courses/{course_id}/knowledge-structure/generate` 只写草稿

点击生成**不会**立即成为正式知识结构。后端写入一个 `draft` 版本
（`user_knowledge_structures`，含 `version` / `status` / `source_mode` / `source_file_ids`），
active 版本与其上的 `user_knowledge_progress`、错题关联、复习安排全部不动。只有
`.../{structure_id}/confirm` 才让草稿成为 active。

### `/knowledge-path/generate-from-materials` 不再是破坏性替换（BREAKING for clients that relied on it）

此前该端点会 **删除** 该课程原有知识点，并连带删除它们的 `user_knowledge_progress`、
`material_knowledge_links`——学会四个章节再换一本教材重新生成，进度会静默消失。现在它委托给同一套
草稿流程：只写 draft，旧版本原样保留，返回体仍是原来的 `path` 形状并新增结构信息。

- 原来依赖「调用后立即生效」的调用方：改为再调用 `confirm`（新前端只走新端点）。
- 已存在的数据：迁移 `20260923_0016` 为每个 `(username, course_id)` 建一个 `active` 版本并挂上其
  现有知识点，`origin` 回填为 `source_extracted`。没有删除任何行。

### `/knowledge-points` 与 `/knowledge-map` 只读 active 版本

`/knowledge-points` 增加版本过滤：只返回当前 active 版本（没有版本记录时按 legacy 无版本点处理），
草稿与被替换的旧版本不再出现在课程任意读取面上。`/knowledge-map` 的「资料补充知识点」同样只取 active。

### 未改动

真题 / 题图 / `full_score` / OCR / 学习状态 UI / Student Twin 算法 / 会员 / deploy workflow 均未触碰。
