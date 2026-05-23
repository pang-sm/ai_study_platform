import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_OCR_MODEL = "qwen-vl-ocr-2025-11-20"
DEFAULT_QWEN_PARSE_MAX_PAGES = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

DEFAULT_IMAGE_PROMPT = """请用中文解析这份学习资料图片。请输出适合进入资料库和 RAG 检索的内容：
1. 图片中能识别出的文字
2. 图表、公式、流程图或截图的含义
3. 关键知识点
4. 如果是表格，请转成 Markdown 表格
5. 如果内容不清晰，请说明不确定部分
6. 不要编造图片中不存在的信息"""


def _build_result(
    success: bool,
    extracted_text: str = "",
    warnings: list[str] | None = None,
    error: str | None = None,
):
    return {
        "success": success,
        "extract_method": "qwen",
        "extracted_text": extracted_text,
        "structured_json": {},
        "warnings": warnings or [],
        "error": error,
    }


def _get_parse_max_pages() -> int:
    raw_value = (os.getenv("QWEN_PARSE_MAX_PAGES") or "").strip()
    try:
        value = int(raw_value)
        return value if value > 0 else DEFAULT_QWEN_PARSE_MAX_PAGES
    except (TypeError, ValueError):
        return DEFAULT_QWEN_PARSE_MAX_PAGES


def get_qwen_status_payload() -> dict:
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    base_url = (os.getenv("QWEN_BASE_URL") or DEFAULT_QWEN_BASE_URL).strip()
    model = (os.getenv("QWEN_OCR_MODEL") or DEFAULT_QWEN_OCR_MODEL).strip() or DEFAULT_QWEN_OCR_MODEL
    return {
        "qwen_enabled": is_qwen_enabled(),
        "has_api_key": bool(api_key),
        "model": model,
        "base_url_configured": bool(base_url),
        "parse_max_pages": _get_parse_max_pages(),
    }


def is_qwen_enabled() -> bool:
    enabled = (os.getenv("QWEN_ENABLED") or "0").strip() == "1"
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    return bool(enabled and api_key)


def _get_qwen_client() -> OpenAI | None:
    if not is_qwen_enabled():
        return None

    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL),
    )


def _image_to_data_url(image_path: Path):
    suffix = image_path.suffix.lower()
    mime_type = IMAGE_MIME_TYPES.get(suffix)
    if not mime_type:
        return None, "仅支持 jpg、jpeg、png、webp 图片调用 Qwen 解析"

    try:
        file_bytes = image_path.read_bytes()
    except OSError:
        return None, "图片文件读取失败"

    if not file_bytes:
        return None, "图片内容为空，无法调用 Qwen 解析"

    if len(file_bytes) > MAX_IMAGE_BYTES:
        return None, "图片过大，暂不支持直接发送给 Qwen 解析"

    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}", None


def _normalize_message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]).strip())
                continue

            text_value = getattr(item, "text", None)
            if text_value:
                text_parts.append(str(text_value).strip())
        return "\n".join(part for part in text_parts if part).strip()

    return str(content or "").strip()


def parse_image_with_qwen(image_path: str, prompt: str | None = None):
    if not is_qwen_enabled():
        return _build_result(False, error="Qwen 多模态解析未启用或未配置 DASHSCOPE_API_KEY")

    image_file = Path(image_path or "")
    if not image_file.exists() or not image_file.is_file():
        return _build_result(False, error="图片文件不存在，无法调用 Qwen 解析")

    data_url, image_error = _image_to_data_url(image_file)
    if image_error:
        return _build_result(False, error=image_error)

    client = _get_qwen_client()
    if client is None:
        return _build_result(False, error="Qwen 多模态解析未启用")

    model = (os.getenv("QWEN_OCR_MODEL") or DEFAULT_QWEN_OCR_MODEL).strip() or DEFAULT_QWEN_OCR_MODEL
    final_prompt = (prompt or DEFAULT_IMAGE_PROMPT).strip() or DEFAULT_IMAGE_PROMPT

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": final_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
    except Exception:
        return _build_result(False, error="Qwen 多模态解析调用失败，请稍后重试")

    extracted_text = _normalize_message_content(
        response.choices[0].message.content if response and response.choices else ""
    )
    if not extracted_text:
        return _build_result(False, error="Qwen 已返回结果，但未提取到有效文本")

    return _build_result(True, extracted_text=extracted_text, error=None)
