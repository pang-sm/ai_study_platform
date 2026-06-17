"""Parse 计算机网络知识脉络整理.docx and generate seed JSON."""
import json, re, sys
from pathlib import Path
from docx import Document

DOCX = Path("C:/Users/26477/Desktop/ai_study_platform/backend/exam_resources/11408/computer_network/knowledge_map/raw/计算机网络知识脉络整理.docx")
OUT = Path("C:/Users/26477/Desktop/ai_study_platform/backend/seed_data/knowledge_maps/computer_network_11408.json")

doc = Document(str(DOCX))

# Parse paragraphs into structured tree
chapters = []
current_chapter = None
current_section = None  # 1.1 level
current_subsection = None  # 1.1.1 level

code_pattern = re.compile(r'^(第?\s*(\d+)\s*章\s+)?(\d+(?:\.\d+)*)\s+(.+)')
chapter_pattern = re.compile(r'^第?\s*(\d+)\s*章\s+(.+)')
numbered_item = re.compile(r'^(\d+)[．、.\s]+(.+)')  # 1．xxx, 2．xxx

for para in doc.paragraphs:
    text = para.text.strip()
    if not text:
        continue
    style = para.style.name if para.style else ""

    # Skip header/title lines
    if '计算机网络知识脉络' in text or 'Chapter' in text or '整理' in text:
        if not text.startswith('第') and not text[0].isdigit():
            continue

    # Match chapter (e.g., "第 1 章 计算机网络体系结构" or "第1章 ...")
    ch_match = chapter_pattern.match(text)
    if ch_match:
        ch_no = int(ch_match.group(1))
        ch_title = text.strip()
        current_chapter = {
            "code": str(ch_no),
            "title": ch_title,
            "chapter_no": ch_no,
            "children": []
        }
        chapters.append(current_chapter)
        current_section = None
        current_subsection = None
        continue

    # Strip bullet/indent prefixes like "• ", "◦ ", "- ", etc.
    clean_text = re.sub(r'^[•◦\-\*\s]+', '', text).strip()

    # Match section numbers (e.g., "1.1 计算机网络的概念" etc.)
    code_match = code_pattern.match(clean_text)
    if code_match and current_chapter:
        code = code_match.group(3)
        parts = code.split('.')
        title_part = code_match.group(4)
        full_title = f"{code} {title_part}"

        if len(parts) == 2:
            # 1.1 level
            current_section = {
                "code": code,
                "title": full_title,
                "children": []
            }
            current_chapter["children"].append(current_section)
            current_subsection = None
        elif len(parts) == 3:
            # 1.1.1 level
            current_subsection = {
                "code": code,
                "title": full_title,
                "children": []
            }
            if current_section:
                current_section["children"].append(current_subsection)
            else:
                current_chapter["children"].append(current_subsection)
        continue

    # Match numbered items (1．xxx, 2．xxx) - use clean text for detection, original text for title
    item_match = numbered_item.match(clean_text)
    if item_match:
        item_node = {
            "code": None,
            "title": text.strip(),
            "children": []
        }
        if current_subsection:
            current_subsection["children"].append(item_node)
        elif current_section:
            current_section["children"].append(item_node)
        elif current_chapter:
            current_chapter["children"].append(item_node)
        continue

    # Unmatched text - add as leaf to current context
    if clean_text and len(clean_text) > 2:
        leaf = {
            "code": None,
            "title": text.strip(),
            "children": []
        }
        if current_subsection:
            current_subsection["children"].append(leaf)
        elif current_section:
            current_section["children"].append(leaf)
        elif current_chapter:
            current_chapter["children"].append(leaf)

# Build output
output = {
    "course_id": "computer_network_11408",
    "course_name": "11408 计算机网络",
    "source": "exam_resources/11408/computer_network/knowledge_map/raw/计算机网络知识脉络整理.docx",
    "chapters": chapters
}

# Validate
all_codes = []
def collect_codes(node):
    if node.get("code"):
        all_codes.append(node["code"])
    for child in node.get("children", []):
        collect_codes(child)

for ch in chapters:
    collect_codes(ch)

# Count stats
def count_leaves(node):
    if not node.get("children"):
        return 1
    return sum(count_leaves(c) for c in node["children"])

def count_all(node):
    total = 1
    for c in node.get("children", []):
        total += count_all(c)
    return total

print(f"Chapters: {len(chapters)}")
for ch in chapters:
    nodes = count_all(ch)
    leaves = count_leaves(ch)
    print(f"  {ch['code']}: {ch['title']} - {nodes} nodes, {leaves} leaves")

dupes = [c for c in all_codes if c and all_codes.count(c) > 1]
print(f"\nTotal chapters: {len(chapters)}")
print(f"Total nodes: {sum(count_all(ch) for ch in chapters)}")
print(f"Total leaves: {sum(count_leaves(ch) for ch in chapters)}")
print(f"Duplicate codes: {len(set(dupes))}")
print(f"Codes with values: {len([c for c in all_codes if c])}")
print(f"Leaf nodes (code=null): {len([c for c in all_codes if c is None])}")

# Save
OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(output, OUT.open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nSaved to: {OUT}")
print(f"File size: {OUT.stat().st_size} bytes")
