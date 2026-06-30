"""Cross-process guard: one delay reminder per ticket channel."""

from __future__ import annotations

import os
import time
from pathlib import Path

_CLAIM_DIR = Path(__file__).resolve().parent.parent / "data" / "ticket_delay_claims"
_CLAIM_TTL_SECONDS = 6 * 60 * 60


def _claim_path(channel_id: int) -> Path:
    return _CLAIM_DIR / f"{channel_id}.claim"


def _read_claim_timestamp(path: Path) -> float | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return float(raw) if raw else None
    except (OSError, ValueError):
        return None


def _is_stale(path: Path, *, now: float) -> bool:
    ts = _read_claim_timestamp(path)
    if ts is None:
        return True
    return (now - ts) >= _CLAIM_TTL_SECONDS


def try_claim_delay_reminder(channel_id: int) -> bool:
    """Atomically claim sending a delay reminder for this ticket channel."""
    _CLAIM_DIR.mkdir(parents=True, exist_ok=True)
    path = _claim_path(channel_id)
    now = time.time()
    payload = f"{now:.3f}".encode("ascii")

    if path.exists() and not _is_stale(path, now=now):
        return False

    if path.exists():
        try:
            path.unlink()
        except OSError:
            return False

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags)
    except FileExistsError:
        return False

    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    return True


def release_delay_reminder(channel_id: int) -> None:
    path = _claim_path(channel_id)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
