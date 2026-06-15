"""
11408 exam paper parser.

Reads docx files from backend/exam_resources/11408/{subject_key}/ and
extracts structured question data.  Most questions are embedded as images
inside the docx, so we also export images and attempt OCR when available.
"""
import json
import logging
import os
import re
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT

logger = logging.getLogger("exam_parser")

BASE_DIR = Path(__file__).resolve().parent
EXAM_RESOURCES_DIR = BASE_DIR / "exam_resources" / "11408"
CACHE_DIR = BASE_DIR / "cache" / "exam_parser"

# Subject key → directory name mapping (same as main.py)
EXAM_SUBJECT_DIRS = {
    "data_structure": "数据结构",
    "computer_organization": "计算机组成原理",
    "operating_system": "操作系统",
    "computer_network": "计算机网络",
}


def _subject_dir(subject_key: str) -> Path:
    return EXAM_RESOURCES_DIR / subject_key


def _cache_path(subject_key: str) -> Path:
    p = CACHE_DIR / subject_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def _find_docx(subject_key: str) -> Path | None:
    """Return the first .docx file in the subject directory, or None."""
    sd = _subject_dir(subject_key)
    if not sd.exists():
        return None
    docx_files = sorted(sd.glob("*.docx"))
    return docx_files[0] if docx_files else None


def _export_images(doc: Document, subject_key: str) -> dict[str, str]:
    """Export all images embedded in the document.

    Returns a mapping from paragraph index → saved image path.
    """
    image_map: dict[str, str] = {}
    cache = _cache_path(subject_key)
    for i, rel in enumerate(doc.part.rels.values()):
        if "image" not in rel.reltype:
            continue
        image = rel.target_part
        ext = os.path.splitext(image.partname)[1] or ".png"
        fname = f"img_{i}{ext}"
        fpath = cache / fname
        if not fpath.exists():
            fpath.write_bytes(image.blob)
        image_map[f"rel_{i}"] = str(fpath)
    # Also map by paragraph index by scanning runs
    para_image_map: dict[str, str] = {}
    img_idx = 0
    for pi, para in enumerate(doc.paragraphs):
        for run in para.runs:
            for elem in run._element:
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag in ("drawing", "pict"):
                    fname = f"img_{img_idx}.png"
                    fpath = cache / fname
                    if fpath.exists():
                        para_image_map[str(pi)] = str(fpath)
                    img_idx += 1
    return para_image_map


def _try_ocr_image(image_path: str) -> str | None:
    """Try OCR on a single image using available OCR tools.

    Returns extracted text or None if OCR is unavailable."""
    try:
        from qwen_parser import parse_image_with_qwen
        result = parse_image_with_qwen(image_path)
        if result.get("success"):
            return result.get("extracted_text", "").strip()
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", image_path, str(exc)[:120])
    return None


def _normalize_answer(raw: str) -> str:
    """Normalize answer text from docx AnswerLine."""
    cleaned = raw.strip()
    # Remove prefix like "答案：" or "答案:"
    cleaned = re.sub(r"^答案[：:]\s*", "", cleaned)
    return cleaned.strip()


