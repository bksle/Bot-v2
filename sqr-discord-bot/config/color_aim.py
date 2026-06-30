"""COLOR・AIM (تتبع الألوان) — role onboarding channel IDs."""

from __future__ import annotations

import os
from typing import Final

from config.keyauth_roles import SUBSCRIPTION_LEVEL_ROLE_IDS

# Fixed channels (SQR Store guild)
COLOR_AIM_GUILD_ID: Final = 1437176621659328599
COLOR_AIM_GUIDE_CHANNEL_ID: Final = 1505338842734133289
COLOR_AIM_UPDATES_CHANNEL_ID: Final = 1498832192024084650
COLOR_AIM_SETTINGS_CHANNEL_ID: Final = 1505339114671702267

# KeyAuth subscription level that maps to COLOR・AIM (override with COLOR_AIM_SUBSCRIPTION_LEVEL)
_DEFAULT_COLOR_AIM_LEVEL: Final = 1

_EMBED_COLOR: Final = 0xD9D9D9


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def color_aim_subscription_level() -> int:
    return _env_int("COLOR_AIM_SUBSCRIPTION_LEVEL") or _DEFAULT_COLOR_AIM_LEVEL


def color_aim_role_id() -> int:
    explicit = _env_int("COLOR_AIM_ROLE_ID")
    if explicit is not None:
        return explicit
    level = color_aim_subscription_level()
    role_id = SUBSCRIPTION_LEVEL_ROLE_IDS.get(level)
    if role_id is None:
        raise ValueError(f"No KeyAuth role mapped for COLOR・AIM level {level}")
    return role_id


def is_color_aim_role(role_id: int) -> bool:
    return role_id == color_aim_role_id()


def color_aim_download_url() -> str | None:
    url = os.environ.get("COLOR_AIM_DOWNLOAD_URL", "").strip()
    return url or None
