"""Permission overwrites for private ticket channels."""

from __future__ import annotations

import discord

from config.tickets import STAFF_ROLE_IDS

_TICKET_MEMBER_PERMS = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=True,
    read_message_history=True,
    attach_files=True,
    embed_links=True,
    add_reactions=True,
    use_external_emojis=True,
)

_BOT_TICKET_PERMS = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=True,
    read_message_history=True,
    manage_messages=True,
    embed_links=True,
    attach_files=True,
    add_reactions=True,
    use_external_emojis=True,
)


def build_ticket_overwrites(
    guild: discord.Guild,
    opener: discord.Member,
    bot_member: discord.Member,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    """
    Deny @everyone, allow opener and bot, and explicitly allow roles with Administrator
    (so the channel list reflects private access clearly).
    """
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        opener: _TICKET_MEMBER_PERMS,
        bot_member: _BOT_TICKET_PERMS,
    }

    for role in guild.roles:
        if role.is_default():
            continue
        if role.permissions.administrator:
            overwrites[role] = _TICKET_MEMBER_PERMS

    for role_id in STAFF_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is not None and role not in overwrites:
            overwrites[role] = _TICKET_MEMBER_PERMS

    return overwrites
