# 240 题线上部署验收

- 部署提交：`5824b5e`
- Actions：`30710013694`，`success`
- 后端：systemd active，公网 `/api/health` 返回 200 和 `{"status":"ok"}`。
- 线上备份：`/var/lib/ai_study_platform/backups/app.db.after-catalog-240.20260802_012123.db`，476553216 bytes，`integrity_check=ok`。
- 线上真实题量：C/C++/Python/Java 均 60，总计 240；中文标题和题干缺失 0；公开/隐藏测试数量不足 0；source_key 重复 0。
- API：四语言分页总数均 60、各抽查 10 个详情；中文字段缺失 0，隐藏测试字段泄漏 0，抽样 4xx/5xx 为 0。
- 根页面 HTTP 200。

未完成项：浏览器自动化加载正式站点两次超时，因此没有宣称网页 UI 抽验全部通过；API 验收已完成。
