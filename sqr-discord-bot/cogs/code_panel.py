"""System 2: subscription code button panel (admin slash + persistent UI)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from views.keyauth_code_panel_view import (
    KeyAuthCodePanelView,
    build_code_panel_embed,
    send_code_panel_sequence,
)


class CodePanel(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup_code_panel",
        description="نشر لوحة التحقق من الاشتراك (للمسؤولين فقط).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_code_panel(self, interaction: discord.Interaction) -> None:
        if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "استخدم الأمر داخل قناة نصية.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed = build_code_panel_embed()
        view = KeyAuthCodePanelView()
        ok = await send_code_panel_sequence(
            interaction.channel,
            panel_embed=embed,
            panel_view=view,
        )

        if ok:
            await interaction.followup.send("✅ تم نشر لوحة التحقق.", ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ فشل نشر اللوحة. تحقق من صلاحيات البوت.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CodePanel(bot))
