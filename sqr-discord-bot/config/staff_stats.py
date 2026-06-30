"""Weekly staff stats channel configuration."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_FILE = _DATA_DIR / "staff_stats_config.json"


def _read_config() -> dict:
    if not _DATA_FILE.is_file():
        return {}
    try:
        data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logger.exception("Could not read staff stats config")
        return {}


def _write_config(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_channel_id(raw: object) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def get_stats_channel_id() -> int | None:
    channel_id = _parse_channel_id(_read_config().get("stats_channel_id"))
    if channel_id is not None:
        return channel_id

    raw = os.environ.get("STAFF_STATS_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("STAFF_STATS_CHANNEL_ID is not a valid integer: %r", raw)
        return None


def get_stats_guild_id() -> int | None:
    guild_id = _parse_channel_id(_read_config().get("guild_id"))
    if guild_id is not None:
        return guild_id
    raw = os.environ.get("STAFF_STATS_GUILD_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def set_stats_channel(*, channel_id: int, guild_id: int) -> None:
    data = _read_config()
    data["stats_channel_id"] = channel_id
    data["guild_id"] = guild_id
    _write_config(data)


def get_last_weekly_report_at() -> datetime | None:
    raw = _read_config().get("last_weekly_report_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def set_last_weekly_report_at(when: datetime | None = None) -> None:
    data = _read_config()
    data["last_weekly_report_at"] = (when or datetime.now(timezone.utc)).isoformat()
    _write_config(data)
