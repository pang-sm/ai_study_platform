# -*- coding: utf-8 -*-
"""Chinese retrieval over course materials — the smallest regression for the n-gram fix.

WHAT WENT WRONG
---------------
Course Q&A retrieved nothing for a question that PARAPHRASED its material — which is what an
ordinary question does. Two causes compounded:

* FTS5's default `unicode61` tokenizer has no Chinese word boundaries. It stores a whole run of
  CJK as ONE term, so `MATCH '线性表'` against a passage containing 线性表 returns zero rows —
  the FTS path is dead for CJK, whatever the query.
* The substring fallback looked for the question's OWN runs (`[一-鿿]{2,8}`, i.e. eight-character
  slices). That only ever matched when the question happened to reuse a run of the passage
  VERBATIM — ask 顺序表和链表的区别 about a passage that says 顺序表与链表的区别 and the one
  character that differs is enough for `hit_count == 0`, so the chunk was dropped. The defect was
  therefore content-dependent, which is exactly why it survived: a question that happened to share
  wording worked, and nobody traced the ones that did not.

The fix is query-side only: `tokenize_query` also emits sliding 2–4 character n-grams. Nothing
about the index, the schema or the stored chunks changed.

WHAT THIS FILE HOLDS (the five behaviours the fix has to keep)
--------------------------------------------------------------
1. an exact Chinese keyword recalls the material that contains it;
2. a Chinese SENTENCE recalls it too — this is the case that used to fail;
3. an unrelated material is not recalled just because the query shares generic two-character
   words with it;
4. the material that actually answers the question outranks one that merely shares the course;
5. Latin and numeric queries still behave — the n-grams are generated for CJK runs only, so
   `ZX_ACCEPTANCE_FACT_921` must keep matching as a whole token.
"""
import rag

COURSE = "数据结构"

ALPHA = (
    "红杉算法的冻结窗口为 37 分钟。冻结窗口是红杉算法在单次调度周期内对同一资源保持排他的最长时间，"
    "窗口长度决定吞吐与公平性之间的取舍。唯一事实标记：ZX_ACCEPTANCE_FACT_921。"
)
BETA = (
    "循环队列的判空与判满：牺牲一个存储单元，队头指针等于队尾指针时队空，"
    "队尾指针的下一个位置等于队头指针时队满。"
)
GAMMA = (
    "顺序存储的二叉树中，若结点下标为 i，则其左孩子下标为 2i，右孩子下标为 2i+1，"
    "父结点下标为 i/2 向下取整。"
)


def _material(db, username, filename, text):
    from models import MaterialChunk, StudyMaterial

    material = StudyMaterial(
        username=username, course_id=COURSE, subject_key=COURSE, subject=COURSE,
        file_type="text", original_filename=filename, file_hash=f"hash-{filename}",
        file_path=f"test/{filename}", file_size=len(text), extracted_text=text,
        summary="", parse_status="success", is_deleted=False,
        visibility="private", allow_private_rag=True)
    db.add(material)
    db.commit()
    db.refresh(material)
    db.add(MaterialChunk(
        material_id=material.id, username=username, course_id=COURSE,
        subject_key=COURSE, subject=COURSE, chunk_index=0, chunk_text=text,
        chunk_summary=text[:80], keywords="", source_filename=filename))
    db.commit()
    return material


def _corpus(db, username):
    return {
        "alpha": _material(db, username, "alpha.md", ALPHA),
        "beta": _material(db, username, "beta.md", BETA),
        "gamma": _material(db, username, "gamma.md", GAMMA),
    }


def _search(username, question, top_k=4):
    return rag.search_relevant_material_chunks(
        username=username, subject=COURSE, question=question, top_k=top_k, course_id=COURSE)


def _files(hits):
    return [hit["source_filename"] for hit in hits]


# ---------------------------------------------------------------- 1 + 2

def test_a_keyword_and_a_full_sentence_both_recall_the_same_material(db_session):
    """The sentence is the case that failed; the keyword is the control that proves the corpus is
    reachable at all. Both must find alpha."""
    corpus = _corpus(db_session, "cjk_forms")

    keyword = _search("cjk_forms", "红杉算法")
    assert "alpha.md" in _files(keyword), _files(keyword)

    # A question phrased as a sentence — the exact shape that returned nothing before the fix.
    sentence = _search("cjk_forms", "红杉算法的冻结窗口是多少分钟？")
    assert "alpha.md" in _files(sentence), _files(sentence)

    assert corpus["alpha"].id in {hit["material_id"] for hit in sentence}


def test_a_second_phrasing_of_the_same_question_also_recalls_it(db_session):
    """More than one Chinese query, so the fix cannot be passing on one lucky phrase."""
    _corpus(db_session, "cjk_phrasings")
    for question in [
        "冻结窗口有多长？",
        "红杉算法保持排他的时间是多少？",
        "调度周期内同一资源的最长占用时间是多久？",
    ]:
        hits = _files(_search("cjk_phrasings", question))
        assert "alpha.md" in hits, f"{question} -> {hits}"


# ---------------------------------------------------------------- 3 + 4

