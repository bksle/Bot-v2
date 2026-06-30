"""Persistent pool for Overwatch 2 color-tracking license keys."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "ow2_keys.json"


@dataclass(slots=True)
class Ow2KeyClaim:
    code: str
    remaining: int


def _lock_file(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_raw() -> dict:
    if not _STORE_PATH.is_file():
        return {"unused": [], "used": []}
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"unused": [], "used": []}


def remaining_key_count() -> int:
    data = _load_raw()
    unused = data.get("unused")
    return len(unused) if isinstance(unused, list) else 0


def claim_next_key(
    *,
    channel_id: int,
    customer_id: int | None,
    staff_id: int,
) -> Ow2KeyClaim | None:
    """Pop the next unused key and persist the assignment."""
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.exists():
        _STORE_PATH.write_text(
            json.dumps({"unused": [], "used": []}, ensure_ascii=False),
            encoding="utf-8",
        )

    with open(_STORE_PATH, "r+", encoding="utf-8") as handle:
        _lock_file(handle)
        try:
            handle.seek(0)
            raw = handle.read()
            data = json.loads(raw) if raw.strip() else {"unused": [], "used": []}
            if not isinstance(data, dict):
                data = {"unused": [], "used": []}

            unused = data.get("unused")
            used = data.get("used")
            if not isinstance(unused, list):
                unused = []
            if not isinstance(used, list):
                used = []

            if not unused:
                return None

            code = str(unused.pop(0)).strip()
            used.append(
                {
                    "code": code,
                    "channel_id": channel_id,
                    "customer_id": customer_id,
                    "staff_id": staff_id,
                    "at": int(time.time()),
                }
            )
            data["unused"] = unused
            data["used"] = used
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            handle.seek(0)
            handle.truncate()
            handle.write(payload)
            handle.flush()
            return Ow2KeyClaim(code=code, remaining=len(unused))
        finally:
            _unlock_file(handle)
