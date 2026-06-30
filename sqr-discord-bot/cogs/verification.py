"""System 1: strict verification pledge panel (slash + persistent button)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from views.verification_pledge_view import VerificationPledgeView, build_pledge_embed


class Verification(commands.Cog):
    """Admin-only pledge setup."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup_verification",
        description="نشر لوحة ميثاق التحقق الإلزامي (للمسؤولين فقط).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_verification(self, interaction: discord.Interaction) -> None:
        embed = build_pledge_embed()
        await interaction.response.send_message(
            embed=embed,
            view=VerificationPledgeView(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))
