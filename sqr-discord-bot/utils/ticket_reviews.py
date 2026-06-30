"""Staff review prompts and publishing completed ticket ratings."""

from __future__ import annotations

import logging

import discord

from config.tickets import (
    TICKET_REVIEW_CHANNEL_ID,
    ticket_color_for_channel_or_option,
    ticket_label_for_channel,
)
from utils.ticket_notifications import collect_staff_members

logger = logging.getLogger(__name__)


async def _resolve_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is not None:
        return member
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def collect_ticket_staff_participants(
    channel: discord.TextChannel,
    *,
    opener_id: int,
    fallback_members: list[discord.Member] | None = None,
) -> list[discord.Member]:
    """Staff who messaged in the ticket, else fallbacks (claimer / stop trigger), else configured staff."""
    guild = channel.guild
    if guild is None:
        return []

    seen: set[int] = set()
    members: list[discord.Member] = []

    try:
        async for message in channel.history(limit=None):
            author = message.author
            if author.bot or author.id == opener_id:
                continue
            if author.id in seen:
                continue
            if not isinstance(author, discord.Member):
                member = await _resolve_member(guild, author.id)
                if member is None:
                    continue
                author = member
            seen.add(author.id)
            members.append(author)
    except discord.HTTPException:
        logger.exception("Failed to scan ticket history in %s", channel.id)

    if members:
        return members

    if fallback_members:
        for member in fallback_members:
            if member.bot or member.id == opener_id or member.id in seen:
                continue
            seen.add(member.id)
            members.append(member)
        if members:
            return members

    return collect_staff_members(guild)


async def post_ticket_review(
    *,
    guild: discord.Guild,
    customer: discord.Member | discord.User,
    admin: discord.Member | discord.User | None,
    admin_label: str,
    product_label: str,
    review_text: str,
    ticket_channel: discord.TextChannel,
    option_value: str | None = None,
    stars: int = 0,
    points_awarded: int = 0,
) -> bool:
    """Publish the customer's review to the configured reviews channel."""
    review_channel = guild.get_channel(TICKET_REVIEW_CHANNEL_ID)
    if not isinstance(review_channel, discord.TextChannel):
        logger.warning("Ticket review channel %s is missing or invalid", TICKET_REVIEW_CHANNEL_ID)
        return False

    embed = discord.Embed(
        title="⭐ تقييم جديد | SQR Store",
        description=review_text,
        color=ticket_color_for_channel_or_option(ticket_channel, option_value),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(
        name=str(customer),
        icon_url=customer.display_avatar.url,
    )
    if admin is not None:
        admin_value = f"{admin.mention}\n`{admin}`"
    else:
        admin_value = f"**{admin_label}**"

    stars_display = "⭐" * stars if stars else "—"
    points_display = f"**{points_awarded}**" if points_awarded else "`0`"

    embed.add_field(name="العميل", value=f"{customer.mention}\n`{customer}`", inline=True)
    embed.add_field(name="المنتج", value=f"`{product_label}`", inline=True)
    embed.add_field(name="الإداري", value=admin_value, inline=True)
    embed.add_field(name="التقييم", value=f"{stars_display} ({stars}/3)", inline=True)
    embed.add_field(name="النقاط", value=points_display, inline=True)
    embed.set_footer(text=f"تذكرة: {ticket_channel.name}")

    try:
        await review_channel.send(embed=embed)
        return True
    except discord.HTTPException:
        logger.exception("Failed to post ticket review for channel %s", ticket_channel.id)
        return False


def product_label_for_ticket(channel: discord.TextChannel) -> str:
    return ticket_label_for_channel(channel)
