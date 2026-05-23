import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from qwen_parser import SCANNED_PDF_PAGE_PROMPT, get_qwen_pdf_ocr_model, parse_image_with_qwen


def get_int_env(name: str, default_value: int, min_value: int = 1) -> int:
    raw_value = (os.getenv(name) or str(default_value)).strip()
    try:
        value = int(raw_value)
        return value if value >= min_value else default_value
    except (TypeError, ValueError):
        return default_value


def get_ocr_config() -> dict:
    image_format = (os.getenv("PDF_OCR_IMAGE_FORMAT") or "jpeg").strip().lower()
    if image_format in {"jpg", "jpeg"}:
        image_format = "jpeg"
    elif image_format not in {"webp", "png"}:
        image_format = "jpeg"
    return {
        "dpi": get_int_env("PDF_OCR_RENDER_DPI", 150, 72),
        "image_format": image_format,
        "jpeg_quality": max(40, min(get_int_env("PDF_OCR_JPEG_QUALITY", 80, 1), 95)),
        "max_side": get_int_env("PDF_OCR_MAX_IMAGE_SIDE", 1600, 800),
        "concurrency": max(1, min(get_int_env("PDF_OCR_CONCURRENCY", 2, 1), 6)),
        "timeout_seconds": get_int_env("PDF_OCR_PAGE_TIMEOUT_SECONDS", 45, 5),
        "model": get_qwen_pdf_ocr_model(),
    }


def render_page(pdf_path: Path, page_index: int, config: dict) -> dict:
    started_at = time.perf_counter()
    document = fitz.open(pdf_path)
    try:
        zoom = config["dpi"] / 72
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        image.load()
        width, height = image.size
        largest_side = max(width, height)
        if largest_side > config["max_side"]:
            scale = config["max_side"] / largest_side
            width = max(1, int(width * scale))
            height = max(1, int(height * scale))
            image = image.resize((width, height), Image.Resampling.LANCZOS)

        suffix = ".jpg" if config["image_format"] == "jpeg" else f".{config['image_format']}"
        temp_file = tempfile.NamedTemporaryFile(suffix=f"_benchmark_page_{page_index + 1}{suffix}", delete=False)
        image_path = temp_file.name
        temp_file.close()
        if config["image_format"] == "jpeg":
            image.convert("RGB").save(image_path, "JPEG", quality=config["jpeg_quality"], optimize=True)
        elif config["image_format"] == "webp":
            image.convert("RGB").save(image_path, "WEBP", quality=config["jpeg_quality"], method=4)
        else:
            image.save(image_path, "PNG")
        return {
            "image_path": image_path,
            "render_seconds": time.perf_counter() - started_at,
            "image_size_bytes": Path(image_path).stat().st_size,
            "image_width": width,
            "image_height": height,
        }
    finally:
        document.close()


def ocr_page(pdf_path: Path, page_index: int, total_pages: int, config: dict) -> dict:
    started_at = time.perf_counter()
    image_path = ""
    render_info = {}
    try:
        render_info = render_page(pdf_path, page_index, config)
        image_path = render_info["image_path"]
        result = parse_image_with_qwen(
            image_path,
            prompt=SCANNED_PDF_PAGE_PROMPT,
            model=config["model"],
            timeout_seconds=config["timeout_seconds"],
        )
        success = bool(result.get("success") and (result.get("extracted_text") or "").strip())
        return {
            "page": page_index + 1,
            "total_pages": total_pages,
            "success": success,
            "error": "" if success else (result.get("error") or "OCR failed"),
            "render_seconds": render_info.get("render_seconds", 0),
            "image_size_bytes": render_info.get("image_size_bytes", 0),
            "image_width": render_info.get("image_width", 0),
            "image_height": render_info.get("image_height", 0),
            "encode_seconds": result.get("encode_seconds", 0),
            "qwen_seconds": result.get("qwen_seconds", 0),
            "total_seconds": time.perf_counter() - started_at,
            "model": result.get("model") or config["model"],
        }
    finally:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/benchmark_pdf_ocr.py <pdf_path> [pages]")
        return 2

    pdf_path = Path(sys.argv[1]).expanduser().resolve()
    max_pages = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
    config = get_ocr_config()
    document = fitz.open(pdf_path)
    try:
        total_pages = len(document)
    finally:
        document.close()

    page_count = min(total_pages, max_pages)
    started_at = time.perf_counter()
    print(
        f"[PDF_OCR_BENCH_START] file={pdf_path.name} pages={page_count}/{total_pages} "
        f"concurrency={config['concurrency']} dpi={config['dpi']} format={config['image_format']} "
        f"quality={config['jpeg_quality']} max_side={config['max_side']} model={config['model']}"
    )
    with ThreadPoolExecutor(max_workers=min(config["concurrency"], page_count)) as executor:
        futures = [executor.submit(ocr_page, pdf_path, index, total_pages, config) for index in range(page_count)]
        for future in as_completed(futures):
            item = future.result()
            print(
                f"[PDF_OCR_BENCH_PAGE] page={item['page']}/{total_pages} render={item['render_seconds']:.2f}s "
                f"image={int((item['image_size_bytes'] + 1023) / 1024)}KB size={item['image_width']}x{item['image_height']} "
                f"encode={item['encode_seconds']:.2f}s qwen={item['qwen_seconds']:.2f}s "
                f"total={item['total_seconds']:.2f}s success={item['success']} error={item['error'][:80]}"
            )
    total_seconds = time.perf_counter() - started_at
    print(
        f"[PDF_OCR_BENCH_DONE] pages={page_count} total={total_seconds:.2f}s "
        f"avg={total_seconds / max(page_count, 1):.2f}s ppm={(page_count / total_seconds * 60) if total_seconds else 0:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
