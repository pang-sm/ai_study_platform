"""
11408 exam paper parser — extracts questions from docx with image export.
"""
import json
import logging
import os
import re
import shutil
from pathlib import Path

from docx import Document

logger = logging.getLogger("exam_parser")

BASE_DIR = Path(__file__).resolve().parent
EXAM_RESOURCES_DIR = BASE_DIR / "exam_resources" / "11408"
CACHE_DIR = BASE_DIR / "cache" / "exam_papers" / "11408"
STATIC_DIR = BASE_DIR / "static" / "exam_papers" / "11408"

EXAM_SUBJECTS = {
    "data_structure": "数据结构",
    "computer_organization": "计算机组成原理",
    "operating_system": "操作系统",
    "computer_network": "计算机网络",
}


def _subject_docx(subject_key: str) -> Path | None:
    sd = EXAM_RESOURCES_DIR / subject_key
    if not sd.exists():
        return None
    docx_files = sorted(sd.glob("*.docx"))
    return docx_files[0] if docx_files else None


def _static_image_dir(subject_key: str, year: int) -> Path:
    d = STATIC_DIR / subject_key / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(subject_key: str) -> Path:
    p = CACHE_DIR / subject_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_docx_questions(subject_key: str, force: bool = False) -> dict:
    """Parse docx into year→questions, exporting images to static/."""
    docx_path = _subject_docx(subject_key)
    if not docx_path:
        return {}

    cache_json = _cache_path(subject_key) / "parsed.json"
    mtime = docx_path.stat().st_mtime
    if not force and cache_json.exists():
        try:
            cached = json.loads(cache_json.read_text(encoding="utf-8"))
            if cached.get("_mtime") == mtime:
                return {k: v for k, v in cached.items() if not k.startswith("_")}
        except Exception:
            pass

    doc = Document(str(docx_path))
    years_data: dict[str, list[dict]] = {}
    current_year = None
    current_questions: list[dict] = []
    paragraphs = list(doc.paragraphs)

    # Build paragraph→image mapping and export images
    para_images: dict[int, list[str]] = {}
    image_index = 0
    for pi, para in enumerate(paragraphs):
        imgs = []
        for run in para.runs:
            for elem in run._element:
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag not in ("drawing", "pict"):
                    continue
                for desc in elem.iter():
                    dtag = desc.tag.split("}")[-1] if "}" in desc.tag else desc.tag
                    if dtag == "blip":
                        embed = desc.get(
                            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                        )
                        if embed and embed in doc.part.rels:
                            rel = doc.part.rels[embed]
                            img_blob = rel.target_part.blob
                            ext = os.path.splitext(rel.target_part.partname)[1] or ".jpg"
                            # Export to static dir
                            static_dir = _static_image_dir(subject_key, 0)
                            fname = f"img_{image_index}{ext}"
                            fpath = static_dir / fname
                            if not fpath.exists():
                                fpath.write_bytes(img_blob)
                            imgs.append(f"/static/exam_papers/11408/{subject_key}/0/{fname}")
                            image_index += 1
        if imgs:
            para_images[pi] = imgs

    # Parse year by year
    i = 0
    while i < len(paragraphs):
        text = paragraphs[i].text.strip()

        # Detect year: "2022 年", "2023年", etc.
        year_match = re.match(r"^(\d{4})\s*年", text)
        if year_match:
            if current_year and current_questions:
                years_data[current_year] = current_questions
                current_questions = []
            current_year = year_match.group(1)
            i += 1
            continue

        # Detect question number: "第 1 题", "第1题", "第 41 题" etc.
        q_match = re.match(r"^第\s*(\d+)\s*题", text)
        if q_match and current_year:
            q_number = int(q_match.group(1))
            answer = ""
            question_images: list[str] = []
            content_parts = []

            # Collect question content: following paragraphs until next heading or answer
            j = i + 1
            while j < len(paragraphs):
                nt = paragraphs[j].text.strip()
                nstyle = paragraphs[j].style.name if paragraphs[j].style else ""

                # Stop at next year or next question
                if re.match(r"^(\d{4})\s*年", nt) or re.match(r"^第\s*(\d+)\s*题", nt):
                    break

                # Detect answer line
                ans_match = re.match(r"^答案[：:]\s*(.+)", nt)
                if ans_match:
                    answer = ans_match.group(1).strip()
                    j += 1
                    continue

                if nt:
                    content_parts.append(nt)

                # Collect images from this paragraph
                if j in para_images:
                    question_images.extend(para_images[j])

                j += 1

            content = "\n".join(content_parts).strip()

            # Determine question type
            q_type = "选择题"
            if q_number >= 40 or (answer and len(answer) > 10):
                q_type = "大题"

            # Generate stable ID
            qid = f"{subject_key}_{current_year}_{q_number}"

            # Move images to year-specific directory
            final_images = []
            static_year_dir = _static_image_dir(subject_key, int(current_year))
            for img_url in question_images:
                old_path = STATIC_DIR / subject_key / "0" / os.path.basename(img_url)
                new_path = static_year_dir / os.path.basename(img_url)
                if old_path.exists() and not new_path.exists():
                    shutil.move(str(old_path), str(new_path))
                final_images.append(f"/static/exam_papers/11408/{subject_key}/{current_year}/{os.path.basename(img_url)}")

            current_questions.append({
                "id": qid,
                "year": int(current_year),
                "number": q_number,
                "type": q_type,
                "content": content or f"第 {q_number} 题",
                "image_urls": final_images,
                "options": {"A": "", "B": "", "C": "", "D": ""} if q_type == "选择题" else {},
                "answer": answer,
            })
            i = j
            continue

        i += 1

    if current_year and current_questions:
        years_data[current_year] = current_questions

    # Cache
    years_data["_mtime"] = mtime
    cache_json.write_text(json.dumps(years_data, ensure_ascii=False), encoding="utf-8")

    # Log stats
    for y, qs in years_data.items():
        if y.startswith("_"): continue
        logger.info(
            "[exam_parser] %s year=%s questions=%d with_images=%d",
            subject_key, y, len(qs),
            sum(1 for q in qs if q.get("image_urls"))
        )

    return {k: v for k, v in years_data.items() if not k.startswith("_")}


