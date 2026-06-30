"""Staff slash command to deliver Overwatch 2 color-tracking keys inside tickets."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config.tickets import is_ticket_channel, opener_id_from_topic
from utils.ow2_key_store import claim_next_key, remaining_key_count
from utils.ticket_notifications import is_ticket_staff

logger = logging.getLogger(__name__)

_OW2_COLOR = 0xF99E1A


def _resolve_opener_id(channel: discord.TextChannel) -> int | None:
    opener_id = opener_id_from_topic(channel.topic)
    if opener_id is not None:
        return opener_id

    guild = channel.guild
    if guild is None:
        return None
    bot_id = guild.me.id if guild.me else None
    for target, overwrite in channel.overwrites.items():
        if not isinstance(target, discord.Member):
            continue
        if target.bot:
            continue
        if bot_id is not None and target.id == bot_id:
            continue
        if overwrite.send_messages is True:
            return target.id
    return None


def _build_customer_embed(*, code: str) -> discord.Embed:
    return discord.Embed(
        title="🎮 OW2 · Color Tracking",
        description=(
            f"**مفتاحك / Your key:**\n"
            f"```{code}```\n"
            "▫️ انسخه وفعّله في البرنامج\n"
            "▫️ Copy & activate in the app\n"
            "▫️ **لا تشاركه** · Do not share"
        ),
        color=_OW2_COLOR,
    ).set_footer(text="SQR Store · Overwatch 2")


class Ow2KeysCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ow2_key",
        description="إرسال مفتاح OW2 (تتبع ألوان) للعميل داخل التذكرة.",
    )
    @app_commands.guild_only()
    async def ow2_key(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "استخدم الأمر داخل السيرفر.",
                ephemeral=True,
            )
            return

        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message(
                "❌ للإدارة فقط.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not is_ticket_channel(channel):
            await interaction.response.send_message(
                "❌ استخدم الأمر **داخل قناة التذكرة**.\n"
                "❌ Use this inside a **ticket channel**.",
                ephemeral=True,
            )
            return

        opener_id = _resolve_opener_id(channel)
        claim = claim_next_key(
            channel_id=channel.id,
            customer_id=opener_id,
            staff_id=interaction.user.id,
        )
        if claim is None:
            await interaction.response.send_message(
                "❌ **انتهت المفاتيح** — لا يوجد مفاتيح OW2 متبقية.\n"
                "❌ **No keys left** in the pool.",
                ephemeral=True,
            )
            return

        mention = f"<@{opener_id}>" if opener_id is not None else ""
        embed = _build_customer_embed(code=claim.code)

        try:
            await channel.send(
                content=mention or None,
                embed=embed,
            )
        except discord.HTTPException:
            logger.exception("Failed to post OW2 key in %s", channel.id)
            await interaction.response.send_message(
                "❌ فشل إرسال المفتاح — تحقق من صلاحيات البوت.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ تم إرسال المفتاح في التذكرة.\n"
            f"📦 متبقي: **{claim.remaining}** مفتاح\n\n"
            f"✅ Key posted in ticket.\n"
            f"📦 Remaining: **{claim.remaining}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="ow2_keys_left",
        description="كم مفتاح OW2 متبقي؟ (إدارة)",
    )
    @app_commands.guild_only()
    async def ow2_keys_left(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(
            interaction.user
        ):
            await interaction.response.send_message("❌ للإدارة فقط.", ephemeral=True)
            return

        count = remaining_key_count()
        await interaction.response.send_message(
            f"📦 مفاتيح OW2 المتبقية: **{count}**\n"
            f"📦 OW2 keys remaining: **{count}**",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ow2KeysCog(bot))
