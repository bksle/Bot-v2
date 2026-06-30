"""Shared ticket close flow: transcript, DM, log, delete."""

from __future__ import annotations

import io
import logging
import os
import re

import chat_exporter
import discord

logger = logging.getLogger(__name__)


def transcript_log_channel_id() -> int | None:
    raw = os.environ.get("TICKET_TRANSCRIPT_LOG_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("TICKET_TRANSCRIPT_LOG_CHANNEL_ID invalid: %r", raw)
        return None


async def close_ticket_channel(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    opener_id: int,
    closed_by: discord.User | discord.Member,
    close_reason: str,
) -> tuple[bool, str]:
    """
    Export transcript, DM opener, post to log, cancel tracking, delete channel.

    Returns (deleted, status_message).
    """
    guild = channel.guild
    channel_name = channel.name

    transcript: str | None = None
    try:
        transcript = await chat_exporter.export(
            channel,
            limit=None,
            tz_info="UTC",
            guild=guild,
            bot=bot,
            military_time=True,
            fancy_times=True,
            raise_exceptions=False,
        )
    except Exception:
        logger.exception("chat_exporter.export failed")

    if transcript is None:
        return False, "تعذّر إنشاء نسخة المحادثة. تحقق من صلاحيات البوت."

    safe_name = re.sub(r"[^\w.\-]+", "_", channel_name, flags=re.UNICODE)[:80] or "transcript"
    file_bytes = transcript.encode("utf-8")
    if len(file_bytes) > 24 * 1024 * 1024:
        return False, "نسخة المحادثة كبيرة جداً (>24 MB)."

    dm_ok = False
    try:
        opener_user = await bot.fetch_user(opener_id)
        await opener_user.send(
            content="**تم إغلاق التذكرة** — نسخة HTML مرفقة.",
            file=discord.File(io.BytesIO(file_bytes), filename=f"{safe_name}.html"),
        )
        dm_ok = True
    except discord.Forbidden:
        logger.info("Could not DM transcript to user %s (DMs closed)", opener_id)
    except discord.HTTPException:
        logger.exception("DM transcript failed for user %s", opener_id)

    log_id = transcript_log_channel_id()
    if log_id and guild:
        log_ch = guild.get_channel(log_id)
        if isinstance(log_ch, discord.TextChannel):
            try:
                await log_ch.send(
                    content=(
                        f"**نسخة التذكرة** — `{channel_name}`\n"
                        f"العميل: <@{opener_id}> — أُغلقت بواسطة: {closed_by.mention}"
                    ),
                    file=discord.File(io.BytesIO(file_bytes), filename=f"{safe_name}.html"),
                )
            except discord.HTTPException:
                logger.exception("Failed to post transcript to log channel")

    notify_cog = bot.get_cog("TicketNotifications")
    if notify_cog is not None:
        notify_cog.cancel_ticket_tracking(channel.id)

    try:
        await channel.delete(reason=f"{close_reason} — {closed_by} ({closed_by.id})")
    except discord.Forbidden:
        return False, "تم حفظ النسخة لكن لا أستطيع حذف القناة."
    except discord.HTTPException as exc:
        return False, f"تعذّر حذف القناة: `{exc}`"

    dm_note = " وتم إرسال النسخة للعميل." if dm_ok else ""
    return True, f"تم إغلاق التذكرة.{dm_note}"
