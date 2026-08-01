# approved 120 编程题库线上部署验收

## 部署结果

- 前一次失败 run `30696899688` 的真实根因是远端根分区只剩约 194 MB，Remote disk preflight 失败。
- 本轮前端修复提交：`e1d4f78`。
- 部署 run `30698483027`：Prepare SSH、磁盘预检、后端重启、前端构建、Deploy to Tencent Cloud 全部成功。
- 本地 `npm run build` 通过。

## 线上持久数据库

- 数据库：`/var/lib/ai_study_platform/app.db`，466,731,008 bytes，`integrity_check=ok`。
- 部署前备份：`/home/ubuntu/ai_study_platform/backend/backups/app.db.before-catalog-reform.20260801_195222.db`，464,588,800 bytes，`integrity_check=ok`。
- approved 且 active：120；C/C++/Python/Java 各 30。
- 32 个课程目标均有覆盖；source_key 重复 0；非 approved 活跃题 0。
- 用户 161、学习记录 15、编程进度 1，部署前后未减少。

## API 验收

- `/` 和 `/api/health`：HTTP 200。
- 四语言列表：HTTP 200，分页总数均为 30。
- 每种语言抽查 10 个详情，共 40 个：HTTP 200，中文标题、摘要、题干、输入格式、输出格式和约束全部存在；每题 3 个公开样例。
- 列表和详情均未返回隐藏测试；公开/隐藏输入重复 0；归档或非 approved 题未出现在普通列表。

## 网页验收

- C、C++、Python、Java 各抽查 10 张题卡：中文标题和摘要正常，第一页显示 12 张、分页为 1/3，隐藏测试文本 0，横向溢出 0。
- C 和 Java Workbench 实测显示完整中文题目说明、输入格式、输出格式、约束和 3 个公开样例，隐藏测试文本 0，横向溢出 0。
- Workbench 修复文件为 `frontend/src/components/ProgrammingWorkbench.jsx` 与 `frontend/src/components/ProgrammingWorkbench.css`。
- console 未捕获应用错误；浏览器工具自身 Statsig 遥测请求偶发超时。公网 API 请求均为 200。

## 真实未完成项

- 尚未逐一打开 C++、Python 的 Workbench 视觉页面；两种语言的卡片、详情 API 和共享 Workbench 组件已验证。
- 本轮没有恢复 Exercism 或早期 pilot 题；120 道均为通过门禁的新高质量原创题，恢复来源数量为 0。

详细机器可读结果见同目录 `programming-catalog-approved-120-deployment-audit.json`。
