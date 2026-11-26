"""Queue stored as one name per line.

The HTTP server must call these functions. Tests call them directly,
with a temporary directory, and do not start Docker.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if sys.platform != "win32":
    import fcntl


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or "\n" in name or "\r" in name:
        raise ValueError("invalid name")
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 40:
        raise ValueError("invalid name")
    return cleaned


@contextmanager
def _queue_lock(queue_file: Path) -> Iterator[None]:
    """Acquire an exclusive lock on a dedicated lock file in the same directory."""
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = queue_file.parent / "queue.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if sys.platform != "win32":
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform != "win32":
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write(target: Path, content: str) -> None:
    """Write content to a unique temp file in the same dir and atomically replace target."""
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".queue-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def join(path: str | Path, name: str) -> int:
    """Append one person and return the ticket number."""
    cleaned = _validate_name(name)
    file_path = Path(path)

    with _queue_lock(file_path):
        existing = file_path.read_text(encoding="utf-8").splitlines() if file_path.exists() else []
        existing.append(cleaned)
        _atomic_write(file_path, "\n".join(existing) + "\n")
        return len(existing)


def take(path: str | Path) -> str:
    """Remove and return the first name."""
    file_path = Path(path)

    with _queue_lock(file_path):
        if not file_path.exists():
            raise LookupError("empty")

        lines = file_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise LookupError("empty")

        first, rest = lines[0], lines[1:]
        content = ("\n".join(rest) + "\n") if rest else ""
        _atomic_write(file_path, content)
        return first