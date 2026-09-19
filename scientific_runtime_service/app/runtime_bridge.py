"""Stateless StudentTwin scientific execution via the ``zhixue_runtime`` public API.

The runtime service owns NO product learner state. Every request is a deterministic replay
of the supplied (already worker-ordered) event history into a fresh StudentTwin, returning
the resulting scientific state. Only ``get_adapter("student_twin")`` is used — no scientific
formula is copied, no ``runtime_src``/``model_assets`` file is read directly.
"""
from __future__ import annotations

import os

from .contracts import StudentTwinEvent

# The adapter's own per-variant output-semantics string, verbatim. It is repeated here
# because ``infer_panel`` does not restate it; a test pins the two to be identical, so
# this constant can never drift from the component it describes.
EVIDENCE_RELIABILITY_SEMANTICS = "reliability weight w in (0,1) — NOT probability"

class RuntimeInputError(ValueError):
    """The CALLER's request was invalid — a 4xx, not an outage.

    ``zhixue_runtime`` errors derive from ``ZhixueRuntimeError``, not from builtin
    ``ValueError``, so they are translated here. The translation keeps the HTTP layer free
    of any ``zhixue_runtime`` import.
    """


class RuntimeExecutionError(RuntimeError):
    """The component could not be loaded or executed — a bounded 503."""


_adapter_cls = None


def _ensure_runtime_path():
    import sys
    src = os.getenv("ZHIXUE_RUNTIME_SRC")
    if src and src not in sys.path:
        sys.path.insert(0, src)


def _get_adapter_cls():
    global _adapter_cls
    if _adapter_cls is None:
        _ensure_runtime_path()
        from zhixue_runtime.components.adapters import get_adapter
        _adapter_cls = get_adapter("student_twin")
    return _adapter_cls


_adapters: dict = {}


def _load_adapter(component_id: str):
    """Resolve and load one scientific adapter through the runtime's public registry."""
    if component_id not in _adapters:
        _ensure_runtime_path()
        from zhixue_runtime.components.adapters import get_adapter

        cls = get_adapter(component_id)
        home = os.getenv("ZHIXUE_HOME")
        from zhixue_runtime.config import RuntimeConfig
        cfg = RuntimeConfig(home=home) if home else RuntimeConfig()
        adapter = cls(cfg)
        adapter.load()
        _adapters[component_id] = adapter
    return _adapters[component_id]


def _to_scientific(ev: StudentTwinEvent, user_ref: str) -> dict:
    return {
        "event_id": ev.event_id,
        "user_id": user_ref,
        "timestamp": ev.occurred_at,
        "activity_type": ev.activity_type,
        "source": ev.source or "product",
        "concept_id": ev.concept_ref,
        "item_id": ev.item_id,
        "correctness": ev.correct,
        "response_time_ms": ev.response_time_ms,
        "attempts": ev.attempt_no,
        "hints": ev.hints,
    }


def replay_state(user_ref: str, events: list[StudentTwinEvent]) -> dict:
    """Replay ``events`` (in supplied order) into a fresh StudentTwin; return final state."""
    _ensure_runtime_path()
    from zhixue_runtime.config import RuntimeConfig

    cls = _get_adapter_cls()
    home = os.getenv("ZHIXUE_HOME")
    cfg = RuntimeConfig(home=home) if home else RuntimeConfig()
    adapter = cls(cfg)
    try:
        adapter.load()
        for ev in events:
            adapter.ingest_event(_to_scientific(ev, user_ref))
        return adapter.get_state(user_ref).output["result"]
    finally:
        adapter.unload()


def misconception_matches(question: str, answer: str, top_k: int) -> dict:
    """Retrieve candidate misconceptions for one (question, wrong answer) pair.

    The retrieved ontology is the scientific one (English Eedi misconceptions), which is a
    DIFFERENT ontology from the product's Chinese CS/11408 one — retrieved ids are WEAK
    labels, never ground truth. The service does not map them.
    """
    try:
        adapter = _load_adapter("misconception_v2")
        result = adapter.infer(question=question, answer=answer, top_k=top_k)
    except _validation_error() as exc:
        raise RuntimeInputError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise RuntimeExecutionError(f"{type(exc).__name__}: {exc}") from exc
    return result.output


def tutor_policy_action(problem: str, wrong: str, profile: str | None,
                        confusion: str | None, prev_actions: list[str],
                        history: list[list[str]]) -> dict:
    """Suggest a pedagogical action for one turn state.

    The returned action MUST NOT drive the tutor's actual response: the 4-way ontology
    (focus / generic / probing / telling) is a research classifier, not a controller.
    """
    try:
        adapter = _load_adapter("tutor_policy")
        result = adapter.infer(problem=problem, wrong=wrong, profile=profile,
                               confusion=confusion, prev_actions=prev_actions,
                               history=history)
    except _validation_error() as exc:
        raise RuntimeInputError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeExecutionError(f"{type(exc).__name__}: {exc}") from exc
    return result.output


def learner_state_predict(family: str, q: list, r_prev: list, mask: list | None) -> dict:
    """Next-response P(correct) for ONE family over a scientific-ontology sequence.

    ``q``/``r_prev`` must index the FAMILY's own ontology — this function does not map a
    product concept onto a scientific index, and has no product concept to map. The
    knowledge-tracing models were trained on ASSISTments (123 skills) and Junyi (835
    concepts); nothing here translates from the product's Chinese CS408 concept space,
    because no such mapping exists.
    """
    try:
        adapter = _load_adapter("learner_state")
        result = adapter.infer(family=family, q=q, r_prev=r_prev, mask=mask)
    except _validation_error() as exc:
        raise RuntimeInputError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise RuntimeExecutionError(f"{type(exc).__name__}: {exc}") from exc
    return result.output


def evidence_reliability_panel(features_by_variant: dict) -> dict:
    """Score the RELIABILITY PANEL: one weight per variant. No averaging, no selection.

    The weight ``w in (0,1)`` says how much an observation should count in a
    reliability-weighted learner-state update. It is NOT the probability the response is
    correct, NOT a confidence, and NOT a quality judgement about the learner.

    The caller supplies features per variant because the five checkpoints are feature
    ablations with different dimensions. Nothing is imputed here.
    """
    try:
        adapter = _load_adapter("evidence_reliability")
        result = adapter.infer_panel(features_by_variant)
    except _validation_error() as exc:
        raise RuntimeInputError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — asset/dependency failures are bounded
        raise RuntimeExecutionError(f"{type(exc).__name__}: {exc}") from exc
    output = dict(result.output)
    # ``infer_panel`` computes the panel but does not restate the output semantics, so the
    # label is added here. It is the adapter's OWN per-variant string, not a new claim —
    # a test asserts it is character-identical to what ``infer`` reports.
    output["score_semantics"] = EVIDENCE_RELIABILITY_SEMANTICS
    return output


_input_validation_error = None


def _validation_error():
    """The runtime's invalid-input class.

    Resolved lazily and NEVER fatally: if the runtime stack is not importable, an empty
    tuple is returned, which matches nothing — so the caller's ``except Exception``
    fallback stays in charge instead of this lookup masking the real failure.
    """
    global _input_validation_error
    if _input_validation_error is None:
        try:
            _ensure_runtime_path()
            from zhixue_runtime.errors import InputValidationError
            _input_validation_error = InputValidationError
        except Exception:  # noqa: BLE001
            _input_validation_error = ()
    return _input_validation_error
