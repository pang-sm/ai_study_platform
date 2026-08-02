# 腾讯云系统盘空间安全审计

- 主机：`101.32.190.42`
- 持久数据库：`/var/lib/ai_study_platform/app.db`

## 结果

| 项目 | 清理前 | 清理后 |
|---|---:|---:|
| 系统盘可用空间 | 3.1G | 20G |
| 使用率 | 92% | 48% |
| inode 使用率 | 8% | 8% |

删除了 43 个已逐一列出并确认非保留项的 2026-07 重复 reconcile 备份，共 17,913,765,888 bytes。当前数据库和命名里程碑备份未删除；没有创建新数据库备份。

`exciting_bouman` 是运行约 4 小时、无数据库句柄的卡住 Java 临时容器，已使用正常 `docker stop` 停止。当前 Python 执行器容器未触碰。

## 数据库与服务

- `PRAGMA quick_check`：`ok`
- `PRAGMA integrity_check`：`ok`
- systemd `ai-backend`：`active`
- `http://127.0.0.1:8000/api/health`：HTTP 200
- `http://101.32.190.42/api/health`：HTTP 200
- users：163
- code_projects：121
- code_project_files：291
- programming_exercise_progress：27
- programming_exercise_submissions：0
- approved：C 60、C++ 60、Java 60、Python 60

## 保护策略

`.github/workflows/deploy.yml` 已在 `58f01b2` 中加入部署前/后的空间检查：低于 3GiB 失败，低于 5GiB 警告；自动快照按目录保留最新 3 个，其他命名的里程碑备份不清理。
