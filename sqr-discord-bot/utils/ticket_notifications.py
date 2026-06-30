"""Staff alerts on ticket open and customer DMs when staff reply."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord

from config.tickets import (
    STAFF_REPLY_NOTIFY_COOLDOWN_SECONDS,
    STAFF_ROLE_IDS,
    option_label_for_value,
    staff_role_mentions,
    ticket_label_for_channel,
)
from utils.ticket_delay_store import release_delay_reminder, try_claim_delay_reminder

logger = logging.getLogger(__name__)


class TicketNotifyState:
    """Per-channel state for staff-reply customer DMs and delay reminders."""

    __slots__ = (
        "notify_on_next_staff_msg",
        "last_staff_ping_at",
        "last_activity_at",
        "awaiting_staff_reply",
        "delay_reminder_sent",
        "rating_prompt_sent",
        "rating_completed",
    )

    def __init__(self) -> None:
        self.notify_on_next_staff_msg = False
        self.last_staff_ping_at: datetime | None = None
        self.last_activity_at: datetime | None = None
        self.awaiting_staff_reply = False
        self.delay_reminder_sent = False
        self.rating_prompt_sent = False
        self.rating_completed = False

    def should_notify_staff_reply(self, now: datetime) -> bool:
        if self.notify_on_next_staff_msg:
            return True
        if self.last_staff_ping_at is None:
            return True
        elapsed = (now - self.last_staff_ping_at).total_seconds()
        return elapsed >= STAFF_REPLY_NOTIFY_COOLDOWN_SECONDS

    def mark_staff_notified(self, now: datetime) -> None:
        self.last_staff_ping_at = now
        self.notify_on_next_staff_msg = False

    def mark_customer_replied(self) -> None:
        self.notify_on_next_staff_msg = True
        self.awaiting_staff_reply = True

    def mark_staff_replied_to_ticket(self) -> None:
        self.awaiting_staff_reply = False
        self.delay_reminder_sent = False

    def begin_awaiting_staff_reply(self) -> None:
        self.awaiting_staff_reply = True


def is_ticket_staff(member: discord.Member) -> bool:
    perms = member.guild_permissions
    if perms.administrator or perms.manage_channels:
        return True
    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in STAFF_ROLE_IDS)


def collect_staff_members(guild: discord.Guild) -> list[discord.Member]:
    seen: set[int] = set()
    members: list[discord.Member] = []
    for role_id in STAFF_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is None:
            continue
        for member in role.members:
            if member.bot or member.id in seen:
                continue
            seen.add(member.id)
            members.append(member)
    return members


async def notify_staff_new_ticket(
    *,
    guild: discord.Guild,
    ticket_channel: discord.TextChannel,
    opener: discord.Member,
    category_label: str,
) -> None:
    """DM staff who hold configured roles about a newly opened ticket."""
    staff_members = collect_staff_members(guild)
    if not staff_members:
        logger.info(
            "No staff members resolved for ticket %s (enable Server Members Intent?)",
            ticket_channel.id,
        )
        return

    embed = discord.Embed(
        title="🎫 تذكرة جديدة | SQR Store",
        description=(
            f"قام العضو {opener.mention} بفتح تذكرة جديدة.\n\n"
            f"**القسم:** `{category_label}`\n"
            f"**التذكرة:** {ticket_channel.mention}"
        ),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="يرجى المتابعة في أقرب وقت ممكن")

    for member in staff_members:
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            logger.info("Staff DM blocked by %s (%s)", member, member.id)
        except discord.HTTPException:
            logger.exception("Failed to DM staff member %s", member.id)


async def _recent_delay_reminder_posted(
    ticket_channel: discord.TextChannel,
    *,
    within_seconds: int = 10 * 60,
) -> bool:
    """Skip duplicate delay alerts (e.g. multiple bot instances)."""
    cutoff = datetime.now(timezone.utc).timestamp() - within_seconds
    try:
        async for message in ticket_channel.history(limit=15):
            if not message.author.bot or not message.embeds:
                continue
            if message.created_at.timestamp() < cutoff:
                break
            for embed in message.embeds:
                title = embed.title or ""
                if "تأخر الرد على العميل" in title:
                    return True
    except discord.HTTPException:
        logger.exception(
            "Failed to scan ticket history for duplicate delay reminder in %s",
            ticket_channel.id,
        )
    return False


async def notify_staff_delayed_response(
    *,
    guild: discord.Guild,
    ticket_channel: discord.TextChannel,
    opener_id: int,
) -> bool:
    """Post a single in-ticket staff ping when nobody replied in time. Returns True if sent."""
    if not try_claim_delay_reminder(ticket_channel.id):
        logger.info(
            "Delay reminder already claimed for ticket %s",
            ticket_channel.id,
        )
        return False

    if await _recent_delay_reminder_posted(ticket_channel):
        logger.info(
            "Skipping duplicate delay reminder in ticket %s",
            ticket_channel.id,
        )
        release_delay_reminder(ticket_channel.id)
        return False

    try:
        opener = guild.get_member(opener_id) or await guild.fetch_member(opener_id)
    except (discord.NotFound, discord.HTTPException):
        opener = None

    opener_mention = opener.mention if opener is not None else f"<@{opener_id}>"
    category_label = ticket_label_for_channel(ticket_channel)
    staff_mentions = staff_role_mentions(guild)

    embed = discord.Embed(
        title="⚠️ تنبيه — تأخر الرد على العميل | SQR Store",
        description=(
            f"مرّ أكثر من **3 دقائق** على تذكرة العميل {opener_mention} "
            f"في قسم **{category_label}** دون أي رد من الإدارة.\n\n"
            f"**التذكرة:** {ticket_channel.mention}\n\n"
            "العميل بانتظاركم — يرجى المتابعة **فوراً**."
        ),
        color=discord.Color.red(),
    )
    embed.set_footer(text="تذكير تلقائي من نظام التذاكر")

    try:
        await ticket_channel.send(
            content=staff_mentions or None,
            embed=embed,
        )
        return True
    except discord.HTTPException:
        logger.exception(
            "Failed to post staff delay reminder in ticket %s",
            ticket_channel.id,
        )
        release_delay_reminder(ticket_channel.id)
        return False


async def notify_customer_staff_replied(
    *,
    bot: discord.Client,
    ticket_channel: discord.TextChannel,
    opener_id: int,
) -> bool:
    """DM the ticket opener that staff replied. Returns True if the DM was sent."""
    try:
        opener = await bot.fetch_user(opener_id)
    except discord.HTTPException:
        logger.exception("Could not fetch ticket opener %s", opener_id)
        return False

    category_label = ticket_label_for_channel(ticket_channel)
    embed = discord.Embed(
        title="📩 رد من الإدارة | SQR Store",
        description=(
            f"مرحباً {opener.mention}،\n\n"
            f"قام فريق **الإدارة** بالرد على تذكرتك في قسم **{category_label}**.\n\n"
            f"يرجى مراجعة تذكرتك في أقرب وقت:\n"
            f"➡️ {ticket_channel.mention}"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="شكراً لصبرك وتعاونك معنا")

    try:
        await opener.send(content=opener.mention, embed=embed)
        return True
    except discord.Forbidden:
        logger.info("Customer staff-reply DM blocked by user %s", opener_id)
        return False
    except discord.HTTPException:
        logger.exception("Failed to DM customer %s about staff reply", opener_id)
        return False


def build_ticket_open_content(
    *,
    guild: discord.Guild,
    opener: discord.Member,
) -> str:
    return opener.mention


__all__ = [
    "TicketNotifyState",
    "build_ticket_open_content",
    "notify_customer_staff_replied",
    "notify_staff_delayed_response",
    "notify_staff_new_ticket",
    "option_label_for_value",
]
