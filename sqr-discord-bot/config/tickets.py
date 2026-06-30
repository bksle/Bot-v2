"""Category IDs, emojis, and channel name templates for ticket dropdown."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import discord

# Discord hard limit per category
MAX_CHANNELS_PER_CATEGORY: Final = 50

# Option values must match select `value=` in ticket views.
VENDORS_VALUE: Final = "vendors_partners"

VENDORS_CATEGORY_ID: Final = 1498832059752255608

# Staff roles pinged on new tickets and notified via DM when they hold any of these roles.
STAFF_ROLE_IDS: Final[tuple[int, ...]] = (
    1494246140026163270,
    1494246341633769513,
    1489174740869320837,
    1443892224994836541,
)

# Persisted in ticket channel topic so reply notifications survive bot restarts.
TICKET_OPENER_TOPIC_PREFIX: Final = "ticket_opener_id:"

# Minimum gap between two customer DMs when the customer has not replied (seconds).
STAFF_REPLY_NOTIFY_COOLDOWN_SECONDS: Final = 30 * 60

# Remind staff if nobody replies to the customer within this window (seconds).
STAFF_NO_REPLY_REMINDER_SECONDS: Final = 3 * 60

# Send a staff rating prompt after this much ticket inactivity (seconds).
TICKET_INACTIVITY_REVIEW_SECONDS: Final = 24 * 60 * 60

# Channel where completed ticket reviews are published.
TICKET_REVIEW_CHANNEL_ID: Final = 1502885046183526450


@dataclass(frozen=True, slots=True)
class TicketCategorySpec:
    category_id: int
    emoji: str
    # Legacy display label inside old UIs (not used in channel names for System 3).
    channel_label: str
    overflow_category_ids: tuple[int, ...] = ()


TICKET_SPECS: Final[dict[str, TicketCategorySpec]] = {
    "xim": TicketCategorySpec(1498832064412123228, "🔴", "XIM"),
    "chairs": TicketCategorySpec(1498832065397784739, "🟠", "CHAIRS"),
    "snap": TicketCategorySpec(1498832067062923318, "🟡", "Snap"),
    "tweak": TicketCategorySpec(1498832068128407593, "🟢", "Tweak"),
    "zen": TicketCategorySpec(1498832068833181828, "🔵", "Zen"),
    "spoof": TicketCategorySpec(
        1498832071005831188,
        "🟣",
        "𝙎𝙋𝙊𝙊𝙁 | سبوف",
    ),
    "iptv": TicketCategorySpec(1498832069982425210, "🟤", "IPTV"),
    "color_aim": TicketCategorySpec(1498832072419049553, "⚪", "COLOR・AIM"),
}


def _emoji_for_option(option_value: str) -> str:
    if option_value == VENDORS_VALUE:
        return "⚫️"
    return TICKET_SPECS[option_value].emoji


def _trim_to_length(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def build_ticket_channel_name(*, option_value: str, styled_name: str) -> str:
    """
    Strict format: ``│〢「{Emoji}」{styled_name}`` (max 100 chars for Discord).
    ``styled_name`` is produced by the caller (e.g. math-sans-bold-italic display name).
    """
    max_len = 100
    emoji = _emoji_for_option(option_value)
    prefix = f"│〢「{emoji}」"
    base = f"{prefix}{styled_name}"
    if len(base) <= max_len:
        return base
    room = max_len - len(prefix)
    return f"{prefix}{_trim_to_length(styled_name, max(1, room))}"


def _parse_overflow_ids(raw: str) -> tuple[int, ...]:
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            ids.append(int(piece))
        except ValueError:
            continue
    return tuple(ids)


def _overflow_from_env(option_value: str) -> tuple[int, ...]:
    if option_value == VENDORS_VALUE:
        raw = os.environ.get("VENDORS_OVERFLOW_CATEGORY_IDS", "")
    else:
        specific = os.environ.get(f"{option_value.upper()}_OVERFLOW_CATEGORY_IDS", "")
        generic = os.environ.get(f"TICKET_OVERFLOW_{option_value.upper()}", "")
        raw = specific or generic
    return _parse_overflow_ids(raw)


def overflow_category_ids_for_option(option_value: str) -> tuple[int, ...]:
    if option_value == VENDORS_VALUE:
        return _overflow_from_env(VENDORS_VALUE)
    spec = TICKET_SPECS.get(option_value)
    if spec is None:
        return _overflow_from_env(option_value)
    env_ids = _overflow_from_env(option_value)
    merged = [spec.category_id, *spec.overflow_category_ids, *env_ids]
    seen: set[int] = set()
    out: list[int] = []
    for cid in merged:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return tuple(out)


def category_ids_for_option(option_value: str) -> tuple[int, ...]:
    if option_value == VENDORS_VALUE:
        ids = [VENDORS_CATEGORY_ID, *_overflow_from_env(VENDORS_VALUE)]
    else:
        ids = list(overflow_category_ids_for_option(option_value))
    seen: set[int] = set()
    out: list[int] = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return tuple(out)


def resolve_ticket_parent_category(
    guild: discord.Guild,
    option_value: str,
) -> discord.CategoryChannel | None:
    """First category for this service with room for a new channel (< 50)."""
    for category_id in category_ids_for_option(option_value):
        channel = guild.get_channel(category_id)
        if not isinstance(channel, discord.CategoryChannel):
            continue
        if len(channel.channels) < MAX_CHANNELS_PER_CATEGORY:
            return channel
    return None


def category_usage(guild: discord.Guild, option_value: str) -> list[tuple[int, int, str]]:
    """(category_id, channel_count, status) for staff diagnostics."""
    rows: list[tuple[int, int, str]] = []
    for category_id in category_ids_for_option(option_value):
        channel = guild.get_channel(category_id)
        if not isinstance(channel, discord.CategoryChannel):
            rows.append((category_id, -1, "missing"))
            continue
        count = len(channel.channels)
        if count >= MAX_CHANNELS_PER_CATEGORY:
            status = "full"
        elif count >= MAX_CHANNELS_PER_CATEGORY - 5:
            status = "almost_full"
        else:
            status = "ok"
        rows.append((category_id, count, status))
    return rows


def category_id_for_option(option_value: str) -> int:
    if option_value == VENDORS_VALUE:
        return VENDORS_CATEGORY_ID
    return TICKET_SPECS[option_value].category_id


_TICKET_CATEGORY_IDS: frozenset[int] | None = None


def all_ticket_category_ids() -> frozenset[int]:
    global _TICKET_CATEGORY_IDS
    if _TICKET_CATEGORY_IDS is None:
        ids: set[int] = {VENDORS_CATEGORY_ID}
        for key in TICKET_SPECS:
            ids.update(category_ids_for_option(key))
        ids.update(category_ids_for_option(VENDORS_VALUE))
        _TICKET_CATEGORY_IDS = frozenset(ids)
    return _TICKET_CATEGORY_IDS


def is_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False
    parent_id = channel.category_id
    return parent_id is not None and parent_id in all_ticket_category_ids()


def staff_role_mentions(guild: discord.Guild) -> str:
    parts: list[str] = []
    for role_id in STAFF_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is not None:
            parts.append(role.mention)
    return " ".join(parts) if parts else ""


def opener_id_from_topic(topic: str | None) -> int | None:
    if not topic or not topic.startswith(TICKET_OPENER_TOPIC_PREFIX):
        return None
    raw = topic[len(TICKET_OPENER_TOPIC_PREFIX) :].strip()
    try:
        return int(raw)
    except ValueError:
        return None


def build_opener_topic(opener_id: int) -> str:
    return f"{TICKET_OPENER_TOPIC_PREFIX}{opener_id}"


def ticket_label_for_channel(channel: discord.TextChannel) -> str:
    option_value = option_value_for_category_id(channel.category_id or 0)
    if option_value is not None:
        return option_label_for_value(option_value)
    return "التذاكر"


def option_label_for_value(option_value: str) -> str:
    if option_value == VENDORS_VALUE:
        return "تجار وشركاء"
    return TICKET_SPECS[option_value].channel_label


def option_value_for_category_id(category_id: int) -> str | None:
    if category_id == VENDORS_CATEGORY_ID:
        return VENDORS_VALUE
    for key in TICKET_SPECS:
        if category_id in category_ids_for_option(key):
            return key
    for oid in _overflow_from_env(VENDORS_VALUE):
        if category_id == oid:
            return VENDORS_VALUE
    return None


def ticket_emoji_for_channel(channel: discord.TextChannel) -> str:
    option_value = option_value_for_category_id(channel.category_id or 0)
    if option_value is None:
        return "🎫"
    if option_value == VENDORS_VALUE:
        return "⚫️"
    return TICKET_SPECS[option_value].emoji


def ticket_color_for_option(option_value: str) -> int:
    """Embed sidebar hex — matched to each service banner (Discord-visible)."""
    colors: dict[str, int] = {
        "xim": 0xE30613,       # أحمر
        "chairs": 0xFF8C00,    # برتقالي
        "snap": 0xFFDC00,      # أصفر
        "tweak": 0x39FF14,     # أخضر
        "zen": 0x1E90FF,       # أزرق
        "spoof": 0x8A7AE0,     # بنفسجي
        "iptv": 0x8B5A2B,     # بني
        # Discord hides pure #000000 — use near-black for the stripe
        "color_aim": 0xD9D9D9,  # أبيض / فضي
        VENDORS_VALUE: 0x1A1A1A,  # أسود
    }
    return colors.get(option_value, 0x5865F2)


def ticket_theme_emoji_for_option(option_value: str) -> str:
    if option_value == VENDORS_VALUE:
        return "⚫"
    if option_value in TICKET_SPECS:
        return TICKET_SPECS[option_value].emoji
    return "🎫"


def ticket_button_style_for_option(option_value: str) -> discord.ButtonStyle:
    """
    Closest Discord button style per ticket category.
    (Discord only supports blurple / grey / green / red — not custom hex.)
    """
    styles: dict[str, discord.ButtonStyle] = {
        "xim": discord.ButtonStyle.danger,
        "chairs": discord.ButtonStyle.danger,
        "snap": discord.ButtonStyle.secondary,
        "tweak": discord.ButtonStyle.success,
        "zen": discord.ButtonStyle.primary,
        "spoof": discord.ButtonStyle.primary,
        "iptv": discord.ButtonStyle.secondary,
        "color_aim": discord.ButtonStyle.secondary,
        VENDORS_VALUE: discord.ButtonStyle.secondary,
    }
    return styles.get(option_value, discord.ButtonStyle.primary)


def option_value_for_channel(channel: discord.TextChannel) -> str | None:
    if channel.category_id is None:
        return None
    return option_value_for_category_id(channel.category_id)


def ticket_color_for_channel(channel: discord.TextChannel) -> int:
    option_value = option_value_for_channel(channel)
    if option_value is None:
        return 0x5865F2
    return ticket_color_for_option(option_value)


def ticket_color_for_channel_or_option(
    channel: discord.TextChannel,
    option_value: str | None = None,
) -> int:
    if option_value is not None:
        return ticket_color_for_option(option_value)
    return ticket_color_for_channel(channel)
