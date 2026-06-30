"""Slash command /code: read-only license check and Discord role grant."""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from integrations.keyauth_role_grant import grant_role_for_keyauth_license

logger = logging.getLogger(__name__)


class LicenseKeyCog(commands.Cog):
    """KeyAuth license check (no activation)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="code",
        description="Verify your license key and get your Discord role (does not activate the key).",
    )
    @app_commands.describe(key="Your KeyAuth license key")
    async def code(self, interaction: discord.Interaction, key: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Not available",
                    description="Use this command inside a server.",
                    color=discord.Color.dark_red(),
                ),
                ephemeral=True,
            )
            return

        try:
            async with aiohttp.ClientSession() as session:
                embed = await grant_role_for_keyauth_license(
                    session,
                    guild=interaction.guild,
                    member=interaction.user,
                    key=key,
                )
        except Exception:
            logger.exception("Unexpected error in /code")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description="An unexpected error occurred. Try again later.",
                    color=discord.Color.dark_red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LicenseKeyCog(bot))