def get_subject_past_papers(subject_key: str) -> dict:
    subject_name = EXAM_SUBJECTS.get(subject_key, subject_key)
    parsed = parse_docx_questions(subject_key)
    years_list = sorted([int(y) for y in parsed.keys()])
    docx_path = _subject_docx(subject_key)
    return {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "available": len(years_list) > 0,
        "years": years_list,
        "files": [{"filename": docx_path.name}] if docx_path else [],
    }


OCR_CACHE_DIR = CACHE_DIR  # same cache dir, ocr files stored alongside

OCR_PROMPT = """识别这张11408考研真题图片。提取题干和选项，严格按下面JSON格式输出：
{"题号":1,"题干":"完整题目文字","选项":{"A":"选项A文字","B":"选项B文字","C":"选项C文字","D":"选项D文字"},"小问":["子问题1","子问题2"],"代码":"如有代码块保留原样"}
不要编造，看不清标[识别不清]，只输出JSON。"""


def _ocr_cache_path(subject_key: str, year: int) -> Path:
    p = CACHE_DIR / subject_key
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{year}.ocr.json"


def _parse_ocr_json(raw_text: str) -> dict:
    """Extract JSON from Qwen OCR response, handling ```json fences and Chinese keys."""
    text = raw_text.strip()
    # Strip markdown code fences
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[ocr] JSON parse failed, raw: %s", text[:200])
        return {"ocr_quality": "failed", "need_manual_check": True}

    # Map Chinese keys to our schema
    stem = data.get("题干") or data.get("stem") or data.get("题目") or ""
    opts_raw = data.get("选项") or data.get("options") or data.get("ABCD选项") or {}
    sub_qs = data.get("小问") or data.get("sub_questions") or data.get("小题") or []

    options = {}
    if isinstance(opts_raw, list):
        # Array format: ["A:xxx", "B:xxx"] or ["A xxx", ...]
        for item in opts_raw:
            item = str(item).strip()
            m = re.match(r"^([A-D])[\.\、\：:\s]+(.+)", item)
            if m:
                options[m.group(1)] = m.group(2)
            elif len(item) > 0:
                label = item[0] if item[0] in "ABCD" else ""
                if label:
                    options[label] = item[1:].lstrip(".:：、 ")
    elif isinstance(opts_raw, dict):
        options = {str(k): str(v) for k, v in opts_raw.items() if str(k) in "ABCD"}

    result = {
        "stem": stem,
        "options": options,
        "sub_questions": sub_qs if isinstance(sub_qs, list) else [str(sub_qs)],
        "ocr_quality": "high" if (stem and options) else "medium",
        "need_manual_check": not (stem and len(options) >= 2),
    }
    return result


