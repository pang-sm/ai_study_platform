import re
from collections import Counter
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

import models
from database import engine, is_material_chunks_fts_enabled

MAX_CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
MAX_CHUNK_SUMMARY_LEN = 180
MAX_CHUNK_INJECTION_LEN = 800
MAX_TOTAL_CONTEXT_LEN = 5000
DEFAULT_TOP_K = 4
MAX_TOP_K = 6

COURSE_HINTS = {
    "Python": ["python", "def", "class", "list", "dict", "import", "函数", "列表", "字典"],
    "Java": ["java", "class", "public", "static", "对象", "继承", "多态", "接口"],
    "数据结构": ["数组", "链表", "栈", "队列", "树", "图", "哈希", "排序", "查找"],
    "计算机网络": ["tcp", "udp", "http", "https", "ip", "dns", "协议", "分层", "路由"],
    "操作系统": ["进程", "线程", "调度", "内存", "页表", "死锁", "文件系统", "中断"],
    "数据库": ["sql", "mysql", "sqlite", "索引", "事务", "表", "查询", "主键", "外键"],
    "前端开发": ["html", "css", "javascript", "react", "组件", "状态", "事件", "页面"],
    "后端开发": ["fastapi", "api", "接口", "数据库", "服务", "鉴权", "路由", "后端"],
    "算法": ["动态规划", "贪心", "二分", "递归", "回溯", "复杂度", "图论", "搜索"],
}


