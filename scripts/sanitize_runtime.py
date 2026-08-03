from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = PROJECT_ROOT / "backend" / "logicrag_runtime"
PUBLIC_ARTIFACTS = {
    "global_template.json",
    "state_index.json",
    "induction_summary.json",
    "run_manifest.json",
}
SECRET_KEYS = {
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "token",
    "username",
    "credential",
}
LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)[a-z]:\\Users\\[^\\/\s\"']+(?:\\[^\r\n\"']*)?"),
    re.compile(r"/(?:Users|home)/[^/\s\"']+(?:/[^\r\n\"']*)?"),
)


def sanitize_string(value: str) -> str:
    cleaned = value
    for pattern in LOCAL_PATH_PATTERNS:
        cleaned = pattern.sub("<local-path>", cleaned)
    return cleaned


def sanitize(value: Any, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if any(part in normalized_key for part in SECRET_KEYS):
        return ""
    if isinstance(value, dict):
        return {item_key: sanitize(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return sanitize_string(value)
    return value


def main() -> None:
    sanitized = 0
    for path in sorted(RUNTIME_ROOT.glob("*/*.json")):
        if path.name not in PUBLIC_ARTIFACTS:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(
            json.dumps(sanitize(payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sanitized += 1
    print(f"Sanitized {sanitized} public DFA artifact(s).")


if __name__ == "__main__":
    main()