def _run_ocr_for_question(image_path: str, q_number: int) -> dict | None:
    """OCR a single question image, returning structured fields or None."""
    try:
        from qwen_parser import parse_image_with_qwen
    except ImportError:
        logger.warning("[ocr] qwen_parser not available")
        return None
    if not os.path.exists(image_path):
        return None
    try:
        result = parse_image_with_qwen(image_path, prompt=OCR_PROMPT, timeout_seconds=60)
        if not result.get("success"):
            logger.warning("[ocr] Q%d OCR call failed: %s", q_number, result.get("error", "")[:120])
            return None
        raw = result.get("extracted_text", "") or ""
        return _parse_ocr_json(raw)
    except Exception as e:
        logger.warning("[ocr] Q%d OCR error: %s", q_number, str(e)[:120])
        return None


def _ocr_year_questions(subject_key: str, year: int, force: bool = False) -> list[dict]:
    """OCR all images for a year's questions, returning merged question dicts.
    Results are cached to {cache}/exam_papers/{subject_key}/{year}.ocr.json"""
    cache_file = _ocr_cache_path(subject_key, year)
    docx_path = _subject_docx(subject_key)
    docx_mtime = docx_path.stat().st_mtime if docx_path else 0

    if not force and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            qs = cached.get("questions", [])
            if len(qs) > 0:
                return qs  # Cache hit — avoid re-parsing on deploy where mtime differs
        except Exception:
            pass

    parsed = parse_docx_questions(subject_key)
    year_str = str(year)
    questions = parsed.get(year_str, [])
    if not questions:
        return []

    logger.info("[ocr] Starting OCR for %s year=%s (%d questions)", subject_key, year, len(questions))
    success_count = 0
    for q in questions:
        img_urls = q.get("image_urls", [])
        if not img_urls:
            q["stem"] = q.get("content", "")
            q["options"] = q.get("options", {"A": "", "B": "", "C": "", "D": ""})
            q["ocr_quality"] = "none"
            q["need_manual_check"] = False
            continue
        # Find first local image
        img_path = None
        for url in img_urls:
            local = STATIC_DIR / subject_key / str(year) / os.path.basename(url)
            if local.exists():
                img_path = str(local)
                break
        if not img_path:
            q["stem"] = q.get("content", f"第 {q['number']} 题")
            q["options"] = q.get("options", {"A": "", "B": "", "C": "", "D": ""})
            q["ocr_quality"] = "none"
            q["need_manual_check"] = True
            continue

        ocr = _run_ocr_for_question(img_path, q["number"])
        if ocr:
            q["stem"] = ocr.get("stem", "") or q.get("content", "")
            q["options"] = ocr.get("options", q.get("options", {}))
            q["ocr_quality"] = ocr.get("ocr_quality", "medium")
            q["need_manual_check"] = ocr.get("need_manual_check", False)
            success_count += 1
        else:
            q["stem"] = q.get("content", f"第 {q['number']} 题")
            q["options"] = q.get("options", {"A": "", "B": "", "C": "", "D": ""})
            q["ocr_quality"] = "failed"
            q["need_manual_check"] = True

    cache_file.write_text(json.dumps({
        "subject_key": subject_key, "subject_name": EXAM_SUBJECTS.get(subject_key, ""),
        "year": year, "docx_mtime": docx_mtime, "questions": questions,
    }, ensure_ascii=False), encoding="utf-8")
    logger.info("[ocr] Done %s year=%s success=%d/%d", subject_key, year, success_count, len(questions))
    return questions