def clean_extracted_text(text_value: str) -> str:
    if not text_value:
        return ""

    normalized = text_value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_text_into_chunks(text_value: str, chunk_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    cleaned = clean_extracted_text(text_value)
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        candidate = cleaned[start:end]

        if end < text_length:
            split_pos = max(
                candidate.rfind("\n\n"),
                candidate.rfind("。"),
                candidate.rfind("！"),
                candidate.rfind("？"),
                candidate.rfind(". "),
            )
            if split_pos >= int(chunk_size * 0.55):
                end = start + split_pos + 1
                candidate = cleaned[start:end]

        candidate = candidate.strip()
        if candidate:
            chunks.append(candidate)

        if end >= text_length:
            break

        next_start = max(0, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def summarize_chunk_text(chunk_text: str) -> str:
    cleaned = clean_extracted_text(chunk_text)
    if len(cleaned) <= MAX_CHUNK_SUMMARY_LEN:
        return cleaned
    return cleaned[:MAX_CHUNK_SUMMARY_LEN].rstrip() + "..."


def extract_keywords(subject: str, material_summary: str, source_filename: str, chunk_text: str):
    combined = " ".join(
        [
            subject or "",
            material_summary or "",
            source_filename or "",
            (chunk_text or "")[:800],
        ]
    ).lower()

    tokens: list[str] = []
    tokens.extend(COURSE_HINTS.get(subject, []))
    tokens.extend(re.findall(r"[a-zA-Z_][a-zA-Z0-9_+#.-]{1,30}", combined))
    tokens.extend([item for item in re.findall(r"[\u4e00-\u9fff]{2,8}", combined) if len(item) >= 2])

    counter = Counter(token for token in tokens if len(token.strip()) >= 2)
    most_common = [token for token, _ in counter.most_common(18)]
    return " ".join(dict.fromkeys(most_common))


def build_chunk_records(material: models.StudyMaterial):
    cleaned_text = clean_extracted_text(material.extracted_text or "")
    if not cleaned_text:
        return []

    chunks = split_text_into_chunks(cleaned_text)
    records = []
    for index, chunk_text in enumerate(chunks):
        chunk_summary = summarize_chunk_text(chunk_text)
        keywords = extract_keywords(
            subject=material.subject,
            material_summary=material.summary,
            source_filename=material.original_filename,
            chunk_text=chunk_text,
        )
        records.append(
            {
                "material_id": material.id,
                "username": material.username,
                "subject": material.subject,
                "chunk_index": index,
                "chunk_text": chunk_text,
                "chunk_summary": chunk_summary,
                "keywords": keywords,
                "source_filename": material.original_filename,
                "is_deleted": False,
                "created_at": datetime.utcnow(),
            }
        )
    return records


def soft_delete_material_chunks(db: Session, material_id: int):
    chunk_ids = [
        row.id
        for row in db.query(models.MaterialChunk.id)
        .filter(models.MaterialChunk.material_id == material_id)
        .all()
    ]

    db.query(models.MaterialChunk).filter(
        models.MaterialChunk.material_id == material_id
    ).update({models.MaterialChunk.is_deleted: True}, synchronize_session=False)
    db.commit()

    if chunk_ids and is_material_chunks_fts_enabled():
        with engine.begin() as conn:
            for chunk_id in chunk_ids:
                conn.execute(
                    text("DELETE FROM material_chunks_fts WHERE chunk_id = :chunk_id"),
                    {"chunk_id": chunk_id},
                )


def replace_material_chunks(db: Session, material: models.StudyMaterial):
    soft_delete_material_chunks(db, material.id)

    records = build_chunk_records(material)
    if not records:
        return 0

    chunk_models = [models.MaterialChunk(**record) for record in records]
    db.add_all(chunk_models)
    db.commit()
    for chunk_model in chunk_models:
        db.refresh(chunk_model)

    if is_material_chunks_fts_enabled():
        with engine.begin() as conn:
            for chunk_model in chunk_models:
                conn.execute(
                    text(
                        """
                        INSERT INTO material_chunks_fts(
                            chunk_text,
                            chunk_summary,
                            keywords,
                            source_filename,
                            chunk_id,
                            material_id,
                            username,
                            subject
                        ) VALUES (
                            :chunk_text,
                            :chunk_summary,
                            :keywords,
                            :source_filename,
                            :chunk_id,
                            :material_id,
                            :username,
                            :subject
                        )
                        """
                    ),
                    {
                        "chunk_text": chunk_model.chunk_text,
                        "chunk_summary": chunk_model.chunk_summary,
                        "keywords": chunk_model.keywords or "",
                        "source_filename": chunk_model.source_filename,
                        "chunk_id": chunk_model.id,
                        "material_id": chunk_model.material_id,
                        "username": chunk_model.username,
                        "subject": chunk_model.subject,
                    },
                )

    return len(chunk_models)


def tokenize_query(question: str, subject: str | None = None):
    combined = f"{subject or ''} {question or ''}".lower()
    keywords = re.findall(r"[a-zA-Z_][a-zA-Z0-9_+#.-]{1,30}", combined)
    keywords += [item for item in re.findall(r"[\u4e00-\u9fff]{2,8}", combined) if len(item) >= 2]
    return list(dict.fromkeys(keywords))[:12]


def build_fts_query(question: str, subject: str | None = None):
    tokens = tokenize_query(question, subject)
    return " OR ".join(tokens)


def compute_keyword_bonus(question_tokens: list[str], chunk):
    haystacks = " ".join(
        [
            (chunk.keywords or "").lower(),
            (chunk.chunk_summary or "").lower(),
            (chunk.source_filename or "").lower(),
            (chunk.chunk_text or "")[:600].lower(),
        ]
    )
    hit_count = sum(1 for token in question_tokens if token in haystacks)
    freshness_bonus = 0.15
    return hit_count * 1.2 + freshness_bonus


def trim_chunks_for_prompt(chunks: list[dict], total_limit: int = MAX_TOTAL_CONTEXT_LEN):
    selected: list[dict] = []
    current_total = 0

    for chunk in chunks:
        trimmed_text = (chunk["chunk_text"] or "")[:MAX_CHUNK_INJECTION_LEN]
        if not trimmed_text.strip():
            continue

        prospective_total = current_total + len(trimmed_text)
        if prospective_total > total_limit and selected:
            break

        selected.append({**chunk, "chunk_text": trimmed_text})
        current_total = prospective_total

    return selected


def search_relevant_material_chunks(
    username: str,
    subject: str | None,
    question: str,
    top_k: int = DEFAULT_TOP_K,
):
    safe_top_k = max(1, min(top_k, MAX_TOP_K))
    question_tokens = tokenize_query(question, subject)
    results: list[dict] = []
    fts_query = build_fts_query(question, subject)

    with Session(engine) as session:
        base_filter = (
            session.query(models.MaterialChunk, models.StudyMaterial)
            .join(models.StudyMaterial, models.StudyMaterial.id == models.MaterialChunk.material_id)
            .filter(
                models.MaterialChunk.username == username,
                models.MaterialChunk.is_deleted.is_(False),
                models.StudyMaterial.is_deleted.is_(False),
            )
        )
        if subject:
            base_filter = base_filter.filter(models.MaterialChunk.subject == subject)

        if is_material_chunks_fts_enabled() and fts_query:
            try:
                rows = session.execute(
                    text(
                        """
                        SELECT
                            mc.id AS chunk_id,
                            mc.material_id AS material_id,
                            mc.source_filename AS source_filename,
                            mc.chunk_text AS chunk_text,
                            mc.chunk_summary AS chunk_summary,
                            mc.keywords AS keywords,
                            sm.subject AS subject,
                            sm.file_type AS file_type,
                            sm.created_at AS created_at,
                            bm25(material_chunks_fts) AS bm25_score,
                            mc.created_at AS chunk_created_at
                        FROM material_chunks_fts fts
                        JOIN material_chunks mc ON mc.id = fts.chunk_id
                        JOIN study_materials sm ON sm.id = mc.material_id
                        WHERE material_chunks_fts MATCH :fts_query
                          AND mc.username = :username
                          AND mc.is_deleted = 0
                          AND sm.is_deleted = 0
                          AND (:subject = '' OR mc.subject = :subject)
                        LIMIT 24
                        """
                    ),
                    {
                        "fts_query": fts_query,
                        "username": username,
                        "subject": subject or "",
                    },
                ).mappings().all()

                for row in rows:
                    score = float(-(row["bm25_score"] or 0.0)) + compute_keyword_bonus(
                        question_tokens,
                        type("ChunkLike", (), row),
                    )
                    results.append(
                        {
                            "material_id": row["material_id"],
                            "chunk_id": row["chunk_id"],
                            "source_filename": row["source_filename"],
                            "chunk_text": row["chunk_text"],
                            "chunk_summary": row["chunk_summary"],
                            "keywords": row["keywords"],
                            "subject": row["subject"],
                            "file_type": row["file_type"],
                            "created_at": row["created_at"] or row["chunk_created_at"],
                            "score": score,
                        }
                    )
            except Exception:
                results = []

        if not results:
            candidate_rows = base_filter.order_by(models.MaterialChunk.created_at.desc()).limit(60).all()
            for chunk, material in candidate_rows:
                searchable = " ".join(
                    [
                        chunk.chunk_text or "",
                        chunk.chunk_summary or "",
                        chunk.keywords or "",
                        chunk.source_filename or "",
                    ]
                ).lower()
                hit_count = sum(1 for token in question_tokens if token in searchable)
                if hit_count == 0:
                    continue
                results.append(
                    {
                        "material_id": chunk.material_id,
                        "chunk_id": chunk.id,
                        "source_filename": chunk.source_filename,
                        "chunk_text": chunk.chunk_text,
                        "chunk_summary": chunk.chunk_summary,
                        "keywords": chunk.keywords,
                        "subject": material.subject,
                        "file_type": material.file_type,
                        "created_at": material.created_at or chunk.created_at,
                        "score": hit_count + 0.1,
                    }
                )

        deduped = {}
        for item in sorted(results, key=lambda item: item["score"], reverse=True):
            if item["chunk_id"] not in deduped:
                deduped[item["chunk_id"]] = item

        ranked = list(deduped.values())[:safe_top_k]
        return trim_chunks_for_prompt(ranked, MAX_TOTAL_CONTEXT_LEN)


def reindex_materials(db: Session, username: str, subject: str | None = None, force: bool = False):
    query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == username,
        models.StudyMaterial.is_deleted.is_(False),
    )
    if subject:
        query = query.filter(models.StudyMaterial.subject == subject)

    materials = query.order_by(models.StudyMaterial.created_at.desc()).all()
    indexed_material_count = 0
    indexed_chunk_count = 0

    for material in materials:
        if not (material.extracted_text or "").strip():
            continue

        existing_count = (
            db.query(models.MaterialChunk)
            .filter(
                models.MaterialChunk.material_id == material.id,
                models.MaterialChunk.is_deleted.is_(False),
            )
            .count()
        )

        if existing_count > 0 and not force:
            continue

        chunk_count = replace_material_chunks(db, material)
        if chunk_count > 0:
            indexed_material_count += 1
            indexed_chunk_count += chunk_count

    return indexed_material_count, indexed_chunk_count
