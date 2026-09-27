"""The E2E harness's scripted provider must never be reachable from the product.

WHAT THIS HOLDS
---------------
``scripts/e2e_serve.py`` teaches the shared ``FakeProvider`` to answer the plan-adjustment
workflow with a JSON diff, because that route parses a structured reply and a sentence-shaped
double can only ever produce ``unusable_proposal``. That behaviour belongs to the harness the
way ``FakeProvider`` itself does — it is what lets an authenticated browser exercise the real
capability → permission → usage → orchestrator → provider → settle chain without a paid call.

It must stop at the harness. A product that could be talked into answering from a canned string
by an environment variable is a different product, so the substitution lives in a launcher that
``main`` never imports — and that is asserted here rather than assumed:

1. ``main`` (and the orchestrator it drives) never references the launcher or its scripted
   provider;
2. importing the product leaves ``ai.orchestrator.default_provider_factory`` as the REAL
   factory that reaches a provider adapter;
3. the scripted plan-adjustment answer is not reachable from the shared ``FakeProvider`` either —
   a test that wants it must go through the harness module explicitly.
"""
from pathlib import Path

import ai.orchestrator as orchestrator
import ai.providers as providers
import main


def test_the_product_never_imports_the_e2e_harness():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "e2e_serve" not in source
    assert "e2e_harness" not in source
    # The scripted answer lives in the launcher, not in product code.
    assert "_plan_adjustment_content" not in source
    assert "_HarnessProvider" not in source


def test_the_default_provider_factory_is_the_real_one():
    """`main` leaves the orchestrator pointed at the real factory, not at a double."""
    assert orchestrator.default_provider_factory.__module__ == "ai.orchestrator"
    assert orchestrator.default_provider_factory is not None
    # And the launcher's substitution is not applied just by importing the product.
    assert orchestrator.default_provider_factory.__name__ == "default_provider_factory"


def test_the_shared_fake_provider_has_no_workflow_scripts():
    """A plain FakeProvider answers every capability with the same sentence.

    If a workflow script were folded into the shared double, the product's own tests would
    start passing on answers that never came from a plan, a question or an analysis.
    """
    source = Path(providers.__file__).read_text(encoding="utf-8")
    for marker in ("plan_adjustment", "create_task", "update_task", "_plan_adjustment_content"):
        assert marker not in source, f"{marker} belongs to the harness, not to the shared double"
