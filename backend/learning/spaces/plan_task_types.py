"""Which task kinds each learning space's plan can hold.

ONE TABLE, THREE VOCABULARIES
-----------------------------
``ExamStudyPlanTask`` is one table shared by course learning, exam prep and programming, but the
kinds of task a space can OWN are not the same — because "completed" is earned differently in
each, and only the plan's own completion engine decides whether it can be earned at all
(``main._compute_task_completion``, whose docstring states the semantics):

    knowledge         mark its knowledge points learned
    chapter_practice  practise its questions          (exam prep only)
    review            clear its review-due leaves

A task type with no completion rule is not a task. The plan would render it as "等待开始"
forever, no learner action could ever finish it, and its status column would never move. That is
why this list IS the product rule rather than a convenience: the vocabulary is bounded by what
can be completed, not by what a form might accept.

``practice`` and ``custom`` are therefore deliberately absent. Neither has a completion branch,
and no space's own creation endpoint produces either — they were reachable only through the plan
adjustment path, which is exactly the inconsistency this module closes.

WHO USES THIS
-------------
Every writer of a plan task: the course, exam and programming creation endpoints and the plan
adjustment apply path. There is no second list to drift from.
"""
from __future__ import annotations

# Course learning: a course plan task is learned, not practised — the completion engine returns
# the named refusal "课程学习不使用章节练习任务" for a chapter-practice task in this space.
COURSE_LEARNING_TASK_TYPES = ("knowledge", "review")

# Exam prep (CS408 and the other national subjects): the three the completion engine implements,
# and the three the exam plan surfaces label.
EXAM_PREP_TASK_TYPES = ("knowledge", "chapter_practice", "review")

# Programming: this space keeps its own task kinds in its own vocabulary.
PROGRAMMING_TASK_TYPES = ("knowledge", "exercise", "project", "review")

PLAN_TASK_TYPES_BY_NAMESPACE = {
    "course_learning": COURSE_LEARNING_TASK_TYPES,
    "exam_prep": EXAM_PREP_TASK_TYPES,
    "programming": PROGRAMMING_TASK_TYPES,
}


def plan_task_types(space: str) -> tuple[str, ...]:
    """The task kinds ``space`` can own. An unknown space owns none, so nothing is written."""
    return PLAN_TASK_TYPES_BY_NAMESPACE.get((space or "").strip(), ())
