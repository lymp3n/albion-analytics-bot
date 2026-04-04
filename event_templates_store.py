"""
Shared event roster templates (events_templates.txt).
Read on every use so Discord /event create and autocomplete see dashboard edits immediately.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

_MAX_BYTES = 512_000

_REPO_ROOT = Path(__file__).resolve().parent


def templates_file_path() -> Path:
    override = (os.environ.get("EVENT_TEMPLATES_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "events_templates.txt"


_DEFAULT_TEXT = (
    "[Castle]\n"
    "1. Caller\n"
    "2. Healer\n"
    "3. DPS\n\n"
    "[Open World]\n"
    "1. Tank\n"
    "2. DPS\n"
)


def parse_templates_text(content: str) -> Dict[str, List[str]]:
    templates: Dict[str, List[str]] = {}
    current: str | None = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            if current:
                templates[current] = []
            else:
                current = None
        elif current:
            role_name = re.sub(r"^\d+\.\s*", "", line)
            templates[current].append(role_name)
    return templates


def validate_templates_content(content: str) -> Tuple[bool, str]:
    if not isinstance(content, str):
        return False, "Body must be a string."
    raw = content.encode("utf-8")
    if len(raw) > _MAX_BYTES:
        return False, f"File too large (max {_MAX_BYTES // 1024} KB)."
    parsed = parse_templates_text(content)
    if not parsed:
        return False, "No templates found. Use lines like [Template Name] then numbered roles."
    for name, roles in parsed.items():
        if not roles:
            return False, f'Template "{name}" has no role lines.'
    return True, ""


def read_raw_text() -> str:
    path = templates_file_path()
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_DEFAULT_TEXT, encoding="utf-8")
            return _DEFAULT_TEXT
        return path.read_text(encoding="utf-8")
    except OSError:
        return _DEFAULT_TEXT


def load_templates_dict() -> Dict[str, List[str]]:
    """Same shape as legacy get_templates(); always reads current file from disk."""
    try:
        content = read_raw_text()
        parsed = parse_templates_text(content)
        if parsed:
            return parsed
    except Exception:
        pass
    return parse_templates_text(_DEFAULT_TEXT)


def save_raw_text(content: str) -> None:
    ok, err = validate_templates_content(content)
    if not ok:
        raise ValueError(err)
    path = templates_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content
    if not data.endswith("\n"):
        data += "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)
