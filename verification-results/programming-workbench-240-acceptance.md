# 240 题 Workbench 验收

## 结果

- 题库全量审计：240/240 通过；C、C++、Python、Java 各 60。
- SQLite `integrity_check`：`ok`。
- 每题 3 个公开测试、5 个隐藏测试；starter 与 reference 完全相同：0。
- Python 公开测试：3/3；完整提交：8/8。提交结果只展示汇总与公开 case，未展示隐藏输入、标准输出或 reference。

## 本轮修复

首次点击 C 题“运行”时，Uvicorn 日志显示缺少 WebSocket 库：`Unsupported upgrade request`、`No supported WebSocket library detected`，原始握手返回 404。按现有 `backend/requirements.txt` 安装 `websockets==15.0.1` 并重启后，握手返回 101。

`backend/main.py` 的交互终端现在以 Docker 为首选；本机没有 Docker 时，C/C++ 使用 gcc/g++，Python 使用当前虚拟环境，Java 使用 javac/java，均继续通过相同的状态、stdin/stdout、EOF、stderr 与退出码协议传输。

## 浏览器抽验

地址：`http://127.0.0.1:5173/`

每种语言抽查 5 道，共 20 道。所有抽查题都显示中文背景知识、完整中文题干、输入输出格式、约束、3 个公开样例及样例解释；starter 为可读 scaffold，不含完整 reference。

- C：终端连接、编译启动、退出码 0。
- C++：终端连接、编译启动、退出码 0。
- Python：终端连接、发送 EOF、退出码 0。
- Java：验证 `DomainModel.java` 与 `Main.java` 多文件 starter；终端连接、发送 EOF、退出码 0。

截图：[workbench-local-240-python-terminal.png](/C:/Users/26477/Desktop/ai_study_platform/verification-screenshots/workbench-local-240-python-terminal.png)

浏览器控制台未发现 error/warn；API 列表和详情核对均为 200，四种语言总数各 60、分页返回 48。详情 API 未返回 hidden/reference 字段。

## 验证命令

- `backend/.venv/Scripts/python.exe -m py_compile ...`：通过。
- `frontend/npm run build`：通过，仅有既有大 chunk warning。
- `backend/scripts/audit_programming_catalog_240_workbench.py`：已有最终报告 240/240 通过；本轮交互终端补丁通过浏览器、WebSocket 101、四语言 API 和终端退出码验收。

## 未完成项

本报告对应本地验收；线上数据库备份、提交推送、Actions 部署和公网验收将在本轮 commit 后继续执行。
