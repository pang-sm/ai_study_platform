import sys, os, json
sys.path.insert(0, r"C:\Users\26477\Desktop\ai_study_platform\backend")
os.chdir(r"C:\Users\26477\Desktop\ai_study_platform\backend")
from qwen_parser import parse_image_with_qwen

img = r"static\exam_papers\11408\data_structure\2024\img_29.jpg"
print("Image exists:", os.path.exists(img))
result = parse_image_with_qwen(img, prompt="识别这道11408数据结构考研真题。提取题号、题干、ABCD选项。严格输出JSON。", timeout_seconds=30)
print("success:", result.get("success"))
raw = result.get("extracted_text","") or ""
print("raw_len:", len(raw))
print("raw[:600]:", raw[:600])
