# HTTPS / Production Security Freeze 架构审计

审计时间：2026-08-10

## 当前生产入口

- 当前公开入口：`http://101.32.190.42/`
- HTTP 80：可访问，返回 `200`，Server 为 `nginx/1.18.0 (Ubuntu)`。
- `/api/health`：HTTP 返回 `200`。
- HTTPS 443：当前 TLS 握手失败/连接超时，未发现可用 HTTPS 服务。
- 正式域名：仓库和部署模板中未发现已绑定的正式域名。
- TLS certificate：仓库和部署模板中未发现证书或 Certbot 配置。

## 当前架构

| 层 | 当前情况 | 证据 |
|---|---|---|
| Nginx | 仅有 HTTP `listen 80` 模板，`server_name _` | `deploy/nginx-ai-study-platform.conf.example` |
| Frontend | Nginx 静态托管，SPA fallback 到 `index.html` | nginx 模板 `/` location |
| REST API | Nginx `/api/` 代理到 `http://127.0.0.1:8000/` | nginx 模板 |
| Backend | systemd 服务名为 `ai-backend`，部署后监听本机 8000 | `.github/workflows/deploy.yml`、backend 日志 |
| Database | systemd drop-in 使用 `/var/lib/ai_study_platform/app.db` | deploy workflow |
| WebSocket | 模板包含 Upgrade/Connection，但当前注释和配置仍是 HTTP/`ws://` 语义 | nginx 模板、`ProgrammingWorkbench.jsx` |
| API base | 前端使用同源相对路径 `API_BASE = "/api"` | `frontend/src/App.jsx` |

## 关键发现

### 1. HTTP 未强制跳转 HTTPS

当前 HTTP 首页和 API 都直接返回 200，没有 301/308 到 HTTPS。

### 2. 443/TLS 尚未上线

对 `https://101.32.190.42/` 的 TLS 请求未完成握手；当前不能进行可信 HTTPS 浏览器验收。

### 3. Cookie 尚未满足生产 HTTPS 要求

`backend/main.py` 的 `create_auth_session()` 当前设置：

- `HttpOnly=true`
- `SameSite=Lax`
- `Path=/`
- `Secure=false`

现有 HTTP storageState 也记录为 `ai_session secure=false`。这不能作为最终 HTTPS 会话来源。

### 4. 代理协议感知尚未配置

当前 nginx HTTP 模板没有 `listen 443`、TLS certificate、`X-Forwarded-Proto $scheme` 或 HTTPS server block。后端代码中也未发现已启用的代理协议处理配置。

### 5. WebSocket

`ProgrammingWorkbench.jsx` 已按页面协议动态选择 `ws`/`wss`，未发现业务代码硬编码公网 IP WebSocket 地址；但正式 HTTPS 上线仍需验证 nginx 的 WSS Upgrade、`Connection` 和长连接超时。

### 6. 安全响应头

当前 HTTP 响应未观察到 HSTS、`X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options` 等安全响应头。HSTS 应在 HTTPS 稳定并完成域名确认后再开启。

### 7. 前端硬编码审计

业务前端 API 使用相对路径；`ws://`/HTTP 公网地址残留主要位于验收脚本、开发代理和部署模板注释/HTTP 配置中。HTTPS 上线前应将验收脚本改为 `--base-url` 参数或 HTTPS 默认值，并重新生成 HTTPS storageState；不得提交 Cookie、token 或密码。

## 阻塞条件

当前只有 IP，没有可用于可信公网证书的正式域名配置。不能把自签名证书或“IP Let's Encrypt 证书”当作正式生产 HTTPS。

需要先提供并解析一个正式域名到 `101.32.190.42`，且确保 80/443 入站可达，之后才能安全实施：

1. Certbot/Let's Encrypt 可信证书
2. HTTP → HTTPS 301/308
3. HTTPS API 与 WSS 代理
4. 生产 Cookie `Secure=true`
5. HTTPS storageState、普通用户和管理员认证回归
6. Mixed Content、Workbench WebSocket、Membership/Checkout 验收

## 当前状态

- `HTTPS_PRODUCTION_NOT_VERIFIED`
- `PRODUCTION_SECURITY_FREEZE_NOT_VERIFIED`
- `HTTPS_REQUIRED_BEFORE_PRODUCTION_SECURITY_FREEZE`

本轮未修改业务源码、数据库、订单、会员或认证架构；未进行部署。
