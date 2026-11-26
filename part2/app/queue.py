"""Queue stored as one name per line.

The HTTP server must call these functions. Tests call them directly,
with a temporary directory, and do not start Docker.
"""

from __future__ import annotations

from pathlib import Path


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or "\n" in name or "\r" in name:
        raise ValueError("invalid name")
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 40:
        raise ValueError("invalid name")
    return cleaned


def join(path: str | Path, name: str) -> int:
    """Append one person and return the ticket number."""
    cleaned = _validate_name(name)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    existing = file_path.read_text(encoding="utf-8").splitlines() if file_path.exists() else []
    existing.append(cleaned)
    file_path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    return len(existing)


def take(path: str | Path) -> str:
    """Remove and return the first name."""
    file_path = Path(path)
    if not file_path.exists():
        raise LookupError("empty")

    lines = file_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise LookupError("empty")

    first, rest = lines[0], lines[1:]
    content = ("\n".join(rest) + "\n") if rest else ""
    file_path.write_text(content, encoding="utf-8")
    return first