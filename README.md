# AI Learning Assistant

## 部署注意事项

如果线上通过 Nginx 代理前端和后端，文件上传功能需要允许 10MB 请求体。
请在对应的 `server` 或 `http` 配置中设置：

```nginx
client_max_body_size 10M;
```

修改 Nginx 配置后需要检查并重载配置，例如：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 图片 OCR 部署要求

图片上传问答使用 Python 依赖 `pillow` 和 `pytesseract`，并依赖服务器系统中的 Tesseract OCR。

Ubuntu 服务器需要安装：

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim
```

安装后可用以下命令验证：

```bash
tesseract --version
tesseract --list-langs
```

图片和 PDF 上传仍需要 Nginx 允许 10MB 请求体：

```nginx
client_max_body_size 10M;
```

一个基于 FastAPI 的 AI 学习助手项目。

## 功能

- AI 对话
- 课程切换
- Markdown 渲染
- 聊天记录

## 技术栈

- Python
- FastAPI
- HTML
- CSS
- JavaScript

## 启动项目

```bash
uvicorn main:app --reload
```

## 作者

逄森淼