def get_year_questions(subject_key: str, year: int) -> dict:
    subject_name = EXAM_SUBJECTS.get(subject_key, subject_key)
    # Fast path: read OCR cache directly
    cache_file = _ocr_cache_path(subject_key, year)
    if cache_file.exists():
        try:
            raw = cache_file.read_text(encoding="utf-8")
            cached = json.loads(raw)
            qs = cached.get("questions", [])
            if len(qs) > 0:
                # Return questions without image_urls (lighter payload)
                slim = []
                for q in qs:
                    sq = {k: v for k, v in q.items() if k not in ("image_urls",)}
                    # Truncate long stems/options to reduce payload
                    if sq.get("stem") and len(sq["stem"]) > 500:
                        sq["stem"] = sq["stem"][:500]
                    slim.append(sq)
                logger.info("[exam_parser] Cache hit %s/%s: %d qs", subject_key, year, len(qs))
                return {"subject_key": subject_key, "subject_name": subject_name, "year": year, "questions": slim}
        except Exception as e:
            logger.warning("[exam_parser] Cache read failed for %s year=%s: %s", subject_key, year, str(e)[:200])
    logger.warning("[exam_parser] Cache miss for %s year=%s, falling back to slow path", subject_key, year)
    questions = _ocr_year_questions(subject_key, year)
    return {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "year": year,
        "questions": questions,
    }


def grade_submission(subject_key: str, year: int, answers: list[dict]) -> dict:
    parsed = get_year_questions(subject_key, year)
    questions = parsed.get("questions", [])
    qmap = {q["id"]: q for q in questions}
    results, wrong = [], []
    correct = 0
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
                correct += 1
                total_score += 2
            else:
                wrong.append({
                    "question_id": qid, "number": q.get("number"), "type": qtype,
                    "content": q.get("stem") or q.get("content", ""), "options": q.get("options", {}),
                    "standard_answer": standard, "user_answer": user_answer,
                    "score": 0, "wrong_reason": "答案不匹配",
                })
            max_score += 2
            results.append({
                "question_id": qid, "number": q.get("number"), "type": qtype,
                "correct": is_correct, "score": 2 if is_correct else 0,
                "full_score": 2, "standard_answer": standard, "user_answer": user_answer,
            })
        else:
            score, feedback = _grade_big_question(q, user_answer, standard, subject_key)
            total_score += score
            max_score += 10
            if score < 7:
                wrong.append({
                    "question_id": qid, "number": q.get("number"), "type": qtype,
                    "content": q.get("stem") or q.get("content", ""), "standard_answer": standard,
                    "user_answer": user_answer, "score": score, "wrong_reason": feedback,
                })
            results.append({
                "question_id": qid, "number": q.get("number"), "type": qtype,
                "score": score, "full_score": 10,
                "standard_answer": standard, "user_answer": user_answer,
                "feedback": feedback,
            })

    big_qs = [q for q in questions if q.get("type") == "大题"]
    return {
        "subject_key": subject_key, "subject_name": parsed.get("subject_name", ""),
        "year": year,
        "results": results,
        "total_questions": len(questions),
        "choice_correct": correct,
        "choice_total": len([q for q in questions if q.get("type") == "选择题"]),
        "big_avg_score": round(total_score / max(1, len(big_qs)), 1) if big_qs else None,
        "total_score": total_score, "max_score": max_score,
        "wrong_questions": wrong,
    }


def _grade_big_question(q: dict, user_answer: str, standard: str, subject_key: str) -> tuple[int, str]:
    if not user_answer.strip():
        return 0, "未作答"
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
        )
        prompt = f"""你是11408考研阅卷老师。请评分(满分10分,按参考答案符合度)。

科目:{EXAM_SUBJECTS.get(subject_key,'')} 题号:第{q.get('number','')}题
题目:{q.get('content','')[:300]}
参考答案:{standard[:500]}
用户答案:{user_answer[:500]}

严格返回JSON(不要markdown):{{"score":8,"feedback":"评语"}}"""
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=[{"role":"user","content":prompt}],
            temperature=0.3, max_tokens=300,
        )
        content = resp.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"): content = content[4:]
        result = json.loads(content)
        return int(result.get("score", 0)), result.get("feedback", "")
    except Exception as e:
        logger.warning("AI grading failed: %s", str(e)[:120])
        if user_answer.strip():
            score = min(9, max(1, len(set(user_answer.lower().split()) & set(standard.lower().split())) * 10 // max(1, len(set(standard.lower().split())))))
            return score, "AI暂不可用,基础评分"
        return 0, "AI评分不可用"
