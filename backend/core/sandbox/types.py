"""Value types for isolated learner-code execution — SECURITY_S0B.

These describe an execution request and its outcome without any knowledge of how
the isolation is achieved. They exist so the calling code (the exercise judge, the
project runner, the terminals) never has to know a container is involved, and so a
future non-Docker backend can reuse every call site unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """The terminal judgement of one execution.

    ``compile_error`` is deliberately distinct from ``runtime_error``: a learner who
    cannot build their program needs a different message than one whose program ran
    and failed.
    """

    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    COMPILE_ERROR = "compile_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    MEMORY_LIMIT = "memory_limit"
    OUTPUT_LIMIT = "output_limit"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class SourceFile:
    """One learner-owned file, identified by a path relative to the project root."""

    relative_path: str
    content: str


@dataclass(frozen=True)
class ExecutionRequest:
    """Everything needed to compile and run one program in isolation."""

    language: str  # "Python" | "C" | "C++" | "Java"
    files: tuple[SourceFile, ...]
    entry_file: str = ""
    main_class: str | None = None
    stdin: str = ""
    # Relative paths that participate in compilation (C/C++/Java). None means "every
    # file whose extension matches the language" — the same default the legacy runner
    # used. Files NOT listed here are still written to disk (headers, includes) but
    # are not passed to the compiler, preserving the current project-execute contract.
    compile_files: tuple[str, ...] | None = None
    # Overrides the per-language default from limits.py; None means "use the default".
    wall_time_ms: int | None = None
    # When True the program is COMPILED but never executed (syntax diagnosis). Only
    # native languages honour this; a compile-only request never runs learner code.
    compile_only: bool = False


@dataclass(frozen=True)
class CompileResult:
    """The compile half of a native-language run. ``ok`` False means the run never happened."""

    ok: bool
    diagnostic: str = ""


@dataclass
class ExecutionResult:
    """The outcome of one execution attempt. Never carries a host path or container id."""

    language: str
    verdict: Verdict
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    timed_out: bool = False
    output_truncated: bool = False
    compile: CompileResult | None = None
    internal_error: str = ""

    @property
    def compiled(self) -> bool:
        """True when compilation either succeeded or was not required."""
        return self.compile is None or self.compile.ok

    @property
    def compile_error(self) -> str | None:
        if self.compile is not None and not self.compile.ok:
            return self.compile.diagnostic
        return None

    @property
    def passed_single(self) -> bool:
        """A single stdin/stdout case passes only on a clean exit."""
        return self.verdict is Verdict.ACCEPTED


@dataclass
class TestCaseResult:
    """One judged case: the raw sample plus the isolated execution it produced."""

    sample: dict = field(default_factory=dict)
    result: ExecutionResult | None = None
