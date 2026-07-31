# 编程题库整改进度

- 总阶段：阶段 1／5（基础设施落地）
- 当前批次：1.1
- 已完成：本地数据库备份、部署前线上备份逻辑、题目统一字段模型、SQLite 幂等补列、启用过滤、API 字段、题卡布局样式。
- 未完成：阶段 1 本地迁移与部署验收；阶段 2 中文化；阶段 3 原创题差异化；阶段 4 审计；阶段 5 浏览器验收。
- 本批修改文件：`.github/workflows/deploy.yml`、`backend/models.py`、`backend/main.py`、`frontend/src/components/ProgrammingHome.css`、审计脚本与报告。
- 本批测试：SQLite 列补齐与 API 序列化断言通过；`npm run build` 通过；Python 编译检查通过；线上 Workbench 已打开并显示统一题干字段。
- commit hash：83ba0e5
- Actions run ID：30622401955
- 部署结果：成功；Prepare SSH、Deploy to Tencent Cloud 均成功。
- 下一批准确任务：阶段 1 部署后线上冒烟；通过后进入阶段 2 第 1 批（Python Exercism 10 题）。
- 阻塞原因：独立 Playwright 无登录态，仅到达 `http://101.32.190.42/` 登录页；已有登录态的应用内浏览器在点击“题库”时连续控制超时并重置，不能安全导出其会话。需用户在独立 Playwright/浏览器登录后提供可复用 storageState，或提供已登录的可控浏览器标签。
