"""Learner-safe MODEL PREFERENCE (POST /chat ``model_preference``).

WHAT THESE TESTS HOLD
---------------------
A learner never picks a MODEL. They pick a CLASS (``basic`` / ``standard`` / ``premium`` /
``reasoning``) and the Router still decides which qualified model inside that class serves
the request — entitlement, cost, availability and fallback all stay with the Router. These
tests use the REAL pool and the REAL router (nothing is mocked):

1. a preference can NEVER escape entitlement: Free has no reasoning-class model for
   ``tutor.chat``, so asking for one fails closed;
2. a class the tier DOES allow narrows the choice and the served model really is of that
   class;
3. an unknown key fails closed (never a silent auto-selection);
4. ``preference_options`` exposes ONLY ``{key, label}`` — no provider / model / price / tier
   may ever reach the client (the §I.5 hard product rule);
5. a class with several qualified models is offered ONCE (the Router, not the learner,
   chooses among them).
"""
import pytest

from ai import pool
from ai.health import registry as health_registry
from ai.router import select_model

CAPABILITY = "tutor.chat"


@pytest.fixture(autouse=True)
def _clean_health():
    """Availability is a runtime singleton shared across the process: reset it so these
    class-selection tests are deterministic and independent of test order."""
    health_registry().reset()
    yield
    health_registry().reset()


def _entry_for(model: str):
    return next(e for e in pool.QUALIFIED_POOL if e.model == model)


# ================================================================ 1. entitlement is a wall


def test_free_cannot_get_a_reasoning_class_model():
    # Free's qualified tutor.chat set exists (a plain call works) ...
    baseline = select_model("free", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200)
    assert baseline.ok is True

    # ... but it holds no reasoning-class model, so asking for one must fail closed.
    decision = select_model("free", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, preference="reasoning")
    assert decision.ok is False
    assert decision.reason == "preference_not_available"

    # The reason the class is empty is entitlement, not a missing qualification: no
    # free-eligible tutor.chat entry is a thinking model.
    free_entries = pool.qualified_models_for("free", CAPABILITY)
    assert free_entries
    assert all(not e.thinking for e in free_entries)


# ================================================================ 2. a real narrowing


def test_advanced_premium_preference_selects_a_premium_model():
    decision = select_model("advanced", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, preference="premium")
    assert decision.ok is True
    assert pool.preference_class(_entry_for(decision.model)) == "premium"

    # And it is a real narrowing: the auto choice for the same request is a different,
    # cheaper class (advanced/tutor.chat's cheapest qualified model is basic).
    auto = select_model("advanced", CAPABILITY, input_tokens=100,
                        expected_output_tokens=200)
    assert auto.ok is True
    assert pool.preference_class(_entry_for(auto.model)) == "basic"
    assert auto.model != decision.model


def test_advanced_reasoning_preference_selects_a_reasoning_model():
    decision = select_model("advanced", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, preference="reasoning")
    assert decision.ok is True
    assert pool.preference_class(_entry_for(decision.model)) == "reasoning"


@pytest.mark.parametrize("value", ["auto", ""])
def test_auto_is_the_unchanged_auto_recommendation(value):
    auto = select_model("advanced", CAPABILITY, input_tokens=100,
                        expected_output_tokens=200)
    same = select_model("advanced", CAPABILITY, input_tokens=100,
                        expected_output_tokens=200, preference=value)
    assert same.ok is True
    assert same.model == auto.model


# ================================================================ 3. unknown key fails closed


def test_unknown_preference_key_fails_closed():
    decision = select_model("advanced", CAPABILITY, input_tokens=100,
                            expected_output_tokens=200, preference="turbo")
    assert decision.ok is False
    assert decision.reason == "preference_not_available"
    # it did NOT quietly fall back to the auto recommendation
    assert decision.model is None


def test_normalize_preference_collapses_junk_to_auto():
    assert pool.normalize_preference(None) == ""
    assert pool.normalize_preference("") == ""
    assert pool.normalize_preference("auto") == ""
    assert pool.normalize_preference("AUTO") == ""
    assert pool.normalize_preference("turbo") == ""
    assert pool.normalize_preference("premium") == "premium"
    assert pool.normalize_preference(" Reasoning ") == "reasoning"


# ================================================================ 4. no model / provider leak


def test_preference_options_are_learner_safe():
    options = pool.preference_options("advanced", CAPABILITY)
    assert {"key": "auto", "label": "自动推荐"} in options

    providers = {e.provider for e in pool.QUALIFIED_POOL}
    models = {e.model for e in pool.QUALIFIED_POOL}
    forbidden = providers | models

    for option in options:
        assert set(option.keys()) == {"key", "label"}, option
        for text in (option["key"], option["label"]):
            assert not any(token in text for token in forbidden), (option, text)


def test_preference_options_use_only_the_closed_vocabulary():
    # The keys are the documented learner classes and nothing else: a free-form string
    # (a price, a tier name, a model nickname) can never appear as a preference key.
    allowed_keys = {"auto", *pool.PREFERENCE_CLASSES}
    allowed_labels = {pool.AUTO_LABEL, *pool.PREFERENCE_LABELS.values()}
    for option in pool.preference_options("advanced", CAPABILITY):
        assert option["key"] in allowed_keys
        assert option["label"] in allowed_labels
    # the known classes are exactly basic / standard / premium / reasoning
    assert pool.PREFERENCE_CLASSES == ("basic", "standard", "premium", "reasoning")


def test_entry_dict_carries_the_learner_class():
    # additive: every detailed option now also names its class, same vocabulary as the
    # picker, and still without ever exposing more than the entry already did.
    entry = _entry_for("qwen3.8-flash")
    assert pool._entry_dict(entry)["preference_key"] == "basic"
    assert pool._entry_dict(_entry_for("doubao-general"))["preference_key"] == "reasoning"


# ================================================================ 5. one entry per class


def test_a_class_with_several_models_is_offered_once():
    # Free tutor.chat has THREE qualified basic models; the picker must show basic once.
    free_basic = [e for e in pool.qualified_models_for("free", CAPABILITY)
                  if pool.preference_class(e) == "basic"]
    assert len(free_basic) >= 2

    options = pool.preference_options("free", CAPABILITY)
    keys = [o["key"] for o in options]
    assert keys.count("basic") == 1
    assert keys == ["auto", "basic"]
    # and the order is the documented stable order
    full = [o["key"] for o in pool.preference_options("advanced", CAPABILITY)]
    assert full == ["auto", "basic", "standard", "premium", "reasoning"]
