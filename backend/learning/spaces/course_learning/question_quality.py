"""What makes a generated practice question good enough to show a learner.

WHY THIS EXISTS AS ITS OWN MODULE
---------------------------------
A question is not "valid" because it parses. The schema gate in ``practice.py`` answers "is
this shaped like a question"; this module answers the different and harder question: *does it
test knowledge of the point it names, or does it merely restate the point's title?*

The distinction was learned from a production incident. A learner asked for 10 questions on
「循环队列」 and got a set of near-identical meta-questions —

    请简述「循环队列」的核心含义，并说明它在什么情况下适用。
    判断：「循环队列」是本章需要掌握的内容之一。

— which passed every structural check. They had no ``assessment_target`` because the model's
answer had been truncated and the deterministic filler produced them. So the rules here are
two-sided: they reject the bad shapes by name, AND they require every question to declare a
concrete ability it exercises, with enough distinct abilities across the batch that the set
cannot collapse into one template.

THE THREE GATES
---------------
1. **Low-information shapes** (``low_information``): the meta-questions above, "请介绍 X",
   "谈谈你的理解", and anything whose explanation is a claim about the syllabus rather than
   about the knowledge. A definition-style question is allowed ONCE per set — for a point
   whose knowledge IS a definition, asking for it once is the right question.
2. **Duplicate shapes** (``Batch.add``): normalized-stem equality, character n-gram
   similarity, and a stable fingerprint. "循环队列的核心含义是什么" and "请说明循环队列的基本
   含义" are the SAME question and the second one is refused.
3. **Target coverage** (``Batch.coverage_ok``): the number of distinct ``assessment_target``
   values must clear ``MIN_UNIQUE_TARGETS``. Swapping the question type while asking the same
   thing does not count.

Everything here is deterministic and model-free: the same input always produces the same
verdict, so a rejection can be explained to a maintainer without re-running a provider.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

# ------------------------------------------------------------------ cognitive levels

UNDERSTAND = "understand"
APPLY = "apply"
ANALYZE = "analyze"
EVALUATE = "evaluate"
SYNTHESIZE = "synthesize"

COGNITIVE_LEVELS = (UNDERSTAND, APPLY, ANALYZE, EVALUATE, SYNTHESIZE)

# What each level asks the question to do, in the words the prompt can use.
LEVEL_LABELS = {
    UNDERSTAND: "理解概念本身",
    APPLY: "应用规则做计算或状态推演",
    ANALYZE: "分析边界条件、辨析错误做法",
    EVALUATE: "比较方案、判断取舍",
    SYNTHESIZE: "综合多个要点或走完整过程",
}


@dataclass(frozen=True)
class Slot:
    """One position of a set: the type it must be, and the ability it must exercise."""

    question_type: str
    cognitive_level: str
    role: str


# The coverage matrix. A product decision, like the type mix it is aligned with: a
# ten-question set that is ten definitions is not ten questions. Every count keeps the same
# question-type multiset practice.py already promised, and distributes abilities across it.
_SET_PLAN: dict[int, tuple[Slot, ...]] = {
    3: (
        Slot("single_choice", UNDERSTAND, "概念理解"),
        Slot("single_choice", APPLY, "计算推演"),
        Slot("true_false", ANALYZE, "边界判断"),
    ),
    5: (
        Slot("single_choice", UNDERSTAND, "概念理解"),
        Slot("single_choice", APPLY, "计算推演"),
        Slot("true_false", ANALYZE, "边界判断"),
        Slot("multiple_choice", ANALYZE, "错误辨析"),
        Slot("short_answer", SYNTHESIZE, "综合过程"),
    ),
    10: (
        Slot("single_choice", UNDERSTAND, "概念理解"),
        Slot("single_choice", UNDERSTAND, "原理判断"),
        Slot("single_choice", APPLY, "计算推演"),
        Slot("single_choice", APPLY, "状态推演"),
        Slot("true_false", ANALYZE, "边界条件"),
        Slot("true_false", ANALYZE, "语义辨析"),
        Slot("multiple_choice", ANALYZE, "错误辨析"),
        Slot("multiple_choice", APPLY, "实现细节"),
        Slot("short_answer", SYNTHESIZE, "综合过程分析"),
        Slot("short_answer", EVALUATE, "方案比较与应用"),
    ),
}

# A set must name at least this many DIFFERENT abilities. 10 → 5 keeps a ten-question set
# from being five abilities asked twice, which is what "换题型继续问同一件事" looks like.
MIN_UNIQUE_TARGETS = {3: 2, 5: 3, 10: 5}

# The most any one ability may be asked. Two is what the threshold above implies for the
# largest set, and it is the binding constraint the collector enforces as it fills.
MAX_TARGET_REUSE = 2

# Two stems at or above this n-gram overlap are the same question asked twice.
#
# Two measures, because one is not enough for Chinese. Jaccard treats the two sentences as
# equal-length bags, which under-reports a question that was rewritten shorter: "顺序表在表尾
# 追加一个元素需要移动多少个元素？" and "…追加一个元素，需要移动的元素个数是多少？" share most of
# their content but score 0.54 on Jaccard. Containment — shared grams over the SHORTER sentence —
# scores the same pair 0.78, while a genuinely different question about the same topic
# ("…追加一个元素…" vs "…删除表头元素…") scores 0.67. Both measures are checked; either is enough.
# Measured 2026-10-01 over the pairs quoted in this module's docstring.
DUPLICATE_SIMILARITY = 0.72
DUPLICATE_CONTAINMENT = 0.76


def set_plan(count: int) -> tuple[Slot, ...]:
    return _SET_PLAN.get(count, _SET_PLAN[5])


def reweight(plan: tuple[Slot, ...],
             level_accuracy: dict[str, float]) -> tuple[tuple[Slot, ...], dict]:
    """Move ONE slot from a ability the learner is already good at to one they are not.

    Deliberately minimal. The engine behind ``adaptive_context`` is not being rebuilt here:
    the only thing asked of it is a deterministic nudge to *which ability gets asked*, never
    to the question-type mix the learner can see. One slot moves at most, and only when the
    record clearly supports it, so an unremarkable history changes nothing.

    ``level_accuracy`` maps a cognitive level to the learner's accuracy on it, from their own
    recent graded answers. A level with too few answers is ignored rather than guessed at.
    """
    weak = sorted((level for level, acc in level_accuracy.items()
                   if acc is not None and acc < 0.5 and level in COGNITIVE_LEVELS))
    strong = sorted((level for level, acc in level_accuracy.items()
                     if acc is not None and acc >= 0.9 and level in COGNITIVE_LEVELS))
    for candidate in weak:
        for donor in reversed(strong):
            if candidate == donor:
                continue
            index = next((i for i in range(len(plan) - 1, -1, -1)
                          if plan[i].cognitive_level == donor), None)
            if index is None:
                continue
            # Keep the slot's type (the visible contract) and change only what it asks.
            moved = Slot(plan[index].question_type, candidate, plan[index].role)
            adjusted = plan[:index] + (moved,) + plan[index + 1:]
            return adjusted, {"reweighted": True, "from_level": donor,
                              "to_level": candidate, "slot": index}
    return plan, {"reweighted": False}


# ------------------------------------------------------------------ low-information shapes

# The shapes a question must never take. Each is a claim about the SYLLABUS or a request to
# recite a title — neither is knowledge of the point. Kept as named rules so a rejection can
# say which one fired.
_META_PATTERNS: tuple[tuple[str, str], ...] = (
    ("syllabus_membership", r"(本章|本课程|本课|本章节|这一章|该章|课程中|教材中).{0,6}"
                            r"(需要|必须|应当|要|是).{0,6}(掌握|学习|记忆|理解|重点|内容|知识点)"),
    ("syllabus_membership", r"(属于|算作|都是).{0,8}(本章|本课程|课程|章节|知识点)"),
    ("syllabus_membership", r"(是否|是不是|是不是要).{0,6}(重要|需要掌握|重点|必学)"),
    ("syllabus_membership", r"是.{0,4}(很重要的|重要的|核心的).{0,4}(内容|知识点|部分)"),
    ("study_advice", r"学习.{0,8}(有助于|有利于|可以帮助|能够帮助)"),
    ("study_advice", r"(复习|备考|学习)(时|的时候)?.{0,6}(应该|应当|要注意|建议)"),
    ("generic_explain", r"(请|试)?(简述|介绍|概述|阐述|说明).{0,20}(的)?(核心|基本|主要)?含义"
                        r".{0,12}(并|，|,|、).{0,10}(说明|阐述|介绍|解释).{0,10}(适用|应用|使用|场景)"),
    ("generic_explain", r"(谈谈|说说|讲讲).{0,8}(你|自己)?.{0,4}(的)?(理解|看法|认识|体会)"),
)

_META_RE = tuple((name, re.compile(pattern)) for name, pattern in _META_PATTERNS)

# "请简述 X" where X is a bare title is a recitation, not a question. The SAME words with an
# angle attached — "简述图的深度优先遍历的基本过程" — are a perfectly good short answer, so the
# rule is about the ABSENCE of an angle rather than about the verb. Banning "简述" outright would
# throw away real questions, which is its own kind of failure.
_RECITE_PREFIX_RE = re.compile(r"^(请|试)?(简述|介绍|概述|阐述|解释|说明|描述)(一下)?[「『\"'《【]?")
_ANGLE_RE = re.compile(
    r"为什么|原因|理由|依据|过程|步骤|顺序|区别|差异|比较|对比|如何|怎样|怎么|"
    r"推演|计算|分析|定位|错误|条件|状态|举例|影响|作用|优点|缺点|取舍|执行")


def _bare_recitation(value: str) -> bool:
    if not _RECITE_PREFIX_RE.match(value):
        return False
    if _ANGLE_RE.search(value):
        return False
    remainder = _RECITE_PREFIX_RE.sub("", value).strip(" 「」『』\"'《》【】。，,？?")
    return len(remainder) <= 18

# A definition-shaped ask. Allowed ONCE per set (see ``Batch.add``), because for a point whose
# knowledge IS a definition, asking for it once is the correct question — asking for it ten
# times is not.
_DEFINITION_RE = re.compile(
    r"(什么(是|叫)|的定义|指什么|含义(是什么|是)|是(如何|怎样)?定义的|解释.{0,6}(概念|定义))")


def low_information(text: str) -> str | None:
    """The rule a stem or an analysis violates, or None when it says something about the point."""
    value = (text or "").strip()
    if not value:
        return "empty"
    for name, pattern in _META_RE:
        if pattern.search(value):
            return name
    if _bare_recitation(value):
        return "generic_explain"
    return None


def definition_style(text: str) -> bool:
    """Whether the question asks for the definition of the point — allowed at most once."""
    return bool(_DEFINITION_RE.search(text or ""))


# ------------------------------------------------------------------ text identity


# NOTE the characters that are deliberately NOT in this class: + - = % < > * / ^. They are
# OPERATORS, and dropping them merges options that differ only by the operation they name —
# "MaxSize-1" and "MaxSize+1" both reduce to "maxsize1", which made a perfectly good choice
# question look like it had two identical options. Punctuation is noise; an operator is content.
_PUNCT = re.compile(r"[\s　。，、；：？！“”‘’（）《》〈〉【】…—·,.;:?!\"'\[\]{}|`@#$&_~\\]+")
_POINT_MARK = re.compile(r"[「『\"'《](.{1,24}?)[」』\"'》]")


def normalize(text: str, *, drop: str = "") -> str:
    """A stem reduced to what it ASKS: no punctuation, no spacing, no knowledge-point title.

    Dropping the point's own name matters more than it looks. Every question about 「循环队列」
    contains those four characters, so leaving them in makes each generation's questions look
    alike to a similarity check that should be comparing their actual content.
    """
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    if drop:
        for token in {drop, drop.strip()}:
            if token:
                value = value.replace(token.casefold(), "")
    value = _POINT_MARK.sub(lambda m: m.group(1), value)
    return _PUNCT.sub("", value)


def _ngrams(text: str, size: int = 3) -> set[str]:
    if len(text) <= size:
        return {text} if text else set()
    return {text[index:index + size] for index in range(len(text) - size + 1)}


def similarity(left: str, right: str) -> float:
    """Character 3-gram Jaccard overlap. Works for Chinese, where there is no token to split on."""
    a, b = _ngrams(left), _ngrams(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_repeat(left: str, right: str) -> bool:
    """Whether two normalized stems are the same question asked twice."""
    a, b = _ngrams(left), _ngrams(right)
    if not a or not b:
        return False
    shared = len(a & b)
    if shared / len(a | b) >= DUPLICATE_SIMILARITY:
        return True
    return shared / min(len(a), len(b)) >= DUPLICATE_CONTAINMENT


def fingerprint(stem: str, *, drop: str = "") -> str:
    """A stable short id for a question's wording, so a repeat is recognisable later."""
    return hashlib.sha1(normalize(stem, drop=drop).encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------ per-question shapes


_LAZY_OPTION_RE = re.compile(r"以上(都|全)(对|正确|是|错|不正确)|都不(对|正确)|均(正确|错误|对)")


def choice_problem(question: dict) -> str | None:
    """Why these options are not a real choice question, or None.

    The distractors are what make a choice question measure anything: a set of options that
    includes "以上都对" can be answered without the knowledge, and options differing only in
    punctuation measure nothing.
    """
    options = question.get("options") or {}
    texts = [str(value or "").strip() for value in options.values()]
    if len(options) != 4 or any(not text for text in texts):
        return "options_incomplete"
    normalized = [normalize(text) for text in texts]
    if len(set(normalized)) != 4:
        return "options_not_distinct"
    if any(_LAZY_OPTION_RE.search(text) for text in texts):
        return "options_lazy_catch_all"
    if any(len(text) > 120 for text in texts):
        return "options_are_sentences"
    stem = normalize(question.get("stem") or "")
    if any(text == stem for text in normalized):
        return "option_repeats_stem"
    answer = str(question.get("standard_answer") or "").strip().upper()
    if len(answer) > 1:
        letters = sorted(set(answer))
        if len({options.get(letter, "") for letter in letters}) != len(letters):
            return "equivalent_correct_options"
    return None


def true_false_problem(question: dict) -> str | None:
    """A true/false item must be a proposition about the knowledge that is actually decidable.

    "循环队列是重要知识" is not: nobody can get it wrong without failing to read the syllabus.
    """
    stem = str(question.get("stem") or "").strip()
    if low_information(stem):
        return "not_a_knowledge_proposition"
    if definition_style(stem) and len(stem) < 40:
        return "not_a_knowledge_proposition"
    return None


def short_answer_problem(question: dict) -> str | None:
    """A short answer must ask for a reason, a derivation, a comparison, or a trace."""
    stem = str(question.get("stem") or "").strip()
    rule = low_information(stem)
    if rule:
        return rule
    return None


def target_is_generic(target: str, point_titles: tuple[str, ...]) -> bool:
    """Whether an ``assessment_target`` names a point instead of an ability within it."""
    value = normalize(target, drop="")
    if not value or len(value) < 2:
        return True
    for title in point_titles:
        title_norm = normalize(title)
        if title_norm and value == title_norm:
            return True
    return bool(re.fullmatch(r"(概念|定义|含义|理解|知识|内容|要点|基本概念)", value))


# ------------------------------------------------------------------ telemetry


@dataclass
class QualityReport:
    """What the gates did to one batch. Server-side only — never rendered to a learner."""

    batch_size: int = 0
    unique_stems: int = 0
    unique_assessment_targets: int = 0
    duplicate_rejected: int = 0
    low_quality_rejected: int = 0
    recent_duplicate_rejected: int = 0
    retry_count: int = 0
    final_accepted: int = 0
    outcome: str = "pending"
    rejected: list[dict] = field(default_factory=list)
    adaptive: dict = field(default_factory=dict)

    def metric(self) -> dict:
        """Exactly the keys the acceptance test and the log line read."""
        return {
            "BATCH_SIZE": self.batch_size,
            "UNIQUE_STEMS": self.unique_stems,
            "UNIQUE_ASSESSMENT_TARGETS": self.unique_assessment_targets,
            "DUPLICATE_REJECTED": self.duplicate_rejected,
            "LOW_QUALITY_REJECTED": self.low_quality_rejected,
            "RECENT_DUPLICATE_REJECTED": self.recent_duplicate_rejected,
            "RETRY_COUNT": self.retry_count,
            "FINAL_ACCEPTED": self.final_accepted,
            "OUTCOME": self.outcome,
        }


class Rejected(Exception):
    """One question refused by a named gate, with the rule that refused it."""

    def __init__(self, kind: str, reason: str):
        super().__init__(reason)
        self.kind = kind      # duplicate | low_quality
        self.reason = reason


# ------------------------------------------------------------------ the batch gate


class Batch:
    """The set being built, and the gates a candidate must pass to join it.

    Held separately from the persistence layer on purpose: the rules that decide what a
    learner may be shown should be readable and testable without a database.
    """

    def __init__(self, count: int, *, point_titles: tuple[str, ...] = (),
                 avoid_stems: tuple[str, ...] = (), avoid_targets: tuple[str, ...] = (),
                 avoid_fingerprints: tuple[str, ...] = ()):
        self.count = count
        self.point_titles = tuple(title for title in point_titles if title)
        self.stems: list[str] = []
        self.targets: list[str] = []
        self.fingerprints: list[str] = []
        self.questions: list[dict] = []
        self._normalized: list[str] = []
        self._definitions = 0
        self._recent_stems = [normalize(stem) for stem in avoid_stems if stem]
        self._recent_fingerprints = {value for value in avoid_fingerprints if value}
        self._target_use: dict[str, int] = {}
        for target in avoid_targets:
            key = normalize(target)
            if key:
                self._target_use[key] = self._target_use.get(key, 0) + 1
        self.report = QualityReport(batch_size=count)

    # -------------------------------------------------- gates

    def reject(self, kind: str, reason: str, stem: str = "") -> None:
        if kind == "duplicate":
            self.report.duplicate_rejected += 1
            if reason.startswith("recently_asked"):
                # Counted apart from an in-batch repeat: "the model asked this again" and "the
                # model asked what this learner was already asked" are different failures, and
                # only the second one means the avoid list is doing work.
                self.report.recent_duplicate_rejected += 1
        else:
            self.report.low_quality_rejected += 1
        if stem:
            # Remember what was refused, so the retry does not have to refuse it a second time
            # — and so the prompt for the retry can name it. Without this, a model that repeats
            # its own bad question burns every remaining attempt on the same one.
            self._recent_stems.append(
                normalize(stem, drop=self.point_titles[0] if self.point_titles else ""))
        if len(self.report.rejected) < 40:
            self.report.rejected.append({"kind": kind, "reason": reason, "stem": stem[:80]})

    def rejected_stems(self) -> list[str]:
        return [entry["stem"] for entry in self.report.rejected if entry.get("stem")]

    def check(self, question: dict) -> dict:
        """The identity of an acceptable question, or ``Rejected`` naming the rule that refused it.

        Reads the question and never writes to it: a gate that mutates its input cannot be
        called twice on the same candidate to ask "would this pass?" without changing the answer.
        """
        stem = str(question.get("stem") or "")
        normalized = normalize(stem, drop=self.point_titles[0] if self.point_titles else "")
        target = str(question.get("assessment_target") or "").strip()

        # 1. The shapes that say nothing about the knowledge.
        rule = low_information(stem)
        if rule:
            raise Rejected("low_quality", f"stem:{rule}")
        analysis_rule = low_information(question.get("analysis") or "")
        if analysis_rule:
            raise Rejected("low_quality", f"analysis:{analysis_rule}")
        if definition_style(stem):
            if self._definitions >= 1:
                raise Rejected("low_quality", "definition_quota")
        if question.get("question_type") == "true_false":
            problem = true_false_problem(question)
            if problem:
                raise Rejected("low_quality", problem)
        if question.get("question_type") == "short_answer":
            problem = short_answer_problem(question)
            if problem:
                raise Rejected("low_quality", problem)
        if question.get("question_type") in ("single_choice", "multiple_choice"):
            problem = choice_problem(question)
            if problem:
                raise Rejected("low_quality", problem)

        # 2. The ability it claims to exercise.
        if target_is_generic(target, self.point_titles):
            raise Rejected("low_quality", "assessment_target_missing_or_generic")
        target_key = normalize(target)
        reuse = self._target_use.get(target_key, 0)
        if reuse >= MAX_TARGET_REUSE:
            raise Rejected("low_quality", "assessment_target_reused")

        # 3. The same question, asked again.
        if normalized in self._normalized:
            raise Rejected("duplicate", "exact_stem")
        for known in self._normalized:
            if is_repeat(normalized, known):
                raise Rejected("duplicate", "paraphrase_stem")
        for known in self._recent_stems:
            if normalized == known or is_repeat(normalized, known):
                raise Rejected("duplicate", "recently_asked_stem")
        mark = fingerprint(stem, drop=self.point_titles[0] if self.point_titles else "")
        if mark in self._recent_fingerprints or mark in self.fingerprints:
            raise Rejected("duplicate", "recently_asked_fingerprint")

        return {"normalized": normalized, "target_key": target_key, "fingerprint": mark}

    def add(self, question: dict) -> None:
        """Admit a question, or record why it was refused."""
        try:
            identity = self.check(question)
        except Rejected as rejected:
            self.reject(rejected.kind, rejected.reason, str(question.get("stem") or ""))
            raise
        self._normalized.append(identity["normalized"])
        self.fingerprints.append(identity["fingerprint"])
        key = identity["target_key"]
        self._target_use[key] = self._target_use.get(key, 0) + 1
        if definition_style(str(question.get("stem") or "")):
            self._definitions += 1
        self.stems.append(str(question.get("stem") or ""))
        self.targets.append(str(question.get("assessment_target") or "").strip())
        self.questions.append(question)

    # -------------------------------------------------- outcome

    def full(self) -> bool:
        return len(self.questions) >= self.count

    def unique_targets(self) -> int:
        return len({normalize(target) for target in self.targets if target})

    def coverage_ok(self) -> bool:
        return self.unique_targets() >= MIN_UNIQUE_TARGETS.get(self.count, 1)

    def finish(self, outcome: str, *, retry_count: int = 0, adaptive: dict | None = None) -> QualityReport:
        self.report.unique_stems = len({normalize(stem) for stem in self.stems})
        self.report.unique_assessment_targets = self.unique_targets()
        self.report.final_accepted = len(self.questions)
        self.report.retry_count = retry_count
        self.report.outcome = outcome
        if adaptive is not None:
            self.report.adaptive = adaptive
        return self.report
