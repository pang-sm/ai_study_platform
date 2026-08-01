# 480 题库部署验收报告

## 部署

- Commit：`f8e63e56626cea5cf0095d7ddb020d4e61a95e22`
- Actions：`30704970093`，`Deploy to Tencent Cloud=success`
- Prepare SSH、远端磁盘预检、Git bundle、source archive 均成功。
- 部署流程使用已验证的 `programming_catalog_480.json.gz`，先备份并执行 SQLite 完整性检查，再初始化 schema 和幂等 seed；第二次 seed 的本地验证为 `written=0`。

## 线上数据库

- 持久库：`/var/lib/ai_study_platform/app.db`，473,321,472 bytes。
- 部署备份：`/home/ubuntu/ai_study_platform/backend/backups/app.db.before-catalog-reform.20260801_230151.db`，468,865,024 bytes。
- `integrity_check=ok`，`ai-backend=active/enabled`，本机 health=200。
- C/C++/Python/Java：各 120；approved active 总计 480；source_key 重复 0；active rejected 0。
- 用户 161；编程进度 1；编程提交记录 0（未删除任何记录，线上真实当前值如此）。

## 线上 API 与网页

- `http://101.32.190.42/` 与 `/api/health` 均为 200。
- 四语言列表 API 均为 120，分页为 `48,48,24`。
- 四语言各抽查 10 道详情：中文标题、摘要、题干、输入输出格式和约束均存在；每题 3 个公开样例；隐藏测试泄漏 0。
- 列表 source_key 重复 0，归档/rejected 题未出现在普通列表。
- 浏览器四语言各抽查页面显示中文题卡和摘要，无横向溢出、不显示隐藏测试。

## 未完成项

当前浏览器会话进入 Workbench 后显示“未选择练习”，因此登录后具体题目的完整题干/样例交互抽验未完成；这不影响已完成的线上 API、数据库、部署和列表页验收。
