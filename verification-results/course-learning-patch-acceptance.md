# 第一轮业务补丁验收报告

## 结论

本地业务闭环已验证通过，正式环境部署与正式网页验收尚未完成，因此整体状态为 `partially_verified`，不能报告为最终完成。

## 课程目录

课程学习目录原有 17 门，本轮保留 17 门，隐藏 0 门。审计依据是：17 门课程均存在对应的 `backend/seed_data/knowledge_maps/*.json`，并且复用同一套课程主页、资料库、知识脉络、AI 对话、学习计划、章节练习和报告组件。叶子知识点数量最低为 C++ 课程的 28 个；没有发现只有名称、没有知识脉络上下文的课程。资料为空是用户数据状态，不作为课程空壳判定。

## 已实现与本地网页验证

| 模块 | 结果 | 证据 |
| --- | --- | --- |
| 课程章节练习 | 通过 | 课程主页 → 章节练习 → 选择知识点 → 生成 → 作答 → 解析 → 刷新后历史记录恢复 |
| 资料到知识脉络 | 通过 | 资料库选择已索引 PDF → AI 预览 4 个模块/20 个知识点 → 确认 → 知识脉络出现“资料补充知识点” |
| 学习报告 | 通过 | 生成、保存、刷新、历史列表、详情恢复均成功 |
| 11408 空数据 | 通过 | 无学习记录时显示“暂无数据”，不显示固定百分比或默认天数 |
| 编程首页空数据 | 通过 | 无活动时显示“暂无学习记录”，不伪造连续学习和任务完成 |

## API 与数据闭环

课程练习使用独立的 `/course-learning/practice/*` API，绑定 `course_id`、章节、知识点和可访问资料摘要；生成接口不返回答案和解析，提交接口判题并保存 `AIGeneratedQuestion`、`AIQuestionAttempt`、`LearningRecord`、`UserKnowledgeProgress`。

资料闭环为：上传/索引 → `/materials/analyze-knowledge-preview` → 用户预览 → `/materials/confirm-knowledge-tree` → 按用户和课程写入并去重 → `/knowledge-map` 读取。确认接口不会覆盖已有知识点。

报告复用 `/learning/reports/save`、列表和详情 API 以及既有 `LearningReport` 模型，没有新增第二套报告存储系统。

AI 返回统一的 `generation_mode`，前端区分 `ai` 与 `fallback`；fallback 不伪装为模型成功。

## 检查结果

- `py -3 -m compileall -q backend`：通过。
- `npm run build --prefix frontend`：通过；仅有既有 chunk size warning。
- `GET http://127.0.0.1:8000/api/health`：200。
- `GET http://127.0.0.1:5173/`：200。
- `py -3 -m pytest backend/tests -q`：未通过，原因是仓库不存在 `backend/tests` 目录，未发现可执行后端测试。
- 浏览器 Console：未发现本地应用错误；Browser runtime 有一次外部 Statsig telemetry 超时，不属于应用请求。

## 未完成项

1. 本轮改动尚未 commit/push。
2. 尚未完成正式环境备份、部署和 health check。
3. 尚未在正式网页逐项重复课程练习、资料确认、报告持久化、11408 空状态和编程提交前后 streak 对比。
4. 尚未建立后端自动化测试目录；当前证据来自本地 API/数据库和真实浏览器操作。
