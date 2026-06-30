"""Welcome new members with a mention in the configured channel."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config.welcome import get_welcome_channel_id, set_welcome_channel_id
from utils.welcome_message import build_member_welcome_embed

logger = logging.getLogger(__name__)


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        channel_id = get_welcome_channel_id()
        if channel_id is None:
            return

        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Welcome channel %s not found in guild %s", channel_id, member.guild.id)
            return

        embed = build_member_welcome_embed(member)
        try:
            await channel.send(content=member.mention, embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to send welcome for member %s", member.id)

    @app_commands.command(
        name="set_welcome_channel",
        description="تعيين هذه القناة لرسائل الترحيب عند دخول الأعضاء.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_welcome_channel(self, interaction: discord.Interaction) -> None:
        if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "استخدم الأمر داخل قناة نصية.",
                ephemeral=True,
            )
            return

        set_welcome_channel_id(interaction.channel.id)
        await interaction.response.send_message(
            f"✅ تم تعيين {interaction.channel.mention} كقناة الترحيب.\n"
            "سيُمنشن كل عضو جديد تلقائياً عند دخوله السيرفر.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