def _parse_docx(doc: Document, subject_key: str, use_ocr: bool = True) -> dict:
    """Parse a docx into structured year→questions data."""
    para_images = _export_images(doc, subject_key)
    years_data: dict[str, list[dict]] = {}
    current_year = None
    current_questions: list[dict] = []

    paragraphs = list(doc.paragraphs)
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        text = p.text.strip()
        style = p.style.name if p.style else ""

        # Year heading
        if style == "Heading 1" and text:
            if current_year and current_questions:
                years_data[current_year] = current_questions
                current_questions = []
            current_year = text.replace(" 年", "").strip()
            i += 1
            continue

        # Question heading
        if style == "Heading 2" and current_year:
            q_number_match = re.search(r"第\s*(\d+)\s*题", text)
            q_number = int(q_number_match.group(1)) if q_number_match else len(current_questions) + 1

            # Look for content in this and following paragraphs (until next heading)
            content_parts = []
            options = {}
            answer = ""
            q_type = "选择题"
            has_image = False

            j = i + 1
            while j < len(paragraphs):
                np = paragraphs[j]
                nstyle = np.style.name if np.style else ""
                if nstyle in ("Heading 1", "Heading 2"):
                    break
                ntext = np.text.strip()

                if "AnswerLine" in nstyle:
                    answer = _normalize_answer(ntext)
                elif ntext:
                    content_parts.append(ntext)
                    # Check if this looks like an option
                    opt_match = re.match(r"^([A-D])[\.\、\)]\s*(.+)", ntext)
                    if opt_match:
                        options[opt_match.group(1)] = opt_match.group(2)

                # Check for image
                if str(j) in para_images:
                    has_image = True
                    img_path = para_images[str(j)]
                    if use_ocr:
                        ocr_text = _try_ocr_image(img_path)
                        if ocr_text:
                            content_parts.append(ocr_text)

                j += 1

            content = "\n".join(content_parts).strip()

            # Determine question type
            if len(answer) == 1 and answer.upper() in "ABCD":
                q_type = "选择题"
            elif answer and len(answer) > 1:
                q_type = "大题"

            qid = f"{subject_key}_{current_year}_{q_number}"
            current_questions.append({
                "id": qid,
                "year": int(current_year),
                "number": q_number,
                "type": q_type,
                "content": content or f"（图片题，请查看原题图片）",
                "options": options,
                "answer": answer,
                "has_image": has_image,
                "image_path": para_images.get(str(j-1), para_images.get(str(i+1), "")),
            })
            i = j
            continue

        i += 1

    if current_year and current_questions:
        years_data[current_year] = current_questions

    return years_data


def get_subject_past_papers(subject_key: str) -> dict:
    """Public API: get past-paper metadata for a subject."""
    subject_name = EXAM_SUBJECT_DIRS.get(subject_key, subject_key)
    docx_path = _find_docx(subject_key)
    if not docx_path:
        return {
            "subject_key": subject_key,
            "subject_name": subject_name,
            "available": False,
            "years": [],
            "resource_files": [],
        }

    # Try cached parse to get years quickly
    cache_file = _cache_path(subject_key) / "metadata.json"
    years_list = []
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            years_list = cached.get("years", [])
        except Exception:
            pass

    if not years_list:
        doc = Document(str(docx_path))
        parsed = _parse_docx(doc, subject_key, use_ocr=False)
        years_list = sorted([int(y) for y in parsed.keys()])
        cache_file.write_text(
            json.dumps({"years": years_list, "source": docx_path.name}, ensure_ascii=False),
            encoding="utf-8",
        )

    return {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "available": True,
        "years": years_list,
        "resource_files": [{"filename": docx_path.name, "years": years_list, "description": f"11408 近五年真题拆分：{subject_name}"}],
    }


