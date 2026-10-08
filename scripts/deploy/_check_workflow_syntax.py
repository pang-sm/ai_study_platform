"""Syntax-check the shell embedded in a workflow's heredocs.

The workflows carry their real logic inside ``ssh ... <<'SOMEEOF'`` blocks. A YAML parser
cannot see a broken ``fi`` in there, so this extracts every quoted heredoc body, de-indents
it, and runs ``bash -n`` — the same shell that will execute it on the host.

Usage: _check_workflow_syntax.py <workflow.yml> [more.yml ...]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

_HEREDOC = re.compile(r"<<'([A-Za-z0-9_]+)'[ \t]*\n(.*?)\n[ \t]*\1[ \t]*$", re.S | re.M)


def check(path: str) -> int:
    raw = open(path, encoding="utf-8").read()
    failures = 0
    for index, match in enumerate(_HEREDOC.finditer(raw)):
        tag, body = match.group(1), match.group(2)
        lines = body.split("\n")
        indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
        cut = min(indents) if indents else 0
        script = "\n".join(line[cut:] if len(line) >= cut else line for line in lines)

        handle, tmp = tempfile.mkstemp(suffix=".sh")
        os.close(handle)
        with open(tmp, "w", encoding="utf-8") as file_handle:
            file_handle.write(script)
        result = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True)
        status = "OK" if result.returncode == 0 else "FAIL"
        print(f"{path} {tag}#{index}: bash -n -> {status}")
        if result.returncode:
            print(result.stderr[:3000])
            failures += 1
        os.unlink(tmp)
    return failures


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: _check_workflow_syntax.py <workflow.yml> [...]")
    total = sum(check(path) for path in sys.argv[1:])
    print("SYNTAX_ERRORS =", total)
    raise SystemExit(1 if total else 0)
