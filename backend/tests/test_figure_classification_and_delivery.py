"""The figure mistakes that actually happened, turned into checks that cannot silently recur.

Each test below corresponds to a failure this project produced at least once:

  * a figure attached to a question that has none            (computer_network 2022 Q38)
  * a question with no figure counted as needing one          (data_structure 2026 Q7)
  * a figure that was accurate but not the one the question   (computer_organization 2026 Q43)
    needed, left on the page
  * a scraped raster one URL away from serving                (the whole legacy trees)
  * the frontend regex treated as the authority on which
    questions need figures

The authority is ``exam_resources/11408/figure_classification.json``. These tests hold what the
resolver actually SERVES to it, at the filesystem level, so they do not depend on which rows a
particular test database happens to hold.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import exam_past_paper

RESOURCES = Path(exam_past_paper.EXAM_RESOURCES_DIR)
CLASSIFICATION_FILE = RESOURCES / "figure_classification.json"
RASTER = (".jpg", ".jpeg", ".png", ".webp")

CLASSIFICATION: dict[str, str] = json.loads(
    CLASSIFICATION_FILE.read_text(encoding="utf-8"))["classification"]

# Figures deliberately WITHDRAWN: the page must not advertise one for these questions.
#
# Currently EMPTY. `data_structure/2024/Q4` was here until its pointer chains could be reproduced
# in full (firstedge + every ilink/jlink, all five vertex chains closing with no omission and no
# repeat). The mechanism is kept because withdrawing an accurate-but-wrong figure is the correct
# response when a figure cannot be reproduced faithfully — and an empty set must not silently
# become "nothing is ever checked".
WITHDRAWN: set[str] = set()

REQUIRED = sorted(k for k, v in CLASSIFICATION.items() if v == "FIGURE_REQUIRED")
OPTIONAL = sorted(k for k, v in CLASSIFICATION.items() if v == "FIGURE_OPTIONAL")
NO_FIGURE = sorted(k for k, v in CLASSIFICATION.items() if v == "NO_FIGURE")


def _split(key: str) -> tuple[str, int, int]:
    subject, year, number = key.split("/")
    return subject, int(year), int(number.removeprefix("Q"))


def _served(key: str) -> list[str]:
    """What the resolver hands the frontend for this question — the real served contract."""
    subject, year, number = _split(key)
    return exam_past_paper._bank_resources(subject, year, number)


def _on_disk(key: str) -> list[str]:
    subject, year, number = _split(key)
    directory = RESOURCES / subject / "past_papers" / "figures" / str(year)
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.glob(f"{year}_q{number}_*.svg"))


# ── 1 & 6: nothing is served that should not be ────────────────────────────────────

@pytest.mark.parametrize("key", NO_FIGURE)
def test_a_no_figure_question_serves_no_image(key):
    """`data_structure 2026 Q7` matched the frontend regex on the word 图中 and was counted as a
    figure question. It has no figure; nothing may be served for it."""
    assert _served(key) == [], f"{key} is NO_FIGURE but serves {_served(key)}"


@pytest.mark.parametrize("key", sorted(WITHDRAWN))
def test_a_withdrawn_figure_is_gone_from_both_disk_and_delivery(key):
    """A figure that was accurate but not the one the question needs still misleads, so it was
    removed. Nothing may put it back."""
    assert _served(key) == [], f"{key} still serves a figure"
    assert _on_disk(key) == [], f"{key} still has a file on disk"


# ── 2: every required question that is not withdrawn actually serves a figure ───────

@pytest.mark.parametrize("key", [k for k in REQUIRED if k not in WITHDRAWN])
def test_every_required_question_serves_a_figure(key):
    names = _served(key)
    assert names, f"{key} is FIGURE_REQUIRED, not withdrawn, and serves nothing"
    subject, year, _number = _split(key)
    for name in names:
        assert name.endswith(".svg"), name
        assert exam_past_paper.resolve_resource_file(subject, year, name) is not None, \
            f"{key}: {name} does not resolve to a real file"


# ── 3 & 4: identity — one figure belongs to one question, and it lines up ───────────

def test_no_figure_file_is_shared_between_two_questions():
    seen: dict[str, str] = {}
    for key in dict.fromkeys(list(CLASSIFICATION)):
        for name in _on_disk(key):
            assert name not in seen, f"{name} serves both {seen.get(name)} and {key}"
            seen[name] = key
    assert seen, "no figure was inspected"


def test_every_figure_on_disk_belongs_to_a_classified_question():
    """Catches a figure whose (subject, year, number) drifted — how a figure ends up on the wrong
    question. `computer_network 2022 Q38` was exactly this class of mistake."""
    unclassified = []
    for path in RESOURCES.glob("*/past_papers/figures/*/*.svg"):
        subject, year = path.parts[-5], int(path.parts[-2])
        match = re.match(rf"^{year}_(?:q)?(\d+)_(\d+)\.svg$", path.name)
        assert match, f"figure filename does not encode its question: {path.name}"
        key = f"{subject}/{year}/Q{int(match.group(1))}"
        if key not in CLASSIFICATION:
            unclassified.append(key)
    assert sorted(set(unclassified)) == []


def test_the_classification_uses_only_the_three_defined_values():
    assert set(CLASSIFICATION.values()) == {"FIGURE_REQUIRED", "FIGURE_OPTIONAL", "NO_FIGURE"}


def test_the_classification_covers_only_known_papers():
    for key in CLASSIFICATION:
        subject, year, number = _split(key)
        assert subject in exam_past_paper.SUBJECT_NAMES, key
        assert 2009 <= year <= 2030, key
        assert number > 0, key


# ── 5: no scraped raster is reachable ───────────────────────────────────────────────

@pytest.mark.parametrize("key", sorted(CLASSIFICATION))
def test_nothing_serves_a_scraped_raster(key):
    for name in _served(key):
        assert not name.lower().endswith(RASTER), f"{key}: {name}"


# ── 7: the regex is a heuristic, not the authority ──────────────────────────────────

def test_the_regex_is_not_the_classification_authority():
    """`data_structure 2026 Q7` is the regression: the regex matches its stem, and the canonical
    classification still says NO_FIGURE. If the two ever agree again, the authority moved back
    into the heuristic."""
    prose = "设有向图顶点数为 n，只有一个初始顶点 S，有多个标记顶点 T，图中每条边有一个字符"
    assert CLASSIFICATION["data_structure/2026/Q7"] == "NO_FIGURE"
    assert re.search("图中", prose), "the stem no longer contains the phrase that fooled the regex"


def test_the_required_count_is_the_number_this_project_last_verified():
    """Pinned deliberately: a silent change to the required set is exactly the kind of drift the
    regex used to hide. Re-derive by hand before changing it."""
    assert len(REQUIRED) == 27
    assert len(NO_FIGURE) == 1
    assert len(OPTIONAL) == 11