def get_year_questions(subject_key: str, year: int, use_ocr: bool = True) -> dict:
    """Public API: get all questions for a specific year."""
    subject_name = EXAM_SUBJECT_DIRS.get(subject_key, subject_key)
    docx_path = _find_docx(subject_key)
    if not docx_path:
        return {"subject_key": subject_key, "subject_name": subject_name, "year": year, "questions": []}

    # Check cache first
    cache_file = _cache_path(subject_key) / f"year_{year}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    doc = Document(str(docx_path))
    parsed = _parse_docx(doc, subject_key, use_ocr=use_ocr)
    year_str = str(year)
    questions = parsed.get(year_str, [])

    # Strip large image_path for API response
    safe_questions = []
    for q in questions:
        sq = dict(q)
        if sq.get("image_path"):
            # Convert to relative/accessible path
            sq["image_url"] = f"/api/exam/11408/{subject_key}/question-image/{year}/{q['number']}"
            del sq["image_path"]
        safe_questions.append(sq)

    result = {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "year": year,
        "questions": safe_questions,
    }

    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def grade_submission(subject_key: str, year: int, answers: list[dict]) -> dict:
    """Grade a submission for a year's worth of questions."""
    parsed = get_year_questions(subject_key, year, use_ocr=False)
    questions = parsed.get("questions", [])
    qmap = {q["id"]: q for q in questions}

    results = []
    wrong_questions = []
    correct_count = 0
    total_score = 0
    max_score = 0

    for ans in answers:
        qid = ans.get("question_id", "")
        user_answer = (ans.get("user_answer") or "").strip()
        q = qmap.get(qid)
        if not q:
            continue

        qtype = q.get("type", "选择题")
        standard = (q.get("answer") or "").strip()

        if qtype == "选择题":
            is_correct = user_answer.upper() == standard.upper()
            if is_correct:
                correct_count += 1
                total_score += 2  # 2 points per choice question
            else:
                wrong_questions.append({
                    "mode": "11408", "source": "past_paper",
                    "subject_key": subject_key, "subject_name": parsed.get("subject_name", ""),
                    "year": year, "question_id": qid, "number": q.get("number"),
                    "type": qtype, "content": q.get("content", ""),
                    "options": q.get("options", {}),
                    "standard_answer": standard, "user_answer": user_answer,
                    "score": 0, "wrong_reason": "答案不匹配",
                })
            max_score += 2
        else:
            # Big question — use AI grading
            ai_result = _grade_big_question_with_ai(q, user_answer, standard)
            score = ai_result.get("score", 0)
            total_score += score
            max_score += 10
            if score < 7:
                wrong_questions.append({
                    "mode": "11408", "source": "past_paper",
                    "subject_key": subject_key, "subject_name": parsed.get("subject_name", ""),
                    "year": year, "question_id": qid, "number": q.get("number"),
                    "type": qtype, "content": q.get("content", ""),
                    "options": q.get("options", {}),
                    "standard_answer": standard, "user_answer": user_answer,
                    "score": score, "wrong_reason": ai_result.get("feedback", ""),
                })

        results.append({
            "question_id": qid, "number": q.get("number"), "type": qtype,
            "correct": is_correct if qtype == "选择题" else None,
            "score": score if qtype != "选择题" else (2 if is_correct else 0),
            "full_score": 2 if qtype == "选择题" else 10,
            "standard_answer": standard,
            "user_answer": user_answer,
            "feedback": ai_result.get("feedback", "") if qtype != "选择题" else "",
        })

    return {
        "subject_key": subject_key,
        "subject_name": parsed.get("subject_name", ""),
        "year": year,
        "results": results,
        "total_questions": len(questions),
        "choice_correct": correct_count,
        "choice_total": sum(1 for q in questions if q.get("type") == "选择题"),
        "big_question_avg_score": round(total_score / max(1, sum(1 for q in questions if q.get("type") == "大题")), 1) if any(q.get("type") == "大题" for q in questions) else None,
        "total_score": total_score,
        "max_score": max_score,
        "wrong_questions": wrong_questions,
    }


def _grade_big_question_with_ai(question: dict, user_answer: str, standard_answer: str) -> dict:
    """Grade a big question using AI (DeepSeek)."""
    if not user_answer.strip():
        return {"score": 0, "feedback": "未作答"}

    try:
        from openai import OpenAI
        import os
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
        )
        prompt = f"""你是 11408 考研真题阅卷老师。请根据以下信息给用户的大题答案评分。

当前科目：{question.get('subject_name', '')}
年份：{question.get('year', '')}
题号：第 {question.get('number', '')} 题
题目内容：{question.get('content', '')}

参考答案：{standard_answer}

用户答案：{user_answer}

评分要求：
- 满分 10 分
- 按与参考答案的符合程度评分
- 如果用户答案基本正确、覆盖关键点，给 8-10 分
- 如果部分正确，给 5-7 分
- 如果偏差较大，给 1-4 分
- 如果完全不对或为空，给 0 分

请严格返回 JSON 格式（不要 markdown 代码块）：
{{"score": 8, "feedback": "评分说明，指出得分点和缺失内容", "missing_points": ["缺失点1", "缺失点2"]}}"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        content = response.choices[0].message.content.strip()
        # Extract JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception as e:
        logger.warning("AI grading failed: %s", str(e)[:120])
        # Fallback: simple keyword matching
        score = 0
        if user_answer.strip():
            # Very basic: count common words
            user_words = set(user_answer.lower().split())
            std_words = set(standard_answer.lower().split())
            if std_words:
                overlap = len(user_words & std_words) / len(std_words)
                score = max(1, min(9, round(overlap * 10)))
        return {"score": score, "feedback": "AI 评分暂不可用，使用基础匹配评分", "missing_points": []}
