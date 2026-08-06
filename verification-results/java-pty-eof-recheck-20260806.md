# Java PTY/EOF 回归验收（2026-08-06）

- 线上 commit：`f5d3626`
- 认证复核：passed
- 后端 health：200
- 公网代理 health：200
- 数据库 integrity_check / quick_check：ok

## Java 1546

- 5 个 Java 文件，入口 `Main.java`
- 样例输入 19 字节，EOF 已发送，PTY 自动补末尾行分隔符
- stdout：`BORROWED B42 R7 14`
- exit_code：0，未超时
- 公开测试：3/3；提交：8/8
- 切题清理：通过；隐藏/参考内容泄漏：0

## Java 1556

- 6 个 Java 文件，入口 `Main.java`
- 样例输入 19 字节，EOF 已发送，PTY 自动补末尾行分隔符
- stdout：`V1 compact 50 Han 3`
- exit_code：0，未超时；原 `-9` 不再复现
- 当前 starter 草稿公开测试：0/3；提交：0/8（真实失败，未伪报通过）
- 先前已同步正确实现的历史结果：公开 3/3；提交 8/8
- 切题清理：通过；隐藏/参考内容泄漏：0

## 根因与修复

1546/1556 的旧 `-9` 来自 PTY 输入结束链路：单行样例没有末尾换行，且 EOF 控制可能在新 WebSocket 建立前丢失。现在 CLI 等待新会话，前端排队连接中的 EOF，后端在无换行输入上先补行分隔符再发送 Ctrl+D。

敏感值、Cookie、token、用户源码、参考实现和隐藏测试未写入本报告。
