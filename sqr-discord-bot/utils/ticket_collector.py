"""Scan guild ticket categories and build staff overview embeds."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import discord

from config.tickets import (
    TICKET_SPECS,
    VENDORS_VALUE,
    all_ticket_category_ids,
    opener_id_from_topic,
    option_label_for_value,
    option_value_for_category_id,
)

logger = logging.getLogger(__name__)
_STATUS_RE = re.compile(r"الحالة\s*›\s*(.+)", re.MULTILINE)
_CLAIMED_RE = re.compile(r"المستلم\s*›\s*(.+)", re.MULTILINE)


@dataclass(slots=True)
class OpenTicketInfo:
    channel: discord.TextChannel
    option_value: str | None
    opener_id: int | None
    status: str
    claimed_display: str


def _parse_control_embed(embed: discord.Embed) -> tuple[str, str]:
    desc = embed.description or ""
    status_match = _STATUS_RE.search(desc)
    claimed_match = _CLAIMED_RE.search(desc)
    status = status_match.group(1).strip() if status_match else "🟡 بانتظار الإدارة"
    claimed = claimed_match.group(1).strip() if claimed_match else "`—`"
    return status, claimed


async def _status_from_channel(channel: discord.TextChannel) -> tuple[str, str]:
    try:
        async for message in channel.history(limit=40):
            if not message.author.bot or not message.embeds:
                continue
            embed = message.embeds[0]
            title = embed.title or ""
            if "لوحة التحكم" not in title:
                continue
            return _parse_control_embed(embed)
    except discord.Forbidden:
        logger.debug("No history access in ticket channel %s", channel.id)
    except discord.HTTPException:
        logger.exception("Failed to read history for ticket %s", channel.id)
    return "🟡 بانتظار الإدارة", "`—`"


async def collect_open_tickets(guild: discord.Guild) -> list[OpenTicketInfo]:
    tickets: list[OpenTicketInfo] = []

    for category_id in sorted(all_ticket_category_ids()):
        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            continue

        for channel in category.channels:
            if not isinstance(channel, discord.TextChannel):
                continue

            option_value = option_value_for_category_id(category_id)
            opener_id = opener_id_from_topic(channel.topic)
            status, claimed_display = await _status_from_channel(channel)
            tickets.append(
                OpenTicketInfo(
                    channel=channel,
                    option_value=option_value,
                    opener_id=opener_id,
                    status=status,
                    claimed_display=claimed_display,
                )
            )

    tickets.sort(key=lambda item: (item.option_value or "", item.channel.name))
    return tickets


def _category_header(option_value: str | None) -> str:
    if option_value is None:
        return "🎫 أخرى"
    emoji = "⚫️" if option_value == VENDORS_VALUE else TICKET_SPECS[option_value].emoji
    label = option_label_for_value(option_value)
    return f"{emoji} {label}"


def _format_ticket_line(info: OpenTicketInfo) -> str:
    opener = f"<@{info.opener_id}>" if info.opener_id is not None else "`—`"
    return (
        f"• {info.channel.mention}\n"
        f"  العميل: {opener} — {info.status}\n"
        f"  المستلم: {info.claimed_display}"
    )


def _split_field_lines(lines: list[str], *, max_len: int = 1024) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        extra = len(line) + (1 if current else 0)
        if current and current_len + extra > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
            continue
        current.append(line)
        current_len += extra

    if current:
        chunks.append("\n".join(current))
    return chunks


def build_ticket_overview_embeds(tickets: list[OpenTicketInfo]) -> list[discord.Embed]:
    if not tickets:
        embed = discord.Embed(
            title="📋 التذاكر المفتوحة",
            description="لا توجد تذاكر مفتوحة حالياً.",
            color=0x57F287,
        )
        embed.set_footer(text="SQR Store · نظام التذاكر")
        return [embed]

    waiting = sum(1 for t in tickets if "بانتظار الإدارة" in t.status)
    in_progress = sum(1 for t in tickets if "قيد المعالجة" in t.status)
    rating = sum(1 for t in tickets if "بانتظار التقييم" in t.status)

    grouped: dict[str | None, list[OpenTicketInfo]] = {}
    for ticket in tickets:
        grouped.setdefault(ticket.option_value, []).append(ticket)

    embeds: list[discord.Embed] = []
    current = discord.Embed(
        title="📋 التذاكر المفتوحة",
        description=(
            f"**الإجمالي:** `{len(tickets)}` تذكرة\n"
            f"🟡 بانتظار الإدارة: `{waiting}`　"
            f"🟢 قيد المعالجة: `{in_progress}`　"
            f"⭐ بانتظار التقييم: `{rating}`"
        ),
        color=0x5865F2,
    )
    current.set_footer(text="SQR Store · نظام التذاكر")

    for option_value in sorted(
        grouped.keys(),
        key=lambda key: (key is None, key or ""),
    ):
        header = _category_header(option_value)
        lines = [_format_ticket_line(info) for info in grouped[option_value]]
        for index, chunk in enumerate(_split_field_lines(lines)):
            field_name = header if index == 0 else f"{header} (تابع)"
            if len(current.fields) >= 25:
                embeds.append(current)
                current = discord.Embed(color=0x5865F2)
                current.set_footer(text="SQR Store · نظام التذاكر (تابع)")
            current.add_field(name=field_name, value=chunk, inline=False)

    embeds.append(current)
    return embeds
