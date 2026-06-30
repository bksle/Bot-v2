"""Weekly staff rating statistics report."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.staff_stats import (
    get_last_weekly_report_at,
    get_stats_channel_id,
    get_stats_guild_id,
    set_last_weekly_report_at,
    set_stats_channel,
)
from utils.staff_stats_embed import build_weekly_stats_embed

logger = logging.getLogger(__name__)

_WEEKLY_INTERVAL = timedelta(days=7)


class StaffStats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.weekly_report_task.start()

    def cog_unload(self) -> None:
        self.weekly_report_task.cancel()

    async def _post_weekly_stats(self, *, channel: discord.TextChannel) -> bool:
        embed = build_weekly_stats_embed()
        try:
            await channel.send(embed=embed)
            return True
        except discord.HTTPException:
            logger.exception("Failed to post weekly staff stats in %s", channel.id)
            return False

    @tasks.loop(hours=1)
    async def weekly_report_task(self) -> None:
        await self.bot.wait_until_ready()

        channel_id = get_stats_channel_id()
        guild_id = get_stats_guild_id()
        if channel_id is None or guild_id is None:
            return

        last_report = get_last_weekly_report_at()
        now = datetime.now(timezone.utc)
        if last_report is not None and now - last_report < _WEEKLY_INTERVAL:
            return

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Staff stats channel %s missing in guild %s", channel_id, guild_id)
            return

        if await self._post_weekly_stats(channel=channel):
            set_last_weekly_report_at(now)

    @weekly_report_task.before_loop
    async def before_weekly_report_task(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="set_stats_channel",
        description="تعيين هذه القناة لإرسال إحصائيات الإدارة كل أسبوع.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_stats_channel_cmd(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("استخدم الأمر داخل السيرفر.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("استخدم الأمر داخل قناة نصية.", ephemeral=True)
            return

        set_stats_channel(channel_id=interaction.channel.id, guild_id=interaction.guild.id)
        await interaction.response.send_message(
            f"✅ تم تعيين {interaction.channel.mention} لإرسال **إحصائيات الإدارة الأسبوعية**.\n"
            "سيُرسل التقرير تلقائياً كل **7 أيام**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="staff_stats_now",
        description="إرسال إحصائيات الإدارة الآن (للمسؤولين).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def staff_stats_now(self, interaction: discord.Interaction) -> None:
        channel_id = get_stats_channel_id()
        if channel_id is None:
            await interaction.response.send_message(
                "لم يتم تعيين قناة الإحصائيات بعد. استخدم `/set_stats_channel` أولاً.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message("استخدم الأمر داخل السيرفر.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "قناة الإحصائيات غير موجودة. عيّنها من جديد بـ `/set_stats_channel`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        ok = await self._post_weekly_stats(channel=channel)
        if ok:
            set_last_weekly_report_at()
            await interaction.followup.send(
                f"✅ تم إرسال الإحصائيات إلى {channel.mention}.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send("❌ فشل إرسال الإحصائيات.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StaffStats(bot))
