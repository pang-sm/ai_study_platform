"""Canonical filesystem containment for uploaded content — SECURITY_S1A.

Every write of user-influenced content under a storage root goes through
:func:`safe_join_under_root`. The rule it enforces is narrow and absolute:

    a written path must stay inside its storage root, no matter what the caller passes

That matters because the previous upload sink built its directory from the *username*
(``UPLOAD_ROOT / username``) with no validation, so a username containing ``..`` or a
separator escaped the root entirely. The fix is architectural — user-facing identity is no
longer filesystem identity — but the containment helper is what keeps the guarantee true
for the filename component and for any sink added later.

Two deliberate choices:

* **Containment is proven on the RESOLVED path, by identity-or-ancestry.** A string prefix
  test is wrong: ``/srv/uploads2`` starts with ``/srv/uploads`` without living inside it.
  Resolving first also collapses ``..`` and follows symlinks, so a symlinked parent that
  points outside the root is caught rather than trusted.
* **Segments are validated individually, before joining.** ``pathlib`` silently discards the
  left side when a later component is absolute (``Path("/root") / "/etc/passwd"`` is
  ``/etc/passwd``), so an absolute or drive-letter segment must never reach ``joinpath``.
"""
from __future__ import annotations

import re
from pathlib import Path

_SEPARATORS = ("/", "\\")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class StoragePathError(ValueError):
    """A path component would have left its storage root."""


def validate_segment(segment: object) -> str:
    """Return one safe path component, or raise.

    A segment is a single name — never a path. Anything that could introduce structure
    (separator), relocate the join (absolute or drive-letter form), or terminate the name
    early (NUL) is refused rather than cleaned, so a caller cannot pass a nearly-safe value
    and get a silently different path than it asked for.
    """
    value = str(segment)
    if not value.strip():
        # Also rejects the tags-only / whitespace-only case, which renders as an invisible
        # directory name rather than an obvious mistake.
        raise StoragePathError("empty path segment")
    if "\x00" in value:
        raise StoragePathError("NUL byte in path segment")
    for separator in _SEPARATORS:
        if separator in value:
            raise StoragePathError(f"path separator in segment {value!r}")
    if value in (".", ".."):
        raise StoragePathError(f"relative path segment {value!r}")
    if _DRIVE_PREFIX.match(value):
        # Windows drive syntax: `C:foo` is drive-relative and would defeat joinpath.
        raise StoragePathError(f"drive-letter segment {value!r}")
    return value


def is_contained(root: Path, candidate: Path) -> bool:
    """True when ``candidate`` resolves to ``root`` itself or something beneath it.

    Exposed separately so the rule can be tested directly — including on hosts where a real
    symlink cannot be created.
    """
    resolved_root = Path(root).resolve()
    resolved_candidate = Path(candidate).resolve()
    return resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents


def safe_join_under_root(root: Path, *segments: object, mkdir_parents: bool = False) -> Path:
    """Join ``segments`` beneath ``root``, proving the result stays inside it.

    Raises:
        StoragePathError: if any segment is structurally unsafe, or if the joined path
            resolves outside ``root`` (e.g. through a symlinked parent).
    """
    resolved_root = Path(root).resolve()
    if mkdir_parents:
        resolved_root.mkdir(parents=True, exist_ok=True)

    validated = [validate_segment(segment) for segment in segments]
    candidate = resolved_root.joinpath(*validated)

    if mkdir_parents and candidate.parent != candidate:
        candidate.parent.mkdir(parents=True, exist_ok=True)

    if not is_contained(resolved_root, candidate):
        raise StoragePathError(f"path escapes storage root: {candidate}")

    return candidate
