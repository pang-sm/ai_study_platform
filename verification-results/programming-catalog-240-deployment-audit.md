# 240 道跨语言题库部署验收

## 部署

- Commit：`359cba99957e97261844f57d541672af42fdb370`
- Actions：`30817287283`，结论 `success`
- 报告同步 Actions：`30818488019`，结论 `success`
- SSH、Git 更新、数据库备份、schema 初始化、240 题幂等 seed、后端重启、前端发布和 health check 均通过。

## 线上真实数据库

- 数据库：`/var/lib/ai_study_platform/app.db`
- `quick_check=ok`，`integrity_check=ok`
- 最新备份：`/home/ubuntu/ai_study_platform/backend/backups/app.db.before-catalog-reform.20260803_213440.db`，`502300672` bytes
- 磁盘：可用约 21GB，使用率 47%，inode 使用率 8%
- approved：C 60、C++ 60、Python 60、Java 60，共 240
- source_key 重复 0，active rejected 0，中文标题/题干缺失 0
- 公开测试少于 3 的题 0，隐藏测试少于 5 的题 0
- 用户与历史数据当前计数：users 164、code_projects 134、code_project_files 358、programming_exercise_progress 39、programming_exercise_submissions 0

## API 与页面

- 四语言列表 API 均返回 60 道，`page_size=48` 时各为 2 页。
- 列表和详情抽查的中文字段完整；每种语言抽查 5 个详情，共 20 个。
- API 未发现 `reference_solution`、`reference_files`、`hidden_tests`、`hidden_cases` 或 `hidden_test_files` 泄漏。
- Java Workbench 页面视觉抽验确认 6 个可编辑文件、中文题干、3 个公开样例且未显示隐藏测试。
- C 与 Python 题库页面视觉抽验确认各 60 道、5 页和中文题卡。

## 未完成项

浏览器语言切换到 C++/Java 的动作超时，未完成这两种语言的页面视觉抽验；API 抽验已通过。此外，页面暴露出部分题卡仍采用“边界保护/状态转移/反例处理”的重复变体标题和通用摘要。自动相似度审计通过不能替代人工级内容整改，这部分应作为下一轮题目内容重写任务处理。
