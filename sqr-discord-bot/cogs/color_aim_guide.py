"""Admin command to publish the COLOR・AIM guide in the download channel."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config.color_aim import COLOR_AIM_GUIDE_CHANNEL_ID
from utils.color_aim_onboarding import build_color_aim_channel_guide_embed


class ColorAimGuide(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup_color_aim_guide",
        description="نشر دليل COLOR・AIM (شرح + تحميل + روابط) في روم تتبع الألوان.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_color_aim_guide(self, interaction: discord.Interaction) -> None:
        channel = interaction.guild.get_channel(COLOR_AIM_GUIDE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                f"روم الدليل غير موجود (ID: `{COLOR_AIM_GUIDE_CHANNEL_ID}`).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed = build_color_aim_channel_guide_embed()
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ فشل النشر — تحقق من صلاحيات البوت في الروم.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ تم نشر دليل COLOR・AIM في {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ColorAimGuide(bot))
