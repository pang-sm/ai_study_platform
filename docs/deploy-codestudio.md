# CodeStudio 编程助手 — 部署与环境检查

## 目录

1. [前端部署](#1-前端部署)
2. [后端服务](#2-后端服务)
3. [WebSocket 依赖](#3-websocket-依赖)
4. [Nginx WebSocket 配置](#4-nginx-websocket-配置)
5. [Docker 环境](#5-docker-环境)
6. [环境健康检查脚本](#6-环境健康检查脚本)
7. [WebSocket 线上验收](#7-websocket-线上验收)
8. [CodeStudio 功能验收](#8-codestudio-功能验收)
9. [常见故障排查](#9-常见故障排查)
10. [自动部署流程](#10-自动部署流程)

---

## 1. 前端部署

### 路径

| 项目 | 路径 |
|---|---|
| 项目根目录 | `~/ai_study_platform` |
| 前端源码 | `~/ai_study_platform/frontend` |
| 构建产物 | `~/ai_study_platform/frontend/dist` |
| Nginx 静态目录 | `/var/www/ai_study_platform` |

### 命令

```bash
cd ~/ai_study_platform/frontend
npm ci
npm run build
sudo rsync -a --delete dist/ /var/www/ai_study_platform/
```

### 验证

```bash
ls /var/www/ai_study_platform/assets/CodeStudio-*.js
curl -I http://127.0.0.1/
```

---

## 2. 后端服务

### 路径

| 项目 | 路径 |
|---|---|
| 后端源码 | `~/ai_study_platform/backend` |
| Python venv | `~/ai_study_platform/backend/.venv` |
| Python 二进制 | `~/ai_study_platform/backend/.venv/bin/python3` |
| systemd 服务 | `ai-backend` |

### 关键命令

```bash
# 语法检查
cd ~/ai_study_platform/backend
/home/ubuntu/ai_study_platform/backend/.venv/bin/python3 -m py_compile main.py schemas.py models.py database.py

# 重启服务
sudo systemctl restart ai-backend

# 查看状态
sudo systemctl status ai-backend --no-pager -l

# 实时日志
sudo journalctl -u ai-backend -f

# 最近日志
sudo journalctl -u ai-backend -n 80 --no-pager
```

---

## 3. WebSocket 依赖

CodeStudio 交互终端依赖 WebSocket。缺少依赖时的症状：

```
Unsupported upgrade request.
No supported WebSocket library detected.
```

### 检查

```bash
/home/ubuntu/ai_study_platform/backend/.venv/bin/python3 - <<'PY'
import asyncio
import websockets
print("asyncio ok")
print("websockets ok")
PY
```

### 安装

```bash
cd ~/ai_study_platform/backend
/home/ubuntu/ai_study_platform/backend/.venv/bin/pip install -r requirements.txt
```

`requirements.txt` 必须包含：

```
websockets==15.0.1
uvicorn==0.47.0
```

> 或者使用 `uvicorn[standard]` 替代 `uvicorn`，`[standard]` 包含 `websockets`。

---

## 4. Nginx WebSocket 配置

CodeStudio 交互终端使用 WebSocket 协议连接后端。Nginx 必须配置 Upgrade 头才能代理 WebSocket 连接。

### 模板

完整模板：`deploy/nginx-ai-study-platform.conf.example`

关键 location 配置：

```nginx
# CodeStudio Interactive Terminal (primary path)
location /code/interactive-run {
    proxy_pass http://127.0.0.1:8000/code/interactive-run;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}

# CodeStudio Interactive Terminal (alternate path)
location /api/code/interactive-run {
    proxy_pass http://127.0.0.1:8000/api/code/interactive-run;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

### 部署

复制模板到 Nginx 配置目录并激活：

```bash
sudo cp deploy/nginx-ai-study-platform.conf.example /etc/nginx/sites-available/ai_study_platform
# 如果之前已有配置，合并 location /code/interactive-run 和 /api/code/interactive-run 块即可
```

### 检查和重载

```bash
# 检查当前配置中是否包含 WebSocket Upgrade
sudo nginx -T | grep -n "interactive-run\|Upgrade\|proxy_http_version" -C 3

# 验证配置
sudo nginx -t

# 重载
sudo systemctl reload nginx
```

### 故障特征

| 症状 | 原因 |
|---|---|
| WebSocket 连接失败 / pending | Nginx 未配置 Upgrade |
| 404 Not Found | location 路径不匹配 |
| 502 Bad Gateway | 后端未运行或端口不对 |
| 101 Switching Protocols → 立即断开 | 后端 WebSocket handler 异常 |

---

## 5. Docker 环境

### 为什么需要 Docker

| 功能 | 需要的镜像 |
|---|---|
| C 代码运行 | `gcc:13` |
| C 语法诊断 | `gcc:13` |
| C 测试用例判定 | `gcc:13` |
| Python 代码运行 | `python:3.11-slim` |

### 检查

```bash
docker --version
docker run --rm gcc:13 gcc --version
docker run --rm python:3.11-slim python --version
```

### 安装

```bash
# 安装 Docker（Ubuntu）
sudo apt-get update
sudo apt-get install -y docker.io

# 拉取镜像
docker pull gcc:13
docker pull python:3.11-slim

# 权限
sudo usermod -aG docker ubuntu

# 注意：加入 docker 组后需要重新登录或重启服务
# 如果后端通过 systemd 以 ubuntu 用户运行：
sudo systemctl restart ai-backend
```

### 故障特征

| 症状 | 原因 |
|---|---|
| Docker permission denied | 用户不在 docker 组 |
| Image not found / pull required | 镜像未拉取 |
| No such file or directory: docker | Docker 未安装 |
| Container permission denied (/tmp) | tmpfs 路径权限问题 |

---

## 6. 环境健康检查脚本

一键检查所有 CodeStudio 依赖：

```bash
cd ~/ai_study_platform
bash scripts/check_codestudio_env.sh
```

脚本会检查：

1. 项目目录是否存在
2. Python venv 是否可用
3. websockets 依赖是否安装
4. Docker 是否可用
5. gcc:13 / python:3.11-slim 镜像是否存在
6. ai-backend 服务是否运行
7. Nginx 配置是否有效
8. WebSocket Upgrade 是否已配置
9. 静态文件是否已部署
10. HTTP 端点是否可达

> 脚本**只读检查**，不修改服务器状态。

---

## 7. WebSocket 线上验收

### 验证步骤

1. 浏览器打开 `http://101.32.190.42`
2. 进入 CodeStudio / 编程助手
3. 打开 DevTools → Network → WS 标签
4. 点击「▶ 运行」按钮

### 成功标准

- 出现请求 `/code/interactive-run`
- 状态：`101 Switching Protocols`
- Messages 标签中出现 JSON 消息

---

## 8. CodeStudio 功能验收

### Python input 测试

```python
a, b = map(int, input().split())
print(a + b)
```

输入：
```
3 5
```

预期输出：
```
8
Process finished with exit code 0
```

### C scanf 测试

```c
#include <stdio.h>
int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\n", a + b);
    return 0;
}
```

输入：
```
3 5
```

预期输出：
```
8
Process finished with exit code 0
```

### Stop 测试

```python
while True:
    pass
```

点击 Stop，验证：

- 终端显示「用户终止运行」
- `docker ps` 不残留容器
- `ps aux | grep python` 不残留进程
- 再次点击 Rerun 能正常运行

---

## 9. 常见故障排查

### A. WebSocket 连接失败

**症状**：终端显示「WebSocket 连接失败」

**排查**：
1. Network → WS 标签，检查请求状态
2. `sudo nginx -T | grep interactive-run` 确认 Nginx 配置
3. `sudo journalctl -u ai-backend -f` 看后端日志
4. 确认 `websockets` 依赖已安装
5. 确认后端 `@app.websocket` 路由存在

### B. No supported WebSocket library detected

**处理**：
```bash
cd ~/ai_study_platform/backend
/home/ubuntu/ai_study_platform/backend/.venv/bin/pip install -r requirements.txt
sudo systemctl restart ai-backend
```

### C. /code/interactive-run 404

**排查**：
1. 前端 console 检查实际 WS URL
2. 后端代码确认 `@app.websocket("/code/interactive-run")` 存在
3. Nginx `location /code/interactive-run` 是否正确代理

### D. Docker permission denied

**处理**：
```bash
sudo usermod -aG docker ubuntu
sudo systemctl restart ai-backend
```

### E. C 诊断不可用

**检查**：
```bash
docker run --rm gcc:13 gcc --version
```

### F. C 诊断提示「诊断服务异常」

本地开发环境没有 Docker 时，后端会 fallback 到基础 regex 诊断。确保线上有 Docker。

### G. 后端 502 Bad Gateway

**排查**：
```bash
sudo systemctl status ai-backend
sudo journalctl -u ai-backend -n 50 --no-pager
```

---

## 10. 自动部署流程

GitHub Actions 在 `main` 分支 push 时自动触发（`.github/workflows/deploy.yml`）。

### 故障排查

| 症状 | 可能原因 |
|---|---|
| Prepare SSH 失败 | `TENCENT_HOST` 或 `TENCENT_SSH_KEY` secret 为空 |
| npm ci 失败 | `package-lock.json` 和 `package.json` 不同步 |
| rsync 未执行 | 服务器构建失败，旧 dist 被保留 |
| 部署成功但页面未更新 | 浏览器缓存旧 index.html（Ctrl+Shift+R 强刷） |

### 手动部署

如果自动部署失败，SSH 到服务器手动执行：

```bash
cd ~/ai_study_platform
git fetch origin main
git reset --hard origin/main

cd frontend
npm ci
npm run build
sudo rsync -a --delete dist/ /var/www/ai_study_platform/

cd ~/ai_study_platform/backend
/home/ubuntu/ai_study_platform/backend/.venv/bin/python3 -m py_compile main.py schemas.py models.py database.py

sudo systemctl restart ai-backend
sudo nginx -t && sudo systemctl reload nginx
```
