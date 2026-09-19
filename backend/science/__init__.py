"""Product Backend → Scientific Runtime bridge (Layer D Intelligence boundary).

The Product Backend and the self-developed scientific models are separate processes:

    Product Backend  --HTTP-->  Scientific Runtime Service  --in-process-->  zhixue_runtime

HARD BOUNDARY (B1): nothing under this package may import ``torch``, ``transformers``,
``faiss`` or ``zhixue_runtime``. A scientific capability is only ever reached through
:mod:`science.client`. This keeps the product importable and deployable without the
scientific stack, and keeps scientific failures from reaching the core learning loop.

Nothing here writes learner facts. Every function returns a PREVIEW.
"""
