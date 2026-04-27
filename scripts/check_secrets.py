"""Fail CI when likely secrets are present in tracked files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{16,}['\"]"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----"),
]

SAFE_FILES = {
    ".env.example",
    "scripts/check_secrets.py",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def main() -> int:
    failures: list[str] = []
    for path in tracked_files():
        if path.as_posix() in SAFE_FILES or not path.exists() or path.is_dir():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(path.as_posix())
                break

    if failures:
        print("Potential secrets found in tracked files:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("No likely secrets found in tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
