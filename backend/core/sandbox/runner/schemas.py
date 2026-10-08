"""Wire schemas for the sandbox runner — SECURITY_S0B-P1.

The runner accepts ONLY this bounded shape. There is deliberately no field for argv,
image, mounts, environment, host paths, capabilities, a raw command or a privileged flag:
the hardened ``docker run`` argv is fixed server-side in
:mod:`core.sandbox.docker_backend`. A caller cannot influence anything below the
source / stdin / operation level.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.sandbox.docker_backend import _normalize_path
from core.sandbox.limits import (
    IMAGES,
    MAX_FILE_BYTES,
    MAX_STDIN_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
)
from core.sandbox.types import ExecutionRequest, ExecutionResult, SourceFile

MAX_FILES = 64


class SourceFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(min_length=1, max_length=1024)
    content: str = ""

    @field_validator("relative_path")
    @classmethod
    def _contained_path(cls, value: str) -> str:
        """Reject an absolute or ``..`` path HERE, not deeper in the run.

        The runner already refuses such a path when it writes the file, but by then the
        request has passed validation and the refusal surfaces as an unhandled error. A
        crafted path is a malformed request, so it belongs in the schema — and reusing the
        backend's own normaliser keeps the two rules from drifting apart. The returned
        value is the normalised form, so the file the schema accepted is the file that gets
        written and the name that reaches the container argv.
        """
        try:
            return _normalize_path(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class ExecutionRequestModel(BaseModel):
    """One bounded execution request. ``extra="forbid"`` rejects any unknown field."""

    model_config = ConfigDict(extra="forbid")

    language: str
    files: list[SourceFileModel] = Field(default_factory=list)
    entry_file: str = ""
    main_class: str | None = None
    stdin: str = ""
    compile_files: list[str] | None = None
    wall_time_ms: int | None = None
    compile_only: bool = False
    request_id: str = ""

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        if value not in IMAGES:
            raise ValueError("unsupported language")
        return value

    @model_validator(mode="after")
    def _size_bounds(self) -> "ExecutionRequestModel":
        if len(self.files) > MAX_FILES:
            raise ValueError("too many files")
        total = 0
        for item in self.files:
            size = len(item.content.encode("utf-8"))
            if size > MAX_FILE_BYTES:
                raise ValueError("a source file exceeds the size limit")
            total += size
        if total > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("total source exceeds the size limit")
        if len(self.stdin.encode("utf-8")) > MAX_STDIN_BYTES:
            raise ValueError("stdin exceeds the size limit")
        return self

    def to_request(self) -> ExecutionRequest:
        return ExecutionRequest(
            language=self.language,
            files=tuple(
                SourceFile(relative_path=item.relative_path, content=item.content)
                for item in self.files
            ),
            entry_file=self.entry_file,
            main_class=self.main_class,
            stdin=self.stdin,
            compile_files=(
                tuple(self.compile_files) if self.compile_files is not None else None
            ),
            wall_time_ms=self.wall_time_ms,
            compile_only=self.compile_only,
        )


def result_to_dict(result: ExecutionResult) -> dict:
    """Project an ExecutionResult onto the wire. Never carries a host path or container id."""
    return {
        "language": result.language,
        "verdict": result.verdict.value,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "timed_out": result.timed_out,
        "output_truncated": result.output_truncated,
        "compile": (
            None
            if result.compile is None
            else {"ok": result.compile.ok, "diagnostic": result.compile.diagnostic}
        ),
        "internal_error": result.internal_error,
    }
