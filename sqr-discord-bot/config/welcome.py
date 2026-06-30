"""Welcome channel configuration (persisted for member-join messages)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_FILE = _DATA_DIR / "welcome_channel.json"

_cached_welcome_channel_id: int | None | object = object()


def get_welcome_channel_id() -> int | None:
    """Return the channel ID for join welcomes, or None if unset."""
    global _cached_welcome_channel_id
    if _cached_welcome_channel_id is not object():
        return _cached_welcome_channel_id  # type: ignore[return-value]

    if _DATA_FILE.is_file():
        try:
            data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            channel_id = data.get("channel_id")
            if isinstance(channel_id, int):
                _cached_welcome_channel_id = channel_id
                return channel_id
            if isinstance(channel_id, str) and channel_id.isdigit():
                _cached_welcome_channel_id = int(channel_id)
                return _cached_welcome_channel_id  # type: ignore[return-value]
        except (json.JSONDecodeError, OSError):
            logger.exception("Could not read welcome channel config")

    raw = os.environ.get("WELCOME_CHANNEL_ID", "").strip()
    if not raw:
        _cached_welcome_channel_id = None
        return None
    try:
        _cached_welcome_channel_id = int(raw)
    except ValueError:
        logger.warning("WELCOME_CHANNEL_ID is not a valid integer: %r", raw)
        _cached_welcome_channel_id = None
    return _cached_welcome_channel_id  # type: ignore[return-value]


def set_welcome_channel_id(channel_id: int) -> None:
    global _cached_welcome_channel_id
    _cached_welcome_channel_id = channel_id
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(
        json.dumps({"channel_id": channel_id}, indent=2),
        encoding="utf-8",
    )