def test_an_unrelated_material_is_not_recalled_by_generic_words(db_session):
    """Gamma shares the course and ordinary wording, and nothing else. It must not come back for a
    question about a different subject."""
    _corpus(db_session, "cjk_precision")
    hits = _files(_search("cjk_precision", "红杉算法的冻结窗口是多少分钟？"))
    assert "gamma.md" not in hits, hits
    assert "beta.md" not in hits, hits


def test_the_answering_material_outranks_one_that_merely_shares_the_course(db_session):
    corpus = _corpus(db_session, "cjk_rank")
    hits = _search("cjk_rank", "红杉算法的冻结窗口是多少分钟？")

    assert hits, "the question must retrieve something"
    assert hits[0]["material_id"] == corpus["alpha"].id, _files(hits)
    # Ranked, not merely present: a weaker match never displaces the right one.
    assert hits[0]["score"] > (hits[1]["score"] if len(hits) > 1 else 0)


def test_each_subject_question_retrieves_its_own_material(db_session):
    """Three questions, three different answers — the recall is topical, not "everything in the
    course"."""
    corpus = _corpus(db_session, "cjk_topical")
    cases = {
        "alpha": "红杉算法的冻结窗口是多少分钟？",
        "beta": "循环队列怎么区分队空和队满？",
        "gamma": "顺序存储的二叉树里左孩子的下标怎么算？",
    }
    for name, question in cases.items():
        hits = _files(_search("cjk_topical", question))
        assert hits and hits[0] == f"{name}.md", f"{question} -> {hits}"
        assert corpus[name].id in {hit["material_id"] for hit in _search("cjk_topical", question)}


# ---------------------------------------------------------------- 5

def test_latin_and_numeric_queries_are_not_regressed(db_session):
    """The n-grams are emitted for CJK runs only. A Latin/numeric token must keep matching as the
    whole token it is — an identifier is not a bag of character pairs."""
    _corpus(db_session, "cjk_latin")

    identifier = _files(_search("cjk_latin", "ZX_ACCEPTANCE_FACT_921"))
    assert "alpha.md" in identifier, identifier

    # ...and it does not drag in the other two, which share none of it.
    assert set(identifier) <= {"alpha.md"}, identifier

    tokens = rag.tokenize_query("ZX_ACCEPTANCE_FACT_921")
    assert "ZX_ACCEPTANCE_FACT_921".lower() in tokens
    # No 2-grams were manufactured out of the identifier.
    assert "zx" not in tokens and "_a" not in tokens


def test_a_purely_english_question_still_uses_fts_terms(db_session):
    _corpus(db_session, "cjk_mixed")
    tokens = rag.tokenize_query("what is the freezing window")
    assert "what" in tokens and "freezing" in tokens and "window" in tokens


def test_the_pre_fix_tokenizer_failed_on_a_paraphrased_question(db_session, monkeypatch):
    """The guard's own proof, and the precise shape of the bug.

    A regression test that passes for a reason unrelated to the change guards nothing. This replays
    the tokenizer exactly as it was and runs it against a passage that says 顺序表与链表的区别 while
    the question asks about 顺序表和链表的区别 — one character apart, which is what paraphrasing
    looks like. The old tokenizer returns nothing; the new one returns the passage.

    The second half matters as much: the old code was NOT uniformly broken. A question that reused
    a run of the passage verbatim matched fine, and that is why the defect went unnoticed.
    """
    import re

    from models import MaterialChunk, StudyMaterial

    def _one(db, username, filename, text):
        material = StudyMaterial(
            username=username, course_id=COURSE, subject_key=COURSE, subject=COURSE,
            file_type="text", original_filename=filename, file_hash=f"hash-{filename}",
            file_path=f"test/{filename}", file_size=len(text), extracted_text=text,
            summary="", parse_status="success", is_deleted=False,
            visibility="private", allow_private_rag=True)
        db.add(material)
        db.commit()
        db.refresh(material)
        db.add(MaterialChunk(
            material_id=material.id, username=username, course_id=COURSE,
            subject_key=COURSE, subject=COURSE, chunk_index=0, chunk_text=text,
            chunk_summary=text[:80], keywords="", source_filename=filename))
        db.commit()

    _one(db_session, "cjk_prefix", "passage.md",
         "顺序表与链表的区别在于：顺序表支持随机访问，链表插入删除不需要移动元素。")

    def old_tokenize(question, subject=None):
        combined = f"{subject or ''} {question or ''}".lower()
        keywords = re.findall(r"[a-zA-Z_][a-zA-Z0-9_+#.-]{1,30}", combined)
        keywords += [item for item in re.findall(r"[一-鿿]{2,8}", combined) if len(item) >= 2]
        return list(dict.fromkeys(keywords))[:12]

    paraphrased = "顺序表和链表的区别是什么？"
    verbatim = "顺序表与链表的区别"

    # Now: the paraphrased question is answered.
    assert _search("cjk_prefix", paraphrased) != []

    monkeypatch.setattr(rag, "tokenize_query", old_tokenize)
    # Before: the paraphrased question retrieved nothing...
    assert _search("cjk_prefix", paraphrased) == []
    # ...while the verbatim one worked all along, which is why the defect hid.
    assert _search("cjk_prefix", verbatim) != []
