# Java 多文件任务暂停断点

- 状态：停车场修复和本地 12/12 审计已完成，等待提交、部署和线上验收；本轮不生成题目、不跨语言去重。
- 本地基线：`c3eae3b`。
- 当前本地数据库：60 道启用 approved Java 题，其中 12 道真实多文件题，exercise_id 为 1660–1671。
- 已有数据库备份：`backend/app.db.pre-java-multifile-20260802-214420.bak`。

## 已完成

- `8ba0303`：首轮 12 道真实 Java 多文件题并部署。
- `c3eae3b`：starter、WorkBench 文件列表、测试协议修复；Actions `30752936219` 部署成功。
- 上一轮线上 API 验收：12/12 通过，包含文件数、独立保存、编译错误文件名/行号、公开测试和提交测试、参考实现/隐藏字段隔离。
- 本轮本地 reference 已加入真实 `abstract class`、`Optional` 和 lambda，并对 12 道题重新生成 starter/reference、真实执行公开和隐藏样例；当前本地数据库已经包含这些 reference 特性。
- 当前专项审计结果：12/12 通过；停车场 `BaseFeePolicy.java` 已通过 starter/reference 相似度门禁。
- 停车场直接相似度：`BaseFeePolicy.java` 0.7465、`StandardFeePolicy.java` 0.6000、`ParkingLot.java` 0.6332；starter 只保留结构、签名和 TODO。
- 本地回归：Python compileall、`npm run build`、Workbench 代码路径检查均通过。

## 未完成

- Java 修复尚未提交、推送或部署。
- 远端磁盘、数据库完整性和线上 health 已在本次暂停中核验并通过，详见 `remote-disk-space-audit.json/.md`。
- 第三次跨语言去重任务未执行。

## 腾讯云空间处置结果

- 清理前：`/dev/vda2` 40G，已用 35G，可用 3.1G，使用率 92%。
- 清理对象：43 个已确认重复的 `/var/lib/ai_study_platform/app.db.before-programming-reconcile.202607*.db`，共 17,913,765,888 bytes；当前数据库、2026-08 备份和命名里程碑备份均保留。
- 另正常停止卡住约 4 小时、无数据库句柄的 `exciting_bouman` Java 临时容器。
- 清理后：已用 18G，可用 20G，使用率 48%；inode 使用率 8%。
- 持久数据库：`/var/lib/ai_study_platform/app.db`。
- 最近部署前备份：`/home/ubuntu/ai_study_platform/backend/backups/app.db.before-catalog-reform.20260802_231820.db`，488,058,880 bytes。
- `quick_check` 和 `integrity_check` 均为 `ok`；systemd active；内网和公网 health 均 HTTP 200。
- 用户/历史核对：users 163、code_projects 121、code_project_files 291、programming_exercise_progress 27、programming_exercise_submissions 0；approved 题仍 C/C++/Java/Python 各 60。

## 部署保护

- `.github/workflows/deploy.yml` 已加入 `<3GiB` 失败、`<5GiB` 警告、创建快照后每个受管目录保留最新 3 个自动备份、部署结束磁盘检查。
- 已提交并推送：`58f01b2 fix: add deployment disk safety guardrails`。

## 已修改文件

- `backend/scripts/repair_java_multifile_catalog.py`
- `backend/scripts/audit_java_multifile_catalog.py`
- 四份 `verification-results/java-multifile-*-audit.json/.md`
- `verification-results/java-multifile-online-acceptance.json/.md`

## 恢复条件与准确下一步

下一步执行：

1. 只提交已验证的 Java 多文件变更；
2. 推送并跟踪 Actions 部署；
3. 重新完成 12 道线上验收。

详细机器可读状态见同目录 `java-multifile-progress.json`。
