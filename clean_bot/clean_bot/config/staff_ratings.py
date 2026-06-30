"""Fixed staff names shown in ticket rating dropdown."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import discord


@dataclass(frozen=True, slots=True)
class StaffRatingEntry:
    key: str
    label: str
    user_id: int | None = None


def _env_user_id(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


RATING_STAFF: Final[tuple[StaffRatingEntry, ...]] = (
    StaffRatingEntry("ahmad", "أحمد", _env_user_id("STAFF_RATING_AHMAD_ID")),
    StaffRatingEntry("abdullatif", "عبداللطيف", _env_user_id("STAFF_RATING_ABDULLATIF_ID")),
    StaffRatingEntry("abdulaziz", "عبدالعزيز", _env_user_id("STAFF_RATING_ABDULAZIZ_ID")),
    StaffRatingEntry("yazan", "يزن", _env_user_id("STAFF_RATING_YAZAN_ID")),
    StaffRatingEntry("fahad", "فهد", _env_user_id("STAFF_RATING_FAHAD_ID")),
    StaffRatingEntry("bnb", "BnB", _env_user_id("STAFF_RATING_BNB_ID")),
)

_RATING_STAFF_BY_KEY: Final[dict[str, StaffRatingEntry]] = {
    entry.key: entry for entry in RATING_STAFF
}


def staff_rating_entry(key: str) -> StaffRatingEntry | None:
    return _RATING_STAFF_BY_KEY.get(key)


async def resolve_staff_member(
    guild: discord.Guild,
    entry: StaffRatingEntry,
) -> discord.Member | discord.User | None:
    if entry.user_id is not None:
        member = guild.get_member(entry.user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(entry.user_id)
        except (discord.NotFound, discord.HTTPException):
            pass

    label_lower = entry.label.lower()
    for member in guild.members:
        if member.bot:
            continue
        haystack = f"{member.display_name} {member.name} {member.global_name or ''}".lower()
        if entry.label in haystack or label_lower in haystack:
            return member
    return None
