"""Format member-derived strings for channel names (Latin -> mathematical bold italic)."""

from __future__ import annotations

import discord

from utils.math_text import to_mathematical_sans_serif_bold_italic

# Backwards-compatible name used elsewhere in the project
stylize_latin_to_math_sans_bold_italic = to_mathematical_sans_serif_bold_italic


def stylized_ticket_display_name(member: discord.Member) -> str:
    """``Member.display_name`` passed through math sans-serif bold-italic mapping."""
    if not isinstance(member, discord.Member):
        msg = "stylized_ticket_display_name expects a discord.Member"
        raise TypeError(msg)
    return to_mathematical_sans_serif_bold_italic(member.display_name)


def format_member_label_for_channels(member: discord.Member) -> str:
    """
    Guild nickname if set, otherwise the member's username (`Member.name`),
    then stylize ASCII English letters only.
    """
    if not isinstance(member, discord.Member):
        msg = "format_member_label_for_channels expects a discord.Member"
        raise TypeError(msg)

    raw = member.nick if member.nick else member.name
    return to_mathematical_sans_serif_bold_italic(raw)
