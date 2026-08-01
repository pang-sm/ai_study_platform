# 编程题库质量整改与线上部署验收

## 结果摘要

- 本地原启用题：800，道道判定为低质量模板并归档；C/C++/Python/Java 各 200。
- 最终线上题目记录：906；其中 rejected/inactive 800、needs_review/inactive 106，approved/active 0。
- 线上数据库与最终备份 `integrity_check` 均为 `ok`。
- 线上用户 161、学习记录 15、编程进度 1；最终部署前后未减少。

## 部署故障与修复

1. `30678986608`：旧 `--prune-unlisted` 删除了备份中的 800 条题目。已从部署前备份恢复原 ID/source_key，并全部设为 `rejected/inactive`。
2. `30679483077`：Remote disk preflight 因根分区仅约 194 MB 可用失败，Deploy 未执行。远端 Git pack 从 2.1 GiB/50 个压缩包清理为 46.67 MiB/1 个压缩包。
3. `30679593790`：删除保护、质量 quarantine、Git 存储预检均生效，部署成功。

最终部署 commit：`d48a1cd65a33684772c7213f4bb7d30ee8655c4d`。

## 线上数据库

- 最终备份：`/var/lib/ai_study_platform/backups/app.db.after-final-deploy.20260801_022342.db`
- 大小：457,658,368 bytes
- 题量：C 233、C++ 233、Python 235、Java 205（包含归档与待审核记录）
- active approved：0
- source_key 重复组：0
- rejected 题中文字段缺失：0
- rejected 题公开测试：2400，隐藏测试：4000，最少 3/5
- 公开/隐藏输入重复：0

## API 验收

- `/`：HTTP 200
- `/api/health`：HTTP 200
- 四种语言列表：HTTP 200，普通可见总数均为 0（当前无 approved 题）。
- 列表响应隐藏测试字段：0
- 归档题 `/api/programming/exercises/140`：HTTP 404

## 网页验收

直接 HTTP 可访问，但 in-app browser 对正式 IP 返回 `ERR_BLOCKED_BY_CLIENT`，因此未宣称完成卡片、Workbench、分页和 Console/Network 的视觉抽验。API smoke 已完成。

## 未完成项

- approved 题量为 0，尚未补充高质量题目；课程蓝图 32 个目标均未覆盖。
- 浏览器视觉抽验等待客户端允许访问正式 IP 后再做。
