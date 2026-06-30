from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.ticket_embed import build_setup_panel_embed, setup_panel_logo_file
from views.setup_view import SetupSelectView


class Setup(commands.Cog):
    """Slash commands for server setup UI."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="نشر لوحة التذاكر الفاخرة (عربي + English).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup(self, interaction: discord.Interaction) -> None:
        if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "استخدم الأمر داخل قناة نصية.\nUse this command in a text channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed = build_setup_panel_embed()
        view = SetupSelectView()
        logo = setup_panel_logo_file()

        try:
            if logo is not None:
                await interaction.channel.send(embed=embed, view=view, file=logo)
            else:
                await interaction.channel.send(embed=embed, view=view)
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ فشل النشر — تحقق من صلاحيات البوت.\n"
                "❌ Failed to post — check bot permissions.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ تم نشر لوحة التذاكر.\n✅ Ticket panel posted.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
