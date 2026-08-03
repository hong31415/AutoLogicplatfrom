from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".bat", ".cfg", ".conf", ".csv", ".css", ".env", ".example", ".html",
    ".ini", ".js", ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml",
}
PATTERNS = {
    "private local path": re.compile(r"(?i)(?:[a-z]:\\Users\\|/(?:Users|home)/[^/\s]+/)"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "probable API key": re.compile(r"(?i)\b(?:sk|ghp|github_pat|glpat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b"),
    "credential assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|password|passwd|secret|token)\s*[=:]\s*['\"](?!your-|<|\.\.\.)[A-Za-z0-9_./+=-]{12,}['\"]"
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT.as_posix()}",
            "-c",
            "core.quotepath=false",
            "ls-files",
            "-z",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [PROJECT_ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[tuple[str, str, int]] = []
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path.relative_to(PROJECT_ROOT).as_posix(), label, line_number))
    if findings:
        print("Security audit failed. Review these locations without committing any secret values:")
        for path, label, line_number in findings:
            print(f"- {path}:{line_number} ({label})")
        return 1
    print(f"Security audit passed for {len(tracked_files())} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
