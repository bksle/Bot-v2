"""Shared logic to create a private ticket channel and post the interior UI."""

from __future__ import annotations

import logging

import discord

from config.tickets import (
    build_opener_topic,
    build_ticket_channel_name,
    category_usage,
    option_label_for_value,
    resolve_ticket_parent_category,
)
from utils.ticket_embed import build_ticket_panel_embed
from utils.ticket_notifications import notify_staff_new_ticket
from utils.ticket_welcome import send_ticket_opening_sequence
from views.ticket_interior_view import TicketInteriorView
from views.ticket_permissions import build_ticket_overwrites

logger = logging.getLogger(__name__)


async def create_private_ticket(
    interaction: discord.Interaction,
    *,
    member: discord.Member,
    option_value: str,
    styled_channel_suffix: str,
) -> None:
    """
    Create the ticket after ``interaction`` has been **deferred** (ephemeral).
    """
    if not interaction.response.is_done():
        raise RuntimeError("create_private_ticket requires interaction.response.defer() first")

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send(
            "Tickets can only be opened from a server.",
            ephemeral=True,
        )
        return

    bot_member = guild.me
    if bot_member is None:
        await interaction.followup.send(
            "Bot member is not available in this guild.",
            ephemeral=True,
        )
        return

    try:
        channel_name = build_ticket_channel_name(
            option_value=option_value,
            styled_name=styled_channel_suffix,
        )
    except KeyError:
        logger.exception("Unknown ticket option value: %s", option_value)
        await interaction.followup.send(
            "❌ قسم غير معروف — راسل الإدارة.\n"
            "❌ Unknown category — contact staff.",
            ephemeral=True,
        )
        return

    parent = resolve_ticket_parent_category(guild, option_value)
    if parent is None:
        label = option_label_for_value(option_value)
        usage = category_usage(guild, option_value)
        full_lines = [
            f"• `{cid}` → **{count}/50** ({status})"
            for cid, count, status in usage
            if count >= 0
        ]
        staff_hint = "\n".join(full_lines) if full_lines else "—"
        await interaction.followup.send(
            f"❌ **تعذّر فتح التذكرة** — قسم **{label}** ممتلئ (حد Discord: 50 قناة).\n"
            "تواصل مع **الإدارة** لحذف التذاكر القديمة أو إضافة كategori جديد.\n\n"
            f"❌ **Cannot open ticket** — **{label}** category is **full** (50 channel limit).\n"
            "Please contact **staff**.\n\n"
            f"📊 `{staff_hint}`",
            ephemeral=True,
        )
        logger.warning(
            "Ticket category full for %s — usage: %s",
            option_value,
            usage,
        )
        return

    overwrites = build_ticket_overwrites(guild, member, bot_member)

    category_label = option_label_for_value(option_value)

    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=parent,
            overwrites=overwrites,
            topic=build_opener_topic(member.id),
            reason=f"Ticket opened by {member} ({member.id}) — {option_value}",
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ لا أستطيع إنشاء التذكرة (صلاحيات Manage Channels).\n"
            "❌ Missing **Manage Channels** permission.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as exc:
        logger.exception("Failed to create ticket channel")
        if getattr(exc, "code", None) == 50035 and "Maximum number of channels" in str(exc):
            await interaction.followup.send(
                "❌ القسم **ممتلئ** (50 تذكرة). راسل الإدارة.\n"
                "❌ Category **full**. Contact staff.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            "❌ تعذّر إنشاء التذكرة. حاول لاحقاً أو راسل الإدارة.\n"
            "❌ Could not create ticket. Try again or contact staff.",
            ephemeral=True,
        )
        return

    embed = build_ticket_panel_embed(
        option_value=option_value,
        opener=member,
    )

    posted = await send_ticket_opening_sequence(
        ticket_channel,
        guild=guild,
        opener=member,
        option_value=option_value,
        control_embed=embed,
        control_view=TicketInteriorView(
            opener_id=member.id,
            option_value=option_value,
            channel=ticket_channel,
        ),
    )
    if not posted:
        await interaction.followup.send(
            f"Channel created: {ticket_channel.mention}, but I could not post the welcome message.",
            ephemeral=True,
        )
        return

    try:
        await notify_staff_new_ticket(
            guild=guild,
            ticket_channel=ticket_channel,
            opener=member,
            category_label=category_label,
        )
    except Exception:
        logger.exception("Failed to DM staff about new ticket %s", ticket_channel.id)

    notify_cog = interaction.client.get_cog("TicketNotifications")
    if notify_cog is not None:
        notify_cog.schedule_staff_response_check(
            channel_id=ticket_channel.id,
            opener_id=member.id,
            guild_id=guild.id,
        )
        notify_cog.schedule_inactivity_review(
            channel_id=ticket_channel.id,
            opener_id=member.id,
            guild_id=guild.id,
        )

    await interaction.followup.send(
        f"✅ تم فتح تذكرتك: {ticket_channel.mention}\n"
        f"✅ Ticket created: {ticket_channel.mention}",
        ephemeral=True,
    )
